from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import User
from friends.models import Block, FriendRequest, Friendship
from social.models import Notification
from social.tests.helpers import ApiTestCase, make_friends, make_user


class FriendRequestFlowTests(ApiTestCase):
    def send(self, client, to):
        return client.post("/api/friends/requests/", {"user_id": to.pk}, format="json")

    def test_send_creates_pending_request_and_notifies(self):
        r = self.send(self.a, self.bob)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["status"], "pending")
        self.assertEqual(self.a.get(f"/api/friends/status/{self.bob.pk}/").data["state"], "REQUEST_SENT")
        self.assertEqual(self.b.get(f"/api/friends/status/{self.alice.pk}/").data["state"], "REQUEST_RECEIVED")
        self.assertEqual(Notification.objects.filter(recipient=self.bob, type="friend_request").count(), 1)

    def test_cannot_friend_yourself(self):
        self.assertEqual(self.send(self.a, self.alice).status_code, 409)
        self.assertFalse(FriendRequest.objects.exists())

    def test_no_duplicate_pending_request(self):
        self.send(self.a, self.bob)
        self.assertEqual(self.send(self.a, self.bob).status_code, 409)
        self.assertEqual(FriendRequest.objects.count(), 1)

    def test_unknown_or_inactive_user(self):
        self.assertEqual(self.a.post("/api/friends/requests/", {"user_id": 99999}, format="json").status_code, 404)
        User.objects.filter(pk=self.bob.pk).update(is_active=False)
        self.assertEqual(self.send(self.a, self.bob).status_code, 404)

    def test_cancel(self):
        rid = self.send(self.a, self.bob).data["id"]
        self.assertEqual(self.b.post(f"/api/friends/requests/{rid}/cancel/").status_code, 403)  # receiver can't "cancel"
        self.assertEqual(self.a.post(f"/api/friends/requests/{rid}/cancel/").data["status"], "cancelled")
        self.assertEqual(Notification.objects.filter(recipient=self.bob, type="friend_request").count(), 0)
        self.assertEqual(self.a.get(f"/api/friends/status/{self.bob.pk}/").data["state"], "NOT_FRIENDS")
        self.assertEqual(self.send(self.a, self.bob).status_code, 201)  # can ask again straight away

    def test_accept_creates_one_friendship_and_notifies(self):
        rid = self.send(self.a, self.bob).data["id"]
        self.assertEqual(self.a.post(f"/api/friends/requests/{rid}/accept/").status_code, 403)  # sender can't accept
        self.assertEqual(self.c.post(f"/api/friends/requests/{rid}/accept/").status_code, 404)  # third party can't see it
        r = self.b.post(f"/api/friends/requests/{rid}/accept/")
        self.assertEqual(r.data["status"], "accepted")
        self.assertEqual(Friendship.objects.count(), 1)
        self.assertEqual(self.a.get("/api/friends/").data["friends_count"], 1)
        self.assertEqual(self.b.get("/api/friends/").data["friends_count"], 1)
        self.assertEqual([u["username"] for u in self.a.get("/api/friends/").data["results"]], ["bob"])
        self.assertEqual(Notification.objects.filter(recipient=self.alice, type="friend_accepted").count(), 1)
        self.assertEqual(self.b.post(f"/api/friends/requests/{rid}/accept/").status_code, 409)  # already handled

    def test_reject_then_cooldown(self):
        rid = self.send(self.a, self.bob).data["id"]
        self.assertEqual(self.b.post(f"/api/friends/requests/{rid}/reject/").data["status"], "rejected")
        self.assertFalse(Friendship.objects.exists())
        self.assertEqual(self.send(self.a, self.bob).status_code, 409)          # cooldown applies to the sender
        FriendRequest.objects.update(responded_at=timezone.now() - timedelta(days=8))
        self.assertEqual(self.send(self.a, self.bob).status_code, 201)
        self.assertEqual(FriendRequest.objects.count(), 2)                      # history is kept

    def test_ignore_hides_from_incoming_but_stays_pending_for_sender(self):
        rid = self.send(self.a, self.bob).data["id"]
        self.b.post(f"/api/friends/requests/{rid}/ignore/")
        self.assertEqual(self.b.get("/api/friends/requests/incoming/").data["results"], [])
        self.assertEqual(len(self.b.get("/api/friends/requests/incoming/?include_ignored=1").data["results"]), 1)
        self.assertEqual(len(self.a.get("/api/friends/requests/outgoing/").data["results"]), 1)
        self.assertEqual(self.send(self.a, self.bob).status_code, 409)           # still no duplicate
        self.assertEqual(self.b.post(f"/api/friends/requests/{rid}/accept/").status_code, 200)  # can still accept

    def test_crossed_requests_auto_accept(self):
        self.send(self.a, self.bob)
        r = self.send(self.b, self.alice)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["auto_accepted"])
        self.assertEqual(Friendship.objects.count(), 1)
        self.assertFalse(FriendRequest.objects.filter(status="pending").exists())

    def test_already_friends(self):
        make_friends(self.alice, self.bob)
        self.assertEqual(self.send(self.a, self.bob).status_code, 409)

    def test_lists(self):
        self.send(self.a, self.bob)
        self.send(self.c, self.alice)
        self.assertEqual([r["sender"]["username"] for r in self.a.get("/api/friends/requests/incoming/").data["results"]], ["carol"])
        self.assertEqual([r["receiver"]["username"] for r in self.a.get("/api/friends/requests/outgoing/").data["results"]], ["bob"])

    def test_remove_friend(self):
        make_friends(self.alice, self.bob)
        self.assertEqual(self.a.delete(f"/api/friends/{self.bob.pk}/").status_code, 204)
        self.assertFalse(Friendship.objects.exists())
        self.assertEqual(self.a.delete(f"/api/friends/{self.bob.pk}/").status_code, 404)
        self.assertEqual(self.a.get(f"/api/friends/status/{self.bob.pk}/").data["state"], "NOT_FRIENDS")

    def test_mutual_friends_endpoint(self):
        make_friends(self.alice, self.carol)
        make_friends(self.bob, self.carol)
        r = self.a.get("/api/friends/mutual/bob/")
        self.assertEqual([u["username"] for u in r.data["results"]], ["carol"])

    def test_search_friends(self):
        make_friends(self.alice, self.bob)
        make_friends(self.alice, self.carol)
        r = self.a.get("/api/friends/?search=car")
        self.assertEqual([u["username"] for u in r.data["results"]], ["carol"])


