from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from messaging.models import Message, MessageVisibility

from .base import MessagingTestCase


class SendMessageTests(MessagingTestCase):
    def setUp(self):
        super().setUp()
        self.befriend(self.alice, self.bob)
        self.cid = self.start(self.alice, self.bob)

    def test_send_text_message(self):
        response = self.send(self.alice, self.cid, "  Hello Bob!  ")
        self.assertEqual(response.status_code, 201, response.content)
        message = self.data(response)["message"]
        self.assertEqual(message["content"], "Hello Bob!")
        self.assertEqual(message["message_type"], "text")
        self.assertEqual(message["sender"]["id"], str(self.alice.pk))
        self.assertEqual(message["conversation_id"], self.cid)
        self.assertEqual(message["status"], "sent")
        self.assertTrue(message["is_own"])
        self.assertFalse(message["is_edited"])
        self.assertIsNotNone(message["created_at"])
        stored = Message.objects.get(pk=message["id"])
        self.assertEqual(stored.sender, self.alice)
        self.assertEqual(stored.conversation.last_message_at, stored.created_at)

    def test_reject_empty_and_whitespace(self):
        for content in ("", "    ", "\n\n"):
            self.assertError(self.send(self.alice, self.cid, content), 400, "validation_error")
        self.assertEqual(Message.objects.count(), 0)

    def test_reject_control_characters_and_too_long(self):
        self.assertError(self.send(self.alice, self.cid, "bad\x00byte"), 400, "validation_error")
        self.assertError(self.send(self.alice, self.cid, "x" * 5001), 400, "validation_error")

    def test_html_is_stored_as_plain_text(self):
        message = self.send_ok(self.alice, self.cid, "<b>hi</b> <3")
        self.assertEqual(message["content"], "<b>hi</b> <3")  # frontend renders as text

    def test_sender_cannot_be_impersonated(self):
        response = self.send(self.alice, self.cid, "hi", sender_id=str(self.bob.pk))
        self.assertError(response, 400, "validation_error")
        self.assertEqual(Message.objects.count(), 0)

    def test_history_is_paginated_newest_first(self):
        for i in range(5):
            self.send_ok(self.alice if i % 2 else self.bob, self.cid, f"m{i}")
        client = self.client_for(self.alice)
        url = self.url("conversation-messages", conversation_id=self.cid)
        first = self.data(client.get(url + "?page_size=2"))
        self.assertEqual([m["content"] for m in first["results"]], ["m4", "m3"])
        second = self.data(client.get(first["pagination"]["next"]))
        self.assertEqual([m["content"] for m in second["results"]], ["m2", "m1"])

    def test_history_query_count_is_constant(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self.send_ok(self.alice, self.cid, "one")
        client = self.client_for(self.bob)
        url = self.url("conversation-messages", conversation_id=self.cid)
        client.get(url)
        with CaptureQueriesContext(connection) as small:
            client.get(url)
        for i in range(15):
            m = self.send_ok(self.alice, self.cid, f"m{i}")
            self.client_for(self.bob).post(self.url("message-reactions", message_id=m["id"]), {"reaction_type": "like"}, format="json")
        client.get(url)  # marks delivered
        with CaptureQueriesContext(connection) as large:
            client.get(url)
        self.assertEqual(len(small), len(large))


class EditMessageTests(MessagingTestCase):
    def setUp(self):
        super().setUp()
        self.befriend(self.alice, self.bob)
        self.cid = self.start(self.alice, self.bob)
        self.message = self.send_ok(self.alice, self.cid, "original")

    def edit(self, user, content, message_id=None):
        return self.client_for(user).patch(
            self.url("message-detail", message_id=message_id or self.message["id"]), {"content": content}, format="json"
        )

    def test_edit_own_message(self):
        response = self.edit(self.alice, "changed")
        self.assertEqual(response.status_code, 200, response.content)
        data = self.data(response)
        self.assertEqual(data["content"], "changed")
        self.assertTrue(data["is_edited"])
        self.assertIsNotNone(data["edited_at"])

    def test_cannot_edit_someone_elses_message(self):
        self.assertError(self.edit(self.bob, "hacked"), 403, "not_message_owner")
        self.assertEqual(Message.objects.get(pk=self.message["id"]).content, "original")

    def test_non_participant_gets_404(self):
        self.assertError(self.edit(self.carol, "x"), 404, "message_not_found")

    def test_edit_validation(self):
        self.assertError(self.edit(self.alice, "   "), 400, "validation_error")

    def test_edit_window(self):
        Message.objects.filter(pk=self.message["id"]).update(created_at=timezone.now() - timedelta(minutes=16))
        self.assertError(self.edit(self.alice, "late"), 403, "edit_window_expired")
        with override_settings(MESSAGING_EDIT_WINDOW_MINUTES=0):
            self.assertEqual(self.edit(self.alice, "no limit").status_code, 200)

    def test_cannot_edit_deleted_message(self):
        self.client_for(self.alice).post(self.url("message-delete-for-everyone", message_id=self.message["id"]))
        self.assertError(self.edit(self.alice, "again"), 409, "message_deleted")


class DeleteMessageTests(MessagingTestCase):
    def setUp(self):
        super().setUp()
        self.befriend(self.alice, self.bob)
        self.cid = self.start(self.alice, self.bob)
        self.message = self.send_ok(self.alice, self.cid, "secret")

    def test_delete_for_me_hides_only_for_me(self):
        response = self.client_for(self.bob).post(self.url("message-delete-for-me", message_id=self.message["id"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.messages(self.bob, self.cid), [])
        self.assertEqual(len(self.messages(self.alice, self.cid)), 1)
        self.assertTrue(MessageVisibility.objects.filter(user=self.bob).exists())
        # idempotent / and now 404 for further actions by bob
        again = self.client_for(self.bob).post(self.url("message-delete-for-me", message_id=self.message["id"]))
        self.assertError(again, 404, "message_not_found")

    def test_delete_for_everyone_leaves_tombstone(self):
        response = self.client_for(self.alice).post(self.url("message-delete-for-everyone", message_id=self.message["id"]))
        self.assertEqual(response.status_code, 200, response.content)
        for user in (self.alice, self.bob):
            [m] = self.messages(user, self.cid)
            self.assertTrue(m["is_deleted"])
            self.assertIsNone(m["content"])
            self.assertEqual(m["attachments"], [])
        stored = Message.objects.get(pk=self.message["id"])
        self.assertEqual(stored.content, "")  # content really removed from the database

    def test_cannot_delete_others_message_for_everyone(self):
        response = self.client_for(self.bob).post(self.url("message-delete-for-everyone", message_id=self.message["id"]))
        self.assertError(response, 403, "not_message_owner")
        self.assertFalse(Message.objects.get(pk=self.message["id"]).is_deleted)

    def test_delete_for_everyone_window(self):
        Message.objects.filter(pk=self.message["id"]).update(created_at=timezone.now() - timedelta(hours=2))
        response = self.client_for(self.alice).post(self.url("message-delete-for-everyone", message_id=self.message["id"]))
        self.assertError(response, 403, "delete_window_expired")
        # delete-for-me is always possible
        response = self.client_for(self.alice).post(self.url("message-delete-for-me", message_id=self.message["id"]))
        self.assertEqual(response.status_code, 200)

    def test_http_delete_scopes(self):
        client = self.client_for(self.alice)
        url = self.url("message-detail", message_id=self.message["id"])
        self.assertError(client.delete(url + "?scope=bogus"), 400, "validation_error")
        self.assertEqual(client.delete(url + "?scope=everyone").status_code, 200)
        self.assertTrue(Message.objects.get(pk=self.message["id"]).is_deleted)
        other = self.send_ok(self.bob, self.cid, "x")
        self.assertEqual(client.delete(self.url("message-detail", message_id=other["id"])).status_code, 200)  # default me
        self.assertTrue(MessageVisibility.objects.filter(user=self.alice, message_id=other["id"]).exists())

    def test_non_participant_cannot_delete(self):
        response = self.client_for(self.carol).post(self.url("message-delete-for-everyone", message_id=self.message["id"]))
        self.assertError(response, 404, "message_not_found")


class ReplyAndForwardTests(MessagingTestCase):
    def setUp(self):
        super().setUp()
        self.befriend(self.alice, self.bob)
        self.befriend(self.alice, self.carol)
        self.cid = self.start(self.alice, self.bob)
        self.original = self.send_ok(self.bob, self.cid, "question?")

    def test_reply_endpoint(self):
        response = self.client_for(self.alice).post(
            self.url("message-reply", message_id=self.original["id"]), {"content": "answer"}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.content)
        reply = self.data(response)["message"]
        self.assertEqual(reply["reply_to"]["id"], self.original["id"])
        self.assertEqual(reply["reply_to"]["content_preview"], "question?")
        self.assertEqual(reply["reply_to"]["sender_username"], "bob")

    def test_reply_via_reply_to_id(self):
        reply = self.send_ok(self.alice, self.cid, "answer", reply_to_id=self.original["id"])
        self.assertEqual(reply["reply_to"]["id"], self.original["id"])

    def test_cannot_reply_across_conversations(self):
        other_cid = self.start(self.alice, self.carol)
        response = self.send(self.alice, other_cid, "sneaky", reply_to_id=self.original["id"])
        self.assertError(response, 400, "validation_error")

    def test_outsider_cannot_reply(self):
        response = self.client_for(self.carol).post(
            self.url("message-reply", message_id=self.original["id"]), {"content": "x"}, format="json"
        )
        self.assertError(response, 404, "message_not_found")

    def test_deleted_original_shows_safe_preview(self):
        reply = self.send_ok(self.alice, self.cid, "answer", reply_to_id=self.original["id"])
        self.client_for(self.bob).post(self.url("message-delete-for-everyone", message_id=self.original["id"]))
        [latest, _] = self.messages(self.alice, self.cid)
        self.assertEqual(latest["id"], reply["id"])
        self.assertTrue(latest["reply_to"]["is_deleted"])
        self.assertIsNone(latest["reply_to"]["content_preview"])
        response = self.send(self.alice, self.cid, "again", reply_to_id=self.original["id"])
        self.assertError(response, 400, "validation_error")

    def test_forward_to_other_conversation(self):
        response = self.client_for(self.alice).post(
            self.url("message-forward", message_id=self.original["id"]), {"user_id": str(self.carol.pk)}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.content)
        forwarded = self.data(response)["message"]
        self.assertTrue(forwarded["is_forwarded"])
        self.assertEqual(forwarded["content"], "question?")
        self.assertNotEqual(forwarded["conversation_id"], self.cid)
        self.assertIsNone(forwarded["reply_to"])

    def test_forward_respects_limit_and_membership(self):
        dave = self.make_user("dave")
        dcid = self.start(self.alice, dave)
        for _ in range(4):
            self.send_ok(self.alice, dcid)
        response = self.client_for(self.alice).post(
            self.url("message-forward", message_id=self.original["id"]), {"conversation_id": dcid}, format="json"
        )
        self.assertError(response, 403, "message_limit_reached")
        response = self.client_for(self.carol).post(
            self.url("message-forward", message_id=self.original["id"]), {"user_id": str(self.alice.pk)}, format="json"
        )
        self.assertError(response, 404, "message_not_found")
