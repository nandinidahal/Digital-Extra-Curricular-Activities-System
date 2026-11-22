"""
Shared test helpers for the DEAS modules built on Common (announcements, achievements,
notifications, integration tests). Not used at runtime.

* Every test gets throw-away MEDIA_ROOT and private-storage folders.
* Rate limits are relaxed; e-mail uses Django's in-memory test backend (locmem).
"""
import os
import shutil
import tempfile
from io import BytesIO

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User

PASSWORD = "Str0ng!Passw0rd#2026"

RELAXED = "100000/min"
TEST_SETTINGS = dict(
    SECURE_SSL_REDIRECT=False,
    MEDIA_URL="/media/",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    NOTIFICATIONS_EMAIL_ENABLED=True,
    FRONTEND_BASE_URL="http://localhost:5173",
    SOCIAL_THROTTLE_RATES={k: RELAXED for k in ("social_post", "social_comment", "social_interaction", "social_report")},
    FRIENDS_THROTTLE_RATES={"friends_request": RELAXED, "friends_action": RELAXED},
    ANNOUNCEMENTS_THROTTLE_RATES={
        k: RELAXED for k in ("announcement_write", "announcement_interaction", "announcement_report", "announcement_search")
    },
    ACHIEVEMENTS_THROTTLE_RATES={k: RELAXED for k in ("achievement_write", "achievement_upload", "achievement_review")},
    NOTIFICATIONS_THROTTLE_RATES={"notification_action": RELAXED},
)

MINIMAL_PDF = (
    b"%PDF-1.4\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
    b"2 0 obj << /Type /Pages /Kids [] /Count 0 >> endobj\n"
    b"trailer << /Root 1 0 R >>\n%%EOF\n"
)


def _redirect_storage(test, storage, prefix):
    root = tempfile.mkdtemp(prefix=prefix)
    saved = storage._location
    storage._location = root
    for attr in ("base_location", "location"):
        storage.__dict__.pop(attr, None)

    def restore():
        storage._location = saved
        for attr in ("base_location", "location"):
            storage.__dict__.pop(attr, None)
        shutil.rmtree(root, ignore_errors=True)

    test.addCleanup(restore)
    return root


class DEASHelpers:
    def setUp(self):
        super().setUp()
        cache.clear()
        media_root = tempfile.mkdtemp(prefix="deas_test_media_")
        media = override_settings(MEDIA_ROOT=media_root)
        media.enable()
        self.addCleanup(media.disable)
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)
        self.media_root = media_root
        from achievements.models import AchievementEvidence

        self.private_root = _redirect_storage(self, AchievementEvidence._meta.get_field("file").storage, "deas_test_private_")

    # ----- users ------------------------------------------------------------
    @staticmethod
    def make_user(username, **extra):
        return User.objects.create_user(
            username=username,
            email=extra.pop("email", f"{username}@example.com"),
            password=PASSWORD,
            full_name=extra.pop("full_name", f"{username.title()} Student"),
            is_email_verified=extra.pop("is_email_verified", True),
            **extra,
        )

    def login(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")

    def logout(self):
        self.client.credentials()

    @staticmethod
    def befriend(a, b):
        from friends.models import Friendship

        return Friendship.objects.create(user1=a, user2=b)

    @staticmethod
    def block(blocker, blocked):
        from friends.models import UserBlock

        return UserBlock.objects.create(blocker=blocker, blocked=blocked)

    # ----- files -------------------------------------------------------------
    @staticmethod
    def image_file(fmt="PNG", name=None, size=(60, 40), content_type=None):
        buffer = BytesIO()
        Image.new("RGB", size, (200, 30, 30)).save(buffer, fmt)
        ext = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "GIF": "gif"}[fmt]
        return SimpleUploadedFile(name or f"photo.{ext}", buffer.getvalue(), content_type or f"image/{'jpeg' if ext == 'jpg' else ext}")

    @staticmethod
    def pdf_file(name="certificate.pdf", content=MINIMAL_PDF):
        return SimpleUploadedFile(name, content, "application/pdf")

    def files_in(self, root):
        found = []
        for current, _dirs, files in os.walk(root):
            found.extend(os.path.join(current, f) for f in files)
        return found

    # ----- assertions --------------------------------------------------------
    def assertError(self, response, status_code, code=None):
        self.assertEqual(response.status_code, status_code, response.content[:500])
        body = response.json()
        self.assertFalse(body["success"])
        if code:
            self.assertEqual(body["code"], code, body)
        return body

    def assertOk(self, response, status_code=200):
        self.assertEqual(response.status_code, status_code, response.content[:800])
        body = response.json()
        self.assertTrue(body["success"], body)
        return body["data"]

    @staticmethod
    def ids(data):
        return [item["id"] for item in data["results"]]


@override_settings(**TEST_SETTINGS)
class DEASTestCase(DEASHelpers, APITestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        self.carol = self.make_user("carol")
        self.admin = self.make_user("admin1", role="admin")
        self.coordinator = self.make_user("coord1", role="coordinator")
