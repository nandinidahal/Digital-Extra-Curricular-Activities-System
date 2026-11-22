"""
Integration events for other modules (the future Notifications module in particular).
Messaging ANNOUNCES what happened; it stores no notifications and sends no e-mails/push.

    from django.dispatch import receiver
    from messaging.signals import message_sent

    @receiver(message_sent)
    def notify(sender, message, notify_user_ids, **kwargs):
        for user_id in notify_user_ids:      # already excludes muted recipients
            ...

Rules (same as friends.signals):
* sent AFTER the database transaction commits (receivers never see rolled-back data);
* sent with send_robust: a failing receiver is logged and never breaks messaging;
* sent exactly once per event: an idempotent retry (same client_id) does NOT re-send.
"""
from django.dispatch import Signal

# conversation=<Conversation>, created_by_id=<UUID>, participant_ids=[UUID]
conversation_started = Signal()
# message=<Message>, sender_id=<UUID>, recipient_ids=[UUID],
# notify_user_ids=[UUID]  (recipients who have NOT muted the conversation)
message_sent = Signal()
# message=<Message>, editor_id=<UUID>
message_edited = Signal()
# message=<Message>, deleted_by_id=<UUID>   (delete for everyone only)
message_deleted = Signal()
# conversation_id=<UUID>, reader_id=<UUID>, message_ids=[UUID], read_at=<datetime>
messages_read = Signal()
# message=<Message>, user_id=<UUID>, reaction_type=<str | None>  (None = removed)
reaction_changed = Signal()
