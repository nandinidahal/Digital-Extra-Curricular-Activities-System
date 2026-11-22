import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Message(models.Model):
    """
    One message. Rows are never hard-deleted by users:

    * "delete for me"       -> a MessageVisibility row hides it from that user only.
    * "delete for everyone" -> tombstone: is_deleted=True, content wiped, attachments removed.

    `counts_toward_limit` is stamped at send time: True when the two users were NOT friends.
    The pre-friendship limit counts these rows, so deleting a message can never give the
    allowance back.

    `client_id` is an optional idempotency key chosen by the client. UNIQUE(sender, client_id)
    means a retried send (for example after a WebSocket reconnect) returns the original message
    instead of creating a duplicate.
    """

    class Type(models.TextChoices):
        TEXT = "text", "Text"
        IMAGE = "image", "Image"
        FILE = "file", "File"
        SYSTEM = "system", "System"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        "messaging.Conversation", on_delete=models.CASCADE, related_name="messages"
    )
    # SET_NULL keeps the other participant's history if an account is deleted.
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messaging_messages",
    )
    message_type = models.CharField(max_length=10, choices=Type.choices, default=Type.TEXT)
    content = models.TextField(blank=True, default="")
    reply_to = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="replies"
    )
    is_forwarded = models.BooleanField(default=False)
    client_id = models.UUIDField(null=True, blank=True)
    counts_toward_limit = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(message_type__in=["text", "image", "file", "system"]),
                name="messaging_message_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(is_deleted=False, deleted_at__isnull=True)
                | Q(is_deleted=True, deleted_at__isnull=False),
                name="messaging_message_deleted_consistent",
            ),
            models.UniqueConstraint(
                fields=["sender", "client_id"],
                condition=Q(client_id__isnull=False),
                name="messaging_message_client_id_unique",
            ),
        ]
        indexes = [
            # history pages + latest message per conversation
            models.Index(fields=["conversation", "-created_at", "-id"], name="messaging_msg_history_idx"),
            # the pre-friendship counter only ever scans these few rows
            models.Index(
                fields=["conversation"],
                condition=Q(counts_toward_limit=True),
                name="messaging_msg_limit_idx",
            ),
        ]

    def __str__(self):
        return f"{self.message_type} message {self.id}"
