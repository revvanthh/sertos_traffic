# SERTOS Automated Testing & Quality Assurance Report

**Test Suite Version:** 1.0.0  
**Testing Framework:** Django Test Runner / Pytest  
**Status:** Baseline Verification Passing  

---

## 1. Executed Test Log

| Test ID | Test Category | Command Executed | Actual Result | Status |
| :--- | :--- | :--- | :--- | :--- |
| **TEST-01** | Git Secret Protection | `git status --ignored` | `.env`, `.venv/`, `.vscode/` confirmed under **Ignored files**. | **PASSED** |
| **TEST-02** | Configuration Integrity | `python manage.py check` | `System check identified no issues (0 silenced).` | **PASSED** |
| **TEST-03** | Settings Dynamic Resolution | `python manage.py shell -c "..."` | `DEBUG: True`, `ALLOWED_HOSTS: ['127.0.0.1', 'localhost', '10.0.2.2']`, `CORS_ALLOWED_ORIGINS: [...]`, `APPS: True`. | **PASSED** |
| **TEST-04** | Database Forensic Row Count | `python scratch/check_db.py` | 10 tables inspected. `auth_user`: 0 rows; `django_admin_log`: 0 rows; business rows: 0. | **PASSED** |
| **TEST-05** | Migration Generation | `python manage.py makemigrations accounts` | Generated `apps/accounts/migrations/0001_initial.py` cleanly. | **PASSED** |
| **TEST-06** | Migration Plan Verification | `python manage.py showmigrations --plan` | Verified `accounts.0001_initial` is queued for execution. | **PASSED** |
| **TEST-07** | Pre-Reset Database Backup | `pg_dump.exe -U postgres sertos_db` | Backup file created (22,629 bytes) in scratch directory outside Git. | **PASSED** |
| **TEST-08** | Database Reset & Recreate | Connect to `postgres`, drop & recreate `sertos_db` | `sertos_db` recreated with `ENCODING=UTF8` and `OWNER=postgres`. | **PASSED** |
| **TEST-09** | Fresh Migration Execution | `python manage.py migrate` | Applied all 18 migrations. `accounts.0001_initial` applied before `admin.0001_initial`. | **PASSED** |
| **TEST-10** | Schema & Model Verification | `python scratch/verify_post_reset.py` | `accounts_user` active, `auth_user` skipped, `django_admin_log.user_id -> accounts_user.id`, test user created and cleaned up. | **PASSED** |
| **TEST-11** | Post-Reset System Diagnostics | `python manage.py check` | `System check identified no issues (0 silenced).` | **PASSED** |
| **TEST-12** | Serializer Unit Tests (10 tests) | `manage.py test apps.accounts` | Valid registration, privilege escalation blocks, password hashing, JWT claims, unverified rejection. | **PASSED** |
| **TEST-13** | Permission Unit Tests (7 tests) | `manage.py test apps.accounts` | Anonymous denial, 4-role matrix isolation, live DB verification checks, DB revocation sensitivity. | **PASSED** |
| **TEST-14** | API View Tests (14 tests) | `manage.py test apps.accounts` | Login, refresh, logout ownership, register, profile update, standard envelope. | **PASSED** |
| **TEST-15** | URL Path Resolution | `manage.py test apps.accounts` | All 5 paths (`/api/auth/...`) resolve to respective views; reverse resolution verified. | **PASSED** |
| **TEST-16** | Unauthenticated Login/Register | `manage.py test apps.accounts` | Both endpoints accept anonymous requests without prior Authorization headers. | **PASSED** |
| **TEST-17** | Token Refresh Access | `manage.py test apps.accounts` | `/api/auth/token/refresh/` accepts anonymous request with valid refresh token payload. | **PASSED** |
| **TEST-18** | Protected Endpoint Rejection | `manage.py test apps.accounts` | Logout and Profile reject unauthenticated requests with HTTP 401. | **PASSED** |
| **TEST-19** | Routed End-to-End Profile | `manage.py test apps.accounts` | Verified user logs in via `/api/auth/login/` and fetches profile via `/api/auth/profile/`. | **PASSED** |
| **TEST-20** | Routed Registration Escalation Block | `manage.py test apps.accounts` | Driver registration via `/api/auth/register/` creates unverified driver; ignores ADMIN role. | **PASSED** |
| **TEST-21** | Response Envelope Integrity | `manage.py test apps.accounts` | Standard envelope (`success`, `data`, `message`, `timestamp`) preserved across success & error. | **PASSED** |
| **TEST-22** | Refresh Verification Revocation Block | `manage.py test apps.accounts` | When user's `is_verified` is revoked in PostgreSQL, old refresh token is rejected with HTTP 401. | **PASSED** |
| **TEST-23** | Deactivated User Refresh Block | `manage.py test apps.accounts` | When user's `is_active` is set to False in PostgreSQL, refresh token is rejected with HTTP 401. | **PASSED** |
| **TEST-43** | Multi-Role E2E: `ADMIN` | `manage.py test apps.accounts` | Full login, ADMIN JWT claims verified, profile inspection via Bearer token. | **PASSED** |
| **TEST-44** | Multi-Role E2E: `HOSPITAL_STAFF` | `manage.py test apps.accounts` | Full login, HOSPITAL_STAFF claims verified, profile inspection via Bearer token. | **PASSED** |
| **TEST-45** | Multi-Role E2E: `POLICE_DISPATCHER` | `manage.py test apps.accounts` | Full login, POLICE_DISPATCHER claims verified, profile inspection via Bearer token. | **PASSED** |
| **TEST-46** | Cross-Role Gating: Driver to Hospital | `manage.py test apps.accounts` | Verified driver denied access to hospital view (HTTP 403 Forbidden with exact message). | **PASSED** |
| **TEST-47** | Cross-Role Gating: Hospital to Police | `manage.py test apps.accounts` | Verified hospital staff denied access to police view (HTTP 403 Forbidden with exact message). | **PASSED** |
| **TEST-48** | Cross-Role Gating: Police to Admin | `manage.py test apps.accounts` | Verified police dispatcher denied access to admin view (HTTP 403 Forbidden with exact message). | **PASSED** |
| **TEST-49** | Token Rotation Replay Prevention | `manage.py test apps.accounts` | Reusing old rotated refresh token fails with HTTP 401 ("Token is blacklisted"). | **PASSED** |
| **TEST-50** | Multi-Device Session Isolation | `manage.py test apps.accounts` | Logging out on Device 1 blacklists Device 1 token; Device 2 refresh token remains valid (HTTP 200). | **PASSED** |
| **TEST-51** | Malformed & Tampered Bearer Tokens | `manage.py test apps.accounts` | Bogus tokens, non-Bearer schemes, empty headers, and tampered signatures all return HTTP 401. | **PASSED** |
| **TEST-52** | Boundary Payloads & Edge Cases | `manage.py test apps.accounts` | Empty payloads `{}` and invalid data types return structured 400/401 errors under standard envelope; zero 500s. | **PASSED** |
| **TEST-53** | Security Hardening: Default User Role | `manage.py test apps.accounts` | User created without explicit role defaults to `AMBULANCE_DRIVER`; superuser creation retains full admin privileges. | **PASSED** |
| **TEST-54** | Exception Handler: Framework 401 Envelope | `manage.py test apps.accounts` | Authentication-level 401 wrapped in standard envelope (`success=False`, `errors`, `detail`, `timestamp`). | **PASSED** |
| **TEST-55** | Exception Handler: Framework 403 Envelope | `manage.py test apps.accounts` | Permission-level 403 wrapped in standard envelope (`success=False`, `message="Permission denied"`, `detail`). | **PASSED** |
| **TEST-56** | Exception Handler: Framework 405 Envelope | `manage.py test apps.accounts` | MethodNotAllowed 405 wrapped in standard envelope (`success=False`, `message="Method not allowed"`, `detail`). | **PASSED** |
| **TEST-57** | Exception Handler: Framework 404 Envelope | `manage.py test apps.accounts` | NotFound 404 wrapped in standard envelope (`success=False`, `message="Not found"`, `detail`). | **PASSED** |
| **TEST-SCAFFOLD** | AppConfig Registration | `manage.py test apps.emergencies` | `apps.emergencies` properly registered and resolved by Django app registry. | **PASSED** |
| **HOSP-01** | Hospital: Valid Creation | `manage.py test apps.emergencies` | Creates valid hospital with full fields, verifies `__str__` and active status. | **PASSED** |
| **HOSP-02** | Hospital: Unique Code | `manage.py test apps.emergencies` | Duplicate `hospital_code` rejected by uniqueness constraint. | **PASSED** |
| **HOSP-03** | Hospital: Latitude Min Bound | `manage.py test apps.emergencies` | Latitude < -90 rejected during full model validation. | **PASSED** |
| **HOSP-04** | Hospital: Latitude Max Bound | `manage.py test apps.emergencies` | Latitude > 90 rejected during full model validation. | **PASSED** |
| **HOSP-05** | Hospital: Longitude Min Bound | `manage.py test apps.emergencies` | Longitude < -180 rejected during full model validation. | **PASSED** |
| **HOSP-06** | Hospital: Longitude Max Bound | `manage.py test apps.emergencies` | Longitude > 180 rejected during full model validation. | **PASSED** |
| **HOSP-07** | Hospital: Coordinates Omitted | `manage.py test apps.emergencies` | Both coordinates null accepted for facilities without fixed GPS. | **PASSED** |
| **HOSP-08** | Hospital: Coordinate Pairing | `manage.py test apps.emergencies` | Supplying only one coordinate rejected by pairing validation rule. | **PASSED** |
| **HOSP-09** | Hospital: Inactive Preservation | `manage.py test apps.emergencies` | Inactive status (`is_active=False`) properly stored and preserved. | **PASSED** |
| **AMB-01** | Ambulance: Valid Creation | `manage.py test apps.emergencies` | Creates valid ambulance with full fields, verifies `__str__` and dispatch eligibility. | **PASSED** |
| **AMB-02** | Ambulance: Unique Vehicle Number | `manage.py test apps.emergencies` | Duplicate `vehicle_number` rejected by uniqueness constraint. | **PASSED** |
| **AMB-03** | Ambulance: Valid Driver Role | `manage.py test apps.emergencies` | Assigning verified user with `AMBULANCE_DRIVER` role succeeds. | **PASSED** |
| **AMB-04** | Ambulance: Non-Driver Role Rejection | `manage.py test apps.emergencies` | Assigning user without `AMBULANCE_DRIVER` role (e.g. `HOSPITAL_STAFF`) rejected. | **PASSED** |
| **AMB-05** | Ambulance: Inactive User Rejection | `manage.py test apps.emergencies` | Assigning inactive user as driver rejected by model validation. | **PASSED** |
| **AMB-06** | Ambulance: Unassigned Creation | `manage.py test apps.emergencies` | Unassigned ambulance (`assigned_driver=None`) valid; dispatch eligibility is False. | **PASSED** |
| **AMB-07** | Ambulance: Inactive Preservation | `manage.py test apps.emergencies` | Inactive ambulance preserved; dispatch eligibility is False. | **PASSED** |
| **AMB-08** | Ambulance: Unavailable Preservation | `manage.py test apps.emergencies` | Unavailable ambulance preserved; dispatch eligibility is False. | **PASSED** |
| **AMB-09** | Ambulance: Single Active Driver | `manage.py test apps.emergencies` | Reassigning driver to second active ambulance blocked; decommissioning first ambulance allows reassignment. | **PASSED** |
| **MIG-0001-EMERG** | Emergencies 0001 Migration | `manage.py migrate emergencies` | Applied migration `0001_initial.py` to `sertos_db`; 14 live tables verified. | **PASSED** |
| **INC-01** | Incident: Valid Creation | `manage.py test apps.emergencies` | Creates valid incident with full lifecycle defaults and verified relations. | **PASSED** |
| **INC-02** | Incident: Unique Incident Number | `manage.py test apps.emergencies` | Duplicate `incident_number` rejected by uniqueness constraint. | **PASSED** |
| **INC-03** | Incident: Non-Driver Reporting User | `manage.py test apps.emergencies` | Reporting user without `AMBULANCE_DRIVER` role (e.g. `HOSPITAL_STAFF`) rejected. | **PASSED** |
| **INC-04** | Incident: Inactive Reporting Driver | `manage.py test apps.emergencies` | Inactive driver (`is_active=False`) rejected during model validation. | **PASSED** |
| **INC-05** | Incident: Inactive Ambulance | `manage.py test apps.emergencies` | Linking incident to inactive ambulance rejected during model validation. | **PASSED** |
| **INC-06** | Incident: Mismatched Driver Vehicle | `manage.py test apps.emergencies` | Incident rejected when reporting driver does not match vehicle's assigned driver. | **PASSED** |
| **INC-07** | Incident: Inactive Destination Hospital | `manage.py test apps.emergencies` | Linking incident to inactive hospital facility rejected during model validation. | **PASSED** |
| **INC-08** | Incident: State Machine Valid Transitions | `manage.py test apps.emergencies` | Follows legal state sequence (`REPORTED` -> `ASSIGNED` -> `IN_TRANSIT` -> `ARRIVED` -> `CLOSED`); captures milestone timestamps. | **PASSED** |
| **INC-09** | Incident: State Machine Illegal Transitions | `manage.py test apps.emergencies` | Illegal status skip (e.g. `REPORTED` directly to `CLOSED` or `ARRIVED`) rejected with `ValidationError`. | **PASSED** |
| **INC-10** | Incident: Terminal Cancellation | `manage.py test apps.emergencies` | Cancellation permitted from active states; modifying terminal `CLOSED` or `CANCELLED` incident rejected. | **PASSED** |
| **PAT-01** | Patient: Valid Creation Linked | `manage.py test apps.emergencies` | Creates patient with demographics and medical notes linked to valid incident. | **PASSED** |
| **PAT-02** | Patient: Unlinked Creation | `manage.py test apps.emergencies` | Creates patient record with `incident=None` (anonymous intake / pre-assignment). | **PASSED** |
| **PAT-03** | Patient: Negative Age Rejection | `manage.py test apps.emergencies` | Negative patient age (`age < 0`) rejected during model validation. | **PASSED** |
| **PAT-04** | Patient: Extreme Age Rejection | `manage.py test apps.emergencies` | Implausible patient age (`age > 150`) rejected during model validation. | **PASSED** |
| **PAT-05** | Patient: Cascade Deletion | `manage.py test apps.emergencies` | Deleting parent incident cleanly cascades and removes linked patient records. | **PASSED** |
| **MIG-0002-EMERG** | Emergencies 0002 Migration | `manage.py migrate emergencies` | Applied migration `0002_emergencyincident_patient_and_more.py` to `sertos_db`; 16 live tables, foreign keys, and indexes verified. | **PASSED** |

