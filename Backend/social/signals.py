from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender="achievements.Achievement")
def keep_post_private_with_achievement(sender, instance, created, **kwargs):
    """A non-public achievement must never stay visible through its feed post."""
    if created or instance.visibility == "public":
        return
    from .models import Post  # local import: avoids loading models at import time
    Post.objects.filter(achievement=instance).exclude(visibility="private").update(visibility="private")
