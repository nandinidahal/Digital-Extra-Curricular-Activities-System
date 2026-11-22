import uuid

from django.core.files.storage import storages
from django.db import models


def private_attachment_storage():
    """Private storage (settings.STORAGES['messaging_private']); never exposed via MEDIA_URL."""
    return storages["messaging_private"]


def attachment_upload_to(instance, filename):
    """
    messaging/<conversation uuid>/<random hex>.<ext>
    `filename` is built by the service from the DETECTED type, never from the client's name.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"messaging/{instance.message.conversation_id}/{uuid.uuid4().hex}.{ext}"


class MessageAttachment(models.Model):
    class Kind(models.TextChoices):
        IMAGE = "image", "Image"
        FILE = "file", "File"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        "messaging.Message", on_delete=models.CASCADE, related_name="attachments"
    )
    kind = models.CharField(max_length=10, choices=Kind.choices)
    file = models.FileField(
        upload_to=attachment_upload_to, storage=private_attachment_storage, max_length=255
    )
    original_name = models.CharField(max_length=150)  # sanitised, display only
    content_type = models.CharField(max_length=100)  # from the detected type, not the client
    size = models.PositiveBigIntegerField()
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind__in=["image", "file"]),
                name="messaging_attachment_kind_valid",
            ),
        ]

    def __str__(self):
        return f"{self.kind} attachment {self.id}"
