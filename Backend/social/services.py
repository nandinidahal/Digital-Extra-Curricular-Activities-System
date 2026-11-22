"""
Business logic of the Social module. Views and serializers stay thin.

Querying rules
--------------
* `feed_posts(user)`       posts a viewer may see in feeds / interact with.
* `readable_posts(user)`   same, but an admin may read everything (moderation).
* Counters (likes, comments, shares) and `is_liked` are computed in the database
  with correlated subqueries, so one page of posts costs a constant number of
  queries (no N+1) and there is no JOIN row-multiplication.
"""
import logging

from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, IntegerField, OuterRef, Prefetch, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from common.relationships import friend_ids as _friend_ids
from common.relationships import hidden_user_ids
from notifications.services import notify

from .exceptions import (
    AlreadyReported,
    AlreadyShared,
    CannotReportOwnContent,
    CommentNotFound,
    MaxDepthReached,
    PostNotFound,
    PostNotShareable,
)
from .models import (
    MAX_COMMENT_DEPTH,
    Comment,
    CommentLike,
    ContentReport,
    Post,
    PostLike,
    PostMedia,
    PostShare,
)
from .permissions import check_post_visible, is_admin, is_authenticated, visibility_filter
from .validators import max_images_per_post, process_post_image

logger = logging.getLogger("social")


# ---------------------------------------------------------------------------
# Querysets
# ---------------------------------------------------------------------------
def _count_subquery(queryset, group_field):
    return Coalesce(
        Subquery(
            queryset.order_by().values(group_field).annotate(c=Count("pk")).values("c"),
            output_field=IntegerField(),
        ),
        Value(0),
    )


def _live_posts():
    return Post.objects.filter(is_deleted=False, author__is_active=True)


def feed_posts(user):
    return _live_posts().filter(visibility_filter(user))


def readable_posts(user):
    if is_admin(user):
        return _live_posts()
    return feed_posts(user)


def annotate_posts(queryset, user):
    """Attach author+profile, media, counts and is_liked to a Post queryset."""
    like_count = _count_subquery(PostLike.objects.filter(post=OuterRef("pk")), "post")
    comment_count = _count_subquery(
        Comment.objects.filter(post=OuterRef("pk"), is_deleted=False), "post"
    )
    share_count = _count_subquery(PostShare.objects.filter(original_post=OuterRef("pk")), "original_post")
    if is_authenticated(user):
        is_liked = Exists(PostLike.objects.filter(post=OuterRef("pk"), user=user))
    else:
        is_liked = Value(False)
    return (
        queryset.select_related(
            "author", "author__profile",
            "shared_announcement", "shared_announcement__author", "shared_announcement__category",
            "shared_achievement", "shared_achievement__user", "shared_achievement__user__profile",
            "shared_achievement__category",
        )
        .prefetch_related(Prefetch("media", queryset=PostMedia.objects.order_by("position", "created_at")))
        .annotate(like_count=like_count, comment_count=comment_count, share_count=share_count, is_liked=is_liked)
    )


def annotate_comments(queryset, user):
    like_count = _count_subquery(CommentLike.objects.filter(comment=OuterRef("pk")), "comment")
    reply_count = _count_subquery(
        Comment.objects.filter(parent_comment=OuterRef("pk"), is_deleted=False), "parent_comment"
    )
    if is_authenticated(user):
        is_liked = Exists(CommentLike.objects.filter(comment=OuterRef("pk"), user=user))
    else:
        is_liked = Value(False)
    return queryset.select_related("author", "author__profile").annotate(
        like_count=like_count, reply_count=reply_count, is_liked=is_liked
    )


def apply_post_filters(queryset, params):
    post_type = params.get("post_type")
    if post_type in Post.PostType.values:
        queryset = queryset.filter(post_type=post_type)
    shared = params.get("shared_type")
    if shared in ("announcement", "achievement"):
        queryset = queryset.filter(shared_type=shared)
    return queryset


def scoped_feed(user, scope):
    """
    The social feed (newest first): the viewer's own posts, friends' posts (incl. friends-only),
    public and members-only posts, and shares of announcements/achievements (they are posts).
    scope="friends" keeps only the viewer's own and friends' posts.
    """
    queryset = feed_posts(user)
    if scope == "friends" and is_authenticated(user):
        queryset = queryset.filter(Q(author=user) | Q(author_id__in=_friend_ids(user)))
    return queryset


