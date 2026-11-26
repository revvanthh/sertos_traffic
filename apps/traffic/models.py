"""
Database models for SERTOS Traffic & ESP32 IoT Integration.

Defines:
1. TrafficDevice: Registry for physical/simulated ESP32 microcontroller traffic light controllers.
2. TrafficSignalState: Real-time telemetry log for intersection signal phases and operational status.
3. TrafficCommand: Safe advisory priority command lifecycle for emergency corridor clearance.
"""

import hashlib
import hmac
import uuid
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class SignalPhase(models.TextChoices):
    """Controlled traffic signal operational phases."""
    RED = "RED", "Red"
    YELLOW = "YELLOW", "Yellow"
    GREEN = "GREEN", "Green"
    ALL_RED = "ALL_RED", "All-Red Clearance"
    FLASHING_YELLOW = "FLASHING_YELLOW", "Flashing Yellow Caution"
    FAULT = "FAULT", "Hardware / Lamp Fault"


class CommandAction(models.TextChoices):
    """Controlled emergency preemption advisory actions."""
    PREPARE_GREEN_CORRIDOR = "PREPARE_GREEN_CORRIDOR", "Prepare Green Corridor"
    EXTEND_GREEN = "EXTEND_GREEN", "Extend Active Green Phase"
    RESTORE_NORMAL_CYCLE = "RESTORE_NORMAL_CYCLE", "Restore Normal Cycle"


class CommandStatus(models.TextChoices):
    """
    Controlled lifecycle status for traffic preemption commands.
    Progression: PENDING -> ACKNOWLEDGED -> EXECUTED
    Terminal / Failure states: EXPIRED, FAILED, CANCELLED
    """
    PENDING = "PENDING", "Pending"
    ACKNOWLEDGED = "ACKNOWLEDGED", "Acknowledged"
    EXECUTED = "EXECUTED", "Executed"
    EXPIRED = "EXPIRED", "Expired"
    FAILED = "FAILED", "Failed"
    CANCELLED = "CANCELLED", "Cancelled"


class TrafficDevice(models.Model):
    """
    Registered ESP32 microcontroller managing a traffic signal intersection.
    Uses independent cryptographic token authentication rather than human JWT.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique internal UUID for the traffic controller.",
    )
    device_id = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Unique hardware device identifier (e.g. ESP32-BLR-MG-01).",
    )
    name = models.CharField(
        max_length=150,
        help_text="Human-readable name or label of the controller unit.",
    )
    intersection_name = models.CharField(
        max_length=150,
        help_text="Physical intersection or junction location description.",
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[
            MinValueValidator(Decimal("-90.000000")),
            MaxValueValidator(Decimal("90.000000")),
        ],
        help_text="GPS latitude coordinate in decimal degrees (-90.0 to 90.0).",
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[
            MinValueValidator(Decimal("-180.000000")),
            MaxValueValidator(Decimal("180.000000")),
        ],
        help_text="GPS longitude coordinate in decimal degrees (-180.0 to 180.0).",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Designates whether this controller unit is active and eligible for preemption commands.",
    )
    token_hash = models.CharField(
        max_length=128,
        help_text="Cryptographic hash of the device authentication secret token.",
    )
    last_heartbeat_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Authoritative server timestamp of the most recent device heartbeat.",
    )
    current_signal_phase = models.CharField(
        max_length=20,
        choices=SignalPhase.choices,
        default=SignalPhase.RED,
        help_text="Most recently reported traffic signal phase.",
    )
    firmware_version = models.CharField(
        max_length=50,
        blank=True,
        default="1.0.0",
        help_text="Firmware version currently running on the microcontroller.",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Reported local or gateway IP address of the controller.",
    )
    mac_address = models.CharField(
        max_length=30,
        blank=True,
        default="",
        help_text="Hardware MAC address of the ESP32 Wi-Fi/Ethernet interface.",
    )
    last_status_payload = models.JSONField(
        default=dict,
        blank=True,
        help_text="Latest full telemetry report (battery, WiFi RSSI, operational mode).",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when device was registered in SERTOS.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when device record was last modified.",
    )

    class Meta:
        db_table = "traffic_device"
        verbose_name = "Traffic Device"
        verbose_name_plural = "Traffic Devices"
        ordering = ["device_id"]
        indexes = [
            models.Index(fields=["is_active", "last_heartbeat_at"], name="idx_dev_active_heartbeat"),
        ]

    def __str__(self) -> str:
        return f"{self.device_id} ({self.intersection_name})"

    @property
    def is_authenticated(self) -> bool:
        """DRF compatibility: indicates authenticated IoT device principal."""
        return True

    @property
    def is_anonymous(self) -> bool:
        """DRF compatibility: device is not anonymous."""
        return False

    def set_token(self, raw_token: str) -> None:
        """Computes and stores SHA-256 hash of the raw device secret."""
        self.token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def check_token(self, raw_token: str) -> bool:
        """Constant-time verification of the incoming secret against stored hash."""
        if not raw_token or not self.token_hash:
            return False
        incoming_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        return hmac.compare_digest(self.token_hash, incoming_hash)

    def clean(self):
        super().clean()
        errors = {}
        if self.latitude is not None:
            if self.latitude < Decimal("-90") or self.latitude > Decimal("90"):
                errors["latitude"] = "Latitude must be between -90 and 90 degrees."
        if self.longitude is not None:
            if self.longitude < Decimal("-180") or self.longitude > Decimal("180"):
                errors["longitude"] = "Longitude must be between -180 and 180 degrees."
        if errors:
            raise ValidationError(errors)


class TrafficSignalState(models.Model):
    """
    Periodic signal state telemetry reported by an ESP32 traffic controller.
    Records current phase, cycle progression, and preemption status.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID for this signal telemetry record.",
    )
    device = models.ForeignKey(
        TrafficDevice,
        on_delete=models.CASCADE,
        related_name="signal_states",
        help_text="The reporting ESP32 traffic controller.",
    )
    current_phase = models.CharField(
        max_length=20,
        choices=SignalPhase.choices,
        help_text="Active traffic signal phase at the time of reporting.",
    )
    cycle_duration_seconds = models.PositiveIntegerField(
        default=90,
        help_text="Total standard cycle duration configured on the local controller in seconds.",
    )
    current_phase_elapsed_seconds = models.PositiveIntegerField(
        default=0,
        help_text="Elapsed duration in the active phase in seconds.",
    )
    is_preempted = models.BooleanField(
        default=False,
        help_text="Designates whether the controller is currently executing emergency preemption.",
    )
    reported_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Authoritative server timestamp when telemetry was received.",
    )
    raw_telemetry = models.JSONField(
        default=dict,
        blank=True,
        help_text="Raw controller telemetry payload.",
    )

    class Meta:
        db_table = "traffic_signal_state"
        verbose_name = "Traffic Signal State"
        verbose_name_plural = "Traffic Signal States"
        ordering = ["-reported_at"]
        indexes = [
            models.Index(fields=["device", "-reported_at"], name="idx_sig_dev_reported"),
        ]

    def __str__(self) -> str:
        return f"{self.device.device_id}: {self.current_phase} [{self.reported_at}]"


