"""
Voice AI Emergency Agent Safe Tool Implementations (Phase 8.1.2).

Provides wrappers for:
1. find_nearby_hospitals: Proximity-based hospital search.
2. get_route_eta: Safe route summary and ETA query with cache prioritization.
3. get_emergency_status: Active incident resolution, status, and patient triage details.

Guarantees:
- Never executes direct database writes.
- Never bypasses existing emergency domain services.
- Never triggers unnecessary upstream Google Routes API calls.
- Enforces strict ownership checks on emergency incidents.
"""

import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from apps.emergencies.models import (
    AmbulanceLocation,
    EmergencyIncident,
    IncidentStatus,
)
from apps.emergencies.routes_service import (
    RouteServiceError,
    get_cached_route_summary,
    get_incident_route_and_eta,
)
from apps.emergencies.services import find_nearby_hospitals
from .registry import registry


def _resolve_driver_incident(user: Any, incident_id: Optional[str] = None) -> Optional[EmergencyIncident]:
    """
    Resolves an EmergencyIncident for the authenticated driver:
    - If incident_id is given (UUID or incident_number):
      Verifies that user is the reporting_driver. Raises PermissionError if owned by another driver.
    - If incident_id is omitted:
      Returns the driver's current active incident (not CLOSED or CANCELLED).
    """
    if incident_id:
        clean_id = str(incident_id).strip()
        incident = None

        # Try UUID lookup
        try:
            parsed_uuid = uuid.UUID(clean_id)
            incident = (
                EmergencyIncident.objects.filter(pk=parsed_uuid)
                .select_related("hospital", "ambulance")
                .prefetch_related("patients")
                .first()
            )
        except (ValueError, AttributeError):
            pass

        # Try incident_number lookup if not found by UUID
        if not incident:
            incident = (
                EmergencyIncident.objects.filter(incident_number=clean_id)
                .select_related("hospital", "ambulance")
                .prefetch_related("patients")
                .first()
            )

        if not incident:
            raise ValueError(f"Emergency incident '{clean_id}' not found.")

        # Enforce driver ownership
        if incident.reporting_driver_id != user.id:
            raise PermissionError("Access denied: You are not the reporting driver for this incident.")

        return incident

    # Default to active emergency (not CLOSED or CANCELLED)
    return (
        EmergencyIncident.objects.filter(reporting_driver=user)
        .exclude(status__in=[IncidentStatus.CLOSED, IncidentStatus.CANCELLED])
        .select_related("hospital", "ambulance")
        .prefetch_related("patients")
        .order_by("-created_at")
        .first()
    )


# -------------------------------------------------------------------------
# Tool 1: find_nearby_hospitals
# -------------------------------------------------------------------------

FIND_NEARBY_HOSPITALS_SCHEMA = {
    "type": "object",
    "properties": {
        "latitude": {
            "type": "number",
            "description": "Ambulance latitude in decimal degrees (-90.0 to 90.0).",
        },
        "longitude": {
            "type": "number",
            "description": "Ambulance longitude in decimal degrees (-180.0 to 180.0).",
        },
        "query": {
            "type": "string",
            "description": "Optional hospital name or keyword filter (case-insensitive).",
        },
        "max_results": {
            "type": "integer",
            "default": 3,
            "description": "Maximum number of candidate hospitals to return (default: 3).",
        },
        "max_distance_km": {
            "type": "number",
            "default": 30,
            "description": "Maximum search radius in kilometers (default: 30 km).",
        },
    },
    "required": ["latitude", "longitude"],
}


@registry.register(
    name="find_nearby_hospitals",
    description="Search and rank nearby active hospitals by spherical distance from given GPS coordinates.",
    parameters_schema=FIND_NEARBY_HOSPITALS_SCHEMA,
)
def tool_find_nearby_hospitals(
    user: Any,
    latitude: Optional[Union[float, Decimal, str, int]] = None,
    longitude: Optional[Union[float, Decimal, str, int]] = None,
    query: Optional[str] = None,
    max_results: int = 3,
    max_distance_km: Union[float, int] = 30,
    **kwargs,
) -> Dict[str, Any]:
    """Wraps find_nearby_hospitals domain service for the Voice AI Agent."""
    if latitude is None or longitude is None:
        raise ValueError("Latitude and longitude coordinates are required.")

    hospitals = find_nearby_hospitals(
        latitude=latitude,
        longitude=longitude,
        query=query,
        max_results=max_results,
        max_distance_km=max_distance_km,
    )

    return {
        "hospitals": hospitals,
        "count": len(hospitals),
        "search_origin": {
            "latitude": float(latitude),
            "longitude": float(longitude),
        },
        "query": query.strip() if query else None,
    }


# -------------------------------------------------------------------------
# Tool 2: get_route_eta
# -------------------------------------------------------------------------

GET_ROUTE_ETA_SCHEMA = {
    "type": "object",
    "properties": {
        "incident_id": {
            "type": "string",
            "description": "Optional UUID or tracking code (e.g. INC-20261121-XXXX). Defaults to driver's active emergency.",
        },
        "force_recalculate": {
            "type": "boolean",
            "default": False,
            "description": "Force live route recalculation with Google Routes API if cooldown/movement permits.",
        },
    },
}


