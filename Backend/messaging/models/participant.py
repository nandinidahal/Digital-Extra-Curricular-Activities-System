import uuid

from django.conf import settings
from django.db import models


class ConversationParticipant(models.Model):
    """
    Membership of one user in one conversation, plus that user's PRIVATE settings for it.
    Mute and archive live here, so one participant's choices never affect the other.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        "messaging.Conversation", on_delete=models.CASCADE, related_name="participants"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="messaging_participations"
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    last_read_at = models.DateTimeField(null=True, blank=True)
    is_muted = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    # False = the user left / was removed (reserved for group chats); history stays.
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"], name="messaging_participant_unique"
            ),
        ]
        indexes = [
            # "my conversations" list (the unique constraint serves conversation-first lookups)
            models.Index(fields=["user", "is_active", "is_archived"], name="messaging_part_user_idx"),
        ]

    def __str__(self):
        return f"{self.user_id} in {self.conversation_id}"
