from django.db import migrations
from django.utils.text import slugify

# (name, description). "Other Achievement" is kept last via its display_order.
CATEGORIES = [
    ("Academic Achievement", "Academic results, scholarships, honours and merit awards."),
    ("Sports Achievement", "Sports medals, rankings and tournament results."),
    ("Competition Achievement", "Contests, olympiads, hackathons and similar competitions."),
    ("Participation Certificate", "Certificates for taking part in an event or programme."),
    ("Training and Workshop", "Courses, training programmes and workshops."),
    ("Leadership Achievement", "Leadership roles and recognitions."),
    ("Volunteering Achievement", "Volunteer work and community service."),
    ("Research and Innovation", "Research papers, projects, patents and innovations."),
    ("Professional Achievement", "Professional certifications, work and career milestones."),
    ("Award and Recognition", "Awards and formal recognitions."),
]
OTHER = ("Other Achievement", "Anything that does not fit the other categories.")


def seed_categories(apps, schema_editor):
    AchievementCategory = apps.get_model("achievements", "AchievementCategory")
    rows = [(n, d, (i + 1) * 10) for i, (n, d) in enumerate(CATEGORIES)] + [(*OTHER, 900)]
    for name, description, order in rows:
        AchievementCategory.objects.get_or_create(
            slug=slugify(name),
            defaults={"name": name, "description": description, "display_order": order},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("achievements", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_categories, migrations.RunPython.noop),
    ]
