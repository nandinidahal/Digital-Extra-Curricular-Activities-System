"""
All Friends business rules live here. Views stay thin and other modules import from here.

PUBLIC INTEGRATION API (safe for Social, Messaging, Search, Notifications to import)
------------------------------------------------------------------------------------
    are_friends(a, b)                         -> bool
    has_blocked(blocker, blocked)             -> bool   (directional)
    is_blocked_between(a, b)                  -> bool   (either direction)
    can_interact(a, b)                        -> bool   (different users and no block either way)
    get_friend_ids(user)                      -> set[UUID]
    get_blocked_user_ids(user)                -> set[UUID]   users `user` has blocked
    get_blocked_by_user_ids(user)             -> set[UUID]   users who blocked `user`
    get_hidden_user_ids(user)                 -> set[UUID]   union of both: never show these to `user`
    get_relationship_statuses(viewer, ids)    -> {user_id: status}   (bulk, 3 queries total)
    get_relationship(viewer, other)           -> dict with status flags for one user
    discoverable_users(viewer)                -> User queryset for the future Search module
    available_users()                         -> active + verified users

Concurrency: every state-changing operation runs in a transaction and first locks the two user
rows (always in primary-key order, so two operations can not deadlock) with SELECT ... FOR UPDATE.
All operations on the same pair are therefore serialised on PostgreSQL. Database constraints
(unique + check) are the second line of defence.
"""
import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from profiles.models import Profile

from . import signals
from .exceptions import (
    AccountUnavailable,
    AlreadyBlocked,
    AlreadyFriends,
    BlockNotFound,
    CannotTargetSelf,
    NotFriends,
    NotRequestReceiver,
    NotRequestSender,
    RequestAlreadySent,
    RequestCooldown,
    RequestNotAllowed,
    RequestNotFound,
    RequestNotPending,
    UserNotFound,
)
from .models import FriendRequest, Friendship, UserBlock
from .validators import available_account_q, is_available

logger = logging.getLogger("friends")

# Relationship statuses (the contract with the frontend)
SELF = "self"
FRIENDS = "friends"
REQUEST_SENT = "request_sent"
REQUEST_RECEIVED = "request_received"
BLOCKED_BY_ME = "blocked_by_me"
BLOCKED_YOU = "blocked_you"
NOT_FRIENDS = "not_friends"

PENDING = FriendRequest.Status.PENDING


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _users():
    return get_user_model().objects


def _uuid(value):
    """Accepts a UUID, a string, or anything with a `.pk` (a user)."""
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(getattr(value, "pk", value)))


def _lock_users(*user_ids):
    """Lock the user rows of one pair, always in the same order (deadlock-free)."""
    ids = sorted({_uuid(i) for i in user_ids}, key=lambda u: u.int)
    list(_users().select_for_update().filter(pk__in=ids).order_by("pk"))


def _emit(signal, sender, **kwargs):
    """Send `signal` after the current transaction commits; receiver errors are only logged."""

    def _send():
        for receiver, result in signal.send_robust(sender=sender, **kwargs):
            if isinstance(result, Exception):
                logger.error("Friends signal receiver %r failed: %r", receiver, result)

    transaction.on_commit(_send)


def available_users():
    return _users().filter(available_account_q())


def get_available_user(user_id):
    user = available_users().filter(pk=_uuid(user_id)).first()
    if user is None:
        raise UserNotFound()
    return user


def _require_available_actor(user):
    if not is_available(user):
        raise AccountUnavailable()


# ---------------------------------------------------------------------------
# Read API for other modules
# ---------------------------------------------------------------------------
def are_friends(a, b):
    a, b = _uuid(a), _uuid(b)
    if a == b:
        return False
    low, high = Friendship.normalize(a, b)
    return Friendship.objects.filter(user1_id=low, user2_id=high).exists()


def has_blocked(blocker, blocked):
    return UserBlock.objects.filter(blocker_id=_uuid(blocker), blocked_id=_uuid(blocked)).exists()


