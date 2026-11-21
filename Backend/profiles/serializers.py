from django.contrib.auth import get_user_model
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers

from accounts.validators import phone_validator, validate_date_of_birth
from achievements.models import Visibility

from .models import UserProfile
from .validators import process_profile_picture

User = get_user_model()


def picture_url(profile, request):
    if not profile.profile_picture:
        return None
    try:
        url = profile.profile_picture.url
    except ValueError:
        return None
    return request.build_absolute_uri(url) if request is not None else url


# --------------------------------------------------------------------------- read side
class PrivacySettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ("profile_visibility", "email_visibility", "date_of_birth_visibility", "bio_visibility")
        read_only_fields = fields


class OwnerProfileSerializer(serializers.ModelSerializer):
    """The complete profile, for its owner only. Passwords, hashes and token data never appear."""

    id = serializers.IntegerField(source="user_id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    phone_number = serializers.CharField(source="user.phone_number", read_only=True)
    country = serializers.CharField(source="user.country", read_only=True)
    date_of_birth = serializers.DateField(source="user.date_of_birth", read_only=True)
    role = serializers.CharField(source="user.role", read_only=True)
    is_email_verified = serializers.BooleanField(source="user.is_email_verified", read_only=True)
    account_created_at = serializers.DateTimeField(source="user.date_joined", read_only=True)
    account_status = serializers.SerializerMethodField()
    profile_picture_url = serializers.SerializerMethodField()
    privacy = PrivacySettingsSerializer(source="*", read_only=True)

    class Meta:
        model = UserProfile
        fields = (
            "id", "username", "full_name", "email", "phone_number", "country", "date_of_birth", "bio",
            "profile_picture_url", "role", "is_email_verified", "account_status", "account_created_at", "privacy",
        )
        read_only_fields = fields

    def get_account_status(self, obj):
        return "active" if obj.user.is_active else "deactivated"

    def get_profile_picture_url(self, obj):
        return picture_url(obj, self.context.get("request"))


class PublicProfileSerializer(serializers.ModelSerializer):
    """What other authenticated users see. Optional fields appear only if the owner allows it.

    Only whitelisted fields are ever written to the output; phone number, country, role and
    verification status are never part of it.
    """

    id = serializers.IntegerField(source="user_id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    member_since = serializers.DateTimeField(source="user.date_joined", read_only=True)
    profile_picture_url = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = ("id", "username", "full_name", "profile_picture_url", "member_since")
        read_only_fields = fields

    def get_profile_picture_url(self, obj):
        return picture_url(obj, self.context.get("request"))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.bio_visibility == Visibility.PUBLIC:
            data["bio"] = instance.bio
        if instance.email_visibility == Visibility.PUBLIC:
            data["email"] = instance.user.email
        if instance.date_of_birth_visibility == Visibility.PUBLIC:
            dob = instance.user.date_of_birth
            data["date_of_birth"] = dob.isoformat() if dob else None
        return data


class AccountSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    is_email_verified = serializers.BooleanField(source="user.is_email_verified", read_only=True)
    role = serializers.CharField(source="user.role", read_only=True)
    account_status = serializers.SerializerMethodField()
    account_created_at = serializers.DateTimeField(source="user.date_joined", read_only=True)
    last_login = serializers.DateTimeField(source="user.last_login", read_only=True)
    pending_email = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = ("username", "email", "is_email_verified", "role", "account_status", "account_created_at",
                  "last_login", "pending_email")
        read_only_fields = fields

    def get_account_status(self, obj):
        return "active" if obj.user.is_active else "deactivated"

    def get_pending_email(self, obj):
        pending = getattr(obj.user, "pending_email_change", None)
        if pending and pending.expires_at > timezone.now():
            return pending.new_email
        return None


# --------------------------------------------------------------------------- write side
class ProfileUpdateSerializer(serializers.Serializer):
    """PUT: full_name and username are required. PATCH: send only what changes.

    The account is always the authenticated user's; there is no user id in the payload.
    The email address is NOT editable here: it changes through the verified flow
    (/me/email/change/ + /me/email/confirm/).
    """

    full_name = serializers.CharField(max_length=150)
    username = serializers.CharField(max_length=150, validators=[UnicodeUsernameValidator()])
    date_of_birth = serializers.DateField(required=False, validators=[validate_date_of_birth])
    bio = serializers.CharField(required=False, allow_blank=True, max_length=500)
    phone_number = serializers.CharField(required=False, validators=[phone_validator])
    country = serializers.CharField(required=False, max_length=80)

    def validate_username(self, value):
        qs = User.objects.filter(username__iexact=value).exclude(pk=self.instance.user_id)
        if qs.exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate(self, attrs):
        submitted = self.initial_data.get("email") if hasattr(self.initial_data, "get") else None
        if submitted is not None and str(submitted).strip().lower() != self.instance.user.email.lower():
            raise serializers.ValidationError({
                "email": ["Email cannot be changed here. Use POST /api/profile/me/email/change/ "
                          "so the new address can be verified."]
            })
        return attrs

    def update(self, profile, validated_data):
        user = profile.user
        user_fields = [f for f in ("full_name", "username", "date_of_birth", "phone_number", "country")
                       if f in validated_data]
        try:
            with transaction.atomic():
                for f in user_fields:
                    setattr(user, f, validated_data[f])
                if user_fields:
                    user.save(update_fields=user_fields)
                if "bio" in validated_data:
                    profile.bio = validated_data["bio"]
                    profile.save(update_fields=["bio", "updated_at"])
        except IntegrityError:  # lost a race against another user taking the same username
            raise serializers.ValidationError({"username": ["This username is already taken."]})
        return profile


class PrivacySettingsUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ("profile_visibility", "email_visibility", "date_of_birth_visibility", "bio_visibility")

    def to_internal_value(self, data):
        unknown = sorted(set(data) - set(self.fields))
        if unknown:
            raise serializers.ValidationError({k: ["Unknown setting."] for k in unknown})
        if not data:
            raise serializers.ValidationError({"detail": ["Provide at least one setting to change."]})
        return super().to_internal_value(data)


class ProfilePictureUploadSerializer(serializers.Serializer):
    profile_picture = serializers.FileField(allow_empty_file=False)

    def validate_profile_picture(self, upload):
        from django.core.exceptions import ValidationError as DjangoValidationError

        try:
            return process_profile_picture(upload)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))


class EmailChangeRequestSerializer(serializers.Serializer):
    new_email = serializers.EmailField()
    current_password = serializers.CharField(write_only=True, style={"input_type": "password"})


class EmailChangeConfirmSerializer(serializers.Serializer):
    otp = serializers.RegexField(r"^\d{6}$", error_messages={"invalid": "OTP must be exactly 6 digits."})


class DeactivateAccountSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    confirm = serializers.BooleanField()

    def validate_confirm(self, value):
        if value is not True:
            raise serializers.ValidationError("You must confirm that you want to deactivate your account.")
        return value


class ReactivateSerializer(serializers.Serializer):
    identifier = serializers.CharField(help_text="Email or username")
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
