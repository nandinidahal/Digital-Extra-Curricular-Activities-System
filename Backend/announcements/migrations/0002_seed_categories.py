"""Seed the default announcement categories (idempotent; never touches existing rows)."""
from django.db import migrations
from django.utils.text import slugify

CATEGORIES = [
    "Technology", "Education", "Sports", "Arts and Culture", "Music and Dance", "Volunteering",
    "Leadership", "Entrepreneurship", "Environment", "Community Service", "Competitions",
    "Workshops and Training", "Conferences and Seminars", "Other",
]


def seed(apps, schema_editor):
    Category = apps.get_model("announcements", "Category")
    for name in CATEGORIES:
        if not Category.objects.filter(name__iexact=name).exists():
            Category.objects.get_or_create(slug=slugify(name), defaults={"name": name})


class Migration(migrations.Migration):
    dependencies = [("announcements", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
