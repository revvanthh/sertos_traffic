"""
Role-Based Access Control (RBAC) Permission Classes for SERTOS.

Enforces:
- Verification of live database-backed request.user authentication and is_verified status.
- Strict isolation across operational roles:
  1. IsSystemAdmin (ADMIN)
  2. IsAmbulanceDriver (AMBULANCE_DRIVER)
  3. IsHospitalStaff (HOSPITAL_STAFF)
  4. IsPoliceDispatcher (POLICE_DISPATCHER)
  5. IsVerifiedPersonnel (any verified authenticated user)
"""

from rest_framework.permissions import BasePermission
from .models import UserRole


class IsVerifiedPersonnel(BasePermission):
    """
    Allows access only to authenticated users whose current database verification status is True.
    Evaluates live request.user.is_verified on every request.
    """

    message = "Access denied: Account is not verified."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "is_verified", False)
        )


class IsSystemAdmin(BasePermission):
    """
    Allows access only to verified users with the ADMIN role (or superusers).
    """

    message = "Access denied: System Administrator privileges required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "is_verified", False)
            and (
                getattr(request.user, "role", None) == UserRole.ADMIN
                or request.user.is_superuser
            )
        )


class IsAmbulanceDriver(BasePermission):
    """
    Allows access only to verified users with the AMBULANCE_DRIVER role.
    """

    message = "Access denied: Ambulance Driver credentials required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "is_verified", False)
            and getattr(request.user, "role", None) == UserRole.AMBULANCE_DRIVER
        )


class IsHospitalStaff(BasePermission):
    """
    Allows access only to verified users with the HOSPITAL_STAFF role.
    """

    message = "Access denied: Hospital Emergency Staff credentials required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "is_verified", False)
            and getattr(request.user, "role", None) == UserRole.HOSPITAL_STAFF
        )


class IsPoliceDispatcher(BasePermission):
    """
    Allows access only to verified users with the POLICE_DISPATCHER role.
    """

    message = "Access denied: Police Traffic Dispatcher credentials required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "is_verified", False)
            and getattr(request.user, "role", None) == UserRole.POLICE_DISPATCHER
        )
