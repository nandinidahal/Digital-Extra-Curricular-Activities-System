"""Query building blocks. Every endpoint gets its queryset from here so the visibility rules
(drafts private, scheduled hidden until their time, expired excluded) live in ONE place."""
from datetime import timedelta

from django.db.models import Count, Exists, OuterRef, Q, Subquery
from django.utils import timezone

from .models import Announcement, AnnouncementStatus, Bookmark


def active_q(now=None):
    """Published, already live and not expired: what every student may see."""
    now = now or timezone.now()
    return (Q(status=AnnouncementStatus.PUBLISHED, published_at__lte=now)
            & (Q(expires_at__isnull=True) | Q(expires_at__gt=now)))


def state_q(state, now=None):
    now = now or timezone.now()
    published = Q(status=AnnouncementStatus.PUBLISHED)
    if state == "draft":
        return Q(status=AnnouncementStatus.DRAFT)
    if state == "scheduled":
        return published & Q(published_at__gt=now)
    if state == "expired":
        return published & Q(published_at__lte=now, expires_at__lte=now)
    if state == "published":
        return active_q(now)
    return Q()


def upcoming_event_q(today=None):
    """Has an event date and the event (or its last day) has not passed yet."""
    today = today or timezone.localdate()
    return Q(start_date__isnull=False) & (Q(end_date__gte=today) | Q(end_date__isnull=True, start_date__gte=today))


def past_event_q(today=None):
    today = today or timezone.localdate()
    return Q(end_date__lt=today) | Q(end_date__isnull=True, start_date__lt=today)


def upcoming_deadline_q(today=None):
    today = today or timezone.localdate()
    return Q(deadline__isnull=False, deadline__gte=today)


def _decorate(qs, user):
    """select_related + real engagement data in the same query (no N+1)."""
    return qs.select_related("category", "published_by").defer("published_by__password").annotate(
        bookmark_count=Count("bookmarks", distinct=True),
        is_bookmarked=Exists(Bookmark.objects.filter(user=user, announcement=OuterRef("pk"))),
    )


def public_queryset(user):
    """Announcements every authenticated student can discover."""
    return _decorate(Announcement.objects.filter(active_q()), user)


def visible_queryset(user):
    """What this user may open by id: public ones plus everything they authored."""
    return _decorate(Announcement.objects.filter(active_q() | Q(published_by=user)), user)


def owned_queryset(user):
    return _decorate(Announcement.objects.filter(published_by=user), user)


def bookmarked_queryset(user):
    mine = Bookmark.objects.filter(user=user, announcement=OuterRef("pk"))
    return public_queryset(user).filter(Exists(mine)).annotate(
        bookmarked_at=Subquery(mine.values("created_at")[:1])
    )


def candidate_q(now=None, today=None, recent_days=90, event_horizon=30, deadline_horizon=14):
    """Bounded pool for ranking: recent + featured + events/deadlines that are close."""
    now = now or timezone.now()
    today = today or timezone.localdate()
    return (
        Q(published_at__gte=now - timedelta(days=recent_days))
        | Q(is_featured=True)
        | (upcoming_event_q(today) & Q(start_date__lte=today + timedelta(days=event_horizon)))
        | Q(deadline__gte=today, deadline__lte=today + timedelta(days=deadline_horizon))
    )
