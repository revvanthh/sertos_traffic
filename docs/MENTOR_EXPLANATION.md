# SERTOS Mentor Review & Oral Defense Cheat-Sheet

**Prepared For:** Project Reviews, Technical Mentorship Sessions, and Viva Voce  
**Project:** SERTOS Backend Architecture  
**Author:** Backend Developer  

---

## 1. Core Speaking Scripts

### What did I build in this phase?
> *"In this phase, I transitioned the SERTOS backend into an enterprise-grade, secure architecture. I established Git version control with strict secret filtering, secured our application keys inside `.env`, integrated Django REST Framework and CORS headers for dashboard interoperability, and introduced our custom `accounts.User` model inheriting from `AbstractUser` with domain roles for Ambulance Drivers, Hospital Staff, and Police Dispatchers. I generated the initial migration for accounts and forensically verified our PostgreSQL database."*

### Why is ESP32 hardware authentication separate from the user model?
> *"Microcontrollers in traffic signals are autonomous edge hardware nodes. They do not have names, emails, passwords, or human roles. Treating them as human users would violate the principle of least privilege and pollute user auditing tables. Instead, ESP32 nodes authenticate using dedicated, hashed hardware device tokens within the traffic domain."*

### Why do we need to reset the empty development database for the custom user model?
> *"Django's internal admin and authentication tables depend on the user model. If you apply initial migrations using default `auth.User`, and then introduce a custom user model later, foreign keys in `django_admin_log` continue pointing to the old table, creating schema corruption. Because we have zero user records and zero business tables in our database, dropping and recreating `sertos_db` allows Django to build the migration graph cleanly with pristine foreign key integrity."*

### How does URL routing work in SERTOS, and what was built in Step 3.7?
> *"In Step 3.7, we completed the URL wiring for our authentication subsystem. We created `apps/accounts/urls.py` with five explicit, named routes and mounted it in the root `config/urls.py` under `/api/auth/`. More importantly, our security inspection identified a subtle vulnerability in SimpleJWT's default token refresh mechanism, which is purely cryptographic and never checks the live database user. If an administrator revokes a compromised user's verification, SimpleJWT would still issue fresh access tokens. We eliminated this loophole by implementing `CustomTokenRefreshSerializer`, which checks PostgreSQL for active and verified status before issuing new tokens. We proved the architecture with 42 passing automated tests."*

### How did we validate the complete Authentication & RBAC subsystem in Step 3.8?
> *"In Step 3.8, we completed our validation suite for Phase 3. We authored ten end-to-end integration tests covering multi-role login and profile access for all four roles, cross-role authorization gating, token rotation replay attack prevention, independent multi-device sessions, and boundary payload testing. We also documented two security observations for future hardening: model-level default role assignment and framework-level exception wrapping. Our entire suite of 52 tests runs cleanly in isolated test databases with zero errors."*

### How did we complete the Phase 3 Security Hardening in Task 3.9?
> *"In Task 3.9, we addressed the two architectural observations flagged during our validation audit. First, we changed the default role on the `User` model from `ADMIN` to `AMBULANCE_DRIVER`, enforcing least privilege across the entire ORM. In PostgreSQL, this was a zero-downtime, no-op migration because Django defaults are handled in Python application code. Second, we implemented `sertos_exception_handler` in `apps/accounts/exceptions.py` and wired it into DRF settings. This guarantees that all framework-level 400, 401, 403, 404, and 405 errors return our standard envelope while still passing 500 server errors to Django's logger. We validated both fixes with five automated unit tests, bringing our total verified test count to 57."*

### How did we implement and migrate the Hospital and Ambulance models in Task 4.1C?
> *"In Task 4.1C, we implemented the foundational infrastructure models for SERTOS: `Hospital` and `Ambulance` within `apps.emergencies`. For `Hospital`, we enforced exact GPS fixed-point coordinate validation with pairing constraints (both supplied or both omitted) and unique facility codes. For `Ambulance`, we established relational integrity with the custom `User` model, strictly validating that only active users with the `AMBULANCE_DRIVER` role can be assigned. Crucially, to prevent a driver from being assigned to multiple active ambulances, we implemented a dual safety architecture: clean Python validation for friendly errors, backed by a PostgreSQL partial unique index (`WHERE assigned_driver_id IS NOT NULL AND is_active`). Following explicit user authorization, we applied migration `0001_initial.py` to `sertos_db`, expanding our physical schema to 14 tables while preserving zero business records. All 76 automated tests across the project pass cleanly."*

