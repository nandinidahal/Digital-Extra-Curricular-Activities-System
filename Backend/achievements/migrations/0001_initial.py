import achievements.models
import achievements.storage
import achievements.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AchievementCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80, unique=True)),
                ("slug", models.SlugField(blank=True, max_length=90, unique=True)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("display_order", models.PositiveSmallIntegerField(default=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name_plural": "achievement categories",
                "ordering": ["display_order", "name"],
            },
        ),
        migrations.CreateModel(
            name="Achievement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("issuing_organization", models.CharField(max_length=200)),
                ("achievement_date", models.DateField()),
                ("certificate_number", models.CharField(blank=True, max_length=100)),
                ("location", models.CharField(blank=True, max_length=200)),
                (
                    "visibility",
                    models.CharField(
                        choices=[("public", "Public"), ("private", "Private")],
                        default="private",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="achievements",
                        to="achievements.achievementcategory",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="achievements",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-achievement_date", "-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="AchievementDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "file",
                    models.FileField(
                        max_length=255,
                        storage=achievements.storage.get_private_storage,
                        upload_to=achievements.models.achievement_document_path,
                        validators=[achievements.validators.validate_achievement_file],
                    ),
                ),
                (
                    "document_type",
                    models.CharField(
                        choices=[("certificate", "Certificate"), ("supporting", "Supporting document")],
                        default="supporting",
                        max_length=15,
                    ),
                ),
                ("document_name", models.CharField(blank=True, max_length=150)),
                ("original_filename", models.CharField(blank=True, max_length=255)),
                ("content_type", models.CharField(blank=True, max_length=100)),
                ("size", models.PositiveIntegerField(default=0)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "achievement",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="achievements.achievement",
                    ),
                ),
            ],
            options={
                "ordering": ["uploaded_at", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="achievement",
            index=models.Index(fields=["user", "-achievement_date"], name="ach_user_date_idx"),
        ),
        migrations.AddIndex(
            model_name="achievement",
            index=models.Index(fields=["user", "visibility", "-achievement_date"], name="ach_user_vis_date_idx"),
        ),
        migrations.AddConstraint(
            model_name="achievement",
            constraint=models.CheckConstraint(
                condition=models.Q(("visibility__in", ["public", "private"])),
                name="achievement_visibility_valid",
            ),
        ),
        migrations.AddIndex(
            model_name="achievementdocument",
            index=models.Index(fields=["achievement", "uploaded_at"], name="achdoc_ach_uploaded_idx"),
        ),
        migrations.AddConstraint(
            model_name="achievementdocument",
            constraint=models.UniqueConstraint(
                condition=models.Q(("document_type", "certificate")),
                fields=("achievement",),
                name="uniq_certificate_per_achievement",
            ),
        ),
    ]
