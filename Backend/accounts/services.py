"""
Business logic for the accounts module.

Views and serializers stay thin; everything that touches OTPs, tokens and
emails lives here so it is easy to test and reuse.

Security notes
--------------
* OTPs are stored only as an HMAC-SHA256 (keyed with SECRET_KEY) of
  "<user id>:<purpose>:<code>". The plain code exists only in memory and in the email.
* Reset tokens are stored only as a SHA-256 hash.
* Nothing in this file ever logs an OTP, a password or a token.
"""
import hashlib
import hmac
import logging
import math
import secrets
import string
from datetime import timedelta
from functools import lru_cache

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import update_last_login
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from .exceptions import (
    EmailDeliveryFailed,
    EmailNotVerified,
    ExpiredOTP,
    InvalidCredentials,
    InvalidOTP,
    InvalidResetToken,
    OTPAttemptsExceeded,
    OTPRateLimited,
)
from . import signals
from .managers import UserManager
from .models import OneTimePassword, PasswordResetToken, User

logger = logging.getLogger("accounts")

Purpose = OneTimePassword.Purpose

EMAIL_TEMPLATES = {
    Purpose.EMAIL_VERIFICATION: ("emails/verify_email", "Verify your email address"),
    Purpose.PASSWORD_RESET: ("emails/password_reset", "Your password reset code"),
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def normalize_email(value):
    return UserManager.normalize_email(value)


def get_user_by_email(email):
    return User.objects.filter(email=normalize_email(email)).first()


def generate_otp():
    """Cryptographically secure numeric code, e.g. '048213'."""
    return "".join(secrets.choice(string.digits) for _ in range(settings.OTP_LENGTH))


def hash_otp(user_id, purpose, code):
    message = f"{user_id}:{purpose}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def hash_token(raw_token):
    return hashlib.sha256(raw_token.encode()).hexdigest()


@lru_cache(maxsize=1)
def _dummy_hash():
    return make_password("not-a-real-password")


# ---------------------------------------------------------------------------
# Email delivery
# ---------------------------------------------------------------------------
def send_otp_email(user, code, purpose):
    """Send the OTP by SMTP. Raises EmailDeliveryFailed if it cannot be sent."""
    template_base, subject = EMAIL_TEMPLATES[purpose]
    context = {
        "full_name": user.full_name or user.username,
        "otp": code,
        "valid_minutes": settings.OTP_VALID_MINUTES,
        "app_name": "DEAS",
    }
    text_body = render_to_string(f"{template_base}.txt", context)
    html_body = render_to_string(f"{template_base}.html", context)

    message = EmailMultiAlternatives(
        subject=f"{subject} - {context['app_name']}",
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    message.attach_alternative(html_body, "text/html")
    try:
        sent = message.send(fail_silently=False)
    except Exception as exc:  # SMTP errors, DNS errors, timeouts, ...
        # Log only the error type: never the code, never the message body.
        logger.error(
            "Could not send %s email to user %s (%s).", purpose, user.pk, type(exc).__name__
        )
        raise EmailDeliveryFailed() from exc
    if not sent:
        logger.error("Email backend reported 0 messages sent for user %s.", user.pk)
        raise EmailDeliveryFailed()


# ---------------------------------------------------------------------------
# OTP issuing and verification
# ---------------------------------------------------------------------------
def _check_issue_limits(user, purpose):
    """Cooldown between codes, plus a maximum number of codes per hour."""
    now = timezone.now()
    queryset = OneTimePassword.objects.filter(user=user, purpose=purpose)

    last = queryset.order_by("-created_at").first()
    cooldown = settings.OTP_RESEND_COOLDOWN_SECONDS
    if last is not None:
        elapsed = (now - last.created_at).total_seconds()
        if elapsed < cooldown:
            raise OTPRateLimited(extra={"retry_after": math.ceil(cooldown - elapsed)})

    window_start = now - timedelta(hours=1)
    recent = queryset.filter(created_at__gte=window_start)
    if recent.count() >= settings.OTP_MAX_REQUESTS_PER_HOUR:
        oldest = recent.order_by("created_at").first()
        wait = (oldest.created_at + timedelta(hours=1) - now).total_seconds()
        raise OTPRateLimited(extra={"retry_after": max(1, math.ceil(wait))})


def create_and_send_otp(user, purpose, enforce_limits=True):
    """
    Invalidate older codes, create a new one and email it.

    Everything runs in one transaction: if the email cannot be sent, the new
    code is rolled back and the previous (still valid) code stays usable.
    """
    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        if enforce_limits:
            _check_issue_limits(locked_user, purpose)

        OneTimePassword.objects.filter(
            user=locked_user, purpose=purpose, is_used=False
        ).update(is_used=True)

        code = generate_otp()
        OneTimePassword.objects.create(
            user=locked_user,
            purpose=purpose,
            email=locked_user.email,
            otp_hash=hash_otp(locked_user.pk, purpose, code),
            expires_at=timezone.now() + timedelta(minutes=settings.OTP_VALID_MINUTES),
            max_attempts=settings.OTP_MAX_ATTEMPTS,
        )
        send_otp_email(locked_user, code, purpose)


def verify_otp(user, purpose, code, on_success=None):
    """
    Check `code` against the user's active OTP for `purpose`.

    On success the OTP is consumed (single use) and `on_success(otp)` runs in
    the same transaction. On failure an exception is raised AFTER the
    transaction has committed, so the failed-attempt counter is really saved.
    """
    failure = None
    with transaction.atomic():
        otp = (
            OneTimePassword.objects.select_for_update()
            .filter(user=user, purpose=purpose, is_used=False)
            .order_by("-created_at")
            .first()
        )
        if otp is None or otp.email != user.email:
            failure = InvalidOTP()
        elif otp.is_expired:
            failure = ExpiredOTP()
        elif otp.attempts_exhausted:
            failure = OTPAttemptsExceeded()
        elif hmac.compare_digest(otp.otp_hash, hash_otp(user.pk, purpose, code)):
            otp.is_used = True
            otp.save(update_fields=["is_used"])
            if on_success is not None:
                on_success(otp)
            return otp
        else:
            otp.attempts += 1
            otp.save(update_fields=["attempts"])
            remaining = otp.max_attempts - otp.attempts
            if remaining <= 0:
                failure = OTPAttemptsExceeded()
            else:
                failure = InvalidOTP(extra={"attempts_remaining": remaining})
    raise failure


def invalidate_otps(user, purpose):
    OneTimePassword.objects.filter(user=user, purpose=purpose, is_used=False).update(is_used=True)


# ---------------------------------------------------------------------------
# Registration / email verification
# ---------------------------------------------------------------------------
def register_user(*, username, email, password, full_name, phone_number, country, date_of_birth):
    """Create an unverified account and email the verification OTP (all or nothing)."""
    with transaction.atomic():
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            full_name=full_name,
            phone_number=phone_number,
            country=country,
            date_of_birth=date_of_birth,
        )
        # If the email cannot be sent the whole registration is rolled back.
        create_and_send_otp(user, Purpose.EMAIL_VERIFICATION, enforce_limits=False)
    return user


def verify_email_address(email, code):
    user = get_user_by_email(email)
    if user is None:
        raise InvalidOTP()

    def mark_verified(_otp):
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified", "updated_at"])
        signals.emit_on_commit(signals.email_verified, user=user)

    verify_otp(user, Purpose.EMAIL_VERIFICATION, code, on_success=mark_verified)
    return user


def request_verification_otp(email):
    """
    Resend flow. Returns silently when nothing was sent (unknown email, already
    verified, rate limited, SMTP failure) so the API reveals nothing.
    """
    user = get_user_by_email(email)
    if user is None or not user.is_active or user.is_email_verified:
        return
    try:
        create_and_send_otp(user, Purpose.EMAIL_VERIFICATION)
    except (OTPRateLimited, EmailDeliveryFailed):
        pass  # already logged where relevant; response stays generic


# ---------------------------------------------------------------------------
# Login / tokens
# ---------------------------------------------------------------------------
def authenticate_user(email, password):
    user = get_user_by_email(email)
    if user is None:
        check_password(password, _dummy_hash())  # keep response time similar
        raise InvalidCredentials()
    if not user.check_password(password) or not user.is_active:
        raise InvalidCredentials()
    # Only reveal "not verified" once the password is proven correct.
    if not user.is_email_verified:
        raise EmailNotVerified()
    return user


def issue_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def login_user(email, password):
    user = authenticate_user(email, password)
    update_last_login(None, user)
    return user, issue_tokens(user)


def revoke_all_refresh_tokens(user):
    """Blacklist every outstanding refresh token of the user (logs out all devices)."""
    outstanding = OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True)
    BlacklistedToken.objects.bulk_create(
        [BlacklistedToken(token=token) for token in outstanding], ignore_conflicts=True
    )


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------
def request_password_reset_otp(email):
    """Always silent about whether the account exists."""
    user = get_user_by_email(email)
    if user is None or not user.is_active:
        return
    try:
        create_and_send_otp(user, Purpose.PASSWORD_RESET)
    except (OTPRateLimited, EmailDeliveryFailed):
        pass


