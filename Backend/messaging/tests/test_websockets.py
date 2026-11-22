"""
End-to-end WebSocket tests through the real ASGI application (origin check -> JWT middleware ->
router -> consumer) with real database commits (TransactionTestCase), so on_commit
broadcasts actually run.
"""
import asyncio
import uuid
from datetime import timedelta

from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase, override_settings
from rest_framework_simplejwt.tokens import AccessToken

from friends import services as friend_services
from messaging import services
from messaging.models import Message

from .base import TEST_SETTINGS, MessagingHelpers

ORIGIN = b"http://localhost:5173"


def _application():
    from config.asgi import application

    return application


@override_settings(**TEST_SETTINGS)
class WebSocketTestCase(MessagingHelpers, TransactionTestCase):
    def setUp(self):
        super().setUp()
        # Each async test runs in a new event loop. channels_redis binds internal locks to the
        # loop that first used it, so give every test a fresh layer (a server process has one
        # loop for its whole life, so this only matters in tests).
        from channels.layers import channel_layers
        channel_layers.backends.clear()
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        self.carol = self.make_user("carol")
        self.befriend(self.alice, self.bob)
        self.conversation = self.make_conversation(self.alice, self.bob)
        self.cid = str(self.conversation.pk)
        self.open = []

    async def asyncTearDown(self):
        pass

    async def connect(self, user=None, path="/ws/messaging/", *, token=None, origin=ORIGIN, expect=True):
        if user is not None:
            token = str(AccessToken.for_user(user))
        headers = [(b"origin", origin)] if origin else []
        communicator = WebsocketCommunicator(
            _application(), path, headers=headers, subprotocols=["deas.jwt", token] if token else []
        )
        connected, detail = await communicator.connect(timeout=3)
        if expect:
            self.assertTrue(connected, f"connection refused: {detail}")
            self.assertEqual(detail, "deas.jwt")
            ready = await communicator.receive_json_from(timeout=3)
            self.assertEqual(ready["type"], "connection.ready")
            self.open.append(communicator)
        return communicator, connected, detail

    async def close_all(self):
        for communicator in self.open:
            try:
                await communicator.disconnect()
            except Exception:
                pass
        self.open = []

    async def receive(self, communicator, event_type, timeout=3):
        """Next event of `event_type`, skipping unrelated ones (presence, etc.)."""
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                self.fail(f"did not receive {event_type}")
            event = await communicator.receive_json_from(timeout=remaining)
            if event["type"] == event_type:
                return event

    async def nothing_of(self, communicator, event_type, timeout=0.4):
        """Assert no `event_type` arrives. Uses receive_nothing(), which - unlike a timed-out
        receive - does not cancel the application under test."""
        quiet = await communicator.receive_nothing(timeout=timeout)
        while not quiet:
            event = await communicator.receive_json_from(timeout=1)
            self.assertNotEqual(event["type"], event_type, event)
            quiet = await communicator.receive_nothing(timeout=0.05)

    async def request(self, communicator, event_type, data=None, conversation_id=None):
        request_id = uuid.uuid4().hex[:8]
        payload = {"type": event_type, "request_id": request_id, "data": data or {}}
        if conversation_id:
            payload["conversation_id"] = conversation_id
        await communicator.send_json_to(payload)
        while True:
            event = await communicator.receive_json_from(timeout=3)
            if event.get("request_id") == request_id and event["type"] in ("ack", "error", "pong"):
                return event


