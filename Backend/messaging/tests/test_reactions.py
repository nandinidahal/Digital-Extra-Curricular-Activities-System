from messaging.models import MessageReaction

from .base import MessagingTestCase


class ReactionTests(MessagingTestCase):
    def setUp(self):
        super().setUp()
        self.cid = self.start(self.alice, self.bob)
        self.message = self.send_ok(self.alice, self.cid, "react to me")
        self.url_ = self.url("message-reactions", message_id=self.message["id"])

    def react(self, user, reaction):
        return self.client_for(user).post(self.url_, {"reaction_type": reaction}, format="json")

    def test_add_reaction(self):
        response = self.react(self.bob, "like")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.data(response)["reactions"], {"like": 1})
        self.assertEqual(self.data(response)["my_reaction"], "like")

    def test_change_reaction_keeps_one_row(self):
        self.react(self.bob, "like")
        data = self.data(self.react(self.bob, "laugh"))
        self.assertEqual(data["reactions"], {"laugh": 1})
        self.assertEqual(MessageReaction.objects.count(), 1)

    def test_no_duplicates_and_counts_per_user(self):
        self.react(self.bob, "love")
        self.react(self.bob, "love")
        data = self.data(self.react(self.alice, "love"))
        self.assertEqual(data["reactions"], {"love": 2})
        self.assertEqual(MessageReaction.objects.count(), 2)

    def test_remove_reaction_is_idempotent(self):
        self.react(self.bob, "sad")
        client = self.client_for(self.bob)
        data = self.data(client.delete(self.url_))
        self.assertEqual(data["reactions"], {})
        self.assertIsNone(data["my_reaction"])
        self.assertEqual(client.delete(self.url_).status_code, 200)

    def test_invalid_reaction(self):
        self.assertError(self.react(self.bob, "angry"), 400, "validation_error")

    def test_outsider_cannot_react(self):
        self.assertError(self.react(self.carol, "like"), 404, "message_not_found")

    def test_blocked_user_cannot_react(self):
        self.block(self.alice, self.bob)
        self.assertError(self.react(self.bob, "like"), 403, "messaging_not_allowed")

    def test_cannot_react_to_deleted_message(self):
        self.client_for(self.alice).post(self.url("message-delete-for-everyone", message_id=self.message["id"]))
        self.assertError(self.react(self.bob, "like"), 409, "message_deleted")

    def test_reactions_do_not_consume_message_allowance(self):
        for r in ("like", "love", "laugh", "sad", "surprised"):
            self.react(self.bob, r)
        for _ in range(3):
            self.send_ok(self.bob, self.cid)
