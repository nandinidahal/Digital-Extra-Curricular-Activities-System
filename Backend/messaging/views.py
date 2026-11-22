"""
Thin HTTP layer: validate input, call a service/selector, shape the project-wide envelope
    {"success": true, "message": "...", "data": {...}}
Errors use accounts.exceptions.api_exception_handler.
"""
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import FileResponse
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from accounts.responses import success_response
from profiles.authentication import OptionalJWTAuthentication

from . import selectors, services
from .exceptions import AttachmentNotFound, PayloadTooLarge
from .models import MessageAttachment
from .pagination import ConversationPagination, MessageCursorPagination, SearchPagination
from .permissions import IsAvailableMember
from .serializers import (
    ArchiveSerializer,
    DeleteMessageSerializer,
    EditMessageSerializer,
    ForwardSerializer,
    MarkDeliveredSerializer,
    MarkReadSerializer,
    MessageSerializer,
    MuteSerializer,
    ReactionSerializer,
    ReplySerializer,
    SendMessageSerializer,
    StartConversationSerializer,
    conversation_data,
    verify_attachment_signature,
)
from .throttles import AttachmentUploadThrottle, MessageActionThrottle, MessageSendThrottle
from .validators import file_max_bytes, max_attachments

WS_TICKET_KEY = "messaging:wsticket:%s"
WS_TICKET_TTL_SECONDS = 30
_MULTIPART_OVERHEAD = 256 * 1024


class _MessagingView(APIView):
    permission_classes = [IsAuthenticated, IsAvailableMember]
    parser_classes = [JSONParser]

    def message_data(self, message):
        message = selectors.message_page_queryset_unscoped().get(pk=message.pk)
        return MessageSerializer(message, context={"viewer": self.request.user, "request": self.request}).data


def _conversation_response(request, conversation_id, message, status_code=status.HTTP_200_OK):
    participation = selectors.conversation_detail(request.user, conversation_id)
    state = selectors.messaging_state(
        request.user, participation.conversation,
        other_user=participation.others[0].user if participation.others else None,
    )
    data = conversation_data(participation, request.user, request, messaging=state)
    return success_response(data, message, status_code)


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------
class ConversationListCreateView(_MessagingView):
    """
    GET  /api/messaging/conversations/?archived=false&page=1
    POST /api/messaging/conversations/   {"user_id": "<uuid>"}  -> start or reuse
    """

    def get_throttles(self):
        return [MessageActionThrottle()] if self.request.method == "POST" else []

    def get(self, request):
        archived = request.query_params.get("archived", "false").lower() in ("1", "true", "yes")
        paginator = ConversationPagination()
        page = paginator.paginate_queryset(
            selectors.conversation_list(request.user, archived=archived), request, view=self
        )
        page = selectors.attach_conversation_extras(page, request.user)
        return paginator.get_paginated_response(
            [conversation_data(p, request.user, request) for p in page]
        )

    def post(self, request):
        serializer = StartConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = services.start_direct_conversation(request.user, serializer.validated_data["user_id"])
        if result.created:
            return _conversation_response(
                request, result.conversation.pk, "Conversation started.", status.HTTP_201_CREATED
            )
        return _conversation_response(request, result.conversation.pk, "Existing conversation returned.")


class ConversationDetailView(_MessagingView):
    """GET /api/messaging/conversations/<id>/ - includes the `messaging` permission state."""

    def get(self, request, conversation_id):
        return _conversation_response(request, conversation_id, "")


class ConversationMuteView(_MessagingView):
    """PATCH {"is_muted": true|false}"""

    throttle_classes = [MessageActionThrottle]

    def patch(self, request, conversation_id):
        serializer = MuteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        muted = serializer.validated_data["is_muted"]
        services.set_muted(request.user, conversation_id, muted)
        return _conversation_response(
            request, conversation_id, "Conversation muted." if muted else "Conversation unmuted."
        )


class ConversationArchiveView(_MessagingView):
    """PATCH {"is_archived": true|false}"""

    throttle_classes = [MessageActionThrottle]

    def patch(self, request, conversation_id):
        serializer = ArchiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        archived = serializer.validated_data["is_archived"]
        services.set_archived(request.user, conversation_id, archived)
        return _conversation_response(
            request, conversation_id, "Conversation archived." if archived else "Conversation unarchived."
        )


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------
def _check_upload_size(request):
    """Refuse obviously oversized multipart bodies before parsing them."""
    limit = file_max_bytes() * max_attachments() + _MULTIPART_OVERHEAD
    try:
        length = int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        length = 0
    if length > limit:
        raise PayloadTooLarge()


def _send_payload(request, serializer_class):
    if (request.content_type or "").startswith("multipart/"):
        _check_upload_size(request)
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = dict(serializer.validated_data)
    files = request.FILES.getlist("attachments") if request.FILES else []
    data.pop("attachments", None)
    return data, files