def is_blocked_between(a, b):
    a, b = _uuid(a), _uuid(b)
    return UserBlock.objects.filter(
        Q(blocker_id=a, blocked_id=b) | Q(blocker_id=b, blocked_id=a)
    ).exists()


def can_interact(a, b):
    """True when the two users are different people and neither has blocked the other."""
    return _uuid(a) != _uuid(b) and not is_blocked_between(a, b)


def get_friend_ids(user):
    user_id = _uuid(user)
    ids = set(Friendship.objects.filter(user1_id=user_id).values_list("user2_id", flat=True))
    ids.update(Friendship.objects.filter(user2_id=user_id).values_list("user1_id", flat=True))
    return ids


def get_blocked_user_ids(user):
    return set(UserBlock.objects.filter(blocker_id=_uuid(user)).values_list("blocked_id", flat=True))


def get_blocked_by_user_ids(user):
    return set(UserBlock.objects.filter(blocked_id=_uuid(user)).values_list("blocker_id", flat=True))


def get_hidden_user_ids(user):
    """Everyone `user` must not see or interact with because of a block in either direction."""
    return get_blocked_user_ids(user) | get_blocked_by_user_ids(user)


def _relationships(viewer_id, other_ids):
    """{other_id: (status, pending_request_id | None)} using exactly three queries."""
    requested = {_uuid(o) for o in other_ids}
    others = requested - {viewer_id}
    found = {}
    if others:
        # Lowest precedence first; later steps overwrite earlier ones.
        pending = (
            FriendRequest.objects.filter(status=PENDING)
            .filter(
                Q(sender_id=viewer_id, receiver_id__in=others)
                | Q(receiver_id=viewer_id, sender_id__in=others)
            )
            .values_list("id", "sender_id", "receiver_id")
        )
        for request_id, sender_id, receiver_id in pending:
            if sender_id == viewer_id:
                found[receiver_id] = (REQUEST_SENT, request_id)
            else:
                found[sender_id] = (REQUEST_RECEIVED, request_id)

        friendships = Friendship.objects.filter(
            Q(user1_id=viewer_id, user2_id__in=others) | Q(user2_id=viewer_id, user1_id__in=others)
        ).values_list("user1_id", "user2_id")
        for user1_id, user2_id in friendships:
            found[user2_id if user1_id == viewer_id else user1_id] = (FRIENDS, None)

        blocks = UserBlock.objects.filter(
            Q(blocker_id=viewer_id, blocked_id__in=others)
            | Q(blocked_id=viewer_id, blocker_id__in=others)
        ).values_list("blocker_id", "blocked_id")
        for blocker_id, blocked_id in blocks:
            if blocker_id == viewer_id:
                found[blocked_id] = (BLOCKED_BY_ME, None)
            elif found.get(blocker_id, (None,))[0] != BLOCKED_BY_ME:
                found[blocker_id] = (BLOCKED_YOU, None)

    result = {}
    for other_id in requested:
        if other_id == viewer_id:
            result[other_id] = (SELF, None)
        else:
            result[other_id] = found.get(other_id, (NOT_FRIENDS, None))
    return result


def _public_status(status):
    """Optionally hide the fact that somebody blocked the viewer (setting, default: reveal)."""
    if status == BLOCKED_YOU and not getattr(settings, "FRIENDS_REVEAL_BLOCKED_BY_OTHER", True):
        return NOT_FRIENDS
    return status


def get_relationship_statuses(viewer, other_ids):
    """Bulk status for lists (search results, feeds, ...). Three queries however long the list."""
    relationships = _relationships(_uuid(viewer), other_ids)
    return {user_id: _public_status(status) for user_id, (status, _rid) in relationships.items()}


def get_relationship(viewer, other):
    other_id = _uuid(other)
    status, request_id = _relationships(_uuid(viewer), [other_id])[other_id]
    status = _public_status(status)
    return {
        "user_id": other_id,
        "friendship_status": status,
        "is_friend": status == FRIENDS,
        "request_sent": status == REQUEST_SENT,
        "request_received": status == REQUEST_RECEIVED,
        "request_id": request_id if status in (REQUEST_SENT, REQUEST_RECEIVED) else None,
        "blocked": status in (BLOCKED_BY_ME, BLOCKED_YOU),
    }


