"""
The centralized notification service. EVERY module creates notifications through here.

Public API
----------
    notify(...)              schedule create_notification() after the current transaction commits
                             (use this from business services: nothing is sent for a rolled-back write)
    notify_many(...)         same, for a list of recipients (bulk insert)
    create_notification(...) create now; returns the Notification or None when suppressed
    unread_count(user), mark_read(...), mark_unread(...), mark_all_read(user),
    delete_notification(...), clear_notifications(user), get_preferences(user),
    update_preferences(user, data), withdraw(...)

Rules applied by create_notification (in this order)
  1. the type must be registered (notifications/types.py)
  2. the recipient must exist and be active
  3. nobody is notified about their OWN action (actor == recipient), except account/security
  4. nothing is delivered between users with a block in either direction (except security)
  5. the recipient's preference for the category must be ON (essential types ignore it)
  6. metadata is sanitised (JSON scalars only, size-capped, secret-looking keys dropped)
  7. dedupe_key -> at most one notification ever; group_key -> one UNREAD per group (collapsed)
  8. after commit: real-time push (if the user allows it) and e-mail (eligible types only)

Failures never propagate to the caller: a broken notification must not break a like, a message
or a friend request. They are logged.
"""
import json
import logging
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from . import realtime
from .models import MESSAGE_MAX_LENGTH, TITLE_MAX_LENGTH, Notification, NotificationPreference
from .types import ACCOUNT, PREFERENCE_FIELDS, get_type, render

logger = logging.getLogger("notifications")

METADATA_MAX_BYTES = 4096
_SECRET_KEY_PATTERN = re.compile(r"(?i)pass|secret|token|otp|code|email|phone|key")
_SAFE_ACTION_URL = re.compile(r"^/(?!/)[A-Za-z0-9_\-./?=&%:]*$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _users():
    return get_user_model().objects


def _resolve_user(value):
    if value is None:
        return None
    if hasattr(value, "pk") and hasattr(value, "is_active"):
        return value
    return _users().filter(pk=value).first()


def _display_name(user):
    if user is None:
        return "Someone"
    return user.full_name or user.username


def sanitize_metadata(metadata):
    """Keep only JSON-serialisable scalars/lists/dicts; drop secret-looking keys; cap the size."""
    if not metadata:
        return {}
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be a dict")

    def clean(value, depth=0):
        if depth > 3:
            return None
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value[:300] if isinstance(value, str) else value
        if isinstance(value, (list, tuple)):
            return [clean(v, depth + 1) for v in list(value)[:20]]
        if isinstance(value, dict):
            return {
                str(k)[:50]: clean(v, depth + 1)
                for k, v in list(value.items())[:30]
                if not _SECRET_KEY_PATTERN.search(str(k))
            }
        return str(value)[:300]  # UUIDs, datetimes ...

    cleaned = clean(metadata)
    if len(json.dumps(cleaned, default=str)) > METADATA_MAX_BYTES:
        raise ValueError("metadata is too large")
    return cleaned


def _validate_action_url(url):
    if not url:
        return ""
    if len(url) > 300 or not _SAFE_ACTION_URL.match(url):
        raise ValueError("action_url must be an internal path such as /announcements/<id>")
    return url


def get_preferences(user):
    preference, _ = NotificationPreference.objects.get_or_create(user=user)
    return preference


def _preferences_for(user_ids):
    """{user_id: NotificationPreference} for users that have a row (others use the defaults)."""
    return {p.user_id: p for p in NotificationPreference.objects.filter(user_id__in=user_ids)}


def _category_allowed(preference, ntype):
    if ntype.essential or ntype.category == ACCOUNT:
        return True
    if preference is None:
        return True
    return getattr(preference, PREFERENCE_FIELDS[ntype.category], True)


def _realtime_allowed(preference):
    return preference is None or preference.realtime_notifications


def _email_wanted(recipient, preference, ntype):
    if not ntype.email or not getattr(settings, "NOTIFICATIONS_EMAIL_ENABLED", False):
        return False
    if not recipient.email or not recipient.is_email_verified:
        return False
    if ntype.essential:
        return True
    return preference is None or preference.email_notifications


def _blocked(actor_id, recipient_id):
    from common.relationships import is_blocked_between

    return is_blocked_between(actor_id, recipient_id)


def _live():
    """Notifications that have not expired."""
    return Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())