---

## 2. Test Execution Summary

### Phase 4 Emergencies Test Suite (Task 4.1D Incident & Patient Models)
```powershell
.\.venv\Scripts\python.exe manage.py test apps.emergencies --verbosity 1
```
* **Total Tests Ran:** 34
* **Total Failures:** 0
* **Total Errors:** 0
* **Execution Time:** ~27.6 seconds
* **Status:** 100% Passing

### Phase 3 Accounts Regression Test Suite (Task 4.1D Verification)
```powershell
.\.venv\Scripts\python.exe manage.py test apps.accounts --verbosity 1
```
* **Total Tests Ran:** 57
* **Total Failures:** 0
* **Total Errors:** 0
* **Execution Time:** ~72.5 seconds
* **Status:** 100% Passing (Zero regressions)

* **Overall Test Suite Total:** **91 Passing Tests (0 failures, 0 errors).**

---

## 3. Resolved Security Findings (Task 3.9 Hardening)

1. **Model-Level Role Default (`apps/accounts/models.py`)**:
   * **Status:** **RESOLVED**
   * **Resolution:** Changed `User.role` default from `UserRole.ADMIN` to `UserRole.AMBULANCE_DRIVER` (least privilege). Generated migration `0002_alter_user_role.py` and applied to `sertos_db`. Automated verification via `TEST-53` confirms baseline user creation defaults safely to Ambulance Driver.
2. **Framework-Level Exception Wrapping**:
   * **Status:** **RESOLVED**
   * **Resolution:** Implemented `sertos_exception_handler` in `apps/accounts/exceptions.py` and registered globally under `REST_FRAMEWORK["EXCEPTION_HANDLER"]` in `config/settings.py`. Guarantees every framework-level 400, 401, 403, 404, and 405 returns the uniform SERTOS envelope (`success`, `data`, `message`, `errors`, `detail`, `timestamp`) while passing unhandled 500 exceptions to Django for internal logging. Validated across `TEST-54` through `TEST-57`.

---

## 4. Integrity Verification
* No tests were mocked or fabricated.
* Database and configuration checks ran against real local PostgreSQL instance on port 5432.
