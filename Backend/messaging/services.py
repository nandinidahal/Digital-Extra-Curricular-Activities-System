"""
All Messaging business rules. REST views and the WebSocket consumer both call these functions,
so every rule (membership, blocks, friendship, the pre-friendship message limit, edit windows,
validation) is enforced in exactly one place and cannot be bypassed by switching transport.

PRE-FRIENDSHIP LIMIT (settings.MESSAGING_NON_FRIEND_MESSAGE_LIMIT, default 4)
---------------------------------------------------------------------------
* Two users who are not friends may exchange at most N messages IN TOTAL (both senders count
  towards the same allowance) in their direct conversation.
* Each message is stamped `counts_toward_limit=True` when it is sent while the users are NOT
  friends. The limit counts stamped rows. Consequences (documented policy):
    - deleting a message (for me or for everyone) never gives allowance back;
    - messages exchanged while friends never consume allowance;
    - if the friendship is later removed, the allowance already used BEFORE the friendship still
      counts. Users who had used all N messages cannot message again until they are friends.
* Enforcement is atomic: the conversation row is locked (SELECT ... FOR UPDATE) before
  counting, so concurrent requests are serialised and can never exceed N. A send that fails for
  any reason (validation, block, file error) rolls back and consumes nothing.
* Blocking always wins over friendship.

CONCURRENCY
-----------
* Direct conversations: UNIQUE(direct_key) + get-or-create-on-IntegrityError.
* Sends: conversation row lock (above) + UNIQUE(sender, client_id) for idempotent retries.
* Reactions / receipts / hides: unique constraints + idempotent writes.
"""
import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.db.models import F
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from friends import services as friends
from friends.validators import is_available

from . import events, selectors
from .exceptions import (
    AccountUnavailable,
    CannotMessageSelf,
    ClientIdConflict,
    ConversationInactive,
    DeleteWindowExpired,
    EditWindowExpired,
    MessageDeleted,
    MessageLimitReached,
    MessageNotEditable,
    MessagingNotAllowed,
    NotMessageOwner,
    RecipientNotFound,
)
from .models import (
    Conversation,
    ConversationParticipant,
    Message,
    MessageAttachment,
    MessageReaction,
    MessageReceipt,
    MessageVisibility,
    direct_key_for,
)
from .validators import clean_message_content, max_attachments, prepare_attachment

logger = logging.getLogger("messaging")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _uuid(value):
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(getattr(value, "pk", value)))


def _require_available_actor(user):
    if not is_available(user):
        raise AccountUnavailable()


def _minutes_setting(name, default):
    return max(0, int(getattr(settings, name, default)))


def _within_window(created_at, minutes):
    return minutes == 0 or timezone.now() - created_at <= timedelta(minutes=minutes)


def _validation_error(field, exc):
    messages = exc.messages if isinstance(exc, DjangoValidationError) else [str(exc)]
    return ValidationError({field: messages})


def _on_commit(func, *args, **kwargs):
    transaction.on_commit(lambda: func(*args, **kwargs))


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------
@dataclass
class StartResult:
    conversation: Conversation
    created: bool


def start_direct_conversation(user, other_user_id):
    """
    Return the existing direct conversation with `other_user_id`, or create it.
    Starting a conversation sends nothing and does not consume the message allowance.
    """
    _require_available_actor(user)
    other_user_id = _uuid(other_user_id)
    if other_user_id == user.pk:
        raise CannotMessageSelf()
    other = selectors.available_user_or_none(other_user_id)
    if other is None:
        raise RecipientNotFound()
    if friends.is_blocked_between(user.pk, other.pk):
        raise MessagingNotAllowed()

    key = direct_key_for(user.pk, other.pk)
    existing = Conversation.objects.filter(direct_key=key).first()
    if existing is not None:
        _reactivate_participants(existing, [user.pk, other.pk])
        return StartResult(existing, False)
    try:
        with transaction.atomic():
            conversation = Conversation.objects.create(
                conversation_type=Conversation.Type.DIRECT, direct_key=key, created_by=user
            )
            ConversationParticipant.objects.bulk_create(
                [
                    ConversationParticipant(conversation=conversation, user=user),
                    ConversationParticipant(conversation=conversation, user=other),
                ]
            )
            _on_commit(events.conversation_started, conversation, user.pk, [user.pk, other.pk])
    except IntegrityError:  # a concurrent request created it first
        return StartResult(Conversation.objects.get(direct_key=key), False)
    return StartResult(conversation, True)


