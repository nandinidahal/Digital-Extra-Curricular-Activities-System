from django.conf import settings
from django.db import migrations

BATCH_SIZE = 500


def create_missing_profiles(apps, schema_editor):
    """Give every user that existed before this module a profile (idempotent)."""
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(app_label, model_name)
    Profile = apps.get_model("profiles", "Profile")

    batch = []
    for pk in list(User.objects.filter(profile__isnull=True).values_list("pk", flat=True)):
        batch.append(Profile(user_id=pk))
        if len(batch) >= BATCH_SIZE:
            Profile.objects.bulk_create(batch, ignore_conflicts=True)
            batch = []
    if batch:
        Profile.objects.bulk_create(batch, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ("profiles", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_missing_profiles, migrations.RunPython.noop),
    ]
