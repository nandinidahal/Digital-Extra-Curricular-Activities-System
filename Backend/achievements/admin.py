from django.contrib import admin

from .models import Achievement, AchievementCategory, AchievementDocument


@admin.register(AchievementCategory)
class AchievementCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "display_order")
    list_editable = ("is_active", "display_order")
    prepopulated_fields = {"slug": ("name",)}


class AchievementDocumentInline(admin.TabularInline):
    model = AchievementDocument
    extra = 0
    readonly_fields = ("original_filename", "content_type", "size", "uploaded_at")


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "category", "issuing_organization", "achievement_date", "visibility")
    list_filter = ("visibility", "category")
    search_fields = ("title", "issuing_organization", "user__username", "user__email")
    readonly_fields = ("created_at", "updated_at")
    inlines = [AchievementDocumentInline]
