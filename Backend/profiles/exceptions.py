"""
Profile-specific API errors. They are rendered by the project's existing
`accounts.exceptions.api_exception_handler`, so they share the same JSON shape:
{"success": false, "message": ..., "code": ..., "errors": {...}}
"""
from rest_framework import status
from rest_framework.exceptions import APIException, NotAuthenticated, NotFound, PermissionDenied


class ProfileNotFound(NotFound):
    default_detail = "This profile does not exist."
    default_code = "profile_not_found"


class ProfilePrivate(PermissionDenied):
    default_detail = "This profile is private."
    default_code = "profile_private"


class AuthenticationRequired(NotAuthenticated):
    default_detail = "Please log in to view this profile."
    default_code = "authentication_required"


class UploadTooLarge(APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "The uploaded file is too large."
    default_code = "file_too_large"
