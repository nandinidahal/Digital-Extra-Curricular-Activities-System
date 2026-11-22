"""
After-commit side effects of every Messaging write: real-time events and integration signals.
Services schedule these with transaction.on_commit, so nothing is announced for a write that
was rolled back.

Who receives what (decided here, per event, from the database - never from the client):
* new / edited message, reactions  -> participants with no block between them and the actor
* delete for everyone              -> all participants (removing content is always allowed)
* delete for me / settings changes -> only the acting user's other devices
* delivered / read receipts        -> the message senders, unless a block exists
"""
import logging

from friends import services as friends

from . import realtime, signals
from .models import Conversation, ConversationParticipant, Message, MessageReaction

logger = logging.getLogger("messaging")


def _emit(signal, **kwargs):
    for receiver, result in signal.send_robust(sender=Message, **kwargs):
        if isinstance(result, Exception):
            logger.error("Messaging signal receiver %r failed: %r", receiver, result)


def _participants(conversation_id):
    return list(
        ConversationParticipant.objects.filter(conversation_id=conversation_id, is_active=True)
        .select_related("user")
    )


def _not_blocked_with(actor_id, participants):
    """Participants who may receive real-time events caused by `actor_id`."""
    if actor_id is None:
        return participants
    hidden = friends.get_hidden_user_ids(actor_id)
    return [p for p in participants if p.user_id == actor_id or p.user_id not in hidden]


def _message_payload(message_id, viewer):
    from .selectors import message_page_queryset_unscoped
    from .serializers import MessageSerializer

    message = message_page_queryset_unscoped().get(pk=message_id)
    return MessageSerializer(message, context={"viewer": viewer}).data


# ---------------------------------------------------------------------------
def conversation_started(conversation, created_by_id, participant_ids):
    _emit(
        signals.conversation_started,
        conversation=conversation, created_by_id=created_by_id, participant_ids=participant_ids,
    )


def participant_settings_changed(participant):
    realtime.send_to_user(
        participant.user_id, "conversation.updated",
        {"is_muted": participant.is_muted, "is_archived": participant.is_archived},
        participant.conversation_id,
    )


def message_created(message_id):
    message = Message.objects.select_related("conversation").get(pk=message_id)
    participants = _participants(message.conversation_id)
    for p in _not_blocked_with(message.sender_id, participants):
        realtime.send_to_user(
            p.user_id, "message.new", _message_payload(message.pk, p.user), message.conversation_id
        )
    recipients = [p for p in participants if p.user_id != message.sender_id]
    _emit(
        signals.message_sent,
        message=message,
        sender_id=message.sender_id,
        recipient_ids=[p.user_id for p in recipients],
        notify_user_ids=[p.user_id for p in recipients if not p.is_muted],
    )


def message_updated(message_id, editor_id):
    message = Message.objects.get(pk=message_id)
    for p in _not_blocked_with(editor_id, _participants(message.conversation_id)):
        realtime.send_to_user(
            p.user_id, "message.updated", _message_payload(message.pk, p.user), message.conversation_id
        )
    _emit(signals.message_edited, message=message, editor_id=editor_id)


def message_deleted_for_everyone(message_id, deleted_by_id):
    message = Message.objects.get(pk=message_id)
    for p in _participants(message.conversation_id):
        realtime.send_to_user(
            p.user_id, "message.deleted",
            {"message_id": str(message.pk), "scope": "everyone", "deleted_at": message.deleted_at.isoformat()},
            message.conversation_id,
        )
    _emit(signals.message_deleted, message=message, deleted_by_id=deleted_by_id)


def message_hidden(message_id, conversation_id, user_id):
    realtime.send_to_user(
        user_id, "message.deleted", {"message_id": str(message_id), "scope": "me"}, conversation_id
    )


def reaction_changed(message_id, user_id, reaction_type):
    from .serializers import reaction_summary

    message = Message.objects.get(pk=message_id)
    reactions = list(MessageReaction.objects.filter(message=message))
    for p in _not_blocked_with(user_id, _participants(message.conversation_id)):
        counts, mine = reaction_summary(reactions, p.user_id)
        realtime.send_to_user(
            p.user_id, "message.reaction_updated",
            {
                "message_id": str(message.pk), "user_id": str(user_id),
                "reaction_type": reaction_type, "reactions": counts, "my_reaction": mine,
            },
            message.conversation_id,
        )
    _emit(signals.reaction_changed, message=message, user_id=user_id, reaction_type=reaction_type)


def messages_delivered(message_ids, recipient_id, delivered_at):
    by_sender = {}
    for message_id, conversation_id, sender_id in Message.objects.filter(pk__in=message_ids).values_list(
        "id", "conversation_id", "sender_id"
    ):
        if sender_id is not None:
            by_sender.setdefault((sender_id, conversation_id), []).append(str(message_id))
    hidden = friends.get_hidden_user_ids(recipient_id)
    for (sender_id, conversation_id), ids in by_sender.items():
        if sender_id in hidden:
            continue
        realtime.send_to_user(
            sender_id, "message.delivered",
            {"message_ids": ids, "user_id": str(recipient_id), "delivered_at": delivered_at.isoformat()},
            conversation_id,
        )


def messages_read(conversation_id, reader_id, message_ids, read_at):
    hidden = friends.get_hidden_user_ids(reader_id)
    data = {
        "message_ids": [str(m) for m in message_ids],
        "user_id": str(reader_id),
        "read_at": read_at.isoformat(),
    }
    for p in _participants(conversation_id):
        if p.user_id == reader_id:
            # other devices of the reader: clear unread badges
            realtime.send_to_user(p.user_id, "conversation.read", data, conversation_id)
        elif p.user_id not in hidden:
            realtime.send_to_user(p.user_id, "message.read", data, conversation_id)
    _emit(
        signals.messages_read,
        conversation_id=conversation_id, reader_id=reader_id, message_ids=message_ids, read_at=read_at,
    )


def relationship_changed(user_a_id, user_b_id):
    """
    Friends/blocks changed for a pair: push each side its new messaging state, so the UI can
    show or hide the composer / "become friends" banner without polling.
    """
    from django.contrib.auth import get_user_model

    from .models import direct_key_for
    from .selectors import messaging_state

    conversation = Conversation.objects.filter(direct_key=direct_key_for(user_a_id, user_b_id)).first()
    if conversation is None:
        return
    users = get_user_model().objects.in_bulk([user_a_id, user_b_id])
    for me_id, other_id in ((user_a_id, user_b_id), (user_b_id, user_a_id)):
        me, other = users.get(me_id), users.get(other_id)
        if me is None:
            continue
        realtime.send_to_user(
            me_id, "conversation.permissions",
            messaging_state(me, conversation, other_user=other), conversation.pk,
        )
