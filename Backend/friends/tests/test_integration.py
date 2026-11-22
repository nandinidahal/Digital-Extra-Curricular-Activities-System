import threading
import unittest
from unittest import mock

from django.db import connection
from django.test import TransactionTestCase, override_settings

from accounts.models import User
from friends import services, signals
from friends.models import FriendRequest, Friendship, UserBlock
from profiles.models import Profile

from .base import FriendsTestCase


class ServiceApiTests(FriendsTestCase):
    """The functions other modules (Social, Messaging, Search) are expected to import."""

    def setUp(self):
        super().setUp()
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        self.carol = self.make_user("carol")

    def test_are_friends_is_symmetric_and_false_for_self(self):
        self.befriend(self.alice, self.bob)
        self.assertTrue(services.are_friends(self.alice, self.bob))
        self.assertTrue(services.are_friends(self.bob.pk, self.alice.pk))
        self.assertFalse(services.are_friends(self.alice, self.carol))
        self.assertFalse(services.are_friends(self.alice, self.alice))

    def test_block_helpers(self):
        self.block(self.alice, self.bob)
        self.assertTrue(services.has_blocked(self.alice, self.bob))
        self.assertFalse(services.has_blocked(self.bob, self.alice))
        self.assertTrue(services.is_blocked_between(self.alice, self.bob))
        self.assertTrue(services.is_blocked_between(self.bob, self.alice))
        self.assertFalse(services.is_blocked_between(self.alice, self.carol))
        self.assertFalse(services.can_interact(self.alice, self.bob))
        self.assertTrue(services.can_interact(self.alice, self.carol))
        self.assertFalse(services.can_interact(self.alice, self.alice))

    def test_id_sets(self):
        self.befriend(self.alice, self.bob)
        self.block(self.alice, self.carol)
        self.block(self.make_user("dave"), self.alice)
        self.assertEqual(services.get_friend_ids(self.alice), {self.bob.pk})
        self.assertEqual(services.get_blocked_user_ids(self.alice), {self.carol.pk})
        self.assertEqual(len(services.get_blocked_by_user_ids(self.alice)), 1)
        self.assertEqual(len(services.get_hidden_user_ids(self.alice)), 2)

    def test_bulk_statuses_use_a_constant_number_of_queries(self):
        dave = self.make_user("dave")
        self.befriend(self.alice, self.bob)
        self.make_request(self.alice, self.carol)
        self.block(self.alice, dave)
        ids = [self.alice.pk, self.bob.pk, self.carol.pk, dave.pk, self.make_user("erin").pk]
        with self.assertNumQueries(3):
            statuses = services.get_relationship_statuses(self.alice, ids)
        self.assertEqual(
            statuses,
            {
                self.alice.pk: "self",
                self.bob.pk: "friends",
                self.carol.pk: "request_sent",
                dave.pk: "blocked_by_me",
                ids[4]: "not_friends",
            },
        )

    def test_discoverable_users_queryset(self):
        self.block(self.alice, self.bob)
        private = self.make_user("private")
        Profile.objects.filter(user=private).update(profile_visibility="private")
        self.make_user("inactive", is_active=False)
        self.make_user("unverified", is_email_verified=False)
        names = set(services.discoverable_users(self.alice).values_list("username", flat=True))
        self.assertEqual(names, {"carol"})


