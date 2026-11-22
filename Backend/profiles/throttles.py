from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle

DEFAULT_RATES = {"profile_upload": "30/hour"}


class ProfileUploadThrottle(SimpleRateThrottle):
    """Limits image uploads/removals per user (image processing is the costly part)."""

    scope = "profile_upload"

    def get_rate(self):
        rates = getattr(settings, "PROFILE_THROTTLE_RATES", DEFAULT_RATES)
        return rates.get(self.scope, DEFAULT_RATES[self.scope])

    def get_cache_key(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return None
        return self.cache_format % {"scope": self.scope, "ident": str(request.user.pk)}
