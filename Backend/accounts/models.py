import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from .managers import UserManager
from .validators import validate_date_of_birth, validate_phone_number, validate_username


class User(AbstractUser):
    """
    The project-wide user model. Other apps should reference it with
    `settings.AUTH_USER_MODEL` (never import this class in a ForeignKey).
    """

    class Role(models.TextChoices):
        USER = "user", "User"
        COORDINATOR = "coordinator", "Coordinator"
        ADMIN = "admin", "Admin"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # We use a single `full_name` instead of Django's first/last name.
    first_name = None
    last_name = None

    username = models.CharField(
        max_length=30,
        unique=True,
        validators=[validate_username],
        error_messages={"unique": "A user with that username already exists."},
    )
    # Uniqueness is enforced case-insensitively by a database constraint (see Meta).
    email = models.EmailField(max_length=254)
    full_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=20, blank=True, validators=[validate_phone_number])
    country = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField(null=True, blank=True, validators=[validate_date_of_birth])
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.USER)
    is_email_verified = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    REQUIRED_FIELDS = ["email", "full_name"]

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique"),
            models.UniqueConstraint(Lower("username"), name="accounts_user_username_ci_unique"),
            models.CheckConstraint(
                condition=Q(role__in=["user", "coordinator", "admin"]),
                name="accounts_user_role_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["role"], name="accounts_user_role_idx"),
        ]

    def save(self, *args, **kwargs):
        self.email = UserManager.normalize_email(self.email)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.username

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN

    @property
    def is_coordinator_role(self):
        return self.role == self.Role.COORDINATOR


class OneTimePassword(models.Model):
    """
    A six-digit OTP. Only an HMAC of the code is stored, never the code itself.
    Each OTP is tied to a user, a purpose and the email address it was sent to,
    so a code for one purpose can never be used for another.
    """

    class Purpose(models.TextChoices):
        EMAIL_VERIFICATION = "email_verification", "Email verification"
        PASSWORD_RESET = "password_reset", "Password reset"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="otps"
    )
    purpose = models.CharField(max_length=30, choices=Purpose.choices)
    email = models.EmailField(max_length=254)  # address the code was sent to
    otp_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "purpose", "is_used"], name="accounts_otp_lookup_idx"),
            models.Index(fields=["user", "purpose", "created_at"], name="accounts_otp_created_idx"),
        ]

    def __str__(self):
        return f"{self.purpose} OTP for {self.user_id}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def attempts_exhausted(self):
        return self.attempts >= self.max_attempts


class PasswordResetToken(models.Model):
    """Short-lived, single-use token issued after a password-reset OTP is verified."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="password_reset_tokens"
    )
    token_hash = models.CharField(max_length=64, unique=True)  # SHA-256 of the raw token
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Password reset token for {self.user_id}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at
