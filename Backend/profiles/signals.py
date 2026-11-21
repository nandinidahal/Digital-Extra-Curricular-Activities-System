import logging

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import UserProfile

logger = logging.getLogger(__name__)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_delete, sender=UserProfile)
def delete_picture_file(sender, instance, **kwargs):
    """Remove the stored picture once the row deletion (e.g. the user being deleted) has committed."""
    if not instance.profile_picture:
        return
    storage, name = instance.profile_picture.storage, instance.profile_picture.name

    def _delete():
        try:
            storage.delete(name)
        except Exception:  # never let clean-up break a request
            logger.exception("Could not delete profile picture %s", name)

    transaction.on_commit(_delete)
