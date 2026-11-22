import uuid

from django.conf import settings
from django.db import models


class MessageReaction(models.Model):
    """One active reaction per (message, user); changing it updates the same row."""

    class Type(models.TextChoices):
        LIKE = "like", "Like"
        LOVE = "love", "Love"
        LAUGH = "laugh", "Laugh"
        SAD = "sad", "Sad"
        SURPRISED = "surprised", "Surprised"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        "messaging.Message", on_delete=models.CASCADE, related_name="reactions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="messaging_reactions"
    )
    reaction_type = models.CharField(max_length=10, choices=Type.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["message", "user"], name="messaging_reaction_unique"),
            models.CheckConstraint(
                condition=models.Q(reaction_type__in=["like", "love", "laugh", "sad", "surprised"]),
                name="messaging_reaction_type_valid",
            ),
        ]

    def __str__(self):
        return f"{self.user_id} {self.reaction_type} {self.message_id}"
