"""
Friends module data model.

Three tables, all referencing `settings.AUTH_USER_MODEL` (accounts.User). No account or
profile data is copied here; names and pictures are read from Accounts/Profiles at query time.

* FriendRequest - one row per request. Rows are kept as history (see README, "History policy").
* Friendship    - one row per friend pair. The pair is stored in a canonical order
                  (user1 < user2) so the same relationship can never exist twice.
* UserBlock     - one row per (blocker, blocked). Directional.
"""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Greatest, Least


def _uuid_key(value):
    """Integer used to order two user ids. Python's UUID order equals PostgreSQL's uuid order."""
    return value.int if isinstance(value, uuid.UUID) else uuid.UUID(str(value)).int


class FriendRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="friends_sent_requests"
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="friends_received_requests"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(sender=F("receiver")), name="friends_request_no_self"
            ),
            models.CheckConstraint(
                condition=Q(status__in=["pending", "accepted", "rejected", "cancelled"]),
                name="friends_request_status_valid",
            ),
            # A pending request has no response time; every other status has one.
            models.CheckConstraint(
                condition=Q(status="pending", responded_at__isnull=True)
                | (~Q(status="pending") & Q(responded_at__isnull=False)),
                name="friends_request_responded_consistent",
            ),
            # At most one pending request per direction ...
            models.UniqueConstraint(
                fields=["sender", "receiver"],
                condition=Q(status="pending"),
                name="friends_request_one_pending_per_direction",
            ),
            # ... and at most one pending request per PAIR (A->B and B->A can not both be pending).
            models.UniqueConstraint(
                Least("sender", "receiver"),
                Greatest("sender", "receiver"),
                condition=Q(status="pending"),
                name="friends_request_one_pending_per_pair",
            ),
        ]
        indexes = [
            models.Index(fields=["receiver", "status", "-created_at"], name="friends_req_recv_idx"),
            models.Index(fields=["sender", "status", "-created_at"], name="friends_req_sent_idx"),
        ]

    def __str__(self):
        return f"{self.sender_id} -> {self.receiver_id} ({self.status})"


class Friendship(models.Model):
    """
    A bidirectional friendship, stored once. `user1_id < user2_id` always holds
    (enforced by `save()` and by a CHECK constraint), so (A, B) and (B, A) are the same row.
    Who sent the original request is irrelevant and not stored here.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user1 = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="friends_as_user1"
    )
    user2 = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="friends_as_user2"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # Also rejects self-friendship (user1 == user2) because the comparison is strict.
            models.CheckConstraint(
                condition=Q(user1_id__lt=F("user2_id")), name="friends_friendship_ordered"
            ),
            models.UniqueConstraint(fields=["user1", "user2"], name="friends_friendship_unique"),
        ]
        indexes = [
            # The unique constraint already serves lookups that start with user1.
            models.Index(fields=["user2", "user1"], name="friends_fs_user2_idx"),
            models.Index(fields=["user1", "-created_at"], name="friends_fs_user1_new_idx"),
        ]

    @staticmethod
    def normalize(a, b):
        """Return (low, high) user ids in canonical order."""
        a = a if isinstance(a, uuid.UUID) else uuid.UUID(str(a))
        b = b if isinstance(b, uuid.UUID) else uuid.UUID(str(b))
        return (a, b) if a.int <= b.int else (b, a)

    def save(self, *args, **kwargs):
        if self.user1_id and self.user2_id and _uuid_key(self.user1_id) > _uuid_key(self.user2_id):
            self.user1_id, self.user2_id = self.user2_id, self.user1_id
        super().save(*args, **kwargs)

    def other_user_id(self, user_id):
        return self.user2_id if self.user1_id == user_id else self.user1_id

    def __str__(self):
        return f"{self.user1_id} <-> {self.user2_id}"


class UserBlock(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="friends_blocks_made"
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="friends_blocks_received"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(blocker=F("blocked")), name="friends_block_no_self"
            ),
            models.UniqueConstraint(fields=["blocker", "blocked"], name="friends_block_unique"),
        ]
        indexes = [
            models.Index(fields=["blocked", "blocker"], name="friends_block_blocked_idx"),
        ]

    def __str__(self):
        return f"{self.blocker_id} blocks {self.blocked_id}"
