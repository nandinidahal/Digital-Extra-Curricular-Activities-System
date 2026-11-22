"""Small reusable rules (kept free of imports from services to avoid cycles)."""
from django.db.models import Q


def available_account_q(prefix=""):
    """
    Q object for "this account may take part in friend features": active AND e-mail verified.
    This is the same rule Profiles uses to decide whether a profile is a public person.
    `prefix` is a relation path such as "sender__".
    """
    return Q(**{f"{prefix}is_active": True, f"{prefix}is_email_verified": True})


def is_available(user):
    return bool(user is not None and user.is_active and user.is_email_verified)
