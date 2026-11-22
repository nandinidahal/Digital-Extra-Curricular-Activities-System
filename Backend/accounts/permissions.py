"""
Permission classes that other apps can reuse.

    from accounts.permissions import IsEmailVerified, IsCoordinatorOrAdmin

    class PostViewSet(ModelViewSet):
        permission_classes = [IsEmailVerified]
"""
from rest_framework.permissions import BasePermission

from .models import User


class IsEmailVerified(BasePermission):
    """Authenticated AND email verified (use on features that need a real email)."""

    message = "Please verify your email address to use this feature."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_email_verified)


class IsAdminRole(BasePermission):
    message = "Only administrators can do this."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == User.Role.ADMIN)


class IsCoordinatorOrAdmin(BasePermission):
    message = "Only coordinators or administrators can do this."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.role in (User.Role.COORDINATOR, User.Role.ADMIN)
        )


class IsOwnerOrAdmin(BasePermission):
    """
    Object-level permission. Set `owner_field` on the view (default "user"):

        class MyView(RetrieveUpdateAPIView):
            permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
            owner_field = "author"
    """

    message = "You do not have permission to access this object."

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role == User.Role.ADMIN:
            return True
        owner = getattr(obj, getattr(view, "owner_field", "user"), None)
        return owner is not None and owner == user
