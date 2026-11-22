from friends import services as friend_services
from messaging.models import Message

from .base import MessagingTestCase


class BlockingTests(MessagingTestCase):
    def setUp(self):
        super().setUp()
        self.befriend(self.alice, self.bob)
        self.cid = self.start(self.alice, self.bob)
        self.message = self.send_ok(self.alice, self.cid, "before block")

    def test_block_stops_messages_both_ways(self):
        friend_services.block_user(self.alice, self.bob.pk)
        self.assertError(self.send(self.alice, self.cid), 403, "messaging_not_allowed")
        self.assertError(self.send(self.bob, self.cid), 403, "messaging_not_allowed")

    def test_block_prevents_new_conversation(self):
        friend_services.block_user(self.carol, self.alice)
        response = self.client_for(self.alice).post(self.url("conversations"), {"user_id": str(self.carol.pk)}, format="json")
        self.assertError(response, 403, "messaging_not_allowed")

    def test_history_is_preserved(self):
        friend_services.block_user(self.bob, self.alice)
        self.assertEqual(len(self.messages(self.alice, self.cid)), 1)
        self.assertEqual(len(self.messages(self.bob, self.cid)), 1)
        self.assertEqual(Message.objects.count(), 1)

    def test_block_prevents_edit_but_allows_delete(self):
        friend_services.block_user(self.bob, self.alice)
        response = self.client_for(self.alice).patch(
            self.url("message-detail", message_id=self.message["id"]), {"content": "edited"}, format="json"
        )
        self.assertError(response, 403, "messaging_not_allowed")
        response = self.client_for(self.alice).post(self.url("message-delete-for-everyone", message_id=self.message["id"]))
        self.assertEqual(response.status_code, 200)

    def test_block_state_is_reported_without_revealing_who(self):
        friend_services.block_user(self.bob, self.alice)
        for user in (self.alice, self.bob):
            state = self.data(self.client_for(user).get(self.url("conversation-detail", conversation_id=self.cid)))["messaging"]
            self.assertFalse(state["can_message"])
            self.assertEqual(state["reason"], "blocked")

    def test_presence_hidden_from_blocked_user(self):
        from messaging import presence
        presence.connect(self.bob.pk)
        detail = self.data(self.client_for(self.alice).get(self.url("conversation-detail", conversation_id=self.cid)))
        self.assertTrue(detail["participant"]["is_online"])
        friend_services.block_user(self.bob, self.alice)
        detail = self.data(self.client_for(self.alice).get(self.url("conversation-detail", conversation_id=self.cid)))
        self.assertIsNone(detail["participant"]["is_online"])
        self.assertIsNone(detail["participant"]["last_seen_at"])

    def test_unblocking_restores_nothing_automatically(self):
        # blocking removed the friendship (Friends policy) -> after unblock the limit applies again
        friend_services.block_user(self.alice, self.bob.pk)
        friend_services.unblock_user(self.alice, self.bob.pk)
        self.assertEqual(Message.objects.count(), 1)  # nothing auto-sent
        state = self.data(self.client_for(self.alice).get(self.url("conversation-detail", conversation_id=self.cid)))["messaging"]
        self.assertFalse(state["is_friend"])
        self.assertTrue(state["can_message"])
        # the message sent while friends did not use allowance
        self.assertEqual(state["messages_used"], 0)
        for _ in range(4):
            self.send_ok(self.alice, self.cid)
        self.assertError(self.send(self.bob, self.cid), 403, "message_limit_reached")
