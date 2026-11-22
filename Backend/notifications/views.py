"""
REST API of the Notifications module (/api/notifications/). Every endpoint needs a JWT and only
ever touches the requesting user's own notifications: querysets are always filtered by
`recipient=request.user`, so another user's notification id simply answers 404.
"""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from accounts.responses import success_response
from common.pagination import paginate

from . import services
from .serializers import NotificationFilterSerializer, NotificationPreferenceSerializer, NotificationSerializer
from .throttles import NotificationActionThrottle


class _Base(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [NotificationActionThrottle]


class NotificationListView(_Base):
    """GET /api/notifications/?is_read=false&category=social&type=post.liked&page=1"""

    def get(self, request):
        filters = NotificationFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        queryset = services.visible_notifications(request.user).select_related("actor", "actor__profile")
        params = filters.validated_data
        if params.get("is_read") is not None:
            queryset = queryset.filter(is_read=params["is_read"])
        if params.get("category"):
            queryset = queryset.filter(category=params["category"])
        if params.get("type"):
            queryset = queryset.filter(notification_type=params["type"])
        return paginate(request, queryset, NotificationSerializer)


class UnreadCountView(_Base):
    def get(self, request):
        return success_response({"unread_count": services.unread_count(request.user)})


class MarkReadView(_Base):
    def post(self, request, notification_id):
        notification = services.mark_read(request.user, notification_id)
        return success_response(
            {"notification": NotificationSerializer(notification, context={"request": request}).data, "unread_count": services.unread_count(request.user)},
            "Notification marked as read.",
        )


class MarkUnreadView(_Base):
    def post(self, request, notification_id):
        notification = services.mark_unread(request.user, notification_id)
        return success_response(
            {"notification": NotificationSerializer(notification, context={"request": request}).data, "unread_count": services.unread_count(request.user)},
            "Notification marked as unread.",
        )


class MarkAllReadView(_Base):
    def post(self, request):
        updated = services.mark_all_read(request.user)
        return success_response({"updated": updated, "unread_count": 0}, "All notifications marked as read.")


class NotificationDetailView(_Base):
    def get(self, request, notification_id):
        notification = services.get_own_notification(request.user, notification_id)
        return success_response({"notification": NotificationSerializer(notification, context={"request": request}).data})

    def delete(self, request, notification_id):
        services.delete_notification(request.user, notification_id)
        return success_response({"unread_count": services.unread_count(request.user)}, "Notification deleted.")


class ClearNotificationsView(_Base):
    """DELETE /api/notifications/clear/  (?read_only=true keeps unread ones)"""

    def delete(self, request):
        read_only = str(request.query_params.get("read_only", "")).lower() in ("1", "true", "yes")
        deleted = services.clear_notifications(request.user, read_only=read_only)
        return success_response(
            {"deleted": deleted, "unread_count": services.unread_count(request.user)}, "Notifications cleared."
        )


class PreferencesView(_Base):
    def get(self, request):
        return success_response({"preferences": NotificationPreferenceSerializer(services.get_preferences(request.user)).data})

    def patch(self, request):
        serializer = NotificationPreferenceSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        preference = services.update_preferences(request.user, serializer.validated_data)
        return success_response(
            {"preferences": NotificationPreferenceSerializer(preference).data}, "Preferences updated.", status.HTTP_200_OK
        )
