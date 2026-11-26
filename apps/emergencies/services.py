"""
Domain services and transactional business logic for SERTOS Emergencies application.

Implements:
1. Unique incident number generation.
2. Transactional emergency incident and patient creation.
3. Pre-dispatch validation for drivers, vehicles, and hospital facilities.
4. Transactional emergency incident status lifecycle transitions with row locking.
5. High-frequency ambulance GPS tracking with authoritative server timestamping.
6. Internal lifecycle event generation (EmergencyEvent) without patient PII.
7. Role-targeted notification generation with GPS ping throttling.
8. Safe on_commit integration hooks for downstream dispatch (SMS, push, AI voice).
"""

import uuid
import math
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import UserRole
from .models import (
    Ambulance,
    AmbulanceLocation,
    EmergencyEvent,
    EmergencyEventType,
    EmergencyIncident,
    Gender,
    Hospital,
    IncidentSeverity,
    IncidentStatus,
    Notification,
    Patient,
)
from .routes_service import haversine_distance_meters

User = get_user_model()

GPS_NOTIFICATION_THROTTLE_SECONDS = 300  # 5 minutes throttle interval for GPS alerts


def dispatch_external_notification(notification_id: uuid.UUID):
    """
    Downstream notification integration hook (SMS, push, AI voice).
    Registered with transaction.on_commit() to ensure external work is
    never triggered for rolled-back operations.
    In Task 4.6, prepares the interface without invoking external providers.
    """
    # Clean extensibility hook for multi-channel external dispatch
    pass


def create_emergency_event(
    incident: EmergencyIncident,
    event_type: str,
    description: str,
    payload: dict,
) -> EmergencyEvent:
    """
    Internal service helper to persist an EmergencyEvent audit log.
    Ensures structured payloads do not contain sensitive patient medical notes.
    """
    event = EmergencyEvent(
        incident=incident,
        event_type=event_type,
        description=description,
        payload=payload,
    )
    event.full_clean()
    event.save()
    return event


def create_notifications_for_event(
    incident: EmergencyIncident,
    event: EmergencyEvent,
    title: str,
    message: str,
) -> list[Notification]:
    """
    Generates internal in-app notifications for:
    1. Verified, active hospital staff affiliated with the incident's hospital.
    2. Verified, active police dispatchers.
    Registers transaction.on_commit() hooks for external notification delivery.
    """
    # 1. Hospital staff of the destination hospital
    staff_users = User.objects.filter(
        hospital_affiliations__hospital=incident.hospital,
        hospital_affiliations__is_active=True,
        role=UserRole.HOSPITAL_STAFF,
        is_active=True,
        is_verified=True,
    ).distinct()

    # 2. Police dispatchers
    police_users = User.objects.filter(
        role=UserRole.POLICE_DISPATCHER,
        is_active=True,
        is_verified=True,
    ).distinct()

    # Combine unique recipients
    recipients_map = {u.id: u for u in list(staff_users) + list(police_users)}
    notifications = []

    for recipient in recipients_map.values():
        notif = Notification.objects.create(
            recipient=recipient,
            incident=incident,
            event=event,
            title=title,
            message=message,
        )
        notifications.append(notif)
        # Register on_commit hook safely
        transaction.on_commit(lambda nid=notif.id: dispatch_external_notification(nid))

    return notifications


def generate_unique_incident_number() -> str:
    """
    Generates a unique, human-readable incident reference code.
    Format: INC-YYYYMMDD-XXXX (e.g. INC-20261114-A1B2C3)
    """
    date_str = timezone.now().strftime("%Y%m%d")
    for _ in range(10):
        suffix = uuid.uuid4().hex[:6].upper()
        incident_number = f"INC-{date_str}-{suffix}"
        if not EmergencyIncident.objects.filter(incident_number=incident_number).exists():
            return incident_number

    # Fallback to longer entropy if collision persists
    return f"INC-{date_str}-{uuid.uuid4().hex[:10].upper()}"


