"""
Real-time hook. The REST API is complete on its own; this is the single seam where WebSockets plug in.

`publish(user_ids, event, payload)` is a no-op unless Django Channels is installed AND a channel layer is
configured (settings.CHANNEL_LAYERS). Then it fans out to the group "user_<id>" for each recipient, so a
consumer that joins "user_<id>" on connect receives {"type": "chat.event", "event": ..., "payload": ...}.
Nothing in the request path depends on Redis being up: failures here are swallowed and logged.
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def publish(user_ids, event, payload):
    if not getattr(settings, "CHANNEL_LAYERS", None):
        return
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
    except ImportError:
        return
    try:
        layer = get_channel_layer()
        if layer is None:
            return
        for uid in set(user_ids):
            async_to_sync(layer.group_send)(
                f"user_{uid}", {"type": "chat.event", "event": event, "payload": payload})
    except Exception:  # never let a broken Redis break sending a message
        logger.exception("Realtime publish failed for event %s", event)
