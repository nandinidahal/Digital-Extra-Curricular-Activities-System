"""
Serializers of the Achievements module.

Input is strict (unknown keys -> 400). verification_status, verified_by, is_featured, user,
submitted_at ... can never be set through these serializers: they change only through the
workflow endpoints. Evidence and review notes are returned only to the owner and reviewers.
"""
import datetime
from collections.abc import Mapping

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from announcements.models import Announcement
from common.serializers import user_card
from common.signing import make_download_token
from common.validators import (
    KIND_IMAGE,
    KIND_PDF,
    validate_plain_text,
    validate_single_line,
    validate_tag_list,
    validate_upload,
)

from .models import COMMENT_MAX_LENGTH, DESCRIPTION_MAX_LENGTH, TITLE_MAX_LENGTH, Achievement, AchievementCategory, AchievementEvidence, AchievementReview

EVIDENCE_TOKEN_KIND = "achievement_evidence"


def _wrap(validator):
    def run(value):
        try:
            validator(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))

    return run


def _text(max_length, *, line=False, required=False):
    return serializers.CharField(
        max_length=max_length, required=required, allow_blank=not required, trim_whitespace=True,
        validators=[_wrap(validate_single_line if line else validate_plain_text)],
    )


class StrictFieldsMixin:
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError({"non_field_errors": ["Expected a JSON object."]})
        writable = {name for name, field in self.fields.items() if not field.read_only}
        errors = {key: ["This field cannot be set or changed here."] for key in data.keys() if key not in writable}
        if errors:
            raise serializers.ValidationError(errors)
        return super().to_internal_value(data)


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------
class AchievementWriteSerializer(StrictFieldsMixin, serializers.Serializer):
    title = _text(TITLE_MAX_LENGTH, line=True, required=True)
    description = _text(DESCRIPTION_MAX_LENGTH)
    category = serializers.PrimaryKeyRelatedField(queryset=AchievementCategory.objects.all(), required=False, allow_null=True)
    achievement_type = serializers.ChoiceField(choices=Achievement.AchievementType.choices, required=False)
    organization = _text(200, line=True)
    event_name = _text(200, line=True)
    related_announcement = serializers.PrimaryKeyRelatedField(queryset=Announcement.objects.all(), required=False, allow_null=True)
    achievement_date = serializers.DateField(required=True)
    location = _text(255, line=True)
    level = serializers.ChoiceField(choices=Achievement.Level.choices, required=False)
    position = _text(100, line=True)
    skills = serializers.ListField(child=serializers.CharField(trim_whitespace=True), required=False, allow_empty=True)
    visibility = serializers.ChoiceField(choices=Achievement.Visibility.choices, required=False)

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError("A title is required.")
        return value

    def validate_achievement_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError("The achievement date cannot be in the future.")
        if value < datetime.date(1950, 1, 1):
            raise serializers.ValidationError("Enter a realistic date.")
        return value

    def validate_skills(self, value):
        value = [item.strip() for item in value]
        _wrap(validate_tag_list)(value)
        return value


class EvidenceUploadSerializer(serializers.Serializer):
    """multipart: one or more `files` (also accepts a single `file`)."""

    files = serializers.ListField(child=serializers.FileField(allow_empty_file=False, use_url=False), required=False)
    file = serializers.FileField(required=False, allow_empty_file=False, use_url=False)

    def validate(self, attrs):
        uploads = list(attrs.get("files") or [])
        if attrs.get("file"):
            uploads.append(attrs["file"])
        if not uploads:
            raise serializers.ValidationError({"files": ["Attach at least one file."]})
        limit = getattr(settings, "ACHIEVEMENT_MAX_EVIDENCE_FILES", 10)
        if len(uploads) > limit:
            raise serializers.ValidationError({"files": [f"At most {limit} files can be uploaded."]})
        checked = []
        for index, upload in enumerate(uploads, start=1):
            try:
                detected = validate_upload(
                    upload, allowed_kinds=(KIND_IMAGE, KIND_PDF),
                    max_image_bytes=getattr(settings, "ACHIEVEMENT_EVIDENCE_IMAGE_MAX_BYTES", 5 * 1024 * 1024),
                    max_pdf_bytes=getattr(settings, "ACHIEVEMENT_EVIDENCE_PDF_MAX_BYTES", 10 * 1024 * 1024),
                )
            except DjangoValidationError as exc:
                prefix = f"File {index}: " if len(uploads) > 1 else ""
                raise serializers.ValidationError({"files": [prefix + " ".join(exc.messages)]})
            checked.append((upload, detected))
        return {"uploads": checked}


