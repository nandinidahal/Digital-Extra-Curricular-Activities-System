"""Shared helpers for the profiles tests."""
import atexit
import os
import shutil
import tempfile
from io import BytesIO

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from profiles.models import Profile

PASSWORD = "Str0ng!Passw0rd#2026"

# Uploaded files go to a throw-away folder, never to the real MEDIA_ROOT.
TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="deas_test_media_")
atexit.register(shutil.rmtree, TEST_MEDIA_ROOT, ignore_errors=True)


@override_settings(
    MEDIA_ROOT=TEST_MEDIA_ROOT,
    MEDIA_URL="/media/",
    SECURE_SSL_REDIRECT=False,
    PROFILE_THROTTLE_RATES={"profile_upload": "100000/min"},
)
class ProfileTestCase(APITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        # A fresh, empty media folder per test so file assertions never see
        # files left behind by earlier tests.
        self.media_root = tempfile.mkdtemp(dir=TEST_MEDIA_ROOT)
        media_override = override_settings(MEDIA_ROOT=self.media_root)
        media_override.enable()
        self.addCleanup(media_override.disable)

    # ----- users / auth -----------------------------------------------------
    @staticmethod
    def make_user(username="student1", email="student1@example.com", **extra):
        return User.objects.create_user(
            username=username,
            email=email,
            password=PASSWORD,
            full_name=extra.pop("full_name", "Test Student"),
            is_email_verified=extra.pop("is_email_verified", True),
            **extra,
        )

    def login(self, user):
        """Authenticate with a real JWT access token."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")

    def logout(self):
        self.client.credentials()

    @staticmethod
    def profile_of(user):
        return Profile.objects.get(user=user)

    # ----- URLs -------------------------------------------------------------
    @staticmethod
    def url(name, **kwargs):
        return reverse(f"profiles:{name}", kwargs=kwargs or None)

    def detail_url(self, user):
        return self.url("detail", user_id=user.pk)

    # ----- images -----------------------------------------------------------
    @staticmethod
    def image_file(fmt="PNG", size=(60, 40), name=None, noisy=False, mode="RGB"):
        if noisy:
            image = Image.frombytes(mode, size, os.urandom(size[0] * size[1] * len(mode)))
        else:
            image = Image.new(mode, size, (200, 30, 30) if mode == "RGB" else 128)
        buffer = BytesIO()
        image.save(buffer, fmt)
        extension = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "GIF": "gif"}[fmt]
        content_type = f"image/{extension.replace('jpg', 'jpeg')}"
        return SimpleUploadedFile(name or f"photo.{extension}", buffer.getvalue(), content_type)

    def upload(self, name, file, **extra):
        return self.client.post(self.url(name), {"image": file}, format="multipart", **extra)

    def stored_files(self):
        found = []
        for root, _dirs, files in os.walk(self.media_root):
            found.extend(os.path.join(root, f) for f in files)
        return found

    def assertError(self, response, status_code, code):
        self.assertEqual(response.status_code, status_code, response.content)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["code"], code, body)
        return body
