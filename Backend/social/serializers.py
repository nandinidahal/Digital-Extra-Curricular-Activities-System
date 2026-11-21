from django.contrib.auth import get_user_model
from rest_framework import serializers

from achievements.models import Achievement
from achievements.models import Visibility as AchievementVisibility
from announcements.models import Announcement, AnnouncementStatus
from profiles.models import UserProfile

from .models import (CLIENT_POST_KINDS, Comment, Notification, NotificationType, Post,
                     PostImage, PostKind, Visibility)
from .validators import validate_image

User = get_user_model()
MAX_IMAGES_PER_POST = 10


def _abs(request, f):
    if not f:
        return None
    url = f.url
    return request.build_absolute_uri(url) if request else url


class UserBriefSerializer(serializers.ModelSerializer):
    """Avatar + name + username: what every card in the UI needs to link to a profile."""
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "full_name", "avatar")
        read_only_fields = fields

    def get_avatar(self, obj):
        profile = getattr(obj, "user_profile", None)  # callers select_related("user_profile")
        return _abs(self.context.get("request"), profile.profile_picture if profile else None)


# ---------------------------------------------------------------- profiles
def _clean_tags(value, label):
    if not isinstance(value, list):
        raise serializers.ValidationError("Provide a list of strings.")
    out, seen = [], set()
    for item in value:
        if not isinstance(item, str):
            raise serializers.ValidationError("Provide a list of strings.")
        item = " ".join(item.split()).lower()
        if not item:
            continue
        if len(item) > 40:
            raise serializers.ValidationError(f"Each {label} must be 40 characters or fewer.")
        if item not in seen:
            seen.add(item)
            out.append(item)
    if len(out) > 20:
        raise serializers.ValidationError(f"At most 20 {label}s.")
    return out


class ProfileUpdateSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(max_length=150, required=False)
    # "avatar" is the API name; it is stored in UserProfile.profile_picture (one picture per user).
    avatar = serializers.ImageField(source="profile_picture", required=False, allow_null=True,
                                    validators=[validate_image])
    cover_image = serializers.ImageField(required=False, allow_null=True, validators=[validate_image])
    bio = serializers.CharField(max_length=300, required=False, allow_blank=True)
    interests = serializers.JSONField(required=False)
    skills = serializers.JSONField(required=False)

    class Meta:
        model = UserProfile
        fields = ("full_name", "avatar", "cover_image", "bio", "institution", "department", "interests", "skills")

    def validate_interests(self, v):
        return _clean_tags(v, "interest")

    def validate_skills(self, v):
        return _clean_tags(v, "skill")

    def update(self, instance, validated):
        full_name = validated.pop("full_name", None)
        if full_name is not None and full_name != instance.user.full_name:
            instance.user.full_name = full_name.strip()
            instance.user.save(update_fields=["full_name"])
        return super().update(instance, validated)


class ProfileSerializer(serializers.Serializer):
    """Read-only profile page. Expects the view to pass precomputed stats in context['stats']."""

    def to_representation(self, user):
        request = self.context.get("request")
        profile = getattr(user, "user_profile", None)
        stats = self.context["stats"]
        return {
            "id": user.pk,
            "username": user.username,
            "full_name": user.full_name,
            "date_joined": user.date_joined,
            "avatar": _abs(request, profile.profile_picture if profile else None),
            "cover_image": _abs(request, profile.cover_image if profile else None),
            "bio": profile.bio if profile else "",
            "institution": profile.institution if profile else "",
            "department": profile.department if profile else "",
            "interests": (profile.interests if profile else []) or [],
            "skills": (profile.skills if profile else []) or [],
            **stats,
        }


# ---------------------------------------------------------------- posts
class PostImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = PostImage
        fields = ("id", "url", "position")

    def get_url(self, obj):
        return _abs(self.context.get("request"), obj.image)


class PostEmbedSerializer(serializers.ModelSerializer):
    """The original post inside a share."""
    author = UserBriefSerializer(read_only=True)
    images = PostImageSerializer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = ("id", "author", "kind", "caption", "images", "created_at")


