import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import profiles.models
import profiles.validators


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Profile",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("profile_picture", models.ImageField(blank=True, max_length=255, upload_to=profiles.models.profile_picture_upload_to)),
                ("cover_photo", models.ImageField(blank=True, max_length=255, upload_to=profiles.models.cover_photo_upload_to)),
                ("headline", models.CharField(blank=True, max_length=120, validators=[profiles.validators.validate_single_line])),
                ("bio", models.CharField(blank=True, max_length=500, validators=[profiles.validators.validate_multiline])),
                ("institution", models.CharField(blank=True, max_length=150, validators=[profiles.validators.validate_single_line])),
                ("education_level", models.CharField(blank=True, choices=[("high_school", "High school"), ("diploma", "Diploma / college"), ("undergraduate", "Undergraduate"), ("postgraduate", "Postgraduate"), ("doctorate", "Doctorate"), ("other", "Other")], max_length=20)),
                ("field_of_study", models.CharField(blank=True, max_length=150, validators=[profiles.validators.validate_single_line])),
                ("interests", models.JSONField(blank=True, default=list, validators=[profiles.validators.validate_tag_list])),
                ("skills", models.JSONField(blank=True, default=list, validators=[profiles.validators.validate_tag_list])),
                ("location", models.CharField(blank=True, max_length=100, validators=[profiles.validators.validate_single_line])),
                ("website", models.URLField(blank=True, max_length=200, validators=[profiles.validators.validate_web_url])),
                ("linkedin_url", models.URLField(blank=True, max_length=200, validators=[profiles.validators.validate_linkedin_url])),
                ("github_url", models.URLField(blank=True, max_length=200, validators=[profiles.validators.validate_github_url])),
                ("portfolio_url", models.URLField(blank=True, max_length=200, validators=[profiles.validators.validate_web_url])),
                ("profile_visibility", models.CharField(choices=[("public", "Public"), ("members_only", "Members only"), ("private", "Private")], default="public", max_length=20)),
                ("show_institution", models.BooleanField(default=True)),
                ("show_education", models.BooleanField(default=True)),
                ("show_interests", models.BooleanField(default=True)),
                ("show_skills", models.BooleanField(default=True)),
                ("show_location", models.BooleanField(default=True)),
                ("show_social_links", models.BooleanField(default=True)),
                ("date_created", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="profile", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddIndex(
            model_name="profile",
            index=models.Index(fields=["profile_visibility"], name="profiles_visibility_idx"),
        ),
        migrations.AddIndex(
            model_name="profile",
            index=models.Index(fields=["institution"], name="profiles_institution_idx"),
        ),
        migrations.AddIndex(
            model_name="profile",
            index=models.Index(fields=["field_of_study"], name="profiles_field_study_idx"),
        ),
        migrations.AddConstraint(
            model_name="profile",
            constraint=models.CheckConstraint(
                condition=models.Q(("profile_visibility__in", ["public", "members_only", "private"])),
                name="profiles_profile_visibility_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="profile",
            constraint=models.CheckConstraint(
                condition=models.Q(("education_level__in", ["", "high_school", "diploma", "undergraduate", "postgraduate", "doctorate", "other"])),
                name="profiles_profile_education_valid",
            ),
        ),
    ]
