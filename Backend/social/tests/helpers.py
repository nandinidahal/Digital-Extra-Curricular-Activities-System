"""Shared test helpers for the social, friends and messaging test suites.

(This file was missing from the uploaded project although three test modules import it;
it has been rebuilt from how those tests use it.)
"""
import io

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import User
from friends.models import Friendship
from friends.selectors import ordered_pair

PASSWORD = "Str0ng!Passw0rd"


def make_user(username, **extra):
    extra.setdefault("is_active", True)
    extra.setdefault("is_email_verified", True)
    return User.objects.create_user(
        username=username, email=f"{username}@example.com", password=PASSWORD,
        full_name=username.title(), phone_number="+9779800000000", country="Nepal", **extra,
    )


def make_friends(u1, u2):
    low, high = ordered_pair(u1.pk, u2.pk)
    return Friendship.objects.get_or_create(user_low_id=low, user_high_id=high)[0]


def png(name="img.png", size=(8, 8)):
    buf = io.BytesIO()
    Image.new("RGB", size, "red").save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class ApiTestCase(TestCase):
    """alice/bob/carol with ready-to-use authenticated clients self.a / self.b / self.c."""

    def setUp(self):
        cache.clear()  # throttle counters live in the cache
        self.alice, self.bob, self.carol = make_user("alice"), make_user("bob"), make_user("carol")
        self.a, self.b, self.c = self.as_user(self.alice), self.as_user(self.bob), self.as_user(self.carol)

    @staticmethod
    def as_user(user):
        client = APIClient()
        client.force_authenticate(user)  # works for inactive users too (tests expect 403, not 401)
        return client

    def new_post(self, who, caption="a post", visibility="friends", **extra):
        """`who` may be a User or an already-authenticated client."""
        client = self.as_user(who) if isinstance(who, User) else who
        r = client.post("/api/social/posts/", {"caption": caption, "visibility": visibility, **extra}, format="json")
        assert r.status_code == 201, r.content
        return r.data["id"]
