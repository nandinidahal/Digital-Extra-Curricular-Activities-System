"""
Validation for message text and attachments.

Text is PLAIN TEXT. It is stored as sent (trimmed, control characters refused) and must be
rendered as text by the frontend (React escapes by default - never use dangerouslySetInnerHTML).
It is not HTML-escaped on the way in, because that would corrupt "<3" or code snippets.

Attachments are identified by their real content, never by file name or client Content-Type:
* images: JPEG / PNG / WebP via Pillow (profiles.validators.validate_image_upload), then
  RE-ENCODED, which strips EXIF/GPS metadata and anything appended to the image;
* documents: PDF only (magic bytes + trailer), PDFs with JavaScript / launch actions /
  embedded files are refused.
Everything else (executables, HTML, SVG, archives, Office files, ...) is rejected.
"""
import os
import re
import unicodedata
from dataclasses import dataclass
from io import BytesIO

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils.text import get_valid_filename
from PIL import Image, ImageOps

from profiles.validators import validate_image_upload

DEFAULT_MAX_LENGTH = 5000
MAX_IMAGE_EDGE = 2560
_IMAGE_TYPES = {"JPEG": ("jpg", "image/jpeg"), "PNG": ("png", "image/png"), "WEBP": ("webp", "image/webp")}
_PDF_DANGEROUS = re.compile(rb"/(?:JavaScript|JS|Launch|EmbeddedFile|RichMedia|XFA)(?![A-Za-z0-9])")
_ALLOWED_CONTROL = {"\n", "\t"}


def max_message_length():
    return getattr(settings, "MESSAGING_MAX_MESSAGE_LENGTH", DEFAULT_MAX_LENGTH)


def max_attachments():
    return getattr(settings, "MESSAGING_MAX_ATTACHMENTS_PER_MESSAGE", 5)


def image_max_bytes():
    return getattr(settings, "MESSAGING_IMAGE_MAX_BYTES", 5 * 1024 * 1024)


def file_max_bytes():
    return getattr(settings, "MESSAGING_FILE_MAX_BYTES", 10 * 1024 * 1024)


def clean_message_content(value):
    """Return the normalised text ('' allowed - the caller decides if empty is acceptable)."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValidationError("Message content must be text.", code="invalid")
    value = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(value) > max_message_length():
        raise ValidationError(
            f"Messages can be at most {max_message_length()} characters long.", code="max_length"
        )
    for char in value:
        if char not in _ALLOWED_CONTROL and unicodedata.category(char) == "Cc":
            raise ValidationError("Message contains invalid control characters.", code="invalid")
    return value


@dataclass
class PreparedAttachment:
    kind: str  # "image" | "file"
    content: ContentFile
    extension: str
    content_type: str
    original_name: str
    size: int
    width: int | None = None
    height: int | None = None


def _human(nbytes):
    return f"{round(nbytes / (1024 * 1024), 1):g} MB" if nbytes >= 1024 * 1024 else f"{max(1, nbytes // 1024)} KB"


def _display_name(raw_name, extension):
    """Safe display name: base name only, no path, harmless characters, detected extension."""
    base = os.path.splitext(os.path.basename(str(raw_name or "")).replace("\\", "/").split("/")[-1])[0]
    base = unicodedata.normalize("NFKC", base)
    try:
        base = get_valid_filename(base)[:100]
    except Exception:  # get_valid_filename raises on names like "." or ""
        base = ""
    return f"{base or 'attachment'}.{extension}"


def _reencode_image(upload, image_format):
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
    data = buffer.getvalue()
    return ContentFile(data), len(data), width, height


def _read_head(upload, n):
    upload.seek(0)
    head = upload.read(n)
    upload.seek(0)
    return head


def _validate_pdf(upload):
    if upload.size > file_max_bytes():
        raise ValidationError(f"File is too large. The maximum size is {_human(file_max_bytes())}.",
                              code="file_too_large")
    upload.seek(0)
    data = upload.read()
    upload.seek(0)
    if not data.startswith(b"%PDF-"):
        raise ValidationError("Unsupported file type.", code="unsupported_format")
    if b"%%EOF" not in data[-2048:]:
        raise ValidationError("The PDF file is incomplete or damaged.", code="invalid_file")
    if _PDF_DANGEROUS.search(data):
        raise ValidationError(
            "PDF files containing scripts, launch actions or embedded files are not allowed.",
            code="unsafe_file",
        )
    return data


def prepare_attachment(upload):
    """Validate one upload and return a PreparedAttachment ready to be stored."""
    size = getattr(upload, "size", None)
    if not size:
        raise ValidationError("The submitted file is empty.", code="empty_file")
    head = _read_head(upload, 16)
    if head.startswith(b"%PDF-"):
        data = _validate_pdf(upload)
        return PreparedAttachment(
            kind="file", content=ContentFile(data), extension="pdf",
            content_type="application/pdf",
            original_name=_display_name(getattr(upload, "name", ""), "pdf"), size=len(data),
        )
    # Everything that is not a PDF must be a real, allowed image.
    if size > image_max_bytes():
        raise ValidationError(f"Image is too large. The maximum size is {_human(image_max_bytes())}.",
                              code="file_too_large")
    try:
        image_format = validate_image_upload(upload, max_bytes=image_max_bytes())
    except ValidationError as exc:
        if getattr(exc, "code", None) in ("invalid_image", "unsupported_format"):
            raise ValidationError(
                "Unsupported file type. Allowed: JPEG, PNG or WebP images and PDF documents.",
                code="unsupported_format",
            )
        raise
    extension, content_type = _IMAGE_TYPES[image_format]
    content, stored_size, width, height = _reencode_image(upload, image_format)
    return PreparedAttachment(
        kind="image", content=content, extension=extension, content_type=content_type,
        original_name=_display_name(getattr(upload, "name", ""), extension),
        size=stored_size, width=width, height=height,
    )
