"""Seed the default achievement categories (idempotent; never touches existing rows)."""
from django.db import migrations
from django.utils.text import slugify

CATEGORIES = [
    "Academic", "Sports", "Technology", "Arts and Culture", "Music and Dance", "Leadership",
    "Volunteering", "Entrepreneurship", "Competitions", "Community Service", "Other",
]


def seed(apps, schema_editor):
    Category = apps.get_model("achievements", "AchievementCategory")
    for name in CATEGORIES:
        if not Category.objects.filter(name__iexact=name).exists():
            Category.objects.get_or_create(slug=slugify(name), defaults={"name": name})


class Migration(migrations.Migration):
    dependencies = [("achievements", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
