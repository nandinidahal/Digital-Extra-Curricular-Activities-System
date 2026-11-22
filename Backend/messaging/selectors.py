"""
Read-side queries. Everything here is scoped to a viewer: a user can only ever reach
conversations they participate in and messages that are not hidden for them.

Query budget (independent of page size):
* conversation list  : 1 main query (unread count + latest message as subqueries)
                       + 1 participants prefetch + 1 latest-messages fetch + presence (<= 5)
* message page      : 1 main query + 3 prefetches (attachments, reactions, receipts)
"""
from django.conf import settings
from django.db.models import Count, Exists, IntegerField, OuterRef, Prefetch, Q, Subquery, Value
from django.db.models.functions import Coalesce

from friends import services as friends
from friends.validators import available_account_q, is_available

from .exceptions import ConversationNotFound, MessageNotFound
from .models import (
    ConversationParticipant,
    Message,
    MessageReaction,
    MessageReceipt,
    MessageVisibility,
)


def non_friend_message_limit():
    return max(0, int(getattr(settings, "MESSAGING_NON_FRIEND_MESSAGE_LIMIT", 4)))


# ---------------------------------------------------------------------------
# Access
# ---------------------------------------------------------------------------
def get_participation(user, conversation_id):
    """The caller's active membership, or 404 (same error for 'missing' and 'not yours')."""
    participant = (
        ConversationParticipant.objects.select_related("conversation")
        .filter(conversation_id=conversation_id, user=user, is_active=True)
        .first()
    )
    if participant is None:
        raise ConversationNotFound()
    return participant


def other_participants(conversation, user_id):
    return list(
        ConversationParticipant.objects.filter(conversation=conversation, is_active=True)
        .exclude(user_id=user_id)
        .select_related("user")
    )


def visible_messages(user):
    """Messages in the user's active conversations that the user has not hidden."""
    hidden = MessageVisibility.objects.filter(message=OuterRef("pk"), user=user)
    return (
        Message.objects.filter(
            conversation__participants__user=user, conversation__participants__is_active=True
        )
        .exclude(Exists(hidden))
    )


def get_message_for_user(user, message_id, *, for_update=False):
    """A message the user may act on, or 404 (also for other people's conversations)."""
    queryset = visible_messages(user).filter(pk=message_id)
    message = queryset.first()
    if message is None:
        raise MessageNotFound()
    if for_update:
        message = Message.objects.select_for_update().select_related("conversation").get(pk=message.pk)
    return message


# ---------------------------------------------------------------------------
# Pre-friendship limit / permission state
# ---------------------------------------------------------------------------
def messaging_state(user, conversation, other_user=None):
    """
    What the UI needs to decide whether to show the composer or a "become friends" banner:
    {can_message, reason, is_friend, messages_used, messages_allowed, messages_remaining}
    `reason` is one of None, "blocked", "user_unavailable", "message_limit_reached",
    "conversation_inactive". It never reveals who blocked whom.
    """
    if other_user is None:
        others = other_participants(conversation, user.pk)
        other_user = others[0].user if others else None
    limit = non_friend_message_limit()
    state = {
        "can_message": True, "reason": None, "is_friend": False,
        "messages_used": 0, "messages_allowed": limit, "messages_remaining": limit,
    }

    def deny(reason):
        state["can_message"] = False
        state["reason"] = reason
        return state

    if not conversation.is_active:
        return deny("conversation_inactive")
    if other_user is None or not is_available(other_user):
        return deny("user_unavailable")
    if friends.is_blocked_between(user.pk, other_user.pk):
        return deny("blocked")
    if friends.are_friends(user.pk, other_user.pk):
        state.update(is_friend=True, messages_used=None, messages_allowed=None, messages_remaining=None)
        return state
    used = conversation.messages.filter(counts_toward_limit=True).count()
    state["messages_used"] = used
    state["messages_remaining"] = max(0, limit - used)
    if used >= limit:
        return deny("message_limit_reached")
    return state


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------
def unread_receipts(user):
    hidden = MessageVisibility.objects.filter(message=OuterRef("message_id"), user=user)
    return MessageReceipt.objects.filter(
        user=user, read_at__isnull=True, message__is_deleted=False
    ).exclude(Exists(hidden))


def unread_count(user, conversation_id):
    return unread_receipts(user).filter(conversation_id=conversation_id).count()