# ---------------------------------------------------------------------------
# Single-object lookups (404 for missing/deleted/private, 401 for members-only visitors)
# ---------------------------------------------------------------------------
def get_post(user, post_id, *, write=False, annotated=False):
    """
    `write=True` is used by every action that changes something (like, comment, share,
    report, edit): admins get no special reading override there.
    """
    queryset = _live_posts().filter(pk=post_id)
    if annotated:
        queryset = annotate_posts(queryset, user)
    else:
        queryset = queryset.select_related("author")
    post = queryset.first()
    if post is None:
        raise PostNotFound()
    check_post_visible(user, post, admin_override=not write)
    return post


def get_comment(user, comment_id, *, write=False, allow_deleted=False, annotated=False):
    queryset = Comment.objects.filter(pk=comment_id)
    if annotated:
        queryset = annotate_comments(queryset, user)
    else:
        queryset = queryset.select_related("author")
    comment = queryset.select_related("post", "post__author").first()
    if comment is None or (comment.is_deleted and not allow_deleted):
        raise CommentNotFound()
    post = comment.post
    if post.is_deleted or not post.author.is_active:
        raise CommentNotFound()
    try:
        check_post_visible(user, post, admin_override=not write)
    except PostNotFound:
        raise CommentNotFound()
    if (write or not is_admin(user)) and comment.author_id in hidden_user_ids(user):
        raise CommentNotFound()  # comments of blocked / blocking users are invisible
    return comment


# ---------------------------------------------------------------------------
# Posts and media
# ---------------------------------------------------------------------------
def _delete_stored_file(storage, name):
    try:
        storage.delete(name)
    except Exception:  # cleanup must never break a request
        logger.warning("Could not delete stored file %s", name)


def _store_images(post, images, start_position):
    """Write validated images to storage and create PostMedia rows. Returns stored names."""
    stored = []
    try:
        for offset, (upload, image_format) in enumerate(images):
            content, width, height, extension = process_post_image(upload, image_format)
            media = PostMedia(post=post, width=width, height=height, position=start_position + offset)
            media.image.save(f"image.{extension}", content, save=False)
            stored.append((media.image.storage, media.image.name))
            media.save()
    except Exception:
        for storage, name in stored:
            _delete_stored_file(storage, name)
        raise
    return stored


def _check_image_count(existing, new):
    limit = max_images_per_post()
    if existing + new > limit:
        raise ValidationError({"images": [f"A post can have at most {limit} images."]})


@transaction.atomic
def create_post(user, validated_data):
    images = validated_data.get("images", [])
    _check_image_count(0, len(images))
    post = Post.objects.create(
        author=user,  # always the authenticated user, never taken from the request body
        content=validated_data.get("content", ""),
        post_type=validated_data.get("post_type", Post.PostType.GENERAL),
        visibility=validated_data.get("visibility", Post.Visibility.PUBLIC),
    )
    # Files are written inside the atomic block; `_store_images` removes them again on any error.
    _store_images(post, images, 0)
    return post


@transaction.atomic
def update_post(post, validated_data):
    images = validated_data.get("images", [])
    new_content = validated_data.get("content", post.content)
    existing = post.media.count()
    if post.shared_type:
        if images:
            raise ValidationError({"images": ["Images cannot be added to a shared announcement or achievement."]})
        if validated_data.get("visibility") == Post.Visibility.PRIVATE:
            raise ValidationError({"visibility": ["A share cannot be private."]})
    _check_image_count(existing, len(images))
    if not post.shared_type and not new_content.strip() and existing + len(images) == 0:
        raise ValidationError({"content": ["A post needs text or at least one image."]})

    content_changed = "content" in validated_data and new_content != post.content
    for field in ("content", "post_type", "visibility"):
        if field in validated_data:
            setattr(post, field, validated_data[field])
    if content_changed:
        post.is_edited = True
    post.save()
    if images:
        last = post.media.order_by("-position").values_list("position", flat=True).first()
        _store_images(post, images, (last + 1) if last is not None else 0)
    return post


@transaction.atomic
def remove_post_media(post, media):
    if not post.content.strip() and post.media.count() <= 1:
        raise ValidationError({"media": ["A post without text must keep at least one image."]})
    media.delete()  # the post_delete signal removes the file once the transaction commits
    post.is_edited = True
    post.save(update_fields=["is_edited", "updated_at"])


@transaction.atomic
def delete_post(post):
    """
    Soft delete: the row stays (report evidence, consistent counters) but disappears from
    every API response. Its image files and rows are removed now (cleanup of orphans).
    """
    post.is_deleted = True
    post.deleted_at = timezone.now()
    post.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
    for media in post.media.all():
        media.delete()


