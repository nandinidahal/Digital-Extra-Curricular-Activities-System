"""
Online / last-seen tracking.

Live state lives in the cache (Redis in production - required when there is more than one
server process), never in PostgreSQL:

    messaging:online:<user>  -> timestamp, expires after MESSAGING_PRESENCE_TTL_SECONDS
    messaging:conns:<user>   -> number of open WebSocket connections (all devices)

* A connection makes the user online. Heartbeats (sent by the client every ~25 s, and only
  while the tab is visible and the user is active) keep the online key alive.
* An open but idle tab therefore does NOT keep a user online forever: once heartbeats stop the
  key expires and the user is reported offline.
* When the LAST connection closes, the user goes offline and `UserPresence.last_seen_at` is
  written - the only database write presence ever does.
* A crashed server can leave the connection counter too high; the online key still expires,
  and the next connection resets the counter.

Visibility (`presence_visible`) is privacy-aware: blocks always hide presence, and
MESSAGING_PRESENCE_VISIBILITY chooses who else may see it: "friends" (default),
"participants" (anyone sharing a conversation) or "nobody".
"""
import time
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from friends import services as friends

from .models import UserPresence

_ONLINE = "messaging:online:%s"
_CONNS = "messaging:conns:%s"


def ttl():
    return max(10, int(getattr(settings, "MESSAGING_PRESENCE_TTL_SECONDS", 70)))


def _counter_ttl():
    return ttl() * 20


def connect(user_id):
    """Register one connection. Returns True when the user just came online."""
    was_online = cache.get(_ONLINE % user_id) is not None
    if not was_online:
        cache.set(_CONNS % user_id, 0, _counter_ttl())  # heal a stale counter
    try:
        cache.incr(_CONNS % user_id)
    except ValueError:
        cache.set(_CONNS % user_id, 1, _counter_ttl())
    cache.set(_ONLINE % user_id, time.time(), ttl())
    return not was_online


def heartbeat(user_id):
    """Refresh the online state. Returns True when the user had expired and is back online."""
    was_online = cache.get(_ONLINE % user_id) is not None
    cache.set(_ONLINE % user_id, time.time(), ttl())
    cache.touch(_CONNS % user_id, _counter_ttl())
    return not was_online


def disconnect(user_id):
    """Unregister one connection. Returns True when that was the user's last connection."""
    try:
        remaining = cache.decr(_CONNS % user_id)
    except ValueError:
        remaining = 0
    if remaining > 0:
        return False
    cache.delete_many([_ONLINE % user_id, _CONNS % user_id])
    UserPresence.objects.update_or_create(user_id=user_id, defaults={"last_seen_at": timezone.now()})
    return True


def online_user_ids(user_ids):
    keys = {(_ONLINE % uid): uid for uid in user_ids}
    found = cache.get_many(list(keys))
    return {keys[key] for key in found}


def presence_visible(viewer_id, target_id, *, friend_ids=None, hidden_ids=None):
    """May `viewer` see `target`'s presence? Pass pre-fetched sets when checking many users."""
    if viewer_id == target_id:
        return True
    policy = getattr(settings, "MESSAGING_PRESENCE_VISIBILITY", "friends")
    if policy == "nobody":
        return False
    hidden = hidden_ids if hidden_ids is not None else friends.get_hidden_user_ids(viewer_id)
    if target_id in hidden:
        return False
    if policy == "participants":
        return True  # callers only ask about people who share a conversation with the viewer
    friend_set = friend_ids if friend_ids is not None else friends.get_friend_ids(viewer_id)
    return target_id in friend_set


def presence_for(viewer_id, target_ids):
    """
    {target_id: {"is_online": bool | None, "last_seen_at": datetime | None}}
    Hidden presence is reported as None/None (indistinguishable from "unknown").
    Costs at most 5 queries + 1 cache round-trip for any number of users.
    """
    target_ids = list({*target_ids})
    if not target_ids:
        return {}
    friend_ids = friends.get_friend_ids(viewer_id)
    hidden_ids = friends.get_hidden_user_ids(viewer_id)
    visible = [
        t for t in target_ids
        if presence_visible(viewer_id, t, friend_ids=friend_ids, hidden_ids=hidden_ids)
    ]
    online = online_user_ids(visible)
    offline = [t for t in visible if t not in online]
    last_seen = dict(
        UserPresence.objects.filter(user_id__in=offline).values_list("user_id", "last_seen_at")
    ) if offline else {}
    result = {}
    for t in target_ids:
        if t not in visible:
            result[t] = {"is_online": None, "last_seen_at": None}
        elif t in online:
            result[t] = {"is_online": True, "last_seen_at": None}
        else:
            result[t] = {"is_online": False, "last_seen_at": last_seen.get(t)}
    return result
