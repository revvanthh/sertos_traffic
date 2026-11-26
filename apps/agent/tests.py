"""
Comprehensive test suite for SERTOS AI Emergency Agent Tool Wrappers (Phase 8.1.2).

Tests:
1. Registry & Dispatch:
   - Tool listing and schema metadata.
   - Unrecognized tool handling (TOOL_NOT_FOUND).
   - Invalid argument formatting (VALIDATION_ERROR).
2. Security & Access Control:
   - Unauthenticated invocation (AUTH_REQUIRED).
   - Unauthorized roles: Hospital staff, Police dispatcher, Admin (PERMISSION_DENIED).
   - Inactive or unverified driver accounts (PERMISSION_DENIED).
   - Incident ownership enforcement across drivers (PERMISSION_DENIED).
3. Tool 1: find_nearby_hospitals:
   - Successful proximity query.
   - Substring query filtering.
   - Missing coordinates validation.
4. Tool 2: get_route_eta:
   - Cached route return without external API calls.
   - Missing location fallback message.
   - Resolution by active driver context or specific incident ID.
   - Missing active emergency handling.
5. Tool 3: get_emergency_status:
   - Active emergency auto-resolution.
   - Lookup by incident UUID and incident_number.
   - Return of full patient triage, ambulance, and hospital details.
   - Missing active emergency handling.
   - Non-existent incident handling.
"""

from decimal import Decimal
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
    Gender,
    Hospital,
    IncidentSeverity,
    IncidentStatus,
    Patient,
)
from apps.emergencies.routes_service import ROUTE_CACHE_KEY_PREFIX
from apps.agent.extraction import (
    BreathingStatus,
    ConsciousnessStatus,
    EmergencyType,
    extract_emergency_information,
)
from apps.agent.models import SessionStatus, VoiceAgentSession
from apps.agent.registry import registry

User = get_user_model()


class AgentToolSecurityAndRegistryTests(TestCase):
    """Verifies security controls, permissions, and dispatch mechanics of AgentToolRegistry."""

    def setUp(self):
        cache.clear()

        # 1. Active verified driver
        self.driver = User.objects.create_user(
            username="verified_driver",
            password="StrongPassword123!@#",
            email="driver@sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_active=True,
            is_verified=True,
        )

        # 2. Inactive driver
        self.inactive_driver = User.objects.create_user(
            username="inactive_driver",
            password="StrongPassword123!@#",
            email="inactive_driver@sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_active=False,
            is_verified=True,
        )

        # 3. Unverified driver
        self.unverified_driver = User.objects.create_user(
            username="unverified_driver",
            password="StrongPassword123!@#",
            email="unverified_driver@sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_active=True,
            is_verified=False,
        )

        # 4. Other roles
        self.hospital_user = User.objects.create_user(
            username="hosp_staff",
            password="StrongPassword123!@#",
            email="hospital@sertos.local",
            role=UserRole.HOSPITAL_STAFF,
            is_active=True,
            is_verified=True,
        )

        self.police_user = User.objects.create_user(
            username="police_disp",
            password="StrongPassword123!@#",
            email="police@sertos.local",
            role=UserRole.POLICE_DISPATCHER,
            is_active=True,
            is_verified=True,
        )

    def test_list_tools_returns_all_three_tools(self):
        """Registry lists the three expected tools with descriptions and schemas."""
        tools = registry.list_tools()
        tool_names = [t["name"] for t in tools]

        self.assertIn("find_nearby_hospitals", tool_names)
        self.assertIn("get_route_eta", tool_names)
        self.assertIn("get_emergency_status", tool_names)

        for t in tools:
            self.assertTrue(len(t["description"]) > 10)
            self.assertIn("type", t["parameters"])

    def test_unauthenticated_invocation_rejected(self):
        """Anonymous or None user is rejected with AUTH_REQUIRED."""
        resp_none = registry.execute("find_nearby_hospitals", {"latitude": 12.97, "longitude": 77.59}, user=None)
        self.assertFalse(resp_none["success"])
        self.assertIsNone(resp_none["data"])
        self.assertEqual(resp_none["error"]["code"], "AUTH_REQUIRED")

        class AnonymousMock:
            is_authenticated = False

        resp_anon = registry.execute("find_nearby_hospitals", {"latitude": 12.97, "longitude": 77.59}, user=AnonymousMock())
        self.assertFalse(resp_anon["success"])
        self.assertEqual(resp_anon["error"]["code"], "AUTH_REQUIRED")

    def test_unauthorized_roles_rejected(self):
        """Hospital staff, police dispatchers, and non-drivers cannot execute agent tools."""
        resp_hosp = registry.execute("find_nearby_hospitals", {"latitude": 12.97, "longitude": 77.59}, user=self.hospital_user)
        self.assertFalse(resp_hosp["success"])
        self.assertEqual(resp_hosp["error"]["code"], "PERMISSION_DENIED")

        resp_police = registry.execute("find_nearby_hospitals", {"latitude": 12.97, "longitude": 77.59}, user=self.police_user)
        self.assertFalse(resp_police["success"])
        self.assertEqual(resp_police["error"]["code"], "PERMISSION_DENIED")

    def test_inactive_and_unverified_drivers_rejected(self):
        """Inactive or unverified driver accounts are denied access."""
        resp_inactive = registry.execute("find_nearby_hospitals", {"latitude": 12.97, "longitude": 77.59}, user=self.inactive_driver)
        self.assertFalse(resp_inactive["success"])
        self.assertEqual(resp_inactive["error"]["code"], "PERMISSION_DENIED")

        resp_unverified = registry.execute("find_nearby_hospitals", {"latitude": 12.97, "longitude": 77.59}, user=self.unverified_driver)
        self.assertFalse(resp_unverified["success"])
        self.assertEqual(resp_unverified["error"]["code"], "PERMISSION_DENIED")

    def test_unrecognized_tool_name_rejected(self):
        """Calling an unregistered tool returns TOOL_NOT_FOUND."""
        resp = registry.execute("non_existent_tool", {}, user=self.driver)
        self.assertFalse(resp["success"])
        self.assertEqual(resp["error"]["code"], "TOOL_NOT_FOUND")

    def test_invalid_argument_payload_type(self):
        """Passing non-dictionary arguments returns VALIDATION_ERROR."""
        resp = registry.execute("find_nearby_hospitals", "not-a-dict", user=self.driver)
        self.assertFalse(resp["success"])
        self.assertEqual(resp["error"]["code"], "VALIDATION_ERROR")


