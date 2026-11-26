"""
Django administration configuration for SERTOS Emergencies application.

Supports:
- Safe administrative assignment of Hospital Staff affiliations.
- Operational management of Hospitals, Ambulances, Incidents, and Patients.
"""

from django.contrib import admin
from .models import (
    Ambulance,
    AmbulanceLocation,
    EmergencyEvent,
    EmergencyIncident,
    Hospital,
    HospitalStaff,
    HospitalBed,
    HospitalIncidentResponse,
    PoliceIncidentAcknowledgement,
    Notification,
    Patient,
)


class HospitalStaffInline(admin.TabularInline):
    model = HospitalStaff
    extra = 1
    autocomplete_fields = ["user"]
    fields = ["user", "is_active", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = ["name", "hospital_code", "contact_number", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "hospital_code", "address"]
    inlines = [HospitalStaffInline]


@admin.register(HospitalStaff)
class HospitalStaffAdmin(admin.ModelAdmin):
    list_display = ["user", "hospital", "is_active", "created_at", "updated_at"]
    list_filter = ["is_active", "hospital"]
    search_fields = ["user__username", "user__first_name", "user__last_name", "hospital__name", "hospital__hospital_code"]
    autocomplete_fields = ["hospital", "user"]


@admin.register(HospitalBed)
class HospitalBedAdmin(admin.ModelAdmin):
    list_display = ["hospital", "bed_number", "category", "status", "patient_label", "updated_at"]
    list_filter = ["hospital", "category", "status"]
    search_fields = ["hospital__name", "bed_number", "patient_label"]


@admin.register(HospitalIncidentResponse)
class HospitalIncidentResponseAdmin(admin.ModelAdmin):
    list_display = ["incident", "hospital", "decision", "responded_by", "created_at"]
    list_filter = ["hospital", "decision"]
    search_fields = ["incident__incident_number", "reason"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Ambulance)
class AmbulanceAdmin(admin.ModelAdmin):
    list_display = ["vehicle_number", "vehicle_type", "assigned_driver", "is_available", "is_active"]
    list_filter = ["is_available", "is_active", "vehicle_type"]
    search_fields = ["vehicle_number", "assigned_driver__username"]


class PatientInline(admin.StackedInline):
    model = Patient
    extra = 0
    readonly_fields = ["created_at", "updated_at"]


@admin.register(EmergencyIncident)
class EmergencyIncidentAdmin(admin.ModelAdmin):
    list_display = [
        "incident_number",
        "severity",
        "status",
        "hospital",
        "ambulance",
        "reporting_driver",
        "created_at",
    ]
    list_filter = ["status", "severity", "hospital"]
    search_fields = ["incident_number", "reporting_driver__username", "ambulance__vehicle_number"]
    inlines = [PatientInline]
    readonly_fields = [
        "incident_number",
        "assigned_at",
        "in_transit_at",
        "arrived_at",
        "closed_at",
        "cancelled_at",
        "created_at",
        "updated_at",
    ]


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ["name", "age", "gender", "blood_group", "incident", "created_at"]
    list_filter = ["gender", "blood_group"]
    search_fields = ["name", "incident__incident_number"]


@admin.register(AmbulanceLocation)
class AmbulanceLocationAdmin(admin.ModelAdmin):
    list_display = [
        "ambulance",
        "incident",
        "latitude",
        "longitude",
        "accuracy",
        "recorded_at",
        "server_received_at",
    ]
    list_filter = ["ambulance", "incident__status"]
    search_fields = [
        "ambulance__vehicle_number",
        "incident__incident_number",
    ]
    readonly_fields = ["server_received_at"]


@admin.register(EmergencyEvent)
class EmergencyEventAdmin(admin.ModelAdmin):
    list_display = ["incident", "event_type", "description", "created_at"]
    list_filter = ["event_type", "created_at"]
    search_fields = ["incident__incident_number", "description"]
    readonly_fields = ["id", "created_at"]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["recipient", "title", "incident", "is_read", "created_at", "read_at"]
    list_filter = ["is_read", "created_at"]
    search_fields = ["recipient__username", "title", "incident__incident_number"]
    readonly_fields = ["id", "created_at", "read_at"]


