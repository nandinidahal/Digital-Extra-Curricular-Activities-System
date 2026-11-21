"""
Feed generation.

latest (default): strictly chronological, keyset (cursor) pagination -> O(page) per request,
                  stable while new posts arrive, served by post_created_idx.
ranked (opt-in) : a bounded candidate window (last 14 days, max 150 visible posts) scored in memory,
                  then page-number paginated. Bounded on purpose: ranking never scans the whole table.
"""
import math
from datetime import timedelta

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from friends.selectors import friend_id_subqueries, friend_ids

from .models import Post, PostKind
from .visibility import annotate_for_viewer, visible_posts_q

RANK_WINDOW_DAYS = 14
RANK_WINDOW_SIZE = 150


def feed_queryset(user, scope="all"):
    visible = visible_posts_q(user)
    qs = Post.objects.filter(visible).exclude(kind=PostKind.SHARE, shared_from__isnull=True)

    if scope == "friends":
        fa, fb = friend_id_subqueries(user)
        qs = qs.filter(Q(author_id__in=fa) | Q(author_id__in=fb))

    # Shares: hide orphaned shares and shares whose original this viewer may not see...
    original_visible = Exists(Post.objects.filter(visible, pk=OuterRef("shared_from_id")))
    qs = qs.filter(Q(shared_from__isnull=True) | (Q(kind=PostKind.SHARE) & original_visible))
    # ...and collapse repeated shares of the same original into the newest one (no duplicates).
    newer_share = Post.objects.filter(visible, shared_from_id=OuterRef("shared_from_id")).filter(
        Q(created_at__gt=OuterRef("created_at")) | Q(created_at=OuterRef("created_at"), id__gt=OuterRef("id"))
    )
    qs = qs.filter(Q(shared_from__isnull=True) | ~Exists(newer_share))
    return qs


def latest_feed(user, scope="all"):
    return annotate_for_viewer(feed_queryset(user, scope), user)


def _score(post, now, friends, interests):
    age_hours = max((now - post.created_at).total_seconds() / 3600.0, 0.0)
    recency = 1.0 / (1.0 + age_hours / 12.0)                        # 1.0 fresh -> 0.5 at 12h -> ~0.08 at 6d
    friend_boost = 0.6 if post.author_id in friends else 0.0
    engagement = 0.15 * math.log1p(post.like_count + 2 * post.comment_count + 3 * post.share_count)
    relevance = 0.0
    if interests:
        text = (post.caption or "").lower()
        if any(i in text for i in interests):
            relevance += 0.25
    if post.kind in (PostKind.ACHIEVEMENT, PostKind.EVENT, PostKind.ACTIVITY, PostKind.EDUCATION):
        relevance += 0.15                                            # extracurricular content is the point of the platform
    return recency + friend_boost + engagement + relevance


def ranked_feed(user, scope="all"):
    """Returns a list of annotated posts, best first."""
    from profiles.models import UserProfile

    cutoff = timezone.now() - timedelta(days=RANK_WINDOW_DAYS)
    qs = annotate_for_viewer(feed_queryset(user, scope).filter(created_at__gte=cutoff), user)
    posts = list(qs.order_by("-created_at", "-id")[:RANK_WINDOW_SIZE])
    friends = friend_ids(user)
    profile = UserProfile.objects.filter(user=user).first()
    interests = [i for i in ((profile.interests if profile else []) or []) if i]
    now = timezone.now()
    posts.sort(key=lambda p: (_score(p, now, friends, interests), p.created_at, p.pk), reverse=True)
    return posts