def _reactivate_participants(conversation, user_ids):
    ConversationParticipant.objects.filter(
        conversation=conversation, user_id__in=user_ids, is_active=False
    ).update(is_active=True)


def set_muted(user, conversation_id, muted):
    participant = selectors.get_participation(user, conversation_id)
    if participant.is_muted != muted:
        participant.is_muted = muted
        participant.save(update_fields=["is_muted"])
    _on_commit(events.participant_settings_changed, participant)
    return participant


def set_archived(user, conversation_id, archived):
    participant = selectors.get_participation(user, conversation_id)
    if participant.is_archived != archived:
        participant.is_archived = archived
        participant.save(update_fields=["is_archived"])
    _on_commit(events.participant_settings_changed, participant)
    return participant


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------
@dataclass
class SendResult:
    message: Message
    created: bool  # False = idempotent retry returned the original message


def prepare_uploads(files):
    """Validate uploads BEFORE any lock is taken. Raises a 400 listing the problem."""
    files = list(files or [])
    if len(files) > max_attachments():
        raise ValidationError(
            {"attachments": [f"You can attach at most {max_attachments()} files per message."]}
        )
    prepared = []
    for upload in files:
        try:
            prepared.append(prepare_attachment(upload))
        except DjangoValidationError as exc:
            raise _validation_error("attachments", exc)
    return prepared


def _message_type_for(prepared):
    if not prepared:
        return Message.Type.TEXT
    return Message.Type.IMAGE if all(p.kind == "image" for p in prepared) else Message.Type.FILE


def send_message(
    user,
    conversation_id,
    *,
    content="",
    files=None,
    prepared_attachments=None,
    reply_to_id=None,
    client_id=None,
    is_forwarded=False,
):
    """
    Create a message after every rule has passed. See the module docstring for the limit.
    `files` are raw uploads (validated here); `prepared_attachments` are already validated
    (used by forwarding). Returns SendResult.
    """
    _require_available_actor(user)
    try:
        content = clean_message_content(content)
    except DjangoValidationError as exc:
        raise _validation_error("content", exc)
    prepared = list(prepared_attachments or []) + prepare_uploads(files)
    if not content and not prepared:
        raise ValidationError({"content": ["A message needs text or at least one attachment."]})
    client_id = _uuid(client_id) if client_id else None

    # Idempotent retry: same sender + client_id returns the original message, no side effects.
    if client_id is not None:
        previous = _existing_by_client_id(user, client_id, conversation_id)
        if previous is not None:
            return SendResult(previous, False)

    stored_names = []
    try:
        with transaction.atomic():
            selectors.get_participation(user, conversation_id)  # 404 for non-participants
            conversation = Conversation.objects.select_for_update().get(pk=conversation_id)
            if not conversation.is_active:
                raise ConversationInactive()
            others = selectors.other_participants(conversation, user.pk)
            counts = _check_can_send(user, conversation, others)

            reply_to = _resolve_reply_target(user, conversation, reply_to_id) if reply_to_id else None
            try:
                with transaction.atomic():
                    message = Message.objects.create(
                        conversation=conversation,
                        sender=user,
                        message_type=_message_type_for(prepared),
                        content=content,
                        reply_to=reply_to,
                        is_forwarded=is_forwarded,
                        client_id=client_id,
                        counts_toward_limit=counts,
                    )
            except IntegrityError:
                # Same client_id raced in from another connection: return that message.
                previous = _existing_by_client_id(user, client_id, conversation_id)
                if previous is None:
                    raise
                return SendResult(previous, False)

            for position, item in enumerate(prepared):
                attachment = MessageAttachment(
                    message=message, kind=item.kind, original_name=item.original_name,
                    content_type=item.content_type, size=item.size,
                    width=item.width, height=item.height, position=position,
                )
                item.content.seek(0)
                attachment.file.save(f"upload.{item.extension}", item.content, save=False)
                stored_names.append(attachment.file.name)
                attachment.save()

            MessageReceipt.objects.bulk_create(
                [MessageReceipt(message=message, conversation=conversation, user_id=o.user_id) for o in others]
            )
            Conversation.objects.filter(pk=conversation.pk).update(
                last_message_at=message.created_at, updated_at=timezone.now()
            )
            if getattr(settings, "MESSAGING_UNARCHIVE_ON_NEW_MESSAGE", True):
                ConversationParticipant.objects.filter(
                    conversation=conversation, is_archived=True, is_active=True
                ).update(is_archived=False)
            _on_commit(events.message_created, message.pk)
    except BaseException:
        _delete_files(stored_names)  # nothing may be left behind by a failed send
        raise
    return SendResult(message, True)


