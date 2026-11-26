"""
Database models for SERTOS Emergency Response System.

Defines core medical infrastructure, transport fleet, incident management, patient triage, and GPS location models:
1. Hospital: Registered medical facilities with geographic coordinates.
2. HospitalStaff: Staff affiliations linking verified hospital emergency personnel to medical facilities.
3. Ambulance: Emergency transport vehicles with driver assignment and operational status.
4. EmergencyIncident: Core emergency event tracking dispatch lifecycle, reporting driver, vehicle, and hospital.
5. Patient: Individual patient information linked to an emergency incident.
6. AmbulanceLocation: High-frequency GPS tracking breadcrumbs for an active emergency incident.
"""

import uuid
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from apps.accounts.models import UserRole


class Hospital(models.Model):
    """
    Emergency medical facility capable of receiving inbound triage cases.
    Stores institutional identifiers, address, and geographic coordinates.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID identifier for the hospital.",
    )
    name = models.CharField(
        max_length=150,
        help_text="Full institutional name of the hospital.",
    )
    hospital_code = models.CharField(
        max_length=30,
        unique=True,
        help_text="Unique institutional hospital code (e.g. HOSP-BLR-001).",
    )
    address = models.TextField(
        help_text="Physical street address and landmarks.",
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("-90.000000")),
            MaxValueValidator(Decimal("90.000000")),
        ],
        help_text="GPS latitude coordinate in decimal degrees (-90.0 to 90.0).",
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("-180.000000")),
            MaxValueValidator(Decimal("180.000000")),
        ],
        help_text="GPS longitude coordinate in decimal degrees (-180.0 to 180.0).",
    )
    contact_number = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        help_text="Emergency room intake direct contact number.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Designates whether this hospital is operational and accepting patients.",
    )
    staff = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="HospitalStaff",
        related_name="associated_hospitals",
        blank=True,
        help_text="Medical personnel and emergency room staff associated with this facility.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when hospital record was created.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when hospital record was last updated.",
    )

    class Meta:
        db_table = "emergencies_hospital"
        verbose_name = "Hospital"
        verbose_name_plural = "Hospitals"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active"], name="idx_hosp_is_active"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.hospital_code})"

    def clean(self):
        super().clean()
        errors = {}

        # Coordinate pairing rule: both coordinates must be supplied together or both omitted.
        has_lat = self.latitude is not None
        has_lng = self.longitude is not None

        if (has_lat and not has_lng) or (has_lng and not has_lat):
            errors["__all__"] = "Both latitude and longitude must be provided together, or both omitted."

        # Range validation in clean() providing descriptive field errors
        if has_lat:
            if self.latitude < Decimal("-90") or self.latitude > Decimal("90"):
                errors["latitude"] = "Latitude must be between -90 and 90 degrees."
        if has_lng:
            if self.longitude < Decimal("-180") or self.longitude > Decimal("180"):
                errors["longitude"] = "Longitude must be between -180 and 180 degrees."

        if errors:
            raise ValidationError(errors)



class HospitalStaff(models.Model):
    """
    Junction association linking verified HOSPITAL_STAFF users to Hospital facilities.
    Allows multiple staff members per hospital and multiple hospitals per staff member.
    Enforces role validation, account activity, and administrative-only assignment.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID identifier for this hospital staff affiliation.",
    )
    hospital = models.ForeignKey(
        Hospital,
        on_delete=models.CASCADE,
        related_name="staff_affiliations",
        help_text="Associated medical facility.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="hospital_affiliations",
        help_text="Personnel with HOSPITAL_STAFF role assigned to this hospital.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Designates whether this staff affiliation is active.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when affiliation was established.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when affiliation was last modified.",
    )

    class Meta:
        db_table = "emergencies_hospital_staff"
        verbose_name = "Hospital Staff Affiliation"
        verbose_name_plural = "Hospital Staff Affiliations"
        ordering = ["hospital", "user"]
        constraints = [
            models.UniqueConstraint(
                fields=["hospital", "user"],
                name="unique_hospital_staff_user",
            ),
        ]
        indexes = [
            models.Index(fields=["hospital", "user"], name="idx_hosp_staff_user"),
            models.Index(fields=["is_active"], name="idx_hosp_staff_active"),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} -> {self.hospital.name}"

    def clean(self):
        super().clean()
        errors = {}

        if self.user_id:
            user = self.user
            if getattr(user, "role", None) != UserRole.HOSPITAL_STAFF:
                errors["user"] = "Assigned user must have the HOSPITAL_STAFF role."
            elif not user.is_active:
                errors["user"] = "Cannot assign an inactive user to a hospital."

        if self.hospital_id:
            if not self.hospital.is_active:
                errors["hospital"] = "Cannot assign staff to an inactive hospital facility."

        if errors:
            raise ValidationError(errors)



