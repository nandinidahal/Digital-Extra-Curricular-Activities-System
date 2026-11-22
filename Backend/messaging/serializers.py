"""
Serializers. Input serializers are strict (unknown keys such as `sender_id` -> 400, so the
client can never set the sender, status or counters). Output is built explicitly.

Person cards reuse friends.serializers.build_user_card, so profile privacy (private profiles
hide picture/headline) is applied exactly as in the Friends module.
"""
from django.core import signing
from django.urls import reverse
from rest_framework import serializers

from friends.serializers import StrictFieldsMixin, build_user_card

from .models import MessageReaction

_DT = serializers.DateTimeField()
ATTACHMENT_SIGNING_SALT = "messaging.attachment.download"
REPLY_PREVIEW_LENGTH = 120


def iso(value):
    return _DT.to_representation(value) if value else None


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------
class StartConversationSerializer(StrictFieldsMixin, serializers.Serializer):
    user_id = serializers.UUIDField()


class MuteSerializer(StrictFieldsMixin, serializers.Serializer):
    is_muted = serializers.BooleanField()


class ArchiveSerializer(StrictFieldsMixin, serializers.Serializer):
    is_archived = serializers.BooleanField()


class SendMessageSerializer(StrictFieldsMixin, serializers.Serializer):
    """JSON or multipart. Files arrive as repeated `attachments` parts (see the view)."""

    content = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False, max_length=20000)
    reply_to_id = serializers.UUIDField(required=False, allow_null=True)
    client_id = serializers.UUIDField(required=False, allow_null=True)
    attachments = serializers.ListField(child=serializers.FileField(), required=False)


class ReplySerializer(StrictFieldsMixin, serializers.Serializer):
    content = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False, max_length=20000)
    client_id = serializers.UUIDField(required=False, allow_null=True)
    attachments = serializers.ListField(child=serializers.FileField(), required=False)


class EditMessageSerializer(StrictFieldsMixin, serializers.Serializer):
    content = serializers.CharField(allow_blank=True, trim_whitespace=False, max_length=20000)


class ForwardSerializer(StrictFieldsMixin, serializers.Serializer):
    conversation_id = serializers.UUIDField(required=False)
    user_id = serializers.UUIDField(required=False)
    client_id = serializers.UUIDField(required=False, allow_null=True)


class ReactionSerializer(StrictFieldsMixin, serializers.Serializer):
    reaction_type = serializers.ChoiceField(choices=MessageReaction.Type.choices)


class MarkReadSerializer(StrictFieldsMixin, serializers.Serializer):
    up_to_message_id = serializers.UUIDField(required=False, allow_null=True)


class MarkDeliveredSerializer(StrictFieldsMixin, serializers.Serializer):
    message_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=500)


class DeleteMessageSerializer(StrictFieldsMixin, serializers.Serializer):
    scope = serializers.ChoiceField(choices=["me", "everyone"], default="me")


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
def user_card(user, viewer, request=None):
    if user is None:
        return None  # account deleted
    card = build_user_card(user, viewer, request)
    return {
        "id": card["user_id"],
        "username": card["username"],
        "full_name": card["full_name"],
        "profile_picture": card["profile_picture"],
    }


def reaction_summary(reactions, viewer_id):
    counts, mine = {}, None
    for r in reactions:
        counts[r.reaction_type] = counts.get(r.reaction_type, 0) + 1
        if r.user_id == viewer_id:
            mine = r.reaction_type
    return counts, mine


def signed_attachment_url(attachment, viewer, request=None):
    """Short-lived link bound to (attachment, viewer). Works in <img src> without headers."""
    token = signing.dumps({"a": str(attachment.pk), "u": str(viewer.pk)}, salt=ATTACHMENT_SIGNING_SALT)
    path = reverse("messaging:attachment-download", kwargs={"attachment_id": attachment.pk})
    url = f"{path}?sig={token}"
    return request.build_absolute_uri(url) if request is not None else url


def attachment_data(attachment, viewer, request=None):
    return {
        "id": str(attachment.pk),
        "kind": attachment.kind,
        "name": attachment.original_name,
        "content_type": attachment.content_type,
        "size": attachment.size,
        "width": attachment.width,
        "height": attachment.height,
        "url": signed_attachment_url(attachment, viewer, request),
    }


