"""
Custom User Model for SERTOS Emergency Response Coordination System.

Enforces Role-Based Access Control (RBAC) across:
- System Administrators
- Ambulance Drivers & Paramedics
- Hospital Emergency Staff
- Police Traffic Dispatchers

Note: ESP32 IoT hardware devices use separate device-token authentication
in the `traffic` app and do not utilize human User accounts.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
    ADMIN = "ADMIN", "System Administrator"
    AMBULANCE_DRIVER = "AMBULANCE_DRIVER", "Ambulance Driver / Paramedic"
    HOSPITAL_STAFF = "HOSPITAL_STAFF", "Hospital Emergency Staff"
    POLICE_DISPATCHER = "POLICE_DISPATCHER", "Police Traffic Dispatcher"


class User(AbstractUser):
    """
    Primary user model for all human actors in SERTOS.
    Extends Django's AbstractUser to maintain built-in authentication,
    permission systems, and password hashing while adding domain roles.
    """

    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.AMBULANCE_DRIVER,
        help_text="Primary system role determining access permissions.",
    )
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="Direct emergency contact number.",
    )
    badge_or_employee_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Official institutional identification (e.g. Police Badge, Hospital ID, Ambulance Fleet License).",
    )
    age = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Driver age in years.",
    )
    is_verified = models.BooleanField(
        default=True,
        help_text="Designates whether this official personnel account has been verified by an administrator.",
    )

    class Meta:
        db_table = "accounts_user"
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-date_joined"]

    def __str__(self) -> str:
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_ambulance_driver(self) -> bool:
        return self.role == UserRole.AMBULANCE_DRIVER

    @property
    def is_hospital_staff(self) -> bool:
        return self.role == UserRole.HOSPITAL_STAFF

    @property
    def is_police_dispatcher(self) -> bool:
        return self.role == UserRole.POLICE_DISPATCHER

    @property
    def is_system_admin(self) -> bool:
        return self.role == UserRole.ADMIN or self.is_superuser
