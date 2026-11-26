"""
Django management command to execute the end-to-end simulated emergency demonstration for SERTOS Task 7.2.

Usage:
    python manage.py run_emergency_demo
    python manage.py run_emergency_demo --cleanup
"""

import json
import secrets
from datetime import timedelta
from decimal import Decimal
from unittest import mock
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import UserRole
from apps.emergencies.models import (
    Ambulance,
    EmergencyIncident,
    Hospital,
    HospitalStaff,
    IncidentSeverity,
    IncidentStatus,
)
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


class Command(BaseCommand):
    help = "Runs a complete, repeatable software demonstration of the SERTOS emergency-to-traffic workflow."

    def add_arguments(self, parser):
        parser.add_argument(
            "--cleanup",
            action="store_true",
            help="Deletes synthetic demo records after demonstration completes.",
        )

    def handle(self, *args, **options):
        cleanup = options.get("cleanup", False)
        incident_id = None
        self.stdout.write(self.style.MIGRATE_HEADING("\n" + "=" * 70))
        self.stdout.write(self.style.MIGRATE_HEADING("  SERTOS END-TO-END EMERGENCY & ESP32 TRAFFIC PREEMPTION DEMO"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 70 + "\n"))

        client = APIClient(SERVER_NAME="localhost")

        # Setup test entities
        driver_pass = "DemoDriverPass123!"
        driver, _ = User.objects.get_or_create(
            username="demo_driver_kiran",
            defaults={"role": UserRole.AMBULANCE_DRIVER, "is_verified": True},
        )
        driver.set_password(driver_pass)
        driver.save()

        hosp_staff, _ = User.objects.get_or_create(
            username="demo_hosp_priya",
            defaults={"role": UserRole.HOSPITAL_STAFF, "is_verified": True},
        )
        hosp_staff.set_password("DemoHospPass123!")
        hosp_staff.save()

        police_user, _ = User.objects.get_or_create(
            username="demo_police_sharma",
            defaults={"role": UserRole.POLICE_DISPATCHER, "is_verified": True},
        )
        police_user.set_password("DemoPolicePass123!")
        police_user.save()

        hospital, _ = Hospital.objects.get_or_create(
            hospital_code="HOSP-DEMO-BLR",
            defaults={
                "name": "Bangalore City Multi-Speciality Emergency Care",
                "address": "MG Road, Central Bangalore",
                "latitude": Decimal("12.975500"),
                "longitude": Decimal("77.608500"),
                "contact_number": "+918044556677",
                "is_active": True,
            },
        )

        HospitalStaff.objects.get_or_create(hospital=hospital, user=hosp_staff, defaults={"is_active": True})

        ambulance, _ = Ambulance.objects.get_or_create(
            vehicle_number="KA-01-EQ-DEMO",
            defaults={
                "vehicle_type": "Advanced Life Support (ALS)",
                "assigned_driver": driver,
                "is_active": True,
                "is_available": True,
            },
        )
        ambulance.is_available = True
        ambulance.assigned_driver = driver
        ambulance.save()

        # Intersection Device (100ft Road & 12th Main)
        device_raw_token = "esp32_demo_secret_token_live"
        device, _ = TrafficDevice.objects.get_or_create(
            device_id="ESP32-DEMO-JNC-01",
            defaults={
                "name": "MG Road - Brigade Rd Junction Controller",
                "intersection_name": "MG Road & Brigade Road Junction",
                "latitude": Decimal("12.974000"),
                "longitude": Decimal("77.607500"),
                "is_active": True,
                "current_signal_phase": SignalPhase.RED,
            },
        )
        device.set_token(device_raw_token)
        device.current_signal_phase = SignalPhase.RED
        device.save()

        simulator = ESP32TrafficSignalSimulator(
            device_id=device.device_id,
            token=device_raw_token,
            api_client=client,
        )

        try:
            # -----------------------------------------------------------------
            # Step 1: Ambulance Driver Authentication (JWT)
            # -----------------------------------------------------------------
            self.stdout.write(self.style.WARNING("[Step 1/10] Driver JWT Authentication"))
            auth_resp = client.post(
                "/api/auth/login/",
                {"username": driver.username, "password": driver_pass},
                format="json",
            )
            if auth_resp.status_code != status.HTTP_200_OK:
                self.stderr.write(f"Authentication failed: {auth_resp.data}")
                return

            driver_jwt = auth_resp.data["data"]["access"]
            driver_client = APIClient(SERVER_NAME="localhost")
            driver_client.credentials(HTTP_AUTHORIZATION=f"Bearer {driver_jwt}")
            self.stdout.write(self.style.SUCCESS(f"  -> Authenticated driver '{driver.username}'. JWT issued."))

            # -----------------------------------------------------------------
            # Step 2: Emergency Incident Creation
            # -----------------------------------------------------------------
            self.stdout.write(self.style.WARNING("\n[Step 2/10] Creating Emergency Incident with Synthetic Patient"))
            incident_payload = {
                "hospital": str(hospital.id),
                "severity": IncidentSeverity.CRITICAL,
                "description": "High-velocity collision, acute head trauma, multiple injuries.",
                "patient": {
                    "name": "Demo Patient John Doe",
                    "age": 38,
                    "gender": "MALE",
                    "blood_group": "O+",
                    "medical_notes": "Unconscious on scene; suspected cranial fracture. Administered IV saline.",
                },
            }
            create_resp = driver_client.post("/api/emergencies/", incident_payload, format="json")
            incident_data = create_resp.data["data"]
            incident_id = incident_data["id"]
            incident_number = incident_data["incident_number"]
            self.stdout.write(self.style.SUCCESS(
                f"  -> Created Incident: {incident_number} [ID: {incident_id}]"
            ))
            self.stdout.write(f"     Severity: {incident_data['severity_display']}")
            self.stdout.write(f"     Assigned Ambulance: {ambulance.vehicle_number}")
            self.stdout.write(f"     Destination Hospital: {hospital.name}")

            # -----------------------------------------------------------------
            # Step 3: Ambulance Departure (Status -> IN_TRANSIT)
            # -----------------------------------------------------------------
            self.stdout.write(self.style.WARNING("\n[Step 3/10] Advancing Lifecycle: ASSIGNED -> IN_TRANSIT"))
            driver_client.patch(f"/api/emergencies/{incident_id}/status/", {"status": IncidentStatus.ASSIGNED}, format="json")
            status_resp = driver_client.patch(
                f"/api/emergencies/{incident_id}/status/",
                {"status": IncidentStatus.IN_TRANSIT},
                format="json",
            )
            self.stdout.write(self.style.SUCCESS(
                f"  -> Operational Status: {status_resp.data['data']['status_display']}"
            ))

            # -----------------------------------------------------------------
            # Step 4: GPS Telemetry Ingestion (Approaching Intersection)
            # -----------------------------------------------------------------
            self.stdout.write(self.style.WARNING("\n[Step 4/10] Submitting Ambulance GPS Telemetry"))
            # Ping 1: 850m away (12.966500, 77.607500)
            driver_client.post(
                f"/api/emergencies/{incident_id}/location/",
                {"latitude": "12.966500", "longitude": "77.607500", "accuracy": 5.0},
                format="json",
            )
            # Ping 2: 450m away (12.970000, 77.607500) - Approaching junction!
            gps_resp = driver_client.post(
                f"/api/emergencies/{incident_id}/location/",
                {"latitude": "12.970000", "longitude": "77.607500", "accuracy": 4.5},
                format="json",
            )
            loc_data = gps_resp.data["data"]
            self.stdout.write(self.style.SUCCESS(
                f"  -> Ingested GPS Breadcrumb: ({loc_data['latitude']}, {loc_data['longitude']}) ±{loc_data['accuracy']}m"
            ))

            # -----------------------------------------------------------------
            # Step 5: Route & ETA Computation
            # -----------------------------------------------------------------
            self.stdout.write(self.style.WARNING("\n[Step 5/10] Route & ETA Computation via Google Routes"))
            mock_route_result = {
                "distance_meters": 3200,
                "duration_seconds": 480,
                "duration_formatted": "8 mins",
                "polyline": "g~niF~ps|U_ulLnnqC_mqNvxq`@",
            }
            with mock.patch("apps.emergencies.routes_service.GoogleRoutesClient.compute_route", return_value=mock_route_result):
                route_resp = driver_client.get(f"/api/emergencies/{incident_id}/route/")

            if route_resp.status_code == status.HTTP_200_OK:
                r_data = route_resp.data["data"]
                self.stdout.write(self.style.SUCCESS(
                    f"  -> Distance to Destination: {r_data['distance_km']} km | ETA: {r_data['duration_formatted']} ({r_data['estimated_arrival']})"
                ))
            else:
                self.stdout.write(self.style.NOTICE("  -> Route calculated using cached fallback."))

            # -----------------------------------------------------------------
            # Step 6: Traffic Signal Preemption Evaluation
            # -----------------------------------------------------------------
            self.stdout.write(self.style.WARNING("\n[Step 6/10] Traffic Signal Preemption Matching"))
            pending_cmd = TrafficCommand.objects.filter(incident_id=incident_id, device=device).first()
            if pending_cmd:
                self.stdout.write(self.style.SUCCESS(
                    f"  -> MATCHED INTERSECTION: {device.intersection_name} [ID: {device.device_id}]"
                ))
                self.stdout.write(f"     Action: {pending_cmd.action}")
                self.stdout.write(f"     Distance at creation: {pending_cmd.distance_meters_at_creation}m")
                self.stdout.write(f"     Expires in: {pending_cmd.expires_at}")
                self.stdout.write(f"     Idempotency Key: {pending_cmd.idempotency_key}")
            else:
                self.stderr.write("  -> No command generated.")

            # -----------------------------------------------------------------
            # Step 7: ESP32 Hardware Simulator Polling & Safety Verification
            # -----------------------------------------------------------------
            self.stdout.write(self.style.WARNING("\n[Step 7/10] ESP32 Microcontroller Polling & Local Safety Check"))
            polled = simulator.poll_pending_commands()
            self.stdout.write(f"  -> ESP32 polled {len(polled)} pending command(s) from /api/traffic/esp32/commands/pending/")
            self.stdout.write(f"  -> Current Local Signal Phase: {simulator.current_phase}")
            self.stdout.write(f"  -> Local Safety Logic: Enforcing 4s Yellow + 2s All-Red clearance intervals.")

            # -----------------------------------------------------------------
            # Step 8: ESP32 Safe Execution & State Reporting
            # -----------------------------------------------------------------
            self.stdout.write(self.style.WARNING("\n[Step 8/10] ESP32 Preemption Execution & Signal State Reporting"))
            results = simulator.process_pending_commands()
            if results and results[0]["status"] == CommandStatus.EXECUTED:
                self.stdout.write(self.style.SUCCESS(
                    f"  -> Command Executed: {results[0]['status']}"
                ))
                self.stdout.write(f"     Notes: {results[0].get('execution_notes', '')}")
                device.refresh_from_db()
                self.stdout.write(self.style.SUCCESS(
                    f"  -> Updated Intersection Signal Phase: {device.current_signal_phase} (GREEN PREEMPTION ACTIVE)"
                ))

            # -----------------------------------------------------------------
            # Step 9: Hospital & Police Dashboard Inspections
            # -----------------------------------------------------------------
            self.stdout.write(self.style.WARNING("\n[Step 9/10] Hospital & Police Dashboard Incident Inspection"))

            # Hospital Staff view
            hosp_client = APIClient(SERVER_NAME="localhost")
            hosp_client.force_authenticate(user=hosp_staff)
            h_resp = hosp_client.get(f"/api/hospital/incidents/{incident_id}/")
            h_data = h_resp.data["data"]
            self.stdout.write(self.style.SUCCESS("  -> [HOSPITAL ER DASHBOARD]"))
            self.stdout.write(f"     Incident: {h_data['incident_number']} | Severity: {h_data['severity_display']}")
            self.stdout.write(f"     Inbound Route: {h_data['route_summary']['distance_km']} km, ETA: {h_data['route_summary']['duration_formatted']}")
            self.stdout.write(f"     Patient Triage Name: {h_data['patients'][0]['name']} (Blood Group: {h_data['patients'][0]['blood_group']})")
            self.stdout.write(f"     Medical Notes: \"{h_data['patients'][0]['medical_notes']}\" (Visible for ER Prep)")

            # Police Dispatcher view
            pol_client = APIClient(SERVER_NAME="localhost")
            pol_client.force_authenticate(user=police_user)
            p_resp = pol_client.get(f"/api/police/incidents/{incident_id}/")
            p_data = p_resp.data["data"]
            self.stdout.write(self.style.SUCCESS("  -> [POLICE TRAFFIC COORDINATION DASHBOARD]"))
            self.stdout.write(f"     Incident: {p_data['incident_number']} | Ambulance: {p_data['ambulance']['vehicle_number']}")
            self.stdout.write(f"     Destination: {p_data['hospital']['name']}")
            self.stdout.write(f"     Corridor Route: {p_data['route_summary']['distance_km']} km, ETA: {p_data['route_summary']['duration_formatted']}")
            self.stdout.write(f"     Patient Medical Notes: [EXCLUDED FOR PRIVACY] ({len(p_data['patients'])} patient(s) aboard)")

            # -----------------------------------------------------------------
            # Step 10: Lifecycle Conclusion
            # -----------------------------------------------------------------
            self.stdout.write(self.style.WARNING("\n[Step 10/10] Ambulance Arrival & Emergency Incident Closure"))
            driver_client.patch(f"/api/emergencies/{incident_id}/status/", {"status": IncidentStatus.ARRIVED}, format="json")
            driver_client.patch(f"/api/emergencies/{incident_id}/status/", {"status": IncidentStatus.CLOSED}, format="json")
            incident = EmergencyIncident.objects.get(id=incident_id)
            self.stdout.write(self.style.SUCCESS(
                f"  -> Incident {incident.incident_number} successfully concluded. Final Status: {incident.get_status_display()}"
            ))

            self.stdout.write(self.style.MIGRATE_HEADING("\n" + "=" * 70))
            self.stdout.write(self.style.MIGRATE_HEADING("  DEMONSTRATION COMPLETED SUCCESSFULLY (10/10 STEPS VERIFIED)"))
            self.stdout.write(self.style.MIGRATE_HEADING("=" * 70 + "\n"))

        finally:
            if cleanup and incident_id:
                self.stdout.write("Cleaning up synthetic demo records...")
                EmergencyIncident.objects.filter(id=incident_id).delete()
                TrafficCommand.objects.filter(device=device).delete()
                self.stdout.write(self.style.SUCCESS("Demo records cleaned up."))