class WebSocketAuthTests(WebSocketTestCase):
    async def test_rejects_missing_and_invalid_token(self):
        _c, connected, _d = await self.connect(expect=False)
        self.assertFalse(connected)
        _c, connected, _d = await self.connect(token="garbage.token.value", expect=False)
        self.assertFalse(connected)

    async def test_rejects_foreign_origin(self):
        _c, connected, _d = await self.connect(self.alice, origin=b"https://evil.example", expect=False)
        self.assertFalse(connected)

    async def test_rejects_unverified_or_inactive_user(self):
        ghost = await database_sync_to_async(self.make_user)("ghost", is_email_verified=False)
        _c, connected, code = await self.connect(ghost, expect=False)
        self.assertFalse(connected)

    async def test_accepts_jwt_subprotocol(self):
        await self.connect(self.alice)
        await self.close_all()

    async def test_one_time_ticket(self):
        from rest_framework.test import APIClient

        def get_ticket():
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.alice)}")
            return client.post("/api/messaging/ws-ticket/").json()["data"]["ticket"]

        ticket = await database_sync_to_async(get_ticket)()
        communicator = WebsocketCommunicator(_application(), f"/ws/messaging/?ticket={ticket}", headers=[(b"origin", ORIGIN)])
        connected, _ = await communicator.connect(timeout=3)
        self.assertTrue(connected)
        await communicator.disconnect()
        again = WebsocketCommunicator(_application(), f"/ws/messaging/?ticket={ticket}", headers=[(b"origin", ORIGIN)])
        connected, _ = await again.connect(timeout=3)
        self.assertFalse(connected)  # single use

    async def test_non_participant_cannot_open_conversation_socket(self):
        _c, connected, code = await self.connect(
            self.carol, f"/ws/messaging/conversations/{self.cid}/", expect=False
        )
        self.assertFalse(connected)
        self.assertEqual(code, 4404)

    async def test_expired_token_closes_socket(self):
        token = AccessToken.for_user(self.alice)
        token.set_exp(lifetime=timedelta(seconds=1))
        communicator, _c, _d = await self.connect(token=str(token))
        await asyncio.sleep(1.2)
        await communicator.send_json_to({"type": "ping"})
        event = await communicator.receive_json_from(timeout=3)
        self.assertEqual(event["type"], "auth.expired")
        output = await communicator.receive_output(timeout=3)
        self.assertEqual(output["type"], "websocket.close")
        self.assertEqual(output["code"], 4401)