def _send_response(view, result, conversation_id):
    request = view.request
    participation = selectors.get_participation(request.user, conversation_id)
    state = selectors.messaging_state(request.user, participation.conversation)
    data = {"message": view.message_data(result.message), "messaging": state}
    if result.created:
        return success_response(data, "Message sent.", status.HTTP_201_CREATED)
    return success_response(data, "Message already sent (duplicate client_id).", status.HTTP_200_OK)


class ConversationMessagesView(_MessagingView):
    """
    GET  /api/messaging/conversations/<id>/messages/?cursor=...&page_size=30 (newest first)
    POST /api/messaging/conversations/<id>/messages/
         JSON:      {"content": "...", "reply_to_id": "<uuid>", "client_id": "<uuid>"}
         multipart: content, reply_to_id, client_id, attachments (repeat for several files)
    """

    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_throttles(self):
        if self.request.method == "POST":
            return [MessageSendThrottle(), AttachmentUploadThrottle()]
        return []

    def get(self, request, conversation_id):
        selectors.get_participation(request.user, conversation_id)
        paginator = MessageCursorPagination()
        page = paginator.paginate_queryset(
            selectors.message_page_queryset(request.user, conversation_id), request, view=self
        )
        # Loading history is a real delivery to this user's client.
        services.mark_page_delivered(request.user, page)
        data = MessageSerializer(page, many=True, context={"viewer": request.user, "request": request}).data
        return paginator.get_paginated_response(data)

    def post(self, request, conversation_id):
        data, files = _send_payload(request, SendMessageSerializer)
        result = services.send_message(
            request.user, conversation_id,
            content=data.get("content", ""), files=files,
            reply_to_id=data.get("reply_to_id"), client_id=data.get("client_id"),
        )
        return _send_response(self, result, conversation_id)


class MessageDetailView(_MessagingView):
    """
    PATCH  /api/messaging/messages/<id>/  {"content": "..."}  - edit own message
    DELETE /api/messaging/messages/<id>/?scope=me|everyone    - default "me"
    """

    throttle_classes = [MessageActionThrottle]

    def patch(self, request, message_id):
        serializer = EditMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = services.edit_message(request.user, message_id, serializer.validated_data["content"])
        return success_response(self.message_data(message), "Message updated.")

    def delete(self, request, message_id):
        serializer = DeleteMessageSerializer(data={"scope": request.query_params.get("scope", "me")})
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data["scope"] == "everyone":
            return _delete_for_everyone(self, message_id)
        return _delete_for_me(message_id, request)


def _delete_for_me(message_id, request):
    services.delete_for_me(request.user, message_id)
    return success_response({"message_id": str(message_id), "scope": "me"}, "Message deleted for you.")


def _delete_for_everyone(view, message_id):
    message = services.delete_for_everyone(view.request.user, message_id)
    return success_response(view.message_data(message), "Message deleted for everyone.")


class DeleteForMeView(_MessagingView):
    throttle_classes = [MessageActionThrottle]

    def post(self, request, message_id):
        return _delete_for_me(message_id, request)


class DeleteForEveryoneView(_MessagingView):
    throttle_classes = [MessageActionThrottle]

    def post(self, request, message_id):
        return _delete_for_everyone(self, message_id)


class ReplyView(_MessagingView):
    """POST /api/messaging/messages/<id>/reply/  (JSON or multipart, same fields as sending)"""

    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_throttles(self):
        return [MessageSendThrottle(), AttachmentUploadThrottle()]

    def post(self, request, message_id):
        data, files = _send_payload(request, ReplySerializer)
        result = services.reply_to_message(
            request.user, message_id, content=data.get("content", ""), files=files,
            client_id=data.get("client_id"),
        )
        return _send_response(self, result, result.message.conversation_id)


class ForwardView(_MessagingView):
    """POST /api/messaging/messages/<id>/forward/  {"conversation_id": "..."} or {"user_id": "..."}"""

    throttle_classes = [MessageSendThrottle]

    def post(self, request, message_id):
        serializer = ForwardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = services.forward_message(request.user, message_id, **serializer.validated_data)
        return _send_response(self, result, result.message.conversation_id)


class ReactionView(_MessagingView):
    """POST {"reaction_type": "like"} adds or changes; DELETE removes (idempotent)."""

    throttle_classes = [MessageActionThrottle]

    def post(self, request, message_id):
        serializer = ReactionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = services.set_reaction(request.user, message_id, serializer.validated_data["reaction_type"])
        return success_response(self.message_data(message), "Reaction saved.")

    def delete(self, request, message_id):
        message = services.remove_reaction(request.user, message_id)
        return success_response(self.message_data(message), "Reaction removed.")


# ---------------------------------------------------------------------------
# Receipts
# ---------------------------------------------------------------------------
class MarkReadView(_MessagingView):
    """POST {"up_to_message_id": "<uuid>"} (optional; default: everything received so far)"""

    throttle_classes = [MessageActionThrottle]

    def post(self, request, conversation_id):
        serializer = MarkReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids, read_at = services.mark_read(
            request.user, conversation_id, serializer.validated_data.get("up_to_message_id")
        )
        return success_response(
            {
                "marked_read": len(ids),
                "message_ids": [str(i) for i in ids],
                "read_at": read_at.isoformat(),
                "unread_count": selectors.unread_count(request.user, conversation_id),
            },
            "Messages marked as read.",
        )


