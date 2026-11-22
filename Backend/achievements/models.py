"""
Achievements data model.

Relationships
* Achievement.user                 -> AUTH_USER_MODEL (CASCADE)
* Achievement.category             -> AchievementCategory (PROTECT; deactivate instead of delete)
* Achievement.related_announcement -> announcements.Announcement (SET_NULL, optional)
* Achievement.verified_by          -> AUTH_USER_MODEL (SET_NULL)
* AchievementEvidence              -> Achievement (CASCADE); file in PRIVATE storage
* AchievementReview                -> Achievement (CASCADE); append-only verification history
* social.Post.shared_achievement points here with SET_NULL.

Uploading a certificate does NOT verify anything: only a reviewer's decision does.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from common.files import build_storage_name, private_storage
from common.models import BaseModel, UUIDPrimaryKeyModel

TITLE_MAX_LENGTH = 200
DESCRIPTION_MAX_LENGTH = 5000
COMMENT_MAX_LENGTH = 2000


def evidence_upload_to(instance, filename):
    """achievements/<achievement uuid>/evidence/<random>.<detected ext> in PRIVATE storage."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    if ext not in {"jpg", "png", "webp", "pdf"}:
        ext = "bin"
    return build_storage_name("achievements", instance.achievement_id, "evidence", extension=ext)


class AchievementCategory(BaseModel):
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=90, unique=True)
    description = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "achievement categories"
        constraints = [
            models.UniqueConstraint(Lower("name"), name="achievements_category_name_ci_unique"),
        ]

    def __str__(self):
        return self.name


class Achievement(BaseModel):
    class AchievementType(models.TextChoices):
        AWARD = "award", "Award"
        CERTIFICATE = "certificate", "Certificate"
        COMPETITION = "competition", "Competition result"
        PARTICIPATION = "participation", "Participation"
        PROJECT = "project", "Project"
        PUBLICATION = "publication", "Publication"
        SCHOLARSHIP = "scholarship", "Scholarship"
        VOLUNTEERING = "volunteering", "Volunteering"
        LEADERSHIP = "leadership", "Leadership role"
        OTHER = "other", "Other"

    class Level(models.TextChoices):
        INSTITUTIONAL = "institutional", "Institutional"
        LOCAL = "local", "Local"
        NATIONAL = "national", "National"
        INTERNATIONAL = "international", "International"
        OTHER = "other", "Other"

    class VerificationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        MORE_INFORMATION_REQUIRED = "more_information_required", "More information required"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Public"
        MEMBERS_ONLY = "members_only", "Members only"
        PRIVATE = "private", "Private"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="achievements")
    title = models.CharField(max_length=TITLE_MAX_LENGTH)
    description = models.TextField(max_length=DESCRIPTION_MAX_LENGTH, blank=True)
    category = models.ForeignKey(
        AchievementCategory, null=True, blank=True, on_delete=models.PROTECT, related_name="achievements"
    )
    achievement_type = models.CharField(max_length=20, choices=AchievementType.choices, default=AchievementType.OTHER)
    organization = models.CharField(max_length=200, blank=True)
    event_name = models.CharField(max_length=200, blank=True)
    related_announcement = models.ForeignKey(
        "announcements.Announcement", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="achievements",
    )
    achievement_date = models.DateField()
    location = models.CharField(max_length=255, blank=True)
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.INSTITUTIONAL)
    position = models.CharField(max_length=100, blank=True)  # e.g. "1st place", "Finalist"
    # Same design as Profile.skills: a JSON list of short strings (validated), no extra tables.
    skills = models.JSONField(default=list, blank=True)
    visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.PUBLIC)

    verification_status = models.CharField(
        max_length=30, choices=VerificationStatus.choices, default=VerificationStatus.PENDING
    )
    submitted_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="achievements_verified",
    )
    rejection_reason = models.TextField(max_length=COMMENT_MAX_LENGTH, blank=True)
    is_featured = models.BooleanField(default=False)
    featured_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-achievement_date", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(verification_status__in=["pending", "verified", "rejected", "more_information_required"]),
                name="achievements_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(visibility__in=["public", "members_only", "private"]), name="achievements_visibility_valid"
            ),
            models.CheckConstraint(
                condition=Q(level__in=["institutional", "local", "national", "international", "other"]),
                name="achievements_level_valid",
            ),
            # Only verified achievements can be featured.
            models.CheckConstraint(
                condition=Q(is_featured=False) | Q(verification_status="verified"),
                name="achievements_featured_requires_verified",
            ),
            models.CheckConstraint(
                condition=~Q(verification_status="verified") | Q(verified_at__isnull=False),
                name="achievements_verified_has_timestamp",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "verification_status", "-achievement_date"], name="ach_user_status_idx"),
            models.Index(fields=["verification_status", "submitted_at"], name="ach_review_queue_idx"),
            models.Index(fields=["verification_status", "visibility", "-achievement_date"], name="ach_listing_idx"),
            models.Index(fields=["user", "is_featured"], name="ach_featured_idx"),
        ]

    def __str__(self):
        return self.title

    @property
    def is_verified(self):
        return self.verification_status == self.VerificationStatus.VERIFIED


class AchievementEvidence(UUIDPrimaryKeyModel):
    class Kind(models.TextChoices):
        IMAGE = "image", "Image"
        PDF = "pdf", "PDF"

    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE, related_name="evidence")
    file = models.FileField(upload_to=evidence_upload_to, storage=private_storage, max_length=255)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    original_name = models.CharField(max_length=150)  # sanitised, display only
    content_type = models.CharField(max_length=100)  # from the DETECTED type
    size = models.PositiveBigIntegerField()
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="achievement_evidence_uploaded"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["achievement", "created_at"], name="ach_evidence_idx")]

    def __str__(self):
        return f"Evidence {self.id} of {self.achievement_id}"


class AchievementReview(UUIDPrimaryKeyModel):
    """Append-only verification history. Never edited or deleted through the API."""

    class Decision(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        RESUBMITTED = "resubmitted", "Resubmitted with more information"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        MORE_INFORMATION_REQUIRED = "more_information_required", "More information requested"
        REVERIFICATION_REQUIRED = "reverification_required", "Changed after verification"

    class ActorRole(models.TextChoices):
        OWNER = "owner", "Owner"
        REVIEWER = "reviewer", "Reviewer"
        SYSTEM = "system", "System"

    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="achievement_reviews",
    )
    actor_role = models.CharField(max_length=10, choices=ActorRole.choices)
    previous_status = models.CharField(max_length=30, blank=True)
    new_status = models.CharField(max_length=30)
    decision = models.CharField(max_length=30, choices=Decision.choices)
    comments = models.TextField(max_length=COMMENT_MAX_LENGTH, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["achievement", "created_at"], name="ach_review_hist_idx")]

    def __str__(self):
        return f"{self.decision} on {self.achievement_id}"
