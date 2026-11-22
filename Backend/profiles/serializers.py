"""
Serializers for the Profiles API.

* `ProfileUpdateSerializer`  - input for PATCH /me/ (strict: unknown or protected keys -> 400)
* `PrivacySerializer`        - input for PATCH /me/privacy/
* `OwnProfileSerializer`     - output for the owner (everything, plus privacy and completion)
* `ProfileViewSerializer`    - output for everybody else; hidden fields are REMOVED here,
                               on the server, never left to the frontend.

Every output serializer lists its fields explicitly, so a field added to the model
later is never exposed by accident.
"""
from collections.abc import Mapping

from rest_framework import serializers

from . import services, validators
from .models import Profile
from .permissions import ADMIN

PRIVACY_FIELDS = (
    "profile_visibility",
    "show_institution",
    "show_education",
    "show_interests",
    "show_skills",
    "show_location",
    "show_social_links",
)

# output field -> privacy flag that must be True for others to see it
FIELD_VISIBILITY = {
    "institution": "show_institution",
    "education_level": "show_education",
    "field_of_study": "show_education",
    "interests": "show_interests",
    "skills": "show_skills",
    "location": "show_location",
    "website": "show_social_links",
    "linkedin_url": "show_social_links",
    "github_url": "show_social_links",
    "portfolio_url": "show_social_links",
}


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------
class StrictFieldsMixin:
    """
    Reject any key that is not a writable field of this serializer. DRF would
    silently ignore unknown keys; here a client sending `role`, `email`, `user`
    or `profile_picture` gets a clear 400 instead of a false "success".
    """

    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError({"non_field_errors": ["Expected a JSON object."]})
        writable = {name for name, field in self.fields.items() if not field.read_only}
        errors = {}
        for key in data.keys():
            if key not in writable:
                errors[key] = ["This field cannot be set or changed here."]
        if errors:
            raise serializers.ValidationError(errors)
        return super().to_internal_value(data)


class TagListField(serializers.ListField):
    """List of short strings: trimmed, case-insensitively de-duplicated, order kept."""

    def __init__(self, **kwargs):
        kwargs.setdefault("child", serializers.CharField(max_length=40, trim_whitespace=True))
        kwargs.setdefault("allow_empty", True)
        kwargs.setdefault("required", False)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if isinstance(data, str):  # a bare string would be split into characters
            self.fail("not_a_list", input_type="str")
        items = super().to_internal_value(data)
        seen, unique = set(), []
        for item in items:
            key = item.casefold()
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique


def _text(max_length, *, validator=validators.validate_single_line):
    return serializers.CharField(
        max_length=max_length, required=False, allow_blank=True, validators=[validator]
    )


def _link(*extra_validators):
    return serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=True,
        validators=[validators.validate_web_url, *extra_validators],
    )


class ProfileUpdateSerializer(StrictFieldsMixin, serializers.Serializer):
    headline = _text(120)
    bio = _text(500, validator=validators.validate_multiline)
    institution = _text(150)
    education_level = serializers.ChoiceField(
        choices=Profile.EducationLevel.choices, required=False, allow_blank=True
    )
    field_of_study = _text(150)
    interests = TagListField(max_length=20)
    skills = TagListField(max_length=30)
    location = _text(100)
    website = _link()
    linkedin_url = _link(validators.validate_linkedin_url)
    github_url = _link(validators.validate_github_url)
    portfolio_url = _link()


class PrivacySerializer(StrictFieldsMixin, serializers.Serializer):
    profile_visibility = serializers.ChoiceField(choices=Profile.Visibility.choices, required=False)
    show_institution = serializers.BooleanField(required=False)
    show_education = serializers.BooleanField(required=False)
    show_interests = serializers.BooleanField(required=False)
    show_skills = serializers.BooleanField(required=False)
    show_location = serializers.BooleanField(required=False)
    show_social_links = serializers.BooleanField(required=False)


class ImageUploadSerializer(serializers.Serializer):
    """multipart/form-data with a single file field named `image`."""

    image = serializers.FileField(allow_empty_file=False, use_url=False)

    def validate(self, attrs):
        field_name = self.context["field_name"]
        attrs["image_format"] = services.validate_upload(attrs["image"], field_name)
        return attrs


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
class _ProfileOutputBase(serializers.ModelSerializer):
    user_id = serializers.UUIDField(read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    profile_picture = serializers.SerializerMethodField()
    cover_photo = serializers.SerializerMethodField()

    def _absolute_url(self, file_field):
        if not file_field:
            return None
        try:
            url = file_field.url
        except ValueError:
            return None
        request = self.context.get("request")
        if request is not None and url.startswith("/"):
            return request.build_absolute_uri(url)  # S3/CDN storages already return full URLs
        return url

    def get_profile_picture(self, obj):
        return self._absolute_url(obj.profile_picture)

    def get_cover_photo(self, obj):
        return self._absolute_url(obj.cover_photo)


class OwnProfileSerializer(_ProfileOutputBase):
    privacy = serializers.SerializerMethodField()
    profile_completion = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = (
            "id", "user_id", "username", "full_name",
            "profile_picture", "cover_photo",
            "headline", "bio", "institution", "education_level", "field_of_study",
            "interests", "skills", "location",
            "website", "linkedin_url", "github_url", "portfolio_url",
            "privacy", "profile_completion", "is_owner",
            "date_created", "updated_at",
        )
        read_only_fields = fields

    def get_privacy(self, obj):
        return {name: getattr(obj, name) for name in PRIVACY_FIELDS}

    def get_profile_completion(self, obj):
        return services.calculate_completion(obj)

    def get_is_owner(self, obj):
        return True


class ProfileViewSerializer(_ProfileOutputBase):
    """
    What other people see. Context key `access` is the viewer level from
    permissions.py; admins see every content field, everybody else only what
    the owner allowed.
    """

    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = (
            "user_id", "username", "full_name",
            "profile_picture", "cover_photo",
            "headline", "bio", "institution", "education_level", "field_of_study",
            "interests", "skills", "location",
            "website", "linkedin_url", "github_url", "portfolio_url",
            "is_owner", "date_created",
        )
        read_only_fields = fields

    def get_is_owner(self, obj):
        return False

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if self.context.get("access") == ADMIN:
            return data
        for field_name, flag in FIELD_VISIBILITY.items():
            if not getattr(instance, flag):
                data.pop(field_name, None)
        return data
