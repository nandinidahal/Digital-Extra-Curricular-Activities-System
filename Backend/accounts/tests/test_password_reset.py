import smtplib
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.utils import timezone

from accounts.models import OneTimePassword, PasswordResetToken

from .base import NEW_PASSWORD, PASSWORD, BaseAPITestCase


class PasswordResetTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = self.create_user()

    # ----- helpers ----------------------------------------------------------
    def request_code(self):
        response = self.post("forgot-password", {"email": "student@example.com"})
        self.assertEqual(response.status_code, 200, response.json())
        return self.last_otp()

    def get_reset_token(self):
        code = self.request_code()
        response = self.post("verify-reset-otp", {"email": "student@example.com", "otp": code})
        self.assertEqual(response.status_code, 200, response.json())
        return response.json()["data"]["reset_token"]

    def reset(self, token, new=NEW_PASSWORD, confirm=None):
        return self.post(
            "reset-password",
            {"token": token, "new_password": new, "confirm_password": confirm or new},
        )

    # ----- step 1: forgot password -----------------------------------------
    def test_forgot_password_sends_otp(self):
        self.request_code()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["student@example.com"])
        otp = OneTimePassword.objects.get()
        self.assertEqual(otp.purpose, OneTimePassword.Purpose.PASSWORD_RESET)
        self.assertNotEqual(otp.otp_hash, self.last_otp())

    def test_forgot_password_does_not_reveal_whether_email_exists(self):
        known = self.post("forgot-password", {"email": "student@example.com"})
        unknown = self.post("forgot-password", {"email": "nobody@example.com"})
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.json(), unknown.json())
        self.assertEqual(len(mail.outbox), 1)

    def test_forgot_password_email_failure_is_not_revealed(self):
        with patch(
            "accounts.services.EmailMultiAlternatives.send",
            side_effect=smtplib.SMTPException("down"),
        ):
            response = self.post("forgot-password", {"email": "student@example.com"})
        self.assertEqual(response.status_code, 200)

    def test_forgot_password_rejects_invalid_email_format(self):
        self.assertError(self.post("forgot-password", {"email": "nope"}), 400, "validation_error")

    # ----- step 2: verify reset OTP ----------------------------------------
    def test_correct_reset_otp_returns_reset_token(self):
        token = self.get_reset_token()
        self.assertGreater(len(token), 30)
        stored = PasswordResetToken.objects.get()
        self.assertNotEqual(stored.token_hash, token)  # only a hash is stored
        self.assertTrue(OneTimePassword.objects.get().is_used)

    def test_incorrect_reset_otp(self):
        code = self.request_code()
        wrong = "000000" if code != "000000" else "111111"
        response = self.post("verify-reset-otp", {"email": "student@example.com", "otp": wrong})
        self.assertError(response, 400, "otp_invalid")
        self.assertEqual(PasswordResetToken.objects.count(), 0)

    def test_expired_reset_otp(self):
        code = self.request_code()
        self.expire_otps(self.user)
        response = self.post("verify-reset-otp", {"email": "student@example.com", "otp": code})
        self.assertError(response, 400, "otp_expired")

    def test_reset_otp_cannot_be_reused(self):
        code = self.request_code()
        payload = {"email": "student@example.com", "otp": code}
        self.assertEqual(self.post("verify-reset-otp", payload).status_code, 200)
        self.assertError(self.post("verify-reset-otp", payload), 400, "otp_invalid")

    def test_too_many_wrong_reset_otps(self):
        code = self.request_code()
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(5):
            self.post("verify-reset-otp", {"email": "student@example.com", "otp": wrong})
        response = self.post("verify-reset-otp", {"email": "student@example.com", "otp": code})
        self.assertError(response, 400, "otp_max_attempts")

    def test_unknown_email_gets_generic_otp_error(self):
        response = self.post("verify-reset-otp", {"email": "nobody@example.com", "otp": "123456"})
        self.assertError(response, 400, "otp_invalid")

    def test_email_verification_otp_cannot_be_used_for_password_reset(self):
        unverified = self.create_user(email="new@example.com", username="newuser", verified=False)
        self.post("resend-otp", {"email": "new@example.com"})
        code = self.last_otp()
        response = self.post("verify-reset-otp", {"email": "new@example.com", "otp": code})
        self.assertError(response, 400, "otp_invalid")
        self.assertEqual(PasswordResetToken.objects.filter(user=unverified).count(), 0)

    # ----- step 3: reset password ------------------------------------------
    def test_successful_reset(self):
        token = self.get_reset_token()
        response = self.reset(token)
        self.assertEqual(response.status_code, 200, response.json())

    def test_old_password_no_longer_works_and_new_one_does(self):
        self.reset(self.get_reset_token())
        old = self.post("login", {"email": "student@example.com", "password": PASSWORD})
        self.assertError(old, 401, "invalid_credentials")
        new = self.post("login", {"email": "student@example.com", "password": NEW_PASSWORD})
        self.assertEqual(new.status_code, 200, new.json())

    def test_password_is_stored_hashed(self):
        self.reset(self.get_reset_token())
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.password, NEW_PASSWORD)
        self.assertTrue(self.user.check_password(NEW_PASSWORD))

    def test_password_mismatch(self):
        response = self.reset(self.get_reset_token(), confirm="Different!Pass123")
        body = self.assertError(response, 400, "validation_error")
        self.assertIn("confirm_password", body["errors"])

    def test_weak_password(self):
        response = self.reset(self.get_reset_token(), new="12345678")
        body = self.assertError(response, 400, "validation_error")
        self.assertIn("new_password", body["errors"])

    def test_invalid_reset_token(self):
        self.assertError(self.reset("not-a-real-token"), 400, "reset_token_invalid")

    def test_reset_token_cannot_be_reused(self):
        token = self.get_reset_token()
        self.assertEqual(self.reset(token).status_code, 200)
        self.assertError(self.reset(token, new="Third$Str0ng#Pass88"), 400, "reset_token_invalid")

    def test_expired_reset_token(self):
        token = self.get_reset_token()
        PasswordResetToken.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertError(self.reset(token), 400, "reset_token_invalid")

    def test_cannot_reset_with_only_email_and_new_password(self):
        response = self.post(
            "reset-password",
            {
                "email": "student@example.com",
                "new_password": NEW_PASSWORD,
                "confirm_password": NEW_PASSWORD,
            },
        )
        body = self.assertError(response, 400, "validation_error")
        self.assertIn("token", body["errors"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))

    def test_existing_refresh_tokens_are_revoked(self):
        tokens = self.login_tokens()
        self.reset(self.get_reset_token())
        response = self.post("token-refresh", {"refresh": tokens["refresh"]})
        self.assertError(response, 401, "token_not_valid")

    def test_outstanding_reset_otps_are_invalidated(self):
        token = self.get_reset_token()
        self.request_code()  # a second, still unused reset OTP
        self.assertEqual(
            OneTimePassword.objects.filter(
                purpose=OneTimePassword.Purpose.PASSWORD_RESET, is_used=False
            ).count(),
            1,
        )
        self.reset(token)
        self.assertEqual(
            OneTimePassword.objects.filter(
                purpose=OneTimePassword.Purpose.PASSWORD_RESET, is_used=False
            ).count(),
            0,
        )

    def test_new_reset_token_invalidates_the_previous_one(self):
        first = self.get_reset_token()
        second = self.get_reset_token()
        self.assertError(self.reset(first), 400, "reset_token_invalid")
        self.assertEqual(self.reset(second).status_code, 200)