def _existing_by_client_id(user, client_id, conversation_id):
    previous = Message.objects.filter(sender=user, client_id=client_id).first()
    if previous is None:
        return None
    if str(previous.conversation_id) != str(conversation_id):
        raise ClientIdConflict()
    return previous


def _check_can_send(user, conversation, others):
    """
    Raise unless `user` may send now. Must run while holding the conversation row lock.
    Returns True when the new message counts towards the pre-friendship limit.
    """
    if not others:
        raise MessagingNotAllowed()
    if conversation.is_direct:
        other = others[0].user
        if not is_available(other):
            raise MessagingNotAllowed()
        if friends.is_blocked_between(user.pk, other.pk):
            raise MessagingNotAllowed()
        if friends.are_friends(user.pk, other.pk):
            return False
        limit = selectors.non_friend_message_limit()
        used = conversation.messages.filter(counts_toward_limit=True).count()
        if used >= limit:
            raise MessageLimitReached(used, limit)
        return True
    raise MessagingNotAllowed()  # group conversations are not implemented yet


def _resolve_reply_target(user, conversation, reply_to_id):
    target = (
        selectors.visible_messages(user)
        .filter(pk=reply_to_id, conversation=conversation)
        .first()
    )
    if target is None:
        raise ValidationError({"reply_to_id": ["You can only reply to a message in this conversation."]})
    if target.is_deleted:
        raise ValidationError({"reply_to_id": ["You cannot reply to a deleted message."]})
    if target.message_type == Message.Type.SYSTEM:
        raise ValidationError({"reply_to_id": ["You cannot reply to a system message."]})
    return target


def reply_to_message(user, message_id, **kwargs):
    original = selectors.get_message_for_user(user, message_id)
    return send_message(user, original.conversation_id, reply_to_id=original.pk, **kwargs)


def forward_message(user, message_id, *, conversation_id=None, user_id=None, client_id=None):
    """
    Copy a message (text + attachments) into another conversation the user belongs to (or a
    direct conversation with `user_id`, created if needed). Every send rule applies to the
    target conversation, including the pre-friendship limit. The copy is marked forwarded and
    does NOT link back to the original, so nothing about the source conversation leaks.
    """
    original = selectors.get_message_for_user(user, message_id)
    if original.is_deleted:
        raise MessageDeleted()
    if original.message_type == Message.Type.SYSTEM:
        raise ValidationError({"message": ["System messages cannot be forwarded."]})
    if (conversation_id is None) == (user_id is None):
        raise ValidationError({"non_field_errors": ["Send exactly one of conversation_id or user_id."]})
    if user_id is not None:
        conversation_id = start_direct_conversation(user, user_id).conversation.pk
    prepared = _copy_attachments(original)
    return send_message(
        user, conversation_id, content=original.content,
        prepared_attachments=prepared, client_id=client_id, is_forwarded=True,
    )


def _copy_attachments(message):
    from .validators import PreparedAttachment

    copies = []
    for attachment in message.attachments.all():
        with attachment.file.open("rb") as handle:
            data = handle.read()
        copies.append(
            PreparedAttachment(
                kind=attachment.kind, content=ContentFile(data),
                extension=attachment.file.name.rsplit(".", 1)[-1],
                content_type=attachment.content_type, original_name=attachment.original_name,
                size=len(data), width=attachment.width, height=attachment.height,
            )
        )
    return copies


