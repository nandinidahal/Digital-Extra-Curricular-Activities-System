"""
Serializers of the Social module.

Input serializers are strict: unknown keys (author, author_id, user, is_deleted,
like_count ...) are rejected with a 400 instead of being silently ignored, so a
client can never believe it changed ownership or a counter.
Output serializers list every field explicitly.
"""
from collections.abc import Mapping

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from common.relationships import hidden_user_ids
from common.serializers import user_card

from .models import (
    COMMENT_MAX_LENGTH,
    POST_MAX_LENGTH,
    REPORT_DESCRIPTION_MAX_LENGTH,
    SHARE_CAPTION_MAX_LENGTH,
    Comment,
    ContentReport,
    Post,
    PostMedia,
    PostShare,
)
from .validators import max_images_per_post, validate_post_image, validate_social_text


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------
class StrictFieldsMixin:
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError({"non_field_errors": ["Expected a JSON object."]})
        writable = {name for name, field in self.fields.items() if not field.read_only}
        errors = {key: ["This field cannot be set or changed here."] for key in data.keys() if key not in writable}
        if errors:
            raise serializers.ValidationError(errors)
        return super().to_internal_value(data)


def _text_field(max_length, *, required=True, allow_blank=False):
    return serializers.CharField(
        max_length=max_length,
        required=required,
        allow_blank=allow_blank,
        trim_whitespace=True,
        validators=[validate_social_text],
    )


class PostWriteSerializer(StrictFieldsMixin, serializers.Serializer):
    """Create (JSON or multipart) and edit (partial) a post. New images go in the `images` field."""

    content = _text_field(POST_MAX_LENGTH, required=False, allow_blank=True)
    post_type = serializers.ChoiceField(choices=Post.PostType.choices, required=False)
    visibility = serializers.ChoiceField(choices=Post.Visibility.choices, required=False)
    images = serializers.ListField(
        child=serializers.FileField(allow_empty_file=False, use_url=False),
        required=False,
        allow_empty=True,
    )

    def validate_images(self, files):
        limit = max_images_per_post()
        if len(files) > limit:
            raise serializers.ValidationError(f"A post can have at most {limit} images.")
        checked = []
        for index, upload in enumerate(files, start=1):
            try:
                image_format = validate_post_image(upload)
            except DjangoValidationError as exc:
                prefix = f"Image {index}: " if len(files) > 1 else ""
                raise serializers.ValidationError(prefix + " ".join(exc.messages))
            checked.append((upload, image_format))
        return checked

    def validate(self, attrs):
        if not self.partial and not attrs.get("content", "").strip() and not attrs.get("images"):
            raise serializers.ValidationError(
                {"content": ["A post needs text or at least one image."]}
            )
        return attrs


class CommentWriteSerializer(StrictFieldsMixin, serializers.Serializer):
    content = _text_field(COMMENT_MAX_LENGTH)


class ShareWriteSerializer(StrictFieldsMixin, serializers.Serializer):
    caption = _text_field(SHARE_CAPTION_MAX_LENGTH, required=False, allow_blank=True)


class ReportWriteSerializer(StrictFieldsMixin, serializers.Serializer):
    reason = serializers.ChoiceField(choices=ContentReport.Reason.choices)
    description = _text_field(REPORT_DESCRIPTION_MAX_LENGTH, required=False, allow_blank=True)


class GenericReportWriteSerializer(ReportWriteSerializer):
    """POST /api/social/reports/ {"content_type": "post"|"comment", "object_id": "<uuid>", "reason", "description"}"""

    content_type = serializers.ChoiceField(choices=ContentReport.ContentType.choices)
    object_id = serializers.UUIDField()


class ResourceShareWriteSerializer(StrictFieldsMixin, serializers.Serializer):
    """POST /api/social/shares/ - share a post, a public announcement or a verified public achievement."""

    resource_type = serializers.ChoiceField(choices=["post", "announcement", "achievement"])
    resource_id = serializers.UUIDField()
    caption = _text_field(SHARE_CAPTION_MAX_LENGTH, required=False, allow_blank=True)
    visibility = serializers.ChoiceField(
        choices=[c for c in Post.Visibility.choices if c[0] != "private"], required=False
    )


