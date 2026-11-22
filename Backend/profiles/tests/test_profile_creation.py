from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import transaction

from accounts.models import User
from profiles import services
from profiles.models import Profile

from .base import ProfileTestCase


class ProfileCreationTests(ProfileTestCase):
    def test_profile_created_for_new_user(self):
        user = self.make_user()
        self.assertTrue(Profile.objects.filter(user=user).exists())
        self.assertEqual(user.profile.profile_visibility, "public")

    def test_new_profile_is_empty_with_sensible_defaults(self):
        profile = self.profile_of(self.make_user())
        self.assertEqual(profile.bio, "")
        self.assertEqual(profile.interests, [])
        self.assertEqual(profile.skills, [])
        self.assertFalse(profile.profile_picture)
        self.assertTrue(profile.show_institution)

    def test_no_duplicate_profiles(self):
        user = self.make_user()
        first = services.create_profile_for_user(user)
        second = services.create_profile_for_user(user)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Profile.objects.filter(user=user).count(), 1)

    def test_saving_existing_user_does_not_create_another_profile(self):
        user = self.make_user()
        user.full_name = "Changed Name"
        user.save()
        self.assertEqual(Profile.objects.filter(user=user).count(), 1)

    def test_existing_user_without_profile_is_healed_on_access(self):
        user = self.make_user()
        Profile.objects.filter(user=user).delete()
        self.login(user)
        response = self.client.get(self.url("me"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Profile.objects.filter(user=user).count(), 1)

    def test_management_command_creates_only_missing_profiles(self):
        keep = self.make_user("keep1", "keep1@example.com")
        lose = self.make_user("lose1", "lose1@example.com")
        kept_pk = keep.profile.pk
        Profile.objects.filter(user=lose).delete()

        out = StringIO()
        call_command("create_missing_profiles", "--dry-run", stdout=out)
        self.assertIn("Would create 1", out.getvalue())
        self.assertFalse(Profile.objects.filter(user=lose).exists())

        out = StringIO()
        call_command("create_missing_profiles", stdout=out)
        self.assertIn("Created 1", out.getvalue())
        self.assertTrue(Profile.objects.filter(user=lose).exists())
        self.assertEqual(Profile.objects.get(user=keep).pk, kept_pk)  # untouched

        out = StringIO()
        call_command("create_missing_profiles", stdout=out)  # idempotent
        self.assertIn("Created 0", out.getvalue())

    def test_profile_failure_rolls_back_the_account(self):
        """If the profile cannot be created, no half-created account remains."""
        with patch("profiles.signals.create_profile_for_user", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    User.objects.create_user(
                        username="ghost1",
                        email="ghost1@example.com",
                        password="Str0ng!Passw0rd#2026",
                        full_name="Ghost",
                    )
        self.assertFalse(User.objects.filter(username="ghost1").exists())

    def test_deleting_user_deletes_profile(self):
        user = self.make_user()
        pk = user.profile.pk
        user.delete()
        self.assertFalse(Profile.objects.filter(pk=pk).exists())
