"""Profile picture validation. Never trusts the file name or the declared content type."""
import io
import os
from collections import namedtuple

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

DEFAULT_MAX_SIZE = 2 * 1024 * 1024  # 2 MB
DEFAULT_MAX_DIMENSION = 4096        # pixels, width and height
MB = 1024 * 1024

# Pillow format -> (stored extension, content type, extensions a client may use)
FORMATS = {
    "JPEG": (".jpg", "image/jpeg", {".jpg", ".jpeg"}),
    "PNG": (".png", "image/png", {".png"}),
    "WEBP": (".webp", "image/webp", {".webp"}),
}
ALLOWED_DECLARED_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/pjpeg", "image/png", "image/webp"}

ProcessedImage = namedtuple("ProcessedImage", "content extension content_type")


def max_picture_size():
    return int(getattr(settings, "PROFILE_PICTURE_MAX_SIZE", DEFAULT_MAX_SIZE))


def max_picture_dimension():
    return int(getattr(settings, "PROFILE_PICTURE_MAX_DIMENSION", DEFAULT_MAX_DIMENSION))


def _human_size(n):
    return f"{n / MB:.1f} MB".replace(".0 MB", " MB") if n >= MB else f"{max(1, round(n / 1024))} KB"


def process_profile_picture(upload):
    """Validate an uploaded picture and return a clean, re-encoded copy.

    Checks: extension, size, declared content type, real image content (Pillow), that the
    content matches the extension, and the pixel dimensions (decompression-bomb guard).
    The image is re-encoded from its pixels, which strips EXIF data such as GPS location.
    Animated images keep only their first frame.
    """
    name = getattr(upload, "name", "") or ""
    ext = os.path.splitext(name)[1].lower()
    allowed_exts = sorted({e for _, _, exts in FORMATS.values() for e in exts})
    if ext not in allowed_exts:
        raise ValidationError("Unsupported file type. Allowed types: JPEG, PNG and WebP.", code="invalid_extension")

    size = getattr(upload, "size", None)
    if not size:
        raise ValidationError("The submitted file is empty.", code="empty_file")
    limit = max_picture_size()
    if size > limit:
        raise ValidationError(
            f"Image is too large ({_human_size(size)}). The maximum allowed size is {_human_size(limit)}.",
            code="file_too_large",
        )

    declared = (getattr(upload, "content_type", "") or "").split(";")[0].strip().lower()
    if declared and declared not in ALLOWED_DECLARED_CONTENT_TYPES:
        raise ValidationError(f"Unsupported content type '{declared}'.", code="invalid_content_type")

    upload.seek(0)
    try:
        probe = Image.open(upload)
        fmt = probe.format
        width, height = probe.size  # read from the header only; nothing is decoded yet
    except Exception:
        raise ValidationError("The file is not a valid image.", code="invalid_content")
    if fmt not in FORMATS:
        raise ValidationError("Images must be JPEG, PNG or WebP.", code="invalid_format")
    if ext not in FORMATS[fmt][2]:
        raise ValidationError("The file contents do not match its extension.", code="extension_mismatch")
    max_dim = max_picture_dimension()
    if width > max_dim or height > max_dim:
        raise ValidationError(
            f"Image dimensions are too large. The maximum is {max_dim}x{max_dim} pixels.", code="dimensions_too_large"
        )

    try:
        upload.seek(0)
        Image.open(upload).verify()  # detects truncated / corrupt files
        upload.seek(0)
        img = Image.open(upload)
        img.load()
        img = ImageOps.exif_transpose(img)  # honour camera rotation before metadata is dropped
        extension, content_type, _ = FORMATS[fmt]
        if fmt == "JPEG":
            img = img.convert("RGB")
        elif img.mode not in ("RGB", "RGBA", "L", "LA"):
            img = img.convert("RGBA" if "A" in img.getbands() or "transparency" in img.info else "RGB")
        buf = io.BytesIO()
        if fmt == "JPEG":
            img.save(buf, "JPEG", quality=90, optimize=True)
        elif fmt == "WEBP":
            img.save(buf, "WEBP", quality=90)
        else:
            img.save(buf, "PNG", optimize=True)
    except Exception:
        raise ValidationError("The file is not a valid image.", code="invalid_content")
    finally:
        upload.seek(0)
    return ProcessedImage(ContentFile(buf.getvalue()), extension, content_type)
