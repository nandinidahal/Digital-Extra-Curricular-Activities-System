import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


def direct_key_for(user_a_id, user_b_id):
    """
    Canonical key of a direct conversation: "<lower uuid>:<higher uuid>".
    Ordering uses the integer value of the UUID (same order as PostgreSQL's uuid type and the
    Friends module), so (A, B) and (B, A) always produce the same key.
    """
    a = user_a_id if isinstance(user_a_id, uuid.UUID) else uuid.UUID(str(user_a_id))
    b = user_b_id if isinstance(user_b_id, uuid.UUID) else uuid.UUID(str(user_b_id))
    low, high = (a, b) if a.int <= b.int else (b, a)
    return f"{low}:{high}"


class Conversation(models.Model):
    """
    A conversation. Only DIRECT (exactly two participants) is implemented; GROUP is reserved so
    group chats can be added later without a schema rewrite (participants already live in their
    own table).

    `direct_key` is UNIQUE, so two concurrent "start conversation" requests for the same pair can
    never create two rows - the second insert fails and the existing row is returned instead.
    """

    class Type(models.TextChoices):
        DIRECT = "direct", "Direct"
        GROUP = "group", "Group"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation_type = models.CharField(max_length=10, choices=Type.choices, default=Type.DIRECT)
    direct_key = models.CharField(max_length=73, null=True, blank=True, unique=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messaging_conversations_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    # Last activity (bumped whenever a message is sent).
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(conversation_type__in=["direct", "group"]),
                name="messaging_conversation_type_valid",
            ),
            # Direct conversations always carry their pair key; group conversations never do.
            models.CheckConstraint(
                condition=Q(conversation_type="direct", direct_key__isnull=False)
                | Q(conversation_type="group", direct_key__isnull=True),
                name="messaging_conversation_direct_key_consistent",
            ),
        ]
        indexes = [
            models.Index(fields=["-last_message_at"], name="messaging_conv_last_msg_idx"),
        ]

    def __str__(self):
        return f"{self.conversation_type} conversation {self.id}"

    @property
    def is_direct(self):
        return self.conversation_type == self.Type.DIRECT