def create_emergency_incident(
    driver,
    hospital_id,
    severity=IncidentSeverity.MEDIUM,
    description="",
    patient_data=None,
) -> EmergencyIncident:
    """
    Transactional service function to create an EmergencyIncident, associated Patient,
    initial EMERGENCY_REPORTED event, and notifications for hospital and police personnel.

    Workflow:
    1. Validates the authenticated driver (role, active status, verification).
    2. Finds the ambulance assigned to the driver.
    3. Verifies ambulance is active and available for dispatch.
    4. Validates the selected active destination hospital.
    5. Generates a unique incident tracking number.
    6. Creates EmergencyIncident and Patient records within transaction.atomic().
    7. Creates EmergencyEvent (EMERGENCY_REPORTED) and targeted Notifications.
    8. Atomically rolls back if validation fails, leaving zero orphaned records.
    """
    # 1. Validate driver
    if not driver or not getattr(driver, "is_authenticated", False):
        raise serializers.ValidationError({"reporting_driver": ["Authentication required."]})

    if getattr(driver, "role", None) != UserRole.AMBULANCE_DRIVER:
        raise serializers.ValidationError(
            {"reporting_driver": ["Only verified ambulance drivers can report emergency incidents."]}
        )

    if not driver.is_active:
        raise serializers.ValidationError({"reporting_driver": ["Reporting driver account is inactive."]})

    if not getattr(driver, "is_verified", False):
        raise serializers.ValidationError({"reporting_driver": ["Reporting driver account is not verified."]})

    # 2. Find assigned ambulance
    ambulance = Ambulance.objects.filter(assigned_driver=driver, is_active=True).first()
    if not ambulance:
        raise serializers.ValidationError(
            {"ambulance": [f"No active ambulance is currently assigned to driver '{driver.username}'."]}
        )

    # 3. Verify ambulance availability
    if not ambulance.is_available:
        raise serializers.ValidationError(
            {"ambulance": [f"Assigned ambulance '{ambulance.vehicle_number}' is currently unavailable for dispatch."]}
        )

    # 4. Validate hospital
    if not hospital_id:
        raise serializers.ValidationError({"hospital": ["Destination hospital is required."]})

    if isinstance(hospital_id, Hospital):
        hospital = hospital_id
    else:
        try:
            hospital = Hospital.objects.get(pk=hospital_id)
        except (Hospital.DoesNotExist, ValueError):
            raise serializers.ValidationError({"hospital": ["Selected destination hospital does not exist."]})

    if not hospital.is_active:
        raise serializers.ValidationError(
            {"hospital": ["Selected destination hospital is inactive or not accepting patients."]}
        )

    # 5. Generate unique incident number
    incident_number = generate_unique_incident_number()

    # 6. Transactional creation
    with transaction.atomic():
        incident = EmergencyIncident(
            incident_number=incident_number,
            reporting_driver=driver,
            ambulance=ambulance,
            hospital=hospital,
            severity=severity or IncidentSeverity.MEDIUM,
            status=IncidentStatus.REPORTED,
            description=description or "",
        )

        try:
            incident.full_clean()
        except DjangoValidationError as e:
            raise serializers.ValidationError(
                e.message_dict if hasattr(e, "message_dict") else {"non_field_errors": [str(e)]}
            )

        incident.save()

        # 7. Create nested patient if provided
        if patient_data:
            patient = Patient(
                incident=incident,
                name=patient_data.get("name") or "Unknown",
                age=patient_data.get("age"),
                gender=patient_data.get("gender") or Gender.UNKNOWN,
                blood_group=patient_data.get("blood_group", ""),
                medical_notes=patient_data.get("medical_notes", ""),
            )

            try:
                patient.full_clean()
            except DjangoValidationError as e:
                raise serializers.ValidationError(
                    {"patient": e.message_dict if hasattr(e, "message_dict") else [str(e)]}
                )

            patient.save()

        # 8. Create EmergencyEvent
        event = create_emergency_event(
            incident=incident,
            event_type=EmergencyEventType.EMERGENCY_REPORTED,
            description=f"Emergency incident {incident.incident_number} reported by driver {driver.username}.",
            payload={
                "incident_id": str(incident.id),
                "incident_number": incident.incident_number,
                "severity": incident.severity,
                "severity_display": incident.get_severity_display(),
                "status": incident.status,
                "status_display": incident.get_status_display(),
                "hospital_id": str(hospital.id),
                "hospital_name": hospital.name,
                "hospital_code": hospital.hospital_code,
                "ambulance_id": str(ambulance.id),
                "ambulance_vehicle_number": ambulance.vehicle_number,
                "reporting_driver_id": str(driver.id),
                "reporting_driver_username": driver.username,
                "description": incident.description,
            },
        )

        # 9. Create notifications for hospital staff & police
        create_notifications_for_event(
            incident=incident,
            event=event,
            title=f"New Emergency Reported: {incident.incident_number}",
            message=(
                f"Emergency incident {incident.incident_number} reported with severity "
                f"'{incident.get_severity_display()}'. Destination: {hospital.name}. "
                f"Assigned vehicle: {ambulance.vehicle_number}."
            ),
        )

    return incident


