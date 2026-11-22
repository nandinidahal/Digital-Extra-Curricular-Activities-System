from django.apps import AppConfig


class FriendsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"  # every Friends model uses a UUID primary key
    name = "friends"
    verbose_name = "Friends"
