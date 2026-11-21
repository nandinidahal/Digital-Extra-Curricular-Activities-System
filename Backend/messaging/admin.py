from django.contrib import admin

from .models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "user_low", "user_high", "restricted_message_count", "last_message_at")
    raw_id_fields = ("user_low", "user_high", "last_message")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "created_at", "read_at", "deleted_at")
    raw_id_fields = ("conversation", "sender")
