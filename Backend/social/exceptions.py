"""
Social-specific API errors. They are rendered by the project's existing
`accounts.exceptions.api_exception_handler`, so they share its JSON shape:
{"success": false, "message": ..., "code": ..., "errors": {...}}
"""
from rest_framework import status
from rest_framework.exceptions import APIException, NotAuthenticated, NotFound, PermissionDenied


class PostNotFound(NotFound):
    default_detail = "This post does not exist or is not available."
    default_code = "post_not_found"


class CommentNotFound(NotFound):
    default_detail = "This comment does not exist or is not available."
    default_code = "comment_not_found"


class ShareNotFound(NotFound):
    default_detail = "This share does not exist."
    default_code = "share_not_found"


class MediaNotFound(NotFound):
    default_detail = "This attachment does not exist."
    default_code = "media_not_found"


class AuthorNotFound(NotFound):
    default_detail = "This user does not exist."
    default_code = "user_not_found"


class AuthenticationRequired(NotAuthenticated):
    default_detail = "Please log in to view this content."
    default_code = "authentication_required"


class NotOwner(PermissionDenied):
    default_detail = "You can only change your own content."
    default_code = "not_owner"


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This action was already performed."
    default_code = "conflict"


class AlreadyShared(Conflict):
    default_detail = "You have already shared this post."
    default_code = "already_shared"


class AlreadyReported(Conflict):
    default_detail = "You have already reported this content and it is still being reviewed."
    default_code = "already_reported"


class BusinessRuleViolation(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "This action is not allowed."
    default_code = "not_allowed"


class MaxDepthReached(BusinessRuleViolation):
    default_code = "max_depth_reached"


class PostNotShareable(BusinessRuleViolation):
    default_detail = "Private posts cannot be shared."
    default_code = "post_not_shareable"


class CannotReportOwnContent(BusinessRuleViolation):
    default_detail = "You cannot report your own content."
    default_code = "cannot_report_own_content"


class UploadTooLarge(APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "The upload is too large."
    default_code = "file_too_large"
