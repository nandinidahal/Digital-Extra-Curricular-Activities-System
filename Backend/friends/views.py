"""
Thin HTTP layer: validate input, call a service, shape the JSON envelope.
Responses use the project-wide envelope from accounts.responses:
    {"success": true, "message": "...", "data": {...}}
"""
from django.conf import settings
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from accounts.responses import success_response

from . import services
from .exceptions import CannotTargetSelf, DiscoveryDisabled, UserNotFound
from .pagination import FriendsPagination
from .permissions import (
    IsAvailableMember,
    IsRequestReceiver,
    IsRequestSender,
    ensure_can_view_profile,
)
from .serializers import (
    BlockCreateSerializer,
    BlockedUserSerializer,
    DiscoverUserSerializer,
    FriendRequestCreateSerializer,
    FriendRequestSerializer,
    FriendSerializer,
    FriendshipSerializer,
    MutualFriendSerializer,
)
from .throttles import FriendActionThrottle, FriendRequestSendThrottle


class _FriendsView(APIView):
    permission_classes = [IsAuthenticated, IsAvailableMember]
    parser_classes = [JSONParser]

    def paginated(self, request, queryset, serializer_class, **context):
        paginator = FriendsPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        data = serializer_class(page, many=True, context={"request": request, **context}).data
        return paginator.get_paginated_response(data)


# ---------------------------------------------------------------------------
# Friend requests
# ---------------------------------------------------------------------------
class SendFriendRequestView(_FriendsView):
    """POST /api/friends/requests/  {"receiver_id": "<uuid>"}"""

    throttle_classes = [FriendRequestSendThrottle]

    def post(self, request):
        serializer = FriendRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = services.send_friend_request(request.user, serializer.validated_data["receiver_id"])
        context = {"request": request}
        data = {
            "request": FriendRequestSerializer(result.friend_request, context=context).data,
            "auto_accepted": result.auto_accepted,
            "friendship": (
                FriendshipSerializer(result.friendship, context=context).data
                if result.friendship
                else None
            ),
        }
        if result.auto_accepted:
            return success_response(
                data, "You both sent each other a request, so you are now friends.", status.HTTP_200_OK
            )
        return success_response(data, "Friend request sent successfully.", status.HTTP_201_CREATED)


class ReceivedRequestsView(_FriendsView):
    """GET /api/friends/requests/received/ - pending requests sent TO me."""

    def get(self, request):
        return self.paginated(
            request, services.received_requests(request.user), FriendRequestSerializer,
            include_user="sender",
        )


class SentRequestsView(_FriendsView):
    """GET /api/friends/requests/sent/ - pending requests sent BY me."""

    def get(self, request):
        return self.paginated(
            request, services.sent_requests(request.user), FriendRequestSerializer,
            include_user="receiver",
        )


class _RequestActionView(_FriendsView):
    """
    The role check happens twice on purpose: here as an object-level permission (clear 403 with
    a specific code) and again inside the service under the row lock (the authoritative check).
    """

    throttle_classes = [FriendActionThrottle]

    def load(self, request, request_id):
        friend_request = services.get_request_for_participant(request.user, request_id)  # 404 for strangers
        self.check_object_permissions(request, friend_request)
        return friend_request


class AcceptFriendRequestView(_RequestActionView):
    permission_classes = [IsAuthenticated, IsAvailableMember, IsRequestReceiver]

    def post(self, request, request_id):
        self.load(request, request_id)
        friend_request, friendship = services.accept_friend_request(request.user, request_id)
        context = {"request": request}
        return success_response(
            {
                "request": FriendRequestSerializer(friend_request, context=context).data,
                "friendship": FriendshipSerializer(friendship, context=context).data,
            },
            "Friend request accepted.",
        )


class RejectFriendRequestView(_RequestActionView):
    permission_classes = [IsAuthenticated, IsAvailableMember, IsRequestReceiver]

    def post(self, request, request_id):
        self.load(request, request_id)
        friend_request = services.reject_friend_request(request.user, request_id)
        return success_response(
            {"request": FriendRequestSerializer(friend_request, context={"request": request}).data},
            "Friend request rejected.",
        )


class CancelFriendRequestView(_RequestActionView):
    permission_classes = [IsAuthenticated, IsAvailableMember, IsRequestSender]

    def post(self, request, request_id):
        self.load(request, request_id)
        friend_request = services.cancel_friend_request(request.user, request_id)
        return success_response(
            {"request": FriendRequestSerializer(friend_request, context={"request": request}).data},
            "Friend request cancelled.",
        )


