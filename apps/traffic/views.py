"""
REST API views for SERTOS Traffic Signal & ESP32 Integration.

Cleanly split across:
1. Administrative Endpoints (Human JWT + IsSystemAdmin):
   - Device registration
   - Device inventory listing & detail
2. IoT Controller Endpoints (ESP32 Device Authentication + IsRegisteredESP32Device):
   - Heartbeat ping
   - Telemetry status report
   - Configuration retrieval
   - Intersection signal state report
   - Pending preemption commands polling
   - Command acknowledgement & execution reporting
"""

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsSystemAdmin
from apps.accounts.views import standard_response
from apps.emergencies.permissions import IsPoliceDispatcherDashboardPermission
from apps.emergencies.models import EmergencyIncident, IncidentStatus
from .authentication import ESP32DeviceAuthentication
from .models import CommandStatus, TrafficCommand, TrafficDevice, TrafficSignalState
from .permissions import IsRegisteredESP32Device
from .serializers import (
    DeviceConfigSerializer,
    DeviceHeartbeatResponseSerializer,
    DeviceStatusReportSerializer,
    TrafficCommandAckSerializer,
    TrafficCommandSerializer,
    TrafficDeviceRegistrationSerializer,
    TrafficDeviceSerializer,
    TrafficSignalStateSerializer,
)
from .services import acknowledge_traffic_command, evaluate_and_match_traffic_signals, expire_stale_commands


# ============================================================================
# Administrative Endpoints (Human System Administrators)
# ============================================================================

class DeviceRegistrationView(generics.CreateAPIView):
    """
    POST /api/traffic/devices/register/
    Registers a new ESP32 controller. Generates hardware secret token returned ONCE.
    """
    queryset = TrafficDevice.objects.all()
    serializer_class = TrafficDeviceRegistrationSerializer
    permission_classes = [IsAuthenticated, IsSystemAdmin]


class DeviceListView(generics.ListAPIView):
    """
    GET /api/traffic/devices/
    Lists all registered traffic controllers. Secrets are completely excluded.
    """
    queryset = TrafficDevice.objects.order_by("device_id").prefetch_related(
        Prefetch(
            "signal_states",
            queryset=TrafficSignalState.objects.order_by("-reported_at"),
            to_attr="recent_signal_states",
        )
    )
    serializer_class = TrafficDeviceSerializer
    permission_classes = [IsAuthenticated, IsSystemAdmin]


class DeviceDetailView(generics.RetrieveUpdateAPIView):
    """
    GET /api/traffic/devices/<device_id>/
    Retrieves metadata for a specific traffic controller.
    """
    queryset = TrafficDevice.objects.all()
    serializer_class = TrafficDeviceSerializer
    permission_classes = [IsAuthenticated, IsSystemAdmin]
    lookup_field = "device_id"


class PoliceTrafficOverviewView(APIView):
    """Read-only live view of controller telemetry and corridor command status."""

    permission_classes = [IsPoliceDispatcherDashboardPermission]

    def get(self, request):
        devices = TrafficDevice.objects.prefetch_related(
            Prefetch(
                "signal_states",
                queryset=TrafficSignalState.objects.order_by("-reported_at"),
                to_attr="recent_signal_states",
            )
        ).order_by("intersection_name", "device_id")

        device_rows = []
        for device in devices:
            latest_state = device.recent_signal_states[0] if device.recent_signal_states else None
            device_rows.append({
                "id": str(device.id),
                "device_id": device.device_id,
                "name": device.name,
                "intersection_name": device.intersection_name,
                "latitude": str(device.latitude),
                "longitude": str(device.longitude),
                "is_active": device.is_active,
                "last_heartbeat_at": device.last_heartbeat_at,
                "current_signal_phase": device.current_signal_phase,
                "firmware_version": device.firmware_version,
                "sensor_1_detected": device.last_status_payload.get("sensor_1_detected"),
                "sensor_2_detected": device.last_status_payload.get("sensor_2_detected"),
                "latest_signal_state": {
                    "current_phase": latest_state.current_phase,
                    "is_preempted": latest_state.is_preempted,
                    "reported_at": latest_state.reported_at,
                } if latest_state else None,
            })

        commands = TrafficCommand.objects.select_related("device", "incident").order_by("-created_at")[:25]
        return standard_response(
            data={
                "devices": device_rows,
                "commands": TrafficCommandSerializer(commands, many=True).data,
            },
            message="Live traffic controller status retrieved successfully.",
        )


class PoliceTrafficRecheckView(APIView):
    """Re-evaluate an in-transit ambulance's latest GPS report against controllers."""

    permission_classes = [IsPoliceDispatcherDashboardPermission]

    def post(self, request, incident_id):
        incident = get_object_or_404(EmergencyIncident, pk=incident_id)
        if incident.status != IncidentStatus.IN_TRANSIT:
            return standard_response(
                success=False,
                errors={"detail": ["Corridor evaluation requires an incident marked in transit."]},
                message="Incident is not in transit.",
                status_code=status.HTTP_409_CONFLICT,
            )

        location = incident.locations.order_by("-server_received_at", "-id").first()
        if location is None:
            return standard_response(
                success=False,
                errors={"detail": ["No ambulance GPS report is available for this incident."]},
                message="Corridor evaluation requires a current GPS report.",
                status_code=status.HTTP_409_CONFLICT,
            )

        commands = evaluate_and_match_traffic_signals(incident, location)
        return standard_response(
            data={
                "created_count": len(commands),
                "commands": TrafficCommandSerializer(commands, many=True).data,
            },
            message="Corridor evaluation completed using the latest ambulance GPS report.",
        )


