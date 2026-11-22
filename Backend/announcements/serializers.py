"""
Serializers of the Announcements module.

Input is strict: unknown keys (author, status, published_at, slug, is_edited ...) are rejected
with 400, so protected fields can never be mass-assigned. Output depends on the viewer:
organizer e-mail/phone/contact text and the online link are hidden from visitors.
"""
from collections.abc import Mapping

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from common.serializers import absolute_url, user_card
from common.validators import (
    KIND_IMAGE,
    validate_http_url,
    validate_phone,
    validate_plain_text,
    validate_single_line,
    validate_upload,
)

from .models import (
    DESCRIPTION_MAX_LENGTH,
    LONG_TEXT_MAX_LENGTH,
    REPORT_DESCRIPTION_MAX_LENGTH,
    REVIEW_COMMENT_MAX_LENGTH,
    SHORT_DESCRIPTION_MAX_LENGTH,
    TITLE_MAX_LENGTH,
    Announcement,
    AnnouncementReport,
    Category,
)


def _django_to_drf(validator):
    def run(value):
        try:
            validator(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))

    return run


plain = _django_to_drf(validate_plain_text)
single_line = _django_to_drf(validate_single_line)
http_url = _django_to_drf(validate_http_url)
phone = _django_to_drf(validate_phone)


class StrictFieldsMixin:
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError({"non_field_errors": ["Expected a JSON object."]})
        writable = {name for name, field in self.fields.items() if not field.read_only}
        errors = {key: ["This field cannot be set or changed here."] for key in data.keys() if key not in writable}
        if errors:
            raise serializers.ValidationError(errors)
        return super().to_internal_value(data)