def visible_notifications(user):
    return Notification.objects.filter(recipient=user).filter(_live())


def unread_count(user):
    user_id = getattr(user, "pk", user)
    return Notification.objects.filter(recipient_id=user_id, is_read=False).filter(_live()).count()


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------
def create_notification(
    *,
    recipient,
    notification_type,
    actor=None,
    target_type="",
    target_id="",
    context=None,
    title=None,
    message=None,
    metadata=None,
    action_url="",
    dedupe_key=None,
    group_key=None,
    expires_at=None,
):
    ntype = get_type(notification_type)
    recipient = _resolve_user(recipient)
    if recipient is None or not recipient.is_active:
        return None
    actor = _resolve_user(actor)
    if actor is not None and actor.pk == recipient.pk and not (ntype.essential or ntype.category == ACCOUNT):
        return None  # never notify people about their own actions
    if actor is not None and not ntype.essential and actor.pk != recipient.pk and _blocked(actor.pk, recipient.pk):
        return None

    preference = NotificationPreference.objects.filter(user=recipient).first()
    if not _category_allowed(preference, ntype):
        return None

    values = {"actor": _display_name(actor), **(context or {})}
    fields = {
        "actor": actor,
        "notification_type": ntype.key,
        "category": ntype.category,
        "title": render(title or ntype.title, values, TITLE_MAX_LENGTH) or ntype.key,
        "message": render(message or ntype.message, values, MESSAGE_MAX_LENGTH),
        "metadata": sanitize_metadata(metadata),
        "target_type": str(target_type or "")[:40],
        "target_id": str(target_id or "")[:64],
        "action_url": _validate_action_url(action_url),
        "expires_at": expires_at,
    }
    email = _email_wanted(recipient, preference, ntype)
    fields["email_status"] = Notification.EmailStatus.PENDING if email else Notification.EmailStatus.NOT_REQUESTED

    with transaction.atomic():
        if group_key:
            notification, collapsed = _create_or_collapse(recipient, group_key, dedupe_key, fields)
        else:
            notification, collapsed = _create(recipient, dedupe_key, fields), False
        if notification is None:
            return None
        _after_commit(notification, preference, collapsed=collapsed, email=email and not collapsed)
    return notification


def _create(recipient, dedupe_key, fields):
    try:
        with transaction.atomic():
            return Notification.objects.create(recipient=recipient, dedupe_key=dedupe_key, **fields)
    except IntegrityError:  # dedupe_key already used for this recipient: idempotent no-op
        return None


def _create_or_collapse(recipient, group_key, dedupe_key, fields):
    """One UNREAD notification per (recipient, group_key): bump it instead of adding another."""
    for _attempt in range(2):
        existing = (
            Notification.objects.select_for_update()
            .filter(recipient=recipient, group_key=group_key, is_read=False)
            .first()
        )
        if existing is not None:
            count = int((existing.metadata or {}).get("count", 1)) + 1
            existing.metadata = {**fields["metadata"], "count": count}
            existing.actor = fields["actor"]
            existing.title = fields["title"]
            existing.message = fields["message"]
            existing.created_at = timezone.now()  # "latest occurrence": moves it to the top
            existing.save(update_fields=["metadata", "actor", "title", "message", "created_at", "updated_at"])
            return existing, True
        try:
            with transaction.atomic():
                fields = {**fields, "metadata": {**fields["metadata"], "count": 1}}
                return (
                    Notification.objects.create(
                        recipient=recipient, dedupe_key=dedupe_key, group_key=group_key, **fields
                    ),
                    False,
                )
        except IntegrityError:
            continue  # a concurrent request created it first: collapse into that one
    return None, False


