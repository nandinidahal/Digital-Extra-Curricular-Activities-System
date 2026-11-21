from django.contrib import admin

from .models import Block, FriendRequest, Friendship


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ("user_low", "user_high", "created_at")
    raw_id_fields = ("user_low", "user_high")


@admin.register(FriendRequest)
class FriendRequestAdmin(admin.ModelAdmin):
    list_display = ("sender", "receiver", "status", "is_ignored", "created_at", "responded_at")
    list_filter = ("status",)
    raw_id_fields = ("sender", "receiver")


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("blocker", "blocked", "created_at")
    raw_id_fields = ("blocker", "blocked")
