"""Notifications module: service rules, REST API, preferences, e-mail delivery, WebSockets."""
import asyncio
from datetime import timedelta
from io import StringIO
from unittest import mock

from channels.testing import WebsocketCommunicator
from django.core import mail
from django.core.management import call_command
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken

from common.testing import TEST_SETTINGS, DEASHelpers, DEASTestCase
from notifications import services
from notifications.models import Notification, NotificationPreference

BASE = "/api/notifications/"


class ServiceRuleTests(DEASTestCase):
    def create(self, **kwargs):
        kwargs.setdefault("recipient", self.alice)
        kwargs.setdefault("notification_type", "post.liked")
        kwargs.setdefault("actor", self.bob)
        return services.create_notification(**kwargs)

    def test_create_renders_title_and_message(self):
        note = self.create(target_type="post", target_id="abc", action_url="/social/posts/abc")
        self.assertEqual((note.title, note.message, note.category), ("New like", "Bob Student liked your post.", "social"))
        self.assertEqual(note.email_status, "not_requested")

    def test_unknown_type_is_a_programming_error(self):
        with self.assertRaises(ValueError):
            self.create(notification_type="post.exploded")

    def test_self_action_not_notified_except_account(self):
        self.assertIsNone(self.create(actor=self.alice))
        self.assertIsNotNone(self.create(notification_type="account.password_changed", actor=self.alice))

    def test_inactive_recipient_skipped(self):
        self.alice.is_active = False
        self.alice.save()
        self.assertIsNone(self.create())

    def test_blocked_actor_suppressed(self):
        self.block(self.alice, self.bob)
        self.assertIsNone(self.create())
        self.assertIsNotNone(self.create(notification_type="account.security_alert", actor=None, context={"detail": "x"}))

    def test_preferences_respected_but_security_always_on(self):
        NotificationPreference.objects.create(user=self.alice, social_interactions=False)
        self.assertIsNone(self.create())
        self.assertIsNotNone(self.create(notification_type="account.password_changed", actor=None))

    def test_dedupe_key_is_idempotent(self):
        self.assertIsNotNone(self.create(dedupe_key="post.liked:1:2"))
        self.assertIsNone(self.create(dedupe_key="post.liked:1:2"))
        self.assertEqual(Notification.objects.count(), 1)

    def test_group_key_collapses_unread(self):
        first = self.create(notification_type="message.received", group_key="message.received:c1")
        second = self.create(notification_type="message.received", group_key="message.received:c1", actor=self.carol)
        self.assertEqual(first.pk, second.pk)
        first.refresh_from_db()
        self.assertEqual((first.metadata["count"], first.actor), (2, self.carol))
        services.mark_read(self.alice, first.pk)
        third = self.create(notification_type="message.received", group_key="message.received:c1")
        self.assertNotEqual(third.pk, first.pk)

    def test_metadata_sanitised_and_action_url_validated(self):
        note = self.create(metadata={"post_id": "p1", "password": "x", "email": "a@b.c", "nested": {"token": "t", "ok": 1}})
        self.assertEqual(note.metadata, {"post_id": "p1", "nested": {"ok": 1}})
        for bad in ("https://evil.example.com", "//evil.example.com", "javascript:alert(1)"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.create(action_url=bad)
        with self.assertRaises(ValueError):
            self.create(metadata={f"k{i}": "v" * 290 for i in range(20)})  # > 4 KB after sanitising

    def test_notify_runs_only_after_commit(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            services.notify(recipient=self.alice.pk, actor=self.bob.pk, notification_type="post.liked")
        self.assertEqual(Notification.objects.count(), 0)
        for callback in callbacks:
            callback()
        self.assertEqual(Notification.objects.count(), 1)

    def test_notify_never_raises(self):
        with self.captureOnCommitCallbacks(execute=True):
            services.notify(recipient=self.alice.pk, notification_type="does.not.exist")
        self.assertEqual(Notification.objects.count(), 0)

    def test_bulk_creation_applies_rules(self):
        NotificationPreference.objects.create(user=self.carol, announcements=False)
        self.block(self.alice, self.admin)
        ids = services.create_bulk(
            recipient_ids=[self.alice.pk, self.bob.pk, self.carol.pk, self.admin.pk], notification_type="announcement.published",
            actor=self.alice, context={"title": "Hackathon"}, dedupe_key="announcement.published:1",
        )
        self.assertEqual(list(Notification.objects.filter(pk__in=ids).values_list("recipient__username", flat=True)), ["bob"])
        again = services.create_bulk(recipient_ids=[self.bob.pk], notification_type="announcement.published", actor=self.alice, dedupe_key="announcement.published:1")
        self.assertEqual(again, [])

    def test_expired_notifications_hidden(self):
        self.create(expires_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(services.unread_count(self.alice), 0)


class ApiTests(DEASTestCase):
    def setUp(self):
        super().setUp()
        self.n1 = services.create_notification(recipient=self.alice, actor=self.bob, notification_type="post.liked")
        self.n2 = services.create_notification(recipient=self.alice, actor=self.carol, notification_type="friend_request.received")
        self.other = services.create_notification(recipient=self.bob, actor=self.carol, notification_type="post.liked")

    def test_requires_authentication(self):
        for method, path in (("get", BASE), ("get", BASE + "unread-count/"), ("post", BASE + "read-all/"), ("get", BASE + "preferences/")):
            self.assertError(getattr(self.client, method)(path), 401)

    def test_list_only_own_newest_first_with_filters(self):
        self.login(self.alice)
        data = self.assertOk(self.client.get(BASE))
        self.assertEqual(self.ids(data), [str(self.n2.pk), str(self.n1.pk)])
        self.assertEqual(data["results"][0]["actor"]["username"], "carol")
        self.assertEqual(self.ids(self.assertOk(self.client.get(BASE + "?category=social"))), [str(self.n1.pk)])
        self.assertEqual(self.ids(self.assertOk(self.client.get(BASE + "?type=friend_request.received"))), [str(self.n2.pk)])
        self.assertError(self.client.get(BASE + "?category=nope"), 400)

    def test_unread_count_and_mark_read(self):
        self.login(self.alice)
        self.assertEqual(self.assertOk(self.client.get(BASE + "unread-count/"))["unread_count"], 2)
        data = self.assertOk(self.client.post(f"{BASE}{self.n1.pk}/read/"))
        self.assertTrue(data["notification"]["is_read"])
        self.assertEqual(data["unread_count"], 1)
        self.assertEqual(self.ids(self.assertOk(self.client.get(BASE + "?is_read=false"))), [str(self.n2.pk)])
        self.assertEqual(self.assertOk(self.client.post(f"{BASE}{self.n1.pk}/unread/"))["unread_count"], 2)

    def test_mark_all_read(self):
        self.login(self.alice)
        self.assertEqual(self.assertOk(self.client.post(BASE + "read-all/"))["updated"], 2)
        self.assertEqual(services.unread_count(self.alice), 0)
        self.assertEqual(services.unread_count(self.bob), 1)  # other users untouched

    def test_cannot_touch_other_users_notifications(self):
        self.login(self.alice)
        for method, path in (("post", f"{BASE}{self.other.pk}/read/"), ("delete", f"{BASE}{self.other.pk}/"), ("get", f"{BASE}{self.other.pk}/")):
            self.assertError(getattr(self.client, method)(path), 404, "notification_not_found")
        self.other.refresh_from_db()
        self.assertFalse(self.other.is_read)

    def test_delete_and_clear(self):
        self.login(self.alice)
        self.assertOk(self.client.delete(f"{BASE}{self.n1.pk}/"))
        self.assertFalse(Notification.objects.filter(pk=self.n1.pk).exists())
        services.mark_read(self.alice, self.n2.pk)
        services.create_notification(recipient=self.alice, actor=self.bob, notification_type="post.commented")
        self.assertEqual(self.assertOk(self.client.delete(BASE + "clear/?read_only=true"))["deleted"], 1)
        self.assertEqual(self.assertOk(self.client.delete(BASE + "clear/"))["deleted"], 1)
        self.assertEqual(Notification.objects.filter(recipient=self.alice).count(), 0)
        self.assertTrue(Notification.objects.filter(pk=self.other.pk).exists())

    def test_preferences(self):
        self.login(self.alice)
        prefs = self.assertOk(self.client.get(BASE + "preferences/"))["preferences"]
        self.assertTrue(all(prefs[k] for k in NotificationPreference.SWITCHES))
        self.assertIn("account.security_alert", prefs["always_on"])
        prefs = self.assertOk(self.client.patch(BASE + "preferences/", {"messages": False, "email_notifications": False}, format="json"))["preferences"]
        self.assertFalse(prefs["messages"])
        self.assertError(self.client.patch(BASE + "preferences/", {"user": str(self.bob.pk)}, format="json"), 400)
        self.assertError(self.client.patch(BASE + "preferences/", {"messages": "maybe"}, format="json"), 400)
        self.assertError(self.client.patch(BASE + "preferences/", {"security_alerts": False}, format="json"), 400)


class EmailTests(DEASTestCase):
    def test_eligible_type_is_emailed_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            note = services.create_notification(
                recipient=self.alice, notification_type="account.password_changed", action_url="/settings/security"
            )
        note.refresh_from_db()
        self.assertEqual(note.email_status, "sent")
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["alice@example.com"])
        self.assertIn("Password changed", message.subject)
        self.assertIn("http://localhost:5173/settings/security", message.body)

    def test_low_value_types_never_emailed(self):
        with self.captureOnCommitCallbacks(execute=True):
            services.create_notification(recipient=self.alice, actor=self.bob, notification_type="post.liked")
        self.assertEqual(mail.outbox, [])

    def test_email_preference_respected_except_security(self):
        NotificationPreference.objects.create(user=self.alice, email_notifications=False)
        with self.captureOnCommitCallbacks(execute=True):
            services.create_notification(recipient=self.alice, actor=self.admin, notification_type="achievement.verified", context={"title": "x"})
            services.create_notification(recipient=self.alice, notification_type="account.security_alert", context={"detail": "Reset"})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Security alert", mail.outbox[0].subject)

    def test_unverified_email_not_used(self):
        self.alice.is_email_verified = False
        self.alice.save()
        with self.captureOnCommitCallbacks(execute=True):
            note = services.create_notification(recipient=self.alice, notification_type="account.password_changed")
        self.assertEqual((note.email_status, len(mail.outbox)), ("not_requested", 0))

    @override_settings(NOTIFICATIONS_EMAIL_ENABLED=False)
    def test_global_switch(self):
        with self.captureOnCommitCallbacks(execute=True):
            services.create_notification(recipient=self.alice, notification_type="account.password_changed")
        self.assertEqual(mail.outbox, [])

    def test_failure_is_recorded_and_retried_not_claimed_as_sent(self):
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("smtp down")):
            with self.captureOnCommitCallbacks(execute=True):
                note = services.create_notification(recipient=self.alice, notification_type="account.password_changed")
        note.refresh_from_db()
        self.assertEqual((note.email_status, note.email_attempts, note.emailed_at), ("failed", 1, None))
        out = StringIO()
        call_command("send_notification_emails", stdout=out)
        note.refresh_from_db()
        self.assertEqual((note.email_status, note.email_attempts), ("sent", 2))
        self.assertIn("Sent 1 of 1", out.getvalue())
        call_command("send_notification_emails", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)  # never sent twice

    def test_backend_returning_zero_is_failure(self):
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", return_value=0):
            with self.captureOnCommitCallbacks(execute=True):
                note = services.create_notification(recipient=self.alice, notification_type="account.password_changed")
        note.refresh_from_db()
        self.assertEqual(note.email_status, "failed")

    def test_email_contains_no_metadata(self):
        with self.captureOnCommitCallbacks(execute=True):
            services.create_notification(
                recipient=self.alice, notification_type="account.security_alert",
                context={"detail": "Reset done"}, metadata={"internal_ref": "SECRET-REF-123"},
            )
        self.assertNotIn("SECRET-REF-123", mail.outbox[0].body)
        self.assertNotIn("SECRET-REF-123", mail.outbox[0].alternatives[0][0])


class CleanupCommandTests(DEASTestCase):
    def test_cleanup_removes_expired_and_old_read(self):
        keep = services.create_notification(recipient=self.alice, actor=self.bob, notification_type="post.liked")
        expired = services.create_notification(recipient=self.alice, actor=self.bob, notification_type="post.commented",
                                               expires_at=timezone.now() - timedelta(days=1))
        old = services.create_notification(recipient=self.alice, actor=self.carol, notification_type="post.liked")
        Notification.objects.filter(pk=old.pk).update(is_read=True, read_at=timezone.now() - timedelta(days=200))
        call_command("cleanup_notifications", stdout=StringIO())
        self.assertEqual(list(Notification.objects.values_list("pk", flat=True)), [keep.pk])
        self.assertIsNotNone(expired)


ORIGIN = b"http://localhost:5173"


def _application():
    from config.asgi import application

    return application


@override_settings(**TEST_SETTINGS)
class WebSocketTests(DEASHelpers, TransactionTestCase):
    def setUp(self):
        super().setUp()
        from channels.layers import channel_layers

        channel_layers.backends.clear()
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")

    async def connect(self, user=None, token=None):
        if user is not None:
            token = str(AccessToken.for_user(user))
        communicator = WebsocketCommunicator(
            _application(), "/ws/notifications/", headers=[(b"origin", ORIGIN)],
            subprotocols=["deas.jwt", token] if token else [],
        )
        connected, detail = await communicator.connect(timeout=3)
        return communicator, connected, detail

    def test_unauthenticated_rejected(self):
        async def run():
            communicator, connected, code = await self.connect(token=None)
            self.assertFalse(connected)
            self.assertEqual(code, 4401)
            communicator, connected, code = await self.connect(token="not-a-jwt")
            self.assertFalse(connected)

        asyncio.run(run())

    def test_receives_only_own_notifications_in_real_time(self):
        from channels.db import database_sync_to_async

        async def run():
            alice_socket, connected, protocol = await self.connect(self.alice)
            self.assertTrue(connected)
            self.assertEqual(protocol, "deas.jwt")
            ready = await alice_socket.receive_json_from(timeout=3)
            self.assertEqual((ready["type"], ready["data"]["unread_count"]), ("connection.ready", 0))
            bob_socket, _c, _p = await self.connect(self.bob)
            await bob_socket.receive_json_from(timeout=3)

            note = await database_sync_to_async(services.create_notification)(
                recipient=self.alice, actor=self.bob, notification_type="post.liked"
            )
            event = await alice_socket.receive_json_from(timeout=3)
            self.assertEqual(event["type"], "notification.new")
            self.assertEqual(event["data"]["notification"]["id"], str(note.pk))
            self.assertEqual(event["data"]["unread_count"], 1)
            self.assertTrue(await bob_socket.receive_nothing(timeout=0.3))

            await database_sync_to_async(services.mark_read)(self.alice, note.pk)
            event = await alice_socket.receive_json_from(timeout=3)
            self.assertEqual((event["type"], event["data"]["unread_count"]), ("notification.read", 0))

            await alice_socket.send_json_to({"type": "ping"})
            self.assertEqual((await alice_socket.receive_json_from(timeout=3))["type"], "pong")
            await alice_socket.send_json_to({"type": "subscribe", "user_id": str(self.bob.pk)})
            self.assertEqual((await alice_socket.receive_json_from(timeout=3))["code"], "unsupported_event")
            await alice_socket.disconnect()
            await bob_socket.disconnect()

        asyncio.run(run())

    def test_realtime_preference_off_means_no_push(self):
        from channels.db import database_sync_to_async

        NotificationPreference.objects.create(user=self.alice, realtime_notifications=False)

        async def run():
            socket, connected, _p = await self.connect(self.alice)
            await socket.receive_json_from(timeout=3)
            await database_sync_to_async(services.create_notification)(recipient=self.alice, actor=self.bob, notification_type="post.liked")
            self.assertTrue(await socket.receive_nothing(timeout=0.3))
            await socket.disconnect()

        asyncio.run(run())

    def test_expired_token_closes_socket(self):
        async def run():
            token = AccessToken.for_user(self.alice)
            token.set_exp(lifetime=timedelta(seconds=1))
            socket, connected, _p = await self.connect(token=str(token))
            self.assertTrue(connected)
            await socket.receive_json_from(timeout=3)
            await asyncio.sleep(1.2)
            await socket.send_json_to({"type": "ping"})
            self.assertEqual((await socket.receive_json_from(timeout=3))["type"], "auth.expired")
            self.assertEqual((await socket.receive_output(timeout=3))["type"], "websocket.close")

        asyncio.run(run())