class Ambulance(models.Model):
    """
    Emergency response vehicle assigned to an ambulance driver / paramedic.
    Tracks vehicle registration, availability, and active status.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID identifier for the ambulance vehicle.",
    )
    vehicle_number = models.CharField(
        max_length=20,
        unique=True,
        help_text="Official vehicle registration number / license plate (e.g. KA-01-EQ-1234).",
    )
    vehicle_type = models.CharField(
        max_length=50,
        help_text="Vehicle classification (e.g. Advanced Life Support, Basic Life Support, Patient Transport).",
    )
    assigned_driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_ambulances",
        help_text="Assigned paramedic or driver with AMBULANCE_DRIVER role.",
    )
    is_available = models.BooleanField(
        default=True,
        help_text="Designates whether the ambulance is currently available for dispatch.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Designates whether the vehicle is active in the fleet.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when vehicle was registered.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when vehicle record was last updated.",
    )

    class Meta:
        db_table = "emergencies_ambulance"
        verbose_name = "Ambulance"
        verbose_name_plural = "Ambulances"
        ordering = ["vehicle_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["assigned_driver"],
                condition=models.Q(assigned_driver__isnull=False, is_active=True),
                name="unique_active_ambulance_driver",
            ),
        ]
        indexes = [
            models.Index(fields=["is_available"], name="idx_amb_is_available"),
            models.Index(fields=["is_active"], name="idx_amb_is_active"),
        ]

    def __str__(self) -> str:
        return f"Ambulance {self.vehicle_number} ({self.vehicle_type})"

    @property
    def is_eligible_for_dispatch(self) -> bool:
        """
        Determines whether the ambulance is eligible for a new emergency assignment.
        Must be active, available, and have an assigned, active, verified driver.
        """
        return bool(
            self.is_active
            and self.is_available
            and self.assigned_driver
            and self.assigned_driver.is_active
            and getattr(self.assigned_driver, "is_verified", False)
        )

    def clean(self):
        super().clean()
        errors = {}

        if self.assigned_driver_id:
            driver = self.assigned_driver

            # 1. Role validation: Must have AMBULANCE_DRIVER role
            if getattr(driver, "role", None) != UserRole.AMBULANCE_DRIVER:
                errors["assigned_driver"] = "Assigned user must have the AMBULANCE_DRIVER role."

            # 2. Activity validation: Inactive user must not be assigned
            elif not driver.is_active:
                errors["assigned_driver"] = "Cannot assign an inactive user as an ambulance driver."

            # 3. Driver assignment safety: One active ambulance per driver
            if self.is_active:
                existing_qs = Ambulance.objects.filter(
                    assigned_driver=driver,
                    is_active=True,
                )
                if self.pk:
                    existing_qs = existing_qs.exclude(pk=self.pk)
                if existing_qs.exists():
                    errors["assigned_driver"] = "This driver is already assigned to another active ambulance."

        if errors:
            raise ValidationError(errors)



class IncidentSeverity(models.TextChoices):
    """Controlled severity levels for emergency triage."""
    CRITICAL = "CRITICAL", "Critical (Immediate Life Threat)"
    HIGH = "HIGH", "High (Severe / Urgent Care Required)"
    MEDIUM = "MEDIUM", "Medium (Standard Emergency)"
    LOW = "LOW", "Low (Non-Life Threatening)"


class IncidentStatus(models.TextChoices):
    """
    Controlled lifecycle status for emergency response.
    Progression: REPORTED -> ASSIGNED -> IN_TRANSIT -> ARRIVED -> CLOSED
    Terminal state: CANCELLED
    """
    REPORTED = "REPORTED", "Reported"
    ASSIGNED = "ASSIGNED", "Assigned"
    IN_TRANSIT = "IN_TRANSIT", "In Transit"
    ARRIVED = "ARRIVED", "Arrived at Hospital"
    CLOSED = "CLOSED", "Closed"
    CANCELLED = "CANCELLED", "Cancelled"


class EmergencyIncident(models.Model):
    """
    Core emergency incident tracking life-cycle dispatch, vehicle, driver, and destination hospital.
    """

    VALID_TRANSITIONS = {
        IncidentStatus.REPORTED: [IncidentStatus.REPORTED, IncidentStatus.ASSIGNED, IncidentStatus.CANCELLED],
        IncidentStatus.ASSIGNED: [IncidentStatus.ASSIGNED, IncidentStatus.IN_TRANSIT, IncidentStatus.CANCELLED],
        IncidentStatus.IN_TRANSIT: [IncidentStatus.IN_TRANSIT, IncidentStatus.ARRIVED, IncidentStatus.CANCELLED],
        IncidentStatus.ARRIVED: [IncidentStatus.ARRIVED, IncidentStatus.CLOSED, IncidentStatus.CANCELLED],
        IncidentStatus.CLOSED: [IncidentStatus.CLOSED],
        IncidentStatus.CANCELLED: [IncidentStatus.CANCELLED],
    }

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID identifier for the emergency incident.",
    )
    incident_number = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        help_text="Human-readable unique incident reference code (e.g. INC-20261114-0001).",
    )
    reporting_driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reported_incidents",
        help_text="Authenticated ambulance driver who initiated/reported this incident.",
    )
    ambulance = models.ForeignKey(
        Ambulance,
        on_delete=models.PROTECT,
        related_name="emergency_incidents",
        help_text="Active ambulance vehicle assigned to this incident.",
    )
    hospital = models.ForeignKey(
        Hospital,
        on_delete=models.PROTECT,
        related_name="emergency_incidents",
        help_text="Destination medical facility for patient transport.",
    )
    severity = models.CharField(
        max_length=20,
        choices=IncidentSeverity.choices,
        default=IncidentSeverity.MEDIUM,
        db_index=True,
        help_text="Triage severity level determining traffic preemption and hospital priority.",
    )
    status = models.CharField(
        max_length=20,
        choices=IncidentStatus.choices,
        default=IncidentStatus.REPORTED,
        db_index=True,
        help_text="Current operational lifecycle status of the emergency response.",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Preliminary emergency description, chief complaint, or location notes.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when incident was reported.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp of last update.",
    )

    # Lifecycle Milestone Timestamps
    assigned_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when vehicle and driver were assigned/acknowledged.",
    )
    in_transit_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when ambulance departed for hospital (patient onboard).",
    )
    arrived_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when ambulance arrived at destination hospital.",
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when emergency transfer concluded.",
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp if emergency response was cancelled.",
    )

    class Meta:
        db_table = "emergencies_incident"
        verbose_name = "Emergency Incident"
        verbose_name_plural = "Emergency Incidents"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="idx_inc_status"),
            models.Index(fields=["severity"], name="idx_inc_severity"),
            models.Index(fields=["status", "severity"], name="idx_inc_status_sev"),
            models.Index(fields=["created_at"], name="idx_inc_created_at"),
        ]

    def __str__(self) -> str:
        return f"Incident {self.incident_number} [{self.get_severity_display()}] - {self.get_status_display()}"

    def clean(self):
        super().clean()
        errors = {}

        # 1. Validate reporting driver
        if self.reporting_driver_id:
            driver = self.reporting_driver
            if getattr(driver, "role", None) != UserRole.AMBULANCE_DRIVER:
                errors["reporting_driver"] = "Reporting user must have the AMBULANCE_DRIVER role."
            elif not driver.is_active:
                errors["reporting_driver"] = "Reporting driver account is inactive."

        # 2. Validate ambulance activity and driver ownership
        if self.ambulance_id:
            if not self.ambulance.is_active:
                errors["ambulance"] = "The selected ambulance is inactive / decommissioned."
            elif self.reporting_driver_id:
                if self.ambulance.assigned_driver_id != self.reporting_driver_id:
                    errors["ambulance"] = (
                        f"The selected ambulance '{self.ambulance.vehicle_number}' is not "
                        f"assigned to reporting driver '{self.reporting_driver.username}'."
                    )

        # 3. Validate hospital operational status
        if self.hospital_id:
            if not self.hospital.is_active:
                errors["hospital"] = "The selected destination hospital is inactive or not accepting patients."

        # 4. Lifecycle state machine validation
        if self.pk:
            orig = EmergencyIncident.objects.filter(pk=self.pk).values("status").first()
            if orig and self.status != orig["status"]:
                allowed = self.VALID_TRANSITIONS.get(orig["status"], [])
                if self.status not in allowed:
                    errors["status"] = (
                        f"Invalid status transition from '{orig['status']}' to '{self.status}'."
                    )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """
        Automatically sets lifecycle transition timestamps when incident status advances.
        """
        now = timezone.now()
        if self.status == IncidentStatus.ASSIGNED and not self.assigned_at:
            self.assigned_at = now
        elif self.status == IncidentStatus.IN_TRANSIT and not self.in_transit_at:
            self.in_transit_at = now
        elif self.status == IncidentStatus.ARRIVED and not self.arrived_at:
            self.arrived_at = now
        elif self.status == IncidentStatus.CLOSED and not self.closed_at:
            self.closed_at = now
        elif self.status == IncidentStatus.CANCELLED and not self.cancelled_at:
            self.cancelled_at = now

        super().save(*args, **kwargs)


class HospitalBed(models.Model):
    class Category(models.TextChoices):
        GENERAL = "GENERAL", "General"
        ICU = "ICU", "ICU"
        EMERGENCY = "EMERGENCY", "Emergency"

    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        OCCUPIED = "OCCUPIED", "Occupied"
        RESERVED = "RESERVED", "Reserved"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="beds")
    bed_number = models.CharField(max_length=30)
    category = models.CharField(max_length=20, choices=Category.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    patient_label = models.CharField(max_length=150, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "emergencies_hospital_bed"
        ordering = ["bed_number"]
        constraints = [
            models.UniqueConstraint(fields=["hospital", "bed_number"], name="unique_hospital_bed_number"),
        ]


class HospitalIncidentResponse(models.Model):
    class Decision(models.TextChoices):
        ACCEPTED = "ACCEPTED", "Accepted"
        REJECTED = "REJECTED", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.OneToOneField(
        EmergencyIncident, on_delete=models.CASCADE, related_name="hospital_response"
    )
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT, related_name="incident_responses")
    responded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    decision = models.CharField(max_length=20, choices=Decision.choices)
    reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "emergencies_hospital_incident_response"


class PoliceIncidentAcknowledgement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.OneToOneField(
        EmergencyIncident,
        on_delete=models.CASCADE,
        related_name="police_acknowledgement",
    )
    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    acknowledged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "emergencies_police_incident_acknowledgement"


class Gender(models.TextChoices):
    """Controlled gender choices for emergency patient triage."""
    MALE = "MALE", "Male"
    FEMALE = "FEMALE", "Female"
    OTHER = "OTHER", "Other"
    UNKNOWN = "UNKNOWN", "Unknown"


class BloodGroup(models.TextChoices):
    """Controlled ABO and Rh blood group choices."""
    A_POSITIVE = "A+", "A Positive (A+)"
    A_NEGATIVE = "A-", "A Negative (A-)"
    B_POSITIVE = "B+", "B Positive (B+)"
    B_NEGATIVE = "B-", "B Negative (B-)"
    AB_POSITIVE = "AB+", "AB Positive (AB+)"
    AB_NEGATIVE = "AB-", "AB Negative (AB-)"
    O_POSITIVE = "O+", "O Positive (O+)"
    O_NEGATIVE = "O-", "O Negative (O-)"
    UNKNOWN = "UNKNOWN", "Unknown"


class Patient(models.Model):
    """
    Patient information collected during emergency response transport.
    Minimizes PII collection to emergency medical triage data.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID identifier for the patient record.",
    )
    incident = models.ForeignKey(
        EmergencyIncident,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="patients",
        help_text="Associated emergency incident.",
    )
    name = models.CharField(
        max_length=150,
        help_text="Patient full name (or 'Unidentified' if unconscious/unknown).",
    )
    age = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(150)],
        help_text="Patient age in years (0 to 150), null if unknown.",
    )
    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        default=Gender.UNKNOWN,
        help_text="Patient gender identity.",
    )
    blood_group = models.CharField(
        max_length=10,
        choices=BloodGroup.choices,
        blank=True,
        default="",
        help_text="ABO/Rh blood group (optional, blank if unverified).",
    )
    medical_notes = models.TextField(
        blank=True,
        default="",
        help_text="Pre-existing conditions, allergies, or emergency triage notes.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when patient was registered in system.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp of last update.",
    )

    class Meta:
        db_table = "emergencies_patient"
        verbose_name = "Patient"
        verbose_name_plural = "Patients"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"], name="idx_patient_created_at"),
        ]

    def __str__(self) -> str:
        return f"Patient {self.name} ({self.get_gender_display()})"

    def clean(self):
        super().clean()
        errors = {}

        if self.age is not None and (self.age < 0 or self.age > 150):
            errors["age"] = "Patient age must be between 0 and 150."

        if errors:
            raise ValidationError(errors)



