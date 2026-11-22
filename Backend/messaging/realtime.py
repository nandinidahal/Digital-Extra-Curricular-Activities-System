"""
Low-level real-time delivery through the Channels layer.

Every event goes to a per-USER group ("messaging.user.<uuid>"), never to a shared
conversation group. The server therefore decides the recipients of every single event at
send time (membership, blocks, privacy), and a socket can never "subscribe" to a
conversation it does not belong to. Conversation-scoped sockets simply filter the events of
their user group by conversation id.

Sending never raises: if Redis is down the database write has already succeeded and the
client will see the change on its next fetch; the failure is logged.
"""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger("messaging")

EVENT_HANDLER = "messaging.event"  # -> MessagingConsumer.messaging_event


def user_group(user_id):
    return f"messaging.user.{user_id}"


def build_event(event_type, data, conversation_id=None):
    payload = {"type": event_type, "data": data}
    if conversation_id is not None:
        payload["conversation_id"] = str(conversation_id)
    return payload


def send_to_user(user_id, event_type, data, conversation_id=None):
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(
            user_group(user_id),
            {"type": EVENT_HANDLER, "payload": build_event(event_type, data, conversation_id)},
        )
    except Exception:  # never break the request because the channel layer failed
        logger.exception("Messaging: real-time delivery of %s to %s failed", event_type, user_id)
