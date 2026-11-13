from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import transaction
from rest_framework import serializers

from .models import OTPPurpose
from .services import issue_otp
from .validators import phone_validator, validate_date_of_birth

User = get_user_model()

OTP_FIELD = serializers.RegexField(r"^\d{6}$", error_messages={"invalid": "OTP must be exactly 6 digits."})


class UserSerializer(serializers.ModelSerializer):
    """Public/own profile. Never exposes password, OTPs or token data."""

    class Meta:
        model = User
        fields = ("id", "full_name", "username", "email", "phone_number", "country",
                  "date_of_birth", "role", "is_email_verified", "date_joined")
        read_only_fields = fields


class RegisterSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    username = serializers.CharField(max_length=150, validators=[UnicodeUsernameValidator()])
    email = serializers.EmailField()
    phone_number = serializers.CharField(validators=[phone_validator])
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    confirm_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    country = serializers.CharField(max_length=80)
    date_of_birth = serializers.DateField(validators=[validate_date_of_birth])

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "An account with this email already exists. If you have not verified it, request a new code."
            )
        return value

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": ["Passwords do not match."]})
        probe = User(username=attrs["username"], email=attrs["email"], full_name=attrs["full_name"])
        try:
            validate_password(attrs["password"], user=probe)
        except Exception as exc:
            raise serializers.ValidationError({"password": list(getattr(exc, "messages", [str(exc)]))})
        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password")
        password = validated_data.pop("password")
        with transaction.atomic():  # user is rolled back if the OTP email cannot be sent
            user = User(**validated_data, is_active=False, is_email_verified=False)
            user.set_password(password)  # Django's PBKDF2 hasher
            user.save()
            issue_otp(user, OTPPurpose.EMAIL_VERIFICATION)
        return user


class VerifyEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = OTP_FIELD


class EmailOnlySerializer(serializers.Serializer):
    email = serializers.EmailField()


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(help_text="Email or username")
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class VerifyResetOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = OTP_FIELD


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    reset_token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    confirm_password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": ["Passwords do not match."]})
        return attrs

class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"}
    )

    new_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"}
    )

    confirm_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"}
    )

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({
                "confirm_password": ["Passwords do not match."]
            })

        return attrs