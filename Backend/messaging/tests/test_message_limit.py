import threading

from django.db import connection
from django.test import TransactionTestCase, override_settings

from messaging import services
from messaging.exceptions import MessageLimitReached
from messaging.models import Message

from .base import TEST_SETTINGS, MessagingHelpers, MessagingTestCase


class NonFriendLimitTests(MessagingTestCase):
    def setUp(self):
        super().setUp()
        self.cid = self.start(self.alice, self.bob)

    def test_four_messages_in_total_then_blocked(self):
        # A, B, A, B allowed - 5th blocked (both senders share ONE allowance)
        for i, sender in enumerate([self.alice, self.bob, self.alice, self.bob], start=1):
            message = self.send_ok(sender, self.cid, f"message {i}")
            self.assertEqual(message["content"], f"message {i}")
        body = self.assertError(self.send(self.alice, self.cid, "5th"), 403, "message_limit_reached")
        self.assertEqual(body["messages_used"], 4)
        self.assertEqual(body["messages_allowed"], 4)
        self.assertFalse(body["can_message"])
        self.assertIn("four", body["message"].lower().replace("4", "four"))
        # and the other side is blocked as well
        self.assertError(self.send(self.bob, self.cid, "5th"), 403, "message_limit_reached")
        self.assertEqual(Message.objects.count(), 4)

    def test_remaining_allowance_is_reported(self):
        response = self.send(self.alice, self.cid, "one")
        state = self.data(response)["messaging"]
        self.assertEqual(state["messages_used"], 1)
        self.assertEqual(state["messages_remaining"], 3)
        detail = self.data(self.client_for(self.bob).get(self.url("conversation-detail", conversation_id=self.cid)))
        self.assertEqual(detail["messaging"]["messages_used"], 1)

    def test_one_sender_can_use_whole_allowance(self):
        for _ in range(4):
            self.send_ok(self.alice, self.cid)
        self.assertError(self.send(self.bob, self.cid), 403, "message_limit_reached")

    def test_deleted_messages_still_count(self):
        ids = [self.send_ok(self.alice, self.cid, f"m{i}")["id"] for i in range(4)]
        client = self.client_for(self.alice)
        client.post(self.url("message-delete-for-everyone", message_id=ids[0]))
        client.post(self.url("message-delete-for-me", message_id=ids[1]))
        self.assertError(self.send(self.alice, self.cid), 403, "message_limit_reached")

    def test_failed_messages_do_not_consume_allowance(self):
        self.assertError(self.send(self.alice, self.cid, "   "), 400, "validation_error")
        self.assertError(self.send(self.alice, self.cid, "x" * 6000), 400, "validation_error")
        response = self.client_for(self.alice).post(
            self.url("conversation-messages", conversation_id=self.cid),
            {"content": "bad file", "attachments": [self.pdf_file(body=b"/JavaScript (alert)")]},
            format="multipart",
        )
        self.assertError(response, 400, "validation_error")
        for _ in range(4):
            self.send_ok(self.alice, self.cid)

    def test_becoming_friends_removes_limit(self):
        for _ in range(4):
            self.send_ok(self.alice, self.cid)
        self.assertError(self.send(self.alice, self.cid), 403, "message_limit_reached")
        self.befriend(self.alice, self.bob)
        for _ in range(10):
            self.send_ok(self.bob, self.cid)
        self.assertEqual(Message.objects.filter(counts_toward_limit=False).count(), 10)
        state = self.data(self.client_for(self.alice).get(self.url("conversation-detail", conversation_id=self.cid)))["messaging"]
        self.assertTrue(state["is_friend"])
        self.assertIsNone(state["messages_allowed"])

    def test_unfriending_reapplies_limit_with_previous_usage(self):
        # policy: allowance used BEFORE the friendship still counts; messages sent as friends do not
        self.send_ok(self.alice, self.cid)
        self.send_ok(self.bob, self.cid)
        self.befriend(self.alice, self.bob)
        for _ in range(5):
            self.send_ok(self.alice, self.cid)
        self.unfriend(self.alice, self.bob)
        self.send_ok(self.alice, self.cid)  # 3rd counted
        self.send_ok(self.bob, self.cid)  # 4th counted
        self.assertError(self.send(self.alice, self.cid), 403, "message_limit_reached")

    def test_unfriending_after_full_use_blocks_immediately(self):
        for _ in range(4):
            self.send_ok(self.alice, self.cid)
        self.befriend(self.alice, self.bob)
        self.send_ok(self.alice, self.cid)
        self.unfriend(self.alice, self.bob)
        self.assertError(self.send(self.alice, self.cid), 403, "message_limit_reached")

    def test_blocking_overrides_friendship(self):
        self.befriend(self.alice, self.bob)
        self.block(self.bob, self.alice)
        self.assertError(self.send(self.alice, self.cid), 403, "messaging_not_allowed")
        self.assertError(self.send(self.bob, self.cid), 403, "messaging_not_allowed")

    @override_settings(MESSAGING_NON_FRIEND_MESSAGE_LIMIT=2)
    def test_limit_is_configurable(self):
        self.send_ok(self.alice, self.cid)
        self.send_ok(self.bob, self.cid)
        body = self.assertError(self.send(self.alice, self.cid), 403, "message_limit_reached")
        self.assertEqual(body["messages_allowed"], 2)

    @override_settings(MESSAGING_NON_FRIEND_MESSAGE_LIMIT=0)
    def test_limit_zero_means_friends_only(self):
        self.assertError(self.send(self.alice, self.cid), 403, "message_limit_reached")

    def test_duplicate_client_id_does_not_consume_allowance(self):
        client_id = "6f1c2a7e-6a59-4c4d-9d2f-1f7c9a6c0001"
        first = self.send(self.alice, self.cid, "hi", client_id=client_id)
        again = self.send(self.alice, self.cid, "hi", client_id=client_id)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(again.status_code, 200)
        self.assertEqual(self.data(first)["message"]["id"], self.data(again)["message"]["id"])
        self.assertEqual(Message.objects.count(), 1)
        for _ in range(3):
            self.send_ok(self.alice, self.cid)


@override_settings(**TEST_SETTINGS)
class ConcurrentLimitTests(MessagingHelpers, TransactionTestCase):
    """Real PostgreSQL transactions in parallel threads: the row lock must serialise them."""

    def test_parallel_sends_cannot_exceed_limit(self):
        if connection.vendor != "postgresql":
            self.skipTest("needs PostgreSQL row locks")
        alice, bob = self.make_user("alice"), self.make_user("bob")
        conversation = self.make_conversation(alice, bob)
        services.send_message(alice, conversation.pk, content="first")  # 1 used
        attempts = 12
        barrier = threading.Barrier(attempts)
        outcomes = []
        lock = threading.Lock()

        def worker(i):
            from django.db import connection as thread_connection
            try:
                barrier.wait()
                sender = alice if i % 2 else bob
                services.send_message(sender, conversation.pk, content=f"race {i}")
                result = "ok"
            except MessageLimitReached:
                result = "limit"
            except Exception as exc:  # pragma: no cover - surfaced by the assertion below
                result = repr(exc)
            finally:
                thread_connection.close()
            with lock:
                outcomes.append(result)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(attempts)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(outcomes.count("ok"), 3, outcomes)
        self.assertEqual(outcomes.count("limit"), attempts - 3, outcomes)
        self.assertEqual(Message.objects.filter(conversation=conversation).count(), 4)
