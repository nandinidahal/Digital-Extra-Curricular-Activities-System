from datetime import timedelta

from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.text import Truncator
from rest_framework import serializers

from .models import Announcement, AnnouncementStatus, Category
from .permissions import can_curate
from .signals import delete_stored_files
from .validators import safe_original_name
import os


def _abs(request, url):
    return request.build_absolute_uri(url) if request else url


def public_author(user):
    """Only what other students may see: id, username, display name. Never email/phone/etc."""
    if user is None:
        return None
    full = getattr(user, "full_name", "") or (user.get_full_name() if hasattr(user, "get_full_name") else "")
    return {"id": user.pk, "username": user.get_username(), "full_name": full}


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "description")
        read_only_fields = fields


class AnnouncementPreviewSerializer(serializers.ModelSerializer):
    """Card/preview data used by every list and the landing page."""

    category = CategorySerializer(read_only=True)
    author = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    event_date = serializers.DateField(source="start_date", read_only=True)
    bookmark_count = serializers.SerializerMethodField()
    is_bookmarked = serializers.SerializerMethodField()
    state = serializers.CharField(read_only=True)

    class Meta:
        model = Announcement
        fields = ("id", "title", "short_description", "activity_name", "category", "author", "image_url",
                  "published_at", "event_date", "start_date", "end_date", "deadline", "location",
                  "is_featured", "is_important", "bookmark_count", "is_bookmarked", "state")
        read_only_fields = fields

    def get_author(self, obj):
        return public_author(obj.published_by)

    def get_image_url(self, obj):
        return _abs(self.context.get("request"), obj.image.url) if obj.image else None

    def get_bookmark_count(self, obj):
        return getattr(obj, "bookmark_count", 0)

    def get_is_bookmarked(self, obj):
        return bool(getattr(obj, "is_bookmarked", False))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        score = getattr(instance, "rank_score", None)
        if score is not None:
            data["score"] = score
        return data


class AnnouncementDetailSerializer(AnnouncementPreviewSerializer):
    is_owner = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    attachment = serializers.SerializerMethodField()
    share_url = serializers.SerializerMethodField()

    class Meta(AnnouncementPreviewSerializer.Meta):
        fields = AnnouncementPreviewSerializer.Meta.fields + (
            "full_description", "activity_type", "country", "keywords", "expires_at", "created_at",
            "updated_at", "is_owner", "can_edit", "attachment", "share_id", "share_url")
        read_only_fields = fields

    def _is_owner(self, obj):
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated and obj.published_by_id == request.user.id)

    def get_is_owner(self, obj):
        return self._is_owner(obj)

    def get_can_edit(self, obj):
        return self._is_owner(obj)

    def get_attachment(self, obj):
        if not obj.attachment:
            return None
        request = self.context.get("request")
        name = obj.attachment_name or os.path.basename(obj.attachment.name)
        url = reverse("announcement-attachment", args=[obj.pk])
        return {"name": name, "size": obj.attachment.size if obj.attachment.storage.exists(obj.attachment.name) else None,
                "download_url": _abs(request, url)}

    def get_share_url(self, obj):
        return _abs(self.context.get("request"), reverse("announcement-detail", args=[obj.pk]))