class ReviewSerializer(StrictFieldsMixin, serializers.Serializer):
    comments = _text(COMMENT_MAX_LENGTH)


class ResubmitSerializer(StrictFieldsMixin, serializers.Serializer):
    note = _text(COMMENT_MAX_LENGTH)


class AchievementFilterSerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True, max_length=100)
    category = serializers.CharField(required=False, max_length=90)
    achievement_type = serializers.ChoiceField(choices=Achievement.AchievementType.choices, required=False)
    level = serializers.ChoiceField(choices=Achievement.Level.choices, required=False)
    visibility = serializers.ChoiceField(choices=Achievement.Visibility.choices, required=False)
    status = serializers.ChoiceField(choices=Achievement.VerificationStatus.choices, required=False)
    featured = serializers.BooleanField(required=False, allow_null=True, default=None)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    skill = serializers.CharField(required=False, max_length=40)
    ordering = serializers.ChoiceField(choices=["newest", "oldest", "submitted", "-submitted", "title"], required=False)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
class AchievementCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AchievementCategory
        fields = ("id", "name", "slug", "description", "is_active")
        read_only_fields = fields


class EvidenceSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = AchievementEvidence
        fields = ("id", "kind", "original_name", "content_type", "size", "download_url", "created_at")
        read_only_fields = fields

    def get_download_url(self, obj):
        """Short-lived signed link (works in <img>/<a> without an Authorization header)."""
        request = self.context.get("request")
        viewer = getattr(request, "user", None)
        if viewer is None or not viewer.is_authenticated:
            return None
        from django.urls import reverse

        token = make_download_token(EVIDENCE_TOKEN_KIND, obj.pk, viewer.pk)
        path = reverse("achievements:evidence-download", kwargs={"evidence_id": obj.pk}) + f"?token={token}"
        return request.build_absolute_uri(path) if request is not None else path


class ReviewHistorySerializer(serializers.ModelSerializer):
    reviewer = serializers.SerializerMethodField()

    class Meta:
        model = AchievementReview
        fields = ("id", "decision", "previous_status", "new_status", "comments", "actor_role", "reviewer", "created_at")
        read_only_fields = fields

    def get_reviewer(self, obj):
        if obj.reviewer_id is None:
            return None
        return {"id": str(obj.reviewer_id), "username": obj.reviewer.username, "full_name": obj.reviewer.full_name}


class AchievementSerializer(serializers.ModelSerializer):
    """Expects services.with_relations(). Private workflow data only for owner / reviewers."""

    user = serializers.SerializerMethodField()
    category = AchievementCategorySerializer(read_only=True)
    related_announcement = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Achievement
        fields = (
            "id", "user", "title", "description", "category", "achievement_type", "organization", "event_name",
            "related_announcement", "achievement_date", "location", "level", "position", "skills", "visibility",
            "verification_status", "is_featured", "featured_at", "verified_at", "submitted_at",
            "is_owner", "created_at", "updated_at",
        )
        read_only_fields = fields

    def _viewer(self):
        return getattr(self.context.get("request"), "user", None)

    def _private_access(self, obj):
        from .services import can_view_evidence

        return can_view_evidence(self._viewer(), obj)

    def get_user(self, obj):
        return user_card(obj.user, self._viewer(), self.context.get("request"))

    def get_related_announcement(self, obj):
        announcement = obj.related_announcement
        if announcement is None:
            return None
        from announcements.services import NotFound, check_visible
        from common.exceptions import AuthenticationRequired

        try:
            check_visible(self._viewer(), announcement)
        except (NotFound, AuthenticationRequired):
            return {"id": None, "title": None, "available": False}
        return {"id": str(announcement.pk), "title": announcement.title, "available": True}

    def get_is_owner(self, obj):
        viewer = self._viewer()
        return bool(viewer and viewer.is_authenticated and viewer.pk == obj.user_id)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if self._private_access(instance):
            data["rejection_reason"] = instance.rejection_reason or None
            data["verified_by"] = (
                {"id": str(instance.verified_by_id), "username": instance.verified_by.username}
                if instance.verified_by_id else None
            )
        else:
            data.pop("submitted_at", None)
        if self.context.get("include_evidence") and self._private_access(instance):
            data["evidence"] = EvidenceSerializer(instance.evidence.all(), many=True, context=self.context).data
        return data
