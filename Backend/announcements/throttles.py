from common.throttles import SettingsScopedThrottle


class _AnnouncementThrottle(SettingsScopedThrottle):
    rates_setting = "ANNOUNCEMENTS_THROTTLE_RATES"


class AnnouncementWriteThrottle(_AnnouncementThrottle):
    scope = "announcement_write"


class AnnouncementInteractionThrottle(_AnnouncementThrottle):
    scope = "announcement_interaction"


class AnnouncementReportThrottle(_AnnouncementThrottle):
    scope = "announcement_report"


class AnnouncementSearchThrottle(_AnnouncementThrottle):
    scope = "announcement_search"

    def allow_request(self, request, view):  # searching is a GET, but it is still rate-limited
        from rest_framework.throttling import SimpleRateThrottle

        return SimpleRateThrottle.allow_request(self, request, view)
