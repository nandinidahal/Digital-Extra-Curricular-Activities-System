import uuid

from django.conf import settings
from django.db import models


class MessageVisibility(models.Model):
    """'Delete for me': hides one message from one user. The other participant is unaffected."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        "messaging.Message", on_delete=models.CASCADE, related_name="hidden_for"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="messaging_hidden_messages"
    )
    hidden_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["message", "user"], name="messaging_visibility_unique"),
        ]
        indexes = [
            models.Index(fields=["user", "message"], name="messaging_hidden_user_idx"),
        ]

    def __str__(self):
        return f"{self.message_id} hidden for {self.user_id}"
