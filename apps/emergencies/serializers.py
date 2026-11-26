"""
Serializers for SERTOS Emergencies application.

Implements:
1. PatientSerializer - Patient clinical triage data.
2. EmergencyIncidentCreateSerializer - Validated emergency creation with nested patient.
3. EmergencyIncidentListSerializer - Lightweight summary representation for incident list.
4. EmergencyIncidentDetailSerializer - Full operational and clinical incident representation.
5. EmergencyIncidentStatusUpdateSerializer - Validated status lifecycle transition.
6. HospitalIncidentListSerializer & DetailSerializer - Hospital staff dashboard feeds.
7. PolicePatientSummarySerializer, PoliceIncidentListSerializer & DetailSerializer - Police traffic coordination feeds.
8. AmbulanceLocationCreateSerializer & AmbulanceLocationSerializer - GPS tracking breadcrumbs.
"""

from decimal import Decimal
from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import (
    Ambulance,
    AmbulanceLocation,
    EmergencyEvent,
    EmergencyIncident,
    Gender,
    Hospital,
    HospitalBed,
    HospitalIncidentResponse,
    IncidentSeverity,
    IncidentStatus,
    Notification,
    Patient,
)
from .routes_service import get_cached_route_summary
from .services import create_emergency_incident, record_ambulance_location

User = get_user_model()


class PatientSerializer(serializers.ModelSerializer):
    """
    Serializer for Patient model.
    Handles demographic and triage data with age validation.
    """

    class Meta:
        model = Patient
        fields = [
            "id",
            "name",
            "age",
            "gender",
            "blood_group",
            "medical_notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_age(self, value):
        if value is not None and (value < 0 or value > 150):
            raise serializers.ValidationError("Patient age must be between 0 and 150.")
        return value


class HospitalSummarySerializer(serializers.ModelSerializer):
    """Compact summary of destination hospital facility."""

    class Meta:
        model = Hospital
        fields = [
            "id",
            "name",
            "hospital_code",
            "address",
            "contact_number",
            "latitude",
            "longitude",
            "is_active",
        ]


class HospitalBedSerializer(serializers.ModelSerializer):
    class Meta:
        model = HospitalBed
        fields = ["id", "hospital", "bed_number", "category", "status", "patient_label", "updated_at"]
        read_only_fields = ["id", "hospital", "updated_at"]


class HospitalIncidentResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = HospitalIncidentResponse
        fields = ["id", "incident", "hospital", "decision", "reason", "responded_by", "created_at", "updated_at"]
        read_only_fields = ["id", "incident", "hospital", "responded_by", "created_at", "updated_at"]


class AmbulanceSummarySerializer(serializers.ModelSerializer):
    """Compact summary of dispatched ambulance vehicle."""

    class Meta:
        model = Ambulance
        fields = [
            "id",
            "vehicle_number",
            "vehicle_type",
            "is_available",
            "is_active",
        ]


class ReportingDriverSummarySerializer(serializers.ModelSerializer):
    """Compact summary of authenticated reporting driver."""

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "role",
            "phone_number",
            "badge_or_employee_id",
            "is_verified",
        ]


class EmergencyIncidentCreateSerializer(serializers.Serializer):
    """
    Serializer for creating an emergency incident.
    Accepts destination hospital, triage severity, description, and nested patient details.
    Derives reporting driver strictly from request.user (prevents client spoofing).
    """

    hospital_id = serializers.UUIDField(
        required=False,
        help_text="UUID of the destination hospital.",
    )
    hospital = serializers.UUIDField(
        required=False,
        help_text="UUID alias for hospital_id.",
    )
    severity = serializers.ChoiceField(
        choices=IncidentSeverity.choices,
        default=IncidentSeverity.MEDIUM,
        required=False,
        help_text="Triage priority level (CRITICAL, HIGH, MEDIUM, LOW).",
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="Preliminary incident description and chief complaint.",
    )
    patient = PatientSerializer(
        required=False,
        allow_null=True,
        help_text="Nested patient demographic and triage information.",
    )

    def validate(self, attrs):
        hospital_id = attrs.get("hospital_id") or attrs.get("hospital")
        if not hospital_id:
            raise serializers.ValidationError({"hospital": ["Destination hospital is required."]})
        attrs["hospital_id"] = hospital_id
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        if not request or not request.user:
            raise serializers.ValidationError({"reporting_driver": ["Authentication required."]})

        driver = request.user
        hospital_id = validated_data["hospital_id"]
        severity = validated_data.get("severity", IncidentSeverity.MEDIUM)
        description = validated_data.get("description", "")
        patient_data = validated_data.get("patient")

        return create_emergency_incident(
            driver=driver,
            hospital_id=hospital_id,
            severity=severity,
            description=description,
            patient_data=patient_data,
        )


