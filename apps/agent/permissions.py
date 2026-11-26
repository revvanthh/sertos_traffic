"""
Permission policies for SERTOS AI Emergency Agent endpoints (Phase 8.1.3).
"""

from rest_framework.permissions import BasePermission
from apps.accounts.models import UserRole


class IsVerifiedAmbulanceDriver(BasePermission):
    """
    Strict permission policy:
    Allows access only to active, verified users with AMBULANCE_DRIVER role.
    """

    message = "Access restricted to verified ambulance drivers."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            self.message = "Authentication credentials were not provided."
            return False

        if getattr(user, "role", None) != UserRole.AMBULANCE_DRIVER:
            self.message = "Access denied: Ambulance driver credentials required."
            return False

        if not user.is_active or not getattr(user, "is_verified", False):
            self.message = "Access denied: Ambulance driver account is inactive or not verified."
            return False

        return True
