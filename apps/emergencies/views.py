"""
API views for SERTOS Emergencies application.

Implements:
1. EmergencyIncidentListCreateView:
   - POST /api/emergencies/ : Driver-reported emergency incident creation with nested patient.
   - GET  /api/emergencies/ : Scoped incident listing (driver gets own, admin gets all).
2. EmergencyIncidentDetailView:
   - GET  /api/emergencies/<uuid:pk>/ : Scoped incident details inspection.
3. EmergencyIncidentStatusUpdateView:
   - PATCH /api/emergencies/<uuid:pk>/status/ : Status lifecycle transition for reporting driver.
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView

from apps.accounts.models import UserRole
from apps.accounts.views import standard_response
from .models import (
    EmergencyIncident,
    Hospital,
    HospitalBed,
    HospitalIncidentResponse,
    HospitalStaff,
    IncidentStatus,
    Notification,
    PoliceIncidentAcknowledgement,
)
from .permissions import (
    EmergencyIncidentLocationPermission,
    EmergencyIncidentPermission,
    EmergencyIncidentRoutePermission,
    IsHospitalStaffDashboardPermission,
    HospitalOperationsPermission,
    IsPoliceDispatcherDashboardPermission,
    IsVerifiedUserPermission,
)
from .routes_service import RouteServiceError, get_incident_route_and_eta
from .serializers import (
    AmbulanceLocationCreateSerializer,
    AmbulanceLocationSerializer,
    EmergencyIncidentCreateSerializer,
    EmergencyIncidentDetailSerializer,
    EmergencyIncidentListSerializer,
    EmergencyIncidentRouteSerializer,
    EmergencyIncidentStatusUpdateSerializer,
    HospitalIncidentDetailSerializer,
    HospitalIncidentListSerializer,
    NotificationSerializer,
    PoliceIncidentDetailSerializer,
    HospitalSummarySerializer,
    HospitalBedSerializer,
    HospitalIncidentResponseSerializer,
    PoliceIncidentListSerializer,
)
from .services import update_emergency_status


class HospitalListView(APIView):
    """GET /api/hospitals/ - Lists active hospitals available for dispatch."""

    permission_classes = [IsVerifiedUserPermission]

    def get(self, request):
        hospitals = Hospital.objects.filter(is_active=True).order_by("name")
        return standard_response(
            data=HospitalSummarySerializer(hospitals, many=True).data,
            message="Active hospitals retrieved successfully.",
            status_code=status.HTTP_200_OK,
        )


class HospitalBedListView(APIView):
    permission_classes = [HospitalOperationsPermission]

    def get_hospital(self, request):
        return Hospital.objects.filter(
            staff_affiliations__user=request.user,
            staff_affiliations__is_active=True,
            is_active=True,
        ).first()

    def get(self, request):
        hospital = self.get_hospital(request)
        if not hospital:
            return standard_response(data=[], message="No active hospital assignment.", status_code=status.HTTP_200_OK)
        return standard_response(
            data=HospitalBedSerializer(HospitalBed.objects.filter(hospital=hospital), many=True).data,
            message="Hospital beds retrieved successfully.",
            status_code=status.HTTP_200_OK,
        )

    def post(self, request):
        hospital = self.get_hospital(request)
        if not hospital:
            return standard_response(
                success=False,
                errors={"hospital": ["No active hospital assignment was found."]},
                message="Cannot add a bed without an active hospital assignment.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        bed_number = str(request.data.get("bed_number", "")).strip()
        category = str(request.data.get("category", "GENERAL")).upper()
        patient_label = str(request.data.get("patient_label", "")).strip()
        status_value = str(request.data.get("status", "AVAILABLE")).upper()
        if not bed_number:
            return standard_response(
                success=False,
                errors={"bed_number": ["Bed number is required."]},
                message="Bed creation failed.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if category not in ("GENERAL", "ICU", "EMERGENCY"):
            category = "GENERAL"
        if status_value not in ("AVAILABLE", "OCCUPIED", "RESERVED"):
            status_value = "AVAILABLE"
        if HospitalBed.objects.filter(hospital=hospital, bed_number=bed_number).exists():
            return standard_response(
                success=False,
                errors={"bed_number": ["A bed with this number already exists at the hospital."]},
                message="Duplicate bed number.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        bed = HospitalBed.objects.create(
            hospital=hospital,
            bed_number=bed_number,
            category=category,
            status=status_value,
            patient_label=patient_label,
        )
        return standard_response(
            data=HospitalBedSerializer(bed).data,
            message="Hospital bed added successfully.",
            status_code=status.HTTP_201_CREATED,
        )


class HospitalBedDetailView(HospitalBedListView):
    def patch(self, request, pk):
        hospital = self.get_hospital(request)
        bed = get_object_or_404(HospitalBed, pk=pk, hospital=hospital)
        serializer = HospitalBedSerializer(bed, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return standard_response(
            data=serializer.data,
            message="Hospital bed updated successfully.",
            status_code=status.HTTP_200_OK,
        )


class HospitalIncidentDecisionView(APIView):
    permission_classes = [HospitalOperationsPermission]

    def patch(self, request, pk):
        incident = get_object_or_404(
            EmergencyIncident.objects.select_related("hospital"),
            pk=pk,
            hospital__staff_affiliations__user=request.user,
            hospital__staff_affiliations__is_active=True,
        )
        decision = request.data.get("decision")
        if decision not in HospitalIncidentResponse.Decision.values:
            return standard_response(
                success=False,
                data={},
                errors={"decision": ["Decision must be ACCEPTED or REJECTED."]},
                message="Invalid hospital decision.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if decision == HospitalIncidentResponse.Decision.REJECTED and not str(request.data.get("reason", "")).strip():
            return standard_response(
                success=False,
                data={},
                errors={"reason": ["A rejection reason is required."]},
                message="Rejection reason is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        response, _ = HospitalIncidentResponse.objects.update_or_create(
            incident=incident,
            defaults={
                "hospital": incident.hospital,
                "responded_by": request.user,
                "decision": decision,
                "reason": str(request.data.get("reason", "")).strip(),
            },
        )
        if decision == "ACCEPTED":
            available_bed = HospitalBed.objects.filter(
                hospital=incident.hospital,
                status=HospitalBed.Status.AVAILABLE,
            ).first()
            if not available_bed:
                response.delete()
                return standard_response(
                    success=False,
                    errors={"bed": ["No available bed is registered for this hospital."]},
                    message="Accept the case only after reserving an available bed.",
                    status_code=status.HTTP_409_CONFLICT,
                )
            available_bed.status = HospitalBed.Status.RESERVED
            available_bed.patient_label = incident.patients.first().name if incident.patients.exists() else "Incoming emergency patient"
            available_bed.save(update_fields=["status", "patient_label", "updated_at"])
            if incident.status == IncidentStatus.REPORTED:
                incident.status = IncidentStatus.ASSIGNED
                incident.save(update_fields=["status", "assigned_at", "updated_at"])
        else:
            HospitalBed.objects.filter(
                hospital=incident.hospital,
                patient_label__icontains=incident.incident_number,
            ).update(status=HospitalBed.Status.AVAILABLE, patient_label="")
        return standard_response(
            data=HospitalIncidentResponseSerializer(response).data,
            message="Hospital incident decision saved successfully.",
            status_code=status.HTTP_200_OK,
        )


class EmergencyIncidentListCreateView(APIView):
    """
    POST /api/emergencies/
      - Creates a new emergency incident and nested patient.
      - Restricted to verified, active ambulance drivers.

    GET /api/emergencies/
      - Lists emergency incidents.
      - Ambulance drivers see only their own reported incidents.
      - System administrators see all incidents.
      - Other roles (hospital, police) are denied access (403).
    """

    permission_classes = [EmergencyIncidentPermission]

    def get_queryset(self):
        user = self.request.user
        base_qs = EmergencyIncident.objects.select_related(
            "hospital", "ambulance", "reporting_driver"
        ).prefetch_related("patients")

        if getattr(user, "role", None) == UserRole.ADMIN or user.is_superuser:
            return base_qs.all()

        if getattr(user, "role", None) == UserRole.AMBULANCE_DRIVER:
            return base_qs.filter(reporting_driver=user)

        return base_qs.none()

    def post(self, request):
        serializer = EmergencyIncidentCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        incident = serializer.save()

        detail_serializer = EmergencyIncidentDetailSerializer(incident)
        return standard_response(
            data=detail_serializer.data,
            message="Emergency incident reported successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def get(self, request):
        incidents = self.get_queryset()
        serializer = EmergencyIncidentListSerializer(incidents, many=True)
        return standard_response(
            data=serializer.data,
            message="Emergency incidents retrieved successfully.",
            status_code=status.HTTP_200_OK,
        )


class EmergencyIncidentDetailView(APIView):
    """
    GET /api/emergencies/<uuid:pk>/
      - Retrieves full operational details of an emergency incident.
      - Ambulance drivers can only retrieve their own reported incidents (404 for others).
      - System administrators can retrieve any incident.
      - Other roles are denied access (403).
    """

    permission_classes = [EmergencyIncidentPermission]

    def get_queryset(self):
        user = self.request.user
        base_qs = EmergencyIncident.objects.select_related(
            "hospital", "ambulance", "reporting_driver"
        ).prefetch_related("patients")

        if getattr(user, "role", None) == UserRole.ADMIN or user.is_superuser:
            return base_qs.all()

        if getattr(user, "role", None) == UserRole.AMBULANCE_DRIVER:
            return base_qs.filter(reporting_driver=user)

        return base_qs.none()

    def get(self, request, pk):
        incident = get_object_or_404(self.get_queryset(), pk=pk)
        self.check_object_permissions(request, incident)
        serializer = EmergencyIncidentDetailSerializer(incident)
        return standard_response(
            data=serializer.data,
            message="Emergency incident retrieved successfully.",
            status_code=status.HTTP_200_OK,
        )


class EmergencyIncidentStatusUpdateView(APIView):
    """
    PATCH /api/emergencies/<uuid:pk>/status/
      - Updates operational lifecycle status of an emergency incident.
      - Restricted strictly to the reporting ambulance driver.
      - Admin users cannot transition status in this task (403).
      - Hospital staff and police dispatchers cannot transition status (403).
      - Other drivers querying this incident receive 404 (scoped queryset).
      - Invalid transitions or terminal-state modifications return HTTP 400.
    """

    permission_classes = [EmergencyIncidentPermission]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "role", None) == UserRole.AMBULANCE_DRIVER:
            return EmergencyIncident.objects.filter(reporting_driver=user)
        return EmergencyIncident.objects.none()

    def patch(self, request, pk):
        incident = get_object_or_404(self.get_queryset(), pk=pk)
        self.check_object_permissions(request, incident)

        serializer = EmergencyIncidentStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]

        updated_incident = update_emergency_status(
            incident=incident,
            new_status=new_status,
            user=request.user,
        )

        detail_serializer = EmergencyIncidentDetailSerializer(updated_incident)
        return standard_response(
            data=detail_serializer.data,
            message="Emergency incident status updated successfully.",
            status_code=status.HTTP_200_OK,
        )


class HospitalIncidentListView(APIView):
    """
    GET /api/hospital/incidents/
      - Lists emergency incidents assigned strictly to the authenticated hospital staff's associated hospital(s).
      - Supports optional query parameter filters: ?status=... and ?severity=...
      - Restricted to verified, active HOSPITAL_STAFF personnel (403 for other roles).
    """

    permission_classes = [IsHospitalStaffDashboardPermission]

    def get_queryset(self):
        user = self.request.user
        hospital_ids = HospitalStaff.objects.filter(
            user=user,
            is_active=True,
            hospital__is_active=True,
        ).values_list("hospital_id", flat=True)

        qs = EmergencyIncident.objects.filter(hospital_id__in=hospital_ids)
        qs = qs.select_related("hospital", "ambulance", "reporting_driver").prefetch_related("patients")

        status_param = self.request.query_params.get("status")
        severity_param = self.request.query_params.get("severity")

        if status_param:
            qs = qs.filter(status=status_param.upper())
        if severity_param:
            qs = qs.filter(severity=severity_param.upper())

        return qs.order_by("-created_at")

    def get(self, request):
        incidents = self.get_queryset()
        serializer = HospitalIncidentListSerializer(incidents, many=True)
        return standard_response(
            data=serializer.data,
            message="Hospital emergency incidents retrieved successfully.",
            status_code=status.HTTP_200_OK,
        )

    def post(self, request):
        return standard_response(
            success=False,
            errors={"detail": ["Hospital dashboard incident listing is read-only."]},
            message="Hospital dashboard incident listing is read-only.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class HospitalIncidentDetailView(APIView):
    """
    GET /api/hospital/incidents/<uuid:pk>/
      - Retrieves full operational details of an incident assigned to the staff member's associated hospital.
      - Returns nested patient clinical triage data including medical notes.
      - Returns 404 Not Found if incident belongs to another hospital or does not exist.
      - Restricted to verified, active HOSPITAL_STAFF personnel.
    """

    permission_classes = [IsHospitalStaffDashboardPermission]

    def get_queryset(self):
        user = self.request.user
        hospital_ids = HospitalStaff.objects.filter(
            user=user,
            is_active=True,
            hospital__is_active=True,
        ).values_list("hospital_id", flat=True)

        qs = EmergencyIncident.objects.filter(hospital_id__in=hospital_ids)
        return qs.select_related("hospital", "ambulance", "reporting_driver").prefetch_related("patients")

    def get(self, request, pk):
        incident = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = HospitalIncidentDetailSerializer(incident)
        return standard_response(
            data=serializer.data,
            message="Hospital emergency incident retrieved successfully.",
            status_code=status.HTTP_200_OK,
        )

    def patch(self, request, pk):
        return standard_response(
            success=False,
            errors={"detail": ["Hospital dashboard incident detail is read-only."]},
            message="Hospital dashboard incident detail is read-only.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class PoliceIncidentListView(APIView):
    """
    GET /api/police/incidents/
      - City-wide listing of emergency incidents across all hospitals for traffic clearance and dispatch coordination.
      - Supports optional query parameter filters: ?status=... and ?severity=...
      - Restricted to verified, active POLICE_DISPATCHER personnel (403 for other roles).
    """

    permission_classes = [IsPoliceDispatcherDashboardPermission]

    def get_queryset(self):
        qs = EmergencyIncident.objects.all()
        qs = qs.select_related("hospital", "ambulance", "reporting_driver").prefetch_related("patients")

        status_param = self.request.query_params.get("status")
        severity_param = self.request.query_params.get("severity")

        if status_param:
            qs = qs.filter(status=status_param.upper())
        if severity_param:
            qs = qs.filter(severity=severity_param.upper())

        return qs.order_by("-created_at")

    def get(self, request):
        incidents = self.get_queryset()
        serializer = PoliceIncidentListSerializer(incidents, many=True)
        return standard_response(
            data=serializer.data,
            message="Police emergency incidents retrieved successfully.",
            status_code=status.HTTP_200_OK,
        )

    def post(self, request):
        return standard_response(
            success=False,
            errors={"detail": ["Police dashboard incident listing is read-only."]},
            message="Police dashboard incident listing is read-only.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class PoliceIncidentDetailView(APIView):
    """
    GET /api/police/incidents/<uuid:pk>/
      - Retrieves operational routing and dispatch details for an emergency incident across any hospital.
      - Includes hospital GPS coordinates, ambulance details, and patient count.
      - Strictly excludes confidential patient medical notes.
      - Restricted to verified, active POLICE_DISPATCHER personnel.
    """

    permission_classes = [IsPoliceDispatcherDashboardPermission]

    def get_queryset(self):
        return EmergencyIncident.objects.select_related(
            "hospital", "ambulance", "reporting_driver"
        ).prefetch_related("patients")

    def get(self, request, pk):
        incident = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = PoliceIncidentDetailSerializer(incident)
        return standard_response(
            data=serializer.data,
            message="Police emergency incident retrieved successfully.",
            status_code=status.HTTP_200_OK,
        )

    def patch(self, request, pk):
        return standard_response(
            success=False,
            errors={"detail": ["Police dashboard incident detail is read-only."]},
            message="Police dashboard incident detail is read-only.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class PoliceIncidentAcknowledgementView(APIView):
    permission_classes = [IsPoliceDispatcherDashboardPermission]

    def post(self, request, pk):
        incident = get_object_or_404(EmergencyIncident, pk=pk)
        acknowledgement, _ = PoliceIncidentAcknowledgement.objects.update_or_create(
            incident=incident,
            defaults={"acknowledged_by": request.user},
        )
        if incident.status == IncidentStatus.REPORTED:
            incident.status = IncidentStatus.ASSIGNED
            incident.save(update_fields=["status", "assigned_at", "updated_at"])
        return standard_response(
            data={
                "incident_id": str(incident.id),
                "acknowledged": True,
                "acknowledged_at": acknowledgement.acknowledged_at.isoformat(),
            },
            message="Police acknowledgement recorded successfully.",
            status_code=status.HTTP_200_OK,
        )


def get_scoped_incident(user, pk):
    """
    Helper function to scope incident retrieval based on user role:
    - AMBULANCE_DRIVER: only own reported incidents.
    - HOSPITAL_STAFF: only incidents directed to their associated active hospital(s).
    - POLICE_DISPATCHER: all incidents city-wide.
    - ADMIN / superuser: all incidents.
    - Out of scope or non-existent: raises Http404.
    """
    user_role = getattr(user, "role", None)

    if user_role == UserRole.ADMIN or getattr(user, "is_superuser", False):
        qs = EmergencyIncident.objects.all()
    elif user_role == UserRole.AMBULANCE_DRIVER:
        qs = EmergencyIncident.objects.filter(
            Q(reporting_driver=user) | Q(ambulance__assigned_driver=user)
        ).distinct()
    elif user_role == UserRole.HOSPITAL_STAFF:
        hospital_ids = HospitalStaff.objects.filter(
            user=user,
            is_active=True,
            hospital__is_active=True,
        ).values_list("hospital_id", flat=True)
        qs = EmergencyIncident.objects.filter(hospital_id__in=hospital_ids)
    elif user_role == UserRole.POLICE_DISPATCHER:
        qs = EmergencyIncident.objects.all()
    else:
        qs = EmergencyIncident.objects.none()

    qs = qs.select_related("ambulance", "hospital", "reporting_driver")
    return get_object_or_404(qs, pk=pk)


class EmergencyIncidentLocationView(APIView):
    """
    POST /api/emergencies/<uuid:pk>/location/
      - Ingests high-frequency GPS coordinate ping for an active emergency incident.
      - Restricted strictly to the reporting ambulance driver.
      - Incident must be active (not CLOSED or CANCELLED).

    GET /api/emergencies/<uuid:pk>/location/
      - Retrieves the latest GPS coordinate ping for an emergency incident.
      - Accessible by reporting driver, associated hospital staff, police, and admin.
      - Out-of-scope incidents return 404 Not Found.
    """

    permission_classes = [EmergencyIncidentLocationPermission]

    def post(self, request, pk):
        incident = get_scoped_incident(request.user, pk)

        serializer = AmbulanceLocationCreateSerializer(
            data=request.data,
            context={"request": request, "incident": incident},
        )
        serializer.is_valid(raise_exception=True)
        location = serializer.save()

        detail_serializer = AmbulanceLocationSerializer(location)
        return standard_response(
            data=detail_serializer.data,
            message="Ambulance GPS location updated successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def get(self, request, pk):
        incident = get_scoped_incident(request.user, pk)
        latest_location = incident.locations.order_by("-server_received_at", "-id").first()

        if not latest_location:
            return standard_response(
                data=None,
                message="No GPS location recorded for this incident yet.",
                status_code=status.HTTP_200_OK,
            )

        serializer = AmbulanceLocationSerializer(latest_location)
        return standard_response(
            data=serializer.data,
            message="Latest ambulance GPS location retrieved successfully.",
            status_code=status.HTTP_200_OK,
        )


class EmergencyIncidentLocationHistoryView(APIView):
    """
    GET /api/emergencies/<uuid:pk>/locations/
      - Retrieves ordered historical GPS breadcrumbs for an emergency incident.
      - Supports optional ?limit= query parameter (default 50, maximum 200).
      - Accessible by reporting driver, associated hospital staff, police, and admin.
      - Out-of-scope incidents return 404 Not Found.
    """

    permission_classes = [EmergencyIncidentLocationPermission]

    def get(self, request, pk):
        incident = get_scoped_incident(request.user, pk)

        try:
            limit = int(request.query_params.get("limit", 50))
            limit = max(1, min(limit, 200))
        except (ValueError, TypeError):
            limit = 50

        locations = incident.locations.order_by("-server_received_at", "-id")[:limit]
        serializer = AmbulanceLocationSerializer(locations, many=True)
        return standard_response(
            data=serializer.data,
            message="Ambulance location history retrieved successfully.",
            status_code=status.HTTP_200_OK,
        )


class EmergencyIncidentRouteView(APIView):
    """
    GET /api/emergencies/<uuid:pk>/route/
      - Computes real-time road route, distance, duration, ETA, and polyline
        between the latest ambulance GPS location and the destination hospital.
      - Access restricted to verified reporting/assigned driver, destination hospital staff,
        police dispatchers, and system administrators.
      - Out-of-scope incidents return 404 Not Found.
    """

    permission_classes = [EmergencyIncidentRoutePermission]

    def get(self, request, pk):
        incident = get_scoped_incident(request.user, pk)
        force_recalculate = request.query_params.get("force", "").lower() in ("true", "1")
        try:
            route_data = get_incident_route_and_eta(incident, force_recalculate=force_recalculate)
        except RouteServiceError as exc:
            return standard_response(
                success=False,
                data={},
                errors={"detail": [exc.message]},
                message=exc.message,
                status_code=exc.status_code,
            )

        serializer = EmergencyIncidentRouteSerializer(route_data)
        return standard_response(
            data=serializer.data,
            message="Incident route and ETA computed successfully.",
            status_code=status.HTTP_200_OK,
        )



class NotificationPagination(PageNumberPagination):
    """
    Standard pagination for notification list endpoints.
    Default page size is 20, configurable up to 100 via ?page_size=.
    """
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class NotificationListView(APIView):
    """
    GET /api/notifications/
      - Lists in-app notifications for the authenticated, verified user.
      - Strictly isolated to the recipient's own notifications.
      - Supports optional ?is_read=true/false filtering.
      - Uses pagination and returns standard SERTOS response envelope.
      - Strictly excludes confidential patient medical notes.
    """

    permission_classes = [IsVerifiedUserPermission]

    def get(self, request):
        queryset = (
            Notification.objects.filter(recipient=request.user)
            .select_related("incident", "event")
            .order_by("-created_at")
        )

        is_read_param = request.query_params.get("is_read")
        if is_read_param is not None:
            if is_read_param.lower() in ["true", "1"]:
                queryset = queryset.filter(is_read=True)
            elif is_read_param.lower() in ["false", "0"]:
                queryset = queryset.filter(is_read=False)

        paginator = NotificationPagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = NotificationSerializer(page, many=True)
            return standard_response(
                data={
                    "count": paginator.page.paginator.count,
                    "next": paginator.get_next_link(),
                    "previous": paginator.get_previous_link(),
                    "results": serializer.data,
                },
                message="Notifications retrieved successfully.",
                status_code=status.HTTP_200_OK,
            )

        serializer = NotificationSerializer(queryset, many=True)
        return standard_response(
            data={
                "count": queryset.count(),
                "next": None,
                "previous": None,
                "results": serializer.data,
            },
            message="Notifications retrieved successfully.",
            status_code=status.HTTP_200_OK,
        )


class NotificationDetailView(APIView):
    """
    GET /api/notifications/<uuid:pk>/
      - Retrieves full operational details of a single notification.
      - Validates that the notification belongs to the authenticated user (404 otherwise).
      - Strictly excludes confidential patient medical notes.
    """

    permission_classes = [IsVerifiedUserPermission]

    def get(self, request, pk):
        notification = get_object_or_404(
            Notification.objects.select_related("incident", "event"),
            pk=pk,
            recipient=request.user,
        )
        serializer = NotificationSerializer(notification)
        return standard_response(
            data=serializer.data,
            message="Notification retrieved successfully.",
            status_code=status.HTTP_200_OK,
        )


class NotificationMarkReadView(APIView):
    """
    PATCH /api/notifications/<uuid:pk>/read/
      - Marks a single notification as read for the authenticated recipient.
      - Enforces recipient ownership validation before update (404 otherwise).
      - Returns updated notification in standard SERTOS response envelope.
    """

    permission_classes = [IsVerifiedUserPermission]

    def patch(self, request, pk):
        notification = get_object_or_404(
            Notification.objects.select_related("incident", "event"),
            pk=pk,
            recipient=request.user,
        )
        notification.mark_as_read()
        serializer = NotificationSerializer(notification)
        return standard_response(
            data=serializer.data,
            message="Notification marked as read successfully.",
            status_code=status.HTTP_200_OK,
        )


class NotificationMarkReadAllView(APIView):
    """
    PATCH /api/notifications/read-all/
      - Marks all unread notifications for the authenticated recipient as read.
      - Sets read_at timestamp to current server UTC time.
      - Returns count of updated records in standard SERTOS response envelope.
    """

    permission_classes = [IsVerifiedUserPermission]

    def patch(self, request):
        now = timezone.now()
        updated_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).update(is_read=True, read_at=now)

        return standard_response(
            data={"updated_count": updated_count},
            message=f"Marked {updated_count} notification(s) as read.",
            status_code=status.HTTP_200_OK,
        )



