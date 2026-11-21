from django.contrib import admin

from .models import Announcement, Bookmark, Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "display_order")
    list_editable = ("is_active", "display_order")
    search_fields = ("name",)


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "published_by", "status", "published_at", "is_featured", "is_important")
    list_filter = ("status", "category", "is_featured", "is_important")
    search_fields = ("title", "activity_name", "keywords")
    raw_id_fields = ("published_by",)
    readonly_fields = ("share_id", "created_at", "updated_at")


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ("user", "announcement", "created_at")
    raw_id_fields = ("user", "announcement")
