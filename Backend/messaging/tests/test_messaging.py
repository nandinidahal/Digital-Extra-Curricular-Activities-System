from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from accounts.models import User
from friends.models import Block, Friendship
from messaging.models import Conversation, Message
from social.models import Notification
from social.tests.helpers import ApiTestCase, make_friends, make_user


class MessagingBase(ApiTestCase):
    def open(self, client, other):
        r = client.post("/api/messaging/conversations/", {"recipient_id": other.pk}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        return r.data["id"]

    def send(self, client, cid, body="hi"):
        return client.post(f"/api/messaging/conversations/{cid}/messages/", {"body": body}, format="json")


class FourMessageLimitTests(MessagingBase):
    def test_non_friends_limited_to_four_messages_total_both_directions(self):
        cid = self.open(self.a, self.bob)
        self.assertEqual(self.send(self.a, cid, "1").status_code, 201)
        self.assertEqual(self.send(self.b, cid, "2").status_code, 201)
        self.assertEqual(self.send(self.a, cid, "3").status_code, 201)
        self.assertEqual(self.send(self.b, cid, "4").status_code, 201)
        for client in (self.a, self.b):
            r = self.send(client, cid, "5")
            self.assertEqual(r.status_code, 403)
            self.assertEqual(r.data["code"], "message_limit_reached")
            self.assertEqual(r.data["action"], "send_friend_request")
        self.assertEqual(Message.objects.count(), 4)

    def test_state_fields_drive_the_ui(self):
        cid = self.open(self.a, self.bob)
        r = self.a.get(f"/api/messaging/conversations/{cid}/")
        self.assertEqual((r.data["can_send"], r.data["messages_remaining"], r.data["limit"]), (True, 4, 4))
        for i in range(4):
            self.send(self.a, cid, str(i))
        r = self.a.get(f"/api/messaging/conversations/{cid}/")
        self.assertFalse(r.data["can_send"])
        self.assertEqual(r.data["reason"], "message_limit_reached")
        self.assertEqual(r.data["action"], "send_friend_request")
        self.assertIn("friends", r.data["notice"])

    def test_limit_state_reflects_pending_request(self):
        cid = self.open(self.a, self.bob)
        for i in range(4):
            self.send(self.a, cid, str(i))
        self.a.post("/api/friends/requests/", {"user_id": self.bob.pk}, format="json")
        self.assertEqual(self.a.get(f"/api/messaging/conversations/{cid}/").data["action"], "request_pending")
        self.assertEqual(self.b.get(f"/api/messaging/conversations/{cid}/").data["action"], "accept_friend_request")

    def test_accepting_friendship_unlocks_unlimited_messages(self):
        cid = self.open(self.a, self.bob)
        for i in range(4):
            self.send(self.a, cid, str(i))
        self.assertEqual(self.send(self.a, cid, "blocked").status_code, 403)
        rid = self.a.post("/api/friends/requests/", {"user_id": self.bob.pk}, format="json").data["id"]
        self.b.post(f"/api/friends/requests/{rid}/accept/")
        for i in range(10):
            self.assertEqual(self.send(self.b if i % 2 else self.a, cid, f"free {i}").status_code, 201)
        r = self.a.get(f"/api/messaging/conversations/{cid}/")
        self.assertTrue(r.data["can_send"])
        self.assertIsNone(r.data["messages_remaining"])

    def test_friends_are_never_limited_and_do_not_consume_the_allowance(self):
        make_friends(self.alice, self.bob)
        cid = self.open(self.a, self.bob)
        for i in range(8):
            self.assertEqual(self.send(self.a, cid, str(i)).status_code, 201)
        self.assertEqual(Conversation.objects.get(pk=cid).restricted_message_count, 0)

    def test_cannot_bypass_limit_with_second_conversation(self):
        cid = self.open(self.a, self.bob)
        self.assertEqual(self.open(self.a, self.bob), cid)       # same pair -> same conversation
        self.assertEqual(self.open(self.b, self.alice), cid)     # from the other side too
        self.assertEqual(Conversation.objects.count(), 1)

    def test_unfriending_reapplies_limit_and_keeps_history(self):
        make_friends(self.alice, self.bob)
        cid = self.open(self.a, self.bob)
        for i in range(6):
            self.send(self.a, cid, f"as friends {i}")
        self.a.delete(f"/api/friends/{self.bob.pk}/")
        self.assertEqual(Message.objects.filter(conversation_id=cid).count(), 6)            # history intact
        self.assertEqual(self.send(self.a, cid, "again").status_code, 201)                  # restriction is back...
        for i in range(3):
            self.send(self.b, cid, str(i))
        self.assertEqual(self.send(self.a, cid, "over").status_code, 403)                   # ...4 messages max
        self.assertEqual(Message.objects.filter(conversation_id=cid).count(), 6 + 4)
        self.assertEqual(len(self.a.get(f"/api/messaging/conversations/{cid}/messages/").data["results"]), 10)

    @override_settings(MESSAGING_RESET_LIMIT_ON_UNFRIEND=True)
    def test_optional_reset_on_unfriend(self):
        cid = self.open(self.a, self.bob)
        for i in range(4):
            self.send(self.a, cid, str(i))
        make_friends(self.alice, self.bob)
        self.a.delete(f"/api/friends/{self.bob.pk}/")
        self.assertEqual(Conversation.objects.get(pk=cid).restricted_message_count, 0)
        self.assertEqual(self.send(self.a, cid, "fresh").status_code, 201)

    def test_deleting_messages_does_not_refund_the_limit(self):
        cid = self.open(self.a, self.bob)
        ids = [self.send(self.a, cid, str(i)).data["id"] for i in range(4)]
        self.a.delete(f"/api/messaging/messages/{ids[0]}/")
        self.assertEqual(self.send(self.a, cid, "more").status_code, 403)

    def test_limit_is_a_setting(self):
        with override_settings(MESSAGING_PRE_FRIEND_LIMIT=2):
            cid = self.open(self.a, self.bob)
            self.send(self.a, cid)
            self.send(self.a, cid)
            self.assertEqual(self.send(self.a, cid).status_code, 403)

    def test_sequential_sends_never_exceed_limit(self):
        """Counter is incremented under SELECT ... FOR UPDATE; hammer it and check the invariant."""
        cid = self.open(self.a, self.bob)
        results = [self.send(self.a if i % 2 else self.b, cid, str(i)).status_code for i in range(12)]
        self.assertEqual(results.count(201), 4)
        self.assertEqual(Message.objects.count(), 4)


class AccessControlTests(MessagingBase):
    def test_third_party_cannot_access_conversation_by_id(self):
        cid = self.open(self.a, self.bob)
        mid = self.send(self.a, cid, "secret").data["id"]
        for url, method in ((f"/api/messaging/conversations/{cid}/", "get"),
                            (f"/api/messaging/conversations/{cid}/messages/", "get"),
                            (f"/api/messaging/conversations/{cid}/read/", "post")):
            self.assertEqual(getattr(self.c, method)(url).status_code, 404, url)
        self.assertEqual(self.send(self.c, cid, "intrude").status_code, 404)
        self.assertEqual(self.c.patch(f"/api/messaging/messages/{mid}/", {"body": "x"}, format="json").status_code, 404)
        self.assertEqual(self.c.delete(f"/api/messaging/messages/{mid}/").status_code, 404)
        self.assertEqual(self.c.get("/api/messaging/conversations/").data["results"], [])

    def test_cannot_edit_or_delete_someone_elses_message(self):
        cid = self.open(self.a, self.bob)
        mid = self.send(self.a, cid, "mine").data["id"]
        self.assertEqual(self.b.patch(f"/api/messaging/messages/{mid}/", {"body": "x"}, format="json").status_code, 404)
        self.assertEqual(self.b.delete(f"/api/messaging/messages/{mid}/").status_code, 404)

    def test_cannot_message_self_or_unknown_or_inactive(self):
        for uid in (self.alice.pk, 99999):
            self.assertIn(self.a.post("/api/messaging/conversations/", {"recipient_id": uid}, format="json").status_code, (400, 404))
        User.objects.filter(pk=self.bob.pk).update(is_active=False)
        self.assertEqual(self.a.post("/api/messaging/conversations/", {"recipient_id": self.bob.pk}, format="json").status_code, 404)

    def test_deactivated_recipient_cannot_receive_and_deactivated_sender_cannot_send(self):
        make_friends(self.alice, self.bob)
        cid = self.open(self.a, self.bob)
        User.objects.filter(pk=self.bob.pk).update(is_active=False)
        self.assertEqual(self.send(self.a, cid).status_code, 403)
        User.objects.filter(pk=self.bob.pk).update(is_active=True)
        self.assertEqual(self.send(self.a, cid).status_code, 201)
        User.objects.filter(pk=self.alice.pk).update(is_active=False)
        self.alice.refresh_from_db()
        self.assertEqual(self.as_user(self.alice).post(f"/api/messaging/conversations/{cid}/messages/", {"body": "x"}, format="json").status_code, 403)

    def test_blocking_prevents_messaging_both_ways_even_between_friends(self):
        make_friends(self.alice, self.bob)
        cid = self.open(self.a, self.bob)
        self.send(self.a, cid, "before")
        self.b.post("/api/friends/blocks/", {"user_id": self.alice.pk}, format="json")
        self.assertEqual(self.send(self.a, cid, "after").status_code, 403)
        self.assertEqual(self.send(self.b, cid, "after").status_code, 403)
        self.assertEqual(self.a.post("/api/messaging/conversations/", {"recipient_id": self.bob.pk}, format="json").status_code, 403)
        state = self.a.get(f"/api/messaging/conversations/{cid}/").data
        self.assertFalse(state["can_send"])
        self.assertEqual(state["reason"], "blocked")
        self.assertEqual(Message.objects.count(), 1)                       # history preserved

    def test_requires_authentication(self):
        from rest_framework.test import APIClient
        self.assertEqual(APIClient().get("/api/messaging/conversations/").status_code, 401)


class FeatureTests(MessagingBase):
    def test_conversation_list_preview_unread_and_order(self):
        make_friends(self.alice, self.bob)
        make_friends(self.alice, self.carol)
        c1 = self.open(self.b, self.alice)
        c2 = self.open(self.c, self.alice)
        self.send(self.b, c1, "from bob 1")
        self.send(self.b, c1, "from bob 2")
        self.send(self.c, c2, "x" * 200)
        r = self.a.get("/api/messaging/conversations/")
        self.assertEqual([c["id"] for c in r.data["results"]], [c2, c1])            # most recent first
        first, second = r.data["results"]
        self.assertEqual(first["other_user"]["username"], "carol")
        self.assertEqual(first["unread_count"], 1)
        self.assertEqual(len(first["last_message"]["preview"]), 81)                 # truncated with an ellipsis
        self.assertEqual(second["unread_count"], 2)
        self.assertEqual(second["last_message"]["preview"], "from bob 2")
        self.assertFalse(second["last_message"]["is_mine"])
        self.assertEqual(self.a.get("/api/messaging/unread-count/").data["unread"], 3)
        self.assertEqual(self.a.get("/api/social/home/").data["unread_messages"], 3)
        # sender's view: nothing unread
        self.assertEqual(self.b.get("/api/messaging/conversations/").data["results"][0]["unread_count"], 0)

    def test_mark_read_and_read_receipts(self):
        make_friends(self.alice, self.bob)
        cid = self.open(self.a, self.bob)
        mid = self.send(self.a, cid, "ping").data["id"]
        self.assertFalse(self.a.get(f"/api/messaging/conversations/{cid}/messages/").data["results"][0]["is_read"])
        self.assertEqual(self.b.post(f"/api/messaging/conversations/{cid}/read/").data["marked_read"], 1)
        self.assertTrue(self.a.get(f"/api/messaging/conversations/{cid}/messages/").data["results"][0]["is_read"])
        self.assertEqual(self.a.post(f"/api/messaging/conversations/{cid}/read/").data["marked_read"], 0)  # own msgs aren't "unread" for me
        self.assertEqual(self.b.get("/api/messaging/unread-count/").data["unread"], 0)

    def test_empty_conversation_state(self):
        cid = self.open(self.a, self.bob)
        r = self.a.get(f"/api/messaging/conversations/{cid}/messages/")
        self.assertEqual(r.data["results"], [])
        item = self.a.get("/api/messaging/conversations/").data["results"][0]
        self.assertIsNone(item["last_message"])
        self.assertEqual(item["unread_count"], 0)

    def test_message_pagination_newest_first(self):
        make_friends(self.alice, self.bob)
        cid = self.open(self.a, self.bob)
        for i in range(25):
            self.send(self.a, cid, f"m{i}")
        r = self.a.get(f"/api/messaging/conversations/{cid}/messages/?page_size=10")
        self.assertEqual([m["body"] for m in r.data["results"]][:2], ["m24", "m23"])
        seen = [m["id"] for m in r.data["results"]]
        while r.data["next"]:
            r = self.a.get(r.data["next"])
            seen += [m["id"] for m in r.data["results"]]
        self.assertEqual(len(seen), 25)
        self.assertEqual(len(set(seen)), 25)

    def test_edit_within_window_only(self):
        make_friends(self.alice, self.bob)
        cid = self.open(self.a, self.bob)
        mid = self.send(self.a, cid, "typo").data["id"]
        r = self.a.patch(f"/api/messaging/messages/{mid}/", {"body": "fixed"}, format="json")
        self.assertEqual((r.status_code, r.data["body"]), (200, "fixed"))
        self.assertIsNotNone(r.data["edited_at"])
        Message.objects.filter(pk=mid).update(created_at=timezone.now() - timedelta(hours=1))
        self.assertEqual(self.a.patch(f"/api/messaging/messages/{mid}/", {"body": "late"}, format="json").status_code, 403)

    def test_delete_leaves_tombstone(self):
        make_friends(self.alice, self.bob)
        cid = self.open(self.a, self.bob)
        mid = self.send(self.a, cid, "oops").data["id"]
        self.assertEqual(self.a.delete(f"/api/messaging/messages/{mid}/").status_code, 204)
        msg = self.b.get(f"/api/messaging/conversations/{cid}/messages/").data["results"][0]
        self.assertEqual((msg["body"], msg["is_deleted"]), ("", True))
        self.assertEqual(self.b.get("/api/messaging/conversations/").data["results"][0]["last_message"]["preview"], "Message deleted")
        self.assertEqual(self.b.get("/api/messaging/unread-count/").data["unread"], 0)
        self.assertEqual(self.a.patch(f"/api/messaging/messages/{mid}/", {"body": "x"}, format="json").status_code, 409)

    def test_validation(self):
        cid = self.open(self.a, self.bob)
        self.assertEqual(self.send(self.a, cid, "   ").status_code, 400)
        self.assertEqual(self.send(self.a, cid, "x" * 2001).status_code, 400)
        self.assertEqual(Conversation.objects.get(pk=cid).restricted_message_count, 0)   # rejected messages don't count

    def test_start_conversation_with_first_message(self):
        r = self.a.post("/api/messaging/conversations/", {"recipient_id": self.bob.pk, "body": "hello!"}, format="json")
        self.assertEqual(r.data["last_message"]["preview"], "hello!")
        self.assertEqual(r.data["messages_remaining"], 3)

    def test_new_message_notification_is_collapsed(self):
        cid = self.open(self.a, self.bob)
        self.send(self.a, cid, "1")
        self.send(self.a, cid, "2")
        self.assertEqual(Notification.objects.filter(recipient=self.bob, type="new_message").count(), 1)

    def test_profile_message_permission(self):
        self.assertTrue(self.a.get("/api/social/profiles/bob/").data["can_message"])
        Block.objects.create(blocker=self.bob, blocked=self.alice)
        self.assertEqual(self.a.get("/api/social/profiles/bob/").status_code, 404)
