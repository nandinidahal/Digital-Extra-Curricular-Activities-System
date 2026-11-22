"""
Shared permission helpers.

Role permissions already exist in Accounts and are RE-EXPORTED here, not duplicated:
    IsEmailVerified, IsAdminRole, IsCoordinatorOrAdmin, IsOwnerOrAdmin

Role vocabulary used by the new modules:
    admin      - accounts.User.Role.ADMIN
    moderator  - ADMIN or COORDINATOR: reviews achievements and moderates reports
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import User
from accounts.permissions import (  # noqa: F401  (re-exported)
    IsAdminRole,
    IsCoordinatorOrAdmin,
    IsEmailVerified,
    IsOwnerOrAdmin,
)

MODERATOR_ROLES = (User.Role.ADMIN, User.Role.COORDINATOR)


def is_authenticated(user):
    return bool(user is not None and user.is_authenticated)


def is_admin(user):
    return is_authenticated(user) and user.role == User.Role.ADMIN


def is_moderator(user):
    return is_authenticated(user) and user.role in MODERATOR_ROLES


def is_owner(user, obj, owner_field="user"):
    return is_authenticated(user) and getattr(obj, f"{owner_field}_id", None) == user.pk


class IsModerator(IsCoordinatorOrAdmin):
    """Alias with the DEAS vocabulary: admins and coordinators moderate and review."""

    message = "Only moderators (coordinators or administrators) can do this."


class IsOwner(BasePermission):
    """Object-level: the object's `owner_field` (default "user") is the requesting user."""

    message = "You can only change your own content."

    def has_object_permission(self, request, view, obj):
        return is_owner(request.user, obj, getattr(view, "owner_field", "user"))


class ReadAnyWriteAuthenticated(BasePermission):
    """GET/HEAD/OPTIONS for everybody (object visibility is checked separately); writes need a login."""

    message = "Authentication credentials were not provided."

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or is_authenticated(request.user)