# ---------------------------------------------------------------------------
# Friendships
# ---------------------------------------------------------------------------
class FriendListView(_FriendsView):
    """GET /api/friends/ - my friends, newest friendship first."""

    def get(self, request):
        return self.paginated(request, services.friendships_of(request.user), FriendSerializer)


class FriendDetailView(_FriendsView):
    """DELETE /api/friends/<user_id>/ - remove a friend (either side may do it)."""

    def delete(self, request, user_id):
        services.remove_friend(request.user, user_id)
        return success_response({"user_id": str(user_id)}, "Friend removed.")


class FriendCountView(_FriendsView):
    """GET /api/friends/count/"""

    def get(self, request):
        return success_response({"friend_count": services.friend_count(request.user)})


class FriendStatusView(_FriendsView):
    """GET /api/friends/status/<user_id>/"""

    def get(self, request, user_id):
        if user_id != request.user.pk:
            services.get_available_user(user_id)  # 404 for unknown / deactivated accounts
        relationship = services.get_relationship(request.user, user_id)
        relationship["user_id"] = str(relationship["user_id"])
        if relationship["request_id"]:
            relationship["request_id"] = str(relationship["request_id"])
        return success_response(relationship)


class MutualFriendsView(_FriendsView):
    """
    GET /api/friends/mutual/<user_id>/
    Hidden (404) when either person has blocked the other; refused (403) when the target's
    profile is private, because mutual friends would reveal the target's connections.
    """

    def get(self, request, user_id):
        if user_id == request.user.pk:
            raise CannotTargetSelf("Mutual friends are only defined between two different people.")
        target = services.get_available_user(user_id)
        if services.is_blocked_between(request.user.pk, target.pk):
            raise UserNotFound()
        ensure_can_view_profile(request, self, target)
        return self.paginated(
            request, services.mutual_friends(request.user, target), MutualFriendSerializer
        )


# ---------------------------------------------------------------------------
# Blocking
# ---------------------------------------------------------------------------
class BlockedListCreateView(_FriendsView):
    """
    GET  /api/friends/blocked/            - MY block list (nobody else's)
    POST /api/friends/blocked/ {"user_id"} - block a user
    """

    throttle_classes = [FriendActionThrottle]

    def get(self, request):
        return self.paginated(request, services.blocked_users(request.user), BlockedUserSerializer)

    def post(self, request):
        serializer = BlockCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        block = services.block_user(request.user, serializer.validated_data["user_id"])
        return success_response(
            {"user_id": str(block.blocked_id), "blocked_at": block.created_at},
            "User blocked.",
            status.HTTP_201_CREATED,
        )


class BlockedDetailView(_FriendsView):
    """DELETE /api/friends/blocked/<user_id>/ - unblock (only blocks I created can be removed)."""

    def delete(self, request, user_id):
        services.unblock_user(request.user, user_id)
        return success_response({"user_id": str(user_id)}, "User unblocked.")


class BlockStatusView(_FriendsView):
    """
    GET /api/friends/blocked/status/<user_id>/
    Only answers "did I block them?". Whether THEY blocked ME is never revealed here.
    """

    def get(self, request, user_id):
        return success_response(
            {"user_id": str(user_id), "blocked_by_me": services.has_blocked(request.user.pk, user_id)}
        )


# ---------------------------------------------------------------------------
# Discovery (TEMPORARY)
# ---------------------------------------------------------------------------
class DiscoverUsersView(_FriendsView):
    """
    GET /api/friends/discover/

    TEMPORARY stand-in until the shared Search/Discovery service exists: a plain paginated list
    of people with each person's friendship status, so the frontend can test "Add friend" flows.
    It has NO search logic on purpose. When Search ships, build on `services.discoverable_users`
    and `services.get_relationship_statuses`, then remove this view (or set
    FRIENDS_ENABLE_TEMP_DISCOVERY=False).
    """

    def get(self, request):
        if not getattr(settings, "FRIENDS_ENABLE_TEMP_DISCOVERY", True):
            raise DiscoveryDisabled()
        queryset = services.discoverable_users(request.user).select_related("profile").order_by(
            "username", "id"
        )
        paginator = FriendsPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        statuses = services.get_relationship_statuses(request.user, [u.pk for u in page])
        data = DiscoverUserSerializer(
            page, many=True, context={"request": request, "statuses": statuses}
        ).data
        return paginator.get_paginated_response(data)
