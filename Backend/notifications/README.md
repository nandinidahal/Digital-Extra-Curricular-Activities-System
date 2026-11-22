# Notifications module (`/api/notifications/`, `ws/notifications/`)

One central notification system for every module. Full API/WebSocket reference: `../API_DOCUMENTATION.md` §5.

## How modules create notifications
* **New modules** (Social, Announcements, Achievements) call `notifications.services.notify(...)` / `notify_many(...)`
  explicitly from their services. Both run **after the database commit** (`transaction.on_commit`), so nothing is sent for
  a failed or rolled-back action, and errors are logged, never raised into the business action.
* **Existing modules** already publish after-commit integration signals. `receivers.py` listens to:
  Friends (`friend_request_sent/accepted/rejected/cancelled`, `friend_removed`), Messaging (`message_sent`, `messages_read`)
  and two new Accounts signals (`email_verified`, `password_changed`). Those modules are not otherwise modified.

## Rules (services.create_notification)
registered type → active recipient → never your own action (except account/security) → nothing across a block (except security) →
category preference (security cannot be disabled) → sanitised metadata (no secret-looking keys, ≤4 KB) → internal `action_url` only →
`dedupe_key` (UNIQUE per recipient: "notify once", e.g. likes, publications, reminders) or `group_key`
(one **unread** item per group: messages per conversation, comments per post) → after commit: WebSocket push + e-mail.

Specific behaviour: a cancelled friend request withdraws the receiver's notification; accepting/rejecting marks it read;
reading a conversation marks its message notification read; removal caused by a block is never announced; message text is never copied.

## Models
`Notification` (UUID, recipient, actor, type, category, title, message, metadata, target type/id, action URL, read state,
expiry, dedupe/group keys, e-mail status/attempts) and `NotificationPreference` (8 switches, created lazily, all on).

## Real-time
`/ws/notifications/` uses the project's existing JWT WebSocket middleware and origin check (`config/asgi.py` now routes
messaging **and** notifications sockets; messaging is unchanged). Group per user, derived from the JWT only.
REST stays the source of truth (clients fetch the list after reconnecting).

## E-mail
SMTP through the existing settings. Only important types, only verified addresses, preference respected (not for security),
claimed with a conditional UPDATE so it can never be sent twice, `sent` only when the backend confirmed it.
No Celery: low-volume e-mails are sent right after commit; a cron retries failures.

## Cron jobs
```
*/5 * * * *   python manage.py send_notification_emails      # retry pending/failed e-mails
15 3 * * *    python manage.py cleanup_notifications         # expired + read older than 90 days
```
Push notifications (mobile/browser push) are **not** implemented; `types.py` + `services._after_commit` is where a push channel would be added.
