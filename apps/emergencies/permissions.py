"""
Role-based permission classes for SERTOS Emergencies application.

Enforces:
1. Incident Creation: Only verified, active ambulance drivers (AMBULANCE_DRIVER).
2. Incident Listing / Retrieval: Scoped to the reporting driver, or system administrators.
3. Incident Status Update (PATCH): Only the verified reporting ambulance driver.
4. Hospital Dashboard: Strictly verified, active HOSPITAL_STAFF personnel (read-only).
5. Police Dashboard: Strictly verified, active POLICE_DISPATCHER personnel (read-only).
6. Ambulance GPS Tracking: Reporting driver for POST; driver, staff, police, admin for GET.
7. Notifications: Authenticated, verified, active users (scoped to own notifications).
8. Strict isolation across roles (403).
9. Unauthenticated requests are rejected with 401.
"""

from rest_framework.permissions import BasePermission
from apps.accounts.models import UserRole


class EmergencyIncidentPermission(BasePermission):
    """
    Permission policy for EmergencyIncident API endpoints:
    - POST: Only verified, active users with role AMBULANCE_DRIVER.
    - PATCH: Only verified, active users with role AMBULANCE_DRIVER for their own incident.
    - GET (List / Detail): Verified AMBULANCE_DRIVER or verified ADMIN.
    - Other operational roles (HOSPITAL_STAFF, POLICE_DISPATCHER) receive 403 Forbidden.
    - Anonymous / unauthenticated users receive 401 Unauthorized.
    - Unverified / inactive users receive 403 Forbidden.
    """

    message = "Access denied: You do not have permission to perform this action."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        if not getattr(user, "is_verified", False) or not user.is_active:
            self.message = "Access denied: Account is not verified or is inactive."
            return False

        user_role = getattr(user, "role", None)

        if request.method == "POST":
            if user_role != UserRole.AMBULANCE_DRIVER:
                self.message = "Access denied: Only verified ambulance drivers can report emergency incidents."
                return False
            return True

        if request.method == "PATCH":
            if user_role != UserRole.AMBULANCE_DRIVER:
                self.message = "Access denied: Only verified ambulance drivers can update emergency incident status."
                return False
            return True

        if request.method in ["GET", "HEAD", "OPTIONS"]:
            if user_role in [UserRole.AMBULANCE_DRIVER, UserRole.ADMIN] or user.is_superuser:
                return True
            self.message = "Access denied: Insufficient permissions to view emergency incidents."
            return False

        return False


class IsHospitalStaffDashboardPermission(BasePermission):
    """
    Permission policy for Hospital Emergency Dashboard endpoints (/api/hospital/incidents/):
    - Strictly restricted to authenticated, verified, active users with HOSPITAL_STAFF role.
    - Strictly read-only: only GET, HEAD, OPTIONS allowed. Mutating methods receive 403.
    - Other roles (ADMIN, AMBULANCE_DRIVER, POLICE_DISPATCHER) receive 403 Forbidden.
    - Unauthenticated requests receive 401 Unauthorized.
    """

    message = "Access denied: Hospital Emergency Staff credentials required."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        if not user.is_active or not getattr(user, "is_verified", False):
            self.message = "Access denied: Account is not verified or is inactive."
            return False

        if request.method not in ["GET", "POST", "PATCH", "HEAD", "OPTIONS"]:
            self.message = "Access denied: Unsupported hospital dashboard operation."
            return False

        if getattr(user, "role", None) != UserRole.HOSPITAL_STAFF:
            self.message = "Access denied: Hospital Emergency Staff credentials required."
            return False

        return True


class HospitalOperationsPermission(BasePermission):
    """Verified hospital staff may read and update their own operational records."""

    message = "Access denied: Hospital Emergency Staff credentials required."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_active and getattr(user, "is_verified", False)):
            self.message = "Access denied: Account is not verified or is inactive."
            return False
        if getattr(user, "role", None) != UserRole.HOSPITAL_STAFF:
            return False
        return request.method in ["GET", "POST", "PATCH", "HEAD", "OPTIONS"]


