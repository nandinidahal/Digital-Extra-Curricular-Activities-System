from messaging.models import Message

from .base import MessagingTestCase


class PermissionTests(MessagingTestCase):
    def setUp(self):
        super().setUp()
        self.cid = self.start(self.alice, self.bob)
        self.message = self.send_ok(self.alice, self.cid, "private")

    def test_conversation_uuid_alone_grants_nothing(self):
        client = self.client_for(self.carol)
        self.assertEqual(client.get(self.url("conversation-messages", conversation_id=self.cid)).status_code, 404)
        self.assertEqual(client.post(self.url("message-reactions", message_id=self.message["id"]),
                                     {"reaction_type": "like"}, format="json").status_code, 404)
        self.assertEqual(client.post(self.url("message-delete-for-me", message_id=self.message["id"])).status_code, 404)

    def test_anonymous_is_rejected(self):
        self.logout()
        for response in (
            self.client.get(self.url("conversations")),
            self.client.get(self.url("conversation-messages", conversation_id=self.cid)),
            self.client.post(self.url("conversation-messages", conversation_id=self.cid), {"content": "x"}, format="json"),
        ):
            self.assertEqual(response.status_code, 401)

    def test_invalid_token_is_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-token")
        self.assertEqual(self.client.get(self.url("conversations")).status_code, 401)

    def test_client_cannot_set_server_fields(self):
        for field, value in [("status", "read"), ("is_edited", True), ("counts_toward_limit", False),
                             ("conversation_id", self.cid), ("message_type", "system")]:
            response = self.client_for(self.alice).post(
                self.url("conversation-messages", conversation_id=self.cid),
                {"content": "x", field: value}, format="json",
            )
            self.assertError(response, 400, "validation_error")
        self.assertEqual(Message.objects.count(), 1)

    def test_deactivated_recipient_cannot_be_messaged(self):
        self.bob.is_active = False
        self.bob.save()
        self.assertError(self.send(self.alice, self.cid), 403, "messaging_not_allowed")

    def test_throttling(self):
        from django.test import override_settings
        with override_settings(MESSAGING_THROTTLE_RATES={"messaging_send": "2/min"}):
            self.befriend(self.alice, self.bob)
            self.send(self.alice, self.cid)
            self.send(self.alice, self.cid)
            self.assertError(self.send(self.alice, self.cid), 429, "throttled")
