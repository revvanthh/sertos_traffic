"""
SERTOS Phase 8.1.6 — End-to-End Voice AI Verification Test Suite.

Verifies the entire voice emergency workflow against the PostgreSQL database:
1. Authenticate as a verified ambulance driver (POST /api/auth/login/).
2. Start a new voice-agent session (POST /api/agent/sessions/).
3. Send a realistic emergency transcript (POST /api/agent/sessions/<id>/turn/).
4. Verify assistant_message is returned (natural, speakable text).
5. Verify extracted emergency data is correct (deterministic clinical triage).
6. Test a multi-turn conversation with missing information.
7. Verify needs_confirmation becomes true at the appropriate point.
8. Test confirmation validation (explicit flag, hospital validity, incomplete data).
9. Test duplicate confirmation/idempotency.
10. Verify incident creation and association with the voice session.
11. Verify session completion (ended_at, COMPLETED status).
12. Verify invalid requests, permissions, and session ownership isolation.
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
    EmergencyEvent,
    EmergencyIncident,
    Gender,
    Hospital,
    HospitalStaff,
    IncidentSeverity,
    IncidentStatus,
    Notification,
    Patient,
)
from apps.agent.extraction import (
    BreathingStatus,
    ConsciousnessStatus,
    EmergencyType,
)
from apps.agent.models import SessionStatus, VoiceAgentSession

User = get_user_model()


class VoiceAgentEndToEndVerificationTests(TestCase):
    """
    Focused end-to-end integration tests strictly validating the 12 sequence steps
    of SERTOS Phase 8.1.6.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # 1. Primary Verified Ambulance Driver
        self.driver_password = "DriverStrongPassword123!@#"
        self.driver1 = User.objects.create_user(
            username="e2e_verified_driver",
            password=self.driver_password,
            email="driver1@e2e.sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_active=True,
            is_verified=True,
        )

        # 2. Second Verified Ambulance Driver (for ownership checks)
        self.driver2 = User.objects.create_user(
            username="e2e_driver_two",
            password="DriverTwoPassword123!@#",
            email="driver2@e2e.sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_active=True,
            is_verified=True,
        )

        # 3. Unverified Ambulance Driver
        self.unverified_driver = User.objects.create_user(
            username="e2e_unverified_driver",
            password="UnverifiedPassword123!@#",
            email="unverified@e2e.sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_active=True,
            is_verified=False,
        )

        # 4. Hospital Emergency Staff User
        self.hospital_staff = User.objects.create_user(
            username="e2e_hospital_nurse",
            password="StaffPassword123!@#",
            email="staff@e2e.sertos.local",
            role=UserRole.HOSPITAL_STAFF,
            is_active=True,
            is_verified=True,
        )

        # 5. Police Dispatcher User
        self.police_dispatcher = User.objects.create_user(
            username="e2e_police_officer",
            password="PolicePassword123!@#",
            email="police@e2e.sertos.local",
            role=UserRole.POLICE_DISPATCHER,
            is_active=True,
            is_verified=True,
        )

        # 6. Active Destination Hospital Facility
        self.hospital = Hospital.objects.create(
            name="Manipal Emergency Trauma Care",
            hospital_code="HOSP-E2E-MANIPAL",
            address="98 Old Airport Road, Kodihalli, Bengaluru",
            latitude=Decimal("12.959100"),
            longitude=Decimal("77.654400"),
            contact_number="+918025024444",
            is_active=True,
        )

        # Staff Affiliation with Hospital
        HospitalStaff.objects.create(
            user=self.hospital_staff,
            hospital=self.hospital,
            is_active=True,
        )

        # 7. Inactive Hospital Facility
        self.inactive_hospital = Hospital.objects.create(
            name="Decommissioned Community Clinic",
            hospital_code="HOSP-E2E-INACTIVE",
            address="12 Closed Bypass, Bengaluru",
            latitude=Decimal("12.950000"),
            longitude=Decimal("77.650000"),
            contact_number="+918099999999",
            is_active=False,
        )

        # 8. Available Ambulance Assigned to Driver 1
        self.ambulance = Ambulance.objects.create(
            vehicle_number="KA-04-E2E-1008",
            vehicle_type="Advanced Life Support (ALS)",
            assigned_driver=self.driver1,
            is_available=True,
            is_active=True,
        )

    def _get_jwt_token(self, username, password):
        """Authenticates via POST /api/auth/login/ and returns access token."""
        response = self.client.post(
            "/api/auth/login/",
            {"username": username, "password": password},
            format="json",
        )
        if response.status_code == status.HTTP_200_OK and response.data.get("success"):
            return response.data["data"]["access"]
        return None

    # -------------------------------------------------------------------------
    # Step 1: Driver Authentication
    # -------------------------------------------------------------------------
    def test_step_01_authenticate_as_verified_ambulance_driver(self):
        """Driver logs in via /api/auth/login/ and obtains valid JWT claims."""
        # 1. Valid verified driver credentials
        response = self.client.post(
            "/api/auth/login/",
            {"username": self.driver1.username, "password": self.driver_password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertIn("access", response.data["data"])
        self.assertIn("refresh", response.data["data"])
        self.assertEqual(response.data["data"]["user"]["role"], UserRole.AMBULANCE_DRIVER)
        self.assertTrue(response.data["data"]["user"]["is_verified"])

        # 2. Unverified driver rejected
        unverified_resp = self.client.post(
            "/api/auth/login/",
            {"username": self.unverified_driver.username, "password": "UnverifiedPassword123!@#"},
            format="json",
        )
        self.assertEqual(unverified_resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(unverified_resp.data["success"])

        # 3. Invalid password rejected
        bad_resp = self.client.post(
            "/api/auth/login/",
            {"username": self.driver1.username, "password": "WrongPassword!"},
            format="json",
        )
        self.assertEqual(bad_resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(bad_resp.data["success"])

    # -------------------------------------------------------------------------
    # Step 2: Start Voice Agent Session
    # -------------------------------------------------------------------------
    def test_step_02_start_new_voice_agent_session(self):
        """Verified driver starts a voice session with standardized initial contract."""
        token = self._get_jwt_token(self.driver1.username, self.driver_password)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.post("/api/agent/sessions/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("session_id", response.data)
        self.assertEqual(response.data["session_status"], SessionStatus.ACTIVE)
        self.assertFalse(response.data["needs_confirmation"])
        self.assertIsNone(response.data["error"])

        # Check speakable greeting
        greeting = response.data["assistant_message"]
        self.assertTrue(len(greeting) > 10)
        self.assertIn("SERTOS", greeting)

        # Check missing information initialized
        missing = response.data["missing_information"]
        for field in ["emergency_type", "location_description", "consciousness", "breathing_status"]:
            self.assertIn(field, missing)

        # Verify session record in PostgreSQL
        session = VoiceAgentSession.objects.get(pk=response.data["session_id"])
        self.assertEqual(session.driver, self.driver1)
        self.assertEqual(session.status, SessionStatus.ACTIVE)
        self.assertIsNone(session.associated_incident)

    # -------------------------------------------------------------------------
    # Steps 3, 4, 5: Send Realistic Transcript, Verify Assistant Speech & Extraction
    # -------------------------------------------------------------------------
    def test_steps_03_04_05_realistic_transcript_speech_and_extraction(self):
        """Driver submits realistic incident speech; backend extracts clinical triage accurately."""
        token = self._get_jwt_token(self.driver1.username, self.driver_password)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        start_resp = self.client.post("/api/agent/sessions/", {}, format="json")
        session_id = start_resp.data["session_id"]

        # Step 3: Send realistic transcript
        transcript = (
            "Control room, this is Ambulance 1008. We have a severe two-vehicle collision "
            "on Outer Ring Road near Marathahalli Bridge. A 35-year-old male driver is bleeding "
            "heavily from head lacerations."
        )
        turn_resp = self.client.post(
            f"/api/agent/sessions/{session_id}/turn/",
            {"message": transcript},
            format="json",
        )
        self.assertEqual(turn_resp.status_code, status.HTTP_200_OK)

        # Step 4: Verify assistant_message is returned and speakable
        speech = turn_resp.data["assistant_message"]
        self.assertTrue(len(speech) > 0)
        self.assertNotIn("```", speech)
        self.assertNotIn("|", speech)  # No markdown table syntax
        self.assertIn("trauma", speech.lower())

        # Step 5: Verify extracted emergency data
        extracted = turn_resp.data["extracted_emergency_data"]
        self.assertEqual(extracted["emergency_type"], EmergencyType.TRAUMA)
        self.assertEqual(extracted["location_description"], "Outer Ring Road near Marathahalli Bridge")
        self.assertNotIn("35-year-old", extracted["location_description"])
        self.assertEqual(extracted["patient_details"]["age"], 35)
        self.assertEqual(extracted["patient_details"]["gender"], "MALE")
        self.assertIn("laceration", extracted["reported_injuries"])
        self.assertIn("bleeding", extracted["reported_injuries"])

        # Verify assistant message has no duplicate age
        self.assertEqual(turn_resp.data["assistant_message"].count("35-year-old"), 1)

        # Consciousness and breathing were not explicitly stated yet
        self.assertEqual(extracted["consciousness"], ConsciousnessStatus.UNKNOWN)
        self.assertEqual(extracted["breathing_status"], BreathingStatus.UNKNOWN)
        self.assertIn("consciousness", turn_resp.data["missing_information"])
        self.assertIn("breathing_status", turn_resp.data["missing_information"])
        self.assertFalse(turn_resp.data["needs_confirmation"])

    # -------------------------------------------------------------------------
    # Steps 6 & 7: Multi-turn Conversation & Confirmation Progression
    # -------------------------------------------------------------------------
    def test_steps_06_07_multiturn_conversation_and_needs_confirmation(self):
        """Multi-turn conversation fills missing triage fields until needs_confirmation flips to True."""
        token = self._get_jwt_token(self.driver1.username, self.driver_password)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        start_resp = self.client.post("/api/agent/sessions/", {}, format="json")
        session_id = start_resp.data["session_id"]

        # Turn 1: Emergency type and location
        t1 = self.client.post(
            f"/api/agent/sessions/{session_id}/turn/",
            {"message": "Cardiac arrest patient at Indiranagar 100ft road."},
            format="json",
        )
        self.assertEqual(t1.status_code, status.HTTP_200_OK)
        self.assertEqual(t1.data["extracted_emergency_data"]["emergency_type"], EmergencyType.CARDIAC)
        self.assertFalse(t1.data["needs_confirmation"])
        self.assertIn("consciousness", t1.data["missing_information"])
        self.assertIn("breathing_status", t1.data["missing_information"])

        # Turn 2: Driver supplies patient vitals
        t2 = self.client.post(
            f"/api/agent/sessions/{session_id}/turn/",
            {"message": "Patient is unconscious and not breathing. CPR is in progress."},
            format="json",
        )
        self.assertEqual(t2.status_code, status.HTTP_200_OK)
        self.assertEqual(t2.data["extracted_emergency_data"]["consciousness"], ConsciousnessStatus.UNCONSCIOUS)
        self.assertEqual(t2.data["extracted_emergency_data"]["breathing_status"], BreathingStatus.NOT_BREATHING)

        # Step 7: All mandatory critical triage fields satisfied -> needs_confirmation is True
        for critical_field in ["emergency_type", "location_description", "consciousness", "breathing_status"]:
            self.assertNotIn(critical_field, t2.data["missing_information"])
        self.assertTrue(t2.data["needs_confirmation"])
        self.assertIn("confirm", t2.data["assistant_message"].lower())

    # -------------------------------------------------------------------------
    # Step 8: Confirmation Validation Rules
    # -------------------------------------------------------------------------
    def test_step_08_confirmation_validation(self):
        """Validates error scenarios for the emergency confirmation endpoint."""
        token = self._get_jwt_token(self.driver1.username, self.driver_password)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        start_resp = self.client.post("/api/agent/sessions/", {}, format="json")
        session_id = start_resp.data["session_id"]

        # 1. Attempt confirmation with incomplete data
        incomplete_resp = self.client.post(
            f"/api/agent/sessions/{session_id}/confirm-emergency/",
            {"confirmation": True},
            format="json",
        )
        self.assertEqual(incomplete_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(incomplete_resp.data["error"]["code"], "MISSING_INFORMATION")

        # Complete the extraction via turns
        self.client.post(
            f"/api/agent/sessions/{session_id}/turn/",
            {"message": "Severe stroke victim at Koramangala 5th Block."},
            format="json",
        )
        self.client.post(
            f"/api/agent/sessions/{session_id}/turn/",
            {"message": "Patient is conscious with normal breathing."},
            format="json",
        )

        # 2. Driver sends confirmation = False
        false_confirm_resp = self.client.post(
            f"/api/agent/sessions/{session_id}/confirm-emergency/",
            {"confirmation": False},
            format="json",
        )
        self.assertEqual(false_confirm_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(false_confirm_resp.data["error"]["code"], "CONFIRMATION_REQUIRED")

        # 3. Selected hospital is inactive
        inactive_hosp_resp = self.client.post(
            f"/api/agent/sessions/{session_id}/confirm-emergency/",
            {"confirmation": True, "hospital_id": str(self.inactive_hospital.id)},
            format="json",
        )
        self.assertEqual(inactive_hosp_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(inactive_hosp_resp.data["error"]["code"], "HOSPITAL_INACTIVE")

        # 4. Non-existent hospital ID
        bad_uuid = "00000000-0000-0000-0000-000000000000"
        non_existent_hosp_resp = self.client.post(
            f"/api/agent/sessions/{session_id}/confirm-emergency/",
            {"confirmation": True, "hospital_id": bad_uuid},
            format="json",
        )
        self.assertEqual(non_existent_hosp_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(non_existent_hosp_resp.data["error"]["code"], "INVALID_HOSPITAL")

    # -------------------------------------------------------------------------
    # Steps 9, 10, 11: Incident Creation, Association, Duplicate Idempotency & Completion
    # -------------------------------------------------------------------------
    def test_steps_09_10_11_incident_creation_association_idempotency_and_completion(self):
        """Confirms emergency, verifies incident creation, links, notifications, and idempotency."""
        token = self._get_jwt_token(self.driver1.username, self.driver_password)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        start_resp = self.client.post("/api/agent/sessions/", {}, format="json")
        session_id = start_resp.data["session_id"]

        # Populate triage fields
        self.client.post(
            f"/api/agent/sessions/{session_id}/turn/",
            {"message": "Cardiac arrest, 60yo male patient at Bellandur EcoSpace."},
            format="json",
        )
        self.client.post(
            f"/api/agent/sessions/{session_id}/turn/",
            {"message": "Patient is unconscious and not breathing."},
            format="json",
        )

        initial_incident_count = EmergencyIncident.objects.count()

        # Step 10: Confirm and create incident
        confirm_payload = {
            "confirmation": True,
            "hospital_id": str(self.hospital.id),
            "latitude": 12.9352,
            "longitude": 77.6245,
            "accuracy": 4.0,
        }
        confirm_resp = self.client.post(
            f"/api/agent/sessions/{session_id}/confirm-emergency/",
            confirm_payload,
            format="json",
        )
        self.assertEqual(confirm_resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(confirm_resp.data["success"])
        incident_id = confirm_resp.data["incident_id"]
        incident_number = confirm_resp.data["incident_number"]
        self.assertEqual(confirm_resp.data["status"], IncidentStatus.REPORTED)
        self.assertEqual(confirm_resp.data["hospital"]["id"], str(self.hospital.id))

        # Verify database association
        self.assertEqual(EmergencyIncident.objects.count(), initial_incident_count + 1)
        session = VoiceAgentSession.objects.get(pk=session_id)
        incident = EmergencyIncident.objects.get(pk=incident_id)

        self.assertEqual(session.associated_incident, incident)
        self.assertEqual(incident.reporting_driver, self.driver1)
        self.assertEqual(incident.hospital, self.hospital)
        self.assertEqual(incident.ambulance, self.ambulance)

        # Verify Patient record created with unknown/explicit attributes preserved
        patient = incident.patients.first()
        self.assertIsNotNone(patient)
        self.assertEqual(patient.age, 60)
        self.assertEqual(patient.gender, Gender.MALE)

        # Verify initial GPS location recorded
        self.assertEqual(incident.locations.count(), 1)
        loc = incident.locations.first()
        self.assertEqual(float(loc.latitude), 12.9352)
        self.assertEqual(float(loc.longitude), 77.6245)

        # Verify EmergencyEvent audit log
        self.assertTrue(
            EmergencyEvent.objects.filter(incident=incident).exists()
        )

        # Verify Notifications created for Hospital Staff and Police Dispatcher
        notifs = Notification.objects.filter(incident=incident)
        recipient_roles = {n.recipient.role for n in notifs}
        self.assertIn(UserRole.HOSPITAL_STAFF, recipient_roles)
        self.assertIn(UserRole.POLICE_DISPATCHER, recipient_roles)

        # Step 11: Verify session completion
        self.assertEqual(session.status, SessionStatus.COMPLETED)
        self.assertIsNotNone(session.ended_at)

        # Step 9: Test duplicate confirmation / idempotency
        dup_resp = self.client.post(
            f"/api/agent/sessions/{session_id}/confirm-emergency/",
            confirm_payload,
            format="json",
        )
        self.assertEqual(dup_resp.status_code, status.HTTP_200_OK)
        self.assertTrue(dup_resp.data["success"])
        self.assertTrue(dup_resp.data["is_duplicate_confirmation"])
        self.assertEqual(dup_resp.data["incident_id"], incident_id)
        self.assertEqual(dup_resp.data["incident_number"], incident_number)
        # Incident count did not increase
        self.assertEqual(EmergencyIncident.objects.count(), initial_incident_count + 1)

        # Conclude session via /end/ is safe and idempotent
        end_resp = self.client.post(f"/api/agent/sessions/{session_id}/end/", {}, format="json")
        self.assertEqual(end_resp.status_code, status.HTTP_200_OK)
        self.assertTrue(end_resp.data["success"])

    # -------------------------------------------------------------------------
    # Step 12: Invalid Requests, Permissions, and Session Ownership
    # -------------------------------------------------------------------------
    def test_step_12_invalid_requests_permissions_and_ownership(self):
        """Verifies strict RBAC, driver ownership isolation, and input validation."""
        # 1. Unauthenticated request rejected
        unauth_resp = self.client.post("/api/agent/sessions/", {}, format="json")
        self.assertEqual(unauth_resp.status_code, status.HTTP_401_UNAUTHORIZED)

        # 2. Non-driver roles rejected (Hospital staff)
        staff_token = self._get_jwt_token(self.hospital_staff.username, "StaffPassword123!@#")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {staff_token}")
        staff_resp = self.client.post("/api/agent/sessions/", {}, format="json")
        self.assertEqual(staff_resp.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Non-driver roles rejected (Police dispatcher)
        police_token = self._get_jwt_token(self.police_dispatcher.username, "PolicePassword123!@#")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {police_token}")
        police_resp = self.client.post("/api/agent/sessions/", {}, format="json")
        self.assertEqual(police_resp.status_code, status.HTTP_403_FORBIDDEN)

        # 4. Session ownership isolation: Driver 2 cannot access Driver 1's session
        driver1_token = self._get_jwt_token(self.driver1.username, self.driver_password)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {driver1_token}")
        d1_session_resp = self.client.post("/api/agent/sessions/", {}, format="json")
        d1_session_id = d1_session_resp.data["session_id"]

        # Driver 2 tries to access
        driver2_token = self._get_jwt_token(self.driver2.username, "DriverTwoPassword123!@#")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {driver2_token}")

        # Detail inspect
        d2_get_resp = self.client.get(f"/api/agent/sessions/{d1_session_id}/")
        self.assertEqual(d2_get_resp.status_code, status.HTTP_404_NOT_FOUND)

        # Turn post
        d2_turn_resp = self.client.post(
            f"/api/agent/sessions/{d1_session_id}/turn/",
            {"message": "I am hijacking this session."},
            format="json",
        )
        self.assertEqual(d2_turn_resp.status_code, status.HTTP_404_NOT_FOUND)

        # Confirm post
        d2_confirm_resp = self.client.post(
            f"/api/agent/sessions/{d1_session_id}/confirm-emergency/",
            {"confirmation": True},
            format="json",
        )
        self.assertEqual(d2_confirm_resp.status_code, status.HTTP_404_NOT_FOUND)

        # End post
        d2_end_resp = self.client.post(f"/api/agent/sessions/{d1_session_id}/end/", {}, format="json")
        self.assertEqual(d2_end_resp.status_code, status.HTTP_404_NOT_FOUND)

        # 5. Input validation on turn message (Driver 1)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {driver1_token}")

        # Empty message
        empty_resp = self.client.post(
            f"/api/agent/sessions/{d1_session_id}/turn/",
            {"message": ""},
            format="json",
        )
        self.assertEqual(empty_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(empty_resp.data["error"]["code"], "VALIDATION_ERROR")

        # Whitespace message
        white_resp = self.client.post(
            f"/api/agent/sessions/{d1_session_id}/turn/",
            {"message": "    \t \n  "},
            format="json",
        )
        self.assertEqual(white_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(white_resp.data["error"]["code"], "VALIDATION_ERROR")

        # Excessively long message (> 2000 characters)
        huge_resp = self.client.post(
            f"/api/agent/sessions/{d1_session_id}/turn/",
            {"message": "A" * 2005},
            format="json",
        )
        self.assertEqual(huge_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(huge_resp.data["error"]["code"], "VALIDATION_ERROR")

        # 6. Interaction with ended session rejected
        self.client.post(f"/api/agent/sessions/{d1_session_id}/end/", {}, format="json")
        post_end_turn = self.client.post(
            f"/api/agent/sessions/{d1_session_id}/turn/",
            {"message": "Can I continue talking?"},
            format="json",
        )
        self.assertEqual(post_end_turn.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(post_end_turn.data["error"]["code"], "SESSION_INACTIVE")
