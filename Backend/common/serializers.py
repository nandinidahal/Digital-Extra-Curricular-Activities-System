"""Shared representation helpers."""
from django.core.exceptions import ObjectDoesNotExist

from .permissions import is_admin, is_authenticated


def absolute_url(file_field, request=None):
    if not file_field:
        return None
    try:
        url = file_field.url
    except ValueError:
        return None
    if request is not None and url.startswith("/"):
        return request.build_absolute_uri(url)  # S3/CDN storages already return absolute URLs
    return url


def user_card(user, viewer=None, request=None):
    """
    Public person card used by every module: id, username, full name and (when permitted) the
    profile picture. A PRIVATE profile's picture is shown only to its owner and to admins, the
    same rule the Friends module applies. Load users with select_related("profile").
    """
    if user is None:
        return None
    picture = None
    try:
        profile = user.profile
    except ObjectDoesNotExist:
        profile = None
    if profile is not None:
        may_see = (
            profile.profile_visibility != "private"
            or (is_authenticated(viewer) and viewer.pk == user.pk)
            or is_admin(viewer)
        )
        if may_see:
            picture = absolute_url(profile.profile_picture, request)
    return {
        "id": str(user.pk),
        "username": user.username,
        "full_name": user.full_name,
        "profile_picture": picture,
    }
