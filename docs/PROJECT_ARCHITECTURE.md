# SERTOS Project Architecture & System Design

**System Name:** SERTOS (Smart Emergency Response & Traffic Optimization System)  
**Document Version:** 1.0.0  
**Status:** Baseline Established (Phase 2)  
**Author:** Backend Architecture Team  

---

## 1. Executive Architecture Overview

SERTOS is a high-availability, unified emergency response coordination platform designed to eliminate fatal delays during medical emergencies. It bridges five key stakeholders:

1. **Ambulance Android Application:** Telemetry streaming, vital sign updates, turn-by-turn navigation.
2. **Hospital Web Dashboard:** Real-time incoming emergency queue, triage vital preview, emergency bed/trauma capacity management.
3. **Police Web Dashboard:** Emergency corridor spatial visualization, active signal preemption authorization, manual signal override.
4. **AI Voice-Processing Module:** Voice call transcription, medical symptom extraction, automated priority scoring.
5. **ESP32-based Traffic Signal Prototype:** Hardware microcontroller nodes at traffic intersections receiving corridor clearance commands.

```
                                +-----------------------------+
                                |  AI Voice-Processing Engine |
                                | (Audio Ingest & Symptom NLP)|
                                +--------------+--------------+
                                               |
                                               | Webhook (JSON)
                                               v
+------------------------+      +------------------------------+      +------------------------+
| Ambulance Android App  |      |   CENTRAL SERTOS BACKEND     |      | Hospital Web Dashboard |
| (Kotlin / Jetpack)     |      |      Django 5.2 + DRF        |      | (React / Vite)         |
|                        |<---->|                              |<---->|                        |
| - GPS Telemetry Stream | HTTP | - Identity & RBAC (accounts) | HTTP | - Live Incoming Queue  |
| - Triage Status Input  | REST | - Incidents & Dispatch       | REST | - Bed Availability     |
+------------------------+      | - Telemetry & Fleet Tracking |      +------------------------+
                                | - Traffic & ESP32 Preemption |
                                | - Audit & Compliance Logs    |
                                +--------------+---------------+
                                               |
                                               | HTTP REST / Polling
                                               v
                                +------------------------------+
                                | Police Dashboard & ESP32     |
                                | - Corridor Approval Screen   |
                                | - ESP32 Hardware Signal Node |
                                +------------------------------+
```

---

## 2. Subsystem Communication Protocols

| Integration Point | Protocol | Authentication Method | Frequency / Trigger |
| :--- | :--- | :--- | :--- |
| **Ambulance Android App** | HTTP REST (JSON) | JWT Bearer Token | GPS telemetry streamed every 2–3 seconds; Triage on patient onboard. |
| **Hospital Web Dashboard** | HTTP REST (CORS enabled) | JWT Bearer Token (Role: `HOSPITAL_STAFF`) | Dashboard polled or event-driven; bed updates on admission. |
| **Police Web Dashboard** | HTTP REST (CORS enabled) | JWT Bearer Token (Role: `POLICE_DISPATCHER`) | Continuous active corridor monitoring; manual override commands. |
| **AI Voice Module** | HTTP Webhook (POST) | HMAC Signature / Webhook Secret | Triggered on emergency 911/112 call conclusion. |
| **ESP32 Signal Prototype** | HTTP REST (JSON) | Pre-Shared Hardware Device Token (`X-Device-Token`) | Heartbeat every 5 seconds; signal preemption status checks. |

---

## 3. Modular Django Application Architecture

The backend code is partitioned strictly by domain within `E:\sertos\apps/`:

```
E:\sertos\
├── apps/
│   ├── accounts/       # User identity, RBAC (Admin, Driver, Hospital, Police) [Phase 3 COMPLETE]
│   ├── emergencies/    # Hospital, Ambulance, EmergencyIncident, Patient models [Task 4.1D Models Implemented, 0002 Generated, NOT Yet Applied]
│   ├── ambulances/     # Ambulance fleet registry, Trip sessions, GPS telemetry [Planned]
│   ├── hospitals/      # Hospital facilities, Department bed counters, Patient admissions [Planned]
│   ├── traffic/        # Intersections, ESP32 device auth, Green corridor sessions [Planned]
│   └── audit_logs/     # System-wide compliance, state transitions, security events [Planned]
```

---

## 4. Security Architecture

1. **Role-Based Access Control (RBAC):** Every endpoint validates user role before returning or mutating data.
2. **Decoupled IoT Device Authentication:** ESP32 devices authenticate through unique hardware tokens and do not possess human user accounts.
3. **Environment Security:** Secrets (`SECRET_KEY`, database credentials) are stored exclusively in `.env` and excluded from Git via `.gitignore`.
4. **CORS Governance:** Restricted to approved web dashboard origins (`CORS_ALLOWED_ORIGINS`).
