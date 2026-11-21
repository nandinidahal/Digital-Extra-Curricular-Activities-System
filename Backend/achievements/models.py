import mimetypes
import os
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.text import slugify

from .storage import get_private_storage
from .validators import ALLOWED_EXTENSIONS, safe_original_name, validate_achievement_file


class AchievementCategory(models.Model):
    """Admin-managed categories: add new ones in the admin, no code change required."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name_plural = "achievement categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "category"
            slug, n = base, 2
            while AchievementCategory.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Visibility(models.TextChoices):
    PUBLIC = "public", "Public"
    PRIVATE = "private", "Private"


class Achievement(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="achievements")
    category = models.ForeignKey(AchievementCategory, on_delete=models.PROTECT, related_name="achievements")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    issuing_organization = models.CharField(max_length=200)
    achievement_date = models.DateField()
    certificate_number = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=200, blank=True)
    # Private by default: nothing becomes public unless the owner chooses it.
    visibility = models.CharField(max_length=10, choices=Visibility.choices, default=Visibility.PRIVATE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-achievement_date", "-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "-achievement_date"], name="ach_user_date_idx"),
            models.Index(fields=["user", "visibility", "-achievement_date"], name="ach_user_vis_date_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(visibility__in=Visibility.values), name="achievement_visibility_valid"
            ),
        ]

    def __str__(self):
        return self.title


class DocumentType(models.TextChoices):
    CERTIFICATE = "certificate", "Certificate"
    SUPPORTING = "supporting", "Supporting document"


def achievement_document_path(instance, filename):
    """Random, collision-free storage name. The user's file name is never part of the path."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        ext = ""
    return f"achievements/{instance.achievement.user_id}/{uuid.uuid4().hex}{ext}"


class AchievementDocument(models.Model):
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE, related_name="documents")
    file = models.FileField(
        upload_to=achievement_document_path,
        storage=get_private_storage,
        max_length=255,
        validators=[validate_achievement_file],
    )
    document_type = models.CharField(max_length=15, choices=DocumentType.choices, default=DocumentType.SUPPORTING)
    document_name = models.CharField(max_length=150, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    size = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at", "id"]
        indexes = [models.Index(fields=["achievement", "uploaded_at"], name="achdoc_ach_uploaded_idx")]
        constraints = [
            # at most one certificate per achievement; any number of supporting documents
            models.UniqueConstraint(
                fields=["achievement"],
                condition=Q(document_type="certificate"),
                name="uniq_certificate_per_achievement",
            ),
        ]

    def save(self, *args, **kwargs):
        # Fill metadata for documents created outside the API (e.g. the admin).
        if self.file and not self.original_filename:
            ext = os.path.splitext(self.file.name)[1].lower()
            self.original_filename = safe_original_name(self.file.name, ext)
        if self.file and not self.document_name:
            self.document_name = os.path.splitext(self.original_filename)[0][:150]
        if self.file and not self.content_type:
            self.content_type = mimetypes.guess_type(self.file.name)[0] or "application/octet-stream"
        if self.file and not self.size:
            try:
                self.size = self.file.size
            except (OSError, ValueError):
                pass
        super().save(*args, **kwargs)

    def __str__(self):
        return self.document_name or self.original_filename or f"Document {self.pk}"
