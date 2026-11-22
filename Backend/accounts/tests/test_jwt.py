from datetime import timedelta

from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from accounts.models import User

from .base import BaseAPITestCase


class JWTTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = self.create_user()
        self.tokens = self.login_tokens()

    # ----- access token -----------------------------------------------------
    def test_valid_access_token_is_accepted(self):
        self.authenticate(self.tokens["access"])
        response = self.client.get(self.url("me"))
        self.assertEqual(response.status_code, 200, response.json())

    def test_missing_access_token_is_rejected(self):
        self.assertError(self.client.get(self.url("me")), 401, "not_authenticated")

    def test_invalid_access_token_is_rejected(self):
        self.authenticate("garbage")
        self.assertError(self.client.get(self.url("me")), 401, "token_not_valid")

    def test_refresh_token_cannot_be_used_as_access_token(self):
        self.authenticate(self.tokens["refresh"])
        self.assertEqual(self.client.get(self.url("me")).status_code, 401)

    def test_expired_access_token_is_rejected(self):
        token = AccessToken(self.tokens["access"])
        token.set_exp(from_time=token.current_time - timedelta(hours=1), lifetime=timedelta(minutes=1))
        self.authenticate(str(token))
        self.assertError(self.client.get(self.url("me")), 401, "token_not_valid")

    # ----- refresh + rotation ----------------------------------------------
    def test_refresh_returns_new_access_and_refresh_tokens(self):
        response = self.post("token-refresh", {"refresh": self.tokens["refresh"]})
        self.assertEqual(response.status_code, 200, response.json())
        new = response.json()["data"]["tokens"]
        self.assertTrue(new["access"])
        self.assertNotEqual(new["refresh"], self.tokens["refresh"])  # rotated

    def test_old_refresh_token_is_blacklisted_after_rotation(self):
        self.post("token-refresh", {"refresh": self.tokens["refresh"]})
        again = self.post("token-refresh", {"refresh": self.tokens["refresh"]})
        self.assertError(again, 401, "token_not_valid")

    def test_new_refresh_token_works(self):
        new = self.post("token-refresh", {"refresh": self.tokens["refresh"]}).json()["data"]["tokens"]
        response = self.post("token-refresh", {"refresh": new["refresh"]})
        self.assertEqual(response.status_code, 200, response.json())

    def test_invalid_refresh_token_is_rejected(self):
        self.assertError(self.post("token-refresh", {"refresh": "nonsense"}), 401, "token_not_valid")

    def test_access_token_cannot_be_used_to_refresh(self):
        response = self.post("token-refresh", {"refresh": self.tokens["access"]})
        self.assertEqual(response.status_code, 401)

    def test_missing_refresh_field(self):
        self.assertError(self.post("token-refresh", {}), 400, "validation_error")

    def test_expired_refresh_token_is_rejected(self):
        refresh = RefreshToken.for_user(self.user)
        refresh.set_exp(from_time=refresh.current_time - timedelta(days=2), lifetime=timedelta(days=1))
        response = self.post("token-refresh", {"refresh": str(refresh)})
        self.assertError(response, 401, "token_not_valid")

    def test_refresh_is_rejected_for_deactivated_user(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        response = self.post("token-refresh", {"refresh": self.tokens["refresh"]})
        self.assertEqual(response.status_code, 401)

    # ----- logout -----------------------------------------------------------
    def test_logout_blacklists_refresh_token(self):
        self.authenticate(self.tokens["access"])
        response = self.post("logout", {"refresh": self.tokens["refresh"]})
        self.assertEqual(response.status_code, 200, response.json())
        self.logout_client()
        reuse = self.post("token-refresh", {"refresh": self.tokens["refresh"]})
        self.assertError(reuse, 401, "token_not_valid")

    def test_logout_requires_authentication(self):
        response = self.post("logout", {"refresh": self.tokens["refresh"]})
        self.assertError(response, 401, "not_authenticated")

    def test_logout_twice_with_same_token_fails_second_time(self):
        self.authenticate(self.tokens["access"])
        self.assertEqual(self.post("logout", {"refresh": self.tokens["refresh"]}).status_code, 200)
        self.assertError(self.post("logout", {"refresh": self.tokens["refresh"]}), 400, "token_invalid")

    def test_logout_with_invalid_token(self):
        self.authenticate(self.tokens["access"])
        self.assertError(self.post("logout", {"refresh": "nonsense"}), 400, "token_invalid")

    def test_cannot_log_out_another_users_token(self):
        self.create_user(email="other@example.com", username="other1")
        other_tokens = self.login_tokens("other@example.com")
        self.authenticate(self.tokens["access"])
        response = self.post("logout", {"refresh": other_tokens["refresh"]})
        self.assertError(response, 400, "token_invalid")
        # The other user's token must still work.
        self.logout_client()
        self.assertEqual(
            self.post("token-refresh", {"refresh": other_tokens["refresh"]}).status_code, 200
        )

    def test_logout_requires_refresh_field(self):
        self.authenticate(self.tokens["access"])
        self.assertError(self.post("logout", {}), 400, "validation_error")