@registry.register(
    name="get_route_eta",
    description="Retrieve cached route summary and ETA to destination hospital for the driver's emergency incident.",
    parameters_schema=GET_ROUTE_ETA_SCHEMA,
)
def tool_get_route_eta(
    user: Any,
    incident_id: Optional[str] = None,
    force_recalculate: bool = False,
    **kwargs,
) -> Dict[str, Any]:
    """Safely retrieves route and ETA metrics, prioritizing cached data to avoid paid API calls."""
    incident = _resolve_driver_incident(user=user, incident_id=incident_id)
    if not incident:
        return {
            "has_active_emergency": False,
            "incident_id": None,
            "incident_number": None,
            "route_summary": None,
            "message": "No active emergency found for driver.",
        }

    # 1. Check cache first (zero external cost, < 2ms latency)
    cached_summary = get_cached_route_summary(incident.id)

    # 2. If cached route exists and force_recalculate is False, return immediately
    if cached_summary and not force_recalculate:
        return {
            "has_active_emergency": True,
            "incident_id": str(incident.id),
            "incident_number": incident.incident_number,
            "destination_hospital": {
                "id": str(incident.hospital.id),
                "name": incident.hospital.name,
            },
            "route_summary": cached_summary,
            "source": "cache",
        }

    # 3. If cache is empty or force_recalculate requested, verify GPS location availability
    has_location = AmbulanceLocation.objects.filter(incident=incident).exists()
    if not has_location:
        return {
            "has_active_emergency": True,
            "incident_id": str(incident.id),
            "incident_number": incident.incident_number,
            "destination_hospital": {
                "id": str(incident.hospital.id),
                "name": incident.hospital.name,
            },
            "route_summary": cached_summary,
            "source": "cache" if cached_summary else "none",
            "message": "Ambulance GPS location has not been recorded yet. Live route cannot be computed.",
        }

    # 4. Attempt route calculation through domain service (governed by movement & lock throttling)
    try:
        route_data = get_incident_route_and_eta(
            incident=incident,
            force_recalculate=force_recalculate,
        )
        return {
            "has_active_emergency": True,
            "incident_id": str(incident.id),
            "incident_number": incident.incident_number,
            "destination_hospital": {
                "id": str(incident.hospital.id),
                "name": incident.hospital.name,
            },
            "route_summary": {
                "distance_km": route_data.get("distance_km"),
                "duration_formatted": route_data.get("duration_formatted"),
                "estimated_arrival": route_data.get("estimated_arrival"),
                "is_stale": bool(route_data.get("is_stale", False)),
                "last_calculated_at": route_data.get("last_calculated_at"),
            },
            "source": "cached" if route_data.get("is_cached") else "calculated",
        }
    except RouteServiceError as exc:
        fallback_summary = get_cached_route_summary(incident.id)
        return {
            "has_active_emergency": True,
            "incident_id": str(incident.id),
            "incident_number": incident.incident_number,
            "destination_hospital": {
                "id": str(incident.hospital.id),
                "name": incident.hospital.name,
            },
            "route_summary": fallback_summary,
            "source": "stale_cache" if fallback_summary else "none",
            "message": f"Route calculation unavailable: {exc.message}",
        }


# -------------------------------------------------------------------------
# Tool 3: get_emergency_status
# -------------------------------------------------------------------------

GET_EMERGENCY_STATUS_SCHEMA = {
    "type": "object",
    "properties": {
        "incident_id": {
            "type": "string",
            "description": "Optional UUID or tracking number of the incident. Defaults to driver's active emergency.",
        },
    },
}


@registry.register(
    name="get_emergency_status",
    description="Retrieve status, destination hospital, ambulance details, and patient triage info for the driver's emergency.",
    parameters_schema=GET_EMERGENCY_STATUS_SCHEMA,
)
def tool_get_emergency_status(
    user: Any,
    incident_id: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Retrieves full operational status and triage data for an authorized driver's emergency."""
    incident = _resolve_driver_incident(user=user, incident_id=incident_id)
    if not incident:
        return {
            "has_active_emergency": False,
            "incident": None,
            "message": "No active emergency found for driver.",
        }

    patient = incident.patients.first()

    return {
        "has_active_emergency": True,
        "incident": {
            "id": str(incident.id),
            "incident_number": incident.incident_number,
            "status": incident.status,
            "status_display": incident.get_status_display(),
            "severity": incident.severity,
            "severity_display": incident.get_severity_display(),
            "description": incident.description,
            "hospital": {
                "id": str(incident.hospital.id),
                "name": incident.hospital.name,
                "hospital_code": incident.hospital.hospital_code,
                "address": incident.hospital.address,
                "contact_number": incident.hospital.contact_number,
            },
            "ambulance": {
                "id": str(incident.ambulance.id),
                "vehicle_number": incident.ambulance.vehicle_number,
                "vehicle_type": incident.ambulance.vehicle_type,
            },
            "patient": {
                "name": patient.name,
                "age": patient.age,
                "gender": patient.gender,
                "blood_group": patient.blood_group,
                "medical_notes": patient.medical_notes,
            } if patient else None,
            "created_at": incident.created_at.isoformat(),
            "assigned_at": incident.assigned_at.isoformat() if incident.assigned_at else None,
            "in_transit_at": incident.in_transit_at.isoformat() if incident.in_transit_at else None,
            "arrived_at": incident.arrived_at.isoformat() if incident.arrived_at else None,
            "closed_at": incident.closed_at.isoformat() if incident.closed_at else None,
            "cancelled_at": incident.cancelled_at.isoformat() if incident.cancelled_at else None,
        },
    }