def discoverable_users(viewer):
    """
    Users `viewer` may be shown in a people list: available accounts, not the viewer, no block in
    either direction, and not users who set their whole profile to private.
    The future Search module should start from this queryset and add its own filters.
    """
    return (
        available_users()
        .exclude(pk=_uuid(viewer))
        .exclude(pk__in=get_hidden_user_ids(viewer))
        .exclude(profile__profile_visibility=Profile.Visibility.PRIVATE)
    )


# ---------------------------------------------------------------------------
# List querysets
# ---------------------------------------------------------------------------
def received_requests(user):
    return (
        FriendRequest.objects.filter(receiver=user, status=PENDING)
        .filter(available_account_q("sender__"))
        .exclude(sender_id__in=get_hidden_user_ids(user))
        .select_related("sender__profile")
        .order_by("-created_at", "-id")
    )


def sent_requests(user):
    return (
        FriendRequest.objects.filter(sender=user, status=PENDING)
        .filter(available_account_q("receiver__"))
        .exclude(receiver_id__in=get_hidden_user_ids(user))
        .select_related("receiver__profile")
        .order_by("-created_at", "-id")
    )


def friendships_of(user):
    """Accepted friendships of `user`, newest first, other side available and not blocked."""
    hidden = get_hidden_user_ids(user)
    return (
        Friendship.objects.filter(
            Q(user1=user) & available_account_q("user2__")
            | Q(user2=user) & available_account_q("user1__")
        )
        .exclude(user1_id__in=hidden)
        .exclude(user2_id__in=hidden)
        .select_related("user1__profile", "user2__profile")
        .order_by("-created_at", "-id")
    )


def friend_count(user):
    return friendships_of(user).count()


def _friends_q(user_id):
    return Q(pk__in=Friendship.objects.filter(user1_id=user_id).values("user2_id")) | Q(
        pk__in=Friendship.objects.filter(user2_id=user_id).values("user1_id")
    )


def mutual_friends(viewer, target):
    """Users who are friends with BOTH `viewer` and `target` (available accounts only)."""
    viewer_id, target_id = _uuid(viewer), _uuid(target)
    return (
        available_users()
        .filter(_friends_q(viewer_id))
        .filter(_friends_q(target_id))
        .exclude(pk__in=get_hidden_user_ids(viewer_id))
        .select_related("profile")
        .order_by("username", "id")
    )


def blocked_users(user):
    return (
        UserBlock.objects.filter(blocker=user)
        .filter(available_account_q("blocked__"))
        .select_related("blocked__profile")
        .order_by("-created_at", "-id")
    )


def get_request_for_participant(user, request_id):
    """Strangers get 'not found' so request ids can not be probed."""
    friend_request = (
        FriendRequest.objects.filter(pk=request_id)
        .filter(Q(sender=user) | Q(receiver=user))
        .first()
    )
    if friend_request is None:
        raise RequestNotFound()
    return friend_request


# ---------------------------------------------------------------------------
# Friend requests
# ---------------------------------------------------------------------------
@dataclass
class SendResult:
    friend_request: FriendRequest
    friendship: Friendship | None = None
    auto_accepted: bool = False


def _accept_locked(friend_request):
    """Create the friendship and mark the request accepted. Caller holds the pair lock."""
    low, high = Friendship.normalize(friend_request.sender_id, friend_request.receiver_id)
    friendship, _created = Friendship.objects.get_or_create(user1_id=low, user2_id=high)
    now = timezone.now()
    friend_request.status = FriendRequest.Status.ACCEPTED
    friend_request.responded_at = now
    friend_request.save(update_fields=["status", "responded_at", "updated_at"])
    return friendship


