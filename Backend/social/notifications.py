from django.utils import timezone

from .models import Notification, NotificationType


def notify(recipient, actor, type_, post=None, target_id=None):
    """
    Create a notification. Never notifies a user about their own action.
    Repeated identical, still-unread notifications are collapsed (bump the timestamp)
    so a like/unlike loop or a chatty conversation cannot flood the inbox.
    """
    if actor is not None and recipient.pk == actor.pk:
        return None
    lookup = {"recipient": recipient, "actor": actor, "type": type_, "post": post,
              "target_id": target_id, "is_read": False}
    existing = Notification.objects.filter(**lookup).first()
    if existing:
        Notification.objects.filter(pk=existing.pk).update(created_at=timezone.now())
        return existing
    return Notification.objects.create(**lookup)


def clear_notification(recipient, actor, type_, post=None, target_id=None):
    """Remove an unread notification that no longer applies (e.g. request cancelled)."""
    Notification.objects.filter(recipient=recipient, actor=actor, type=type_, post=post,
                                target_id=target_id, is_read=False).delete()