def _delete_files(names):
    if not names:
        return
    storage = MessageAttachment._meta.get_field("file").storage
    for name in names:
        try:
            storage.delete(name)
        except Exception:
            logger.warning("Messaging: could not delete attachment file %s", name)


# ---------------------------------------------------------------------------
# Edit / delete
# ---------------------------------------------------------------------------
def _other_user_ids(message):
    return list(
        ConversationParticipant.objects.filter(conversation_id=message.conversation_id, is_active=True)
        .exclude(user_id=message.sender_id)
        .values_list("user_id", flat=True)
    )


@transaction.atomic
def edit_message(user, message_id, content):
    _require_available_actor(user)
    message = selectors.get_message_for_user(user, message_id, for_update=True)
    if message.sender_id != user.pk:
        raise NotMessageOwner()
    if message.is_deleted:
        raise MessageDeleted()
    if message.message_type == Message.Type.SYSTEM or message.is_forwarded:
        raise MessageNotEditable()
    if not _within_window(message.created_at, _minutes_setting("MESSAGING_EDIT_WINDOW_MINUTES", 15)):
        raise EditWindowExpired()
    if any(friends.is_blocked_between(user.pk, other) for other in _other_user_ids(message)):
        raise MessagingNotAllowed()
    try:
        content = clean_message_content(content)
    except DjangoValidationError as exc:
        raise _validation_error("content", exc)
    if not content and not message.attachments.exists():
        raise ValidationError({"content": ["A message needs text or at least one attachment."]})
    if content != message.content:
        message.content = content
        message.is_edited = True
        message.edited_at = timezone.now()
        message.save(update_fields=["content", "is_edited", "edited_at", "updated_at"])
        _on_commit(events.message_updated, message.pk, user.pk)
    return message


@transaction.atomic
def delete_for_me(user, message_id):
    """Hide the message from `user` only. Idempotent. The allowance is NOT given back."""
    message = selectors.get_message_for_user(user, message_id)
    try:
        with transaction.atomic():
            MessageVisibility.objects.get_or_create(message=message, user=user)
    except IntegrityError:
        pass
    # Hiding an unread message also clears it from the unread count.
    now = timezone.now()
    MessageReceipt.objects.filter(message=message, user=user, read_at__isnull=True).update(
        read_at=now, delivered_at=Coalesce(F("delivered_at"), now)
    )
    _on_commit(events.message_hidden, message.pk, message.conversation_id, user.pk)
    return message


@transaction.atomic
def delete_for_everyone(user, message_id):
    """
    Sender only, within MESSAGING_DELETE_FOR_EVERYONE_WINDOW_MINUTES. Leaves a tombstone:
    content is wiped, attachments and reactions are removed, the row (and its place in the
    pre-friendship count) stays.
    """
    message = selectors.get_message_for_user(user, message_id, for_update=True)
    if message.sender_id != user.pk:
        raise NotMessageOwner("You can only delete your own messages for everyone.")
    if message.is_deleted:
        return message  # idempotent
    if not _within_window(
        message.created_at, _minutes_setting("MESSAGING_DELETE_FOR_EVERYONE_WINDOW_MINUTES", 60)
    ):
        raise DeleteWindowExpired()
    names = list(message.attachments.values_list("file", flat=True))
    message.attachments.all().delete()
    message.reactions.all().delete()
    message.content = ""
    message.is_deleted = True
    message.deleted_at = timezone.now()
    message.save(update_fields=["content", "is_deleted", "deleted_at", "updated_at"])
    _on_commit(_delete_files, names)
    _on_commit(events.message_deleted_for_everyone, message.pk, user.pk)
    return message


# ---------------------------------------------------------------------------
# Reactions
# ---------------------------------------------------------------------------
def _check_can_react(user, message):
    if message.is_deleted:
        raise MessageDeleted()
    if message.message_type == Message.Type.SYSTEM:
        raise ValidationError({"message": ["You cannot react to a system message."]})
    others = selectors.other_participants(message.conversation, user.pk)
    if any(friends.is_blocked_between(user.pk, o.user_id) for o in others):
        raise MessagingNotAllowed()


