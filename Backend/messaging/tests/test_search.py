from .base import MessagingTestCase


class SearchTests(MessagingTestCase):
    def setUp(self):
        super().setUp()
        self.befriend(self.alice, self.bob)
        self.befriend(self.alice, self.carol)
        self.cid = self.start(self.alice, self.bob)
        self.other = self.start(self.alice, self.carol)
        self.send_ok(self.alice, self.cid, "Robotics club meets Friday")
        self.send_ok(self.bob, self.cid, "I love robotics!")
        self.send_ok(self.alice, self.cid, "Chess is fun")
        self.send_ok(self.carol, self.other, "robotics secret in another chat")

    def search(self, user, q, cid=None):
        return self.client_for(user).get(self.url("conversation-search", conversation_id=cid or self.cid) + f"?q={q}")

    def test_case_insensitive_search_in_own_conversation(self):
        results = self.data(self.search(self.alice, "ROBOTICS"))["results"]
        self.assertEqual({r["content"] for r in results}, {"Robotics club meets Friday", "I love robotics!"})

    def test_never_returns_other_conversations(self):
        results = self.data(self.search(self.bob, "secret"))["results"]
        self.assertEqual(results, [])

    def test_outsider_cannot_search(self):
        self.assertError(self.search(self.carol, "robotics"), 404, "conversation_not_found")

    def test_respects_deletions(self):
        target = self.data(self.search(self.alice, "chess"))["results"][0]
        self.client_for(self.bob).post(self.url("message-delete-for-me", message_id=target["id"]))
        self.assertEqual(self.data(self.search(self.bob, "chess"))["results"], [])
        self.assertEqual(len(self.data(self.search(self.alice, "chess"))["results"]), 1)
        self.client_for(self.alice).post(self.url("message-delete-for-everyone", message_id=target["id"]))
        self.assertEqual(self.data(self.search(self.alice, "chess"))["results"], [])

    def test_query_validation_and_pagination(self):
        self.assertError(self.search(self.alice, "a"), 400, "validation_error")
        self.assertError(self.search(self.alice, "x" * 101), 400, "validation_error")
        body = self.data(self.search(self.alice, "o"[0] * 2 if False else "ro"))
        self.assertIn("pagination", body)
