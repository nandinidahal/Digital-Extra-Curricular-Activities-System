from django.dispatch import receiver  # noqa: F401

from messaging import signals

from .base import MessagingTestCase


class NotificationSignalTests(MessagingTestCase):
    def setUp(self):
        super().setUp()
        self.befriend(self.alice, self.bob)
        self.cid = self.start(self.alice, self.bob)
        self.received = []

        def handler(sender, **kwargs):
            self.received.append(kwargs)

        signals.message_sent.connect(handler, weak=False, dispatch_uid="test_handler")
        self.addCleanup(signals.message_sent.disconnect, dispatch_uid="test_handler")

    def test_message_sent_fires_once_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.send_ok(self.alice, self.cid, "hi")
        self.assertEqual(len(self.received), 1)
        event = self.received[0]
        self.assertEqual(event["sender_id"], self.alice.pk)
        self.assertEqual(event["recipient_ids"], [self.bob.pk])
        self.assertEqual(event["notify_user_ids"], [self.bob.pk])

    def test_muted_recipient_is_not_notified(self):
        self.client_for(self.bob).patch(self.url("conversation-mute", conversation_id=self.cid), {"is_muted": True}, format="json")
        with self.captureOnCommitCallbacks(execute=True):
            self.send_ok(self.alice, self.cid, "hi")
        self.assertEqual(self.received[0]["recipient_ids"], [self.bob.pk])
        self.assertEqual(self.received[0]["notify_user_ids"], [])

    def test_idempotent_retry_does_not_notify_twice(self):
        client_id = "1c3f6d2e-0000-4000-8000-000000000001"
        with self.captureOnCommitCallbacks(execute=True):
            self.send(self.alice, self.cid, "hi", client_id=client_id)
        with self.captureOnCommitCallbacks(execute=True):
            self.send(self.alice, self.cid, "hi", client_id=client_id)
        self.assertEqual(len(self.received), 1)

    def test_failed_send_does_not_notify(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.send(self.alice, self.cid, "")
        self.assertEqual(self.received, [])

    def test_broken_receiver_does_not_break_sending(self):
        def broken(sender, **kwargs):
            raise RuntimeError("notifications down")

        signals.message_sent.connect(broken, dispatch_uid="broken")
        self.addCleanup(signals.message_sent.disconnect, dispatch_uid="broken")
        with self.captureOnCommitCallbacks(execute=True):
            response = self.send(self.alice, self.cid, "still works")
        self.assertEqual(response.status_code, 201)
