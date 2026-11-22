from profiles.models import Profile

from .base import FriendsTestCase


class MutualFriendsTests(FriendsTestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        self.carol = self.make_user("carol")  # friend of both
        self.dave = self.make_user("dave")  # friend of both
        self.erin = self.make_user("erin")  # friend of alice only
        self.frank = self.make_user("frank")  # friend of bob only
        for friend in (self.carol, self.dave, self.erin):
            self.befriend(self.alice, friend)
        for friend in (self.carol, self.dave, self.frank):
            self.befriend(self.bob, friend)
        self.login(self.alice)

    def mutual(self, user, query=""):
        response = self.get("mutual", query, user_id=user.pk)
        self.assertEqual(response.status_code, 200, response.content)
        return self.data(response)

    def test_returns_only_shared_friends(self):
        data = self.mutual(self.bob)
        self.assertEqual([r["username"] for r in data["results"]], ["carol", "dave"])
        self.assertEqual(data["pagination"]["count"], 2)
        self.assertNotIn("email", data["results"][0])

    def test_is_symmetric(self):
        first = [r["user_id"] for r in self.mutual(self.bob)["results"]]
        self.login(self.bob)
        second = [r["user_id"] for r in self.mutual(self.alice)["results"]]
        self.assertEqual(first, second)

    def test_unavailable_mutual_friend_is_excluded(self):
        self.dave.is_active = False
        self.dave.save()
        self.assertEqual([r["username"] for r in self.mutual(self.bob)["results"]], ["carol"])

    def test_pagination(self):
        data = self.mutual(self.bob, "?page_size=1")
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["pagination"]["total_pages"], 2)

    def test_no_mutual_friends_is_an_empty_list(self):
        self.assertEqual(self.mutual(self.frank)["results"], [])

    def test_blocked_either_way_hides_the_user(self):
        self.block(self.alice, self.bob)
        self.assertError(self.get("mutual", user_id=self.bob.pk), 404, "user_not_found")
        self.login(self.bob)
        self.assertError(self.get("mutual", user_id=self.alice.pk), 404, "user_not_found")

    def test_private_profile_target_does_not_reveal_connections(self):
        Profile.objects.filter(user=self.bob).update(profile_visibility="private")
        self.assertError(self.get("mutual", user_id=self.bob.pk), 403, "profile_private")

    def test_members_only_profile_is_fine_for_members(self):
        Profile.objects.filter(user=self.bob).update(profile_visibility="members_only")
        self.assertEqual(self.get("mutual", user_id=self.bob.pk).status_code, 200)

    def test_with_myself_is_a_bad_request(self):
        self.assertError(self.get("mutual", user_id=self.alice.pk), 400, "cannot_target_self")

    def test_unknown_user(self):
        import uuid

        self.assertError(self.get("mutual", user_id=uuid.uuid4()), 404, "user_not_found")
