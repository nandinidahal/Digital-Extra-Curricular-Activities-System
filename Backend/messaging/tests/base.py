"""Shared helpers for the messaging tests."""
import os
import shutil
import tempfile
from io import BytesIO

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from friends.models import Friendship, UserBlock
from messaging.models import Conversation, ConversationParticipant, MessageAttachment, direct_key_for

PASSWORD = "Str0ng!Passw0rd#2026"
RELAXED_RATES = {
    "messaging_send": "100000/min",
    "messaging_action": "100000/min",
    "messaging_upload": "100000/min",
    "messaging_ws_event": "100000/min",
}
TEST_SETTINGS = dict(
    SECURE_SSL_REDIRECT=False,
    MESSAGING_THROTTLE_RATES=RELAXED_RATES,
    FRIENDS_THROTTLE_RATES={"friends_request": "100000/min", "friends_action": "100000/min"},
    MESSAGING_NON_FRIEND_MESSAGE_LIMIT=4,
    MESSAGING_EDIT_WINDOW_MINUTES=15,
    MESSAGING_DELETE_FOR_EVERYONE_WINDOW_MINUTES=60,
    MESSAGING_PRESENCE_VISIBILITY="friends",
)


def private_storage():
    return MessageAttachment._meta.get_field("file").storage


class MessagingHelpers:
    """Mixed into both APITestCase and TransactionTestCase based classes."""

    def setUp(self):
        super().setUp()
        cache.clear()
        # Attachments go to a throw-away folder, never to the real PRIVATE_MEDIA_ROOT.
        self.private_root = tempfile.mkdtemp(prefix="deas_msg_test_")
        storage = private_storage()
        saved = storage._location
        storage._location = self.private_root
        for attr in ("base_location", "location"):
            storage.__dict__.pop(attr, None)

        def restore():
            storage._location = saved
            for attr in ("base_location", "location"):
                storage.__dict__.pop(attr, None)
            shutil.rmtree(self.private_root, ignore_errors=True)

        self.addCleanup(restore)

    # ----- users ------------------------------------------------------------
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

    @staticmethod
    def befriend(a, b):
        return Friendship.objects.create(user1=a, user2=b)

    @staticmethod
    def unfriend(a, b):
        low, high = Friendship.normalize(a.pk, b.pk)
        Friendship.objects.filter(user1_id=low, user2_id=high).delete()

    @staticmethod
    def block(blocker, blocked):
        return UserBlock.objects.create(blocker=blocker, blocked=blocked)

    @staticmethod
    def make_conversation(a, b):
        conversation = Conversation.objects.create(
            conversation_type="direct", direct_key=direct_key_for(a.pk, b.pk), created_by=a
        )
        ConversationParticipant.objects.create(conversation=conversation, user=a)
        ConversationParticipant.objects.create(conversation=conversation, user=b)
        return conversation

    # ----- files ------------------------------------------------------------
    @staticmethod
    def image_file(fmt="PNG", name=None, size=(60, 40)):
        buffer = BytesIO()
        Image.new("RGB", size, (200, 30, 30)).save(buffer, fmt)
        ext = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "GIF": "gif"}[fmt]
        return SimpleUploadedFile(name or f"photo.{ext}", buffer.getvalue(), f"image/{ext.replace('jpg', 'jpeg')}")

    @staticmethod
    def pdf_file(name="notes.pdf", body=b"1 0 obj << /Type /Catalog >> endobj"):
        data = b"%PDF-1.4\n" + body + b"\ntrailer << /Root 1 0 R >>\n%%EOF\n"
        return SimpleUploadedFile(name, data, "application/pdf")

    def stored_files(self):
        found = []
        for root, _dirs, files in os.walk(self.private_root):
            found.extend(os.path.join(root, f) for f in files)
        return found


@override_settings(**TEST_SETTINGS)
class MessagingTestCase(MessagingHelpers, APITestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        self.carol = self.make_user("carol")

    # ----- auth / requests ----------------------------------------------------
    def login(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")

    def logout(self):
        self.client.credentials()

    def client_for(self, user):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
        return client

    @staticmethod
    def url(name, **kwargs):
        return reverse(f"messaging:{name}", kwargs=kwargs or None)

    def start(self, user, other):
        response = self.client_for(user).post(self.url("conversations"), {"user_id": str(other.pk)}, format="json")
        assert response.status_code in (200, 201), response.content
        return response.json()["data"]["id"]

    def send(self, user, conversation_id, content="hello", **extra):
        return self.client_for(user).post(
            self.url("conversation-messages", conversation_id=conversation_id),
            {"content": content, **extra}, format="json",
        )

    def send_ok(self, user, conversation_id, content="hello", **extra):
        response = self.send(user, conversation_id, content, **extra)
        assert response.status_code == 201, response.content
        return response.json()["data"]["message"]

    def messages(self, user, conversation_id, query=""):
        response = self.client_for(user).get(
            self.url("conversation-messages", conversation_id=conversation_id) + query
        )
        assert response.status_code == 200, response.content
        return response.json()["data"]["results"]

    def assertError(self, response, status_code, code):
        self.assertEqual(response.status_code, status_code, response.content)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["code"], code, body)
        return body

    @staticmethod
    def data(response):
        return response.json()["data"]