### How did we implement and migrate the EmergencyIncident and Patient models in Task 4.1D?
> *"In Task 4.1D, we implemented the core transactional and clinical emergency models: `EmergencyIncident` and `Patient` in `apps.emergencies`. For `EmergencyIncident`, we created an audit-resilient entity with UUID primary keys and unique incident tracking numbers. We established a finite state machine enforcing strict lifecycle progression from REPORTED to CLOSED, while supporting aborts via CANCELLED. We validated that the reporting driver possesses the AMBULANCE_DRIVER role, is active, and is the actual assigned driver of the dispatched ambulance, preventing cross-fleet spoofing. Foreign keys to driver, ambulance, and hospital are protected with `models.PROTECT` to preserve clinical audit trails. For `Patient`, we decoupled the model to support pre-dispatch intake and multi-patient casualties, with strict age boundary checks. We generated migration `0002`, thoroughly verified it across 34 emergencies tests, and following explicit user authorization, safely applied it to `sertos_db`. PostgreSQL schema introspection confirmed the addition of `emergencies_incident` and `emergencies_patient`, bringing our verified database to 16 live tables and 0 business rows, with all 91 automated tests passing."*

---

## 2. High-Yield Viva Questions & Answers

1. **What is the difference between `AbstractUser` and `AbstractBaseUser`?**
   * *Answer:* `AbstractUser` keeps Django's default user fields (username, first_name, last_name, email, is_staff, is_active, permissions) while allowing you to add custom fields like `role`. `AbstractBaseUser` provides only the bare minimum password hashing and last_login fields, requiring you to implement all other fields from scratch.

2. **Why is `db_table = "accounts_user"` specified in `Meta`?**
   * *Answer:* Explicitly setting `db_table` ensures predictable database table naming across environments and prevents naming collisions if the app label is modified.

3. **How does CORS protect web applications?**
   * *Answer:* Cross-Origin Resource Sharing is a browser security mechanism that blocks web pages hosted on one domain/origin from making requests to a different domain unless the backend explicitly declares that origin in its `Access-Control-Allow-Origin` response header.

4. **Why did `auth_user` disappear completely from our PostgreSQL database?**
   * *Answer:* Django's `auth` app migration checks `settings.AUTH_USER_MODEL`. When `AUTH_USER_MODEL` points to `accounts.User` during initial migration, Django skips creating `auth_user` entirely and relies solely on `accounts_user`, avoiding dead legacy tables.

5. **How did we verify that `django_admin_log` points to `accounts_user` instead of `auth_user`?**
   * *Answer:* We queried PostgreSQL's `information_schema.table_constraints` and confirmed that the foreign key constraint on `django_admin_log.user_id` targets `accounts_user.id`, ensuring full referential integrity.

6. **What does `as_view()` do in Django class-based views?**
   * *Answer:* `as_view()` is a class method that returns a callable closure. It acts as an entry point for Django's URL resolver, creating a new instance of the view class for each incoming HTTP request, setting up request attributes, and calling `dispatch()` to route the request to `get()`, `post()`, etc.

7. **Why is `include()` preferred over defining all routes in `config/urls.py`?**
   * *Answer:* `include()` enforces modular design and separation of concerns. Each application maintains its own `urls.py`. If an application is moved or reused, its URL definitions travel with it without requiring edits to a global monolithic routing file.

8. **Why was standard SimpleJWT `TokenRefreshView` vulnerable to revoked users, and how did we fix it?**
   * *Answer:* SimpleJWT's default serializer only checks the HMAC/RSA signature and expiration of the refresh token string, and whether its `jti` is on the blacklist. It does not query the PostgreSQL `User` table. If an admin revoked `is_verified` or `is_active`, the user could keep obtaining access tokens. We introduced `CustomTokenRefreshSerializer`, which explicitly queries PostgreSQL and denies token renewal if `is_verified` or `is_active` is `False`.

