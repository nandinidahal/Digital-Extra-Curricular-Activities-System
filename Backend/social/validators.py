"""
Validation for the Social module.

Text: plain text only. The API stores exactly what is sent (after trimming) and
the frontend must render it as text (React does this by default; never use
dangerouslySetInnerHTML). Because of that, HTML-looking input is rejected
instead of being "cleaned", so what the user sees is what is stored.

Images: the real file content is inspected with Pillow (profiles.validators);
the extension and Content-Type sent by the client are never trusted.
"""
from io import BytesIO

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

from common.validators import validate_plain_text
from profiles.validators import ALLOWED_IMAGE_FORMATS, validate_image_upload

DEFAULT_MAX_IMAGES = 6
DEFAULT_MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_EDGE = 2048  # longest side is scaled down to this
MULTIPART_OVERHEAD_BYTES = 256 * 1024


def max_images_per_post():
    return getattr(settings, "SOCIAL_MAX_IMAGES_PER_POST", DEFAULT_MAX_IMAGES)


def max_image_bytes():
    return getattr(settings, "SOCIAL_IMAGE_MAX_BYTES", DEFAULT_MAX_IMAGE_BYTES)


def validate_social_text(value):
    """Reject control characters (except newline/tab), HTML tags and script-like URLs."""
    validate_plain_text(value)


def validate_post_image(upload):
    """Return the real image format ("JPEG"/"PNG"/"WEBP") or raise ValidationError."""
    return validate_image_upload(upload, max_bytes=max_image_bytes())


def process_post_image(upload, image_format):
    """
    Re-encode the image: strips EXIF/GPS metadata, applies the EXIF rotation, scales
    very large images down, and proves the whole file decodes (not just its header).
    Returns (ContentFile, width, height, extension).
    """
    upload.seek(0)
    try:
        with Image.open(upload) as image:
            image.load()
            image = ImageOps.exif_transpose(image)
            image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.LANCZOS)
            buffer = BytesIO()
            if image_format == "JPEG":
                if image.mode not in ("RGB", "L"):
                    image = image.convert("RGB")
                image.save(buffer, "JPEG", quality=85, optimize=True)
            elif image_format == "PNG":
                image.save(buffer, "PNG", optimize=True)
            else:
                image.save(buffer, "WEBP", quality=85)
            width, height = image.size
    except (OSError, SyntaxError, ValueError, EOFError, Image.DecompressionBombError):
        raise ValidationError("The uploaded file is not a valid image.", code="invalid_image")
    extension = ALLOWED_IMAGE_FORMATS[image_format]
    return ContentFile(buffer.getvalue()), width, height, extension
