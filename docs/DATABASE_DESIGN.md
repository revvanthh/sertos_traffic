# SERTOS Database Design & Entity Relationships

**Database Engine:** PostgreSQL 18.7  
**Database Name:** `sertos_db`  
**Host & Port:** `127.0.0.1:5432`  
**Document Version:** 1.0.0  

---

## 1. Entity-Relationship Diagram (Conceptual ERD)

```
                     +------------------------+
                     |     accounts_user      |
                     | (Custom User Model)    |
                     | id (PK)                |
                     | role (ADMIN, DRIVER..) |
                     +-----------+------------+
                                 |
                                 | 1
                                 |
                                 | creates / assigned
                                 v *
+--------------------+      +--------------------+      +-----------------------+
|  emergencies_call  | 1  * |  emergencies_inc   | *  1 |  hospitals_hospital   |
| (Voice Call Log)   |----->| (Emergency Incident|----->| id (PK)               |
| transcript, audio  |      |  status, severity) |      | name, location, beds  |
+--------------------+      +---------+----------+      +-----------+-----------+
                                      | 1                           | 1
                                      |                             |
                                      | 1                           | *
                            +---------v----------+      +-----------v-----------+
                            |  ambulances_trip   |      |  hospitals_admission  |
                            | id (PK)            |      | (Patient Admission)   |
                            | status, timestamps |      | triage vital summary  |
                            +----+----------+----+      +-----------------------+
                                 | *        | 1
                                 |          v
                                 |     +--------------------+
                                 |     | ambulances_vehicle |
                                 |     | vehicle_number     |
                                 |     +--------------------+
                                 v *
                    +---------------------------+
                    |   ambulances_telemetry    |
                    | (High-frequency GPS Ping) |
                    | lat, lng, speed, heading  |
                    +-------------+-------------+
                                  | Proximity Check
                                  v
+------------------------+ *    * +---------------------------+
|    traffic_junction    |<------>|  traffic_greencorridor    |
| id (PK), name, coords  |        | session_id, active_route  |
+-----------+------------+        +---------------------------+
            | 1
            |
            | 1..*
            v
+------------------------+
|  traffic_signaldriver  |
| (ESP32 IoT Node)       |
| device_token_hash      |
+------------------------+
```

---

## 2. Core Schemas & Table Definitions

### 2.1 `accounts_user` (Implemented in Stage 2.2)
* `id`: `BigAutoField` (Primary Key).
* `username`: `CharField(150)` (Unique).
* `password`: `CharField(128)` (PBKDF2/SHA-256 hashed).
* `role`: `CharField(20)` (`ADMIN`, `AMBULANCE_DRIVER`, `HOSPITAL_STAFF`, `POLICE_DISPATCHER`). Default: `AMBULANCE_DRIVER`.
* `phone_number`: `CharField(20)` (Direct contact).
* `badge_or_employee_id`: `CharField(50)` (Official ID).
* `is_verified`: `BooleanField` (Account verification flag).
* `is_active`, `is_staff`, `is_superuser`, `date_joined`, `last_login`.

