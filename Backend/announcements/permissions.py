from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsCoordinatorOrAdmin(BasePermission):
    message = "Only coordinators and administrators can do this."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_coordinator)


class IsOwnerOrAdmin(BasePermission):
    """Object level: owners edit their own announcements, admins edit all."""
    message = "You can only modify announcements you created."

    def has_object_permission(self, request, view, obj):
        u = request.user
        return bool(u.is_authenticated and (u.is_platform_admin or obj.published_by_id == u.id))


class IsAdminOrReadOnly(BasePermission):
    message = "Only administrators can manage categories."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        u = request.user
        return bool(u and u.is_authenticated and u.is_platform_admin)
