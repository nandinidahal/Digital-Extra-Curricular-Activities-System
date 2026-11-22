"""Shared helpers for the social tests."""
import atexit
import os
import shutil
import tempfile
from io import BytesIO

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from social.models import Comment, Post

PASSWORD = "Str0ng!Passw0rd#2026"

# Uploaded files go to a throw-away folder, never to the real MEDIA_ROOT.
TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="deas_social_test_media_")
atexit.register(shutil.rmtree, TEST_MEDIA_ROOT, ignore_errors=True)


@override_settings(
    MEDIA_ROOT=TEST_MEDIA_ROOT,
    MEDIA_URL="/media/",
    SECURE_SSL_REDIRECT=False,
    SOCIAL_THROTTLE_RATES={
        "social_post": "100000/min",
        "social_comment": "100000/min",
        "social_interaction": "100000/min",
        "social_report": "100000/min",
    },
)
class SocialTestCase(APITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        # A fresh, empty media folder per test so file assertions never see
        # files left behind by earlier tests.
        self.media_root = tempfile.mkdtemp(dir=TEST_MEDIA_ROOT)
        media_override = override_settings(MEDIA_ROOT=self.media_root)
        media_override.enable()
        self.addCleanup(media_override.disable)
        self.alice = self.make_user("alice", "alice@example.com", full_name="Alice Student")
        self.bob = self.make_user("bob", "bob@example.com", full_name="Bob Student")
        self.admin = self.make_user("admin1", "admin1@example.com", role="admin")

    # ----- users / auth -----------------------------------------------------
    @staticmethod
    def make_user(username, email, **extra):
        return User.objects.create_user(
            username=username,
            email=email,
            password=PASSWORD,
            full_name=extra.pop("full_name", "Test User"),
            is_email_verified=extra.pop("is_email_verified", True),
            **extra,
        )

    def login(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")

    def logout(self):
        self.client.credentials()

    # ----- data builders (ORM, so tests do not depend on the API they test) --
    @staticmethod
    def make_post(author, content="Hello world", visibility="public", post_type="general", **extra):
        return Post.objects.create(
            author=author, content=content, visibility=visibility, post_type=post_type, **extra
        )

    @staticmethod
    def make_comment(post, author, content="Nice!", parent=None):
        depth = parent.depth + 1 if parent else 0
        return Comment.objects.create(
            post=post, author=author, content=content, parent_comment=parent, depth=depth
        )

    @staticmethod
    def set_created(post, when):
        Post.objects.filter(pk=post.pk).update(created_at=when)

    # ----- URLs -------------------------------------------------------------
    @staticmethod
    def url(name, **kwargs):
        return reverse(f"social:{name}", kwargs=kwargs or None)

    # ----- images -----------------------------------------------------------
    @staticmethod
    def image_file(fmt="PNG", size=(60, 40), name=None, noisy=False):
        if noisy:
            image = Image.frombytes("RGB", size, os.urandom(size[0] * size[1] * 3))
        else:
            image = Image.new("RGB", size, (200, 30, 30))
        buffer = BytesIO()
        image.save(buffer, fmt)
        extension = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "GIF": "gif"}[fmt]
        content_type = f"image/{extension.replace('jpg', 'jpeg')}"
        return SimpleUploadedFile(name or f"photo.{extension}", buffer.getvalue(), content_type)

    def stored_files(self):
        found = []
        for root, _dirs, files in os.walk(self.media_root):
            found.extend(os.path.join(root, f) for f in files)
        return found

    # ----- API helpers ------------------------------------------------------
    def create_post_api(self, **data):
        return self.client.post(self.url("post-list"), data, format="json")

    def assertError(self, response, status_code, code=None):
        self.assertEqual(response.status_code, status_code, response.content)
        body = response.json()
        self.assertFalse(body["success"])
        if code:
            self.assertEqual(body["code"], code, body)
        return body

    @staticmethod
    def data(response):
        return response.json()["data"]

    @staticmethod
    def now():
        return timezone.now()
