# SERTOS REST API Documentation

**API Base URL:** `/api/v1/`  
**Data Format:** JSON (`application/json`)  
**Standard Authentication:** `Authorization: Bearer <JWT_ACCESS_TOKEN>`  
**Hardware Authentication:** `X-Device-Token: <ESP32_SECRET_TOKEN>`  

---

## 1. Unified Response Envelope

All API endpoints return data formatted according to the unified SERTOS envelope:

```json
{
  "success": true,
  "data": { ... },
  "message": "Operation completed successfully.",
  "timestamp": "2026-11-12T16:00:00Z"
}
```

Error responses adhere to:
```json
{
  "success": false,
  "errors": {
    "field_name": ["Specific validation error message."]
  },
  "message": "Invalid request payload.",
  "timestamp": "2026-11-12T16:00:00Z"
}
```

---

## 2. API Endpoints Catalog

### 2.1 Identity & Authentication (`/api/auth/`) [Fully Implemented, Routed, Validated & Hardened - Steps 3.1–3.9]

> **Security & RBAC Status:** 100% Validated across all 4 roles (`ADMIN`, `AMBULANCE_DRIVER`, `HOSPITAL_STAFF`, `POLICE_DISPATCHER`). 57 automated tests passing.
> **Security Hardening (Task 3.9):** Model-level default role secured to `AMBULANCE_DRIVER` (least privilege); framework-level exception wrapping (`sertos_exception_handler`) active for all 400/401/403/404/405 errors. Zero unresolved security findings.

| Method | Endpoint | Route Name | Permission | Description |
|---|---|---|---|---|
| `POST` | `/api/auth/login/` | `login` | `AllowAny` | Authenticate user & issue tokens. Rejects unverified accounts. |
| `POST` | `/api/auth/token/refresh/` | `token_refresh` | `AllowAny` | Refresh access token. Verifies live database active & verified status. |
| `POST` | `/api/auth/logout/` | `logout` | `IsAuthenticated` | Blacklist refresh token after verifying user token ownership. |
| `POST` | `/api/auth/register/` | `register` | `AllowAny` | Public self-registration for unverified ambulance drivers. |
| `GET` | `/api/auth/profile/` | `profile` | `IsAuthenticated` | Inspect authenticated user's profile. |
| `PATCH` | `/api/auth/profile/` | `profile` | `IsAuthenticated` | Update non-critical profile fields (role/verified immutable). |

#### 1. User Login
* **Endpoint:** `POST /api/auth/login/`
* **Permission:** `AllowAny`
* **Request Payload:**
  ```json
  {
    "username": "driver_john",
    "password": "SecurePassword123!@#"
  }
  ```
* **Success Response (HTTP 200):**
  ```json
  {
    "success": true,
    "data": {
      "refresh": "eyJhbGciOi...",
      "access": "eyJhbGciOi...",
      "user": {
        "id": 1,
        "username": "driver_john",
        "role": "AMBULANCE_DRIVER",
        "is_verified": true
      }
    },
    "message": "Authentication successful.",
    "timestamp": "2026-11-13T05:15:33Z"
  }
  ```

#### 2. Token Refresh
* **Endpoint:** `POST /api/auth/token/refresh/`
* **Permission:** `AllowAny`
* **Request Payload:**
  ```json
  {
    "refresh": "eyJhbGciOi..."
  }
  ```
* **Success Response (HTTP 200):**
  ```json
  {
    "success": true,
    "data": {
      "access": "eyJhbGciOi...",
      "refresh": "eyJhbGciOi..."
    },
    "message": "Access token refreshed successfully.",
    "timestamp": "2026-11-13T05:15:33Z"
  }
  ```

#### 3. User Logout & Token Blacklist
* **Endpoint:** `POST /api/auth/logout/`
* **Permission:** `IsAuthenticated` (Bearer token required)
* **Request Payload:**
  ```json
  {
    "refresh": "eyJhbGciOi..."
  }
  ```
* **Success Response (HTTP 200):**
  ```json
  {
    "success": true,
    "data": {},
    "message": "Logged out successfully. Refresh token invalidated.",
    "timestamp": "2026-11-13T05:15:33Z"
  }
  ```

#### 4. Controlled User Registration
* **Endpoint:** `POST /api/auth/register/`
* **Permission:** `AllowAny`
* **Request Payload:**
  ```json
  {
    "username": "new_driver",
    "email": "driver@sertos.local",
    "password": "StrongPassword123!@#",
    "phone_number": "+91-9876543210",
    "badge_or_employee_id": "AMB-DL-001"
  }
  ```
