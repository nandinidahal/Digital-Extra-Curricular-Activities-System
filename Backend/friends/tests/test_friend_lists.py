from datetime import timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from friends.models import Friendship
from profiles.models import Profile

from .base import FriendsTestCase


class FriendListTests(FriendsTestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        self.carol = self.make_user("carol")
        self.login(self.alice)

    def test_entry_shape_and_contents(self):
        Profile.objects.filter(user=self.bob).update(headline="Chess club")
        self.befriend(self.alice, self.bob)
        entry = self.data(self.get("list"))["results"][0]
        self.assertEqual(entry["user_id"], str(self.bob.pk))
        self.assertEqual(entry["username"], "bob")
        self.assertEqual(entry["full_name"], self.bob.full_name)
        self.assertEqual(entry["headline"], "Chess club")
        self.assertIn("profile_picture", entry)
        self.assertEqual(entry["friendship_status"], "friends")
        self.assertIsNotNone(entry["friendship_created_at"])
        self.assertNotIn("email", entry)
        self.assertNotIn("date_of_birth", entry)

    def test_only_my_friendships_are_returned(self):
        self.befriend(self.alice, self.bob)
        self.befriend(self.bob, self.carol)  # not mine
        results = self.data(self.get("list"))["results"]
        self.assertEqual([r["user_id"] for r in results], [str(self.bob.pk)])

    def test_newest_friendship_first(self):
        old = self.befriend(self.alice, self.bob)
        new = self.befriend(self.alice, self.carol)
        Friendship.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=5))
        Friendship.objects.filter(pk=new.pk).update(created_at=timezone.now())
        results = self.data(self.get("list"))["results"]
        self.assertEqual([r["username"] for r in results], ["carol", "bob"])

    def test_pagination(self):
        for i in range(5):
            self.befriend(self.alice, self.make_user(f"friend{i}"))
        data = self.data(self.get("list", "?page_size=2"))
        self.assertEqual(len(data["results"]), 2)
        self.assertEqual(data["pagination"]["count"], 5)
        self.assertEqual(data["pagination"]["total_pages"], 3)
        self.assertIsNotNone(data["pagination"]["next"])
        self.assertIsNone(data["pagination"]["previous"])
        last = self.data(self.get("list", "?page_size=2&page=3"))
        self.assertEqual(len(last["results"]), 1)

    def test_page_size_is_capped(self):
        self.assertEqual(self.data(self.get("list", "?page_size=100000"))["pagination"]["page_size"], 100)

    def test_unavailable_friends_are_hidden_and_not_counted(self):
        ghost = self.make_user("ghost")
        self.befriend(self.alice, ghost)
        self.befriend(self.alice, self.bob)
        ghost.is_active = False
        ghost.save()
        self.assertEqual([r["username"] for r in self.data(self.get("list"))["results"]], ["bob"])
        self.assertEqual(self.data(self.get("count"))["friend_count"], 1)

    def test_private_profile_hides_picture_and_headline_but_keeps_identity(self):
        Profile.objects.filter(user=self.bob).update(profile_visibility="private", headline="Hidden")
        self.befriend(self.alice, self.bob)
        entry = self.data(self.get("list"))["results"][0]
        self.assertEqual(entry["username"], "bob")
        self.assertIsNone(entry["headline"])
        self.assertIsNone(entry["profile_picture"])

    def test_friend_count(self):
        self.assertEqual(self.data(self.get("count"))["friend_count"], 0)
        self.befriend(self.alice, self.bob)
        self.befriend(self.carol, self.alice)
        self.befriend(self.bob, self.carol)  # not mine
        self.assertEqual(self.data(self.get("count"))["friend_count"], 2)
        self.assertEqual(self.data(self.get("list"))["pagination"]["count"], 2)

    def test_query_count_does_not_grow_with_the_number_of_friends(self):
        for i in range(2):
            self.befriend(self.alice, self.make_user(f"early{i}"))
        with CaptureQueriesContext(connection) as small:
            self.get("list")
        for i in range(8):
            self.befriend(self.alice, self.make_user(f"late{i}"))
        with CaptureQueriesContext(connection) as large:
            self.get("list")
        self.assertEqual(len(small), len(large))