class DiscoveryEndpointTests(FriendsTestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        self.carol = self.make_user("carol")
        self.login(self.alice)

    def test_lists_people_with_friendship_status(self):
        self.befriend(self.alice, self.bob)
        data = self.data(self.get("discover"))
        by_name = {r["username"]: r for r in data["results"]}
        self.assertEqual(set(by_name), {"bob", "carol"})
        self.assertEqual(by_name["bob"]["friendship_status"], "friends")
        self.assertEqual(by_name["carol"]["friendship_status"], "not_friends")

    def test_hides_blocked_private_and_unavailable_people(self):
        self.block(self.bob, self.alice)
        Profile.objects.filter(user=self.carol).update(profile_visibility="private")
        self.assertEqual(self.data(self.get("discover"))["results"], [])

    def test_can_be_switched_off(self):
        with override_settings(FRIENDS_ENABLE_TEMP_DISCOVERY=False):
            self.assertEqual(self.get("discover").status_code, 404)


class EventTests(FriendsTestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        self.events = []

    def listen(self, signal, label):
        def receiver(sender, **kwargs):
            self.events.append((label, kwargs))

        signal.connect(receiver, weak=False)
        self.addCleanup(signal.disconnect, receiver)

    def test_events_are_sent_after_commit_with_useful_payloads(self):
        self.listen(signals.friend_request_sent, "sent")
        self.listen(signals.friend_request_accepted, "accepted")
        self.listen(signals.friend_request_rejected, "rejected")
        self.listen(signals.friend_removed, "removed")
        self.listen(signals.user_blocked, "blocked")
        self.listen(signals.user_unblocked, "unblocked")

        self.login(self.alice)
        with self.captureOnCommitCallbacks(execute=True):
            sent = self.post("request-send", {"receiver_id": str(self.bob.pk)})
        self.assertEqual([e[0] for e in self.events], ["sent"])
        self.assertEqual(str(self.events[0][1]["friend_request"].pk), self.data(sent)["request"]["id"])

        self.login(self.bob)
        request_id = self.data(sent)["request"]["id"]
        with self.captureOnCommitCallbacks(execute=True):
            self.post("request-accept", request_id=request_id)
        self.assertEqual(self.events[-1][0], "accepted")
        self.assertFalse(self.events[-1][1]["auto_accepted"])

        with self.captureOnCommitCallbacks(execute=True):
            self.delete("remove", user_id=self.alice.pk)
        self.assertEqual(self.events[-1][0], "removed")
        self.assertEqual(self.events[-1][1]["reason"], "removed")

        with self.captureOnCommitCallbacks(execute=True):
            self.post("blocked", {"user_id": str(self.alice.pk)})
        self.assertEqual(self.events[-1][0], "blocked")
        with self.captureOnCommitCallbacks(execute=True):
            self.delete("unblock", user_id=self.alice.pk)
        self.assertEqual(self.events[-1][0], "unblocked")

    def test_rejection_event(self):
        self.listen(signals.friend_request_rejected, "rejected")
        fr = self.make_request(self.alice, self.bob)
        self.login(self.bob)
        with self.captureOnCommitCallbacks(execute=True):
            self.post("request-reject", request_id=fr.pk)
        self.assertEqual([e[0] for e in self.events], ["rejected"])

    def test_failed_operations_send_no_events(self):
        self.listen(signals.friend_request_sent, "sent")
        self.login(self.alice)
        with self.captureOnCommitCallbacks(execute=True):
            self.post("request-send", {"receiver_id": str(self.alice.pk)})
        self.assertEqual(self.events, [])

    def test_a_broken_receiver_never_breaks_the_operation(self):
        def broken(sender, **kwargs):
            raise RuntimeError("notifications are down")

        signals.friend_request_sent.connect(broken, weak=False)
        self.addCleanup(signals.friend_request_sent.disconnect, broken)
        self.login(self.alice)
        with self.assertLogs("friends", level="ERROR"):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.post("request-send", {"receiver_id": str(self.bob.pk)})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(FriendRequest.objects.count(), 1)


class TransactionTests(FriendsTestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")

    def test_accept_is_all_or_nothing(self):
        fr = self.make_request(self.alice, self.bob)
        with mock.patch("friends.services._emit", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                services.accept_friend_request(self.bob, fr.pk)
        fr.refresh_from_db()
        self.assertEqual(fr.status, "pending")
        self.assertIsNone(fr.responded_at)
        self.assertEqual(Friendship.objects.count(), 0)

    def test_block_is_all_or_nothing(self):
        self.befriend(self.alice, self.bob)
        fr = self.make_request(self.bob, self.alice)
        with mock.patch("friends.services._emit", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                services.block_user(self.alice, self.bob.pk)
        self.assertEqual(UserBlock.objects.count(), 0)
        self.assertEqual(Friendship.objects.count(), 1)
        fr.refresh_from_db()
        self.assertEqual(fr.status, "pending")

    def test_repeated_identical_requests_leave_exactly_one_pending_request(self):
        self.login(self.alice)
        codes = [self.post("request-send", {"receiver_id": str(self.bob.pk)}).status_code for _ in range(4)]
        self.assertEqual(codes, [201, 409, 409, 409])
        self.assertEqual(FriendRequest.objects.count(), 1)


@unittest.skipUnless(connection.vendor == "postgresql", "row locking needs PostgreSQL")
class ConcurrencyTests(TransactionTestCase):
    """Real threads and real transactions, so it needs a database with row locks."""

    @staticmethod
    def _user(name):
        return User.objects.create_user(
            username=name, email=f"{name}@example.com", password="x", full_name=name, is_email_verified=True
        )

    def _race(self, jobs):
        results, barrier = [], threading.Barrier(len(jobs))

        def run(job):
            try:
                barrier.wait(timeout=10)
                job()
                results.append("ok")
            except Exception as exc:  # noqa: BLE001 - we want to see every outcome
                results.append(type(exc).__name__)
            finally:
                connection.close()

        threads = [threading.Thread(target=run, args=(job,)) for job in jobs]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        return results

    def test_simultaneous_accepts_create_one_friendship(self):
        alice, bob = self._user("alice"), self._user("bob")
        fr = FriendRequest.objects.create(sender=alice, receiver=bob)
        results = self._race([lambda: services.accept_friend_request(bob, fr.pk)] * 2)
        self.assertEqual(sorted(results), ["RequestNotPending", "ok"])
        self.assertEqual(Friendship.objects.count(), 1)

    def test_crossing_requests_end_in_exactly_one_friendship_and_no_pending_row(self):
        alice, bob = self._user("alice"), self._user("bob")
        self._race(
            [
                lambda: services.send_friend_request(alice, bob.pk),
                lambda: services.send_friend_request(bob, alice.pk),
            ]
        )
        self.assertEqual(Friendship.objects.count(), 1)
        self.assertEqual(FriendRequest.objects.filter(status="pending").count(), 0)

    def test_block_racing_with_accept_never_leaves_a_friendship_behind(self):
        alice, bob = self._user("alice"), self._user("bob")
        fr = FriendRequest.objects.create(sender=alice, receiver=bob)
        self._race(
            [
                lambda: services.accept_friend_request(bob, fr.pk),
                lambda: services.block_user(alice, bob.pk),
            ]
        )
        self.assertTrue(UserBlock.objects.filter(blocker=alice, blocked=bob).exists())
        self.assertEqual(Friendship.objects.count(), 0)
