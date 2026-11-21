import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.text import get_valid_filename
from django.core.exceptions import SuspiciousFileOperation
from PIL import Image

IMAGE_FORMAT_BY_EXTENSION = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
ALLOWED_IMAGE_EXTENSIONS = set(IMAGE_FORMAT_BY_EXTENSION)
ALLOWED_ATTACHMENT_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | {".pdf"}
CONTENT_TYPE_BY_FORMAT = {
    "PDF": "application/pdf",
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}
ALLOWED_DECLARED_CONTENT_TYPES = {
    "application/pdf", "application/x-pdf",
    "image/jpeg", "image/jpg", "image/pjpeg", "image/png", "image/webp",
}
MB = 1024 * 1024
DEFAULT_MAX_IMAGE_SIZE = 5 * MB
DEFAULT_MAX_ATTACHMENT_SIZE = 10 * MB


def _human_size(num_bytes):
    if num_bytes >= MB:
        return f"{num_bytes / MB:.1f} MB".replace(".0 MB", " MB")
    return f"{max(1, round(num_bytes / 1024))} KB"


def max_image_size():
    return int(getattr(settings, "ANNOUNCEMENT_MAX_IMAGE_SIZE", DEFAULT_MAX_IMAGE_SIZE))


def max_attachment_size():
    return int(getattr(settings, "ANNOUNCEMENT_MAX_ATTACHMENT_SIZE", DEFAULT_MAX_ATTACHMENT_SIZE))


def inspect_upload(file, allowed_extensions, limit):
    """Validate extension, size, declared content type and the REAL file contents.

    Returns (extension, content_type). A renamed or corrupt file is rejected.
    """
    name = getattr(file, "name", "") or ""
    ext = os.path.splitext(name)[1].lower()
    if ext not in allowed_extensions:
        allowed = ", ".join(sorted(e.lstrip(".").upper() for e in allowed_extensions))
        raise ValidationError(f"Unsupported file type. Allowed types: {allowed}.", code="invalid_extension")

    size = getattr(file, "size", None)
    if not size:
        raise ValidationError("The submitted file is empty.", code="empty_file")
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
            if not file.read(1024).lstrip().startswith(b"%PDF-"):
                raise ValidationError("The file is not a valid PDF document.", code="invalid_content")
            actual = "PDF"
        else:
            try:
                img = Image.open(file)
                actual = img.format
                img.verify()
            except Exception:
                raise ValidationError("The file is not a valid image.", code="invalid_content")
            if actual != IMAGE_FORMAT_BY_EXTENSION[ext]:
                raise ValidationError("The file contents do not match its extension.", code="extension_mismatch")
    finally:
        file.seek(0)
    return ext, CONTENT_TYPE_BY_FORMAT[actual]


def validate_image_file(file):
    inspect_upload(file, ALLOWED_IMAGE_EXTENSIONS, max_image_size())


def validate_attachment_file(file):
    inspect_upload(file, ALLOWED_ATTACHMENT_EXTENSIONS, max_attachment_size())


def safe_original_name(name, ext=""):
    """Sanitised, display-only version of the uploaded name (never used as a storage path)."""
    stem = os.path.splitext(os.path.basename(name or ""))[0]
    try:
        stem = get_valid_filename(stem)
    except SuspiciousFileOperation:
        stem = ""
    stem = stem[:100].strip("._ ") or "attachment"
    return f"{stem}{ext}"
