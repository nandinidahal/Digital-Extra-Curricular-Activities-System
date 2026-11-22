"""
Delete expired notifications and READ notifications older than NOTIFICATIONS_RETENTION_DAYS.

    python manage.py cleanup_notifications [--days 90] [--dry-run]
"""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from notifications.models import Notification


class Command(BaseCommand):
    help = "Remove expired and old read notifications."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        days = options["days"] or getattr(settings, "NOTIFICATIONS_RETENTION_DAYS", 90)
        now = timezone.now()
        queryset = Notification.objects.filter(
            Q(expires_at__lte=now) | Q(is_read=True, read_at__lt=now - timedelta(days=days))
        )
        if options["dry_run"]:
            self.stdout.write(f"Would delete {queryset.count()} notification(s).")
            return
        deleted, _ = queryset.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} notification(s)."))