class BlockTests(ApiTestCase):
    def test_block_removes_friendship_and_cancels_requests(self):
        make_friends(self.alice, self.bob)
        r = self.a.post("/api/friends/blocks/", {"user_id": self.bob.pk}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertFalse(Friendship.objects.exists())
        self.assertEqual(self.a.get(f"/api/friends/status/{self.bob.pk}/").data["state"], "BLOCKED")
        self.assertEqual(self.b.get(f"/api/friends/status/{self.alice.pk}/").data["state"], "BLOCKED_BY")

    def test_blocked_cannot_send_request_either_direction(self):
        self.a.post("/api/friends/blocks/", {"user_id": self.bob.pk}, format="json")
        self.assertEqual(self.b.post("/api/friends/requests/", {"user_id": self.alice.pk}, format="json").status_code, 403)
        self.assertEqual(self.a.post("/api/friends/requests/", {"user_id": self.bob.pk}, format="json").status_code, 403)

    def test_block_cancels_pending_request(self):
        self.b.post("/api/friends/requests/", {"user_id": self.alice.pk}, format="json")
        self.a.post("/api/friends/blocks/", {"user_id": self.bob.pk}, format="json")
        self.assertFalse(FriendRequest.objects.filter(status="pending").exists())

    def test_unblock(self):
        self.a.post("/api/friends/blocks/", {"user_id": self.bob.pk}, format="json")
        self.assertEqual(len(self.a.get("/api/friends/blocks/").data["results"]), 1)
        self.assertEqual(self.a.delete(f"/api/friends/blocks/{self.bob.pk}/").status_code, 204)
        self.assertEqual(self.a.get(f"/api/friends/status/{self.bob.pk}/").data["state"], "NOT_FRIENDS")

    def test_cannot_block_self(self):
        self.assertEqual(self.a.post("/api/friends/blocks/", {"user_id": self.alice.pk}, format="json").status_code, 409)


class DatabaseConstraintTests(ApiTestCase):
    """The DB itself must refuse states the service layer is supposed to prevent."""

    def test_duplicate_or_reversed_friendship_rows_rejected(self):
        low, high = sorted((self.alice.pk, self.bob.pk))
        Friendship.objects.create(user_low_id=low, user_high_id=high)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Friendship.objects.create(user_low_id=low, user_high_id=high)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Friendship.objects.create(user_low_id=high, user_high_id=low)  # wrong order

    def test_two_pending_requests_for_one_pair_rejected(self):
        FriendRequest.objects.create(sender=self.alice, receiver=self.bob)
        with self.assertRaises(IntegrityError), transaction.atomic():
            FriendRequest.objects.create(sender=self.bob, receiver=self.alice)
        with self.assertRaises(IntegrityError), transaction.atomic():
            FriendRequest.objects.create(sender=self.alice, receiver=self.bob)

    def test_self_request_rejected(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            FriendRequest.objects.create(sender=self.alice, receiver=self.alice)


class SuggestionTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.dave = make_user("dave")
        self.erin = make_user("erin")
        self.frank = make_user("frank")

    def names(self, client=None):
        r = (client or self.a).get("/api/friends/suggestions/")
        self.assertEqual(r.status_code, 200)
        return [i["user"]["username"] for i in r.data], r.data

    def test_mutual_friends_rank_first(self):
        make_friends(self.alice, self.bob)
        make_friends(self.bob, self.dave)
        make_friends(self.bob, self.erin)
        make_friends(self.alice, self.carol)
        make_friends(self.carol, self.erin)
        names, data = self.names()
        self.assertEqual(names[0], "erin")                                   # 2 mutual friends
        self.assertEqual(data[0]["reasons"]["mutual_friends"], 2)
        self.assertEqual(names[1], "dave")                                   # 1 mutual friend
        self.assertNotIn("alice", names)
        self.assertNotIn("bob", names)                                       # already friends
        self.assertNotIn("carol", names)

    def test_institution_department_and_interests(self):
        self.a.patch("/api/social/profiles/me/", {"institution": "KU", "department": "CS", "interests": ["chess", "debate"]}, format="json")
        self.as_user(self.dave).patch("/api/social/profiles/me/", {"institution": "ku", "department": "cs", "interests": ["Chess"]}, format="json")
        self.as_user(self.erin).patch("/api/social/profiles/me/", {"institution": "KU"}, format="json")
        names, data = self.names()
        self.assertEqual(names[:2], ["dave", "erin"])
        self.assertEqual(data[0]["reasons"]["shared_interests"], ["chess"])
        self.assertTrue(data[0]["reasons"]["same_department"])

    def test_exclusions(self):
        FriendRequest.objects.create(sender=self.alice, receiver=self.bob)       # pending, outgoing
        FriendRequest.objects.create(sender=self.carol, receiver=self.alice)     # pending, incoming
        Block.objects.create(blocker=self.alice, blocked=self.dave)              # blocked by me
        Block.objects.create(blocker=self.erin, blocked=self.alice)              # blocked me
        User.objects.filter(pk=self.frank.pk).update(is_active=False)           # deactivated
        names, _ = self.names()
        self.assertEqual(names, [])

    def test_shared_event_participation(self):
        from announcements.models import Announcement, Category
        from datetime import date
        cat = Category.objects.create(name="Sports")
        ev = Announcement.objects.create(
            title="Cup", short_description="s", full_description="f", activity_name="Football", category=cat,
            activity_type="physical", country="Nepal", start_date=date.today(), end_date=date.today(),
            published_by=self.carol, status="published")
        self.new_post(self.a, "went", "public", announcement_id=ev.pk)
        self.new_post(self.dave, "went too", "public", announcement_id=ev.pk)
        names, data = self.names()
        self.assertEqual(names[0], "dave")
        self.assertTrue(data[0]["reasons"]["shared_activities"])

    def test_cold_start_returns_newest_members(self):
        names, _ = self.names()
        self.assertEqual(set(names), {"bob", "carol", "dave", "erin", "frank"})
