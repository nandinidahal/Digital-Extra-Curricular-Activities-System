from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower

from .validators import phone_validator, validate_date_of_birth


class Role(models.TextChoices):
    USER = "user", "User"
    COORDINATOR = "coordinator", "Coordinator"
    ADMIN = "admin", "Administrator"


class User(AbstractUser):
    email = models.EmailField("email address", unique=True)
    full_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=16, validators=[phone_validator])
    country = models.CharField(max_length=80)
    date_of_birth = models.DateField(validators=[validate_date_of_birth], null=True, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.USER)
    is_email_verified = models.BooleanField(default=False)
    # Bumped on password reset; JWTs carrying an older value are rejected.
    token_version = models.PositiveIntegerField(default=0)

    REQUIRED_FIELDS = ["email"]

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="uniq_user_email_ci"),
            models.UniqueConstraint(Lower("username"), name="uniq_user_username_ci"),
        ]

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        if self.is_superuser:
            self.role = Role.ADMIN
            self.is_email_verified = True
        super().save(*args, **kwargs)

    @property
    def is_coordinator(self):
        return self.role in (Role.COORDINATOR, Role.ADMIN)

    @property
    def is_platform_admin(self):
        return self.role == Role.ADMIN

    def __str__(self):
        return self.username


class OTPPurpose(models.TextChoices):
    EMAIL_VERIFICATION = "verify_email", "Email verification"
    PASSWORD_RESET = "password_reset", "Password reset"


class EmailOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="otps")
    purpose = models.CharField(max_length=20, choices=OTPPurpose.choices)
    code_hash = models.CharField(max_length=64)  # HMAC-SHA256, never the plain OTP
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)
    # Password reset only: single-use authorization issued after the OTP is verified.
    reset_token_hash = models.CharField(max_length=64, blank=True, default="")
    reset_token_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "purpose", "-created_at"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_id}:{self.purpose}:{self.created_at:%Y-%m-%d %H:%M}"
