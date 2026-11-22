from .base import PASSWORD, BaseAPITestCase


class LoginTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = self.create_user()

    def test_successful_login(self):
        response = self.post("login", {"email": "student@example.com", "password": PASSWORD})
        self.assertEqual(response.status_code, 200, response.json())
        data = response.json()["data"]
        self.assertTrue(data["tokens"]["access"])
        self.assertTrue(data["tokens"]["refresh"])
        self.assertEqual(data["user"]["email"], "student@example.com")
        self.assertEqual(data["user"]["role"], "user")

    def test_response_never_contains_password_or_hash(self):
        response = self.post("login", {"email": "student@example.com", "password": PASSWORD})
        text = response.content.decode()
        self.assertNotIn("password", text)
        self.assertNotIn("pbkdf2", text)
        self.assertNotIn("is_staff", text)

    def test_login_updates_last_login(self):
        self.assertIsNone(self.user.last_login)
        self.post("login", {"email": "student@example.com", "password": PASSWORD})
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_login)

    def test_email_is_case_insensitive(self):
        response = self.post("login", {"email": " STUDENT@Example.com ", "password": PASSWORD})
        self.assertEqual(response.status_code, 200, response.json())

    def test_incorrect_password(self):
        response = self.post("login", {"email": "student@example.com", "password": "WrongPass!1"})
        self.assertError(response, 401, "invalid_credentials")

    def test_unknown_email_returns_same_error_as_wrong_password(self):
        wrong_password = self.post(
            "login", {"email": "student@example.com", "password": "WrongPass!1"}
        )
        unknown = self.post("login", {"email": "nobody@example.com", "password": "WrongPass!1"})
        self.assertEqual(wrong_password.status_code, unknown.status_code)
        self.assertEqual(wrong_password.json(), unknown.json())

    def test_unverified_account_cannot_log_in(self):
        self.create_user(email="new@example.com", username="newuser", verified=False)
        response = self.post("login", {"email": "new@example.com", "password": PASSWORD})
        self.assertError(response, 403, "email_not_verified")
        self.assertNotIn("tokens", response.json().get("data", {}))

    def test_unverified_account_with_wrong_password_gets_generic_error(self):
        self.create_user(email="new@example.com", username="newuser", verified=False)
        response = self.post("login", {"email": "new@example.com", "password": "WrongPass!1"})
        self.assertError(response, 401, "invalid_credentials")

    def test_inactive_account_cannot_log_in(self):
        self.user.is_active = False
        self.user.save()
        response = self.post("login", {"email": "student@example.com", "password": PASSWORD})
        self.assertError(response, 401, "invalid_credentials")

    def test_missing_fields(self):
        response = self.post("login", {})
        body = self.assertError(response, 400, "validation_error")
        self.assertIn("email", body["errors"])
        self.assertIn("password", body["errors"])

    def test_stale_authorization_header_does_not_break_login(self):
        """A browser may still send an expired token; public endpoints must ignore it."""
        response = self.post(
            "login",
            {"email": "student@example.com", "password": PASSWORD},
            HTTP_AUTHORIZATION="Bearer this.is.not.valid",
        )
        self.assertEqual(response.status_code, 200, response.json())