def _check_rejection_cooldown(sender_id, receiver_id):
    hours = getattr(settings, "FRIENDS_REJECTION_COOLDOWN_HOURS", 24)
    if not hours:
        return
    last = (
        FriendRequest.objects.filter(
            sender_id=sender_id, receiver_id=receiver_id, status=FriendRequest.Status.REJECTED
        )
        .order_by("-responded_at")
        .values_list("responded_at", flat=True)
        .first()
    )
    if last is not None:
        remaining = (last + timedelta(hours=hours) - timezone.now()).total_seconds()
        if remaining > 0:
            raise RequestCooldown(retry_after=int(remaining) + 1)


@transaction.atomic
def send_friend_request(sender, receiver_id):
    """
    Order of checks (the first failing one wins):
    self -> receiver exists/available -> blocked -> already friends -> reverse pending request
    (auto-accepted) -> duplicate pending -> cooldown after a rejection.
    """
    _require_available_actor(sender)
    receiver_id = _uuid(receiver_id)
    if receiver_id == sender.pk:
        raise CannotTargetSelf("You cannot send a friend request to yourself.")
    receiver = get_available_user(receiver_id)

    _lock_users(sender.pk, receiver.pk)

    if is_blocked_between(sender.pk, receiver.pk):
        raise RequestNotAllowed()
    if are_friends(sender.pk, receiver.pk):
        raise AlreadyFriends()

    reverse = (
        FriendRequest.objects.select_for_update()
        .filter(sender_id=receiver.pk, receiver_id=sender.pk, status=PENDING)
        .first()
    )
    if reverse is not None:
        # Both people want the connection: accept the older request instead of creating a new one.
        friendship = _accept_locked(reverse)
        _emit(
            signals.friend_request_accepted, FriendRequest,
            friend_request=reverse, friendship=friendship, auto_accepted=True,
        )
        return SendResult(reverse, friendship, auto_accepted=True)

    if FriendRequest.objects.filter(
        sender_id=sender.pk, receiver_id=receiver.pk, status=PENDING
    ).exists():
        raise RequestAlreadySent()

    _check_rejection_cooldown(sender.pk, receiver.pk)

    try:
        with transaction.atomic():
            friend_request = FriendRequest.objects.create(sender=sender, receiver=receiver)
    except IntegrityError:  # the DB constraints caught a race the lock did not
        raise RequestAlreadySent()
    _emit(signals.friend_request_sent, FriendRequest, friend_request=friend_request)
    return SendResult(friend_request)


def _lock_pending_request(user, request_id, role):
    """
    Lock the pair, re-read the request FOR UPDATE and validate role and status.
    Everything is decided from the database row and `user` - never from client data.
    """
    pair = FriendRequest.objects.filter(pk=request_id).values_list("sender_id", "receiver_id").first()
    if pair is None or user.pk not in pair:
        raise RequestNotFound()
    _lock_users(*pair)
    friend_request = FriendRequest.objects.select_for_update().filter(pk=request_id).first()
    if friend_request is None:
        raise RequestNotFound()
    if role == "receiver" and friend_request.receiver_id != user.pk:
        raise NotRequestReceiver()
    if role == "sender" and friend_request.sender_id != user.pk:
        raise NotRequestSender()
    if friend_request.status != PENDING:
        raise RequestNotPending(friend_request.status)
    return friend_request


@transaction.atomic
def accept_friend_request(user, request_id):
    _require_available_actor(user)
    friend_request = _lock_pending_request(user, request_id, "receiver")
    if (
        available_users().filter(pk__in=[friend_request.sender_id, friend_request.receiver_id]).count()
        != 2
    ):
        raise UserNotFound()
    if is_blocked_between(friend_request.sender_id, friend_request.receiver_id):
        raise RequestNotAllowed()
    friendship = _accept_locked(friend_request)
    _emit(
        signals.friend_request_accepted, FriendRequest,
        friend_request=friend_request, friendship=friendship, auto_accepted=False,
    )
    return friend_request, friendship


