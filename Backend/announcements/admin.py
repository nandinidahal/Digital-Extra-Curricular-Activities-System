from django.contrib import admin

from .models import Announcement, Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "activity_type", "country", "city", "status", "published_by", "published_at")
    list_filter = ("status", "activity_type", "category", "country")
    search_fields = ("title", "activity_name", "city", "keywords")
    readonly_fields = ("published_at", "created_at", "updated_at")