class PostSerializer(serializers.ModelSerializer):
    author = UserBriefSerializer(read_only=True)
    images = PostImageSerializer(many=True, read_only=True)
    achievement = serializers.SerializerMethodField()
    announcement = serializers.SerializerMethodField()
    shared_from = serializers.SerializerMethodField()
    original_unavailable = serializers.SerializerMethodField()
    liked_by_me = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ("id", "author", "kind", "caption", "visibility", "images", "achievement", "announcement",
                  "shared_from", "original_unavailable", "like_count", "comment_count", "share_count",
                  "liked_by_me", "is_mine", "is_edited", "created_at", "updated_at")

    def get_achievement(self, obj):
        a = obj.achievement
        if a is None:
            return None
        return {"id": a.pk, "title": a.title, "achieved_on": a.achievement_date, "organization": a.issuing_organization}

    def get_announcement(self, obj):
        a = obj.announcement
        return {"id": a.pk, "title": a.title} if a else None

    def get_shared_from(self, obj):
        if obj.shared_from_id and getattr(obj, "original_visible", False):
            return PostEmbedSerializer(obj.shared_from, context=self.context).data
        return None

    def get_original_unavailable(self, obj):
        return bool(obj.kind == PostKind.SHARE and not getattr(obj, "original_visible", False))

    def get_liked_by_me(self, obj):
        if hasattr(obj, "liked_by_me"):
            return obj.liked_by_me
        return False

    def get_is_mine(self, obj):
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated and obj.author_id == request.user.pk)


class PostWriteSerializer(serializers.Serializer):
    caption = serializers.CharField(max_length=5000, required=False, allow_blank=True)
    visibility = serializers.ChoiceField(choices=Visibility.choices, required=False)
    kind = serializers.ChoiceField(choices=CLIENT_POST_KINDS, required=False)
    achievement_id = serializers.IntegerField(required=False)
    announcement_id = serializers.IntegerField(required=False)
    images = serializers.ListField(child=serializers.ImageField(validators=[validate_image]), required=False,
                                   max_length=MAX_IMAGES_PER_POST)
    remove_image_ids = serializers.ListField(child=serializers.IntegerField(), required=False)

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user
        post = self.instance  # None on create

        if post is not None and post.kind == PostKind.SHARE:
            if attrs.get("images") or attrs.get("remove_image_ids") or "kind" in attrs \
                    or "achievement_id" in attrs or "announcement_id" in attrs:
                raise serializers.ValidationError("A shared post only supports a caption and visibility.")
            return attrs

        if post is not None:
            for locked in ("kind", "achievement_id", "announcement_id"):
                if locked in attrs:
                    raise serializers.ValidationError({locked: ["This cannot be changed after posting."]})
            existing = post.images.count()
            remove = set(attrs.get("remove_image_ids", []))
            if remove - set(post.images.values_list("pk", flat=True)):
                raise serializers.ValidationError({"remove_image_ids": ["Unknown image id."]})
            if existing - len(remove) + len(attrs.get("images", [])) > MAX_IMAGES_PER_POST:
                raise serializers.ValidationError({"images": [f"At most {MAX_IMAGES_PER_POST} images per post."]})
            vis = attrs.get("visibility", post.visibility)
            if post.achievement_id and post.achievement \
                    and post.achievement.visibility != AchievementVisibility.PUBLIC \
                    and vis != Visibility.PRIVATE:
                raise serializers.ValidationError(
                    {"visibility": ["This achievement is private, so its post can only be private."]})
            return attrs

        # ---- create
        images = attrs.get("images", [])
        caption = (attrs.get("caption") or "").strip()
        kind = attrs.get("kind")
        achievement = announcement = None

        if "achievement_id" in attrs:
            achievement = Achievement.objects.filter(pk=attrs["achievement_id"], user=user).select_related("post").first()
            if achievement is None:
                raise serializers.ValidationError({"achievement_id": ["Achievement not found."]})
            if hasattr(achievement, "post") and achievement.post is not None:
                raise serializers.ValidationError(
                    {"achievement_id": ["This achievement has already been posted."]})
            kind = kind or PostKind.ACHIEVEMENT
            if kind != PostKind.ACHIEVEMENT:
                raise serializers.ValidationError({"kind": ["Use kind 'achievement' with achievement_id."]})
        elif kind == PostKind.ACHIEVEMENT:
            raise serializers.ValidationError({"achievement_id": ["Required for achievement posts."]})

        if "announcement_id" in attrs:
            announcement = Announcement.objects.filter(pk=attrs["announcement_id"],
                                                       status=AnnouncementStatus.PUBLISHED).first()
            if announcement is None:
                raise serializers.ValidationError({"announcement_id": ["Event not found."]})
            kind = kind or PostKind.EVENT
            if kind not in (PostKind.EVENT, PostKind.ACTIVITY):
                raise serializers.ValidationError({"kind": ["announcement_id is only for event/activity posts."]})

        if kind is None:
            kind = PostKind.IMAGE if images else PostKind.TEXT
        if kind == PostKind.IMAGE and not images:
            raise serializers.ValidationError({"images": ["Image posts need at least one image."]})
        if not caption and not images and achievement is None:
            raise serializers.ValidationError({"caption": ["A post needs text or at least one image."]})

        visibility = attrs.get("visibility", Visibility.FRIENDS)
        if achievement is not None and achievement.visibility != AchievementVisibility.PUBLIC \
                and visibility != Visibility.PRIVATE:
            raise serializers.ValidationError(
                {"visibility": ["This achievement is private. Make it public first, or post it as private."]})

        attrs.update(kind=kind, achievement=achievement, announcement=announcement, visibility=visibility,
                     caption=caption)
        return attrs


