"""
Shared validators for every DEAS module.

Files
-----
`validate_upload()` is the one entry point for new uploads (announcement covers, achievement
evidence). It never trusts the client: the type is detected from the file's own bytes
(magic numbers + a full parse with Pillow for images, a structural check for PDF), and the
client's extension and Content-Type must AGREE with what was detected.

Rejected always: executables and scripts (PE/ELF/Mach-O/shebang), archives (ZIP/RAR/7z/gz),
SVG / XML / HTML (no sanitiser is implemented, so SVG is not accepted at all), and anything
that is not JPEG, PNG, WebP or PDF.

`validate_image_content()` is the content-only image check that Profiles already used; Profiles
now delegates to it so there is one implementation.

Text and URLs
-------------
`validate_plain_text`, `validate_single_line`, `validate_http_url` and `validate_phone`.
"""
import os
import re
import unicodedata
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator, URLValidator
from PIL import Image, UnidentifiedImageError

KIND_IMAGE = "image"
KIND_PDF = "pdf"

IMAGE_FORMATS = {
    # Pillow format -> (extension we store, MIME type, client extensions accepted)
    "JPEG": ("jpg", "image/jpeg", {".jpg", ".jpeg", ".jpe", ".jfif"}),
    "PNG": ("png", "image/png", {".png"}),
    "WEBP": ("webp", "image/webp", {".webp"}),
}
PDF_MIME = "application/pdf"
PDF_EXTENSIONS = {".pdf"}

# Content types browsers send when they do not know better; these never contradict detection.
GENERIC_CONTENT_TYPES = {"", "application/octet-stream", "binary/octet-stream"}

DEFAULT_MAX_IMAGE_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_PDF_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_IMAGE_PIXELS = 25_000_000

# Signatures of content that is never acceptable, whatever the extension says.
_FORBIDDEN_SIGNATURES = (
    (b"MZ", "Executable files are not allowed."),
    (b"\x7fELF", "Executable files are not allowed."),
    (b"\xca\xfe\xba\xbe", "Executable files are not allowed."),
    (b"\xcf\xfa\xed\xfe", "Executable files are not allowed."),
    (b"\xce\xfa\xed\xfe", "Executable files are not allowed."),
    (b"\xfe\xed\xfa\xce", "Executable files are not allowed."),
    (b"\xfe\xed\xfa\xcf", "Executable files are not allowed."),
    (b"#!", "Scripts are not allowed."),
    (b"PK\x03\x04", "Archives and office files are not allowed."),
    (b"Rar!", "Archives are not allowed."),
    (b"7z\xbc\xaf\x27\x1c", "Archives are not allowed."),
    (b"\x1f\x8b", "Archives are not allowed."),
)
_MARKUP_PREFIX = re.compile(rb"^\s*(?:\xef\xbb\xbf)?\s*<", re.DOTALL)
_SVG_MARKER = re.compile(rb"<svg[\s>]", re.IGNORECASE)

# PDF features that can run code or carry hidden payloads. Names may be hex-escaped
# (/J#61vaScript), so escapes are decoded before matching.
_PDF_NAME_ESCAPE = re.compile(rb"#([0-9A-Fa-f]{2})")
_PDF_ACTIVE_CONTENT = re.compile(
    rb"/(?:JavaScript|JS|Launch|EmbeddedFiles?|RichMedia|XFA|SubmitForm|ImportData)(?![A-Za-z])"
)


@dataclass(frozen=True)
class DetectedFile:
    kind: str  # "image" | "pdf"
    format: str  # "JPEG" | "PNG" | "WEBP" | "PDF"
    mime: str
    extension: str  # extension we store (from the detected type)
    size: int
    width: int | None = None
    height: int | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def human_size(num_bytes):
    if num_bytes >= 1024 * 1024:
        return f"{round(num_bytes / (1024 * 1024), 1):g} MB"
    return f"{max(1, num_bytes // 1024)} KB"


def _read_head(upload, length=4096):
    upload.seek(0)
    head = upload.read(length)
    upload.seek(0)
    return head


def _check_forbidden(head):
    for signature, message in _FORBIDDEN_SIGNATURES:
        if head.startswith(signature):
            raise ValidationError(message, code="forbidden_file_type")
    if _MARKUP_PREFIX.match(head) or _SVG_MARKER.search(head):
        raise ValidationError(
            "SVG, HTML and XML files are not allowed.", code="forbidden_file_type"
        )


