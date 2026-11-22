import os
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from . import validators

_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _image_path(instance, filename, folder):
    """
    profiles/<user uuid>/<folder>/<random uuid>.<ext>

    The client-supplied file name is never used, so there is no path traversal
    and no name collision. The extension is only kept when it is an image one.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        ext = ".jpg"
    return f"profiles/{instance.user_id}/{folder}/{uuid.uuid4().hex}{ext}"


def profile_picture_upload_to(instance, filename):
    return _image_path(instance, filename, "pictures")


def cover_photo_upload_to(instance, filename):
    return _image_path(instance, filename, "covers")


class Profile(models.Model):
    """
    Extra information about a user. Account data (username, e-mail, full name,
    role, password...) stays in `accounts.User` and is never copied here.
    """

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Public"
        MEMBERS_ONLY = "members_only", "Members only"
        PRIVATE = "private", "Private"

    class EducationLevel(models.TextChoices):
        HIGH_SCHOOL = "high_school", "High school"
        DIPLOMA = "diploma", "Diploma / college"
        UNDERGRADUATE = "undergraduate", "Undergraduate"
        POSTGRADUATE = "postgraduate", "Postgraduate"
        DOCTORATE = "doctorate", "Doctorate"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )

    # --- images (files live in media storage; only the path is in the database)
    profile_picture = models.ImageField(
        upload_to=profile_picture_upload_to, max_length=255, blank=True
    )
    cover_photo = models.ImageField(upload_to=cover_photo_upload_to, max_length=255, blank=True)

    # --- about
    headline = models.CharField(max_length=120, blank=True, validators=[validators.validate_single_line])
    bio = models.CharField(max_length=500, blank=True, validators=[validators.validate_multiline])
    institution = models.CharField(max_length=150, blank=True, validators=[validators.validate_single_line])
    education_level = models.CharField(max_length=20, choices=EducationLevel.choices, blank=True)
    field_of_study = models.CharField(max_length=150, blank=True, validators=[validators.validate_single_line])
    # JSON lists of short strings (see README for why JSONField).
    interests = models.JSONField(default=list, blank=True, validators=[validators.validate_tag_list])
    skills = models.JSONField(default=list, blank=True, validators=[validators.validate_tag_list])
    location = models.CharField(max_length=100, blank=True, validators=[validators.validate_single_line])

    # --- links
    website = models.URLField(max_length=200, blank=True, validators=[validators.validate_web_url])
    linkedin_url = models.URLField(max_length=200, blank=True, validators=[validators.validate_linkedin_url])
    github_url = models.URLField(max_length=200, blank=True, validators=[validators.validate_github_url])
    portfolio_url = models.URLField(max_length=200, blank=True, validators=[validators.validate_web_url])

    # --- privacy
    profile_visibility = models.CharField(
        max_length=20, choices=Visibility.choices, default=Visibility.PUBLIC
    )
    show_institution = models.BooleanField(default=True)
    show_education = models.BooleanField(default=True)
    show_interests = models.BooleanField(default=True)
    show_skills = models.BooleanField(default=True)
    show_location = models.BooleanField(default=True)
    show_social_links = models.BooleanField(default=True)

    date_created = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(profile_visibility__in=["public", "members_only", "private"]),
                name="profiles_profile_visibility_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    education_level__in=[
                        "", "high_school", "diploma", "undergraduate",
                        "postgraduate", "doctorate", "other",
                    ]
                ),
                name="profiles_profile_education_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["profile_visibility"], name="profiles_visibility_idx"),
            models.Index(fields=["institution"], name="profiles_institution_idx"),
            models.Index(fields=["field_of_study"], name="profiles_field_study_idx"),
        ]

    def __str__(self):
        return f"Profile of {self.user_id}"
