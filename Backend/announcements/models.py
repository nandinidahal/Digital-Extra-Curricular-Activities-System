import os
import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.text import slugify

from .storage import get_private_storage
from .validators import (ALLOWED_ATTACHMENT_EXTENSIONS, ALLOWED_IMAGE_EXTENSIONS,
                         validate_attachment_file, validate_image_file)


class Category(models.Model):
    """Admin-managed announcement categories (no duplicates, case-insensitive)."""

    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name_plural = "categories"
        constraints = [models.UniqueConstraint(Lower("name"), name="uniq_ann_category_name_ci")]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "category"
            slug, n = base, 2
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class AnnouncementStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"


class ActivityType(models.TextChoices):
    PHYSICAL = "physical", "Physical"
    ONLINE = "online", "Online"
    HYBRID = "hybrid", "Hybrid"


def announcement_image_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        ext = ""
    return f"announcements/images/{uuid.uuid4().hex}{ext}"


def announcement_attachment_path(instance, filename):
    """Random storage name; the user's file name is never part of the path."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
        ext = ""
    return f"announcements/attachments/{instance.published_by_id}/{uuid.uuid4().hex}{ext}"


class Announcement(models.Model):
    # Field names such as published_by / short_description / full_description / activity_name /
    # activity_type / country / start_date / end_date are relied on by other modules
    # (social, friends) - do not rename them.
    title = models.CharField(max_length=200)
    short_description = models.CharField(max_length=300)
    full_description = models.TextField()
    activity_name = models.CharField(max_length=200, blank=True, default="")
    keywords = models.CharField(max_length=255, blank=True, default="")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="announcements")
    activity_type = models.CharField(max_length=10, choices=ActivityType.choices, default=ActivityType.PHYSICAL)
    country = models.CharField(max_length=100, blank=True, default="")
    location = models.CharField(max_length=255, blank=True, default="")
    start_date = models.DateField(null=True, blank=True)   # "event date"
    end_date = models.DateField(null=True, blank=True)
    deadline = models.DateField(null=True, blank=True)

    image = models.FileField(upload_to=announcement_image_path, max_length=255, null=True, blank=True,
                             validators=[validate_image_file])
    attachment = models.FileField(upload_to=announcement_attachment_path, storage=get_private_storage,
                                  max_length=255, null=True, blank=True, validators=[validate_attachment_file])
    attachment_name = models.CharField(max_length=255, blank=True, default="")

    # The author always comes from the authenticated request, never from the payload.
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                     related_name="published_announcements")
    status = models.CharField(max_length=10, choices=AnnouncementStatus.choices, default=AnnouncementStatus.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)   # future value == scheduled
    expires_at = models.DateTimeField(null=True, blank=True)     # after this it leaves active listings
    # Curation flags: only coordinators/admins may set them (see serializers).
    is_featured = models.BooleanField(default=False)
    is_important = models.BooleanField(default=False)
    share_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "-published_at"], name="ann_status_published_idx"),
            models.Index(fields=["category", "-published_at"], name="ann_cat_published_idx"),
            models.Index(fields=["published_by", "status"], name="ann_author_status_idx"),
            models.Index(fields=["start_date"], name="ann_start_date_idx"),
            models.Index(fields=["deadline"], name="ann_deadline_idx"),
            models.Index(fields=["expires_at"], name="ann_expires_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(status__in=AnnouncementStatus.values), name="ann_status_valid"),
            models.CheckConstraint(condition=Q(activity_type__in=ActivityType.values), name="ann_activity_type_valid"),
            models.CheckConstraint(
                condition=Q(status="draft") | Q(published_at__isnull=False), name="ann_published_has_date"
            ),
            models.CheckConstraint(
                condition=Q(start_date__isnull=True) | Q(end_date__isnull=True) | Q(end_date__gte=F("start_date")),
                name="ann_end_not_before_start",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.status == AnnouncementStatus.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def state(self):
        """draft | scheduled | published | expired (what the owner sees in "my announcements")."""
        now = timezone.now()
        if self.status != AnnouncementStatus.PUBLISHED:
            return "draft"
        if self.published_at and self.published_at > now:
            return "scheduled"
        if self.expires_at and self.expires_at <= now:
            return "expired"
        return "published"

    def __str__(self):
        return self.title


class Bookmark(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="announcement_bookmarks")
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="bookmarks")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "-created_at"], name="ann_bm_user_created_idx")]
        constraints = [
            models.UniqueConstraint(fields=["user", "announcement"], name="uniq_announcement_bookmark"),
        ]

    def __str__(self):
        return f"{self.user_id} -> {self.announcement_id}"