def _sniff(head):
    if head.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "WEBP"
    if head.startswith(b"%PDF-"):
        return "PDF"
    return None


def _client_extension(upload):
    name = getattr(upload, "name", "") or ""
    if "\x00" in name:
        raise ValidationError("Invalid file name.", code="invalid_filename")
    return os.path.splitext(name.replace("\\", "/").rsplit("/", 1)[-1])[1].lower()


def _client_content_type(upload):
    value = (getattr(upload, "content_type", "") or "").split(";", 1)[0].strip().lower()
    return value


# ---------------------------------------------------------------------------
# Images (content-only check, shared with Profiles)
# ---------------------------------------------------------------------------
def validate_image_content(upload, *, max_bytes):
    """
    Validate an uploaded image by its real content and return the Pillow format
    ("JPEG", "PNG", "WEBP"). Checks: empty file, size limit, Pillow can parse it, allowed
    format, pixel-count limit (decompression bombs) and structural integrity (verify()).
    """
    if upload.size == 0:
        raise ValidationError("The submitted file is empty.", code="empty_file")
    if upload.size > max_bytes:
        raise ValidationError(
            f"Image is too large. The maximum size is {human_size(max_bytes)}.",
            code="file_too_large",
        )
    max_pixels = getattr(settings, "PROFILE_IMAGE_MAX_PIXELS", DEFAULT_MAX_IMAGE_PIXELS)
    try:
        upload.seek(0)
        with Image.open(upload) as image:  # reads the header only
            detected = image.format
            if detected not in IMAGE_FORMATS:
                raise ValidationError(
                    "Unsupported image format. Please upload a JPEG, PNG or WebP image.",
                    code="unsupported_format",
                )
            width, height = image.size
            if width < 1 or height < 1 or width * height > max_pixels:
                raise ValidationError("The image dimensions are too large.", code="image_too_large")
            image.verify()
    except ValidationError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError, EOFError):
        raise ValidationError("The uploaded file is not a valid image.", code="invalid_image")
    finally:
        try:
            upload.seek(0)
        except (ValueError, OSError):
            pass
    return detected


def _image_dimensions(upload):
    upload.seek(0)
    with Image.open(upload) as image:
        size = image.size
    upload.seek(0)
    return size


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
def validate_pdf_content(upload, *, max_bytes):
    if upload.size == 0:
        raise ValidationError("The submitted file is empty.", code="empty_file")
    if upload.size > max_bytes:
        raise ValidationError(
            f"PDF is too large. The maximum size is {human_size(max_bytes)}.", code="file_too_large"
        )
    upload.seek(0)
    data = upload.read()
    upload.seek(0)
    if not re.match(rb"%PDF-\d\.\d", data[:16]):
        raise ValidationError("The uploaded file is not a valid PDF.", code="invalid_pdf")
    if b"%%EOF" not in data[-2048:]:
        raise ValidationError("The PDF file is incomplete or damaged.", code="invalid_pdf")
    decoded = _PDF_NAME_ESCAPE.sub(lambda m: bytes([int(m.group(1), 16)]), data)
    if _PDF_ACTIVE_CONTENT.search(decoded):
        raise ValidationError(
            "PDFs containing scripts, embedded files or interactive forms are not allowed.",
            code="pdf_active_content",
        )
    return "PDF"


