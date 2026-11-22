import uuid

from django.db import IntegrityError, transaction

from friends.models import FriendRequest, Friendship

from .base import FriendsTestCase


class FriendshipModelTests(FriendsTestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")

    def test_pair_is_stored_in_canonical_order_whatever_the_input_order(self):
        low, high = sorted([self.alice, self.bob], key=lambda u: u.pk.int)
        friendship = Friendship.objects.create(user1=high, user2=low)  # reversed on purpose
        friendship.refresh_from_db()
        self.assertEqual((friendship.user1, friendship.user2), (low, high))

    def test_same_friendship_cannot_be_stored_twice_in_either_order(self):
        self.befriend(self.alice, self.bob)
        for first, second in ((self.alice, self.bob), (self.bob, self.alice)):
            with self.assertRaises(IntegrityError), transaction.atomic():
                Friendship.objects.create(user1=first, user2=second)
        self.assertEqual(Friendship.objects.count(), 1)

    def test_self_friendship_is_rejected_by_the_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Friendship.objects.create(user1=self.alice, user2=self.alice)

    def test_unordered_row_is_rejected_by_the_database(self):
        low, high = sorted([self.alice, self.bob], key=lambda u: u.pk.int)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Friendship.objects.bulk_create([Friendship(user1=high, user2=low)])  # bypasses save()

    def test_request_constraints(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            FriendRequest.objects.create(sender=self.alice, receiver=self.alice)
        FriendRequest.objects.create(sender=self.alice, receiver=self.bob)
        with self.assertRaises(IntegrityError), transaction.atomic():  # same direction
            FriendRequest.objects.create(sender=self.alice, receiver=self.bob)
        with self.assertRaises(IntegrityError), transaction.atomic():  # reverse direction
            FriendRequest.objects.create(sender=self.bob, receiver=self.alice)

    def test_request_history_rows_do_not_block_new_pending_requests(self):
        self.make_request(self.alice, self.bob, status="rejected")
        self.make_request(self.alice, self.bob, status="cancelled")
        FriendRequest.objects.create(sender=self.alice, receiver=self.bob)
        self.assertEqual(FriendRequest.objects.count(), 3)

    def test_responded_at_must_match_status(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            FriendRequest.objects.create(sender=self.alice, receiver=self.bob, status="accepted")


class FriendshipApiTests(FriendsTestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        self.carol = self.make_user("carol")

    def test_friendship_is_visible_to_both_users(self):
        fr = self.make_request(self.alice, self.bob)
        self.login(self.bob)
        self.post("request-accept", request_id=fr.pk)
        for me, other in ((self.alice, self.bob), (self.bob, self.alice)):
            self.login(me)
            results = self.data(self.get("list"))["results"]
            self.assertEqual([r["user_id"] for r in results], [str(other.pk)])

    def test_either_user_can_remove_the_friendship(self):
        for remover, other in ((self.alice, self.bob), (self.bob, self.alice)):
            Friendship.objects.all().delete()
            self.befriend(self.alice, self.bob)
            self.login(remover)
            response = self.delete("remove", user_id=other.pk)
            self.assertEqual(response.status_code, 200, response.content)
            self.assertEqual(Friendship.objects.count(), 0)
            self.login(other)  # the other side sees it immediately
            self.assertEqual(self.data(self.get("list"))["results"], [])
            self.assertEqual(self.data(self.get("status", user_id=remover.pk))["friendship_status"], "not_friends")

    def test_removing_a_non_friend_is_404(self):
        self.login(self.alice)
        self.assertError(self.delete("remove", user_id=self.bob.pk), 404, "not_friends")
        self.assertError(self.delete("remove", user_id=uuid.uuid4()), 404, "not_friends")

    def test_cannot_remove_someone_elses_friendship(self):
        self.befriend(self.alice, self.bob)
        self.login(self.carol)
        self.assertError(self.delete("remove", user_id=self.alice.pk), 404, "not_friends")
        self.assertError(self.delete("remove", user_id=self.bob.pk), 404, "not_friends")
        self.assertEqual(Friendship.objects.count(), 1)

    def test_cannot_remove_self(self):
        self.login(self.alice)
        self.assertError(self.delete("remove", user_id=self.alice.pk), 400, "cannot_target_self")

    def test_new_request_possible_after_removal(self):
        self.befriend(self.alice, self.bob)
        self.login(self.alice)
        self.delete("remove", user_id=self.bob.pk)
        self.assertEqual(self.post("request-send", {"receiver_id": str(self.bob.pk)}).status_code, 201)

    def test_friendship_does_not_depend_on_who_sent_the_request(self):
        fr = self.make_request(self.bob, self.alice)
        self.login(self.alice)
        self.post("request-accept", request_id=fr.pk)
        friendship = Friendship.objects.get()
        self.assertEqual({friendship.user1_id, friendship.user2_id}, {self.alice.pk, self.bob.pk})
        self.assertLess(friendship.user1_id.int, friendship.user2_id.int)