* **Success Response (HTTP 201):**
  ```json
  {
    "success": true,
    "data": {
      "id": 2,
      "username": "new_driver",
      "email": "driver@sertos.local",
      "role": "AMBULANCE_DRIVER",
      "phone_number": "+91-9876543210",
      "badge_or_employee_id": "AMB-DL-001",
      "is_verified": false
    },
    "message": "Account registered successfully. Awaiting administrative verification.",
    "timestamp": "2026-11-13T05:15:33Z"
  }
  ```

#### 5. User Profile (Retrieve & Update)
* **Endpoint:** `GET /api/auth/profile/` | `PATCH /api/auth/profile/`
* **Permission:** `IsAuthenticated` (Bearer token required)
* **PATCH Request Payload:**
  ```json
  {
    "phone_number": "+91-9988776655",
    "email": "updated_email@sertos.local"
  }
  ```
* **Success Response (HTTP 200):**
  ```json
  {
    "success": true,
    "data": {
      "id": 1,
      "username": "driver_john",
      "email": "updated_email@sertos.local",
      "role": "AMBULANCE_DRIVER",
      "phone_number": "+91-9988776655",
      "badge_or_employee_id": "AMB-DL-001",
      "is_verified": true,
      "date_joined": "2026-11-12T15:00:00Z"
    },
    "message": "User profile retrieved successfully.",
    "timestamp": "2026-11-13T05:15:33Z"
  }
  ```

### 2.2 Emergencies Management (`/api/emergencies/`) [Implemented & Tested - Task 4.2]

> **Security & RBAC Status:** 
> - `POST`: Restricted to verified, active `AMBULANCE_DRIVER` accounts with an active, available assigned ambulance. Clients cannot supply `reporting_driver` or `ambulance`; both are derived from `request.user`.
> - `GET` (List & Detail): Ambulance drivers are strictly scoped to their own reported incidents. System administrators (`ADMIN` / superuser) can inspect all incidents. `HOSPITAL_STAFF` and `POLICE_DISPATCHER` are rejected with HTTP 403 Forbidden.
> - Transactional Integrity: All incident creations and nested patient creations execute inside `transaction.atomic()`, rolling back completely if validation fails.

