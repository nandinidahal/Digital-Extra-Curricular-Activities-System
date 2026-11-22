from .base import NEW_PASSWORD, PASSWORD, BaseAPITestCase


class PasswordChangeTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = self.create_user()
        self.tokens = self.login_tokens()
        self.authenticate(self.tokens["access"])

    def change(self, current=PASSWORD, new=NEW_PASSWORD, confirm=None):
        return self.post(
            "change-password",
            {"current_password": current, "new_password": new, "confirm_password": confirm or new},
        )

    def test_successful_change(self):
        response = self.change()
        self.assertEqual(response.status_code, 200, response.json())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        self.assertNotEqual(self.user.password, NEW_PASSWORD)

    def test_old_password_stops_working(self):
        self.change()
        self.logout_client()
        old = self.post("login", {"email": "student@example.com", "password": PASSWORD})
        self.assertError(old, 401, "invalid_credentials")
        new = self.post("login", {"email": "student@example.com", "password": NEW_PASSWORD})
        self.assertEqual(new.status_code, 200)

    def test_other_sessions_are_revoked_but_current_device_gets_new_tokens(self):
        other_device = self.login_tokens()
        response = self.change()
        fresh = response.json()["data"]["tokens"]
        self.logout_client()
        self.assertError(
            self.post("token-refresh", {"refresh": self.tokens["refresh"]}), 401, "token_not_valid"
        )
        self.assertError(
            self.post("token-refresh", {"refresh": other_device["refresh"]}), 401, "token_not_valid"
        )
        self.assertEqual(self.post("token-refresh", {"refresh": fresh["refresh"]}).status_code, 200)

    def test_wrong_current_password(self):
        body = self.assertError(self.change(current="WrongPass!1"), 400, "validation_error")
        self.assertIn("current_password", body["errors"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))

    def test_password_mismatch(self):
        body = self.assertError(self.change(confirm="Different!Pass123"), 400, "validation_error")
        self.assertIn("confirm_password", body["errors"])

    def test_new_password_must_differ_from_current(self):
        body = self.assertError(self.change(new=PASSWORD), 400, "validation_error")
        self.assertIn("new_password", body["errors"])

    def test_weak_new_password(self):
        body = self.assertError(self.change(new="12345678"), 400, "validation_error")
        self.assertIn("new_password", body["errors"])

    def test_requires_authentication(self):
        self.logout_client()
        self.assertError(self.change(), 401, "not_authenticated")
