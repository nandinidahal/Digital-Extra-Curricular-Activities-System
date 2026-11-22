from django.apps import AppConfig


class SocialConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"  # every Social model uses a UUID primary key
    name = "social"
    verbose_name = "Social"

    def ready(self):
        from . import signals  # noqa: F401  (connects the file-cleanup receiver)
