from django.urls import path

from .consumers import MessagingConsumer

websocket_urlpatterns = [
    # Inbox socket: every event for every conversation of the user (recommended: one per tab).
    path("ws/messaging/", MessagingConsumer.as_asgi()),
    # Conversation socket: only events of one conversation (membership checked on connect).
    path("ws/messaging/conversations/<uuid:conversation_id>/", MessagingConsumer.as_asgi()),
]
