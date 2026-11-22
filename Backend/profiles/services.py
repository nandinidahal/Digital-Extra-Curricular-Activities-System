"""
Business logic for the Profiles module. Views and serializers stay thin.
"""
import logging
import uuid
from io import BytesIO

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from PIL import Image, ImageOps
from rest_framework import serializers

from .exceptions import UploadTooLarge
from .models import Profile
from .validators import ALLOWED_IMAGE_FORMATS, validate_image_upload

logger = logging.getLogger("profiles")

# Which fields count towards "profile completion" (documented in the README).
COMPLETION_FIELDS = (
    "profile_picture",
    "bio",
    "headline",
    "institution",
    "education_level",
    "field_of_study",
    "interests",
    "skills",
    "location",
)

IMAGE_SPECS = {
    "profile_picture": {
        "label": "profile picture",
        "max_bytes_setting": "PROFILE_PICTURE_MAX_BYTES",
        "default_max_bytes": 2 * 1024 * 1024,
        "bounding_box": (1024, 1024),
    },
    "cover_photo": {
        "label": "cover photo",
        "max_bytes_setting": "PROFILE_COVER_MAX_BYTES",
        "default_max_bytes": 5 * 1024 * 1024,
        "bounding_box": (2400, 1200),
    },
}
# Extra room for multipart boundaries/headers when checking Content-Length early.
MULTIPART_OVERHEAD_BYTES = 256 * 1024


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------
def create_profile_for_user(user):
    """Idempotent: returns the existing profile or creates exactly one."""
    profile, _created = Profile.objects.get_or_create(user=user)
    return profile


def get_or_create_profile(user):
    """
    Profile of `user` with the account loaded. Users created before the module
    existed (or by a path that bypassed the signal) get their profile lazily.
    """
    profile = Profile.objects.select_related("user").filter(user=user).first()
    if profile is None:
        create_profile_for_user(user)
        profile = Profile.objects.select_related("user").get(user=user)
    return profile


def create_missing_profiles(batch_size=500, dry_run=False):
    """Create a profile for every user that has none. Returns how many were (or would be) created."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    missing_ids = list(User.objects.filter(profile__isnull=True).values_list("pk", flat=True))
    total = 0
    batch = []
    for pk in missing_ids:
        batch.append(Profile(user_id=pk))
        if len(batch) >= batch_size:
            total += _flush(batch, dry_run)
            batch = []
    total += _flush(batch, dry_run)
    return total


def _flush(batch, dry_run):
    if not batch:
        return 0
    if not dry_run:
        Profile.objects.bulk_create(batch, ignore_conflicts=True)
    return len(batch)


# ---------------------------------------------------------------------------
# Completion
# ---------------------------------------------------------------------------
def _is_filled(profile, field_name):
    value = getattr(profile, field_name)
    if field_name == "profile_picture":
        return bool(value)
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)  # lists


def calculate_completion(profile):
    """Computed on every call, never stored, so it can never be out of date."""
    completed = [name for name in COMPLETION_FIELDS if _is_filled(profile, name)]
    missing = [name for name in COMPLETION_FIELDS if name not in completed]
    percentage = round(len(completed) * 100 / len(COMPLETION_FIELDS))
    return {
        "percentage": percentage,
        "completed_fields": completed,
        "missing_fields": missing,
    }


# ---------------------------------------------------------------------------
# Updates
# ---------------------------------------------------------------------------
def update_profile(profile, validated_data):
    """Apply already-validated data (partial update)."""
    for name, value in validated_data.items():
        setattr(profile, name, value)
    profile.save(update_fields=[*validated_data.keys(), "updated_at"])
    return profile


def update_privacy(profile, validated_data):
    return update_profile(profile, validated_data)


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------
def max_image_bytes(field_name):
    spec = IMAGE_SPECS[field_name]
    return getattr(settings, spec["max_bytes_setting"], spec["default_max_bytes"])


def check_content_length(request, field_name):
    """Reject absurdly large bodies before they are read from the socket."""
    try:
        length = int(request.META.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        length = 0
    if length > max_image_bytes(field_name) + MULTIPART_OVERHEAD_BYTES:
        raise UploadTooLarge(
            f"The uploaded file is too large for a {IMAGE_SPECS[field_name]['label']}."
        )


def validate_upload(upload, field_name):
    """Returns the detected image format, or raises a DRF validation error on `image`."""
    try:
        return validate_image_upload(upload, max_bytes=max_image_bytes(field_name))
    except DjangoValidationError as exc:
        raise serializers.ValidationError({"image": list(exc.messages)})


def process_image(upload, image_format, field_name):
    """
    Re-encode the image. This (a) strips EXIF/GPS and any hidden payload,
    (b) applies the camera rotation, (c) caps the dimensions and
    (d) guarantees the stored bytes are exactly what we say they are.
    """
    spec = IMAGE_SPECS[field_name]
    try:
        upload.seek(0)
        with Image.open(upload) as source:
            image = ImageOps.exif_transpose(source)
            image.load()  # decodes fully; truncated/corrupt files fail here
        for metadata_key in ("exif", "xmp", "comment"):
            image.info.pop(metadata_key, None)
        if image_format == "JPEG":
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
        elif image.mode not in ("RGB", "RGBA", "L", "LA"):
            image = image.convert("RGBA")
        image.thumbnail(spec["bounding_box"], Image.Resampling.LANCZOS)

        buffer = BytesIO()
        if image_format == "JPEG":
            image.save(buffer, "JPEG", quality=85, optimize=True)
        elif image_format == "PNG":
            image.save(buffer, "PNG", optimize=True)
        else:
            image.save(buffer, "WEBP", quality=85)
    except (OSError, ValueError, SyntaxError, EOFError, Image.DecompressionBombError):
        raise serializers.ValidationError({"image": ["The uploaded file is not a valid image."]})

    extension = ALLOWED_IMAGE_FORMATS[image_format]
    return ContentFile(buffer.getvalue(), name=f"{uuid.uuid4().hex}.{extension}")


def _delete_stored_file(storage, name):
    try:
        storage.delete(name)
    except Exception:  # never fail a request because cleanup failed
        logger.warning("Could not delete old profile image %s", name, exc_info=True)


def set_profile_image(profile, field_name, upload, image_format):
    """
    Store a new image and remove the previous one (after the database commit,
    so a failed save never leaves a profile pointing at a deleted file).
    """
    content = process_image(upload, image_format, field_name)
    storage = Profile._meta.get_field(field_name).storage
    new_name = None
    try:
        with transaction.atomic():
            locked = (
                Profile.objects.select_for_update(of=("self",))
                .select_related("user")
                .get(pk=profile.pk)
            )
            field_file = getattr(locked, field_name)
            old_name = field_file.name if field_file else None
            field_file.save(content.name, content, save=False)
            new_name = field_file.name
            locked.save(update_fields=[field_name, "updated_at"])
            if old_name:
                transaction.on_commit(lambda: _delete_stored_file(storage, old_name))
    except Exception:
        if new_name:
            _delete_stored_file(storage, new_name)
        raise
    return locked


def remove_profile_image(profile, field_name):
    storage = Profile._meta.get_field(field_name).storage
    with transaction.atomic():
        locked = (
            Profile.objects.select_for_update(of=("self",))
            .select_related("user")
            .get(pk=profile.pk)
        )
        field_file = getattr(locked, field_name)
        old_name = field_file.name if field_file else None
        if old_name:
            setattr(locked, field_name, "")
            locked.save(update_fields=[field_name, "updated_at"])
            transaction.on_commit(lambda: _delete_stored_file(storage, old_name))
    return locked
