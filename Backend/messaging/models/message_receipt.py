import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class MessageReceipt(models.Model):
    """
    Delivery/read state of one message for ONE recipient (the sender never gets a receipt).

    * created with the message            -> status "sent"
    * delivered_at set on a real client acknowledgement (WebSocket `message.delivered`,
      REST /delivered/, or the recipient loading the message list)  -> "delivered"
    * read_at set only by the recipient's own "mark as read" action    -> "read"

    State is per user, not per device: the first device to acknowledge wins.
    `conversation` is denormalised so unread counts are a single indexed lookup.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        "messaging.Message", on_delete=models.CASCADE, related_name="receipts"
    )
    conversation = models.ForeignKey(
        "messaging.Conversation", on_delete=models.CASCADE, related_name="receipts"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="messaging_receipts"
    )
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["message", "user"], name="messaging_receipt_unique"),
            # read implies delivered
            models.CheckConstraint(
                condition=Q(read_at__isnull=True) | Q(delivered_at__isnull=False),
                name="messaging_receipt_read_implies_delivered",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "conversation"],
                condition=Q(read_at__isnull=True),
                name="messaging_receipt_unread_idx",
            ),
        ]

    def __str__(self):
        return f"receipt {self.message_id} for {self.user_id}"
