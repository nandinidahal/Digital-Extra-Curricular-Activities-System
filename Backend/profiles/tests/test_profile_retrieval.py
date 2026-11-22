import uuid

from profiles.models import Profile

from .base import ProfileTestCase


class OwnProfileRetrievalTests(ProfileTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.login(self.user)

    def test_owner_sees_complete_profile(self):
        response = self.client.get(self.url("me"))
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertTrue(body["success"])
        profile = body["data"]["profile"]
        self.assertEqual(profile["user_id"], str(self.user.pk))
        self.assertEqual(profile["username"], "student1")
        self.assertEqual(profile["full_name"], "Test Student")
        self.assertTrue(profile["is_owner"])
        self.assertIn("privacy", profile)
        self.assertIn("profile_completion", profile)
        self.assertIsNone(profile["profile_picture"])
        self.assertIsNone(profile["cover_photo"])
        self.assertIn("date_created", profile)

    def test_response_never_contains_secrets_or_account_internals(self):
        text = self.client.get(self.url("me")).content.decode().lower()
        for forbidden in ("password", "pbkdf2", "token", "otp", "is_staff", "is_superuser",
                          "role", "email", "phone", "date_of_birth"):
            self.assertNotIn(forbidden, text)

    def test_me_requires_authentication(self):
        self.logout()
        response = self.client.get(self.url("me"))
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.json()["success"])

    def test_invalid_token_is_rejected_on_me(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        self.assertEqual(self.client.get(self.url("me")).status_code, 401)

    def test_put_is_not_allowed(self):
        self.assertEqual(self.client.put(self.url("me"), {}, format="json").status_code, 405)

    def test_json_error_shape_matches_accounts(self):
        self.logout()
        body = self.client.get(self.url("me")).json()
        for key in ("success", "message", "code", "errors"):
            self.assertIn(key, body)


class OtherProfileRetrievalTests(ProfileTestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.make_user("owner1", "owner1@example.com")
        self.viewer = self.make_user("viewer1", "viewer1@example.com")
        Profile.objects.filter(user=self.owner).update(
            headline="Robotics club lead", bio="Hello!", institution="DEAS College"
        )

    def test_visitor_can_view_public_profile(self):
        response = self.client.get(self.detail_url(self.owner))
        self.assertEqual(response.status_code, 200, response.content)
        profile = response.json()["data"]["profile"]
        self.assertEqual(profile["username"], "owner1")
        self.assertEqual(profile["headline"], "Robotics club lead")
        self.assertFalse(profile["is_owner"])

    def test_other_user_view_has_no_owner_only_data(self):
        self.login(self.viewer)
        profile = self.client.get(self.detail_url(self.owner)).json()["data"]["profile"]
        for key in ("privacy", "profile_completion", "id", "updated_at"):
            self.assertNotIn(key, profile)

    def test_owner_viewing_own_id_gets_full_profile(self):
        self.login(self.owner)
        profile = self.client.get(self.detail_url(self.owner)).json()["data"]["profile"]
        self.assertTrue(profile["is_owner"])
        self.assertIn("privacy", profile)

    def test_unknown_user_returns_404(self):
        response = self.client.get(self.url("detail", user_id=uuid.uuid4()))
        self.assertError(response, 404, "profile_not_found")

    def test_user_without_profile_returns_404_for_others(self):
        Profile.objects.filter(user=self.owner).delete()
        self.assertError(self.client.get(self.detail_url(self.owner)), 404, "profile_not_found")

    def test_unverified_account_is_not_visible_to_others(self):
        ghost = self.make_user("ghost1", "ghost1@example.com", is_email_verified=False)
        self.assertError(self.client.get(self.detail_url(ghost)), 404, "profile_not_found")

    def test_inactive_account_is_not_visible_to_others(self):
        self.owner.is_active = False
        self.owner.save()
        self.assertError(self.client.get(self.detail_url(self.owner)), 404, "profile_not_found")

    def test_expired_or_invalid_token_is_treated_as_visitor_on_public_profile(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer stale.token.value")
        self.assertEqual(self.client.get(self.detail_url(self.owner)).status_code, 200)

    def test_non_uuid_id_is_json_404(self):
        response = self.client.get("/api/profiles/not-a-uuid/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "not_found")

    def test_response_never_leaks_account_data(self):
        text = self.client.get(self.detail_url(self.owner)).content.decode().lower()
        for forbidden in ("password", "email", "role", "phone", "token", "otp", "date_of_birth"):
            self.assertNotIn(forbidden, text)