def update_emergency_status(
    incident,
    new_status: str,
    user,
) -> EmergencyIncident:
    """
    Transactional service to update the operational status of an EmergencyIncident.

    Enforces:
    1. Driver ownership: Only the authenticated reporting driver can update status.
    2. Role verification: User must have AMBULANCE_DRIVER role, be verified and active.
    3. Terminal state protection: Incidents in CLOSED or CANCELLED cannot transition or reopen.
    4. FSM validation: Transition must be allowed according to EmergencyIncident.VALID_TRANSITIONS.
    5. Concurrency safety: Row-level locking via select_for_update() inside transaction.atomic().
    6. Automatic timestamp updates: Handled by the model save() method.
    7. Lifecycle event and notification generation.
    """
    if not user or not getattr(user, "is_authenticated", False):
        raise serializers.ValidationError({"detail": "Authentication required."})

    if getattr(user, "role", None) != UserRole.AMBULANCE_DRIVER:
        raise serializers.ValidationError(
            {"detail": "Only verified ambulance drivers may update emergency incident status."}
        )

    if not user.is_active or not getattr(user, "is_verified", False):
        raise serializers.ValidationError({"detail": "Driver account is inactive or not verified."})

    incident_id = incident.pk if isinstance(incident, EmergencyIncident) else incident

    with transaction.atomic():
        try:
            locked_incident = (
                EmergencyIncident.objects.select_for_update()
                .select_related("hospital", "ambulance", "reporting_driver")
                .prefetch_related("patients")
                .get(pk=incident_id)
            )
        except (EmergencyIncident.DoesNotExist, ValueError):
            raise serializers.ValidationError({"detail": "Emergency incident not found."})

        # 1. Enforce reporting driver ownership
        if locked_incident.reporting_driver_id != user.id:
            raise serializers.ValidationError(
                {"detail": "Only the reporting driver may update the status of this incident."}
            )

        # 2. Check terminal state
        if locked_incident.status in [IncidentStatus.CLOSED, IncidentStatus.CANCELLED]:
            raise serializers.ValidationError(
                {"status": [f"Cannot update incident in terminal state '{locked_incident.status}'."]}
            )

        # 3. Check transition against FSM (excluding same-state transitions)
        allowed_transitions = [
            s for s in EmergencyIncident.VALID_TRANSITIONS.get(locked_incident.status, [])
            if s != locked_incident.status
        ]

        if new_status not in allowed_transitions:
            raise serializers.ValidationError(
                {"status": [f"Invalid status transition from '{locked_incident.status}' to '{new_status}'."]}
            )

        old_status = locked_incident.status

        if new_status == IncidentStatus.IN_TRANSIT:
            hospital_response = getattr(locked_incident, "hospital_response", None)
            police_acknowledgement = getattr(locked_incident, "police_acknowledgement", None)
            missing = []
            if not hospital_response or hospital_response.decision != "ACCEPTED":
                missing.append("hospital acceptance")
            if not police_acknowledgement:
                missing.append("police acknowledgement")
            if missing:
                raise serializers.ValidationError(
                    {"status": [f"Ambulance cannot start transit until: {', '.join(missing)}."]}
                )

        # 4. Apply status change and full_clean
        locked_incident.status = new_status
        try:
            locked_incident.full_clean()
        except DjangoValidationError as e:
            raise serializers.ValidationError(
                e.message_dict if hasattr(e, "message_dict") else {"non_field_errors": [str(e)]}
            )

        locked_incident.save()

        # 5. Determine event type
        if new_status == IncidentStatus.ARRIVED:
            event_type = EmergencyEventType.AMBULANCE_ARRIVED
        elif new_status == IncidentStatus.CANCELLED:
            event_type = EmergencyEventType.EMERGENCY_CANCELLED
        elif new_status == IncidentStatus.CLOSED:
            event_type = EmergencyEventType.EMERGENCY_CLOSED
        else:
            event_type = EmergencyEventType.STATUS_CHANGED

        # 6. Create EmergencyEvent
        event = create_emergency_event(
            incident=locked_incident,
            event_type=event_type,
            description=(
                f"Incident {locked_incident.incident_number} transitioned from "
                f"'{old_status}' to '{new_status}' by driver {user.username}."
            ),
            payload={
                "incident_id": str(locked_incident.id),
                "incident_number": locked_incident.incident_number,
                "old_status": old_status,
                "new_status": new_status,
                "new_status_display": locked_incident.get_status_display(),
                "hospital_id": str(locked_incident.hospital_id),
                "hospital_name": locked_incident.hospital.name,
                "ambulance_id": str(locked_incident.ambulance_id),
                "ambulance_vehicle_number": locked_incident.ambulance.vehicle_number,
                "driver_id": str(user.id),
            },
        )

        # 7. Create notifications for hospital staff & police
        create_notifications_for_event(
            incident=locked_incident,
            event=event,
            title=f"Incident Status Update: {locked_incident.incident_number} ({locked_incident.get_status_display()})",
            message=(
                f"Incident {locked_incident.incident_number} status changed to "
                f"'{locked_incident.get_status_display()}'. Ambulance: {locked_incident.ambulance.vehicle_number}."
            ),
        )

        # 8. Phase 7: Automatically cancel any pending traffic commands on arrival or terminal transitions
        if new_status in [IncidentStatus.ARRIVED, IncidentStatus.CLOSED, IncidentStatus.CANCELLED]:
            try:
                from apps.traffic.services import evaluate_and_match_traffic_signals
                evaluate_and_match_traffic_signals(locked_incident)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Traffic preemption cleanup skipped on status change: %s", e)

    return locked_incident


