"""
Remind people who bookmarked an announcement that it starts soon.

    python manage.py send_announcement_reminders [--hours 24]

Run it from cron (e.g. every 15 minutes). It is idempotent: each bookmarker gets one reminder
per start time, however often the command runs.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from announcements import services


class Command(BaseCommand):
    help = "Send announcement.reminder notifications for events starting soon."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=None)

    def handle(self, *args, **options):
        with transaction.atomic():
            scheduled = services.send_due_reminders(hours=options["hours"])
        self.stdout.write(self.style.SUCCESS(f"Processed {scheduled} reminder(s) (duplicates are skipped)."))
