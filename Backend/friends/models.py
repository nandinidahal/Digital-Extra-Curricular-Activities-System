from django.conf import settings
from django.db import models
from django.db.models import F, Q

User = settings.AUTH_USER_MODEL


class Friendship(models.Model):
    """
    ONE row per friendship. The pair is stored canonically (user_low.id < user_high.id), so
    (A, B) and (B, A) can never both exist: the unique + check constraints enforce it in the DB.
    """

    user_low = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    user_high = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user_low", "user_high"], name="uniq_friendship_pair"),
            models.CheckConstraint(condition=Q(user_low__lt=F("user_high")), name="friendship_ordered_pair"),
        ]

    def __str__(self):
        return f"{self.user_low_id} <-> {self.user_high_id}"


class RequestStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACCEPTED = "accepted", "Accepted"
    REJECTED = "rejected", "Rejected"
    CANCELLED = "cancelled", "Cancelled"


class FriendRequest(models.Model):
    """
    Request history is kept (accepted / rejected / cancelled rows stay) so a rejected request
    can enforce a re-send cooldown. At most ONE pending request may exist per pair of users,
    in either direction: pair_low/pair_high carry the unordered pair for that constraint.
    """

    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_friend_requests")
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_friend_requests")
    status = models.CharField(max_length=10, choices=RequestStatus.choices, default=RequestStatus.PENDING)
    pair_low = models.BigIntegerField(editable=False)
    pair_high = models.BigIntegerField(editable=False)
    # "Ignore": hidden from the receiver's incoming list; the sender still sees it as pending.
    is_ignored = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["pair_low", "pair_high"], name="uniq_pending_request_per_pair",
                                    condition=Q(status="pending")),
            models.CheckConstraint(condition=~Q(sender=F("receiver")), name="friend_request_not_self"),
        ]
        indexes = [
            models.Index(fields=["receiver", "status", "-created_at"], name="fr_receiver_idx"),
            models.Index(fields=["sender", "status", "-created_at"], name="fr_sender_idx"),
        ]

    def save(self, *args, **kwargs):
        self.pair_low, self.pair_high = sorted((self.sender_id, self.receiver_id))
        super().save(*args, **kwargs)


class Block(models.Model):
    blocker = models.ForeignKey(User, on_delete=models.CASCADE, related_name="blocks_made")
    blocked = models.ForeignKey(User, on_delete=models.CASCADE, related_name="blocks_received")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["blocker", "blocked"], name="uniq_block"),
            models.CheckConstraint(condition=~Q(blocker=F("blocked")), name="block_not_self"),
        ]
