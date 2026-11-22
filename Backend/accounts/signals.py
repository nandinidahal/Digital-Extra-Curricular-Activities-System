"""
Integration events published by Accounts (same rules as friends.signals / messaging.signals):

* sent AFTER the database transaction commits, so receivers never see rolled-back data;
* sent with send_robust: a failing receiver is logged and never breaks an account operation.

Accounts stores no notifications; the Notifications module listens to these.
"""
import logging

from django.db import transaction
from django.dispatch import Signal

logger = logging.getLogger("accounts")

# user=<User>
email_verified = Signal()
# user=<User>, method="change" | "reset"
password_changed = Signal()


def emit_on_commit(signal, **kwargs):
    def _send():
        for receiver, result in signal.send_robust(sender=None, **kwargs):
            if isinstance(result, Exception):
                logger.error("Accounts signal receiver %r failed: %r", receiver, result)

    transaction.on_commit(_send)
