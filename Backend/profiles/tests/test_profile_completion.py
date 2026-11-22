from profiles import services
from profiles.models import Profile

from .base import ProfileTestCase

ALL_FIELDS = {
    "bio": "Bio",
    "headline": "Head",
    "institution": "School",
    "education_level": "diploma",
    "field_of_study": "Maths",
    "interests": ["a"],
    "skills": ["b"],
    "location": "Pokhara",
}


class ProfileCompletionTests(ProfileTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.login(self.user)

    def completion(self):
        return self.client.get(self.url("me")).json()["data"]["profile"]["profile_completion"]

    def test_empty_profile_is_zero_percent(self):
        completion = self.completion()
        self.assertEqual(completion["percentage"], 0)
        self.assertEqual(completion["completed_fields"], [])
        self.assertEqual(len(completion["missing_fields"]), 9)

    def test_partially_completed_profile(self):
        Profile.objects.filter(user=self.user).update(bio="Hello", headline="Hi", institution="School")
        completion = self.completion()
        self.assertEqual(completion["percentage"], 33)  # 3 of 9
        self.assertEqual(set(completion["completed_fields"]), {"bio", "headline", "institution"})
        self.assertIn("skills", completion["missing_fields"])

    def test_fully_completed_profile(self):
        Profile.objects.filter(user=self.user).update(**ALL_FIELDS)
        self.upload("me-picture", self.image_file())
        completion = self.completion()
        self.assertEqual(completion["percentage"], 100)
        self.assertEqual(completion["missing_fields"], [])

    def test_percentage_changes_after_updates(self):
        self.assertEqual(self.completion()["percentage"], 0)
        self.client.patch(self.url("me"), {"bio": "Hello"}, format="json")
        self.assertEqual(self.completion()["percentage"], 11)
        self.client.patch(self.url("me"), {"skills": ["Python"], "location": "Kathmandu"}, format="json")
        self.assertEqual(self.completion()["percentage"], 33)
        self.client.patch(self.url("me"), {"bio": ""}, format="json")
        self.assertEqual(self.completion()["percentage"], 22)

    def test_patch_response_already_contains_new_percentage(self):
        response = self.client.patch(self.url("me"), {"bio": "x", "headline": "y"}, format="json")
        self.assertEqual(response.json()["data"]["profile"]["profile_completion"]["percentage"], 22)

    def test_whitespace_only_and_empty_lists_do_not_count(self):
        profile = Profile(bio="   ", interests=[], skills=[])
        self.assertEqual(services.calculate_completion(profile)["percentage"], 0)

    def test_social_links_and_cover_are_optional_and_not_counted(self):
        Profile.objects.filter(user=self.user).update(
            website="https://example.com", github_url="https://github.com/x",
            linkedin_url="https://linkedin.com/in/x", portfolio_url="https://p.example.com",
        )
        self.upload("me-cover", self.image_file())
        self.assertEqual(self.completion()["percentage"], 0)

    def test_completion_is_not_exposed_to_other_users(self):
        other = self.make_user("other1", "other1@example.com")
        self.login(other)
        profile = self.client.get(self.detail_url(self.user)).json()["data"]["profile"]
        self.assertNotIn("profile_completion", profile)

    def test_percentage_is_not_a_stored_column(self):
        self.assertNotIn("completion", {f.name for f in Profile._meta.get_fields()})
