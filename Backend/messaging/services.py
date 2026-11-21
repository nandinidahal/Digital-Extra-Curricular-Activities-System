"""
Messaging rules, all enforced here (never in the frontend):

* only participants can touch a conversation (everyone else gets 404, so ids can't be probed)
* one conversation per pair of users
* NOT friends -> at most MESSAGING_PRE_FRIEND_LIMIT (4) messages in total, both directions combined
* friends -> unlimited
* blocked pair / inactive account -> no sending
The 4-message check-and-increment runs while holding a row lock on the conversation
(SELECT ... FOR UPDATE), so simultaneous sends are serialised and can never exceed the limit.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError

from friends.selectors import are_friends, is_blocked_between, ordered_pair
from friends.services import Conflict, RelationshipState, get_relationship
from social.models import NotificationType
from social.notifications import notify

from .events import publish
from .models import Conversation, Message

User = get_user_model()


def pre_friend_limit():
    return int(getattr(settings, "MESSAGING_PRE_FRIEND_LIMIT", 4))


def edit_window():
    return timedelta(seconds=int(getattr(settings, "MESSAGE_EDIT_WINDOW_SECONDS", 15 * 60)))


class MessageLimitReached(APIException):
    status_code = 403
    default_code = "message_limit_reached"

    def __init__(self, limit):
        super().__init__(detail={
            "detail": (f"You and this user have reached the limit of {limit} messages. "
                       "Become friends to keep chatting."),
            "code": self.default_code,
            "limit": limit,
            "action": "send_friend_request",
        })


def conversation_state(user, conv, other, rel_state):
    """What the UI needs to enable/disable the composer. Pure function: no queries."""
    limit = pre_friend_limit()
    is_friend = rel_state == RelationshipState.FRIENDS
    state = {"is_friend": is_friend, "relationship": rel_state, "can_send": True, "reason": None,
             "messages_remaining": None, "limit": None, "action": None, "notice": None}
    if not user.is_active:
        state.update(can_send=False, reason="inactive_sender", notice="Your account is deactivated.")
    elif other is None or not other.is_active:
        state.update(can_send=False, reason="recipient_unavailable", notice="This user is not available.")
    elif rel_state in (RelationshipState.BLOCKED, RelationshipState.BLOCKED_BY):
        state.update(can_send=False, reason="blocked", notice="You can't send messages to this user.")
    elif not is_friend:
        remaining = max(limit - conv.restricted_message_count, 0)
        state.update(limit=limit, messages_remaining=remaining)
        if remaining == 0:
            action = {"NOT_FRIENDS": "send_friend_request", "REQUEST_SENT": "request_pending",
                      "REQUEST_RECEIVED": "accept_friend_request"}.get(rel_state, "send_friend_request")
            state.update(can_send=False, reason="message_limit_reached", action=action,
                         notice=f"You've reached the {limit}-message limit. Become friends to continue chatting.")
    return state


def get_or_create_conversation(user, other_id):
    if user.pk == other_id:
        raise DRFValidationError({"recipient_id": ["You cannot message yourself."]})
    other = User.objects.filter(pk=other_id, is_active=True).first()
    if other is None:
        raise NotFound("User not found.")
    if not user.is_active:
        raise PermissionDenied("Your account is deactivated.")
    if is_blocked_between(user, other):
        raise PermissionDenied("You can't message this user.")
    low, high = ordered_pair(user.pk, other.pk)
    conv, _ = Conversation.objects.get_or_create(user_low_id=low, user_high_id=high)
    return conv


def get_conversation_for(user, conversation_id):
    conv = (Conversation.objects.select_related("user_low", "user_low__user_profile", "user_high", "user_high__user_profile",
                                                "last_message").filter(pk=conversation_id)
            .filter(Q(user_low=user) | Q(user_high=user)).first())
    if conv is None:
        raise NotFound("Conversation not found.")
    return conv


def send_message(user, conversation_id, body):
    body = (body or "").strip()
    if not body:
        raise DRFValidationError({"body": ["Message cannot be empty."]})
    if len(body) > 2000:
        raise DRFValidationError({"body": ["Message is too long (max 2000 characters)."]})

    with transaction.atomic():
        # row lock: concurrent sends in this conversation queue up here
        conv = (Conversation.objects.select_for_update().filter(pk=conversation_id)
                .filter(Q(user_low=user) | Q(user_high=user)).first())
        if conv is None:
            raise NotFound("Conversation not found.")
        other = User.objects.filter(pk=conv.other_user_id(user.pk)).first()

        if not user.is_active:
            raise PermissionDenied("Your account is deactivated.")
        if other is None or not other.is_active:
            raise PermissionDenied("This user is not available.")
        if is_blocked_between(user, other):
            raise PermissionDenied("You can't send messages to this user.")

        if not are_friends(user, other):
            limit = pre_friend_limit()
            if conv.restricted_message_count >= limit:
                raise MessageLimitReached(limit)
            conv.restricted_message_count += 1

        msg = Message.objects.create(conversation=conv, sender=user, body=body)
        conv.last_message = msg
        conv.last_message_at = msg.created_at
        conv.save(update_fields=["restricted_message_count", "last_message", "last_message_at"])

    notify(other, user, NotificationType.NEW_MESSAGE, target_id=conv.pk)
    publish([other.pk], "message.new", {"conversation_id": conv.pk, "message_id": msg.pk})
    return msg


def _own_message(user, message_id):
    msg = Message.objects.select_related("conversation").filter(pk=message_id, sender=user).first()
    if msg is None:
        # also covers "someone else's message": don't confirm it exists
        raise NotFound("Message not found.")
    return msg


def edit_message(user, message_id, body):
    body = (body or "").strip()
    if not body or len(body) > 2000:
        raise DRFValidationError({"body": ["Message must be 1-2000 characters."]})
    msg = _own_message(user, message_id)
    if msg.deleted_at:
        raise Conflict("Deleted messages cannot be edited.")
    if timezone.now() - msg.created_at > edit_window():
        raise PermissionDenied("Messages can only be edited for a short time after sending.")
    other_id = msg.conversation.other_user_id(user.pk)
    if is_blocked_between(user, other_id):
        raise PermissionDenied("You can't edit messages in this conversation.")
    msg.body = body
    msg.edited_at = timezone.now()
    msg.save(update_fields=["body", "edited_at"])
    publish([other_id], "message.updated", {"conversation_id": msg.conversation_id, "message_id": msg.pk})
    return msg


def delete_message(user, message_id):
    msg = _own_message(user, message_id)
    if msg.deleted_at is None:
        msg.body = ""
        msg.deleted_at = timezone.now()
        msg.save(update_fields=["body", "deleted_at"])
        publish([msg.conversation.other_user_id(user.pk)], "message.deleted",
                {"conversation_id": msg.conversation_id, "message_id": msg.pk})
    return msg


def mark_read(user, conversation_id):
    conv = get_conversation_for(user, conversation_id)
    n = (Message.objects.filter(conversation=conv, read_at__isnull=True).exclude(sender=user)
         .update(read_at=timezone.now()))
    if n:
        publish([conv.other_user_id(user.pk)], "messages.read", {"conversation_id": conv.pk})
    return n


def relationship_state_for(user, other):
    return get_relationship(user, other)["state"]
