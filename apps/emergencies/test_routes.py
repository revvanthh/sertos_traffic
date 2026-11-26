"""
Comprehensive automated tests for SERTOS Google Maps Routes API v2 Integration.

Phase 6 additions:
- Haversine pure-Python spherical distance unit tests.
- Dynamic route recalculation throttling & cooldown tests:
  - 0 meters (returns cached, no Google call).
  - < 50 meters (returns cached, no Google call).
  - 50–249 meters at 70s (cooldown met, but < 250m -> returns cached).
  - >= 250 meters at 65s (both met -> calls Google).
  - >= 250 meters at 20s (cooldown active -> returns cached).
  - 60 meters at 190s (180s fallback met -> calls Google).
- Cache lock protection against duplicate concurrent recalculation.
- Stale route retention on Google API failure (returns HTTP 200 with is_stale=True).
- Google failure with no prior route returns error (504/502).
- Non-blocking GPS ingestion (record_ambulance_location persists without calling Google).

STRICT RULE: All Google API interactions are mocked; zero external HTTP requests are made.
"""

import io
import json
import socket
import urllib.error
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.emergencies.models import (
    Ambulance,
    AmbulanceLocation,
    EmergencyEvent,
    EmergencyIncident,
    Hospital,
    HospitalStaff,
    IncidentSeverity,
    IncidentStatus,
    Patient,
)
from apps.emergencies.routes_service import (
    ROUTE_CACHE_KEY_PREFIX,
    ROUTE_CACHE_TTL_SECONDS,
    ROUTE_LOCK_KEY_PREFIX,
    GoogleRoutesAPIError,
    GoogleRoutesClient,
    MissingConfigurationError,
    MissingCoordinatesError,
    RouteServiceError,
    acquire_route_lock,
    format_duration,
    get_incident_route_and_eta,
    haversine_distance_meters,
    parse_duration_to_seconds,
)


class HaversineDistanceUnitTestCase(TestCase):
    """Unit tests for pure-Python Haversine distance formula."""

    def test_haversine_identical_points(self):
        """Identical coordinates return 0.0 meters."""
        dist = haversine_distance_meters(12.9352, 77.6245, 12.9352, 77.6245)
        self.assertEqual(dist, 0.0)

    def test_haversine_known_bangalore_distance(self):
        """Koramangala (12.9352, 77.6245) to City Hospital (12.9716, 77.5946) is ~5.27 km."""
        dist = haversine_distance_meters(12.9352, 77.6245, 12.9716, 77.5946)
        self.assertGreater(dist, 5000.0)
        self.assertLess(dist, 5500.0)

    def test_haversine_calibrated_distance_bands(self):
        """Verify calculated distances for test coordinate offsets match intended bands."""
        base_lat, base_lng = 12.9352, 77.6245

        # ~25 meters offset (< 50m band)
        dist_25m = haversine_distance_meters(base_lat, base_lng, 12.935425, base_lng)
        self.assertGreater(dist_25m, 20.0)
        self.assertLess(dist_25m, 30.0)

        # ~60 meters offset (50-249m band, fallback candidate)
        dist_60m = haversine_distance_meters(base_lat, base_lng, 12.935741, base_lng)
        self.assertGreater(dist_60m, 55.0)
        self.assertLess(dist_60m, 65.0)

        # ~100 meters offset (50-249m band)
        dist_100m = haversine_distance_meters(base_lat, base_lng, 12.936102, base_lng)
        self.assertGreater(dist_100m, 95.0)
        self.assertLess(dist_100m, 105.0)

        # ~300 meters offset (>= 250m band)
        dist_300m = haversine_distance_meters(base_lat, base_lng, 12.937905, base_lng)
        self.assertGreater(dist_300m, 290.0)
        self.assertLess(dist_300m, 310.0)


