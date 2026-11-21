import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from achievements.models import Visibility  # reuse: same Public/Private choices as achievements

from .storage import get_profile_storage


def profile_picture_path(instance, filename):
    """Random, collision-free name. The user's own file name is never part of the path."""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in (".jpg", ".png", ".webp"):
        ext = ""
    return f"profiles/{instance.user_id}/{uuid.uuid4().hex}{ext}"


def cover_image_path(instance, filename):
    """Random, collision-free name for cover images (same rule as profile pictures)."""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in (".jpg", ".png", ".webp"):
        ext = ""
    return f"profiles/{instance.user_id}/covers/{uuid.uuid4().hex}{ext}"


class UserProfile(models.Model):
    """Profile + privacy settings for a user.

    Name, username, email, date of birth, phone and country stay on the existing
    ``accounts.User`` model. Only what the User model lacks lives here: the picture, the bio
    and the privacy choices. One row per user, created automatically (see signals.py).
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_profile")
    profile_picture = models.ImageField(
        upload_to=profile_picture_path, storage=get_profile_storage, max_length=255, blank=True, null=True
    )
    bio = models.CharField(max_length=500, blank=True)

    # Social-profile details (these used to live on a second model, social.Profile).
    cover_image = models.ImageField(upload_to=cover_image_path, max_length=255, blank=True, null=True)
    institution = models.CharField(max_length=150, blank=True)
    department = models.CharField(max_length=120, blank=True)
    interests = models.JSONField(default=list, blank=True)  # list[str], lower-cased
    skills = models.JSONField(default=list, blank=True)     # list[str], lower-cased

    # Privacy: everything is private unless the owner opts in (the bio is the one exception).
    profile_visibility = models.CharField(max_length=10, choices=Visibility.choices, default=Visibility.PRIVATE)
    email_visibility = models.CharField(max_length=10, choices=Visibility.choices, default=Visibility.PRIVATE)
    date_of_birth_visibility = models.CharField(max_length=10, choices=Visibility.choices, default=Visibility.PRIVATE)
    bio_visibility = models.CharField(max_length=10, choices=Visibility.choices, default=Visibility.PUBLIC)

    # Set when the user deactivates their own account. Lets reactivation tell a self-deactivated
    # account apart from one an administrator disabled (which must stay disabled).
    deactivated_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["institution"], name="profile_institution_idx"),
            models.Index(fields=["department"], name="profile_department_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(profile_visibility__in=Visibility.values), name="profile_visibility_valid"
            ),
            models.CheckConstraint(condition=Q(email_visibility__in=Visibility.values), name="profile_email_vis_valid"),
            models.CheckConstraint(
                condition=Q(date_of_birth_visibility__in=Visibility.values), name="profile_dob_vis_valid"
            ),
            models.CheckConstraint(condition=Q(bio_visibility__in=Visibility.values), name="profile_bio_vis_valid"),
        ]

    def __str__(self):
        return f"Profile<{self.user_id}>"


class PendingEmailChange(models.Model):
    """A requested e-mail change waiting for the OTP sent to the NEW address.

    The address on the User row only changes once the code is confirmed, so a typo or someone
    else's address can never lock the owner out.
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pending_email_change")
    new_email = models.EmailField()
    code_hash = models.CharField(max_length=64)  # HMAC-SHA256, never the plain code
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"EmailChange<{self.user_id}>"
