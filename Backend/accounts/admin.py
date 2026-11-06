from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import EmailOTP, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "full_name", "role", "is_email_verified", "is_active")
    list_filter = ("role", "is_email_verified", "is_active")
    search_fields = ("username", "email", "full_name")
    fieldsets = UserAdmin.fieldsets + (
        ("XCA profile", {"fields": ("full_name", "phone_number", "country", "date_of_birth",
                                     "role", "is_email_verified", "token_version")}),
    )


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "created_at", "expires_at", "attempts", "is_used")
    readonly_fields = ("code_hash", "reset_token_hash")
