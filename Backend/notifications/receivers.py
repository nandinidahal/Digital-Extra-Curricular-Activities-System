"""
Notifications for events published by EXISTING modules through their integration signals
(Accounts, Friends, Messaging). Those modules are not modified beyond publishing the event;
they already send their signals after commit with send_robust.

New modules (Social, Announcements, Achievements) call notifications.services.notify()
explicitly from their services instead of using signals.
"""
import logging

from django.dispatch import receiver

from accounts import signals as account_signals
from friends import signals as friend_signals
from messaging import signals as messaging_signals

from . import services
from .models import Notification

logger = logging.getLogger("notifications")


def _safe(func, **kwargs):
    try:
        return func(**kwargs)
    except Exception:  # never break the module that published the event
        logger.exception("Notifications receiver failed")
        return None


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------
@receiver(account_signals.email_verified, dispatch_uid="notifications_email_verified")
def on_email_verified(sender, user, **kwargs):
    first_time = not Notification.objects.filter(recipient=user, dedupe_key="account.welcome").exists()
    if first_time:
        _safe(
            services.create_notification, recipient=user, notification_type="account.welcome",
            dedupe_key="account.welcome", action_url="/profile/edit",
        )
    else:
        _safe(services.create_notification, recipient=user, notification_type="account.email_verified", action_url="/settings/account")


@receiver(account_signals.password_changed, dispatch_uid="notifications_password_changed")
def on_password_changed(sender, user, method, **kwargs):
    if method == "reset":
        _safe(
            services.create_notification, recipient=user, notification_type="account.security_alert",
            context={"detail": "Your password was reset and all devices were signed out. If this was not you, contact support."},
            metadata={"event": "password_reset"}, action_url="/settings/security",
        )
    else:
        _safe(services.create_notification, recipient=user, notification_type="account.password_changed", action_url="/settings/security")


# ---------------------------------------------------------------------------
# Friends
# ---------------------------------------------------------------------------
def _request_key(friend_request):
    return f"friend_request.received:{friend_request.pk}"


@receiver(friend_signals.friend_request_sent, dispatch_uid="notifications_friend_request_sent")
def on_friend_request_sent(sender, friend_request, **kwargs):
    _safe(
        services.create_notification,
        recipient=friend_request.receiver_id, actor=friend_request.sender_id,
        notification_type="friend_request.received",
        target_type="friend_request", target_id=friend_request.pk,
        metadata={"friend_request_id": friend_request.pk, "user_id": friend_request.sender_id},
        action_url="/friends/requests", dedupe_key=_request_key(friend_request),
    )


@receiver(friend_signals.friend_request_accepted, dispatch_uid="notifications_friend_request_accepted")
def on_friend_request_accepted(sender, friend_request, friendship, **kwargs):
    # The receiver acted on it: their "new request" notification is done.
    _safe(services.withdraw, recipient_id=friend_request.receiver_id, dedupe_key=_request_key(friend_request), mark_read_only=True)
    _safe(
        services.create_notification,
        recipient=friend_request.sender_id, actor=friend_request.receiver_id,
        notification_type="friend_request.accepted",
        target_type="user", target_id=friend_request.receiver_id,
        metadata={"user_id": friend_request.receiver_id},
        action_url=f"/profile/{friend_request.receiver_id}",
        dedupe_key=f"friend_request.accepted:{friend_request.pk}",
    )


@receiver(friend_signals.friend_request_rejected, dispatch_uid="notifications_friend_request_rejected")
def on_friend_request_rejected(sender, friend_request, **kwargs):
    _safe(services.withdraw, recipient_id=friend_request.receiver_id, dedupe_key=_request_key(friend_request), mark_read_only=True)
    _safe(
        services.create_notification,
        recipient=friend_request.sender_id, actor=friend_request.receiver_id,
        notification_type="friend_request.rejected",
        target_type="friend_request", target_id=friend_request.pk,
        dedupe_key=f"friend_request.rejected:{friend_request.pk}",
    )


@receiver(friend_signals.friend_request_cancelled, dispatch_uid="notifications_friend_request_cancelled")
def on_friend_request_cancelled(sender, friend_request, **kwargs):
    # A cancelled (or block-cancelled) request must disappear from the receiver's list.
    _safe(services.withdraw, recipient_id=friend_request.receiver_id, dedupe_key=_request_key(friend_request))


@receiver(friend_signals.friend_removed, dispatch_uid="notifications_friend_removed")
def on_friend_removed(sender, user_id, other_user_id, reason, **kwargs):
    if reason != "removed":
        return  # removal caused by a block is never announced (it would reveal the block)
    _safe(
        services.create_notification,
        recipient=other_user_id, actor=user_id, notification_type="friend.removed",
        target_type="user", target_id=user_id,
    )


# ---------------------------------------------------------------------------
# Messaging
# ---------------------------------------------------------------------------
def _conversation_group(conversation_id):
    return f"message.received:{conversation_id}"


@receiver(messaging_signals.message_sent, dispatch_uid="notifications_message_sent")
def on_message_sent(sender, message, sender_id, notify_user_ids, **kwargs):
    # notify_user_ids already excludes muted recipients. Message content is never copied.
    for user_id in notify_user_ids:
        _safe(
            services.create_notification,
            recipient=user_id, actor=sender_id, notification_type="message.received",
            target_type="conversation", target_id=message.conversation_id,
            metadata={"conversation_id": message.conversation_id},
            action_url=f"/messages/{message.conversation_id}",
            group_key=_conversation_group(message.conversation_id),
        )


@receiver(messaging_signals.messages_read, dispatch_uid="notifications_messages_read")
def on_messages_read(sender, conversation_id, reader_id, **kwargs):
    _safe(services.withdraw, recipient_id=reader_id, group_key=_conversation_group(conversation_id), mark_read_only=True)