@transaction.atomic
def reject_friend_request(user, request_id):
    _require_available_actor(user)
    friend_request = _lock_pending_request(user, request_id, "receiver")
    friend_request.status = FriendRequest.Status.REJECTED
    friend_request.responded_at = timezone.now()
    friend_request.save(update_fields=["status", "responded_at", "updated_at"])
    _emit(signals.friend_request_rejected, FriendRequest, friend_request=friend_request)
    return friend_request


@transaction.atomic
def cancel_friend_request(user, request_id):
    _require_available_actor(user)
    friend_request = _lock_pending_request(user, request_id, "sender")
    friend_request.status = FriendRequest.Status.CANCELLED
    friend_request.responded_at = timezone.now()
    friend_request.save(update_fields=["status", "responded_at", "updated_at"])
    _emit(
        signals.friend_request_cancelled, FriendRequest,
        friend_request=friend_request, reason="cancelled_by_sender",
    )
    return friend_request


# ---------------------------------------------------------------------------
# Friendships
# ---------------------------------------------------------------------------
@transaction.atomic
def remove_friend(user, other_id):
    other_id = _uuid(other_id)
    if other_id == user.pk:
        raise CannotTargetSelf("You cannot remove yourself.")
    _lock_users(user.pk, other_id)
    low, high = Friendship.normalize(user.pk, other_id)
    deleted, _ = Friendship.objects.filter(user1_id=low, user2_id=high).delete()
    if not deleted:
        raise NotFriends()
    _emit(
        signals.friend_removed, Friendship,
        user_id=user.pk, other_user_id=other_id, reason="removed",
    )


# ---------------------------------------------------------------------------
# Blocking
#
# POLICY: blocking someone (1) deletes an existing friendship, (2) cancels pending requests in
# BOTH directions and (3) forbids new requests until the block is removed. Unblocking only removes
# the block row: friendship and requests are NOT restored and nothing is sent automatically.
# ---------------------------------------------------------------------------
@transaction.atomic
def block_user(blocker, blocked_id):
    _require_available_actor(blocker)
    blocked_id = _uuid(blocked_id)
    if blocked_id == blocker.pk:
        raise CannotTargetSelf("You cannot block yourself.")
    blocked = get_available_user(blocked_id)

    _lock_users(blocker.pk, blocked.pk)

    if has_blocked(blocker.pk, blocked.pk):
        raise AlreadyBlocked()
    try:
        with transaction.atomic():
            block = UserBlock.objects.create(blocker=blocker, blocked=blocked)
    except IntegrityError:
        raise AlreadyBlocked()

    low, high = Friendship.normalize(blocker.pk, blocked.pk)
    friendship_removed = Friendship.objects.filter(user1_id=low, user2_id=high).delete()[0] > 0

    now = timezone.now()
    requests_cancelled = (
        FriendRequest.objects.filter(status=PENDING)
        .filter(
            Q(sender_id=blocker.pk, receiver_id=blocked.pk)
            | Q(sender_id=blocked.pk, receiver_id=blocker.pk)
        )
        .update(status=FriendRequest.Status.CANCELLED, responded_at=now, updated_at=now)
    )

    if friendship_removed:
        _emit(
            signals.friend_removed, Friendship,
            user_id=blocker.pk, other_user_id=blocked.pk, reason="blocked",
        )
    _emit(
        signals.user_blocked, UserBlock,
        block=block, friendship_removed=friendship_removed, requests_cancelled=requests_cancelled,
    )
    return block


@transaction.atomic
def unblock_user(blocker, blocked_id):
    """Only rows owned by `blocker` are ever touched, so nobody can lift a block placed on them."""
    blocked_id = _uuid(blocked_id)
    _lock_users(blocker.pk, blocked_id)
    deleted, _ = UserBlock.objects.filter(blocker_id=blocker.pk, blocked_id=blocked_id).delete()
    if not deleted:
        raise BlockNotFound()
    _emit(signals.user_unblocked, UserBlock, blocker_id=blocker.pk, blocked_id=blocked_id)
