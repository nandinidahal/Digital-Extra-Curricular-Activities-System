"""
Database models of the Social module.

Design notes (details in README.md):
* Every primary key is a UUID, like Accounts and Profiles.
* Posts and comments are soft-deleted (`is_deleted`) so discussion structure,
  report evidence and counters stay consistent. Likes/shares are hard-deleted.
* Uniqueness of likes, shares and active reports is enforced by the database.
* A share is a row that points at the original post; content is never copied.
"""
import os
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

MAX_COMMENT_DEPTH = 2  # 0 = top-level comment, 1 = reply, 2 = reply to a reply (last level)
POST_MAX_LENGTH = 5000
COMMENT_MAX_LENGTH = 2000
SHARE_CAPTION_MAX_LENGTH = 500
REPORT_DESCRIPTION_MAX_LENGTH = 1000

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def post_media_upload_to(instance, filename):
    """social/posts/<post uuid>/<random uuid>.<ext>; the client's file name is never used."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _IMAGE_EXTENSIONS:
        ext = ".jpg"
    return f"social/posts/{instance.post_id}/{uuid.uuid4().hex}{ext}"


class Post(models.Model):
    class PostType(models.TextChoices):
        GENERAL = "general", "General"
        ACTIVITY = "activity", "Activity"
        ACHIEVEMENT = "achievement", "Achievement"  # a post only; NOT an official achievement record
        EXPERIENCE = "experience", "Experience"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Public"
        MEMBERS_ONLY = "members_only", "Members only"
        FRIENDS = "friends", "Friends"
        PRIVATE = "private", "Private"

    class SharedType(models.TextChoices):
        NONE = "", "Not a share"
        ANNOUNCEMENT = "announcement", "Announcement"
        ACHIEVEMENT = "achievement", "Achievement"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="social_posts"
    )
    content = models.TextField(max_length=POST_MAX_LENGTH, blank=True)
    post_type = models.CharField(max_length=20, choices=PostType.choices, default=PostType.GENERAL)
    visibility = models.CharField(
        max_length=20, choices=Visibility.choices, default=Visibility.PUBLIC
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    # A post can be a share of an announcement or an achievement. Only a REFERENCE is stored
    # (never a copy); the original's visibility is re-checked every time the post is shown.
    # SET_NULL: if the original is deleted the share stays and shows "no longer available".
    shared_type = models.CharField(max_length=20, choices=SharedType.choices, blank=True, default="")
    shared_announcement = models.ForeignKey(
        "announcements.Announcement", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="social_shares",
    )
    shared_achievement = models.ForeignKey(
        "achievements.Achievement", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="social_shares",
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(post_type__in=["general", "activity", "achievement", "experience"]),
                name="social_post_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(visibility__in=["public", "members_only", "friends", "private"]),
                name="social_post_visibility_valid_v2",
            ),
            models.CheckConstraint(
                condition=(
                    Q(shared_type="", shared_announcement__isnull=True, shared_achievement__isnull=True)
                    | Q(shared_type="announcement", shared_achievement__isnull=True)
                    | Q(shared_type="achievement", shared_announcement__isnull=True)
                ),
                name="social_post_shared_consistent",
            ),
            # One live share per user per announcement / achievement.
            models.UniqueConstraint(
                fields=["author", "shared_announcement"],
                condition=Q(is_deleted=False, shared_announcement__isnull=False),
                name="social_post_one_announcement_share",
            ),
            models.UniqueConstraint(
                fields=["author", "shared_achievement"],
                condition=Q(is_deleted=False, shared_achievement__isnull=False),
                name="social_post_one_achievement_share",
            ),
        ]
        indexes = [
            # general feed: WHERE is_deleted = false AND visibility IN (...) ORDER BY created_at DESC
            models.Index(fields=["is_deleted", "visibility", "-created_at"], name="social_post_feed_idx"),
            # "posts of one author" (profile page, /me/posts/)
            models.Index(fields=["author", "is_deleted", "-created_at"], name="social_post_author_idx"),
        ]

    def __str__(self):
        return f"Post {self.id} by {self.author_id}"


class PostMedia(models.Model):
    """One image attached to a post. Only the storage path is in the database."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="media")
    image = models.ImageField(upload_to=post_media_upload_to, max_length=255)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "created_at"]
        indexes = [models.Index(fields=["post", "position"], name="social_media_post_idx")]

    def __str__(self):
        return f"Media {self.id} of post {self.post_id}"


