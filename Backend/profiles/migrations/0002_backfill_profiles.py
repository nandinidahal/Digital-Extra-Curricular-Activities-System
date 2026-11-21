from django.conf import settings
from django.db import migrations


def create_missing_profiles(apps, schema_editor):
    """Existing users get a profile row (private by default) so the API works for them straight away."""
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(app_label, model_name)
    UserProfile = apps.get_model("profiles", "UserProfile")
    existing = set(UserProfile.objects.values_list("user_id", flat=True))
    UserProfile.objects.bulk_create(
        [UserProfile(user_id=pk) for pk in User.objects.values_list("pk", flat=True) if pk not in existing],
        batch_size=500,
    )


class Migration(migrations.Migration):
    dependencies = [("profiles", "0001_initial")]
    operations = [migrations.RunPython(create_missing_profiles, migrations.RunPython.noop)]
