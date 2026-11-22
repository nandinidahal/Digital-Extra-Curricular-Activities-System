from django.db.models.signals import post_delete
from django.dispatch import receiver

from common.files import delete_file_on_commit

from .models import Announcement


@receiver(post_delete, sender=Announcement, dispatch_uid="announcements_cover_cleanup")
def delete_cover_with_announcement(sender, instance, **kwargs):
    """Covers are removed after commit whenever an announcement row disappears (incl. cascades)."""
    delete_file_on_commit(instance.cover_image)
