"""
E-mail copies of important notifications over the project's SMTP settings.

* Only types marked `email=True` in types.py, only to verified addresses, only when the user's
  e-mail preference is on (security notices ignore the preference) and only when
  NOTIFICATIONS_EMAIL_ENABLED is true.
* A notification is "claimed" with a conditional UPDATE before sending, so two workers can never
  e-mail the same notification twice.
* `email_status = "sent"` is stored only when the SMTP backend reported one message sent.
  Failures are stored as "failed" and retried by `python manage.py send_notification_emails`.
* The e-mail contains the title, message and a link to the app; metadata is never included.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db.models import F, Q
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Notification

logger = logging.getLogger("notifications")

MAX_EMAIL_ATTEMPTS = 3
STUCK_SENDING_MINUTES = 15
Status = Notification.EmailStatus


def _claim(notification_id):
    stale = timezone.now() - timedelta(minutes=STUCK_SENDING_MINUTES)
    return (
        Notification.objects.filter(pk=notification_id, email_attempts__lt=MAX_EMAIL_ATTEMPTS)
        .filter(
            Q(email_status__in=[Status.PENDING, Status.FAILED])
            | Q(email_status=Status.SENDING, updated_at__lt=stale)
        )
        .update(email_status=Status.SENDING, email_attempts=F("email_attempts") + 1, updated_at=timezone.now())
    ) == 1


def send_notification_email(notification_id):
    """Returns True only when the backend confirmed delivery to the SMTP server."""
    if not _claim(notification_id):
        return False
    notification = Notification.objects.select_related("recipient").get(pk=notification_id)
    recipient = notification.recipient
    if not recipient.is_active or not recipient.email or not recipient.is_email_verified:
        Notification.objects.filter(pk=notification_id).update(email_status=Status.SKIPPED)
        return False

    base = getattr(settings, "FRONTEND_BASE_URL", "").rstrip("/")
    context = {
        "app_name": "DEAS",
        "full_name": recipient.full_name or recipient.username,
        "title": notification.title,
        "message": notification.message,
        "action_link": f"{base}{notification.action_url}" if base and notification.action_url else (base or ""),
        "preferences_link": f"{base}/settings/notifications" if base else "",
    }
    email = EmailMultiAlternatives(
        subject=f"{notification.title} - DEAS",
        body=render_to_string("emails/notification.txt", context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient.email],
    )
    email.attach_alternative(render_to_string("emails/notification.html", context), "text/html")
    try:
        sent = email.send(fail_silently=False)
    except Exception as exc:  # SMTP/DNS errors, timeouts...
        logger.error("Notification e-mail %s failed (%s)", notification_id, type(exc).__name__)
        sent = 0
    if sent == 1:
        Notification.objects.filter(pk=notification_id).update(email_status=Status.SENT, emailed_at=timezone.now())
        return True
    Notification.objects.filter(pk=notification_id).update(email_status=Status.FAILED)
    return False


def pending_email_ids(limit=200):
    stale = timezone.now() - timedelta(minutes=STUCK_SENDING_MINUTES)
    return list(
        Notification.objects.filter(email_attempts__lt=MAX_EMAIL_ATTEMPTS)
        .filter(
            Q(email_status__in=[Status.PENDING, Status.FAILED])
            | Q(email_status=Status.SENDING, updated_at__lt=stale)
        )
        .order_by("created_at")
        .values_list("pk", flat=True)[:limit]
    )
