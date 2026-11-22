from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm as DjangoUserChangeForm
from django.contrib.auth.forms import UserCreationForm as DjangoUserCreationForm

from .models import OneTimePassword, PasswordResetToken, User


class UserCreationForm(DjangoUserCreationForm):
    class Meta(DjangoUserCreationForm.Meta):
        model = User
        fields = ("username", "email", "full_name", "role", "is_email_verified")


class UserChangeForm(DjangoUserChangeForm):
    class Meta(DjangoUserChangeForm.Meta):
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    # Django's default admin expects first_name/last_name, which this model replaces with full_name.
    list_display = ("username", "email", "full_name", "role", "is_email_verified", "is_active", "date_joined")
    list_filter = ("role", "is_email_verified", "is_active", "is_staff")
    search_fields = ("username", "email", "full_name")
    ordering = ("-date_joined",)
    readonly_fields = ("id", "last_login", "date_joined", "updated_at")

    fieldsets = (
        (None, {"fields": ("id", "username", "password")}),
        ("Personal info", {"fields": ("full_name", "email", "phone_number", "country", "date_of_birth")}),
        ("Role & verification", {"fields": ("role", "is_email_verified")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "email",
                    "full_name",
                    "role",
                    "is_email_verified",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


@admin.register(OneTimePassword)
class OneTimePasswordAdmin(admin.ModelAdmin):
    """Read-only: the hash is stored, never the code."""

    list_display = ("user", "purpose", "is_used", "attempts", "expires_at", "created_at")
    list_filter = ("purpose", "is_used")
    search_fields = ("user__username", "user__email")
    exclude = ("otp_hash",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "is_used", "expires_at", "created_at")
    list_filter = ("is_used",)
    exclude = ("token_hash",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
