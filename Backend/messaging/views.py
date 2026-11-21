from django.contrib.auth import get_user_model
from django.db.models import Count, F, OuterRef, Subquery
from django.db.models.functions import Coalesce
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from friends.services import relationship_states
from social.pagination import StandardPagination

from . import services
from .models import Conversation, Message
from .pagination import MessageCursorPagination
from .selectors import conversations_for, unread_message_count
from .serializers import (ConversationSerializer, MessageSerializer, MessageWriteSerializer,
                          StartConversationSerializer)

User = get_user_model()


def _unread_subquery(user):
    return Subquery(
        Message.objects.filter(conversation=OuterRef("pk"), read_at__isnull=True, deleted_at__isnull=True)
        .exclude(sender=user).order_by().values("conversation").annotate(c=Count("pk")).values("c")[:1]
    )


def _conversation_payload(request, convs):
    """Serialize conversations with relationship states loaded in bulk (no per-row queries)."""
    me = request.user
    other_ids = [c.user_high_id if c.user_low_id == me.pk else c.user_low_id for c in convs]
    rel_states = relationship_states(me, other_ids)
    return ConversationSerializer(convs, many=True, context={"request": request, "rel_states": rel_states}).data


def _list_qs(user):
    return (conversations_for(user)
            .select_related("user_low", "user_low__user_profile", "user_high", "user_high__user_profile", "last_message")
            .annotate(unread_count=Coalesce(_unread_subquery(user), 0))
            .order_by(F("last_message_at").desc(nulls_last=True), "-id"))


class ConversationListView(GenericAPIView):
    serializer_class = ConversationSerializer

    def get(self, request):
        paginator = StandardPagination()
        page = paginator.paginate_queryset(_list_qs(request.user), request, view=self)
        return paginator.get_paginated_response(_conversation_payload(request, page))

    def post(self, request):
        """Open (or fetch) the single conversation with a user; optionally send the first message."""
        s = StartConversationSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        conv = services.get_or_create_conversation(request.user, s.validated_data["recipient_id"])
        body = s.validated_data.get("body")
        if body:
            services.send_message(request.user, conv.pk, body)
        conv = _list_qs(request.user).get(pk=conv.pk)
        return Response(_conversation_payload(request, [conv])[0], status=status.HTTP_200_OK)


class ConversationDetailView(APIView):
    def get(self, request, conversation_id):
        services.get_conversation_for(request.user, conversation_id)  # 404 for non-participants
        conv = _list_qs(request.user).get(pk=conversation_id)
        return Response(_conversation_payload(request, [conv])[0])


class MessageListCreateView(GenericAPIView):
    serializer_class = MessageSerializer

    def get_throttles(self):
        if self.request.method == "POST":
            self.throttle_scope = "message_send"
            return [ScopedRateThrottle()]
        return []

    def get(self, request, conversation_id):
        conv = services.get_conversation_for(request.user, conversation_id)
        qs = Message.objects.filter(conversation=conv)
        paginator = MessageCursorPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(MessageSerializer(page, many=True, context={"request": request}).data)

    def post(self, request, conversation_id):
        s = MessageWriteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        msg = services.send_message(request.user, conversation_id, s.validated_data["body"])
        return Response(MessageSerializer(msg, context={"request": request}).data, status=status.HTTP_201_CREATED)


class ConversationReadView(APIView):
    def post(self, request, conversation_id):
        return Response({"marked_read": services.mark_read(request.user, conversation_id)})


class MessageDetailView(APIView):
    def patch(self, request, message_id):
        s = MessageWriteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        msg = services.edit_message(request.user, message_id, s.validated_data["body"])
        return Response(MessageSerializer(msg, context={"request": request}).data)

    def delete(self, request, message_id):
        services.delete_message(request.user, message_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UnreadCountView(APIView):
    def get(self, request):
        return Response({"unread": unread_message_count(request.user)})
