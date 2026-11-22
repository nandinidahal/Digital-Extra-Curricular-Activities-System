import smtplib
from unittest.mock import patch

from django.core import mail

from accounts.models import OneTimePassword, User

from .base import PASSWORD, BaseAPITestCase


class RegistrationTests(BaseAPITestCase):
    def test_successful_registration(self):
        response = self.post("register", self.registration_payload())
        self.assertEqual(response.status_code, 201, response.json())
        body = response.json()
        self.assertTrue(body["success"])
        self.assertTrue(body["data"]["email_verification_required"])
        self.assertEqual(body["data"]["user"]["email"], "student@example.com")

        user = User.objects.get(email="student@example.com")
        self.assertFalse(user.is_email_verified)
        self.assertEqual(user.role, User.Role.USER)
        self.assertEqual(user.phone_number, "+9779812345678")

    def test_password_is_hashed(self):
        self.post("register", self.registration_payload())
        user = User.objects.get(username="student1")
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.password.startswith(("pbkdf2_", "argon2", "bcrypt", "scrypt")))
        self.assertTrue(user.check_password(PASSWORD))

    def test_no_tokens_issued_and_no_secrets_in_response(self):
        response = self.post("register", self.registration_payload())
        text = response.content.decode()
        self.assertNotIn("access", text)
        self.assertNotIn("refresh", text)
        self.assertNotIn("password", text.replace("password_", ""))
        self.assertNotIn("otp\":", text)

    def test_verification_email_is_sent_and_otp_stored_hashed(self):
        self.post("register", self.registration_payload())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["student@example.com"])
        code = self.last_otp()
        self.assertEqual(len(code), 6)
        # Both a plain-text and an HTML version are sent.
        self.assertEqual(mail.outbox[0].alternatives[0][1], "text/html")
        otp = OneTimePassword.objects.get()
        self.assertNotEqual(otp.otp_hash, code)
        self.assertEqual(len(otp.otp_hash), 64)
        self.assertEqual(otp.purpose, OneTimePassword.Purpose.EMAIL_VERIFICATION)

    def test_email_is_normalized(self):
        response = self.post("register", self.registration_payload(email="  Student@Example.COM "))
        self.assertEqual(response.status_code, 201, response.json())
        self.assertTrue(User.objects.filter(email="student@example.com").exists())

    def test_duplicate_email_is_rejected_case_insensitively(self):
        self.create_user()
        response = self.post(
            "register", self.registration_payload(username="other", email="STUDENT@example.com")
        )
        body = self.assertError(response, 400, "validation_error")
        self.assertIn("email", body["errors"])
        self.assertEqual(User.objects.count(), 1)

    def test_duplicate_username_is_rejected_case_insensitively(self):
        self.create_user()
        response = self.post(
            "register", self.registration_payload(username="STUDENT1", email="new@example.com")
        )
        body = self.assertError(response, 400, "validation_error")
        self.assertIn("username", body["errors"])

    def test_invalid_email(self):
        response = self.post("register", self.registration_payload(email="not-an-email"))
        body = self.assertError(response, 400, "validation_error")
        self.assertIn("email", body["errors"])

    def test_weak_password(self):
        for weak in ("12345678", "password", "short1!"):
            response = self.post(
                "register",
                self.registration_payload(password=weak, confirm_password=weak),
            )
            body = self.assertError(response, 400, "validation_error")
            self.assertIn("password", body["errors"], weak)
        self.assertEqual(User.objects.count(), 0)

    def test_password_mismatch(self):
        response = self.post(
            "register", self.registration_payload(confirm_password="Different!Pass123")
        )
        body = self.assertError(response, 400, "validation_error")
        self.assertIn("confirm_password", body["errors"])

    def test_missing_required_fields(self):
        response = self.post("register", {})
        body = self.assertError(response, 400, "validation_error")
        for field in (
            "full_name",
            "username",
            "email",
            "password",
            "confirm_password",
            "date_of_birth",
            "phone_number",
            "country",
        ):
            self.assertIn(field, body["errors"])

    def test_invalid_date_of_birth(self):
        for bad in ("2999-01-01", "not-a-date", "1800-01-01", "2024-01-01"):
            response = self.post("register", self.registration_payload(date_of_birth=bad))
            body = self.assertError(response, 400, "validation_error")
            self.assertIn("date_of_birth", body["errors"], bad)

    def test_invalid_phone_number(self):
        for bad in ("abc", "123", "+0123456789", "98 12"):
            response = self.post("register", self.registration_payload(phone_number=bad))
            body = self.assertError(response, 400, "validation_error")
            self.assertIn("phone_number", body["errors"], bad)

    def test_phone_number_is_normalized(self):
        self.post("register", self.registration_payload(phone_number="+977 98-1234-5678"))
        self.assertEqual(User.objects.get().phone_number, "+9779812345678")

    def test_cannot_register_as_admin_or_set_protected_fields(self):
        for field, value in (
            ("role", "admin"),
            ("is_staff", True),
            ("is_superuser", True),
            ("is_email_verified", True),
            ("is_active", True),
        ):
            response = self.post("register", self.registration_payload(**{field: value}))
            body = self.assertError(response, 400, "validation_error")
            self.assertIn(field, body["errors"])
        self.assertEqual(User.objects.count(), 0)

    def test_email_delivery_failure_rolls_back_registration(self):
        with patch(
            "accounts.services.EmailMultiAlternatives.send",
            side_effect=smtplib.SMTPException("SMTP down"),
        ):
            response = self.post("register", self.registration_payload())
        self.assertError(response, 503, "email_delivery_failed")
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(OneTimePassword.objects.count(), 0)
