from django.db.models.signals import post_delete
from django.dispatch import receiver

from common.files import delete_file_on_commit

from .models import AchievementEvidence


@receiver(post_delete, sender=AchievementEvidence, dispatch_uid="achievements_evidence_file_cleanup")
def delete_evidence_file(sender, instance, **kwargs):
    """Private evidence files disappear after commit whenever their row does (incl. cascades)."""
    delete_file_on_commit(instance.file)
