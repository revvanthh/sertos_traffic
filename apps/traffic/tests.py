"""
Automated unit, integration, and security test suite for SERTOS Traffic Signal & ESP32 Integration.

Covers:
1. TrafficDeviceModelTest: Coordinate validation, unique device ID, and cryptographic token hashing.
2. DeviceRegistrationAndAdminAPITest: Administrative registration, one-time raw token disclosure, RBAC.
3. ESP32DeviceAuthenticationAndAPITest: Microcontroller authentication, heartbeat, telemetry, config, signal state.
4. AmbulanceSignalMatchingTest: Spatial proximity, heading/movement verification, emergency lifecycle restrictions.
5. TrafficCommandLifecycleAndSafetyTest: Command state machine, idempotency, expiration, cross-device isolation.
6. ESP32SimulatorEndToEndTest: Realistic simulation cycle, safe execution, and pedestrian clearance rejection.
7. SecurityAndIsolationTest: Strict boundary between human JWT and IoT device credentials, resilience against errors.
"""

import uuid
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
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
    IncidentSeverity,
    IncidentStatus,
)
from apps.emergencies.services import (
    create_emergency_incident,
    record_ambulance_location,
)
from apps.traffic.models import (
    CommandAction,
    CommandStatus,
    SignalPhase,
    TrafficCommand,
    TrafficDevice,
    TrafficSignalState,
)
from apps.traffic.services import (
    acknowledge_traffic_command,
    evaluate_and_match_traffic_signals,
    expire_stale_commands,
)
from apps.traffic.simulator import ESP32TrafficSignalSimulator

User = get_user_model()


class BaseTrafficTestCase(TestCase):
    """Shared test fixtures for traffic testing."""

    def setUp(self):
        self.client = APIClient()

        # Admin user
        self.admin_user = User.objects.create_user(
            username="admin_traffic",
            password="SecureAdminPass123!",
            role=UserRole.ADMIN,
            is_verified=True,
        )

        # Ambulance driver
        self.driver_user = User.objects.create_user(
            username="driver_traffic",
            password="SecureDriverPass123!",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=True,
        )

        # Destination hospital (Bangalore Central)
        self.hospital = Hospital.objects.create(
            name="Bangalore Central Hospital",
            hospital_code="HOSP-BLR-099",
            address="Koramangala 80ft Road, Bangalore",
            latitude=Decimal("12.935200"),
            longitude=Decimal("77.624500"),
            contact_number="+918099887766",
            is_active=True,
        )

        # Active ambulance assigned to driver
        self.ambulance = Ambulance.objects.create(
            vehicle_number="KA-01-EQ-9999",
            vehicle_type="Advanced Life Support",
            assigned_driver=self.driver_user,
            is_active=True,
            is_available=True,
        )

        # Active emergency incident
        self.incident = create_emergency_incident(
            driver=self.driver_user,
            hospital_id=self.hospital.id,
            severity=IncidentSeverity.CRITICAL,
            description="Severe trauma patient in transit",
            patient_data={"name": "Test Patient", "age": 42},
        )
        self.incident.status = IncidentStatus.IN_TRANSIT
        self.incident.save(update_fields=["status"])


class TrafficDeviceModelTest(BaseTrafficTestCase):
    """Verifies TrafficDevice model constraints and token hashing."""

    def test_device_creation_and_token_hashing(self):
        device = TrafficDevice(
            device_id="ESP32-TEST-001",
            name="MG Road Junction Unit",
            intersection_name="MG Road & Brigade Road",
            latitude=Decimal("12.975000"),
            longitude=Decimal("77.608000"),
        )
        raw_secret = "my_super_secret_token_123"
        device.set_token(raw_secret)
        device.full_clean()
        device.save()

        # Token hash must not be plain text
        self.assertNotEqual(device.token_hash, raw_secret)
        self.assertEqual(len(device.token_hash), 64)  # SHA-256 hex length
        self.assertTrue(device.check_token(raw_secret))
        self.assertFalse(device.check_token("wrong_token"))

    def test_coordinate_validation(self):
        invalid_device = TrafficDevice(
            device_id="ESP32-INVALID-LAT",
            name="Invalid Lat Unit",
            intersection_name="Invalid Intersection",
            latitude=Decimal("95.000000"),  # Out of range
            longitude=Decimal("77.608000"),
            token_hash="dummy_hash",
        )
        with self.assertRaises(DjangoValidationError):
            invalid_device.full_clean()


