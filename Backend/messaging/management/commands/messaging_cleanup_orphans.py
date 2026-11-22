"""
Delete attachment files that no database row references (left behind by a crash between the
file write and the rollback cleanup, or by manual database edits).

    python manage.py messaging_cleanup_orphans            # dry run: only lists
    python manage.py messaging_cleanup_orphans --delete

Works with any storage that implements listdir() (FileSystemStorage, S3Storage, ...).
Files younger than --min-age-minutes (default 60) are skipped so in-flight uploads are safe.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from messaging.models import MessageAttachment
from messaging.models.message_attachment import private_attachment_storage


class Command(BaseCommand):
    help = "Find (and optionally delete) messaging attachment files without a database row."

    def add_arguments(self, parser):
        parser.add_argument("--delete", action="store_true", help="Actually delete the orphans.")
        parser.add_argument("--min-age-minutes", type=int, default=60)

    def _walk(self, storage, path):
        try:
            dirs, files = storage.listdir(path)
        except FileNotFoundError:
            return
        for name in files:
            yield f"{path}/{name}" if path else name
        for d in dirs:
            yield from self._walk(storage, f"{path}/{d}" if path else d)

    def handle(self, *args, **options):
        storage = private_attachment_storage()
        known = set(MessageAttachment.objects.values_list("file", flat=True))
        cutoff = timezone.now() - timedelta(minutes=options["min_age_minutes"])
        orphans = []
        for name in self._walk(storage, "messaging"):
            if name in known:
                continue
            try:
                if storage.get_modified_time(name) > cutoff:
                    continue
            except (NotImplementedError, OSError):
                pass
            orphans.append(name)
        for name in orphans:
            if options["delete"]:
                storage.delete(name)
            self.stdout.write(("deleted " if options["delete"] else "orphan ") + name)
        self.stdout.write(self.style.SUCCESS(f"{len(orphans)} orphaned file(s) found."))
