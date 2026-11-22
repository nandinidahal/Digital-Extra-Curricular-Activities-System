"""
Messaging permissions. Conversation membership is NOT a permission class: every query in
selectors.py is already scoped to the requesting user, so a non-member simply gets 404 and
cannot learn whether a conversation id exists.
"""
from rest_framework.permissions import BasePermission

from friends.validators import is_available


class IsAvailableMember(BasePermission):
    """Authenticated, active and e-mail verified (the same rule as Friends)."""

    message = "Your account cannot use messaging right now."
    code = "account_unavailable"

    def has_permission(self, request, view):
        return is_available(request.user)
