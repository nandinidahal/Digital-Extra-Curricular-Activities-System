"""
Notifications data model.

* One central table for every module (no module keeps its own notification table).
* `dedupe_key` + UNIQUE(recipient, dedupe_key) makes "notify once" idempotent in the database
  (double clicks, retried requests, cron re-runs).
* `group_key` + partial UNIQUE(recipient, group_key) WHERE unread keeps at most ONE unread
  notification per group, e.g. one "new messages from Bob" instead of one per message.
* The target is stored as (type, id) strings, not a foreign key, so deleting a post or an
  achievement never deletes the user's notification history.
* E-mail delivery is tracked per notification; `sent` is written only after the SMTP backend
  reported success.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q

from common.models import BaseModel

from .types import CATEGORIES, TYPE_CHOICES

TITLE_MAX_LENGTH = 150
MESSAGE_MAX_LENGTH = 500


class Notification(BaseModel):
    class EmailStatus(models.TextChoices):
        NOT_REQUESTED = "not_requested", "Not requested"
        PENDING = "pending", "Pending"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications_caused",
    )
    notification_type = models.CharField(max_length=64, choices=TYPE_CHOICES)
    category = models.CharField(max_length=20, choices=[(c, c) for c in CATEGORIES])
    title = models.CharField(max_length=TITLE_MAX_LENGTH)
    message = models.CharField(max_length=MESSAGE_MAX_LENGTH, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    target_type = models.CharField(max_length=40, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    action_url = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    dedupe_key = models.CharField(max_length=200, null=True, blank=True)
    group_key = models.CharField(max_length=200, null=True, blank=True)
    email_status = models.CharField(
        max_length=20, choices=EmailStatus.choices, default=EmailStatus.NOT_REQUESTED
    )
    email_attempts = models.PositiveSmallIntegerField(default=0)
    emailed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "dedupe_key"],
                condition=Q(dedupe_key__isnull=False),
                name="notifications_dedupe_unique",
            ),
            models.UniqueConstraint(
                fields=["recipient", "group_key"],
                condition=Q(group_key__isnull=False, is_read=False),
                name="notifications_one_unread_per_group",
            ),
            models.CheckConstraint(
                condition=Q(is_read=False, read_at__isnull=True) | Q(is_read=True, read_at__isnull=False),
                name="notifications_read_consistent",
            ),
        ]
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"], name="notif_recipient_unread_idx"),
            models.Index(fields=["recipient", "-created_at"], name="notif_recipient_list_idx"),
            models.Index(fields=["recipient", "category"], name="notif_recipient_cat_idx"),
            models.Index(fields=["email_status", "created_at"], name="notif_email_queue_idx"),
            models.Index(fields=["expires_at"], name="notif_expiry_idx"),
        ]

    def __str__(self):
        return f"{self.notification_type} -> {self.recipient_id}"


class NotificationPreference(BaseModel):
    """
    One row per user, created lazily with every switch ON. Account/security notifications have
    no switch: they cannot be disabled.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preference"
    )
    friend_requests = models.BooleanField(default=True)
    social_interactions = models.BooleanField(default=True)
    messages = models.BooleanField(default=True)
    announcements = models.BooleanField(default=True)
    achievements = models.BooleanField(default=True)
    system_notifications = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    realtime_notifications = models.BooleanField(default=True)

    SWITCHES = (
        "friend_requests",
        "social_interactions",
        "messages",
        "announcements",
        "achievements",
        "system_notifications",
        "email_notifications",
        "realtime_notifications",
    )

    def __str__(self):
        return f"Notification preferences of {self.user_id}"