class EmergencyIncidentListSerializer(serializers.ModelSerializer):
    """
    Lightweight summary serializer for listing emergency incidents.
    Optimized for high-concurrency dispatch feeds.
    """

    hospital_name = serializers.CharField(source="hospital.name", read_only=True, default=None)
    hospital_code = serializers.CharField(source="hospital.hospital_code", read_only=True, default=None)
    ambulance_vehicle_number = serializers.CharField(source="ambulance.vehicle_number", read_only=True, default=None)
    patient_count = serializers.IntegerField(source="patients.count", read_only=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = EmergencyIncident
        fields = [
            "id",
            "incident_number",
            "severity",
            "severity_display",
            "status",
            "status_display",
            "description",
            "hospital_name",
            "hospital_code",
            "ambulance_vehicle_number",
            "patient_count",
            "created_at",
            "updated_at",
        ]


class EmergencyIncidentStatusUpdateSerializer(serializers.Serializer):
    """
    Serializer for PATCH status update of an EmergencyIncident.
    Validates that status is one of the supported IncidentStatus choices.
    """

    status = serializers.ChoiceField(
        choices=IncidentStatus.choices,
        help_text="Target lifecycle status for the emergency response.",
    )


class EmergencyIncidentDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for single emergency incident inspection.
    Includes full vehicle, hospital, reporting driver, and patient triage details.
    """

    reporting_driver = ReportingDriverSummarySerializer(read_only=True)
    ambulance = AmbulanceSummarySerializer(read_only=True)
    hospital = HospitalSummarySerializer(read_only=True)
    patients = PatientSerializer(many=True, read_only=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = EmergencyIncident
        fields = [
            "id",
            "incident_number",
            "reporting_driver",
            "ambulance",
            "hospital",
            "severity",
            "severity_display",
            "status",
            "status_display",
            "description",
            "patients",
            "assigned_at",
            "in_transit_at",
            "arrived_at",
            "closed_at",
            "cancelled_at",
            "created_at",
            "updated_at",
        ]


class HospitalIncidentListSerializer(serializers.ModelSerializer):
    """
    Lightweight incident summary serializer for Hospital Dashboard feeds.
    Includes hospital, ambulance vehicle number, patient count, and lifecycle timestamps.
    """

    hospital_name = serializers.CharField(source="hospital.name", read_only=True)
    hospital_code = serializers.CharField(source="hospital.hospital_code", read_only=True)
    ambulance_vehicle_number = serializers.CharField(source="ambulance.vehicle_number", read_only=True)
    ambulance_vehicle_type = serializers.CharField(source="ambulance.vehicle_type", read_only=True)
    patient_count = serializers.IntegerField(source="patients.count", read_only=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    hospital_decision = serializers.SerializerMethodField()
    police_acknowledged = serializers.SerializerMethodField()

    class Meta:
        model = EmergencyIncident
        fields = [
            "id",
            "incident_number",
            "severity",
            "severity_display",
            "status",
            "status_display",
            "description",
            "hospital_name",
            "hospital_code",
            "ambulance_vehicle_number",
            "ambulance_vehicle_type",
            "patient_count",
            "assigned_at",
            "in_transit_at",
            "arrived_at",
            "closed_at",
            "cancelled_at",
            "created_at",
            "updated_at",
            "hospital_decision",
            "police_acknowledged",
        ]

    def get_hospital_decision(self, obj):
        response = getattr(obj, "hospital_response", None)
        return response.decision if response else None

    def get_police_acknowledged(self, obj):
        return hasattr(obj, "police_acknowledgement")


class HospitalIncidentRouteSummarySerializer(serializers.Serializer):
    """
    Lightweight route summary for Hospital and Police Dashboard incident detail.
    Strictly read from cache; never invokes upstream Google API.
    """

    distance_km = serializers.FloatField(help_text="Driving distance in kilometers.")
    duration_formatted = serializers.CharField(help_text="Human-readable driving duration (e.g. '17 mins').")
    estimated_arrival = serializers.DateTimeField(help_text="Estimated arrival timestamp at the hospital.")
    is_stale = serializers.BooleanField(default=False, help_text="True if route recalculation failed and cached route was retained.")
    last_calculated_at = serializers.DateTimeField(help_text="Timestamp when the route was last computed.")


# Alias for cross-dashboard reuse
IncidentRouteSummarySerializer = HospitalIncidentRouteSummarySerializer


class HospitalIncidentDetailSerializer(serializers.ModelSerializer):
    """
    Detailed incident serializer for Hospital Emergency Staff inspection.
    Includes full patient triage information, medical notes, driver, vehicle, hospital, and cached route summary.
    """

    reporting_driver = ReportingDriverSummarySerializer(read_only=True)
    ambulance = AmbulanceSummarySerializer(read_only=True)
    hospital = HospitalSummarySerializer(read_only=True)
    patients = PatientSerializer(many=True, read_only=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    route_summary = serializers.SerializerMethodField(help_text="Cached route metrics or null if uncomputed.")

    class Meta:
        model = EmergencyIncident
        fields = [
            "id",
            "incident_number",
            "reporting_driver",
            "ambulance",
            "hospital",
            "severity",
            "severity_display",
            "status",
            "status_display",
            "description",
            "patients",
            "route_summary",
            "assigned_at",
            "in_transit_at",
            "arrived_at",
            "closed_at",
            "cancelled_at",
            "created_at",
            "updated_at",
        ]

    def get_route_summary(self, obj):
        """
        Retrieves route summary strictly from cache.
        Guaranteed NEVER to invoke Google API or trigger recalculation.
        Returns None (null in JSON) if no cached route exists.
        """
        summary = get_cached_route_summary(obj.id)
        if not summary:
            return None
        return HospitalIncidentRouteSummarySerializer(summary).data


class PolicePatientSummarySerializer(serializers.ModelSerializer):
    """
    Sanitized patient serializer for Police Traffic Dispatcher inspection.
    Strictly EXCLUDES confidential patient medical notes for privacy and regulatory compliance.
    """

    class Meta:
        model = Patient
        fields = [
            "id",
            "name",
            "age",
            "gender",
            "blood_group",
            "created_at",
            "updated_at",
        ]


class PoliceIncidentListSerializer(serializers.ModelSerializer):
    """
    Incident list serializer for Police Traffic Coordination Dashboard.
    Provides city-wide emergency visibility, destination hospital coordinates, ambulance, and patient count.
    """

    hospital = HospitalSummarySerializer(read_only=True)
    ambulance = AmbulanceSummarySerializer(read_only=True)
    patient_count = serializers.IntegerField(source="patients.count", read_only=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    hospital_decision = serializers.SerializerMethodField()
    police_acknowledged = serializers.SerializerMethodField()

    class Meta:
        model = EmergencyIncident
        fields = [
            "id",
            "incident_number",
            "severity",
            "severity_display",
            "status",
            "status_display",
            "description",
            "hospital",
            "ambulance",
            "patient_count",
            "assigned_at",
            "in_transit_at",
            "arrived_at",
            "closed_at",
            "cancelled_at",
            "created_at",
            "updated_at",
            "hospital_decision",
            "police_acknowledged",
        ]

    def get_hospital_decision(self, obj):
        response = getattr(obj, "hospital_response", None)
        return response.decision if response else None

    def get_police_acknowledged(self, obj):
        return hasattr(obj, "police_acknowledgement")


class PoliceIncidentDetailSerializer(serializers.ModelSerializer):
    """
    Detailed incident serializer for Police Traffic Dispatchers.
    Excludes private patient medical notes while providing full routing coordinates and cached route summary.
    """

    reporting_driver = ReportingDriverSummarySerializer(read_only=True)
    ambulance = AmbulanceSummarySerializer(read_only=True)
    hospital = HospitalSummarySerializer(read_only=True)
    patients = PolicePatientSummarySerializer(many=True, read_only=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    route_summary = serializers.SerializerMethodField(help_text="Cached route metrics or null if uncomputed.")

    class Meta:
        model = EmergencyIncident
        fields = [
            "id",
            "incident_number",
            "reporting_driver",
            "ambulance",
            "hospital",
            "severity",
            "severity_display",
            "status",
            "status_display",
            "description",
            "patients",
            "route_summary",
            "assigned_at",
            "in_transit_at",
            "arrived_at",
            "closed_at",
            "cancelled_at",
            "created_at",
            "updated_at",
        ]

    def get_route_summary(self, obj):
        """
        Retrieves route summary strictly from cache.
        Guaranteed NEVER to invoke Google API or trigger recalculation.
        Returns None (null in JSON) if no cached route exists.
        """
        summary = get_cached_route_summary(obj.id)
        if not summary:
            return None
        return IncidentRouteSummarySerializer(summary).data


class AmbulanceLocationCreateSerializer(serializers.Serializer):
    """
    Serializer for ingesting ambulance GPS location updates via POST /api/emergencies/<uuid:pk>/location/.
    Validates latitude, longitude, and optional accuracy/recorded timestamp.
    Derives ambulance and incident strictly from context.
    """

    latitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=True,
        help_text="GPS latitude coordinate in decimal degrees (-90.0 to 90.0).",
    )
    longitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=True,
        help_text="GPS longitude coordinate in decimal degrees (-180.0 to 180.0).",
    )
    accuracy = serializers.FloatField(
        required=False,
        allow_null=True,
        default=None,
        help_text="Estimated horizontal GPS accuracy radius in metres.",
    )
    recorded_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
        default=None,
        help_text="Client device recorded timestamp (ISO 8601).",
    )

    def validate_latitude(self, value):
        if value < Decimal("-90") or value > Decimal("90"):
            raise serializers.ValidationError("Latitude must be between -90 and 90 degrees.")
        return value

    def validate_longitude(self, value):
        if value < Decimal("-180") or value > Decimal("180"):
            raise serializers.ValidationError("Longitude must be between -180 and 180 degrees.")
        return value

    def validate_accuracy(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Accuracy radius cannot be negative.")
        return value

    def create(self, validated_data):
        incident = self.context.get("incident")
        request = self.context.get("request")
        if not incident or not request:
            raise serializers.ValidationError({"detail": "Incident context required."})

        return record_ambulance_location(
            incident=incident,
            latitude=validated_data["latitude"],
            longitude=validated_data["longitude"],
            accuracy=validated_data.get("accuracy"),
            recorded_at=validated_data.get("recorded_at"),
            user=request.user,
        )


class AmbulanceLocationSerializer(serializers.ModelSerializer):
    """
    Serializer for representing ambulance GPS location breadcrumbs.
    Excludes sensitive patient medical notes while providing full coordinate precision.
    """

    incident_id = serializers.UUIDField(source="incident.id", read_only=True)
    incident_number = serializers.CharField(source="incident.incident_number", read_only=True)
    ambulance_id = serializers.UUIDField(source="ambulance.id", read_only=True)
    ambulance_vehicle_number = serializers.CharField(source="ambulance.vehicle_number", read_only=True)

    class Meta:
        model = AmbulanceLocation
        fields = [
            "id",
            "incident_id",
            "incident_number",
            "ambulance_id",
            "ambulance_vehicle_number",
            "latitude",
            "longitude",
            "accuracy",
            "recorded_at",
            "server_received_at",
        ]
        read_only_fields = fields


class EmergencyEventSerializer(serializers.ModelSerializer):
    """
    Serializer for EmergencyEvent audit records.
    Provides structured event data excluding sensitive patient medical notes.
    """

    incident_id = serializers.UUIDField(source="incident.id", read_only=True)
    incident_number = serializers.CharField(source="incident.incident_number", read_only=True)
    event_type_display = serializers.CharField(source="get_event_type_display", read_only=True)

    class Meta:
        model = EmergencyEvent
        fields = [
            "id",
            "incident_id",
            "incident_number",
            "event_type",
            "event_type_display",
            "description",
            "payload",
            "created_at",
        ]
        read_only_fields = fields


class NotificationSerializer(serializers.ModelSerializer):
    """
    Serializer for Notification delivery to operational actors.
    Excludes sensitive patient medical notes.
    """

    incident_id = serializers.UUIDField(source="incident.id", read_only=True)
    incident_number = serializers.CharField(source="incident.incident_number", read_only=True)
    event = EmergencyEventSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "incident_id",
            "incident_number",
            "event",
            "title",
            "message",
            "is_read",
            "created_at",
            "read_at",
        ]
        read_only_fields = fields


class RouteCoordinateSerializer(serializers.Serializer):
    latitude = serializers.FloatField(help_text="Latitude coordinate in decimal degrees.")
    longitude = serializers.FloatField(help_text="Longitude coordinate in decimal degrees.")


class RouteDestinationSerializer(serializers.Serializer):
    latitude = serializers.FloatField(help_text="Destination latitude coordinate in decimal degrees.")
    longitude = serializers.FloatField(help_text="Destination longitude coordinate in decimal degrees.")
    hospital_name = serializers.CharField(help_text="Name of the destination hospital facility.")


class EmergencyIncidentRouteSerializer(serializers.Serializer):
    """
    Serializer for the road route and ETA response between ambulance and hospital.
    """

    incident_id = serializers.UUIDField(help_text="UUID of the emergency incident.")
    incident_number = serializers.CharField(help_text="Human-readable incident code.")
    origin = RouteCoordinateSerializer(help_text="Current ambulance GPS coordinates.")
    destination = RouteDestinationSerializer(help_text="Destination hospital coordinates and facility name.")
    distance_meters = serializers.IntegerField(help_text="Total driving distance in meters.")
    distance_km = serializers.FloatField(help_text="Total driving distance in kilometers.")
    duration_seconds = serializers.IntegerField(help_text="Total estimated driving time in seconds.")
    duration_formatted = serializers.CharField(help_text="Human-readable driving duration (e.g. '17 mins').")
    estimated_arrival = serializers.DateTimeField(help_text="Estimated arrival timestamp at the hospital.")
    polyline = serializers.CharField(help_text="Google encoded polyline representing the navigation path.")
    is_stale = serializers.BooleanField(default=False, help_text="True if route recalculation failed and cached route was retained.")
    last_calculated_at = serializers.DateTimeField(help_text="Timestamp when the route was last computed.")