class ReportReviewSerializer(StrictFieldsMixin, serializers.Serializer):
    status = serializers.ChoiceField(choices=ContentReport.Status.choices)
    review_comments = _text_field(REPORT_DESCRIPTION_MAX_LENGTH, required=False, allow_blank=True)
    action = serializers.ChoiceField(choices=["none", "content_removed"], required=False, default="none")


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
def absolute_url(file_field, request):
    if not file_field:
        return None
    try:
        url = file_field.url
    except ValueError:
        return None
    if request is not None and url.startswith("/"):
        return request.build_absolute_uri(url)  # S3/CDN storages already return full URLs
    return url


def author_payload(user, request):
    """
    Public author card (shared implementation in common.serializers.user_card). A PRIVATE
    profile's picture is shown only to its owner and admins. Needs `author__profile` to be
    select_related (no extra query).
    """
    return user_card(user, getattr(request, "user", None), request)


class AuthorMixin:
    def get_author(self, obj):
        return author_payload(obj.author, self.context.get("request"))


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
class PostMediaSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = PostMedia
        fields = ("id", "url", "width", "height", "position")
        read_only_fields = fields

    def get_url(self, obj):
        return absolute_url(obj.image, self.context.get("request"))


def _viewer_state(context):
    """Viewer + their blocked/blocking user ids, computed ONCE per response (shared context)."""
    request = context.get("request")
    viewer = getattr(request, "user", None)
    if "hidden_ids" not in context:
        context["hidden_ids"] = hidden_user_ids(viewer)
    return viewer, context["hidden_ids"]


def _announcement_available(announcement, viewer, hidden):
    if announcement is None or not announcement.author.is_active:
        return False
    if viewer is not None and viewer.is_authenticated and announcement.author_id == viewer.pk:
        return True
    if announcement.status != "published" or announcement.author_id in hidden:
        return False
    if announcement.visibility == "public":
        return True
    return announcement.visibility == "members_only" and bool(viewer and viewer.is_authenticated)


def _achievement_available(achievement, viewer, hidden):
    if achievement is None or not achievement.user.is_active:
        return False
    if viewer is not None and viewer.is_authenticated and achievement.user_id == viewer.pk:
        return True
    if achievement.verification_status != "verified" or achievement.user_id in hidden:
        return False
    if achievement.visibility == "public":
        return True
    return achievement.visibility == "members_only" and bool(viewer and viewer.is_authenticated)


def shared_resource_payload(post, context):
    """
    What a share-post shows of its original. The original's CURRENT visibility is re-checked:
    if it was deleted, unpublished, made private or its owner blocked the viewer, only
    {"available": false} is returned (no content leaks through shares).
    """
    if not post.shared_type:
        return None
    viewer, hidden = _viewer_state(context)
    request = context.get("request")
    if post.shared_type == "announcement":
        item = post.shared_announcement
        if not _announcement_available(item, viewer, hidden):
            return {"type": "announcement", "id": None, "available": False, "data": None}
        return {
            "type": "announcement", "id": str(item.pk), "available": True,
            "data": {
                "id": str(item.pk), "title": item.title, "short_description": item.short_description,
                "category": item.category.name if item.category_id else None,
                "activity_type": item.activity_type, "location": item.location,
                "start_datetime": item.start_datetime, "end_datetime": item.end_datetime,
                "registration_deadline": item.registration_deadline,
                "cover_image": absolute_url(item.cover_image, request),
            },
        }
    item = post.shared_achievement
    if not _achievement_available(item, viewer, hidden):
        return {"type": "achievement", "id": None, "available": False, "data": None}
    return {
        "type": "achievement", "id": str(item.pk), "available": True,
        "data": {
            "id": str(item.pk), "title": item.title, "achievement_type": item.achievement_type,
            "level": item.level, "position": item.position, "organization": item.organization,
            "achievement_date": item.achievement_date,
            "category": item.category.name if item.category_id else None,
            "user": user_card(item.user, viewer, request),
        },
    }


