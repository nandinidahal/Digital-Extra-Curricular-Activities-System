from django.conf import settings
from django.db import models


class UserPresence(models.Model):
    """
    Last-seen time. Live "online" state is NOT stored here: it lives in the cache (Redis in
    production) and is refreshed by WebSocket heartbeats. This row is written only when a
    user's LAST connection closes, so heartbeats never cause database writes.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="messaging_presence",
    )
    last_seen_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"presence of {self.user_id}"
