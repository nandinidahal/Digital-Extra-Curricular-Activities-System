from django.conf import settings
from django.db import models
from django.db.models import F, Q

User = settings.AUTH_USER_MODEL


class Conversation(models.Model):
    """
    Exactly ONE conversation per pair of users (canonical order user_low < user_high, unique in the DB),
    so non-friends cannot dodge the pre-friendship limit by opening several conversations.
    """

    user_low = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    user_high = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    # Messages sent while the two were NOT friends (counts both directions). Guarded by a row lock.
    restricted_message_count = models.PositiveSmallIntegerField(default=0)
    last_message = models.ForeignKey("Message", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    last_message_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user_low", "user_high"], name="uniq_conversation_pair"),
            models.CheckConstraint(condition=Q(user_low__lt=F("user_high")), name="conversation_ordered_pair"),
        ]
        indexes = [
            models.Index(fields=["user_low", "-last_message_at"], name="conv_low_idx"),
            models.Index(fields=["user_high", "-last_message_at"], name="conv_high_idx"),
        ]

    def other_user_id(self, user_id):
        return self.user_high_id if self.user_low_id == user_id else self.user_low_id

    def includes(self, user_id):
        return user_id in (self.user_low_id, self.user_high_id)


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    body = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    # Delete policy: the sender may delete their own message at any time ("delete for everyone").
    # The row stays as a tombstone (body cleared) so the conversation keeps its shape and the
    # pre-friendship limit cannot be reset by deleting messages.
    deleted_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["conversation", "-id"], name="msg_conv_id_idx"),
            models.Index(fields=["conversation", "read_at"], name="msg_conv_read_idx"),
        ]
