from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin configuration for custom SERTOS User model."""

    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "SERTOS Role & Identification",
            {
                "fields": (
                    "role",
                    "phone_number",
                    "badge_or_employee_id",
                    "is_verified",
                )
            },
        ),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            "SERTOS Role & Identification",
            {
                "fields": (
                    "role",
                    "phone_number",
                    "badge_or_employee_id",
                    "is_verified",
                )
            },
        ),
    )
    list_display = (
        "username",
        "email",
        "role",
        "badge_or_employee_id",
        "is_verified",
        "is_staff",
    )
    list_filter = ("role", "is_verified", "is_staff", "is_superuser")
    search_fields = ("username", "email", "badge_or_employee_id", "phone_number")