| Method | Endpoint | Route Name | Permission | Description |
|---|---|---|---|---|
| `POST` | `/api/emergencies/` | `incident_list_create` | `IsAmbulanceDriver` | Driver reports an emergency incident with optional nested patient triage data. |
| `GET` | `/api/emergencies/` | `incident_list_create` | `IsAmbulanceDriver` \| `IsSystemAdmin` | List incidents (scoped to driver's own; admin sees all). |
| `GET` | `/api/emergencies/<uuid:pk>/` | `incident_detail` | `IsAmbulanceDriver` \| `IsSystemAdmin` | Retrieve full incident details (driver gets 404 for other drivers' incidents; admin sees all). |
| `PATCH` | `/api/emergencies/<uuid:pk>/status/` | `incident_status_update` | `IsAmbulanceDriver` | Transition incident lifecycle status (driver only; validated FSM transitions). |
| `POST` | `/api/emergencies/<uuid:pk>/location/` | `incident_location` | `EmergencyIncidentLocationPermission` | Driver ingests high-frequency GPS coordinate ping for active incident. |
| `GET` | `/api/emergencies/<uuid:pk>/location/` | `incident_location` | `EmergencyIncidentLocationPermission` | Retrieve latest GPS ping (driver, affiliated hospital, police, admin). |
| `GET` | `/api/emergencies/<uuid:pk>/locations/` | `incident_location_history` | `EmergencyIncidentLocationPermission` | Retrieve ordered GPS breadcrumbs with optional `?limit=` (default 50, max 200). |

#### 1. Report Emergency Incident
* **Endpoint:** `POST /api/emergencies/`
* **Permission:** Authenticated, verified `AMBULANCE_DRIVER` with active assigned vehicle.
* **Request Payload:**
  ```json
  {
    "hospital_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "severity": "CRITICAL",
    "description": "Multi-vehicle collision on Outer Ring Road.",
    "patient": {
      "name": "Ramesh Rao",
      "age": 42,
      "gender": "MALE",
      "blood_group": "O+",
      "medical_notes": "Blunt chest trauma, stable vitals."
    }
  }
  ```
* **Success Response (HTTP 201 Created):**
  ```json
  {
    "success": true,
    "data": {
      "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "incident_number": "INC-20261114-A1B2C3",
      "reporting_driver": {
        "id": 2,
        "username": "driver_alpha",
        "first_name": "Ravi",
        "last_name": "Kumar",
        "role": "AMBULANCE_DRIVER",
        "phone_number": "+91-9876543210",
        "badge_or_employee_id": "AMB-BLR-101",
        "is_verified": true
      },
      "ambulance": {
        "id": "c1a2b3c4-d5e6-7890-abcd-ef1234567890",
        "vehicle_number": "KA-01-EQ-5001",
        "vehicle_type": "Advanced Life Support (ALS)",
        "is_available": true,
        "is_active": true
      },
      "hospital": {
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "name": "City Central Emergency Care",
        "hospital_code": "HOSP-API-001",
        "address": "100 Main St, Bangalore",
        "contact_number": "+91-80-23456789",
        "latitude": "12.971598",
        "longitude": "77.594562",
        "is_active": true
      },
      "severity": "CRITICAL",
      "severity_display": "Critical (Immediate Life Threat)",
      "status": "REPORTED",
      "status_display": "Reported",
      "description": "Multi-vehicle collision on Outer Ring Road.",
      "patients": [
        {
          "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
          "name": "Ramesh Rao",
          "age": 42,
          "gender": "MALE",
          "blood_group": "O+",
          "medical_notes": "Blunt chest trauma, stable vitals.",
          "created_at": "2026-11-14T15:10:00Z",
          "updated_at": "2026-11-14T15:10:00Z"
        }
      ],
      "assigned_at": null,
      "in_transit_at": null,
      "arrived_at": null,
      "closed_at": null,
      "cancelled_at": null,
      "created_at": "2026-11-14T15:10:00Z",
      "updated_at": "2026-11-14T15:10:00Z"
    },
    "message": "Emergency incident reported successfully.",
    "timestamp": "2026-11-14T15:10:00Z"
  }
  ```

#### 2. List Emergency Incidents
* **Endpoint:** `GET /api/emergencies/`
* **Permission:** Authenticated `AMBULANCE_DRIVER` (scoped to own) or `ADMIN` (unrestricted).
* **Success Response (HTTP 200 OK):**
  ```json
  {
    "success": true,
    "data": [
      {
        "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "incident_number": "INC-20261114-A1B2C3",
        "severity": "CRITICAL",
        "severity_display": "Critical (Immediate Life Threat)",
        "status": "REPORTED",
        "status_display": "Reported",
        "description": "Multi-vehicle collision on Outer Ring Road.",
        "hospital_name": "City Central Emergency Care",
        "hospital_code": "HOSP-API-001",
        "ambulance_vehicle_number": "KA-01-EQ-5001",
        "patient_count": 1,
        "created_at": "2026-11-14T15:10:00Z",
        "updated_at": "2026-11-14T15:10:00Z"
      }
    ],
    "message": "Emergency incidents retrieved successfully.",
    "timestamp": "2026-11-14T15:10:00Z"
  }
  ```

#### 3. Retrieve Emergency Incident Details
* **Endpoint:** `GET /api/emergencies/<uuid:pk>/`
* **Permission:** Authenticated `AMBULANCE_DRIVER` (own incident) or `ADMIN` (unrestricted).
* **Success Response (HTTP 200 OK):** Returns detailed incident envelope (identical format to Create response).
* **Error Response for other driver's incident (HTTP 404 Not Found):**
  ```json
  {
    "success": false,
    "data": {},
    "message": "Not found.",
    "errors": {
      "detail": "No EmergencyIncident matches the given query."
    },
    "detail": "Not found.",
    "timestamp": "2026-11-14T15:10:00Z"
  }
  ```

#### 4. Update Emergency Incident Status Lifecycle
* **Endpoint:** `PATCH /api/emergencies/<uuid:pk>/status/`
* **Permission:** Authenticated `AMBULANCE_DRIVER` (strictly restricted to the driver who reported this incident).
  * `ADMIN` users may inspect via GET but receive `403 Forbidden` on PATCH to enforce lifecycle integrity.
  * `HOSPITAL_STAFF` and `POLICE_DISPATCHER` receive `403 Forbidden`.
  * Other ambulance drivers receive `404 Not Found` (scoped queryset).
  * Unauthenticated requests receive `401 Unauthorized`.
* **State Machine Rules (`VALID_TRANSITIONS`):**
  * `REPORTED` $\rightarrow$ `ASSIGNED` or `CANCELLED`
  * `ASSIGNED` $\rightarrow$ `IN_TRANSIT` or `CANCELLED`
  * `IN_TRANSIT` $\rightarrow$ `ARRIVED` or `CANCELLED`
  * `ARRIVED` $\rightarrow$ `CLOSED` or `CANCELLED`
  * `CLOSED` $\rightarrow$ Terminal state (cannot transition or reopen)
  * `CANCELLED` $\rightarrow$ Terminal state (cannot transition or reopen)
* **Concurrency & Safety:**
  * Uses `transaction.atomic()` with row-level locking (`select_for_update()`).
  * Automatic milestone timestamps set on model `save()` (`assigned_at`, `in_transit_at`, `arrived_at`, `closed_at`, `cancelled_at`).
* **Request Payload Example:**
  ```json
  {
    "status": "IN_TRANSIT"
  }
  ```
* **Success Response (HTTP 200 OK):**
  ```json
  {
    "success": true,
    "data": {
      "id": "c3d4e5f6-a7b8-9012-cdef-1234567890ab",
      "incident_number": "INC-20261114-A1B2C3",
      "reporting_driver": {
        "id": "e4f5a6b7-c8d9-0123-ef01-234567890abc",
        "username": "paramedic_ramesh",
        "first_name": "Ramesh",
        "last_name": "Kumar",
        "role": "AMBULANCE_DRIVER",
        "phone_number": "+919876543210",
        "badge_or_employee_id": "KA-AMB-4091",
        "is_verified": true
      },
      "ambulance": {
        "id": "b2c3d4e5-f6a7-8901-bcde-f1234567890a",
        "vehicle_number": "KA-01-EQ-9999",
        "vehicle_type": "Advanced Life Support",
        "is_available": true,
        "is_active": true
      },
      "hospital": {
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "name": "Manipal Emergency Care",
        "hospital_code": "HOSP-MAN-01",
        "address": "HAL Airport Road, Bangalore",
        "contact_number": "+918022223333",
        "latitude": "12.959172",
        "longitude": "77.654884",
        "is_active": true
      },
      "severity": "CRITICAL",
      "severity_display": "Critical (Immediate Life Threat)",
      "status": "IN_TRANSIT",
      "status_display": "In Transit",
      "description": "Multi-vehicle trauma incident",
      "patients": [
        {
          "id": "d4e5f6a7-b8c9-0123-def0-1234567890cd",
          "name": "Ramesh Rao",
          "age": 42,
          "gender": "MALE",
          "blood_group": "O+",
          "medical_notes": "Blunt chest trauma, vitals stable",
          "created_at": "2026-11-14T15:00:00Z",
          "updated_at": "2026-11-14T15:00:00Z"
        }
      ],
      "assigned_at": "2026-11-14T15:05:00Z",
      "in_transit_at": "2026-11-14T15:15:00Z",
      "arrived_at": null,
      "closed_at": null,
      "cancelled_at": null,
      "created_at": "2026-11-14T15:00:00Z",
      "updated_at": "2026-11-14T15:15:00Z"
    },
    "message": "Emergency incident status updated successfully.",
    "timestamp": "2026-11-14T15:15:00Z"
  }
  ```
* **Error Response Example — Invalid Transition (HTTP 400 Bad Request):**
  ```json
  {
    "success": false,
    "data": {},
    "message": "Validation error.",
    "errors": {
      "status": [
        "Invalid status transition from 'REPORTED' to 'IN_TRANSIT'."
      ]
    },
    "detail": "Invalid status transition from 'REPORTED' to 'IN_TRANSIT'.",
    "timestamp": "2026-11-14T15:15:00Z"
  }
  ```
* **Error Response Example — Terminal State Reopen (HTTP 400 Bad Request):**
  ```json
  {
    "success": false,
    "data": {},
    "message": "Validation error.",
    "errors": {
      "status": [
        "Cannot update incident in terminal state 'CLOSED'."
      ]
    },
    "detail": "Cannot update incident in terminal state 'CLOSED'.",
    "timestamp": "2026-11-14T15:15:00Z"
  }
  ```

#### 5. Submit Ambulance GPS Location Ping
* **Endpoint:** `POST /api/emergencies/<uuid:pk>/location/`
* **Route Name:** `emergencies:incident_location`
* **Permission:** Authenticated, verified, active `AMBULANCE_DRIVER` strictly assigned as the reporting driver of this incident.
* **Incident Precondition:** The emergency incident must be in an active lifecycle state (rejects terminal `CLOSED` or `CANCELLED` states with HTTP 400).
* **Payload Validation:**
  * `latitude`: Decimal degrees, required, strictly within `[-90.000000, 90.000000]`.
  * `longitude`: Decimal degrees, required, strictly within `[-180.000000, 180.000000]`.
  * `accuracy`: Float in metres, optional, strictly $\ge 0.0$.
  * `recorded_at`: ISO 8601 timestamp reported by hardware, optional.
  * `server_received_at`: Authoritative UTC server timestamp recorded automatically at ingestion.
  * Vehicle and incident association are strictly verified; ambulance assignment is derived directly from the verified incident.
* **Privacy & Triage Isolation:** Response strictly excludes confidential patient triage details and medical notes.
* **Request Payload Example:**
  ```json
  {
    "latitude": 12.972500,
    "longitude": 77.595500,
    "accuracy": 4.8,
    "recorded_at": "2026-11-14T10:00:00Z"
  }
  ```
* **Success Response (HTTP 201 Created):**
  ```json
  {
    "success": true,
    "data": {
      "id": "e5f6a7b8-c9d0-1234-ef01-567890abcdef",
      "incident_id": "c3d4e5f6-a7b8-9012-cdef-1234567890ab",
      "incident_number": "INC-20261114-A1B2C3",
      "ambulance_id": "b2c3d4e5-f6a7-8901-bcde-f1234567890a",
      "ambulance_vehicle_number": "KA-01-EQ-9999",
      "latitude": "12.972500",
      "longitude": "77.595500",
      "accuracy": 4.8,
      "recorded_at": "2026-11-14T10:00:00Z",
      "server_received_at": "2026-11-14T10:00:00.123456Z"
    },
    "message": "Ambulance GPS location updated successfully.",
    "timestamp": "2026-11-14T10:00:00Z"
  }
  ```
* **Error Response — Terminal Incident (HTTP 400 Bad Request):**
  ```json
  {
    "success": false,
    "data": {},
    "message": "status: Cannot update location for incident in terminal state 'CLOSED'.",
    "errors": {
      "status": [
        "Cannot update location for incident in terminal state 'CLOSED'."
      ]
    },
    "detail": "status: Cannot update location for incident in terminal state 'CLOSED'.",
    "timestamp": "2026-11-14T10:00:00Z"
  }
  ```
* **Error Response — Non-Driver Role Attempting POST (HTTP 403 Forbidden):**
  ```json
  {
    "success": false,
    "data": {},
    "message": "Access denied: Only verified ambulance drivers may submit GPS location updates.",
    "errors": {
      "detail": "Access denied: Only verified ambulance drivers may submit GPS location updates."
    },
    "detail": "Access denied: Only verified ambulance drivers may submit GPS location updates.",
    "timestamp": "2026-11-14T10:00:00Z"
  }
  ```

#### 6. Retrieve Latest Ambulance GPS Location
* **Endpoint:** `GET /api/emergencies/<uuid:pk>/location/`
* **Route Name:** `emergencies:incident_location`
* **Permissions & Scoping:**
  * Authenticated, verified `AMBULANCE_DRIVER` (scoped to incidents they reported).
  * Authenticated, verified `HOSPITAL_STAFF` (scoped to incidents assigned to their affiliated hospital).
  * Authenticated, verified `POLICE_DISPATCHER` (city-wide emergency preemption).
  * Authenticated `ADMIN` (full system oversight).
  * Out-of-scope or cross-tenant access returns **HTTP 404 Not Found**.
  * Unauthenticated requests return **HTTP 401 Unauthorized**.
* **Success Response — Active Location (HTTP 200 OK):**
  ```json
  {
    "success": true,
    "data": {
      "id": "e5f6a7b8-c9d0-1234-ef01-567890abcdef",
      "incident_id": "c3d4e5f6-a7b8-9012-cdef-1234567890ab",
      "incident_number": "INC-20261114-A1B2C3",
      "ambulance_id": "b2c3d4e5-f6a7-8901-bcde-f1234567890a",
      "ambulance_vehicle_number": "KA-01-EQ-9999",
      "latitude": "12.972500",
      "longitude": "77.595500",
      "accuracy": 4.8,
      "recorded_at": "2026-11-14T10:00:00Z",
      "server_received_at": "2026-11-14T10:00:00.123456Z"
    },
    "message": "Latest ambulance GPS location retrieved successfully.",
    "timestamp": "2026-11-14T10:00:00Z"
  }
  ```
* **Success Response — Empty State / No Pings Yet (HTTP 200 OK):**
  ```json
  {
    "success": true,
    "data": {},
    "message": "No GPS location recorded for this incident yet.",
    "timestamp": "2026-11-14T10:00:00Z"
  }
  ```

#### 7. Retrieve Ambulance GPS Location History
* **Endpoint:** `GET /api/emergencies/<uuid:pk>/locations/`
* **Route Name:** `emergencies:incident_location_history`
* **Query Parameters (Optional):**
  * `limit`: Integer specifying maximum breadcrumb records to return (default: `50`, maximum: `200`). Invalid values default safely to 50.
* **Permissions & Scoping:** Same RBAC authorization matrix as latest location (Reporting driver, affiliated hospital staff, police dispatcher, system admin).
* **Ordering:** Reverse chronological order by `server_received_at` (newest first).
* **Success Response (HTTP 200 OK):**
  ```json
  {
    "success": true,
    "data": [
      {
        "id": "e5f6a7b8-c9d0-1234-ef01-567890abcdef",
        "incident_id": "c3d4e5f6-a7b8-9012-cdef-1234567890ab",
        "incident_number": "INC-20261114-A1B2C3",
        "ambulance_id": "b2c3d4e5-f6a7-8901-bcde-f1234567890a",
        "ambulance_vehicle_number": "KA-01-EQ-9999",
        "latitude": "12.973000",
        "longitude": "77.596000",
        "accuracy": 3.5,
        "recorded_at": "2026-11-14T10:05:00Z",
        "server_received_at": "2026-11-14T10:05:00.654321Z"
      },
      {
        "id": "d4e5f6a7-b8c9-0123-def0-1234567890cd",
        "incident_id": "c3d4e5f6-a7b8-9012-cdef-1234567890ab",
        "incident_number": "INC-20261114-A1B2C3",
        "ambulance_id": "b2c3d4e5-f6a7-8901-bcde-f1234567890a",
        "ambulance_vehicle_number": "KA-01-EQ-9999",
        "latitude": "12.972500",
        "longitude": "77.595500",
        "accuracy": 4.8,
        "recorded_at": "2026-11-14T10:00:00Z",
        "server_received_at": "2026-11-14T10:00:00.123456Z"
      }
    ],
    "message": "Ambulance location history retrieved successfully.",
    "timestamp": "2026-11-14T10:05:01Z"
  }
  ```

---

## 3. Hospital Emergency Dashboard APIs (`/api/hospital/`)

Strictly restricted to authenticated, verified, active users with role `HOSPITAL_STAFF`. Staff members see only emergency incidents directed to their associated hospital facility.

### 1. List Hospital Emergency Incidents
* **Endpoint:** `GET /api/hospital/incidents/`
* **Query Parameters (Optional):**
  * `status`: Filter by operational status (e.g. `IN_TRANSIT`, `ARRIVED`, `REPORTED`, `CLOSED`).
  * `severity`: Filter by triage severity (e.g. `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
* **Permissions:** Verified `HOSPITAL_STAFF` with active hospital affiliation.
* **Success Response (HTTP 200 OK):**
  ```json
  {
    "success": true,
    "data": [
      {
        "id": "c3d4e5f6-a7b8-9012-cdef-1234567890ab",
        "incident_number": "INC-20261114-DASH01",
        "severity": "CRITICAL",
        "severity_display": "Critical (Immediate Life Threat)",
        "status": "IN_TRANSIT",
        "status_display": "In Transit",
        "description": "Major vehicular crash",
        "hospital_name": "City Hospital Central",
        "hospital_code": "HOSP-CTY-01",
        "ambulance_vehicle_number": "KA-01-EQ-9001",
        "ambulance_vehicle_type": "Advanced Life Support",
        "patient_count": 1,
        "assigned_at": "2026-11-14T15:05:00Z",
        "in_transit_at": "2026-11-14T15:15:00Z",
        "arrived_at": null,
        "closed_at": null,
        "cancelled_at": null,
        "created_at": "2026-11-14T15:00:00Z",
        "updated_at": "2026-11-14T15:15:00Z"
      }
    ],
    "message": "Hospital emergency incidents retrieved successfully.",
    "timestamp": "2026-11-14T15:15:00Z"
  }
  ```

### 2. Retrieve Hospital Incident Details
* **Endpoint:** `GET /api/hospital/incidents/<uuid:pk>/`
* **Permissions:** Verified `HOSPITAL_STAFF` affiliated with the incident's destination hospital.
* **Success Response (HTTP 200 OK):** Returns complete incident details including nested patient triage data and clinical `medical_notes`.
* **Error Response — Another Hospital's Incident (HTTP 404 Not Found):**
  ```json
  {
    "success": false,
    "data": {},
    "message": "Not found.",
    "errors": {
      "detail": "No EmergencyIncident matches the given query."
    },
    "detail": "Not found.",
    "timestamp": "2026-11-14T15:15:00Z"
  }
  ```

---

## 4. Police Traffic Coordination Dashboard APIs (`/api/police/`)

Strictly restricted to authenticated, verified, active users with role `POLICE_DISPATCHER`. Provides city-wide incident visibility across all hospitals for traffic preemption and corridor clearance.

### 1. List Police Emergency Incidents
* **Endpoint:** `GET /api/police/incidents/`
* **Query Parameters (Optional):**
  * `status`: Filter by operational status (e.g. `IN_TRANSIT`, `ARRIVED`).
  * `severity`: Filter by triage severity (e.g. `CRITICAL`, `HIGH`).
* **Permissions:** Verified `POLICE_DISPATCHER`.
* **Success Response (HTTP 200 OK):** Returns all active emergency incidents across hospitals with destination GPS coordinates and ambulance identification.

### 2. Retrieve Police Incident Details
* **Endpoint:** `GET /api/police/incidents/<uuid:pk>/`
* **Permissions:** Verified `POLICE_DISPATCHER`.
* **Privacy & Compliance:** Strictly **excludes** confidential patient `medical_notes` from the serialized response.
* **Success Response (HTTP 200 OK):**
  ```json
  {
    "success": true,
    "data": {
      "id": "c3d4e5f6-a7b8-9012-cdef-1234567890ab",
      "incident_number": "INC-20261114-DASH01",
      "reporting_driver": {
        "id": "e4f5a6b7-c8d9-0123-ef01-234567890abc",
        "username": "driver_dash",
        "role": "AMBULANCE_DRIVER",
        "phone_number": "+919876543210",
        "badge_or_employee_id": "AMB-KA-01",
        "is_verified": true
      },
      "ambulance": {
        "id": "b2c3d4e5-f6a7-8901-bcde-f1234567890a",
        "vehicle_number": "KA-01-EQ-9001",
        "vehicle_type": "Advanced Life Support",
        "is_available": true,
        "is_active": true
      },
      "hospital": {
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "name": "City Hospital Central",
        "hospital_code": "HOSP-CTY-01",
        "address": "100 Central Road, Bangalore",
        "latitude": "12.971598",
        "longitude": "77.594562",
        "is_active": true
      },
      "severity": "CRITICAL",
      "severity_display": "Critical (Immediate Life Threat)",
      "status": "IN_TRANSIT",
      "status_display": "In Transit",
      "description": "Major vehicular crash",
      "patients": [
        {
          "id": "d4e5f6a7-b8c9-0123-def0-1234567890cd",
          "name": "Arun Kumar",
          "age": 35,
          "gender": "MALE",
          "blood_group": "O+",
          "created_at": "2026-11-14T15:00:00Z",
          "updated_at": "2026-11-14T15:00:00Z"
        }
      ],
      "assigned_at": "2026-11-14T15:05:00Z",
      "in_transit_at": "2026-11-14T15:15:00Z",
      "arrived_at": null,
      "closed_at": null,
      "cancelled_at": null,
      "created_at": "2026-11-14T15:00:00Z",
      "updated_at": "2026-11-14T15:15:00Z"
    },
    "message": "Police emergency incident retrieved successfully.",
    "timestamp": "2026-11-14T15:15:00Z"
  }
  ```

---

## 5. Notification & Internal Event APIs (`/api/notifications/`)

Provides real-time event-driven notifications to authenticated, active, verified users according to their role and scope.
* Hospital staff (`HOSPITAL_STAFF`) receive notifications for emergencies assigned to their hospital.
* Police dispatchers (`POLICE_DISPATCHER`) receive notifications for all emergency incidents across the city.
* Notification endpoints enforce strict user isolation (users can only access notifications addressed to them).
* Sensitive patient medical triage notes are strictly excluded from all notifications and event payloads.
* Downstream external channels (SMS, push, AI voice) integrate via transactional `on_commit` hooks (`dispatch_external_notification`).

| Method | Endpoint | Route Name | Permission | Description |
|---|---|---|---|---|
| `GET` | `/api/notifications/` | `notification_list` | `IsVerifiedUserPermission` | Paginated list of user's own notifications (`?is_read=true/false`). |
| `PATCH` | `/api/notifications/read-all/` | `notification_read_all` | `IsVerifiedUserPermission` | Mark all unread notifications for the user as read. |
| `GET` | `/api/notifications/<uuid:pk>/` | `notification_detail` | `IsVerifiedUserPermission` | Retrieve detail of a notification owned by the user (404 otherwise). |
| `PATCH` | `/api/notifications/<uuid:pk>/read/` | `notification_mark_read` | `IsVerifiedUserPermission` | Mark single notification as read (idempotent, 404 for other users). |

### 1. List User Notifications
* **Endpoint:** `GET /api/notifications/`
* **Query Parameters (Optional):**
  * `is_read`: Boolean filter (`true` for read, `false` for unread).
  * `page`: Page number (default: 1, pagination size: 20, max: 100).
* **Permissions:** Authenticated, active, verified user.
* **Success Response (HTTP 200 OK):** Paginated list of notifications belonging exclusively to the requesting user.
  ```json
  {
    "success": true,
    "data": {
      "count": 1,
      "next": null,
      "previous": null,
      "results": [
        {
          "id": "e5f6a7b8-c9d0-1234-ef01-234567890abc",
          "incident_id": "c3d4e5f6-a7b8-9012-cdef-1234567890ab",
          "incident_number": "INC-20261114-EVT01",
          "event_type": "EMERGENCY_REPORTED",
          "title": "New Emergency Incident: INC-20261114-EVT01",
          "message": "Emergency INC-20261114-EVT01 reported with CRITICAL severity destined for City Hospital Central.",
          "is_read": false,
          "created_at": "2026-11-14T17:00:00Z",
          "read_at": null
        }
      ]
    },
    "message": "Notifications retrieved successfully.",
    "timestamp": "2026-11-14T17:05:00Z"
  }
  ```

### 2. Retrieve Notification Detail
* **Endpoint:** `GET /api/notifications/<uuid:pk>/`
* **Permissions:** Authenticated, active, verified recipient.
* **Security & Isolation:** If the notification does not exist or belongs to another user, returns `404 Not Found`.
* **Success Response (HTTP 200 OK):**
  ```json
  {
    "success": true,
    "data": {
      "id": "e5f6a7b8-c9d0-1234-ef01-234567890abc",
      "incident_id": "c3d4e5f6-a7b8-9012-cdef-1234567890ab",
      "incident_number": "INC-20261114-EVT01",
      "event_type": "EMERGENCY_REPORTED",
      "title": "New Emergency Incident: INC-20261114-EVT01",
      "message": "Emergency INC-20261114-EVT01 reported with CRITICAL severity destined for City Hospital Central.",
      "is_read": false,
      "created_at": "2026-11-14T17:00:00Z",
      "read_at": null
    },
    "message": "Notification retrieved successfully.",
    "timestamp": "2026-11-14T17:05:00Z"
  }
  ```

### 3. Mark Single Notification as Read
* **Endpoint:** `PATCH /api/notifications/<uuid:pk>/read/`
* **Permissions:** Authenticated, active, verified recipient.
* **Security & Isolation:** Idempotent operation. Automatically sets `is_read = true` and `read_at = timezone.now()`. Accessing another user's notification returns `404 Not Found`.
* **Success Response (HTTP 200 OK):**
  ```json
  {
    "success": true,
    "data": {
      "id": "e5f6a7b8-c9d0-1234-ef01-234567890abc",
      "incident_id": "c3d4e5f6-a7b8-9012-cdef-1234567890ab",
      "incident_number": "INC-20261114-EVT01",
      "event_type": "EMERGENCY_REPORTED",
      "title": "New Emergency Incident: INC-20261114-EVT01",
      "message": "Emergency INC-20261114-EVT01 reported with CRITICAL severity destined for City Hospital Central.",
      "is_read": true,
      "created_at": "2026-11-14T17:00:00Z",
      "read_at": "2026-11-14T17:06:00Z"
    },
    "message": "Notification marked as read.",
    "timestamp": "2026-11-14T17:06:00Z"
  }
  ```

### 4. Mark All Notifications as Read
* **Endpoint:** `PATCH /api/notifications/read-all/`
* **Permissions:** Authenticated, active, verified recipient.
* **Behavior:** Updates all unread notifications for the calling user in a single atomic query.
* **Success Response (HTTP 200 OK):**
  ```json
  {
    "success": true,
    "data": {
      "updated_count": 5
    },
    "message": "5 notifications marked as read.",
    "timestamp": "2026-11-14T17:06:00Z"
  }
  ```

---

### 2.3 Ambulance Android Client (`/api/v1/ambulances/`)
* `POST /api/v1/ambulances/trips/{id}/telemetry/` — Ingests GPS telemetry (lat, lng, speed, heading).
* `PATCH /api/v1/ambulances/trips/{id}/status/` — Updates trip milestone (`ACCEPTED`, `EN_ROUTE`, `PATIENT_ONBOARD`, `ARRIVED`).
* `POST /api/v1/ambulances/trips/{id}/triage/` — Submits patient vitals (heart rate, BP, SpO2, consciousness).

### 2.4 Hospital Web Dashboard (`/api/v1/hospitals/`)
* `GET  /api/v1/hospitals/incoming/` — Real-time list of ambulances en route with patient vitals and calculated ETA.
* `GET  /api/v1/hospitals/resources/` — Current bed/ventilator capacity.
* `PATCH /api/v1/hospitals/resources/` — Update resource counters (ICU, Emergency, Surgical).
* `POST /api/v1/hospitals/admissions/` — Confirms patient handoff from ambulance.

### 2.5 Police Dashboard & ESP32 Signals (`/api/v1/traffic/`)
* `GET  /api/v1/traffic/corridors/` — Active emergency corridors requiring traffic clearance.
* `POST /api/v1/traffic/corridors/{id}/override/` — Police manual authorization of Green Corridor.
* `POST /api/v1/traffic/esp32/heartbeat/` — Microcontroller hardware status ping with cryptographic device token.
* `GET  /api/v1/traffic/esp32/signal-command/` — Polling endpoint for ESP32 unit to receive signal state.
