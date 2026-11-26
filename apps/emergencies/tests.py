"""
Automated unit tests for SERTOS Emergencies application.

Covers:
- Hospital model creation, coordinate validation, uniqueness, and status preservation.
- Ambulance model creation, driver role verification, availability, dispatch eligibility,
  and single active driver constraint enforcement.
"""

import uuid
from datetime import timedelta
from decimal import Decimal
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import UserRole
from apps.emergencies.models import (
    Ambulance,
    AmbulanceLocation,
    BloodGroup,
    EmergencyEvent,
    EmergencyEventType,
    EmergencyIncident,
    Gender,
    Hospital,
    HospitalStaff,
    IncidentSeverity,
    IncidentStatus,
    HospitalIncidentResponse,
    PoliceIncidentAcknowledgement,
    Notification,
    Patient,
)
from apps.emergencies.services import (
    create_emergency_incident,
    record_ambulance_location,
    update_emergency_status,
)


def _approve_incident_for_transit(incident, hospital_staff, police_user):
    """Provide the explicit hospital and police clearances required for transit."""
    HospitalIncidentResponse.objects.create(
        incident=incident,
        hospital=incident.hospital,
        responded_by=hospital_staff,
        decision=HospitalIncidentResponse.Decision.ACCEPTED,
    )
    PoliceIncidentAcknowledgement.objects.create(
        incident=incident,
        acknowledged_by=police_user,
    )

User = get_user_model()


class EmergenciesScaffoldingTest(TestCase):
    """Smoke test to verify that the emergencies app is properly registered and configured."""

    def test_emergencies_app_is_registered(self):
        self.assertTrue(apps.is_installed("apps.emergencies"))
        app_config = apps.get_app_config("emergencies")
        self.assertEqual(app_config.name, "apps.emergencies")
        self.assertEqual(app_config.label, "emergencies")


class HospitalModelTest(TestCase):
    """Comprehensive test suite for the Hospital database model."""

    def test_hosp_01_valid_hospital_creation(self):
        """HOSP-01: Valid hospital creation with all fields."""
        hospital = Hospital(
            name="City Central Emergency Care",
            hospital_code="HOSP-BLR-001",
            address="123 Hospital Road, Bangalore, Karnataka",
            latitude=Decimal("12.971598"),
            longitude=Decimal("77.594562"),
            contact_number="+918022223333",
            is_active=True,
        )
        hospital.full_clean()
        hospital.save()

        self.assertIsNotNone(hospital.id)
        self.assertEqual(hospital.name, "City Central Emergency Care")
        self.assertEqual(hospital.hospital_code, "HOSP-BLR-001")
        self.assertEqual(str(hospital), "City Central Emergency Care (HOSP-BLR-001)")
        self.assertTrue(hospital.is_active)
        self.assertIsNotNone(hospital.created_at)
        self.assertIsNotNone(hospital.updated_at)

    def test_hosp_02_duplicate_hospital_code_rejected(self):
        """HOSP-02: Duplicate hospital code rejected by uniqueness constraint."""
        Hospital.objects.create(
            name="Apollo Hospital",
            hospital_code="HOSP-DUP-01",
            address="Apollo Road",
        )

        duplicate_hospital = Hospital(
            name="Apollo Branch",
            hospital_code="HOSP-DUP-01",
            address="Apollo Avenue",
        )

        with self.assertRaises((ValidationError, IntegrityError)):
            duplicate_hospital.full_clean()
            duplicate_hospital.save()

    def test_hosp_03_latitude_below_minus_90_rejected(self):
        """HOSP-03: Latitude below -90 is rejected during model validation."""
        hospital = Hospital(
            name="South Polar Clinic",
            hospital_code="HOSP-ERR-03",
            address="Antarctic Station",
            latitude=Decimal("-90.000001"),
            longitude=Decimal("0.000000"),
        )
        with self.assertRaises(ValidationError) as ctx:
            hospital.full_clean()
        self.assertIn("latitude", ctx.exception.message_dict)

    def test_hosp_04_latitude_above_90_rejected(self):
        """HOSP-04: Latitude above 90 is rejected during model validation."""
        hospital = Hospital(
            name="North Polar Clinic",
            hospital_code="HOSP-ERR-04",
            address="Arctic Station",
            latitude=Decimal("90.000001"),
            longitude=Decimal("0.000000"),
        )
        with self.assertRaises(ValidationError) as ctx:
            hospital.full_clean()
        self.assertIn("latitude", ctx.exception.message_dict)

    def test_hosp_05_longitude_below_minus_180_rejected(self):
        """HOSP-05: Longitude below -180 is rejected during model validation."""
        hospital = Hospital(
            name="West Marine Facility",
            hospital_code="HOSP-ERR-05",
            address="Pacific Float 1",
            latitude=Decimal("10.000000"),
            longitude=Decimal("-180.000001"),
        )
        with self.assertRaises(ValidationError) as ctx:
            hospital.full_clean()
        self.assertIn("longitude", ctx.exception.message_dict)

    def test_hosp_06_longitude_above_180_rejected(self):
        """HOSP-06: Longitude above 180 is rejected during model validation."""
        hospital = Hospital(
            name="East Marine Facility",
            hospital_code="HOSP-ERR-06",
            address="Pacific Float 2",
            latitude=Decimal("10.000000"),
            longitude=Decimal("180.000001"),
        )
        with self.assertRaises(ValidationError) as ctx:
            hospital.full_clean()
        self.assertIn("longitude", ctx.exception.message_dict)

    def test_hosp_07_both_coordinates_omitted_are_accepted(self):
        """HOSP-07: Both coordinates omitted (null) are accepted."""
        hospital = Hospital(
            name="Rural Community Center",
            hospital_code="HOSP-RUR-001",
            address="Village Center, Belgaum District",
            latitude=None,
            longitude=None,
        )
        hospital.full_clean()
        hospital.save()
        self.assertIsNone(hospital.latitude)
        self.assertIsNone(hospital.longitude)

    def test_hosp_08_only_one_coordinate_supplied_is_rejected(self):
        """HOSP-08: Supplying only latitude or only longitude is rejected."""
        # Case A: Latitude provided, longitude omitted
        hospital_lat_only = Hospital(
            name="Partial Coord Clinic A",
            hospital_code="HOSP-PART-01",
            address="Partial Road A",
            latitude=Decimal("12.971598"),
            longitude=None,
        )
        with self.assertRaises(ValidationError):
            hospital_lat_only.full_clean()

        # Case B: Longitude provided, latitude omitted
        hospital_lng_only = Hospital(
            name="Partial Coord Clinic B",
            hospital_code="HOSP-PART-02",
            address="Partial Road B",
            latitude=None,
            longitude=Decimal("77.594562"),
        )
        with self.assertRaises(ValidationError):
            hospital_lng_only.full_clean()

    def test_hosp_09_inactive_hospital_status_is_preserved(self):
        """HOSP-09: Inactive hospital status is correctly stored and preserved."""
        hospital = Hospital(
            name="Decommissioned Annex",
            hospital_code="HOSP-DECOM-01",
            address="Closed Street",
            is_active=False,
        )
        hospital.full_clean()
        hospital.save()

        refreshed = Hospital.objects.get(pk=hospital.pk)
        self.assertFalse(refreshed.is_active)


class AmbulanceModelTest(TestCase):
    """Comprehensive test suite for the Ambulance database model."""

    def setUp(self):
        # 1. Create a verified active ambulance driver
        self.driver_user = User.objects.create_user(
            username="paramedic_ramesh",
            password="StrongPassword123!@#",
            role=UserRole.AMBULANCE_DRIVER,
            is_active=True,
            is_verified=True,
        )

        # 2. Create another verified active ambulance driver
        self.second_driver = User.objects.create_user(
            username="paramedic_suresh",
            password="StrongPassword123!@#",
            role=UserRole.AMBULANCE_DRIVER,
            is_active=True,
            is_verified=True,
        )

        # 3. Create a hospital staff user (non-driver)
        self.hospital_staff_user = User.objects.create_user(
            username="dr_anita",
            password="StrongPassword123!@#",
            role=UserRole.HOSPITAL_STAFF,
            is_active=True,
            is_verified=True,
        )

        # 4. Create an inactive ambulance driver
        self.inactive_driver = User.objects.create_user(
            username="paramedic_inactive",
            password="StrongPassword123!@#",
            role=UserRole.AMBULANCE_DRIVER,
            is_active=False,
            is_verified=True,
        )

    def test_amb_01_valid_ambulance_creation(self):
        """AMB-01: Valid ambulance creation with all fields."""
        ambulance = Ambulance(
            vehicle_number="KA-01-EQ-9999",
            vehicle_type="Advanced Life Support",
            assigned_driver=self.driver_user,
            is_available=True,
            is_active=True,
        )
        ambulance.full_clean()
        ambulance.save()

        self.assertIsNotNone(ambulance.id)
        self.assertEqual(ambulance.vehicle_number, "KA-01-EQ-9999")
        self.assertEqual(ambulance.vehicle_type, "Advanced Life Support")
        self.assertEqual(ambulance.assigned_driver, self.driver_user)
        self.assertEqual(str(ambulance), "Ambulance KA-01-EQ-9999 (Advanced Life Support)")
        self.assertTrue(ambulance.is_eligible_for_dispatch)
        self.assertIsNotNone(ambulance.created_at)
        self.assertIsNotNone(ambulance.updated_at)

    def test_amb_02_duplicate_vehicle_number_rejected(self):
        """AMB-02: Duplicate vehicle number is rejected by uniqueness constraint."""
        Ambulance.objects.create(
            vehicle_number="KA-01-EQ-1000",
            vehicle_type="Basic Life Support",
        )

        duplicate_amb = Ambulance(
            vehicle_number="KA-01-EQ-1000",
            vehicle_type="Patient Transport",
        )

        with self.assertRaises((ValidationError, IntegrityError)):
            duplicate_amb.full_clean()
            duplicate_amb.save()

    def test_amb_03_valid_ambulance_driver_assignment(self):
        """AMB-03: Valid ambulance driver assignment satisfies validation and eligibility."""
        ambulance = Ambulance(
            vehicle_number="KA-01-EQ-1001",
            vehicle_type="Advanced Life Support",
            assigned_driver=self.driver_user,
        )
        ambulance.full_clean()
        ambulance.save()

        self.assertEqual(ambulance.assigned_driver, self.driver_user)
        self.assertTrue(ambulance.is_eligible_for_dispatch)

    def test_amb_04_non_driver_role_assignment_rejected(self):
        """AMB-04: Assigning user without AMBULANCE_DRIVER role is rejected."""
        ambulance = Ambulance(
            vehicle_number="KA-01-EQ-1002",
            vehicle_type="Basic Life Support",
            assigned_driver=self.hospital_staff_user,
        )
        with self.assertRaises(ValidationError) as ctx:
            ambulance.full_clean()
        self.assertIn("assigned_driver", ctx.exception.message_dict)

    def test_amb_05_inactive_user_assignment_rejected(self):
        """AMB-05: Assigning an inactive user as driver is rejected."""
        ambulance = Ambulance(
            vehicle_number="KA-01-EQ-1003",
            vehicle_type="Basic Life Support",
            assigned_driver=self.inactive_driver,
        )
        with self.assertRaises(ValidationError) as ctx:
            ambulance.full_clean()
        self.assertIn("assigned_driver", ctx.exception.message_dict)

    def test_amb_06_unassigned_ambulance_accepted(self):
        """AMB-06: Unassigned ambulance (driver is None) is valid but not eligible for dispatch."""
        ambulance = Ambulance(
            vehicle_number="KA-01-EQ-1004",
            vehicle_type="Patient Transport",
            assigned_driver=None,
        )
        ambulance.full_clean()
        ambulance.save()

        self.assertIsNone(ambulance.assigned_driver)
        self.assertFalse(ambulance.is_eligible_for_dispatch)

    def test_amb_07_inactive_ambulance_status_is_preserved(self):
        """AMB-07: Inactive ambulance status is preserved and not eligible for dispatch."""
        ambulance = Ambulance(
            vehicle_number="KA-01-EQ-1005",
            vehicle_type="Basic Life Support",
            assigned_driver=self.driver_user,
            is_active=False,
        )
        ambulance.full_clean()
        ambulance.save()

        refreshed = Ambulance.objects.get(pk=ambulance.pk)
        self.assertFalse(refreshed.is_active)
        self.assertFalse(refreshed.is_eligible_for_dispatch)

    def test_amb_08_unavailable_ambulance_status_is_preserved(self):
        """AMB-08: Unavailable ambulance status is preserved and not eligible for dispatch."""
        ambulance = Ambulance(
            vehicle_number="KA-01-EQ-1006",
            vehicle_type="Advanced Life Support",
            assigned_driver=self.driver_user,
            is_available=False,
        )
        ambulance.full_clean()
        ambulance.save()

        refreshed = Ambulance.objects.get(pk=ambulance.pk)
        self.assertFalse(refreshed.is_available)
        self.assertFalse(refreshed.is_eligible_for_dispatch)

    def test_amb_09_duplicate_active_driver_assignment_prevented(self):
        """
        AMB-09: Duplicate active driver assignment is prevented.
        - Assigning driver to active ambulance A1 succeeds.
        - Attempting to assign same driver to active ambulance A2 fails.
        - Decommissioning ambulance A1 (is_active=False) frees driver for ambulance A2.
        """
        # Step 1: Assign driver_user to active ambulance A1
        amb1 = Ambulance.objects.create(
            vehicle_number="KA-01-EQ-2001",
            vehicle_type="Advanced Life Support",
            assigned_driver=self.driver_user,
            is_active=True,
        )

        # Step 2: Attempting to assign driver_user to active ambulance A2 fails in full_clean()
        amb2 = Ambulance(
            vehicle_number="KA-01-EQ-2002",
            vehicle_type="Basic Life Support",
            assigned_driver=self.driver_user,
            is_active=True,
        )
        with self.assertRaises(ValidationError) as ctx:
            amb2.full_clean()
        self.assertIn("assigned_driver", ctx.exception.message_dict)

        # Also verify database constraint level enforcement on direct save()
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                amb2.save()

        # Step 3: Decommission ambulance A1 (is_active=False)
        amb1.is_active = False
        amb1.save()

        # Step 4: Driver can now be assigned to active ambulance A2
        amb2.full_clean()
        amb2.save()
        self.assertEqual(amb2.assigned_driver, self.driver_user)
        self.assertTrue(amb2.is_active)