class AgentToolFindNearbyHospitalsTests(TestCase):
    """Verifies the find_nearby_hospitals tool wrapper."""

    def setUp(self):
        self.driver = User.objects.create_user(
            username="driver_hosp_test",
            password="StrongPassword123!@#",
            email="driver_hosp@sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_active=True,
            is_verified=True,
        )

        self.hospital_1 = Hospital.objects.create(
            name="Apollo Emergency Hospital",
            hospital_code="HOSP-AGT-01",
            address="100 Richmond Road, Bengaluru",
            latitude=Decimal("12.971600"),
            longitude=Decimal("77.594600"),
            contact_number="+918011111111",
            is_active=True,
        )
        self.hospital_2 = Hospital.objects.create(
            name="Manipal Trauma Care",
            hospital_code="HOSP-AGT-02",
            address="98 HAL Airport Road, Bengaluru",
            latitude=Decimal("12.958000"),
            longitude=Decimal("77.648000"),
            contact_number="+918022222222",
            is_active=True,
        )

    def test_find_nearby_hospitals_success(self):
        """Valid coordinates return structured nearby hospitals in data payload."""
        resp = registry.execute(
            "find_nearby_hospitals",
            {"latitude": 12.975000, "longitude": 77.609000, "max_results": 2},
            user=self.driver,
        )

        self.assertTrue(resp["success"])
        self.assertIsNone(resp["error"])
        data = resp["data"]
        self.assertEqual(data["count"], 2)
        self.assertEqual(len(data["hospitals"]), 2)
        self.assertEqual(data["search_origin"]["latitude"], 12.975)
        self.assertEqual(data["search_origin"]["longitude"], 77.609)
        self.assertIn("distance_km", data["hospitals"][0])

    def test_find_nearby_hospitals_query_filter(self):
        """Optional query filters hospital name case-insensitively."""
        resp = registry.execute(
            "find_nearby_hospitals",
            {"latitude": 12.975000, "longitude": 77.609000, "query": "manipal"},
            user=self.driver,
        )

        self.assertTrue(resp["success"])
        data = resp["data"]
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["hospitals"][0]["id"], str(self.hospital_2.id))

    def test_find_nearby_hospitals_missing_coords(self):
        """Missing latitude or longitude returns VALIDATION_ERROR."""
        resp = registry.execute(
            "find_nearby_hospitals",
            {"latitude": 12.975000},
            user=self.driver,
        )

        self.assertFalse(resp["success"])
        self.assertEqual(resp["error"]["code"], "VALIDATION_ERROR")


