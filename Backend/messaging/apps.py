from django.apps import AppConfig


class MessagingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"  # every Messaging model uses a UUID primary key
    name = "messaging"
    verbose_name = "Messaging"

    def ready(self):
        from . import receivers  # noqa: F401  (friends/block integration + file cleanup)
