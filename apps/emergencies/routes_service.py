"""
Google Maps Routes API v2 Integration Service for SERTOS Emergencies application.

Implements:
1. GoogleRoutesClient: Lightweight HTTP client for Google Routes API v2 using urllib.request.
2. Route duration and distance parser (converts Google duration strings like '1020s' to seconds and human-readable minutes).
3. haversine_distance_meters: Pure-Python spherical distance calculation between coordinates.
4. get_incident_route_and_eta: Intelligent, movement-based route resolution between latest ambulance GPS and destination hospital with:
   - Dual-condition throttling (cooldown + movement threshold).
   - Fallback recalculation (180s cooldown with >= 50m movement).
   - Distributed cache locking to prevent duplicate concurrent API requests.
   - Stale route retention on upstream Google failure.
5. get_cached_route_summary: Lightweight cache-only summary for Hospital and Police dashboards.
6. Error hierarchy for missing coordinates, unconfigured API keys, and upstream failures.

PRODUCTION CACHING ARCHITECTURE NOTE:
- Django defaults to django.core.cache.backends.locmem.LocMemCache if CACHES is unconfigured in settings.py.
- LocMemCache is strictly process-local (per-Python-process memory) and is intended ONLY for development and single-process automated testing.
- LocMemCache does NOT provide shared caching across multiple Gunicorn/Uvicorn worker processes or distributed container instances in production.
- For production multi-worker deployment, configure a production-grade distributed cache backend such as Redis (django.core.cache.backends.redis.RedisCache or django-redis) or Memcached in settings.py CACHES.
"""

import json
import logging
import math
import os
import socket
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

DEFAULT_ROUTES_ENDPOINT = "https://routes.googleapis.com/directions/v2:computeRoutes"
DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_FIELD_MASK = "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline,routes.description"

# Movement and Throttling Thresholds (Phase 6)
ROUTE_MIN_MOVEMENT_METERS = 250
ROUTE_RECALCULATION_COOLDOWN_SECONDS = 60
ROUTE_FALLBACK_COOLDOWN_SECONDS = 180
ROUTE_FALLBACK_MIN_MOVEMENT_METERS = 50

# Cache Keys and TTLs
ROUTE_CACHE_KEY_PREFIX = "sertos:route:"
ROUTE_LOCK_KEY_PREFIX = "sertos:route:lock:"
ROUTE_CACHE_TTL_SECONDS = 3600  # 1 hour
ROUTE_LOCK_TIMEOUT_SECONDS = 10  # 10 seconds max lock hold