def _after_commit(notification, preference, *, collapsed, email):
    notification_id, recipient_id = notification.pk, notification.recipient_id

    def _deliver():
        if _realtime_allowed(preference):
            push_notification(notification_id, "notification.updated" if collapsed else "notification.new")
        if email:
            from .emails import send_notification_email

            send_notification_email(notification_id)

    transaction.on_commit(_deliver)
    return recipient_id


def _safe_create(**kwargs):
    try:
        return create_notification(**kwargs)
    except Exception:
        logger.exception("Could not create %s notification", kwargs.get("notification_type"))
        return None


def notify(**kwargs):
    """
    Create a notification once the current transaction commits (immediately when not inside
    one). Use this from business services. Errors are logged, never raised.
    """
    transaction.on_commit(lambda: _safe_create(**kwargs))


def notify_many(*, recipients, notification_type, actor=None, dedupe_key=None, **kwargs):
    """Schedule the same notification for many users after commit (bulk insert)."""
    recipient_ids = list({getattr(r, "pk", r) for r in recipients})
    if not recipient_ids:
        return
    transaction.on_commit(
        lambda: _safe_bulk(recipient_ids, notification_type, actor, dedupe_key, kwargs)
    )


def _safe_bulk(recipient_ids, notification_type, actor, dedupe_key, kwargs):
    try:
        return create_bulk(
            recipient_ids=recipient_ids, notification_type=notification_type,
            actor=actor, dedupe_key=dedupe_key, **kwargs,
        )
    except Exception:
        logger.exception("Could not create bulk %s notifications", notification_type)
        return []


def create_bulk(
    *, recipient_ids, notification_type, actor=None, target_type="", target_id="", context=None,
    metadata=None, action_url="", dedupe_key=None, expires_at=None,
):
    """Same rules as create_notification (no grouping, no e-mail) for many recipients at once."""
    ntype = get_type(notification_type)
    actor = _resolve_user(actor)
    recipients = list(_users().filter(pk__in=recipient_ids, is_active=True))
    if actor is not None:
        from common.relationships import hidden_user_ids

        hidden = hidden_user_ids(actor) if not ntype.essential else set()
        recipients = [r for r in recipients if r.pk != actor.pk and r.pk not in hidden]
    preferences = _preferences_for([r.pk for r in recipients])
    recipients = [r for r in recipients if _category_allowed(preferences.get(r.pk), ntype)]
    if not recipients:
        return []

    values = {"actor": _display_name(actor), **(context or {})}
    common_fields = dict(
        actor=actor,
        notification_type=ntype.key,
        category=ntype.category,
        title=render(ntype.title, values, TITLE_MAX_LENGTH),
        message=render(ntype.message, values, MESSAGE_MAX_LENGTH),
        metadata=sanitize_metadata(metadata),
        target_type=str(target_type or "")[:40],
        target_id=str(target_id or "")[:64],
        action_url=_validate_action_url(action_url),
        expires_at=expires_at,
        dedupe_key=dedupe_key,
    )
    rows = [Notification(recipient=r, **common_fields) for r in recipients]
    Notification.objects.bulk_create(rows, ignore_conflicts=True, batch_size=500)
    # With ignore_conflicts PostgreSQL does not tell which rows were skipped: re-read them.
    created = list(Notification.objects.filter(pk__in=[row.pk for row in rows]).values_list("pk", "recipient_id"))

    def _deliver():
        for notification_id, recipient_id in created:
            if _realtime_allowed(preferences.get(recipient_id)):
                push_notification(notification_id, "notification.new")

    transaction.on_commit(_deliver)
    return [pk for pk, _ in created]


# ---------------------------------------------------------------------------
# Real-time
# ---------------------------------------------------------------------------
def push_notification(notification_id, event_type):
    from .serializers import NotificationSerializer

    notification = Notification.objects.select_related("actor", "actor__profile").filter(pk=notification_id).first()
    if notification is None:
        return
    realtime.send_to_user(
        notification.recipient_id,
        event_type,
        {
            "notification": NotificationSerializer(notification).data,
            "unread_count": unread_count(notification.recipient_id),
        },
    )


