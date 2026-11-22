import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import social.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Post",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("content", models.TextField(blank=True, max_length=5000)),
                ("post_type", models.CharField(choices=[("general", "General"), ("activity", "Activity"), ("achievement", "Achievement"), ("experience", "Experience")], default="general", max_length=20)),
                ("visibility", models.CharField(choices=[("public", "Public"), ("members_only", "Members only"), ("private", "Private")], default="public", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_edited", models.BooleanField(default=False)),
                ("is_deleted", models.BooleanField(default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="social_posts", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="PostMedia",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("image", models.ImageField(max_length=255, upload_to=social.models.post_media_upload_to)),
                ("width", models.PositiveIntegerField(default=0)),
                ("height", models.PositiveIntegerField(default=0)),
                ("position", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("post", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="media", to="social.post")),
            ],
            options={"ordering": ["position", "created_at"]},
        ),
        migrations.CreateModel(
            name="PostLike",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("post", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="likes", to="social.post")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="social_post_likes", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="Comment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("depth", models.PositiveSmallIntegerField(default=0)),
                ("content", models.TextField(max_length=2000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_edited", models.BooleanField(default=False)),
                ("is_deleted", models.BooleanField(default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="social_comments", to=settings.AUTH_USER_MODEL)),
                ("parent_comment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="replies", to="social.comment")),
                ("post", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comments", to="social.post")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.CreateModel(
            name="CommentLike",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("comment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="likes", to="social.comment")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="social_comment_likes", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="PostShare",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("share_caption", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("original_post", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="shares", to="social.post")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="social_shares", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="ContentReport",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("content_type", models.CharField(choices=[("post", "Post"), ("comment", "Comment")], max_length=10)),
                ("reason", models.CharField(choices=[("spam", "Spam"), ("harassment", "Harassment"), ("inappropriate", "Inappropriate content"), ("false_information", "False information"), ("bullying", "Bullying"), ("other", "Other")], max_length=30)),
                ("description", models.TextField(blank=True, max_length=1000)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("reviewing", "Under review"), ("resolved", "Resolved (action taken)"), ("dismissed", "Dismissed")], default="pending", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("comment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="reports", to="social.comment")),
                ("post", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="reports", to="social.post")),
                ("reporter", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="social_reports_made", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="social_reports_reviewed", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        # ---- indexes -------------------------------------------------------
        migrations.AddIndex(model_name="post", index=models.Index(fields=["is_deleted", "visibility", "-created_at"], name="social_post_feed_idx")),
        migrations.AddIndex(model_name="post", index=models.Index(fields=["author", "is_deleted", "-created_at"], name="social_post_author_idx")),
        migrations.AddIndex(model_name="postmedia", index=models.Index(fields=["post", "position"], name="social_media_post_idx")),
        migrations.AddIndex(model_name="comment", index=models.Index(fields=["post", "parent_comment", "created_at"], name="social_comment_list_idx")),
        migrations.AddIndex(model_name="comment", index=models.Index(fields=["parent_comment", "created_at"], name="social_comment_reply_idx")),
        migrations.AddIndex(model_name="postshare", index=models.Index(fields=["user", "-created_at"], name="social_share_user_idx")),
        migrations.AddIndex(model_name="contentreport", index=models.Index(fields=["status", "-created_at"], name="social_report_status_idx")),
        # ---- constraints ---------------------------------------------------
        migrations.AddConstraint(model_name="post", constraint=models.CheckConstraint(condition=models.Q(("post_type__in", ["general", "activity", "achievement", "experience"])), name="social_post_type_valid")),
        migrations.AddConstraint(model_name="post", constraint=models.CheckConstraint(condition=models.Q(("visibility__in", ["public", "members_only", "private"])), name="social_post_visibility_valid")),
        migrations.AddConstraint(model_name="postlike", constraint=models.UniqueConstraint(fields=("post", "user"), name="social_postlike_unique")),
        migrations.AddConstraint(model_name="commentlike", constraint=models.UniqueConstraint(fields=("comment", "user"), name="social_commentlike_unique")),
        migrations.AddConstraint(model_name="postshare", constraint=models.UniqueConstraint(fields=("original_post", "user"), name="social_postshare_unique")),
        migrations.AddConstraint(
            model_name="comment",
            constraint=models.CheckConstraint(
                condition=models.Q(models.Q(("depth", 0), ("parent_comment__isnull", True)), models.Q(("depth__gt", 0), ("parent_comment__isnull", False)), _connector="OR"),
                name="social_comment_depth_consistent",
            ),
        ),
        migrations.AddConstraint(
            model_name="contentreport",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("comment__isnull", True), ("content_type", "post"), ("post__isnull", False)),
                    models.Q(("comment__isnull", False), ("content_type", "comment"), ("post__isnull", True)),
                    _connector="OR",
                ),
                name="social_report_target_consistent",
            ),
        ),
        migrations.AddConstraint(
            model_name="contentreport",
            constraint=models.UniqueConstraint(fields=("reporter", "post"), condition=models.Q(("post__isnull", False), ("status__in", ["pending", "reviewing"])), name="social_report_active_post_unique"),
        ),
        migrations.AddConstraint(
            model_name="contentreport",
            constraint=models.UniqueConstraint(fields=("reporter", "comment"), condition=models.Q(("comment__isnull", False), ("status__in", ["pending", "reviewing"])), name="social_report_active_comment_unique"),
        ),
    ]
