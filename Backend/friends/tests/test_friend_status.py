import uuid

from django.test import override_settings

from .base import FriendsTestCase


class FriendStatusTests(FriendsTestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        self.login(self.alice)

    def status(self, user):
        response = self.get("status", user_id=user.pk)
        self.assertEqual(response.status_code, 200, response.content)
        return self.data(response)

    def test_self(self):
        self.assertEqual(self.status(self.alice)["friendship_status"], "self")

    def test_not_friends(self):
        data = self.status(self.bob)
        self.assertEqual(data["friendship_status"], "not_friends")
        self.assertEqual(data["user_id"], str(self.bob.pk))
        self.assertFalse(any([data["is_friend"], data["request_sent"], data["request_received"], data["blocked"]]))
        self.assertIsNone(data["request_id"])

    def test_friends(self):
        self.befriend(self.bob, self.alice)
        data = self.status(self.bob)
        self.assertEqual(data["friendship_status"], "friends")
        self.assertTrue(data["is_friend"])

    def test_request_sent_includes_request_id(self):
        fr = self.make_request(self.alice, self.bob)
        data = self.status(self.bob)
        self.assertEqual(data["friendship_status"], "request_sent")
        self.assertTrue(data["request_sent"])
        self.assertEqual(data["request_id"], str(fr.pk))

    def test_request_received_includes_request_id(self):
        fr = self.make_request(self.bob, self.alice)
        data = self.status(self.bob)
        self.assertEqual(data["friendship_status"], "request_received")
        self.assertTrue(data["request_received"])
        self.assertEqual(data["request_id"], str(fr.pk))

    def test_old_requests_do_not_count(self):
        self.make_request(self.alice, self.bob, status="rejected")
        self.assertEqual(self.status(self.bob)["friendship_status"], "not_friends")

    def test_blocked_by_me(self):
        self.block(self.alice, self.bob)
        data = self.status(self.bob)
        self.assertEqual(data["friendship_status"], "blocked_by_me")
        self.assertTrue(data["blocked"])

    def test_blocked_you(self):
        self.block(self.bob, self.alice)
        data = self.status(self.bob)
        self.assertEqual(data["friendship_status"], "blocked_you")
        self.assertTrue(data["blocked"])

    def test_my_block_wins_when_both_blocked(self):
        self.block(self.alice, self.bob)
        self.block(self.bob, self.alice)
        self.assertEqual(self.status(self.bob)["friendship_status"], "blocked_by_me")

    @override_settings(FRIENDS_REVEAL_BLOCKED_BY_OTHER=False)
    def test_blocker_can_be_hidden_by_setting(self):
        self.block(self.bob, self.alice)
        data = self.status(self.bob)
        self.assertEqual(data["friendship_status"], "not_friends")
        self.assertFalse(data["blocked"])

    def test_unknown_and_unavailable_users_are_404(self):
        ghost = self.make_user("ghost", is_active=False)
        self.assertError(self.get("status", user_id=ghost.pk), 404, "user_not_found")
        self.assertError(self.get("status", user_id=uuid.uuid4()), 404, "user_not_found")