def _push_on_commit(user_id, event_type, data):
    def _send():
        preference = NotificationPreference.objects.filter(user_id=user_id).first()
        if _realtime_allowed(preference):
            realtime.send_to_user(user_id, event_type, {**data, "unread_count": unread_count(user_id)})

    transaction.on_commit(_send)


# ---------------------------------------------------------------------------
# Reading / managing (always scoped to the requesting user)
# ---------------------------------------------------------------------------
def get_own_notification(user, notification_id):
    from common.exceptions import ResourceNotFound

    notification = visible_notifications(user).filter(pk=notification_id).first()
    if notification is None:
        raise ResourceNotFound("This notification does not exist.", code="notification_not_found")
    return notification


@transaction.atomic
def mark_read(user, notification_id):
    notification = get_own_notification(user, notification_id)
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at", "updated_at"])
        _push_on_commit(user.pk, "notification.read", {"notification_ids": [str(notification.pk)]})
    return notification


@transaction.atomic
def mark_unread(user, notification_id):
    notification = get_own_notification(user, notification_id)
    if notification.is_read:
        # If another unread notification of the same group exists, the group key is dropped so the
        # "one unread per group" constraint holds.
        if notification.group_key and Notification.objects.filter(
            recipient=user, group_key=notification.group_key, is_read=False
        ).exists():
            notification.group_key = None
        notification.is_read = False
        notification.read_at = None
        notification.save(update_fields=["is_read", "read_at", "group_key", "updated_at"])
        _push_on_commit(user.pk, "notification.updated", {"notification_ids": [str(notification.pk)], "is_read": False})
    return notification


@transaction.atomic
def mark_all_read(user):
    now = timezone.now()
    ids = list(visible_notifications(user).filter(is_read=False).values_list("pk", flat=True))
    updated = Notification.objects.filter(pk__in=ids).update(is_read=True, read_at=now, updated_at=now)
    if updated:
        _push_on_commit(user.pk, "notification.read", {"notification_ids": [str(i) for i in ids], "all": True})
    return updated


@transaction.atomic
def delete_notification(user, notification_id):
    notification = get_own_notification(user, notification_id)
    notification_pk = notification.pk
    notification.delete()
    _push_on_commit(user.pk, "notification.deleted", {"notification_ids": [str(notification_pk)]})


@transaction.atomic
def clear_notifications(user, *, read_only=False):
    queryset = Notification.objects.filter(recipient=user)
    if read_only:
        queryset = queryset.filter(is_read=True)
    deleted, _ = queryset.delete()
    if deleted:
        _push_on_commit(user.pk, "notification.deleted", {"all": True, "read_only": read_only})
    return deleted


@transaction.atomic
def update_preferences(user, data):
    preference = NotificationPreference.objects.select_for_update().get(pk=get_preferences(user).pk)
    for field in NotificationPreference.SWITCHES:
        if field in data:
            setattr(preference, field, data[field])
    preference.save()
    return preference


# ---------------------------------------------------------------------------
# Withdrawing / auto-reading notifications when the underlying event is undone
# ---------------------------------------------------------------------------
def withdraw(*, recipient_id, dedupe_key=None, group_key=None, mark_read_only=False):
    """
    Delete (or just mark read) a recipient's notification identified by dedupe/group key, e.g.
    a cancelled friend request or a conversation the user has already read.
    """
    queryset = Notification.objects.filter(recipient_id=recipient_id)
    if dedupe_key:
        queryset = queryset.filter(dedupe_key=dedupe_key)
    elif group_key:
        queryset = queryset.filter(group_key=group_key, is_read=False)
    else:
        return 0
    ids = [str(i) for i in queryset.values_list("pk", flat=True)]
    if not ids:
        return 0
    if mark_read_only:
        now = timezone.now()
        changed = queryset.filter(is_read=False).update(is_read=True, read_at=now, updated_at=now)
        if changed:
            _push_on_commit(recipient_id, "notification.read", {"notification_ids": ids})
        return changed
    deleted, _ = queryset.delete()
    _push_on_commit(recipient_id, "notification.deleted", {"notification_ids": ids})
    return deleted
