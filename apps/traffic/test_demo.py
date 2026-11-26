"""
End-to-End Automated Integration Test Suite for SERTOS Task 7.2:
Emergency Lifecycle, Google Routes, and ESP32 Traffic Signal Preemption Demo.

Verifies the complete 9-step demonstration flow:
1. Ambulance driver authenticates via JWT.
2. Driver creates a new emergency incident with synthetic patient triage data.
3. Driver posts live GPS breadcrumbs approaching a traffic intersection.
4. Google Routes API calculates distance, duration, ETA, and polyline.
5. Traffic matching service identifies approaching ambulance and issues an advisory command.
6. ESP32 simulator polls pending commands with hardware credentials.
7. ESP32 simulator acknowledges, safely transitions through clearance phases, executes preemption, and reports signal state.
8. Hospital dashboard retrieves emergency with cached route summary and patient medical notes.
9. Police dashboard retrieves emergency with route summary while strictly excluding patient medical notes.
10. Failure cases:
    - No nearby intersection: preemption skipped cleanly.
    - Unavailable Google API: graceful degradation, GPS updates unaffected.
    - Expired command: controller execution rejected, command marked EXPIRED.
    - Terminal emergency: CANCELLED/CLOSED emergencies cancel pending commands and block new ones.
    - Hospital isolation: unauthorized hospital staff cannot view other hospitals' incidents.
"""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest import mock
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import UserRole
from apps.emergencies.models import (
    Ambulance,
    AmbulanceLocation,
    EmergencyIncident,
    Hospital,
    HospitalStaff,
    HospitalIncidentResponse,
    IncidentSeverity,
    IncidentStatus,
    PoliceIncidentAcknowledgement,
)
from apps.emergencies.routes_service import GoogleRoutesAPIError
from apps.traffic.models import (
    CommandAction,
    CommandStatus,
    SignalPhase,
    TrafficCommand,
    TrafficDevice,
    TrafficSignalState,
)
from apps.traffic.simulator import ESP32TrafficSignalSimulator

User = get_user_model()