# ---------------------------------------------------------------------------
# Likes
# ---------------------------------------------------------------------------
def like_post(user, post):
    """Idempotent. Returns True if a like was created, False if it already existed."""
    _, created = PostLike.objects.get_or_create(post=post, user=user)
    if created:
        # dedupe: unlike + like again never notifies twice
        notify(
            recipient=post.author_id, actor=user.pk, notification_type="post.liked",
            target_type="post", target_id=post.pk, metadata={"post_id": post.pk},
            action_url=f"/social/posts/{post.pk}", dedupe_key=f"post.liked:{post.pk}:{user.pk}",
        )
    return created


def unlike_post(user, post):
    deleted, _ = PostLike.objects.filter(post=post, user=user).delete()
    return bool(deleted)


def like_comment(user, comment):
    _, created = CommentLike.objects.get_or_create(comment=comment, user=user)
    return created


def unlike_comment(user, comment):
    deleted, _ = CommentLike.objects.filter(comment=comment, user=user).delete()
    return bool(deleted)


def post_like_state(user, post_id):
    return {
        "like_count": PostLike.objects.filter(post_id=post_id).count(),
        "is_liked": PostLike.objects.filter(post_id=post_id, user=user).exists(),
    }


def comment_like_state(user, comment_id):
    return {
        "like_count": CommentLike.objects.filter(comment_id=comment_id).count(),
        "is_liked": CommentLike.objects.filter(comment_id=comment_id, user=user).exists(),
    }


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------
def create_comment(user, post, content, parent=None):
    depth = 0
    if parent is not None:
        if parent.depth >= MAX_COMMENT_DEPTH:
            raise MaxDepthReached(
                f"Replies can only be nested {MAX_COMMENT_DEPTH} levels deep. "
                "Reply to the thread above instead."
            )
        depth = parent.depth + 1
    comment = Comment.objects.create(
        post=post, author=user, parent_comment=parent, depth=depth, content=content
    )
    metadata = {"post_id": post.pk, "comment_id": comment.pk}
    if parent is not None:
        notify(
            recipient=parent.author_id, actor=user.pk, notification_type="comment.replied",
            target_type="comment", target_id=comment.pk, metadata=metadata,
            action_url=f"/social/posts/{post.pk}", group_key=f"comment.replied:{parent.pk}",
        )
    else:
        notify(
            recipient=post.author_id, actor=user.pk, notification_type="post.commented",
            target_type="post", target_id=post.pk, metadata=metadata,
            action_url=f"/social/posts/{post.pk}", group_key=f"post.commented:{post.pk}",
        )
    return comment


def update_comment(comment, content):
    if content != comment.content:
        comment.content = content
        comment.is_edited = True
        comment.save()
    return comment


def delete_comment(comment):
    """Soft delete: the row stays so replies keep their place; the API shows a placeholder."""
    comment.is_deleted = True
    comment.deleted_at = timezone.now()
    comment.save(update_fields=["is_deleted", "deleted_at", "updated_at"])


def _without_hidden(queryset, viewer):
    hidden = hidden_user_ids(viewer)
    return queryset.exclude(author_id__in=hidden) if hidden else queryset


def visible_top_level_comments(post, viewer=None):
    """Top-level comments; a deleted one is kept only as a placeholder while it still has live replies."""
    live_replies = Comment.objects.filter(parent_comment=OuterRef("pk"), is_deleted=False)
    queryset = (
        Comment.objects.filter(post=post, parent_comment__isnull=True)
        .filter(Q(is_deleted=False) | Exists(live_replies))
    )
    return _without_hidden(queryset, viewer)


def visible_replies(parent, viewer=None):
    live_replies = Comment.objects.filter(parent_comment=OuterRef("pk"), is_deleted=False)
    queryset = Comment.objects.filter(parent_comment=parent).filter(Q(is_deleted=False) | Exists(live_replies))
    return _without_hidden(queryset, viewer)


# ---------------------------------------------------------------------------
# Shares
# ---------------------------------------------------------------------------
def share_post(user, post, caption=""):
    # Private and friends-only posts have a closed audience: re-broadcasting them is not allowed.
    if post.visibility in (Post.Visibility.PRIVATE, Post.Visibility.FRIENDS):
        raise PostNotShareable("Private and friends-only posts cannot be shared.")
    try:
        with transaction.atomic():
            share = PostShare.objects.create(original_post=post, user=user, share_caption=caption)
    except IntegrityError:  # double click / replayed request: the unique constraint wins
        raise AlreadyShared()
    notify(
        recipient=post.author_id, actor=user.pk, notification_type="post.shared",
        context={"resource": "post"}, target_type="post", target_id=post.pk,
        metadata={"post_id": post.pk}, action_url=f"/social/posts/{post.pk}",
        dedupe_key=f"post.shared:post:{post.pk}:{user.pk}",
    )
    return share


