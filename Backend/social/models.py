from django.conf import settings
from django.db import models
from django.db.models import F, Q

from .validators import validate_image

User = settings.AUTH_USER_MODEL


class Visibility(models.TextChoices):
    PUBLIC = "public", "Public"
    FRIENDS = "friends", "Friends"
    PRIVATE = "private", "Private"


class PostKind(models.TextChoices):
    TEXT = "text", "Text"
    IMAGE = "image", "Image"
    ACHIEVEMENT = "achievement", "Achievement"
    ACTIVITY = "activity", "Activity update"
    EVENT = "event", "Event participation"
    EDUCATION = "education", "Educational update"
    SHARE = "share", "Shared post"


# kinds a client may choose; SHARE is only ever created through the share endpoint
CLIENT_POST_KINDS = [k for k in PostKind.values if k != PostKind.SHARE]


class Post(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="posts")
    kind = models.CharField(max_length=12, choices=PostKind.choices, default=PostKind.TEXT)
    caption = models.TextField(blank=True, max_length=5000)
    visibility = models.CharField(max_length=8, choices=Visibility.choices, default=Visibility.FRIENDS)

    # One post per achievement, so an achievement can never be published twice.
    # Points at the single Achievement model owned by the achievements app.
    achievement = models.OneToOneField("achievements.Achievement", null=True, blank=True,
                                       on_delete=models.SET_NULL, related_name="post")
    # Event participation updates can reference an existing announcement.
    announcement = models.ForeignKey("announcements.Announcement", null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="social_posts")
    # A share is a thin pointer to the ORIGINAL post (never a copy), always the root post.
    shared_from = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="shares")

    like_count = models.PositiveIntegerField(default=0)
    comment_count = models.PositiveIntegerField(default=0)
    share_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_edited = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["-created_at", "-id"], name="post_created_idx"),
            models.Index(fields=["author", "-created_at"], name="post_author_created_idx"),
            models.Index(fields=["visibility", "-created_at"], name="post_vis_created_idx"),
            models.Index(fields=["shared_from", "-created_at"], name="post_shared_idx"),
        ]
        constraints = [
            # a user shares a given original at most once
            models.UniqueConstraint(fields=["author", "shared_from"], name="uniq_share_per_user",
                                    condition=Q(shared_from__isnull=False)),
        ]

    def __str__(self):
        return f"Post<{self.pk}> by {self.author_id}"


class PostImage(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="social/posts/%Y/%m/", validators=[validate_image])
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]


class PostLike(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="post_likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["post", "user"], name="uniq_post_like")]
        indexes = [models.Index(fields=["post", "-created_at"])]


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comments")
    # Replies are one level deep: parent must itself be a top-level comment.
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE,
                               related_name="replies")
    body = models.TextField(max_length=2000)
    like_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_edited = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["post", "parent", "created_at"]),
            models.Index(fields=["parent", "created_at"]),
        ]


class CommentLike(models.Model):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comment_likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["comment", "user"], name="uniq_comment_like")]


class NotificationType(models.TextChoices):
    FRIEND_REQUEST = "friend_request", "Friend request"
    FRIEND_ACCEPTED = "friend_accepted", "Friend request accepted"
    POST_LIKE = "post_like", "Post liked"
    POST_COMMENT = "post_comment", "Post commented"
    COMMENT_REPLY = "comment_reply", "Comment reply"
    COMMENT_LIKE = "comment_like", "Comment liked"
    POST_SHARE = "post_share", "Post shared"
    NEW_MESSAGE = "new_message", "New message"


class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    type = models.CharField(max_length=20, choices=NotificationType.choices)
    post = models.ForeignKey(Post, null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    # friend request id / conversation id, depending on `type`
    target_id = models.BigIntegerField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"], name="notif_recipient_idx"),
        ]
