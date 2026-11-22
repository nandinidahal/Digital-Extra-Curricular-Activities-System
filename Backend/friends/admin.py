from django.contrib import admin

from .models import FriendRequest, Friendship, UserBlock


@admin.register(FriendRequest)
class FriendRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "sender", "receiver", "status", "created_at", "responded_at")
    list_filter = ("status",)
    search_fields = ("sender__username", "receiver__username")
    raw_id_fields = ("sender", "receiver")
    readonly_fields = ("created_at", "updated_at", "responded_at")
    list_select_related = ("sender", "receiver")


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ("id", "user1", "user2", "created_at")
    search_fields = ("user1__username", "user2__username")
    raw_id_fields = ("user1", "user2")
    readonly_fields = ("created_at",)
    list_select_related = ("user1", "user2")


@admin.register(UserBlock)
class UserBlockAdmin(admin.ModelAdmin):
    list_display = ("id", "blocker", "blocked", "created_at")
    search_fields = ("blocker__username", "blocked__username")
    raw_id_fields = ("blocker", "blocked")
    readonly_fields = ("created_at",)
    list_select_related = ("blocker", "blocked")