class IsPoliceDispatcherDashboardPermission(BasePermission):
    """
    Permission policy for Police Traffic Dashboard endpoints (/api/police/incidents/):
    - Strictly restricted to authenticated, verified, active users with POLICE_DISPATCHER role.
    - Strictly read-only: only GET, HEAD, OPTIONS allowed.
    - Other roles (ADMIN, AMBULANCE_DRIVER, HOSPITAL_STAFF) receive 403 Forbidden.
    - Unauthenticated requests receive 401 Unauthorized.
    """

    message = "Access denied: Police Traffic Dispatcher credentials required."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        if not user.is_active or not getattr(user, "is_verified", False):
            self.message = "Access denied: Account is not verified or is inactive."
            return False

        if request.method not in ["GET", "POST", "HEAD", "OPTIONS"]:
            self.message = "Access denied: Unsupported police dashboard operation."
            return False

        if getattr(user, "role", None) != UserRole.POLICE_DISPATCHER:
            self.message = "Access denied: Police Traffic Dispatcher credentials required."
            return False

        return True


class EmergencyIncidentLocationPermission(BasePermission):
    """
    Permission policy for Emergency Location APIs (/api/emergencies/<uuid:pk>/location/):
    - POST: Only authenticated, active, verified users with role AMBULANCE_DRIVER.
    - GET: Authenticated, active, verified users with role AMBULANCE_DRIVER, HOSPITAL_STAFF, POLICE_DISPATCHER, or ADMIN.
    - Other operational roles receive 403 Forbidden.
    - Anonymous / unauthenticated users receive 401 Unauthorized.
    - Unverified / inactive users receive 403 Forbidden.
    """

    message = "Access denied: You do not have permission to access GPS location endpoints."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        if not getattr(user, "is_verified", False) or not user.is_active:
            self.message = "Access denied: Account is not verified or is inactive."
            return False

        user_role = getattr(user, "role", None)

        if request.method == "POST":
            if user_role != UserRole.AMBULANCE_DRIVER:
                self.message = "Access denied: Only verified ambulance drivers may submit GPS location updates."
                return False
            return True

        if request.method in ["GET", "HEAD", "OPTIONS"]:
            if user_role in [
                UserRole.AMBULANCE_DRIVER,
                UserRole.HOSPITAL_STAFF,
                UserRole.POLICE_DISPATCHER,
                UserRole.ADMIN,
            ] or user.is_superuser:
                return True
            self.message = "Access denied: Insufficient permissions to access GPS location data."
            return False

        return False


class IsVerifiedUserPermission(BasePermission):
    """
    Permission policy for Notification endpoints (/api/notifications/):
    - Authenticated users only (anonymous receives 401).
    - User account must be active (user.is_active is True).
    - User account must be verified by an administrator (user.is_verified is True).
    - Unverified or inactive users receive 403 Forbidden.
    """

    message = "Access denied: Account must be active and verified."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        if not user.is_active or not getattr(user, "is_verified", False):
            self.message = "Access denied: Account is not verified or is inactive."
            return False

        return True


class EmergencyIncidentRoutePermission(BasePermission):
    """
    Permission policy for Emergency Route and ETA endpoints (/api/emergencies/<uuid:pk>/route/):
    - Strictly read-only: only GET, HEAD, OPTIONS allowed. Mutating methods receive 403.
    - Authenticated, active, verified users with role AMBULANCE_DRIVER, HOSPITAL_STAFF, POLICE_DISPATCHER, or ADMIN.
    - Other operational roles receive 403 Forbidden.
    - Anonymous / unauthenticated users receive 401 Unauthorized.
    - Unverified / inactive users receive 403 Forbidden.
    """

    message = "Access denied: You do not have permission to access route and ETA data."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        if not getattr(user, "is_verified", False) or not user.is_active:
            self.message = "Access denied: Account is not verified or is inactive."
            return False

        if request.method not in ["GET", "HEAD", "OPTIONS"]:
            self.message = "Access denied: Route endpoint is read-only."
            return False

        user_role = getattr(user, "role", None)
        if user_role in [
            UserRole.AMBULANCE_DRIVER,
            UserRole.HOSPITAL_STAFF,
            UserRole.POLICE_DISPATCHER,
            UserRole.ADMIN,
        ] or getattr(user, "is_superuser", False):
            return True

        self.message = "Access denied: Insufficient permissions to access route and ETA data."
        return False

