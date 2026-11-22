from django.test import override_settings

from messaging import presence
from messaging.models import UserPresence

from .base import MessagingTestCase


class PresenceTests(MessagingTestCase):
    def setUp(self):
        super().setUp()
        self.cid = self.start(self.alice, self.bob)

    def participant(self, viewer):
        return self.data(self.client_for(viewer).get(self.url("conversation-detail", conversation_id=self.cid)))["participant"]

    def test_multiple_sessions(self):
        self.assertTrue(presence.connect(self.bob.pk))  # came online
        self.assertFalse(presence.connect(self.bob.pk))  # second device
        self.assertFalse(presence.disconnect(self.bob.pk))  # still one device
        self.assertEqual(presence.online_user_ids([self.bob.pk]), {self.bob.pk})
        self.assertTrue(presence.disconnect(self.bob.pk))  # last one
        self.assertEqual(presence.online_user_ids([self.bob.pk]), set())
        self.assertIsNotNone(UserPresence.objects.get(user=self.bob).last_seen_at)

    def test_heartbeat_does_not_write_to_database(self):
        presence.connect(self.bob.pk)
        with self.assertNumQueries(0):
            for _ in range(10):
                presence.heartbeat(self.bob.pk)

    def test_expired_heartbeat_means_offline(self):
        from django.core.cache import cache
        presence.connect(self.bob.pk)
        cache.delete(f"messaging:online:{self.bob.pk}")  # simulate TTL expiry (idle tab)
        self.assertEqual(presence.online_user_ids([self.bob.pk]), set())
        self.assertTrue(presence.heartbeat(self.bob.pk))  # back online

    def test_default_policy_friends_only(self):
        presence.connect(self.bob.pk)
        self.assertIsNone(self.participant(self.alice)["is_online"])
        self.befriend(self.alice, self.bob)
        self.assertTrue(self.participant(self.alice)["is_online"])

    def test_last_seen_visible_to_friends(self):
        self.befriend(self.alice, self.bob)
        presence.connect(self.bob.pk)
        presence.disconnect(self.bob.pk)
        p = self.participant(self.alice)
        self.assertFalse(p["is_online"])
        self.assertIsNotNone(p["last_seen_at"])

    @override_settings(MESSAGING_PRESENCE_VISIBILITY="participants")
    def test_participants_policy(self):
        presence.connect(self.bob.pk)
        self.assertTrue(self.participant(self.alice)["is_online"])

    @override_settings(MESSAGING_PRESENCE_VISIBILITY="nobody")
    def test_nobody_policy(self):
        self.befriend(self.alice, self.bob)
        presence.connect(self.bob.pk)
        self.assertIsNone(self.participant(self.alice)["is_online"])