### 2.2 `emergencies_hospital` (Implemented & Applied in Task 4.1C)
* `id`: `UUIDField` (Primary Key, default=`uuid.uuid4`).
* `name`: `CharField(150)` (Full hospital name).
* `hospital_code`: `CharField(30)` (Unique institutional code).
* `address`: `TextField` (Physical street address).
* `latitude`, `longitude`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)` (GPS coordinates with pairing validation and bounds checking -90..90 and -180..180).
* `contact_number`: `CharField(15, null=True, blank=True)`.
* `is_active`: `BooleanField(default=True)` (Indexed via `idx_hosp_is_active`).
* `created_at`, `updated_at`: `DateTimeField`.

### 2.3 `emergencies_ambulance` (Implemented & Applied in Task 4.1C)
* `id`: `UUIDField` (Primary Key, default=`uuid.uuid4`).
* `vehicle_number`: `CharField(20)` (Unique license plate/registration).
* `vehicle_type`: `CharField(50)` (ALS, BLS, Patient Transport).
* `assigned_driver`: `ForeignKey(accounts.User, null=True, blank=True, on_delete=SET_NULL, related_name="assigned_ambulances")` (Validated for `AMBULANCE_DRIVER` role and `is_active=True`).
* `is_available`: `BooleanField(default=True)` (Indexed via `idx_amb_is_available`).
* `is_active`: `BooleanField(default=True)` (Indexed via `idx_amb_is_active`).
* `created_at`, `updated_at`: `DateTimeField`.
* **Constraint:** `UniqueConstraint(fields=["assigned_driver"], condition=Q(assigned_driver__isnull=False, is_active=True), name="unique_active_ambulance_driver")` (Partial unique index enforcing at most one active ambulance per driver).

### 2.4 `emergencies_incident` (Implemented in Task 4.1D — Migration Generated, NOT Yet Applied)
* `id`: `UUIDField` (Primary Key, default=`uuid.uuid4`).
* `incident_number`: `CharField(32)` (Unique human-readable incident code, db_index=True).
* `reporting_driver`: `ForeignKey(accounts.User, on_delete=PROTECT, related_name="reported_incidents")` (Must be active user with `AMBULANCE_DRIVER` role).
* `ambulance`: `ForeignKey(Ambulance, on_delete=PROTECT, related_name="emergency_incidents")` (Must be active and assigned to reporting driver).
* `hospital`: `ForeignKey(Hospital, on_delete=PROTECT, related_name="emergency_incidents")` (Destination medical facility, must be active).
* `severity`: `CharField(20)` (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, default=`MEDIUM`, db_index=True).
* `status`: `CharField(20)` (`REPORTED`, `ASSIGNED`, `IN_TRANSIT`, `ARRIVED`, `CLOSED`, `CANCELLED`, default=`REPORTED`, db_index=True).
* `description`: `TextField(blank=True)`.
* Lifecycle transition timestamps: `assigned_at`, `in_transit_at`, `arrived_at`, `closed_at`, `cancelled_at` (`DateTimeField`, null=True, blank=True).
* Timestamps: `created_at` (auto_now_add), `updated_at` (auto_now).
* Indexes: `idx_inc_status`, `idx_inc_severity`, `idx_inc_status_sev`, `idx_inc_created_at`.

### 2.5 `emergencies_patient` (Implemented in Task 4.1D — Migration Generated, NOT Yet Applied)
* `id`: `UUIDField` (Primary Key, default=`uuid.uuid4`).
* `incident`: `ForeignKey(EmergencyIncident, null=True, blank=True, on_delete=CASCADE, related_name="patients")`.
* `name`: `CharField(150)` (Patient full name or identifier).
* `age`: `PositiveIntegerField(null=True, blank=True)` (Validated range 0 to 150).
* `gender`: `CharField(10)` (`MALE`, `FEMALE`, `OTHER`, `UNKNOWN`, default=`UNKNOWN`).
* `blood_group`: `CharField(10)` (`A+`, `A-`, `B+`, `B-`, `AB+`, `AB-`, `O+`, `O-`, `UNKNOWN`, blank=True).
* `medical_notes`: `TextField(blank=True)` (Triage notes, allergies, pre-existing conditions).
* `created_at`, `updated_at`: `DateTimeField`.
* Index: `idx_patient_created_at`.

### 2.3 `ambulances_telemetry` (Phase 4)
* `id`: `BigAutoField` (Primary Key).
* `trip_id`: `ForeignKey(ambulances_trip)` (Indexed).
* `latitude`, `longitude`: `DecimalField(max_digits=9, decimal_places=6)`.
* `speed_kmh`: `FloatField`.
* `heading_degrees`: `FloatField`.
* `recorded_at`: `DateTimeField` (Indexed jointly with `trip_id`).

### 2.4 `traffic_signaldriver` (Phase 5)
* `id`: `BigAutoField` (Primary Key).
* `junction_id`: `ForeignKey(traffic_junction)`.
* `device_identifier`: `CharField(50)` (e.g., `ESP32-JNC-001`).
* `device_token_hash`: `CharField(64)` (SHA-256 hash of hardware token).
* `is_online`: `BooleanField`.
* `last_heartbeat`: `DateTimeField`.
* `current_signal_state`: `CharField(20)` (`NORMAL_CYCLE`, `GREEN_PREEMPTION`).


---

## 3. Physical Database State (Verified Post-Reset)

The database `sertos_db` was reset and migrated cleanly with `AUTH_USER_MODEL = "accounts.User"`:

### 3.1 Live Tables in `sertos_db` (16 Tables Confirmed)
1. `accounts_user` (Primary custom user table)
2. `accounts_user_groups` (User-to-group junction)
3. `accounts_user_user_permissions` (User-to-permission junction)
4. `auth_group` (Django permission groups)
5. `auth_group_permissions` (Group-to-permission junction)
6. `auth_permission` (Django action permissions)
7. `django_admin_log` (Admin history log)
8. `django_content_type` (Installed model catalog)
9. `django_migrations` (Migration version tracker)
10. `django_session` (Encrypted web sessions)
11. `token_blacklist_blacklistedtoken` (JWT blacklist)
12. `token_blacklist_outstandingtoken` (JWT outstanding session tracker)
13. `emergencies_hospital` (Authorized & applied in Task 4.1C)
14. `emergencies_ambulance` (Authorized & applied in Task 4.1C)
15. `emergencies_incident` (Authorized & applied in Task 4.1D Migration Execution)
16. `emergencies_patient` (Authorized & applied in Task 4.1D Migration Execution)

> [!NOTE]
> Migration `emergencies.0001_initial` (creating `emergencies_hospital` and `emergencies_ambulance`) was explicitly authorized, applied to `sertos_db`, and forensically verified with 14 live tables, UUID primary keys, and partial unique constraint `unique_active_ambulance_driver`.
> 
> Migration `emergencies.0002_emergencyincident_patient_and_more` (defining `emergencies_incident` and `emergencies_patient`) was authorized by the user, applied to `sertos_db`, and forensically verified with 16 live tables, UUID primary keys, relational foreign keys with `ON DELETE NO ACTION` (ORM `PROTECT`), and compound performance indexes (`idx_inc_status_sev`).

### 3.2 Relational Integrity Verification
* `auth_user` table: **Does not exist.** Django cleanly skipped `auth_user` generation because `accounts.User` superseded it.
* `django_admin_log.user_id`: Confirmed foreign key references `accounts_user.id`.
