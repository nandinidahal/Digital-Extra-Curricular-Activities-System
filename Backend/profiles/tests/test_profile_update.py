from .base import ProfileTestCase


class ProfileUpdateTests(ProfileTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.other = self.make_user("other1", "other1@example.com")
        self.login(self.user)

    def patch(self, data):
        return self.client.patch(self.url("me"), data, format="json")

    def test_owner_can_update_profile_and_gets_updated_data_back(self):
        payload = {
            "headline": "CS student",
            "bio": "I love robotics.\nAnd football.",
            "institution": "DEAS University",
            "education_level": "undergraduate",
            "field_of_study": "Computer Science",
            "interests": ["Robotics", "Football"],
            "skills": ["Python", "Django"],
            "location": "Kathmandu",
            "website": "https://example.com",
            "linkedin_url": "https://www.linkedin.com/in/someone",
            "github_url": "https://github.com/someone",
            "portfolio_url": "https://portfolio.example.com/me",
        }
        response = self.patch(payload)
        self.assertEqual(response.status_code, 200, response.content)
        profile = response.json()["data"]["profile"]
        for key, value in payload.items():
            self.assertEqual(profile[key], value, key)
        self.assertEqual(self.profile_of(self.user).headline, "CS student")

    def test_partial_update_changes_only_sent_fields(self):
        self.patch({"headline": "One", "bio": "Two"})
        self.patch({"headline": "Changed"})
        profile = self.profile_of(self.user)
        self.assertEqual(profile.headline, "Changed")
        self.assertEqual(profile.bio, "Two")

    def test_fields_can_be_cleared(self):
        self.patch({"website": "https://example.com", "location": "Pokhara"})
        response = self.patch({"website": "", "location": ""})
        self.assertEqual(response.status_code, 200, response.content)
        profile = self.profile_of(self.user)
        self.assertEqual(profile.website, "")
        self.assertEqual(profile.location, "")

    def test_interests_are_trimmed_and_deduplicated(self):
        response = self.patch({"interests": ["  Chess ", "chess", "Debate"]})
        self.assertEqual(response.json()["data"]["profile"]["interests"], ["Chess", "Debate"])

    def test_non_ascii_text_is_accepted(self):
        response = self.patch({"headline": "इन्जिनियरिङ विद्यार्थी", "location": "काठमाडौँ"})
        self.assertEqual(response.status_code, 200, response.content)

    # ----- invalid values -----------------------------------------------------
    def test_invalid_urls_are_rejected(self):
        for field, value in [
            ("website", "not a url"),
            ("website", "javascript:alert(1)"),
            ("website", "ftp://example.com/file"),
            ("portfolio_url", "data:text/html,<script>1</script>"),
            ("linkedin_url", "https://example.com/in/someone"),
            ("github_url", "https://notgithub.com/someone"),
            ("github_url", "https://github.com.evil.com/someone"),
        ]:
            response = self.patch({field: value})
            body = self.assertError(response, 400, "validation_error")
            self.assertIn(field, body["errors"], (field, value))

    def test_text_length_limits(self):
        for field, too_long in [("headline", "x" * 121), ("bio", "x" * 501),
                                ("institution", "x" * 151), ("location", "x" * 101)]:
            body = self.assertError(self.patch({field: too_long}), 400, "validation_error")
            self.assertIn(field, body["errors"])

    def test_invalid_education_level(self):
        body = self.assertError(self.patch({"education_level": "wizard"}), 400, "validation_error")
        self.assertIn("education_level", body["errors"])

    def test_invalid_interests_and_skills(self):
        for payload in [
            {"interests": "chess"},
            {"interests": ["ok", ""]},
            {"interests": ["x" * 41]},
            {"interests": [f"i{n}" for n in range(21)]},
            {"skills": [f"s{n}" for n in range(31)]},
            {"skills": [["nested"]]},
        ]:
            self.assertError(self.patch(payload), 400, "validation_error")

    def test_control_characters_rejected_in_single_line_fields(self):
        body = self.assertError(self.patch({"headline": "line1\nline2"}), 400, "validation_error")
        self.assertIn("headline", body["errors"])
        self.assertError(self.patch({"institution": "bad\x00name"}), 400, "validation_error")

    def test_body_must_be_a_json_object(self):
        self.assertError(self.patch(["headline"]), 400, "validation_error")

    # ----- protected / unexpected fields -------------------------------------------
    def test_protected_account_fields_cannot_be_modified(self):
        for field, value in [
            ("role", "admin"), ("username", "hacked"), ("email", "x@example.com"),
            ("password", "NewPass#12345"), ("is_staff", True), ("is_superuser", True),
            ("is_email_verified", False), ("full_name", "Hacker"),
            ("user", str(self.other.pk)), ("id", "123"), ("user_id", str(self.other.pk)),
            ("date_created", "2000-01-01T00:00:00Z"),
        ]:
            body = self.assertError(self.patch({field: value}), 400, "validation_error")
            self.assertIn(field, body["errors"], field)
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, "user")
        self.assertEqual(self.user.username, "student1")
        self.assertEqual(self.user.email, "student1@example.com")
        self.assertTrue(self.user.check_password("Str0ng!Passw0rd#2026"))

    def test_unknown_fields_are_rejected(self):
        self.assertError(self.patch({"favourite_colour": "blue"}), 400, "validation_error")

    def test_image_and_privacy_fields_are_not_updatable_here(self):
        for field in ("profile_picture", "cover_photo", "profile_visibility", "show_skills"):
            self.assertError(self.patch({field: "x"}), 400, "validation_error")

    def test_rejected_request_changes_nothing(self):
        self.assertError(self.patch({"headline": "Valid", "role": "admin"}), 400, "validation_error")
        self.assertEqual(self.profile_of(self.user).headline, "")

    # ----- permissions ---------------------------------------------------------------
    def test_update_requires_authentication(self):
        self.logout()
        response = self.patch({"headline": "x"})
        self.assertEqual(response.status_code, 401)

    def test_user_cannot_update_another_users_profile(self):
        # There is no endpoint that takes a target user id for writing ...
        response = self.client.patch(self.detail_url(self.other), {"headline": "pwned"}, format="json")
        self.assertEqual(response.status_code, 405)
        # ... and PATCH /me/ only ever touches the caller's own profile.
        self.patch({"headline": "Mine"})
        self.assertEqual(self.profile_of(self.other).headline, "")
        self.assertEqual(self.profile_of(self.user).headline, "Mine")
