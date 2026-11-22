"""
Per-user rate limits, shared by REST and WebSocket (same cache keys), so switching transport
does not reset a limit. Rates: settings.MESSAGING_THROTTLE_RATES (read at request time).
Reads and DELETE are never throttled.
"""
from types import SimpleNamespace

from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle

DEFAULT_RATES = {
    "messaging_send": "60/min",
    "messaging_action": "300/min",
    "messaging_upload": "60/hour",
    "messaging_ws_event": "120/min",
}
_UNTHROTTLED_METHODS = {"GET", "HEAD", "OPTIONS", "DELETE"}


class _MessagingThrottle(SimpleRateThrottle):
    def get_rate(self):
        rates = getattr(settings, "MESSAGING_THROTTLE_RATES", DEFAULT_RATES)
        return rates.get(self.scope, DEFAULT_RATES[self.scope])

    def allow_request(self, request, view):
        if request.method in _UNTHROTTLED_METHODS:
            return True
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return None
        return self.cache_format % {"scope": self.scope, "ident": str(request.user.pk)}


class MessageSendThrottle(_MessagingThrottle):
    scope = "messaging_send"


class MessageActionThrottle(_MessagingThrottle):
    scope = "messaging_action"


class AttachmentUploadThrottle(_MessagingThrottle):
    scope = "messaging_upload"

    def allow_request(self, request, view):
        # Only count requests that actually carry files.
        if request.method in _UNTHROTTLED_METHODS or not request.FILES:
            return True
        return super().allow_request(request, view)


class WebSocketEventThrottle(_MessagingThrottle):
    scope = "messaging_ws_event"


def check_rate(throttle_class, user):
    """
    Use a REST throttle outside a request (WebSocket). Returns (allowed, wait_seconds).
    """
    throttle = throttle_class()
    allowed = throttle.allow_request(SimpleNamespace(user=user, method="POST", FILES=None), None)
    return allowed, (None if allowed else throttle.wait())
