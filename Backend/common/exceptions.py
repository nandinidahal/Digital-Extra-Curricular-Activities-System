"""
Shared API errors. Rendered by the project-wide `accounts.exceptions.api_exception_handler`,
so every module answers with the same JSON shape:

    {"success": false, "message": "...", "code": "...", "errors": {...}}
"""
from rest_framework import status
from rest_framework.exceptions import APIException, NotAuthenticated, NotFound, PermissionDenied


class ResourceNotFound(NotFound):
    default_detail = "This resource does not exist or is not available."
    default_code = "not_found"


class AuthenticationRequired(NotAuthenticated):
    default_detail = "Please log in to view this content."
    default_code = "authentication_required"


class NotOwner(PermissionDenied):
    default_detail = "You can only change your own content."
    default_code = "not_owner"


class ModeratorRequired(PermissionDenied):
    default_detail = "Only moderators can do this."
    default_code = "moderator_required"


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This action conflicts with the current state."
    default_code = "conflict"


class BusinessRuleViolation(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "This action is not allowed."
    default_code = "not_allowed"


class UploadTooLarge(APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "The upload is too large."
    default_code = "file_too_large"


def check_content_length(request, max_bytes):
    """Refuse oversized bodies from the Content-Length header, before they are parsed."""
    try:
        length = int(request.META.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        length = 0
    if length > max_bytes:
        raise UploadTooLarge()
