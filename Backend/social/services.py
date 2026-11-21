"""Write-side operations for posts, likes, comments and shares. Counters are maintained with F()
expressions inside transactions, guarded by unique constraints, so concurrent requests can't
double-count or double-like."""
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.db.models.functions import Greatest
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError

from friends.services import Conflict

from .models import (Comment, CommentLike, NotificationType, Post, PostImage, PostKind, PostLike,
                     Visibility)
from .notifications import clear_notification, notify
from .visibility import get_visible_post_or_404, visible_posts


def _dec(field):
    return Greatest(F(field) - 1, 0)


# ---------------------------------------------------------------- posts
def create_post(user, *, caption, visibility, kind, images, achievement=None, announcement=None):
    with transaction.atomic():
        post = Post.objects.create(author=user, caption=caption, visibility=visibility, kind=kind,
                                   achievement=achievement, announcement=announcement)
        for pos, img in enumerate(images):
            PostImage.objects.create(post=post, image=img, position=pos)
    return post


def update_post(post, *, caption=None, visibility=None, add_images=(), remove_image_ids=()):
    with transaction.atomic():
        post = Post.objects.select_for_update().get(pk=post.pk)
        if caption is not None:
            post.caption = caption
        if visibility is not None:
            post.visibility = visibility
        post.is_edited = True
        post.save()
        if remove_image_ids:
            post.images.filter(pk__in=remove_image_ids).delete()
        if add_images:
            start = (post.images.order_by("-position").values_list("position", flat=True).first() or -1) + 1
            for offset, img in enumerate(add_images):
                PostImage.objects.create(post=post, image=img, position=start + offset)
        if post.kind != PostKind.SHARE and not post.caption.strip() and not post.images.exists():
            raise DRFValidationError({"caption": ["A post needs text or at least one image."]})
    return post


def delete_post(post):
    with transaction.atomic():
        if post.shared_from_id:
            Post.objects.filter(pk=post.shared_from_id).update(share_count=_dec("share_count"))
        post.delete()


# ---------------------------------------------------------------- likes
def like_post(user, post_id):
    post = get_visible_post_or_404(user, post_id)
    with transaction.atomic():
        try:
            with transaction.atomic():
                PostLike.objects.create(post=post, user=user)
        except IntegrityError:
            raise Conflict("You already liked this post.")
        Post.objects.filter(pk=post.pk).update(like_count=F("like_count") + 1)
    notify(post.author, user, NotificationType.POST_LIKE, post=post)
    post.refresh_from_db(fields=["like_count"])
    return post


def unlike_post(user, post_id):
    post = get_visible_post_or_404(user, post_id)
    with transaction.atomic():
        deleted, _ = PostLike.objects.filter(post=post, user=user).delete()
        if not deleted:
            raise Conflict("You have not liked this post.")
        Post.objects.filter(pk=post.pk).update(like_count=_dec("like_count"))
    clear_notification(post.author, user, NotificationType.POST_LIKE, post=post)
    post.refresh_from_db(fields=["like_count"])
    return post


# ---------------------------------------------------------------- comments
def add_comment(user, post_id, body, parent_id=None):
    post = get_visible_post_or_404(user, post_id)
    parent = None
    if parent_id is not None:
        parent = Comment.objects.filter(pk=parent_id, post=post).select_related("author").first()
        if parent is None:
            raise NotFound("Comment not found.")
        if parent.parent_id is not None:
            raise DRFValidationError({"parent": ["Replies can only be added to top-level comments."]})
        from friends.selectors import is_blocked_between
        if is_blocked_between(user, parent.author_id):
            raise PermissionDenied("You can't reply to this comment.")
    with transaction.atomic():
        comment = Comment.objects.create(post=post, author=user, body=body, parent=parent)
        Post.objects.filter(pk=post.pk).update(comment_count=F("comment_count") + 1)
    if parent is not None:
        notify(parent.author, user, NotificationType.COMMENT_REPLY, post=post)
    if parent is None or parent.author_id != post.author_id:
        notify(post.author, user, NotificationType.POST_COMMENT, post=post)
    return comment


def get_comment_for_user(user, comment_id):
    """Comment, but only if its post is visible to `user`."""
    comment = Comment.objects.select_related("post", "author", "author__user_profile").filter(pk=comment_id).first()
    if comment is None or not visible_posts(user).filter(pk=comment.post_id).exists():
        raise NotFound("Comment not found.")
    from friends.selectors import is_blocked_between
    if is_blocked_between(user, comment.author_id):
        raise NotFound("Comment not found.")
    return comment


def edit_comment(user, comment_id, body):
    comment = get_comment_for_user(user, comment_id)
    if comment.author_id != user.pk:
        raise PermissionDenied("You can only edit your own comments.")
    comment.body = body
    comment.is_edited = True
    comment.save(update_fields=["body", "is_edited", "updated_at"])
    return comment


def delete_comment(user, comment_id):
    comment = get_comment_for_user(user, comment_id)
    # the comment's author, or the post's owner (moderating their own post), may delete it
    if comment.author_id != user.pk and comment.post.author_id != user.pk:
        raise PermissionDenied("You can only delete your own comments.")
    with transaction.atomic():
        removed = 1 + comment.replies.count()
        post_id = comment.post_id
        comment.delete()
        Post.objects.filter(pk=post_id).update(comment_count=Greatest(F("comment_count") - removed, 0))


def like_comment(user, comment_id):
    comment = get_comment_for_user(user, comment_id)
    with transaction.atomic():
        try:
            with transaction.atomic():
                CommentLike.objects.create(comment=comment, user=user)
        except IntegrityError:
            raise Conflict("You already liked this comment.")
        Comment.objects.filter(pk=comment.pk).update(like_count=F("like_count") + 1)
    notify(comment.author, user, NotificationType.COMMENT_LIKE, post=comment.post)
    comment.refresh_from_db(fields=["like_count"])
    return comment


def unlike_comment(user, comment_id):
    comment = get_comment_for_user(user, comment_id)
    with transaction.atomic():
        deleted, _ = CommentLike.objects.filter(comment=comment, user=user).delete()
        if not deleted:
            raise Conflict("You have not liked this comment.")
        Comment.objects.filter(pk=comment.pk).update(like_count=_dec("like_count"))
    comment.refresh_from_db(fields=["like_count"])
    return comment


# ---------------------------------------------------------------- shares
def share_post(user, post_id, caption, visibility):
    target = get_visible_post_or_404(user, post_id)          # can't share what you can't see
    original = target
    if target.shared_from_id:                                # always point at the root post
        original = visible_posts(user).filter(pk=target.shared_from_id).first()
        if original is None:
            raise NotFound("The original post is not available.")
    if original.author_id != user.pk and original.visibility != Visibility.PUBLIC:
        raise PermissionDenied("Only public posts can be shared.")
    if original.visibility == Visibility.PRIVATE:            # own private post: sharing it can't leak it
        if visibility != Visibility.PRIVATE:
            raise DRFValidationError({"visibility": ["A private post can only be shared privately."]})

    with transaction.atomic():
        try:
            with transaction.atomic():
                share = Post.objects.create(author=user, kind=PostKind.SHARE, caption=caption,
                                            visibility=visibility, shared_from=original)
        except IntegrityError:
            raise Conflict("You have already shared this post.")
        Post.objects.filter(pk=original.pk).update(share_count=F("share_count") + 1)
    notify(original.author, user, NotificationType.POST_SHARE, post=original)
    return share