class MarkDeliveredView(_MessagingView):
    """POST {"message_ids": [...]} - delivery acknowledgement for clients without a socket."""

    throttle_classes = [MessageActionThrottle]

    def post(self, request, conversation_id):
        selectors.get_participation(request.user, conversation_id)
        serializer = MarkDeliveredSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = services.mark_delivered(
            request.user,
            selectors.visible_messages(request.user)
            .filter(conversation_id=conversation_id, pk__in=serializer.validated_data["message_ids"])
            .values_list("pk", flat=True),
        )
        return success_response({"message_ids": [str(i) for i in ids]}, "Delivery recorded.")


class UnreadCountView(_MessagingView):
    def get(self, request, conversation_id):
        selectors.get_participation(request.user, conversation_id)
        return success_response(
            {"conversation_id": str(conversation_id),
             "unread_count": selectors.unread_count(request.user, conversation_id)}
        )


class TotalUnreadCountView(_MessagingView):
    """GET /api/messaging/unread-count/ - badge for the navigation bar (muted excluded)."""

    def get(self, request):
        return success_response({"unread_count": selectors.total_unread_count(request.user)})


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
class SearchView(_MessagingView):
    """GET /api/messaging/conversations/<id>/search/?q=text  (only inside your own conversation)"""

    def get(self, request, conversation_id):
        selectors.get_participation(request.user, conversation_id)
        query = (request.query_params.get("q") or "").strip()
        if len(query) < 2 or len(query) > 100:
            raise ValidationError({"q": ["Search text must be between 2 and 100 characters."]})
        paginator = SearchPagination()
        page = paginator.paginate_queryset(
            selectors.search_messages(request.user, conversation_id, query), request, view=self
        )
        data = MessageSerializer(page, many=True, context={"viewer": request.user, "request": request}).data
        return paginator.get_paginated_response(data)


# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------
class AttachmentDownloadView(APIView):
    """
    GET /api/messaging/attachments/<id>/download/?sig=<signed token>   (for <img src>, links)
    GET /api/messaging/attachments/<id>/download/  + Authorization: Bearer <jwt>

    Access is re-checked on every request: the (signed or authenticated) user must still be an
    active participant, the message must not be deleted or hidden for them, and the account must
    still be active. Files are never reachable through MEDIA_URL.
    """

    authentication_classes = [OptionalJWTAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, attachment_id):
        signature = request.query_params.get("sig")
        if signature:
            verified = verify_attachment_signature(
                signature, getattr(settings, "MESSAGING_ATTACHMENT_URL_MAX_AGE_SECONDS", 600)
            )
            if verified is None or verified[0] != str(attachment_id):
                raise AttachmentNotFound()
            user_id = verified[1]
        elif request.user and request.user.is_authenticated:
            user_id = request.user.pk
        else:
            raise NotAuthenticated()
        if not get_user_model().objects.filter(pk=user_id, is_active=True).exists():
            raise AttachmentNotFound()
        attachment = (
            MessageAttachment.objects.filter(
                pk=attachment_id,
                message__is_deleted=False,
                message__conversation__participants__user_id=user_id,
                message__conversation__participants__is_active=True,
            )
            .exclude(message__hidden_for__user_id=user_id)
            .first()
        )
        if attachment is None:
            raise AttachmentNotFound()
        try:
            handle = attachment.file.open("rb")
        except (FileNotFoundError, OSError):
            raise AttachmentNotFound()
        response = FileResponse(
            handle,
            content_type=attachment.content_type,
            as_attachment=attachment.kind != MessageAttachment.Kind.IMAGE,
            filename=attachment.original_name,
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        response["Cache-Control"] = "private, max-age=300"
        response["Referrer-Policy"] = "no-referrer"
        return response


# ---------------------------------------------------------------------------
# WebSocket ticket
# ---------------------------------------------------------------------------
class WebSocketTicketView(_MessagingView):
    """
    POST /api/messaging/ws-ticket/ -> {"ticket": "...", "expires_in": 30}
    One-time, 30-second ticket for clients that cannot send the JWT as a WebSocket
    subprotocol: connect to ws://.../ws/messaging/?ticket=<ticket>. The JWT itself never
    appears in a URL (URLs end up in proxy logs).
    """

    throttle_classes = [MessageActionThrottle]

    def post(self, request):
        ticket = secrets.token_urlsafe(32)
        cache.set(WS_TICKET_KEY % ticket, str(request.user.pk), WS_TICKET_TTL_SECONDS)
        return success_response(
            {"ticket": ticket, "expires_in": WS_TICKET_TTL_SECONDS}, "WebSocket ticket issued.",
            status.HTTP_201_CREATED,
        )
