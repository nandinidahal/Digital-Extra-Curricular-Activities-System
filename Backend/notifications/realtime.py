"""
Real-time delivery through the existing Channels layer (Redis in production).

Each user has a private group "notifications.user.<uuid>". Only the consumer for an
authenticated socket of THAT user joins it (the group name is derived from the JWT user, never
from client input), so nobody can subscribe to somebody else's notifications.

Sending never raises: the REST API stays the source of truth when Redis is unavailable.
"""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger("notifications")

EVENT_HANDLER = "notification.event"  # -> NotificationConsumer.notification_event


def user_group(user_id):
    return f"notifications.user.{user_id}"


def send_to_user(user_id, event_type, data):
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(
            user_group(user_id), {"type": EVENT_HANDLER, "payload": {"type": event_type, "data": data}}
        )
    except Exception:
        logger.exception("Notifications: real-time delivery of %s to %s failed", event_type, user_id)
