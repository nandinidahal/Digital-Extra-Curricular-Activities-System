from rest_framework.permissions import SAFE_METHODS, BasePermission


def can_curate(user):
    """Who may set the featured / important flags.

    Uses the existing role system when present (``accounts.User.is_coordinator`` covers
    coordinators and admins); if a user model has no such property nobody can curate.
    """
    return bool(user and user.is_authenticated and getattr(user, "is_coordinator", False))


class IsAnnouncementOwnerOrReadOnly(BasePermission):
    """Object level. Read: any authenticated student (visibility is enforced by the queryset,
    so other people's drafts are a 404 before this runs). Write/delete: the author only -> 403."""

    message = "You can only modify your own announcements."

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.published_by_id == request.user.id