class ShareSerializer(serializers.Serializer):
    caption = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")
    visibility = serializers.ChoiceField(choices=Visibility.choices, default=Visibility.FRIENDS)


# ---------------------------------------------------------------- comments
class CommentSerializer(serializers.ModelSerializer):
    author = UserBriefSerializer(read_only=True)
    liked_by_me = serializers.SerializerMethodField()
    replies_count = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ("id", "post", "parent", "author", "body", "like_count", "liked_by_me", "replies_count",
                  "is_mine", "is_edited", "created_at", "updated_at")
        read_only_fields = fields

    def get_liked_by_me(self, obj):
        return getattr(obj, "liked_by_me", False)

    def get_replies_count(self, obj):
        return getattr(obj, "replies_total", 0)

    def get_is_mine(self, obj):
        return obj.author_id == self.context["request"].user.pk


class CommentWriteSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=2000)
    parent = serializers.IntegerField(required=False, allow_null=True)

    def validate_body(self, v):
        v = v.strip()
        if not v:
            raise serializers.ValidationError("Comment cannot be empty.")
        return v


# ---------------------------------------------------------------- notifications
NOTIFICATION_TEXT = {
    NotificationType.FRIEND_REQUEST: "sent you a friend request",
    NotificationType.FRIEND_ACCEPTED: "accepted your friend request",
    NotificationType.POST_LIKE: "liked your post",
    NotificationType.POST_COMMENT: "commented on your post",
    NotificationType.COMMENT_REPLY: "replied to your comment",
    NotificationType.COMMENT_LIKE: "liked your comment",
    NotificationType.POST_SHARE: "shared your post",
    NotificationType.NEW_MESSAGE: "sent you a message",
}


class NotificationSerializer(serializers.ModelSerializer):
    actor = UserBriefSerializer(read_only=True)
    text = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ("id", "type", "actor", "text", "post", "target_id", "is_read", "created_at")
        read_only_fields = fields

    def get_text(self, obj):
        who = obj.actor.full_name or obj.actor.username if obj.actor else "Someone"
        return f"{who} {NOTIFICATION_TEXT.get(obj.type, 'interacted with you')}"
