from django.core.exceptions import ValidationError
from PIL import Image

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_CERTIFICATE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_image(image):
    """Real image check (Pillow), not just a file extension."""
    if image.size > MAX_IMAGE_BYTES:
        raise ValidationError("Images must be 5 MB or smaller.")
    try:
        image.seek(0)
        img = Image.open(image)
        fmt = img.format
        img.verify()
    except Exception:
        raise ValidationError("Upload a valid image file.")
    finally:
        image.seek(0)
    if fmt not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError("Images must be JPEG, PNG or WebP.")


def validate_certificate(upload):
    """Certificates may be images or PDFs."""
    if upload.size > MAX_CERTIFICATE_BYTES:
        raise ValidationError("Certificate must be 5 MB or smaller.")
    upload.seek(0)
    head = upload.read(5)
    upload.seek(0)
    if head == b"%PDF-":
        return
    validate_image(upload)
