"""
Who may see a profile.

Access levels of the viewer:
    owner   - the profile belongs to the viewer
    admin   - viewer has the `admin` role in Accounts (explicit administrative access)
    member  - any other authenticated user
    visitor - anonymous

Friendship-based visibility is intentionally NOT implemented yet; when the Friends
module exists, add a "friend" level here and let `members_only`/`private` consult it.
"""
from rest_framework.permissions import BasePermission

from accounts.models import User

from .exceptions import AuthenticationRequired, ProfileNotFound, ProfilePrivate
from .models import Profile

OWNER = "owner"
ADMIN = "admin"
MEMBER = "member"
VISITOR = "visitor"


def get_viewer_access(viewer, profile):
    if not (viewer and viewer.is_authenticated):
        return VISITOR
    if viewer.pk == profile.user_id:
        return OWNER
    if viewer.role == User.Role.ADMIN:
        return ADMIN
    return MEMBER


class CanViewProfile(BasePermission):
    """
    Object-level rule for GET /api/profiles/<user_id>/. Raises specific errors so
    the frontend can tell "log in" (401) from "private" (403) from "missing" (404).
    """

    def has_object_permission(self, request, view, profile):
        access = get_viewer_access(request.user, profile)
        if access in (OWNER, ADMIN):
            return True

        account = profile.user
        # Inactive or not-yet-verified accounts are not public people.
        if not account.is_active or not account.is_email_verified:
            raise ProfileNotFound()

        visibility = profile.profile_visibility
        if visibility == Profile.Visibility.PUBLIC:
            return True
        if visibility == Profile.Visibility.MEMBERS_ONLY:
            if access == VISITOR:
                raise AuthenticationRequired()
            return True
        raise ProfilePrivate()  # private
