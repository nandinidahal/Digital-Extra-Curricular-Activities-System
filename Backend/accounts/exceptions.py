"""
Custom API exceptions and the global exception handler.

Every error response has the same shape:

{
    "success": false,
    "message": "Human readable summary",
    "code": "machine_readable_code",
    "errors": {"field_name": ["Problem 1", "Problem 2"]},
    ...optional extras such as "retry_after" or "attempts_remaining"
}
"""
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    NotFound,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.views import exception_handler as drf_exception_handler


class AccountAPIException(APIException):
    """Base class for errors raised by the accounts module."""

    def __init__(self, detail=None, extra=None):
        super().__init__(detail)
        self.extra = extra or {}


class InvalidCredentials(AccountAPIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Invalid email or password."
    default_code = "invalid_credentials"


class EmailNotVerified(AccountAPIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Please verify your email address before logging in."
    default_code = "email_not_verified"


class InvalidOTP(AccountAPIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "The code is incorrect or no longer valid."
    default_code = "otp_invalid"


class ExpiredOTP(AccountAPIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "This code has expired. Please request a new one."
    default_code = "otp_expired"


class OTPAttemptsExceeded(AccountAPIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Too many incorrect attempts. Please request a new code."
    default_code = "otp_max_attempts"


class OTPRateLimited(AccountAPIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "You requested too many codes. Please wait before trying again."
    default_code = "otp_rate_limited"


class InvalidResetToken(AccountAPIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "The password reset link or token is invalid or has expired."
    default_code = "reset_token_invalid"


class InvalidRefreshToken(AccountAPIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "The refresh token is invalid, expired or already used."
    default_code = "token_invalid"


class EmailDeliveryFailed(AccountAPIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "We could not send the email right now. Please try again in a few minutes."
    default_code = "email_delivery_failed"


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------
def _to_plain(detail):
    if isinstance(detail, dict):
        return {key: _to_plain(value) for key, value in detail.items()}
    if isinstance(detail, (list, tuple)):
        return [_to_plain(item) for item in detail]
    return str(detail)


def _normalize_field_errors(detail):
    plain = _to_plain(detail)
    if not isinstance(plain, dict):
        plain = {"non_field_errors": plain if isinstance(plain, list) else [plain]}
    return {
        key: value if isinstance(value, (list, dict)) else [value]
        for key, value in plain.items()
    }


def _message_for(exc):
    detail = exc.detail
    if isinstance(detail, dict):
        return str(detail.get("detail", "Request failed."))
    if isinstance(detail, (list, tuple)):
        return " ".join(str(item) for item in detail)
    return str(detail)


def _code_for(exc):
    codes = exc.get_codes() if hasattr(exc, "get_codes") else None
    if isinstance(codes, str):
        return codes
    if isinstance(codes, dict) and isinstance(codes.get("detail"), str):
        return codes["detail"]
    return getattr(exc, "default_code", "error")


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None  # unexpected errors stay 500s (and are logged by Django)

    # DRF converts these Django exceptions internally; do the same to read .detail
    if isinstance(exc, Http404):
        exc = NotFound(*(exc.args))
    elif isinstance(exc, DjangoPermissionDenied):
        exc = PermissionDenied(*(exc.args))

    body = {"success": False, "message": "", "code": "error", "errors": {}}

    if isinstance(exc, ValidationError):
        body["message"] = "Please correct the highlighted errors."
        body["code"] = "validation_error"
        body["errors"] = _normalize_field_errors(exc.detail)
    elif isinstance(exc, Throttled):
        retry_after = int(exc.wait) if exc.wait else None
        body["message"] = (
            f"Too many requests. Please try again in {retry_after} seconds."
            if retry_after
            else "Too many requests. Please try again later."
        )
        body["code"] = "throttled"
        body["retry_after"] = retry_after
    else:
        body["message"] = _message_for(exc)
        body["code"] = _code_for(exc)

    extra = getattr(exc, "extra", None)
    if extra:
        body.update(extra)

    response.data = body
    return response
