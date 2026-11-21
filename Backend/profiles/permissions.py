from rest_framework.permissions import BasePermission

from achievements.models import Visibility


class CanViewProfile(BasePermission):
    """Object level (obj is a UserProfile): the owner always; everyone else only if it is Public."""

    message = "This profile is private."

    def has_object_permission(self, request, view, obj):
        if obj.user_id == request.user.id:
            return True
        return obj.user.is_active and obj.profile_visibility == Visibility.PUBLIC
