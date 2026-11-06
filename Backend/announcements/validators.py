from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from PIL import Image

MAX_BANNER_BYTES = 2 * 1024 * 1024  # 2 MB
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}

_url_validator = URLValidator(schemes=["http", "https"])


def validate_http_url(value):
    """Only absolute http(s) URLs: blocks javascript:, data:, ftp:, etc."""
    _url_validator(value)


def validate_banner(image):
    if image.size > MAX_BANNER_BYTES:
        raise ValidationError("Banner image must be 2 MB or smaller.")
    try:
        image.seek(0)
        img = Image.open(image)
        fmt = img.format
        img.verify()  # detects truncated / corrupt files
    except Exception:
        raise ValidationError("Upload a valid image file.")
    finally:
        image.seek(0)
    if fmt not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError("Banner must be a JPEG, PNG or WebP image.")
