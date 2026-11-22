"""
WebSocket consumer for real-time messaging.

Routes:  ws/messaging/                                  (inbox: all conversations)
         ws/messaging/conversations/<conversation_id>/  (one conversation)

Envelope, client -> server:
    {"type": "message.send", "request_id": "c-17", "conversation_id": "<uuid>", "data": {...}}
    (conversation_id may be omitted on a conversation socket)
Server -> client:
    {"type": "message.new", "conversation_id": "<uuid>", "data": {...}}
    {"type": "ack",   "request_id": "c-17", "data": {...}}
    {"type": "error", "request_id": "c-17", "code": "message_limit_reached", "message": "...", ...}

Every client event goes through the SAME services as REST (membership, blocks, friendship,
pre-friendship limit, validation, idempotency). The sender is always the authenticated
socket user - any sender/user id in the payload is ignored.

Close codes: 4401 not authenticated / token expired, 4403 account not allowed,
4404 conversation not found (or not a participant), 4429 too many events.
"""
import logging
import time
import uuid

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import APIException, ValidationError

from friends import services as friends
from friends.validators import is_available

from . import presence, realtime, selectors, services
from .exceptions import ConversationNotFound
from .models import ConversationParticipant
from .serializers import MessageSerializer
from .throttles import MessageActionThrottle, MessageSendThrottle, WebSocketEventThrottle, check_rate

logger = logging.getLogger("messaging")

HEARTBEAT_INTERVAL_SECONDS = 25
TYPING_MIN_INTERVAL_SECONDS = 2.0
MAX_ABUSE_STRIKES = 20


def _str_or_none(value, max_length=64):
    return value if isinstance(value, str) and len(value) <= max_length else None


def _uuid_or_error(value, field):
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError({field: ["Must be a valid UUID."]})


# ---------------------------------------------------------------------------
# Sync helpers (run in a worker thread)
# ---------------------------------------------------------------------------
def _serialize_message(message_id, viewer):
    message = selectors.message_page_queryset_unscoped().get(pk=message_id)
    return MessageSerializer(message, context={"viewer": viewer}).data


def _is_participant(user, conversation_id):
    return ConversationParticipant.objects.filter(
        conversation_id=conversation_id, user=user, is_active=True, conversation__is_active=True
    ).exists()


def _conversation_peer_ids(user_id, conversation_id=None):
    """Other participants of the user's conversations (or of one conversation)."""
    mine = ConversationParticipant.objects.filter(user_id=user_id, is_active=True)
    if conversation_id is not None:
        mine = mine.filter(conversation_id=conversation_id)
    return set(
        ConversationParticipant.objects.filter(
            conversation_id__in=mine.values("conversation_id"), is_active=True
        )
        .exclude(user_id=user_id)
        .values_list("user_id", flat=True)
    )


def _presence_watchers(user_id):
    """Users allowed to see `user_id`'s presence (visibility is symmetric for every policy)."""
    peers = _conversation_peer_ids(user_id)
    if not peers:
        return []
    friend_ids = friends.get_friend_ids(user_id)
    hidden = friends.get_hidden_user_ids(user_id)
    return [p for p in peers if presence.presence_visible(user_id, p, friend_ids=friend_ids, hidden_ids=hidden)]


def _broadcast_presence(user_id, is_online):
    from django.utils import timezone

    data = {
        "user_id": str(user_id),
        "is_online": is_online,
        "last_seen_at": None if is_online else timezone.now().isoformat(),
    }
    for watcher in _presence_watchers(user_id):
        realtime.send_to_user(watcher, "user.presence", data)


def _typing_recipients(user, conversation_id):
    if not _is_participant(user, conversation_id):
        raise ConversationNotFound()
    hidden = friends.get_hidden_user_ids(user.pk)
    return [
        uid for uid in _conversation_peer_ids(user.pk, conversation_id) if uid not in hidden
    ]


def _send_typing(user, conversation_id, is_typing):
    ttl = getattr(settings, "MESSAGING_TYPING_TTL_SECONDS", 6)
    for uid in _typing_recipients(user, conversation_id):
        realtime.send_to_user(
            uid, "user.typing",
            {"user_id": str(user.pk), "is_typing": bool(is_typing), "expires_in": ttl},
            conversation_id,
        )


def _connect_presence(user_id):
    if presence.connect(user_id):
        _broadcast_presence(user_id, True)


def _disconnect_presence(user_id):
    if presence.disconnect(user_id):
        _broadcast_presence(user_id, False)


def _heartbeat(user_id):
    if presence.heartbeat(user_id):
        _broadcast_presence(user_id, True)


