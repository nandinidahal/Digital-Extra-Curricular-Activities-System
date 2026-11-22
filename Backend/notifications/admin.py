from django.contrib import admin

from .models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("notification_type", "recipient", "actor", "is_read", "email_status", "created_at")
    list_filter = ("category", "notification_type", "is_read", "email_status")
    search_fields = ("recipient__username", "recipient__email", "title")
    raw_id_fields = ("recipient", "actor")
    readonly_fields = ("id", "created_at", "updated_at", "read_at", "emailed_at", "email_attempts", "dedupe_key", "group_key")
    date_hierarchy = "created_at"


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "email_notifications", "realtime_notifications", "updated_at")
    search_fields = ("user__username", "user__email")
    raw_id_fields = ("user",)
