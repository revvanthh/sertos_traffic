"""
Serializers for SERTOS Traffic & ESP32 IoT endpoints.

Enforces:
1. Complete omission of sensitive credentials (token_hash is NEVER exposed).
2. One-time disclosure of raw_token during administrative registration only.
3. Strict telemetry validation and safety constraint serialization.
4. Clean separation between human administration and IoT device reporting.
"""

import re
import secrets
from rest_framework import serializers

from .models import (
    CommandAction,
    CommandStatus,
    SignalPhase,
    TrafficCommand,
    TrafficDevice,
    TrafficSignalState,
)


class TrafficDeviceRegistrationSerializer(serializers.ModelSerializer):
    """
    Administrative serializer for registering new ESP32 traffic controllers.
    Generates a cryptographically secure token and returns it ONLY ONCE upon creation.
    """

    raw_token = serializers.CharField(read_only=True)
    raw_token_warning = serializers.SerializerMethodField()

    class Meta:
        model = TrafficDevice
        fields = [
            "id",
            "device_id",
            "name",
            "intersection_name",
            "latitude",
            "longitude",
            "is_active",
            "raw_token",
            "raw_token_warning",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_raw_token_warning(self, obj):
        if getattr(obj, "raw_token", None):
            return "Save this device secret token immediately. It will not be shown again."
        return None

    def validate_device_id(self, value):
        cleaned = value.strip().upper()
        if not re.match(r"^[A-Z0-9_\-]+$", cleaned):
            raise serializers.ValidationError(
                "Device ID must consist only of alphanumeric characters, dashes, and underscores."
            )
        if TrafficDevice.objects.filter(device_id=cleaned).exists():
            raise serializers.ValidationError(f"Device with ID '{cleaned}' is already registered.")
        return cleaned

    def create(self, validated_data):
        raw_token = f"esp32_{secrets.token_urlsafe(32)}"
        device = TrafficDevice(**validated_data)
        device.set_token(raw_token)
        device.save()
        # Ephemeral attribute returned strictly on initial 201 response
        device.raw_token = raw_token
        return device


class TrafficDeviceSerializer(serializers.ModelSerializer):
    """
    Administrative view serializer for inspecting registered traffic controllers.
    Guarantees secrets and token hashes are completely excluded.
    """

    sensor_1_detected = serializers.SerializerMethodField()
    sensor_2_detected = serializers.SerializerMethodField()
    wifi_rssi = serializers.SerializerMethodField()
    operational_mode = serializers.SerializerMethodField()
    latest_signal_state = serializers.SerializerMethodField()

    class Meta:
        model = TrafficDevice
        fields = [
            "id",
            "device_id",
            "name",
            "intersection_name",
            "latitude",
            "longitude",
            "is_active",
            "last_heartbeat_at",
            "current_signal_phase",
            "firmware_version",
            "sensor_1_detected",
            "sensor_2_detected",
            "wifi_rssi",
            "operational_mode",
            "latest_signal_state",
            "ip_address",
            "mac_address",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "device_id",
            "last_heartbeat_at",
            "current_signal_phase",
            "firmware_version",
            "sensor_1_detected",
            "sensor_2_detected",
            "wifi_rssi",
            "operational_mode",
            "latest_signal_state",
            "ip_address",
            "mac_address",
            "created_at",
            "updated_at",
        ]

    def get_sensor_1_detected(self, obj):
        value = obj.last_status_payload.get("sensor_1_detected")
        return value if isinstance(value, bool) else None

    def get_sensor_2_detected(self, obj):
        value = obj.last_status_payload.get("sensor_2_detected")
        return value if isinstance(value, bool) else None

    def get_wifi_rssi(self, obj):
        value = obj.last_status_payload.get("wifi_rssi")
        return value if isinstance(value, int) else None

    def get_operational_mode(self, obj):
        value = obj.last_status_payload.get("operational_mode")
        return value if isinstance(value, str) else None

    def get_latest_signal_state(self, obj):
        recent = getattr(obj, "recent_signal_states", None)
        state = recent[0] if recent else obj.signal_states.order_by("-reported_at").first()
        if not state:
            return None
        return {
            "current_phase": state.current_phase,
            "is_preempted": state.is_preempted,
            "reported_at": state.reported_at,
        }


class DeviceHeartbeatResponseSerializer(serializers.Serializer):
    """Response serializer for ESP32 heartbeat ping."""
    status = serializers.CharField()
    device_id = serializers.CharField()
    server_time = serializers.DateTimeField()
    is_active = serializers.BooleanField()


class DeviceStatusReportSerializer(serializers.Serializer):
    """Validates real-time telemetry reported by ESP32 controller."""
    firmware_version = serializers.CharField(max_length=50, required=False, allow_blank=True)
    battery_percentage = serializers.IntegerField(min_value=0, max_value=100, required=False)
    wifi_rssi = serializers.IntegerField(min_value=-120, max_value=0, required=False)
    operational_mode = serializers.ChoiceField(
        choices=["NORMAL", "FAILSAFE", "PREEMPTION", "MAINTENANCE"],
        required=False,
        default="NORMAL",
    )
    temperature_celsius = serializers.FloatField(required=False)
    mac_address = serializers.CharField(max_length=30, required=False, allow_blank=True)
    # Optional local prototype sensors; persisted in TrafficDevice.last_status_payload.
    sensor_1_detected = serializers.BooleanField(required=False)
    sensor_2_detected = serializers.BooleanField(required=False)


class DeviceConfigSerializer(serializers.Serializer):
    """Configuration parameters returned to ESP32 controller upon startup or poll."""
    device_id = serializers.CharField()
    intersection_name = serializers.CharField()
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    heartbeat_interval_seconds = serializers.IntegerField(default=30)
    command_poll_interval_seconds = serializers.IntegerField(default=5)
    safety_min_green_seconds = serializers.IntegerField(default=15)
    safety_yellow_seconds = serializers.IntegerField(default=4)
    safety_all_red_seconds = serializers.IntegerField(default=2)
    max_preemption_seconds = serializers.IntegerField(default=45)
    failsafe_reversion_timeout_seconds = serializers.IntegerField(default=60)


class TrafficSignalStateSerializer(serializers.ModelSerializer):
    """Validates and persists real-time intersection signal phase telemetry."""

    class Meta:
        model = TrafficSignalState
        fields = [
            "id",
            "current_phase",
            "cycle_duration_seconds",
            "current_phase_elapsed_seconds",
            "is_preempted",
            "reported_at",
            "raw_telemetry",
        ]
        read_only_fields = ["id", "reported_at"]


class TrafficCommandSerializer(serializers.ModelSerializer):
    """Serializes advisory preemption commands delivered to ESP32."""

    incident_number = serializers.CharField(source="incident.incident_number", read_only=True)
    device_id = serializers.CharField(source="device.device_id", read_only=True)

    class Meta:
        model = TrafficCommand
        fields = [
            "id",
            "device_id",
            "incident_id",
            "incident_number",
            "action",
            "status",
            "created_at",
            "expires_at",
            "acknowledged_at",
            "executed_at",
            "execution_notes",
            "failure_reason",
            "distance_meters_at_creation",
            "eta_seconds_at_creation",
            "safety_constraints",
        ]
        read_only_fields = fields


class TrafficCommandAckSerializer(serializers.Serializer):
    """Validates command receipt and execution report from ESP32."""

    status = serializers.ChoiceField(
        choices=[CommandStatus.ACKNOWLEDGED, CommandStatus.EXECUTED, CommandStatus.FAILED]
    )
    execution_notes = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    failure_reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