def share_resource(user, resource_type, resource_id, caption="", visibility=Post.Visibility.PUBLIC):
    """
    Share a published PUBLIC announcement or a VERIFIED PUBLIC achievement as a post that
    references it. The original's visibility is checked now and again whenever it is shown.
    """
    if visibility == Post.Visibility.PRIVATE:
        raise ValidationError({"visibility": ["A share cannot be private."]})
    if resource_type == "announcement":
        from announcements import services as announcement_services

        resource = announcement_services.get_visible_announcement(user, resource_id, annotated=False)
        if not announcement_services.is_shareable(resource):
            raise PostNotShareable("Only published public announcements can be shared.")
        owner_id, fields = resource.author_id, {"shared_announcement": resource}
    elif resource_type == "achievement":
        from achievements import services as achievement_services

        resource = achievement_services.get_visible_achievement(user, resource_id)
        if not achievement_services.is_shareable(resource):
            raise PostNotShareable("Only verified public achievements can be shared.")
        owner_id, fields = resource.user_id, {"shared_achievement": resource}
    else:
        raise ValidationError({"resource_type": ["Unsupported resource type."]})
    try:
        with transaction.atomic():
            post = Post.objects.create(
                author=user, content=caption, visibility=visibility, shared_type=resource_type,
                post_type=Post.PostType.ACHIEVEMENT if resource_type == "achievement" else Post.PostType.ACTIVITY,
                **fields,
            )
    except IntegrityError:
        raise AlreadyShared(f"You have already shared this {resource_type}.")
    notify(
        recipient=owner_id, actor=user.pk, notification_type="post.shared",
        context={"resource": resource_type}, target_type=resource_type, target_id=resource.pk,
        metadata={"post_id": post.pk, f"{resource_type}_id": resource.pk},
        action_url=f"/social/posts/{post.pk}", dedupe_key=f"post.shared:{resource_type}:{resource.pk}:{user.pk}",
    )
    return post


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
def report_content(user, *, post=None, comment=None, reason, description=""):
    target_author_id = post.author_id if post is not None else comment.author_id
    if target_author_id == user.pk:
        raise CannotReportOwnContent()
    already = ContentReport.objects.filter(
        reporter=user, status__in=ContentReport.ACTIVE_STATUSES, post=post, comment=comment
    ).exists()
    if already:
        raise AlreadyReported()
    try:
        with transaction.atomic():
            return ContentReport.objects.create(
                reporter=user,
                content_type=ContentReport.ContentType.POST if post else ContentReport.ContentType.COMMENT,
                post=post,
                comment=comment,
                reason=reason,
                description=description,
            )
    except IntegrityError:
        raise AlreadyReported()


# ---------------------------------------------------------------------------
# Report moderation (moderators: admin or coordinator)
# ---------------------------------------------------------------------------
REPORT_TRANSITIONS = {
    ContentReport.Status.PENDING: {"reviewing", "resolved", "dismissed"},
    ContentReport.Status.REVIEWING: {"resolved", "dismissed"},
    ContentReport.Status.RESOLVED: set(),
    ContentReport.Status.DISMISSED: set(),
}


@transaction.atomic
def review_report(moderator, report_id, *, status, review_comments="", action="none"):
    from common.exceptions import BusinessRuleViolation, ResourceNotFound

    report = ContentReport.objects.select_for_update().filter(pk=report_id).first()
    if report is None:
        raise ResourceNotFound("This report does not exist.", code="report_not_found")
    if status != report.status and status not in REPORT_TRANSITIONS[report.status]:
        raise BusinessRuleViolation(f"A {report.status} report cannot be changed to {status}.", code="invalid_status_transition")
    if action == "content_removed":
        if status != ContentReport.Status.RESOLVED:
            raise ValidationError({"action": ["Content can only be removed when resolving a report."]})
        if report.post_id:
            post = Post.objects.select_for_update().get(pk=report.post_id)
            if not post.is_deleted:
                delete_post(post)
        else:
            comment = Comment.objects.select_for_update().get(pk=report.comment_id)
            if not comment.is_deleted:
                delete_comment(comment)
        report.action_taken = "content_removed"
    report.status = status
    if review_comments:
        report.review_comments = review_comments
    report.reviewed_by = moderator
    report.reviewed_at = timezone.now()
    report.save()
    return report
