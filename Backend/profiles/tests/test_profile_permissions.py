from django.test import override_settings

from accounts.models import User

from .base import ProfileTestCase


class ProfilePermissionTests(ProfileTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.other = self.make_user("other1", "other1@example.com")

    def test_all_own_endpoints_require_authentication(self):
        calls = [
            ("get", "me"), ("patch", "me"), ("patch", "me-privacy"),
            ("post", "me-picture"), ("delete", "me-picture"),
            ("post", "me-cover"), ("delete", "me-cover"),
        ]
        for method, name in calls:
            response = getattr(self.client, method)(self.url(name))
            self.assertEqual(response.status_code, 401, (method, name))
            body = response.json()
            self.assertFalse(body["success"])

    def test_profile_detail_has_no_write_methods(self):
        self.login(self.user)
        for method in ("patch", "put", "post", "delete"):
            response = getattr(self.client, method)(self.detail_url(self.other))
            self.assertEqual(response.status_code, 405, method)

    def test_me_endpoints_only_affect_the_caller(self):
        self.login(self.user)
        self.client.patch(self.url("me"), {"headline": "Mine"}, format="json")
        self.client.patch(self.url("me-privacy"), {"profile_visibility": "private"}, format="json")
        self.upload("me-picture", self.image_file())
        other = self.profile_of(self.other)
        self.assertEqual(other.headline, "")
        self.assertEqual(other.profile_visibility, "public")
        self.assertFalse(other.profile_picture)

    def test_profile_apis_cannot_change_role_or_credentials(self):
        self.login(self.user)
        self.client.patch(self.url("me"), {"role": "admin", "password": "Hacked#12345"}, format="json")
        self.client.patch(self.url("me-privacy"), {"role": "admin"}, format="json")
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.USER)
        self.assertTrue(self.user.check_password("Str0ng!Passw0rd#2026"))

    def test_jwt_bearer_authentication_works_and_wrong_scheme_fails(self):
        self.login(self.user)
        self.assertEqual(self.client.get(self.url("me")).status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION="Token abc")
        self.assertEqual(self.client.get(self.url("me")).status_code, 401)

    def test_deactivated_user_cannot_use_their_token(self):
        self.login(self.user)
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.client.get(self.url("me")).status_code, 401)

    @override_settings(CORS_ALLOWED_ORIGINS=["http://localhost:5173"])
    def test_cors_preflight_allows_authorization_and_patch(self):
        response = self.client.options(
            self.url("me"),
            HTTP_ORIGIN="http://localhost:5173",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="PATCH",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization,content-type",
        )
        self.assertEqual(response["Access-Control-Allow-Origin"], "http://localhost:5173")
        self.assertIn("PATCH", response["Access-Control-Allow-Methods"])
        self.assertIn("authorization", response["Access-Control-Allow-Headers"])
