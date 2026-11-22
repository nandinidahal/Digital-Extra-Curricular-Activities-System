"""
Serializers: input validation and output shaping for the accounts API.

`RejectProtectedFieldsMixin` blocks mass-assignment: if a client sends a field
such as `role` or `is_email_verified`, the request fails with a clear 400
instead of the field being silently accepted or ignored.
"""
import re

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken

from . import services
from .models import User
from .validators import (
    normalize_phone_number,
    validate_date_of_birth,
    validate_phone_number,
    validate_username,
)

OTP_REGEX = re.compile(r"^\d{6}$")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
class RejectProtectedFieldsMixin:
    protected_fields = (
        "id",
        "role",
        "is_staff",
        "is_superuser",
        "is_active",
        "is_email_verified",
        "date_joined",
        "created_at",
        "last_login",
        "updated_at",
        "groups",
        "user_permissions",
    )

    def to_internal_value(self, data):
        if hasattr(data, "keys"):
            blocked = {
                name: ["This field cannot be set or changed."]
                for name in self.protected_fields
                if name in data
            }
            if blocked:
                raise serializers.ValidationError(blocked)
        return super().to_internal_value(data)


def run_password_validators(password, user, field_name="password"):
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({field_name: list(exc.messages)})


def _clean_email(value):
    return services.normalize_email(value)


class NormalizedEmailField(serializers.EmailField):
    """Email field that trims and lower-cases its value."""

    def to_internal_value(self, data):
        return _clean_email(super().to_internal_value(data))


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
class UserSerializer(serializers.ModelSerializer):
    """What the frontend receives about an account. Never contains secrets."""

    created_at = serializers.DateTimeField(source="date_joined", read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "full_name",
            "email",
            "phone_number",
            "country",
            "date_of_birth",
            "role",
            "is_email_verified",
            "created_at",
        )
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
class RegisterSerializer(RejectProtectedFieldsMixin, serializers.Serializer):
    full_name = serializers.CharField(min_length=2, max_length=150)
    username = serializers.CharField(max_length=30, validators=[validate_username])
    email = NormalizedEmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    confirm_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    date_of_birth = serializers.DateField(validators=[validate_date_of_birth])
    phone_number = serializers.CharField(max_length=25)
    country = serializers.CharField(max_length=100)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return value

    def validate_phone_number(self, value):
        value = normalize_phone_number(value)
        try:
            validate_phone_number(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": ["Passwords do not match."]}
            )
        candidate = User(
            username=attrs["username"], email=attrs["email"], full_name=attrs["full_name"]
        )
        run_password_validators(attrs["password"], candidate)
        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password")
        try:
            return services.register_user(**validated_data)
        except IntegrityError:
            # Two people registering the same username/email at the same instant.
            raise serializers.ValidationError(
                {"non_field_errors": ["An account with these details already exists."]}
            )


# ---------------------------------------------------------------------------
# OTP / email flows
# ---------------------------------------------------------------------------
class EmailSerializer(serializers.Serializer):
    email = NormalizedEmailField(max_length=254)


class OTPVerifySerializer(serializers.Serializer):
    email = NormalizedEmailField(max_length=254)
    otp = serializers.CharField(trim_whitespace=True)

    def validate_otp(self, value):
        if not OTP_REGEX.match(value):
            raise serializers.ValidationError("Enter the 6-digit code.")
        return value


# ---------------------------------------------------------------------------
# Login / tokens
# ---------------------------------------------------------------------------
class LoginSerializer(serializers.Serializer):
    email = NormalizedEmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


# ---------------------------------------------------------------------------
# Password reset / change
# ---------------------------------------------------------------------------
class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    confirm_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": ["Passwords do not match."]}
            )
        # Raises InvalidResetToken (generic message) for bad/expired/used tokens.
        token = services.get_valid_reset_token(attrs["token"])
        run_password_validators(attrs["new_password"], token.user, "new_password")
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    confirm_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        user = self.context["request"].user
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": ["Passwords do not match."]}
            )
        if attrs["new_password"] == attrs["current_password"]:
            raise serializers.ValidationError(
                {"new_password": ["New password must be different from the current password."]}
            )
        run_password_validators(attrs["new_password"], user, "new_password")
        return attrs


# ---------------------------------------------------------------------------
# Account update (PATCH /me/)
# ---------------------------------------------------------------------------
class UpdateAccountSerializer(RejectProtectedFieldsMixin, serializers.Serializer):
    """Only these basic fields can be edited. Role and security fields never can."""

    protected_fields = RejectProtectedFieldsMixin.protected_fields + (
        "password",
        "confirm_password",
    )

    full_name = serializers.CharField(min_length=2, max_length=150)
    username = serializers.CharField(max_length=30, validators=[validate_username])
    email = NormalizedEmailField(max_length=254)
    phone_number = serializers.CharField(max_length=25)
    country = serializers.CharField(max_length=100)
    date_of_birth = serializers.DateField(validators=[validate_date_of_birth])
    # Needed only when the email address changes (protects against session hijacking).
    current_password = serializers.CharField(
        write_only=True, required=False, trim_whitespace=False, max_length=128
    )

    def validate_username(self, value):
        user = self.context["request"].user
        if User.objects.filter(username__iexact=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def validate_email(self, value):
        user = self.context["request"].user
        if User.objects.filter(email=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return value

    def validate_phone_number(self, value):
        value = normalize_phone_number(value)
        try:
            validate_phone_number(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def validate(self, attrs):
        user = self.context["request"].user
        new_email = attrs.get("email")
        if new_email is not None and new_email != user.email:
            password = attrs.get("current_password")
            if not password:
                raise serializers.ValidationError(
                    {"current_password": ["Enter your current password to change your email."]}
                )
            if not user.check_password(password):
                raise serializers.ValidationError(
                    {"current_password": ["Current password is incorrect."]}
                )
        return attrs


# ---------------------------------------------------------------------------
# Token refresh (extends Simple JWT with an "account still active" check)
# ---------------------------------------------------------------------------


class AccountTokenRefreshSerializer(TokenRefreshSerializer):
    """
    Rejects refresh tokens of deleted or deactivated users. Expired, invalid and
    blacklisted tokens are rejected by Simple JWT itself.
    """

    def validate(self, attrs):
        try:
            token = RefreshToken(attrs["refresh"])  # checks signature, expiry, blacklist
        except TokenError as exc:
            raise InvalidToken(exc.args[0])

        try:
            user_exists = User.objects.filter(
                pk=token.get(jwt_settings.USER_ID_CLAIM), is_active=True
            ).exists()
        except (ValueError, DjangoValidationError):
            user_exists = False
        if not user_exists:
            raise InvalidToken("Token is invalid or expired")
        return super().validate(attrs)
