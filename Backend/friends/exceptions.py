"""
Friends-specific API errors. Rendered by the project's existing
`accounts.exceptions.api_exception_handler`, so they share its JSON shape:
{"success": false, "message": ..., "code": ..., "errors": {...}}
"""
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, PermissionDenied


class _WithExtra:
    """The global handler merges `exc.extra` into the error body."""

    extra = None


class UserNotFound(NotFound):
    default_detail = "This user does not exist or is not available."
    default_code = "user_not_found"


class CannotTargetSelf(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "You cannot do this to yourself."
    default_code = "cannot_target_self"


class RequestNotFound(NotFound):
    default_detail = "This friend request does not exist."
    default_code = "request_not_found"


class NotRequestReceiver(PermissionDenied):
    default_detail = "Only the receiver can respond to this friend request."
    default_code = "not_request_receiver"


class NotRequestSender(PermissionDenied):
    default_detail = "Only the sender can cancel this friend request."
    default_code = "not_request_sender"


class RequestNotAllowed(PermissionDenied):
    """Deliberately vague: it must not reveal WHO blocked WHOM."""

    default_detail = "You cannot send a friend request to this user."
    default_code = "request_not_allowed"


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This action conflicts with the current state."
    default_code = "conflict"


class RequestNotPending(_WithExtra, Conflict):
    default_detail = "This friend request is no longer pending."
    default_code = "request_not_pending"

    def __init__(self, current_status=None, detail=None, code=None):
        super().__init__(detail, code)
        self.extra = {"current_status": current_status} if current_status else {}


class AlreadyFriends(Conflict):
    default_detail = "You are already friends with this user."
    default_code = "already_friends"


class RequestAlreadySent(Conflict):
    default_detail = "You already have a pending friend request to this user."
    default_code = "request_already_sent"


class RequestCooldown(_WithExtra, APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "This user declined your earlier request. Please wait before asking again."
    default_code = "request_cooldown"

    def __init__(self, retry_after=None, detail=None, code=None):
        super().__init__(detail, code)
        self.extra = {"retry_after": retry_after} if retry_after else {}


class NotFriends(NotFound):
    default_detail = "You are not friends with this user."
    default_code = "not_friends"


class AlreadyBlocked(Conflict):
    default_detail = "You have already blocked this user."
    default_code = "already_blocked"


class BlockNotFound(NotFound):
    default_detail = "You have not blocked this user."
    default_code = "block_not_found"


class AccountUnavailable(PermissionDenied):
    default_detail = "Your account cannot use friend features right now."
    default_code = "account_unavailable"


class DiscoveryDisabled(NotFound):
    default_detail = "Not found."
    default_code = "not_found"
