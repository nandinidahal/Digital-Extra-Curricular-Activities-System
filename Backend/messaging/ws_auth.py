"""
WebSocket authentication (browsers cannot send an Authorization header on a WebSocket).

Two supported ways, checked in this order:

1. JWT as subprotocol (preferred):
       new WebSocket(url, ["deas.jwt", accessToken])
   The server accepts the "deas.jwt" subprotocol; the token is never echoed and never part of
   the URL, so it does not end up in proxy/access logs.
2. One-time ticket:
       POST /api/messaging/ws-ticket/  (normal JWT request)  -> {"ticket": "..."}
       new WebSocket(`${url}?ticket=${ticket}`)
   Tickets live 30 seconds in the cache and work exactly once.

The access token's expiry is stored in the scope; the consumer closes the socket (code 4401)
once it has expired, so a stolen-then-expired token cannot keep a socket alive forever.
JWT in a plain ?token= query parameter is deliberately NOT supported.
"""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken

SUBPROTOCOL = "deas.jwt"
TICKET_KEY = "messaging:wsticket:%s"  # must match views.WS_TICKET_KEY


@database_sync_to_async
def _user_from_token(raw):
    try:
        token = AccessToken(raw)
    except TokenError:
        return None, None
    user_id = token.get(api_settings.USER_ID_CLAIM)
    if user_id is None:
        return None, None
    user = get_user_model().objects.filter(**{api_settings.USER_ID_FIELD: user_id}).first()
    if user is None or not user.is_active:
        return None, None
    return user, token.get("exp")


@database_sync_to_async
def _user_from_ticket(ticket):
    key = TICKET_KEY % ticket
    user_id = cache.get(key)
    if not user_id or not cache.delete(key):  # delete() returns True exactly once -> single use
        return None
    user = get_user_model().objects.filter(pk=user_id).first()
    return user if user is not None and user.is_active else None


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        scope["user"] = AnonymousUser()
        scope["token_exp"] = None
        scope["accepted_subprotocol"] = None

        protocols = list(scope.get("subprotocols") or [])
        if len(protocols) >= 2 and protocols[0] == SUBPROTOCOL:
            user, exp = await _user_from_token(protocols[1])
            if user is not None:
                scope["user"], scope["token_exp"] = user, exp
                scope["accepted_subprotocol"] = SUBPROTOCOL
        else:
            query = parse_qs((scope.get("query_string") or b"").decode("latin-1"))
            ticket = (query.get("ticket") or [None])[0]
            if ticket and len(ticket) <= 128:
                user = await _user_from_ticket(ticket)
                if user is not None:
                    scope["user"] = user
        return await super().__call__(scope, receive, send)
