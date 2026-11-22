from django.apps import AppConfig


class ProfilesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"  # Profile itself uses a UUID primary key
    name = "profiles"
    verbose_name = "Profiles"

    def ready(self):
        from . import signals  # noqa: F401  (connects the post_save receiver)
