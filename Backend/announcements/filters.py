"""Validated query parameters, filtering, PostgreSQL-friendly search and sorting.

Everything goes through the Django ORM (parameterised), so user input never reaches raw SQL.
"""
import operator
import re
from datetime import datetime, time, timedelta
from functools import reduce

from django.db.models import Case, F, IntegerField, Q, Value, When
from django.utils import timezone
from rest_framework import serializers

from . import selectors
from .models import ActivityType

MAX_SEARCH_TERMS = 8
MAX_TERM_LENGTH = 64
SORT_CHOICES = ("latest", "oldest", "relevant", "event_date", "deadline", "bookmarks")
STATE_CHOICES = ("draft", "scheduled", "published", "expired")

# (field, weight): how much a match in that field contributes to text relevance.
SEARCH_FIELDS = (
    ("title", 5), ("activity_name", 3), ("keywords", 3), ("category__name", 2),
    ("location", 1), ("country", 1), ("short_description", 1), ("full_description", 1),
)


class AnnouncementQuerySerializer(serializers.Serializer):
    """Validates every query parameter; invalid values produce a 400 with field messages."""

    q = serializers.CharField(required=False, allow_blank=True, max_length=200)
    category = serializers.CharField(required=False, max_length=90)  # id or slug
    author = serializers.IntegerField(required=False, min_value=1)
    event = serializers.ChoiceField(choices=("upcoming", "past"), required=False)
    deadline = serializers.ChoiceField(choices=("upcoming",), required=False)
    featured = serializers.ChoiceField(choices=("true", "false", "1", "0"), required=False)
    important = serializers.ChoiceField(choices=("true", "false", "1", "0"), required=False)
    activity_type = serializers.ChoiceField(choices=ActivityType.values, required=False)
    published_from = serializers.DateField(required=False)
    published_to = serializers.DateField(required=False)
    event_from = serializers.DateField(required=False)
    event_to = serializers.DateField(required=False)
    sort = serializers.ChoiceField(choices=SORT_CHOICES, required=False)
    state = serializers.ChoiceField(choices=STATE_CHOICES, required=False)  # owner lists only

    def validate(self, attrs):
        for lo, hi in (("published_from", "published_to"), ("event_from", "event_to")):
            if lo in attrs and hi in attrs and attrs[lo] > attrs[hi]:
                raise serializers.ValidationError({hi: [f"Must not be earlier than {lo}."]})
        return attrs


def _bool(value):
    return value in ("true", "1")


def _day_start(d):
    return timezone.make_aware(datetime.combine(d, time.min))


def apply_filters(qs, p, today=None):
    today = today or timezone.localdate()
    if "category" in p:
        c = p["category"].strip()
        qs = qs.filter(category_id=int(c)) if c.isdigit() else qs.filter(category__slug__iexact=c)
    if "author" in p:
        qs = qs.filter(published_by_id=p["author"])
    if p.get("event") == "upcoming":
        qs = qs.filter(selectors.upcoming_event_q(today))
    elif p.get("event") == "past":
        qs = qs.filter(selectors.past_event_q(today))
    if p.get("deadline") == "upcoming":
        qs = qs.filter(selectors.upcoming_deadline_q(today))
    if "featured" in p:
        qs = qs.filter(is_featured=_bool(p["featured"]))
    if "important" in p:
        qs = qs.filter(is_important=_bool(p["important"]))
    if "activity_type" in p:
        qs = qs.filter(activity_type=p["activity_type"])
    if "published_from" in p:
        qs = qs.filter(published_at__gte=_day_start(p["published_from"]))
    if "published_to" in p:
        qs = qs.filter(published_at__lt=_day_start(p["published_to"] + timedelta(days=1)))
    if "event_from" in p or "event_to" in p:
        qs = qs.filter(start_date__isnull=False)
        if "event_to" in p:
            qs = qs.filter(start_date__lte=p["event_to"])
        if "event_from" in p:
            f = p["event_from"]
            qs = qs.filter(Q(end_date__gte=f) | Q(end_date__isnull=True, start_date__gte=f))
    return qs


def search_terms(q):
    return [t[:MAX_TERM_LENGTH] for t in re.split(r"\s+", (q or "").strip()) if t][:MAX_SEARCH_TERMS]


def apply_search(qs, q):
    """Case-insensitive, partial-word, multi-word search.

    Every term must match (substring) in at least one searchable field; a weighted
    ``search_score`` is annotated so results can be sorted by relevance. Returns (qs, searched).
    """
    terms = search_terms(q)
    if not terms:
        return qs, False
    parts = []
    for term in terms:
        any_field = Q()
        for field, weight in SEARCH_FIELDS:
            any_field |= Q(**{f"{field}__icontains": term})
            parts.append(Case(When(**{f"{field}__icontains": term}, then=Value(weight)),
                              default=Value(0), output_field=IntegerField()))
        qs = qs.filter(any_field)
    return qs.annotate(search_score=reduce(operator.add, parts)), True


def apply_sort(qs, sort, today=None, searched=False):
    today = today or timezone.localdate()
    newest = F("published_at").desc(nulls_last=True)
    if sort == "oldest":
        return qs.order_by(F("published_at").asc(nulls_last=True), "id")
    if sort == "event_date":  # upcoming/ongoing first (soonest first), then past, then none
        group = Case(When(selectors.upcoming_event_q(today), then=Value(0)),
                     When(start_date__isnull=False, then=Value(1)), default=Value(2),
                     output_field=IntegerField())
        return qs.annotate(event_group=group).order_by("event_group", F("start_date").asc(nulls_last=True), newest, "-id")
    if sort == "deadline":  # nearest upcoming deadline first, then passed, then none
        group = Case(When(selectors.upcoming_deadline_q(today), then=Value(0)),
                     When(deadline__isnull=False, then=Value(1)), default=Value(2),
                     output_field=IntegerField())
        return qs.annotate(deadline_group=group).order_by("deadline_group", F("deadline").asc(nulls_last=True), newest, "-id")
    if sort == "bookmarks":
        return qs.order_by("-bookmark_count", newest, "-id")
    if sort == "relevant" and searched:
        return qs.order_by("-search_score", newest, "-id")
    if sort == "bookmarked":   # internal: "my bookmarks", most recently bookmarked first
        return qs.order_by(F("bookmarked_at").desc(), "-id")
    if sort == "updated":      # internal: owner lists
        return qs.order_by("-updated_at", "-id")
    return qs.order_by(newest, "-id")  # latest (stable secondary sort: publication date, then id)