# ---------------------------------------------------------------------------
class MessagingConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        self.conversation_id = None
        self.peer_ids = set()
        self.presence_registered = False
        self.group = None
        self.last_typing = {}
        self.strikes = 0

        if not (self.user and self.user.is_authenticated):
            await self.close(code=4401)
            return
        if not is_available(self.user):
            await self.close(code=4403)
            return
        conversation_id = self.scope["url_route"]["kwargs"].get("conversation_id")
        if conversation_id is not None:
            if not await database_sync_to_async(_is_participant)(self.user, conversation_id):
                await self.close(code=4404)
                return
            self.conversation_id = str(conversation_id)
            self.peer_ids = {
                str(p) for p in await database_sync_to_async(_conversation_peer_ids)(self.user.pk, conversation_id)
            }

        self.group = realtime.user_group(self.user.pk)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept(subprotocol=self.scope.get("accepted_subprotocol"))
        await database_sync_to_async(_connect_presence)(self.user.pk)
        self.presence_registered = True
        await self.send_json(
            {
                "type": "connection.ready",
                "data": {
                    "user_id": str(self.user.pk),
                    "conversation_id": self.conversation_id,
                    "heartbeat_interval": HEARTBEAT_INTERVAL_SECONDS,
                },
            }
        )

    async def disconnect(self, code):
        if self.group:
            await self.channel_layer.group_discard(self.group, self.channel_name)
        if getattr(self, "presence_registered", False):
            self.presence_registered = False
            await database_sync_to_async(_disconnect_presence)(self.user.pk)

    # ----- helpers ----------------------------------------------------------
    def _token_expired(self):
        exp = self.scope.get("token_exp")
        return exp is not None and time.time() >= exp

    async def _close_expired(self):
        await self.send_json({"type": "auth.expired", "data": {}})
        await self.close(code=4401)

    async def _error(self, request_id, code, message, **extra):
        await self.send_json(
            {"type": "error", "request_id": request_id, "code": code, "message": message, **extra}
        )

    async def _ack(self, request_id, data=None):
        await self.send_json({"type": "ack", "request_id": request_id, "data": data or {}})

    def _target_conversation(self, content):
        requested = content.get("conversation_id")
        if self.conversation_id is not None:
            if requested is not None and str(requested) != self.conversation_id:
                raise ValidationError({"conversation_id": ["This socket is bound to another conversation."]})
            return uuid.UUID(self.conversation_id)
        if requested is None:
            raise ValidationError({"conversation_id": ["This field is required on the inbox socket."]})
        return _uuid_or_error(requested, "conversation_id")

    async def _rate(self, throttle_class):
        allowed, wait = await database_sync_to_async(check_rate)(throttle_class, self.user)
        if not allowed:
            raise _Throttled(wait)

    # ----- inbound ----------------------------------------------------------
    async def receive_json(self, content, **kwargs):
        if self._token_expired():
            await self._close_expired()
            return
        if not isinstance(content, dict) or not isinstance(content.get("type"), str):
            await self._error(None, "invalid_event", "Events must be JSON objects with a string `type`.")
            await self._strike()
            return
        event_type = content["type"]
        request_id = _str_or_none(content.get("request_id"))
        data = content.get("data") or {}
        if not isinstance(data, dict):
            await self._error(request_id, "invalid_event", "`data` must be a JSON object.")
            return
        handler = self.HANDLERS.get(event_type)
        if handler is None:
            await self._error(request_id, "unknown_event", f"Unknown event type: {event_type[:50]}")
            await self._strike()
            return
        try:
            if event_type not in ("presence.heartbeat", "ping", "message.typing"):
                await self._rate(WebSocketEventThrottle)
            await handler(self, content, data, request_id)
        except _Throttled as exc:
            await self._error(request_id, "throttled", "Too many events. Slow down.", retry_after=exc.wait)
            await self._strike()
        except ValidationError as exc:
            await self._error(request_id, "validation_error", "Please correct the highlighted errors.",
                              errors=_plain(exc.detail))
        except DjangoValidationError as exc:
            await self._error(request_id, "validation_error", "Invalid data.", errors={"data": exc.messages})
        except APIException as exc:
            codes = exc.get_codes()
            await self._error(
                request_id, codes if isinstance(codes, str) else getattr(exc, "default_code", "error"),
                str(exc.detail), status=exc.status_code, **(getattr(exc, "extra", None) or {}),
            )
        except Exception:
            logger.exception("Messaging WebSocket handler %s failed", event_type)
            await self._error(request_id, "server_error", "Something went wrong. Please try again.")

    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        if bytes_data is not None:
            await self._error(None, "invalid_event", "Binary frames are not supported.")
            return
        if text_data is not None and len(text_data) > 64 * 1024:
            await self._error(None, "invalid_event", "Event too large.")
            await self._strike()
            return
        try:
            await super().receive(text_data=text_data, bytes_data=bytes_data, **kwargs)
        except ValueError:  # invalid JSON
            await self._error(None, "invalid_event", "Events must be valid JSON.")
            await self._strike()

    async def _strike(self):
        self.strikes += 1
        if self.strikes >= MAX_ABUSE_STRIKES:
            await self.close(code=4429)

    # ----- event handlers ---------------------------------------------------
    async def on_send(self, content, data, request_id):
        await self._rate(MessageSendThrottle)
        conversation_id = self._target_conversation(content)
        client_id = data.get("client_id")
        reply_to_id = data.get("reply_to_id")
        result = await database_sync_to_async(services.send_message)(
            self.user, conversation_id,
            content=data.get("content", ""),
            reply_to_id=_uuid_or_error(reply_to_id, "reply_to_id") if reply_to_id else None,
            client_id=_uuid_or_error(client_id, "client_id") if client_id else None,
        )
        payload = await database_sync_to_async(_serialize_message)(result.message.pk, self.user)
        state = await database_sync_to_async(self._state)(conversation_id)
        await self._ack(request_id, {"message": payload, "created": result.created, "messaging": state})

    def _state(self, conversation_id):
        participation = selectors.get_participation(self.user, conversation_id)
        return selectors.messaging_state(self.user, participation.conversation)

    async def on_edit(self, content, data, request_id):
        await self._rate(MessageActionThrottle)
        message_id = _uuid_or_error(data.get("message_id"), "message_id")
        if not isinstance(data.get("content"), str):
            raise ValidationError({"content": ["This field is required."]})
        message = await database_sync_to_async(services.edit_message)(self.user, message_id, data["content"])
        await self._ack(request_id, {"message": await database_sync_to_async(_serialize_message)(message.pk, self.user)})

    async def on_delete(self, content, data, request_id):
        await self._rate(MessageActionThrottle)
        message_id = _uuid_or_error(data.get("message_id"), "message_id")
        scope = data.get("scope", "me")
        if scope == "everyone":
            await database_sync_to_async(services.delete_for_everyone)(self.user, message_id)
        elif scope == "me":
            await database_sync_to_async(services.delete_for_me)(self.user, message_id)
        else:
            raise ValidationError({"scope": ['Use "me" or "everyone".']})
        await self._ack(request_id, {"message_id": str(message_id), "scope": scope})

    async def on_reaction(self, content, data, request_id):
        await self._rate(MessageActionThrottle)
        message_id = _uuid_or_error(data.get("message_id"), "message_id")
        reaction_type = data.get("reaction_type")
        if reaction_type is None:
            await database_sync_to_async(services.remove_reaction)(self.user, message_id)
        else:
            await database_sync_to_async(services.set_reaction)(self.user, message_id, reaction_type)
        await self._ack(request_id, {"message_id": str(message_id), "reaction_type": reaction_type})

    async def on_read(self, content, data, request_id):
        conversation_id = self._target_conversation(content)
        up_to = data.get("up_to_message_id")
        ids, read_at = await database_sync_to_async(services.mark_read)(
            self.user, conversation_id, _uuid_or_error(up_to, "up_to_message_id") if up_to else None
        )
        await self._ack(request_id, {"message_ids": [str(i) for i in ids], "read_at": read_at.isoformat()})

    async def on_delivered(self, content, data, request_id):
        raw = data.get("message_ids")
        if not isinstance(raw, list) or not raw or len(raw) > 500:
            raise ValidationError({"message_ids": ["Send a list of 1-500 message ids."]})
        ids = [_uuid_or_error(v, "message_ids") for v in raw]
        changed = await database_sync_to_async(services.mark_delivered)(self.user, ids)
        await self._ack(request_id, {"message_ids": [str(i) for i in changed]})

    async def on_typing(self, content, data, request_id):
        conversation_id = self._target_conversation(content)
        is_typing = bool(data.get("is_typing", True))
        key = str(conversation_id)
        now = time.monotonic()
        # "started typing" is forwarded at most every 2 s per conversation; "stopped" always.
        if is_typing and now - self.last_typing.get(key, 0) < TYPING_MIN_INTERVAL_SECONDS:
            return
        self.last_typing[key] = now if is_typing else 0
        await database_sync_to_async(_send_typing)(self.user, conversation_id, is_typing)

    async def on_heartbeat(self, content, data, request_id):
        await database_sync_to_async(_heartbeat)(self.user.pk)
        if request_id:
            await self._ack(request_id)

    async def on_ping(self, content, data, request_id):
        await self.send_json({"type": "pong", "request_id": request_id, "data": {}})

    HANDLERS = {
        "message.send": on_send,
        "message.edit": on_edit,
        "message.delete": on_delete,
        "message.reaction": on_reaction,
        "message.read": on_read,
        "message.delivered": on_delivered,
        "message.typing": on_typing,
        "presence.heartbeat": on_heartbeat,
        "ping": on_ping,
    }

    # ----- outbound (from realtime.send_to_user) -----------------------------
    async def messaging_event(self, event):
        if self._token_expired():
            await self._close_expired()
            return
        payload = event["payload"]
        if self.conversation_id is not None:
            event_conversation = payload.get("conversation_id")
            if event_conversation is None:
                # presence: only for the other participant of this conversation
                if (payload.get("data") or {}).get("user_id") not in self.peer_ids:
                    return
            elif event_conversation != self.conversation_id:
                return
        await self.send_json(payload)


class _Throttled(Exception):
    def __init__(self, wait):
        super().__init__("throttled")
        self.wait = int(wait) + 1 if wait else None


def _plain(detail):
    if isinstance(detail, dict):
        return {k: _plain(v) for k, v in detail.items()}
    if isinstance(detail, (list, tuple)):
        return [_plain(v) for v in detail]
    return str(detail)
