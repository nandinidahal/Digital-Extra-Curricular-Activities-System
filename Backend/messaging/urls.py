from django.urls import path

from . import views

urlpatterns = [
    path("conversations/", views.ConversationListView.as_view(), name="conversation-list"),
    path("conversations/<int:conversation_id>/", views.ConversationDetailView.as_view(), name="conversation-detail"),
    path("conversations/<int:conversation_id>/messages/", views.MessageListCreateView.as_view(), name="message-list"),
    path("conversations/<int:conversation_id>/read/", views.ConversationReadView.as_view(), name="conversation-read"),
    path("messages/<int:message_id>/", views.MessageDetailView.as_view(), name="message-detail"),
    path("unread-count/", views.UnreadCountView.as_view(), name="messages-unread-count"),
]
