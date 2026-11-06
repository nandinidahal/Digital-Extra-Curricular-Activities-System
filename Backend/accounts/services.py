import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, Throttled, ValidationError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from .models import EmailOTP, OTPPurpose

GENERIC_OTP_ERROR = "Invalid or expired code."


class EmailDeliveryError(APIException):
    status_code = 503
    default_detail = "We could not send the email right now. Please try again shortly."
    default_code = "email_delivery_failed"


def hash_value(value: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


def generate_otp() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def _send_otp_email(user, code, purpose):
    minutes = settings.OTP_EXPIRY_SECONDS // 60
    if purpose == OTPPurpose.EMAIL_VERIFICATION:
        subject, intro = "Verify your Digital Extra account", "Use this code to verify your email address"
    else:
        subject, intro = "Reset your Digital Extra password", "Use this code to reset your password"
    body = (
        f"Hi {user.full_name or user.username},\n\n"
        f"{intro}:\n\n    {code}\n\n"
        f"This code expires in {minutes} minutes and can be used once.\n"
        "If you did not request it, you can ignore this email.\n\n"
        "Digital Extra - From Screen Time to Life Time."
    )
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
    except Exception as exc:  # SMTP errors, DNS errors, etc.
        raise EmailDeliveryError() from exc


def issue_otp(user, purpose):
    """Create + email a fresh OTP, invalidating older ones. Enforces resend cooldown."""
    now = timezone.now()
    last = EmailOTP.objects.filter(user=user, purpose=purpose).order_by("-created_at").first()
    if last:
        wait = settings.OTP_RESEND_COOLDOWN_SECONDS - (now - last.created_at).total_seconds()
        if wait > 0:
            wait = int(wait) + 1
            raise Throttled(wait=wait, detail=f"Please wait {wait} seconds before requesting a new code.")

    code = generate_otp()
    with transaction.atomic():
        EmailOTP.objects.filter(user=user, purpose=purpose, is_used=False).update(is_used=True)
        if purpose == OTPPurpose.PASSWORD_RESET:  # kill any earlier reset authorization
            EmailOTP.objects.filter(user=user, purpose=purpose).update(reset_token_hash="")
        EmailOTP.objects.create(
            user=user,
            purpose=purpose,
            code_hash=hash_value(code),
            expires_at=now + timedelta(seconds=settings.OTP_EXPIRY_SECONDS),
        )
        _send_otp_email(user, code, purpose)  # failure rolls the new OTP back


def verify_otp(user, purpose, code):
    """Validate and consume an OTP. Raises ValidationError on any failure."""
    error = None
    with transaction.atomic():
        otp = (
            EmailOTP.objects.select_for_update()
            .filter(user=user, purpose=purpose, is_used=False)
            .order_by("-created_at")
            .first()
        )
        if otp is None:
            error = GENERIC_OTP_ERROR
        elif otp.expires_at <= timezone.now():
            otp.is_used = True
            otp.save(update_fields=["is_used"])
            error = "This code has expired. Please request a new one."
        elif otp.attempts >= settings.OTP_MAX_ATTEMPTS:
            otp.is_used = True
            otp.save(update_fields=["is_used"])
            error = "Too many incorrect attempts. Please request a new code."
        elif not hmac.compare_digest(otp.code_hash, hash_value(code)):
            otp.attempts += 1
            if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
                otp.is_used = True
            otp.save(update_fields=["attempts", "is_used"])
            error = GENERIC_OTP_ERROR
        else:
            otp.is_used = True
            otp.save(update_fields=["is_used"])
    if error:
        raise ValidationError({"otp": [error]})
    return otp


def verify_reset_otp_and_issue_token(user, code) -> str:
    otp = verify_otp(user, OTPPurpose.PASSWORD_RESET, code)
    token = secrets.token_urlsafe(32)
    otp.reset_token_hash = hash_value(token)
    otp.reset_token_expires_at = timezone.now() + timedelta(seconds=settings.RESET_TOKEN_EXPIRY_SECONDS)
    otp.save(update_fields=["reset_token_hash", "reset_token_expires_at"])
    return token


def consume_reset_token(user, token):
    """Return the OTP row if the reset token is valid, consuming it. Else raise."""
    with transaction.atomic():
        otp = (
            EmailOTP.objects.select_for_update()
            .filter(
                user=user,
                purpose=OTPPurpose.PASSWORD_RESET,
                reset_token_hash=hash_value(token),
                reset_token_expires_at__gt=timezone.now(),
            )
            .first()
        )
        if otp is None:
            raise ValidationError({"reset_token": ["Invalid or expired reset authorization."]})
        otp.reset_token_hash = ""
        otp.save(update_fields=["reset_token_hash"])
    return otp


def revoke_all_sessions(user):
    """Blacklist every outstanding refresh token and invalidate live access tokens."""
    for outstanding in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=outstanding)
    user.token_version += 1
    user.save(update_fields=["token_version"])


def tokens_for_user(user) -> dict:
    refresh = RefreshToken.for_user(user)
    refresh["tv"] = user.token_version  # copied to access tokens minted from this refresh
    return {"refresh": str(refresh), "access": str(refresh.access_token)}