class RouteServiceError(Exception):
    """Base exception for route and ETA computation failures."""

    def __init__(self, message: str, code: str = "route_error", status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class MissingCoordinatesError(RouteServiceError):
    """Raised when origin or destination coordinates are unavailable."""

    def __init__(self, message: str):
        super().__init__(message, code="missing_coordinates", status_code=400)


class MissingConfigurationError(RouteServiceError):
    """Raised when the Google Maps API key is missing or unconfigured."""

    def __init__(self, message: str = "Google Maps API key is not configured on the server."):
        super().__init__(message, code="missing_configuration", status_code=503)


class GoogleRoutesAPIError(RouteServiceError):
    """Raised when the upstream Google Routes API fails, times out, or returns an error."""

    def __init__(self, message: str, status_code: int = 502, code: str = "google_api_error"):
        super().__init__(message, code=code, status_code=status_code)


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance between two GPS coordinates in meters
    using the Haversine formula on a spherical Earth (mean radius = 6,371,000 m).

    Parameters:
        lat1, lon1: First coordinate in decimal degrees.
        lat2, lon2: Second coordinate in decimal degrees.

    Returns:
        Distance in meters as float.
    """
    if lat1 == lat2 and lon1 == lon2:
        return 0.0

    r = 6371000.0  # Earth radius in meters
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    delta_phi = math.radians(float(lat2) - float(lat1))
    delta_lambda = math.radians(float(lon2) - float(lon1))

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    )
    # Clamp to avoid floating point precision issues outside [0.0, 1.0]
    a = min(1.0, max(0.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return r * c


@contextmanager
def acquire_route_lock(incident_id: Any, timeout: int = ROUTE_LOCK_TIMEOUT_SECONDS):
    """
    Context manager for distributed cache lock per emergency incident.
    Uses cache.add() which is atomic across all Django cache backends.

    Yields True if lock acquired, False otherwise.
    """
    lock_key = f"{ROUTE_LOCK_KEY_PREFIX}{incident_id}"
    acquired = cache.add(lock_key, "locked", timeout=timeout)
    try:
        yield acquired
    finally:
        if acquired:
            try:
                cache.delete(lock_key)
            except Exception as exc:
                logger.warning("Failed to release route lock for incident %s: %s", incident_id, exc)


def parse_duration_to_seconds(duration_str: str) -> int:
    """
    Parses Google's duration string (e.g. '1020s', '45s', '1020.5s') into integer seconds.
    """
    if not duration_str or not isinstance(duration_str, str):
        return 0
    clean = duration_str.strip().rstrip("sS")
    try:
        return int(round(float(clean)))
    except (ValueError, TypeError):
        return 0


def format_duration(seconds: int) -> str:
    """
    Formats duration in seconds into a human-readable minutes value.
    Examples:
        1020 -> '17 mins'
        60 -> '1 min'
        120 -> '2 mins'
        30 -> '1 min'
        10 -> '< 1 min'
        0 -> '0 mins'
    """
    if seconds <= 0:
        return "0 mins"
    minutes = int((seconds + 30) // 60)
    if minutes == 0:
        return "< 1 min"
    if minutes == 1:
        return "1 min"
    return f"{minutes} mins"


class GoogleRoutesClient:
    """
    Lightweight, production-hardened client for Google Maps Routes API v2 (computeRoutes).
    Uses Python's standard library urllib.request to avoid external dependency overhead.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        if api_key is not None:
            self.api_key = api_key
        else:
            self.api_key = getattr(settings, "GOOGLE_MAPS_API_KEY", "") or os.getenv("GOOGLE_MAPS_API_KEY", "")
        self.endpoint = endpoint or getattr(settings, "GOOGLE_MAPS_ROUTES_ENDPOINT", DEFAULT_ROUTES_ENDPOINT)
        self.timeout = timeout if timeout is not None else getattr(settings, "GOOGLE_MAPS_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)

    def compute_route(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
    ) -> Dict[str, Any]:
        """
        Executes a POST request to Google Routes API v2 computeRoutes.
        Returns parsed route metrics: distance_meters, duration_seconds, duration_formatted, polyline.
        """
        if not self.api_key:
            raise MissingConfigurationError("Google Maps API key is not configured on the server.")

        payload = {
            "origin": {
                "location": {
                    "latLng": {
                        "latitude": float(origin_lat),
                        "longitude": float(origin_lng),
                    }
                }
            },
            "destination": {
                "location": {
                    "latLng": {
                        "latitude": float(dest_lat),
                        "longitude": float(dest_lng),
                    }
                }
            },
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
            "computeAlternativeRoutes": False,
            "units": "METRIC",
        }

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": DEFAULT_FIELD_MASK,
        }

        req_body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.endpoint, data=req_body, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                status_code = response.getcode()
                response_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            err_msg = f"HTTP {exc.code}"
            try:
                err_content = exc.read().decode("utf-8")
                parsed_err = json.loads(err_content)
                if "error" in parsed_err and "message" in parsed_err["error"]:
                    err_msg = parsed_err["error"]["message"]
            except Exception:
                pass
            logger.warning("Google Routes API HTTP error: %s (%d)", err_msg, exc.code)
            raise GoogleRoutesAPIError(
                f"Google Routes API request failed ({exc.code}): {err_msg}",
                status_code=502,
                code="google_api_http_error",
            )
        except (urllib.error.URLError, socket.timeout, TimeoutError) as exc:
            logger.warning("Google Routes API timeout or network error: %s", str(exc))
            raise GoogleRoutesAPIError(
                "Google Routes API connection timed out or failed.",
                status_code=504,
                code="google_api_timeout",
            )
        except Exception as exc:
            logger.error("Unexpected error contacting Google Routes API: %s", str(exc))
            raise GoogleRoutesAPIError(
                f"Unexpected error communicating with Google Routes API: {str(exc)}",
                status_code=502,
                code="google_api_unknown_error",
            )

        try:
            data = json.loads(response_body)
        except json.JSONDecodeError:
            raise GoogleRoutesAPIError(
                "Google Routes API returned an invalid JSON response.",
                status_code=502,
                code="google_api_invalid_json",
            )

        routes = data.get("routes")
        if not routes or not isinstance(routes, list) or len(routes) == 0:
            raise GoogleRoutesAPIError(
                "No route could be calculated between the specified coordinates.",
                status_code=404,
                code="no_route_found",
            )

        first_route = routes[0]
        distance_meters = int(first_route.get("distanceMeters", 0))
        duration_str = first_route.get("duration", "0s")
        duration_seconds = parse_duration_to_seconds(duration_str)
        polyline = first_route.get("polyline", {}).get("encodedPolyline", "")

        return {
            "distance_meters": distance_meters,
            "duration_seconds": duration_seconds,
            "duration_formatted": format_duration(duration_seconds),
            "polyline": polyline,
        }


def get_incident_route_and_eta(
    incident,
    client: Optional[GoogleRoutesClient] = None,
    force_recalculate: bool = False,
) -> Dict[str, Any]:
    """
    Calculates or retrieves live road route and estimated time of arrival (ETA) for an emergency incident:
    - Origin: Authoritative latest saved AmbulanceLocation breadcrumb for the incident.
    - Destination: Geographic coordinates of the incident's assigned hospital.
    - Throttling & Caching:
      1. Primary condition: Recalculates if >= 60 seconds elapsed AND ambulance moved >= 250 meters.
      2. Fallback condition: Recalculates if >= 180 seconds elapsed AND ambulance moved >= 50 meters.
      3. If conditions not met: Returns cached route with refreshed estimated arrival time.
      4. Stale route retention: If Google API fails/times out, retains last successful route with is_stale=True.
      5. Concurrency protection: Incident-scoped cache lock prevents duplicate upstream requests.

    Guarantees:
    - Never called within an open database transaction.
    - Never uses hardcoded or fallback coordinates.
    - Fails fast with clear descriptive error if coordinates, hospital, or GPS breadcrumbs are missing.
    """
    # 1. Validate destination hospital
    hospital = incident.hospital
    if not hospital:
        raise MissingCoordinatesError("Destination hospital is not assigned to this emergency incident.")

    if hospital.latitude is None or hospital.longitude is None:
        raise MissingCoordinatesError(
            f"Destination hospital '{hospital.name}' does not have valid GPS coordinates."
        )

    # 2. Validate latest ambulance GPS breadcrumb
    latest_location = incident.locations.order_by("-server_received_at", "-id").first()
    if not latest_location:
        raise MissingCoordinatesError(
            f"No ambulance GPS location recorded for incident '{incident.incident_number}'."
        )

    if latest_location.latitude is None or latest_location.longitude is None:
        raise MissingCoordinatesError(
            f"Latest ambulance GPS location for incident '{incident.incident_number}' lacks valid coordinates."
        )

    origin_lat = float(latest_location.latitude)
    origin_lng = float(latest_location.longitude)
    dest_lat = float(hospital.latitude)
    dest_lng = float(hospital.longitude)

    cache_key = f"{ROUTE_CACHE_KEY_PREFIX}{incident.id}"
    cached_route = cache.get(cache_key)
    now = timezone.now()

    # 3. Check if cached route exists and whether recalculation conditions are met
    should_recalculate = True

    if cached_route and not force_recalculate:
        cached_origin = cached_route.get("origin", {})
        cached_dest = cached_route.get("destination", {})

        # If hospital destination changed, always recalculate
        dest_changed = (
            cached_dest.get("latitude") != dest_lat or cached_dest.get("longitude") != dest_lng
        )

        if not dest_changed:
            distance_moved = haversine_distance_meters(
                cached_origin.get("latitude", 0.0),
                cached_origin.get("longitude", 0.0),
                origin_lat,
                origin_lng,
            )

            last_calc_raw = cached_route.get("last_calculated_at")
            if last_calc_raw:
                if isinstance(last_calc_raw, str):
                    try:
                        last_calc_dt = datetime.fromisoformat(last_calc_raw)
                    except (ValueError, TypeError):
                        last_calc_dt = now
                elif isinstance(last_calc_raw, datetime):
                    last_calc_dt = last_calc_raw
                else:
                    last_calc_dt = now

                if last_calc_dt.tzinfo is None:
                    last_calc_dt = timezone.make_aware(last_calc_dt)

                elapsed_seconds = (now - last_calc_dt).total_seconds()
            else:
                elapsed_seconds = float("inf")

            # Condition 1: Normal movement recalculation (>= 60s cooldown AND >= 250m movement)
            normal_met = (
                elapsed_seconds >= ROUTE_RECALCULATION_COOLDOWN_SECONDS
                and distance_moved >= ROUTE_MIN_MOVEMENT_METERS
            )

            # Condition 2: Fallback recalculation (>= 180s fallback cooldown AND >= 50m movement)
            fallback_met = (
                elapsed_seconds >= ROUTE_FALLBACK_COOLDOWN_SECONDS
                and distance_moved >= ROUTE_FALLBACK_MIN_MOVEMENT_METERS
            )

            if not normal_met and not fallback_met:
                should_recalculate = False

    # 4. If recalculation is not required, return cached route with dynamic ETA
    if not should_recalculate and cached_route:
        cached_copy = dict(cached_route)
        duration_sec = cached_copy.get("duration_seconds", 0)
        cached_copy["estimated_arrival"] = (now + timedelta(seconds=duration_sec)).isoformat()
        return cached_copy

    # 5. Execute route calculation with Google Routes API v2 under concurrency lock
    with acquire_route_lock(incident.id) as lock_acquired:
        if not lock_acquired:
            logger.info("Route calculation lock held for incident %s; checking cache.", incident.id)
            current_cached = cache.get(cache_key)
            if current_cached:
                cached_copy = dict(current_cached)
                duration_sec = cached_copy.get("duration_seconds", 0)
                cached_copy["estimated_arrival"] = (now + timedelta(seconds=duration_sec)).isoformat()
                return cached_copy

            # Wait briefly for lock holder to populate cache
            for _ in range(20):
                time.sleep(0.1)
                current_cached = cache.get(cache_key)
                if current_cached:
                    cached_copy = dict(current_cached)
                    duration_sec = cached_copy.get("duration_seconds", 0)
                    cached_copy["estimated_arrival"] = (
                        timezone.now() + timedelta(seconds=duration_sec)
                    ).isoformat()
                    return cached_copy

        # Call Google Routes API
        routes_client = client or GoogleRoutesClient()
        try:
            route_metrics = routes_client.compute_route(
                origin_lat=origin_lat,
                origin_lng=origin_lng,
                dest_lat=dest_lat,
                dest_lng=dest_lng,
            )
        except Exception as exc:
            # If Google API call fails and we have a previously cached route, retain it with is_stale=True
            prior_route = cache.get(cache_key)
            if prior_route:
                logger.warning(
                    "Google Routes API call failed for incident %s (%s); retaining prior route with is_stale=True.",
                    incident.id,
                    str(exc),
                )
                prior_copy = dict(prior_route)
                prior_copy["is_stale"] = True
                duration_sec = prior_copy.get("duration_seconds", 0)
                prior_copy["estimated_arrival"] = (now + timedelta(seconds=duration_sec)).isoformat()
                cache.set(cache_key, prior_copy, timeout=ROUTE_CACHE_TTL_SECONDS)
                return prior_copy

            # No prior route exists to fall back to: propagate error to caller
            raise exc

        # Success! Assemble complete route data
        duration_seconds = route_metrics["duration_seconds"]
        estimated_arrival = now + timedelta(seconds=duration_seconds)
        distance_meters = route_metrics["distance_meters"]

        route_data = {
            "incident_id": str(incident.id),
            "incident_number": incident.incident_number,
            "origin": {
                "latitude": origin_lat,
                "longitude": origin_lng,
            },
            "destination": {
                "latitude": dest_lat,
                "longitude": dest_lng,
                "hospital_name": hospital.name,
            },
            "distance_meters": distance_meters,
            "distance_km": round(distance_meters / 1000.0, 2),
            "duration_seconds": duration_seconds,
            "duration_formatted": route_metrics["duration_formatted"],
            "estimated_arrival": estimated_arrival.isoformat(),
            "polyline": route_metrics["polyline"],
            "is_stale": False,
            "last_calculated_at": now.isoformat(),
        }

        cache.set(cache_key, route_data, timeout=ROUTE_CACHE_TTL_SECONDS)
        return route_data


def get_cached_route_summary(incident_id: Any) -> Optional[Dict[str, Any]]:
    """
    Retrieves a lightweight route summary for an emergency incident strictly from cache.
    Guaranteed NEVER to invoke Google Routes API or execute database queries.
    Returns None if no cached route exists.
    """
    cache_key = f"{ROUTE_CACHE_KEY_PREFIX}{incident_id}"
    cached = cache.get(cache_key)
    if not cached or not isinstance(cached, dict):
        return None

    # Verify cached route has necessary metrics
    if "distance_km" not in cached or "duration_formatted" not in cached:
        return None

    now = timezone.now()
    duration_sec = cached.get("duration_seconds", 0)
    estimated_arrival = (now + timedelta(seconds=duration_sec)).isoformat()

    return {
        "distance_km": cached.get("distance_km"),
        "duration_formatted": cached.get("duration_formatted"),
        "estimated_arrival": estimated_arrival,
        "is_stale": bool(cached.get("is_stale", False)),
        "last_calculated_at": cached.get("last_calculated_at"),
    }
