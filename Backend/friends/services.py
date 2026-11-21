"""
Friend-request / friendship state machine.

Concurrency: every mutating operation runs in a transaction and first takes row locks on BOTH
users (ordered by id, so two opposing requests can't deadlock). That serialises all activity
for a given pair. Database constraints (unique friendship pair, one pending request per pair)
are the safety net behind the locks.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, PermissionDenied

from social.models import NotificationType
from social.notifications import clear_notification, notify

from .models import Block, FriendRequest, Friendship, RequestStatus
from .selectors import are_friends, ordered_pair
from .signals import friendship_removed

User = get_user_model()


class Conflict(APIException):
    status_code = 409
    default_detail = "This action conflicts with the current state."
    default_code = "conflict"


class RelationshipState:
    NOT_FRIENDS = "NOT_FRIENDS"
    REQUEST_SENT = "REQUEST_SENT"
    REQUEST_RECEIVED = "REQUEST_RECEIVED"
    FRIENDS = "FRIENDS"
    BLOCKED = "BLOCKED"          # the viewer blocked the other user
    BLOCKED_BY = "BLOCKED_BY"    # the other user blocked the viewer (never reveal who blocked whom in the UI)


def resend_cooldown():
    return timedelta(days=getattr(settings, "FRIEND_REQUEST_RESEND_COOLDOWN_DAYS", 7))


def _lock_users(a_id, b_id):
    """Row-lock both users in a stable order. Must be called inside transaction.atomic()."""
    low, high = ordered_pair(a_id, b_id)
    list(User.objects.select_for_update().filter(pk__in=[low, high]).order_by("pk").values_list("pk", flat=True))


def get_relationship(viewer, other):
    """
    Returns {"state": ..., "request_id": ...}. Priority: BLOCKED > FRIENDS > pending request > NOT_FRIENDS.
    """
    if viewer.pk == other.pk:
        return {"state": "SELF", "request_id": None}
    if Block.objects.filter(blocker=viewer, blocked=other).exists():
        return {"state": RelationshipState.BLOCKED, "request_id": None}
    if Block.objects.filter(blocker=other, blocked=viewer).exists():
        return {"state": RelationshipState.BLOCKED_BY, "request_id": None}
    if are_friends(viewer, other):
        return {"state": RelationshipState.FRIENDS, "request_id": None}
    low, high = ordered_pair(viewer.pk, other.pk)
    pending = FriendRequest.objects.filter(pair_low=low, pair_high=high, status=RequestStatus.PENDING).first()
    if pending:
        state = RelationshipState.REQUEST_SENT if pending.sender_id == viewer.pk else RelationshipState.REQUEST_RECEIVED
        return {"state": state, "request_id": pending.pk}
    return {"state": RelationshipState.NOT_FRIENDS, "request_id": None}


def relationship_states(viewer, user_ids):
    """Bulk version for lists: {user_id: state}. Four queries total, independent of list size."""
    user_ids = list(user_ids)
    states = {uid: RelationshipState.NOT_FRIENDS for uid in user_ids}
    for fr in FriendRequest.objects.filter(status=RequestStatus.PENDING).filter(
        Q(sender=viewer, receiver_id__in=user_ids) | Q(receiver=viewer, sender_id__in=user_ids)
    ):
        if fr.sender_id == viewer.pk:
            states[fr.receiver_id] = RelationshipState.REQUEST_SENT
        else:
            states[fr.sender_id] = RelationshipState.REQUEST_RECEIVED
    for f in Friendship.objects.filter(Q(user_low=viewer, user_high_id__in=user_ids) |
                                       Q(user_high=viewer, user_low_id__in=user_ids)):
        states[f.user_high_id if f.user_low_id == viewer.pk else f.user_low_id] = RelationshipState.FRIENDS
    for b in Block.objects.filter(Q(blocker=viewer, blocked_id__in=user_ids) |
                                  Q(blocked=viewer, blocker_id__in=user_ids)):
        if b.blocker_id == viewer.pk:
            states[b.blocked_id] = RelationshipState.BLOCKED
        else:
            states[b.blocker_id] = RelationshipState.BLOCKED_BY
    return states


def _create_friendship(a_id, b_id):
    low, high = ordered_pair(a_id, b_id)
    friendship, _ = Friendship.objects.get_or_create(user_low_id=low, user_high_id=high)
    return friendship


def send_request(sender, receiver_id):
    """
    Returns (friend_request, auto_accepted). If the receiver already has a pending request to the
    sender, the two intents match and we simply make them friends (no duplicate / crossed requests).
    """
    if sender.pk == receiver_id:
        raise Conflict("You cannot send a friend request to yourself.")
    with transaction.atomic():
        _lock_users(sender.pk, receiver_id)
        receiver = User.objects.filter(pk=receiver_id, is_active=True).first()
        if receiver is None:
            raise NotFound("User not found.")
        if Block.objects.filter(Q(blocker=sender, blocked=receiver) | Q(blocker=receiver, blocked=sender)).exists():
            raise PermissionDenied("You can't send a friend request to this user.")
        if are_friends(sender, receiver):
            raise Conflict("You are already friends.")

        low, high = ordered_pair(sender.pk, receiver.pk)
        pending = FriendRequest.objects.filter(pair_low=low, pair_high=high, status=RequestStatus.PENDING).first()
        if pending:
            if pending.sender_id == sender.pk:
                raise Conflict("A friend request is already pending.")
            # crossed requests: accept theirs
            return _accept_locked(pending, sender), True

        last_rejected = (FriendRequest.objects.filter(sender=sender, receiver=receiver, status=RequestStatus.REJECTED)
                         .order_by("-responded_at").first())
        if last_rejected and last_rejected.responded_at and timezone.now() < last_rejected.responded_at + resend_cooldown():
            raise Conflict("You can send another request to this user later.")

        try:
            with transaction.atomic():  # savepoint, so the unique-constraint safety net can't poison the outer txn
                fr = FriendRequest.objects.create(sender=sender, receiver=receiver)
        except IntegrityError:
            raise Conflict("A friend request is already pending.")
        notify(receiver, sender, NotificationType.FRIEND_REQUEST, target_id=fr.pk)
        return fr, False


def _accept_locked(fr, acting_user):
    fr.status = RequestStatus.ACCEPTED
    fr.responded_at = timezone.now()
    fr.save(update_fields=["status", "responded_at"])
    _create_friendship(fr.sender_id, fr.receiver_id)
    clear_notification(fr.receiver, fr.sender, NotificationType.FRIEND_REQUEST, target_id=fr.pk)
    notify(fr.sender, fr.receiver, NotificationType.FRIEND_ACCEPTED, target_id=fr.pk)
    return fr


def _get_pending_for_update(request_id):
    fr = FriendRequest.objects.select_for_update().filter(pk=request_id).first()
    if fr is None:
        raise NotFound("Friend request not found.")
    return fr


def respond(user, request_id, action):
    """action: accept | reject | ignore (receiver) or cancel (sender)."""
    with transaction.atomic():
        fr = FriendRequest.objects.filter(pk=request_id).first()
        if fr is None:
            raise NotFound("Friend request not found.")
        # Only the two parties may even learn that the request exists.
        if user.pk not in (fr.sender_id, fr.receiver_id):
            raise NotFound("Friend request not found.")
        _lock_users(fr.sender_id, fr.receiver_id)
        fr = _get_pending_for_update(request_id)
        if fr.status != RequestStatus.PENDING:
            raise Conflict("This friend request is no longer pending.")

        if action == "cancel":
            if fr.sender_id != user.pk:
                raise PermissionDenied("Only the sender can cancel a request.")
            fr.status = RequestStatus.CANCELLED
            fr.responded_at = timezone.now()
            fr.save(update_fields=["status", "responded_at"])
            clear_notification(fr.receiver, fr.sender, NotificationType.FRIEND_REQUEST, target_id=fr.pk)
            return fr

        if fr.receiver_id != user.pk:
            raise PermissionDenied("Only the receiver can respond to a request.")
        if Block.objects.filter(Q(blocker_id=fr.sender_id, blocked_id=fr.receiver_id) |
                                Q(blocker_id=fr.receiver_id, blocked_id=fr.sender_id)).exists():
            raise PermissionDenied("This request can no longer be answered.")

        if action == "accept":
            if not fr.sender.is_active:
                raise Conflict("This user is no longer available.")
            return _accept_locked(fr, user)
        if action == "reject":
            fr.status = RequestStatus.REJECTED
            fr.responded_at = timezone.now()
            fr.save(update_fields=["status", "responded_at"])
            clear_notification(fr.receiver, fr.sender, NotificationType.FRIEND_REQUEST, target_id=fr.pk)
            return fr
        if action == "ignore":
            fr.is_ignored = True
            fr.save(update_fields=["is_ignored"])
            return fr
        raise Conflict("Unknown action.")


def remove_friend(user, other_id):
    with transaction.atomic():
        _lock_users(user.pk, other_id)
        low, high = ordered_pair(user.pk, other_id)
        deleted, _ = Friendship.objects.filter(user_low_id=low, user_high_id=high).delete()
        if not deleted:
            raise NotFound("You are not friends with this user.")
        friendship_removed.send(sender=Friendship, user_ids=(low, high))


def block_user(blocker, target_id):
    if blocker.pk == target_id:
        raise Conflict("You cannot block yourself.")
    with transaction.atomic():
        _lock_users(blocker.pk, target_id)
        target = User.objects.filter(pk=target_id).first()
        if target is None:
            raise NotFound("User not found.")
        block, _ = Block.objects.get_or_create(blocker=blocker, blocked=target)
        low, high = ordered_pair(blocker.pk, target_id)
        Friendship.objects.filter(user_low_id=low, user_high_id=high).delete()
        FriendRequest.objects.filter(pair_low=low, pair_high=high, status=RequestStatus.PENDING).update(
            status=RequestStatus.CANCELLED, responded_at=timezone.now())
        friendship_removed.send(sender=Friendship, user_ids=(low, high))
        return block


def unblock_user(blocker, target_id):
    deleted, _ = Block.objects.filter(blocker=blocker, blocked_id=target_id).delete()
    if not deleted:
        raise NotFound("You have not blocked this user.")