class EndToEndSimulatedEmergencyDemoTestCase(TestCase):
    """Full demonstration and failure resilience test suite for Task 7.2."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # 1. Accounts & Roles
        self.driver_password = "SecureDriverPass123!"
        self.driver_user = User.objects.create_user(
            username="driver_rajesh",
            password=self.driver_password,
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=True,
        )

        self.hospital_staff_password = "SecureHospPass123!"
        self.hospital_staff_user = User.objects.create_user(
            username="nurse_anita",
            password=self.hospital_staff_password,
            role=UserRole.HOSPITAL_STAFF,
            is_verified=True,
        )

        self.other_staff_user = User.objects.create_user(
            username="nurse_other",
            password="SecureOtherPass123!",
            role=UserRole.HOSPITAL_STAFF,
            is_verified=True,
        )

        self.police_password = "SecurePolicePass123!"
        self.police_user = User.objects.create_user(
            username="officer_kumar",
            password=self.police_password,
            role=UserRole.POLICE_DISPATCHER,
            is_verified=True,
        )

        # 2. Medical Infrastructure
        self.hospital_a = Hospital.objects.create(
            name="Manipal Emergency Care Bangalore",
            hospital_code="HOSP-BLR-001",
            address="Old Airport Road, Kodihalli, Bangalore",
            latitude=Decimal("12.959200"),
            longitude=Decimal("77.644400"),
            contact_number="+918025024444",
            is_active=True,
        )

        self.hospital_b = Hospital.objects.create(
            name="Apollo Hospitals Jayanagar",
            hospital_code="HOSP-BLR-002",
            address="Jayanagar 4th Block, Bangalore",
            latitude=Decimal("12.926000"),
            longitude=Decimal("77.583000"),
            contact_number="+918026304050",
            is_active=True,
        )

        HospitalStaff.objects.create(
            hospital=self.hospital_a,
            user=self.hospital_staff_user,
            is_active=True,
        )
        HospitalStaff.objects.create(
            hospital=self.hospital_b,
            user=self.other_staff_user,
            is_active=True,
        )

        # 3. Transport Fleet
        self.ambulance = Ambulance.objects.create(
            vehicle_number="KA-01-EQ-7788",
            vehicle_type="Advanced Life Support",
            assigned_driver=self.driver_user,
            is_active=True,
            is_available=True,
        )

        # 4. Traffic Intersection & ESP32 Controller
        # Intersection at (12.971600, 77.641200) - 100ft Rd & 12th Main Indiranagar
        self.device_raw_token = "esp32_secret_demo_token_123456"
        self.traffic_device = TrafficDevice.objects.create(
            device_id="ESP32-BLR-IND-01",
            name="Indiranagar 100ft Rd Controller",
            intersection_name="100ft Road & 12th Main",
            latitude=Decimal("12.971600"),
            longitude=Decimal("77.641200"),
            is_active=True,
            current_signal_phase=SignalPhase.RED,
        )
        self.traffic_device.set_token(self.device_raw_token)
        self.traffic_device.save()

        # Hardware Simulator
        self.simulator = ESP32TrafficSignalSimulator(
            device_id=self.traffic_device.device_id,
            token=self.device_raw_token,
            api_client=self.client,
        )

    def _get_mock_google_routes_response(self):
        """Mocked response simulating GoogleRoutesClient.compute_route."""
        return {
            "distance_meters": 3500,
            "duration_seconds": 540,
            "duration_formatted": "9 mins",
            "polyline": "_p~iF~ps|U_ulLnnqC_mqNvxq`@",
        }

    # =========================================================================
    # Task 7.2 Core Flow Demonstration Test
    # =========================================================================

    @mock.patch("apps.emergencies.routes_service.GoogleRoutesClient.compute_route")
    def test_complete_end_to_end_emergency_and_traffic_demo(self, mock_compute):
        mock_compute.return_value = self._get_mock_google_routes_response()

        # ---------------------------------------------------------------------
        # Step 1: Driver Authentication (JWT)
        # ---------------------------------------------------------------------
        auth_resp = self.client.post(
            "/api/auth/login/",
            {"username": self.driver_user.username, "password": self.driver_password},
            format="json",
        )
        self.assertEqual(auth_resp.status_code, status.HTTP_200_OK)
        driver_jwt = auth_resp.data["data"]["access"]
        self.assertIsNotNone(driver_jwt)

        driver_client = APIClient()
        driver_client.credentials(HTTP_AUTHORIZATION=f"Bearer {driver_jwt}")

        # ---------------------------------------------------------------------
        # Step 2: Driver Creates Emergency Incident with Synthetic Patient
        # ---------------------------------------------------------------------
        incident_payload = {
            "hospital": str(self.hospital_a.id),
            "severity": IncidentSeverity.CRITICAL,
            "description": "Pedestrian vehicular impact, multiple trauma fractures.",
            "patient": {
                "name": "Synthetic Patient Alpha",
                "age": 35,
                "gender": "MALE",
                "blood_group": "B+",
                "medical_notes": "Allergic to penicillin. Severe hypotension, GCS score 11.",
            },
        }
        create_resp = driver_client.post("/api/emergencies/", incident_payload, format="json")
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        create_data = create_resp.data["data"]
        incident_id = create_data["id"]
        incident_number = create_data["incident_number"]
        self.assertEqual(create_data["status"], IncidentStatus.REPORTED)

        # Advance status to IN_TRANSIT
        status_resp = driver_client.patch(
            f"/api/emergencies/{incident_id}/status/",
            {"status": IncidentStatus.ASSIGNED},
            format="json",
        )
        self.assertEqual(status_resp.status_code, status.HTTP_200_OK)

        HospitalIncidentResponse.objects.create(
            incident_id=incident_id,
            hospital=self.hospital_a,
            responded_by=self.hospital_staff_user,
            decision=HospitalIncidentResponse.Decision.ACCEPTED,
        )
        PoliceIncidentAcknowledgement.objects.create(
            incident_id=incident_id,
            acknowledged_by=self.police_user,
        )

        status_resp2 = driver_client.patch(
            f"/api/emergencies/{incident_id}/status/",
            {"status": IncidentStatus.IN_TRANSIT},
            format="json",
        )
        self.assertEqual(status_resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(status_resp2.data["data"]["status"], IncidentStatus.IN_TRANSIT)

        # ---------------------------------------------------------------------
        # Step 3: Driver Submits Live GPS Coordinates Approaching Intersection
        # ---------------------------------------------------------------------
        # Ping 1: 750m south of intersection (12.965000, 77.641200)
        gps1_resp = driver_client.post(
            f"/api/emergencies/{incident_id}/location/",
            {"latitude": "12.965000", "longitude": "77.641200", "accuracy": 5.0},
            format="json",
        )
        self.assertEqual(gps1_resp.status_code, status.HTTP_201_CREATED)

        # Ping 2: 450m south (12.967500, 77.641200) - Approaching!
        gps2_resp = driver_client.post(
            f"/api/emergencies/{incident_id}/location/",
            {"latitude": "12.967500", "longitude": "77.641200", "accuracy": 4.2},
            format="json",
        )
        self.assertEqual(gps2_resp.status_code, status.HTTP_201_CREATED)

        # ---------------------------------------------------------------------
        # Step 4: Backend Calculates Route and ETA via Google Routes
        # ---------------------------------------------------------------------
        route_resp = driver_client.get(f"/api/emergencies/{incident_id}/route/")
        self.assertEqual(route_resp.status_code, status.HTTP_200_OK)
        route_data = route_resp.data["data"]
        self.assertEqual(route_data["distance_meters"], 3500)
        self.assertEqual(route_data["distance_km"], 3.5)
        self.assertEqual(route_data["duration_seconds"], 540)
        self.assertEqual(route_data["duration_formatted"], "9 mins")
        self.assertFalse(route_data["is_stale"])
        self.assertIsNotNone(route_data["estimated_arrival"])
        self.assertIsNotNone(route_data["polyline"])

        # ---------------------------------------------------------------------
        # Step 5: Traffic Matching Service Generated Advisory Preemption Command
        # ---------------------------------------------------------------------
        pending_commands = TrafficCommand.objects.filter(
            device=self.traffic_device,
            incident_id=incident_id,
            status=CommandStatus.PENDING,
        )
        self.assertEqual(pending_commands.count(), 1)
        command = pending_commands.first()
        self.assertEqual(command.action, CommandAction.PREPARE_GREEN_CORRIDOR)
        self.assertGreater(command.distance_meters_at_creation, 0)
        self.assertIsNotNone(command.expires_at)

        # ---------------------------------------------------------------------
        # Step 6: Simulated ESP32 Polls Pending Commands via Hardware API
        # ---------------------------------------------------------------------
        polled_cmds = self.simulator.poll_pending_commands()
        self.assertEqual(len(polled_cmds), 1)
        self.assertEqual(polled_cmds[0]["id"], str(command.id))
        self.assertEqual(polled_cmds[0]["incident_number"], incident_number)

        # ---------------------------------------------------------------------
        # Step 7: Simulator Acknowledges, Executes Safely, and Reports Signal State
        # ---------------------------------------------------------------------
        sim_results = self.simulator.process_pending_commands()
        self.assertEqual(len(sim_results), 1)
        self.assertEqual(sim_results[0]["status"], CommandStatus.EXECUTED)

        # Verify command and device state in backend
        command.refresh_from_db()
        self.assertEqual(command.status, CommandStatus.EXECUTED)
        self.assertIsNotNone(command.acknowledged_at)
        self.assertIsNotNone(command.executed_at)

        self.traffic_device.refresh_from_db()
        self.assertEqual(self.traffic_device.current_signal_phase, SignalPhase.GREEN)

        # Verify signal state log
        signal_states = TrafficSignalState.objects.filter(device=self.traffic_device)
        self.assertTrue(signal_states.exists())
        self.assertEqual(signal_states.first().current_phase, SignalPhase.GREEN)

        # ---------------------------------------------------------------------
        # Step 8: Hospital Dashboard Retrieves Emergency & Cached Route Summary
        # ---------------------------------------------------------------------
        hosp_auth = self.client.post(
            "/api/auth/login/",
            {"username": self.hospital_staff_user.username, "password": self.hospital_staff_password},
            format="json",
        )
        hosp_client = APIClient()
        hosp_client.credentials(HTTP_AUTHORIZATION=f"Bearer {hosp_auth.data['data']['access']}")

        hosp_resp = hosp_client.get(f"/api/hospital/incidents/{incident_id}/")
        self.assertEqual(hosp_resp.status_code, status.HTTP_200_OK)
        hosp_data = hosp_resp.data["data"]

        self.assertEqual(hosp_data["incident_number"], incident_number)
        self.assertEqual(hosp_data["status"], IncidentStatus.IN_TRANSIT)
        self.assertIsNotNone(hosp_data["route_summary"])
        self.assertEqual(hosp_data["route_summary"]["distance_km"], 3.5)
        self.assertEqual(hosp_data["route_summary"]["duration_formatted"], "9 mins")
        self.assertFalse(hosp_data["route_summary"]["is_stale"])

        # Hospital staff CAN see patient medical notes
        self.assertEqual(len(hosp_data["patients"]), 1)
        self.assertEqual(hosp_data["patients"][0]["name"], "Synthetic Patient Alpha")
        self.assertIn("Allergic to penicillin", hosp_data["patients"][0]["medical_notes"])

        # ---------------------------------------------------------------------
        # Step 9: Police Dashboard Retrieves Incident (Excludes Medical Notes)
        # ---------------------------------------------------------------------
        police_auth = self.client.post(
            "/api/auth/login/",
            {"username": self.police_user.username, "password": self.police_password},
            format="json",
        )
        police_client = APIClient()
        police_client.credentials(HTTP_AUTHORIZATION=f"Bearer {police_auth.data['data']['access']}")

        police_resp = police_client.get(f"/api/police/incidents/{incident_id}/")
        self.assertEqual(police_resp.status_code, status.HTTP_200_OK)
        police_data = police_resp.data["data"]

        self.assertEqual(police_data["incident_number"], incident_number)
        self.assertIsNotNone(police_data["route_summary"])
        self.assertEqual(police_data["route_summary"]["distance_km"], 3.5)

        # Police CAN see patient triage count but CANNOT see private medical notes
        self.assertEqual(len(police_data["patients"]), 1)
        self.assertNotIn("medical_notes", police_data["patients"][0])

        # ---------------------------------------------------------------------
        # Step 10: Complete Emergency Lifecycle (ARRIVED -> CLOSED)
        # ---------------------------------------------------------------------
        driver_client.patch(
            f"/api/emergencies/{incident_id}/status/",
            {"status": IncidentStatus.ARRIVED},
            format="json",
        )
        close_resp = driver_client.patch(
            f"/api/emergencies/{incident_id}/status/",
            {"status": IncidentStatus.CLOSED},
            format="json",
        )
        self.assertEqual(close_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(close_resp.data["data"]["status"], IncidentStatus.CLOSED)

    # =========================================================================
    # Failure Cases & Edge Scenarios
    # =========================================================================

    def test_failure_case_no_nearby_device(self):
        """When ambulance is far from any intersection, no command is created."""
        # Incident in transit
        incident = EmergencyIncident.objects.create(
            incident_number="INC-FAR-001",
            reporting_driver=self.driver_user,
            ambulance=self.ambulance,
            hospital=self.hospital_a,
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.IN_TRANSIT,
        )

        driver_client = APIClient()
        driver_client.force_authenticate(user=self.driver_user)

        # GPS coordinates 5 km away from any intersection (12.920000, 77.610000)
        gps_resp = driver_client.post(
            f"/api/emergencies/{incident.id}/location/",
            {"latitude": "12.920000", "longitude": "77.610000", "accuracy": 5.0},
            format="json",
        )
        self.assertEqual(gps_resp.status_code, status.HTTP_201_CREATED)

        # No commands generated
        commands = TrafficCommand.objects.filter(incident=incident)
        self.assertEqual(commands.count(), 0)

    @mock.patch("apps.emergencies.routes_service.GoogleRoutesClient.compute_route")
    def test_failure_case_unavailable_google_api(self, mock_compute):
        """When Google Routes API fails, route endpoint fails gracefully without breaking GPS or emergency flows."""
        mock_compute.side_effect = GoogleRoutesAPIError("Upstream Google Routes API connection timed out.")

        incident = EmergencyIncident.objects.create(
            incident_number="INC-FAIL-GOOGLE-001",
            reporting_driver=self.driver_user,
            ambulance=self.ambulance,
            hospital=self.hospital_a,
            severity=IncidentSeverity.MEDIUM,
            status=IncidentStatus.IN_TRANSIT,
        )

        driver_client = APIClient()
        driver_client.force_authenticate(user=self.driver_user)

        # GPS updates continue to succeed
        gps_resp = driver_client.post(
            f"/api/emergencies/{incident.id}/location/",
            {"latitude": "12.967500", "longitude": "77.641200", "accuracy": 4.0},
            format="json",
        )
        self.assertEqual(gps_resp.status_code, status.HTTP_201_CREATED)

        # Route endpoint returns controlled error
        route_resp = driver_client.get(f"/api/emergencies/{incident.id}/route/")
        self.assertEqual(route_resp.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertFalse(route_resp.data["success"])

    def test_failure_case_expired_command_rejected_by_backend(self):
        """Commands that pass their expiry timestamp cannot be executed by the controller."""
        incident = EmergencyIncident.objects.create(
            incident_number="INC-EXP-001",
            reporting_driver=self.driver_user,
            ambulance=self.ambulance,
            hospital=self.hospital_a,
            status=IncidentStatus.IN_TRANSIT,
        )

        past_time = timezone.now() - timedelta(seconds=15)
        expired_command = TrafficCommand.objects.create(
            device=self.traffic_device,
            incident=incident,
            action=CommandAction.PREPARE_GREEN_CORRIDOR,
            status=CommandStatus.PENDING,
            expires_at=past_time,
            idempotency_key="cmd:expired:test:99",
        )

        # Controller attempts to report execution
        ack_resp = self.client.post(
            f"/api/traffic/esp32/commands/{expired_command.id}/ack/",
            {"status": CommandStatus.EXECUTED, "execution_notes": "Late execution attempt"},
            format="json",
            HTTP_X_DEVICE_ID=self.traffic_device.device_id,
            HTTP_X_DEVICE_TOKEN=self.device_raw_token,
        )
        self.assertEqual(ack_resp.status_code, status.HTTP_400_BAD_REQUEST)

        expired_command.refresh_from_db()
        self.assertEqual(expired_command.status, CommandStatus.EXPIRED)

    def test_failure_case_terminal_emergency_cancels_commands(self):
        """Cancelling or closing an emergency automatically invalidates pending traffic commands."""
        incident = EmergencyIncident.objects.create(
            incident_number="INC-TERM-001",
            reporting_driver=self.driver_user,
            ambulance=self.ambulance,
            hospital=self.hospital_a,
            status=IncidentStatus.IN_TRANSIT,
        )

        active_cmd = TrafficCommand.objects.create(
            device=self.traffic_device,
            incident=incident,
            action=CommandAction.PREPARE_GREEN_CORRIDOR,
            status=CommandStatus.PENDING,
            expires_at=timezone.now() + timedelta(seconds=60),
            idempotency_key="cmd:term:active:01",
        )

        driver_client = APIClient()
        driver_client.force_authenticate(user=self.driver_user)

        # Driver cancels the incident
        cancel_resp = driver_client.patch(
            f"/api/emergencies/{incident.id}/status/",
            {"status": IncidentStatus.CANCELLED},
            format="json",
        )
        self.assertEqual(cancel_resp.status_code, status.HTTP_200_OK)

        # Incident status cancellation immediately cancels pending traffic commands
        active_cmd.refresh_from_db()
        self.assertEqual(active_cmd.status, CommandStatus.CANCELLED)

    def test_hospital_dashboard_isolation(self):
        """Staff at Hospital B cannot view incidents routed to Hospital A."""
        incident = EmergencyIncident.objects.create(
            incident_number="INC-HOSP-ISO-001",
            reporting_driver=self.driver_user,
            ambulance=self.ambulance,
            hospital=self.hospital_a,
            status=IncidentStatus.IN_TRANSIT,
        )

        # Staff at Hospital B attempts to view Hospital A incident
        other_client = APIClient()
        other_client.force_authenticate(user=self.other_staff_user)

        resp = other_client.get(f"/api/hospital/incidents/{incident.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
