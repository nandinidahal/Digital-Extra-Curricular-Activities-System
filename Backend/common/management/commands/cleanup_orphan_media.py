"""
Find (and optionally delete) stored files that no database row references any more.

    python manage.py cleanup_orphan_media                 # dry run: only lists
    python manage.py cleanup_orphan_media --delete        # really deletes
    python manage.py cleanup_orphan_media --prefix achievements --min-age-hours 48

Normal deletes already remove files after commit; this catches leftovers from crashes.
Files younger than --min-age-hours are skipped so an upload in progress is never touched.
Messaging has its own command (messaging_cleanup_orphans) and is not scanned here.
"""
from datetime import timedelta

from django.apps import apps
from django.core.files.storage import storages
from django.core.management.base import BaseCommand
from django.db import models
from django.utils import timezone

from common.files import delete_stored_file, list_stored_files

# (storage alias, top-level prefix) pairs scanned by default
DEFAULT_TARGETS = [
    ("default", "announcements"),
    ("default", "social"),
    ("default", "profiles"),
    ("private", "achievements"),
]


def _referenced_names():
    names = set()
    for model in apps.get_models():
        for field in model._meta.get_fields():
            if isinstance(field, models.FileField):
                names.update(
                    model._default_manager.exclude(**{field.name: ""})
                    .exclude(**{f"{field.name}__isnull": True})
                    .values_list(field.name, flat=True)
                )
    return names


class Command(BaseCommand):
    help = "List or delete media files that are no longer referenced by any database row."

    def add_arguments(self, parser):
        parser.add_argument("--delete", action="store_true", help="Delete the orphans (default: dry run).")
        parser.add_argument("--prefix", action="append", help="Only scan this top-level prefix (repeatable).")
        parser.add_argument("--min-age-hours", type=int, default=24)

    def handle(self, *args, **options):
        targets = DEFAULT_TARGETS
        if options["prefix"]:
            targets = [t for t in DEFAULT_TARGETS if t[1] in options["prefix"]]
        referenced = _referenced_names()
        cutoff = timezone.now() - timedelta(hours=options["min_age_hours"])
        orphans = 0
        for alias, prefix in targets:
            storage = storages[alias]
            for name in list_stored_files(storage, prefix):
                if name in referenced:
                    continue
                try:
                    if storage.get_modified_time(name) > cutoff:
                        continue
                except (NotImplementedError, OSError):
                    continue
                orphans += 1
                if options["delete"]:
                    delete_stored_file(storage, name)
                    self.stdout.write(f"deleted {alias}:{name}")
                else:
                    self.stdout.write(f"orphan  {alias}:{name}")
        verb = "Deleted" if options["delete"] else "Found"
        self.stdout.write(self.style.SUCCESS(f"{verb} {orphans} orphaned file(s)."))