def _text(max_length, *, line=False, required=False):
    return serializers.CharField(
        max_length=max_length, required=required, allow_blank=not required, trim_whitespace=True,
        validators=[single_line if line else plain],
    )


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "description", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")
        extra_kwargs = {"slug": {"required": False}}

    def validate_name(self, value):
        value = value.strip()
        single_line(value)
        queryset = Category.objects.filter(name__iexact=value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("A category with this name already exists.")
        return value

    def validate_description(self, value):
        plain(value)
        return value

    def validate(self, attrs):
        from django.utils.text import slugify

        if "slug" not in attrs and "name" in attrs and self.instance is None:
            attrs["slug"] = slugify(attrs["name"])[:90]
        slug = attrs.get("slug")
        if slug is not None:
            queryset = Category.objects.filter(slug=slug)
            if self.instance is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            if not slug or queryset.exists():
                raise serializers.ValidationError({"slug": ["This slug is already used or invalid."]})
        return attrs


class CategoryBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug")
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------
class AnnouncementWriteSerializer(StrictFieldsMixin, serializers.Serializer):
    """
    Create (JSON or multipart) and partial update. `status` is only accepted on CREATE and only
    as "draft" or "published"; later changes go through publish/archive/restore endpoints.
    """

    title = _text(TITLE_MAX_LENGTH, line=True)
    short_description = _text(SHORT_DESCRIPTION_MAX_LENGTH, line=True)
    description = _text(DESCRIPTION_MAX_LENGTH)
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), required=False, allow_null=True)
    activity_type = serializers.ChoiceField(choices=Announcement.ActivityType.choices, required=False)
    organizer_name = _text(150, line=True)
    organizer_email = serializers.EmailField(max_length=254, required=False, allow_blank=True)
    organizer_phone = serializers.CharField(max_length=20, required=False, allow_blank=True, validators=[phone])
    contact_information = _text(1000)
    show_contact_details = serializers.BooleanField(required=False)
    location = _text(255, line=True)
    online_link = serializers.CharField(max_length=500, required=False, allow_blank=True, validators=[http_url])
    start_datetime = serializers.DateTimeField(required=False, allow_null=True)
    end_datetime = serializers.DateTimeField(required=False, allow_null=True)
    registration_deadline = serializers.DateTimeField(required=False, allow_null=True)
    registration_link = serializers.CharField(max_length=500, required=False, allow_blank=True, validators=[http_url])
    eligibility_criteria = _text(LONG_TEXT_MAX_LENGTH)
    requirements = _text(LONG_TEXT_MAX_LENGTH)
    visibility = serializers.ChoiceField(choices=Announcement.Visibility.choices, required=False)
    cover_image = serializers.FileField(required=False, allow_empty_file=False, use_url=False)
    remove_cover_image = serializers.BooleanField(required=False)
    status = serializers.ChoiceField(choices=[("draft", "Draft"), ("published", "Published")], required=False)

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError("A title is required.")
        return value

    def validate_cover_image(self, upload):
        from django.conf import settings

        try:
            detected = validate_upload(
                upload, allowed_kinds=(KIND_IMAGE,),
                max_image_bytes=getattr(settings, "ANNOUNCEMENT_COVER_MAX_BYTES", 5 * 1024 * 1024),
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return (upload, detected)

    def validate(self, attrs):
        if self.partial:
            if "status" in attrs:
                raise serializers.ValidationError(
                    {"status": ["Use the publish, archive or restore endpoints to change the status."]}
                )
            if "title" in attrs and not attrs["title"].strip():
                raise serializers.ValidationError({"title": ["A title is required."]})
        elif not attrs.get("title", "").strip():
            raise serializers.ValidationError({"title": ["A title is required."]})
        if attrs.get("cover_image") and attrs.get("remove_cover_image"):
            raise serializers.ValidationError({"remove_cover_image": ["Send a new cover or remove it, not both."]})
        return attrs


class AnnouncementFilterSerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True, max_length=100)
    category = serializers.CharField(required=False, max_length=90)
    activity_type = serializers.ChoiceField(choices=Announcement.ActivityType.choices, required=False)
    location = serializers.CharField(required=False, max_length=100)
    organizer = serializers.CharField(required=False, max_length=100)
    start_from = serializers.DateTimeField(required=False)
    start_to = serializers.DateTimeField(required=False)
    deadline_from = serializers.DateTimeField(required=False)
    deadline_to = serializers.DateTimeField(required=False)
    published_from = serializers.DateTimeField(required=False)
    published_to = serializers.DateTimeField(required=False)
    when = serializers.ChoiceField(choices=["upcoming", "past", "ongoing"], required=False)
    registration_open = serializers.BooleanField(required=False, default=False)
    status = serializers.ChoiceField(choices=Announcement.Status.choices, required=False)
    visibility = serializers.ChoiceField(choices=Announcement.Visibility.choices, required=False)
    ordering = serializers.ChoiceField(
        choices=["newest", "oldest", "start", "-start", "deadline", "title", "updated"], required=False
    )

    def validate(self, attrs):
        if attrs.get("start_from") and attrs.get("start_to") and attrs["start_from"] > attrs["start_to"]:
            raise serializers.ValidationError({"start_to": ["Must be after start_from."]})
        return attrs


class ReportWriteSerializer(StrictFieldsMixin, serializers.Serializer):
    reason = serializers.ChoiceField(choices=AnnouncementReport.Reason.choices)
    description = _text(REPORT_DESCRIPTION_MAX_LENGTH)


