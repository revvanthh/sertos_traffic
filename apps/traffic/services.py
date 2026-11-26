"""
Domain services for SERTOS Traffic Signal Integration.

Implements:
1. evaluate_and_match_traffic_signals: Matches approaching ambulances to registered traffic intersections.
2. acknowledge_traffic_command: Transactional, idempotent command acknowledgement and execution.
3. expire_stale_commands: Automatically transitions expired pending commands.

SAFETY AND RELIABILITY GUARANTEES:
- Device failures NEVER interrupt emergency creation or GPS tracking.
- Local ESP32 controller always retains authority and safety checks.
- Unrelated intersections and moving-away vehicles are strictly excluded.
- Closed and cancelled emergencies never generate commands and immediately cancel pending requests.
- All commands are bounded by an expiration deadline (default 60 seconds).
"""

import logging
from datetime import timedelta
from typing import List, Optional

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.emergencies.models import (
    AmbulanceLocation,
    EmergencyIncident,
    IncidentStatus,
)
from apps.emergencies.routes_service import haversine_distance_meters
from .models import (
    CommandAction,
    CommandStatus,
    SignalPhase,
    TrafficCommand,
    TrafficDevice,
)

logger = logging.getLogger(__name__)

# Spatial and Timing Constants for Preemption Evaluation
MAX_APPROACH_DISTANCE_METERS = 1000.0  # 1 km approach corridor
MIN_TRIGGER_DISTANCE_METERS = 80.0    # Ambulance already at/inside intersection
IMMEDIATE_APPROACH_DISTANCE_METERS = 500.0
COMMAND_EXPIRY_SECONDS = 60
IDEMPOTENCY_WINDOW_SECONDS = 30