class AmbulanceLocation(models.Model):
    """
    High-frequency GPS tracking breadcrumbs for an active ambulance on an emergency incident.
    Tracks geographic coordinates, accuracy radius, client-recorded timestamp, and authoritative server timestamp.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID identifier for this GPS breadcrumb.",
    )
    ambulance = models.ForeignKey(
        Ambulance,
        on_delete=models.CASCADE,
        related_name="locations",
        help_text="The ambulance vehicle emitting GPS coordinates.",
    )
    incident = models.ForeignKey(
        EmergencyIncident,
        on_delete=models.CASCADE,
        related_name="locations",
        help_text="The emergency incident during which this location was recorded.",
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[
            MinValueValidator(Decimal("-90.000000")),
            MaxValueValidator(Decimal("90.000000")),
        ],
        help_text="GPS latitude coordinate in decimal degrees (-90.0 to 90.0).",
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[
            MinValueValidator(Decimal("-180.000000")),
            MaxValueValidator(Decimal("180.000000")),
        ],
        help_text="GPS longitude coordinate in decimal degrees (-180.0 to 180.0).",
    )
    accuracy = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0)],
        help_text="Estimated horizontal accuracy radius in metres.",
    )
    recorded_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp reported by the in-vehicle GPS hardware / client.",
    )
    server_received_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Authoritative server timestamp when coordinates were ingested.",
    )

    class Meta:
        db_table = "emergencies_ambulance_location"
        verbose_name = "Ambulance Location"
        verbose_name_plural = "Ambulance Locations"
        ordering = ["-server_received_at"]
        indexes = [
            models.Index(fields=["incident", "-server_received_at"], name="idx_loc_inc_received"),
            models.Index(fields=["ambulance", "-server_received_at"], name="idx_loc_amb_received"),
        ]

    def __str__(self) -> str:
        return f"{self.ambulance.vehicle_number} @ ({self.latitude}, {self.longitude}) [{self.server_received_at}]"

    def save(self, *args, **kwargs):
        if self.recorded_at is None:
            self.recorded_at = timezone.now()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        errors = {}

        # 1. Coordinate range validation
        if self.latitude is not None:
            if self.latitude < Decimal("-90") or self.latitude > Decimal("90"):
                errors["latitude"] = "Latitude must be between -90 and 90 degrees."
        else:
            errors["latitude"] = "Latitude coordinate is required."

        if self.longitude is not None:
            if self.longitude < Decimal("-180") or self.longitude > Decimal("180"):
                errors["longitude"] = "Longitude must be between -180 and 180 degrees."
        else:
            errors["longitude"] = "Longitude coordinate is required."

        # 2. Accuracy validation
        if self.accuracy is not None and self.accuracy < 0:
            errors["accuracy"] = "GPS accuracy radius cannot be negative."

        # 3. Association integrity: ambulance must match the incident's assigned ambulance
        if self.ambulance_id and self.incident_id:
            if self.ambulance_id != self.incident.ambulance_id:
                errors["ambulance"] = (
                    f"Ambulance '{self.ambulance.vehicle_number}' does not match incident "
                    f"'{self.incident.incident_number}' vehicle '{self.incident.ambulance.vehicle_number}'."
                )

        if errors:
            raise ValidationError(errors)

class EmergencyEventType(models.TextChoices):
    """
    Controlled event types for the emergency incident lifecycle.
    Used for audit logging and internal operational notification dispatch.
    """
    EMERGENCY_REPORTED = "EMERGENCY_REPORTED", "Emergency Reported"
    STATUS_CHANGED = "STATUS_CHANGED", "Status Changed"
    LOCATION_UPDATED = "LOCATION_UPDATED", "Location Updated"
    AMBULANCE_ARRIVED = "AMBULANCE_ARRIVED", "Ambulance Arrived"
    EMERGENCY_CANCELLED = "EMERGENCY_CANCELLED", "Emergency Cancelled"
    EMERGENCY_CLOSED = "EMERGENCY_CLOSED", "Emergency Closed"


class EmergencyEvent(models.Model):
    """
    Internal event audit record representing lifecycle events of an emergency incident.
    Captures operational state changes, vehicle arrivals, and telemetry updates.
    Strictly excludes sensitive patient medical triage notes from event payload.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID identifier for the emergency event.",
    )
    incident = models.ForeignKey(
        EmergencyIncident,
        on_delete=models.CASCADE,
        related_name="events",
        help_text="Associated emergency incident.",
    )
    event_type = models.CharField(
        max_length=50,
        choices=EmergencyEventType.choices,
        db_index=True,
        help_text="Controlled classification of the emergency lifecycle event.",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Human-readable summary of the event occurrence.",
    )
    payload = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured operational event data (excludes patient medical notes).",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when the event occurred.",
    )

    class Meta:
        db_table = "emergencies_event"
        verbose_name = "Emergency Event"
        verbose_name_plural = "Emergency Events"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["incident", "-created_at"], name="idx_event_inc_created"),
            models.Index(fields=["event_type", "-created_at"], name="idx_event_type_created"),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} - {self.incident.incident_number} [{self.created_at}]"


