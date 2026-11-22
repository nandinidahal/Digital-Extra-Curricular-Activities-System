"""
Cross-module integration tests through the real HTTP APIs: every notification here is caused by a
real, successful action in Accounts, Friends, Messaging, Social, Announcements or Achievements.
Also checks that private resources and blocks cannot be bypassed across modules.
"""
import datetime
from unittest import mock

from django.core import mail
from django.test import override_settings
from django.utils import timezone

from achievements.models import Achievement
from announcements.models import Announcement, Category
from common.testing import DEASTestCase
from notifications.models import Notification
from social.models import Post


def kinds(user):
    return list(Notification.objects.filter(recipient=user).order_by("created_at").values_list("notification_type", flat=True))


@override_settings(
    MESSAGING_THROTTLE_RATES={k: "100000/min" for k in ("messaging_send", "messaging_action", "messaging_upload", "messaging_ws_event")},
    AUTH_THROTTLE_RATES={k: "100000/min" for k in (
        "register", "login", "login_email", "otp_verify", "otp_request_ip", "otp_request_email",
        "otp_request_email_burst", "password_reset", "token_refresh", "password_change")},
)
class CrossModuleNotificationTests(DEASTestCase):
    # ----- Friends ------------------------------------------------------------
    def send_request(self, sender, receiver):
        self.login(sender)
        with self.captureOnCommitCallbacks(execute=True):
            body = self.assertOk(self.client.post("/api/friends/requests/", {"receiver_id": str(receiver.pk)}, format="json"), 201)
        return body["request"]["id"]

    def test_friend_request_generates_notification(self):
        self.send_request(self.alice, self.bob)
        note = Notification.objects.get(recipient=self.bob)
        self.assertEqual((note.notification_type, note.actor, note.action_url), ("friend_request.received", self.alice, "/friends/requests"))
        self.assertEqual(kinds(self.alice), [])

    def test_accepted_friend_request_generates_notification(self):
        request_id = self.send_request(self.alice, self.bob)
        self.login(self.bob)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertOk(self.client.post(f"/api/friends/requests/{request_id}/accept/"))
        self.assertEqual(kinds(self.alice), ["friend_request.accepted"])
        self.assertTrue(Notification.objects.get(recipient=self.bob).is_read)  # the request notice is done

    def test_rejected_and_cancelled_requests(self):
        request_id = self.send_request(self.alice, self.bob)
        self.login(self.bob)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/api/friends/requests/{request_id}/reject/")
        self.assertEqual(kinds(self.alice), ["friend_request.rejected"])
        request_id = self.send_request(self.carol, self.bob)
        self.login(self.carol)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/api/friends/requests/{request_id}/cancel/")
        self.assertFalse(Notification.objects.filter(recipient=self.bob, actor=self.carol).exists())

    def test_friend_removed_but_block_never_revealed(self):
        self.befriend(self.alice, self.bob)
        self.befriend(self.alice, self.carol)
        self.login(self.alice)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.delete(f"/api/friends/{self.bob.pk}/")
            self.client.post("/api/friends/blocked/", {"user_id": str(self.carol.pk)}, format="json")
        self.assertEqual(kinds(self.bob), ["friend.removed"])
        self.assertEqual(kinds(self.carol), [])

    # ----- Messaging -------------------------------------------------------------
    def start_conversation(self, a, b):
        self.login(a)
        return self.assertOk(self.client.post("/api/messaging/conversations/", {"user_id": str(b.pk)}, format="json"), 201)["id"]

    def test_new_messages_generate_one_grouped_notification(self):
        self.befriend(self.alice, self.bob)
        conversation_id = self.start_conversation(self.alice, self.bob)
        with self.captureOnCommitCallbacks(execute=True):
            for text in ("hi", "are you there?", "ping"):
                self.assertOk(self.client.post(f"/api/messaging/conversations/{conversation_id}/messages/", {"content": text}, format="json"), 201)
        note = Notification.objects.get(recipient=self.bob)
        self.assertEqual((note.notification_type, note.metadata["count"]), ("message.received", 3))
        self.assertNotIn("ping", note.message)  # message content is never copied
        self.login(self.bob)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/api/messaging/conversations/{conversation_id}/read/", {}, format="json")
        note.refresh_from_db()
        self.assertTrue(note.is_read)

    def test_muted_conversation_not_notified(self):
        self.befriend(self.alice, self.bob)
        conversation_id = self.start_conversation(self.alice, self.bob)
        self.login(self.bob)
        self.client.patch(f"/api/messaging/conversations/{conversation_id}/mute/", {"is_muted": True}, format="json")
        self.login(self.alice)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/api/messaging/conversations/{conversation_id}/messages/", {"content": "hi"}, format="json")
        self.assertEqual(kinds(self.bob), [])

    # ----- Accounts ----------------------------------------------------------------
    def test_password_change_notifies_and_emails(self):
        from common.testing import PASSWORD

        self.login(self.alice)
        new = "N3w!Passw0rd#2026x"
        with self.captureOnCommitCallbacks(execute=True):
            self.assertOk(self.client.post("/api/auth/change-password/", {
                "current_password": PASSWORD, "new_password": new, "confirm_password": new}, format="json"))
        note = Notification.objects.get(recipient=self.alice)
        self.assertEqual((note.notification_type, note.email_status), ("account.password_changed", "sent"))
        self.assertTrue(any("Password changed" in m.subject for m in mail.outbox))

    def test_email_verification_welcomes_once(self):
        from accounts import services as account_services
        from accounts.models import OneTimePassword

        user = self.make_user("newbie", is_email_verified=False)
        for expected in (["account.welcome"], ["account.welcome", "account.email_verified"]):
            with mock.patch("accounts.services.generate_otp", return_value="123456"):
                account_services.create_and_send_otp(user, OneTimePassword.Purpose.EMAIL_VERIFICATION, enforce_limits=False)
            with self.captureOnCommitCallbacks(execute=True):
                self.assertOk(self.client.post("/api/auth/verify-email/", {"email": user.email, "otp": "123456"}, format="json"))
            self.assertEqual(kinds(user), expected)
            user.is_email_verified = False
            user.save()

    # ----- Social / Announcements / Achievements -----------------------------------
    def test_post_like_generates_notification(self):
        post = Post.objects.create(author=self.alice, content="Our team won!")
        self.login(self.bob)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/api/social/posts/{post.pk}/like/")
        self.assertEqual(kinds(self.alice), ["post.liked"])

    def test_announcement_publication_generates_notification(self):
        self.befriend(self.alice, self.bob)
        self.login(self.alice)
        payload = {
            "title": "Coding Bootcamp", "short_description": "Learn Python", "description": "Three days of code",
            "category": str(Category.objects.get(slug="technology").pk), "activity_type": "online",
            "online_link": "https://meet.example.com/bootcamp",
            "start_datetime": (timezone.now() + datetime.timedelta(days=5)).isoformat(),
        }
        with self.captureOnCommitCallbacks(execute=True):
            announcement_id = self.assertOk(self.client.post("/api/announcements/", payload, format="json"), 201)["announcement"]["id"]
            self.assertOk(self.client.post(f"/api/announcements/{announcement_id}/publish/"))
        self.assertEqual(kinds(self.bob), ["announcement.published"])
        self.assertEqual(kinds(self.alice), ["announcement.created"])

    def test_achievement_verification_generates_notification(self):
        self.login(self.alice)
        with self.captureOnCommitCallbacks(execute=True):
            achievement_id = self.assertOk(self.client.post("/api/achievements/", {
                "title": "Science Olympiad Gold", "achievement_date": "2026-04-01", "level": "national"}, format="json"), 201)["achievement"]["id"]
        self.assertEqual(kinds(self.coordinator), ["achievement.submitted"])
        self.login(self.coordinator)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertOk(self.client.post(f"/api/achievements/{achievement_id}/verify/"))
        self.assertEqual(kinds(self.alice), ["achievement.verified"])
        self.assertTrue(Notification.objects.get(recipient=self.coordinator).is_read)
        self.assertEqual(Notification.objects.get(recipient=self.alice).email_status, "sent")

    def test_notification_api_reflects_events(self):
        post = Post.objects.create(author=self.alice, content="x")
        self.login(self.bob)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/api/social/posts/{post.pk}/like/")
        self.login(self.alice)
        self.assertEqual(self.assertOk(self.client.get("/api/notifications/unread-count/"))["unread_count"], 1)
        self.login(self.bob)
        self.assertEqual(self.assertOk(self.client.get("/api/notifications/unread-count/"))["unread_count"], 0)


