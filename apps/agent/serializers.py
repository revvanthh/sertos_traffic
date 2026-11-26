"""
Serializers for SERTOS AI Emergency Agent endpoints (Phase 8.1.3).
"""

from rest_framework import serializers
from apps.emergencies.models import IncidentSeverity
from .models import SessionStatus, VoiceAgentSession


class VoiceTurnInputSerializer(serializers.Serializer):
    """Input serializer for a driver voice/transcribed conversation turn."""

    message = serializers.CharField(
        min_length=1,
        max_length=2000,
        trim_whitespace=True,
        error_messages={
            "blank": "Conversation turn message cannot be empty or blank.",
            "required": "A 'message' field is required for each conversation turn.",
            "max_length": "Message length exceeds the 2000-character safety limit.",
        },
    )


class VoiceTurnResponseSerializer(serializers.Serializer):
    """Standardized response contract for Voice Agent interactions."""

    session_id = serializers.UUIDField()
    assistant_message = serializers.CharField()
    extracted_emergency_data = serializers.DictField()
    missing_information = serializers.ListField(child=serializers.CharField())
    session_status = serializers.ChoiceField(choices=SessionStatus.choices)
    needs_confirmation = serializers.BooleanField()
    error = serializers.DictField(allow_null=True, required=False)


class VoiceSessionSummarySerializer(serializers.ModelSerializer):
    """Compact summary of a voice session."""

    class Meta:
        model = VoiceAgentSession
        fields = [
            "id",
            "status",
            "needs_confirmation",
            "created_at",
            "updated_at",
            "ended_at",
        ]


class VoiceSessionDetailSerializer(serializers.ModelSerializer):
    """Full detail view of a voice session including history and active incident context."""

    driver_username = serializers.CharField(source="driver.username", read_only=True)
    active_incident = serializers.SerializerMethodField()

    class Meta:
        model = VoiceAgentSession
        fields = [
            "id",
            "driver_username",
            "status",
            "conversation_history",
            "extracted_emergency_data",
            "missing_information",
            "needs_confirmation",
            "active_incident",
            "created_at",
            "updated_at",
            "ended_at",
        ]

    def get_active_incident(self, obj) -> dict | None:
        """Retrieves active emergency incident for the driver if available."""
        from apps.emergencies.models import EmergencyIncident, IncidentStatus

        active = (
            EmergencyIncident.objects.filter(reporting_driver=obj.driver)
            .exclude(status__in=[IncidentStatus.CLOSED, IncidentStatus.CANCELLED])
            .select_related("hospital", "ambulance")
            .order_by("-created_at")
            .first()
        )
        if not active:
            return None

        return {
            "id": str(active.id),
            "incident_number": active.incident_number,
            "status": active.status,
            "status_display": active.get_status_display(),
            "hospital_name": active.hospital.name if active.hospital else None,
            "ambulance_vehicle": active.ambulance.vehicle_number if active.ambulance else None,
        }


class VoiceSessionConfirmSerializer(serializers.Serializer):
    """Input serializer for explicit emergency confirmation and dispatch."""

    confirmation = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Explicit driver confirmation boolean flag.",
    )
    hospital_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional destination hospital UUID. If omitted, resolved via nearest active facility.",
    )
    severity = serializers.ChoiceField(
        choices=IncidentSeverity.choices,
        required=False,
        allow_null=True,
        help_text="Optional severity override (LOW, MEDIUM, HIGH, CRITICAL).",
    )
    latitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=False,
        allow_null=True,
        help_text="Current GPS latitude of the ambulance device.",
    )
    longitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=False,
        allow_null=True,
        help_text="Current GPS longitude of the ambulance device.",
    )
    accuracy = serializers.DecimalField(
        max_digits=6,
        decimal_places=2,
        required=False,
        allow_null=True,
        help_text="GPS accuracy in meters.",
    )

