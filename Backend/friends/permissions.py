"""
Permissions for the Friends API.

* IsAvailableMember   - authenticated, active and e-mail verified account.
* IsRequestReceiver   - object-level: only the receiver may accept/reject.
* IsRequestSender     - object-level: only the sender may cancel.
* ensure_can_view_profile - reuses the Profiles visibility rules (no second copy of them).

Roles are always derived from `request.user` and the database row, never from request data.
"""
from rest_framework.permissions import BasePermission

from profiles.models import Profile
from profiles.permissions import CanViewProfile

from .validators import is_available


class IsAvailableMember(BasePermission):
    message = "Your account cannot use friend features right now."
    code = "account_unavailable"

    def has_permission(self, request, view):
        return is_available(request.user)


class IsRequestReceiver(BasePermission):
    message = "Only the receiver can respond to this friend request."
    code = "not_request_receiver"

    def has_object_permission(self, request, view, obj):
        return obj.receiver_id == request.user.pk


class IsRequestSender(BasePermission):
    message = "Only the sender can cancel this friend request."
    code = "not_request_sender"

    def has_object_permission(self, request, view, obj):
        return obj.sender_id == request.user.pk


def ensure_can_view_profile(request, view, target_user):
    """
    Raise the Profiles module's own errors (profile_private, profile_not_found) when the
    viewer may not see `target_user`'s profile. A user without a profile row counts as public.
    """
    profile = Profile.objects.select_related("user").filter(user=target_user).first()
    if profile is not None:
        CanViewProfile().has_object_permission(request, view, profile)
