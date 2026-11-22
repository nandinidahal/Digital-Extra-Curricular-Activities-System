"""
WebSocket: /ws/notifications/

Authentication is done by the project's existing JWT middleware (messaging/ws_auth.py):
    new WebSocket(url, ["deas.jwt", accessToken])           (preferred)
    or a one-time ticket from POST /api/messaging/ws-ticket/  -> ?ticket=...

Server -> client events:
    connection.ready           {"user_id", "unread_count"}
    notification.new           {"notification": {...}, "unread_count": n}
    notification.updated       {"notification": {...}, "unread_count": n}   (grouped notification bumped)
    notification.read          {"notification_ids": [...], "unread_count": n}
    notification.deleted       {"notification_ids": [...] | "all": true, "unread_count": n}
    notification.count_updated {"unread_count": n}
    pong / auth.expired / error
Client -> server: {"type": "ping"} and {"type": "count"} only. Everything else uses REST.

Close codes: 4401 not authenticated / token expired, 4403 account inactive.
"""
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from . import realtime


@database_sync_to_async
def _unread(user_id):
    from .services import unread_count

    return unread_count(user_id)


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.group = None
        self.user = self.scope.get("user")
        if not (self.user and self.user.is_authenticated):
            await self.close(code=4401)
            return
        if not self.user.is_active:
            await self.close(code=4403)
            return
        # The group is derived from the authenticated user only, never from client input.
        self.group = realtime.user_group(self.user.pk)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept(subprotocol=self.scope.get("accepted_subprotocol"))
        await self.send_json(
            {"type": "connection.ready", "data": {"user_id": str(self.user.pk), "unread_count": await _unread(self.user.pk)}}
        )

    async def disconnect(self, code):
        if self.group:
            await self.channel_layer.group_discard(self.group, self.channel_name)
            self.group = None

    def _token_expired(self):
        exp = self.scope.get("token_exp")
        return exp is not None and time.time() >= exp

    async def _close_expired(self):
        await self.send_json({"type": "auth.expired", "data": {}})
        await self.close(code=4401)

    async def receive_json(self, content, **kwargs):
        if self._token_expired():
            await self._close_expired()
            return
        event_type = content.get("type") if isinstance(content, dict) else None
        if event_type == "ping":
            await self.send_json({"type": "pong", "data": {}})
        elif event_type == "count":
            await self.send_json({"type": "notification.count_updated", "data": {"unread_count": await _unread(self.user.pk)}})
        else:
            await self.send_json({"type": "error", "code": "unsupported_event", "message": "Use the REST API for this action."})

    async def notification_event(self, event):
        if self._token_expired():
            await self._close_expired()
            return
        await self.send_json(event["payload"])
