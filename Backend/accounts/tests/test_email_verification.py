import smtplib
from unittest.mock import patch

from django.core import mail
from django.test import override_settings

from accounts.models import OneTimePassword, User

from .base import RELAXED_RATES, BaseAPITestCase


class EmailVerificationTests(BaseAPITestCase):
    def register(self):
        response = self.post("register", self.registration_payload())
        self.assertEqual(response.status_code, 201, response.json())
        return User.objects.get(email="student@example.com")

    def verify(self, code, email="student@example.com"):
        return self.post("verify-email", {"email": email, "otp": code})

    def test_correct_otp_verifies_email(self):
        user = self.register()
        response = self.verify(self.last_otp())
        self.assertEqual(response.status_code, 200, response.json())
        user.refresh_from_db()
        self.assertTrue(user.is_email_verified)
        self.assertTrue(OneTimePassword.objects.get().is_used)

    def test_user_can_log_in_after_verification(self):
        self.register()
        self.verify(self.last_otp())
        response = self.post("login", {"email": "student@example.com", "password": self.registration_payload()["password"]})
        self.assertEqual(response.status_code, 200, response.json())

    def test_incorrect_otp(self):
        user = self.register()
        wrong = "000000" if self.last_otp() != "000000" else "111111"
        body = self.assertError(self.verify(wrong), 400, "otp_invalid")
        self.assertEqual(body["attempts_remaining"], 4)
        user.refresh_from_db()
        self.assertFalse(user.is_email_verified)

    def test_expired_otp(self):
        user = self.register()
        code = self.last_otp()
        self.expire_otps(user)
        self.assertError(self.verify(code), 400, "otp_expired")
        user.refresh_from_db()
        self.assertFalse(user.is_email_verified)

    def test_otp_cannot_be_reused(self):
        self.register()
        code = self.last_otp()
        self.assertEqual(self.verify(code).status_code, 200)
        self.assertError(self.verify(code), 400, "otp_invalid")

    def test_too_many_attempts_locks_the_code(self):
        user = self.register()
        code = self.last_otp()
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(5):
            self.assertEqual(self.verify(wrong).status_code, 400)
        # Even the correct code is refused now.
        self.assertError(self.verify(code), 400, "otp_max_attempts")
        user.refresh_from_db()
        self.assertFalse(user.is_email_verified)

    def test_failed_attempts_are_really_saved(self):
        self.register()
        wrong = "000000" if self.last_otp() != "000000" else "111111"
        self.verify(wrong)
        self.verify(wrong)
        self.assertEqual(OneTimePassword.objects.get().attempts, 2)

    def test_unknown_email_gets_generic_otp_error(self):
        self.assertError(self.verify("123456", email="nobody@example.com"), 400, "otp_invalid")

    def test_otp_must_be_six_digits(self):
        self.register()
        for bad in ("12345", "1234567", "abcdef", ""):
            self.assertError(self.verify(bad), 400, "validation_error")

    def test_resend_sends_new_code_and_invalidates_old_one(self):
        user = self.register()
        old_code = self.last_otp()
        response = self.post("resend-otp", {"email": "student@example.com"})
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(len(mail.outbox), 2)
        new_code = self.last_otp()
        self.assertEqual(OneTimePassword.objects.filter(user=user, is_used=False).count(), 1)
        if old_code != new_code:
            self.assertError(self.verify(old_code), 400, "otp_invalid")
        self.assertEqual(self.verify(new_code).status_code, 200)

    def test_resend_response_does_not_reveal_whether_email_exists(self):
        self.register()
        known = self.post("resend-otp", {"email": "student@example.com"})
        unknown = self.post("resend-otp", {"email": "nobody@example.com"})
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.json()["message"], unknown.json()["message"])
        self.assertEqual(len(mail.outbox), 2)  # registration + known resend only

    def test_resend_for_already_verified_user_sends_nothing(self):
        self.create_user()
        response = self.post("resend-otp", {"email": "student@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(OTP_RESEND_COOLDOWN_SECONDS=60)
    def test_resend_cooldown_prevents_a_second_email(self):
        self.register()
        self.post("resend-otp", {"email": "student@example.com"})
        self.assertEqual(len(mail.outbox), 1)  # still just the registration email

    @override_settings(OTP_MAX_REQUESTS_PER_HOUR=2)
    def test_hourly_limit_prevents_more_emails(self):
        self.register()  # code 1
        self.post("resend-otp", {"email": "student@example.com"})  # code 2
        self.post("resend-otp", {"email": "student@example.com"})  # blocked
        self.assertEqual(len(mail.outbox), 2)

    def test_email_failure_on_resend_keeps_previous_code_valid(self):
        self.register()
        code = self.last_otp()
        with patch(
            "accounts.services.EmailMultiAlternatives.send",
            side_effect=smtplib.SMTPException("down"),
        ):
            response = self.post("resend-otp", {"email": "student@example.com"})
        self.assertEqual(response.status_code, 200)  # generic, nothing revealed
        self.assertEqual(self.verify(code).status_code, 200)

    def test_password_reset_otp_cannot_verify_email(self):
        self.register()
        self.post("forgot-password", {"email": "student@example.com"})
        reset_code = self.last_otp()
        self.assertError(self.verify(reset_code), 400, "otp_invalid")
        user = User.objects.get(email="student@example.com")
        self.assertFalse(user.is_email_verified)

    @override_settings(
        AUTH_THROTTLE_RATES={**RELAXED_RATES, "otp_request_email_burst": "1/min"}
    )
    def test_resend_is_throttled_per_email(self):
        self.register()
        first = self.post("resend-otp", {"email": "student@example.com"})
        second = self.post("resend-otp", {"email": "student@example.com"})
        self.assertEqual(first.status_code, 200)
        body = self.assertError(second, 429, "throttled")
        self.assertIn("retry_after", body)
