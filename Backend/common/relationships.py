"""
Friendship / block helpers for querysets. The Friends module stays the single source of truth;
these are thin wrappers so other modules never re-implement block or friend rules.
"""
from .permissions import is_authenticated


def hidden_user_ids(viewer):
    """Users the viewer must never see because of a block in EITHER direction (empty for visitors)."""
    if not is_authenticated(viewer):
        return set()
    from friends.services import get_hidden_user_ids

    return get_hidden_user_ids(viewer.pk)


def friend_ids(viewer):
    if not is_authenticated(viewer):
        return set()
    from friends.services import get_friend_ids

    return get_friend_ids(viewer.pk)


def is_blocked_between(a, b):
    if a is None or b is None:
        return False
    from friends.services import is_blocked_between as _blocked

    a_id, b_id = getattr(a, "pk", a), getattr(b, "pk", b)
    return a_id != b_id and _blocked(a_id, b_id)


def are_friends(a, b):
    if a is None or b is None:
        return False
    from friends.services import are_friends as _friends

    return _friends(getattr(a, "pk", a), getattr(b, "pk", b))


def exclude_hidden(queryset, viewer, field="author"):
    """Drop rows whose `field` user is blocked by / blocking the viewer."""
    hidden = hidden_user_ids(viewer)
    if not hidden:
        return queryset
    return queryset.exclude(**{f"{field}_id__in": hidden})
