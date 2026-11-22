import uuid

from django.test import override_settings

from friends.models import FriendRequest, Friendship, UserBlock

from .base import RELAXED_RATES, FriendsTestCase


class SendFriendRequestTests(FriendsTestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        self.login(self.alice)

    def send(self, receiver_id):
        return self.post("request-send", {"receiver_id": str(receiver_id)})

    def test_send_valid_request(self):
        response = self.send(self.bob.pk)
        self.assertEqual(response.status_code, 201, response.content)
        data = self.data(response)
        self.assertEqual(data["request"]["status"], "pending")
        self.assertEqual(data["request"]["sender_id"], str(self.alice.pk))
        self.assertEqual(data["request"]["receiver_id"], str(self.bob.pk))
        self.assertIsNotNone(data["request"]["created_at"])
        self.assertFalse(data["auto_accepted"])
        stored = FriendRequest.objects.get(pk=data["request"]["id"])
        self.assertEqual((stored.sender, stored.receiver), (self.alice, self.bob))
        self.assertIsNone(stored.responded_at)

    def test_cannot_send_to_self(self):
        self.assertError(self.send(self.alice.pk), 400, "cannot_target_self")
        self.assertEqual(FriendRequest.objects.count(), 0)

    def test_duplicate_pending_request_rejected(self):
        self.assertEqual(self.send(self.bob.pk).status_code, 201)
        self.assertError(self.send(self.bob.pk), 409, "request_already_sent")
        self.assertEqual(FriendRequest.objects.count(), 1)

    def test_reverse_pending_request_is_auto_accepted(self):
        existing = self.make_request(self.bob, self.alice)
        response = self.send(self.bob.pk)
        self.assertEqual(response.status_code, 200, response.content)
        data = self.data(response)
        self.assertTrue(data["auto_accepted"])
        self.assertIsNotNone(data["friendship"])
        existing.refresh_from_db()
        self.assertEqual(existing.status, "accepted")
        self.assertEqual(FriendRequest.objects.count(), 1)  # no second request row
        self.assertEqual(Friendship.objects.count(), 1)

    def test_cannot_request_an_existing_friend(self):
        self.befriend(self.alice, self.bob)
        self.assertError(self.send(self.bob.pk), 409, "already_friends")

    def test_blocked_in_either_direction_prevents_request_with_same_error(self):
        self.block(self.alice, self.bob)  # I blocked them
        first = self.assertError(self.send(self.bob.pk), 403, "request_not_allowed")
        UserBlock.objects.all().delete()
        self.block(self.bob, self.alice)  # they blocked me
        second = self.assertError(self.send(self.bob.pk), 403, "request_not_allowed")
        self.assertEqual(first["message"], second["message"])  # nothing reveals who blocked whom
        self.assertEqual(FriendRequest.objects.count(), 0)

    def test_unavailable_or_unknown_receivers_are_not_found(self):
        inactive = self.make_user("inactive", is_active=False)
        unverified = self.make_user("unverified", is_email_verified=False)
        for receiver_id in (inactive.pk, unverified.pk, uuid.uuid4()):
            self.assertError(self.send(receiver_id), 404, "user_not_found")
        self.assertEqual(FriendRequest.objects.count(), 0)

    def test_input_is_validated(self):
        self.assertError(self.post("request-send", {}), 400, "validation_error")
        self.assertError(self.post("request-send", {"receiver_id": "not-a-uuid"}), 400, "validation_error")

    def test_ownership_fields_cannot_be_supplied(self):
        carol = self.make_user("carol")
        body = {"receiver_id": str(self.bob.pk), "sender_id": str(carol.pk), "status": "accepted"}
        response = self.post("request-send", body)
        self.assertError(response, 400, "validation_error")
        self.assertEqual(FriendRequest.objects.count(), 0)

    def test_resend_after_cancel_keeps_history(self):
        first = self.data(self.send(self.bob.pk))["request"]["id"]
        self.assertEqual(self.post("request-cancel", request_id=first).status_code, 200)
        self.assertEqual(self.send(self.bob.pk).status_code, 201)
        self.assertEqual(FriendRequest.objects.count(), 2)
        self.assertEqual(FriendRequest.objects.filter(status="pending").count(), 1)

    def test_cooldown_after_rejection(self):
        rejected = self.make_request(self.alice, self.bob, status="rejected")
        body = self.assertError(self.send(self.bob.pk), 429, "request_cooldown")
        self.assertGreater(body["retry_after"], 0)
        FriendRequest.objects.filter(pk=rejected.pk).update(responded_at=self.hours_ago(25))
        self.assertEqual(self.send(self.bob.pk).status_code, 201)

    @override_settings(FRIENDS_REJECTION_COOLDOWN_HOURS=0)
    def test_cooldown_can_be_disabled(self):
        self.make_request(self.alice, self.bob, status="rejected")
        self.assertEqual(self.send(self.bob.pk).status_code, 201)

    @override_settings(FRIENDS_THROTTLE_RATES={**RELAXED_RATES, "friends_request": "2/hour"})
    def test_sending_is_rate_limited(self):
        for name in ("u1", "u2"):
            self.assertEqual(self.send(self.make_user(name).pk).status_code, 201)
        self.assertError(self.send(self.make_user("u3").pk), 429, "throttled")


class RespondToRequestTests(FriendsTestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.make_user("alice")  # sender
        self.bob = self.make_user("bob")  # receiver
        self.eve = self.make_user("eve")  # stranger
        self.fr = self.make_request(self.alice, self.bob)

    def test_receiver_accepts(self):
        self.login(self.bob)
        response = self.post("request-accept", request_id=self.fr.pk)
        self.assertEqual(response.status_code, 200, response.content)
        self.fr.refresh_from_db()
        self.assertEqual(self.fr.status, "accepted")
        self.assertIsNotNone(self.fr.responded_at)
        friendship = Friendship.objects.get()
        self.assertEqual({friendship.user1, friendship.user2}, {self.alice, self.bob})
        self.assertEqual(self.data(response)["friendship"]["id"], str(friendship.id))

    def test_receiver_rejects(self):
        self.login(self.bob)
        self.assertEqual(self.post("request-reject", request_id=self.fr.pk).status_code, 200)
        self.fr.refresh_from_db()
        self.assertEqual(self.fr.status, "rejected")
        self.assertIsNotNone(self.fr.responded_at)
        self.assertEqual(Friendship.objects.count(), 0)

    def test_sender_cancels(self):
        self.login(self.alice)
        self.assertEqual(self.post("request-cancel", request_id=self.fr.pk).status_code, 200)
        self.fr.refresh_from_db()
        self.assertEqual(self.fr.status, "cancelled")
        self.assertIsNotNone(self.fr.responded_at)
        self.assertEqual(Friendship.objects.count(), 0)

    def test_wrong_participant_gets_403_with_specific_code(self):
        self.login(self.alice)
        self.assertError(self.post("request-accept", request_id=self.fr.pk), 403, "not_request_receiver")
        self.assertError(self.post("request-reject", request_id=self.fr.pk), 403, "not_request_receiver")
        self.login(self.bob)
        self.assertError(self.post("request-cancel", request_id=self.fr.pk), 403, "not_request_sender")
        self.fr.refresh_from_db()
        self.assertEqual(self.fr.status, "pending")

    def test_strangers_get_404_for_every_action(self):
        self.login(self.eve)
        for name in ("request-accept", "request-reject", "request-cancel"):
            self.assertError(self.post(name, request_id=self.fr.pk), 404, "request_not_found")
        self.assertError(self.post("request-accept", request_id=uuid.uuid4()), 404, "request_not_found")
        self.fr.refresh_from_db()
        self.assertEqual(self.fr.status, "pending")

    def test_actions_on_non_pending_requests_conflict(self):
        self.login(self.bob)
        self.assertEqual(self.post("request-accept", request_id=self.fr.pk).status_code, 200)
        body = self.assertError(self.post("request-accept", request_id=self.fr.pk), 409, "request_not_pending")
        self.assertEqual(body["current_status"], "accepted")
        self.assertError(self.post("request-reject", request_id=self.fr.pk), 409, "request_not_pending")
        self.login(self.alice)
        self.assertError(self.post("request-cancel", request_id=self.fr.pk), 409, "request_not_pending")
        self.assertEqual(Friendship.objects.count(), 1)  # repeated accept did not duplicate it

    def test_cancelled_request_cannot_be_accepted(self):
        self.login(self.alice)
        self.post("request-cancel", request_id=self.fr.pk)
        self.login(self.bob)
        self.assertError(self.post("request-accept", request_id=self.fr.pk), 409, "request_not_pending")
        self.assertEqual(Friendship.objects.count(), 0)

    def test_accept_fails_if_sender_account_was_deactivated(self):
        self.alice.is_active = False
        self.alice.save()
        self.login(self.bob)
        self.assertError(self.post("request-accept", request_id=self.fr.pk), 404, "user_not_found")
        self.assertEqual(Friendship.objects.count(), 0)

    def test_request_status_cannot_be_changed_with_generic_methods(self):
        self.login(self.bob)
        url = self.url("request-accept", request_id=self.fr.pk)
        for method in (self.client.put, self.client.patch, self.client.delete):
            self.assertEqual(method(url).status_code, 405)


class RequestListTests(FriendsTestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.make_user("alice", full_name="Alice Adams")
        self.bob = self.make_user("bob")
        self.carol = self.make_user("carol")
        self.dave = self.make_user("dave")

    def test_received_lists_only_my_pending_requests_with_sender_card(self):
        mine = self.make_request(self.bob, self.alice)
        self.make_request(self.carol, self.alice, status="rejected")  # not pending
        self.make_request(self.bob, self.dave)  # someone else's
        self.login(self.alice)
        results = self.data(self.get("requests-received"))["results"]
        self.assertEqual([r["id"] for r in results], [str(mine.pk)])
        entry = results[0]
        self.assertEqual(entry["status"], "pending")
        self.assertEqual(entry["sender"]["user_id"], str(self.bob.pk))
        self.assertEqual(entry["sender"]["username"], "bob")
        self.assertEqual(entry["sender"]["full_name"], self.bob.full_name)
        self.assertIn("profile_picture", entry["sender"])
        self.assertIn("headline", entry["sender"])
        self.assertIn("created_at", entry)
        self.assertNotIn("email", entry["sender"])

    def test_sent_lists_only_my_pending_requests_with_receiver_card(self):
        mine = self.make_request(self.alice, self.bob)
        self.make_request(self.alice, self.carol, status="cancelled")
        self.make_request(self.dave, self.bob)
        self.login(self.alice)
        results = self.data(self.get("requests-sent"))["results"]
        self.assertEqual([r["id"] for r in results], [str(mine.pk)])
        self.assertEqual(results[0]["receiver"]["username"], "bob")

    def test_private_profile_content_is_not_exposed_on_cards(self):
        from profiles.models import Profile

        Profile.objects.filter(user=self.bob).update(
            profile_visibility="private", headline="Secret headline"
        )
        self.make_request(self.bob, self.alice)
        self.login(self.alice)
        sender = self.data(self.get("requests-received"))["results"][0]["sender"]
        self.assertEqual(sender["username"], "bob")
        self.assertIsNone(sender["headline"])
        self.assertIsNone(sender["profile_picture"])

    def test_public_headline_is_shown(self):
        from profiles.models import Profile

        Profile.objects.filter(user=self.bob).update(headline="Robotics club lead")
        self.make_request(self.bob, self.alice)
        self.login(self.alice)
        sender = self.data(self.get("requests-received"))["results"][0]["sender"]
        self.assertEqual(sender["headline"], "Robotics club lead")

    def test_requests_from_unavailable_senders_are_hidden(self):
        ghost = self.make_user("ghost", is_active=False)
        self.make_request(ghost, self.alice)
        self.login(self.alice)
        self.assertEqual(self.data(self.get("requests-received"))["results"], [])

    def test_pagination(self):
        for i in range(3):
            self.make_request(self.make_user(f"sender{i}"), self.alice)
        self.login(self.alice)
        data = self.data(self.get("requests-received", "?page_size=2"))
        self.assertEqual(len(data["results"]), 2)
        self.assertEqual(data["pagination"]["count"], 3)
        self.assertEqual(data["pagination"]["total_pages"], 2)
        page2 = self.data(self.get("requests-received", "?page_size=2&page=2"))
        self.assertEqual(len(page2["results"]), 1)
