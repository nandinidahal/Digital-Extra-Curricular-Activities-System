from django.contrib import admin

from .models import Achievement, AchievementCategory, AchievementEvidence, AchievementReview


@admin.register(AchievementCategory)
class AchievementCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}


class EvidenceInline(admin.TabularInline):
    model = AchievementEvidence
    extra = 0
    fields = ("original_name", "kind", "content_type", "size", "created_at")
    readonly_fields = fields
    can_delete = False


class ReviewInline(admin.TabularInline):
    model = AchievementReview
    extra = 0
    fields = ("decision", "previous_status", "new_status", "reviewer", "actor_role", "comments", "created_at")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False  # history is written by the workflow only


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    """Verification decisions go through the API workflow so history + notifications stay correct."""

    list_display = ("title", "user", "verification_status", "level", "visibility", "is_featured", "submitted_at")
    list_filter = ("verification_status", "level", "visibility", "is_featured", "category")
    search_fields = ("title", "organization", "user__username")
    raw_id_fields = ("user", "verified_by", "related_announcement")
    readonly_fields = ("verification_status", "verified_at", "verified_by", "submitted_at", "is_featured", "featured_at", "created_at", "updated_at")
    inlines = [EvidenceInline, ReviewInline]
