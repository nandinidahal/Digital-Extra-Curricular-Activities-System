import uuid

from friends.models import FriendRequest, Friendship, UserBlock

from .base import FriendsTestCase


class BlockingTests(FriendsTestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        self.login(self.alice)

    def block_via_api(self, user):
        return self.post("blocked", {"user_id": str(user.pk)})

    def test_block_a_user(self):
        response = self.block_via_api(self.bob)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(self.data(response)["user_id"], str(self.bob.pk))
        block = UserBlock.objects.get()
        self.assertEqual((block.blocker, block.blocked), (self.alice, self.bob))
        self.assertIsNotNone(block.created_at)

    def test_cannot_block_self(self):
        self.assertError(self.block_via_api(self.alice), 400, "cannot_target_self")
        self.assertEqual(UserBlock.objects.count(), 0)

    def test_duplicate_block_is_rejected(self):
        self.block_via_api(self.bob)
        self.assertError(self.block_via_api(self.bob), 409, "already_blocked")
        self.assertEqual(UserBlock.objects.count(), 1)

    def test_unknown_or_unavailable_user_cannot_be_blocked(self):
        ghost = self.make_user("ghost", is_active=False)
        for user_id in (uuid.uuid4(), ghost.pk):
            self.assertError(self.post("blocked", {"user_id": str(user_id)}), 404, "user_not_found")

    def test_blocker_field_cannot_be_supplied(self):
        carol = self.make_user("carol")
        body = {"user_id": str(self.bob.pk), "blocker_id": str(carol.pk)}
        self.assertError(self.post("blocked", body), 400, "validation_error")
        self.assertEqual(UserBlock.objects.count(), 0)

    def test_blocking_removes_the_friendship(self):
        self.befriend(self.alice, self.bob)
        self.block_via_api(self.bob)
        self.assertEqual(Friendship.objects.count(), 0)
        self.assertEqual(self.data(self.get("count"))["friend_count"], 0)

    def test_blocking_cancels_pending_requests_in_both_directions(self):
        outgoing = self.make_request(self.alice, self.bob)
        self.block_via_api(self.bob)
        outgoing.refresh_from_db()
        self.assertEqual(outgoing.status, "cancelled")
        self.assertIsNotNone(outgoing.responded_at)

        UserBlock.objects.all().delete()
        incoming = self.make_request(self.bob, self.alice)
        self.block_via_api(self.bob)
        incoming.refresh_from_db()
        self.assertEqual(incoming.status, "cancelled")
        self.assertEqual(FriendRequest.objects.filter(status="pending").count(), 0)

    def test_blocking_keeps_old_request_history_untouched(self):
        old = self.make_request(self.alice, self.bob, status="rejected")
        self.block_via_api(self.bob)
        old.refresh_from_db()
        self.assertEqual(old.status, "rejected")

    def test_blocked_user_cannot_send_requests_and_neither_can_the_blocker(self):
        self.block_via_api(self.bob)
        self.assertError(
            self.post("request-send", {"receiver_id": str(self.bob.pk)}), 403, "request_not_allowed"
        )
        self.login(self.bob)
        self.assertError(
            self.post("request-send", {"receiver_id": str(self.alice.pk)}), 403, "request_not_allowed"
        )
        self.assertEqual(FriendRequest.objects.count(), 0)

    def test_unblock(self):
        self.block(self.alice, self.bob)
        response = self.delete("unblock", user_id=self.bob.pk)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(UserBlock.objects.count(), 0)

    def test_unblock_does_not_restore_friendship_or_requests_and_sends_nothing(self):
        self.befriend(self.alice, self.bob)
        self.make_request(self.bob, self.alice)
        self.block_via_api(self.bob)
        self.delete("unblock", user_id=self.bob.pk)
        self.assertEqual(Friendship.objects.count(), 0)
        self.assertEqual(FriendRequest.objects.filter(status="pending").count(), 0)
        self.assertEqual(self.data(self.get("status", user_id=self.bob.pk))["friendship_status"], "not_friends")

    def test_new_request_allowed_after_unblocking(self):
        self.block_via_api(self.bob)
        self.delete("unblock", user_id=self.bob.pk)
        self.assertEqual(self.post("request-send", {"receiver_id": str(self.bob.pk)}).status_code, 201)

    def test_only_the_blocker_can_unblock(self):
        self.block(self.bob, self.alice)  # bob blocked alice
        self.assertError(self.delete("unblock", user_id=self.bob.pk), 404, "block_not_found")
        self.assertEqual(UserBlock.objects.count(), 1)
        self.login(self.make_user("carol"))
        self.assertError(self.delete("unblock", user_id=self.bob.pk), 404, "block_not_found")
        self.assertError(self.delete("unblock", user_id=self.alice.pk), 404, "block_not_found")
        self.assertEqual(UserBlock.objects.count(), 1)

    def test_block_list_shows_only_my_blocks(self):
        carol = self.make_user("carol")
        self.block(self.alice, self.bob)
        self.block(carol, self.alice)  # someone blocked me: must not appear
        self.block(carol, self.bob)  # someone else's block
        data = self.data(self.get("blocked"))
        self.assertEqual([r["username"] for r in data["results"]], ["bob"])
        self.assertIn("blocked_at", data["results"][0])
        self.assertNotIn("email", data["results"][0])

    def test_block_status_only_reports_my_own_block(self):
        self.assertFalse(self.data(self.get("block-status", user_id=self.bob.pk))["blocked_by_me"])
        self.block(self.bob, self.alice)  # they blocked me: still False for me
        self.assertFalse(self.data(self.get("block-status", user_id=self.bob.pk))["blocked_by_me"])
        self.block(self.alice, self.bob)
        self.assertTrue(self.data(self.get("block-status", user_id=self.bob.pk))["blocked_by_me"])

    def test_blocked_users_disappear_from_the_other_side_of_lists(self):
        self.make_request(self.bob, self.alice)
        self.block_via_api(self.bob)
        self.assertEqual(self.data(self.get("requests-received"))["results"], [])
        self.login(self.bob)
        self.assertEqual(self.data(self.get("requests-sent"))["results"], [])
