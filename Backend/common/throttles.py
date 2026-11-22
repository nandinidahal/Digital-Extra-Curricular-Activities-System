"""
Per-user rate limits configured from settings, the same pattern Social/Friends/Messaging use.

    class AnnouncementWriteThrottle(SettingsScopedThrottle):
        rates_setting = "ANNOUNCEMENTS_THROTTLE_RATES"
        scope = "announcement_write"

Reads (GET/HEAD/OPTIONS) are never throttled; DELETE is not throttled unless `throttle_delete`.
Anonymous requests are throttled by IP.
"""
from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle

_READ_METHODS = {"GET", "HEAD", "OPTIONS"}


class SettingsScopedThrottle(SimpleRateThrottle):
    rates_setting = None
    default_rate = "120/hour"
    throttle_delete = False

    def get_rate(self):
        rates = getattr(settings, self.rates_setting, None) or {}
        return rates.get(self.scope, self.default_rate)

    def allow_request(self, request, view):
        if request.method in _READ_METHODS or (request.method == "DELETE" and not self.throttle_delete):
            return True
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = str(request.user.pk)
        else:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}