def total_unread_count(user, include_muted=False):
    mine = ConversationParticipant.objects.filter(user=user, is_active=True)
    if not include_muted:
        mine = mine.filter(is_muted=False)
    # Subquery, not a join: a join on participants would match every member of the
    # conversation and count each receipt once per member.
    return unread_receipts(user).filter(conversation_id__in=mine.values("conversation_id")).count()


def _annotated_participations(user):
    """The user's active participations, annotated with `unread` and `latest_message_id`."""
    hidden = MessageVisibility.objects.filter(message=OuterRef("pk"), user=user)
    latest = (
        Message.objects.filter(conversation_id=OuterRef("conversation_id"))
        .exclude(Exists(hidden))
        .order_by("-created_at", "-id")
        .values("id")[:1]
    )
    unread = (
        unread_receipts(user)
        .filter(conversation_id=OuterRef("conversation_id"))
        .order_by()
        .values("conversation_id")
        .annotate(c=Count("id"))
        .values("c")
    )
    return (
        ConversationParticipant.objects.filter(user=user, is_active=True, conversation__is_active=True)
        .select_related("conversation")
        .annotate(
            latest_message_id=Subquery(latest),
            unread=Coalesce(Subquery(unread, output_field=IntegerField()), Value(0)),
        )
    )


def conversation_list(user, *, archived=False):
    """
    Inbox (archived=False) or archive (archived=True), newest activity first. Conversations
    without messages are only listed for the user who started them.
    """
    return (
        _annotated_participations(user)
        .filter(is_archived=archived)
        .filter(Q(conversation__last_message_at__isnull=False) | Q(conversation__created_by=user))
        .order_by(
            Coalesce("conversation__last_message_at", "conversation__created_at").desc(),
            "-conversation_id",
        )
    )


def conversation_detail(user, conversation_id):
    participation = _annotated_participations(user).filter(conversation_id=conversation_id).first()
    if participation is None:
        raise ConversationNotFound()
    return attach_conversation_extras([participation], user)[0]


def attach_conversation_extras(participations, user):
    """
    Bulk-load what the serializer needs for a page of participations, in a fixed number of
    queries: the other participants (+profiles), the latest messages, and presence.
    Sets `p.others`, `p.latest_message`, `p.presence` on every item.
    """
    from . import presence  # local import keeps module import order simple

    participations = list(participations)
    conversation_ids = [p.conversation_id for p in participations]
    others = {}
    for other in (
        ConversationParticipant.objects.filter(conversation_id__in=conversation_ids, is_active=True)
        .exclude(user=user)
        .select_related("user__profile")
    ):
        others.setdefault(other.conversation_id, []).append(other)
    latest_ids = [p.latest_message_id for p in participations if getattr(p, "latest_message_id", None)]
    latest = Message.objects.select_related("sender").in_bulk(latest_ids)
    other_user_ids = [o.user_id for group in others.values() for o in group]
    presence_map = presence.presence_for(user.pk, other_user_ids)
    for p in participations:
        p.others = others.get(p.conversation_id, [])
        p.latest_message = latest.get(getattr(p, "latest_message_id", None))
        p.presence = presence_map
    return participations


def message_page_queryset(user, conversation_id):
    """History of one conversation for `user` (newest first), with everything prefetched."""
    hidden = MessageVisibility.objects.filter(message=OuterRef("pk"), user=user)
    return (
        Message.objects.filter(conversation_id=conversation_id)
        .exclude(Exists(hidden))
        .select_related("sender__profile", "reply_to__sender")
        .prefetch_related(
            "attachments",
            Prefetch("reactions", queryset=MessageReaction.objects.only("message_id", "user_id", "reaction_type")),
            Prefetch("receipts", queryset=MessageReceipt.objects.all()),
        )
        .order_by("-created_at", "-id")
    )


def message_page_queryset_unscoped():
    return (
        Message.objects.select_related("sender__profile", "reply_to__sender")
        .prefetch_related("attachments", "reactions", "receipts")
    )


def search_messages(user, conversation_id, query):
    return (
        message_page_queryset(user, conversation_id)
        .filter(is_deleted=False, content__icontains=query)
    )


def available_user_or_none(user_id):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.filter(available_account_q()).filter(pk=user_id).first()