class PostLike(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="social_post_likes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["post", "user"], name="social_postlike_unique"),
        ]

    def __str__(self):
        return f"{self.user_id} likes {self.post_id}"


class Comment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="social_comments"
    )
    parent_comment = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies"
    )
    # Stored so the depth limit is checked without walking the parent chain.
    depth = models.PositiveSmallIntegerField(default=0)
    content = models.TextField(max_length=COMMENT_MAX_LENGTH)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(parent_comment__isnull=True, depth=0))
                | (Q(parent_comment__isnull=False, depth__gt=0)),
                name="social_comment_depth_consistent",
            ),
        ]
        indexes = [
            models.Index(fields=["post", "parent_comment", "created_at"], name="social_comment_list_idx"),
            models.Index(fields=["parent_comment", "created_at"], name="social_comment_reply_idx"),
        ]

    def __str__(self):
        return f"Comment {self.id} on {self.post_id}"


class CommentLike(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="social_comment_likes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["comment", "user"], name="social_commentlike_unique"),
        ]

    def __str__(self):
        return f"{self.user_id} likes comment {self.comment_id}"


class PostShare(models.Model):
    """A user's share of a post. References the original; never copies its content."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    original_post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="shares")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="social_shares"
    )
    share_caption = models.CharField(max_length=SHARE_CAPTION_MAX_LENGTH, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            # One share per user per post: stops double-click/replayed requests from inflating counts.
            models.UniqueConstraint(fields=["original_post", "user"], name="social_postshare_unique"),
        ]
        indexes = [models.Index(fields=["user", "-created_at"], name="social_share_user_idx")]

    def __str__(self):
        return f"{self.user_id} shared {self.original_post_id}"


class ContentReport(models.Model):
    class ContentType(models.TextChoices):
        POST = "post", "Post"
        COMMENT = "comment", "Comment"

    class Reason(models.TextChoices):
        SPAM = "spam", "Spam"
        HARASSMENT = "harassment", "Harassment"
        INAPPROPRIATE = "inappropriate", "Inappropriate content"
        FALSE_INFORMATION = "false_information", "False information"
        BULLYING = "bullying", "Bullying"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        REVIEWING = "reviewing", "Under review"
        RESOLVED = "resolved", "Resolved (action taken)"
        DISMISSED = "dismissed", "Dismissed"

    ACTIVE_STATUSES = ("pending", "reviewing")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="social_reports_made"
    )
    content_type = models.CharField(max_length=10, choices=ContentType.choices)
    post = models.ForeignKey(
        Post, null=True, blank=True, on_delete=models.CASCADE, related_name="reports"
    )
    comment = models.ForeignKey(
        Comment, null=True, blank=True, on_delete=models.CASCADE, related_name="reports"
    )
    reason = models.CharField(max_length=30, choices=Reason.choices)
    description = models.TextField(max_length=REPORT_DESCRIPTION_MAX_LENGTH, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comments = models.TextField(max_length=REPORT_DESCRIPTION_MAX_LENGTH, blank=True)
    action_taken = models.CharField(
        max_length=20, choices=[("none", "No action"), ("content_removed", "Content removed")], default="none"
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="social_reports_reviewed",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(content_type="post", post__isnull=False, comment__isnull=True)
                    | Q(content_type="comment", comment__isnull=False, post__isnull=True)
                ),
                name="social_report_target_consistent",
            ),
            models.UniqueConstraint(
                fields=["reporter", "post"],
                condition=Q(post__isnull=False, status__in=["pending", "reviewing"]),
                name="social_report_active_post_unique",
            ),
            models.UniqueConstraint(
                fields=["reporter", "comment"],
                condition=Q(comment__isnull=False, status__in=["pending", "reviewing"]),
                name="social_report_active_comment_unique",
            ),
        ]
        indexes = [models.Index(fields=["status", "-created_at"], name="social_report_status_idx")]

    def __str__(self):
        return f"Report {self.id} ({self.content_type}, {self.status})"
