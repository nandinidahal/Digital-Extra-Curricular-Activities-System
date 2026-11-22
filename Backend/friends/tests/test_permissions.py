import uuid

from friends.models import FriendRequest, Friendship, UserBlock

from .base import FriendsTestCase


class AuthenticationTests(FriendsTestCase):
    def test_every_endpoint_requires_authentication(self):
        some_id, some_user = uuid.uuid4(), uuid.uuid4()
        cases = [
            ("get", "list", {}),
            ("get", "count", {}),
            ("get", "discover", {}),
            ("post", "request-send", {}),
            ("get", "requests-received", {}),
            ("get", "requests-sent", {}),
            ("post", "request-accept", {"request_id": some_id}),
            ("post", "request-reject", {"request_id": some_id}),
            ("post", "request-cancel", {"request_id": some_id}),
            ("delete", "remove", {"user_id": some_user}),
            ("get", "status", {"user_id": some_user}),
            ("get", "mutual", {"user_id": some_user}),
            ("get", "blocked", {}),
            ("post", "blocked", {}),
            ("delete", "unblock", {"user_id": some_user}),
            ("get", "block-status", {"user_id": some_user}),
        ]
        for method, name, kwargs in cases:
            response = getattr(self.client, method)(self.url(name, **kwargs))
            self.assertEqual(response.status_code, 401, f"{method.upper()} {name}")

    def test_invalid_token_is_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        self.assertEqual(self.get("list").status_code, 401)

    def test_unverified_or_deactivated_accounts_cannot_use_friend_features(self):
        unverified = self.make_user("unverified", is_email_verified=False)
        self.login(unverified)
        self.assertError(self.get("list"), 403, "account_unavailable")
        self.assertError(self.post("request-send", {"receiver_id": str(uuid.uuid4())}), 403, "account_unavailable")


class RelationshipTamperingTests(FriendsTestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        self.eve = self.make_user("eve")

    def test_eve_cannot_touch_a_request_between_alice_and_bob(self):
        fr = self.make_request(self.alice, self.bob)
        self.login(self.eve)
        for name in ("request-accept", "request-reject", "request-cancel"):
            self.assertEqual(self.post(name, request_id=fr.pk).status_code, 404)
        fr.refresh_from_db()
        self.assertEqual(fr.status, "pending")
        self.assertEqual(Friendship.objects.count(), 0)

    def test_eve_cannot_remove_the_friendship_between_alice_and_bob(self):
        self.befriend(self.alice, self.bob)
        self.login(self.eve)
        self.assertEqual(self.delete("remove", user_id=self.alice.pk).status_code, 404)
        self.assertEqual(self.delete("remove", user_id=self.bob.pk).status_code, 404)
        self.assertEqual(Friendship.objects.count(), 1)

    def test_eve_cannot_lift_a_block_between_alice_and_bob(self):
        self.block(self.alice, self.bob)
        self.login(self.eve)
        self.assertEqual(self.delete("unblock", user_id=self.bob.pk).status_code, 404)
        self.assertEqual(self.delete("unblock", user_id=self.alice.pk).status_code, 404)
        self.login(self.bob)  # the blocked person can not lift it either
        self.assertEqual(self.delete("unblock", user_id=self.alice.pk).status_code, 404)
        self.assertEqual(UserBlock.objects.count(), 1)

    def test_ownership_is_taken_from_the_token_not_the_body(self):
        self.login(self.eve)
        response = self.post(
            "request-send", {"receiver_id": str(self.bob.pk), "sender_id": str(self.alice.pk)}
        )
        self.assertEqual(response.status_code, 400)
        response = self.post("request-send", {"receiver_id": str(self.bob.pk)})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(FriendRequest.objects.get().sender, self.eve)

    def test_no_endpoint_lists_another_users_blocks_friends_or_requests(self):
        self.block(self.bob, self.eve)
        self.befriend(self.bob, self.alice)
        self.make_request(self.alice, self.bob)
        self.login(self.eve)
        self.assertEqual(self.data(self.get("blocked"))["results"], [])
        self.assertEqual(self.data(self.get("list"))["results"], [])
        self.assertEqual(self.data(self.get("requests-received"))["results"], [])
        self.assertEqual(self.data(self.get("requests-sent"))["results"], [])
        # Query-string tricks do not change whose data is returned
        self.assertEqual(self.data(self.get("blocked", f"?blocker={self.bob.pk}"))["results"], [])
        self.assertEqual(self.data(self.get("list", f"?user={self.bob.pk}"))["results"], [])

    def test_responses_never_contain_private_account_data(self):
        self.befriend(self.alice, self.bob)
        self.make_request(self.eve, self.alice)
        self.login(self.alice)
        for response in (self.get("list"), self.get("requests-received"), self.get("discover")):
            body = response.content.decode()
            for secret in ("alice@example.com", "bob@example.com", "eve@example.com", "password", "phone_number"):
                self.assertNotIn(secret, body)