# ============================================================================
# Microcontroller IoT Endpoints (ESP32 Controller Hardware)
# ============================================================================

class DeviceHeartbeatView(APIView):
    """
    POST /api/traffic/esp32/heartbeat/
    ESP32 periodic heartbeat ping. Updates device last_heartbeat_at timestamp.
    """
    authentication_classes = [ESP32DeviceAuthentication]
    permission_classes = [IsRegisteredESP32Device]

    def post(self, request):
        device: TrafficDevice = request.user
        device.last_heartbeat_at = timezone.now()
        device.save(update_fields=["last_heartbeat_at"])

        data = {
            "status": "healthy",
            "device_id": device.device_id,
            "server_time": device.last_heartbeat_at,
            "is_active": device.is_active,
        }
        serializer = DeviceHeartbeatResponseSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DeviceStatusView(APIView):
    """
    POST /api/traffic/esp32/status/
    ESP32 telemetry report (battery, WiFi RSSI, operational mode, temperature).
    """
    authentication_classes = [ESP32DeviceAuthentication]
    permission_classes = [IsRegisteredESP32Device]

    def post(self, request):
        device: TrafficDevice = request.user
        serializer = DeviceStatusReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        update_fields = ["last_status_payload", "updated_at"]

        if "firmware_version" in validated and validated["firmware_version"]:
            device.firmware_version = validated["firmware_version"]
            update_fields.append("firmware_version")

        if "mac_address" in validated and validated["mac_address"]:
            device.mac_address = validated["mac_address"]
            update_fields.append("mac_address")

        device.last_status_payload = validated
        device.save(update_fields=update_fields)

        return Response(
            {"status": "recorded", "device_id": device.device_id, "timestamp": timezone.now().isoformat()},
            status=status.HTTP_200_OK,
        )


class DeviceConfigView(APIView):
    """
    GET /api/traffic/esp32/config/
    Retrieves operational configuration, timing constraints, and polling intervals for ESP32.
    """
    authentication_classes = [ESP32DeviceAuthentication]
    permission_classes = [IsRegisteredESP32Device]

    def get(self, request):
        device: TrafficDevice = request.user
        config_data = {
            "device_id": device.device_id,
            "intersection_name": device.intersection_name,
            "latitude": device.latitude,
            "longitude": device.longitude,
            "heartbeat_interval_seconds": 30,
            "command_poll_interval_seconds": 5,
            "safety_min_green_seconds": 15,
            "safety_yellow_seconds": 4,
            "safety_all_red_seconds": 2,
            "max_preemption_seconds": 45,
            "failsafe_reversion_timeout_seconds": 60,
        }
        serializer = DeviceConfigSerializer(config_data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DeviceSignalStateView(APIView):
    """
    POST /api/traffic/esp32/signal-state/
    Reports current intersection signal phase (RED, YELLOW, GREEN, etc.) and cycle elapsed duration.
    """
    authentication_classes = [ESP32DeviceAuthentication]
    permission_classes = [IsRegisteredESP32Device]

    def post(self, request):
        device: TrafficDevice = request.user
        serializer = TrafficSignalStateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        signal_state = serializer.save(device=device)

        # Sync latest reported phase to the device record
        device.current_signal_phase = signal_state.current_phase
        device.save(update_fields=["current_signal_phase"])

        return Response(TrafficSignalStateSerializer(signal_state).data, status=status.HTTP_201_CREATED)


class PendingCommandsView(APIView):
    """
    GET /api/traffic/esp32/commands/pending/
    Polls active, unexpired advisory preemption commands for the authenticated ESP32 controller.
    Automatically marks expired pending commands before returning.
    """
    authentication_classes = [ESP32DeviceAuthentication]
    permission_classes = [IsRegisteredESP32Device]

    def get(self, request):
        device: TrafficDevice = request.user

        # Transition any expired pending commands
        expire_stale_commands()

        now = timezone.now()
        pending = (
            TrafficCommand.objects.filter(
                device=device,
                status=CommandStatus.PENDING,
                expires_at__gt=now,
            )
            .select_related("incident")
            .order_by("created_at")
        )

        serializer = TrafficCommandSerializer(pending, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AcknowledgeCommandView(APIView):
    """
    POST /api/traffic/esp32/commands/<command_id>/ack/
    Reports acknowledgement or execution result of an advisory preemption command.
    Enforces device isolation, idempotency, and expiration validation.
    """
    authentication_classes = [ESP32DeviceAuthentication]
    permission_classes = [IsRegisteredESP32Device]

    def post(self, request, command_id):
        device: TrafficDevice = request.user
        serializer = TrafficCommandAckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cmd = acknowledge_traffic_command(
            device=device,
            command_id=command_id,
            status=serializer.validated_data["status"],
            execution_notes=serializer.validated_data.get("execution_notes", ""),
            failure_reason=serializer.validated_data.get("failure_reason", ""),
        )

        return Response(TrafficCommandSerializer(cmd).data, status=status.HTTP_200_OK)