class CrossModulePrivacyTests(DEASTestCase):
    def setUp(self):
        super().setUp()
        category = Category.objects.get(slug="technology")
        self.private_announcement = Announcement.objects.create(
            author=self.alice, title="Private planning", slug="private-planning", category=category,
            status="published", published_at=timezone.now(), visibility="private",
        )
        self.private_achievement = Achievement.objects.create(
            user=self.alice, title="Private award", achievement_date=datetime.date(2026, 1, 1),
            verification_status="verified", verified_at=timezone.now(), submitted_at=timezone.now(), visibility="private",
        )
        self.private_post = Post.objects.create(author=self.alice, content="Diary", visibility="private")

    def test_private_resources_inaccessible_everywhere(self):
        self.login(self.bob)
        self.assertError(self.client.get(f"/api/announcements/{self.private_announcement.pk}/"), 404)
        self.assertError(self.client.get(f"/api/achievements/{self.private_achievement.pk}/"), 404)
        self.assertError(self.client.get(f"/api/social/posts/{self.private_post.pk}/"), 404)
        self.assertError(self.client.post("/api/social/shares/", {"resource_type": "announcement", "resource_id": str(self.private_announcement.pk)}, format="json"), 404)
        self.assertError(self.client.post("/api/social/shares/", {"resource_type": "achievement", "resource_id": str(self.private_achievement.pk)}, format="json"), 404)
        self.assertError(self.client.post(f"/api/announcements/{self.private_announcement.pk}/bookmark/"), 404)
        self.assertError(self.client.post("/api/achievements/", {
            "title": "Linked", "achievement_date": "2026-01-02", "related_announcement": str(self.private_announcement.pk)}, format="json"), 400)
        for path in ("/api/social/feed/", "/api/announcements/search/?q=private", "/api/achievements/search/?q=private"):
            self.assertNotIn("Private", self.client.get(path).content.decode(), path)

    def test_blocked_user_cannot_bypass_through_social_or_messaging(self):
        public_post = Post.objects.create(author=self.alice, content="Public news")
        self.block(self.alice, self.bob)
        self.login(self.bob)
        self.assertError(self.client.get(f"/api/social/posts/{public_post.pk}/"), 404)
        self.assertError(self.client.post("/api/social/shares/", {"resource_type": "post", "resource_id": str(public_post.pk)}, format="json"), 404)
        self.assertError(self.client.post("/api/social/reports/", {"content_type": "post", "object_id": str(public_post.pk), "reason": "spam"}, format="json"), 404)
        response = self.client.post("/api/messaging/conversations/", {"user_id": str(self.alice.pk)}, format="json")
        self.assertIn(response.status_code, (403, 404))
        with self.captureOnCommitCallbacks(execute=True):
            from notifications.services import create_notification

            self.assertIsNone(create_notification(recipient=self.alice, actor=self.bob, notification_type="post.liked"))
        self.assertEqual(kinds(self.alice), [])
