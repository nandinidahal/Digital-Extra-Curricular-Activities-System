import uuid

import django.db.models.deletion
import django.db.models.functions.comparison
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FriendRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("accepted", "Accepted"),
                            ("rejected", "Rejected"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="pending",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                (
                    "receiver",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="friends_received_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "sender",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="friends_sent_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Friendship",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user1",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="friends_as_user1",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user2",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="friends_as_user2",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="UserBlock",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "blocked",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="friends_blocks_received",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "blocker",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="friends_blocks_made",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        # ---- FriendRequest indexes and constraints
        migrations.AddIndex(
            model_name="friendrequest",
            index=models.Index(fields=["receiver", "status", "-created_at"], name="friends_req_recv_idx"),
        ),
        migrations.AddIndex(
            model_name="friendrequest",
            index=models.Index(fields=["sender", "status", "-created_at"], name="friends_req_sent_idx"),
        ),
        migrations.AddConstraint(
            model_name="friendrequest",
            constraint=models.CheckConstraint(
                condition=~models.Q(sender=models.F("receiver")), name="friends_request_no_self"
            ),
        ),
        migrations.AddConstraint(
            model_name="friendrequest",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=["pending", "accepted", "rejected", "cancelled"]),
                name="friends_request_status_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="friendrequest",
            constraint=models.CheckConstraint(
                condition=models.Q(status="pending", responded_at__isnull=True)
                | (~models.Q(status="pending") & models.Q(responded_at__isnull=False)),
                name="friends_request_responded_consistent",
            ),
        ),
        migrations.AddConstraint(
            model_name="friendrequest",
            constraint=models.UniqueConstraint(
                fields=("sender", "receiver"),
                condition=models.Q(status="pending"),
                name="friends_request_one_pending_per_direction",
            ),
        ),
        migrations.AddConstraint(
            model_name="friendrequest",
            constraint=models.UniqueConstraint(
                django.db.models.functions.comparison.Least("sender", "receiver"),
                django.db.models.functions.comparison.Greatest("sender", "receiver"),
                condition=models.Q(status="pending"),
                name="friends_request_one_pending_per_pair",
            ),
        ),
        # ---- Friendship indexes and constraints
        migrations.AddIndex(
            model_name="friendship",
            index=models.Index(fields=["user2", "user1"], name="friends_fs_user2_idx"),
        ),
        migrations.AddIndex(
            model_name="friendship",
            index=models.Index(fields=["user1", "-created_at"], name="friends_fs_user1_new_idx"),
        ),
        migrations.AddConstraint(
            model_name="friendship",
            constraint=models.CheckConstraint(
                condition=models.Q(user1_id__lt=models.F("user2_id")), name="friends_friendship_ordered"
            ),
        ),
        migrations.AddConstraint(
            model_name="friendship",
            constraint=models.UniqueConstraint(fields=("user1", "user2"), name="friends_friendship_unique"),
        ),
        # ---- UserBlock indexes and constraints
        migrations.AddIndex(
            model_name="userblock",
            index=models.Index(fields=["blocked", "blocker"], name="friends_block_blocked_idx"),
        ),
        migrations.AddConstraint(
            model_name="userblock",
            constraint=models.CheckConstraint(
                condition=~models.Q(blocker=models.F("blocked")), name="friends_block_no_self"
            ),
        ),
        migrations.AddConstraint(
            model_name="userblock",
            constraint=models.UniqueConstraint(fields=("blocker", "blocked"), name="friends_block_unique"),
        ),
    ]
