import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.text import get_valid_filename
from django.core.exceptions import SuspiciousFileOperation
from PIL import Image

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
IMAGE_FORMAT_BY_EXTENSION = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
CONTENT_TYPE_BY_FORMAT = {
    "PDF": "application/pdf",
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}
# Content types a client may legitimately declare for the allowed formats.
ALLOWED_DECLARED_CONTENT_TYPES = {
    "application/pdf", "application/x-pdf",
    "image/jpeg", "image/jpg", "image/pjpeg", "image/png", "image/webp",
}
DEFAULT_MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB
MB = 1024 * 1024


def _human_size(num_bytes):
    if num_bytes >= MB:
        return f"{num_bytes / MB:.1f} MB".replace(".0 MB", " MB")
    return f"{max(1, round(num_bytes / 1024))} KB"


def max_upload_size():
    return int(getattr(settings, "ACHIEVEMENT_MAX_UPLOAD_SIZE", DEFAULT_MAX_UPLOAD_SIZE))


def inspect_upload(file):
    """Validate an uploaded achievement document and return (extension, content_type).

    Checks the extension, size, the client-declared content type, and the real file
    contents (PDF header / Pillow image decoding), so a renamed file is rejected.
    """
    name = getattr(file, "name", "") or ""
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            "Unsupported file type. Allowed types: PDF, JPG, JPEG, PNG and WEBP.", code="invalid_extension"
        )

    size = getattr(file, "size", None)
    if not size:
        raise ValidationError("The submitted file is empty.", code="empty_file")
    limit = max_upload_size()
    if size > limit:
        raise ValidationError(
            f"File is too large ({_human_size(size)}). The maximum allowed size is {_human_size(limit)}.",
            code="file_too_large",
        )

    declared = (getattr(file, "content_type", "") or "").split(";")[0].strip().lower()
    if declared and declared not in ALLOWED_DECLARED_CONTENT_TYPES:
        raise ValidationError(f"Unsupported content type '{declared}'.", code="invalid_content_type")

    try:
        file.seek(0)
        if ext == ".pdf":
            if b"%PDF-" not in file.read(1024):
                raise ValidationError("The file is not a valid PDF document.", code="invalid_content")
            actual = "PDF"
        else:
            try:
                img = Image.open(file)
                actual = img.format
                img.verify()  # detects truncated / corrupt images
            except Exception:
                raise ValidationError("The file is not a valid image.", code="invalid_content")
            if actual != IMAGE_FORMAT_BY_EXTENSION[ext]:
                raise ValidationError(
                    "The file contents do not match its extension.", code="extension_mismatch"
                )
    finally:
        file.seek(0)
    return ext, CONTENT_TYPE_BY_FORMAT[actual]


def validate_achievement_file(file):
    """Field validator (usable on model and serializer fields)."""
    inspect_upload(file)


def safe_original_name(name, ext=""):
    """A sanitised, display-only version of the user's file name (never used as a path)."""
    stem = os.path.splitext(os.path.basename(name or ""))[0]
    try:
        stem = get_valid_filename(stem)
    except SuspiciousFileOperation:
        stem = ""
    stem = stem[:100].strip("._ ") or "document"
    return f"{stem}{ext}"
