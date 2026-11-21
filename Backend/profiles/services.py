import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import Throttled, ValidationError

from accounts import services as account_services
from accounts.services import EmailDeliveryError, generate_otp, hash_value

from .models import PendingEmailChange
from .validators import ProcessedImage

User = get_user_model()
logger = logging.getLogger(__name__)

GENERIC_CODE_ERROR = "Invalid or expired code."


# ------------------------------------------------------------------ profile picture
def _delete_file_on_commit(storage, name):
    def _delete():
        try:
            storage.delete(name)
        except Exception:
            logger.exception("Could not delete profile picture %s", name)

    transaction.on_commit(_delete)


def set_profile_picture(profile, processed: ProcessedImage):
    """Store a new picture, replacing (and later deleting) the old one."""
    field = profile.profile_picture
    old_name = field.name if field else None
    storage = field.storage
    with transaction.atomic():
        profile.profile_picture.save(f"picture{processed.extension}", processed.content, save=False)
        new_name = profile.profile_picture.name
        try:
            profile.save(update_fields=["profile_picture", "updated_at"])
        except Exception:
            storage.delete(new_name)  # do not leave an orphan file behind
            raise
        if old_name and old_name != new_name:
            _delete_file_on_commit(storage, old_name)
    return profile


def remove_profile_picture(profile):
    """Returns True if a picture was removed."""
    field = profile.profile_picture
    if not field:
        return False
    storage, name = field.storage, field.name
    with transaction.atomic():
        profile.profile_picture = None
        profile.save(update_fields=["profile_picture", "updated_at"])
        _delete_file_on_commit(storage, name)
    return True


# ------------------------------------------------------------------ e-mail change
def _send_email_change_code(user, new_email, code):
    minutes = settings.OTP_EXPIRY_SECONDS // 60
    body = (
        f"Hi {user.full_name or user.username},\n\n"
        f"Use this code to confirm your new email address for Digital Extra:\n\n    {code}\n\n"
        f"This code expires in {minutes} minutes and can be used once.\n"
        "If you did not request this change, you can ignore this email.\n\n"
        "Digital Extra - From Screen Time to Life Time."
    )
    try:
        send_mail("Confirm your new Digital Extra email", body, settings.DEFAULT_FROM_EMAIL, [new_email],
                  fail_silently=False)
    except Exception as exc:
        raise EmailDeliveryError() from exc


def request_email_change(user, new_email, current_password):
    """Validate, store a pending change and mail an OTP to the NEW address."""
    new_email = (new_email or "").strip().lower()
    if not user.check_password(current_password):
        raise ValidationError({"current_password": ["Current password is incorrect."]})
    if new_email == user.email.lower():
        raise ValidationError({"new_email": ["This is already your email address."]})
    if User.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists():
        raise ValidationError({"new_email": ["An account with this email already exists."]})

    now = timezone.now()
    pending = PendingEmailChange.objects.filter(user=user).first()
    if pending:
        wait = settings.OTP_RESEND_COOLDOWN_SECONDS - (now - pending.created_at).total_seconds()
        if wait > 0:
            wait = int(wait) + 1
            raise Throttled(wait=wait, detail=f"Please wait {wait} seconds before requesting a new code.")

    code = generate_otp()
    with transaction.atomic():  # the pending change is rolled back if the e-mail cannot be sent
        PendingEmailChange.objects.update_or_create(
            user=user,
            defaults={
                "new_email": new_email,
                "code_hash": hash_value(code),
                "attempts": 0,
                "created_at": now,
                "expires_at": now + timedelta(seconds=settings.OTP_EXPIRY_SECONDS),
            },
        )
        _send_email_change_code(user, new_email, code)
    return new_email


def confirm_email_change(user, code):
    """Verify the OTP and switch the account's e-mail address."""
    import hmac

    error = None
    old_email = user.email
    with transaction.atomic():
        pending = PendingEmailChange.objects.select_for_update().filter(user=user).first()
        if pending is None:
            error = "There is no pending email change. Request one first."
        elif pending.expires_at <= timezone.now():
            pending.delete()
            error = "This code has expired. Please request a new one."
        elif pending.attempts >= settings.OTP_MAX_ATTEMPTS:
            pending.delete()
            error = "Too many incorrect attempts. Please request a new code."
        elif not hmac.compare_digest(pending.code_hash, hash_value(code)):
            pending.attempts += 1
            pending.save(update_fields=["attempts"])
            error = GENERIC_CODE_ERROR
        elif User.objects.filter(email__iexact=pending.new_email).exclude(pk=user.pk).exists():
            pending.delete()
            error = "An account with this email already exists."
        else:
            user.email = pending.new_email
            try:
                with transaction.atomic():
                    user.save(update_fields=["email"])
            except IntegrityError:
                pending.delete()
                error = "An account with this email already exists."
            else:
                pending.delete()
    if error:
        raise ValidationError({"otp": [error]})

    # Tell the previous address that the change happened (best effort).
    try:
        send_mail(
            "Your Digital Extra email was changed",
            f"The email address on your Digital Extra account was changed to {user.email}.\n"
            "If this was not you, contact support immediately.",
            settings.DEFAULT_FROM_EMAIL, [old_email], fail_silently=True,
        )
    except Exception:
        logger.exception("Could not notify the previous email address")
    return user


# ------------------------------------------------------------------ deactivation
def deactivate_account(user, profile):
    """Disable the account (never deletes data) and end every session."""
    with transaction.atomic():
        user.is_active = False
        user.save(update_fields=["is_active"])
        profile.deactivated_at = timezone.now()
        profile.save(update_fields=["deactivated_at", "updated_at"])
        account_services.revoke_all_sessions(user)


def reactivate_account(user, profile):
    with transaction.atomic():
        user.is_active = True
        user.save(update_fields=["is_active"])
        profile.deactivated_at = None
        profile.save(update_fields=["deactivated_at", "updated_at"])