class AnnouncementWriteSerializer(serializers.ModelSerializer):
    """Create / update. The author is NOT a field: it is set from request.user in create(), so a
    submitted published_by / author / user value is simply ignored."""

    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.filter(is_active=True))
    short_description = serializers.CharField(max_length=300, required=False, allow_blank=True)
    publish_at = serializers.DateTimeField(write_only=True, required=False, allow_null=True)
    remove_image = serializers.BooleanField(write_only=True, required=False)
    remove_attachment = serializers.BooleanField(write_only=True, required=False)

    class Meta:
        model = Announcement
        fields = ("title", "short_description", "full_description", "activity_name", "keywords", "category",
                  "activity_type", "country", "location", "start_date", "end_date", "deadline", "image",
                  "attachment", "status", "publish_at", "expires_at", "is_featured", "is_important",
                  "remove_image", "remove_attachment")
        extra_kwargs = {"title": {"min_length": 3}, "full_description": {"min_length": 5}}

    # -- field level -------------------------------------------------------------------------
    def validate_keywords(self, value):
        seen, out = set(), []
        for token in value.replace(";", ",").split(","):
            token = " ".join(token.split()).lower()
            if token and token not in seen:
                seen.add(token)
                out.append(token)
        return ", ".join(out)[:255]

    # -- object level ------------------------------------------------------------------------
    def validate(self, attrs):
        inst = self.instance
        user = self.context["request"].user
        now = timezone.now()
        today = timezone.localdate()

        def current(name):
            return attrs[name] if name in attrs else getattr(inst, name, None)

        # curation flags: coordinators/admins only
        for flag in ("is_featured", "is_important"):
            if flag in attrs:
                if attrs[flag] and not can_curate(user):
                    raise serializers.ValidationError({flag: ["Only coordinators or administrators can set this."]})
                if not can_curate(user):
                    attrs.pop(flag)

        # dates
        start, end = current("start_date"), current("end_date")
        if end and not start:
            raise serializers.ValidationError({"end_date": ["end_date requires start_date."]})
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": ["end_date cannot be before start_date."]})
        for name in ("start_date", "end_date", "deadline"):
            value = attrs.get(name)
            if value is not None and value < today and (inst is None or value != getattr(inst, name)):
                raise serializers.ValidationError({name: ["This date cannot be in the past."]})

        # publication state
        status_value = attrs.get("status", inst.status if inst else AnnouncementStatus.DRAFT)
        publish_at = attrs.pop("publish_at", None)
        if publish_at is not None:
            if status_value != AnnouncementStatus.PUBLISHED:
                raise serializers.ValidationError({"publish_at": ["publish_at needs status=published."]})
            if inst and inst.status == AnnouncementStatus.PUBLISHED and inst.published_at and inst.published_at <= now:
                raise serializers.ValidationError({"publish_at": ["This announcement is already live."]})
            if publish_at < now - timedelta(minutes=5):
                raise serializers.ValidationError({"publish_at": ["publish_at cannot be in the past."]})

        was_live_or_scheduled = bool(inst and inst.status == AnnouncementStatus.PUBLISHED)
        if status_value == AnnouncementStatus.PUBLISHED:
            if publish_at is not None:
                attrs["published_at"] = max(publish_at, now)
            elif not was_live_or_scheduled:
                attrs["published_at"] = now
        elif "status" in attrs:
            attrs["published_at"] = None

        published_at = attrs.get("published_at", inst.published_at if inst else None)
        expires_at = attrs.get("expires_at")
        if expires_at is not None:
            if expires_at <= now:
                raise serializers.ValidationError({"expires_at": ["expires_at must be in the future."]})
            if published_at and expires_at <= published_at:
                raise serializers.ValidationError({"expires_at": ["expires_at must be after the publication time."]})

        # short description: derive from the full description when absent
        if inst is None or "short_description" in attrs:
            if not (attrs.get("short_description") or "").strip():
                full = attrs.get("full_description") or (inst.full_description if inst else "")
                attrs["short_description"] = Truncator(" ".join(full.split())).chars(300)
        return attrs

    # -- persistence -------------------------------------------------------------------------
    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop("remove_image", None)
        validated_data.pop("remove_attachment", None)
        validated_data.setdefault("status", AnnouncementStatus.DRAFT)
        if validated_data.get("attachment"):
            validated_data["attachment_name"] = safe_original_name(
                validated_data["attachment"].name, os.path.splitext(validated_data["attachment"].name)[1].lower())
        # The author always comes from the authenticated request.
        return Announcement.objects.create(published_by=self.context["request"].user, **validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        remove_image = validated_data.pop("remove_image", False)
        remove_attachment = validated_data.pop("remove_attachment", False)
        old_image, old_attachment = instance.image, instance.attachment
        stale = []
        if "image" in validated_data or remove_image:
            stale.append(old_image)
            if "image" not in validated_data:
                validated_data["image"] = None
        if "attachment" in validated_data or remove_attachment:
            stale.append(old_attachment)
            if validated_data.get("attachment"):
                up = validated_data["attachment"]
                validated_data["attachment_name"] = safe_original_name(up.name, os.path.splitext(up.name)[1].lower())
            else:
                validated_data["attachment"] = None
                validated_data["attachment_name"] = ""
        # Keep references to the old files, delete them only after the new state is committed.
        old_files = [(f.storage, f.name) for f in stale if f and f.name]
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        if old_files:
            class _F:  # tiny adapter so delete_stored_files can take (storage, name) pairs
                def __init__(self, storage, name):
                    self.storage, self.name = storage, name
            delete_stored_files(*[_F(s, n) for s, n in old_files])
        return instance
