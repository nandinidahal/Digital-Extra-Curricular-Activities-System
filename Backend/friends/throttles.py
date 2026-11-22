"""
Per-user rate limits for the write endpoints. Reads and DELETE are never throttled
(removing a friend or a block must always be possible).
Rates live in settings.FRIENDS_THROTTLE_RATES (read at request time).
"""
from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle

DEFAULT_RATES = {
    "friends_request": "30/hour",  # sending friend requests (the abuse-prone action)
    "friends_action": "300/hour",  # accept / reject / cancel / block
}
_UNTHROTTLED_METHODS = {"GET", "HEAD", "OPTIONS", "DELETE"}


class _FriendsThrottle(SimpleRateThrottle):
    def get_rate(self):
        rates = getattr(settings, "FRIENDS_THROTTLE_RATES", DEFAULT_RATES)
        return rates.get(self.scope, DEFAULT_RATES[self.scope])

    def allow_request(self, request, view):
        if request.method in _UNTHROTTLED_METHODS:
            return True
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return None
        return self.cache_format % {"scope": self.scope, "ident": str(request.user.pk)}


class FriendRequestSendThrottle(_FriendsThrottle):
    scope = "friends_request"


class FriendActionThrottle(_FriendsThrottle):
    scope = "friends_action"