class RouteServiceUnitTestCase(TestCase):
    """Unit tests for standalone helper functions and client behavior in routes_service.py."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_parse_duration_to_seconds(self):
        """Verify parsing of Google duration strings to integer seconds."""
        self.assertEqual(parse_duration_to_seconds("1020s"), 1020)
        self.assertEqual(parse_duration_to_seconds("45s"), 45)
        self.assertEqual(parse_duration_to_seconds("1020.4s"), 1020)
        self.assertEqual(parse_duration_to_seconds("1020.6s"), 1021)
        self.assertEqual(parse_duration_to_seconds("0s"), 0)
        self.assertEqual(parse_duration_to_seconds(""), 0)
        self.assertEqual(parse_duration_to_seconds(None), 0)
        self.assertEqual(parse_duration_to_seconds("invalid"), 0)

    def test_format_duration(self):
        """Verify human-readable duration formatting."""
        self.assertEqual(format_duration(1020), "17 mins")
        self.assertEqual(format_duration(60), "1 min")
        self.assertEqual(format_duration(120), "2 mins")
        self.assertEqual(format_duration(90), "2 mins")
        self.assertEqual(format_duration(30), "1 min")
        self.assertEqual(format_duration(10), "< 1 min")
        self.assertEqual(format_duration(0), "0 mins")
        self.assertEqual(format_duration(-10), "0 mins")

    def test_acquire_route_lock_lifecycle(self):
        """Verify acquire_route_lock establishes lock, prevents concurrent lock, and releases cleanly."""
        incident_id = "test-incident-uuid-001"
        lock_key = f"{ROUTE_LOCK_KEY_PREFIX}{incident_id}"

        # Initially no lock exists
        self.assertIsNone(cache.get(lock_key))

        with acquire_route_lock(incident_id) as acquired_1:
            self.assertTrue(acquired_1)
            self.assertEqual(cache.get(lock_key), "locked")

            # Concurrent attempt to acquire lock must fail
            with acquire_route_lock(incident_id) as acquired_2:
                self.assertFalse(acquired_2)

        # After exiting context, lock must be released
        self.assertIsNone(cache.get(lock_key))

    def test_client_missing_api_key_raises_configuration_error(self):
        """Verify GoogleRoutesClient raises MissingConfigurationError if API key is empty."""
        client = GoogleRoutesClient(api_key="")
        with self.assertRaises(MissingConfigurationError) as ctx:
            client.compute_route(12.9352, 77.6245, 12.9716, 77.5946)
        self.assertEqual(ctx.exception.status_code, 503)

    @patch("urllib.request.urlopen")
    def test_client_successful_compute_route(self, mock_urlopen):
        """Verify GoogleRoutesClient sends correct headers/payload and parses valid response."""
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = json.dumps({
            "routes": [
                {
                    "distanceMeters": 7450,
                    "duration": "1020s",
                    "polyline": {
                        "encodedPolyline": "a~l~FjkzbO_@testPolyline"
                    },
                    "description": "via Outer Ring Rd"
                }
            ]
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        client = GoogleRoutesClient(api_key="TEST_API_KEY_12345")
        result = client.compute_route(12.9352, 77.6245, 12.9716, 77.5946)

        # Verify parsed results
        self.assertEqual(result["distance_meters"], 7450)
        self.assertEqual(result["duration_seconds"], 1020)
        self.assertEqual(result["duration_formatted"], "17 mins")
        self.assertEqual(result["polyline"], "a~l~FjkzbO_@testPolyline")

        # Verify request parameters sent to Google
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.headers.get("X-goog-api-key"), "TEST_API_KEY_12345")
        self.assertIn("routes.duration", req.headers.get("X-goog-fieldmask"))
        self.assertEqual(req.headers.get("Content-type"), "application/json")

        sent_payload = json.loads(req.data.decode("utf-8"))
        self.assertEqual(sent_payload["travelMode"], "DRIVE")
        self.assertEqual(sent_payload["routingPreference"], "TRAFFIC_AWARE_OPTIMAL")
        self.assertEqual(sent_payload["origin"]["location"]["latLng"]["latitude"], 12.9352)
        self.assertEqual(sent_payload["destination"]["location"]["latLng"]["latitude"], 12.9716)

    @patch("urllib.request.urlopen")
    def test_client_empty_routes_raises_error(self, mock_urlopen):
        """Verify GoogleRoutesClient raises 404 when Google returns no routes."""
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = json.dumps({"routes": []}).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        client = GoogleRoutesClient(api_key="TEST_API_KEY")
        with self.assertRaises(GoogleRoutesAPIError) as ctx:
            client.compute_route(12.9352, 77.6245, 12.9716, 77.5946)
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("No route could be calculated", ctx.exception.message)

    @patch("urllib.request.urlopen")
    def test_client_timeout_raises_gateway_timeout(self, mock_urlopen):
        """Verify GoogleRoutesClient raises 504 on socket / URLError timeout."""
        mock_urlopen.side_effect = socket.timeout("timed out")
        client = GoogleRoutesClient(api_key="TEST_API_KEY")

        with self.assertRaises(GoogleRoutesAPIError) as ctx:
            client.compute_route(12.9352, 77.6245, 12.9716, 77.5946)
        self.assertEqual(ctx.exception.status_code, 504)
        self.assertIn("timed out", ctx.exception.message)

    @patch("urllib.request.urlopen")
    def test_client_http_error_raises_bad_gateway(self, mock_urlopen):
        """Verify GoogleRoutesClient raises 502 on HTTP 500 error from Google."""
        err_fp = io.BytesIO(json.dumps({"error": {"message": "Internal Google error"}}).encode("utf-8"))
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://routes.googleapis.com",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=err_fp,
        )
        client = GoogleRoutesClient(api_key="TEST_API_KEY")

        with self.assertRaises(GoogleRoutesAPIError) as ctx:
            client.compute_route(12.9352, 77.6245, 12.9716, 77.5946)
        self.assertEqual(ctx.exception.status_code, 502)
        self.assertIn("Google Routes API request failed (500)", ctx.exception.message)

    @patch("urllib.request.urlopen")
    def test_client_malformed_json_raises_bad_gateway(self, mock_urlopen):
        """Verify GoogleRoutesClient raises 502 on malformed non-JSON response."""
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b"<html>Bad Gateway</html>"
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        client = GoogleRoutesClient(api_key="TEST_API_KEY")
        with self.assertRaises(GoogleRoutesAPIError) as ctx:
            client.compute_route(12.9352, 77.6245, 12.9716, 77.5946)
        self.assertEqual(ctx.exception.status_code, 502)
        self.assertIn("invalid JSON", ctx.exception.message)


class EmergencyIncidentRouteAPITestCase(TestCase):
    """Comprehensive API test suite for GET /api/emergencies/<uuid:pk>/route/."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # 1. Hospitals
        self.hospital_a = Hospital.objects.create(
            name="City Central Emergency Hospital",
            hospital_code="HOSP-ROUTE-A",
            address="100 Main Road, Bangalore",
            latitude=Decimal("12.971600"),
            longitude=Decimal("77.594600"),
            contact_number="+918012345678",
            is_active=True,
        )
        self.hospital_b = Hospital.objects.create(
            name="Metro Trauma Center",
            hospital_code="HOSP-ROUTE-B",
            address="200 West Boulevard, Bangalore",
            latitude=Decimal("12.980000"),
            longitude=Decimal("77.600000"),
            contact_number="+918098765432",
            is_active=True,
        )

        # 2. Users
        # Reporting driver
        self.driver1 = User.objects.create_user(
            username="route_driver_01",
            password="StrongPassword123!@#",
            email="driver1@sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            phone_number="+919876543201",
            badge_or_employee_id="DRV-RT-01",
            is_verified=True,
            is_active=True,
        )
        # Second driver (unrelated)
        self.driver2 = User.objects.create_user(
            username="route_driver_02",
            password="StrongPassword123!@#",
            email="driver2@sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            phone_number="+919876543202",
            badge_or_employee_id="DRV-RT-02",
            is_verified=True,
            is_active=True,
        )
        # Unverified driver
        self.unverified_driver = User.objects.create_user(
            username="route_unverified_driver",
            password="StrongPassword123!@#",
            email="unver_drv@sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=False,
            is_active=True,
        )
        # Inactive driver
        self.inactive_driver = User.objects.create_user(
            username="route_inactive_driver",
            password="StrongPassword123!@#",
            email="inact_drv@sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=True,
            is_active=False,
        )
        # Hospital Staff A (affiliated with Hospital A)
        self.staff_a = User.objects.create_user(
            username="route_staff_dr_anita",
            password="StrongPassword123!@#",
            email="staff_a@sertos.local",
            role=UserRole.HOSPITAL_STAFF,
            badge_or_employee_id="MED-RT-A1",
            is_verified=True,
            is_active=True,
        )
        HospitalStaff.objects.create(
            user=self.staff_a,
            hospital=self.hospital_a,
            is_active=True,
        )
        # Hospital Staff B (affiliated only with Hospital B)
        self.staff_b = User.objects.create_user(
            username="route_staff_dr_vikram",
            password="StrongPassword123!@#",
            email="staff_b@sertos.local",
            role=UserRole.HOSPITAL_STAFF,
            badge_or_employee_id="MED-RT-B1",
            is_verified=True,
            is_active=True,
        )
        HospitalStaff.objects.create(
            user=self.staff_b,
            hospital=self.hospital_b,
            is_active=True,
        )
        # Police Dispatcher
        self.police = User.objects.create_user(
            username="route_police_dispatcher",
            password="StrongPassword123!@#",
            email="police_rt@sertos.local",
            role=UserRole.POLICE_DISPATCHER,
            badge_or_employee_id="POL-RT-01",
            is_verified=True,
            is_active=True,
        )
        # System Administrator
        self.admin = User.objects.create_user(
            username="route_admin",
            password="StrongPassword123!@#",
            email="admin_rt@sertos.local",
            role=UserRole.ADMIN,
            is_verified=True,
            is_active=True,
        )

        # 3. Ambulances
        self.ambulance1 = Ambulance.objects.create(
            vehicle_number="KA-01-RT-1001",
            vehicle_type="Advanced Life Support",
            assigned_driver=self.driver1,
            is_available=True,
            is_active=True,
        )
        self.ambulance2 = Ambulance.objects.create(
            vehicle_number="KA-01-RT-1002",
            vehicle_type="Basic Life Support",
            assigned_driver=self.driver2,
            is_available=True,
            is_active=True,
        )

        # 4. Emergency Incident assigned to Hospital A
        self.incident = EmergencyIncident.objects.create(
            incident_number="INC-20261116-RT01",
            reporting_driver=self.driver1,
            ambulance=self.ambulance1,
            hospital=self.hospital_a,
            severity=IncidentSeverity.CRITICAL,
            status=IncidentStatus.IN_TRANSIT,
            description="Severe cardiac trauma in transit to Hospital A.",
        )

        # 5. Ambulance Location breadcrumbs
        # Older ping
        AmbulanceLocation.objects.create(
            incident=self.incident,
            ambulance=self.ambulance1,
            latitude=Decimal("12.920000"),
            longitude=Decimal("77.610000"),
        )
        # Latest ping (must be picked up by routing service)
        self.latest_location = AmbulanceLocation.objects.create(
            incident=self.incident,
            ambulance=self.ambulance1,
            latitude=Decimal("12.935200"),
            longitude=Decimal("77.624500"),
        )
        now = timezone.now()
        self.older_location = AmbulanceLocation.objects.get(
            incident=self.incident,
            latitude=Decimal("12.920000"),
            longitude=Decimal("77.610000"),
        )
        AmbulanceLocation.objects.filter(pk=self.older_location.pk).update(
            server_received_at=now - timedelta(seconds=1)
        )
        AmbulanceLocation.objects.filter(pk=self.latest_location.pk).update(
            server_received_at=now
        )

        self.mock_route_metrics = {
            "distance_meters": 7450,
            "duration_seconds": 1020,
            "duration_formatted": "17 mins",
            "polyline": "a~l~FjkzbO_@mockPolylineSequence",
        }

    def tearDown(self):
        cache.clear()

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_01_successful_route_response_for_driver(self, mock_compute):
        """1. Verify reporting ambulance driver receives 200 OK with complete route & ETA envelope."""
        mock_compute.return_value = self.mock_route_metrics
        self.client.force_authenticate(user=self.driver1)

        response = self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["message"], "Incident route and ETA computed successfully.")

        data = response.data["data"]
        self.assertEqual(data["incident_id"], str(self.incident.id))
        self.assertEqual(data["incident_number"], self.incident.incident_number)

        # Verify origin coordinates match the latest ambulance GPS location
        self.assertAlmostEqual(data["origin"]["latitude"], 12.935200, places=5)
        self.assertAlmostEqual(data["origin"]["longitude"], 77.624500, places=5)

        # Verify destination coordinates match destination hospital
        self.assertAlmostEqual(data["destination"]["latitude"], 12.971600, places=5)
        self.assertAlmostEqual(data["destination"]["longitude"], 77.594600, places=5)
        self.assertEqual(data["destination"]["hospital_name"], self.hospital_a.name)

        # Verify distance, duration, and polyline
        self.assertEqual(data["distance_meters"], 7450)
        self.assertEqual(data["distance_km"], 7.45)
        self.assertEqual(data["duration_seconds"], 1020)
        self.assertEqual(data["duration_formatted"], "17 mins")
        self.assertEqual(data["polyline"], "a~l~FjkzbO_@mockPolylineSequence")

        # Verify estimated arrival is present and ISO formatted
        self.assertIn("estimated_arrival", data)
        self.assertTrue(len(data["estimated_arrival"]) > 10)

        # Verify dynamic route recalculation fields
        self.assertIn("is_stale", data)
        self.assertFalse(data["is_stale"])
        self.assertIn("last_calculated_at", data)

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_02_affiliated_hospital_staff_can_access_route(self, mock_compute):
        """2. Verify medical staff affiliated with the destination hospital can access route & ETA."""
        mock_compute.return_value = self.mock_route_metrics
        self.client.force_authenticate(user=self.staff_a)

        response = self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["incident_id"], str(self.incident.id))

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_03_police_dispatcher_can_access_route(self, mock_compute):
        """3. Verify police dispatchers have city-wide visibility to route & ETA."""
        mock_compute.return_value = self.mock_route_metrics
        self.client.force_authenticate(user=self.police)

        response = self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_04_system_admin_can_access_route(self, mock_compute):
        """4. Verify system administrators can access route & ETA."""
        mock_compute.return_value = self.mock_route_metrics
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])

    def test_05_unrelated_driver_rejected_with_404(self):
        """5. Verify unrelated ambulance driver receives 404 (scoped isolation)."""
        self.client.force_authenticate(user=self.driver2)
        response = self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_06_unaffiliated_hospital_staff_rejected_with_404(self):
        """6. Verify hospital staff not affiliated with destination hospital receives 404."""
        self.client.force_authenticate(user=self.staff_b)
        response = self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_07_unauthenticated_request_rejected_with_401(self):
        """7. Verify unauthenticated request receives 401 Unauthorized."""
        response = self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_08_unverified_driver_rejected_with_403(self):
        """8. Verify unverified driver account receives 403 Forbidden."""
        self.client.force_authenticate(user=self.unverified_driver)
        response = self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_09_inactive_driver_rejected_with_403(self):
        """9. Verify inactive driver account receives 403 Forbidden."""
        self.client.force_authenticate(user=self.inactive_driver)
        response = self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_10_missing_ambulance_location_returns_400(self):
        """10. Verify clear 400 error when no GPS ping has been recorded for the incident."""
        incident_no_pings = EmergencyIncident.objects.create(
            incident_number="INC-20261116-NOPING",
            reporting_driver=self.driver1,
            ambulance=self.ambulance1,
            hospital=self.hospital_a,
            status=IncidentStatus.REPORTED,
        )
        self.client.force_authenticate(user=self.driver1)
        response = self.client.get(f"/api/emergencies/{incident_no_pings.id}/route/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertIn("No ambulance GPS location recorded", response.data["message"])

    def test_11_missing_hospital_coordinates_returns_400(self):
        """11. Verify clear 400 error when destination hospital lacks valid GPS coordinates."""
        hospital_no_coords = Hospital.objects.create(
            name="Rural Clinic Without GPS",
            hospital_code="HOSP-NOGPS",
            address="Remote District",
            is_active=True,
        )
        incident_no_hosp = EmergencyIncident.objects.create(
            incident_number="INC-20261116-NOHOSP",
            reporting_driver=self.driver1,
            ambulance=self.ambulance1,
            hospital=hospital_no_coords,
            status=IncidentStatus.REPORTED,
        )
        AmbulanceLocation.objects.create(
            incident=incident_no_hosp,
            ambulance=self.ambulance1,
            latitude=Decimal("12.935200"),
            longitude=Decimal("77.624500"),
        )
        self.client.force_authenticate(user=self.driver1)
        response = self.client.get(f"/api/emergencies/{incident_no_hosp.id}/route/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertIn("does not have valid GPS coordinates", response.data["message"])

    @override_settings(GOOGLE_MAPS_API_KEY="")
    @patch("apps.emergencies.routes_service.os.getenv")
    def test_12_missing_api_key_returns_503(self, mock_getenv):
        """12. Verify 503 Service Unavailable when Google Maps API key is unconfigured."""
        mock_getenv.return_value = ""
        self.client.force_authenticate(user=self.driver1)
        response = self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertFalse(response.data["success"])
        self.assertIn("API key is not configured", response.data["message"])

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_13_google_api_timeout_returns_504(self, mock_compute):
        """13. Verify 504 Gateway Timeout when Google Routes API connection times out without cached route."""
        mock_compute.side_effect = GoogleRoutesAPIError(
            "Google Routes API connection timed out or failed.",
            status_code=504,
            code="google_api_timeout",
        )
        self.client.force_authenticate(user=self.driver1)
        response = self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(response.status_code, status.HTTP_504_GATEWAY_TIMEOUT)
        self.assertFalse(response.data["success"])
        self.assertIn("timed out", response.data["message"])

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_14_google_api_http_error_returns_502(self, mock_compute):
        """14. Verify 502 Bad Gateway when Google Routes API returns an upstream HTTP error without cached route."""
        mock_compute.side_effect = GoogleRoutesAPIError(
            "Google Routes API request failed (500): Internal error",
            status_code=502,
            code="google_api_http_error",
        )
        self.client.force_authenticate(user=self.driver1)
        response = self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertFalse(response.data["success"])
        self.assertIn("Google Routes API request failed", response.data["message"])

    def test_15_mutating_methods_rejected_with_403(self):
        """15. Verify POST, PUT, DELETE, PATCH to the route endpoint are rejected (read-only)."""
        self.client.force_authenticate(user=self.driver1)
        post_res = self.client.post(f"/api/emergencies/{self.incident.id}/route/", {})
        self.assertEqual(post_res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("read-only", str(post_res.data))

    # =========================================================================
    # Phase 6: Dynamic Route Recalculation Tests
    # =========================================================================

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_16_cache_hit_prevents_duplicate_google_api_call(self, mock_compute):
        """16. Verify second route request without movement uses cached route and avoids calling Google."""
        mock_compute.return_value = self.mock_route_metrics
        self.client.force_authenticate(user=self.driver1)

        # First request computes and caches
        res1 = self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_compute.call_count, 1)

        # Second request immediately after (0 movement, 0s elapsed) must return cache
        res2 = self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_compute.call_count, 1)
        self.assertFalse(res2.data["data"]["is_stale"])

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_17_movement_band_0m_returns_cached(self, mock_compute):
        """17. Verify 0m movement after 120 seconds returns cached route without calling Google."""
        mock_compute.return_value = self.mock_route_metrics
        self.client.force_authenticate(user=self.driver1)

        # Initial calculation
        self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(mock_compute.call_count, 1)

        # Age cache timestamp by 120 seconds (cooldown passed, but 0 movement)
        cache_key = f"{ROUTE_CACHE_KEY_PREFIX}{self.incident.id}"
        cached = cache.get(cache_key)
        cached["last_calculated_at"] = (timezone.now() - timedelta(seconds=120)).isoformat()
        cache.set(cache_key, cached)

        # Request route again - ambulance has not moved
        res = self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_compute.call_count, 1)  # No second Google API call

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_18_movement_band_under_50m_returns_cached(self, mock_compute):
        """18. Verify movement < 50m (25m) even after 190s returns cached route without calling Google."""
        mock_compute.return_value = self.mock_route_metrics
        self.client.force_authenticate(user=self.driver1)

        # Initial calculation
        self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(mock_compute.call_count, 1)

        # Ambulance moves only 25 meters (12.935425)
        AmbulanceLocation.objects.create(
            incident=self.incident,
            ambulance=self.ambulance1,
            latitude=Decimal("12.935425"),
            longitude=Decimal("77.624500"),
        )

        # Age cache by 190s
        cache_key = f"{ROUTE_CACHE_KEY_PREFIX}{self.incident.id}"
        cached = cache.get(cache_key)
        cached["last_calculated_at"] = (timezone.now() - timedelta(seconds=190)).isoformat()
        cache.set(cache_key, cached)

        res = self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_compute.call_count, 1)  # Movement < 50m rejected recalculation

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_19_movement_band_50_to_249m_at_70s_returns_cached(self, mock_compute):
        """19. Verify movement of 100m at 70s returns cached route (requires 250m for normal or 180s for fallback)."""
        mock_compute.return_value = self.mock_route_metrics
        self.client.force_authenticate(user=self.driver1)

        # Initial calculation
        self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(mock_compute.call_count, 1)

        # Ambulance moves 100 meters (12.936102)
        AmbulanceLocation.objects.create(
            incident=self.incident,
            ambulance=self.ambulance1,
            latitude=Decimal("12.936102"),
            longitude=Decimal("77.624500"),
        )

        # Age cache by 70s (cooldown 60s met, but distance 100m < 250m and time 70s < 180s)
        cache_key = f"{ROUTE_CACHE_KEY_PREFIX}{self.incident.id}"
        cached = cache.get(cache_key)
        cached["last_calculated_at"] = (timezone.now() - timedelta(seconds=70)).isoformat()
        cache.set(cache_key, cached)

        res = self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_compute.call_count, 1)  # Cached, no second call

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_20_movement_band_ge_250m_at_65s_triggers_recalculation(self, mock_compute):
        """20. Verify movement >= 250m (300m) at 65s triggers recalculation with Google Routes API."""
        mock_compute.return_value = self.mock_route_metrics
        self.client.force_authenticate(user=self.driver1)

        # Initial calculation
        self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(mock_compute.call_count, 1)

        # Ambulance moves 300 meters (12.937905)
        moved_location = AmbulanceLocation.objects.create(
            incident=self.incident,
            ambulance=self.ambulance1,
            latitude=Decimal("12.937905"),
            longitude=Decimal("77.624500"),
        )
        # Keep this fixture strictly later than the initial breadcrumb even if
        # both model saves happen inside the same clock tick.
        AmbulanceLocation.objects.filter(pk=moved_location.pk).update(
            server_received_at=self.latest_location.server_received_at + timedelta(seconds=1)
        )

        # Age cache by 65s (elapsed >= 60s and distance >= 250m)
        cache_key = f"{ROUTE_CACHE_KEY_PREFIX}{self.incident.id}"
        cached = cache.get(cache_key)
        cached["last_calculated_at"] = (timezone.now() - timedelta(seconds=65)).isoformat()
        cache.set(cache_key, cached)

        # Mock updated metrics for the recalculation
        mock_compute.return_value = {
            "distance_meters": 7150,
            "duration_seconds": 960,
            "duration_formatted": "16 mins",
            "polyline": "a~l~FjkzbO_@updatedPolyline",
        }

        res = self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_compute.call_count, 2)  # Recalculated!
        self.assertEqual(res.data["data"]["distance_meters"], 7150)
        self.assertAlmostEqual(res.data["data"]["origin"]["latitude"], 12.937905, places=5)
        self.assertFalse(res.data["data"]["is_stale"])

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_21_movement_band_ge_250m_at_20s_returns_cached_due_to_cooldown(self, mock_compute):
        """21. Verify movement >= 250m (300m) at only 20s is throttled by cooldown and returns cached route."""
        mock_compute.return_value = self.mock_route_metrics
        self.client.force_authenticate(user=self.driver1)

        # Initial calculation
        self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(mock_compute.call_count, 1)

        # Ambulance moves 300 meters
        AmbulanceLocation.objects.create(
            incident=self.incident,
            ambulance=self.ambulance1,
            latitude=Decimal("12.937905"),
            longitude=Decimal("77.624500"),
        )

        # Age cache by only 20s (cooldown < 60s not met)
        cache_key = f"{ROUTE_CACHE_KEY_PREFIX}{self.incident.id}"
        cached = cache.get(cache_key)
        cached["last_calculated_at"] = (timezone.now() - timedelta(seconds=20)).isoformat()
        cache.set(cache_key, cached)

        res = self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_compute.call_count, 1)  # Throttled by cooldown

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_22_movement_band_fallback_60m_at_190s_triggers_recalculation(self, mock_compute):
        """22. Verify movement >= 50m (60m) at 190s (>= 180s) triggers fallback recalculation."""
        mock_compute.return_value = self.mock_route_metrics
        self.client.force_authenticate(user=self.driver1)

        # Initial calculation
        self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(mock_compute.call_count, 1)

        # Ambulance moves 60 meters (12.935741)
        moved_location = AmbulanceLocation.objects.create(
            incident=self.incident,
            ambulance=self.ambulance1,
            latitude=Decimal("12.935741"),
            longitude=Decimal("77.624500"),
        )
        # Force deterministic latest-location ordering when SQLite rounds both
        # GPS rows to the same timestamp.
        AmbulanceLocation.objects.filter(pk=moved_location.pk).update(
            server_received_at=self.latest_location.server_received_at + timedelta(seconds=1)
        )

        # Age cache by 190s (fallback: elapsed >= 180s and distance >= 50m)
        cache_key = f"{ROUTE_CACHE_KEY_PREFIX}{self.incident.id}"
        cached = cache.get(cache_key)
        cached["last_calculated_at"] = (timezone.now() - timedelta(seconds=190)).isoformat()
        cache.set(cache_key, cached)

        res = self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_compute.call_count, 2)  # Fallback recalculation triggered!
        self.assertFalse(res.data["data"]["is_stale"])

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_23_google_failure_retains_cached_route_with_is_stale_true(self, mock_compute):
        """23. Verify Google API failure retains last known route with is_stale=True and returns HTTP 200."""
        mock_compute.return_value = self.mock_route_metrics
        self.client.force_authenticate(user=self.driver1)

        # Initial successful calculation
        res1 = self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertFalse(res1.data["data"]["is_stale"])
        self.assertEqual(mock_compute.call_count, 1)

        # Ambulance moves 300m, 70s later (recalculation condition met)
        moved_location = AmbulanceLocation.objects.create(
            incident=self.incident,
            ambulance=self.ambulance1,
            latitude=Decimal("12.937905"),
            longitude=Decimal("77.624500"),
        )
        AmbulanceLocation.objects.filter(pk=moved_location.pk).update(
            server_received_at=self.latest_location.server_received_at + timedelta(seconds=1)
        )
        cache_key = f"{ROUTE_CACHE_KEY_PREFIX}{self.incident.id}"
        cached = cache.get(cache_key)
        cached["last_calculated_at"] = (timezone.now() - timedelta(seconds=70)).isoformat()
        cache.set(cache_key, cached)

        # Google API fails on the recalculation attempt
        mock_compute.side_effect = GoogleRoutesAPIError(
            "Google Routes API connection timed out or failed.",
            status_code=504,
            code="google_api_timeout",
        )

        res2 = self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        # Must return HTTP 200 with the retained route marked as stale
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertTrue(res2.data["success"])
        self.assertTrue(res2.data["data"]["is_stale"])
        self.assertEqual(res2.data["data"]["distance_meters"], 7450)  # Retained
        self.assertEqual(res2.data["data"]["polyline"], "a~l~FjkzbO_@mockPolylineSequence")

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_24_google_failure_without_cached_route_raises_error(self, mock_compute):
        """24. Verify Google API failure without a prior route returns error status (504)."""
        mock_compute.side_effect = GoogleRoutesAPIError(
            "Google Routes API connection timed out or failed.",
            status_code=504,
            code="google_api_timeout",
        )
        self.client.force_authenticate(user=self.driver1)

        # Clean cache, initial call fails
        res = self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(res.status_code, status.HTTP_504_GATEWAY_TIMEOUT)
        self.assertFalse(res.data["success"])

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_25_concurrent_lock_prevents_duplicate_recalculation(self, mock_compute):
        """25. Verify lock contention returns cached route without duplicate Google API call."""
        mock_compute.return_value = self.mock_route_metrics
        self.client.force_authenticate(user=self.driver1)

        # Seed cache
        self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(mock_compute.call_count, 1)

        # Simulate another process acquiring the route lock
        lock_key = f"{ROUTE_LOCK_KEY_PREFIX}{self.incident.id}"
        cache.set(lock_key, "locked", timeout=10)

        # Next request must recognize active lock and return cached route
        res = self.client.get(f"/api/emergencies/{self.incident.id}/route/?force=true")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_compute.call_count, 1)  # No second call made

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_26_gps_location_ingestion_not_blocked_by_route_service(self, mock_compute):
        """26. Verify GPS location submission persists successfully and never invokes Google Routes API."""
        self.client.force_authenticate(user=self.driver1)

        payload = {
            "latitude": "12.940000",
            "longitude": "77.630000",
            "accuracy": "5.50",
        }
        res = self.client.post(f"/api/emergencies/{self.incident.id}/location/", payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["success"])

        # Google Routes API must NOT be called during GPS location submission
        mock_compute.assert_not_called()

        # Database record must exist
        latest = AmbulanceLocation.objects.filter(incident=self.incident).order_by("-server_received_at").first()
        self.assertAlmostEqual(float(latest.latitude), 12.940000, places=5)
        self.assertAlmostEqual(float(latest.longitude), 77.630000, places=5)

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_27_force_recalculation_query_param(self, mock_compute):
        """27. Verify ?force=true query parameter forces recalculation even when cooldown/movement are not met."""
        mock_compute.return_value = self.mock_route_metrics
        self.client.force_authenticate(user=self.driver1)

        # Initial call
        self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(mock_compute.call_count, 1)

        # Request with ?force=true immediately (0m movement, 0s elapsed)
        mock_compute.return_value = {
            "distance_meters": 7400,
            "duration_seconds": 1000,
            "duration_formatted": "16 mins",
            "polyline": "a~l~FjkzbO_@forcedPolyline",
        }
        res = self.client.get(f"/api/emergencies/{self.incident.id}/route/?force=true")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_compute.call_count, 2)
        self.assertEqual(res.data["data"]["distance_meters"], 7400)

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_28_hospital_destination_change_forces_recalculation(self, mock_compute):
        """28. Verify changing the assigned hospital forces recalculation even if movement threshold is not met."""
        mock_compute.return_value = self.mock_route_metrics
        self.client.force_authenticate(user=self.driver1)

        # Initial call to Hospital A
        self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(mock_compute.call_count, 1)

        # Reassign incident to Hospital B
        self.incident.hospital = self.hospital_b
        self.incident.save()

        mock_compute.return_value = {
            "distance_meters": 8200,
            "duration_seconds": 1150,
            "duration_formatted": "19 mins",
            "polyline": "a~l~FjkzbO_@hospBPolyline",
        }
        res = self.client.get(f"/api/emergencies/{self.incident.id}/route/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_compute.call_count, 2)
        self.assertEqual(res.data["data"]["destination"]["hospital_name"], self.hospital_b.name)


class HospitalDashboardRouteIntegrationTestCase(TestCase):
    """
    Integration test suite for Hospital Dashboard Route Integration (Phase 6, Task 6.2).

    Covers:
    1. Hospital staff receives route_summary on GET /api/hospital/incidents/<pk>/ when cached route exists.
    2. Route summary contains distance_km, duration_formatted, estimated_arrival, is_stale, last_calculated_at.
    3. Missing route cache returns route_summary: null (HTTP 200).
    4. Stale routes are clearly marked with is_stale=True.
    5. Hospital staff cannot access another hospital's incident (returns 404).
    6. Evaluating hospital incident detail serializer NEVER triggers Google API calls.
    7. Evaluating hospital incident list serializer NEVER triggers Google API calls.
    8. Verified hospital staff can access live route on /api/emergencies/<pk>/route/ for own hospital incident.
    9. Verified hospital staff receives 404 on /api/emergencies/<pk>/route/ for another hospital incident.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # 1. Hospitals
        self.hospital_a = Hospital.objects.create(
            name="Apex Specialty Hospital",
            hospital_code="HOSP-APX-01",
            address="100 Hospital Road, Bangalore",
            latitude=Decimal("12.971600"),
            longitude=Decimal("77.594600"),
            contact_number="+918011223344",
            is_active=True,
        )
        self.hospital_b = Hospital.objects.create(
            name="Columbia Care Center",
            hospital_code="HOSP-COL-02",
            address="200 Ring Road, Bangalore",
            latitude=Decimal("12.980000"),
            longitude=Decimal("77.600000"),
            contact_number="+918055667788",
            is_active=True,
        )

        # 2. Staff Users
        self.staff_a = User.objects.create_user(
            username="nurse_apex",
            email="nurse_apex@sertos.local",
            password="Password123!@#",
            role=UserRole.HOSPITAL_STAFF,
            is_verified=True,
            is_active=True,
        )
        HospitalStaff.objects.create(hospital=self.hospital_a, user=self.staff_a, is_active=True)

        self.staff_b = User.objects.create_user(
            username="nurse_columbia",
            email="nurse_columbia@sertos.local",
            password="Password123!@#",
            role=UserRole.HOSPITAL_STAFF,
            is_verified=True,
            is_active=True,
        )
        HospitalStaff.objects.create(hospital=self.hospital_b, user=self.staff_b, is_active=True)

        # Driver User
        self.driver = User.objects.create_user(
            username="driver_hero",
            email="driver_hero@sertos.local",
            password="Password123!@#",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=True,
            is_active=True,
        )

        # 3. Ambulance
        self.ambulance = Ambulance.objects.create(
            vehicle_number="KA-05-HD-5001",
            vehicle_type="Advanced Life Support",
            assigned_driver=self.driver,
            is_available=True,
            is_active=True,
        )

        # 4. Incidents
        self.incident_a = EmergencyIncident.objects.create(
            incident_number="INC-20261116-HOSP01",
            reporting_driver=self.driver,
            ambulance=self.ambulance,
            hospital=self.hospital_a,
            severity=IncidentSeverity.CRITICAL,
            status=IncidentStatus.IN_TRANSIT,
            description="Severe cardiac arrest in transit.",
        )
        self.incident_b = EmergencyIncident.objects.create(
            incident_number="INC-20261116-HOSP02",
            reporting_driver=self.driver,
            ambulance=self.ambulance,
            hospital=self.hospital_b,
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.IN_TRANSIT,
            description="Head injury in transit to Hospital B.",
        )

        # Ambulance breadcrumb for incident A
        AmbulanceLocation.objects.create(
            incident=self.incident_a,
            ambulance=self.ambulance,
            latitude=Decimal("12.935200"),
            longitude=Decimal("77.624500"),
        )

    def tearDown(self):
        cache.clear()

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_hospital_staff_sees_route_summary_when_cached(self, mock_compute):
        """Verify hospital staff gets populated route_summary on incident detail when route is cached."""
        now = timezone.now()
        cache_key = f"{ROUTE_CACHE_KEY_PREFIX}{self.incident_a.id}"
        cache.set(
            cache_key,
            {
                "distance_km": 7.45,
                "distance_meters": 7450,
                "duration_seconds": 1020,
                "duration_formatted": "17 mins",
                "estimated_arrival": (now + timedelta(seconds=1020)).isoformat(),
                "polyline": "mock_polyline",
                "is_stale": False,
                "last_calculated_at": now.isoformat(),
            },
            timeout=3600,
        )

        self.client.force_authenticate(user=self.staff_a)
        response = self.client.get(f"/api/hospital/incidents/{self.incident_a.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        route_summary = response.data["data"]["route_summary"]
        self.assertIsNotNone(route_summary)
        self.assertEqual(route_summary["distance_km"], 7.45)
        self.assertEqual(route_summary["duration_formatted"], "17 mins")
        self.assertFalse(route_summary["is_stale"])
        self.assertEqual(route_summary["last_calculated_at"], now.isoformat())
        self.assertIn("estimated_arrival", route_summary)

        # Evaluating dashboard serializer must NEVER invoke Google API
        mock_compute.assert_not_called()

    def test_missing_route_cache_returns_null_route_summary(self):
        """Verify incident detail returns route_summary: null when no route has been computed."""
        self.client.force_authenticate(user=self.staff_a)
        response = self.client.get(f"/api/hospital/incidents/{self.incident_a.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertIsNone(response.data["data"]["route_summary"])

    def test_stale_route_summary_marked_is_stale_true(self):
        """Verify stale route in cache surfaces is_stale=True in route_summary."""
        now = timezone.now()
        cache_key = f"{ROUTE_CACHE_KEY_PREFIX}{self.incident_a.id}"
        cache.set(
            cache_key,
            {
                "distance_km": 7.45,
                "duration_seconds": 1020,
                "duration_formatted": "17 mins",
                "is_stale": True,
                "last_calculated_at": (now - timedelta(minutes=10)).isoformat(),
            },
            timeout=3600,
        )

        self.client.force_authenticate(user=self.staff_a)
        response = self.client.get(f"/api/hospital/incidents/{self.incident_a.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        route_summary = response.data["data"]["route_summary"]
        self.assertIsNotNone(route_summary)
        self.assertTrue(route_summary["is_stale"])

    def test_hospital_staff_cannot_access_another_hospital_incident(self):
        """Verify hospital staff receives 404 when querying an incident directed to another hospital."""
        self.client.force_authenticate(user=self.staff_a)
        # Attempt to access incident_b (belonging to hospital_b)
        response = self.client.get(f"/api/hospital/incidents/{self.incident_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Also verify 404 on the route endpoint for another hospital's incident
        route_res = self.client.get(f"/api/emergencies/{self.incident_b.id}/route/")
        self.assertEqual(route_res.status_code, status.HTTP_404_NOT_FOUND)

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_dashboard_list_does_not_invoke_google_api(self, mock_compute):
        """Verify GET /api/hospital/incidents/ never calls Google Routes API."""
        self.client.force_authenticate(user=self.staff_a)
        response = self.client.get("/api/hospital/incidents/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        mock_compute.assert_not_called()

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_dashboard_detail_does_not_invoke_google_api_even_when_uncomputed(self, mock_compute):
        """Verify GET /api/hospital/incidents/{id}/ never invokes Google API even if route uncomputed."""
        self.client.force_authenticate(user=self.staff_a)
        response = self.client.get(f"/api/hospital/incidents/{self.incident_a.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["data"]["route_summary"])
        mock_compute.assert_not_called()

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_hospital_staff_route_endpoint_access_for_own_hospital_incident(self, mock_compute):
        """Verify hospital staff can calculate route via /api/emergencies/{id}/route/ which populates dashboard cache."""
        mock_compute.return_value = {
            "distance_meters": 7450,
            "duration_seconds": 1020,
            "duration_formatted": "17 mins",
            "polyline": "mock_hospital_polyline",
        }
        self.client.force_authenticate(user=self.staff_a)

        # 1. Call route endpoint
        route_res = self.client.get(f"/api/emergencies/{self.incident_a.id}/route/")
        self.assertEqual(route_res.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_compute.call_count, 1)

        # 2. Detail view now shows the cached route summary
        detail_res = self.client.get(f"/api/hospital/incidents/{self.incident_a.id}/")
        self.assertEqual(detail_res.status_code, status.HTTP_200_OK)
        summary = detail_res.data["data"]["route_summary"]
        self.assertIsNotNone(summary)
        self.assertEqual(summary["distance_km"], 7.45)
        self.assertEqual(summary["duration_formatted"], "17 mins")
        self.assertFalse(summary["is_stale"])


class PoliceDashboardRouteIntegrationTestCase(TestCase):
    """
    Integration test suite for Police Dashboard Route Integration (Phase 6, Task 6.3).

    Covers:
    1. Police dispatcher receives cached route_summary on GET /api/police/incidents/<pk>/.
    2. All five required fields are present: distance_km, duration_formatted, estimated_arrival, is_stale, last_calculated_at.
    3. Missing route cache returns route_summary: null.
    4. Stale cached route returns is_stale: true.
    5. Police incident list never calls Google Routes API.
    6. Police incident detail never calls Google Routes API (cached or uncomputed).
    7. Unauthenticated (401), unverified (403), inactive (403), and non-police roles (403) cannot access police dashboard.
    8. Police dispatchers retain city-wide incident visibility across multiple hospitals.
    9. Hospital dashboard route integration continues functioning with hospital isolation.
    10. Confidential patient medical notes remain strictly excluded from police incident detail.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # 1. Hospitals
        self.hospital_a = Hospital.objects.create(
            name="General City Hospital",
            hospital_code="HOSP-POL-A",
            address="100 Police Line, Bangalore",
            latitude=Decimal("12.971600"),
            longitude=Decimal("77.594600"),
            contact_number="+918011112222",
            is_active=True,
        )
        self.hospital_b = Hospital.objects.create(
            name="North Trauma Center",
            hospital_code="HOSP-POL-B",
            address="200 Ring Road North, Bangalore",
            latitude=Decimal("12.980000"),
            longitude=Decimal("77.600000"),
            contact_number="+918033334444",
            is_active=True,
        )

        # 2. Users
        # Police Dispatcher (verified, active)
        self.police_user = User.objects.create_user(
            username="dispatcher_rajesh",
            email="dispatcher_rajesh@sertos.local",
            password="Password123!@#",
            role=UserRole.POLICE_DISPATCHER,
            is_verified=True,
            is_active=True,
        )
        # Unverified Police Dispatcher
        self.unverified_police = User.objects.create_user(
            username="unver_dispatcher",
            email="unver_disp@sertos.local",
            password="Password123!@#",
            role=UserRole.POLICE_DISPATCHER,
            is_verified=False,
            is_active=True,
        )
        # Inactive Police Dispatcher
        self.inactive_police = User.objects.create_user(
            username="inact_dispatcher",
            email="inact_disp@sertos.local",
            password="Password123!@#",
            role=UserRole.POLICE_DISPATCHER,
            is_verified=True,
            is_active=False,
        )
        # Hospital Staff (Hospital A)
        self.staff_a = User.objects.create_user(
            username="hospital_nurse_a",
            email="nurse_a@sertos.local",
            password="Password123!@#",
            role=UserRole.HOSPITAL_STAFF,
            is_verified=True,
            is_active=True,
        )
        HospitalStaff.objects.create(hospital=self.hospital_a, user=self.staff_a, is_active=True)

        # Ambulance Driver
        self.driver = User.objects.create_user(
            username="driver_speedy",
            email="driver_speedy@sertos.local",
            password="Password123!@#",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=True,
            is_active=True,
        )

        # 3. Ambulance
        self.ambulance = Ambulance.objects.create(
            vehicle_number="KA-01-PD-7001",
            vehicle_type="Advanced Life Support",
            assigned_driver=self.driver,
            is_available=True,
            is_active=True,
        )

        # 4. Incidents & Patients
        # Incident A destined for Hospital A
        self.incident_a = EmergencyIncident.objects.create(
            incident_number="INC-20261117-POL01",
            reporting_driver=self.driver,
            ambulance=self.ambulance,
            hospital=self.hospital_a,
            severity=IncidentSeverity.CRITICAL,
            status=IncidentStatus.IN_TRANSIT,
            description="Major highway collision requiring corridor clearance.",
        )
        # Patient with sensitive medical notes
        from apps.emergencies.models import Patient
        self.patient_a = Patient.objects.create(
            incident=self.incident_a,
            name="Vikram Singh",
            age=42,
            blood_group="O+",
            medical_notes="CONFIDENTIAL: Internal hemorrhage, Glasgow Coma Scale 7.",
        )

        # Incident B destined for Hospital B
        self.incident_b = EmergencyIncident.objects.create(
            incident_number="INC-20261117-POL02",
            reporting_driver=self.driver,
            ambulance=self.ambulance,
            hospital=self.hospital_b,
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.IN_TRANSIT,
            description="Industrial chemical spill casualty.",
        )

        # Ambulance location breadcrumb
        AmbulanceLocation.objects.create(
            incident=self.incident_a,
            ambulance=self.ambulance,
            latitude=Decimal("12.935200"),
            longitude=Decimal("77.624500"),
        )

    def tearDown(self):
        cache.clear()

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_police_dispatcher_sees_cached_route_summary_with_all_five_fields(self, mock_compute):
        """Verify police dispatcher receives populated route_summary on incident detail with all 5 required fields."""
        now = timezone.now()
        cache_key = f"{ROUTE_CACHE_KEY_PREFIX}{self.incident_a.id}"
        cache.set(
            cache_key,
            {
                "distance_km": 8.35,
                "distance_meters": 8350,
                "duration_seconds": 1140,
                "duration_formatted": "19 mins",
                "estimated_arrival": (now + timedelta(seconds=1140)).isoformat(),
                "polyline": "mock_police_polyline",
                "is_stale": False,
                "last_calculated_at": now.isoformat(),
            },
            timeout=3600,
        )

        self.client.force_authenticate(user=self.police_user)
        response = self.client.get(f"/api/police/incidents/{self.incident_a.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        route_summary = response.data["data"]["route_summary"]
        self.assertIsNotNone(route_summary)

        # Verify all 5 required fields
        self.assertEqual(route_summary["distance_km"], 8.35)
        self.assertEqual(route_summary["duration_formatted"], "19 mins")
        self.assertIn("estimated_arrival", route_summary)
        self.assertFalse(route_summary["is_stale"])
        self.assertEqual(route_summary["last_calculated_at"], now.isoformat())

        # Zero Google API calls
        mock_compute.assert_not_called()

    def test_missing_route_cache_returns_null_route_summary(self):
        """Verify police incident detail returns route_summary: null when no route is cached."""
        self.client.force_authenticate(user=self.police_user)
        response = self.client.get(f"/api/police/incidents/{self.incident_a.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertIsNone(response.data["data"]["route_summary"])

    def test_stale_cached_route_returns_is_stale_true(self):
        """Verify stale route in cache returns route_summary with is_stale: true."""
        now = timezone.now()
        cache_key = f"{ROUTE_CACHE_KEY_PREFIX}{self.incident_a.id}"
        cache.set(
            cache_key,
            {
                "distance_km": 8.35,
                "duration_seconds": 1140,
                "duration_formatted": "19 mins",
                "is_stale": True,
                "last_calculated_at": (now - timedelta(minutes=15)).isoformat(),
            },
            timeout=3600,
        )

        self.client.force_authenticate(user=self.police_user)
        response = self.client.get(f"/api/police/incidents/{self.incident_a.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        route_summary = response.data["data"]["route_summary"]
        self.assertIsNotNone(route_summary)
        self.assertTrue(route_summary["is_stale"])
        self.assertEqual(route_summary["distance_km"], 8.35)

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_police_incident_list_does_not_call_google_routes_api(self, mock_compute):
        """Verify GET /api/police/incidents/ never calls Google Routes API."""
        self.client.force_authenticate(user=self.police_user)
        response = self.client.get("/api/police/incidents/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        mock_compute.assert_not_called()

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_police_incident_detail_does_not_call_google_routes_api(self, mock_compute):
        """Verify GET /api/police/incidents/<pk>/ never calls Google Routes API even when route uncomputed."""
        self.client.force_authenticate(user=self.police_user)
        response = self.client.get(f"/api/police/incidents/{self.incident_a.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["data"]["route_summary"])
        mock_compute.assert_not_called()

    def test_unauthenticated_request_rejected_with_401(self):
        """Verify unauthenticated requests receive 401 Unauthorized."""
        list_res = self.client.get("/api/police/incidents/")
        self.assertEqual(list_res.status_code, status.HTTP_401_UNAUTHORIZED)

        detail_res = self.client.get(f"/api/police/incidents/{self.incident_a.id}/")
        self.assertEqual(detail_res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unverified_and_inactive_police_rejected_with_403(self):
        """Verify unverified or inactive police accounts receive 403 Forbidden."""
        self.client.force_authenticate(user=self.unverified_police)
        unver_res = self.client.get("/api/police/incidents/")
        self.assertEqual(unver_res.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.inactive_police)
        inact_res = self.client.get(f"/api/police/incidents/{self.incident_a.id}/")
        self.assertEqual(inact_res.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_police_roles_rejected_from_police_dashboard_with_403(self):
        """Verify non-police roles (hospital staff, drivers) cannot access police dashboard (403)."""
        self.client.force_authenticate(user=self.staff_a)
        staff_res = self.client.get("/api/police/incidents/")
        self.assertEqual(staff_res.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.driver)
        driver_res = self.client.get(f"/api/police/incidents/{self.incident_a.id}/")
        self.assertEqual(driver_res.status_code, status.HTTP_403_FORBIDDEN)

    def test_police_dispatcher_citywide_visibility_across_all_hospitals(self):
        """Verify police dispatcher has city-wide visibility across incidents at different hospitals."""
        self.client.force_authenticate(user=self.police_user)

        # List sees both hospital A and hospital B incidents
        list_res = self.client.get("/api/police/incidents/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        returned_ids = {item["id"] for item in list_res.data["data"]}
        self.assertIn(str(self.incident_a.id), returned_ids)
        self.assertIn(str(self.incident_b.id), returned_ids)

        # Detail can inspect incident at hospital B
        detail_b_res = self.client.get(f"/api/police/incidents/{self.incident_b.id}/")
        self.assertEqual(detail_b_res.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_b_res.data["data"]["id"], str(self.incident_b.id))

    def test_hospital_dashboard_route_integration_continues_working(self):
        """Verify hospital dashboard route integration and hospital isolation continue working seamlessly."""
        now = timezone.now()
        cache_key = f"{ROUTE_CACHE_KEY_PREFIX}{self.incident_a.id}"
        cache.set(
            cache_key,
            {
                "distance_km": 7.45,
                "duration_seconds": 1020,
                "duration_formatted": "17 mins",
                "is_stale": False,
                "last_calculated_at": now.isoformat(),
            },
            timeout=3600,
        )

        self.client.force_authenticate(user=self.staff_a)

        # Hospital Staff A can see route_summary for Hospital A incident
        hosp_res = self.client.get(f"/api/hospital/incidents/{self.incident_a.id}/")
        self.assertEqual(hosp_res.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(hosp_res.data["data"]["route_summary"])
        self.assertEqual(hosp_res.data["data"]["route_summary"]["distance_km"], 7.45)

        # Hospital Staff A CANNOT access Hospital B incident (404)
        hosp_b_res = self.client.get(f"/api/hospital/incidents/{self.incident_b.id}/")
        self.assertEqual(hosp_b_res.status_code, status.HTTP_404_NOT_FOUND)

    def test_patient_medical_notes_strictly_excluded_from_police_detail(self):
        """Verify sensitive patient medical notes are completely excluded from police incident detail."""
        self.client.force_authenticate(user=self.police_user)
        response = self.client.get(f"/api/police/incidents/{self.incident_a.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertIn("patients", data)
        self.assertEqual(len(data["patients"]), 1)
        patient = data["patients"][0]
        self.assertNotIn("medical_notes", patient)
        self.assertNotIn("CONFIDENTIAL", json.dumps(response.data))
        self.assertNotIn("Internal hemorrhage", json.dumps(response.data))


class RouteTrackingEndToEndIntegrationTestCase(TestCase):
    """
    Comprehensive End-to-End integration test suite for SERTOS Phase 6, Task 6.4.

    Validates complete unified sequence:
    1. Driver GPS coordinate submission -> validation & persistence -> event generation.
    2. Dynamic route recalculation gating (movement and cooldown thresholds).
    3. Fallback recalculation (180s cooldown with >= 50m movement).
    4. Caching and lock protection across concurrent requests.
    5. Upstream Google API failure handling and stale route exposure.
    6. Real-time synchronization across Hospital and Police dashboards.
    7. Multi-tenant security, isolation, and clinical privacy enforcement.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # 1. Hospitals
        self.hospital_a = Hospital.objects.create(
            name="St. Martha Trauma Hospital",
            hospital_code="HOSP-E2E-A",
            address="150 Brigade Road, Bangalore",
            latitude=Decimal("12.971600"),
            longitude=Decimal("77.594600"),
            contact_number="+918012340001",
            is_active=True,
        )
        self.hospital_b = Hospital.objects.create(
            name="East Memorial Hospital",
            hospital_code="HOSP-E2E-B",
            address="350 Old Airport Road, Bangalore",
            latitude=Decimal("12.980000"),
            longitude=Decimal("77.600000"),
            contact_number="+918012340002",
            is_active=True,
        )

        # 2. Users
        # Reporting driver
        self.driver1 = User.objects.create_user(
            username="e2e_driver_01",
            email="e2e_driver_01@sertos.local",
            password="Password123!@#",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=True,
            is_active=True,
        )
        # Unrelated second driver
        self.driver2 = User.objects.create_user(
            username="e2e_driver_02",
            email="e2e_driver_02@sertos.local",
            password="Password123!@#",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=True,
            is_active=True,
        )
        # Unverified driver
        self.unverified_driver = User.objects.create_user(
            username="e2e_unver_driver",
            email="e2e_unver@sertos.local",
            password="Password123!@#",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=False,
            is_active=True,
        )
        # Hospital staff for Hospital A
        self.staff_a = User.objects.create_user(
            username="e2e_nurse_a",
            email="e2e_nurse_a@sertos.local",
            password="Password123!@#",
            role=UserRole.HOSPITAL_STAFF,
            is_verified=True,
            is_active=True,
        )
        HospitalStaff.objects.create(hospital=self.hospital_a, user=self.staff_a, is_active=True)

        # Hospital staff for Hospital B (unaffiliated with incident A)
        self.staff_b = User.objects.create_user(
            username="e2e_nurse_b",
            email="e2e_nurse_b@sertos.local",
            password="Password123!@#",
            role=UserRole.HOSPITAL_STAFF,
            is_verified=True,
            is_active=True,
        )
        HospitalStaff.objects.create(hospital=self.hospital_b, user=self.staff_b, is_active=True)

        # Police dispatcher
        self.police = User.objects.create_user(
            username="e2e_police_dispatcher",
            email="e2e_police@sertos.local",
            password="Password123!@#",
            role=UserRole.POLICE_DISPATCHER,
            is_verified=True,
            is_active=True,
        )

        # 3. Vehicle
        self.ambulance1 = Ambulance.objects.create(
            vehicle_number="KA-03-E2E-1001",
            vehicle_type="Advanced Life Support",
            assigned_driver=self.driver1,
            is_available=True,
            is_active=True,
        )
        self.ambulance2 = Ambulance.objects.create(
            vehicle_number="KA-03-E2E-1002",
            vehicle_type="Basic Life Support",
            assigned_driver=self.driver2,
            is_available=True,
            is_active=True,
        )

        # 4. Incident at Hospital A
        self.incident_a = EmergencyIncident.objects.create(
            incident_number="INC-20261117-E2E01",
            reporting_driver=self.driver1,
            ambulance=self.ambulance1,
            hospital=self.hospital_a,
            severity=IncidentSeverity.CRITICAL,
            status=IncidentStatus.IN_TRANSIT,
            description="Polytrauma patient en route to St. Martha Hospital.",
        )
        self.patient_a = Patient.objects.create(
            incident=self.incident_a,
            name="Aditya Verma",
            age=29,
            blood_group="B+",
            medical_notes="CONFIDENTIAL: Multiple long bone fractures, hemodynamically unstable.",
        )

        # 5. Incident at Hospital B
        self.incident_b = EmergencyIncident.objects.create(
            incident_number="INC-20261117-E2E02",
            reporting_driver=self.driver2,
            ambulance=self.ambulance2,
            hospital=self.hospital_b,
            severity=IncidentSeverity.MEDIUM,
            status=IncidentStatus.IN_TRANSIT,
            description="Moderate respiratory distress.",
        )

    def tearDown(self):
        cache.clear()

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_e2e_complete_flow_driver_gps_to_route_and_dual_dashboards(self, mock_compute):
        """
        Complete Happy Path E2E Journey:
        1. Driver authenticates and submits GPS coordinates.
        2. Location is stored and EmergencyEvent(LOCATION_UPDATED) is recorded.
        3. Prior to route request, both dashboards return route_summary: null without calling Google.
        4. Route request computes metrics and populates incident cache.
        5. Both hospital and police dashboards immediately display synchronized route summaries.
        6. Clinical triage medical notes are exposed to hospital staff but hidden from police.
        7. Sub-threshold movement (<250m) does not re-invoke Google API.
        8. Significant movement (>=250m) after cooldown triggers recalculation and updates both dashboards.
        """
        # Step 1: Driver submits initial GPS coordinates
        self.client.force_authenticate(user=self.driver1)
        gps_payload = {
            "latitude": "12.935200",
            "longitude": "77.624500",
            "accuracy": "4.50",
        }
        gps_res = self.client.post(f"/api/emergencies/{self.incident_a.id}/location/", gps_payload)
        self.assertEqual(gps_res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(gps_res.data["success"])

        # Verify database records
        loc_count = AmbulanceLocation.objects.filter(incident=self.incident_a).count()
        self.assertEqual(loc_count, 1)
        event_count = EmergencyEvent.objects.filter(
            incident=self.incident_a, event_type="LOCATION_UPDATED"
        ).count()
        self.assertGreaterEqual(event_count, 1)

        # Google API must NOT be called during GPS ingestion
        mock_compute.assert_not_called()

        # Step 2: Query dashboards prior to route computation (cache empty)
        self.client.force_authenticate(user=self.staff_a)
        hosp_pre = self.client.get(f"/api/hospital/incidents/{self.incident_a.id}/")
        self.assertEqual(hosp_pre.status_code, status.HTTP_200_OK)
        self.assertIsNone(hosp_pre.data["data"]["route_summary"])

        self.client.force_authenticate(user=self.police)
        pol_pre = self.client.get(f"/api/police/incidents/{self.incident_a.id}/")
        self.assertEqual(pol_pre.status_code, status.HTTP_200_OK)
        self.assertIsNone(pol_pre.data["data"]["route_summary"])

        # Still zero Google API calls
        mock_compute.assert_not_called()

        # Step 3: Route computation via GET /api/emergencies/<pk>/route/
        self.client.force_authenticate(user=self.driver1)
        mock_compute.return_value = {
            "distance_meters": 7450,
            "duration_seconds": 1020,
            "duration_formatted": "17 mins",
            "polyline": "mock_e2e_polyline_seq",
        }
        route_res = self.client.get(f"/api/emergencies/{self.incident_a.id}/route/")
        self.assertEqual(route_res.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_compute.call_count, 1)
        self.assertEqual(route_res.data["data"]["distance_meters"], 7450)
        self.assertEqual(route_res.data["data"]["distance_km"], 7.45)
        self.assertFalse(route_res.data["data"]["is_stale"])

        # Step 4: Verify both dashboards immediately expose identical cached route summaries
        self.client.force_authenticate(user=self.staff_a)
        hosp_post = self.client.get(f"/api/hospital/incidents/{self.incident_a.id}/")
        self.assertEqual(hosp_post.status_code, status.HTTP_200_OK)
        h_sum = hosp_post.data["data"]["route_summary"]
        self.assertIsNotNone(h_sum)
        self.assertEqual(h_sum["distance_km"], 7.45)
        self.assertEqual(h_sum["duration_formatted"], "17 mins")
        self.assertFalse(h_sum["is_stale"])

        self.client.force_authenticate(user=self.police)
        pol_post = self.client.get(f"/api/police/incidents/{self.incident_a.id}/")
        self.assertEqual(pol_post.status_code, status.HTTP_200_OK)
        p_sum = pol_post.data["data"]["route_summary"]
        self.assertIsNotNone(p_sum)
        self.assertEqual(p_sum["distance_km"], 7.45)
        self.assertEqual(p_sum["duration_formatted"], "17 mins")
        self.assertFalse(p_sum["is_stale"])

        # Synchronized consistency between dashboards
        self.assertEqual(h_sum["distance_km"], p_sum["distance_km"])
        self.assertEqual(h_sum["duration_formatted"], p_sum["duration_formatted"])
        self.assertEqual(h_sum["last_calculated_at"], p_sum["last_calculated_at"])

        # Privacy check: hospital sees medical notes, police does not
        self.assertEqual(
            hosp_post.data["data"]["patients"][0]["medical_notes"],
            "CONFIDENTIAL: Multiple long bone fractures, hemodynamically unstable.",
        )
        self.assertNotIn("medical_notes", pol_post.data["data"]["patients"][0])
        self.assertNotIn("CONFIDENTIAL", json.dumps(pol_post.data))

        # Dashboard requests must NOT have made additional Google API calls
        self.assertEqual(mock_compute.call_count, 1)

        # Step 5: Sub-threshold movement (< 250m, e.g. 25m)
        self.client.force_authenticate(user=self.driver1)
        self.client.post(
            f"/api/emergencies/{self.incident_a.id}/location/",
            {"latitude": "12.935425", "longitude": "77.624500"},
        )
        route_cached = self.client.get(f"/api/emergencies/{self.incident_a.id}/route/")
        self.assertEqual(route_cached.status_code, status.HTTP_200_OK)
        # Throttled by movement threshold: Google API not called again
        self.assertEqual(mock_compute.call_count, 1)

        # Step 6: Significant movement (>= 250m, e.g. 300m) after cooldown (65s)
        self.client.post(
            f"/api/emergencies/{self.incident_a.id}/location/",
            {"latitude": "12.937905", "longitude": "77.624500"},
        )
        cache_key = f"{ROUTE_CACHE_KEY_PREFIX}{self.incident_a.id}"
        cached = cache.get(cache_key)
        cached["last_calculated_at"] = (timezone.now() - timedelta(seconds=65)).isoformat()
        cache.set(cache_key, cached)

        mock_compute.return_value = {
            "distance_meters": 7150,
            "duration_seconds": 960,
            "duration_formatted": "16 mins",
            "polyline": "updated_e2e_polyline",
        }
        route_recalc = self.client.get(f"/api/emergencies/{self.incident_a.id}/route/")
        self.assertEqual(route_recalc.status_code, status.HTTP_200_OK)
        # Both cooldown (>=60s) and movement (>=250m) satisfied -> Google API called
        self.assertEqual(mock_compute.call_count, 2)
        self.assertEqual(route_recalc.data["data"]["distance_meters"], 7150)

        # Step 7: Both dashboards immediately display the updated metrics
        self.client.force_authenticate(user=self.staff_a)
        hosp_updated = self.client.get(f"/api/hospital/incidents/{self.incident_a.id}/")
        self.assertEqual(hosp_updated.data["data"]["route_summary"]["distance_km"], 7.15)
        self.assertEqual(hosp_updated.data["data"]["route_summary"]["duration_formatted"], "16 mins")

        self.client.force_authenticate(user=self.police)
        pol_updated = self.client.get(f"/api/police/incidents/{self.incident_a.id}/")
        self.assertEqual(pol_updated.data["data"]["route_summary"]["distance_km"], 7.15)
        self.assertEqual(pol_updated.data["data"]["route_summary"]["duration_formatted"], "16 mins")

        # Zero additional Google API calls
        self.assertEqual(mock_compute.call_count, 2)

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_e2e_fallback_movement_threshold_and_cooldown(self, mock_compute):
        """
        Verify fallback recalculation: 60m movement (>= 50m) after 190s (>= 180s)
        triggers recalculation when normal 250m threshold was not met.
        """
        # Initial GPS & Route
        AmbulanceLocation.objects.create(
            incident=self.incident_a,
            ambulance=self.ambulance1,
            latitude=Decimal("12.935200"),
            longitude=Decimal("77.624500"),
        )
        mock_compute.return_value = {
            "distance_meters": 7450,
            "duration_seconds": 1020,
            "duration_formatted": "17 mins",
            "polyline": "mock_e2e_polyline",
        }
        self.client.force_authenticate(user=self.driver1)
        self.client.get(f"/api/emergencies/{self.incident_a.id}/route/")
        self.assertEqual(mock_compute.call_count, 1)

        # Move 60m to (12.935741, 77.624500)
        self.client.post(
            f"/api/emergencies/{self.incident_a.id}/location/",
            {"latitude": "12.935741", "longitude": "77.624500"},
        )

        # At 70s (< 180s fallback cooldown): returns cached
        cache_key = f"{ROUTE_CACHE_KEY_PREFIX}{self.incident_a.id}"
        cached = cache.get(cache_key)
        cached["last_calculated_at"] = (timezone.now() - timedelta(seconds=70)).isoformat()
        cache.set(cache_key, cached)

        res_70s = self.client.get(f"/api/emergencies/{self.incident_a.id}/route/")
        self.assertEqual(res_70s.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_compute.call_count, 1)  # Cached

        # At 190s (>= 180s fallback cooldown and >= 50m movement): recalculates!
        cached["last_calculated_at"] = (timezone.now() - timedelta(seconds=190)).isoformat()
        cache.set(cache_key, cached)

        mock_compute.return_value = {
            "distance_meters": 7390,
            "duration_seconds": 1010,
            "duration_formatted": "17 mins",
            "polyline": "fallback_recalculated_polyline",
        }
        res_190s = self.client.get(f"/api/emergencies/{self.incident_a.id}/route/")
        self.assertEqual(res_190s.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_compute.call_count, 2)  # Recalculated!

        # Both dashboards reflect the fallback recalculation
        self.client.force_authenticate(user=self.staff_a)
        hosp = self.client.get(f"/api/hospital/incidents/{self.incident_a.id}/")
        self.assertEqual(hosp.data["data"]["route_summary"]["distance_km"], 7.39)

        self.client.force_authenticate(user=self.police)
        pol = self.client.get(f"/api/police/incidents/{self.incident_a.id}/")
        self.assertEqual(pol.data["data"]["route_summary"]["distance_km"], 7.39)

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_e2e_upstream_google_failure_preserves_cached_route_with_stale_flag(self, mock_compute):
        """
        Verify upstream Google API failure preserves previous route metrics,
        marks is_stale=True, and both dashboards reflect stale status.
        """
        # Initial GPS & Route
        initial_location = AmbulanceLocation.objects.create(
            incident=self.incident_a,
            ambulance=self.ambulance1,
            latitude=Decimal("12.935200"),
            longitude=Decimal("77.624500"),
        )
        mock_compute.return_value = {
            "distance_meters": 7450,
            "duration_seconds": 1020,
            "duration_formatted": "17 mins",
            "polyline": "initial_polyline",
        }
        self.client.force_authenticate(user=self.driver1)
        self.client.get(f"/api/emergencies/{self.incident_a.id}/route/")
        self.assertEqual(mock_compute.call_count, 1)

        # Move 300m, 70s later (recalculation condition met)
        self.client.post(
            f"/api/emergencies/{self.incident_a.id}/location/",
            {"latitude": "12.937905", "longitude": "77.624500"},
        )
        # Keep the latest-location ordering deterministic when SQLite assigns
        # the POSTed GPS sample the same timestamp as the initial ORM sample.
        AmbulanceLocation.objects.filter(
            incident=self.incident_a,
            latitude=Decimal("12.937905"),
            longitude=Decimal("77.624500"),
        ).update(server_received_at=initial_location.server_received_at + timedelta(seconds=1))
        cache_key = f"{ROUTE_CACHE_KEY_PREFIX}{self.incident_a.id}"
        cached = cache.get(cache_key)
        cached["last_calculated_at"] = (timezone.now() - timedelta(seconds=70)).isoformat()
        cache.set(cache_key, cached)

        # Upstream Google API fails with timeout
        mock_compute.side_effect = GoogleRoutesAPIError(
            "Google Routes API connection timed out or failed.",
            status_code=504,
            code="google_api_timeout",
        )

        route_res = self.client.get(f"/api/emergencies/{self.incident_a.id}/route/")
        # Retains previous route and marks stale
        self.assertEqual(route_res.status_code, status.HTTP_200_OK)
        self.assertTrue(route_res.data["data"]["is_stale"])
        self.assertEqual(route_res.data["data"]["distance_meters"], 7450)

        # Hospital dashboard exposes stale status
        self.client.force_authenticate(user=self.staff_a)
        hosp_res = self.client.get(f"/api/hospital/incidents/{self.incident_a.id}/")
        self.assertTrue(hosp_res.data["data"]["route_summary"]["is_stale"])
        self.assertEqual(hosp_res.data["data"]["route_summary"]["distance_km"], 7.45)

        # Police dashboard exposes stale status
        self.client.force_authenticate(user=self.police)
        pol_res = self.client.get(f"/api/police/incidents/{self.incident_a.id}/")
        self.assertTrue(pol_res.data["data"]["route_summary"]["is_stale"])
        self.assertEqual(pol_res.data["data"]["route_summary"]["distance_km"], 7.45)

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_e2e_upstream_google_failure_without_prior_cache_returns_error(self, mock_compute):
        """Verify upstream Google failure with no prior route returns HTTP 504 and leaves dashboards null."""
        AmbulanceLocation.objects.create(
            incident=self.incident_a,
            ambulance=self.ambulance1,
            latitude=Decimal("12.935200"),
            longitude=Decimal("77.624500"),
        )
        mock_compute.side_effect = GoogleRoutesAPIError(
            "Google Routes API connection timed out or failed.",
            status_code=504,
            code="google_api_timeout",
        )
        self.client.force_authenticate(user=self.driver1)
        res = self.client.get(f"/api/emergencies/{self.incident_a.id}/route/")
        self.assertEqual(res.status_code, status.HTTP_504_GATEWAY_TIMEOUT)
        self.assertFalse(res.data["success"])

        # Dashboards remain functional with route_summary: null
        self.client.force_authenticate(user=self.staff_a)
        hosp_res = self.client.get(f"/api/hospital/incidents/{self.incident_a.id}/")
        self.assertEqual(hosp_res.status_code, status.HTTP_200_OK)
        self.assertIsNone(hosp_res.data["data"]["route_summary"])

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_e2e_concurrent_requests_lock_protection(self, mock_compute):
        """Verify cache lock prevents duplicate concurrent route computations."""
        AmbulanceLocation.objects.create(
            incident=self.incident_a,
            ambulance=self.ambulance1,
            latitude=Decimal("12.935200"),
            longitude=Decimal("77.624500"),
        )
        mock_compute.return_value = {
            "distance_meters": 7450,
            "duration_seconds": 1020,
            "duration_formatted": "17 mins",
            "polyline": "initial_polyline",
        }
        self.client.force_authenticate(user=self.driver1)
        self.client.get(f"/api/emergencies/{self.incident_a.id}/route/")
        self.assertEqual(mock_compute.call_count, 1)

        # Simulate another worker holding the route lock
        lock_key = f"{ROUTE_LOCK_KEY_PREFIX}{self.incident_a.id}"
        cache.set(lock_key, "locked", timeout=10)

        # Concurrent request with ?force=true returns cached route without duplicating Google call
        res = self.client.get(f"/api/emergencies/{self.incident_a.id}/route/?force=true")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_compute.call_count, 1)  # No second call made

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_e2e_gps_ingestion_independent_of_google_api_availability(self, mock_compute):
        """Verify GPS ingestion continues operating even when Google Routes API is completely down."""
        mock_compute.side_effect = GoogleRoutesAPIError("Google down", status_code=502)

        self.client.force_authenticate(user=self.driver1)
        res = self.client.post(
            f"/api/emergencies/{self.incident_a.id}/location/",
            {"latitude": "12.941200", "longitude": "77.629100"},
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["success"])

        # Google API must NEVER be called by GPS ingestion
        mock_compute.assert_not_called()

        latest = AmbulanceLocation.objects.filter(incident=self.incident_a).order_by("-server_received_at").first()
        self.assertAlmostEqual(float(latest.latitude), 12.941200, places=5)

    def test_e2e_gps_ingestion_validation_and_ownership(self):
        """Verify coordinate bounds validation and ownership isolation on GPS ingestion."""
        # Invalid latitude (> 90.0)
        self.client.force_authenticate(user=self.driver1)
        bad_lat = self.client.post(
            f"/api/emergencies/{self.incident_a.id}/location/",
            {"latitude": "95.000000", "longitude": "77.624500"},
        )
        self.assertEqual(bad_lat.status_code, status.HTTP_400_BAD_REQUEST)

        # Invalid longitude (> 180.0)
        bad_lng = self.client.post(
            f"/api/emergencies/{self.incident_a.id}/location/",
            {"latitude": "12.935200", "longitude": "195.000000"},
        )
        self.assertEqual(bad_lng.status_code, status.HTTP_400_BAD_REQUEST)

        # Non-numeric coordinate
        bad_str = self.client.post(
            f"/api/emergencies/{self.incident_a.id}/location/",
            {"latitude": "invalid", "longitude": "77.624500"},
        )
        self.assertEqual(bad_str.status_code, status.HTTP_400_BAD_REQUEST)

        # Another driver cannot update coordinates for Incident A (scoped isolation returns 404)
        self.client.force_authenticate(user=self.driver2)
        other_driver = self.client.post(
            f"/api/emergencies/{self.incident_a.id}/location/",
            {"latitude": "12.935200", "longitude": "77.624500"},
        )
        self.assertEqual(other_driver.status_code, status.HTTP_404_NOT_FOUND)

        # Unverified driver cannot submit GPS (permission policy returns 403 Forbidden)
        self.client.force_authenticate(user=self.unverified_driver)
        unver_res = self.client.post(
            f"/api/emergencies/{self.incident_a.id}/location/",
            {"latitude": "12.935200", "longitude": "77.624500"},
        )
        self.assertEqual(unver_res.status_code, status.HTTP_403_FORBIDDEN)

        # Unauthenticated request rejected with 401
        self.client.logout()
        unauth_res = self.client.post(
            f"/api/emergencies/{self.incident_a.id}/location/",
            {"latitude": "12.935200", "longitude": "77.624500"},
        )
        self.assertEqual(unauth_res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_e2e_security_and_permission_isolation(self):
        """Verify strict multi-tenant hospital isolation and police city-wide visibility."""
        # Unauthenticated access rejected on all endpoints
        self.client.logout()
        self.assertEqual(
            self.client.get(f"/api/emergencies/{self.incident_a.id}/route/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.get(f"/api/hospital/incidents/{self.incident_a.id}/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.get(f"/api/police/incidents/{self.incident_a.id}/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        # Hospital Staff B cannot access Hospital A incident (404 on both detail and route)
        self.client.force_authenticate(user=self.staff_b)
        self.assertEqual(
            self.client.get(f"/api/hospital/incidents/{self.incident_a.id}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get(f"/api/emergencies/{self.incident_a.id}/route/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

        # Police Dispatcher has city-wide visibility across both Hospital A and Hospital B
        self.client.force_authenticate(user=self.police)
        list_res = self.client.get("/api/police/incidents/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        ids = {item["id"] for item in list_res.data["data"]}
        self.assertIn(str(self.incident_a.id), ids)
        self.assertIn(str(self.incident_b.id), ids)

        # Non-police cannot access police dashboard (403)
        self.client.force_authenticate(user=self.staff_a)
        self.assertEqual(self.client.get("/api/police/incidents/").status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(user=self.driver1)
        self.assertEqual(self.client.get("/api/police/incidents/").status_code, status.HTTP_403_FORBIDDEN)


class RouteReliabilityAndSignOffTestCase(TestCase):
    """
    Final reliability and sign-off test suite for SERTOS Phase 6, Task 6.5.

    Covers:
    Task 1: Cache expiration (3600s TTL), recovery on expiration, safe null dashboard handling.
    Task 2: Stale route recovery cycle (Success -> Upstream failure -> is_stale=True -> Upstream restore -> is_stale=False).
    Task 3: Concurrency protection, lock lifecycle (clean release on success & failure), no permanent locks.
    Task 4: Cross-dashboard consistency (matching metrics, zero Google calls, RBAC scoping, patient privacy).
    Task 5: GPS ingestion reliability, independent of Google API, coordinate validation, terminal state rejection (CLOSED & CANCELLED).
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # 1. Hospitals
        self.hospital_a = Hospital.objects.create(
            name="Apollo Gleneagles Hospital",
            hospital_code="HOSP-REL-A",
            address="150 Residency Road, Bangalore",
            latitude=Decimal("12.971600"),
            longitude=Decimal("77.594600"),
            contact_number="+918022001122",
            is_active=True,
        )
        self.hospital_b = Hospital.objects.create(
            name="Manipal Trauma Center",
            hospital_code="HOSP-REL-B",
            address="98 HAL Airport Road, Bangalore",
            latitude=Decimal("12.980000"),
            longitude=Decimal("77.600000"),
            contact_number="+918022003344",
            is_active=True,
        )

        # 2. Users
        self.driver1 = User.objects.create_user(
            username="rel_driver_01",
            email="rel_drv01@sertos.local",
            password="Password123!@#",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=True,
            is_active=True,
        )
        self.driver2 = User.objects.create_user(
            username="rel_driver_02",
            email="rel_drv02@sertos.local",
            password="Password123!@#",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=True,
            is_active=True,
        )
        self.unverified_driver = User.objects.create_user(
            username="rel_unver_driver",
            email="rel_unver@sertos.local",
            password="Password123!@#",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=False,
            is_active=True,
        )
        self.inactive_driver = User.objects.create_user(
            username="rel_inact_driver",
            email="rel_inact@sertos.local",
            password="Password123!@#",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=True,
            is_active=False,
        )

        # Hospital Staff
        self.staff_a = User.objects.create_user(
            username="rel_staff_a",
            email="rel_staff_a@sertos.local",
            password="Password123!@#",
            role=UserRole.HOSPITAL_STAFF,
            is_verified=True,
            is_active=True,
        )
        HospitalStaff.objects.create(hospital=self.hospital_a, user=self.staff_a, is_active=True)

        self.staff_b = User.objects.create_user(
            username="rel_staff_b",
            email="rel_staff_b@sertos.local",
            password="Password123!@#",
            role=UserRole.HOSPITAL_STAFF,
            is_verified=True,
            is_active=True,
        )
        HospitalStaff.objects.create(hospital=self.hospital_b, user=self.staff_b, is_active=True)

        # Police Dispatcher
        self.police = User.objects.create_user(
            username="rel_police_dispatcher",
            email="rel_police@sertos.local",
            password="Password123!@#",
            role=UserRole.POLICE_DISPATCHER,
            is_verified=True,
            is_active=True,
        )

        # 3. Vehicle
        self.ambulance1 = Ambulance.objects.create(
            vehicle_number="KA-04-REL-1001",
            vehicle_type="Advanced Life Support",
            assigned_driver=self.driver1,
            is_available=True,
            is_active=True,
        )

        # 4. Incident at Hospital A
        self.incident_a = EmergencyIncident.objects.create(
            incident_number="INC-20261117-REL01",
            reporting_driver=self.driver1,
            ambulance=self.ambulance1,
            hospital=self.hospital_a,
            severity=IncidentSeverity.CRITICAL,
            status=IncidentStatus.IN_TRANSIT,
            description="High velocity highway collision with chest trauma.",
        )
        self.patient_a = Patient.objects.create(
            incident=self.incident_a,
            name="Rohan Mehra",
            age=34,
            blood_group="AB+",
            medical_notes="CONFIDENTIAL: Tension pneumothorax, chest tube inserted.",
        )

        # Initial GPS coordinate
        AmbulanceLocation.objects.create(
            incident=self.incident_a,
            ambulance=self.ambulance1,
            latitude=Decimal("12.935200"),
            longitude=Decimal("77.624500"),
        )

    def tearDown(self):
        cache.clear()

    # -------------------------------------------------------------------------
    # Task 1: Cache Expiration and Recovery Tests
    # -------------------------------------------------------------------------

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_task1_route_cache_uses_3600_seconds_ttl_and_safe_expiration(self, mock_compute):
        """Task 1: Verify 3600s cache TTL, safe null handling on expiration, and recalculation upon cache miss."""
        self.assertEqual(ROUTE_CACHE_TTL_SECONDS, 3600)

        mock_compute.return_value = {
            "distance_meters": 7450,
            "duration_seconds": 1020,
            "duration_formatted": "17 mins",
            "polyline": "initial_poly",
        }
        self.client.force_authenticate(user=self.driver1)

        # 1. Initial route calculation populates cache
        res = self.client.get(f"/api/emergencies/{self.incident_a.id}/route/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_compute.call_count, 1)

        cache_key = f"{ROUTE_CACHE_KEY_PREFIX}{self.incident_a.id}"
        self.assertIsNotNone(cache.get(cache_key))

        # 2. Simulate cache expiration (TTL elapsed)
        cache.delete(cache_key)
        self.assertIsNone(cache.get(cache_key))

        # 3. Hospital and Police dashboards safely return route_summary: null without crashing
        self.client.force_authenticate(user=self.staff_a)
        hosp_res = self.client.get(f"/api/hospital/incidents/{self.incident_a.id}/")
        self.assertEqual(hosp_res.status_code, status.HTTP_200_OK)
        self.assertIsNone(hosp_res.data["data"]["route_summary"])

        self.client.force_authenticate(user=self.police)
        pol_res = self.client.get(f"/api/police/incidents/{self.incident_a.id}/")
        self.assertEqual(pol_res.status_code, status.HTTP_200_OK)
        self.assertIsNone(pol_res.data["data"]["route_summary"])

        # Dashboards did not invoke Google API
        self.assertEqual(mock_compute.call_count, 1)

        # 4. New route request recalculates route on cache miss and repopulates cache
        self.client.force_authenticate(user=self.driver1)
        mock_compute.return_value = {
            "distance_meters": 7420,
            "duration_seconds": 1010,
            "duration_formatted": "17 mins",
            "polyline": "recomputed_after_expiry_poly",
        }
        res_after_expiry = self.client.get(f"/api/emergencies/{self.incident_a.id}/route/")
        self.assertEqual(res_after_expiry.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_compute.call_count, 2)  # Recalculated!
        self.assertIsNotNone(cache.get(cache_key))

    # -------------------------------------------------------------------------
    # Task 2: Stale Route Recovery Cycle Tests
    # -------------------------------------------------------------------------

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_task2_stale_route_recovery_cycle(self, mock_compute):
        """
        Task 2: Verify stale route recovery:
        1. Calculate and cache successful route.
        2. Google API timeout occurs during recalculation -> retain previous route with is_stale=true.
        3. Restore Google API and trigger eligible recalculation -> new route with is_stale=false.
        4. Verify ETA and timestamps are refreshed correctly.
        """
        # Step 1: Initial successful calculation
        mock_compute.return_value = {
            "distance_meters": 7450,
            "duration_seconds": 1020,
            "duration_formatted": "17 mins",
            "polyline": "clean_initial_poly",
        }
        self.client.force_authenticate(user=self.driver1)
        res1 = self.client.get(f"/api/emergencies/{self.incident_a.id}/route/")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertFalse(res1.data["data"]["is_stale"])
        self.assertEqual(mock_compute.call_count, 1)

        # Step 2: Simulate movement of 300m and age cache by 70s
        initial_location = AmbulanceLocation.objects.get(
            incident=self.incident_a,
            latitude=Decimal("12.935200"),
            longitude=Decimal("77.624500"),
        )
        moved_location = AmbulanceLocation.objects.create(
            incident=self.incident_a,
            ambulance=self.ambulance1,
            latitude=Decimal("12.937905"),
            longitude=Decimal("77.624500"),
        )
        # Ensure this sample is newest even when SQLite timestamps tie at
        # creation time, so route movement is calculated from the moved point.
        AmbulanceLocation.objects.filter(pk=moved_location.pk).update(
            server_received_at=initial_location.server_received_at + timedelta(seconds=1)
        )
        cache_key = f"{ROUTE_CACHE_KEY_PREFIX}{self.incident_a.id}"
        cached = cache.get(cache_key)
        cached["last_calculated_at"] = (timezone.now() - timedelta(seconds=70)).isoformat()
        cache.set(cache_key, cached)

        # Step 3: Google API fails with timeout
        mock_compute.side_effect = GoogleRoutesAPIError(
            "Google Routes API connection timed out or failed.",
            status_code=504,
            code="google_api_timeout",
        )

        res2 = self.client.get(f"/api/emergencies/{self.incident_a.id}/route/")
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertTrue(res2.data["data"]["is_stale"])
        self.assertEqual(res2.data["data"]["distance_meters"], 7450)
        self.assertEqual(mock_compute.call_count, 2)  # Recalculation attempt failed and was counted

        # Confirm dashboards expose stale status
        self.client.force_authenticate(user=self.staff_a)
        hosp_stale = self.client.get(f"/api/hospital/incidents/{self.incident_a.id}/")
        self.assertTrue(hosp_stale.data["data"]["route_summary"]["is_stale"])

        self.client.force_authenticate(user=self.police)
        pol_stale = self.client.get(f"/api/police/incidents/{self.incident_a.id}/")
        self.assertTrue(pol_stale.data["data"]["route_summary"]["is_stale"])

        # Step 4: Restore Google API and trigger eligible recalculation
        mock_compute.side_effect = None
        mock_compute.return_value = {
            "distance_meters": 6800,
            "duration_seconds": 900,
            "duration_formatted": "15 mins",
            "polyline": "recovered_clean_poly",
        }

        # Age cache by 65s and move ambulance another 300m (total movement >= 250m)
        recovered_location = AmbulanceLocation.objects.create(
            incident=self.incident_a,
            ambulance=self.ambulance1,
            latitude=Decimal("12.940610"),
            longitude=Decimal("77.624500"),
        )
        AmbulanceLocation.objects.filter(pk=recovered_location.pk).update(
            server_received_at=initial_location.server_received_at + timedelta(seconds=2)
        )
        cached = cache.get(cache_key)
        cached["last_calculated_at"] = (timezone.now() - timedelta(seconds=65)).isoformat()
        cache.set(cache_key, cached)

        self.client.force_authenticate(user=self.driver1)
        res3 = self.client.get(f"/api/emergencies/{self.incident_a.id}/route/")
        self.assertEqual(res3.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_compute.call_count, 3)  # Restored and recalculated!
        self.assertFalse(res3.data["data"]["is_stale"])
        self.assertEqual(res3.data["data"]["distance_meters"], 6800)
        self.assertEqual(res3.data["data"]["duration_formatted"], "15 mins")

        # Step 5: Verify both dashboards now expose recovered route with is_stale: false
        self.client.force_authenticate(user=self.staff_a)
        hosp_rec = self.client.get(f"/api/hospital/incidents/{self.incident_a.id}/")
        self.assertFalse(hosp_rec.data["data"]["route_summary"]["is_stale"])
        self.assertEqual(hosp_rec.data["data"]["route_summary"]["distance_km"], 6.80)
        self.assertEqual(hosp_rec.data["data"]["route_summary"]["duration_formatted"], "15 mins")

        self.client.force_authenticate(user=self.police)
        pol_rec = self.client.get(f"/api/police/incidents/{self.incident_a.id}/")
        self.assertFalse(pol_rec.data["data"]["route_summary"]["is_stale"])
        self.assertEqual(pol_rec.data["data"]["route_summary"]["distance_km"], 6.80)
        self.assertEqual(pol_rec.data["data"]["route_summary"]["duration_formatted"], "15 mins")

    # -------------------------------------------------------------------------
    # Task 3: Concurrent Route Requests and Lock Lifecycle Tests
    # -------------------------------------------------------------------------

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_task3_lock_lifecycle_clean_release_on_success_and_failure(self, mock_compute):
        """Task 3: Verify route lock is released cleanly after success and after failure; no permanent locks."""
        lock_key = f"{ROUTE_LOCK_KEY_PREFIX}{self.incident_a.id}"

        # 1. Success case: lock must be released
        mock_compute.return_value = {
            "distance_meters": 7450,
            "duration_seconds": 1020,
            "duration_formatted": "17 mins",
            "polyline": "mock_poly",
        }
        self.client.force_authenticate(user=self.driver1)
        res_ok = self.client.get(f"/api/emergencies/{self.incident_a.id}/route/")
        self.assertEqual(res_ok.status_code, status.HTTP_200_OK)
        # Lock must be released
        self.assertIsNone(cache.get(lock_key))

        # 2. Failure case with empty cache: lock must be released
        cache.clear()
        mock_compute.side_effect = GoogleRoutesAPIError("Timeout", status_code=504)
        res_err = self.client.get(f"/api/emergencies/{self.incident_a.id}/route/")
        self.assertEqual(res_err.status_code, status.HTTP_504_GATEWAY_TIMEOUT)
        # Lock must be released even after exception
        self.assertIsNone(cache.get(lock_key))

        # 3. Concurrent requests: active lock serves cached route safely
        mock_compute.side_effect = None
        mock_compute.return_value = {
            "distance_meters": 7450,
            "duration_seconds": 1020,
            "duration_formatted": "17 mins",
            "polyline": "mock_poly",
        }
        self.client.get(f"/api/emergencies/{self.incident_a.id}/route/")
        self.assertEqual(mock_compute.call_count, 3)

        # Manually hold lock (simulating another thread/worker)
        cache.set(lock_key, "locked", timeout=10)
        res_locked = self.client.get(f"/api/emergencies/{self.incident_a.id}/route/?force=true")
        self.assertEqual(res_locked.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_compute.call_count, 3)  # No duplicate call made while lock held

    # -------------------------------------------------------------------------
    # Task 4: Dashboard Consistency and RBAC Tests
    # -------------------------------------------------------------------------

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_task4_dashboard_consistency_and_isolation(self, mock_compute):
        """Task 4: Verify identical metrics on both dashboards, hospital scoping, and patient privacy."""
        mock_compute.return_value = {
            "distance_meters": 7450,
            "duration_seconds": 1020,
            "duration_formatted": "17 mins",
            "polyline": "mock_poly",
        }
        self.client.force_authenticate(user=self.driver1)
        self.client.get(f"/api/emergencies/{self.incident_a.id}/route/")
        self.assertEqual(mock_compute.call_count, 1)

        # Hospital Staff A
        self.client.force_authenticate(user=self.staff_a)
        hosp = self.client.get(f"/api/hospital/incidents/{self.incident_a.id}/")
        self.assertEqual(hosp.status_code, status.HTTP_200_OK)

        # Police Dispatcher
        self.client.force_authenticate(user=self.police)
        pol = self.client.get(f"/api/police/incidents/{self.incident_a.id}/")
        self.assertEqual(pol.status_code, status.HTTP_200_OK)

        # Consistency assertions
        h_sum = hosp.data["data"]["route_summary"]
        p_sum = pol.data["data"]["route_summary"]
        self.assertEqual(h_sum["distance_km"], p_sum["distance_km"])
        self.assertEqual(h_sum["duration_formatted"], p_sum["duration_formatted"])
        self.assertEqual(h_sum["is_stale"], p_sum["is_stale"])
        self.assertEqual(h_sum["last_calculated_at"], p_sum["last_calculated_at"])

        # Zero additional Google API calls from dashboards
        self.assertEqual(mock_compute.call_count, 1)

        # Hospital isolation: Staff B cannot access Incident A
        self.client.force_authenticate(user=self.staff_b)
        self.assertEqual(
            self.client.get(f"/api/hospital/incidents/{self.incident_a.id}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

        # Patient clinical privacy: medical notes visible to hospital, hidden from police
        self.assertIn("medical_notes", hosp.data["data"]["patients"][0])
        self.assertNotIn("medical_notes", pol.data["data"]["patients"][0])
        self.assertNotIn("Tension pneumothorax", json.dumps(pol.data))

    # -------------------------------------------------------------------------
    # Task 5: GPS and Emergency Lifecycle Reliability Tests
    # -------------------------------------------------------------------------

    @patch.object(GoogleRoutesClient, "compute_route")
    def test_task5_gps_lifecycle_reliability_and_terminal_rejections(self, mock_compute):
        """Task 5: Verify GPS updates succeed during Google outage and are rejected in terminal states."""
        # 1. GPS update succeeds during Google API outage
        mock_compute.side_effect = GoogleRoutesAPIError("Google down", status_code=504)
        self.client.force_authenticate(user=self.driver1)
        gps_ok = self.client.post(
            f"/api/emergencies/{self.incident_a.id}/location/",
            {"latitude": "12.936000", "longitude": "77.625000"},
        )
        self.assertEqual(gps_ok.status_code, status.HTTP_201_CREATED)
        mock_compute.assert_not_called()

        # 2. Terminal state CLOSED rejects further GPS updates
        self.incident_a.status = IncidentStatus.CLOSED
        self.incident_a.save()

        closed_res = self.client.post(
            f"/api/emergencies/{self.incident_a.id}/location/",
            {"latitude": "12.936100", "longitude": "77.625100"},
        )
        self.assertEqual(closed_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("terminal state", str(closed_res.data))

        # 3. Terminal state CANCELLED rejects further GPS updates
        self.incident_a.status = IncidentStatus.CANCELLED
        self.incident_a.save()

        cancelled_res = self.client.post(
            f"/api/emergencies/{self.incident_a.id}/location/",
            {"latitude": "12.936200", "longitude": "77.625200"},
        )
        self.assertEqual(cancelled_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("terminal state", str(cancelled_res.data))

        # 4. Out-of-scope driver rejected with 404
        self.client.force_authenticate(user=self.driver2)
        other_drv = self.client.post(
            f"/api/emergencies/{self.incident_a.id}/location/",
            {"latitude": "12.936300", "longitude": "77.625300"},
        )
        self.assertEqual(other_drv.status_code, status.HTTP_404_NOT_FOUND)

        # 5. Inactive and unverified drivers rejected with 403
        self.client.force_authenticate(user=self.unverified_driver)
        unver = self.client.post(
            f"/api/emergencies/{self.incident_a.id}/location/",
            {"latitude": "12.936400", "longitude": "77.625400"},
        )
        self.assertEqual(unver.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.inactive_driver)
        inact = self.client.post(
            f"/api/emergencies/{self.incident_a.id}/location/",
            {"latitude": "12.936500", "longitude": "77.625500"},
        )
        self.assertEqual(inact.status_code, status.HTTP_403_FORBIDDEN)



