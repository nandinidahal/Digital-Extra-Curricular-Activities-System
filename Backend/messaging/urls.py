from django.urls import path

from . import views

app_name = "messaging"

urlpatterns = [
    # Conversations
    path("conversations/", views.ConversationListCreateView.as_view(), name="conversations"),
    path("conversations/<uuid:conversation_id>/", views.ConversationDetailView.as_view(), name="conversation-detail"),
    path("conversations/<uuid:conversation_id>/mute/", views.ConversationMuteView.as_view(), name="conversation-mute"),
    path("conversations/<uuid:conversation_id>/archive/", views.ConversationArchiveView.as_view(), name="conversation-archive"),
    # Messages in a conversation
    path("conversations/<uuid:conversation_id>/messages/", views.ConversationMessagesView.as_view(), name="conversation-messages"),
    path("conversations/<uuid:conversation_id>/read/", views.MarkReadView.as_view(), name="conversation-read"),
    path("conversations/<uuid:conversation_id>/delivered/", views.MarkDeliveredView.as_view(), name="conversation-delivered"),
    path("conversations/<uuid:conversation_id>/unread-count/", views.UnreadCountView.as_view(), name="conversation-unread"),
    path("conversations/<uuid:conversation_id>/search/", views.SearchView.as_view(), name="conversation-search"),
    # Single messages
    path("messages/<uuid:message_id>/", views.MessageDetailView.as_view(), name="message-detail"),
    path("messages/<uuid:message_id>/delete-for-me/", views.DeleteForMeView.as_view(), name="message-delete-for-me"),
    path("messages/<uuid:message_id>/delete-for-everyone/", views.DeleteForEveryoneView.as_view(), name="message-delete-for-everyone"),
    path("messages/<uuid:message_id>/reply/", views.ReplyView.as_view(), name="message-reply"),
    path("messages/<uuid:message_id>/forward/", views.ForwardView.as_view(), name="message-forward"),
    path("messages/<uuid:message_id>/reactions/", views.ReactionView.as_view(), name="message-reactions"),
    # Attachments (private, signed or JWT)
    path("attachments/<uuid:attachment_id>/download/", views.AttachmentDownloadView.as_view(), name="attachment-download"),
    # Misc
    path("unread-count/", views.TotalUnreadCountView.as_view(), name="unread-total"),
    path("ws-ticket/", views.WebSocketTicketView.as_view(), name="ws-ticket"),
]