class AgentToolRouteAndStatusTests(TestCase):
    """Verifies get_route_eta and get_emergency_status tool wrappers."""

    def setUp(self):
        cache.clear()

        # Driver 1
        self.driver1 = User.objects.create_user(
            username="driver_route_01",
            password="StrongPassword123!@#",
            email="driver1@sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_active=True,
            is_verified=True,
        )

        # Driver 2 (for multi-tenant isolation checks)
        self.driver2 = User.objects.create_user(
            username="driver_route_02",
            password="StrongPassword123!@#",
            email="driver2@sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_active=True,
            is_verified=True,
        )

        # Hospital
        self.hospital = Hospital.objects.create(
            name="General Emergency Center",
            hospital_code="HOSP-ROUTE-01",
            address="50 Central Avenue, Bengaluru",
            latitude=Decimal("12.971600"),
            longitude=Decimal("77.594600"),
            contact_number="+918012345678",
            is_active=True,
        )

        # Ambulance
        self.ambulance = Ambulance.objects.create(
            vehicle_number="KA-01-EQ-9999",
            vehicle_type="ALS",
            assigned_driver=self.driver1,
            is_available=False,
            is_active=True,
        )

        # Active incident for Driver 1
        self.incident = EmergencyIncident.objects.create(
            incident_number="INC-20261121-AA11BB",
            reporting_driver=self.driver1,
            ambulance=self.ambulance,
            hospital=self.hospital,
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.IN_TRANSIT,
            description="Motor vehicle collision with respiratory distress.",
        )

        # Associated Patient
        self.patient = Patient.objects.create(
            incident=self.incident,
            name="John Doe",
            age=45,
            gender=Gender.MALE,
            blood_group="O+",
            medical_notes="Suspected rib fracture, stable pulse.",
        )

    def test_get_emergency_status_active_auto_resolution(self):
        """Driver 1 retrieves active incident status without specifying incident_id."""
        resp = registry.execute("get_emergency_status", {}, user=self.driver1)

        self.assertTrue(resp["success"])
        data = resp["data"]
        self.assertTrue(data["has_active_emergency"])
        incident_info = data["incident"]
        self.assertEqual(incident_info["id"], str(self.incident.id))
        self.assertEqual(incident_info["incident_number"], "INC-20261121-AA11BB")
        self.assertEqual(incident_info["status"], IncidentStatus.IN_TRANSIT)
        self.assertEqual(incident_info["hospital"]["name"], "General Emergency Center")
        self.assertEqual(incident_info["ambulance"]["vehicle_number"], "KA-01-EQ-9999")
        self.assertEqual(incident_info["patient"]["name"], "John Doe")
        self.assertEqual(incident_info["patient"]["blood_group"], "O+")

    def test_get_emergency_status_by_incident_number(self):
        """Retrieves status explicitly by incident tracking number string."""
        resp = registry.execute(
            "get_emergency_status",
            {"incident_id": "INC-20261121-AA11BB"},
            user=self.driver1,
        )

        self.assertTrue(resp["success"])
        self.assertEqual(resp["data"]["incident"]["id"], str(self.incident.id))

    def test_get_emergency_status_no_active_emergency(self):
        """Driver 2 with no emergencies receives has_active_emergency=False without errors."""
        resp = registry.execute("get_emergency_status", {}, user=self.driver2)

        self.assertTrue(resp["success"])
        data = resp["data"]
        self.assertFalse(data["has_active_emergency"])
        self.assertIsNone(data["incident"])
        self.assertIn("No active emergency", data["message"])

    def test_get_emergency_status_ownership_denied(self):
        """Driver 2 cannot query Driver 1's incident ID (PERMISSION_DENIED)."""
        resp = registry.execute(
            "get_emergency_status",
            {"incident_id": str(self.incident.id)},
            user=self.driver2,
        )

        self.assertFalse(resp["success"])
        self.assertEqual(resp["error"]["code"], "PERMISSION_DENIED")

    def test_get_emergency_status_non_existent_id(self):
        """Querying a non-existent incident UUID or code returns VALIDATION_ERROR."""
        resp = registry.execute(
            "get_emergency_status",
            {"incident_id": "INC-00000000-NONEXIST"},
            user=self.driver1,
        )

        self.assertFalse(resp["success"])
        self.assertEqual(resp["error"]["code"], "VALIDATION_ERROR")

    def test_get_route_eta_from_cached_summary(self):
        """Cached route summary is retrieved instantly without API calls."""
        cache_key = f"{ROUTE_CACHE_KEY_PREFIX}{self.incident.id}"
        cache.set(
            cache_key,
            {
                "distance_km": 5.4,
                "distance_meters": 5400,
                "duration_seconds": 720,
                "duration_formatted": "12 mins",
                "estimated_arrival": timezone.now().isoformat(),
                "is_stale": False,
                "last_calculated_at": timezone.now().isoformat(),
            },
            timeout=3600,
        )

        resp = registry.execute("get_route_eta", {}, user=self.driver1)

        self.assertTrue(resp["success"])
        data = resp["data"]
        self.assertTrue(data["has_active_emergency"])
        self.assertEqual(data["source"], "cache")
        self.assertEqual(data["route_summary"]["distance_km"], 5.4)
        self.assertEqual(data["route_summary"]["duration_formatted"], "12 mins")
        self.assertFalse(data["route_summary"]["is_stale"])

    def test_get_route_eta_no_location_recorded(self):
        """If cache is empty and ambulance has no GPS ping, returns safe message."""
        resp = registry.execute("get_route_eta", {}, user=self.driver1)

        self.assertTrue(resp["success"])
        data = resp["data"]
        self.assertTrue(data["has_active_emergency"])
        self.assertIsNone(data["route_summary"])
        self.assertIn("location has not been recorded", data["message"])

    def test_get_route_eta_ownership_denied(self):
        """Driver 2 attempting to access Driver 1's route ETA is denied."""
        resp = registry.execute(
            "get_route_eta",
            {"incident_id": str(self.incident.id)},
            user=self.driver2,
        )

        self.assertFalse(resp["success"])
        self.assertEqual(resp["error"]["code"], "PERMISSION_DENIED")

    def test_get_route_eta_no_active_emergency(self):
        """Driver 2 with no emergencies receives has_active_emergency=False."""
        resp = registry.execute("get_route_eta", {}, user=self.driver2)

        self.assertTrue(resp["success"])
        self.assertFalse(resp["data"]["has_active_emergency"])


