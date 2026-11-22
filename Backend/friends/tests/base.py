"""Shared helpers for the friends tests."""
from datetime import timedelta

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from friends.models import FriendRequest, Friendship, UserBlock

PASSWORD = "Str0ng!Passw0rd#2026"
RELAXED_RATES = {"friends_request": "100000/min", "friends_action": "100000/min"}


@override_settings(SECURE_SSL_REDIRECT=False, FRIENDS_THROTTLE_RATES=RELAXED_RATES)
class FriendsTestCase(APITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    # ----- users / auth -----------------------------------------------------
    @staticmethod
    def make_user(username, **extra):
        return User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password=PASSWORD,
            full_name=extra.pop("full_name", f"{username.title()} Student"),
            is_email_verified=extra.pop("is_email_verified", True),
            **extra,
        )

    def login(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")

    def logout(self):
        self.client.credentials()

    # ----- requests ---------------------------------------------------------
    @staticmethod
    def url(name, **kwargs):
        return reverse(f"friends:{name}", kwargs=kwargs or None)

    def get(self, name, query="", **kwargs):
        return self.client.get(self.url(name, **kwargs) + query)

    def post(self, name, data=None, **kwargs):
        return self.client.post(self.url(name, **kwargs), data or {}, format="json")

    def delete(self, name, **kwargs):
        return self.client.delete(self.url(name, **kwargs))

    @staticmethod
    def data(response):
        return response.json()["data"]

    def assertError(self, response, status_code, code):
        self.assertEqual(response.status_code, status_code, response.content)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["code"], code, body)
        return body

    # ----- database fixtures (bypass the API on purpose) ----------------------
    @staticmethod
    def befriend(a, b):
        return Friendship.objects.create(user1=a, user2=b)  # save() normalises the order

    @staticmethod
    def make_request(sender, receiver, status=FriendRequest.Status.PENDING):
        responded = None if status == FriendRequest.Status.PENDING else timezone.now()
        return FriendRequest.objects.create(
            sender=sender, receiver=receiver, status=status, responded_at=responded
        )

    @staticmethod
    def block(blocker, blocked):
        return UserBlock.objects.create(blocker=blocker, blocked=blocked)

    @staticmethod
    def hours_ago(hours):
        return timezone.now() - timedelta(hours=hours)
