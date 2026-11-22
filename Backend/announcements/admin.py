from django.contrib import admin, messages
from django.utils import timezone

from .models import Announcement, AnnouncementBookmark, AnnouncementReport, Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "category", "status", "visibility", "start_datetime", "published_at")
    list_filter = ("status", "visibility", "activity_type", "category")
    search_fields = ("title", "organizer_name", "author__username")
    raw_id_fields = ("author", "archived_by")
    readonly_fields = ("id", "slug", "published_at", "archived_at", "archived_by", "created_at", "updated_at")
    actions = ["archive_selected"]

    @admin.action(description="Archive selected announcements (moderation)")
    def archive_selected(self, request, queryset):
        updated = queryset.exclude(status="archived").update(
            status="archived", archived_at=timezone.now(), archived_by=request.user
        )
        self.message_user(request, f"{updated} announcement(s) archived.", messages.SUCCESS)


@admin.register(AnnouncementBookmark)
class AnnouncementBookmarkAdmin(admin.ModelAdmin):
    list_display = ("user", "announcement", "created_at")
    raw_id_fields = ("user", "announcement")


@admin.register(AnnouncementReport)
class AnnouncementReportAdmin(admin.ModelAdmin):
    list_display = ("announcement", "reporter", "reason", "status", "action_taken", "created_at")
    list_filter = ("status", "reason", "action_taken")
    raw_id_fields = ("announcement", "reporter", "reviewed_by")
    readonly_fields = ("created_at", "updated_at", "reviewed_at")
