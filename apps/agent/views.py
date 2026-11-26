"""
API Views for SERTOS AI Emergency Agent (Phases 8.1.3 - 8.1.5).

Exposes:
1. POST /api/agent/sessions/: Start a new voice agent session for the authenticated driver.
2. GET  /api/agent/sessions/: List driver's voice sessions.
3. GET  /api/agent/sessions/<uuid:session_id>/: Inspect session history, state, and emergency context.
4. PATCH /api/agent/sessions/<uuid:session_id>/: Transition session to COMPLETED or ABANDONED.
5. POST /api/agent/sessions/<uuid:session_id>/turn/: Send a text/transcribed driver conversation turn.
6. POST /api/agent/sessions/<uuid:session_id>/confirm-emergency/: Explicit driver emergency confirmation and dispatch.
7. POST /api/agent/sessions/<uuid:session_id>/end/: Explicitly end or abandon an active voice session.
"""

from decimal import Decimal
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.emergencies.models import (
    Ambulance,
    AmbulanceLocation,
    Gender,
    Hospital,
    IncidentSeverity,
)
from apps.emergencies.services import (
    create_emergency_incident,
    find_nearby_hospitals,
    record_ambulance_location,
)
from .extraction import extract_emergency_information
from .models import SessionStatus, VoiceAgentSession
from .permissions import IsVerifiedAmbulanceDriver
from .serializers import (
    VoiceSessionConfirmSerializer,
    VoiceSessionDetailSerializer,
    VoiceSessionSummarySerializer,
    VoiceTurnInputSerializer,
)

INITIAL_GREETING = (
    "SERTOS Emergency Voice Agent ready. Please report the emergency situation, "
    "patient condition, and location."
)

INITIAL_MISSING_INFO = [
    "emergency_type",
    "location_description",
    "consciousness",
    "breathing_status",
    "reported_injuries",
    "patient_age",
    "patient_gender",
]


class VoiceSessionListCreateView(APIView):
    """
    POST: Initiates a new VoiceAgentSession for the authenticated, verified driver.
    GET:  Lists past and active voice sessions for the authenticated driver.
    """

    permission_classes = [IsVerifiedAmbulanceDriver]

    def post(self, request):
        now = timezone.now()
        initial_history = [
            {
                "role": "assistant",
                "message": INITIAL_GREETING,
                "timestamp": now.isoformat(),
            }
        ]

        session = VoiceAgentSession.objects.create(
            driver=request.user,
            status=SessionStatus.ACTIVE,
            conversation_history=initial_history,
            extracted_emergency_data={
                "patient_details": {
                    "name": None,
                    "age": None,
                    "gender": "UNKNOWN",
                    "blood_group": None,
                },
                "consciousness": "UNKNOWN",
                "breathing_status": "UNKNOWN",
                "reported_injuries": [],
                "additional_notes": [],
            },
            missing_information=INITIAL_MISSING_INFO,
            needs_confirmation=False,
        )

        response_data = {
            "session_id": str(session.id),
            "assistant_message": INITIAL_GREETING,
            "extracted_emergency_data": session.extracted_emergency_data,
            "missing_information": session.missing_information,
            "session_status": session.status,
            "needs_confirmation": False,
            "error": None,
        }
        return Response(response_data, status=status.HTTP_201_CREATED)

    def get(self, request):
        sessions = VoiceAgentSession.objects.filter(driver=request.user).order_by("-created_at")
        serializer = VoiceSessionSummarySerializer(sessions, many=True)
        return Response({"sessions": serializer.data}, status=status.HTTP_200_OK)