def message_status(message, viewer_id):
    """
    Direct conversations: the state of the (single) recipient's receipt.
    sent -> delivered (real client acknowledgement) -> read (recipient action).
    """
    receipts = list(message.receipts.all())
    if not receipts:
        return "sent", None, None
    if all(r.read_at for r in receipts):
        return "read", max(r.delivered_at for r in receipts), max(r.read_at for r in receipts)
    if all(r.delivered_at for r in receipts):
        return "delivered", max(r.delivered_at for r in receipts), None
    return "sent", None, None


def reply_preview(message):
    target = message.reply_to
    if message.reply_to_id is None:
        return None
    if target is None:  # hard-deleted (account removal)
        return {"id": None, "is_deleted": True, "is_available": False}
    preview = None if target.is_deleted else (target.content or "")[:REPLY_PREVIEW_LENGTH]
    return {
        "id": str(target.pk),
        "sender_id": str(target.sender_id) if target.sender_id else None,
        "sender_username": target.sender.username if target.sender_id and target.sender else None,
        "message_type": target.message_type,
        "content_preview": preview,
        "is_deleted": target.is_deleted,
        "is_available": not target.is_deleted,
    }


class MessageSerializer(serializers.BaseSerializer):
    """
    Expects messages loaded with selectors.message_page_queryset (everything prefetched).
    context: {"viewer": user, "request": request (optional)}
    """

    def to_representation(self, message):
        viewer = self.context["viewer"]
        request = self.context.get("request")
        deleted = message.is_deleted
        status, delivered_at, read_at = message_status(message, viewer.pk)
        counts, mine = reaction_summary([] if deleted else message.reactions.all(), viewer.pk)
        is_own = message.sender_id == viewer.pk
        return {
            "id": str(message.pk),
            "conversation_id": str(message.conversation_id),
            "sender": user_card(message.sender, viewer, request) if message.sender_id else None,
            "is_own": is_own,
            "message_type": message.message_type,
            "content": None if deleted else message.content,
            "attachments": [] if deleted else [
                attachment_data(a, viewer, request) for a in message.attachments.all()
            ],
            "reply_to": reply_preview(message),
            "is_forwarded": message.is_forwarded,
            "status": status,
            "delivered_at": iso(delivered_at),
            "read_at": iso(read_at),
            "reactions": counts,
            "my_reaction": mine,
            "is_edited": message.is_edited,
            "edited_at": iso(message.edited_at),
            "is_deleted": deleted,
            "deleted_at": iso(message.deleted_at),
            "client_id": str(message.client_id) if is_own and message.client_id else None,
            "created_at": iso(message.created_at),
            "updated_at": iso(message.updated_at),
        }


def last_message_data(message, viewer):
    if message is None:
        return None
    return {
        "id": str(message.pk),
        "content": None if message.is_deleted else message.content,
        "message_type": message.message_type,
        "sender_id": str(message.sender_id) if message.sender_id else None,
        "is_own": message.sender_id == viewer.pk,
        "is_deleted": message.is_deleted,
        "created_at": iso(message.created_at),
    }


def conversation_data(participation, viewer, request=None, *, messaging=None):
    """
    `participation` must come from selectors.conversation_list + attach_conversation_extras
    (or have `others`, `latest_message`, `presence`, `unread` set).
    """
    conversation = participation.conversation
    other = participation.others[0].user if participation.others else None
    participant = None
    if other is not None:
        presence = participation.presence.get(other.pk, {"is_online": None, "last_seen_at": None})
        participant = {
            **user_card(other, viewer, request),
            "is_online": presence["is_online"],
            "last_seen_at": iso(presence["last_seen_at"]),
        }
    data = {
        "id": str(conversation.pk),
        "conversation_type": conversation.conversation_type,
        "participant": participant,
        "last_message": last_message_data(participation.latest_message, viewer),
        "unread_count": participation.unread,
        "is_muted": participation.is_muted,
        "is_archived": participation.is_archived,
        "last_read_at": iso(participation.last_read_at),
        "created_at": iso(conversation.created_at),
        "updated_at": iso(conversation.last_message_at or conversation.created_at),
    }
    if messaging is not None:
        data["messaging"] = messaging
    return data


def verify_attachment_signature(token, max_age):
    """Return (attachment_id, user_id) or None."""
    try:
        payload = signing.loads(token, salt=ATTACHMENT_SIGNING_SALT, max_age=max_age)
        return payload["a"], payload["u"]
    except (signing.BadSignature, KeyError, TypeError):
        return None

