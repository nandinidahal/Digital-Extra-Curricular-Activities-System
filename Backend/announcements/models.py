"""
Announcements data model (user-based: any authenticated user may create and publish).

Relationships
* Announcement.author     -> AUTH_USER_MODEL (CASCADE: a deleted account takes its announcements)
* Announcement.category   -> Category (PROTECT: a category in use can only be deactivated)
* AnnouncementBookmark    -> user + announcement, UNIQUE(user, announcement)
* AnnouncementReport      -> reporter + announcement; one ACTIVE report per (reporter, announcement)
* achievements.Achievement.related_announcement and social.Post.shared_announcement point here
  with SET_NULL, so deleting an announcement never deletes someone's achievement or post.
"""
from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower

from common.files import build_storage_name
from common.models import BaseModel, UUIDPrimaryKeyModel

TITLE_MAX_LENGTH = 200
SHORT_DESCRIPTION_MAX_LENGTH = 300
DESCRIPTION_MAX_LENGTH = 10000
LONG_TEXT_MAX_LENGTH = 3000
REPORT_DESCRIPTION_MAX_LENGTH = 1000
REVIEW_COMMENT_MAX_LENGTH = 1000


def announcement_cover_upload_to(instance, filename):
    """announcements/covers/<announcement uuid>/<random>.<detected ext> (client name never used)."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    if ext not in {"jpg", "png", "webp"}:
        ext = "jpg"
    return build_storage_name("announcements", "covers", instance.pk, extension=ext)


class Category(BaseModel):
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=90, unique=True)
    description = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"
        constraints = [
            models.UniqueConstraint(Lower("name"), name="announcements_category_name_ci_unique"),
        ]

    def __str__(self):
        return self.name


class Announcement(BaseModel):
    class ActivityType(models.TextChoices):
        PHYSICAL = "physical", "Physical"
        ONLINE = "online", "Online"
        HYBRID = "hybrid", "Hybrid"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Public"
        MEMBERS_ONLY = "members_only", "Members only"
        PRIVATE = "private", "Private"

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="announcements")
    title = models.CharField(max_length=TITLE_MAX_LENGTH)
    slug = models.SlugField(max_length=230, unique=True)
    short_description = models.CharField(max_length=SHORT_DESCRIPTION_MAX_LENGTH, blank=True)
    description = models.TextField(max_length=DESCRIPTION_MAX_LENGTH, blank=True)
    category = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.PROTECT, related_name="announcements"
    )
    activity_type = models.CharField(max_length=10, choices=ActivityType.choices, default=ActivityType.PHYSICAL)

    organizer_name = models.CharField(max_length=150, blank=True)
    organizer_email = models.EmailField(max_length=254, blank=True)
    organizer_phone = models.CharField(max_length=20, blank=True)
    contact_information = models.TextField(max_length=1000, blank=True)
    # Organizer e-mail/phone/contact text are shown to logged-in members only when this is on.
    # Visitors never see them; the author and moderators always do.
    show_contact_details = models.BooleanField(default=False)

    location = models.CharField(max_length=255, blank=True)
    online_link = models.URLField(max_length=500, blank=True)
    start_datetime = models.DateTimeField(null=True, blank=True)
    end_datetime = models.DateTimeField(null=True, blank=True)
    registration_deadline = models.DateTimeField(null=True, blank=True)
    registration_link = models.URLField(max_length=500, blank=True)
    eligibility_criteria = models.TextField(max_length=LONG_TEXT_MAX_LENGTH, blank=True)
    requirements = models.TextField(max_length=LONG_TEXT_MAX_LENGTH, blank=True)
    cover_image = models.ImageField(upload_to=announcement_cover_upload_to, max_length=255, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.PUBLIC)
    published_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="announcements_archived",
    )
    is_edited = models.BooleanField(default=False)  # changed after it was published

    class Meta:
        ordering = ["-published_at", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["draft", "published", "archived"]), name="announcements_status_valid"
            ),
            models.CheckConstraint(
                condition=Q(visibility__in=["public", "members_only", "private"]),
                name="announcements_visibility_valid",
            ),
            models.CheckConstraint(
                condition=Q(activity_type__in=["physical", "online", "hybrid"]),
                name="announcements_activity_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(end_datetime__isnull=True) | Q(start_datetime__isnull=True)
                | Q(end_datetime__gte=F("start_datetime")),
                name="announcements_end_after_start",
            ),
            # Event-date policy: registration closes no later than the event starts.
            models.CheckConstraint(
                condition=Q(registration_deadline__isnull=True) | Q(start_datetime__isnull=True)
                | Q(registration_deadline__lte=F("start_datetime")),
                name="announcements_deadline_before_start",
            ),
            models.CheckConstraint(
                condition=~Q(status="published") | Q(published_at__isnull=False),
                name="announcements_published_has_timestamp",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "visibility", "-published_at"], name="ann_listing_idx"),
            models.Index(fields=["author", "status", "-created_at"], name="ann_author_idx"),
            models.Index(fields=["category", "status"], name="ann_category_idx"),
            models.Index(fields=["start_datetime"], name="ann_start_idx"),
            models.Index(fields=["registration_deadline"], name="ann_deadline_idx"),
        ]

    def __str__(self):
        return self.title

    @property
    def is_published(self):
        return self.status == self.Status.PUBLISHED


class AnnouncementBookmark(UUIDPrimaryKeyModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="announcement_bookmarks"
    )
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="bookmarks")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "announcement"], name="announcements_bookmark_unique"),
        ]
        indexes = [models.Index(fields=["user", "-created_at"], name="ann_bookmark_user_idx")]

    def __str__(self):
        return f"{self.user_id} bookmarked {self.announcement_id}"


class AnnouncementReport(BaseModel):
    class Reason(models.TextChoices):
        SPAM = "spam", "Spam"
        MISLEADING = "misleading", "Misleading information"
        INAPPROPRIATE = "inappropriate", "Inappropriate content"
        FRAUDULENT = "fraudulent", "Fraudulent opportunity"
        HARASSMENT = "harassment", "Harassment"
        INCORRECT = "incorrect", "Incorrect information"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        REVIEWED = "reviewed", "Reviewed"
        RESOLVED = "resolved", "Resolved"
        REJECTED = "rejected", "Rejected"

    class Action(models.TextChoices):
        NONE = "none", "No action"
        ARCHIVED = "archived", "Announcement archived"

    ACTIVE_STATUSES = ("pending", "reviewed")

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="announcement_reports_made"
    )
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="reports")
    reason = models.CharField(max_length=20, choices=Reason.choices)
    description = models.TextField(max_length=REPORT_DESCRIPTION_MAX_LENGTH, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    action_taken = models.CharField(max_length=10, choices=Action.choices, default=Action.NONE)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="announcement_reports_reviewed",
    )
    review_comments = models.TextField(max_length=REVIEW_COMMENT_MAX_LENGTH, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["reporter", "announcement"],
                condition=Q(status__in=["pending", "reviewed"]),
                name="announcements_report_active_unique",
            ),
        ]
        indexes = [models.Index(fields=["status", "-created_at"], name="ann_report_status_idx")]

    def __str__(self):
        return f"Report {self.id} ({self.status})"
