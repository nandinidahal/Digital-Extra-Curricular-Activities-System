from django.contrib import admin

from .models import PendingEmailChange, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "profile_visibility", "email_visibility", "date_of_birth_visibility", "deactivated_at")
    list_filter = ("profile_visibility", "email_visibility", "date_of_birth_visibility", "bio_visibility")
    search_fields = ("user__username", "user__email", "user__full_name")
    raw_id_fields = ("user",)


@admin.register(PendingEmailChange)
class PendingEmailChangeAdmin(admin.ModelAdmin):
    list_display = ("user", "new_email", "created_at", "expires_at", "attempts")
    exclude = ("code_hash",)
    raw_id_fields = ("user",)
