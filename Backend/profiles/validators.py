"""
Validators for the Profiles module.

Text and URL validators are plain functions so they can be used both by the
model (admin / full_clean) and by the serializers. Image validation inspects
the real file content with Pillow; the file extension and the Content-Type sent
by the client are never trusted.
"""
import unicodedata
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

from common.validators import validate_image_content

ALLOWED_IMAGE_FORMATS = {
    # Pillow format name -> file extension we store
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
}
DEFAULT_MAX_IMAGE_PIXELS = 25_000_000  # 25 megapixels; guards against decompression bombs

_web_url_validator = URLValidator(schemes=["http", "https"])


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------
def _has_control_chars(value, allowed=""):
    return any(unicodedata.category(ch) == "Cc" and ch not in allowed for ch in value)


def validate_single_line(value):
    """No control characters at all (no newlines, tabs, NUL bytes...)."""
    if value and _has_control_chars(value):
        raise ValidationError("Control characters and line breaks are not allowed here.")


def validate_multiline(value):
    """Newlines and tabs are fine in a bio; other control characters are not."""
    if value and _has_control_chars(value, allowed="\n\r\t"):
        raise ValidationError("Control characters are not allowed.")


def validate_tag_list(value):
    """Interests / skills are stored as a JSON list of short, non-empty strings."""
    if not isinstance(value, list):
        raise ValidationError("Must be a list of text values.")
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValidationError("Every item must be non-empty text.")
        if len(item) > 40:
            raise ValidationError("Each item can be at most 40 characters.")


# ---------------------------------------------------------------------------
# URLs
# ---------------------------------------------------------------------------
def validate_web_url(value):
    """http(s) only: rejects javascript:, data:, ftp: and similar schemes."""
    if not value:
        return
    try:
        _web_url_validator(value)
    except ValidationError:
        raise ValidationError("Enter a valid URL starting with http:// or https://.")


def _validate_host(value, domain, label):
    if not value:
        return
    validate_web_url(value)
    host = (urlparse(value).hostname or "").lower()
    if host != domain and not host.endswith("." + domain):
        raise ValidationError(f"Enter a valid {label} URL (it must be on {domain}).")


def validate_linkedin_url(value):
    _validate_host(value, "linkedin.com", "LinkedIn")


def validate_github_url(value):
    _validate_host(value, "github.com", "GitHub")


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------
def validate_image_upload(upload, *, max_bytes):
    """
    Validate an uploaded image and return its real format ("JPEG", "PNG", "WEBP").

    Checks: size limit, that Pillow can really parse the file, that the detected
    format is allowed, a pixel-count limit, and structural integrity.
    The implementation is shared by every module and lives in common.validators.
    """
    return validate_image_content(upload, max_bytes=max_bytes)