def record_ambulance_location(
    incident,
    latitude,
    longitude,
    accuracy=None,
    recorded_at=None,
    user=None,
) -> AmbulanceLocation:
    """
    Transactional service to record an ambulance GPS location update.

    Enforces:
    1. Driver validation: User must be authenticated, active, verified AMBULANCE_DRIVER.
    2. Incident ownership: User must be the reporting driver for this incident.
    3. Operational state: Incident must be active (not CLOSED or CANCELLED).
    4. Derived references: Ambulance is derived strictly from incident.ambulance.
    5. Coordinate validation: Handled via model clean().
    6. Authoritative server timestamping via transaction.atomic().
    7. EmergencyEvent generation (LOCATION_UPDATED) on every ping.
    8. Controlled/throttled notification delivery to prevent alert fatigue.
    """
    if not user or not getattr(user, "is_authenticated", False):
        raise serializers.ValidationError({"detail": "Authentication required."})

    if getattr(user, "role", None) != UserRole.AMBULANCE_DRIVER:
        raise serializers.ValidationError(
            {"detail": "Only verified ambulance drivers can submit GPS locations."}
        )

    if not user.is_active or not getattr(user, "is_verified", False):
        raise serializers.ValidationError({"detail": "Driver account is inactive or not verified."})

    # Validate ownership
    if incident.reporting_driver_id != user.id:
        raise serializers.ValidationError(
            {"detail": "Only the reporting driver can update GPS coordinates for this incident."}
        )

    # Validate active state (reject terminal states)
    if incident.status in [IncidentStatus.CLOSED, IncidentStatus.CANCELLED]:
        raise serializers.ValidationError(
            {"status": [f"Cannot update location for incident in terminal state '{incident.status}'."]}
        )

    with transaction.atomic():
        location = AmbulanceLocation(
            ambulance=incident.ambulance,
            incident=incident,
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy,
            recorded_at=recorded_at,
        )
        try:
            location.full_clean()
        except DjangoValidationError as e:
            raise serializers.ValidationError(
                e.message_dict if hasattr(e, "message_dict") else {"non_field_errors": [str(e)]}
            )
        location.save()

        # Create LOCATION_UPDATED event
        event = create_emergency_event(
            incident=incident,
            event_type=EmergencyEventType.LOCATION_UPDATED,
            description=f"Ambulance {incident.ambulance.vehicle_number} reported GPS coordinates ({latitude}, {longitude}).",
            payload={
                "incident_id": str(incident.id),
                "incident_number": incident.incident_number,
                "ambulance_id": str(incident.ambulance_id),
                "ambulance_vehicle_number": incident.ambulance.vehicle_number,
                "latitude": str(latitude),
                "longitude": str(longitude),
                "accuracy": accuracy,
                "location_id": str(location.id),
            },
        )

        # Throttled notification delivery:
        # Check if a LOCATION_UPDATED notification was already generated within the cooldown window
        throttle_cutoff = timezone.now() - timezone.timedelta(seconds=GPS_NOTIFICATION_THROTTLE_SECONDS)
        recent_notification_exists = Notification.objects.filter(
            incident=incident,
            event__event_type=EmergencyEventType.LOCATION_UPDATED,
            created_at__gte=throttle_cutoff,
        ).exists()

        if not recent_notification_exists:
            create_notifications_for_event(
                incident=incident,
                event=event,
                title=f"Ambulance Location Update: {incident.incident_number}",
                message=(
                    f"Ambulance {incident.ambulance.vehicle_number} reported new GPS coordinates "
                    f"({latitude}, {longitude})."
                ),
            )

        # Phase 7: Safely evaluate traffic preemption for approaching intersections
        try:
            from apps.traffic.services import evaluate_and_match_traffic_signals
            evaluate_and_match_traffic_signals(incident, location)
        except Exception as e:
            # Device or traffic failures must NEVER interrupt GPS ingestion
            import logging
            logging.getLogger(__name__).warning(
                "Traffic preemption matching skipped due to error: %s", e
            )

    return location


