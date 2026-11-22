from common.throttles import SettingsScopedThrottle


class _AchievementThrottle(SettingsScopedThrottle):
    rates_setting = "ACHIEVEMENTS_THROTTLE_RATES"


class AchievementWriteThrottle(_AchievementThrottle):
    scope = "achievement_write"


class AchievementUploadThrottle(_AchievementThrottle):
    scope = "achievement_upload"


class AchievementReviewThrottle(_AchievementThrottle):
    scope = "achievement_review"