# ---------------------------------------------------------------------------
# The main entry point
# ---------------------------------------------------------------------------
def validate_upload(upload, *, allowed_kinds=(KIND_IMAGE, KIND_PDF), max_image_bytes=None, max_pdf_bytes=None):
    """
    Validate one uploaded file. Returns a DetectedFile; raises django ValidationError.
    The extension we later store comes from the DETECTED type, never from the client name.
    """
    max_image_bytes = max_image_bytes or getattr(settings, "COMMON_MAX_IMAGE_BYTES", DEFAULT_MAX_IMAGE_BYTES)
    max_pdf_bytes = max_pdf_bytes or getattr(settings, "COMMON_MAX_PDF_BYTES", DEFAULT_MAX_PDF_BYTES)
    if upload is None or not getattr(upload, "size", 0):
        raise ValidationError("The submitted file is empty.", code="empty_file")

    client_ext = _client_extension(upload)
    head = _read_head(upload)
    _check_forbidden(head)
    detected = _sniff(head)

    allowed_labels = []
    if KIND_IMAGE in allowed_kinds:
        allowed_labels.append("JPEG, PNG or WebP images")
    if KIND_PDF in allowed_kinds:
        allowed_labels.append("PDF documents")
    unsupported = ValidationError(
        f"Unsupported file type. Allowed: {' and '.join(allowed_labels)}.", code="unsupported_format"
    )

    if detected in IMAGE_FORMATS and KIND_IMAGE in allowed_kinds:
        fmt = validate_image_content(upload, max_bytes=max_image_bytes)
        if fmt != detected:  # header magic and Pillow disagree: refuse
            raise ValidationError("The uploaded file is not a valid image.", code="invalid_image")
        extension, mime, accepted_ext = IMAGE_FORMATS[fmt]
        kind = KIND_IMAGE
    elif detected == "PDF" and KIND_PDF in allowed_kinds:
        fmt = validate_pdf_content(upload, max_bytes=max_pdf_bytes)
        extension, mime, accepted_ext = "pdf", PDF_MIME, PDF_EXTENSIONS
        kind = KIND_PDF
    else:
        raise unsupported

    if client_ext and client_ext not in accepted_ext:
        raise ValidationError(
            "The file extension does not match the file content.", code="extension_mismatch"
        )
    client_type = _client_content_type(upload)
    if client_type not in GENERIC_CONTENT_TYPES and client_type != mime and not (
        mime == "image/jpeg" and client_type in {"image/jpg", "image/pjpeg"}
    ):
        raise ValidationError("The file type does not match the file content.", code="mime_mismatch")

    width = height = None
    if kind == KIND_IMAGE:
        width, height = _image_dimensions(upload)
    return DetectedFile(kind, fmt, mime, extension, upload.size, width, height)


# ---------------------------------------------------------------------------
# Text, URLs, phone numbers
# ---------------------------------------------------------------------------
_HTML_TAG = re.compile(r"<\s*/?\s*[a-zA-Z!?][^>]*>")
_DANGEROUS_SCHEMES = re.compile(r"(?i)\b(?:javascript|vbscript)\s*:|\bdata:\s*(?:text|image|application)/")
_PHONE = re.compile(r"^\+?[0-9 ()\-]{6,20}$")

_http_url_validator = URLValidator(schemes=["http", "https"])
_email_validator = EmailValidator()


def validate_plain_text(value):
    """Multi-line plain text: no control characters (except newline/tab), no HTML, no script URLs."""
    if not value:
        return
    for ch in value:
        if unicodedata.category(ch) == "Cc" and ch not in "\n\r\t":
            raise ValidationError("Control characters are not allowed.", code="control_chars")
    if _HTML_TAG.search(value):
        raise ValidationError("HTML is not allowed. Please use plain text.", code="html_not_allowed")
    if _DANGEROUS_SCHEMES.search(value):
        raise ValidationError("This text contains a link type that is not allowed.", code="unsafe_url")


def validate_single_line(value):
    if not value:
        return
    if any(unicodedata.category(ch) == "Cc" for ch in value):
        raise ValidationError("Line breaks and control characters are not allowed here.", code="control_chars")
    validate_plain_text(value)


def validate_http_url(value):
    """http(s) only: javascript:, data:, file:, ftp: ... are rejected."""
    if not value:
        return
    try:
        _http_url_validator(value)
    except ValidationError:
        raise ValidationError("Enter a valid URL starting with http:// or https://.", code="invalid_url")


def validate_phone(value):
    if not value:
        return
    digits = sum(ch.isdigit() for ch in value)
    if not _PHONE.match(value) or digits < 6 or digits > 15:
        raise ValidationError(
            "Enter a valid phone number (digits, spaces, +, -, parentheses).", code="invalid_phone"
        )


def validate_tag_list(value, *, max_items=20, max_length=40):
    if not isinstance(value, list):
        raise ValidationError("Must be a list of text values.", code="invalid_list")
    if len(value) > max_items:
        raise ValidationError(f"At most {max_items} items are allowed.", code="too_many_items")
    seen = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValidationError("Every item must be non-empty text.", code="invalid_item")
        if len(item) > max_length:
            raise ValidationError(f"Each item can be at most {max_length} characters.", code="item_too_long")
        validate_single_line(item)
        key = item.strip().lower()
        if key in seen:
            raise ValidationError("Duplicate items are not allowed.", code="duplicate_item")
        seen.add(key)
