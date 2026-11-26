"""
Permissions for SERTOS Traffic & ESP32 IoT endpoints.

Enforces:
1. IsRegisteredESP32Device: strictly permits authenticated active TrafficDevice instances.
   Rejects human JWT credentials and anonymous requests.
2. System administrative access for hardware registration.
"""

from rest_framework.permissions import BasePermission
from apps.accounts.permissions import IsSystemAdmin
from .models import TrafficDevice


class IsRegisteredESP32Device(BasePermission):
    """
    Allows access only to active, authenticated ESP32 traffic controllers.
    Strictly prevents human users from accessing or impersonating IoT hardware endpoints.
    """

    message = "Access denied: Valid ESP32 device credentials required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and isinstance(request.user, TrafficDevice)
            and request.user.is_active
        )


__all__ = ["IsRegisteredESP32Device", "IsSystemAdmin"]
