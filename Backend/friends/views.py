from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from social.pagination import StandardPagination
from social.serializers import UserBriefSerializer
from social.visibility import can_view_user_content

from . import services
from .models import Block, FriendRequest, Friendship, RequestStatus
from .selectors import friends_of, mutual_friends
from .serializers import BlockSerializer, FriendRequestSerializer, SendRequestSerializer
from .suggestions import suggest_friends

User = get_user_model()


def _ctx(request):
    return {"request": request}


class FriendListView(GenericAPIView):
    """GET /api/friends/ - the signed-in user's accepted friends (searchable with ?search=)."""
    serializer_class = UserBriefSerializer

    def get(self, request):
        qs = friends_of(request.user).filter(is_active=True).select_related("user_profile").order_by("full_name", "id")
        term = request.query_params.get("search", "").strip()
        if term:
            qs = qs.filter(Q(full_name__icontains=term) | Q(username__icontains=term))
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        resp = paginator.get_paginated_response(UserBriefSerializer(page, many=True, context=_ctx(request)).data)
        resp.data["friends_count"] = friends_of(request.user).filter(is_active=True).count()
        return resp


class FriendDetailView(APIView):
    """DELETE /api/friends/<user_id>/ - unfriend. Chat history is kept."""

    def delete(self, request, user_id):
        services.remove_friend(request.user, user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MutualFriendsView(GenericAPIView):
    serializer_class = UserBriefSerializer

    def get(self, request, username):
        target = User.objects.filter(username__iexact=username).first()
        if target is None or not can_view_user_content(request.user, target):
            raise NotFound("User not found.")
        qs = mutual_friends(request.user, target).filter(is_active=True).select_related("user_profile").order_by("full_name", "id")
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(UserBriefSerializer(page, many=True, context=_ctx(request)).data)


class FriendStatusView(APIView):
    """GET /api/friends/status/<user_id>/ - the relationship-state algorithm's result."""

    def get(self, request, user_id):
        other = User.objects.filter(pk=user_id, is_active=True).first()
        if other is None:
            raise NotFound("User not found.")
        return Response(services.get_relationship(request.user, other))


class SendRequestView(GenericAPIView):
    """POST /api/friends/requests/ {"user_id": 5}"""
    serializer_class = SendRequestSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "friend_requests"

    def post(self, request):
        s = SendRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        fr, auto = services.send_request(request.user, s.validated_data["user_id"])
        data = FriendRequestSerializer(fr, context=_ctx(request)).data
        data["auto_accepted"] = auto
        return Response(data, status=status.HTTP_200_OK if auto else status.HTTP_201_CREATED)


class IncomingRequestsView(GenericAPIView):
    serializer_class = FriendRequestSerializer

    def get(self, request):
        qs = (FriendRequest.objects.filter(receiver=request.user, status=RequestStatus.PENDING)
              .select_related("sender", "sender__user_profile", "receiver", "receiver__user_profile"))
        if request.query_params.get("include_ignored") not in ("1", "true"):
            qs = qs.filter(is_ignored=False)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(FriendRequestSerializer(page, many=True, context=_ctx(request)).data)


class OutgoingRequestsView(GenericAPIView):
    serializer_class = FriendRequestSerializer

    def get(self, request):
        qs = (FriendRequest.objects.filter(sender=request.user, status=RequestStatus.PENDING)
              .select_related("sender", "sender__user_profile", "receiver", "receiver__user_profile"))
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(FriendRequestSerializer(page, many=True, context=_ctx(request)).data)


class RequestActionView(APIView):
    """POST /api/friends/requests/<id>/<accept|reject|ignore|cancel>/"""
    action_name = None

    def post(self, request, request_id):
        fr = services.respond(request.user, request_id, self.action_name)
        fr = FriendRequest.objects.select_related("sender__user_profile", "receiver__user_profile").get(pk=fr.pk)
        return Response(FriendRequestSerializer(fr, context=_ctx(request)).data)


class SuggestionsView(APIView):
    """GET /api/friends/suggestions/?limit=20"""

    def get(self, request):
        try:
            limit = max(1, min(int(request.query_params.get("limit", 20)), 50))
        except ValueError:
            limit = 20
        items = suggest_friends(request.user, limit=limit)
        return Response([
            {"user": UserBriefSerializer(i["user"], context=_ctx(request)).data, "score": i["score"],
             "reasons": i["reasons"]}
            for i in items
        ])


class BlockListView(GenericAPIView):
    serializer_class = BlockSerializer

    def get(self, request):
        qs = Block.objects.filter(blocker=request.user).select_related("blocked", "blocked__user_profile")
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(BlockSerializer(page, many=True, context=_ctx(request)).data)

    def post(self, request):
        s = SendRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        block = services.block_user(request.user, s.validated_data["user_id"])
        block = Block.objects.select_related("blocked__user_profile").get(pk=block.pk)
        return Response(BlockSerializer(block, context=_ctx(request)).data, status=status.HTTP_201_CREATED)


class BlockDetailView(APIView):
    def delete(self, request, user_id):
        services.unblock_user(request.user, user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