class ReportReviewSerializer(StrictFieldsMixin, serializers.Serializer):
    status = serializers.ChoiceField(choices=AnnouncementReport.Status.choices)
    review_comments = _text(REVIEW_COMMENT_MAX_LENGTH)
    action = serializers.ChoiceField(choices=AnnouncementReport.Action.choices, required=False, default="none")


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
class _ViewerMixin:
    def _viewer(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    def _level(self, obj):
        from .services import access_level

        return access_level(self._viewer(), obj)


class AnnouncementCardSerializer(_ViewerMixin, serializers.ModelSerializer):
    """Listing card. Expects services.with_relations() (author, profile, category, is_bookmarked)."""

    category = CategoryBriefSerializer(read_only=True)
    author = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()
    is_bookmarked = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = (
            "id", "title", "slug", "short_description", "category", "activity_type", "organizer_name",
            "location", "start_datetime", "end_datetime", "registration_deadline", "cover_image",
            "status", "visibility", "author", "is_bookmarked", "is_owner", "is_edited",
            "published_at", "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_author(self, obj):
        return user_card(obj.author, self._viewer(), self.context.get("request"))

    def get_cover_image(self, obj):
        return absolute_url(obj.cover_image, self.context.get("request"))

    def get_is_bookmarked(self, obj):
        return bool(getattr(obj, "is_bookmarked", False))

    def get_is_owner(self, obj):
        viewer = self._viewer()
        return bool(viewer and viewer.is_authenticated and obj.author_id == viewer.pk)


class AnnouncementDetailSerializer(AnnouncementCardSerializer):
    organizer_email = serializers.SerializerMethodField()
    organizer_phone = serializers.SerializerMethodField()
    contact_information = serializers.SerializerMethodField()
    online_link = serializers.SerializerMethodField()
    contact_details_hidden = serializers.SerializerMethodField()

    class Meta(AnnouncementCardSerializer.Meta):
        fields = AnnouncementCardSerializer.Meta.fields + (
            "description", "organizer_email", "organizer_phone", "contact_information",
            "contact_details_hidden", "show_contact_details", "online_link", "registration_link",
            "eligibility_criteria", "requirements", "archived_at",
        )
        read_only_fields = fields

    def _may_see_contact(self, obj):
        level = self._level(obj)
        return level in ("owner", "moderator") or (level == "member" and obj.show_contact_details)

    def get_organizer_email(self, obj):
        return obj.organizer_email if self._may_see_contact(obj) else None

    def get_organizer_phone(self, obj):
        return obj.organizer_phone if self._may_see_contact(obj) else None

    def get_contact_information(self, obj):
        return obj.contact_information if self._may_see_contact(obj) else None

    def get_contact_details_hidden(self, obj):
        has_any = bool(obj.organizer_email or obj.organizer_phone or obj.contact_information)
        return has_any and not self._may_see_contact(obj)

    def get_online_link(self, obj):
        # Meeting links are for members only: a visitor sees that one exists, not the link.
        if not obj.online_link:
            return None
        return obj.online_link if self._level(obj) != "visitor" else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        level = self._level(instance)
        if level not in ("owner", "moderator"):
            data.pop("show_contact_details", None)
            data.pop("archived_at", None)
        data["requires_login_for_online_link"] = level == "visitor" and bool(instance.online_link)
        return data


class BookmarkSerializer(serializers.Serializer):
    """`context["visible_ids"]`: announcement ids the viewer may still see."""

    id = serializers.UUIDField(read_only=True)
    announcement_id = serializers.UUIDField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        cards = self.context.get("cards", {})
        card = cards.get(instance.announcement_id)
        data["available"] = card is not None
        data["announcement"] = card
        return data


class ReportReceiptSerializer(serializers.ModelSerializer):
    announcement_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = AnnouncementReport
        fields = ("id", "announcement_id", "reason", "status", "created_at")
        read_only_fields = fields


class ReportModerationSerializer(serializers.ModelSerializer):
    announcement = serializers.SerializerMethodField()
    reporter = serializers.SerializerMethodField()
    reviewed_by = serializers.SerializerMethodField()

    class Meta:
        model = AnnouncementReport
        fields = (
            "id", "announcement", "reporter", "reason", "description", "status", "action_taken",
            "reviewed_by", "review_comments", "reviewed_at", "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_announcement(self, obj):
        a = obj.announcement
        return {"id": str(a.pk), "title": a.title, "status": a.status, "visibility": a.visibility, "author_id": str(a.author_id)}

    def get_reporter(self, obj):
        return {"id": str(obj.reporter_id), "username": obj.reporter.username}

    def get_reviewed_by(self, obj):
        return {"id": str(obj.reviewed_by_id), "username": obj.reviewed_by.username} if obj.reviewed_by_id else None