class Notification(models.Model):
    """
    Internal operational notification delivered to hospital staff and police dispatchers.
    Prepares a clean foundation for external multi-channel dispatch (SMS, push, AI voice).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID identifier for the notification.",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        help_text="User recipient of the notification.",
    )
    incident = models.ForeignKey(
        EmergencyIncident,
        on_delete=models.CASCADE,
        related_name="notifications",
        help_text="Associated emergency incident.",
    )
    event = models.ForeignKey(
        EmergencyEvent,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
        help_text="Triggering emergency event (if applicable).",
    )
    title = models.CharField(
        max_length=255,
        help_text="Notification headline or brief summary.",
    )
    message = models.TextField(
        help_text="Detailed notification body text (excludes patient medical notes).",
    )
    is_read = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Designates whether the recipient has read the notification.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when the notification was created.",
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the notification was marked as read.",
    )

    class Meta:
        db_table = "emergencies_notification"
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"], name="idx_notif_user_read"),
            models.Index(fields=["incident", "-created_at"], name="idx_notif_inc_created"),
        ]

    def __str__(self) -> str:
        status_str = "READ" if self.is_read else "UNREAD"
        return f"[{status_str}] {self.recipient.username}: {self.title}"

    def mark_as_read(self):
        """Marks the notification as read with a timestamp if currently unread."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])

