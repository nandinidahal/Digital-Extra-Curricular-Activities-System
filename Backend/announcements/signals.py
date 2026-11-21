from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Announcement


def delete_stored_files(*fields):
    """Remove stored files once the surrounding transaction commits."""
    pairs = [(f.storage, f.name) for f in fields if f and f.name]

    def _cleanup():
        for storage, name in pairs:
            try:
                storage.delete(name)
            except Exception:  # pragma: no cover - never fail a request over clean-up
                pass

    if pairs:
        transaction.on_commit(_cleanup)


@receiver(post_delete, sender=Announcement)
def remove_files_on_delete(sender, instance, **kwargs):
    delete_stored_files(instance.image, instance.attachment)
