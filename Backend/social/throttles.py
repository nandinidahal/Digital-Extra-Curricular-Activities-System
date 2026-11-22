"""
Per-user rate limits for the write endpoints. Reads are never throttled here
and DELETE is not throttled (removing content must always be possible).
Rates live in settings.SOCIAL_THROTTLE_RATES (read at request time).
"""
from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle

DEFAULT_RATES = {
    "social_post": "30/hour",         # create / edit posts (includes uploads)
    "social_comment": "90/hour",      # create / edit comments and replies
    "social_interaction": "600/hour", # likes, unlikes (POST), shares
    "social_report": "20/hour",       # reports
}
_UNTHROTTLED_METHODS = {"GET", "HEAD", "OPTIONS", "DELETE"}


class _SocialThrottle(SimpleRateThrottle):
    def get_rate(self):
        rates = getattr(settings, "SOCIAL_THROTTLE_RATES", DEFAULT_RATES)
        return rates.get(self.scope, DEFAULT_RATES[self.scope])

    def allow_request(self, request, view):
        if request.method in _UNTHROTTLED_METHODS:
            return True
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return None
        return self.cache_format % {"scope": self.scope, "ident": str(request.user.pk)}


class PostWriteThrottle(_SocialThrottle):
    scope = "social_post"


class CommentWriteThrottle(_SocialThrottle):
    scope = "social_comment"


class InteractionThrottle(_SocialThrottle):
    scope = "social_interaction"


class ReportThrottle(_SocialThrottle):
    scope = "social_report"
