from messaging.models import MessageReceipt

from .base import MessagingTestCase


class ReceiptTests(MessagingTestCase):
    def setUp(self):
        super().setUp()
        self.befriend(self.alice, self.bob)
        self.cid = self.start(self.alice, self.bob)

    def unread(self, user):
        response = self.client_for(user).get(self.url("conversation-unread", conversation_id=self.cid))
        return self.data(response)["unread_count"]

    def test_new_message_is_sent_not_read(self):
        message = self.send_ok(self.alice, self.cid)
        self.assertEqual(message["status"], "sent")
        receipt = MessageReceipt.objects.get(message_id=message["id"])
        self.assertEqual(receipt.user, self.bob)  # only the recipient has a receipt
        self.assertIsNone(receipt.delivered_at)
        self.assertIsNone(receipt.read_at)

    def test_loading_history_marks_delivered_not_read(self):
        message = self.send_ok(self.alice, self.cid)
        self.messages(self.bob, self.cid)
        [mine] = self.messages(self.alice, self.cid)
        self.assertEqual(mine["status"], "delivered")
        self.assertIsNone(mine["read_at"])
        self.assertEqual(self.unread(self.bob), 1)
        self.assertEqual(MessageReceipt.objects.get(message_id=message["id"]).read_at, None)

    def test_sender_loading_history_does_not_mark_delivered(self):
        self.send_ok(self.alice, self.cid)
        [mine] = self.messages(self.alice, self.cid)
        self.assertEqual(mine["status"], "sent")

    def test_mark_read_and_unread_counts(self):
        for _ in range(3):
            self.send_ok(self.alice, self.cid)
        self.assertEqual(self.unread(self.bob), 3)
        self.assertEqual(self.unread(self.alice), 0)
        response = self.client_for(self.bob).post(self.url("conversation-read", conversation_id=self.cid), {}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.data(response)["marked_read"], 3)
        self.assertEqual(self.unread(self.bob), 0)
        statuses = {m["status"] for m in self.messages(self.alice, self.cid)}
        self.assertEqual(statuses, {"read"})

    def test_mark_read_up_to_message(self):
        first = self.send_ok(self.alice, self.cid, "1")
        self.send_ok(self.alice, self.cid, "2")
        self.client_for(self.bob).post(
            self.url("conversation-read", conversation_id=self.cid), {"up_to_message_id": first["id"]}, format="json"
        )
        self.assertEqual(self.unread(self.bob), 1)

    def test_sender_cannot_mark_recipient_messages_read(self):
        self.send_ok(self.alice, self.cid)
        response = self.client_for(self.alice).post(self.url("conversation-read", conversation_id=self.cid), {}, format="json")
        self.assertEqual(self.data(response)["marked_read"], 0)
        self.assertEqual(self.unread(self.bob), 1)
        [mine] = self.messages(self.alice, self.cid)
        self.assertEqual(mine["status"], "sent")

    def test_sender_cannot_mark_delivered_on_behalf(self):
        message = self.send_ok(self.alice, self.cid)
        response = self.client_for(self.alice).post(
            self.url("conversation-delivered", conversation_id=self.cid), {"message_ids": [message["id"]]}, format="json"
        )
        self.assertEqual(self.data(response)["message_ids"], [])
        self.assertIsNone(MessageReceipt.objects.get(message_id=message["id"]).delivered_at)

    def test_non_participant_cannot_mark_read(self):
        self.send_ok(self.alice, self.cid)
        response = self.client_for(self.carol).post(self.url("conversation-read", conversation_id=self.cid), {}, format="json")
        self.assertError(response, 404, "conversation_not_found")
        self.assertEqual(self.unread(self.bob), 1)

    def test_hidden_and_deleted_messages_leave_unread_count(self):
        a = self.send_ok(self.alice, self.cid)
        b = self.send_ok(self.alice, self.cid)
        self.client_for(self.bob).post(self.url("message-delete-for-me", message_id=a["id"]))
        self.client_for(self.alice).post(self.url("message-delete-for-everyone", message_id=b["id"]))
        self.assertEqual(self.unread(self.bob), 0)

    def test_conversation_list_and_total_unread(self):
        self.send_ok(self.alice, self.cid)
        self.send_ok(self.alice, self.cid)
        [conv] = self.data(self.client_for(self.bob).get(self.url("conversations")))["results"]
        self.assertEqual(conv["unread_count"], 2)
        total = self.data(self.client_for(self.bob).get(self.url("unread-total")))
        self.assertEqual(total["unread_count"], 2)
        self.client_for(self.bob).patch(self.url("conversation-mute", conversation_id=self.cid), {"is_muted": True}, format="json")
        total = self.data(self.client_for(self.bob).get(self.url("unread-total")))
        self.assertEqual(total["unread_count"], 0)  # muted excluded from the badge