class WebSocketMessagingTests(WebSocketTestCase):
    async def test_send_and_receive_in_real_time(self):
        alice, _, _ = await self.connect(self.alice)
        bob, _, _ = await self.connect(self.bob)
        carol, _, _ = await self.connect(self.carol)
        ack = await self.request(alice, "message.send", {"content": "hi bob", "client_id": str(uuid.uuid4())}, self.cid)
        self.assertEqual(ack["type"], "ack", ack)
        self.assertTrue(ack["data"]["created"])
        new = await self.receive(bob, "message.new")
        self.assertEqual(new["conversation_id"], self.cid)
        self.assertEqual(new["data"]["content"], "hi bob")
        self.assertEqual(new["data"]["sender"]["id"], str(self.alice.pk))
        self.assertFalse(new["data"]["is_own"])
        await self.nothing_of(carol, "message.new")  # only participants
        await self.close_all()

    async def test_sender_id_in_payload_is_ignored(self):
        alice, _, _ = await self.connect(self.alice)
        ack = await self.request(alice, "message.send", {"content": "x", "sender_id": str(self.bob.pk)}, self.cid)
        self.assertEqual(ack["data"]["message"]["sender"]["id"], str(self.alice.pk))
        await self.close_all()

    async def test_rest_send_is_pushed_to_socket(self):
        bob, _, _ = await self.connect(self.bob)
        await database_sync_to_async(services.send_message)(self.alice, self.cid, content="via REST")
        new = await self.receive(bob, "message.new")
        self.assertEqual(new["data"]["content"], "via REST")
        await self.close_all()

    async def test_edit_delete_and_reaction_events(self):
        alice, _, _ = await self.connect(self.alice)
        bob, _, _ = await self.connect(self.bob)
        ack = await self.request(alice, "message.send", {"content": "draft"}, self.cid)
        message_id = ack["data"]["message"]["id"]
        await self.receive(bob, "message.new")

        ack = await self.request(alice, "message.edit", {"message_id": message_id, "content": "final"})
        self.assertEqual(ack["type"], "ack", ack)
        updated = await self.receive(bob, "message.updated")
        self.assertEqual(updated["data"]["content"], "final")
        self.assertTrue(updated["data"]["is_edited"])

        await self.request(bob, "message.reaction", {"message_id": message_id, "reaction_type": "love"})
        reaction = await self.receive(alice, "message.reaction_updated")
        self.assertEqual(reaction["data"]["reactions"], {"love": 1})
        self.assertIsNone(reaction["data"]["my_reaction"])  # alice did not react

        await self.request(alice, "message.delete", {"message_id": message_id, "scope": "everyone"})
        deleted = await self.receive(bob, "message.deleted")
        self.assertEqual(deleted["data"], {**deleted["data"], "message_id": message_id, "scope": "everyone"})
        await self.close_all()

    async def test_bob_cannot_edit_alice_message_over_socket(self):
        alice, _, _ = await self.connect(self.alice)
        bob, _, _ = await self.connect(self.bob)
        ack = await self.request(alice, "message.send", {"content": "mine"}, self.cid)
        error = await self.request(bob, "message.edit", {"message_id": ack["data"]["message"]["id"], "content": "hacked"})
        self.assertEqual(error["type"], "error")
        self.assertEqual(error["code"], "not_message_owner")
        await self.close_all()

    async def test_typing_indicator(self):
        alice, _, _ = await self.connect(self.alice)
        bob, _, _ = await self.connect(self.bob)
        carol, _, _ = await self.connect(self.carol)
        await alice.send_json_to({"type": "message.typing", "conversation_id": self.cid, "data": {"is_typing": True}})
        typing = await self.receive(bob, "user.typing")
        self.assertEqual(typing["data"]["user_id"], str(self.alice.pk))
        self.assertTrue(typing["data"]["is_typing"])
        self.assertGreater(typing["data"]["expires_in"], 0)
        await self.nothing_of(carol, "user.typing")
        await alice.send_json_to({"type": "message.typing", "conversation_id": self.cid, "data": {"is_typing": False}})
        stopped = await self.receive(bob, "user.typing")
        self.assertFalse(stopped["data"]["is_typing"])
        await self.close_all()

    async def test_typing_into_foreign_conversation_is_refused(self):
        carol, _, _ = await self.connect(self.carol)
        bob, _, _ = await self.connect(self.bob)
        error = await self.request(carol, "message.typing", {"is_typing": True}, self.cid)
        self.assertEqual(error["code"], "conversation_not_found")
        await self.nothing_of(bob, "user.typing")
        await self.close_all()

    async def test_read_and_delivered_receipts(self):
        alice, _, _ = await self.connect(self.alice)
        bob, _, _ = await self.connect(self.bob)
        ack = await self.request(alice, "message.send", {"content": "read me"}, self.cid)
        message_id = ack["data"]["message"]["id"]
        self.assertEqual(ack["data"]["message"]["status"], "sent")
        await self.receive(bob, "message.new")

        await self.request(bob, "message.delivered", {"message_ids": [message_id]})
        delivered = await self.receive(alice, "message.delivered")
        self.assertEqual(delivered["data"]["message_ids"], [message_id])

        await self.request(bob, "message.read", {}, self.cid)
        read = await self.receive(alice, "message.read")
        self.assertEqual(read["data"]["message_ids"], [message_id])
        self.assertEqual(read["data"]["user_id"], str(self.bob.pk))
        await self.close_all()

    async def test_sender_cannot_fake_read_receipt(self):
        alice, _, _ = await self.connect(self.alice)
        ack = await self.request(alice, "message.send", {"content": "x"}, self.cid)
        result = await self.request(alice, "message.read", {}, self.cid)
        self.assertEqual(result["data"]["message_ids"], [])
        result = await self.request(alice, "message.delivered", {"message_ids": [ack["data"]["message"]["id"]]})
        self.assertEqual(result["data"]["message_ids"], [])
        await self.close_all()

    async def test_four_message_limit_over_websocket(self):
        conversation = await database_sync_to_async(self.make_conversation)(self.alice, self.carol)
        cid = str(conversation.pk)
        alice, _, _ = await self.connect(self.alice)
        carol, _, _ = await self.connect(self.carol)
        for i, sock in enumerate([alice, carol, alice, carol]):
            ack = await self.request(sock, "message.send", {"content": f"m{i}"}, cid)
            self.assertEqual(ack["type"], "ack", ack)
        error = await self.request(alice, "message.send", {"content": "fifth"}, cid)
        self.assertEqual(error["type"], "error")
        self.assertEqual(error["code"], "message_limit_reached")
        self.assertEqual(error["messages_used"], 4)
        self.assertFalse(error["can_message"])
        count = await database_sync_to_async(Message.objects.filter(conversation_id=cid).count)()
        self.assertEqual(count, 4)
        await self.close_all()

    async def test_block_restrictions_over_websocket(self):
        await database_sync_to_async(friend_services.block_user)(self.bob, self.alice.pk)
        alice, _, _ = await self.connect(self.alice)
        bob, _, _ = await self.connect(self.bob)
        error = await self.request(alice, "message.send", {"content": "let me in"}, self.cid)
        self.assertEqual(error["code"], "messaging_not_allowed")
        await alice.send_json_to({"type": "message.typing", "conversation_id": self.cid, "data": {"is_typing": True}})
        await self.nothing_of(bob, "user.typing")
        await self.nothing_of(bob, "message.new", timeout=0.2)
        await self.close_all()

    async def test_reconnect_with_same_client_id_does_not_duplicate(self):
        client_id = str(uuid.uuid4())
        alice, _, _ = await self.connect(self.alice)
        bob, _, _ = await self.connect(self.bob)
        first = await self.request(alice, "message.send", {"content": "once", "client_id": client_id}, self.cid)
        await self.receive(bob, "message.new")
        await alice.disconnect()
        self.open.remove(alice)
        alice2, _, _ = await self.connect(self.alice)  # reconnect and retry
        second = await self.request(alice2, "message.send", {"content": "once", "client_id": client_id}, self.cid)
        self.assertFalse(second["data"]["created"])
        self.assertEqual(first["data"]["message"]["id"], second["data"]["message"]["id"])
        await self.nothing_of(bob, "message.new")
        count = await database_sync_to_async(Message.objects.count)()
        self.assertEqual(count, 1)
        await self.close_all()

    async def test_conversation_socket_filters_other_conversations(self):
        await database_sync_to_async(self.befriend)(self.alice, self.carol)
        other = await database_sync_to_async(self.make_conversation)(self.alice, self.carol)
        alice_conv, _, _ = await self.connect(self.alice, f"/ws/messaging/conversations/{self.cid}/")
        await database_sync_to_async(services.send_message)(self.carol, other.pk, content="elsewhere")
        await self.nothing_of(alice_conv, "message.new")
        await database_sync_to_async(services.send_message)(self.bob, self.cid, content="here")
        new = await self.receive(alice_conv, "message.new")
        self.assertEqual(new["data"]["content"], "here")
        # conversation id may be omitted on a conversation socket
        ack = await self.request(alice_conv, "message.send", {"content": "implicit"})
        self.assertEqual(ack["type"], "ack", ack)
        await self.close_all()

    async def test_invalid_events(self):
        alice, _, _ = await self.connect(self.alice)
        await alice.send_to(text_data="not json")
        self.assertEqual((await alice.receive_json_from())["code"], "invalid_event")
        error = await self.request(alice, "message.explode", {})
        self.assertEqual(error["code"], "unknown_event")
        error = await self.request(alice, "message.send", {"content": "x"})  # inbox socket needs conversation_id
        self.assertEqual(error["code"], "validation_error")
        error = await self.request(alice, "message.send", {"content": "   "}, self.cid)
        self.assertEqual(error["code"], "validation_error")
        error = await self.request(alice, "message.edit", {"message_id": "nope", "content": "x"})
        self.assertEqual(error["code"], "validation_error")
        pong = await self.request(alice, "ping")
        self.assertEqual(pong["type"], "pong")
        await self.close_all()

    async def test_event_rate_limit(self):
        with override_settings(MESSAGING_THROTTLE_RATES={**TEST_SETTINGS["MESSAGING_THROTTLE_RATES"], "messaging_ws_event": "3/min"}):
            alice, _, _ = await self.connect(self.alice)
            for _ in range(3):
                await self.request(alice, "message.send", {"content": "spam"}, self.cid)
            error = await self.request(alice, "message.send", {"content": "spam"}, self.cid)
            self.assertEqual(error["code"], "throttled")
            await self.close_all()


