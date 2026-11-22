from profiles.models import Profile

from .base import ProfileTestCase

FULL = {
    "headline": "Headline text",
    "bio": "Bio text",
    "institution": "Secret Institution",
    "education_level": "undergraduate",
    "field_of_study": "Secret Field",
    "interests": ["secret-interest"],
    "skills": ["secret-skill"],
    "location": "Secret Location",
    "website": "https://secret-site.example.com",
    "linkedin_url": "https://linkedin.com/in/secret",
    "github_url": "https://github.com/secret",
    "portfolio_url": "https://secret-portfolio.example.com",
}


class PrivacySettingsTests(ProfileTestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.make_user("owner1", "owner1@example.com")
        self.viewer = self.make_user("viewer1", "viewer1@example.com")
        Profile.objects.filter(user=self.owner).update(**FULL)

    def set_privacy(self, **data):
        self.login(self.owner)
        response = self.client.patch(self.url("me-privacy"), data, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.logout()
        return response

    def view_as_visitor(self):
        self.logout()
        return self.client.get(self.detail_url(self.owner))

    def view_as_member(self):
        self.login(self.viewer)
        return self.client.get(self.detail_url(self.owner))

    # ----- the settings endpoint ------------------------------------------------
    def test_defaults_are_public_and_everything_visible(self):
        self.login(self.owner)
        privacy = self.client.get(self.url("me")).json()["data"]["profile"]["privacy"]
        self.assertEqual(privacy["profile_visibility"], "public")
        for flag in ("show_institution", "show_education", "show_interests",
                     "show_skills", "show_location", "show_social_links"):
            self.assertTrue(privacy[flag], flag)

    def test_owner_can_change_privacy_and_gets_profile_back(self):
        response = self.set_privacy(profile_visibility="members_only", show_skills=False)
        privacy = response.json()["data"]["profile"]["privacy"]
        self.assertEqual(privacy["profile_visibility"], "members_only")
        self.assertFalse(privacy["show_skills"])
        self.assertTrue(privacy["show_location"])  # untouched

    def test_invalid_visibility_value_rejected(self):
        self.login(self.owner)
        response = self.client.patch(self.url("me-privacy"), {"profile_visibility": "friends"}, format="json")
        self.assertError(response, 400, "validation_error")

    def test_non_boolean_flag_rejected(self):
        self.login(self.owner)
        response = self.client.patch(self.url("me-privacy"), {"show_skills": "maybe"}, format="json")
        self.assertError(response, 400, "validation_error")

    def test_privacy_endpoint_rejects_other_fields(self):
        self.login(self.owner)
        for payload in ({"bio": "x"}, {"role": "admin"}, {"user": "1"}):
            self.assertError(self.client.patch(self.url("me-privacy"), payload, format="json"),
                             400, "validation_error")

    def test_privacy_requires_authentication(self):
        self.logout()
        self.assertEqual(self.client.patch(self.url("me-privacy"), {"show_skills": False}, format="json").status_code, 401)

    def test_privacy_cannot_change_another_users_settings(self):
        self.login(self.viewer)
        self.client.patch(self.url("me-privacy"), {"profile_visibility": "private"}, format="json")
        self.assertEqual(self.profile_of(self.owner).profile_visibility, "public")
        self.assertEqual(self.profile_of(self.viewer).profile_visibility, "private")

    # ----- profile-level visibility ----------------------------------------------
    def test_public_profile_visible_to_visitor_and_member(self):
        self.set_privacy(profile_visibility="public")
        self.assertEqual(self.view_as_visitor().status_code, 200)
        self.assertEqual(self.view_as_member().status_code, 200)

    def test_members_only_rejects_visitors_but_allows_members(self):
        self.set_privacy(profile_visibility="members_only")
        response = self.view_as_visitor()
        self.assertError(response, 401, "authentication_required")
        self.assertNotIn("Secret", response.content.decode())
        self.assertEqual(self.view_as_member().status_code, 200)

    def test_private_profile_only_visible_to_owner(self):
        self.set_privacy(profile_visibility="private")
        visitor = self.view_as_visitor()
        self.assertError(visitor, 403, "profile_private")
        member = self.view_as_member()
        self.assertError(member, 403, "profile_private")
        for response in (visitor, member):
            text = response.content.decode()
            self.assertNotIn("Secret", text)
            self.assertNotIn("Headline text", text)
        self.login(self.owner)
        own = self.client.get(self.detail_url(self.owner))
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own.json()["data"]["profile"]["institution"], "Secret Institution")

    def test_private_profile_visible_to_admin_role(self):
        self.set_privacy(profile_visibility="private", show_skills=False)
        admin = self.make_user("admin1", "admin1@example.com", role="admin")
        self.login(admin)
        response = self.client.get(self.detail_url(self.owner))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["data"]["profile"]["skills"], ["secret-skill"])

    def test_coordinator_role_gets_no_special_access_to_private_profiles(self):
        self.set_privacy(profile_visibility="private")
        coordinator = self.make_user("coord1", "coord1@example.com", role="coordinator")
        self.login(coordinator)
        self.assertError(self.client.get(self.detail_url(self.owner)), 403, "profile_private")

    def test_visibility_change_takes_effect_immediately(self):
        self.set_privacy(profile_visibility="private")
        self.assertEqual(self.view_as_visitor().status_code, 403)
        self.set_privacy(profile_visibility="public")
        self.assertEqual(self.view_as_visitor().status_code, 200)

    # ----- field-level privacy -----------------------------------------------------
    def test_hidden_fields_are_removed_from_the_response(self):
        cases = {
            "show_institution": ["institution"],
            "show_education": ["education_level", "field_of_study"],
            "show_interests": ["interests"],
            "show_skills": ["skills"],
            "show_location": ["location"],
            "show_social_links": ["website", "linkedin_url", "github_url", "portfolio_url"],
        }
        for flag, hidden_keys in cases.items():
            self.set_privacy(**{flag: False})
            for response in (self.view_as_visitor(), self.view_as_member()):
                profile = response.json()["data"]["profile"]
                for key in hidden_keys:
                    self.assertNotIn(key, profile, f"{key} leaked while {flag}=False")
                # everything else is still there
                for key in set(FULL) - set(hidden_keys):
                    self.assertIn(key, profile, key)
            self.set_privacy(**{flag: True})

    def test_hidden_values_never_appear_anywhere_in_the_raw_response(self):
        self.set_privacy(show_institution=False, show_education=False, show_interests=False,
                         show_skills=False, show_location=False, show_social_links=False)
        for response in (self.view_as_visitor(), self.view_as_member()):
            text = response.content.decode()
            self.assertNotIn("Secret", text)
            self.assertNotIn("secret", text)
            self.assertNotIn("undergraduate", text)
            profile = response.json()["data"]["profile"]
            self.assertEqual(profile["headline"], "Headline text")  # always-visible parts remain
            self.assertEqual(profile["bio"], "Bio text")

    def test_owner_still_sees_everything_with_all_fields_hidden(self):
        self.set_privacy(show_institution=False, show_skills=False, show_social_links=False)
        self.login(self.owner)
        profile = self.client.get(self.url("me")).json()["data"]["profile"]
        self.assertEqual(profile["institution"], "Secret Institution")
        self.assertEqual(profile["skills"], ["secret-skill"])
        self.assertEqual(profile["github_url"], "https://github.com/secret")

    def test_private_data_is_not_in_a_public_response_even_with_members_only_member(self):
        self.set_privacy(profile_visibility="members_only", show_location=False)
        profile = self.view_as_member().json()["data"]["profile"]
        self.assertNotIn("location", profile)
