from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import RegistrationRequest, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    model = User

    list_display = ("username", "user_id", "name", "is_approved", "is_staff","role")
    search_fields = ("username", "user_id", "name")
    ordering = ("id",)

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal Info", {"fields": ("name","role")}),
        ("MLM Info", {"fields": ("user_id", "sponsor")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Status", {"fields": ("is_approved", "is_wallet_active")}),
        ("Important Dates", {"fields": ("last_login",)}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "password1", "password2", "is_staff", "is_superuser"),
        }),
    )


@admin.register(RegistrationRequest)
class RegistrationRequestAdmin(admin.ModelAdmin):
    list_display = ["name", "phone", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["name", "phone"]