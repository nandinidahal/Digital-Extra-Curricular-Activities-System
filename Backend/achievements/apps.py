from django.apps import AppConfig


class AchievementsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"  # every model here uses a UUID primary key
    name = "achievements"
    verbose_name = "Achievements"

    def ready(self):
        from . import signals  # noqa: F401  (evidence file cleanup)
