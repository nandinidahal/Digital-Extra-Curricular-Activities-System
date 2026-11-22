from django.db import connection
from django.test.utils import CaptureQueriesContext

from messaging.models import Conversation, ConversationParticipant

from .base import MessagingTestCase


class StartConversationTests(MessagingTestCase):
    def test_start_direct_conversation(self):
        self.login(self.alice)
        response = self.client.post(self.url("conversations"), {"user_id": str(self.bob.pk)}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        data = self.data(response)
        self.assertEqual(data["conversation_type"], "direct")
        self.assertEqual(data["participant"]["id"], str(self.bob.pk))
        self.assertEqual(data["participant"]["username"], "bob")
        self.assertEqual(data["unread_count"], 0)
        self.assertEqual(data["messaging"]["messages_allowed"], 4)
        self.assertEqual(data["messaging"]["messages_used"], 0)
        self.assertTrue(data["messaging"]["can_message"])
        conversation = Conversation.objects.get(pk=data["id"])
        self.assertEqual(conversation.participants.count(), 2)

    def test_existing_conversation_is_returned(self):
        first = self.start(self.alice, self.bob)
        self.login(self.bob)  # also from the other side
        response = self.client.post(self.url("conversations"), {"user_id": str(self.alice.pk)}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.data(response)["id"], first)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_no_duplicate_direct_conversation_even_with_database_race(self):
        self.make_conversation(self.alice, self.bob)
        # a second row for the same pair is refused by the database itself
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_conversation(self.bob, self.alice)

    def test_cannot_start_with_self(self):
        self.login(self.alice)
        response = self.client.post(self.url("conversations"), {"user_id": str(self.alice.pk)}, format="json")
        self.assertError(response, 400, "cannot_message_self")

    def test_cannot_start_with_unknown_or_unverified_user(self):
        ghost = self.make_user("ghost", is_email_verified=False)
        self.login(self.alice)
        for user_id in (ghost.pk, "00000000-0000-0000-0000-000000000000"):
            response = self.client.post(self.url("conversations"), {"user_id": str(user_id)}, format="json")
            self.assertError(response, 404, "user_not_found")

    def test_cannot_start_with_blocked_user_either_direction(self):
        self.block(self.bob, self.alice)
        self.login(self.alice)
        response = self.client.post(self.url("conversations"), {"user_id": str(self.bob.pk)}, format="json")
        self.assertError(response, 403, "messaging_not_allowed")
        self.login(self.bob)
        response = self.client.post(self.url("conversations"), {"user_id": str(self.alice.pk)}, format="json")
        self.assertError(response, 403, "messaging_not_allowed")
        self.assertEqual(Conversation.objects.count(), 0)

    def test_requires_authentication(self):
        response = self.client.post(self.url("conversations"), {"user_id": str(self.bob.pk)}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_unverified_actor_cannot_use_messaging(self):
        unverified = self.make_user("newbie", is_email_verified=False)
        self.login(unverified)
        response = self.client.get(self.url("conversations"))
        self.assertError(response, 403, "account_unavailable")

    def test_unknown_fields_are_rejected(self):
        self.login(self.alice)
        response = self.client.post(
            self.url("conversations"), {"user_id": str(self.bob.pk), "created_by": str(self.bob.pk)}, format="json"
        )
        self.assertError(response, 400, "validation_error")


class ConversationAccessTests(MessagingTestCase):
    def setUp(self):
        super().setUp()
        self.conversation_id = self.start(self.alice, self.bob)

    def test_both_participants_can_retrieve(self):
        for user in (self.alice, self.bob):
            response = self.client_for(user).get(self.url("conversation-detail", conversation_id=self.conversation_id))
            self.assertEqual(response.status_code, 200)

    def test_non_participant_gets_404_everywhere(self):
        self.login(self.carol)
        cid = self.conversation_id
        for method, name, body in [
            ("get", "conversation-detail", None),
            ("get", "conversation-messages", None),
            ("post", "conversation-messages", {"content": "hi"}),
            ("patch", "conversation-mute", {"is_muted": True}),
            ("patch", "conversation-archive", {"is_archived": True}),
            ("post", "conversation-read", {}),
            ("get", "conversation-unread", None),
            ("get", "conversation-search", None),
        ]:
            response = getattr(self.client, method)(self.url(name, conversation_id=cid), body, format="json")
            self.assertError(response, 404, "conversation_not_found")

    def test_list_shows_only_own_conversations(self):
        self.start(self.carol, self.bob)
        self.send_ok(self.alice, self.conversation_id, "hi bob")
        self.login(self.alice)
        results = self.data(self.client.get(self.url("conversations")))["results"]
        self.assertEqual([r["id"] for r in results], [self.conversation_id])
        self.assertEqual(results[0]["last_message"]["content"], "hi bob")

    def test_empty_conversation_listed_only_for_its_creator(self):
        self.login(self.bob)
        self.assertEqual(self.data(self.client.get(self.url("conversations")))["results"], [])
        self.login(self.alice)
        self.assertEqual(len(self.data(self.client.get(self.url("conversations")))["results"]), 1)

    def test_list_ordered_by_last_activity_and_query_count_is_constant(self):
        other = self.start(self.alice, self.carol)
        self.send_ok(self.alice, self.conversation_id, "older")
        self.send_ok(self.alice, other, "newer")
        self.login(self.alice)
        results = self.data(self.client.get(self.url("conversations")))["results"]
        self.assertEqual([r["id"] for r in results], [other, self.conversation_id])

        with CaptureQueriesContext(connection) as small:
            self.client.get(self.url("conversations"))
        for i in range(6):
            extra = self.make_user(f"extra{i}")
            cid = self.start(self.alice, extra)
            self.send_ok(extra, cid, "yo")
        with CaptureQueriesContext(connection) as large:
            self.client.get(self.url("conversations"))
        self.assertEqual(len(small), len(large))


class MuteArchiveTests(MessagingTestCase):
    def setUp(self):
        super().setUp()
        self.cid = self.start(self.alice, self.bob)
        self.send_ok(self.bob, self.cid, "hello")

    def participant(self, user):
        return ConversationParticipant.objects.get(conversation_id=self.cid, user=user)

    def test_mute_and_unmute_affect_only_me(self):
        self.login(self.alice)
        response = self.client.patch(self.url("conversation-mute", conversation_id=self.cid), {"is_muted": True}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.data(response)["is_muted"])
        self.assertTrue(self.participant(self.alice).is_muted)
        self.assertFalse(self.participant(self.bob).is_muted)
        self.client.patch(self.url("conversation-mute", conversation_id=self.cid), {"is_muted": False}, format="json")
        self.assertFalse(self.participant(self.alice).is_muted)

    def test_archive_hides_from_inbox_without_deleting_and_only_for_me(self):
        self.login(self.alice)
        self.client.patch(self.url("conversation-archive", conversation_id=self.cid), {"is_archived": True}, format="json")
        inbox = self.data(self.client.get(self.url("conversations")))["results"]
        archive = self.data(self.client.get(self.url("conversations") + "?archived=true"))["results"]
        self.assertEqual(inbox, [])
        self.assertEqual([c["id"] for c in archive], [self.cid])
        self.assertEqual(len(self.messages(self.alice, self.cid)), 1)  # nothing deleted
        bob_inbox = self.data(self.client_for(self.bob).get(self.url("conversations")))["results"]
        self.assertEqual([c["id"] for c in bob_inbox], [self.cid])

    def test_new_message_unarchives_conversation(self):
        self.client_for(self.alice).patch(
            self.url("conversation-archive", conversation_id=self.cid), {"is_archived": True}, format="json"
        )
        self.send_ok(self.bob, self.cid, "are you there?")
        self.assertFalse(self.participant(self.alice).is_archived)

    def test_invalid_payload(self):
        self.login(self.alice)
        response = self.client.patch(self.url("conversation-mute", conversation_id=self.cid), {"is_muted": "maybe"}, format="json")
        self.assertError(response, 400, "validation_error")