class VoiceSessionDetailView(APIView):
    """
    GET: Inspects a driver's voice session detail, history, and active emergency context.
    PATCH: Updates session status (COMPLETED, ABANDONED).
    """

    permission_classes = [IsVerifiedAmbulanceDriver]

    def get_session(self, request, session_id):
        try:
            return VoiceAgentSession.objects.get(pk=session_id, driver=request.user)
        except (VoiceAgentSession.DoesNotExist, ValueError):
            return None

    def get(self, request, session_id):
        session = self.get_session(request, session_id)
        if not session:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "Voice session not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = VoiceSessionDetailSerializer(session)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, session_id):
        session = self.get_session(request, session_id)
        if not session:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "Voice session not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        new_status = request.data.get("status")
        if new_status not in [SessionStatus.COMPLETED, SessionStatus.ABANDONED]:
            return Response(
                {
                    "error": {
                        "code": "INVALID_STATUS",
                        "message": f"Status must be '{SessionStatus.COMPLETED}' or '{SessionStatus.ABANDONED}'.",
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        session.status = new_status
        session.ended_at = timezone.now()
        session.save(update_fields=["status", "ended_at", "updated_at"])

        serializer = VoiceSessionDetailSerializer(session)
        return Response(serializer.data, status=status.HTTP_200_OK)


class VoiceSessionEndView(APIView):
    """
    POST: Formally ends an active voice session with status COMPLETED or ABANDONED.
    Provides a simple single-call termination endpoint for frontend voice clients.
    """

    permission_classes = [IsVerifiedAmbulanceDriver]

    def post(self, request, session_id):
        try:
            session = VoiceAgentSession.objects.get(pk=session_id, driver=request.user)
        except (VoiceAgentSession.DoesNotExist, ValueError):
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Voice session not found or access denied.",
                    },
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        target_status = request.data.get("status", SessionStatus.COMPLETED)
        if target_status not in [SessionStatus.COMPLETED, SessionStatus.ABANDONED]:
            target_status = SessionStatus.COMPLETED

        session.status = target_status
        session.ended_at = timezone.now()
        session.save(update_fields=["status", "ended_at", "updated_at"])

        return Response(
            {
                "success": True,
                "session_id": str(session.id),
                "session_status": session.status,
                "ended_at": session.ended_at.isoformat(),
                "message": f"Voice session ended with status '{session.status}'.",
            },
            status=status.HTTP_200_OK,
        )


class VoiceSessionTurnView(APIView):
    """
    POST: Processes a driver's transcribed speech turn, extracts emergency information,
    updates persistent conversation context, and returns a structured response.
    """

    permission_classes = [IsVerifiedAmbulanceDriver]

    def post(self, request, session_id):
        # 1. Resolve session with strict driver ownership
        try:
            session = VoiceAgentSession.objects.get(pk=session_id, driver=request.user)
        except (VoiceAgentSession.DoesNotExist, ValueError):
            return Response(
                {
                    "session_id": str(session_id),
                    "assistant_message": "",
                    "extracted_emergency_data": {},
                    "missing_information": [],
                    "session_status": "NOT_FOUND",
                    "needs_confirmation": False,
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Voice session not found or access denied.",
                    },
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # 2. Check operational status
        if session.status != SessionStatus.ACTIVE:
            return Response(
                {
                    "session_id": str(session.id),
                    "assistant_message": f"This voice session is already {session.status.lower()}.",
                    "extracted_emergency_data": session.extracted_emergency_data,
                    "missing_information": session.missing_information,
                    "session_status": session.status,
                    "needs_confirmation": session.needs_confirmation,
                    "error": {
                        "code": "SESSION_INACTIVE",
                        "message": f"Cannot send turns to a session with status '{session.status}'.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Validate input
        serializer = VoiceTurnInputSerializer(data=request.data)
        if not serializer.is_valid():
            # Extract first validation error message
            first_field = next(iter(serializer.errors))
            first_err = serializer.errors[first_field][0]
            return Response(
                {
                    "session_id": str(session.id),
                    "assistant_message": "",
                    "extracted_emergency_data": session.extracted_emergency_data,
                    "missing_information": session.missing_information,
                    "session_status": session.status,
                    "needs_confirmation": session.needs_confirmation,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": str(first_err),
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        driver_message = serializer.validated_data["message"]
        now = timezone.now()

        # 4. Extract emergency information & evaluate missing info
        extracted_data, missing_fields, needs_confirmation, assistant_reply = extract_emergency_information(
            new_message=driver_message,
            prior_data=session.extracted_emergency_data,
        )

        # 5. Append chronological turns to history
        updated_history = list(session.conversation_history)
        updated_history.append({
            "role": "user",
            "message": driver_message,
            "timestamp": now.isoformat(),
        })
        updated_history.append({
            "role": "assistant",
            "message": assistant_reply,
            "timestamp": now.isoformat(),
        })

        # 6. Persist session updates
        session.extracted_emergency_data = extracted_data
        session.missing_information = missing_fields
        session.needs_confirmation = needs_confirmation
        session.conversation_history = updated_history
        session.save(update_fields=[
            "extracted_emergency_data",
            "missing_information",
            "needs_confirmation",
            "conversation_history",
            "updated_at",
        ])

        # 7. Standardized response contract
        response_payload = {
            "session_id": str(session.id),
            "assistant_message": assistant_reply,
            "extracted_emergency_data": extracted_data,
            "missing_information": missing_fields,
            "session_status": session.status,
            "needs_confirmation": needs_confirmation,
            "error": None,
        }
        return Response(response_payload, status=status.HTTP_200_OK)


class VoiceSessionConfirmEmergencyView(APIView):
    """
    POST: On explicit driver confirmation, creates an EmergencyIncident via domain services,
    links it to the voice session, transitions session to COMPLETED, and initiates dispatch.
    Safely prevents duplicate creation on repeated calls.
    """

    permission_classes = [IsVerifiedAmbulanceDriver]

    def post(self, request, session_id):
        # 1. Resolve session with driver ownership
        try:
            session = (
                VoiceAgentSession.objects.select_related("associated_incident")
                .get(pk=session_id, driver=request.user)
            )
        except (VoiceAgentSession.DoesNotExist, ValueError):
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Voice session not found or access denied.",
                    },
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # 2. Prevent duplicate creation if confirmation was already executed
        if session.associated_incident_id is not None:
            incident = session.associated_incident
            patient = incident.patients.first() if hasattr(incident, "patients") else None
            return Response(
                {
                    "success": True,
                    "incident_id": str(incident.id),
                    "incident_number": incident.incident_number,
                    "status": incident.status,
                    "status_display": incident.get_status_display(),
                    "severity": incident.severity,
                    "severity_display": incident.get_severity_display(),
                    "hospital": {
                        "id": str(incident.hospital.id),
                        "name": incident.hospital.name,
                        "hospital_code": incident.hospital.hospital_code,
                        "address": incident.hospital.address,
                        "contact_number": incident.hospital.contact_number,
                    },
                    "ambulance": {
                        "id": str(incident.ambulance.id),
                        "vehicle_number": incident.ambulance.vehicle_number,
                    },
                    "patient": {
                        "name": patient.name if patient else "Unknown",
                    },
                    "session_id": str(session.id),
                    "session_status": session.status,
                    "is_duplicate_confirmation": True,
                    "message": f"Emergency incident {incident.incident_number} is already confirmed and active.",
                    "next_steps": [
                        "Proceed immediately to destination hospital",
                        "Hospital ER staff and police dispatch notified",
                        "Continuous GPS telemetry active",
                    ],
                },
                status=status.HTTP_200_OK,
            )

        # 3. Check operational status
        if session.status != SessionStatus.ACTIVE:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "SESSION_INACTIVE",
                        "message": f"Cannot confirm emergency on an inactive session with status '{session.status}'.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4. Validate input payload
        serializer = VoiceSessionConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            first_field = next(iter(serializer.errors))
            first_err = serializer.errors[first_field][0]
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": str(first_err),
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 5. Check explicit confirmation flag
        if not serializer.validated_data.get("confirmation", True):
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "CONFIRMATION_REQUIRED",
                        "message": "Emergency dispatch cancelled: explicit driver confirmation was not granted.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 6. Validate required triage information
        extracted = session.extracted_emergency_data or {}
        missing = []

        if not extracted.get("emergency_type"):
            missing.append("emergency_type")
        if extracted.get("consciousness") in [None, "UNKNOWN"]:
            missing.append("consciousness")
        if extracted.get("breathing_status") in [None, "UNKNOWN"]:
            missing.append("breathing_status")

        if missing:
            return Response(
                {
                    "success": False,
                    "incident_id": None,
                    "incident_number": None,
                    "message": "Cannot confirm emergency: essential triage information is missing.",
                    "missing_information": missing,
                    "can_continue_conversation": True,
                    "error": {
                        "code": "MISSING_INFORMATION",
                        "message": f"Please provide missing details before confirming: {', '.join(missing)}.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 7. Resolve trusted GPS coordinates (never invent coordinates)
        lat = serializer.validated_data.get("latitude")
        lng = serializer.validated_data.get("longitude")
        trusted_gps = None

        if lat is not None and lng is not None:
            trusted_gps = (Decimal(f"{float(lat):.6f}"), Decimal(f"{float(lng):.6f}"))
        else:
            # Check latest recorded GPS from driver's assigned ambulance
            ambulance_obj = Ambulance.objects.filter(assigned_driver=request.user, is_active=True).first()
            if ambulance_obj:
                latest_loc = (
                    AmbulanceLocation.objects.filter(ambulance=ambulance_obj)
                    .order_by("-server_received_at", "-id")
                    .first()
                )
                if latest_loc and latest_loc.latitude is not None and latest_loc.longitude is not None:
                    trusted_gps = (
                        Decimal(f"{float(latest_loc.latitude):.6f}"),
                        Decimal(f"{float(latest_loc.longitude):.6f}"),
                    )

        # 8. Resolve destination hospital
        hospital_id = serializer.validated_data.get("hospital_id")
        selected_hospital = None

        if hospital_id:
            try:
                selected_hospital = Hospital.objects.get(pk=hospital_id)
            except (Hospital.DoesNotExist, ValueError):
                return Response(
                    {
                        "success": False,
                        "error": {
                            "code": "INVALID_HOSPITAL",
                            "message": "Selected destination hospital does not exist.",
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not selected_hospital.is_active:
                return Response(
                    {
                        "success": False,
                        "error": {
                            "code": "HOSPITAL_INACTIVE",
                            "message": "Selected destination hospital is inactive or not accepting patients.",
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            # Auto-resolve nearest active hospital using trusted GPS if available
            if trusted_gps:
                try:
                    nearest = find_nearby_hospitals(
                        latitude=trusted_gps[0],
                        longitude=trusted_gps[1],
                        max_results=1,
                        max_distance_km=50,
                    )
                    if nearest:
                        selected_hospital = Hospital.objects.get(pk=nearest[0]["id"])
                except Exception:
                    pass

            if not selected_hospital:
                # Fallback to default active hospital in database
                selected_hospital = Hospital.objects.filter(is_active=True).first()

            if not selected_hospital:
                return Response(
                    {
                        "success": False,
                        "error": {
                            "code": "NO_ACTIVE_HOSPITAL",
                            "message": "No active destination hospital facility is available for dispatch.",
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # 9. Derive or override triage severity
        severity = serializer.validated_data.get("severity")
        if not severity:
            c = extracted.get("consciousness")
            b = extracted.get("breathing_status")
            t = extracted.get("emergency_type")
            inj = extracted.get("reported_injuries", [])

            if c == "UNCONSCIOUS" or b == "NOT_BREATHING":
                severity = IncidentSeverity.CRITICAL
            elif t == "CARDIAC" or b == "LABORED" or "profuse bleeding" in inj:
                severity = IncidentSeverity.HIGH
            else:
                severity = IncidentSeverity.MEDIUM

        # 10. Assemble structured description & patient data
        desc_parts = []
        if extracted.get("emergency_type"):
            desc_parts.append(f"Type: {extracted['emergency_type']}")
        if extracted.get("location_description"):
            desc_parts.append(f"Location: {extracted['location_description']}")
        if extracted.get("consciousness"):
            desc_parts.append(f"Consciousness: {extracted['consciousness']}")
        if extracted.get("breathing_status"):
            desc_parts.append(f"Breathing: {extracted['breathing_status']}")
        if extracted.get("reported_injuries"):
            desc_parts.append(f"Injuries: {', '.join(extracted['reported_injuries'])}")
        if extracted.get("additional_notes"):
            desc_parts.append(f"Notes: {'; '.join(extracted['additional_notes'])}")

        description = " | ".join(desc_parts)

        pd = extracted.get("patient_details", {})
        med_notes = []
        if extracted.get("consciousness"):
            med_notes.append(f"Consciousness: {extracted['consciousness']}")
        if extracted.get("breathing_status"):
            med_notes.append(f"Breathing: {extracted['breathing_status']}")
        if extracted.get("reported_injuries"):
            med_notes.append(f"Injuries: {', '.join(extracted['reported_injuries'])}")

        patient_data = {
            "name": pd.get("name") or "Unknown",
            "age": pd.get("age"),
            "gender": pd.get("gender") if pd.get("gender") in [Gender.MALE, Gender.FEMALE, Gender.OTHER] else Gender.UNKNOWN,
            "blood_group": pd.get("blood_group") or "",
            "medical_notes": " | ".join(med_notes),
        }

        # 11. Transactional creation via existing domain service
        try:
            incident = create_emergency_incident(
                driver=request.user,
                hospital_id=selected_hospital,
                severity=severity,
                description=description,
                patient_data=patient_data,
            )
        except DRFValidationError as exc:
            err_details = exc.detail if hasattr(exc, "detail") else str(exc)
            first_err = err_details
            if isinstance(err_details, dict):
                first_k = next(iter(err_details))
                first_val = err_details[first_k]
                first_err = first_val[0] if isinstance(first_val, list) else first_val
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "DISPATCH_FAILED",
                        "message": str(first_err),
                        "details": err_details,
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "DISPATCH_ERROR",
                        "message": str(exc),
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 12. Link incident to session and transition to COMPLETED
        now = timezone.now()
        session.associated_incident = incident
        session.status = SessionStatus.COMPLETED
        session.ended_at = now
        session.conversation_history.append({
            "role": "assistant",
            "message": (
                f"Emergency confirmed and reported successfully. Reference: {incident.incident_number}. "
                f"Destination: {incident.hospital.name}. Severity: {incident.get_severity_display()}."
            ),
            "timestamp": now.isoformat(),
        })
        session.save(update_fields=[
            "associated_incident",
            "status",
            "ended_at",
            "conversation_history",
            "updated_at",
        ])

        # 13. Telemetry bootstrap if trusted coordinates provided
        if trusted_gps:
            try:
                acc_val = serializer.validated_data.get("accuracy")
                record_ambulance_location(
                    incident=incident,
                    latitude=trusted_gps[0],
                    longitude=trusted_gps[1],
                    accuracy=round(float(acc_val), 2) if acc_val is not None else None,
                    user=request.user,
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Initial GPS recording skipped on confirmation: %s", e)

        # 14. Return standardized dispatch response
        patient_obj = incident.patients.first()
        return Response(
            {
                "success": True,
                "incident_id": str(incident.id),
                "incident_number": incident.incident_number,
                "status": incident.status,
                "status_display": incident.get_status_display(),
                "severity": incident.severity,
                "severity_display": incident.get_severity_display(),
                "hospital": {
                    "id": str(incident.hospital.id),
                    "name": incident.hospital.name,
                    "hospital_code": incident.hospital.hospital_code,
                    "address": incident.hospital.address,
                    "contact_number": incident.hospital.contact_number,
                },
                "ambulance": {
                    "id": str(incident.ambulance.id),
                    "vehicle_number": incident.ambulance.vehicle_number,
                },
                "patient": {
                    "name": patient_obj.name if patient_obj else "Unknown",
                    "age": patient_obj.age if patient_obj else None,
                    "gender": patient_obj.gender if patient_obj else "UNKNOWN",
                    "blood_group": patient_obj.blood_group if patient_obj else "",
                },
                "session_id": str(session.id),
                "session_status": session.status,
                "is_duplicate_confirmation": False,
                "message": f"Emergency incident {incident.incident_number} successfully created and dispatched.",
                "next_steps": [
                    "Proceed immediately to destination hospital",
                    "Hospital ER staff and police dispatch notified",
                    "Continuous GPS telemetry active",
                ],
            },
            status=status.HTTP_201_CREATED,
        )


class VoiceSessionEndView(APIView):
    """
    POST: Gracefully concludes or abandons an active voice agent session.
    Sets status to COMPLETED (default) or ABANDONED, and records ended_at timestamp.
    """

    permission_classes = [IsVerifiedAmbulanceDriver]

    def post(self, request, session_id):
        try:
            session = VoiceAgentSession.objects.get(pk=session_id, driver=request.user)
        except (VoiceAgentSession.DoesNotExist, ValueError):
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Voice session not found or access denied.",
                    },
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        requested_status = (
            request.data.get("status", SessionStatus.COMPLETED)
            if request.data
            else SessionStatus.COMPLETED
        )
        if requested_status not in [SessionStatus.COMPLETED, SessionStatus.ABANDONED]:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_STATUS",
                        "message": f"Status must be '{SessionStatus.COMPLETED}' or '{SessionStatus.ABANDONED}'.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Idempotent response if already in a terminated state
        if session.status in [SessionStatus.COMPLETED, SessionStatus.ABANDONED]:
            return Response(
                {
                    "success": True,
                    "session_id": str(session.id),
                    "status": session.status,
                    "message": f"Voice session was already {session.status.lower()}.",
                },
                status=status.HTTP_200_OK,
            )

        session.status = requested_status
        session.ended_at = timezone.now()
        session.save(update_fields=["status", "ended_at", "updated_at"])

        return Response(
            {
                "success": True,
                "session_id": str(session.id),
                "status": session.status,
                "message": f"Voice session successfully ended as {session.status.lower()}.",
            },
            status=status.HTTP_200_OK,
        )