9. **Why do we test both `resolve()` and `reverse()`?**
   * *Answer:* `resolve()` confirms that an incoming HTTP URL path properly maps to the designated view class and URL name. `reverse()` confirms that code generating URLs by name (e.g. for redirects or email links) produces the exact expected path. Testing both ensures bidirectional routing integrity.

10. **How does SERTOS prevent token replay attacks on refresh tokens?**
    * *Answer:* By configuring `ROTATE_REFRESH_TOKENS = True` and `BLACKLIST_AFTER_ROTATION = True`, every refresh request writes the submitted refresh token's `jti` into PostgreSQL's `BlacklistedToken` table. Any subsequent attempt to use that same refresh token triggers an immediate HTTP 401 Unauthorized (`"Token is blacklisted"`).

11. **How do multi-device sessions remain independent during logout?**
    * *Answer:* Each login event issues a token with a unique `jti`. Logging out on Device 1 blacklists only `refresh_dev1`'s specific `jti`. Device 2's refresh token carries a different `jti`, so Device 2 remains authenticated and can continue refreshing tokens without interruption.

12. **Why do we test role permissions using isolated test views rather than production endpoints in Step 3.8?**
    * *Answer:* Domain endpoints for Hospital and Police (e.g., triage ingestion and signal preemption) belong to future phases (Phases 5–7). Writing test-only views in `apps/accounts/tests.py` allowed us to test real DRF 403 authorization gating, response codes, and error messages without creating mock production endpoints or polluting the routing table.

13. **What is the significance of the model default role finding?**
    * *Answer:* The `User` model currently defaults `role` to `ADMIN`. Although API self-registration strictly overrides this to `AMBULANCE_DRIVER`, creating users internally via `create_user()` without specifying a role could inadvertently create an admin. Documenting this ensures it is scheduled for hardening in a separate migration task.

14. **How do we ensure that passwords and secrets are never exposed in error responses?**
    * *Answer:* Serializers declare `password` as `write_only=True`, and `standard_response` envelopes capture sanitized validation dictionaries rather than raw request dumps. Our boundary tests verified that neither raw passwords nor server credentials appear anywhere in success or error response payloads.

15. **Why was migration `0002_alter_user_role` a no-op in PostgreSQL DDL?**
    * *Answer:* In Django, a standard `default=...` argument on a model field is evaluated at the Python ORM layer when model instances are initialized. Unless `db_default` is specified, Django does not generate an `ALTER TABLE ... ALTER COLUMN SET DEFAULT` statement in PostgreSQL. Thus, the migration modified Django's migration state without altering database schema or locking tables.

16. **Why was changing the default role to `AMBULANCE_DRIVER` preferred over removing the default entirely?**
    * *Answer:* If `default` were removed from a `NOT NULL` column, Django's CLI command `createsuperuser` would crash because it only prompts for the model's `REQUIRED_FIELDS` and username/password. Defaulting to `AMBULANCE_DRIVER` enforces least privilege while allowing `createsuperuser` and backend factories to instantiate users safely.

17. **How does `sertos_exception_handler` preserve field-level validation errors while providing backward compatibility?**
    * *Answer:* When DRF raises an exception, the handler inspects `response.data`. If it is a dictionary, it preserves it in the `errors` payload; if it is a list or scalar `detail`, it normalizes it. It also attaches the top-level error string to `response.data["detail"]`, ensuring existing frontend clients or test assertions expecting DRF's standard `detail` key continue to work seamlessly.

18. **Why must a custom DRF exception handler return `None` on unhandled 500 exceptions?**
    * *Answer:* When DRF's base exception handler cannot process an unhandled exception (like a database connection failure or code syntax error), it returns `None`. If the custom handler caught everything and returned an HTTP 200/500 JSON response, it would swallow the exception traceback, preventing Django's logging handlers and error monitoring tools (like Sentry) from recording the stack trace. Returning `None` lets Django trigger its native 500 handler and generate diagnostic logs.

19. **Why did we use UUIDs for `Hospital` and `Ambulance` instead of auto-incrementing integers?**
    * *Answer:* Sequential integer IDs (1, 2, 3...) expose fleet and facility counts to external scrapers and enable enumeration attacks. UUIDv4 primary keys provide cryptographically non-enumerable, globally unique identifiers that can be generated distributedly without round-trip database locks.

