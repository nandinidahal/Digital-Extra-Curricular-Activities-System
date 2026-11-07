from django.core.management.base import BaseCommand

from announcements.models import Category

DEFAULTS = [
    "Sports", "Technology", "Music", "Dance", "Arts & Culture", "Volunteering",
    "Photography", "Debate", "Workshops", "Coding Competitions",
]


class Command(BaseCommand):
    help = "Create the default activity categories (safe to run repeatedly)."

    def handle(self, *args, **options):
        created = 0
        for name in DEFAULTS:
            _, was_created = Category.objects.get_or_create(name=name)
            created += was_created
        self.stdout.write(self.style.SUCCESS(f"{created} categories created, {len(DEFAULTS) - created} already existed."))
