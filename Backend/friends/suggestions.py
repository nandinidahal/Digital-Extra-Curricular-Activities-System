"""
Friend suggestions: a transparent score, computed on a bounded candidate pool (no ML).

score = 10 * mutual friends          (dominant signal)
      +  5 * same institution
      +  3 * same department
      +  2 * shared interests/skills (capped at 5 shared)
      +  3 * shared event participation (posted about the same announcement), capped

Candidate pool (each part is capped so cost doesn't grow with the user table):
friends-of-friends, same institution, same department, and the newest members as a cold-start fallback.
Excluded in SQL: self, friends, pending requests (either direction), blocked (either direction), inactive.
"""
from collections import Counter

from django.contrib.auth import get_user_model
from django.db.models import Q

from profiles.models import UserProfile
from social.models import Post

from .models import Friendship, FriendRequest, RequestStatus
from .selectors import blocked_id_subqueries, friend_id_subqueries

User = get_user_model()

POOL_FOF = 200
POOL_SAME_GROUP = 150
POOL_RECENT = 50


def _excluded_user_ids(user):
    excluded = {user.pk}
    for qs in (*friend_id_subqueries(user), *blocked_id_subqueries(user)):
        excluded.update(next(iter(row.values())) for row in qs)
    for sender_id, receiver_id in FriendRequest.objects.filter(status=RequestStatus.PENDING).filter(
        Q(sender=user) | Q(receiver=user)
    ).values_list("sender_id", "receiver_id"):
        excluded.update((sender_id, receiver_id))
    return excluded


def suggest_friends(user, limit=20):
    my_friends = set()
    for qs in friend_id_subqueries(user):
        my_friends.update(next(iter(row.values())) for row in qs)
    excluded = _excluded_user_ids(user)

    # mutual-friend counts via friends-of-friends (two indexed queries)
    mutual = Counter()
    if my_friends:
        for low, high in Friendship.objects.filter(
            Q(user_low__in=my_friends) | Q(user_high__in=my_friends)
        ).values_list("user_low_id", "user_high_id"):
            if low in my_friends and high not in my_friends:
                mutual[high] += 1
            elif high in my_friends and low not in my_friends:
                mutual[low] += 1
            # both in my_friends: an existing friend pair, neither is a candidate
    for uid in list(mutual):
        if uid in excluded:
            del mutual[uid]

    me = UserProfile.objects.filter(user=user).first()
    my_interests = set((me.interests if me else []) or []) | set((me.skills if me else []) or [])

    pool = {uid for uid, _ in mutual.most_common(POOL_FOF)}
    if me and me.institution:
        pool.update(UserProfile.objects.filter(institution__iexact=me.institution).exclude(user_id__in=excluded)
                    .order_by("-user_id").values_list("user_id", flat=True)[:POOL_SAME_GROUP])
    if me and me.department:
        pool.update(UserProfile.objects.filter(department__iexact=me.department).exclude(user_id__in=excluded)
                    .order_by("-user_id").values_list("user_id", flat=True)[:POOL_SAME_GROUP])
    pool.update(User.objects.filter(is_active=True).exclude(pk__in=excluded)
                .order_by("-date_joined").values_list("pk", flat=True)[:POOL_RECENT])
    pool -= excluded
    if not pool:
        return []

    my_announcements = set(Post.objects.filter(author=user, announcement__isnull=False)
                           .values_list("announcement_id", flat=True))
    shared_events = Counter()
    if my_announcements:
        for author_id in (Post.objects.filter(announcement_id__in=my_announcements, author_id__in=pool)
                          .values_list("author_id", flat=True).distinct()):
            shared_events[author_id] += 1

    users = (User.objects.filter(pk__in=pool, is_active=True).select_related("user_profile"))
    scored = []
    for cand in users:
        prof = getattr(cand, "user_profile", None)
        reasons = {}
        score = 0
        m = mutual.get(cand.pk, 0)
        if m:
            score += 10 * m
            reasons["mutual_friends"] = m
        if prof and me:
            if me.institution and prof.institution.lower() == me.institution.lower():
                score += 5
                reasons["same_institution"] = True
            if me.department and prof.department.lower() == me.department.lower():
                score += 3
                reasons["same_department"] = True
            common = my_interests & (set(prof.interests or []) | set(prof.skills or []))
            if common:
                score += 2 * min(len(common), 5)
                reasons["shared_interests"] = sorted(common)[:5]
        if shared_events.get(cand.pk):
            score += 3
            reasons["shared_activities"] = True
        scored.append((score, cand.date_joined, cand, reasons))

    scored.sort(key=lambda t: (-t[0], -t[1].timestamp(), -t[2].pk))
    return [{"user": c, "score": s, "reasons": r} for s, _, c, r in scored[:limit]]