class WebSocketPresenceTests(WebSocketTestCase):
    async def test_online_and_offline_events_for_friends_only(self):
        await database_sync_to_async(self.make_conversation)(self.carol, self.bob)  # carol shares a chat, not a friend
        alice, _, _ = await self.connect(self.alice)
        carol, _, _ = await self.connect(self.carol)
        bob, _, _ = await self.connect(self.bob)
        online = await self.receive(alice, "user.presence")
        self.assertEqual(online["data"]["user_id"], str(self.bob.pk))
        self.assertTrue(online["data"]["is_online"])
        await self.nothing_of(carol, "user.presence")
        await bob.disconnect()
        self.open.remove(bob)
        offline = await self.receive(alice, "user.presence")
        self.assertFalse(offline["data"]["is_online"])
        self.assertIsNotNone(offline["data"]["last_seen_at"])
        await self.close_all()

    async def test_presence_not_sent_to_blocked_user(self):
        await database_sync_to_async(friend_services.block_user)(self.bob, self.alice.pk)
        alice, _, _ = await self.connect(self.alice)
        await self.connect(self.bob)
        await self.nothing_of(alice, "user.presence")
        await self.close_all()

    async def test_second_device_does_not_flap_presence(self):
        alice, _, _ = await self.connect(self.alice)
        bob1, _, _ = await self.connect(self.bob)
        await self.receive(alice, "user.presence")
        bob2, _, _ = await self.connect(self.bob)
        await self.nothing_of(alice, "user.presence")
        await bob1.disconnect()
        self.open.remove(bob1)
        await self.nothing_of(alice, "user.presence")  # still online on device 2
        await self.close_all()

    async def test_heartbeat_ack(self):
        alice, _, _ = await self.connect(self.alice)
        ack = await self.request(alice, "presence.heartbeat")
        self.assertEqual(ack["type"], "ack")
        await self.close_all()


class RelationshipEventTests(WebSocketTestCase):
    async def test_friendship_change_pushes_new_permissions(self):
        conversation = await database_sync_to_async(self.make_conversation)(self.alice, self.carol)
        carol, _, _ = await self.connect(self.carol)

        def befriend_via_friends_module():
            result = friend_services.send_friend_request(self.alice, self.carol.pk)
            friend_services.accept_friend_request(self.carol, result.friend_request.pk)

        await database_sync_to_async(befriend_via_friends_module)()
        event = await self.receive(carol, "conversation.permissions")
        self.assertEqual(event["conversation_id"], str(conversation.pk))
        self.assertTrue(event["data"]["is_friend"])
        self.assertTrue(event["data"]["can_message"])

        await database_sync_to_async(friend_services.block_user)(self.alice, self.carol.pk)
        event = await self.receive(carol, "conversation.permissions")
        self.assertFalse(event["data"]["can_message"])
        self.assertEqual(event["data"]["reason"], "blocked")
        await self.close_all()