class PostSerializer(AuthorMixin, serializers.ModelSerializer):
    """Expects a queryset passed through services.annotate_posts()."""

    author = serializers.SerializerMethodField()
    media = serializers.SerializerMethodField()
    shared_resource = serializers.SerializerMethodField()
    like_count = serializers.IntegerField(read_only=True)
    comment_count = serializers.IntegerField(read_only=True)
    share_count = serializers.IntegerField(read_only=True)
    is_liked = serializers.BooleanField(read_only=True)
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id", "author", "content", "post_type", "visibility", "media", "shared_type", "shared_resource",
            "like_count", "comment_count", "share_count", "is_liked", "is_owner",
            "is_edited", "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_shared_resource(self, obj):
        return shared_resource_payload(obj, self.context)

    def get_media(self, obj):
        return PostMediaSerializer(obj.media.all(), many=True, context=self.context).data

    def get_is_owner(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and obj.author_id == user.pk)


class CommentSerializer(AuthorMixin, serializers.ModelSerializer):
    """Expects a queryset passed through services.annotate_comments()."""

    author = serializers.SerializerMethodField()
    post_id = serializers.UUIDField(read_only=True)
    parent_comment_id = serializers.UUIDField(read_only=True)
    like_count = serializers.IntegerField(read_only=True)
    reply_count = serializers.IntegerField(read_only=True)
    is_liked = serializers.BooleanField(read_only=True)
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = (
            "id", "post_id", "parent_comment_id", "depth", "author", "content",
            "like_count", "reply_count", "is_liked", "is_owner", "is_edited", "is_deleted",
            "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_is_owner(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and obj.author_id == user.pk)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.is_deleted:
            # Placeholder: keeps the thread intact without exposing text or author.
            data["content"] = ""
            data["author"] = None
            data["is_owner"] = False
        return data


class ShareSerializer(serializers.ModelSerializer):
    """`context["post_map"]` maps post id -> serialized post (only posts the viewer may still see)."""

    caption = serializers.CharField(source="share_caption", read_only=True)
    original_post_id = serializers.UUIDField(read_only=True)
    original_post = serializers.SerializerMethodField()
    original_post_available = serializers.SerializerMethodField()

    class Meta:
        model = PostShare
        fields = ("id", "caption", "original_post_id", "original_post", "original_post_available", "created_at")
        read_only_fields = fields

    def get_original_post(self, obj):
        return self.context.get("post_map", {}).get(obj.original_post_id)

    def get_original_post_available(self, obj):
        return obj.original_post_id in self.context.get("post_map", {})


class ReportReceiptSerializer(serializers.ModelSerializer):
    """What the reporter gets back. No reporter data, no reviewer data."""

    class Meta:
        model = ContentReport
        fields = ("id", "content_type", "reason", "status", "created_at")
        read_only_fields = fields


class ReportModerationSerializer(serializers.ModelSerializer):
    """Moderator view of a report (moderators only)."""

    reporter = serializers.SerializerMethodField()
    target = serializers.SerializerMethodField()
    reviewed_by = serializers.SerializerMethodField()

    class Meta:
        model = ContentReport
        fields = (
            "id", "content_type", "target", "reporter", "reason", "description", "status",
            "action_taken", "review_comments", "reviewed_by", "reviewed_at", "created_at",
        )
        read_only_fields = fields

    def get_reporter(self, obj):
        return {"id": str(obj.reporter_id), "username": obj.reporter.username}

    def get_reviewed_by(self, obj):
        return {"id": str(obj.reviewed_by_id), "username": obj.reviewed_by.username} if obj.reviewed_by_id else None

    def get_target(self, obj):
        item = obj.post if obj.post_id else obj.comment
        return {
            "id": str(item.pk),
            "author_id": str(item.author_id),
            "content": item.content,
            "is_deleted": item.is_deleted,
            "post_id": str(item.post_id) if obj.comment_id else str(item.pk),
        }
