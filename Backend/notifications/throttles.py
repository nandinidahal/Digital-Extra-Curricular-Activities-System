from common.throttles import SettingsScopedThrottle


class NotificationActionThrottle(SettingsScopedThrottle):
    rates_setting = "NOTIFICATIONS_THROTTLE_RATES"
    scope = "notification_action"
    default_rate = "600/hour"
