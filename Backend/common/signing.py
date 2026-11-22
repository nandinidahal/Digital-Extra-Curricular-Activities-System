"""
Short-lived signed download links for PRIVATE files (same approach Messaging uses).

An <img src> or <a href> cannot send an Authorization header, so private file endpoints accept
either a JWT or `?token=<signed>`. A token is bound to the file kind, the object id and the user
it was issued to, and expires after `max_age` seconds.
"""
from django.core import signing

SALT = "deas.common.download"


def make_download_token(kind, object_id, user_id):
    return signing.dumps({"k": kind, "o": str(object_id), "u": str(user_id)}, salt=SALT)


def read_download_token(token, *, kind, object_id, max_age):
    """Return the user id the token was issued to, or None when invalid/expired/for another file."""
    if not token or len(token) > 512:
        return None
    try:
        payload = signing.loads(token, salt=SALT, max_age=max_age)
    except (signing.BadSignature, signing.SignatureExpired):
        return None
    if not isinstance(payload, dict) or payload.get("k") != kind or payload.get("o") != str(object_id):
        return None
    return payload.get("u")
