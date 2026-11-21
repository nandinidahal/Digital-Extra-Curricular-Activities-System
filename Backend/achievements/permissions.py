from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Visibility


class CanAccessAchievement(BasePermission):
    """Object level: read = owner or PUBLIC; write/delete = owner only."""

    message = "You can only modify your own achievements."

    def has_object_permission(self, request, view, obj):
        is_owner = obj.user_id == request.user.id
        if request.method in SAFE_METHODS:
            return is_owner or obj.visibility == Visibility.PUBLIC
        return is_owner
