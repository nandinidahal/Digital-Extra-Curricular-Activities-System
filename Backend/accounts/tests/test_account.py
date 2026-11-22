import smtplib
from unittest.mock import patch

from django.core import mail
from django.db import IntegrityError, transaction

from accounts.models import User

from .base import PASSWORD, BaseAPITestCase


class CurrentUserTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = self.create_user()
        self.authenticate(self.login_tokens()["access"])

    def test_get_me_returns_own_account(self):
        response = self.client.get(self.url("me"))
        self.assertEqual(response.status_code, 200, response.json())
        user = response.json()["data"]["user"]
        self.assertEqual(user["id"], str(self.user.pk))
        self.assertEqual(user["username"], "student1")
        self.assertEqual(user["email"], "student@example.com")
        self.assertEqual(user["role"], "user")
        self.assertTrue(user["is_email_verified"])
        for field in ("full_name", "phone_number", "country", "date_of_birth", "created_at"):
            self.assertIn(field, user)

    def test_get_me_never_exposes_sensitive_fields(self):
        text = self.client.get(self.url("me")).content.decode()
        for forbidden in ("password", "is_staff", "is_superuser", "last_login", "pbkdf2"):
            self.assertNotIn(forbidden, text)

    def test_me_returns_only_the_authenticated_user(self):
        other = self.create_user(email="other@example.com", username="other1")
        user = self.client.get(self.url("me")).json()["data"]["user"]
        self.assertNotEqual(user["id"], str(other.pk))

    def test_unauthenticated_access_is_rejected(self):
        self.logout_client()
        self.assertError(self.client.get(self.url("me")), 401, "not_authenticated")
        self.assertError(self.client.patch(self.url("me"), {}, format="json"), 401, "not_authenticated")

    def test_put_and_delete_are_not_allowed(self):
        self.assertEqual(self.client.put(self.url("me"), {}, format="json").status_code, 405)
        self.assertEqual(self.client.delete(self.url("me")).status_code, 405)


class UpdateAccountTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = self.create_user()
        self.authenticate(self.login_tokens()["access"])

    def patch(self, data):
        return self.client.patch(self.url("me"), data, format="json")

    def test_update_own_basic_information(self):
        response = self.patch(
            {
                "full_name": "New Name",
                "username": "newname",
                "phone_number": "+977 98-7654-3210",
                "country": "India",
                "date_of_birth": "1999-05-20",
            }
        )
        self.assertEqual(response.status_code, 200, response.json())
        self.assertFalse(response.json()["data"]["email_verification_required"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "New Name")
        self.assertEqual(self.user.username, "newname")
        self.assertEqual(self.user.phone_number, "+9779876543210")
        self.assertEqual(self.user.country, "India")
        self.assertEqual(str(self.user.date_of_birth), "1999-05-20")
        self.assertTrue(self.user.is_email_verified)  # unchanged email stays verified

    def test_keeping_own_username_is_allowed(self):
        self.assertEqual(self.patch({"username": "student1"}).status_code, 200)

    def test_duplicate_username_is_rejected(self):
        self.create_user(email="other@example.com", username="taken")
        body = self.assertError(self.patch({"username": "TAKEN"}), 400, "validation_error")
        self.assertIn("username", body["errors"])

    def test_duplicate_email_is_rejected(self):
        self.create_user(email="other@example.com", username="other1")
        body = self.assertError(
            self.patch({"email": "other@example.com", "current_password": PASSWORD}),
            400,
            "validation_error",
        )
        self.assertIn("email", body["errors"])

    def test_invalid_values_are_rejected(self):
        self.assertIn("phone_number", self.patch({"phone_number": "abc"}).json()["errors"])
        self.assertIn("date_of_birth", self.patch({"date_of_birth": "2999-01-01"}).json()["errors"])
        self.assertIn("username", self.patch({"username": "a b"}).json()["errors"])

    def test_role_cannot_be_changed(self):
        body = self.assertError(self.patch({"role": "admin"}), 400, "validation_error")
        self.assertIn("role", body["errors"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, "user")

    def test_protected_security_fields_cannot_be_changed(self):
        for field, value in (
            ("is_staff", True),
            ("is_superuser", True),
            ("is_active", False),
            ("is_email_verified", False),
            ("password", "Hacked!Pass123"),
        ):
            self.assertError(self.patch({field: value}), 400, "validation_error")
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
        self.assertTrue(self.user.is_active)
        self.assertTrue(self.user.check_password(PASSWORD))

    def test_cannot_update_another_users_account(self):
        other = self.create_user(email="other@example.com", username="other1", full_name="Other Person")
        response = self.patch({"id": str(other.pk), "full_name": "Hijacked"})
        self.assertError(response, 400, "validation_error")
        other.refresh_from_db()
        self.assertEqual(other.full_name, "Other Person")
        # A normal update only ever touches the logged-in user.
        self.patch({"full_name": "Changed Me"})
        other.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(other.full_name, "Other Person")
        self.assertEqual(self.user.full_name, "Changed Me")

    # ----- email change -----------------------------------------------------
    def test_email_change_requires_current_password(self):
        body = self.assertError(self.patch({"email": "new@example.com"}), 400, "validation_error")
        self.assertIn("current_password", body["errors"])
        body = self.assertError(
            self.patch({"email": "new@example.com", "current_password": "WrongPass!1"}),
            400,
            "validation_error",
        )
        self.assertIn("current_password", body["errors"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "student@example.com")

    def test_email_change_marks_unverified_and_sends_otp_to_new_address(self):
        response = self.patch({"email": "New@Example.com", "current_password": PASSWORD})
        self.assertEqual(response.status_code, 200, response.json())
        self.assertTrue(response.json()["data"]["email_verification_required"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new@example.com")
        self.assertFalse(self.user.is_email_verified)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["new@example.com"])

    def test_new_email_can_be_verified_with_the_otp(self):
        self.patch({"email": "new@example.com", "current_password": PASSWORD})
        code = self.last_otp()
        response = self.post("verify-email", {"email": "new@example.com", "otp": code})
        self.assertEqual(response.status_code, 200, response.json())
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)

    def test_unverified_new_email_blocks_future_logins_until_verified(self):
        self.patch({"email": "new@example.com", "current_password": PASSWORD})
        self.logout_client()
        response = self.post("login", {"email": "new@example.com", "password": PASSWORD})
        self.assertError(response, 403, "email_not_verified")

    def test_email_change_is_rolled_back_if_email_cannot_be_sent(self):
        with patch(
            "accounts.services.EmailMultiAlternatives.send",
            side_effect=smtplib.SMTPException("down"),
        ):
            response = self.patch(
                {"email": "new@example.com", "full_name": "Should Not Save", "current_password": PASSWORD}
            )
        self.assertError(response, 503, "email_delivery_failed")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "student@example.com")
        self.assertEqual(self.user.full_name, "Test Student")
        self.assertTrue(self.user.is_email_verified)


class UserModelTests(BaseAPITestCase):
    def test_email_uniqueness_is_enforced_by_the_database_case_insensitively(self):
        self.create_user(email="Case@Example.com", username="first")
        with self.assertRaises(IntegrityError), transaction.atomic():
            # Bypass the manager/save() normalisation to prove the DB constraint itself works.
            User.objects.bulk_create(
                [User(username="second", email="CASE@example.com", full_name="Second")]
            )

    def test_email_is_normalized_on_save(self):
        user = self.create_user(email="  MiXeD@Example.COM ", username="mixed")
        self.assertEqual(user.email, "mixed@example.com")

    def test_default_role_is_user_and_id_is_uuid(self):
        user = self.create_user()
        self.assertEqual(user.role, User.Role.USER)
        self.assertEqual(len(str(user.pk)), 36)

    def test_superuser_is_admin_and_verified(self):
        admin = User.objects.create_superuser(
            username="boss", email="boss@example.com", password=PASSWORD, full_name="Boss"
        )
        self.assertEqual(admin.role, User.Role.ADMIN)
        self.assertTrue(admin.is_email_verified)
        self.assertTrue(admin.is_staff and admin.is_superuser)
