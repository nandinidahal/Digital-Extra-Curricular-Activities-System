"""
Read-mostly admin for support/moderation. Message content is shown only on the detail page,
never in list columns, to limit casual exposure of private conversations.
"""
from django.contrib import admin

from .models import (
    Conversation,
    ConversationParticipant,
    Message,
    MessageAttachment,
    MessageReaction,
    MessageReceipt,
    UserPresence,
)


class ParticipantInline(admin.TabularInline):
    model = ConversationParticipant
    extra = 0
    raw_id_fields = ("user",)
    readonly_fields = ("joined_at", "last_read_at")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation_type", "created_at", "last_message_at", "is_active")
    list_filter = ("conversation_type", "is_active")
    readonly_fields = ("id", "direct_key", "created_by", "created_at", "updated_at", "last_message_at")
    inlines = [ParticipantInline]


class AttachmentInline(admin.TabularInline):
    model = MessageAttachment
    extra = 0
    fields = ("kind", "original_name", "content_type", "size", "created_at")
    readonly_fields = fields
    can_delete = False


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "message_type", "created_at", "is_edited", "is_deleted")
    list_filter = ("message_type", "is_deleted", "is_edited", "counts_toward_limit")
    raw_id_fields = ("conversation", "sender", "reply_to")
    readonly_fields = ("id", "client_id", "created_at", "updated_at", "edited_at", "deleted_at", "counts_toward_limit")
    inlines = [AttachmentInline]


@admin.register(MessageReaction)
class MessageReactionAdmin(admin.ModelAdmin):
    list_display = ("message", "user", "reaction_type", "created_at")
    raw_id_fields = ("message", "user")


@admin.register(MessageReceipt)
class MessageReceiptAdmin(admin.ModelAdmin):
    list_display = ("message", "user", "delivered_at", "read_at")
    raw_id_fields = ("message", "conversation", "user")


@admin.register(UserPresence)
class UserPresenceAdmin(admin.ModelAdmin):
    list_display = ("user", "last_seen_at")
    raw_id_fields = ("user",)