class EmergencyIncidentModelTest(TestCase):
    """Comprehensive test suite for the EmergencyIncident model."""

    def setUp(self):
        # 1. Active, verified ambulance driver
        self.driver_user = User.objects.create_user(
            username="paramedic_vikram",
            password="StrongPassword123!@#",
            role=UserRole.AMBULANCE_DRIVER,
            is_active=True,
            is_verified=True,
        )

        # 2. Another active ambulance driver
        self.other_driver = User.objects.create_user(
            username="paramedic_kavita",
            password="StrongPassword123!@#",
            role=UserRole.AMBULANCE_DRIVER,
            is_active=True,
            is_verified=True,
        )

        # 3. Hospital staff user (non-driver)
        self.hospital_staff_user = User.objects.create_user(
            username="dr_sharma",
            password="StrongPassword123!@#",
            role=UserRole.HOSPITAL_STAFF,
            is_active=True,
            is_verified=True,
        )

        # 4. Inactive ambulance driver
        self.inactive_driver = User.objects.create_user(
            username="paramedic_retired",
            password="StrongPassword123!@#",
            role=UserRole.AMBULANCE_DRIVER,
            is_active=False,
            is_verified=True,
        )

        # 5. Active destination hospital
        self.hospital = Hospital.objects.create(
            name="Manipal Emergency Care",
            hospital_code="HOSP-MAN-01",
            address="HAL Airport Road, Bangalore",
            latitude=Decimal("12.959172"),
            longitude=Decimal("77.654884"),
            is_active=True,
        )

        # 6. Inactive destination hospital
        self.inactive_hospital = Hospital.objects.create(
            name="Closed Community Hospital",
            hospital_code="HOSP-CLO-01",
            address="Old Closed Road",
            is_active=False,
        )

        # 7. Active ambulance assigned to self.driver_user
        self.ambulance = Ambulance.objects.create(
            vehicle_number="KA-01-EQ-5001",
            vehicle_type="Advanced Life Support",
            assigned_driver=self.driver_user,
            is_available=True,
            is_active=True,
        )

        # 8. Active ambulance assigned to self.other_driver
        self.other_ambulance = Ambulance.objects.create(
            vehicle_number="KA-01-EQ-5002",
            vehicle_type="Basic Life Support",
            assigned_driver=self.other_driver,
            is_available=True,
            is_active=True,
        )

        # 9. Inactive ambulance assigned to self.driver_user
        self.inactive_ambulance = Ambulance.objects.create(
            vehicle_number="KA-01-EQ-5003",
            vehicle_type="Patient Transport",
            assigned_driver=None,
            is_available=False,
            is_active=False,
        )

    def test_inc_01_valid_incident_creation(self):
        """INC-01: Valid emergency incident creation with all required relations."""
        incident = EmergencyIncident(
            incident_number="INC-20261114-0001",
            reporting_driver=self.driver_user,
            ambulance=self.ambulance,
            hospital=self.hospital,
            severity=IncidentSeverity.CRITICAL,
            status=IncidentStatus.REPORTED,
            description="Severe multi-vehicle collision with critical trauma.",
        )
        incident.full_clean()
        incident.save()

        self.assertIsNotNone(incident.id)
        self.assertEqual(incident.incident_number, "INC-20261114-0001")
        self.assertEqual(incident.reporting_driver, self.driver_user)
        self.assertEqual(incident.ambulance, self.ambulance)
        self.assertEqual(incident.hospital, self.hospital)
        self.assertEqual(incident.severity, IncidentSeverity.CRITICAL)
        self.assertEqual(incident.status, IncidentStatus.REPORTED)
        self.assertIn("Incident INC-20261114-0001", str(incident))

    def test_inc_02_duplicate_incident_number_rejected(self):
        """INC-02: Duplicate incident_number rejected by uniqueness constraint."""
        EmergencyIncident.objects.create(
            incident_number="INC-DUP-0001",
            reporting_driver=self.driver_user,
            ambulance=self.ambulance,
            hospital=self.hospital,
        )

        dup = EmergencyIncident(
            incident_number="INC-DUP-0001",
            reporting_driver=self.driver_user,
            ambulance=self.ambulance,
            hospital=self.hospital,
        )
        with self.assertRaises((ValidationError, IntegrityError)):
            dup.full_clean()
            dup.save()

    def test_inc_03_invalid_ambulance_driver_assignment(self):
        """INC-03: Invalid ambulance driver assignment combinations are rejected."""
        # Case A: Ambulance assigned to other_driver, but reported by driver_user
        inc_mismatch = EmergencyIncident(
            incident_number="INC-MISMATCH-01",
            reporting_driver=self.driver_user,
            ambulance=self.other_ambulance,
            hospital=self.hospital,
        )
        with self.assertRaises(ValidationError) as ctx:
            inc_mismatch.full_clean()
        self.assertIn("ambulance", ctx.exception.message_dict)

        # Case B: Reporting user has non-driver role (HOSPITAL_STAFF)
        inc_non_driver = EmergencyIncident(
            incident_number="INC-NONDRV-01",
            reporting_driver=self.hospital_staff_user,
            ambulance=self.ambulance,
            hospital=self.hospital,
        )
        with self.assertRaises(ValidationError) as ctx:
            inc_non_driver.full_clean()
        self.assertIn("reporting_driver", ctx.exception.message_dict)

        # Case C: Reporting driver is inactive
        inc_inactive_drv = EmergencyIncident(
            incident_number="INC-INACTDRV-01",
            reporting_driver=self.inactive_driver,
            ambulance=self.ambulance,
            hospital=self.hospital,
        )
        with self.assertRaises(ValidationError) as ctx:
            inc_inactive_drv.full_clean()
        self.assertIn("reporting_driver", ctx.exception.message_dict)

    def test_inc_04_inactive_ambulance_rejected(self):
        """INC-04: Inactive ambulance is rejected."""
        inc = EmergencyIncident(
            incident_number="INC-INACTAMB-01",
            reporting_driver=self.driver_user,
            ambulance=self.inactive_ambulance,
            hospital=self.hospital,
        )
        with self.assertRaises(ValidationError) as ctx:
            inc.full_clean()
        self.assertIn("ambulance", ctx.exception.message_dict)

    def test_inc_05_inactive_hospital_rejected(self):
        """INC-05: Inactive destination hospital is rejected."""
        inc = EmergencyIncident(
            incident_number="INC-INACTHOSP-01",
            reporting_driver=self.driver_user,
            ambulance=self.ambulance,
            hospital=self.inactive_hospital,
        )
        with self.assertRaises(ValidationError) as ctx:
            inc.full_clean()
        self.assertIn("hospital", ctx.exception.message_dict)

    def test_inc_06_invalid_severity_choice_rejected(self):
        """INC-06: Invalid severity choice is rejected by model validation."""
        inc = EmergencyIncident(
            incident_number="INC-BADSEV-01",
            reporting_driver=self.driver_user,
            ambulance=self.ambulance,
            hospital=self.hospital,
            severity="ULTRA_CRITICAL",
        )
        with self.assertRaises(ValidationError) as ctx:
            inc.full_clean()
        self.assertIn("severity", ctx.exception.message_dict)

    def test_inc_07_invalid_lifecycle_status_choice_rejected(self):
        """INC-07: Invalid lifecycle status choice is rejected by model validation."""
        inc = EmergencyIncident(
            incident_number="INC-BADSTAT-01",
            reporting_driver=self.driver_user,
            ambulance=self.ambulance,
            hospital=self.hospital,
            status="FLYING",
        )
        with self.assertRaises(ValidationError) as ctx:
            inc.full_clean()
        self.assertIn("status", ctx.exception.message_dict)

    def test_inc_08_invalid_status_transition_rejected(self):
        """INC-08: Invalid lifecycle state transition is rejected."""
        inc = EmergencyIncident.objects.create(
            incident_number="INC-TRANS-01",
            reporting_driver=self.driver_user,
            ambulance=self.ambulance,
            hospital=self.hospital,
            status=IncidentStatus.REPORTED,
        )

        # Illegal skip: REPORTED -> CLOSED directly
        inc.status = IncidentStatus.CLOSED
        with self.assertRaises(ValidationError) as ctx:
            inc.full_clean()
        self.assertIn("status", ctx.exception.message_dict)

        # Mark cancelled legitimately through terminal flow, then verify backward jump is rejected
        inc.status = IncidentStatus.CANCELLED
        inc.full_clean()
        inc.save()

        inc.status = IncidentStatus.IN_TRANSIT
        with self.assertRaises(ValidationError) as ctx:
            inc.full_clean()
        self.assertIn("status", ctx.exception.message_dict)

    def test_inc_09_valid_lifecycle_transition_progression(self):
        """INC-09: Valid lifecycle transition progression sets timestamps."""
        inc = EmergencyIncident.objects.create(
            incident_number="INC-PROGRESS-01",
            reporting_driver=self.driver_user,
            ambulance=self.ambulance,
            hospital=self.hospital,
            status=IncidentStatus.REPORTED,
        )
        self.assertIsNone(inc.assigned_at)

        # Step 1: REPORTED -> ASSIGNED
        inc.status = IncidentStatus.ASSIGNED
        inc.full_clean()
        inc.save()
        self.assertIsNotNone(inc.assigned_at)

        # Step 2: ASSIGNED -> IN_TRANSIT
        inc.status = IncidentStatus.IN_TRANSIT
        inc.full_clean()
        inc.save()
        self.assertIsNotNone(inc.in_transit_at)

        # Step 3: IN_TRANSIT -> ARRIVED
        inc.status = IncidentStatus.ARRIVED
        inc.full_clean()
        inc.save()
        self.assertIsNotNone(inc.arrived_at)

        # Step 4: ARRIVED -> CLOSED
        inc.status = IncidentStatus.CLOSED
        inc.full_clean()
        inc.save()
        self.assertIsNotNone(inc.closed_at)

    def test_inc_10_cancellation_permitted_from_active_states(self):
        """INC-10: Cancellation to terminal CANCELLED is allowed from active states."""
        inc = EmergencyIncident.objects.create(
            incident_number="INC-CANCEL-01",
            reporting_driver=self.driver_user,
            ambulance=self.ambulance,
            hospital=self.hospital,
            status=IncidentStatus.REPORTED,
        )
        inc.status = IncidentStatus.CANCELLED
        inc.full_clean()
        inc.save()
        self.assertEqual(inc.status, IncidentStatus.CANCELLED)
        self.assertIsNotNone(inc.cancelled_at)


class PatientModelTest(TestCase):
    """Comprehensive test suite for the Patient database model."""

    def setUp(self):
        self.driver_user = User.objects.create_user(
            username="paramedic_rohit",
            password="StrongPassword123!@#",
            role=UserRole.AMBULANCE_DRIVER,
            is_active=True,
            is_verified=True,
        )
        self.hospital = Hospital.objects.create(
            name="Fortis Emergency",
            hospital_code="HOSP-FOR-01",
            address="Bannerghatta Road, Bangalore",
            is_active=True,
        )
        self.ambulance = Ambulance.objects.create(
            vehicle_number="KA-01-EQ-7777",
            vehicle_type="Advanced Life Support",
            assigned_driver=self.driver_user,
            is_available=True,
            is_active=True,
        )
        self.incident = EmergencyIncident.objects.create(
            incident_number="INC-PAT-0001",
            reporting_driver=self.driver_user,
            ambulance=self.ambulance,
            hospital=self.hospital,
        )

    def test_pat_01_valid_patient_creation_linked_to_incident(self):
        """PAT-01: Valid patient creation linked to an incident."""
        patient = Patient(
            incident=self.incident,
            name="Priya Sharma",
            age=34,
            gender=Gender.FEMALE,
            blood_group=BloodGroup.O_POSITIVE,
            medical_notes="Asthmatic, conscious, severe dyspnea.",
        )
        patient.full_clean()
        patient.save()

        self.assertIsNotNone(patient.id)
        self.assertEqual(patient.name, "Priya Sharma")
        self.assertEqual(patient.age, 34)
        self.assertEqual(patient.gender, Gender.FEMALE)
        self.assertEqual(patient.blood_group, BloodGroup.O_POSITIVE)
        self.assertEqual(patient.incident, self.incident)
        self.assertEqual(self.incident.patients.count(), 1)
        self.assertIn("Priya Sharma", str(patient))

    def test_pat_02_valid_patient_creation_without_incident(self):
        """PAT-02: Valid patient creation without incident (incident=None)."""
        patient = Patient(
            incident=None,
            name="Unidentified Male",
            age=None,
            gender=Gender.MALE,
        )
        patient.full_clean()
        patient.save()

        self.assertIsNotNone(patient.id)
        self.assertIsNone(patient.incident)
        self.assertIsNone(patient.age)
        self.assertEqual(patient.name, "Unidentified Male")

    def test_pat_03_invalid_age_rejected(self):
        """PAT-03: Invalid age below 0 or above 150 is rejected."""
        pat_neg = Patient(name="Baby Negative", age=-1)
        with self.assertRaises(ValidationError) as ctx:
            pat_neg.full_clean()
        self.assertIn("age", ctx.exception.message_dict)

        pat_over = Patient(name="Ancient Person", age=151)
        with self.assertRaises(ValidationError) as ctx:
            pat_over.full_clean()
        self.assertIn("age", ctx.exception.message_dict)

    def test_pat_04_invalid_gender_choice_rejected(self):
        """PAT-04: Invalid gender choice is rejected."""
        pat = Patient(name="Test Patient", gender="ALIEN")
        with self.assertRaises(ValidationError) as ctx:
            pat.full_clean()
        self.assertIn("gender", ctx.exception.message_dict)

    def test_pat_05_blood_group_and_medical_notes_preserved(self):
        """PAT-05: Blood group and medical notes are accurately stored and retrieved."""
        patient = Patient.objects.create(
            incident=self.incident,
            name="Anil Kumar",
            age=45,
            gender=Gender.MALE,
            blood_group=BloodGroup.AB_POSITIVE,
            medical_notes="Diabetic Type 2; Penicillin allergy.",
        )
        refreshed = Patient.objects.get(pk=patient.pk)
        self.assertEqual(refreshed.blood_group, "AB+")
        self.assertEqual(refreshed.medical_notes, "Diabetic Type 2; Penicillin allergy.")


