from rest_framework import serializers

from social.serializers import UserBriefSerializer

from .models import Message
from .services import conversation_state

PREVIEW_LEN = 80


def _preview(msg):
    if msg is None:
        return None
    return "Message deleted" if msg.deleted_at else (msg.body[:PREVIEW_LEN] + ("…" if len(msg.body) > PREVIEW_LEN else ""))


class MessageSerializer(serializers.ModelSerializer):
    is_mine = serializers.SerializerMethodField()
    is_deleted = serializers.SerializerMethodField()
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ("id", "conversation", "sender", "body", "is_mine", "is_deleted", "is_read", "created_at",
                  "edited_at", "read_at")
        read_only_fields = fields

    def get_is_mine(self, obj):
        return obj.sender_id == self.context["request"].user.pk

    def get_is_deleted(self, obj):
        return obj.deleted_at is not None

    def get_is_read(self, obj):
        return obj.read_at is not None


class MessageWriteSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=2000, allow_blank=False, trim_whitespace=True)


class StartConversationSerializer(serializers.Serializer):
    recipient_id = serializers.IntegerField()
    body = serializers.CharField(max_length=2000, required=False, allow_blank=True)


class ConversationSerializer(serializers.Serializer):
    """Expects context: request, rel_states ({other_user_id: relationship state})."""

    def to_representation(self, conv):
        request = self.context["request"]
        me = request.user
        other = conv.user_high if conv.user_low_id == me.pk else conv.user_low
        rel = self.context["rel_states"].get(other.pk, "NOT_FRIENDS")
        last = conv.last_message
        return {
            "id": conv.pk,
            "other_user": UserBriefSerializer(other, context={"request": request}).data,
            "last_message": None if last is None else {
                "id": last.pk, "preview": _preview(last), "created_at": last.created_at,
                "is_mine": last.sender_id == me.pk, "is_deleted": last.deleted_at is not None,
            },
            "last_message_at": conv.last_message_at,
            "unread_count": getattr(conv, "unread_count", 0),
            "created_at": conv.created_at,
            **conversation_state(me, conv, other, rel),
        }
