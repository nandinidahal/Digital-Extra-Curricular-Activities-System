from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import PostMedia
from .services import _delete_stored_file


@receiver(post_delete, sender=PostMedia, dispatch_uid="social_cleanup_media_files")
def delete_file_with_media(sender, instance, **kwargs):
    """
    Whenever a PostMedia row disappears (attachment removed, post deleted, user deleted,
    cascade), its file is removed from storage after the transaction commits, so a rolled-back
    delete never loses a file.
    """
    name = instance.image.name
    if not name:
        return
    storage = instance.image.storage
    transaction.on_commit(lambda: _delete_stored_file(storage, name))
