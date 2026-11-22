from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "profile_visibility", "institution", "education_level", "date_created")
    list_filter = ("profile_visibility", "education_level")
    search_fields = ("user__username", "user__email", "user__full_name", "institution")
    raw_id_fields = ("user",)
    readonly_fields = ("id", "date_created", "updated_at")
    ordering = ("-date_created",)
