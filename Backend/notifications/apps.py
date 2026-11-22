from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"  # every model here uses a UUID primary key
    name = "notifications"
    verbose_name = "Notifications"

    def ready(self):
        # Listens to the integration signals Accounts, Friends and Messaging already publish.
        from . import receivers  # noqa: F401