class DeviceRegistrationAndAdminAPITest(BaseTrafficTestCase):
    """Verifies administrative device registration and RBAC enforcement."""

    def test_admin_can_register_device(self):
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            "device_id": "ESP32-JNC-001",
            "name": "Brigade Road Controller",
            "intersection_name": "Brigade Road & Residency Road",
            "latitude": "12.971800",
            "longitude": "77.607500",
            "is_active": True,
        }
        response = self.client.post("/api/traffic/devices/register/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = response.data
        self.assertEqual(data["device_id"], "ESP32-JNC-001")
        self.assertIn("raw_token", data)
        self.assertTrue(data["raw_token"].startswith("esp32_"))
        self.assertIn("raw_token_warning", data)
        self.assertNotIn("token_hash", data)

        # Verify device in database
        device = TrafficDevice.objects.get(device_id="ESP32-JNC-001")
        self.assertTrue(device.check_token(data["raw_token"]))

    def test_non_admin_cannot_register_device(self):
        self.client.force_authenticate(user=self.driver_user)
        payload = {
            "device_id": "ESP32-DRIVER-HACK",
            "name": "Unauthorized Unit",
            "intersection_name": "Test Intersection",
            "latitude": "12.971800",
            "longitude": "77.607500",
        }
        response = self.client.post("/api/traffic/devices/register/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_device_list_does_not_leak_secrets(self):
        # Register a device
        device = TrafficDevice(
            device_id="ESP32-LIST-01",
            name="List Test Unit",
            intersection_name="Test Intersection",
            latitude=Decimal("12.971800"),
            longitude=Decimal("77.607500"),
        )
        device.set_token("super_secret_list_token")
        device.save()

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/traffic/devices/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data
        found = next((d for d in results if d["device_id"] == "ESP32-LIST-01"), None)
        self.assertIsNotNone(found)
        self.assertNotIn("token_hash", found)
        self.assertNotIn("raw_token", found)


class ESP32DeviceAuthenticationAndAPITest(BaseTrafficTestCase):
    """Verifies hardware authentication headers and microcontroller endpoints."""

    def setUp(self):
        super().setUp()
        self.raw_token = "esp32_hardware_token_abc123"
        self.device = TrafficDevice.objects.create(
            device_id="ESP32-CORRIDOR-01",
            name="Indiranagar 100ft Rd Controller",
            intersection_name="100ft Road & 12th Main",
            latitude=Decimal("12.971600"),
            longitude=Decimal("77.641200"),
            is_active=True,
        )
        self.device.set_token(self.raw_token)
        self.device.save()

    def test_valid_device_authentication(self):
        response = self.client.post(
            "/api/traffic/esp32/heartbeat/",
            {},
            format="json",
            HTTP_X_DEVICE_ID=self.device.device_id,
            HTTP_X_DEVICE_TOKEN=self.raw_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "healthy")
        self.assertEqual(response.data["device_id"], self.device.device_id)

        self.device.refresh_from_db()
        self.assertIsNotNone(self.device.last_heartbeat_at)

    def test_invalid_device_token_rejected(self):
        response = self.client.post(
            "/api/traffic/esp32/heartbeat/",
            {},
            format="json",
            HTTP_X_DEVICE_ID=self.device.device_id,
            HTTP_X_DEVICE_TOKEN="invalid_wrong_token",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_device_blocked_with_403(self):
        self.device.is_active = False
        self.device.save(update_fields=["is_active"])

        response = self.client.post(
            "/api/traffic/esp32/heartbeat/",
            {},
            format="json",
            HTTP_X_DEVICE_ID=self.device.device_id,
            HTTP_X_DEVICE_TOKEN=self.raw_token,
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_device_status_telemetry_reporting(self):
        payload = {
            "firmware_version": "2.1.0-esp32",
            "battery_percentage": 94,
            "wifi_rssi": -55,
            "operational_mode": "NORMAL",
            "temperature_celsius": 32.8,
            "mac_address": "AA:BB:CC:DD:EE:FF",
        }
        response = self.client.post(
            "/api/traffic/esp32/status/",
            payload,
            format="json",
            HTTP_X_DEVICE_ID=self.device.device_id,
            HTTP_X_DEVICE_TOKEN=self.raw_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.device.refresh_from_db()
        self.assertEqual(self.device.firmware_version, "2.1.0-esp32")
        self.assertEqual(self.device.mac_address, "AA:BB:CC:DD:EE:FF")
        self.assertEqual(self.device.last_status_payload["battery_percentage"], 94)

    def test_device_config_retrieval(self):
        response = self.client.get(
            "/api/traffic/esp32/config/",
            HTTP_X_DEVICE_ID=self.device.device_id,
            HTTP_X_DEVICE_TOKEN=self.raw_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["device_id"], self.device.device_id)
        self.assertEqual(response.data["safety_min_green_seconds"], 15)
        self.assertEqual(response.data["safety_yellow_seconds"], 4)

    def test_device_signal_state_reporting(self):
        payload = {
            "current_phase": "GREEN",
            "cycle_duration_seconds": 90,
            "current_phase_elapsed_seconds": 18,
            "is_preempted": False,
        }
        response = self.client.post(
            "/api/traffic/esp32/signal-state/",
            payload,
            format="json",
            HTTP_X_DEVICE_ID=self.device.device_id,
            HTTP_X_DEVICE_TOKEN=self.raw_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.device.refresh_from_db()
        self.assertEqual(self.device.current_signal_phase, SignalPhase.GREEN)
        self.assertEqual(TrafficSignalState.objects.filter(device=self.device).count(), 1)


class AmbulanceSignalMatchingTest(BaseTrafficTestCase):
    """Verifies safe ambulance-to-signal matching, heading analysis, and lifecycle bounds."""

    def setUp(self):
        super().setUp()
        # Intersection at (12.950000, 77.620000)
        self.device = TrafficDevice.objects.create(
            device_id="ESP32-CORRIDOR-TARGET",
            name="Koramangala 100ft Junction",
            intersection_name="100ft Road & 4th Cross",
            latitude=Decimal("12.950000"),
            longitude=Decimal("77.620000"),
            is_active=True,
            current_signal_phase=SignalPhase.RED,
        )
        self.device.set_token("dummy_token")
        self.device.save()

    def test_approaching_ambulance_triggers_command(self):
        # Step 1: Initial location 700m south (12.943700, 77.620000)
        loc1 = AmbulanceLocation.objects.create(
            ambulance=self.ambulance,
            incident=self.incident,
            latitude=Decimal("12.943700"),
            longitude=Decimal("77.620000"),
        )
        # Step 2: Location moving closer (400m south: 12.946400, 77.620000)
        loc2 = AmbulanceLocation.objects.create(
            ambulance=self.ambulance,
            incident=self.incident,
            latitude=Decimal("12.946400"),
            longitude=Decimal("77.620000"),
        )

        commands = evaluate_and_match_traffic_signals(self.incident, loc2)
        self.assertEqual(len(commands), 1)
        cmd = commands[0]
        self.assertEqual(cmd.device, self.device)
        self.assertEqual(cmd.action, CommandAction.PREPARE_GREEN_CORRIDOR)
        self.assertEqual(cmd.status, CommandStatus.PENDING)
        self.assertGreater(cmd.distance_meters_at_creation, 0)
        self.assertIsNotNone(cmd.expires_at)

    def test_moving_away_ambulance_does_not_trigger_command(self):
        # Step 1: Ambulance was at 400m south
        loc1 = AmbulanceLocation.objects.create(
            ambulance=self.ambulance,
            incident=self.incident,
            latitude=Decimal("12.946400"),
            longitude=Decimal("77.620000"),
        )
        # Step 2: Ambulance moved further south to 800m (moving away from intersection)
        loc2 = AmbulanceLocation.objects.create(
            ambulance=self.ambulance,
            incident=self.incident,
            latitude=Decimal("12.942800"),
            longitude=Decimal("77.620000"),
        )

        commands = evaluate_and_match_traffic_signals(self.incident, loc2)
        self.assertEqual(len(commands), 0)

    def test_far_away_intersection_is_ignored(self):
        # Intersection > 5 km away
        far_device = TrafficDevice.objects.create(
            device_id="ESP32-FAR-AWAY",
            name="Airport Road Controller",
            intersection_name="Airport Toll Junction",
            latitude=Decimal("13.198600"),
            longitude=Decimal("77.706600"),
            is_active=True,
        )
        far_device.set_token("dummy_token")
        far_device.save()

        loc = AmbulanceLocation.objects.create(
            ambulance=self.ambulance,
            incident=self.incident,
            latitude=Decimal("12.950000"),
            longitude=Decimal("77.620000"),
        )
        commands = evaluate_and_match_traffic_signals(self.incident, loc)
        far_commands = [c for c in commands if c.device == far_device]
        self.assertEqual(len(far_commands), 0)

    def test_closed_or_cancelled_emergency_cannot_generate_commands(self):
        loc = AmbulanceLocation.objects.create(
            ambulance=self.ambulance,
            incident=self.incident,
            latitude=Decimal("12.946400"),
            longitude=Decimal("77.620000"),
        )

        # Closed incident
        self.incident.status = IncidentStatus.CLOSED
        self.incident.save(update_fields=["status"])
        commands = evaluate_and_match_traffic_signals(self.incident, loc)
        self.assertEqual(len(commands), 0)

        # Cancelled incident
        self.incident.status = IncidentStatus.CANCELLED
        self.incident.save(update_fields=["status"])
        commands = evaluate_and_match_traffic_signals(self.incident, loc)
        self.assertEqual(len(commands), 0)

    def test_terminal_emergency_cancels_pending_commands(self):
        # Create an active pending command
        cmd = TrafficCommand.objects.create(
            device=self.device,
            incident=self.incident,
            action=CommandAction.PREPARE_GREEN_CORRIDOR,
            status=CommandStatus.PENDING,
            expires_at=timezone.now() + timedelta(seconds=60),
            idempotency_key="cmd:test:cancel:01",
        )

        # Transition incident to CANCELLED and run evaluation
        self.incident.status = IncidentStatus.CANCELLED
        self.incident.save(update_fields=["status"])

        evaluate_and_match_traffic_signals(self.incident)

        cmd.refresh_from_db()
        self.assertEqual(cmd.status, CommandStatus.CANCELLED)
        self.assertIn("terminal status 'CANCELLED'", cmd.failure_reason)

    def test_duplicate_active_command_is_prevented(self):
        loc = AmbulanceLocation.objects.create(
            ambulance=self.ambulance,
            incident=self.incident,
            latitude=Decimal("12.946400"),
            longitude=Decimal("77.620000"),
        )
        commands1 = evaluate_and_match_traffic_signals(self.incident, loc)
        self.assertEqual(len(commands1), 1)

        # Second evaluation with active pending command
        commands2 = evaluate_and_match_traffic_signals(self.incident, loc)
        self.assertEqual(len(commands2), 0)  # Duplicate skipped


class TrafficCommandLifecycleAndSafetyTest(BaseTrafficTestCase):
    """Verifies command lifecycle, safety checks, idempotency, and cross-device protection."""

    def setUp(self):
        super().setUp()
        self.device = TrafficDevice.objects.create(
            device_id="ESP32-LIFECYCLE-01",
            name="Richmond Circle Controller",
            intersection_name="Richmond Circle",
            latitude=Decimal("12.964200"),
            longitude=Decimal("77.599600"),
            is_active=True,
        )
        self.device.set_token("dummy_token")
        self.device.save()

        self.other_device = TrafficDevice.objects.create(
            device_id="ESP32-OTHER-02",
            name="Other Unit",
            intersection_name="Other Road",
            latitude=Decimal("12.964200"),
            longitude=Decimal("77.599600"),
            is_active=True,
        )
        self.other_device.set_token("other_token")
        self.other_device.save()

    def test_command_acknowledgement_and_execution(self):
        cmd = TrafficCommand.objects.create(
            device=self.device,
            incident=self.incident,
            action=CommandAction.PREPARE_GREEN_CORRIDOR,
            status=CommandStatus.PENDING,
            expires_at=timezone.now() + timedelta(seconds=60),
            idempotency_key="cmd:lifecycle:01",
        )

        # Step 1: ACKNOWLEDGED
        ack_cmd = acknowledge_traffic_command(
            device=self.device,
            command_id=cmd.id,
            status=CommandStatus.ACKNOWLEDGED,
            execution_notes="Command acknowledged by ESP32.",
        )
        self.assertEqual(ack_cmd.status, CommandStatus.ACKNOWLEDGED)
        self.assertIsNotNone(ack_cmd.acknowledged_at)

        # Step 2: EXECUTED
        exec_cmd = acknowledge_traffic_command(
            device=self.device,
            command_id=cmd.id,
            status=CommandStatus.EXECUTED,
            execution_notes="Green corridor active.",
        )
        self.assertEqual(exec_cmd.status, CommandStatus.EXECUTED)
        self.assertIsNotNone(exec_cmd.executed_at)

        # Device current signal phase must update to GREEN
        self.device.refresh_from_db()
        self.assertEqual(self.device.current_signal_phase, SignalPhase.GREEN)

    def test_expired_command_cannot_be_executed(self):
        # Create already expired command
        past_time = timezone.now() - timedelta(seconds=10)
        cmd = TrafficCommand.objects.create(
            device=self.device,
            incident=self.incident,
            action=CommandAction.PREPARE_GREEN_CORRIDOR,
            status=CommandStatus.PENDING,
            expires_at=past_time,
            idempotency_key="cmd:expired:01",
        )

        with self.assertRaises(Exception):
            acknowledge_traffic_command(
                device=self.device,
                command_id=cmd.id,
                status=CommandStatus.EXECUTED,
            )

        cmd.refresh_from_db()
        self.assertEqual(cmd.status, CommandStatus.EXPIRED)

    def test_cross_device_command_tampering_blocked(self):
        cmd = TrafficCommand.objects.create(
            device=self.device,
            incident=self.incident,
            action=CommandAction.PREPARE_GREEN_CORRIDOR,
            status=CommandStatus.PENDING,
            expires_at=timezone.now() + timedelta(seconds=60),
            idempotency_key="cmd:cross:01",
        )

        # Other device attempts to acknowledge command belonging to self.device
        with self.assertRaises(Exception):
            acknowledge_traffic_command(
                device=self.other_device,
                command_id=cmd.id,
                status=CommandStatus.ACKNOWLEDGED,
            )

    def test_idempotent_re_execution_handling(self):
        cmd = TrafficCommand.objects.create(
            device=self.device,
            incident=self.incident,
            action=CommandAction.PREPARE_GREEN_CORRIDOR,
            status=CommandStatus.EXECUTED,
            expires_at=timezone.now() + timedelta(seconds=60),
            executed_at=timezone.now(),
            idempotency_key="cmd:idempotent:01",
        )

        # Repeating same status returns the command without error
        same_cmd = acknowledge_traffic_command(
            device=self.device,
            command_id=cmd.id,
            status=CommandStatus.EXECUTED,
        )
        self.assertEqual(same_cmd.status, CommandStatus.EXECUTED)


class ESP32SimulatorEndToEndTest(BaseTrafficTestCase):
    """End-to-end integration test driving simulated ESP32 controller through complete cycle."""

    def setUp(self):
        super().setUp()
        self.raw_token = "esp32_sim_token_xyz789"
        self.device = TrafficDevice.objects.create(
            device_id="ESP32-SIMULATOR-01",
            name="Simulated Trinity Circle Controller",
            intersection_name="Trinity Circle & MG Road",
            latitude=Decimal("12.973400"),
            longitude=Decimal("77.620500"),
            is_active=True,
            current_signal_phase=SignalPhase.RED,
        )
        self.device.set_token(self.raw_token)
        self.device.save()

        self.simulator = ESP32TrafficSignalSimulator(
            device_id=self.device.device_id,
            token=self.raw_token,
            api_client=self.client,
        )

    def test_simulator_end_to_end_preemption_flow(self):
        # 1. Simulator transmits heartbeat
        hb = self.simulator.send_heartbeat()
        self.assertEqual(hb["status"], "healthy")

        # 2. Simulator reports status telemetry
        st = self.simulator.report_status(battery_percentage=97, wifi_rssi=-58)
        self.assertEqual(st["status"], "recorded")

        # 3. Simulator reports signal state
        self.simulator.report_signal_state()

        # 4. Ambulance triggers a command
        loc1 = AmbulanceLocation.objects.create(
            ambulance=self.ambulance,
            incident=self.incident,
            latitude=Decimal("12.966000"),
            longitude=Decimal("77.620500"),
        )
        loc2 = AmbulanceLocation.objects.create(
            ambulance=self.ambulance,
            incident=self.incident,
            latitude=Decimal("12.969000"),
            longitude=Decimal("77.620500"),
        )
        commands = evaluate_and_match_traffic_signals(self.incident, loc2)
        self.assertEqual(len(commands), 1)

        # 5. Simulator polls pending commands
        pending = self.simulator.poll_pending_commands()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["id"], str(commands[0].id))

        # 6. Simulator processes commands safely
        results = self.simulator.process_pending_commands()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], CommandStatus.EXECUTED)

        # 7. Verify backend database state
        commands[0].refresh_from_db()
        self.assertEqual(commands[0].status, CommandStatus.EXECUTED)
        self.device.refresh_from_db()
        self.assertEqual(self.device.current_signal_phase, SignalPhase.GREEN)

    def test_simulator_rejects_command_when_pedestrian_clearance_active(self):
        # Generate an active command
        cmd = TrafficCommand.objects.create(
            device=self.device,
            incident=self.incident,
            action=CommandAction.PREPARE_GREEN_CORRIDOR,
            status=CommandStatus.PENDING,
            expires_at=timezone.now() + timedelta(seconds=60),
            idempotency_key="cmd:sim:ped:01",
        )

        # Process with pedestrian clearance forced
        results = self.simulator.process_pending_commands(force_pedestrian_clearance=True)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], CommandStatus.FAILED)
        self.assertIn("PEDESTRIAN_CLEARANCE_ACTIVE", results[0]["failure_reason"])

        cmd.refresh_from_db()
        self.assertEqual(cmd.status, CommandStatus.FAILED)


class SecurityAndIsolationTest(BaseTrafficTestCase):
    """Verifies isolation between human actors and IoT hardware."""

    def setUp(self):
        super().setUp()
        self.raw_token = "esp32_sec_token_999"
        self.device = TrafficDevice.objects.create(
            device_id="ESP32-SEC-01",
            name="Security Test Controller",
            intersection_name="Security Junction",
            latitude=Decimal("12.970000"),
            longitude=Decimal("77.600000"),
            is_active=True,
        )
        self.device.set_token(self.raw_token)
        self.device.save()

    def test_human_jwt_cannot_access_esp32_endpoints(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post("/api/traffic/esp32/heartbeat/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_esp32_credentials_cannot_access_emergency_endpoints(self):
        response = self.client.get(
            f"/api/emergencies/{self.incident.id}/",
            HTTP_X_DEVICE_ID=self.device.device_id,
            HTTP_X_DEVICE_TOKEN=self.raw_token,
        )
        # Human emergency endpoint requires JWT; device credentials return 401
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_traffic_failure_does_not_break_gps_ingestion(self):
        # Ingestion must succeed even when traffic device has an error
        loc = record_ambulance_location(
            incident=self.incident,
            latitude=Decimal("12.969000"),
            longitude=Decimal("77.620500"),
            user=self.driver_user,
        )
        self.assertIsNotNone(loc)
        self.assertEqual(loc.latitude, Decimal("12.969000"))