class TrafficCommand(models.Model):
    """
    Safe advisory emergency preemption command issued to an ESP32 traffic controller.
    
    SAFETY PRINCIPLES:
    1. Central backend provides advisory requests; local ESP32 controller always retains authority.
    2. Local controller enforces minimum clearance times (yellow, all-red, pedestrian clearance).
    3. Commands are strictly idempotent, bounded by an expiry deadline, and never bypass failsafe logic.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID for the traffic preemption command.",
    )
    device = models.ForeignKey(
        TrafficDevice,
        on_delete=models.CASCADE,
        related_name="commands",
        help_text="The target ESP32 traffic controller.",
    )
    incident = models.ForeignKey(
        "emergencies.EmergencyIncident",
        on_delete=models.CASCADE,
        related_name="traffic_commands",
        help_text="The triggering emergency incident.",
    )
    action = models.CharField(
        max_length=50,
        choices=CommandAction.choices,
        default=CommandAction.PREPARE_GREEN_CORRIDOR,
        help_text="Requested safe traffic preemption action.",
    )
    status = models.CharField(
        max_length=20,
        choices=CommandStatus.choices,
        default=CommandStatus.PENDING,
        db_index=True,
        help_text="Current execution status of the command.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when command was generated by SERTOS.",
    )
    expires_at = models.DateTimeField(
        db_index=True,
        help_text="Timestamp after which this command is strictly invalid and must be rejected.",
    )
    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when controller acknowledged receipt of this command.",
    )
    executed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when controller completed safe execution of this command.",
    )
    execution_notes = models.TextField(
        blank=True,
        default="",
        help_text="Controller telemetry or execution summary reported upon acknowledgement.",
    )
    failure_reason = models.TextField(
        blank=True,
        default="",
        help_text="Explanation if the command expired, failed, or was rejected by safety logic.",
    )
    idempotency_key = models.CharField(
        max_length=128,
        unique=True,
        db_index=True,
        help_text="Unique key ensuring duplicate commands are never created or executed concurrently.",
    )
    distance_meters_at_creation = models.FloatField(
        null=True,
        blank=True,
        help_text="Distance between ambulance and intersection at the time of command creation (meters).",
    )
    eta_seconds_at_creation = models.IntegerField(
        null=True,
        blank=True,
        help_text="Estimated time of arrival at the intersection at command creation (seconds).",
    )
    safety_constraints = models.JSONField(
        default=dict,
        blank=True,
        help_text="Mandatory local controller safety constraints (min clearance, max hold).",
    )

    class Meta:
        db_table = "traffic_command"
        verbose_name = "Traffic Command"
        verbose_name_plural = "Traffic Commands"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["device", "status"], name="idx_cmd_dev_status"),
            models.Index(fields=["incident", "status"], name="idx_cmd_inc_status"),
            models.Index(fields=["expires_at"], name="idx_cmd_expires_at"),
        ]

    def __str__(self) -> str:
        return f"Command {self.id} -> {self.device.device_id} [{self.status}]"

    @property
    def is_expired(self) -> bool:
        """Determines whether the command has passed its safe validity deadline."""
        return timezone.now() >= self.expires_at

    def mark_expired_if_due(self) -> bool:
        """Marks the command as EXPIRED if currently PENDING and expired."""
        if self.status == CommandStatus.PENDING and self.is_expired:
            self.status = CommandStatus.EXPIRED
            self.failure_reason = "Command expired before controller acknowledgement."
            self.save(update_fields=["status", "failure_reason"])
            return True
        return False
