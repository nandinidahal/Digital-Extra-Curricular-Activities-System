from django.contrib import admin

from .models import Comment, Notification, Post, PostImage


class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 0


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "kind", "visibility", "like_count", "comment_count", "share_count", "created_at")
    list_filter = ("kind", "visibility")
    search_fields = ("caption", "author__username")
    raw_id_fields = ("author", "shared_from", "achievement", "announcement")
    inlines = [PostImageInline]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "author", "parent", "created_at")
    raw_id_fields = ("post", "author", "parent")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "type", "actor", "is_read", "created_at")
    list_filter = ("type", "is_read")
    raw_id_fields = ("recipient", "actor", "post")
