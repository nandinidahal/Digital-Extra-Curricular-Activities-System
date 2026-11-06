import re
from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import EmailOTP, OTPPurpose, User

PASSWORD = "Str0ng!Passw0rd"

VALID = {
    "full_name": "Asha Sharma",
    "username": "asha",
    "email": "asha@example.com",
    "phone_number": "+9779812345678",
    "password": PASSWORD,
    "confirm_password": PASSWORD,
    "country": "Nepal",
    "date_of_birth": "2000-05-17",
}


def last_otp():
    return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)


class AuthBase(APITestCase):
    def setUp(self):
        cache.clear()

    def register(self, **over):
        return self.client.post(reverse("register"), {**VALID, **over}, format="json")

    def register_and_verify(self, **over):
        self.register(**over)
        email = over.get("email", VALID["email"])
        return self.client.post(reverse("verify-email"), {"email": email, "otp": last_otp()}, format="json")

    def login(self, identifier="asha@example.com", password=PASSWORD):
        return self.client.post(reverse("login"), {"identifier": identifier, "password": password}, format="json")


class RegistrationTests(AuthBase):
    def test_register_valid(self):
        r = self.register()
        self.assertEqual(r.status_code, 201)
        user = User.objects.get(email="asha@example.com")
        self.assertFalse(user.is_active)
        self.assertTrue(user.password.startswith("pbkdf2_"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("password", r.json())

    def test_otp_not_stored_in_plain_text(self):
        self.register()
        otp = EmailOTP.objects.get()
        self.assertNotEqual(otp.code_hash, last_otp())
        self.assertEqual(len(otp.code_hash), 64)

    def test_invalid_email(self):
        self.assertEqual(self.register(email="not-an-email").status_code, 400)

    def test_duplicate_username_and_email(self):
        self.register()
        r = self.register(email="other@example.com")
        self.assertIn("username", r.json())
        r = self.register(username="other", email="ASHA@example.com")
        self.assertIn("email", r.json())

    def test_weak_password_and_mismatch(self):
        self.assertIn("password", self.register(password="abc12345", confirm_password="abc12345").json())
        self.assertIn("confirm_password", self.register(confirm_password="Different1!x").json())

    def test_future_dob_rejected(self):
        self.assertEqual(self.register(date_of_birth="2999-01-01").status_code, 400)


class OTPTests(AuthBase):
    def test_verify_valid_otp(self):
        r = self.register_and_verify()
        self.assertEqual(r.status_code, 200)
        user = User.objects.get(username="asha")
        self.assertTrue(user.is_active and user.is_email_verified)

    def test_expired_otp(self):
        self.register()
        EmailOTP.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        r = self.client.post(reverse("verify-email"), {"email": VALID["email"], "otp": last_otp()}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(User.objects.get().is_active)

    def test_reused_otp(self):
        self.register_and_verify()
        code = last_otp()
        # Already verified account -> OTP cannot be replayed to do anything; also direct service check:
        from accounts.services import verify_otp
        from rest_framework.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            verify_otp(User.objects.get(), OTPPurpose.EMAIL_VERIFICATION, code)

    def test_attempt_limit(self):
        self.register()
        good = last_otp()
        bad = "000000" if good != "000000" else "111111"
        for _ in range(5):
            self.assertEqual(self.client.post(reverse("verify-email"), {"email": VALID["email"], "otp": bad},
                                              format="json").status_code, 400)
        r = self.client.post(reverse("verify-email"), {"email": VALID["email"], "otp": good}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(User.objects.get().is_active)

    def test_resend_cooldown_then_new_code_invalidates_old(self):
        self.register()
        old = last_otp()
        r = self.client.post(reverse("resend-otp"), {"email": VALID["email"]}, format="json")
        self.assertEqual(r.status_code, 429)
        EmailOTP.objects.update(created_at=timezone.now() - timedelta(seconds=120))
        r = self.client.post(reverse("resend-otp"), {"email": VALID["email"]}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 2)
        if old != last_otp():
            r = self.client.post(reverse("verify-email"), {"email": VALID["email"], "otp": old}, format="json")
            self.assertEqual(r.status_code, 400)


class LoginTests(AuthBase):
    def test_login_blocked_before_verification(self):
        self.register()
        r = self.login()
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["code"], "email_not_verified")

    def test_login_after_verification_by_email_and_username(self):
        self.register_and_verify()
        for ident in ("asha@example.com", "ASHA"):
            r = self.login(ident)
            self.assertEqual(r.status_code, 200)
            data = r.json()
            self.assertIn("access", data)
            self.assertIn("refresh", data)
            self.assertEqual(data["user"]["role"], "user")
            self.assertNotIn("password", data["user"])

    def test_invalid_credentials(self):
        self.register_and_verify()
        self.assertEqual(self.login(password="Wrong!pass1").status_code, 401)
        self.assertEqual(self.login(identifier="nobody").status_code, 401)

    def test_me_refresh_logout(self):
        self.register_and_verify()
        tokens = self.login().json()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(self.client.get(reverse("me")).json()["username"], "asha")
        r = self.client.post(reverse("token-refresh"), {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(r.status_code, 200)
        new_refresh = r.json()["refresh"]
        r = self.client.post(reverse("logout"), {"refresh": new_refresh}, format="json")
        self.assertEqual(r.status_code, 200)
        r = self.client.post(reverse("token-refresh"), {"refresh": new_refresh}, format="json")
        self.assertEqual(r.status_code, 401)

    def test_me_requires_auth(self):
        self.assertEqual(self.client.get(reverse("me")).status_code, 401)


class PasswordResetTests(AuthBase):
    NEW = "Brand#New123pw"

    def start_reset(self):
        self.register_and_verify()
        self.client.post(reverse("forgot-password"), {"email": VALID["email"]}, format="json")
        return last_otp()

    def test_full_reset_flow_and_session_invalidation(self):
        self.register_and_verify()
        tokens = self.login().json()
        EmailOTP.objects.update(created_at=timezone.now() - timedelta(minutes=10))
        self.client.post(reverse("forgot-password"), {"email": VALID["email"]}, format="json")
        code = last_otp()
        r = self.client.post(reverse("verify-reset-otp"), {"email": VALID["email"], "otp": code}, format="json")
        self.assertEqual(r.status_code, 200)
        token = r.json()["reset_token"]
        body = {"email": VALID["email"], "reset_token": token, "new_password": self.NEW, "confirm_password": self.NEW}
        self.assertEqual(self.client.post(reverse("reset-password"), body, format="json").status_code, 200)
        # reset token is single use
        self.assertEqual(self.client.post(reverse("reset-password"), body, format="json").status_code, 400)
        # old password dead, new works
        self.assertEqual(self.login().status_code, 401)
        self.assertEqual(self.login(password=self.NEW).status_code, 200)
        # old tokens dead
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(self.client.get(reverse("me")).status_code, 401)
        r = self.client.post(reverse("token-refresh"), {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(r.status_code, 401)

    def test_invalid_reset_otp(self):
        code = self.start_reset()
        bad = "000000" if code != "000000" else "111111"
        r = self.client.post(reverse("verify-reset-otp"), {"email": VALID["email"], "otp": bad}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_cannot_reset_without_verification(self):
        self.start_reset()
        body = {"email": VALID["email"], "reset_token": "guess", "new_password": self.NEW,
                "confirm_password": self.NEW}
        self.assertEqual(self.client.post(reverse("reset-password"), body, format="json").status_code, 400)

    def test_forgot_password_unknown_email_same_response(self):
        r = self.client.post(reverse("forgot-password"), {"email": "ghost@example.com"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_rejects_weak_or_mismatched_password(self):
        code = self.start_reset()
        token = self.client.post(reverse("verify-reset-otp"), {"email": VALID["email"], "otp": code},
                                 format="json").json()["reset_token"]
        weak = {"email": VALID["email"], "reset_token": token, "new_password": "weak", "confirm_password": "weak"}
        self.assertEqual(self.client.post(reverse("reset-password"), weak, format="json").status_code, 400)
        mism = {**weak, "new_password": self.NEW, "confirm_password": "nope"}
        self.assertEqual(self.client.post(reverse("reset-password"), mism, format="json").status_code, 400)