def find_nearby_hospitals(
    latitude: Union[float, Decimal, str, int],
    longitude: Union[float, Decimal, str, int],
    query: Optional[str] = None,
    max_results: int = 3,
    max_distance_km: Union[float, int] = 30,
) -> List[Dict[str, Any]]:
    """
    Read-only spatial query service to find and rank active destination hospitals
    by spherical proximity to given coordinates, with optional name filtering.

    Requirements:
    - Latitude and longitude must be valid floating point coordinates.
    - Only active hospitals with configured GPS coordinates are evaluated.
    - Filters candidate facilities using raw distance in meters before rounding.
    - distance_km is rounded to 2 decimal places in the output.
    - Results are sorted by distance ascending and capped at max_results.
    - Operates purely in-memory over Django ORM reads; no external API calls.
    """
    # 1. Validate coordinates
    if latitude is None or longitude is None:
        raise ValueError("Latitude and longitude coordinates are required.")

    try:
        lat_float = float(latitude)
        lon_float = float(longitude)
    except (ValueError, TypeError):
        raise ValueError("Invalid latitude or longitude coordinate.")

    if not (-90.0 <= lat_float <= 90.0):
        raise ValueError("Latitude must be between -90.0 and 90.0 degrees.")

    if not (-180.0 <= lon_float <= 180.0):
        raise ValueError("Longitude must be between -180.0 and 180.0 degrees.")

    # 2. Validate parameters
    try:
        max_dist_km_float = float(max_distance_km)
    except (ValueError, TypeError):
        raise ValueError("max_distance_km must be a positive number.")

    if not all(math.isfinite(value) for value in (lat_float, lon_float, max_dist_km_float)):
        raise ValueError("Coordinates and max_distance_km must be finite numbers.")

    if max_dist_km_float <= 0:
        raise ValueError("max_distance_km must be a positive number.")

    try:
        max_results_int = int(max_results)
    except (ValueError, TypeError):
        max_results_int = 3

    if max_results_int <= 0:
        max_results_int = 3

    # 3. Query active hospitals with coordinates
    qs = Hospital.objects.filter(
        is_active=True,
        latitude__isnull=False,
        longitude__isnull=False,
    )

    if query is not None:
        clean_query = str(query).strip()
        if clean_query:
            qs = qs.filter(name__icontains=clean_query)

    hospitals = list(
        qs.only(
            "id",
            "name",
            "hospital_code",
            "address",
            "contact_number",
            "latitude",
            "longitude",
            "is_active",
        )
    )

    # 4. Compute distance and filter
    max_distance_meters = max_dist_km_float * 1000.0
    candidates = []

    for hosp in hospitals:
        hosp_lat = float(hosp.latitude)
        hosp_lon = float(hosp.longitude)
        dist_meters = haversine_distance_meters(lat_float, lon_float, hosp_lat, hosp_lon)

        # Apply max_distance_km filtering using raw distance_meters before rounding
        if dist_meters > max_distance_meters:
            continue

        candidates.append({
            "id": str(hosp.id),
            "name": hosp.name,
            "hospital_code": hosp.hospital_code,
            "address": hosp.address,
            "contact_number": hosp.contact_number,
            "latitude": float(hosp.latitude),
            "longitude": float(hosp.longitude),
            "distance_km": round(dist_meters / 1000.0, 2),
            "distance_meters": round(dist_meters, 1),
            "is_active": hosp.is_active,
            "_raw_dist_meters": dist_meters,
        })

    # 5. Sort by nearest distance and limit
    candidates.sort(key=lambda x: x["_raw_dist_meters"])

    for item in candidates:
        del item["_raw_dist_meters"]

    return candidates[:max_results_int]

