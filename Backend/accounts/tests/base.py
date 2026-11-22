"""Shared helpers for the accounts tests."""
import re
from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import OneTimePassword, User

PASSWORD = "Str0ng!Passw0rd#2026"
NEW_PASSWORD = "An0ther$Str0ng#Pass77"

# Generous limits so ordinary tests never hit throttling by accident.
# Throttle behaviour itself is tested separately with tighter rates.
RELAXED_RATES = {
    "register": "100000/min",
    "login": "100000/min",
    "login_email": "100000/min",
    "otp_verify": "100000/min",
    "otp_request_ip": "100000/min",
    "otp_request_email": "100000/min",
    "otp_request_email_burst": "100000/min",
    "password_reset": "100000/min",
    "token_refresh": "100000/min",
    "password_change": "100000/min",
}


@override_settings(
    SECURE_SSL_REDIRECT=False,
    AUTH_THROTTLE_RATES=RELAXED_RATES,
    OTP_RESEND_COOLDOWN_SECONDS=0,
    OTP_MAX_REQUESTS_PER_HOUR=1000,
    OTP_VALID_MINUTES=5,
    OTP_MAX_ATTEMPTS=5,
)
class BaseAPITestCase(APITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        mail.outbox = []

    # ----- URL / request helpers -------------------------------------------
    @staticmethod
    def url(name):
        return reverse(f"accounts:{name}")

    def post(self, name, data=None, **extra):
        return self.client.post(self.url(name), data or {}, format="json", **extra)

    def authenticate(self, access_token):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    def logout_client(self):
        self.client.credentials()

    # ----- data helpers -----------------------------------------------------
    @staticmethod
    def registration_payload(**overrides):
        payload = {
            "full_name": "Test Student",
            "username": "student1",
            "email": "student@example.com",
            "password": PASSWORD,
            "confirm_password": PASSWORD,
            "date_of_birth": "2000-01-15",
            "phone_number": "+9779812345678",
            "country": "Nepal",
        }
        payload.update(overrides)
        return payload

    @staticmethod
    def create_user(
        email="student@example.com",
        username="student1",
        password=PASSWORD,
        verified=True,
        **extra,
    ):
        return User.objects.create_user(
            username=username,
            email=email,
            password=password,
            full_name=extra.pop("full_name", "Test Student"),
            phone_number=extra.pop("phone_number", "+9779812345678"),
            country=extra.pop("country", "Nepal"),
            date_of_birth=extra.pop("date_of_birth", "2000-01-15"),
            is_email_verified=verified,
            **extra,
        )

    @staticmethod
    def last_otp():
        """Read the 6-digit code from the most recent email (what a real user would do)."""
        body = mail.outbox[-1].body
        return re.search(r"\b(\d{6})\b", body).group(1)

    @staticmethod
    def expire_otps(user):
        OneTimePassword.objects.filter(user=user).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )

    def login_tokens(self, email="student@example.com", password=PASSWORD):
        response = self.post("login", {"email": email, "password": password})
        self.assertEqual(response.status_code, 200, response.json())
        return response.json()["data"]["tokens"]

    def assertError(self, response, status_code, code):
        self.assertEqual(response.status_code, status_code, response.json())
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["code"], code, body)
        return body
