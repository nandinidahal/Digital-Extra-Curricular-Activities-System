import logging

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import AchievementDocument

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=AchievementDocument)
def delete_stored_file(sender, instance, **kwargs):
    """Remove the stored file once the row deletion has committed.

    Fires for every way a document can disappear: removed/replaced via the API, the
    achievement or the owner being deleted (cascade), or deletion in the admin.
    """
    if not instance.file:
        return
    storage, name = instance.file.storage, instance.file.name

    def _delete():
        try:
            storage.delete(name)
        except Exception:  # never let clean-up break a request
            logger.exception("Could not delete achievement file %s", name)

    transaction.on_commit(_delete)
