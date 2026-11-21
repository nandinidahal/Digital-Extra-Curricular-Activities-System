from django.core.management.base import BaseCommand
from django.db.models.functions import Lower

from announcements.models import Category

DEFAULT_CATEGORIES = [
    "General Notice", "Events", "Competitions", "Workshops", "Seminars", "Extracurricular Activities",
    "Club Activities", "Important Deadlines", "Sports", "Cultural Activities", "Academic Activities", "Other",
]


class Command(BaseCommand):
    help = "Create the default announcement categories (idempotent; never duplicates a name)."

    def handle(self, *args, **options):
        existing = set(Category.objects.annotate(n=Lower("name")).values_list("n", flat=True))
        created = 0
        for order, name in enumerate(DEFAULT_CATEGORIES, start=1):
            if name.lower() not in existing:
                Category.objects.create(name=name, display_order=order * 10 if name != "Other" else 900)
                created += 1
        self.stdout.write(self.style.SUCCESS(f"{created} categories created, {len(DEFAULT_CATEGORIES) - created} already present."))
