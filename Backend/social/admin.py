"""
Moderation integration point. Reports are reviewed in Django admin (no custom dashboard).
A future Admin module can reuse `services` and the ContentReport model.
"""
from django.contrib import admin
from django.utils import timezone

from . import services
from .models import Comment, CommentLike, ContentReport, Post, PostLike, PostMedia, PostShare


class PostMediaInline(admin.TabularInline):
    model = PostMedia
    extra = 0
    fields = ("image", "position", "width", "height")
    readonly_fields = ("width", "height")


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "post_type", "visibility", "is_deleted", "created_at")
    list_filter = ("post_type", "visibility", "is_deleted")
    search_fields = ("content", "author__username", "author__email")
    raw_id_fields = ("author",)
    readonly_fields = ("id", "created_at", "updated_at", "deleted_at")
    inlines = [PostMediaInline]
    actions = ["soft_delete_selected"]

    @admin.action(description="Remove selected posts from the platform (soft delete)")
    def soft_delete_selected(self, request, queryset):
        for post in queryset.filter(is_deleted=False):
            services.delete_post(post)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "author", "depth", "is_deleted", "created_at")
    list_filter = ("is_deleted", "depth")
    search_fields = ("content", "author__username")
    raw_id_fields = ("post", "author", "parent_comment")
    readonly_fields = ("id", "created_at", "updated_at", "deleted_at")
    actions = ["soft_delete_selected"]

    @admin.action(description="Remove selected comments (soft delete)")
    def soft_delete_selected(self, request, queryset):
        for comment in queryset.filter(is_deleted=False):
            services.delete_comment(comment)


@admin.register(PostLike, CommentLike, PostShare)
class InteractionAdmin(admin.ModelAdmin):
    raw_id_fields = ("user",)
    readonly_fields = ("id", "created_at")


@admin.register(ContentReport)
class ContentReportAdmin(admin.ModelAdmin):
    list_display = ("id", "content_type", "reason", "status", "reporter", "created_at", "reviewed_by")
    list_filter = ("status", "content_type", "reason")
    search_fields = ("description", "reporter__username")
    raw_id_fields = ("reporter", "post", "comment", "reviewed_by")
    readonly_fields = ("id", "created_at", "reporter", "content_type", "post", "comment", "reason", "description")
    actions = ["mark_reviewing", "mark_resolved", "mark_dismissed"]

    def _set_status(self, request, queryset, status):
        queryset.update(status=status, reviewed_by=request.user, reviewed_at=timezone.now())

    @admin.action(description="Mark as under review")
    def mark_reviewing(self, request, queryset):
        self._set_status(request, queryset, ContentReport.Status.REVIEWING)

    @admin.action(description="Mark as resolved (action taken)")
    def mark_resolved(self, request, queryset):
        self._set_status(request, queryset, ContentReport.Status.RESOLVED)

    @admin.action(description="Dismiss")
    def mark_dismissed(self, request, queryset):
        self._set_status(request, queryset, ContentReport.Status.DISMISSED)

    def save_model(self, request, obj, form, change):
        if change and "status" in form.changed_data:
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)