class VoiceAgentSessionAPITests(TestCase):
    """Verifies Voice Agent session lifecycle, turns, and context persistence endpoints (Phase 8.1.3)."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Driver 1 (Owner)
        self.driver1 = User.objects.create_user(
            username="voice_driver_01",
            password="StrongPassword123!@#",
            email="driver1@voice.sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_active=True,
            is_verified=True,
        )

        # Driver 2 (For multi-tenant isolation tests)
        self.driver2 = User.objects.create_user(
            username="voice_driver_02",
            password="StrongPassword123!@#",
            email="driver2@voice.sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_active=True,
            is_verified=True,
        )

        # Hospital Staff (For role rejection tests)
        self.hospital_user = User.objects.create_user(
            username="hosp_staff_voice",
            password="StrongPassword123!@#",
            email="staff@hospital.sertos.local",
            role=UserRole.HOSPITAL_STAFF,
            is_active=True,
            is_verified=True,
        )

        # Inactive Driver
        self.inactive_driver = User.objects.create_user(
            username="inactive_voice_driver",
            password="StrongPassword123!@#",
            email="inactive@voice.sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_active=False,
            is_verified=True,
        )

        # Unverified Driver
        self.unverified_driver = User.objects.create_user(
            username="unverified_voice_driver",
            password="StrongPassword123!@#",
            email="unverified@voice.sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_active=True,
            is_verified=False,
        )

    def test_start_voice_session_success(self):
        """Verified driver starts a session and receives standardized response contract."""
        self.client.force_authenticate(user=self.driver1)
        response = self.client.post("/api/agent/sessions/")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data
        self.assertIn("session_id", data)
        self.assertEqual(data["session_status"], SessionStatus.ACTIVE)
        self.assertTrue(len(data["assistant_message"]) > 10)
        self.assertFalse(data["needs_confirmation"])
        self.assertIsNone(data["error"])
        self.assertIn("emergency_type", data["missing_information"])
        self.assertIn("location_description", data["missing_information"])

        # Verify DB persistence
        session = VoiceAgentSession.objects.get(pk=data["session_id"])
        self.assertEqual(session.driver, self.driver1)
        self.assertEqual(session.status, SessionStatus.ACTIVE)
        self.assertEqual(len(session.conversation_history), 1)

    def test_start_voice_session_unauthenticated_rejected(self):
        """Unauthenticated requests receive 401."""
        response = self.client.post("/api/agent/sessions/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_start_voice_session_unauthorized_roles_rejected(self):
        """Non-driver accounts receive 403 Forbidden."""
        self.client.force_authenticate(user=self.hospital_user)
        response = self.client.post("/api/agent/sessions/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_start_voice_session_inactive_or_unverified_rejected(self):
        """Inactive or unverified drivers receive 403 Forbidden."""
        self.client.force_authenticate(user=self.inactive_driver)
        resp1 = self.client.post("/api/agent/sessions/")
        self.assertEqual(resp1.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.unverified_driver)
        resp2 = self.client.post("/api/agent/sessions/")
        self.assertEqual(resp2.status_code, status.HTTP_403_FORBIDDEN)

    def test_session_driver_isolation(self):
        """Driver 2 cannot access or send turns to Driver 1's voice session (404 Not Found)."""
        # Driver 1 starts session
        self.client.force_authenticate(user=self.driver1)
        start_resp = self.client.post("/api/agent/sessions/")
        session_id = start_resp.data["session_id"]

        # Driver 2 attempts inspection (404)
        self.client.force_authenticate(user=self.driver2)
        get_resp = self.client.get(f"/api/agent/sessions/{session_id}/")
        self.assertEqual(get_resp.status_code, status.HTTP_404_NOT_FOUND)

        # Driver 2 attempts to send a turn (404)
        turn_resp = self.client.post(
            f"/api/agent/sessions/{session_id}/turn/",
            {"message": "Patient is responsive."},
            format="json",
        )
        self.assertEqual(turn_resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_conversation_turn_input_validations(self):
        """Rejects empty, whitespace-only, and excessively large messages safely."""
        self.client.force_authenticate(user=self.driver1)
        start_resp = self.client.post("/api/agent/sessions/")
        session_id = start_resp.data["session_id"]

        # 1. Empty message
        resp_empty = self.client.post(
            f"/api/agent/sessions/{session_id}/turn/",
            {"message": ""},
            format="json",
        )
        self.assertEqual(resp_empty.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp_empty.data["error"]["code"], "VALIDATION_ERROR")

        # 2. Whitespace only message
        resp_space = self.client.post(
            f"/api/agent/sessions/{session_id}/turn/",
            {"message": "    \n   "},
            format="json",
        )
        self.assertEqual(resp_space.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp_space.data["error"]["code"], "VALIDATION_ERROR")

        # 3. Excessive length message (> 2000 chars)
        huge_message = "A" * 2001
        resp_large = self.client.post(
            f"/api/agent/sessions/{session_id}/turn/",
            {"message": huge_message},
            format="json",
        )
        self.assertEqual(resp_large.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp_large.data["error"]["code"], "VALIDATION_ERROR")

    def test_multi_turn_extraction_and_context_persistence(self):
        """Preserves conversation context across turns and extracts structured emergency details."""
        self.client.force_authenticate(user=self.driver1)
        start_resp = self.client.post("/api/agent/sessions/")
        session_id = start_resp.data["session_id"]

        # Turn 1: Driver speaks patient condition and symptoms
        turn1_resp = self.client.post(
            f"/api/agent/sessions/{session_id}/turn/",
            {"message": "We have a 45-year-old male with severe chest pain."},
            format="json",
        )
        self.assertEqual(turn1_resp.status_code, status.HTTP_200_OK)
        t1_data = turn1_resp.data
        t1_extracted = t1_data["extracted_emergency_data"]
        self.assertEqual(t1_extracted["emergency_type"], EmergencyType.CARDIAC)
        self.assertEqual(t1_extracted["patient_details"]["age"], 45)
        self.assertEqual(t1_extracted["patient_details"]["gender"], "MALE")
        self.assertIn("severe chest pain", t1_extracted["reported_injuries"])
        # Breathing and consciousness are not yet mentioned
        self.assertEqual(t1_extracted["breathing_status"], BreathingStatus.UNKNOWN)
        self.assertEqual(t1_extracted["consciousness"], ConsciousnessStatus.UNKNOWN)
        self.assertFalse(t1_data["needs_confirmation"])

        # Turn 2: Driver speaks location, consciousness, and breathing
        turn2_resp = self.client.post(
            f"/api/agent/sessions/{session_id}/turn/",
            {"message": "Location is MG Road near Trinity Circle, patient is conscious and breathing is heavy."},
            format="json",
        )
        self.assertEqual(turn2_resp.status_code, status.HTTP_200_OK)
        t2_data = turn2_resp.data
        t2_extracted = t2_data["extracted_emergency_data"]

        # Assert prior context (age=45, gender=MALE) is retained!
        self.assertEqual(t2_extracted["patient_details"]["age"], 45)
        self.assertEqual(t2_extracted["patient_details"]["gender"], "MALE")
        self.assertEqual(t2_extracted["emergency_type"], EmergencyType.CARDIAC)
        # Assert newly extracted details
        self.assertEqual(t2_extracted["consciousness"], ConsciousnessStatus.CONSCIOUS)
        self.assertEqual(t2_extracted["breathing_status"], BreathingStatus.LABORED)
        self.assertIn("MG Road", t2_extracted["location_description"])

        # Critical checklist satisfied -> needs_confirmation transitions to True
        self.assertTrue(t2_data["needs_confirmation"])
        self.assertIn("confirm", t2_data["assistant_message"].lower())

        # Inspect database history
        session = VoiceAgentSession.objects.get(pk=session_id)
        # 1 greeting + (2 turns * 2 [user, assistant]) = 5 history entries
        self.assertEqual(len(session.conversation_history), 5)
        self.assertEqual(session.conversation_history[1]["role"], "user")
        self.assertEqual(session.conversation_history[2]["role"], "assistant")
        self.assertEqual(session.conversation_history[3]["role"], "user")
        self.assertEqual(session.conversation_history[4]["role"], "assistant")

    def test_inactive_session_rejects_turns(self):
        """Turns cannot be submitted to completed or abandoned voice sessions."""
        self.client.force_authenticate(user=self.driver1)
        start_resp = self.client.post("/api/agent/sessions/")
        session_id = start_resp.data["session_id"]

        # Transition session to COMPLETED via PATCH
        patch_resp = self.client.patch(
            f"/api/agent/sessions/{session_id}/",
            {"status": SessionStatus.COMPLETED},
            format="json",
        )
        self.assertEqual(patch_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_resp.data["status"], SessionStatus.COMPLETED)

        # Attempt to post a turn to completed session (400)
        turn_resp = self.client.post(
            f"/api/agent/sessions/{session_id}/turn/",
            {"message": "Patient condition is worsening."},
            format="json",
        )
        self.assertEqual(turn_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(turn_resp.data["error"]["code"], "SESSION_INACTIVE")


class EmergencyExtractionUnitTests(TestCase):
    """Direct unit tests for information extraction guardrails and missing info evaluation."""

    def test_breathing_status_strictly_unknown_unless_explicit(self):
        """Breathing status remains UNKNOWN unless explicitly stated by driver."""
        # Statement without any breathing mentions
        data, missing, _, _ = extract_emergency_information("Driver reporting 30 year old male with leg fracture.")
        self.assertEqual(data["breathing_status"], BreathingStatus.UNKNOWN)
        self.assertIn("breathing_status", missing)

        # Statement with explicit normal breathing
        data_normal, _, _, _ = extract_emergency_information("Breathing is normal.")
        self.assertEqual(data_normal["breathing_status"], BreathingStatus.NORMAL)

        # Statement with apnea
        data_apnea, _, _, _ = extract_emergency_information("Patient is not breathing.")
        self.assertEqual(data_apnea["breathing_status"], BreathingStatus.NOT_BREATHING)

    def test_no_fabrication_of_unmentioned_demographics(self):
        """Unstated patient age and name remain null."""
        data, missing, _, _ = extract_emergency_information("Car collision on Airport Road.")
        self.assertIsNone(data["patient_details"]["age"])
        self.assertIsNone(data["patient_details"]["name"])
        self.assertEqual(data["patient_details"]["gender"], "UNKNOWN")
        self.assertIn("patient_age", missing)
        self.assertIn("patient_gender", missing)

    def test_blood_group_extraction(self):
        """Recognizes standard blood groups accurately."""
        data, _, _, _ = extract_emergency_information("Patient blood group is O positive.")
        self.assertEqual(data["patient_details"]["blood_group"], "O+")

        data2, _, _, _ = extract_emergency_information("Blood type AB-neg.")
        self.assertEqual(data2["patient_details"]["blood_group"], "AB-")

    def test_exact_reported_transcript_location_and_no_duplicate_age(self):
        """
        Regression test for Phase 8.1.7.1:
        Verifies exact reported transcript cleanly isolates location from subsequent sentences
        and prevents duplicate age/gender phrasing in assistant_message.
        """
        transcript = (
            "We have a severe two-vehicle collision on Outer Ring Road near Marathahalli Bridge. "
            "A 35-year-old male driver is bleeding heavily from head lacerations."
        )
        data, missing, needs_conf, assistant_msg = extract_emergency_information(transcript)

        # 1. Location must NOT leak into subsequent sentences or patient descriptions
        self.assertEqual(data["location_description"], "Outer Ring Road near Marathahalli Bridge")
        self.assertNotIn("35-year-old", data["location_description"])
        self.assertNotIn("A 35", data["location_description"])
        self.assertFalse(data["location_description"].startswith("on "))

        # 2. Patient details correctly isolated
        self.assertEqual(data["emergency_type"], EmergencyType.TRAUMA)
        self.assertEqual(data["patient_details"]["age"], 35)
        self.assertEqual(data["patient_details"]["gender"], "MALE")
        self.assertIn("bleeding", data["reported_injuries"])
        self.assertIn("laceration", data["reported_injuries"])

        # 3. Assistant message must NOT repeat age or gender
        self.assertEqual(assistant_msg.count("35-year-old"), 1)
        self.assertEqual(assistant_msg.count("male"), 1)
        self.assertNotIn("near on", assistant_msg)
        self.assertIn("at Outer Ring Road near Marathahalli Bridge", assistant_msg)

    def test_transcript_variations_location_clause_isolation(self):
        """
        Tests multiple real-world emergency transcript variations for location clause isolation.
        """
        # Variation 1: Location clause followed by patient clause in same sentence
        t1 = "Location is MG Road near Trinity Circle, patient is conscious and breathing is heavy."
        d1, _, _, _ = extract_emergency_information(t1)
        self.assertEqual(d1["location_description"], "MG Road near Trinity Circle")
        self.assertNotIn("patient", d1["location_description"])

        # Variation 2: Location clause with period before next sentence
        t2 = "Accident on Hosur Main Road near Silk Board Junction. Two cars involved."
        d2, _, _, _ = extract_emergency_information(t2)
        self.assertEqual(d2["location_description"], "Hosur Main Road near Silk Board Junction")
        self.assertNotIn("Two cars", d2["location_description"])

        # Variation 3: Location with comma followed by age and symptoms
        t3 = "We are at Koramangala 5th Block near Sony World Signal, 40-year-old male with chest pain."
        d3, _, _, msg3 = extract_emergency_information(t3)
        self.assertEqual(d3["location_description"], "Koramangala 5th Block near Sony World Signal")
        self.assertEqual(d3["patient_details"]["age"], 40)
        self.assertEqual(msg3.count("40-year-old"), 1)

        # Variation 4: Multi-turn context preservation without duplication
        prev_data, _, _, _ = extract_emergency_information("We have a 45-year-old male with severe chest pain.")
        self.assertEqual(prev_data["patient_details"]["age"], 45)
        self.assertEqual(prev_data["patient_details"]["gender"], "MALE")

        t4_turn2 = "Location is MG Road near Trinity Circle, patient is conscious and breathing is heavy."
        d4, missing4, needs_conf4, msg4 = extract_emergency_information(t4_turn2, prior_data=prev_data)

        self.assertEqual(d4["patient_details"]["age"], 45)
        self.assertEqual(d4["patient_details"]["gender"], "MALE")
        self.assertEqual(d4["location_description"], "MG Road near Trinity Circle")
        self.assertTrue(needs_conf4)
        self.assertEqual(msg4.count("45-year-old"), 1)
        self.assertEqual(msg4.count("male"), 1)
        self.assertNotIn("near on", msg4)


class VoiceSessionEmergencyConfirmationTests(TestCase):
    """Verifies Phase 8.1.4: Explicit driver emergency confirmation and domain execution."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Driver 1
        self.driver1 = User.objects.create_user(
            username="confirm_driver_01",
            password="StrongPassword123!@#",
            email="driver1@confirm.sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_active=True,
            is_verified=True,
        )

        # Driver 2
        self.driver2 = User.objects.create_user(
            username="confirm_driver_02",
            password="StrongPassword123!@#",
            email="driver2@confirm.sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_active=True,
            is_verified=True,
        )

        # Hospital Staff
        self.staff_user = User.objects.create_user(
            username="confirm_hosp_staff",
            password="StrongPassword123!@#",
            email="staff@confirm.sertos.local",
            role=UserRole.HOSPITAL_STAFF,
            is_active=True,
            is_verified=True,
        )

        # Destination Hospital
        self.hospital = Hospital.objects.create(
            name="City Trauma & Emergency Center",
            hospital_code="HOSP-CONFIRM-01",
            address="100 Main Boulevard, Bengaluru",
            latitude=Decimal("12.971600"),
            longitude=Decimal("77.594600"),
            contact_number="+918012345678",
            is_active=True,
        )

        # Inactive Hospital
        self.inactive_hospital = Hospital.objects.create(
            name="Decommissioned Clinic",
            hospital_code="HOSP-CONFIRM-INACTIVE",
            address="99 Old Lane, Bengaluru",
            latitude=Decimal("12.970000"),
            longitude=Decimal("77.590000"),
            is_active=False,
        )

        # Assigned Ambulance for Driver 1 (Available)
        self.ambulance = Ambulance.objects.create(
            vehicle_number="KA-01-AMB-8888",
            vehicle_type="ALS",
            assigned_driver=self.driver1,
            is_available=True,
            is_active=True,
        )

    def _setup_fully_extracted_session(self, driver):
        """Helper to create a session with all critical triage fields populated."""
        return VoiceAgentSession.objects.create(
            driver=driver,
            status=SessionStatus.ACTIVE,
            conversation_history=[
                {"role": "assistant", "message": "SERTOS Agent ready.", "timestamp": timezone.now().isoformat()},
                {"role": "user", "message": "45yo male with chest pain at MG Road, conscious, breathing heavy.", "timestamp": timezone.now().isoformat()},
            ],
            extracted_emergency_data={
                "emergency_type": EmergencyType.CARDIAC,
                "location_description": "MG Road near Trinity Circle",
                "consciousness": ConsciousnessStatus.CONSCIOUS,
                "breathing_status": BreathingStatus.LABORED,
                "reported_injuries": ["severe chest pain"],
                "patient_details": {
                    "name": "Arjun Kumar",
                    "age": 45,
                    "gender": "MALE",
                    "blood_group": "O+",
                },
                "additional_notes": ["Heavy traffic"],
            },
            missing_information=[],
            needs_confirmation=True,
        )

    def test_confirm_emergency_success_with_explicit_hospital(self):
        """Explicit driver confirmation creates EmergencyIncident, links to session, and transitions to COMPLETED."""
        session = self._setup_fully_extracted_session(self.driver1)
        self.client.force_authenticate(user=self.driver1)

        payload = {
            "confirmation": True,
            "hospital_id": str(self.hospital.id),
            "severity": IncidentSeverity.HIGH,
            "latitude": 12.975000,
            "longitude": 77.609000,
        }
        response = self.client.post(
            f"/api/agent/sessions/{session.id}/confirm-emergency/",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data
        self.assertTrue(data["success"])
        self.assertFalse(data["is_duplicate_confirmation"])
        self.assertIn("incident_id", data)
        self.assertIn("incident_number", data)
        self.assertEqual(data["status"], IncidentStatus.REPORTED)
        self.assertEqual(data["severity"], IncidentSeverity.HIGH)
        self.assertEqual(data["hospital"]["id"], str(self.hospital.id))
        self.assertEqual(data["patient"]["name"], "Arjun Kumar")
        self.assertEqual(data["patient"]["age"], 45)
        self.assertEqual(data["session_status"], SessionStatus.COMPLETED)

        # Verify DB linkage
        session.refresh_from_db()
        self.assertIsNotNone(session.associated_incident)
        self.assertEqual(str(session.associated_incident.id), data["incident_id"])
        self.assertEqual(session.status, SessionStatus.COMPLETED)
        self.assertIsNotNone(session.ended_at)

        # Verify initial GPS ping recorded for incident
        incident = session.associated_incident
        self.assertTrue(AmbulanceLocation.objects.filter(incident=incident).exists())

    def test_confirm_emergency_auto_selects_nearest_hospital(self):
        """If hospital_id is omitted, auto-selects the nearest active facility via trusted GPS."""
        session = self._setup_fully_extracted_session(self.driver1)
        self.client.force_authenticate(user=self.driver1)

        payload = {
            "confirmation": True,
            "latitude": 12.971600,
            "longitude": 77.594600,
        }
        response = self.client.post(
            f"/api/agent/sessions/{session.id}/confirm-emergency/",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["hospital"]["id"], str(self.hospital.id))

    def test_confirm_emergency_missing_information_blocked(self):
        """Fails with 400 MISSING_INFORMATION when critical fields are absent; zero incidents created."""
        # Session missing consciousness and breathing status
        session = VoiceAgentSession.objects.create(
            driver=self.driver1,
            status=SessionStatus.ACTIVE,
            conversation_history=[],
            extracted_emergency_data={
                "emergency_type": EmergencyType.CARDIAC,
                "location_description": "MG Road",
                "consciousness": ConsciousnessStatus.UNKNOWN,
                "breathing_status": BreathingStatus.UNKNOWN,
                "patient_details": {"age": 45, "gender": "MALE"},
            },
            missing_information=["consciousness", "breathing_status"],
            needs_confirmation=False,
        )
        self.client.force_authenticate(user=self.driver1)

        response = self.client.post(
            f"/api/agent/sessions/{session.id}/confirm-emergency/",
            {"confirmation": True, "hospital_id": str(self.hospital.id)},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["error"]["code"], "MISSING_INFORMATION")
        self.assertIn("consciousness", response.data["missing_information"])
        self.assertIn("breathing_status", response.data["missing_information"])
        self.assertTrue(response.data["can_continue_conversation"])

        # Zero incidents created
        self.assertEqual(EmergencyIncident.objects.count(), 0)
        session.refresh_from_db()
        self.assertEqual(session.status, SessionStatus.ACTIVE)
        self.assertIsNone(session.associated_incident)

    def test_confirm_emergency_duplicate_call_idempotent(self):
        """Repeated confirmation on the same session returns 200 with is_duplicate_confirmation=True."""
        session = self._setup_fully_extracted_session(self.driver1)
        self.client.force_authenticate(user=self.driver1)

        payload = {"confirmation": True, "hospital_id": str(self.hospital.id)}

        # First call creates incident
        resp1 = self.client.post(f"/api/agent/sessions/{session.id}/confirm-emergency/", payload, format="json")
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
        first_incident_id = resp1.data["incident_id"]

        # Second call returns existing incident without creating duplicates
        resp2 = self.client.post(f"/api/agent/sessions/{session.id}/confirm-emergency/", payload, format="json")
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertTrue(resp2.data["is_duplicate_confirmation"])
        self.assertEqual(resp2.data["incident_id"], first_incident_id)

        # Strictly 1 incident exists
        self.assertEqual(EmergencyIncident.objects.count(), 1)

    def test_confirm_emergency_driver_isolation(self):
        """Driver 2 cannot confirm Driver 1's voice session (404 Not Found)."""
        session = self._setup_fully_extracted_session(self.driver1)
        self.client.force_authenticate(user=self.driver2)

        response = self.client.post(
            f"/api/agent/sessions/{session.id}/confirm-emergency/",
            {"confirmation": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(EmergencyIncident.objects.count(), 0)

    def test_confirm_emergency_inactive_session_blocked(self):
        """Cannot confirm an already abandoned or completed voice session."""
        session = self._setup_fully_extracted_session(self.driver1)
        session.status = SessionStatus.ABANDONED
        session.save()

        self.client.force_authenticate(user=self.driver1)
        response = self.client.post(
            f"/api/agent/sessions/{session.id}/confirm-emergency/",
            {"confirmation": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "SESSION_INACTIVE")

    def test_confirm_emergency_explicit_confirmation_false_rejected(self):
        """If confirmation flag is False, emergency is not created."""
        session = self._setup_fully_extracted_session(self.driver1)
        self.client.force_authenticate(user=self.driver1)

        response = self.client.post(
            f"/api/agent/sessions/{session.id}/confirm-emergency/",
            {"confirmation": False},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "CONFIRMATION_REQUIRED")
        self.assertEqual(EmergencyIncident.objects.count(), 0)

    def test_confirm_emergency_inactive_hospital_rejected(self):
        """Selecting an inactive hospital raises error."""
        session = self._setup_fully_extracted_session(self.driver1)
        self.client.force_authenticate(user=self.driver1)

        response = self.client.post(
            f"/api/agent/sessions/{session.id}/confirm-emergency/",
            {"confirmation": True, "hospital_id": str(self.inactive_hospital.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "HOSPITAL_INACTIVE")

    def test_confirm_emergency_ambulance_unavailable_fails_safely(self):
        """If assigned ambulance is unavailable, dispatch fails safely with clear error."""
        self.ambulance.is_available = False
        self.ambulance.save()

        session = self._setup_fully_extracted_session(self.driver1)
        self.client.force_authenticate(user=self.driver1)

        response = self.client.post(
            f"/api/agent/sessions/{session.id}/confirm-emergency/",
            {"confirmation": True, "hospital_id": str(self.hospital.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "DISPATCH_FAILED")
        self.assertIn("unavailable", response.data["error"]["message"].lower())
        self.assertEqual(EmergencyIncident.objects.count(), 0)

    def test_confirm_emergency_unauthorized_roles(self):
        """Hospital staff accounts cannot confirm or create driver emergencies."""
        session = self._setup_fully_extracted_session(self.driver1)
        self.client.force_authenticate(user=self.staff_user)

        response = self.client.post(
            f"/api/agent/sessions/{session.id}/confirm-emergency/",
            {"confirmation": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_voice_session_end_endpoint_completed(self):
        """Driver can explicitly end an active session using the /end/ endpoint."""
        self.client.force_authenticate(user=self.driver1)
        start_resp = self.client.post("/api/agent/sessions/")
        session_id = start_resp.data["session_id"]

        end_resp = self.client.post(f"/api/agent/sessions/{session_id}/end/")
        self.assertEqual(end_resp.status_code, status.HTTP_200_OK)
        self.assertTrue(end_resp.data["success"])
        self.assertEqual(end_resp.data["status"], SessionStatus.COMPLETED)

        # Confirm database update
        session = VoiceAgentSession.objects.get(pk=session_id)
        self.assertEqual(session.status, SessionStatus.COMPLETED)
        self.assertIsNotNone(session.ended_at)

    def test_voice_session_end_endpoint_abandoned(self):
        """Driver can specify status='ABANDONED' to discard an incomplete voice session."""
        self.client.force_authenticate(user=self.driver1)
        start_resp = self.client.post("/api/agent/sessions/")
        session_id = start_resp.data["session_id"]

        end_resp = self.client.post(
            f"/api/agent/sessions/{session_id}/end/",
            {"status": SessionStatus.ABANDONED},
            format="json",
        )
        self.assertEqual(end_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(end_resp.data["status"], SessionStatus.ABANDONED)

        session = VoiceAgentSession.objects.get(pk=session_id)
        self.assertEqual(session.status, SessionStatus.ABANDONED)

    def test_voice_session_end_idempotent(self):
        """Calling end repeatedly on a terminated session returns 200 OK cleanly."""
        self.client.force_authenticate(user=self.driver1)
        start_resp = self.client.post("/api/agent/sessions/")
        session_id = start_resp.data["session_id"]

        self.client.post(f"/api/agent/sessions/{session_id}/end/")
        second_resp = self.client.post(f"/api/agent/sessions/{session_id}/end/")
        self.assertEqual(second_resp.status_code, status.HTTP_200_OK)
        self.assertTrue(second_resp.data["success"])
        self.assertIn("already completed", second_resp.data["message"].lower())

    def test_voice_session_end_ownership_and_auth(self):
        """Other drivers cannot end someone else's voice session."""
        self.client.force_authenticate(user=self.driver1)
        start_resp = self.client.post("/api/agent/sessions/")
        session_id = start_resp.data["session_id"]

        # Driver 2 tries to end Driver 1's session
        self.client.force_authenticate(user=self.driver2)
        end_resp = self.client.post(f"/api/agent/sessions/{session_id}/end/")
        self.assertEqual(end_resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_end_to_end_voice_frontend_integration_flow(self):
        """
        Simulates the complete frontend voice integration lifecycle:
        1. Start voice session
        2. Turn 1 (STT transcript): Report patient and emergency type
        3. Turn 2 (STT transcript): Report location and vitals
        4. Turn 3 (STT transcript): Provide consciousness & breathing
        5. Verify speakable assistant_message suitable for Web Speech API TTS
        6. Explicit confirmation and emergency incident creation with trusted GPS
        7. Inspect incident status and session end
        """
        self.client.force_authenticate(user=self.driver1)

        # 1. Start session
        start_resp = self.client.post("/api/agent/sessions/")
        self.assertEqual(start_resp.status_code, status.HTTP_201_CREATED)
        session_id = start_resp.data["session_id"]
        # Initial greeting is speakable
        self.assertTrue(len(start_resp.data["assistant_message"]) > 0)

        # 2. Turn 1: Driver speaks: "Heart attack victim, 55-year-old female"
        turn1 = self.client.post(
            f"/api/agent/sessions/{session_id}/turn/",
            {"message": "Patient is a 55-year-old female suffering a heart attack."},
            format="json",
        )
        self.assertEqual(turn1.status_code, status.HTTP_200_OK)
        self.assertEqual(turn1.data["extracted_emergency_data"]["emergency_type"], "CARDIAC")
        self.assertIn("location_description", turn1.data["missing_information"])

        # 3. Turn 2: Driver speaks: "We are near MG Road Metro Station"
        turn2 = self.client.post(
            f"/api/agent/sessions/{session_id}/turn/",
            {"message": "We are near MG Road Metro Station."},
            format="json",
        )
        self.assertEqual(turn2.status_code, status.HTTP_200_OK)
        self.assertEqual(
            turn2.data["extracted_emergency_data"]["location_description"],
            "MG Road Metro Station",
        )

        # 4. Turn 3: Driver speaks: "Patient is conscious, breathing is shallow"
        turn3 = self.client.post(
            f"/api/agent/sessions/{session_id}/turn/",
            {"message": "Patient is conscious, breathing is shallow."},
            format="json",
        )
        self.assertEqual(turn3.status_code, status.HTTP_200_OK)
        self.assertEqual(turn3.data["extracted_emergency_data"]["consciousness"], "CONSCIOUS")
        self.assertEqual(turn3.data["extracted_emergency_data"]["breathing_status"], "LABORED")
        self.assertTrue(turn3.data["needs_confirmation"])
        # Speech-to-text / text-to-speech verification: assistant message is clean, friendly text
        assistant_speech = turn3.data["assistant_message"]
        self.assertIn("confirm", assistant_speech.lower())

        # 5. Confirm emergency via dedicated endpoint with live GPS coordinates
        confirm_resp = self.client.post(
            f"/api/agent/sessions/{session_id}/confirm-emergency/",
            {
                "confirmation": True,
                "hospital_id": str(self.hospital.id),
                "latitude": 12.9716,
                "longitude": 77.5946,
                "accuracy": 5.0,
            },
            format="json",
        )
        self.assertEqual(confirm_resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(confirm_resp.data["success"])
        self.assertIn("incident_number", confirm_resp.data)
        self.assertEqual(confirm_resp.data["session_status"], SessionStatus.COMPLETED)

        # 6. Session is already completed by confirm-emergency, calling end/ is safe and idempotent
        end_resp = self.client.post(f"/api/agent/sessions/{session_id}/end/")
        self.assertEqual(end_resp.status_code, status.HTTP_200_OK)
        self.assertTrue(end_resp.data["success"])


