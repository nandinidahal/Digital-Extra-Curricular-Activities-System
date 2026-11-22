"""
Integration with other modules (connected in MessagingConfig.ready()).

* Friends events -> push the new messaging permission state to both users in real time
  (friend accepted = limit lifted; removed/blocked = limit or block applies again).
  Friends sends its signals after commit, so these run on committed data.
* Attachment rows deleted -> delete the stored file after the transaction commits.
"""
import logging

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from friends import signals as friends_signals

from . import events
from .models import MessageAttachment

logger = logging.getLogger("messaging")


def _safe(func, *args):
    try:
        func(*args)
    except Exception:  # integration must never break the Friends action
        logger.exception("Messaging: reacting to a Friends event failed")


@receiver(friends_signals.friend_request_accepted, dispatch_uid="messaging_friend_accepted")
def on_friend_accepted(sender, friendship, **kwargs):
    _safe(events.relationship_changed, friendship.user1_id, friendship.user2_id)


@receiver(friends_signals.friend_removed, dispatch_uid="messaging_friend_removed")
def on_friend_removed(sender, user_id, other_user_id, **kwargs):
    _safe(events.relationship_changed, user_id, other_user_id)


@receiver(friends_signals.user_blocked, dispatch_uid="messaging_user_blocked")
def on_user_blocked(sender, block, **kwargs):
    _safe(events.relationship_changed, block.blocker_id, block.blocked_id)


@receiver(friends_signals.user_unblocked, dispatch_uid="messaging_user_unblocked")
def on_user_unblocked(sender, blocker_id, blocked_id, **kwargs):
    _safe(events.relationship_changed, blocker_id, blocked_id)


@receiver(post_delete, sender=MessageAttachment, dispatch_uid="messaging_attachment_file_cleanup")
def delete_attachment_file(sender, instance, **kwargs):
    name = instance.file.name if instance.file else None
    if not name:
        return
    storage = instance.file.storage

    def _delete():
        try:
            storage.delete(name)
        except Exception:
            logger.warning("Messaging: could not delete attachment file %s", name)

    transaction.on_commit(_delete)
