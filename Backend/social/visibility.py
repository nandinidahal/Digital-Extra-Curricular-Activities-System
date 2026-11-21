"""
Single source of truth for "who may see what". Every read path (feed, detail, comments, likes,
share, profile posts) goes through visible_posts_q so privacy can't be bypassed with a direct id.
"""
from django.db.models import Exists, OuterRef, Q
from rest_framework.exceptions import NotFound

from friends.selectors import blocked_id_subqueries, friend_id_subqueries

from .models import Post, PostLike, Visibility


def visible_posts_q(user):
    fa, fb = friend_id_subqueries(user)
    ba, bb = blocked_id_subqueries(user)
    allowed = (
        Q(author=user)
        | Q(visibility=Visibility.PUBLIC)
        | (Q(visibility=Visibility.FRIENDS) & (Q(author_id__in=fa) | Q(author_id__in=fb)))
    )
    return allowed & ~Q(author_id__in=ba) & ~Q(author_id__in=bb) & Q(author__is_active=True)


def visible_posts(user):
    return Post.objects.filter(visible_posts_q(user))


def annotate_for_viewer(qs, user):
    """Everything the post serializer needs, loaded without per-row queries."""
    return qs.annotate(
        liked_by_me=Exists(PostLike.objects.filter(post=OuterRef("pk"), user=user)),
        original_visible=Exists(Post.objects.filter(visible_posts_q(user), pk=OuterRef("shared_from_id"))),
    ).select_related(
        "author", "author__user_profile", "achievement", "announcement",
        "shared_from", "shared_from__author", "shared_from__author__user_profile",
    ).prefetch_related("images", "shared_from__images")


def get_visible_post_or_404(user, post_id, annotated=False):
    qs = visible_posts(user).filter(pk=post_id)
    if annotated:
        qs = annotate_for_viewer(qs, user)
    post = qs.first()
    if post is None:
        # 404, not 403: don't confirm that a private post exists
        raise NotFound("Post not found.")
    return post


def can_view_user_content(viewer, target):
    """Profile-level gate: blocked pairs and inactive accounts are invisible to each other."""
    from friends.selectors import is_blocked_between
    if viewer.pk == target.pk:
        return True
    return target.is_active and not is_blocked_between(viewer, target)