def verify_password_reset_otp(email, code):
    """Verify the reset OTP and return a one-time reset token (raw, shown once)."""
    user = get_user_by_email(email)
    if user is None or not user.is_active:
        raise InvalidOTP()

    result = {}

    def issue_token(_otp):
        PasswordResetToken.objects.filter(user=user, is_used=False).update(is_used=True)
        raw_token = secrets.token_urlsafe(32)
        PasswordResetToken.objects.create(
            user=user,
            token_hash=hash_token(raw_token),
            expires_at=timezone.now() + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_MINUTES),
        )
        result["token"] = raw_token

    verify_otp(user, Purpose.PASSWORD_RESET, code, on_success=issue_token)
    return result["token"]


def get_valid_reset_token(raw_token):
    token = (
        PasswordResetToken.objects.select_related("user")
        .filter(token_hash=hash_token(raw_token or ""))
        .first()
    )
    if token is None or token.is_used or token.is_expired or not token.user.is_active:
        raise InvalidResetToken()
    return token


def complete_password_reset(raw_token, new_password):
    """Set the new password, burn the token and OTPs, and sign out every device."""
    with transaction.atomic():
        # Re-check inside the transaction to be safe against double submits.
        token = PasswordResetToken.objects.select_for_update().filter(
            token_hash=hash_token(raw_token or "")
        ).first()
        if token is None or token.is_used or token.is_expired:
            raise InvalidResetToken()
        user = token.user
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
        token.is_used = True
        token.save(update_fields=["is_used"])
        PasswordResetToken.objects.filter(user=user, is_used=False).update(is_used=True)
        invalidate_otps(user, Purpose.PASSWORD_RESET)
        revoke_all_refresh_tokens(user)
        signals.emit_on_commit(signals.password_changed, user=user, method="reset")
    return user


# ---------------------------------------------------------------------------
# Change password / account update
# ---------------------------------------------------------------------------
def change_password(user, new_password):
    """Save the new password, sign out other devices and return fresh tokens for this one."""
    with transaction.atomic():
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
        revoke_all_refresh_tokens(user)
        signals.emit_on_commit(signals.password_changed, user=user, method="change")
    return issue_tokens(user)


def update_account(user, validated_data):
    """
    Apply basic account edits. A changed email becomes unverified and a new OTP
    is sent to it; if that email cannot be sent, nothing is changed.
    """
    new_email = validated_data.get("email")
    email_changed = new_email is not None and new_email != user.email

    with transaction.atomic():
        for field in ("full_name", "username", "phone_number", "country", "date_of_birth"):
            if field in validated_data:
                setattr(user, field, validated_data[field])
        if email_changed:
            user.email = new_email
            user.is_email_verified = False
        user.save()
        if email_changed:
            create_and_send_otp(user, Purpose.EMAIL_VERIFICATION)
    return user, email_changed
