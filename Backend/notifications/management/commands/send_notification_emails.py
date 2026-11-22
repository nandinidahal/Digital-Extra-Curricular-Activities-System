"""
Retry notification e-mails that are pending or failed (max 3 attempts each).

    python manage.py send_notification_emails            # run from cron, e.g. every 5 minutes

E-mails are normally sent right after the notification is committed; this command catches
SMTP outages. It prints how many were really accepted by the SMTP server.
"""
from django.core.management.base import BaseCommand

from notifications.emails import pending_email_ids, send_notification_email


class Command(BaseCommand):
    help = "Send pending/failed notification e-mails."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=200)

    def handle(self, *args, **options):
        ids = pending_email_ids(options["limit"])
        sent = sum(1 for notification_id in ids if send_notification_email(notification_id))
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} of {len(ids)} pending notification e-mail(s)."))
