"""Read-side helpers. Everything returns querysets / subqueries so callers stay in the database."""
from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import Block, Friendship

User = get_user_model()


def ordered_pair(a_id, b_id):
    return (a_id, b_id) if a_id < b_id else (b_id, a_id)


def friend_id_subqueries(user):
    """Two `values()` subqueries which together are the ids of `user`'s friends."""
    return (
        Friendship.objects.filter(user_low=user).values("user_high_id"),
        Friendship.objects.filter(user_high=user).values("user_low_id"),
    )


def blocked_id_subqueries(user):
    """Ids of users `user` blocked, and of users who blocked `user`."""
    return (
        Block.objects.filter(blocker=user).values("blocked_id"),
        Block.objects.filter(blocked=user).values("blocker_id"),
    )


def friends_of(user):
    a, b = friend_id_subqueries(user)
    return User.objects.filter(Q(pk__in=a) | Q(pk__in=b))


def friend_ids(user):
    return set(friends_of(user).values_list("pk", flat=True))


def blocked_ids(user):
    a, b = blocked_id_subqueries(user)
    return {row["blocked_id"] for row in a} | {row["blocker_id"] for row in b}


def mutual_friends(a, b):
    return friends_of(a).filter(pk__in=friends_of(b).values("pk"))


def are_friends(a, b):
    low, high = ordered_pair(a.pk if hasattr(a, "pk") else a, b.pk if hasattr(b, "pk") else b)
    return Friendship.objects.filter(user_low_id=low, user_high_id=high).exists()


def is_blocked_between(a, b):
    a_id = a.pk if hasattr(a, "pk") else a
    b_id = b.pk if hasattr(b, "pk") else b
    return Block.objects.filter(Q(blocker_id=a_id, blocked_id=b_id) | Q(blocker_id=b_id, blocked_id=a_id)).exists()
