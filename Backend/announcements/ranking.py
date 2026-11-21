"""Smart ranking ("recommended") for announcements.

    score = 0.30*recency + 0.25*category + 0.20*event + 0.15*deadline + 0.10*engagement
            (+ FEATURED_BOOST when the announcement is featured)

Every component is normalised to [0, 1]; the weighted sum is therefore in [0, 1] (+ the small
featured boost, so max 1.05). Components are small pure functions so each one can be replaced
or re-tuned independently. Only real database data is used.

recency     0.5 ** (age_days / 7): 1.0 when just published, 0.5 after a week, ~0 after months.
            Brand-new announcements therefore score high with zero engagement.
category    The viewer's OWN bookmark history: share of their bookmarks in the announcement's
            category relative to their most-bookmarked category. No bookmarks -> neutral 0.5 for
            every category (nothing is invented). Another student's data is never used.
event       1.0 while the event is running or starts today, falling linearly to 0 at 30 days away;
            0 for past events and for announcements without an event date (no penalty beyond
            not earning this component).
deadline    1.0 if the deadline is today, falling linearly to 0 at 14 days away; 0 if passed/none.
engagement  log(1 + bookmarks) / log(1 + max bookmarks in the candidate pool); 0 when nobody
            bookmarked anything. Log-scaling stops a viral post from drowning everything else.

Ties are broken by newest publication date, then highest id, so ordering is deterministic.
"""
import math
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from . import selectors
from .models import Bookmark

WEIGHTS = {"recency": 0.30, "category": 0.25, "event": 0.20, "deadline": 0.15, "engagement": 0.10}
FEATURED_BOOST = 0.05
RECENCY_HALF_LIFE_DAYS = 7.0
EVENT_HORIZON_DAYS = 30
DEADLINE_HORIZON_DAYS = 14
NEUTRAL_CATEGORY_SCORE = 0.5
POOL_RECENT_DAYS = 90
POOL_MAX = 1000


def recency_score(published_at, now):
    if published_at is None:
        return 0.0
    age_days = max(0.0, (now - published_at).total_seconds() / 86400)
    return 0.5 ** (age_days / RECENCY_HALF_LIFE_DAYS)


def event_score(start_date, end_date, today):
    if start_date is None:
        return 0.0
    if (end_date or start_date) < today:
        return 0.0
    if start_date <= today:
        return 1.0
    return max(0.0, 1.0 - (start_date - today).days / EVENT_HORIZON_DAYS)


def deadline_score(deadline, today):
    if deadline is None or deadline < today:
        return 0.0
    return max(0.0, 1.0 - (deadline - today).days / DEADLINE_HORIZON_DAYS)


def engagement_score(bookmark_count, max_bookmark_count):
    if bookmark_count <= 0 or max_bookmark_count <= 0:
        return 0.0
    return math.log1p(bookmark_count) / math.log1p(max_bookmark_count)


def category_affinity(user):
    """{category_id: 0..1} from the viewer's own bookmarks, or None when there is no history."""
    rows = (Bookmark.objects.filter(user=user)
            .values("announcement__category_id").annotate(n=Count("id")))
    counts = {r["announcement__category_id"]: r["n"] for r in rows if r["announcement__category_id"]}
    if not counts:
        return None
    top = max(counts.values())
    return {cid: n / top for cid, n in counts.items()}


def category_score(category_id, affinity):
    if affinity is None:
        return NEUTRAL_CATEGORY_SCORE
    return affinity.get(category_id, 0.0)


def score_breakdown(a, *, now, today, affinity, max_bookmarks):
    parts = {
        "recency": recency_score(a.published_at, now),
        "category": category_score(a.category_id, affinity),
        "event": event_score(a.start_date, a.end_date, today),
        "deadline": deadline_score(a.deadline, today),
        "engagement": engagement_score(getattr(a, "bookmark_count", 0), max_bookmarks),
    }
    total = sum(WEIGHTS[k] * v for k, v in parts.items())
    if a.is_featured:
        total += FEATURED_BOOST
    return round(total, 6), parts


def rank(queryset, user, now=None):
    """Return the (annotated) announcements of ``queryset``'s candidate pool, best first.

    Each item gets ``rank_score``. The pool is bounded (POOL_MAX) so large tables are never
    loaded fully into memory.
    """
    now = now or timezone.now()
    today = timezone.localdate(now)
    pool = (queryset.filter(selectors.candidate_q(now, today, POOL_RECENT_DAYS, EVENT_HORIZON_DAYS, DEADLINE_HORIZON_DAYS))
            .order_by("-published_at", "-id")[:POOL_MAX])
    items = list(pool)
    max_bookmarks = max((a.bookmark_count for a in items), default=0)
    affinity = category_affinity(user)
    for a in items:
        a.rank_score, _ = score_breakdown(a, now=now, today=today, affinity=affinity, max_bookmarks=max_bookmarks)
    items.sort(key=lambda a: (-a.rank_score, -a.published_at.timestamp(), -a.id))
    return items