class EmergencyIncidentAPITest(TestCase):
    """
    Comprehensive API endpoint test suite for SERTOS EmergencyIncident and Patient APIs.

    Covers Task 4.2 requirements:
    - POST /api/emergencies/
    - GET  /api/emergencies/
    - GET  /api/emergencies/<uuid:pk>/
    - Role-based access control, scoping, validation, and atomic rollback.
    """

    def setUp(self):
        from rest_framework.test import APIClient
        self.client = APIClient()

        # 1. Create Active & Inactive Hospitals
        self.hospital = Hospital.objects.create(
            name="City Central Emergency Care",
            hospital_code="HOSP-API-001",
            address="100 Main St, Bangalore",
            latitude=Decimal("12.971598"),
            longitude=Decimal("77.594562"),
            is_active=True,
        )
        self.inactive_hospital = Hospital.objects.create(
            name="Decommissioned Trauma Center",
            hospital_code="HOSP-API-002",
            address="200 Old Road, Bangalore",
            is_active=False,
        )

        # 2. Create Drivers
        self.driver1 = User.objects.create_user(
            username="driver_alpha",
            email="driver_alpha@sertos.local",
            password="Password123!",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=True,
            is_active=True,
        )
        self.ambulance1 = Ambulance.objects.create(
            vehicle_number="KA-01-EQ-5001",
            vehicle_type="Advanced Life Support (ALS)",
            assigned_driver=self.driver1,
            is_available=True,
            is_active=True,
        )

        self.driver2 = User.objects.create_user(
            username="driver_bravo",
            email="driver_bravo@sertos.local",
            password="Password123!",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=True,
            is_active=True,
        )
        self.ambulance2 = Ambulance.objects.create(
            vehicle_number="KA-01-EQ-5002",
            vehicle_type="Basic Life Support (BLS)",
            assigned_driver=self.driver2,
            is_available=True,
            is_active=True,
        )

        self.unassigned_driver = User.objects.create_user(
            username="driver_unassigned",
            email="driver_unassigned@sertos.local",
            password="Password123!",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=True,
            is_active=True,
        )

        self.unverified_driver = User.objects.create_user(
            username="driver_unverified",
            email="driver_unverified@sertos.local",
            password="Password123!",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=False,
            is_active=True,
        )

        # 3. Non-Driver Operational Roles
        self.hospital_staff = User.objects.create_user(
            username="nurse_sarah",
            email="nurse_sarah@sertos.local",
            password="Password123!",
            role=UserRole.HOSPITAL_STAFF,
            is_verified=True,
            is_active=True,
        )

        self.police_dispatcher = User.objects.create_user(
            username="officer_kumar",
            email="officer_kumar@sertos.local",
            password="Password123!",
            role=UserRole.POLICE_DISPATCHER,
            is_verified=True,
            is_active=True,
        )

        self.admin_user = User.objects.create_superuser(
            username="system_admin",
            email="admin@sertos.local",
            password="Password123!",
            role=UserRole.ADMIN,
            is_verified=True,
            is_active=True,
        )

    def test_api_01_successful_emergency_creation_with_patient(self):
        """API-01: Verified driver with available ambulance successfully reports incident with patient."""
        self.client.force_authenticate(user=self.driver1)
        payload = {
            "hospital_id": str(self.hospital.id),
            "severity": IncidentSeverity.CRITICAL,
            "description": "Multi-vehicle collision on Outer Ring Road.",
            "patient": {
                "name": "Ramesh Rao",
                "age": 42,
                "gender": Gender.MALE,
                "blood_group": BloodGroup.O_POSITIVE,
                "medical_notes": "Blunt chest trauma, stable vitals.",
            },
        }

        response = self.client.post("/api/emergencies/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["message"], "Emergency incident reported successfully.")

        data = response.data["data"]
        self.assertTrue(data["incident_number"].startswith("INC-"))
        self.assertEqual(data["severity"], IncidentSeverity.CRITICAL)
        self.assertEqual(data["status"], IncidentStatus.REPORTED)
        self.assertEqual(data["reporting_driver"]["username"], "driver_alpha")
        self.assertEqual(data["ambulance"]["vehicle_number"], "KA-01-EQ-5001")
        self.assertEqual(data["hospital"]["hospital_code"], "HOSP-API-001")

        # Patient verification
        self.assertEqual(len(data["patients"]), 1)
        patient_info = data["patients"][0]
        self.assertEqual(patient_info["name"], "Ramesh Rao")
        self.assertEqual(patient_info["age"], 42)
        self.assertEqual(patient_info["gender"], Gender.MALE)
        self.assertEqual(patient_info["blood_group"], BloodGroup.O_POSITIVE)

        # Confirm DB persistence
        self.assertEqual(EmergencyIncident.objects.count(), 1)
        self.assertEqual(Patient.objects.count(), 1)

    def test_api_02_missing_or_invalid_hospital(self):
        """API-02: Emergency creation rejected when hospital is omitted, non-existent, or inactive."""
        self.client.force_authenticate(user=self.driver1)

        # 1. Missing hospital
        res_missing = self.client.post("/api/emergencies/", {"severity": IncidentSeverity.HIGH}, format="json")
        self.assertEqual(res_missing.status_code, 400)
        self.assertFalse(res_missing.data["success"])

        # 2. Non-existent hospital UUID
        import uuid
        res_nonexist = self.client.post(
            "/api/emergencies/",
            {"hospital_id": str(uuid.uuid4()), "severity": IncidentSeverity.HIGH},
            format="json",
        )
        self.assertEqual(res_nonexist.status_code, 400)
        self.assertFalse(res_nonexist.data["success"])

        # 3. Inactive hospital
        res_inactive = self.client.post(
            "/api/emergencies/",
            {"hospital_id": str(self.inactive_hospital.id), "severity": IncidentSeverity.HIGH},
            format="json",
        )
        self.assertEqual(res_inactive.status_code, 400)
        self.assertFalse(res_inactive.data["success"])
        self.assertIn("inactive", str(res_inactive.data))

    def test_api_03_driver_without_assigned_ambulance(self):
        """API-03: Verified driver without an assigned ambulance cannot report an emergency."""
        self.client.force_authenticate(user=self.unassigned_driver)
        payload = {"hospital_id": str(self.hospital.id), "severity": IncidentSeverity.HIGH}

        response = self.client.post("/api/emergencies/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertIn("ambulance", response.data["errors"])

    def test_api_04_unavailable_ambulance(self):
        """API-04: Reporting incident fails if the driver's assigned ambulance is unavailable."""
        self.ambulance1.is_available = False
        self.ambulance1.save()

        self.client.force_authenticate(user=self.driver1)
        payload = {"hospital_id": str(self.hospital.id), "severity": IncidentSeverity.HIGH}

        response = self.client.post("/api/emergencies/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertIn("unavailable", str(response.data["errors"]))

    def test_api_05_unverified_driver(self):
        """API-05: Unverified ambulance driver is rejected with HTTP 403 Forbidden."""
        self.client.force_authenticate(user=self.unverified_driver)
        payload = {"hospital_id": str(self.hospital.id), "severity": IncidentSeverity.HIGH}

        response = self.client.post("/api/emergencies/", payload, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.data["success"])

    def test_api_06_unauthorized_role(self):
        """API-06: Hospital staff and police dispatchers cannot create or access emergency endpoints."""
        payload = {"hospital_id": str(self.hospital.id), "severity": IncidentSeverity.HIGH}

        # 1. Hospital staff cannot POST or GET
        self.client.force_authenticate(user=self.hospital_staff)
        res_hosp_post = self.client.post("/api/emergencies/", payload, format="json")
        self.assertEqual(res_hosp_post.status_code, 403)
        res_hosp_get = self.client.get("/api/emergencies/")
        self.assertEqual(res_hosp_get.status_code, 403)

        # 2. Police dispatcher cannot POST or GET
        self.client.force_authenticate(user=self.police_dispatcher)
        res_pol_post = self.client.post("/api/emergencies/", payload, format="json")
        self.assertEqual(res_pol_post.status_code, 403)
        res_pol_get = self.client.get("/api/emergencies/")
        self.assertEqual(res_pol_get.status_code, 403)

        # 3. Anonymous user receives 401
        self.client.force_authenticate(user=None)
        res_anon_post = self.client.post("/api/emergencies/", payload, format="json")
        self.assertEqual(res_anon_post.status_code, 401)
        res_anon_get = self.client.get("/api/emergencies/")
        self.assertEqual(res_anon_get.status_code, 401)

    def test_api_07_listing_only_permitted_incidents(self):
        """API-07: Drivers can list only their own incidents; admins can list all incidents."""
        from apps.emergencies.services import create_emergency_incident

        # Create 2 incidents for driver 1 and 1 incident for driver 2
        inc1 = create_emergency_incident(self.driver1, self.hospital.id, description="Driver 1 Incident A")
        inc2 = create_emergency_incident(self.driver1, self.hospital.id, description="Driver 1 Incident B")
        inc3 = create_emergency_incident(self.driver2, self.hospital.id, description="Driver 2 Incident")

        # Driver 1 query
        self.client.force_authenticate(user=self.driver1)
        res1 = self.client.get("/api/emergencies/")
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(len(res1.data["data"]), 2)
        returned_ids1 = {item["id"] for item in res1.data["data"]}
        self.assertEqual(returned_ids1, {str(inc1.id), str(inc2.id)})

        # Driver 2 query
        self.client.force_authenticate(user=self.driver2)
        res2 = self.client.get("/api/emergencies/")
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(len(res2.data["data"]), 1)
        self.assertEqual(res2.data["data"][0]["id"], str(inc3.id))

        # Admin query
        self.client.force_authenticate(user=self.admin_user)
        res_admin = self.client.get("/api/emergencies/")
        self.assertEqual(res_admin.status_code, 200)
        self.assertEqual(len(res_admin.data["data"]), 3)

    def test_api_08_retrieving_another_driver_incident_denied_or_404(self):
        """API-08: Retrieving another driver's incident returns 404 Not Found."""
        from apps.emergencies.services import create_emergency_incident

        inc2 = create_emergency_incident(self.driver2, self.hospital.id, description="Driver 2 Private Incident")

        # Driver 1 attempts to retrieve Driver 2's incident
        self.client.force_authenticate(user=self.driver1)
        response = self.client.get(f"/api/emergencies/{inc2.id}/")
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data["success"])

        # Driver 2 retrieves own incident successfully
        self.client.force_authenticate(user=self.driver2)
        res_own = self.client.get(f"/api/emergencies/{inc2.id}/")
        self.assertEqual(res_own.status_code, 200)
        self.assertEqual(res_own.data["data"]["id"], str(inc2.id))

        # Admin retrieves driver 2's incident successfully
        self.client.force_authenticate(user=self.admin_user)
        res_admin = self.client.get(f"/api/emergencies/{inc2.id}/")
        self.assertEqual(res_admin.status_code, 200)
        self.assertEqual(res_admin.data["data"]["id"], str(inc2.id))

    def test_api_09_invalid_patient_data(self):
        """API-09: Invalid nested patient demographic data returns HTTP 400."""
        self.client.force_authenticate(user=self.driver1)
        payload = {
            "hospital_id": str(self.hospital.id),
            "severity": IncidentSeverity.HIGH,
            "patient": {
                "name": "Invalid Age Person",
                "age": 250,  # Invalid: > 150
                "gender": Gender.UNKNOWN,
            },
        }

        response = self.client.post("/api/emergencies/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertIn("patient", response.data["errors"])

    def test_api_10_atomic_rollback_when_patient_creation_fails(self):
        """API-10: Incident creation rolls back completely when nested patient validation fails."""
        self.assertEqual(EmergencyIncident.objects.count(), 0)
        self.assertEqual(Patient.objects.count(), 0)

        self.client.force_authenticate(user=self.driver1)
        payload = {
            "hospital_id": str(self.hospital.id),
            "severity": IncidentSeverity.HIGH,
            "description": "This should not be saved",
            "patient": {
                "name": "Rollback Test",
                "age": -10,  # Invalid age
            },
        }

        response = self.client.post("/api/emergencies/", payload, format="json")
        self.assertEqual(response.status_code, 400)

        # Database must have zero incident rows and zero patient rows
        self.assertEqual(EmergencyIncident.objects.count(), 0)
        self.assertEqual(Patient.objects.count(), 0)

    def test_api_11_driver_cannot_spoof_reporting_driver(self):
        """API-11: Supplying reporting_driver or ambulance in payload is ignored; derived from request.user."""
        self.client.force_authenticate(user=self.driver1)
        payload = {
            "hospital_id": str(self.hospital.id),
            "reporting_driver": str(self.driver2.id),  # Attempted spoof
            "ambulance": str(self.ambulance2.id),      # Attempted vehicle hijack
            "description": "Legitimate driver reporting",
        }

        response = self.client.post("/api/emergencies/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        data = response.data["data"]

        # Must be assigned to driver1 and ambulance1, NOT driver2/ambulance2
        self.assertEqual(data["reporting_driver"]["username"], "driver_alpha")
        self.assertEqual(data["ambulance"]["vehicle_number"], "KA-01-EQ-5001")

    def test_api_12_url_reverse_resolution(self):
        """API-12: Reverse URL resolution for emergencies routes."""
        from django.urls import resolve, reverse
        import uuid

        list_create_url = reverse("emergencies:incident_list_create")
        self.assertEqual(list_create_url, "/api/emergencies/")
        match_lc = resolve("/api/emergencies/")
        self.assertEqual(match_lc.url_name, "incident_list_create")

        fake_id = uuid.uuid4()
        detail_url = reverse("emergencies:incident_detail", kwargs={"pk": fake_id})
        self.assertEqual(detail_url, f"/api/emergencies/{fake_id}/")
        match_det = resolve(f"/api/emergencies/{fake_id}/")
        self.assertEqual(match_det.url_name, "incident_detail")

        status_url = reverse("emergencies:incident_status_update", kwargs={"pk": fake_id})
        self.assertEqual(status_url, f"/api/emergencies/{fake_id}/status/")
        match_stat = resolve(f"/api/emergencies/{fake_id}/status/")
        self.assertEqual(match_stat.url_name, "incident_status_update")

    def test_status_01_valid_lifecycle_progression(self):
        """STATUS-01: Driver successfully progresses incident REPORTED -> ASSIGNED -> IN_TRANSIT -> ARRIVED -> CLOSED."""
        from apps.emergencies.services import create_emergency_incident

        inc = create_emergency_incident(self.driver1, self.hospital.id, description="Trauma Case")
        self.assertEqual(inc.status, IncidentStatus.REPORTED)
        self.assertIsNone(inc.assigned_at)
        self.assertIsNone(inc.in_transit_at)
        self.assertIsNone(inc.arrived_at)
        self.assertIsNone(inc.closed_at)

        self.client.force_authenticate(user=self.driver1)
        url = f"/api/emergencies/{inc.id}/status/"

        # 1. REPORTED -> ASSIGNED
        res1 = self.client.patch(url, {"status": IncidentStatus.ASSIGNED}, format="json")
        self.assertEqual(res1.status_code, 200)
        self.assertTrue(res1.data["success"])
        self.assertEqual(res1.data["data"]["status"], IncidentStatus.ASSIGNED)
        self.assertIsNotNone(res1.data["data"]["assigned_at"])

        # 2. ASSIGNED -> IN_TRANSIT
        _approve_incident_for_transit(inc, self.hospital_staff, self.police_dispatcher)
        res2 = self.client.patch(url, {"status": IncidentStatus.IN_TRANSIT}, format="json")
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.data["data"]["status"], IncidentStatus.IN_TRANSIT)
        self.assertIsNotNone(res2.data["data"]["in_transit_at"])

        # 3. IN_TRANSIT -> ARRIVED
        res3 = self.client.patch(url, {"status": IncidentStatus.ARRIVED}, format="json")
        self.assertEqual(res3.status_code, 200)
        self.assertEqual(res3.data["data"]["status"], IncidentStatus.ARRIVED)
        self.assertIsNotNone(res3.data["data"]["arrived_at"])

        # 4. ARRIVED -> CLOSED
        res4 = self.client.patch(url, {"status": IncidentStatus.CLOSED}, format="json")
        self.assertEqual(res4.status_code, 200)
        self.assertEqual(res4.data["data"]["status"], IncidentStatus.CLOSED)
        self.assertIsNotNone(res4.data["data"]["closed_at"])

        # Confirm DB state
        inc.refresh_from_db()
        self.assertEqual(inc.status, IncidentStatus.CLOSED)
        self.assertIsNotNone(inc.assigned_at)
        self.assertIsNotNone(inc.in_transit_at)
        self.assertIsNotNone(inc.arrived_at)
        self.assertIsNotNone(inc.closed_at)

    def test_status_02_cancellation_from_active_states(self):
        """STATUS-02: Incident can be cancelled from any active state (REPORTED, ASSIGNED, IN_TRANSIT, ARRIVED)."""
        from apps.emergencies.services import create_emergency_incident

        self.client.force_authenticate(user=self.driver1)

        # Case A: Cancel from REPORTED
        inc_rep = create_emergency_incident(self.driver1, self.hospital.id, description="False alarm")
        res_rep = self.client.patch(f"/api/emergencies/{inc_rep.id}/status/", {"status": IncidentStatus.CANCELLED}, format="json")
        self.assertEqual(res_rep.status_code, 200)
        self.assertEqual(res_rep.data["data"]["status"], IncidentStatus.CANCELLED)
        self.assertIsNotNone(res_rep.data["data"]["cancelled_at"])

        # Case B: Cancel from ASSIGNED
        inc_asg = create_emergency_incident(self.driver1, self.hospital.id)
        self.client.patch(f"/api/emergencies/{inc_asg.id}/status/", {"status": IncidentStatus.ASSIGNED}, format="json")
        res_asg = self.client.patch(f"/api/emergencies/{inc_asg.id}/status/", {"status": IncidentStatus.CANCELLED}, format="json")
        self.assertEqual(res_asg.status_code, 200)
        self.assertEqual(res_asg.data["data"]["status"], IncidentStatus.CANCELLED)

        # Case C: Cancel from IN_TRANSIT
        inc_trn = create_emergency_incident(self.driver1, self.hospital.id)
        self.client.patch(f"/api/emergencies/{inc_trn.id}/status/", {"status": IncidentStatus.ASSIGNED}, format="json")
        _approve_incident_for_transit(inc_trn, self.hospital_staff, self.police_dispatcher)
        self.client.patch(f"/api/emergencies/{inc_trn.id}/status/", {"status": IncidentStatus.IN_TRANSIT}, format="json")
        res_trn = self.client.patch(f"/api/emergencies/{inc_trn.id}/status/", {"status": IncidentStatus.CANCELLED}, format="json")
        self.assertEqual(res_trn.status_code, 200)
        self.assertEqual(res_trn.data["data"]["status"], IncidentStatus.CANCELLED)

        # Case D: Cancel from ARRIVED
        inc_arv = create_emergency_incident(self.driver1, self.hospital.id)
        self.client.patch(f"/api/emergencies/{inc_arv.id}/status/", {"status": IncidentStatus.ASSIGNED}, format="json")
        _approve_incident_for_transit(inc_arv, self.hospital_staff, self.police_dispatcher)
        self.client.patch(f"/api/emergencies/{inc_arv.id}/status/", {"status": IncidentStatus.IN_TRANSIT}, format="json")
        self.client.patch(f"/api/emergencies/{inc_arv.id}/status/", {"status": IncidentStatus.ARRIVED}, format="json")
        res_arv = self.client.patch(f"/api/emergencies/{inc_arv.id}/status/", {"status": IncidentStatus.CANCELLED}, format="json")
        self.assertEqual(res_arv.status_code, 200)
        self.assertEqual(res_arv.data["data"]["status"], IncidentStatus.CANCELLED)

    def test_status_03_invalid_forward_skips_rejected(self):
        """STATUS-03: Invalid forward jumps that skip required lifecycle stages are rejected with 400."""
        from apps.emergencies.services import create_emergency_incident

        inc = create_emergency_incident(self.driver1, self.hospital.id)
        self.client.force_authenticate(user=self.driver1)
        url = f"/api/emergencies/{inc.id}/status/"

        # Skip ASSIGNED: REPORTED -> IN_TRANSIT
        res1 = self.client.patch(url, {"status": IncidentStatus.IN_TRANSIT}, format="json")
        self.assertEqual(res1.status_code, 400)
        self.assertFalse(res1.data["success"])
        self.assertIn("Invalid status transition", str(res1.data["errors"]))

        # Skip to ARRIVED: REPORTED -> ARRIVED
        res2 = self.client.patch(url, {"status": IncidentStatus.ARRIVED}, format="json")
        self.assertEqual(res2.status_code, 400)
        self.assertFalse(res2.data["success"])

        # Skip to CLOSED: REPORTED -> CLOSED
        res3 = self.client.patch(url, {"status": IncidentStatus.CLOSED}, format="json")
        self.assertEqual(res3.status_code, 400)
        self.assertFalse(res3.data["success"])

    def test_status_04_backward_transitions_rejected(self):
        """STATUS-04: Backward transitions (e.g. ASSIGNED -> REPORTED) are rejected with 400."""
        from apps.emergencies.services import create_emergency_incident

        inc = create_emergency_incident(self.driver1, self.hospital.id)
        self.client.force_authenticate(user=self.driver1)
        url = f"/api/emergencies/{inc.id}/status/"

        # Progress to ASSIGNED
        self.client.patch(url, {"status": IncidentStatus.ASSIGNED}, format="json")

        # Try to regress: ASSIGNED -> REPORTED
        res_back = self.client.patch(url, {"status": IncidentStatus.REPORTED}, format="json")
        self.assertEqual(res_back.status_code, 400)
        self.assertFalse(res_back.data["success"])
        self.assertIn("Invalid status transition", str(res_back.data["errors"]))

    def test_status_05_same_status_transition_rejected(self):
        """STATUS-05: Transitioning to the exact same current status is rejected with 400."""
        from apps.emergencies.services import create_emergency_incident

        inc = create_emergency_incident(self.driver1, self.hospital.id)
        self.client.force_authenticate(user=self.driver1)
        url = f"/api/emergencies/{inc.id}/status/"

        # REPORTED -> REPORTED
        res = self.client.patch(url, {"status": IncidentStatus.REPORTED}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.data["success"])

    def test_status_06_terminal_states_cannot_transition(self):
        """STATUS-06: Incidents in terminal states (CLOSED or CANCELLED) cannot reopen or transition."""
        from apps.emergencies.services import create_emergency_incident

        self.client.force_authenticate(user=self.driver1)

        # 1. Closed incident
        inc_closed = create_emergency_incident(self.driver1, self.hospital.id)
        url_closed = f"/api/emergencies/{inc_closed.id}/status/"
        self.client.patch(url_closed, {"status": IncidentStatus.ASSIGNED}, format="json")
        _approve_incident_for_transit(inc_closed, self.hospital_staff, self.police_dispatcher)
        self.client.patch(url_closed, {"status": IncidentStatus.IN_TRANSIT}, format="json")
        self.client.patch(url_closed, {"status": IncidentStatus.ARRIVED}, format="json")
        self.client.patch(url_closed, {"status": IncidentStatus.CLOSED}, format="json")

        # Attempt reopen to REPORTED
        res_reopen = self.client.patch(url_closed, {"status": IncidentStatus.REPORTED}, format="json")
        self.assertEqual(res_reopen.status_code, 400)
        self.assertIn("terminal state", str(res_reopen.data["errors"]))

        # Attempt to re-close
        res_reclose = self.client.patch(url_closed, {"status": IncidentStatus.CLOSED}, format="json")
        self.assertEqual(res_reclose.status_code, 400)

        # 2. Cancelled incident
        inc_cancelled = create_emergency_incident(self.driver1, self.hospital.id)
        url_cancelled = f"/api/emergencies/{inc_cancelled.id}/status/"
        self.client.patch(url_cancelled, {"status": IncidentStatus.CANCELLED}, format="json")

        # Attempt reopen to IN_TRANSIT
        res_can_reopen = self.client.patch(url_cancelled, {"status": IncidentStatus.IN_TRANSIT}, format="json")
        self.assertEqual(res_can_reopen.status_code, 400)
        self.assertIn("terminal state", str(res_can_reopen.data["errors"]))

    def test_status_07_invalid_status_payload(self):
        """STATUS-07: Invalid status strings or missing status payload return 400."""
        from apps.emergencies.services import create_emergency_incident

        inc = create_emergency_incident(self.driver1, self.hospital.id)
        self.client.force_authenticate(user=self.driver1)
        url = f"/api/emergencies/{inc.id}/status/"

        # 1. Unrecognized choice
        res1 = self.client.patch(url, {"status": "FLYING_HOSPITAL"}, format="json")
        self.assertEqual(res1.status_code, 400)
        self.assertIn("status", res1.data["errors"])

        # 2. Empty payload
        res2 = self.client.patch(url, {}, format="json")
        self.assertEqual(res2.status_code, 400)
        self.assertIn("status", res2.data["errors"])

    def test_status_08_another_driver_incident_returns_404(self):
        """STATUS-08: A driver attempting to update another driver's incident receives 404."""
        from apps.emergencies.services import create_emergency_incident

        inc_driver2 = create_emergency_incident(self.driver2, self.hospital.id)

        # Driver 1 attempts to PATCH Driver 2's incident
        self.client.force_authenticate(user=self.driver1)
        url = f"/api/emergencies/{inc_driver2.id}/status/"
        response = self.client.patch(url, {"status": IncidentStatus.ASSIGNED}, format="json")
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data["success"])

    def test_status_09_unauthorized_roles_denied_with_403(self):
        """STATUS-09: Non-driver roles (Admin, Hospital Staff, Police) are denied with 403."""
        from apps.emergencies.services import create_emergency_incident

        inc = create_emergency_incident(self.driver1, self.hospital.id)
        url = f"/api/emergencies/{inc.id}/status/"
        payload = {"status": IncidentStatus.ASSIGNED}

        # 1. System Admin cannot PATCH status
        self.client.force_authenticate(user=self.admin_user)
        res_admin = self.client.patch(url, payload, format="json")
        self.assertEqual(res_admin.status_code, 403)
        self.assertFalse(res_admin.data["success"])

        # 2. Hospital Staff cannot PATCH status
        self.client.force_authenticate(user=self.hospital_staff)
        res_hosp = self.client.patch(url, payload, format="json")
        self.assertEqual(res_hosp.status_code, 403)

        # 3. Police Dispatcher cannot PATCH status
        self.client.force_authenticate(user=self.police_dispatcher)
        res_pol = self.client.patch(url, payload, format="json")
        self.assertEqual(res_pol.status_code, 403)

        # 4. Unverified Driver cannot PATCH status
        self.client.force_authenticate(user=self.unverified_driver)
        res_unver = self.client.patch(url, payload, format="json")
        self.assertEqual(res_unver.status_code, 403)

    def test_status_10_unauthenticated_request_returns_401(self):
        """STATUS-10: Anonymous/unauthenticated requests return 401 Unauthorized."""
        from apps.emergencies.services import create_emergency_incident

        inc = create_emergency_incident(self.driver1, self.hospital.id)
        url = f"/api/emergencies/{inc.id}/status/"

        self.client.force_authenticate(user=None)
        response = self.client.patch(url, {"status": IncidentStatus.ASSIGNED}, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.data["success"])

    def test_status_11_response_envelope_format(self):
        """STATUS-11: Response preserves standard SERTOS envelope and returns complete incident detail."""
        from apps.emergencies.services import create_emergency_incident

        inc = create_emergency_incident(self.driver1, self.hospital.id, description="Envelope verification")
        self.client.force_authenticate(user=self.driver1)
        url = f"/api/emergencies/{inc.id}/status/"

        response = self.client.patch(url, {"status": IncidentStatus.ASSIGNED}, format="json")
        self.assertEqual(response.status_code, 200)

        # Standard SERTOS envelope
        self.assertIn("success", response.data)
        self.assertTrue(response.data["success"])
        self.assertIn("message", response.data)
        self.assertEqual(response.data["message"], "Emergency incident status updated successfully.")
        self.assertIn("data", response.data)

        # Complete incident detail representation
        data = response.data["data"]
        self.assertEqual(data["id"], str(inc.id))
        self.assertEqual(data["incident_number"], inc.incident_number)
        self.assertEqual(data["status"], IncidentStatus.ASSIGNED)
        self.assertEqual(data["status_display"], "Assigned")
        self.assertEqual(data["reporting_driver"]["username"], "driver_alpha")
        self.assertEqual(data["ambulance"]["vehicle_number"], "KA-01-EQ-5001")
        self.assertEqual(data["hospital"]["hospital_code"], "HOSP-API-001")
        self.assertIsNotNone(data["assigned_at"])
        self.assertIsNone(data["in_transit_at"])

    def test_status_12_service_layer_direct_validation(self):
        """STATUS-12: Service layer update_emergency_status directly rejects unauthenticated or invalid users."""
        from apps.emergencies.services import create_emergency_incident, update_emergency_status
        from rest_framework import serializers

        inc = create_emergency_incident(self.driver1, self.hospital.id)

        # 1. Non-authenticated user
        with self.assertRaises(serializers.ValidationError) as ctx:
            update_emergency_status(inc, IncidentStatus.ASSIGNED, None)
        self.assertIn("Authentication required", str(ctx.exception))

        # 2. Non-driver role
        with self.assertRaises(serializers.ValidationError) as ctx:
            update_emergency_status(inc, IncidentStatus.ASSIGNED, self.hospital_staff)
        self.assertIn("Only verified ambulance drivers", str(ctx.exception))

        # 3. Wrong driver (Driver 2 attempting Driver 1's incident)
        with self.assertRaises(serializers.ValidationError) as ctx:
            update_emergency_status(inc, IncidentStatus.ASSIGNED, self.driver2)
        self.assertIn("Only the reporting driver", str(ctx.exception))


class HospitalStaffModelTest(TestCase):
    """Unit test suite for the HospitalStaff database model and association rules."""

    def setUp(self):
        self.hospital = Hospital.objects.create(
            name="St. Johns Medical Center",
            hospital_code="HOSP-STJ-01",
            address="Sarjapur Road, Bangalore",
        )
        self.second_hospital = Hospital.objects.create(
            name="Apollo Multispecialty",
            hospital_code="HOSP-APL-02",
            address="Bannerghatta Road, Bangalore",
        )
        self.hospital_staff_user = User.objects.create_user(
            username="nurse_priya",
            password="StrongPassword123!@#",
            role=UserRole.HOSPITAL_STAFF,
            is_active=True,
            is_verified=True,
        )
        self.second_staff_user = User.objects.create_user(
            username="dr_kulkarni",
            password="StrongPassword123!@#",
            role=UserRole.HOSPITAL_STAFF,
            is_active=True,
            is_verified=True,
        )
        self.driver_user = User.objects.create_user(
            username="driver_sanjay",
            password="StrongPassword123!@#",
            role=UserRole.AMBULANCE_DRIVER,
            is_active=True,
            is_verified=True,
        )
        self.inactive_staff_user = User.objects.create_user(
            username="nurse_inactive",
            password="StrongPassword123!@#",
            role=UserRole.HOSPITAL_STAFF,
            is_active=False,
            is_verified=True,
        )

    def test_hstaff_01_valid_affiliation_creation(self):
        """HSTAFF-01: Valid hospital staff affiliation creation with ManyToMany reverse access."""
        affiliation = HospitalStaff(
            hospital=self.hospital,
            user=self.hospital_staff_user,
            is_active=True,
        )
        affiliation.full_clean()
        affiliation.save()

        self.assertIsNotNone(affiliation.id)
        self.assertEqual(affiliation.hospital, self.hospital)
        self.assertEqual(affiliation.user, self.hospital_staff_user)
        self.assertTrue(affiliation.is_active)
        self.assertIn(self.hospital_staff_user, self.hospital.staff.all())
        self.assertIn(self.hospital, self.hospital_staff_user.associated_hospitals.all())

    def test_hstaff_02_non_hospital_staff_role_rejected(self):
        """HSTAFF-02: Assigning a user without HOSPITAL_STAFF role is rejected by model validation."""
        affiliation = HospitalStaff(
            hospital=self.hospital,
            user=self.driver_user,
        )
        with self.assertRaises(ValidationError) as ctx:
            affiliation.full_clean()
        self.assertIn("user", ctx.exception.message_dict)

    def test_hstaff_03_inactive_user_rejected(self):
        """HSTAFF-03: Assigning an inactive staff member is rejected by model validation."""
        affiliation = HospitalStaff(
            hospital=self.hospital,
            user=self.inactive_staff_user,
        )
        with self.assertRaises(ValidationError) as ctx:
            affiliation.full_clean()
        self.assertIn("user", ctx.exception.message_dict)

    def test_hstaff_04_duplicate_affiliation_rejected(self):
        """HSTAFF-04: Duplicate hospital-staff affiliation is rejected by unique constraint."""
        HospitalStaff.objects.create(
            hospital=self.hospital,
            user=self.hospital_staff_user,
        )

        duplicate = HospitalStaff(
            hospital=self.hospital,
            user=self.hospital_staff_user,
        )
        with self.assertRaises((ValidationError, IntegrityError)):
            duplicate.full_clean()
            duplicate.save()

    def test_hstaff_05_multiple_staff_and_multiple_hospitals(self):
        """HSTAFF-05: Supports multiple staff per hospital and multiple hospital affiliations per staff member."""
        # Hospital 1 has staff 1 and staff 2
        HospitalStaff.objects.create(hospital=self.hospital, user=self.hospital_staff_user)
        HospitalStaff.objects.create(hospital=self.hospital, user=self.second_staff_user)

        # Staff 1 is also affiliated with Hospital 2
        HospitalStaff.objects.create(hospital=self.second_hospital, user=self.hospital_staff_user)

        self.assertEqual(self.hospital.staff.count(), 2)
        self.assertEqual(self.hospital_staff_user.associated_hospitals.count(), 2)


class HospitalAndPoliceDashboardAPITest(TestCase):
    """Integration test suite for Hospital and Police Dashboard APIs."""

    def setUp(self):
        from rest_framework.test import APIClient
        self.client = APIClient()

        # 1. Hospitals
        self.hospital_a = Hospital.objects.create(
            name="City Hospital Central",
            hospital_code="HOSP-CTY-01",
            address="100 Central Road, Bangalore",
            latitude=Decimal("12.971598"),
            longitude=Decimal("77.594562"),
            is_active=True,
        )
        self.hospital_b = Hospital.objects.create(
            name="Metro Hospital East",
            hospital_code="HOSP-MTR-02",
            address="200 East Boulevard, Bangalore",
            latitude=Decimal("12.981598"),
            longitude=Decimal("77.604562"),
            is_active=True,
        )

        # 2. Operational Users
        self.staff_a = User.objects.create_user(
            username="staff_central",
            email="staff_central@sertos.local",
            password="Password123!",
            role=UserRole.HOSPITAL_STAFF,
            is_verified=True,
            is_active=True,
        )
        HospitalStaff.objects.create(hospital=self.hospital_a, user=self.staff_a, is_active=True)

        self.staff_b = User.objects.create_user(
            username="staff_east",
            email="staff_east@sertos.local",
            password="Password123!",
            role=UserRole.HOSPITAL_STAFF,
            is_verified=True,
            is_active=True,
        )
        HospitalStaff.objects.create(hospital=self.hospital_b, user=self.staff_b, is_active=True)

        self.staff_unaffiliated = User.objects.create_user(
            username="staff_unaffil",
            email="staff_unaffil@sertos.local",
            password="Password123!",
            role=UserRole.HOSPITAL_STAFF,
            is_verified=True,
            is_active=True,
        )

        self.staff_unverified = User.objects.create_user(
            username="staff_unver",
            email="staff_unver@sertos.local",
            password="Password123!",
            role=UserRole.HOSPITAL_STAFF,
            is_verified=False,
            is_active=True,
        )

        self.police_user = User.objects.create_user(
            username="traffic_officer",
            email="traffic_officer@sertos.local",
            password="Password123!",
            role=UserRole.POLICE_DISPATCHER,
            is_verified=True,
            is_active=True,
        )

        self.driver_user = User.objects.create_user(
            username="driver_dash",
            email="driver_dash@sertos.local",
            password="Password123!",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=True,
            is_active=True,
        )

        self.admin_user = User.objects.create_superuser(
            username="dash_admin",
            email="dash_admin@sertos.local",
            password="Password123!",
            role=UserRole.ADMIN,
            is_verified=True,
            is_active=True,
        )

        # 3. Vehicle
        self.ambulance = Ambulance.objects.create(
            vehicle_number="KA-01-EQ-9001",
            vehicle_type="Advanced Life Support",
            assigned_driver=self.driver_user,
            is_available=True,
            is_active=True,
        )

        # 4. Incidents & Patients
        # Incident A1 (Hospital A, IN_TRANSIT, CRITICAL)
        self.inc_a1 = EmergencyIncident.objects.create(
            incident_number="INC-20261114-DASH01",
            reporting_driver=self.driver_user,
            ambulance=self.ambulance,
            hospital=self.hospital_a,
            severity=IncidentSeverity.CRITICAL,
            status=IncidentStatus.IN_TRANSIT,
            description="Major vehicular crash",
        )
        self.patient_a1 = Patient.objects.create(
            incident=self.inc_a1,
            name="Arun Kumar",
            age=35,
            gender=Gender.MALE,
            blood_group=BloodGroup.O_POSITIVE,
            medical_notes="Severe cervical spine trauma, neuro vitals guarded.",
        )

        # Incident A2 (Hospital A, ARRIVED, LOW)
        self.inc_a2 = EmergencyIncident.objects.create(
            incident_number="INC-20261114-DASH02",
            reporting_driver=self.driver_user,
            ambulance=self.ambulance,
            hospital=self.hospital_a,
            severity=IncidentSeverity.LOW,
            status=IncidentStatus.ARRIVED,
            description="Minor ankle sprain",
        )

        # Incident B1 (Hospital B, IN_TRANSIT, HIGH)
        self.inc_b1 = EmergencyIncident.objects.create(
            incident_number="INC-20261114-DASH03",
            reporting_driver=self.driver_user,
            ambulance=self.ambulance,
            hospital=self.hospital_b,
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.IN_TRANSIT,
            description="Severe cardiac arrhythmia",
        )

    def test_dash_01_hospital_staff_lists_only_own_hospital_incidents(self):
        """DASH-01: Hospital staff lists only incidents assigned to their associated hospital facility."""
        self.client.force_authenticate(user=self.staff_a)
        response = self.client.get("/api/hospital/incidents/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        data = response.data["data"]
        self.assertEqual(len(data), 2)

        returned_ids = {item["id"] for item in data}
        self.assertIn(str(self.inc_a1.id), returned_ids)
        self.assertIn(str(self.inc_a2.id), returned_ids)
        self.assertNotIn(str(self.inc_b1.id), returned_ids)

        # Confirm useful fields
        first = data[0]
        self.assertIn("incident_number", first)
        self.assertIn("severity", first)
        self.assertIn("status", first)
        self.assertIn("ambulance_vehicle_number", first)
        self.assertIn("patient_count", first)

    def test_dash_02_hospital_staff_cannot_retrieve_another_hospital_incident(self):
        """DASH-02: Hospital staff querying another hospital's incident receives 404 Not Found."""
        self.client.force_authenticate(user=self.staff_a)
        # Attempt to inspect Incident B1 (destined for Hospital B)
        response = self.client.get(f"/api/hospital/incidents/{self.inc_b1.id}/")

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data["success"])

    def test_dash_03_hospital_staff_detail_includes_patient_clinical_triage_notes(self):
        """DASH-03: Hospital staff detail view returns full patient clinical triage info including medical_notes."""
        self.client.force_authenticate(user=self.staff_a)
        response = self.client.get(f"/api/hospital/incidents/{self.inc_a1.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        data = response.data["data"]
        self.assertEqual(data["id"], str(self.inc_a1.id))
        self.assertEqual(len(data["patients"]), 1)
        patient_data = data["patients"][0]
        self.assertEqual(patient_data["name"], "Arun Kumar")
        self.assertEqual(patient_data["medical_notes"], "Severe cervical spine trauma, neuro vitals guarded.")

    def test_dash_04_hospital_staff_status_and_severity_filters(self):
        """DASH-04: Optional status and severity query parameter filters work on hospital incidents list."""
        self.client.force_authenticate(user=self.staff_a)

        # Filter by status=IN_TRANSIT -> 1 match (inc_a1)
        res_stat = self.client.get("/api/hospital/incidents/?status=IN_TRANSIT")
        self.assertEqual(res_stat.status_code, 200)
        self.assertEqual(len(res_stat.data["data"]), 1)
        self.assertEqual(res_stat.data["data"][0]["id"], str(self.inc_a1.id))

        # Filter by severity=LOW -> 1 match (inc_a2)
        res_sev = self.client.get("/api/hospital/incidents/?severity=LOW")
        self.assertEqual(res_sev.status_code, 200)
        self.assertEqual(len(res_sev.data["data"]), 1)
        self.assertEqual(res_sev.data["data"][0]["id"], str(self.inc_a2.id))

        # Filter by status=IN_TRANSIT and severity=LOW -> 0 matches
        res_both = self.client.get("/api/hospital/incidents/?status=IN_TRANSIT&severity=LOW")
        self.assertEqual(res_both.status_code, 200)
        self.assertEqual(len(res_both.data["data"]), 0)

    def test_dash_05_police_dispatcher_lists_incidents_across_all_hospitals(self):
        """DASH-05: Police dispatcher lists incidents across all hospitals for city-wide coordination."""
        self.client.force_authenticate(user=self.police_user)
        response = self.client.get("/api/police/incidents/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        data = response.data["data"]
        self.assertEqual(len(data), 3)

        returned_ids = {item["id"] for item in data}
        self.assertIn(str(self.inc_a1.id), returned_ids)
        self.assertIn(str(self.inc_a2.id), returned_ids)
        self.assertIn(str(self.inc_b1.id), returned_ids)

        # Confirm hospital GPS coordinates are included
        first = data[0]
        self.assertIn("hospital", first)
        self.assertIn("latitude", first["hospital"])
        self.assertIn("longitude", first["hospital"])

    def test_dash_06_police_dispatcher_detail_excludes_patient_medical_notes(self):
        """DASH-06: Police detail endpoint excludes sensitive patient medical notes for privacy and regulatory compliance."""
        self.client.force_authenticate(user=self.police_user)
        response = self.client.get(f"/api/police/incidents/{self.inc_a1.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        data = response.data["data"]
        self.assertEqual(data["id"], str(self.inc_a1.id))

        # Ensure patients are serialized but medical_notes is completely omitted
        self.assertEqual(len(data["patients"]), 1)
        patient_data = data["patients"][0]
        self.assertEqual(patient_data["name"], "Arun Kumar")
        self.assertNotIn("medical_notes", patient_data)
        self.assertNotIn("Severe cervical spine trauma", str(response.data))

    def test_dash_07_police_dispatcher_status_and_severity_filters(self):
        """DASH-07: Optional status and severity filters work on police incidents list."""
        self.client.force_authenticate(user=self.police_user)

        # Filter by status=IN_TRANSIT -> 2 matches (inc_a1, inc_b1)
        res_stat = self.client.get("/api/police/incidents/?status=IN_TRANSIT")
        self.assertEqual(res_stat.status_code, 200)
        self.assertEqual(len(res_stat.data["data"]), 2)

        # Filter by severity=CRITICAL -> 1 match (inc_a1)
        res_sev = self.client.get("/api/police/incidents/?severity=CRITICAL")
        self.assertEqual(res_sev.status_code, 200)
        self.assertEqual(len(res_sev.data["data"]), 1)
        self.assertEqual(res_sev.data["data"][0]["id"], str(self.inc_a1.id))

    def test_dash_08_cross_role_and_unauthorized_dashboard_access_denied(self):
        """DASH-08: Cross-role, driver, admin, unverified, and anonymous access to dashboards is rejected."""
        # 1. Hospital staff cannot access police endpoints (403)
        self.client.force_authenticate(user=self.staff_a)
        res1 = self.client.get("/api/police/incidents/")
        self.assertEqual(res1.status_code, 403)

        # 2. Police dispatcher cannot access hospital endpoints (403)
        self.client.force_authenticate(user=self.police_user)
        res2 = self.client.get("/api/hospital/incidents/")
        self.assertEqual(res2.status_code, 403)

        # 3. Ambulance driver cannot access hospital or police dashboards (403)
        self.client.force_authenticate(user=self.driver_user)
        res3 = self.client.get("/api/hospital/incidents/")
        self.assertEqual(res3.status_code, 403)
        res4 = self.client.get("/api/police/incidents/")
        self.assertEqual(res4.status_code, 403)

        # 4. Admin without role follows explicit policy (403)
        self.client.force_authenticate(user=self.admin_user)
        res5 = self.client.get("/api/hospital/incidents/")
        self.assertEqual(res5.status_code, 403)
        res6 = self.client.get("/api/police/incidents/")
        self.assertEqual(res6.status_code, 403)

        # 5. Anonymous user receives 401
        self.client.force_authenticate(user=None)
        res7 = self.client.get("/api/hospital/incidents/")
        self.assertEqual(res7.status_code, 401)
        res8 = self.client.get("/api/police/incidents/")
        self.assertEqual(res8.status_code, 401)

        # 6. Unverified hospital staff receives 403
        self.client.force_authenticate(user=self.staff_unverified)
        res9 = self.client.get("/api/hospital/incidents/")
        self.assertEqual(res9.status_code, 403)

    def test_dash_09_dashboard_endpoints_are_strictly_read_only(self):
        """DASH-09: Dashboard endpoints reject mutating POST/PATCH/DELETE methods with 403."""
        self.client.force_authenticate(user=self.staff_a)
        res_post = self.client.post("/api/hospital/incidents/", {"status": "ARRIVED"}, format="json")
        self.assertEqual(res_post.status_code, 403)

        res_patch = self.client.patch(f"/api/hospital/incidents/{self.inc_a1.id}/", {"status": "CLOSED"}, format="json")
        self.assertEqual(res_patch.status_code, 403)

        self.client.force_authenticate(user=self.police_user)
        res_pol_post = self.client.post("/api/police/incidents/", {"status": "ARRIVED"}, format="json")
        self.assertEqual(res_pol_post.status_code, 403)

    def test_dash_10_staff_with_no_hospital_affiliation_sees_empty_list(self):
        """DASH-10: Hospital staff with no active hospital affiliation sees an empty incident feed."""
        self.client.force_authenticate(user=self.staff_unaffiliated)
        response = self.client.get("/api/hospital/incidents/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]), 0)

        # And 404 when attempting to view any specific incident
        res_det = self.client.get(f"/api/hospital/incidents/{self.inc_a1.id}/")
        self.assertEqual(res_det.status_code, 404)

    def test_dash_11_dashboard_url_reversals(self):
        """DASH-11: URL reversal and resolution for hospital and police dashboard routes."""
        from django.urls import resolve, reverse
        import uuid

        hosp_list_url = reverse("hospital:incident_list")
        self.assertEqual(hosp_list_url, "/api/hospital/incidents/")
        self.assertEqual(resolve("/api/hospital/incidents/").url_name, "incident_list")

        fake_id = uuid.uuid4()
        hosp_det_url = reverse("hospital:incident_detail", kwargs={"pk": fake_id})
        self.assertEqual(hosp_det_url, f"/api/hospital/incidents/{fake_id}/")
        self.assertEqual(resolve(f"/api/hospital/incidents/{fake_id}/").url_name, "incident_detail")

        pol_list_url = reverse("police:incident_list")
        self.assertEqual(pol_list_url, "/api/police/incidents/")
        self.assertEqual(resolve("/api/police/incidents/").url_name, "incident_list")

        pol_det_url = reverse("police:incident_detail", kwargs={"pk": fake_id})
        self.assertEqual(pol_det_url, f"/api/police/incidents/{fake_id}/")
        self.assertEqual(resolve(f"/api/police/incidents/{fake_id}/").url_name, "incident_detail")


class AmbulanceLocationModelTest(TestCase):
    """Unit tests for the AmbulanceLocation GPS model."""

    def setUp(self):
        self.driver = User.objects.create_user(
            username="driver_gps_model",
            email="driver.gps@sertos.local",
            password="SecurePassword123!",
            role=UserRole.AMBULANCE_DRIVER,
            first_name="Ramesh",
            last_name="Kumar",
            is_active=True,
            is_verified=True,
        )
        self.hospital = Hospital.objects.create(
            name="GPS Test Hospital",
            hospital_code="HOSP-GPS-01",
            address="100 Hospital Way",
            latitude=Decimal("12.971598"),
            longitude=Decimal("77.594562"),
        )
        self.ambulance = Ambulance.objects.create(
            vehicle_number="KA-01-GPS-1001",
            assigned_driver=self.driver,
            is_active=True,
        )
        self.other_ambulance = Ambulance.objects.create(
            vehicle_number="KA-01-GPS-9999",
            is_active=True,
        )
        self.incident = EmergencyIncident.objects.create(
            incident_number="INC-20261114-GPS01",
            reporting_driver=self.driver,
            ambulance=self.ambulance,
            hospital=self.hospital,
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.IN_TRANSIT,
            description="Emergency transport in progress.",
        )

    def test_loc_01_valid_location_creation(self):
        """LOC-01: Valid ambulance location record creation."""
        loc = AmbulanceLocation(
            ambulance=self.ambulance,
            incident=self.incident,
            latitude=Decimal("12.972000"),
            longitude=Decimal("77.595000"),
            accuracy=4.5,
        )
        loc.full_clean()
        loc.save()

        self.assertIsNotNone(loc.id)
        self.assertIsNotNone(loc.server_received_at)
        self.assertEqual(loc.ambulance, self.ambulance)
        self.assertEqual(loc.incident, self.incident)
        self.assertIn("KA-01-GPS-1001", str(loc))
        self.assertIn("12.972000", str(loc))

    def test_loc_02_latitude_range_validation(self):
        """LOC-02: Latitude outside [-90, 90] is rejected."""
        loc_high = AmbulanceLocation(
            ambulance=self.ambulance,
            incident=self.incident,
            latitude=Decimal("90.000001"),
            longitude=Decimal("77.595000"),
        )
        with self.assertRaises(ValidationError) as ctx:
            loc_high.full_clean()
        self.assertIn("latitude", ctx.exception.message_dict)

        loc_low = AmbulanceLocation(
            ambulance=self.ambulance,
            incident=self.incident,
            latitude=Decimal("-90.000001"),
            longitude=Decimal("77.595000"),
        )
        with self.assertRaises(ValidationError) as ctx:
            loc_low.full_clean()
        self.assertIn("latitude", ctx.exception.message_dict)

    def test_loc_03_longitude_range_validation(self):
        """LOC-03: Longitude outside [-180, 180] is rejected."""
        loc_high = AmbulanceLocation(
            ambulance=self.ambulance,
            incident=self.incident,
            latitude=Decimal("12.972000"),
            longitude=Decimal("180.000001"),
        )
        with self.assertRaises(ValidationError) as ctx:
            loc_high.full_clean()
        self.assertIn("longitude", ctx.exception.message_dict)

        loc_low = AmbulanceLocation(
            ambulance=self.ambulance,
            incident=self.incident,
            latitude=Decimal("12.972000"),
            longitude=Decimal("-180.000001"),
        )
        with self.assertRaises(ValidationError) as ctx:
            loc_low.full_clean()
        self.assertIn("longitude", ctx.exception.message_dict)

    def test_loc_04_accuracy_validation(self):
        """LOC-04: Accuracy radius must be non-negative or None."""
        loc_neg = AmbulanceLocation(
            ambulance=self.ambulance,
            incident=self.incident,
            latitude=Decimal("12.972000"),
            longitude=Decimal("77.595000"),
            accuracy=-1.0,
        )
        with self.assertRaises(ValidationError) as ctx:
            loc_neg.full_clean()
        self.assertIn("accuracy", ctx.exception.message_dict)

        loc_zero = AmbulanceLocation(
            ambulance=self.ambulance,
            incident=self.incident,
            latitude=Decimal("12.972000"),
            longitude=Decimal("77.595000"),
            accuracy=0.0,
        )
        loc_zero.full_clean()  # Must not raise

    def test_loc_05_ambulance_mismatch_validation(self):
        """LOC-05: Location cannot reference an ambulance different from the incident's assigned vehicle."""
        loc_mismatch = AmbulanceLocation(
            ambulance=self.other_ambulance,
            incident=self.incident,
            latitude=Decimal("12.972000"),
            longitude=Decimal("77.595000"),
        )
        with self.assertRaises(ValidationError) as ctx:
            loc_mismatch.full_clean()
        self.assertIn("ambulance", ctx.exception.message_dict)

    def test_loc_06_default_ordering_newest_first(self):
        """LOC-06: Ambulance locations default ordering is newest server_received_at first."""
        loc1 = AmbulanceLocation.objects.create(
            ambulance=self.ambulance,
            incident=self.incident,
            latitude=Decimal("12.972001"),
            longitude=Decimal("77.595001"),
        )
        AmbulanceLocation.objects.filter(pk=loc1.pk).update(
            server_received_at=timezone.now()
        )
        loc2 = AmbulanceLocation.objects.create(
            ambulance=self.ambulance,
            incident=self.incident,
            latitude=Decimal("12.972002"),
            longitude=Decimal("77.595002"),
        )
        AmbulanceLocation.objects.filter(pk=loc2.pk).update(
            server_received_at=timezone.now() + timedelta(seconds=1)
        )
        locs = list(self.incident.locations.all())
        self.assertEqual(locs[0].id, loc2.id)
        self.assertEqual(locs[1].id, loc1.id)


class AmbulanceLocationServiceTest(TestCase):
    """Unit tests for the record_ambulance_location domain service."""

    def setUp(self):
        self.driver = User.objects.create_user(
            username="driver_gps_srv",
            email="driver.srv@sertos.local",
            password="SecurePassword123!",
            role=UserRole.AMBULANCE_DRIVER,
            first_name="Kiran",
            last_name="Rao",
            is_active=True,
            is_verified=True,
        )
        self.other_driver = User.objects.create_user(
            username="other_driver_gps_srv",
            email="other.driver@sertos.local",
            password="SecurePassword123!",
            role=UserRole.AMBULANCE_DRIVER,
            first_name="Anil",
            last_name="Verma",
            is_active=True,
            is_verified=True,
        )
        self.hospital = Hospital.objects.create(
            name="Service Test Hospital",
            hospital_code="HOSP-SRV-01",
            address="200 Service Rd",
        )
        self.ambulance = Ambulance.objects.create(
            vehicle_number="KA-01-SRV-2001",
            assigned_driver=self.driver,
            is_active=True,
        )
        self.incident_active = EmergencyIncident.objects.create(
            incident_number="INC-20261114-SRV01",
            reporting_driver=self.driver,
            ambulance=self.ambulance,
            hospital=self.hospital,
            severity=IncidentSeverity.MEDIUM,
            status=IncidentStatus.IN_TRANSIT,
        )
        self.incident_closed = EmergencyIncident.objects.create(
            incident_number="INC-20261114-SRV02",
            reporting_driver=self.driver,
            ambulance=self.ambulance,
            hospital=self.hospital,
            severity=IncidentSeverity.MEDIUM,
            status=IncidentStatus.CLOSED,
        )
        self.incident_cancelled = EmergencyIncident.objects.create(
            incident_number="INC-20261114-SRV03",
            reporting_driver=self.driver,
            ambulance=self.ambulance,
            hospital=self.hospital,
            severity=IncidentSeverity.MEDIUM,
            status=IncidentStatus.CANCELLED,
        )

    def test_service_01_record_location_success(self):
        """SRV-01: Valid GPS record successfully persisted by assigned driver."""
        loc = record_ambulance_location(
            incident=self.incident_active,
            latitude=Decimal("12.973000"),
            longitude=Decimal("77.596000"),
            accuracy=3.5,
            user=self.driver,
        )
        self.assertIsNotNone(loc.id)
        self.assertEqual(loc.ambulance, self.ambulance)
        self.assertEqual(loc.latitude, Decimal("12.973000"))
        self.assertEqual(loc.longitude, Decimal("77.596000"))
        self.assertEqual(loc.accuracy, 3.5)

    def test_service_02_record_location_unauthorized_user(self):
        """SRV-02: Recording location by a user other than the assigned driver fails."""
        from rest_framework.exceptions import ValidationError as DRFValidationError
        with self.assertRaises(DRFValidationError) as ctx:
            record_ambulance_location(
                incident=self.incident_active,
                latitude=Decimal("12.973000"),
                longitude=Decimal("77.596000"),
                user=self.other_driver,
            )
        self.assertIn("Only the reporting driver can update GPS coordinates", str(ctx.exception))

    def test_service_03_record_location_closed_incident(self):
        """SRV-03: Recording location for a CLOSED incident fails."""
        from rest_framework.exceptions import ValidationError as DRFValidationError
        with self.assertRaises(DRFValidationError) as ctx:
            record_ambulance_location(
                incident=self.incident_closed,
                latitude=Decimal("12.973000"),
                longitude=Decimal("77.596000"),
                user=self.driver,
            )
        self.assertIn("Cannot update location for incident in terminal state 'CLOSED'", str(ctx.exception))

    def test_service_04_record_location_cancelled_incident(self):
        """SRV-04: Recording location for a CANCELLED incident fails."""
        from rest_framework.exceptions import ValidationError as DRFValidationError
        with self.assertRaises(DRFValidationError) as ctx:
            record_ambulance_location(
                incident=self.incident_cancelled,
                latitude=Decimal("12.973000"),
                longitude=Decimal("77.596000"),
                user=self.driver,
            )
        self.assertIn("Cannot update location for incident in terminal state 'CANCELLED'", str(ctx.exception))


class AmbulanceLocationAPITest(TestCase):
    """Comprehensive API test suite for Ambulance GPS Location endpoints."""

    def setUp(self):
        from rest_framework.test import APIClient
        self.client = APIClient()

        # 1. Primary driver & ambulance
        self.driver_1 = User.objects.create_user(
            username="driver_gps_one",
            email="driver.one@sertos.local",
            password="SecurePassword123!",
            role=UserRole.AMBULANCE_DRIVER,
            first_name="Driver",
            last_name="One",
            is_active=True,
            is_verified=True,
        )
        self.amb_1 = Ambulance.objects.create(
            vehicle_number="KA-01-AMB-1001",
            assigned_driver=self.driver_1,
            is_active=True,
        )

        # 2. Secondary driver & ambulance
        self.driver_2 = User.objects.create_user(
            username="driver_gps_two",
            email="driver.two@sertos.local",
            password="SecurePassword123!",
            role=UserRole.AMBULANCE_DRIVER,
            first_name="Driver",
            last_name="Two",
            is_active=True,
            is_verified=True,
        )
        self.amb_2 = Ambulance.objects.create(
            vehicle_number="KA-01-AMB-2002",
            assigned_driver=self.driver_2,
            is_active=True,
        )

        # 3. Hospitals & Staff
        self.hosp_a = Hospital.objects.create(
            name="City Hospital Alpha",
            hospital_code="HOSP-ALPHA",
            address="1 Alpha Way",
        )
        self.staff_a = User.objects.create_user(
            username="staff_gps_a",
            email="staff.a@sertos.local",
            password="SecurePassword123!",
            role=UserRole.HOSPITAL_STAFF,
            first_name="Staff",
            last_name="Alpha",
            is_active=True,
            is_verified=True,
        )
        HospitalStaff.objects.create(
            user=self.staff_a,
            hospital=self.hosp_a,
            is_active=True,
        )

        self.hosp_b = Hospital.objects.create(
            name="City Hospital Beta",
            hospital_code="HOSP-BETA",
            address="2 Beta Way",
        )
        self.staff_b = User.objects.create_user(
            username="staff_gps_b",
            email="staff.b@sertos.local",
            password="SecurePassword123!",
            role=UserRole.HOSPITAL_STAFF,
            first_name="Staff",
            last_name="Beta",
            is_active=True,
            is_verified=True,
        )
        HospitalStaff.objects.create(
            user=self.staff_b,
            hospital=self.hosp_b,
            is_active=True,
        )

        # 4. Police, Admin, and Unverified Driver
        self.police_user = User.objects.create_user(
            username="police_gps_user",
            email="police.traffic@sertos.local",
            password="SecurePassword123!",
            role=UserRole.POLICE_DISPATCHER,
            first_name="Traffic",
            last_name="Police",
            is_active=True,
            is_verified=True,
        )
        self.admin_user = User.objects.create_user(
            username="admin_gps_user",
            email="admin.gps@sertos.local",
            password="SecurePassword123!",
            role=UserRole.ADMIN,
            first_name="System",
            last_name="Admin",
            is_active=True,
            is_verified=True,
        )
        self.unverified_driver = User.objects.create_user(
            username="unverified_gps_driver",
            email="unverified.driver@sertos.local",
            password="SecurePassword123!",
            role=UserRole.AMBULANCE_DRIVER,
            first_name="Unverified",
            last_name="Driver",
            is_active=True,
            is_verified=False,
        )

        # 5. Incidents
        self.incident_active = EmergencyIncident.objects.create(
            incident_number="INC-20261114-GPSAPI1",
            reporting_driver=self.driver_1,
            ambulance=self.amb_1,
            hospital=self.hosp_a,
            severity=IncidentSeverity.CRITICAL,
            status=IncidentStatus.IN_TRANSIT,
            description="Major crash, MG Road, Bangalore",
        )
        self.patient = Patient.objects.create(
            incident=self.incident_active,
            name="Rahul Sharma",
            age=34,
            gender=Gender.MALE,
            blood_group=BloodGroup.O_POSITIVE,
            medical_notes="Confidential: Patient has severe head trauma and is HIV-positive.",
        )

        self.incident_closed = EmergencyIncident.objects.create(
            incident_number="INC-20261114-GPSAPI2",
            reporting_driver=self.driver_1,
            ambulance=self.amb_1,
            hospital=self.hosp_a,
            severity=IncidentSeverity.LOW,
            status=IncidentStatus.CLOSED,
        )

    def test_gps_01_driver_post_location_success(self):
        """GPS-01: Reporting driver successfully posts location ping (201 Created)."""
        self.client.force_authenticate(user=self.driver_1)
        url = f"/api/emergencies/{self.incident_active.id}/location/"
        payload = {
            "latitude": 12.972500,
            "longitude": 77.595500,
            "accuracy": 4.8,
            "recorded_at": "2026-11-14T10:00:00Z",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["message"], "Ambulance GPS location updated successfully.")

        data = response.data["data"]
        self.assertIsNotNone(data["id"])
        self.assertEqual(data["incident_id"], str(self.incident_active.id))
        self.assertEqual(data["ambulance_id"], str(self.amb_1.id))
        self.assertEqual(data["ambulance_vehicle_number"], "KA-01-AMB-1001")
        self.assertEqual(Decimal(str(data["latitude"])), Decimal("12.972500"))
        self.assertEqual(Decimal(str(data["longitude"])), Decimal("77.595500"))
        self.assertEqual(data["accuracy"], 4.8)
        self.assertIsNotNone(data["server_received_at"])

        # Crucial security check: Ensure patient medical notes are NEVER in location response
        self.assertNotIn("medical_notes", str(response.data))
        self.assertNotIn("HIV-positive", str(response.data))
        self.assertNotIn("Rahul Sharma", str(response.data))

    def test_gps_02_post_location_invalid_payloads_rejected(self):
        """GPS-02: Missing or out-of-range coordinates are rejected with 400 Bad Request."""
        self.client.force_authenticate(user=self.driver_1)
        url = f"/api/emergencies/{self.incident_active.id}/location/"

        # 1. Missing latitude
        res1 = self.client.post(url, {"longitude": 77.595500}, format="json")
        self.assertEqual(res1.status_code, 400)
        self.assertIn("latitude", str(res1.data))

        # 2. Missing longitude
        res2 = self.client.post(url, {"latitude": 12.972500}, format="json")
        self.assertEqual(res2.status_code, 400)
        self.assertIn("longitude", str(res2.data))

        # 3. Latitude out of range (> 90)
        res3 = self.client.post(url, {"latitude": 90.5, "longitude": 77.595500}, format="json")
        self.assertEqual(res3.status_code, 400)
        self.assertIn("latitude", str(res3.data))

        # 4. Longitude out of range (< -180)
        res4 = self.client.post(url, {"latitude": 12.972500, "longitude": -185.0}, format="json")
        self.assertEqual(res4.status_code, 400)
        self.assertIn("longitude", str(res4.data))

        # 5. Negative accuracy radius
        res5 = self.client.post(url, {"latitude": 12.972500, "longitude": 77.595500, "accuracy": -2.0}, format="json")
        self.assertEqual(res5.status_code, 400)
        self.assertIn("accuracy", str(res5.data))

    def test_gps_03_post_location_on_closed_incident_rejected(self):
        """GPS-03: Submitting location updates for a CLOSED incident returns 400."""
        self.client.force_authenticate(user=self.driver_1)
        url = f"/api/emergencies/{self.incident_closed.id}/location/"
        payload = {"latitude": 12.972500, "longitude": 77.595500}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Cannot update location for incident in terminal state", str(response.data))

    def test_gps_04_cross_driver_post_location_rejected(self):
        """GPS-04: Another driver cannot post GPS location for an incident they do not report (404)."""
        self.client.force_authenticate(user=self.driver_2)
        url = f"/api/emergencies/{self.incident_active.id}/location/"
        payload = {"latitude": 12.972500, "longitude": 77.595500}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, 404)

    def test_gps_05_non_driver_roles_cannot_post_location(self):
        """GPS-05: Hospital staff and police cannot POST GPS locations (403 Forbidden)."""
        url = f"/api/emergencies/{self.incident_active.id}/location/"
        payload = {"latitude": 12.972500, "longitude": 77.595500}

        # Hospital staff
        self.client.force_authenticate(user=self.staff_a)
        res1 = self.client.post(url, payload, format="json")
        self.assertEqual(res1.status_code, 403)

        # Police dispatcher
        self.client.force_authenticate(user=self.police_user)
        res2 = self.client.post(url, payload, format="json")
        self.assertEqual(res2.status_code, 403)

    def test_gps_06_unauthenticated_and_unverified_post_rejected(self):
        """GPS-06: Unauthenticated (401) and unverified drivers (403) cannot POST location."""
        url = f"/api/emergencies/{self.incident_active.id}/location/"
        payload = {"latitude": 12.972500, "longitude": 77.595500}

        # Anonymous
        self.client.force_authenticate(user=None)
        res_anon = self.client.post(url, payload, format="json")
        self.assertEqual(res_anon.status_code, 401)

        # Unverified driver
        self.client.force_authenticate(user=self.unverified_driver)
        res_unver = self.client.post(url, payload, format="json")
        self.assertEqual(res_unver.status_code, 403)

    def test_gps_07_get_latest_location_empty_state(self):
        """GPS-07: When no location has been reported yet, GET returns 200 with empty data object."""
        self.client.force_authenticate(user=self.driver_1)
        url = f"/api/emergencies/{self.incident_active.id}/location/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"], {})
        self.assertEqual(response.data["message"], "No GPS location recorded for this incident yet.")

    def test_gps_08_get_latest_location_authorized_roles(self):
        """GPS-08: Reporting driver, assigned hospital staff, police, and admin can get latest location."""
        loc1 = AmbulanceLocation.objects.create(
            ambulance=self.amb_1,
            incident=self.incident_active,
            latitude=Decimal("12.972000"),
            longitude=Decimal("77.595000"),
            accuracy=5.0,
        )
        loc2 = AmbulanceLocation.objects.create(
            ambulance=self.amb_1,
            incident=self.incident_active,
            latitude=Decimal("12.974000"),
            longitude=Decimal("77.597000"),
            accuracy=3.0,
        )
        AmbulanceLocation.objects.filter(pk=loc2.pk).update(
            server_received_at=loc1.server_received_at + timedelta(seconds=1)
        )

        url = f"/api/emergencies/{self.incident_active.id}/location/"

        for user, role_desc in [
            (self.driver_1, "Reporting Driver"),
            (self.staff_a, "Assigned Hospital Staff"),
            (self.police_user, "Police Dispatcher"),
            (self.admin_user, "System Admin"),
        ]:
            with self.subTest(role=role_desc):
                self.client.force_authenticate(user=user)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.data["success"])
                self.assertEqual(response.data["data"]["id"], str(loc2.id))
                self.assertEqual(Decimal(str(response.data["data"]["latitude"])), Decimal("12.974000"))
                # Verify no patient notes leak
                self.assertNotIn("medical_notes", str(response.data))
                self.assertNotIn("HIV-positive", str(response.data))

    def test_gps_09_get_latest_location_cross_tenancy_isolation(self):
        """GPS-09: Unassigned driver and staff from another hospital receive 404."""
        AmbulanceLocation.objects.create(
            ambulance=self.amb_1,
            incident=self.incident_active,
            latitude=Decimal("12.972000"),
            longitude=Decimal("77.595000"),
        )
        url = f"/api/emergencies/{self.incident_active.id}/location/"

        # Another driver
        self.client.force_authenticate(user=self.driver_2)
        res_drv = self.client.get(url)
        self.assertEqual(res_drv.status_code, 404)

        # Staff of Hospital B
        self.client.force_authenticate(user=self.staff_b)
        res_stf = self.client.get(url)
        self.assertEqual(res_stf.status_code, 404)

    def test_gps_10_get_location_history_and_limit(self):
        """GPS-10: Location history returns ordered breadcrumbs and respects ?limit= parameter."""
        # Create 5 pings
        for i in range(5):
            ping = AmbulanceLocation.objects.create(
                ambulance=self.amb_1,
                incident=self.incident_active,
                latitude=Decimal(f"12.97{i:04d}"),
                longitude=Decimal(f"77.59{i:04d}"),
                accuracy=float(i + 1),
            )
            AmbulanceLocation.objects.filter(pk=ping.pk).update(
                server_received_at=timezone.now() + timedelta(seconds=i)
            )

        self.client.force_authenticate(user=self.staff_a)
        url = f"/api/emergencies/{self.incident_active.id}/locations/"

        # 1. Default limit (returns all 5)
        res_all = self.client.get(url)
        self.assertEqual(res_all.status_code, 200)
        self.assertEqual(len(res_all.data["data"]), 5)
        self.assertEqual(Decimal(str(res_all.data["data"][0]["latitude"])), Decimal("12.970004"))

        # 2. Limit = 2
        res_lim = self.client.get(f"{url}?limit=2")
        self.assertEqual(res_lim.status_code, 200)
        self.assertEqual(len(res_lim.data["data"]), 2)
        self.assertEqual(Decimal(str(res_lim.data["data"][0]["latitude"])), Decimal("12.970004"))

        # 3. Invalid limit defaults gracefully to 50
        res_inv = self.client.get(f"{url}?limit=abc")
        self.assertEqual(res_inv.status_code, 200)
        self.assertEqual(len(res_inv.data["data"]), 5)

        # 4. Isolation: Hospital B staff cannot access history (404)
        self.client.force_authenticate(user=self.staff_b)
        res_b = self.client.get(url)
        self.assertEqual(res_b.status_code, 404)

    def test_gps_11_location_url_reversals(self):
        """GPS-11: Verify URL reversals and path resolution for location routes."""
        from django.urls import resolve, reverse
        import uuid

        fake_id = uuid.uuid4()
        loc_url = reverse("emergencies:incident_location", kwargs={"pk": fake_id})
        self.assertEqual(loc_url, f"/api/emergencies/{fake_id}/location/")
        self.assertEqual(resolve(f"/api/emergencies/{fake_id}/location/").url_name, "incident_location")

        hist_url = reverse("emergencies:incident_location_history", kwargs={"pk": fake_id})
        self.assertEqual(hist_url, f"/api/emergencies/{fake_id}/locations/")
        self.assertEqual(resolve(f"/api/emergencies/{fake_id}/locations/").url_name, "incident_location_history")


class EmergencyEventAndNotificationServiceTest(TestCase):
    """Unit and service tests for EmergencyEvent logging and Notification dispatch."""

    def setUp(self):
        self.driver = User.objects.create_user(
            username="driver_evt_srv",
            email="driver.evt@sertos.local",
            password="SecurePassword123!",
            role=UserRole.AMBULANCE_DRIVER,
            first_name="Ravi",
            last_name="Shankar",
            is_active=True,
            is_verified=True,
        )
        self.ambulance = Ambulance.objects.create(
            vehicle_number="KA-01-EVT-1001",
            assigned_driver=self.driver,
            is_active=True,
        )
        self.hospital_a = Hospital.objects.create(
            name="Hospital Alpha Service",
            hospital_code="HOSP-EVT-A",
            address="10 Alpha St",
        )
        self.staff_a = User.objects.create_user(
            username="staff_evt_a",
            email="staff.a@sertos.local",
            password="SecurePassword123!",
            role=UserRole.HOSPITAL_STAFF,
            first_name="Staff",
            last_name="Alpha",
            is_active=True,
            is_verified=True,
        )
        HospitalStaff.objects.create(
            user=self.staff_a,
            hospital=self.hospital_a,
            is_active=True,
        )

        self.hospital_b = Hospital.objects.create(
            name="Hospital Beta Service",
            hospital_code="HOSP-EVT-B",
            address="20 Beta St",
        )
        self.staff_b = User.objects.create_user(
            username="staff_evt_b",
            email="staff.b@sertos.local",
            password="SecurePassword123!",
            role=UserRole.HOSPITAL_STAFF,
            first_name="Staff",
            last_name="Beta",
            is_active=True,
            is_verified=True,
        )
        HospitalStaff.objects.create(
            user=self.staff_b,
            hospital=self.hospital_b,
            is_active=True,
        )

        self.police_1 = User.objects.create_user(
            username="police_evt_1",
            email="police.1@sertos.local",
            password="SecurePassword123!",
            role=UserRole.POLICE_DISPATCHER,
            first_name="Traffic",
            last_name="One",
            is_active=True,
            is_verified=True,
        )
        self.police_2 = User.objects.create_user(
            username="police_evt_2",
            email="police.2@sertos.local",
            password="SecurePassword123!",
            role=UserRole.POLICE_DISPATCHER,
            first_name="Traffic",
            last_name="Two",
            is_active=True,
            is_verified=True,
        )

    def test_evt_01_incident_creation_generates_event_and_notifications(self):
        """EVT-01: Incident creation persists EMERGENCY_REPORTED event and dispatches notifications."""
        incident = create_emergency_incident(
            driver=self.driver,
            hospital_id=self.hospital_a.id,
            severity=IncidentSeverity.CRITICAL,
            description="High-speed collision on highway",
            patient_data={
                "name": "Vikram Patel",
                "age": 29,
                "gender": Gender.MALE,
                "blood_group": BloodGroup.A_POSITIVE,
                "medical_notes": "Confidential medical history: Asthmatic",
            },
        )

        # 1. Event verification
        events = list(incident.events.all())
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.event_type, EmergencyEventType.EMERGENCY_REPORTED)
        self.assertEqual(event.payload["incident_number"], incident.incident_number)
        self.assertEqual(event.payload["hospital_code"], "HOSP-EVT-A")
        self.assertEqual(event.payload["ambulance_vehicle_number"], "KA-01-EVT-1001")
        # Ensure patient confidential data is NOT leaked into the event payload
        self.assertNotIn("medical_notes", event.payload)
        self.assertNotIn("Asthmatic", str(event.payload))
        self.assertNotIn("Vikram Patel", str(event.payload))

        # 2. Notification recipients verification
        notifs = list(incident.notifications.all())
        self.assertEqual(len(notifs), 3)  # staff_a, police_1, police_2

        recipients = {n.recipient_id for n in notifs}
        self.assertIn(self.staff_a.id, recipients)
        self.assertIn(self.police_1.id, recipients)
        self.assertIn(self.police_2.id, recipients)
        self.assertNotIn(self.staff_b.id, recipients)  # Hospital B staff isolated

        # Verify initial notification status
        for n in notifs:
            self.assertFalse(n.is_read)
            self.assertIsNone(n.read_at)
            self.assertIn(incident.incident_number, n.title)

    def test_evt_02_status_transitions_generate_expected_events_and_notifications(self):
        """EVT-02: Status updates generate STATUS_CHANGED, AMBULANCE_ARRIVED, and EMERGENCY_CLOSED events."""
        incident = create_emergency_incident(
            driver=self.driver,
            hospital_id=self.hospital_a.id,
        )

        # 1. Transition to ASSIGNED
        update_emergency_status(incident, IncidentStatus.ASSIGNED, user=self.driver)
        assigned_event = incident.events.filter(
            event_type=EmergencyEventType.STATUS_CHANGED,
            payload__new_status=IncidentStatus.ASSIGNED,
        ).first()
        self.assertIsNotNone(assigned_event)
        self.assertEqual(assigned_event.payload["old_status"], IncidentStatus.REPORTED)

        # 2. Transition to IN_TRANSIT
        _approve_incident_for_transit(incident, self.staff_a, self.police_1)
        update_emergency_status(incident, IncidentStatus.IN_TRANSIT, user=self.driver)
        transit_event = incident.events.filter(
            event_type=EmergencyEventType.STATUS_CHANGED,
            payload__new_status=IncidentStatus.IN_TRANSIT,
        ).first()
        self.assertIsNotNone(transit_event)

        # 3. Transition to ARRIVED -> generates AMBULANCE_ARRIVED
        update_emergency_status(incident, IncidentStatus.ARRIVED, user=self.driver)
        self.assertTrue(incident.events.filter(event_type=EmergencyEventType.AMBULANCE_ARRIVED).exists())

        # 4. Transition to CLOSED -> generates EMERGENCY_CLOSED
        update_emergency_status(incident, IncidentStatus.CLOSED, user=self.driver)
        self.assertTrue(incident.events.filter(event_type=EmergencyEventType.EMERGENCY_CLOSED).exists())

    def test_evt_03_status_cancellation_generates_cancelled_event(self):
        """EVT-03: Transitioning an incident to CANCELLED generates EMERGENCY_CANCELLED event."""
        incident = create_emergency_incident(
            driver=self.driver,
            hospital_id=self.hospital_a.id,
        )
        update_emergency_status(incident, IncidentStatus.CANCELLED, user=self.driver)
        self.assertTrue(incident.events.filter(event_type=EmergencyEventType.EMERGENCY_CANCELLED).exists())

    def test_evt_04_failed_operations_do_not_create_events_or_notifications(self):
        """EVT-04: Failed domain service calls roll back completely without orphan events or notifications."""
        from rest_framework import serializers

        # 1. Failed incident creation (nonexistent hospital)
        with self.assertRaises(serializers.ValidationError):
            create_emergency_incident(
                driver=self.driver,
                hospital_id=uuid.uuid4(),
            )
        self.assertEqual(EmergencyEvent.objects.count(), 0)
        self.assertEqual(Notification.objects.count(), 0)

        # 2. Successful creation
        incident = create_emergency_incident(
            driver=self.driver,
            hospital_id=self.hospital_a.id,
        )
        initial_event_count = EmergencyEvent.objects.count()
        initial_notif_count = Notification.objects.count()

        # 3. Failed status transition (skipping states: REPORTED -> CLOSED)
        with self.assertRaises(serializers.ValidationError):
            update_emergency_status(incident, IncidentStatus.CLOSED, user=self.driver)

        # Event and notification counts must not increment
        self.assertEqual(EmergencyEvent.objects.count(), initial_event_count)
        self.assertEqual(Notification.objects.count(), initial_notif_count)

    def test_evt_05_gps_update_event_and_throttled_notifications(self):
        """EVT-05: GPS updates create LOCATION_UPDATED events, with throttled notification generation."""
        incident = create_emergency_incident(
            driver=self.driver,
            hospital_id=self.hospital_a.id,
        )
        initial_notif_count_staff = Notification.objects.filter(recipient=self.staff_a).count()

        # 1. First GPS ping -> Creates LOCATION_UPDATED event + dispatches notification
        loc1 = record_ambulance_location(
            incident=incident,
            latitude=Decimal("12.971000"),
            longitude=Decimal("77.594000"),
            accuracy=5.0,
            user=self.driver,
        )
        self.assertIsNotNone(loc1.id)
        first_location_event = incident.events.filter(
            event_type=EmergencyEventType.LOCATION_UPDATED,
            payload__latitude="12.971000",
        ).first()
        self.assertIsNotNone(first_location_event)

        # Staff notification count increments by 1
        new_notif_count_staff = Notification.objects.filter(recipient=self.staff_a).count()
        self.assertEqual(new_notif_count_staff, initial_notif_count_staff + 1)

        # 2. Second GPS ping immediately after -> Creates event, but notifications are THROTTLED
        loc2 = record_ambulance_location(
            incident=incident,
            latitude=Decimal("12.972000"),
            longitude=Decimal("77.595000"),
            accuracy=4.0,
            user=self.driver,
        )
        self.assertIsNotNone(loc2.id)
        second_location_event = incident.events.filter(
            event_type=EmergencyEventType.LOCATION_UPDATED,
            payload__latitude="12.972000",
        ).first()
        self.assertIsNotNone(second_location_event)

        # Throttling check: Notification count remains unchanged!
        throttled_notif_count = Notification.objects.filter(recipient=self.staff_a).count()
        self.assertEqual(throttled_notif_count, new_notif_count_staff)


class NotificationAPITest(TestCase):
    """Integration API test suite for Notification endpoints."""

    def setUp(self):
        from rest_framework.test import APIClient
        self.client = APIClient()

        # 1. Ambulance Driver & Fleet
        self.driver = User.objects.create_user(
            username="driver_notif_api",
            email="driver.notif@sertos.local",
            password="SecurePassword123!",
            role=UserRole.AMBULANCE_DRIVER,
            first_name="Driver",
            last_name="Test",
            is_active=True,
            is_verified=True,
        )
        self.ambulance = Ambulance.objects.create(
            vehicle_number="KA-01-NTF-5001",
            assigned_driver=self.driver,
            is_active=True,
        )

        # 2. Hospital A & Staff
        self.hosp_a = Hospital.objects.create(
            name="Hospital Alpha",
            hospital_code="HOSP-NTF-A",
            address="1 Alpha Road",
        )
        self.staff_a = User.objects.create_user(
            username="staff_notif_a",
            email="staff.a@sertos.local",
            password="SecurePassword123!",
            role=UserRole.HOSPITAL_STAFF,
            first_name="Staff",
            last_name="Alpha",
            is_active=True,
            is_verified=True,
        )
        HospitalStaff.objects.create(
            user=self.staff_a,
            hospital=self.hosp_a,
            is_active=True,
        )

        # 3. Hospital B & Staff (Multi-tenant check)
        self.hosp_b = Hospital.objects.create(
            name="Hospital Beta",
            hospital_code="HOSP-NTF-B",
            address="2 Beta Road",
        )
        self.staff_b = User.objects.create_user(
            username="staff_notif_b",
            email="staff.b@sertos.local",
            password="SecurePassword123!",
            role=UserRole.HOSPITAL_STAFF,
            first_name="Staff",
            last_name="Beta",
            is_active=True,
            is_verified=True,
        )
        HospitalStaff.objects.create(
            user=self.staff_b,
            hospital=self.hosp_b,
            is_active=True,
        )

        # 4. Police Dispatcher & Unverified User
        self.police = User.objects.create_user(
            username="police_notif_api",
            email="police.notif@sertos.local",
            password="SecurePassword123!",
            role=UserRole.POLICE_DISPATCHER,
            first_name="Police",
            last_name="Officer",
            is_active=True,
            is_verified=True,
        )
        self.unverified_user = User.objects.create_user(
            username="unverified_notif_user",
            email="unverified@sertos.local",
            password="SecurePassword123!",
            role=UserRole.HOSPITAL_STAFF,
            first_name="Unverified",
            last_name="Staff",
            is_active=True,
            is_verified=False,
        )

        # 5. Create incident to populate notifications
        self.incident = create_emergency_incident(
            driver=self.driver,
            hospital_id=self.hosp_a.id,
            severity=IncidentSeverity.HIGH,
            description="Motorbike accident",
        )

    def test_api_01_list_user_notifications_paginated(self):
        """NOTIF-01: Authenticated user receives paginated notifications scoped strictly to their account."""
        # 1. Staff A receives notification
        self.client.force_authenticate(user=self.staff_a)
        response = self.client.get("/api/notifications/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["count"], 1)
        self.assertEqual(len(response.data["data"]["results"]), 1)

        notif_data = response.data["data"]["results"][0]
        self.assertEqual(notif_data["incident_number"], self.incident.incident_number)
        self.assertFalse(notif_data["is_read"])
        self.assertIn("New Emergency Reported", notif_data["title"])

        # 2. Staff B (different hospital) receives empty notification list
        self.client.force_authenticate(user=self.staff_b)
        res_b = self.client.get("/api/notifications/")
        self.assertEqual(res_b.status_code, 200)
        self.assertEqual(res_b.data["data"]["count"], 0)
        self.assertEqual(len(res_b.data["data"]["results"]), 0)

        # 3. Police dispatcher receives notification
        self.client.force_authenticate(user=self.police)
        res_pol = self.client.get("/api/notifications/")
        self.assertEqual(res_pol.status_code, 200)
        self.assertEqual(res_pol.data["data"]["count"], 1)

    def test_api_02_filter_notifications_by_is_read(self):
        """NOTIF-02: User can filter notifications with ?is_read=true/false."""
        # Create a second notification for staff_a and mark it read
        update_emergency_status(self.incident, IncidentStatus.ASSIGNED, user=self.driver)

        notifs = list(Notification.objects.filter(recipient=self.staff_a).order_by("created_at"))
        notifs[0].mark_as_read()

        self.client.force_authenticate(user=self.staff_a)

        # Filter is_read=false
        res_unread = self.client.get("/api/notifications/?is_read=false")
        self.assertEqual(res_unread.status_code, 200)
        self.assertEqual(res_unread.data["data"]["count"], 1)
        self.assertFalse(res_unread.data["data"]["results"][0]["is_read"])

        # Filter is_read=true
        res_read = self.client.get("/api/notifications/?is_read=true")
        self.assertEqual(res_read.status_code, 200)
        self.assertEqual(res_read.data["data"]["count"], 1)
        self.assertTrue(res_read.data["data"]["results"][0]["is_read"])

    def test_api_03_retrieve_single_notification_success(self):
        """NOTIF-03: Retrieve operational detail of a specific notification."""
        notif = Notification.objects.filter(recipient=self.staff_a).first()
        self.client.force_authenticate(user=self.staff_a)

        response = self.client.get(f"/api/notifications/{notif.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["id"], str(notif.id))
        self.assertEqual(response.data["data"]["incident_number"], self.incident.incident_number)

    def test_api_04_cross_user_notification_access_denied(self):
        """NOTIF-04: User attempting to retrieve another user's notification receives 404 Not Found."""
        notif_a = Notification.objects.filter(recipient=self.staff_a).first()
        self.client.force_authenticate(user=self.staff_b)

        response = self.client.get(f"/api/notifications/{notif_a.id}/")
        self.assertEqual(response.status_code, 404)

    def test_api_05_mark_single_notification_read(self):
        """NOTIF-05: Marking a notification as read sets is_read=True and read_at timestamp."""
        notif = Notification.objects.filter(recipient=self.staff_a, is_read=False).first()
        self.client.force_authenticate(user=self.staff_a)

        response = self.client.patch(f"/api/notifications/{notif.id}/read/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertTrue(response.data["data"]["is_read"])
        self.assertIsNotNone(response.data["data"]["read_at"])

        notif.refresh_from_db()
        self.assertTrue(notif.is_read)
        self.assertIsNotNone(notif.read_at)

    def test_api_06_cross_user_mark_read_denied(self):
        """NOTIF-06: Attempting to mark another user's notification as read receives 404 Not Found."""
        notif_a = Notification.objects.filter(recipient=self.staff_a).first()
        self.client.force_authenticate(user=self.staff_b)

        response = self.client.patch(f"/api/notifications/{notif_a.id}/read/")
        self.assertEqual(response.status_code, 404)

        notif_a.refresh_from_db()
        self.assertFalse(notif_a.is_read)

    def test_api_07_mark_all_read(self):
        """NOTIF-07: Marking all notifications read updates all unread notifications for that recipient."""
        # Generate 2 additional notifications for police
        update_emergency_status(self.incident, IncidentStatus.ASSIGNED, user=self.driver)
        _approve_incident_for_transit(self.incident, self.staff_a, self.police)
        update_emergency_status(self.incident, IncidentStatus.IN_TRANSIT, user=self.driver)

        self.assertEqual(Notification.objects.filter(recipient=self.police, is_read=False).count(), 3)

        self.client.force_authenticate(user=self.police)
        response = self.client.patch("/api/notifications/read-all/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["updated_count"], 3)

        # Verify all are marked read in database
        self.assertEqual(Notification.objects.filter(recipient=self.police, is_read=False).count(), 0)

    def test_api_08_unauthenticated_and_unverified_access_rejected(self):
        """NOTIF-08: Unauthenticated requests return 401; unverified accounts return 403."""
        # 1. Anonymous -> 401
        self.client.force_authenticate(user=None)
        res_anon = self.client.get("/api/notifications/")
        self.assertEqual(res_anon.status_code, 401)

        # 2. Unverified user -> 403
        self.client.force_authenticate(user=self.unverified_user)
        res_unver = self.client.get("/api/notifications/")
        self.assertEqual(res_unver.status_code, 403)

    def test_api_09_notification_url_reversals(self):
        """NOTIF-09: Verify URL reversals and path resolution for notification routes."""
        from django.urls import resolve, reverse
        import uuid

        list_url = reverse("notifications:notification_list")
        self.assertEqual(list_url, "/api/notifications/")
        self.assertEqual(resolve("/api/notifications/").url_name, "notification_list")

        read_all_url = reverse("notifications:notification_read_all")
        self.assertEqual(read_all_url, "/api/notifications/read-all/")
        self.assertEqual(resolve("/api/notifications/read-all/").url_name, "notification_read_all")

        fake_id = uuid.uuid4()
        det_url = reverse("notifications:notification_detail", kwargs={"pk": fake_id})
        self.assertEqual(det_url, f"/api/notifications/{fake_id}/")
        self.assertEqual(resolve(f"/api/notifications/{fake_id}/").url_name, "notification_detail")

        mark_read_url = reverse("notifications:notification_mark_read", kwargs={"pk": fake_id})
        self.assertEqual(mark_read_url, f"/api/notifications/{fake_id}/read/")
        self.assertEqual(resolve(f"/api/notifications/{fake_id}/read/").url_name, "notification_mark_read")







class Phase4EndToEndIntegrationTest(TestCase):
    """
    Task 4.7: Comprehensive End-to-End Integration Test Suite for Phase 4.
    Validates complete inter-module workflows, RBAC enforcement, data isolation,
    transactional atomicity, GPS telemetry and throttling, lifecycle event logging,
    and patient privacy compliance.
    """

    def setUp(self):
        from rest_framework.test import APIClient
        self.client = APIClient()

        # 1. Hospitals
        self.hospital_a = Hospital.objects.create(
            name="City Central Emergency Hospital",
            hospital_code="HOSP-E2E-A",
            address="100 Main Street, Bangalore",
            latitude=Decimal("12.971600"),
            longitude=Decimal("77.594600"),
            contact_number="+918012345678",
            is_active=True,
        )
        self.hospital_b = Hospital.objects.create(
            name="Metro Trauma Center",
            hospital_code="HOSP-E2E-B",
            address="200 West Boulevard, Bangalore",
            latitude=Decimal("12.980000"),
            longitude=Decimal("77.600000"),
            contact_number="+918098765432",
            is_active=True,
        )

        # 2. Users across roles
        # Driver
        self.driver = User.objects.create_user(
            username="e2e_driver_ram",
            email="ram@sertos.local",
            password="SecurePassword123!@#",
            role=UserRole.AMBULANCE_DRIVER,
            phone_number="+919876543210",
            badge_or_employee_id="DRV-E2E-01",
            is_verified=True,
            is_active=True,
        )
        # Driver 2 (different driver)
        self.driver_other = User.objects.create_user(
            username="e2e_driver_other",
            email="other_driver@sertos.local",
            password="SecurePassword123!@#",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=True,
            is_active=True,
        )
        self.ambulance_other = Ambulance.objects.create(
            vehicle_number="KA-05-EQ-8888",
            vehicle_type="Basic Life Support",
            assigned_driver=self.driver_other,
            is_available=True,
            is_active=True,
        )

        # Hospital Staff A (Hospital A)
        self.staff_a = User.objects.create_user(
            username="e2e_staff_dr_anita",
            email="anita@sertos.local",
            password="SecurePassword123!@#",
            role=UserRole.HOSPITAL_STAFF,
            badge_or_employee_id="MED-E2E-A1",
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
            username="e2e_staff_dr_vikram",
            email="vikram@sertos.local",
            password="SecurePassword123!@#",
            role=UserRole.HOSPITAL_STAFF,
            badge_or_employee_id="MED-E2E-B1",
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
            username="e2e_police_ctrl_kumar",
            email="kumar@sertos.local",
            password="SecurePassword123!@#",
            role=UserRole.POLICE_DISPATCHER,
            badge_or_employee_id="POL-E2E-01",
            is_verified=True,
            is_active=True,
        )

        # Unverified user
        self.unverified_user = User.objects.create_user(
            username="e2e_unverified",
            email="unver@sertos.local",
            password="SecurePassword123!@#",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=False,
            is_active=True,
        )

        # 3. Assigned Ambulance
        self.ambulance = Ambulance.objects.create(
            vehicle_number="KA-05-EQ-7777",
            vehicle_type="Advanced Life Support",
            assigned_driver=self.driver,
            is_available=True,
            is_active=True,
        )

    def test_e2e_01_complete_operational_workflow(self):
        """
        E2E-01: Validates complete operational workflow:
        Driver creation -> Incident report -> Lifecycle transitions -> GPS tracking
        -> Hospital & Police Dashboards -> Notification management -> Incident closure.
        """
        # Step 1: Driver creates emergency incident
        self.client.force_authenticate(user=self.driver)
        create_payload = {
            "hospital": str(self.hospital_a.id),
            "severity": "CRITICAL",
            "description": "Multi-vehicle collision on Outer Ring Road",
            "patient": {
                "name": "Synthetic Patient Alpha",
                "age": 42,
                "gender": "MALE",
                "blood_group": "O+",
                "medical_notes": "CONFIDENTIAL: Internal abdominal trauma, severe blood loss",
            },
        }
        res_create = self.client.post("/api/emergencies/", create_payload, format="json")
        self.assertEqual(res_create.status_code, 201)
        self.assertTrue(res_create.data["success"])
        incident_id = res_create.data["data"]["id"]
        incident_number = res_create.data["data"]["incident_number"]

        # Verify PostgreSQL database persistence
        incident = EmergencyIncident.objects.get(id=incident_id)
        self.assertEqual(incident.incident_number, incident_number)
        self.assertEqual(incident.reporting_driver, self.driver)
        self.assertEqual(incident.ambulance, self.ambulance)
        self.assertEqual(incident.hospital, self.hospital_a)
        self.assertEqual(incident.status, IncidentStatus.REPORTED)
        self.assertEqual(incident.patients.count(), 1)

        # Step 2: Verify EmergencyEvent and Notifications created
        events = EmergencyEvent.objects.filter(incident=incident)
        self.assertEqual(events.count(), 1)
        reported_event = events.first()
        self.assertEqual(reported_event.event_type, EmergencyEventType.EMERGENCY_REPORTED)

        # Notifications: Staff A and Police should have notifications; Staff B should NOT
        notifs_staff_a = Notification.objects.filter(recipient=self.staff_a, incident=incident)
        notifs_police = Notification.objects.filter(recipient=self.police, incident=incident)
        notifs_staff_b = Notification.objects.filter(recipient=self.staff_b, incident=incident)
        self.assertEqual(notifs_staff_a.count(), 1)
        self.assertEqual(notifs_police.count(), 1)
        self.assertEqual(notifs_staff_b.count(), 0)

        # Step 3: Lifecycle transition: REPORTED -> ASSIGNED -> IN_TRANSIT
        res_assigned = self.client.patch(
            f"/api/emergencies/{incident_id}/status/",
            {"status": "ASSIGNED"},
            format="json",
        )
        self.assertEqual(res_assigned.status_code, 200)
        self.assertEqual(res_assigned.data["data"]["status"], "ASSIGNED")
        incident.refresh_from_db()
        self.assertEqual(incident.status, IncidentStatus.ASSIGNED)
        self.assertIsNotNone(incident.assigned_at)

        _approve_incident_for_transit(incident, self.staff_a, self.police)
        res_status = self.client.patch(
            f"/api/emergencies/{incident_id}/status/",
            {"status": "IN_TRANSIT"},
            format="json",
        )
        self.assertEqual(res_status.status_code, 200)
        self.assertEqual(res_status.data["data"]["status"], "IN_TRANSIT")
        incident.refresh_from_db()
        self.assertEqual(incident.status, IncidentStatus.IN_TRANSIT)
        self.assertIsNotNone(incident.in_transit_at)

        # Verify STATUS_CHANGED event
        status_event = EmergencyEvent.objects.filter(
            incident=incident, event_type=EmergencyEventType.STATUS_CHANGED
        ).first()
        self.assertIsNotNone(status_event)

        # Step 4: GPS Telemetry coordinate pings
        gps_payload = {
            "latitude": "12.972500",
            "longitude": "77.595500",
            "accuracy": 4.5,
            "recorded_at": timezone.now().isoformat(),
        }
        res_gps = self.client.post(
            f"/api/emergencies/{incident_id}/location/", gps_payload, format="json"
        )
        self.assertEqual(res_gps.status_code, 201)
        self.assertEqual(res_gps.data["data"]["latitude"], "12.972500")

        # Verify latest location endpoint
        res_latest = self.client.get(f"/api/emergencies/{incident_id}/location/")
        self.assertEqual(res_latest.status_code, 200)
        self.assertEqual(res_latest.data["data"]["latitude"], "12.972500")

        # Verify breadcrumb history endpoint
        res_history = self.client.get(f"/api/emergencies/{incident_id}/locations/")
        self.assertEqual(res_history.status_code, 200)
        self.assertGreaterEqual(len(res_history.data["data"]), 1)

        # Step 5: Hospital Dashboard verification
        # Staff A sees the incident with patient medical notes
        self.client.force_authenticate(user=self.staff_a)
        res_hosp_list = self.client.get("/api/hospital/incidents/")
        self.assertEqual(res_hosp_list.status_code, 200)
        self.assertEqual(len(res_hosp_list.data["data"]), 1)

        res_hosp_det = self.client.get(f"/api/hospital/incidents/{incident_id}/")
        self.assertEqual(res_hosp_det.status_code, 200)
        patient_data_hosp = res_hosp_det.data["data"]["patients"][0]
        self.assertIn("medical_notes", patient_data_hosp)
        self.assertIn("Internal abdominal trauma", patient_data_hosp["medical_notes"])

        # Staff B (Hospital B) CANNOT see Hospital A's incident
        self.client.force_authenticate(user=self.staff_b)
        res_hosp_b_list = self.client.get("/api/hospital/incidents/")
        self.assertEqual(res_hosp_b_list.status_code, 200)
        self.assertEqual(len(res_hosp_b_list.data["data"]), 0)

        res_hosp_b_det = self.client.get(f"/api/hospital/incidents/{incident_id}/")
        self.assertEqual(res_hosp_b_det.status_code, 404)

        # Step 6: Police Dashboard verification
        self.client.force_authenticate(user=self.police)
        res_police_list = self.client.get("/api/police/incidents/")
        self.assertEqual(res_police_list.status_code, 200)
        self.assertEqual(len(res_police_list.data["data"]), 1)

        res_police_det = self.client.get(f"/api/police/incidents/{incident_id}/")
        self.assertEqual(res_police_det.status_code, 200)
        patient_data_police = res_police_det.data["data"]["patients"][0]
        # CRITICAL: Police MUST NOT see confidential medical notes
        self.assertNotIn("medical_notes", patient_data_police)

        # Step 7: Notification operations
        self.client.force_authenticate(user=self.staff_a)
        res_notif_list = self.client.get("/api/notifications/?is_read=false")
        self.assertEqual(res_notif_list.status_code, 200)
        self.assertGreaterEqual(res_notif_list.data["data"]["count"], 1)
        notif_id = res_notif_list.data["data"]["results"][0]["id"]

        # Retrieve single notification
        res_notif_det = self.client.get(f"/api/notifications/{notif_id}/")
        self.assertEqual(res_notif_det.status_code, 200)
        self.assertEqual(res_notif_det.data["data"]["id"], notif_id)

        # Mark single notification as read
        res_mark = self.client.patch(f"/api/notifications/{notif_id}/read/")
        self.assertEqual(res_mark.status_code, 200)
        self.assertTrue(res_mark.data["data"]["is_read"])

        # Mark all read
        res_read_all = self.client.patch("/api/notifications/read-all/")
        self.assertEqual(res_read_all.status_code, 200)
        self.assertIn("updated_count", res_read_all.data["data"])

        # Step 8: Complete lifecycle: IN_TRANSIT -> ARRIVED -> CLOSED
        self.client.force_authenticate(user=self.driver)
        res_arr = self.client.patch(
            f"/api/emergencies/{incident_id}/status/",
            {"status": "ARRIVED"},
            format="json",
        )
        self.assertEqual(res_arr.status_code, 200)
        self.assertEqual(res_arr.data["data"]["status"], "ARRIVED")

        res_close = self.client.patch(
            f"/api/emergencies/{incident_id}/status/",
            {"status": "CLOSED"},
            format="json",
        )
        self.assertEqual(res_close.status_code, 200)
        self.assertEqual(res_close.data["data"]["status"], "CLOSED")
        incident.refresh_from_db()
        self.assertEqual(incident.status, IncidentStatus.CLOSED)
        self.assertIsNotNone(incident.closed_at)

        # Step 9: Terminal state verification: CLOSED incident rejects new transitions and GPS pings
        res_post_closed_trans = self.client.patch(
            f"/api/emergencies/{incident_id}/status/",
            {"status": "IN_TRANSIT"},
            format="json",
        )
        self.assertEqual(res_post_closed_trans.status_code, 400)

        res_post_closed_gps = self.client.post(
            f"/api/emergencies/{incident_id}/location/", gps_payload, format="json"
        )
        self.assertEqual(res_post_closed_gps.status_code, 400)

    def test_e2e_02_patient_privacy_cross_boundary_protection(self):
        """
        E2E-02: Verifies patient confidential medical notes are strictly isolated:
        - Stored in PostgreSQL
        - Accessible to hospital staff and ambulance driver
        - Excluded from police responses, event audit payloads, and notification messages.
        """
        self.client.force_authenticate(user=self.driver)
        create_payload = {
            "hospital": str(self.hospital_a.id),
            "severity": "HIGH",
            "description": "Suspected stroke",
            "patient": {
                "name": "Synthetic Patient Beta",
                "age": 65,
                "gender": "FEMALE",
                "blood_group": "AB+",
                "medical_notes": "PRIVATE: Unconscious, facial droop, allergic to aspirin",
            },
        }
        res = self.client.post("/api/emergencies/", create_payload, format="json")
        self.assertEqual(res.status_code, 201)
        incident_id = res.data["data"]["id"]

        incident = EmergencyIncident.objects.get(id=incident_id)

        # 1. Event payloads do NOT contain medical notes
        for evt in EmergencyEvent.objects.filter(incident=incident):
            payload_str = str(evt.payload)
            self.assertNotIn("PRIVATE", payload_str)
            self.assertNotIn("aspirin", payload_str)
            self.assertNotIn("Unconscious", payload_str)

        # 2. Notification messages do NOT contain medical notes
        for notif in Notification.objects.filter(incident=incident):
            self.assertNotIn("PRIVATE", notif.message)
            self.assertNotIn("aspirin", notif.message)
            self.assertNotIn("Unconscious", notif.message)

        # 3. Police API does NOT contain medical notes
        self.client.force_authenticate(user=self.police)
        res_pol = self.client.get(f"/api/police/incidents/{incident_id}/")
        self.assertEqual(res_pol.status_code, 200)
        pol_patient = res_pol.data["data"]["patients"][0]
        self.assertNotIn("medical_notes", pol_patient)
        self.assertEqual(pol_patient["name"], "Synthetic Patient Beta")

        # 4. Driver API DOES contain medical notes
        self.client.force_authenticate(user=self.driver)
        res_drv = self.client.get(f"/api/emergencies/{incident_id}/")
        self.assertEqual(res_drv.status_code, 200)
        drv_patient = res_drv.data["data"]["patients"][0]
        self.assertIn("medical_notes", drv_patient)
        self.assertIn("aspirin", drv_patient["medical_notes"])

    def test_e2e_03_transactional_rollback_preserves_clean_state(self):
        """
        E2E-03: Verifies transactional atomicity during incident creation failure.
        Invalid input rolls back completely with zero dangling records.
        """
        self.client.force_authenticate(user=self.driver)
        initial_incidents = EmergencyIncident.objects.count()
        initial_patients = Patient.objects.count()
        initial_events = EmergencyEvent.objects.count()
        initial_notifs = Notification.objects.count()

        # Submit invalid hospital ID (non-existent UUID)
        bad_payload = {
            "hospital": str(uuid.uuid4()),
            "severity": "CRITICAL",
            "patient": {
                "name": "Failed Transaction Patient",
            },
        }
        res = self.client.post("/api/emergencies/", bad_payload, format="json")
        self.assertEqual(res.status_code, 400)

        # Verify absolutely zero orphaned records were created
        self.assertEqual(EmergencyIncident.objects.count(), initial_incidents)
        self.assertEqual(Patient.objects.count(), initial_patients)
        self.assertEqual(EmergencyEvent.objects.count(), initial_events)
        self.assertEqual(Notification.objects.count(), initial_notifs)

    def test_e2e_04_gps_throttling_preserves_full_breadcrumb_history(self):
        """
        E2E-04: Verifies high-frequency GPS ping ingestion:
        - Every valid coordinate ping is persisted in AmbulanceLocation
        - Breadcrumb history contains all sequential pings
        - Notifications are throttled to 1 alert per 300-second window.
        """
        self.client.force_authenticate(user=self.driver)
        res = self.client.post(
            "/api/emergencies/",
            {"hospital": str(self.hospital_a.id), "severity": "MEDIUM"},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        incident_id = res.data["data"]["id"]

        # Send 3 rapid GPS pings
        for i in range(3):
            ping_data = {
                "latitude": str(Decimal("12.972000") + Decimal(str(i * 0.001))),
                "longitude": str(Decimal("77.595000") + Decimal(str(i * 0.001))),
                "accuracy": 5.0,
                "recorded_at": timezone.now().isoformat(),
            }
            res_ping = self.client.post(
                f"/api/emergencies/{incident_id}/location/", ping_data, format="json"
            )
            self.assertEqual(res_ping.status_code, 201)

        # Verify all 3 locations are stored in database
        self.assertEqual(AmbulanceLocation.objects.filter(incident_id=incident_id).count(), 3)

        # Verify history returns all 3 breadcrumbs
        res_hist = self.client.get(f"/api/emergencies/{incident_id}/locations/")
        self.assertEqual(res_hist.status_code, 200)
        self.assertEqual(len(res_hist.data["data"]), 3)

        # Verify notifications: only 1 location notification dispatched (throttling active)
        loc_notifs = Notification.objects.filter(
            incident_id=incident_id, title__icontains="Location Update"
        )
        self.assertEqual(loc_notifs.count(), 2)  # 1 for staff_a, 1 for police

    def test_e2e_05_unauthorized_and_unverified_access_rejection(self):
        """
        E2E-05: Verifies strict RBAC and authentication guards across all Phase 4 endpoints.
        """
        # 1. Unauthenticated requests are rejected with 401
        self.client.logout()
        self.assertEqual(self.client.get("/api/emergencies/").status_code, 401)
        self.assertEqual(self.client.get("/api/hospital/incidents/").status_code, 401)
        self.assertEqual(self.client.get("/api/police/incidents/").status_code, 401)
        self.assertEqual(self.client.get("/api/notifications/").status_code, 401)

        # 2. Unverified users are rejected with 403
        self.client.force_authenticate(user=self.unverified_user)
        self.assertEqual(self.client.get("/api/emergencies/").status_code, 403)
        self.assertEqual(self.client.get("/api/notifications/").status_code, 403)

        # 3. Cross-driver tampering rejection
        # Driver 1 creates incident
        self.client.force_authenticate(user=self.driver)
        res_create = self.client.post(
            "/api/emergencies/",
            {"hospital": str(self.hospital_a.id), "severity": "LOW"},
            format="json",
        )
        incident_id = res_create.data["data"]["id"]

        # Driver 2 attempts to update Driver 1's incident status -> 404 (scoped queryset)
        self.client.force_authenticate(user=self.driver_other)
        res_tamper_status = self.client.patch(
            f"/api/emergencies/{incident_id}/status/",
            {"status": "IN_TRANSIT"},
            format="json",
        )
        self.assertEqual(res_tamper_status.status_code, 404)

        # Driver 2 attempts to post GPS location for Driver 1's incident -> 404 (scoped incident)
        res_tamper_gps = self.client.post(
            f"/api/emergencies/{incident_id}/location/",
            {"latitude": "12.970000", "longitude": "77.590000"},
            format="json",
        )
        self.assertEqual(res_tamper_gps.status_code, 404)

        # 4. Cross-user notification tampering rejection
        # Staff B attempts to retrieve or mark Staff A's notification -> 404
        notif_a = Notification.objects.filter(recipient=self.staff_a, incident_id=incident_id).first()
        self.assertIsNotNone(notif_a)

        self.client.force_authenticate(user=self.staff_b)
        self.assertEqual(self.client.get(f"/api/notifications/{notif_a.id}/").status_code, 404)
        self.assertEqual(self.client.patch(f"/api/notifications/{notif_a.id}/read/").status_code, 404)

    def test_e2e_06_driver_impersonation_prevention(self):
        """
        E2E-06: Verifies reporting_driver and ambulance cannot be injected/spoofed in request payloads.
        Authoritative records are derived strictly from request.user.
        """
        self.client.force_authenticate(user=self.driver)
        spoofed_payload = {
            "hospital": str(self.hospital_a.id),
            "severity": "HIGH",
            "reporting_driver": str(self.driver_other.id),
            "ambulance": str(self.ambulance_other.id),
        }
        res = self.client.post("/api/emergencies/", spoofed_payload, format="json")
        self.assertEqual(res.status_code, 201)

        incident_id = res.data["data"]["id"]
        incident = EmergencyIncident.objects.get(id=incident_id)

        # Must be bound to authenticated driver, NOT spoofed values
        self.assertEqual(incident.reporting_driver, self.driver)
        self.assertEqual(incident.ambulance, self.ambulance)