def evaluate_and_match_traffic_signals(
    incident: EmergencyIncident,
    latest_location: Optional[AmbulanceLocation] = None,
) -> List[TrafficCommand]:
    """
    Evaluates active emergency incidents against registered traffic intersections.
    Generates safe, bounded, idempotent preemption commands if an ambulance is
    approaching an active intersection.
    """
    # 1. Emergency Lifecycle Guard: Only ASSIGNED and IN_TRANSIT emergencies are eligible
    if incident.status in [IncidentStatus.CLOSED, IncidentStatus.CANCELLED, IncidentStatus.ARRIVED]:
        # Cancel any pending commands for concluded/cancelled/arrived emergencies
        cancelled_count = TrafficCommand.objects.filter(
            incident=incident,
            status=CommandStatus.PENDING,
        ).update(
            status=CommandStatus.CANCELLED,
            failure_reason=f"Emergency transitioned to terminal status '{incident.status}'.",
        )
        if cancelled_count:
            logger.info(
                "Cancelled %d pending traffic command(s) for terminal incident %s",
                cancelled_count,
                incident.incident_number,
            )
        return []

    if incident.status not in [IncidentStatus.ASSIGNED, IncidentStatus.IN_TRANSIT]:
        # Incident is REPORTED (not yet dispatched or moving)
        return []

    # 2. Location Resolution
    if latest_location is None:
        latest_location = (
            AmbulanceLocation.objects.filter(incident=incident)
            .order_by("-server_received_at", "-id")
            .first()
        )

    if not latest_location or latest_location.latitude is None or latest_location.longitude is None:
        return []

    curr_lat = float(latest_location.latitude)
    curr_lon = float(latest_location.longitude)

    # 3. Active Controllers Query
    active_devices = TrafficDevice.objects.filter(is_active=True)
    if not active_devices.exists():
        return []

    # 4. Fetch previous GPS location for heading/movement verification
    prev_location = (
        AmbulanceLocation.objects.filter(incident=incident)
        .exclude(pk=latest_location.pk)
        .order_by("-server_received_at", "-id")
        .first()
    )

    generated_commands: List[TrafficCommand] = []
    now = timezone.now()

    for device in active_devices:
        dev_lat = float(device.latitude)
        dev_lon = float(device.longitude)

        curr_distance = haversine_distance_meters(curr_lat, curr_lon, dev_lat, dev_lon)

        # Distance thresholding: Must be inside approach corridor (80m to 1000m)
        if curr_distance > MAX_APPROACH_DISTANCE_METERS or curr_distance < MIN_TRIGGER_DISTANCE_METERS:
            continue

        # Heading / Direction verification
        if prev_location and prev_location.latitude is not None and prev_location.longitude is not None:
            prev_lat = float(prev_location.latitude)
            prev_lon = float(prev_location.longitude)
            prev_distance = haversine_distance_meters(prev_lat, prev_lon, dev_lat, dev_lon)

            # If distance is increasing, ambulance is moving away from the intersection
            if curr_distance >= prev_distance:
                logger.debug(
                    "Ambulance is moving away from intersection %s (curr: %.1fm, prev: %.1fm); skipping",
                    device.device_id,
                    curr_distance,
                    prev_distance,
                )
                continue
        else:
            # Single GPS point: only trigger if in immediate approach zone
            if curr_distance > IMMEDIATE_APPROACH_DISTANCE_METERS:
                continue

        # 5. Duplicate Prevention: Check for existing active command
        active_command_exists = TrafficCommand.objects.filter(
            device=device,
            incident=incident,
            status__in=[CommandStatus.PENDING, CommandStatus.ACKNOWLEDGED],
            expires_at__gt=now,
        ).exists()

        if active_command_exists:
            logger.debug(
                "Active command already exists for device %s and incident %s; skipping duplicate",
                device.device_id,
                incident.incident_number,
            )
            continue

        # 6. Action selection
        if device.current_signal_phase == SignalPhase.GREEN:
            action = CommandAction.EXTEND_GREEN
        else:
            action = CommandAction.PREPARE_GREEN_CORRIDOR

        # 7. Construct safe command with bounded expiry and safety constraints
        time_bucket = int(now.timestamp() // IDEMPOTENCY_WINDOW_SECONDS)
        idempotency_key = f"cmd:{incident.id}:{device.id}:{incident.status}:{time_bucket}"
        expires_at = now + timedelta(seconds=COMMAND_EXPIRY_SECONDS)

        # Rough ETA estimate based on average emergency speed (40 km/h = ~11.1 m/s)
        estimated_eta_seconds = max(10, int(curr_distance / 11.1))

        safety_constraints = {
            "min_green_seconds": 15,
            "min_yellow_seconds": 4,
            "min_all_red_seconds": 2,
            "max_preemption_seconds": 45,
            "allow_pedestrian_clearance": True,
            "local_failsafe_reversion": True,
        }

        try:
            command = TrafficCommand.objects.create(
                device=device,
                incident=incident,
                action=action,
                status=CommandStatus.PENDING,
                expires_at=expires_at,
                idempotency_key=idempotency_key,
                distance_meters_at_creation=round(curr_distance, 1),
                eta_seconds_at_creation=estimated_eta_seconds,
                safety_constraints=safety_constraints,
            )
            generated_commands.append(command)
            logger.info(
                "Created %s traffic command for device %s (incident: %s, distance: %.1fm, ETA: %ds)",
                action,
                device.device_id,
                incident.incident_number,
                curr_distance,
                estimated_eta_seconds,
            )
        except IntegrityError:
            # Duplicate caught by idempotency_key uniqueness constraint
            logger.debug("Caught concurrent duplicate creation via idempotency_key for device %s", device.device_id)

    return generated_commands


def acknowledge_traffic_command(
    device: TrafficDevice,
    command_id,
    status: str,
    execution_notes: str = "",
    failure_reason: str = "",
) -> TrafficCommand:
    """
    Transactional service to acknowledge or report execution of a traffic command by an ESP32.
    Guarantees idempotency and enforces safety bounds:
    - Expired commands cannot be executed and are persisted as EXPIRED.
    - Terminal states cannot be reverted.
    - Commands must belong to the calling device.
    """
    now = timezone.now()

    # Initial lookup and ownership check
    try:
        command = TrafficCommand.objects.select_related("device", "incident").get(pk=command_id)
    except (TrafficCommand.DoesNotExist, DjangoValidationError, ValueError):
        raise ValidationError({"detail": "Traffic command not found."})

    if command.device_id != device.id:
        raise ValidationError({"detail": "Traffic command does not belong to this device."})

    # Check expiration prior to atomic state update
    if command.expires_at <= now:
        TrafficCommand.objects.filter(pk=command.pk).update(
            status=CommandStatus.EXPIRED,
            failure_reason="Command expired before controller execution.",
        )
        command.refresh_from_db()
        if status == CommandStatus.EXECUTED:
            raise ValidationError({"detail": "Cannot execute an expired traffic command."})
        return command

    with transaction.atomic():
        locked_command = (
            TrafficCommand.objects.select_for_update()
            .select_related("device", "incident")
            .get(pk=command_id)
        )

        # Re-check expiration under lock
        if locked_command.expires_at <= timezone.now():
            locked_command.status = CommandStatus.EXPIRED
            locked_command.failure_reason = "Command expired before controller execution."
            locked_command.save(update_fields=["status", "failure_reason"])
            if status == CommandStatus.EXECUTED:
                raise ValidationError({"detail": "Cannot execute an expired traffic command."})
            return locked_command

        # Terminal state idempotency check
        if locked_command.status in [CommandStatus.EXECUTED, CommandStatus.EXPIRED, CommandStatus.FAILED, CommandStatus.CANCELLED]:
            if status == locked_command.status:
                # Idempotent re-submission of same status
                return locked_command
            raise ValidationError(
                {"detail": f"Cannot transition command from terminal status '{locked_command.status}' to '{status}'."}
            )

        # Apply valid transition
        if status == CommandStatus.ACKNOWLEDGED:
            locked_command.status = CommandStatus.ACKNOWLEDGED
            locked_command.acknowledged_at = timezone.now()
            if execution_notes:
                locked_command.execution_notes = execution_notes
            locked_command.save(update_fields=["status", "acknowledged_at", "execution_notes"])

        elif status == CommandStatus.EXECUTED:
            locked_command.status = CommandStatus.EXECUTED
            locked_command.executed_at = timezone.now()
            if not locked_command.acknowledged_at:
                locked_command.acknowledged_at = timezone.now()
            locked_command.execution_notes = execution_notes or "Executed safely under local controller timing constraints."
            locked_command.save(update_fields=["status", "executed_at", "acknowledged_at", "execution_notes"])

            # Reflect green preemption on device record
            device.current_signal_phase = SignalPhase.GREEN
            device.save(update_fields=["current_signal_phase"])

        elif status == CommandStatus.FAILED:
            locked_command.status = CommandStatus.FAILED
            locked_command.failure_reason = failure_reason or execution_notes or "Local controller rejected command."
            locked_command.save(update_fields=["status", "failure_reason"])

        else:
            raise ValidationError({"status": [f"Invalid status '{status}' for command acknowledgement."]})

        return locked_command


def expire_stale_commands() -> int:
    """
    Scans and expires overdue PENDING commands.
    Can be run periodically or during polling.
    """
    now = timezone.now()
    count = TrafficCommand.objects.filter(
        status=CommandStatus.PENDING,
        expires_at__lte=now,
    ).update(
        status=CommandStatus.EXPIRED,
        failure_reason="Command expired before controller receipt.",
    )
    return count