def set_reaction(user, message_id, reaction_type):
    _require_available_actor(user)
    if reaction_type not in MessageReaction.Type.values:
        raise ValidationError({"reaction_type": [f"Choose one of: {', '.join(MessageReaction.Type.values)}."]})
    message = selectors.get_message_for_user(user, message_id)
    _check_can_react(user, message)
    for _attempt in range(2):
        try:
            with transaction.atomic():
                reaction, created = MessageReaction.objects.get_or_create(
                    message=message, user=user, defaults={"reaction_type": reaction_type}
                )
                if not created and reaction.reaction_type != reaction_type:
                    reaction.reaction_type = reaction_type
                    reaction.save(update_fields=["reaction_type", "updated_at"])
                _on_commit(events.reaction_changed, message.pk, user.pk, reaction_type)
            break
        except IntegrityError:  # concurrent first reaction - retry as an update
            continue
    return message


@transaction.atomic
def remove_reaction(user, message_id):
    """Idempotent: removing a reaction that does not exist is not an error."""
    message = selectors.get_message_for_user(user, message_id)
    deleted, _ = MessageReaction.objects.filter(message=message, user=user).delete()
    if deleted:
        _on_commit(events.reaction_changed, message.pk, user.pk, None)
    return message


# ---------------------------------------------------------------------------
# Delivery and read receipts
# ---------------------------------------------------------------------------
def mark_delivered(user, message_ids):
    """
    Record that the recipient's client really received these messages. Only the caller's OWN
    receipts are touched, so nobody can confirm delivery on someone else's behalf.
    Returns the ids that changed.
    """
    message_ids = [_uuid(m) for m in message_ids][:500]
    if not message_ids:
        return []
    now = timezone.now()
    with transaction.atomic():
        receipts = list(
            MessageReceipt.objects.select_for_update()
            .filter(user=user, message_id__in=message_ids, delivered_at__isnull=True)
            .values_list("id", "message_id")
        )
        if not receipts:
            return []
        MessageReceipt.objects.filter(pk__in=[r[0] for r in receipts]).update(delivered_at=now)
        changed = [r[1] for r in receipts]
        _on_commit(events.messages_delivered, changed, user.pk, now)
    return changed


def mark_read(user, conversation_id, up_to_message_id=None):
    """
    The recipient read the conversation up to `up_to_message_id` (default: everything).
    Only the caller's own receipts change; the sender's messages can never be marked read by
    the sender. Returns (message_ids, read_at).
    """
    participant = selectors.get_participation(user, conversation_id)
    now = timezone.now()
    cutoff = now
    if up_to_message_id is not None:
        target = (
            selectors.visible_messages(user)
            .filter(pk=up_to_message_id, conversation_id=conversation_id)
            .first()
        )
        if target is None:
            raise ValidationError({"up_to_message_id": ["Unknown message for this conversation."]})
        cutoff = target.created_at
    with transaction.atomic():
        receipts = list(
            MessageReceipt.objects.select_for_update()
            .filter(
                user=user, conversation_id=conversation_id, read_at__isnull=True,
                message__created_at__lte=cutoff,
            )
            .values_list("id", "message_id")
        )
        if receipts:
            MessageReceipt.objects.filter(pk__in=[r[0] for r in receipts]).update(
                read_at=now, delivered_at=Coalesce(F("delivered_at"), now)
            )
        if participant.last_read_at is None or participant.last_read_at < cutoff:
            ConversationParticipant.objects.filter(pk=participant.pk).update(last_read_at=cutoff)
        message_ids = [r[1] for r in receipts]
        if message_ids:
            _on_commit(events.messages_read, conversation_id, user.pk, message_ids, now)
    return message_ids, now


def mark_page_delivered(user, messages):
    """Called when the recipient loads history: those messages reached a real client."""
    ids = [
        m.pk for m in messages
        if m.sender_id != user.pk
        and any(r.user_id == user.pk and r.delivered_at is None for r in m.receipts.all())
    ]
    if ids:
        mark_delivered(user, ids)
        now = timezone.now()
        for m in messages:  # keep the response consistent with what was just stored
            for r in m.receipts.all():
                if r.user_id == user.pk and r.delivered_at is None and m.pk in ids:
                    r.delivered_at = now
    return ids
