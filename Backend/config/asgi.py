"""
ASGI entry point: HTTP goes to Django, WebSockets to Channels.

Run with an ASGI server, e.g.  daphne -b 0.0.0.0 -p 8000 config.asgi:application
(`python manage.py runserver` also serves WebSockets because `daphne` is in INSTALLED_APPS).
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django_asgi_app = get_asgi_application()  # must run before importing anything that uses models

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import OriginValidator  # noqa: E402
from django.conf import settings  # noqa: E402

from messaging.routing import websocket_urlpatterns as messaging_ws  # noqa: E402
from messaging.ws_auth import JWTAuthMiddleware  # noqa: E402
from notifications.routing import websocket_urlpatterns as notifications_ws  # noqa: E402

# The existing JWT middleware (subprotocol or one-time ticket) protects every socket route.
websocket_urlpatterns = messaging_ws + notifications_ws


def _allowed_ws_origins():
    """Browser origins allowed to open sockets: the frontend origins + this API's own hosts."""
    origins = list(getattr(settings, "MESSAGING_WS_ALLOWED_ORIGINS", []) or [])
    origins += list(getattr(settings, "CORS_ALLOWED_ORIGINS", []) or [])
    for host in settings.ALLOWED_HOSTS:
        origins += [f"http://{host}", f"https://{host}"] if host != "*" else ["*"]
    return sorted(set(origins))


application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": OriginValidator(
            JWTAuthMiddleware(URLRouter(websocket_urlpatterns)), _allowed_ws_origins()
        ),
    }
)
