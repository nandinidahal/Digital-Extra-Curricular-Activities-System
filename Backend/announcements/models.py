from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.text import slugify

from accounts.validators import phone_validator

from .validators import validate_banner, validate_http_url


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

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


class ActivityType(models.TextChoices):
    PHYSICAL = "physical", "Physical"
    ONLINE = "online", "Online"
    HYBRID = "hybrid", "Hybrid"


class AnnouncementStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    ARCHIVED = "archived", "Archived"


class Announcement(models.Model):
    title = models.CharField(max_length=200)
    short_description = models.CharField(max_length=300)
    full_description = models.TextField()
    activity_name = models.CharField(max_length=150)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="announcements")
    activity_type = models.CharField(max_length=10, choices=ActivityType.choices)
    keywords = models.CharField(
        max_length=255, blank=True, help_text="Comma separated extra search terms, e.g. 'football, futsal'"
    )

    country = models.CharField(max_length=80)
    province = models.CharField(max_length=80, blank=True)
    city = models.CharField(max_length=80, blank=True)
    venue = models.CharField(max_length=200, blank=True)

    start_date = models.DateField()
    end_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    registration_deadline = models.DateTimeField(null=True, blank=True)

    is_free = models.BooleanField(default=True)
    fee_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    registration_link = models.URLField(max_length=500, blank=True, validators=[validate_http_url])
    external_link = models.URLField(max_length=500, blank=True, validators=[validate_http_url])
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=16, blank=True, validators=[phone_validator])
    banner = models.ImageField(upload_to="announcements/banners/%Y/%m/", blank=True, null=True,
                               validators=[validate_banner])

    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="announcements"
    )
    status = models.CharField(max_length=10, choices=AnnouncementStatus.choices,
                              default=AnnouncementStatus.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [F("published_at").desc(nulls_last=True), "-created_at"]
        indexes = [
            models.Index(fields=["status", "-published_at"]),
            models.Index(fields=["country", "city"]),
            models.Index(fields=["activity_type"]),
            models.Index(fields=["start_date"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(end_date__gte=F("start_date")), name="announcement_end_after_start"),
        ]

    def save(self, *args, **kwargs):
        if self.status == AnnouncementStatus.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