20. **Why did we use a partial unique index for ambulance driver assignment rather than a simple OneToOneField?**
    * *Answer:* A `OneToOneField` would enforce that every driver could only ever be linked to one ambulance across all historical time, preventing an ambulance from having `NULL` (unassigned fleet vehicles) and preventing a driver from ever being reassigned to a new ambulance when an old one is decommissioned. A partial unique index (`WHERE assigned_driver_id IS NOT NULL AND is_active`) guarantees that a driver is assigned to at most one *active* ambulance at any single point in time.

21. **Why is coordinate pairing enforced on `Hospital`?**
    * *Answer:* A geographical point requires both latitude and longitude to resolve a spatial location. Having only latitude without longitude (or vice versa) results in corrupted GIS routing and preemption calculations. The `clean()` method guarantees that coordinates are either both fully specified or both null (for facilities without fixed GPS coordinates).

22. **What was the verification procedure before and after applying migration `0001_initial` to `sertos_db`?**
    * *Answer:* Under our strict enterprise workflow (PLAN → INSPECT → BUILD → TEST → REPORT → STOP FOR USER APPROVAL), we first generated the migration, inspected its SQL plan via `sqlmigrate`, and verified all 19 tests in an isolated ephemeral test database while keeping the real database untouched. Only after explicit user approval did we execute `migrate emergencies`. Post-migration introspection confirmed exactly 14 live tables in PostgreSQL, UUID primary keys, and the `unique_active_ambulance_driver` partial unique index, with 76 total passing automated tests.

23. **What is the business logic behind the finite state machine transitions in `EmergencyIncident`?**
    * *Answer:* Emergency dispatch involves real-world logistical milestones. An incident progresses logically: `REPORTED` (intake) $\to$ `ASSIGNED` (ambulance dispatched) $\to$ `IN_TRANSIT` (corridor active) $\to$ `ARRIVED` (hospital arrival) $\to$ `CLOSED` (triage finalized). Skipping states (such as jumping from `REPORTED` to `CLOSED` or `ARRIVED`) would compromise automated traffic signal preemption and hospital intake preparation. However, an active emergency can be `CANCELLED` at any operational stage prior to arrival (e.g. false alarm or patient refusal). Once `CLOSED` or `CANCELLED`, the state machine is terminal and immutable.

24. **Why are `reporting_driver`, `ambulance`, and `hospital` foreign keys protected with `models.PROTECT`?**
    * *Answer:* In emergency dispatch and medical systems, statutory regulations require indelible audit trails. If a user account, ambulance vehicle, or hospital is decommissioned or deleted, cascading deletion (`CASCADE`) would wipe out historical incident records. `models.PROTECT` blocks deletion by raising a `ProtectedError` in the ORM and generating `ON DELETE RESTRICT` foreign key constraints in PostgreSQL, ensuring audit history cannot be accidentally purged.

25. **How do we ensure that an ambulance driver can only report emergencies for their own assigned vehicle?**
    * *Answer:* In `EmergencyIncident.clean()`, we validate that `self.ambulance.assigned_driver_id == self.reporting_driver_id`. If driver A attempts to submit an incident claiming ambulance B (assigned to driver C), model validation raises a `ValidationError` on the `ambulance` field. This prevents unauthorized vehicle impersonation and cross-fleet data corruption.

26. **What was the staging and migration procedure for migration `0002_emergencyincident_patient_and_more`?**
    * *Answer:* Under our strict enterprise database governance protocol (PLAN → INSPECT → BUILD → TEST → REPORT → STOP FOR USER APPROVAL), migration `0002` was first generated and tested inside Django's isolated ephemeral test runner (`test_sertos_db`), allowing full verification of migration DDL, model constraints, and queries without touching the active development database `sertos_db`. The migration was presented to the user with full SQL introspection via `sqlmigrate`. Only after explicit user authorization was `python manage.py migrate emergencies` executed on `sertos_db`. Post-migration forensics verified the creation of `emergencies_incident` and `emergencies_patient` (expanding the schema to 16 live tables), valid foreign key constraints, performance indexes, and 0 business rows.

