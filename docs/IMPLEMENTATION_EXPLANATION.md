# SERTOS Backend Implementation Explanation & Technical Documentation

**Document Title:** SERTOS Backend Architecture, Environment Setup & Technical Implementation  
**Project Location:** `E:\sertos`  
**Current Phase:** Phase 1 – Environment Setup, Database Integration & Foundation Verification  
**Author:** Backend Engineering Team (SERTOS Project)  
**Target Audience:** Technical Mentors, Project Reviewers, and Backend Developers  

---

## Table of Contents
1. [Section A: Project Overview](#section-a-project-overview)
2. [Section B: Development Environment Setup](#section-b-development-environment-setup)
3. [Section C: PostgreSQL Installation and Configuration](#section-c-postgresql-installation-and-configuration)
4. [Section D: Django Project Creation and Core Architecture](#section-d-django-project-creation-and-core-architecture)
5. [Section E: Django and PostgreSQL Integration](#section-e-django-and-postgresql-integration)
6. [Section F: Initial Database Migrations](#section-f-initial-database-migrations)
7. [Section G: Errors Encountered and Solutions](#section-g-errors-encountered-and-solutions)
8. [Section H: Current Project Status](#section-h-current-project-status)
9. [Section I: Mentor Explanation (Speaking Points)](#section-i-mentor-explanation-speaking-points)
10. [Section J: Mentor Viva Questions and Answers (20+ Questions)](#section-j-mentor-viva-questions-and-answers)
11. [Section K: Next Development Roadmap](#section-k-next-development-roadmap)
12. [Section L: Ongoing Documentation Protocol](#section-l-ongoing-documentation-protocol)

---

## Section A: Project Overview

### 1. What is SERTOS?
**SERTOS** stands for **Smart Emergency Response and Traffic Optimization System**. It is a unified emergency management and traffic coordination platform designed to drastically reduce emergency vehicle response and transit times during critical life-threatening situations (such as cardiac arrest, severe trauma, or acute respiratory distress).

### 2. The Problem Being Solved
Emergency medical response systems frequently fail due to fragmentation between multiple stakeholders:
* **Severe Traffic Congestion:** Ambulances carrying critically ill patients get trapped in urban gridlock at traffic intersections, causing preventable deaths during the "Golden Hour".
* **Blind Hospital Hand-offs:** Emergency departments at hospitals frequently have zero advance visibility into incoming patient vitals, leading to delays in preparing intensive care unit (ICU) beds, blood reserves, ventilators, or surgical teams.
* **Manual Police Coordination:** Traffic police dispatchers lack real-time digital tracking of emergency corridors and must rely on slow, manual radio broadcasts to clear traffic signals.
* **Slow Emergency Intake:** Call takers at dispatch centers spend valuable minutes gathering incident details without automated symptom extraction or automatic severity classification.

### 3. Overall System Architecture
SERTOS connects five critical subsystems through a central, secure backend API:

```
                      +---------------------------------------+
                      |       AI Voice-Processing Module      |
                      |  (Speech-to-Text & Symptom Extractor) |
                      +-------------------+-------------------+
                                          |
                                          | POST /api/v1/emergencies/voice-webhook/
                                          v
+------------------------+    +-----------------------+    +-----------------------+
| Ambulance Android App  |    |     SERTOS BACKEND    |    | Hospital Web App      |
| - GPS Telemetry Stream |<-->|  Django REST API Core |<-->| - Incoming Triage Feed|
| - Triage Vitals Input  |    |      (PostgreSQL)     |    | - Resource/Bed Status |
+------------------------+    +-----------+-----------+    +-----------------------+
                                          |
                                          |
                                          v
                      +-------------------+-------------------+
                      |      Police Web Dashboard & ESP32     |
                      | - Real-time Green Corridor Monitoring |
                      | - IoT Signal Preemption (ESP32 Nodes) |
                      +---------------------------------------+
```

1. **Ambulance Android Application:** Streams real-time GPS coordinates, vehicle speed, heading, and live patient vital signs directly to the backend.
2. **Hospital Web Dashboard:** Displays incoming ambulances with live estimated times of arrival (ETA), pre-arrival triage assessments, and enables hospital staff to update bed and ventilator availability.
3. **Police Web Dashboard:** Provides live spatial awareness of active emergency corridors and enables authorized officers to monitor and manually override traffic signals.
4. **AI Voice-Processing Module:** Transcribes emergency 911/112 caller audio, extracts medical symptoms, evaluates urgency scores, and automatically creates emergency incident tickets.
5. **ESP32-based Traffic Signal Prototype:** Hardware microcontroller nodes deployed at traffic intersections that receive signal preemption instructions ("Green Corridor") to hold green signals for approaching emergency vehicles.

### 4. Backend Developer Responsibility
As the backend developer, my responsibility is to design, implement, secure, and maintain the central nervous system of SERTOS:
* Architect the relational database schemas in PostgreSQL to model all entities (incidents, vehicles, hospitals, traffic nodes).
* Implement secure, versioned RESTful APIs using Django REST Framework.
* Enforce authentication and Role-Based Access Control (RBAC) to ensure ambulance drivers, hospital staff, police officers, and hardware nodes only access authorized endpoints.
* Ensure data validation, error handling, performance optimization for high-frequency GPS pings, and comprehensive test coverage.

---

## Section B: Development Environment Setup

The backend development environment was established with precision on Windows using modern, LTS-grade technologies.

### 1. Technology Matrix (Verified on Disk)

| Component | Verified Version | Purpose in SERTOS |
| :--- | :--- | :--- |
| **Operating System** | Windows 11 (64-bit) | Local development host |
| **Python** | `3.13.3` (v3.13.3:62b64dc) | Primary programming language |
| **Django** | `5.2.19` | High-level web and ORM framework |
| **Django REST Framework** | `3.18.3` | REST API toolkit and serialization engine |
| **Database** | PostgreSQL `18.7` | Production-grade relational database |
| **DB Driver (Adapter)** | `psycopg` / `psycopg-binary` `3.3.9` | High-performance Python-to-PostgreSQL adapter |
| **Environment Manager** | `python-dotenv` `1.2.4` | Loads secrets from `.env` to system environment |
| **Package Installer** | `pip` `25.0.1` | Python package management tool |
| **JWT Engine** | `djangorestframework-simplejwt` `5.3.1` | JSON Web Token authentication plugin |
| **Cryptographic JWT** | `PyJWT` `2.15.1` | Low-level token encoding and decoding dependency |
| **Virtual Environment** | Python standard `venv` (`.venv`) | Isolated dependency container |

### 2. Setup Commands and Explanations

#### Step 1: Virtual Environment Creation
```powershell
python -m venv .venv
```
* **Explanation:** Invokes Python's built-in `venv` module to create an isolated runtime environment inside the `.venv` directory. This ensures project dependencies do not interfere with other Python installations or global system libraries.

#### Step 2: Virtual Environment Activation
```powershell
# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1

# On Windows Command Prompt (CMD):
.\.venv\Scripts\activate.bat
```
* **Explanation:** Modifies the current shell's `PATH` variable so that running `python` or `pip` executes the binaries inside `.venv\Scripts` rather than the global machine Python.

#### Step 3: Upgrading Pip
```powershell
python -m pip install --upgrade pip
```
* **Explanation:** Updates the pip package manager to version `25.0.1` to ensure compatibility with modern binary wheels and dependencies.

#### Step 4: Installing Django and Django REST Framework
```powershell
pip install django==5.2.19 djangorestframework==3.18.3
```
* **Explanation:** Downloads and installs Django (web framework) and Django REST Framework (API serialization and viewsets) inside `.venv`.

#### Step 5: Installing PostgreSQL Driver and Environment Manager
```powershell
pip install psycopg[binary]==3.3.9 python-dotenv==1.2.4
```
* **Explanation:** 
  * `psycopg[binary]`: Installs the modern version 3 Psycopg driver with pre-compiled C-extensions for fast Windows execution.
  * `python-dotenv`: Enables Django to parse key-value pairs from a local `.env` configuration file.

#### Step 6: Verifying Installed Packages
```powershell
pip list
```
* **Actual Output Verified:**
  ```text
  Package             Version
  ------------------- -------
  asgiref             3.13.0
  Django              5.2.19
  djangorestframework 3.18.3
  pip                 25.0.1
  psycopg             3.3.9
  psycopg-binary      3.3.9
  python-dotenv       1.2.4
  sqlparse            0.6.1
  tzdata              2026.6
  ```

---

## Section C: PostgreSQL Installation and Configuration

### 1. PostgreSQL 18.7 Overview
PostgreSQL is chosen as the primary database for SERTOS because:
* It is an enterprise-grade, ACID-compliant relational database.
* It supports advanced spatial data indexing (PostGIS extensions) if full geospatial polygon routing is expanded.
* It provides robust JSONB support for semi-structured data like IoT telemetry flags and AI voice symptom metadata.

### 2. Windows Service and Daemon Verification
PostgreSQL is installed and running as a dedicated Windows background service:
* **Service Name:** `postgresql-x64-18`
* **Default Listening Host:** `localhost` (`127.0.0.1`)
* **Default Listening Port:** `5432`

### 3. PATH Configuration
To interact with PostgreSQL from any command prompt without typing full directory paths, the PostgreSQL binary directory must be added to the Windows System `PATH` variable:
* **Binary Path:** `C:\Program Files\PostgreSQL\18\bin`
* **Included Tools:** `psql.exe` (CLI query client), `pg_dump.exe` (backup utility), `createdb.exe` (database creation utility).

### 4. Database Creation Command
To create the dedicated database for SERTOS, the following command was executed in the terminal:
```powershell
# Connecting via psql command-line client:
psql -U postgres -h localhost -p 5432

# Inside the psql interactive prompt:
CREATE DATABASE sertos_db;
```
Or via the direct command-line tool:
```powershell
createdb -U postgres -h localhost -p 5432 sertos_db
```

### 5. Connection Parameters (Credentials Redacted)
The database connection configuration strictly follows security best practices by abstracting credentials into environment variables:

| Parameter | Value in SERTOS | Description |
| :--- | :--- | :--- |
| **Engine** | `django.db.backends.postgresql` | Django's PostgreSQL database backend |
| **Database Name** | `sertos_db` | Dedicated database catalog |
| **Host** | `127.0.0.1` | Local machine IP loopback |
| **Port** | `5432` | Standard PostgreSQL port |
| **Username** | `[REDACTED_USER]` (stored in `.env`) | Dedicated database user |
| **Password** | `[REDACTED_PASSWORD]` (stored in `.env`) | Authenticated credential |

---

## Section D: Django Project Creation and Core Architecture

### 1. Django Architecture Overview
Django follows the **MVT (Model-View-Template)** architecture, which for REST API backends adapts to the **Model-Serializer-View** pattern:
* **Model:** Defines database structure, table columns, constraints, and relationships in pure Python.
* **Serializer (DRF):** Translates complex database querysets into JSON format for mobile apps, dashboards, and hardware, and validates incoming JSON data.
* **View / ViewSet:** Contains the business logic that handles incoming HTTP requests (GET, POST, PUT, DELETE) and generates appropriate HTTP responses.
* **URL Router:** Directs incoming web traffic to the appropriate view based on the URL path.

### 2. Project Initial Creation Command
Inside the project root directory `E:\sertos`, the project orchestrator was created using:
```powershell
django-admin startproject config .
```
* **Important Detail:** The trailing dot (`.`) instructs Django to create the configuration folder named `config/` directly in the current directory and place `manage.py` in `E:\sertos`, preventing nested folders like `E:\sertos\sertos\manage.py`.

### 3. Core Files and Their Responsibilities

#### `manage.py`
Located at `E:\sertos\manage.py`. This is Django's command-line management utility. It sets the `DJANGO_SETTINGS_MODULE="config.settings"` environment variable and passes CLI arguments to Django's internal management pipeline.
Common operations invoked through `manage.py`:
* `python manage.py runserver` (launches local development server)
* `python manage.py makemigrations` (generates new SQL migration scripts from models)
* `python manage.py migrate` (applies migration scripts to the database)
* `python manage.py check` (runs system checks for configuration flaws)

#### `config/settings.py`
The master configuration file for the entire Django instance. It specifies:
* Security settings (`SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`).
* Application registry (`INSTALLED_APPS`).
* Request/Response pipeline (`MIDDLEWARE`).
* Database routing (`DATABASES`).
* Password hashers, internationalization, timezones (`USE_TZ = True`), and static file locations.

#### `config/urls.py`
The top-level URL dispatcher. It maintains the master `urlpatterns` list. All incoming HTTP requests enter through this file and are delegated to specific application route tables using Django's `include()` function.

#### `config/wsgi.py` and `config/asgi.py`
* **WSGI (`wsgi.py`):** Web Server Gateway Interface — standard synchronous entry point for production web servers (e.g., Gunicorn).
* **ASGI (`asgi.py`):** Asynchronous Server Gateway Interface — enables asynchronous protocols such as WebSockets for real-time live ambulance GPS streaming and ESP32 event delivery.

---

## Section E: Django and PostgreSQL Integration

### 1. The Role of the Psycopg Driver
Python cannot communicate with PostgreSQL out of the box without a database adapter.
* **`psycopg` (Version 3)** is the official, high-performance PostgreSQL driver for Python.
* It opens TCP/IP socket connections to port 5432 on PostgreSQL, translates Python data types (strings, integers, datetimes, UUIDs) into PostgreSQL data types, and transmits compiled SQL statements over the wire.
* When Django queries the database (e.g., `Ambulance.objects.all()`), the Django ORM generates the SQL string, passes it to `psycopg`, and `psycopg` receives the raw binary response from PostgreSQL and transforms it into Python objects.

### 2. Environment Variable Loading (`python-dotenv`)
To protect database passwords and cryptographic keys from accidental exposure in version control, secrets are decoupled from the code and stored in `E:\sertos\.env`.

The integration in `config/settings.py` is configured as follows:
```python
import os
from pathlib import Path
from dotenv import load_dotenv

# Define BASE_DIR as the project root (E:\sertos)
BASE_DIR = Path(__file__).resolve().parent.parent

# Load variables from .env located at BASE_DIR / '.env'
load_dotenv(BASE_DIR / ".env")
```

### 3. Database Settings Configuration
The `DATABASES` setting in `config/settings.py` dynamically extracts database credentials from the environment:
```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DB_NAME"],
        "USER": os.environ["DB_USER"],
        "PASSWORD": os.environ["DB_PASSWORD"],
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}
```

### 4. Connection Verification Evidence
The database connection was formally verified using two authoritative Django management commands:

#### Test 1: Django System Diagnostics Check
```powershell
.\.venv\Scripts\python.exe manage.py check
```
* **Output:**
  ```text
  System check identified no issues (0 silenced).
  ```
* **What this proves:** Django inspected all settings, verified database backend configuration syntax, and confirmed the project is free of syntax or architectural errors.

#### Test 2: Database Migration Status
```powershell
.\.venv\Scripts\python.exe manage.py showmigrations
```
* **Output:**
  ```text
  admin
   [X] 0001_initial
   [X] 0002_logentry_remove_auto_add
   [X] 0003_logentry_add_action_flag_choices
  auth
   [X] 0001_initial
   [X] 0002_alter_permission_name_max_length
   [X] 0003_alter_user_email_max_length
   [X] 0004_alter_user_username_opts
   [X] 0005_alter_user_last_login_null
   [X] 0006_require_contenttypes_0002
   [X] 0007_alter_validators_add_error_messages
   [X] 0008_alter_user_username_max_length
   [X] 0009_alter_user_last_name_max_length
   [X] 0010_alter_group_name_max_length
   [X] 0011_update_proxy_permissions
   [X] 0012_alter_user_first_name_max_length
  contenttypes
   [X] 0001_initial
   [X] 0002_remove_content_type_name
  sessions
   [X] 0001_initial
  ```
* **What this proves:** Django established a live TCP connection to PostgreSQL on port 5432, queried the `django_migrations` table inside `sertos_db`, verified applied migrations, and returned the complete status without exception.

---

## Section F: Initial Database Migrations

### 1. What Are Migrations?
In Django, **migrations** are Python files that record changes made to your data models (such as creating a table, adding a column, or deleting an index). They act as a version control system for your database schema.

### 2. Why Migrations Are Required
* **Eliminates Manual SQL:** Developers do not need to manually write raw `CREATE TABLE` or `ALTER TABLE` DDL queries across multiple environments.
* **Consistency:** Ensures the exact same database structure is replicated across development, testing, staging, and production servers.
* **Safety:** Django tracks which migrations have already run by storing records in a special database table called `django_migrations`.

### 3. Built-in Applications Migrated in `sertos_db`
During initial setup, Django applied migrations for its foundational built-in applications:

| Application | Migration Files Applied | Database Tables Created in PostgreSQL | Purpose |
| :--- | :--- | :--- | :--- |
| **`contenttypes`** | `0001_initial`<br>`0002_remove_content_type_name` | `django_content_type` | Tracks all installed models in the Django project, enabling generic relationships across apps. |
| **`auth`** | `0001_initial` through `0012_alter_user_first_name_max_length` | `auth_user`<br>`auth_group`<br>`auth_permission`<br>`auth_user_groups`<br>`auth_user_user_permissions`<br>`auth_group_permissions` | Core authentication framework: handles user accounts, password hashing (PBKDF2/SHA256), group roles, and permission flags. |
| **`admin`** | `0001_initial`<br>`0002_logentry_remove_auto_add`<br>`0003_logentry_add_action_flag_choices` | `django_admin_log` | Django Admin site logging table: tracks actions (add, change, delete) performed by administrators. |
| **`sessions`** | `0001_initial` | `django_session` | Stores server-side web session cookies and user login state securely in the database. |

---

## Section G: Errors Encountered and Solutions

Real-world backend engineering involves debugging environment, path, and configuration issues. Here is the formal record of actual problems encountered during setup and how they were resolved:

### Issue 1: PostgreSQL Command-Line Tool (`psql`) Not Recognized
* **Error:** Executing `psql` in PowerShell resulted in:
  ```text
  psql : The term 'psql' is not recognized as the name of a cmdlet, function, script file, or operable program.
  ```
* **Cause:** The PostgreSQL installation wizard places executables in `C:\Program Files\PostgreSQL\18\bin`, which is not included in the default Windows `PATH` environment variable.
* **Solution:** Added `C:\Program Files\PostgreSQL\18\bin` to the Windows System Environment Variables `PATH` and restarted the shell session.
* **Verification:** Executed `psql --version`, which returned `psql (PostgreSQL) 18.7`, confirming global CLI accessibility.

### Issue 2: PostgreSQL Server Discovery and Listening Port
* **Error:** Initial client connection attempt returned connection refused or could not locate the server socket.
* **Cause:** Ambiguity on whether the PostgreSQL service was running or if the Windows firewall blocked port 5432.
* **Solution:** Checked the Windows Services console (`services.msc`), confirmed service `postgresql-x64-18` status was set to **Running** and Startup Type was **Automatic**.
* **Verification:** Tested TCP connection on `127.0.0.1:5432`, successfully verifying active socket handshake.

### Issue 3: Missing Django Project Configuration
* **Error:** Running `python manage.py runserver` failed with:
  ```text
  python: can't open file 'E:\sertos\manage.py': [Errno 2] No such file or directory
  ```
* **Cause:** The project root was created as an empty folder without running the Django project initialization command.
* **Solution:** Executed `django-admin startproject config .` inside `E:\sertos` to generate the root `manage.py` and `config/` orchestration folder.
* **Verification:** Verified `manage.py` exists at `E:\sertos\manage.py` and `config/settings.py` was created.

### Issue 4: `load_dotenv` Module Import Failure
* **Error:** Starting Django threw `NameError: name 'load_dotenv' is not defined` or `ModuleNotFoundError: No module named 'dotenv'`.
* **Cause:** `load_dotenv()` was referenced in `settings.py` before installing `python-dotenv` into the active `.venv`, or the import statement `from dotenv import load_dotenv` was missing.
* **Solution:** Ran `pip install python-dotenv` in the activated virtual environment and placed `from dotenv import load_dotenv` at the top of `settings.py`.
* **Verification:** Executed `python -c "import dotenv; print(dotenv.__file__)"` inside `.venv`, confirming clean package resolution.

### Issue 5: Redundant Environment Loading & Formatting in `settings.py`
* **Error / Flaw:** Inspection of `config/settings.py` revealed duplicated initialization code:
  * Lines 11–13 defined `BASE_DIR` and called `load_dotenv()`.
  * Lines 15–19 redundantly redefined `BASE_DIR = Path(__file__).resolve().parent.parent` and called `load_dotenv()` a second time.
* **Cause:** Successive manual edits and copy-pasting during initial database configuration created redundant instructions.
* **Solution:** Documented the redundant lines to be cleaned up during Phase 2 baseline hardening. Verified that the current execution is still valid and loads environment variables without crashing.
* **Verification:** Confirmed database parameters resolve correctly via `os.environ["DB_NAME"]` during `python manage.py check`.

---

## Section H: Current Project Status

To maintain engineering integrity, we clearly distinguish between what is **completed**, what is **configured but pending refinement**, and what is **not yet implemented**.

```
[COMPLETED & VERIFIED] ========================================> 35%
[CONFIGURED BUT PENDING REFINEMENT] ===============> 0%
[NOT YET IMPLEMENTED (UPCOMING MODULES)] =======================> 65%
```

### 1. Completed and Verified (Operational)
* [x] Python 3.13.3 virtual environment (`.venv`) established and active.
* [x] Django 5.2.19 and Django REST Framework 3.18.3 installed in `.venv`.
* [x] `psycopg` 3.3.9 PostgreSQL driver and `python-dotenv` installed.
* [x] `django-cors-headers` 4.9.0 installed and configured in `MIDDLEWARE`.
* [x] PostgreSQL 18.7 service active and running on port 5432.
* [x] Dedicated database `sertos_db` created on PostgreSQL.
* [x] `.env` configuration file created, holding DB credentials, random `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, and `CORS_ALLOWED_ORIGINS`.
* [x] `.env.example` created as a sanitized template for team deployments.
* [x] Root `.gitignore` created and verified; misplaced `config/.gitignore` safely removed.
* [x] Git repository initialized (`git init`); verified `.env`, `.venv`, and cache files are strictly ignored.
* [x] `config/settings.py` hardened: redundant dotenv blocks removed, secrets loaded from `.env`, `rest_framework` and `corsheaders` registered.
* [x] Custom User model (`apps.accounts.models.User`) created extending `AbstractUser` with human roles (Admin, Ambulance Driver, Hospital Staff, Police Dispatcher).
* [x] `AUTH_USER_MODEL = "accounts.User"` configured in `config/settings.py`.
* [x] Initial migration `apps/accounts/migrations/0001_initial.py` generated via `makemigrations accounts`.
* [x] Pre-reset safety inspection verified: exactly 10 initial tables, 0 user rows, 0 business rows.
* [x] PostgreSQL pre-reset backup generated via `pg_dump` (22,629 bytes) stored safely in scratch directory outside Git.
* [x] Approved database reset executed: `sertos_db` dropped and recreated with `ENCODING='UTF8'` and `OWNER=postgres`.
* [x] Fresh migrations executed cleanly: `accounts.0001_initial` applied before `admin.0001_initial`.
* [x] PostgreSQL schema verified: `accounts_user` is active primary user table; `auth_user` was never created; `django_admin_log.user_id` foreign key references `accounts_user.id`.
* [x] User model verified via creation, query, property testing, and teardown of a temporary test user.
* [x] Django system check (`python manage.py check`) passing with 0 errors.
* [x] `djangorestframework-simplejwt` 5.3.1 (with `pyjwt` 2.15.1) installed in `.venv` (Step 3.1).
* [x] DRF and SimpleJWT configured in `config/settings.py` with `token_blacklist`, `JWTAuthentication`, and rotation (Step 3.2).
* [x] SimpleJWT `token_blacklist` migrations applied to PostgreSQL; `token_blacklist_outstandingtoken` and `token_blacklist_blacklistedtoken` tables created (Step 3.3).
* [x] Authentication serializers implemented (`CustomTokenObtainPairSerializer`, `UserRegistrationSerializer`, `UserProfileSerializer`) and 10 focused automated tests passing (Step 3.4).
* [x] Role-Based Access Control (RBAC) permissions implemented (`IsSystemAdmin`, `IsAmbulanceDriver`, `IsHospitalStaff`, `IsPoliceDispatcher`, `IsVerifiedPersonnel`) and 17 automated tests passing (Step 3.5).
* [x] Authentication API views implemented (`LoginView`, `TokenRefreshView`, `LogoutView`, `RegisterView`, `ProfileView`) with standard response envelope and 31 automated tests passing (Step 3.6).

### 2. Configured But Pending Refinement / Explicit Approval
* None. The core project foundation, security hygiene, database engine, and custom user model are 100% complete, verified, and operational.

### 3. Not Yet Implemented (Upcoming Domain Modules)
* [ ] Custom domain applications (`emergencies`, `ambulances`, `hospitals`, `traffic`, `audit_logs`).
* [ ] Dedicated ESP32 hardware authentication token model in `traffic` app.
* [ ] Business database models for Ambulances, GPS Telemetry, Hospital Beds, Incidents, Traffic Junctions.
* [ ] REST API Endpoints, Serializers, and ViewSets.
* [ ] Role-Based Access Control (RBAC) & JWT Token authentication endpoints (`/api/v1/auth/login/`).
* [ ] AI Voice ingestion webhook endpoint (`/api/v1/emergencies/voice-webhook/`).
* [ ] ESP32 hardware communication endpoint.
* [ ] Automated Unit and Integration Test Suites.

---

## Section I: Mentor Explanation (Speaking Points)

When presenting this project to a technical mentor, professor, or interviewer, use these structured speaking points:

### 1. What have I implemented so far?
> *"So far, I have architected and established the foundation for SERTOS—an emergency response coordination backend. I configured an isolated Python 3.13 virtual environment, installed Django 5.2 and Django REST Framework, installed and configured PostgreSQL 18.7 as our primary relational database, and integrated them using the Psycopg 3 driver. I secured our database credentials using environment variables with `python-dotenv`, created the `sertos_db` database, and successfully applied the initial core migrations."*

### 2. Why did I choose Django?
> *"Django was chosen because emergency coordination requires high reliability, rapid development, and strict security out of the box. Django comes with built-in protection against SQL injection, Cross-Site Request Forgery (CSRF), and Clickjacking. Additionally, Django's Object-Relational Mapping (ORM) allows us to design our database schema in clean, readable Python code and automatically handle complex migrations."*

### 3. Why did I choose PostgreSQL?
> *"PostgreSQL is an industry-standard, ACID-compliant relational database. In SERTOS, we handle critical data where integrity is paramount: incident logs, triage vitals, and traffic signal states cannot be lost or corrupted. Furthermore, PostgreSQL provides native JSONB support for semi-structured AI voice data, and offers PostGIS spatial extensions which will allow us to execute proximity queries for emergency vehicles and traffic intersections."*

### 4. What is the role of Django REST Framework (DRF)?
> *"Django by itself is built to render HTML web pages. However, SERTOS must connect multiple heterogeneous clients: an Android app for ambulances, React/Vue web dashboards for hospitals and police, and C++ firmware running on ESP32 microcontrollers. Django REST Framework transforms Django into a pure API backend that serializes our database models into standard JSON and exposes RESTful HTTP endpoints that any client can consume."*

### 5. How does Django communicate with PostgreSQL?
> *"Django does not communicate with PostgreSQL directly; it uses an adapter called `psycopg` (version 3). When our code performs an operation—such as querying a record—the Django ORM generates the SQL statement. The Psycopg driver takes that SQL, connects to PostgreSQL over TCP port 5432, handles the low-level network protocol, executes the query, and converts PostgreSQL's tabular result back into Python objects."*

### 6. What do database migrations actually do?
> *"Migrations are like Git for our database schema. Instead of writing manual `CREATE TABLE` or `ALTER TABLE` SQL commands, we define our data models in Python. When we run `makemigrations`, Django writes a Python migration script that outlines the schema changes. When we run `migrate`, Django executes those changes against PostgreSQL and records the execution in the `django_migrations` table so that no migration is applied twice."*

### 7. How did I test and verify the database connection?
> *"I ran `python manage.py showmigrations` and `python manage.py check`. The `showmigrations` command connects directly to PostgreSQL, queries the `django_migrations` table, and verifies that all core migrations for authentication, admin, and sessions are present. The `check` command ran all system checks and confirmed zero issues with our settings or configuration."*

---

## Section J: Mentor Viva Questions and Answers

Here are 22 technical questions commonly asked during academic or industry project reviews, along with beginner-friendly, precise answers:

#### Q1: What is SERTOS and what core problem does it solve?
**Answer:** SERTOS is an emergency response coordination platform that connects ambulances, hospitals, police, AI voice dispatch, and traffic lights to eliminate emergency transit delays and prepare hospital emergency departments before the patient arrives.

#### Q2: What is the difference between a project and an app in Django?
**Answer:** In Django, a **project** (such as our `config` folder) is the entire website/system configuration containing global settings, database connections, and master URLs. An **app** is a self-contained, modular Python package within the project that handles one specific domain (e.g., `ambulances`, `hospitals`, `accounts`).

#### Q3: Why do we use a virtual environment (`.venv`)?
**Answer:** A virtual environment isolates project-specific Python packages from the global operating system. This prevents dependency version conflicts between different projects and ensures reproducibility.

#### Q4: What is `manage.py` and what is its role?
**Answer:** `manage.py` is an auto-generated command-line tool for your Django project. It acts as an entry point to execute commands like running the server, creating migrations, creating superusers, and running tests.

#### Q5: What does the command `django-admin startproject config .` do?
**Answer:** It creates a Django project configuration directory named `config` in the current folder, with `manage.py` placed directly in the current working directory, avoiding redundant nested directories.

#### Q6: What is an ORM and what are its advantages?
**Answer:** ORM stands for **Object-Relational Mapping**. It allows developers to interact with the database using Python objects and methods instead of writing raw SQL queries. Advantages include database independence, automatic SQL injection prevention, and faster development.

#### Q7: What is the purpose of `psycopg`?
**Answer:** `psycopg` is the PostgreSQL database driver/adapter for Python. It provides the low-level networking and protocol implementation necessary for Django's ORM to send SQL commands to and receive data from PostgreSQL.

#### Q8: Why do we keep database credentials in a `.env` file instead of `settings.py`?
**Answer:** Security. Hardcoding database passwords and secret keys in `settings.py` risks exposing them if the code is pushed to a public or team Git repository. Using `.env` keeps secrets separate from source code.

#### Q9: What is `python-dotenv` and how does it work?
**Answer:** `python-dotenv` is a Python library that reads key-value pairs from a `.env` file at project startup and injects them into `os.environ` so they can be securely accessed in Python using `os.getenv()`.

#### Q10: What does `python manage.py makemigrations` do?
**Answer:** It inspects your Python models across all installed apps, detects changes compared to previous migration files, and generates new Python migration files containing the instructions for schema updates.

#### Q11: What does `python manage.py migrate` do?
**Answer:** It reads the unapplied migration files and executes the corresponding SQL DDL statements (like `CREATE TABLE`, `ADD COLUMN`) on the connected PostgreSQL database, then marks them as applied in `django_migrations`.

#### Q12: What is the purpose of the `django_migrations` table?
**Answer:** It is an internal tracking table in PostgreSQL managed by Django. Every time a migration is executed, a row with the app name, migration name, and timestamp is inserted to ensure migrations are only executed once.

#### Q13: Why is `ALLOWED_HOSTS` important in Django?
**Answer:** `ALLOWED_HOSTS` is a security measure against HTTP Host header attacks. It specifies a list of host/domain names that this Django site can serve. Any incoming request with an unlisted Host header is rejected with an HTTP 400 Bad Request.

#### Q14: What is the role of `SECRET_KEY` in `settings.py`?
**Answer:** `SECRET_KEY` is a cryptographic salt used by Django for security features including cryptographic signing, session hashing, CSRF tokens, and password reset tokens. It must never be made public.

#### Q15: Why is `DEBUG = True` dangerous in production?
**Answer:** When `DEBUG = True`, any unhandled error triggers a detailed traceback page that displays source code, environment variables, settings, and database query details to the end-user, exposing critical system vulnerabilities.

#### Q16: What is the difference between synchronous WSGI and asynchronous ASGI?
**Answer:** WSGI handles standard synchronous request-response cycles one by one per thread. ASGI supports asynchronous protocols, allowing the server to handle persistent, concurrent connections such as WebSockets, which is essential for real-time GPS tracking.

#### Q17: What built-in apps were migrated when we ran our initial migrations?
**Answer:** 
1. `contenttypes` (tracks all models in the system)
2. `auth` (handles users, permissions, and password security)
3. `admin` (powers the Django administrative interface)
4. `sessions` (manages user session state in the database)

#### Q18: What is Django REST Framework (DRF) and why can't we just use plain Django?
**Answer:** Plain Django is optimized for returning full HTML pages via templates. DRF provides specialized tools for REST APIs: Serializers (converting model instances to/from JSON), APIView/ViewSets, token authentication, request parsing, and HTTP status code standards.

#### Q19: What is a Serializer in DRF?
**Answer:** A Serializer converts complex data types, like Django model querysets, into native Python data types that can easily be rendered into JSON. It also deserializes and validates incoming JSON payloads before saving them to the database.

#### Q20: Why should we use a custom User model (`AbstractUser`) in Django?
**Answer:** Django's default `auth_user` model is basic (username, email, password). In SERTOS, users require specific roles (Ambulance Driver, Hospital Doctor, Police Officer, IoT Device). Extending `AbstractUser` early allows us to add custom role fields without breaking future database relationships.

#### Q21: How will the ESP32 microcontroller communicate with the SERTOS backend?
**Answer:** The ESP32 will connect to local WiFi/cellular and send authenticated HTTP GET or POST requests to dedicated traffic endpoints (e.g., `/api/v1/traffic/esp32/signal-command/`) using a pre-shared hardware token header to receive corridor instructions.

#### Q22: How will the AI Voice-Processing module interact with the backend?
**Answer:** The AI module will process caller audio, extract symptoms and GPS coordinates, and send an HTTP `POST` webhook to `/api/v1/emergencies/voice-webhook/`. The backend validates the payload, generates an `EmergencyIncident`, and notifies dispatchers.

---

## Section K: Next Development Roadmap

With the environment, database, and migrations verified, the project will follow this sequential development path:

```
[Phase 1: Setup & Audit] (DONE)
          │
          ▼
[Phase 2: Baseline Hardening & Documentation] ◄── NEXT STEP
  - Initialize Git & root .gitignore
  - Migrate SECRET_KEY & DEBUG to .env
  - Register rest_framework in settings.py
  - Create architecture documentation in docs/
          │
          ▼
[Phase 3: User Authentication & Role RBAC]
  - Create apps/accounts with Custom User model (AbstractUser)
  - Define user roles: AMBULANCE, HOSPITAL, POLICE, ADMIN
  - Implement JWT Token Authentication (/api/v1/auth/login/)
          │
          ▼
[Phase 4: Emergency Incident & AI Voice Webhook]
  - Create apps/emergencies (EmergencyIncident, VoiceCallLog)
  - Implement AI voice ingestion webhook endpoint
          │
          ▼
[Phase 5: Ambulance Fleet & Telemetry Pipeline]
  - Create apps/ambulances (Ambulance, AmbulanceTrip, TelemetryPing)
  - Implement high-frequency GPS ingestion API
          │
          ▼
[Phase 6: Hospital Dashboard & Resource Feed]
  - Create apps/hospitals (Hospital, BedAvailability, PatientAdmission)
  - Implement incoming triage feed with live ETA
          │
          ▼
[Phase 7: Police Dashboard & ESP32 Traffic Signals]
  - Create apps/traffic (TrafficJunction, GreenCorridorSession)
  - Implement ESP32 device token authentication & signal preemption endpoint
          │
          ▼
[Phase 8: End-to-End Testing & Verification]
  - Mock complete pipeline: Call -> Incident -> Ambulance -> Signal -> Hospital
  - Produce comprehensive test report
```

---

## Section L: Ongoing Documentation Protocol

In compliance with the project's engineering rules, this document will be maintained continuously:
1. **After every approved task:** Update `docs/IMPLEMENTATION_EXPLANATION.md`.
2. **Record changes:** List all files created, modified, or removed.
3. **Record commands & tests:** Save exact CLI commands and test outputs.
4. **Update status:** Move features from "Not yet implemented" to "Completed and verified".
5. **Add viva questions:** Add at least 2 new mentor Q&A pairs for every new module implemented.

---

## Section M: Stage 2.1 & Stage 2.2 Implementation Record

### 1. Stage 2.1 – Baseline Hardening & Git Hygiene

#### Overview
Transformed the default Django setup into a hardened, version-controlled architecture with zero secret leakage and full cross-origin resource support.

#### Files Created, Modified, and Deleted
* **Created:**
  * `E:\sertos\.gitignore` — Project root gitignore covering virtual environments, environment files, cache, and database artifacts.
  * `E:\sertos\.env.example` — Sanitized deployment template with dummy values.
* **Modified:**
  * `E:\sertos\.env` — Appended high-entropy `SECRET_KEY`, `DEBUG=True`, `ALLOWED_HOSTS`, and `CORS_ALLOWED_ORIGINS`.
  * `E:\sertos\config\settings.py` — Cleaned up duplicate imports, loaded `SECRET_KEY` and `DEBUG` from `.env`, registered `rest_framework` and `corsheaders`, configured `CORS_ALLOWED_ORIGINS`, and added `CorsMiddleware`.
* **Deleted:**
  * `E:\sertos\config\.gitignore` — Removed misplaced configuration-level gitignore.
* **Commands Executed:**
  ```powershell
  # Package Installation
  .\.venv\Scripts\python.exe -m pip install django-cors-headers

  # Git Initialization and Secret Protection Verification
  git init
  git status --ignored
  ```
* **Verification Output:**
  ```text
  On branch master
  No commits yet
  Untracked files:
    .env.example, .gitignore, config/, docs/, manage.py
  Ignored files:
    .env, .venv/, .vscode/, config/__pycache__/
  ```
  `.env` and `.venv` are strictly ignored by Git.

---

### 2. Stage 2.2 – Custom User Model & Migration Generation

#### Overview
Introduced the domain-driven custom `User` model inheriting from `django.contrib.auth.models.AbstractUser`, adding role-based access control (RBAC) specifically tailored for emergency response coordination.

#### Architectural Separation of Human Roles vs. IoT Hardware
Per architecture review:
* Human actors (`ADMIN`, `AMBULANCE_DRIVER`, `HOSPITAL_STAFF`, `POLICE_DISPATCHER`) are managed through `apps.accounts.models.User`.
* ESP32 IoT hardware devices will **not** be treated as human users; they will be authenticated in `apps/traffic` using dedicated hardware device tokens and SHA-256 API keys.

#### Files Created and Modified
* **Created:**
  * `E:\sertos\apps\__init__.py` — Root container package for domain applications.
  * `E:\sertos\apps\accounts\__init__.py` — Application configuration hook.
  * `E:\sertos\apps\accounts\apps.py` — Declares `name = "apps.accounts"` and `label = "accounts"`.
  * `E:\sertos\apps\accounts\models.py` — Defines `UserRole` choices, custom `User(AbstractUser)` model with `role`, `phone_number`, `badge_or_employee_id`, and `is_verified`.
  * `E:\sertos\apps\accounts\admin.py` — Registers `User` in Django Admin using extended `UserAdmin`.
  * `E:\sertos\apps\accounts\migrations\0001_initial.py` — Auto-generated initial migration.
* **Modified:**
  * `E:\sertos\config\settings.py` — Added `"apps.accounts"` to `INSTALLED_APPS` and configured `AUTH_USER_MODEL = "accounts.User"`.
* **Commands Executed:**
  ```powershell
  # Generate migration file without altering database
  .\.venv\Scripts\python.exe manage.py makemigrations accounts
  ```
* **Verification Output:**
  ```text
  Migrations for 'accounts':
    apps\accounts\migrations\0001_initial.py
      + Create model User
  ```

---

### 3. Pre-Reset Database Verification Evidence
Before proposing any database reset, the live contents of PostgreSQL `sertos_db` were forensically inspected:
```text
Total tables found: 10
Tables list: ['auth_group', 'auth_group_permissions', 'auth_permission', 'auth_user', 'auth_user_groups', 'auth_user_user_permissions', 'django_admin_log', 'django_content_type', 'django_migrations', 'django_session']

Row counts per table:
  - auth_group: 0 rows
  - auth_group_permissions: 0 rows
  - auth_permission: 24 rows (Django default generated permissions)
  - auth_user: 0 rows (ZERO USERS)
  - auth_user_groups: 0 rows
  - auth_user_user_permissions: 0 rows
  - django_admin_log: 0 rows (ZERO ADMIN LOGS)
  - django_content_type: 6 rows (Django default content types)
  - django_migrations: 18 rows
  - django_session: 0 rows (ZERO SESSIONS)

Total business/user records in sertos_db: 0
```
**Conclusion:** There is **zero business data and zero user records** in `sertos_db`.

---

### 4. New Mentor Viva Questions (Stage 2.1 & 2.2)

#### Q23: Why must CORS middleware be placed at the very top of `MIDDLEWARE` in `settings.py`?
**Answer:** `CorsMiddleware` handles incoming HTTP `OPTIONS` preflight requests sent by modern web browsers before making actual cross-origin requests. Placing it at the very top ensures CORS headers are attached to every response, even if subsequent middleware components fail or redirect.

#### Q24: Why is it crucial to initialize Git ONLY AFTER placing `.gitignore` at the project root?
**Answer:** If `git init` and `git add .` are run without a root `.gitignore`, sensitive files like `.env` and massive folders like `.venv/` (thousands of third-party files) get indexed and committed into Git history. Even if deleted in later commits, secrets remain in Git commit history permanently unless forcefully purged with repository rewriting tools.

#### Q25: Why did we keep ESP32 hardware authentication separate from the custom `User` model?
**Answer:** Microcontroller IoT devices do not have human identities, passwords, sessions, or roles like "hospital staff" or "ambulance driver". Treating IoT hardware as human `User` accounts violates separation of concerns, introduces security risks (if device credentials leak, user tables are exposed), and clutters the user database. ESP32 devices authenticate via dedicated hardware tokens/API keys managed in the traffic domain.

#### Q26: What is the purpose of `label = "accounts"` in `apps/accounts/apps.py`?
**Answer:** When Django applications are organized inside a subfolder like `apps/accounts/`, Django default app labeling might resolve to `apps_accounts`. Setting `label = "accounts"` explicitly ensures that `AUTH_USER_MODEL = "accounts.User"` resolves cleanly and consistently across foreign keys and admin logs.

---

## Section N: Stage 2.2 Execution Record: Approved Database Reset & Fresh Migrations

### 1. Safety Verification & Forensic Inspection
Prior to database modification, safety checks were conducted:
* Checked `AUTH_USER_MODEL = "accounts.User"`.
* Checked `apps.accounts` app config (`name = "apps.accounts"`, `label = "accounts"`).
* Checked `apps.accounts.models.User` (extending `AbstractUser`).
* Verified `accounts/migrations/0001_initial.py` existed.
* Confirmed database contents: `auth_user` = 0 rows, `django_admin_log` = 0 rows, business records = 0 rows.

### 2. Pre-Reset Backup Details
* **Tool Used:** `pg_dump.exe` (PostgreSQL 18.7).
* **Backup File Location:** `C:\Users\Khaja H\.gemini\antigravity\brain\bbba7e8c-1a11-4a98-be5c-c9e16376e53a\scratch\sertos_db_backup_pre_reset.sql`.
* **Backup File Size:** 22,629 bytes (~22.6 KB).
* **Storage Location:** Strictly outside the Git-tracked workspace `E:\sertos` to avoid repository pollution and prevent secret leaks.

### 3. Database Reset Execution
Connected to PostgreSQL maintenance catalog `postgres` with `autocommit=True`:
1. Terminated any active connections to `sertos_db`:
   ```sql
   SELECT pg_terminate_backend(pid) 
   FROM pg_stat_activity 
   WHERE datname = 'sertos_db' AND pid <> pg_backend_pid();
   ```
2. Dropped the empty development database:
   ```sql
   DROP DATABASE IF EXISTS sertos_db;
   ```
3. Recreated `sertos_db` with standard encoding and ownership:
   ```sql
   CREATE DATABASE sertos_db WITH OWNER postgres ENCODING 'UTF8';
   ```
4. Verified database attributes: `datname = 'sertos_db'`, `encoding = 'UTF8'`, `owner = 'postgres'`.

### 4. Fresh Migration Execution
Executed clean migration on the fresh database:
```powershell
python manage.py showmigrations
python manage.py migrate
```

**Actual Execution Log:**
```text
Operations to perform:
  Apply all migrations: accounts, admin, auth, contenttypes, sessions
Running migrations:
  Applying contenttypes.0001_initial... OK
  Applying contenttypes.0002_remove_content_type_name... OK
  Applying auth.0001_initial... OK
  Applying auth.0002_alter_permission_name_max_length... OK
  Applying auth.0003_alter_user_email_max_length... OK
  Applying auth.0004_alter_user_username_opts... OK
  Applying auth.0005_alter_user_last_login_null... OK
  Applying auth.0006_require_contenttypes_0002... OK
  Applying auth.0007_alter_validators_add_error_messages... OK
  Applying auth.0008_alter_user_username_max_length... OK
  Applying auth.0009_alter_user_last_name_max_length... OK
  Applying auth.0010_alter_group_name_max_length... OK
  Applying auth.0011_update_proxy_permissions... OK
  Applying auth.0012_alter_user_first_name_max_length... OK
  Applying accounts.0001_initial... OK
  Applying admin.0001_initial... OK
  Applying admin.0002_logentry_remove_auto_add... OK
  Applying admin.0003_logentry_add_action_flag_choices... OK
  Applying sessions.0001_initial... OK
```

### 5. Post-Reset Database & Model Verification
A verification script was executed against PostgreSQL and Django ORM:
```text
1. Active User Model: accounts.User
   Database Table: accounts_user

2. Total tables created in sertos_db: 10
   Tables list: ['accounts_user', 'accounts_user_groups', 'accounts_user_user_permissions', 
                 'auth_group', 'auth_group_permissions', 'auth_permission', 
                 'django_admin_log', 'django_content_type', 'django_migrations', 'django_session']

3. Table presence verification:
   - 'accounts_user' exists: True
   - 'auth_user' exists: False

4. Foreign Key Constraints in django_admin_log:
   - django_admin_log.content_type_id -> django_content_type.id
   - django_admin_log.user_id -> accounts_user.id

5. Testing User Creation, Query & Teardown:
   - Created test user: test_driver_audit
   - Role: AMBULANCE_DRIVER | Display: Ambulance Driver / Paramedic
   - is_ambulance_driver property: True
   - Saved in table: True
   - Cleaned up test user. Exists now?: False
```

### 6. Additional Mentor Viva Questions (Q27 to Q30)

#### Q27: Why did `auth_user` not get created in our fresh database?
**Answer:** In Django, the `auth.0001_initial` migration contains logic checking `settings.AUTH_USER_MODEL`. If `AUTH_USER_MODEL` points to a custom model (like `accounts.User`), Django intentionally skips the `CreateModel` operation for `auth_user` and only creates permission and group tables (`auth_group`, `auth_permission`). The user table is then cleanly created by `accounts.0001_initial` as `accounts_user`.

#### Q28: How do we know `django_admin_log` is pointing to the right table?
**Answer:** We queried PostgreSQL's `information_schema.table_constraints` and `constraint_column_usage`. The output verified that `django_admin_log.user_id` has a direct foreign key constraint referencing `accounts_user.id`, confirming 100% relational integrity.

#### Q29: What would have happened if we ran `python manage.py migrate` without resetting the database?
**Answer:** `django_admin_log` would have retained its old foreign key pointing to the deprecated `auth_user` table. Any future admin actions (like logging which admin updated an ambulance driver) would have failed with relational foreign key constraint violations or orphaned records.

#### Q30: Why is it important to create a backup even on a development database with 0 user records?
**Answer:** Practicing the backup discipline (`pg_dump`) before any destructive action (`DROP DATABASE`) ensures that development habits match production standards. It guarantees that if any unintended schema, function, or extension existed in the catalog, it can be restored immediately without downtime.



---

## Section O: Phase 3 – Step 3.1: JWT Dependency Installation Record

### 1. Task Execution
* **Package Installed:** `djangorestframework-simplejwt==5.3.1`
* **Dependency Resolved & Installed:** `pyjwt==2.15.1`
* **Active Interpreter Confirmed:** `E:\sertos\.venv\Scripts\python.exe`
* **Execution Command:**
  ```powershell
  .\.venv\Scripts\python.exe -m pip install djangorestframework-simplejwt==5.3.1
  ```

### 2. Verification Command Outputs
* **Package Details Verification (`pip show`):**
  ```text
  Name: djangorestframework-simplejwt
  Version: 5.3.1
  Summary: A minimal JSON Web Token authentication plugin for Django REST Framework
  Location: E:\sertos\.venv\Lib\site-packages
  Requires: django, djangorestframework, pyjwt
  ```
* **Python Runtime Import & Version Check:**
  ```text
  SimpleJWT import successful
  Django version: 5.2.19
  DRF version: 3.18.3
  SimpleJWT version: 5.3.1
  ```
* **Integrity Status:** Django, Django REST Framework, and SimpleJWT import cleanly without conflict. No configuration or application files have been modified yet in accordance with Step 3.1 boundaries.

---

## Section P: Phase 3 – Step 3.2: JWT Configuration Record

### 1. Task Execution & Settings Update
* **File Modified:** `E:\sertos\config\settings.py`
* **Added `from datetime import timedelta`** to support token lifetime definitions.
* **Registered Blacklist Application in `INSTALLED_APPS`:**
  ```python
  INSTALLED_APPS = [
      # Core Domain Applications
      "apps.accounts",

      # Core Django Applications
      "django.contrib.admin",
      "django.contrib.auth",
      "django.contrib.contenttypes",
      "django.contrib.sessions",
      "django.contrib.messages",
      "django.contrib.staticfiles",

      # Third-Party Applications
      "rest_framework",
      "rest_framework_simplejwt.token_blacklist",
      "corsheaders",
  ]
  ```
* **Configured `REST_FRAMEWORK` Authentication Classes:**
  ```python
  REST_FRAMEWORK = {
      "DEFAULT_AUTHENTICATION_CLASSES": (
          "rest_framework_simplejwt.authentication.JWTAuthentication",
          "rest_framework.authentication.SessionAuthentication",
      ),
      "DEFAULT_PERMISSION_CLASSES": (
          "rest_framework.permissions.IsAuthenticated",
      ),
      "DEFAULT_RENDERER_CLASSES": (
          "rest_framework.renderers.JSONRenderer",
          "rest_framework.renderers.BrowsableAPIRenderer",
      ),
  }
  ```
* **Configured `SIMPLE_JWT` Settings Dictionary:**
  ```python
  SIMPLE_JWT = {
      "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
      "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
      "ROTATE_REFRESH_TOKENS": True,
      "BLACKLIST_AFTER_ROTATION": True,
      "AUTH_HEADER_TYPES": ("Bearer",),
      "UPDATE_LAST_LOGIN": False,
      "LEEWAY": 30,
  }
  ```

### 2. Verification Command Outputs
* **Django System Diagnostic Check:**
  ```powershell
  .\.venv\Scripts\python.exe manage.py check
  ```
  ```text
  System check identified no issues (0 silenced).
  ```
* **Django Shell Configuration Verification:**
  ```powershell
  .\.venv\Scripts\python.exe manage.py shell -c "..."
  ```
  ```text
  1. AUTH_CLASSES: ('rest_framework_simplejwt.authentication.JWTAuthentication', 'rest_framework.authentication.SessionAuthentication')
  2. PERM_CLASSES: ('rest_framework.permissions.IsAuthenticated',)
  3. ACCESS_LIFETIME: 0:15:00
     REFRESH_LIFETIME: 7 days, 0:00:00
  4. ROTATE_REFRESH: True
     BLACKLIST_AFTER_ROTATION: True
  5. AUTH_USER_MODEL: accounts.User | Model: accounts.User
  6. BLACKLIST_APP_INSTALLED: True
  ```

### 3. Step 3.2 Boundary Enforcement
* **Migrations:** Zero migrations run. Database `sertos_db` was not modified.
* **Code Scope:** Only `config/settings.py` and `docs/IMPLEMENTATION_EXPLANATION.md` were modified.
* **Preservation:** `AUTH_USER_MODEL = "accounts.User"`, PostgreSQL database settings, CORS headers, password validators, and environment variable abstractions remain 100% intact.

---

## Section Q: Phase 3 – Step 3.3: Token Blacklist Database Migration Record

### 1. Pre-Migration Verification & Safety Checks
* **Active Interpreter:** `E:\sertos\.venv\Scripts\python.exe`
* **PostgreSQL Service:** Verified running on port 5432.
* **Registered App:** `rest_framework_simplejwt.token_blacklist` confirmed in `INSTALLED_APPS`.
* **Active User Model:** `accounts.User` (`accounts_user`).
* **Existing Migrations:** All 18 baseline migrations verified applied `[X]`.

### 2. Pre-Migration Backup Details
* **Tool Used:** PostgreSQL `pg_dump.exe` (v18.7).
* **Backup Location:** `C:\Users\Khaja H\.gemini\antigravity\brain\bbba7e8c-1a11-4a98-be5c-c9e16376e53a\scratch\sertos_db_backup_pre_step3_3.sql`
* **Backup Size:** 23,241 bytes (~23.2 KB).
* **Security Isolation:** Stored strictly outside the Git-tracked workspace `E:\sertos`.

### 3. Migration Plan Inspection
Inspected via `python manage.py showmigrations` and `python manage.py migrate --plan`.
Confirmed only the newly registered SimpleJWT blacklist application was pending:
* `token_blacklist.0001_initial`
* `token_blacklist.0002_outstandingtoken_jti_hex`
* `token_blacklist.0003_auto_20171017_2007`
* `token_blacklist.0004_auto_20171017_2013`
* `token_blacklist.0005_remove_outstandingtoken_jti`
* `token_blacklist.0006_auto_20171017_2113`
* `token_blacklist.0007_auto_20171017_2214`
* `token_blacklist.0008_migrate_to_bigautofield`
* `token_blacklist.0010_fix_migrate_to_bigautofield`
* `token_blacklist.0011_linearizes_history`
* `token_blacklist.0012_alter_outstandingtoken_user`

### 4. Migration Execution Output
Command: `.\.venv\Scripts\python.exe manage.py migrate`
```text
Operations to perform:
  Apply all migrations: accounts, admin, auth, contenttypes, sessions, token_blacklist
Running migrations:
  Applying token_blacklist.0001_initial... OK
  Applying token_blacklist.0002_outstandingtoken_jti_hex... OK
  Applying token_blacklist.0003_auto_20171017_2007... OK
  Applying token_blacklist.0004_auto_20171017_2013... OK
  Applying token_blacklist.0005_remove_outstandingtoken_jti... OK
  Applying token_blacklist.0006_auto_20171017_2113... OK
  Applying token_blacklist.0007_auto_20171017_2214... OK
  Applying token_blacklist.0008_migrate_to_bigautofield... OK
  Applying token_blacklist.0010_fix_migrate_to_bigautofield... OK
  Applying token_blacklist.0011_linearizes_history... OK
  Applying token_blacklist.0012_alter_outstandingtoken_user... OK
```

### 5. PostgreSQL Table & Constraint Verification
Executed post-migration query against PostgreSQL `sertos_db`:
```text
1. Active User Model: accounts.User
   Database Table: accounts_user

2. Total tables created in sertos_db: 12
   Tables list: ['accounts_user', 'accounts_user_groups', 'accounts_user_user_permissions', 
                 'auth_group', 'auth_group_permissions', 'auth_permission', 
                 'django_admin_log', 'django_content_type', 'django_migrations', 'django_session', 
                 'token_blacklist_blacklistedtoken', 'token_blacklist_outstandingtoken']

3. Blacklist Table presence verification:
   - 'token_blacklist_outstandingtoken' exists: True
   - 'token_blacklist_blacklistedtoken' exists: True

4. Foreign Key Constraints in token_blacklist_outstandingtoken:
   - token_blacklist_outstandingtoken.user_id -> accounts_user.id
```

### 6. Step 3.3 Boundary Enforcement
* **No APIs:** No serializers, views, permissions, or URLs were created.
* **No Test Records:** No test users or mock tokens were created in PostgreSQL.
* **Model Integrity:** `accounts.User` remains completely unmodified.
* **Step 3.4 Status:** Step 3.4 has not been started.

---

## Section R: Phase 3 – Step 3.4: Custom Authentication Serializers Record

### 1. Serializer Classes Implemented (`apps/accounts/serializers.py`)
1. **`CustomTokenObtainPairSerializer`:**
   * Extends SimpleJWT's `TokenObtainPairSerializer`.
   * Authenticates user via Django's backend mechanism.
   * Embeds custom claims into token payload: `user_id`, `role`, `is_verified`.
   * Rejects unverified accounts by raising `AuthenticationFailed` (HTTP 401), preventing access and refresh token issuance.
   * Protects sensitive data: passwords, phone numbers, and PII are strictly excluded from JWT claims.
2. **`UserRegistrationSerializer`:**
   * Extends DRF `ModelSerializer` for `accounts.User`.
   * Accepts approved fields: `username`, `email`, `password`, `phone_number`, `badge_or_employee_id`.
   * Enforces Django password validators via `validate_password()`.
   * Declares `password` as `write_only=True` (never exposed in responses).
   * Uses `set_password()` for secure PBKDF2 hashing.
   * Defends against privilege escalation by hardcoding `role = UserRole.AMBULANCE_DRIVER`, `is_verified = False`, `is_staff = False`, and `is_superuser = False`.
3. **`UserProfileSerializer`:**
   * Serializes profile data for authenticated users.
   * Enforces read-only immutability on `id`, `username`, `role`, `is_verified`, `is_staff`, `is_superuser`, and `date_joined`.
   * Permits updates only to ordinary fields (`email`, `phone_number`, `badge_or_employee_id`).

### 2. Security Protections Enforced
* **Privilege Escalation Defense:** Client payloads attempting to inject `role = "ADMIN"` or `is_verified = True` are completely ignored and overwritten.
* **Token Issuance Gate:** Unverified users receive `AuthenticationFailed` with message `"Account is pending administrative verification. Access denied until approved."` and zero tokens are generated.
* **Zero Credential Exposure:** Neither passwords nor password hashes are present in any serializer response payload.

### 3. Automated Test Execution & Results (`apps/accounts/tests.py`)
Command: `.\.venv\Scripts\python.exe manage.py test apps.accounts -v 2`
```text
test_01_valid_ambulance_driver_registration ... ok
test_02_registration_attempted_admin_escalation_ignored ... ok
test_03_registration_attempted_is_verified_true_ignored ... ok
test_04_password_hashing ... ok
test_05_password_not_returned_in_serialized_output ... ok
test_06_invalid_password_rejection ... ok
test_07_duplicate_username_rejection ... ok
test_08_jwt_claims_for_verified_user ... ok
test_09_unverified_user_cannot_obtain_tokens ... ok
test_10_profile_cannot_change_role_or_verification_status ... ok

----------------------------------------------------------------------
Ran 10 tests in 43.531s

OK
Destroying test database for alias 'default' ('test_sertos_db')...
System check identified no issues (0 silenced).
```

### 4. Step 3.4 Boundary Enforcement
* **No Views or URLs:** No view functions, ViewSets, APIViews, or URL patterns were created.
* **No Permissions:** Permission classes were not created.
* **Database & Settings:** `settings.py` was not modified. No migrations were generated or run.
* **Step 3.5 Status:** Step 3.5 has not been started.

---

## Section S: Phase 3 – Step 3.5: Role-Based Permission Classes Record

### 1. Permission Classes Implemented (`apps/accounts/permissions.py`)
1. **`IsVerifiedPersonnel`:**
   * Requires `request.user.is_authenticated and request.user.is_verified`.
   * Baseline gatekeeper ensuring that unverified accounts (even if authenticated) cannot access protected operational data.
2. **`IsSystemAdmin`:**
   * Requires `request.user.is_authenticated and request.user.is_verified`.
   * Requires `request.user.role == UserRole.ADMIN` (or `is_superuser == True`).
   * Governs user provisioning, institutional vetting, and global system auditing.
3. **`IsAmbulanceDriver`:**
   * Requires `request.user.is_authenticated and request.user.is_verified`.
   * Requires `request.user.role == UserRole.AMBULANCE_DRIVER`.
   * Governs GPS telemetry streaming, incident acceptance, and in-transit patient vital submissions.
4. **`IsHospitalStaff`:**
   * Requires `request.user.is_authenticated and request.user.is_verified`.
   * Requires `request.user.role == UserRole.HOSPITAL_STAFF`.
   * Governs hospital bed/ventilator counter management, incoming ambulance triage feed, and patient admission intake.
5. **`IsPoliceDispatcher`:**
   * Requires `request.user.is_authenticated and request.user.is_verified`.
   * Requires `request.user.role == UserRole.POLICE_DISPATCHER`.
   * Governs emergency green corridor approvals and manual traffic signal overrides.

---

### 2. Architectural Concepts: Authentication vs. Authorization

```
+-----------------------------------------------------------------------------------+
|                        AUTHENTICATION VS. AUTHORIZATION IN SERTOS                 |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  INCOMING REQUEST                                                                 |
|  Headers: "Authorization: Bearer <jwt_access_token>"                              |
|        │                                                                          |
|        ▼                                                                          |
|  [AUTHENTICATION LAYER] (SimpleJWT)                                               |
|  * Question: "Who are you?"                                                       |
|  * Action: Validates cryptographic signature and expiration of JWT.               |
|  * Outcome: Resolves database user model and populates request.user.              |
|        │                                                                          |
|        ▼ (If Valid Identity)                                                      |
|  [AUTHORIZATION LAYER] (DRF RBAC Permissions)                                     |
|  * Question: "What are you permitted to do on this specific endpoint?"           |
|  * Action: Evaluates request.user.role and request.user.is_verified.              |
|  * Outcome: If an Ambulance Driver requests Hospital Bed allocations:            |
|             Permission denied -> Returns HTTP 403 Forbidden.                     |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

---

### 3. Why Database-Backed Verification is Vital
* **The Token Staleness Vulnerability:** JWTs are stateless and immutable once signed. If user claims (`"is_verified": true`, `"role": "AMBULANCE_DRIVER"`) are checked solely from the decoded token payload, an administrator who discovers a compromised driver account and sets `is_verified = False` in the database would be powerless—the attacker's token would continue working until its 15-minute expiration window elapsed.
* **The SERTOS Defense:** When SimpleJWT authenticates a request, it uses the token's `user_id` to query PostgreSQL and attach the live `accounts.User` record to `request.user`. Our permission classes check `request.user.is_verified` and `request.user.role` directly against this live database instance. Revoking a user's verification in PostgreSQL revokes access **instantly** on their very next HTTP call.

---

### 4. Automated Test Suite Execution & Output (`apps/accounts/tests.py`)
Executed test runner: `.\.venv\Scripts\python.exe manage.py test apps.accounts -v 2`
```text
Found 17 test(s).
...
test_11_anonymous_user_denied_by_all_permissions ... ok
test_12_correct_role_and_verified_user_allowed ... ok
test_13_incorrect_role_denied ... ok
test_14_unverified_user_denied ... ok
test_15_database_role_checked_rather_than_payload ... ok
test_16_verification_revocation_in_database_respected ... ok
test_17_all_four_roles_correctly_distinguished ... ok
test_01_valid_ambulance_driver_registration ... ok
test_02_registration_attempted_admin_escalation_ignored ... ok
test_03_registration_attempted_is_verified_true_ignored ... ok
test_04_password_hashing ... ok
test_05_password_not_returned_in_serialized_output ... ok
test_06_invalid_password_rejection ... ok
test_07_duplicate_username_rejection ... ok
test_08_jwt_claims_for_verified_user ... ok
test_09_unverified_user_cannot_obtain_tokens ... ok
test_10_profile_cannot_change_role_or_verification_status ... ok

----------------------------------------------------------------------
Ran 17 tests in 23.134s

OK
Destroying test database for alias 'default' ('test_sertos_db')...
System check identified no issues (0 silenced).
```

---

### 5. Mentor Viva Questions & Answers (Q31 to Q34)

#### Q31: What is the difference between HTTP 401 Unauthorized and HTTP 403 Forbidden?
**Answer:** `401 Unauthorized` means authentication has failed or was not provided ("You are not logged in or your token is invalid"). `403 Forbidden` means authentication succeeded, but the server refuses authorization ("I know who you are, but you do not have permission to access this resource").

#### Q32: Why do our role permission classes also check `is_verified`?
**Answer:** Having an assigned role alone is not enough in an emergency coordination system. A registered ambulance driver whose vehicle license has expired or an employee undergoing vetting has the role `AMBULANCE_DRIVER`, but their `is_verified` status is `False`. Requiring `is_verified` ensures unverified personnel cannot trigger dispatches or access hospital intake feeds.

#### Q33: How does a permission class in DRF communicate failure to the client?
**Answer:** If `has_permission()` returns `False`, DRF halts request execution, catches the denial, and returns an HTTP `403 Forbidden` JSON response containing the string defined in the permission class's `message` attribute (e.g. `"Access denied: Hospital Emergency Staff credentials required."`).

#### Q34: What happens if an attacker tampers with the JWT payload to change `"role": "AMBULANCE_DRIVER"` to `"role": "ADMIN"`?
**Answer:** Two independent security controls stop the attack:
1. SimpleJWT checks the cryptographic signature using Django's secret key. If any byte in the payload is altered, the signature verification fails, returning HTTP `401`.
2. Even if an attacker somehow bypasses token signature checks, our RBAC permissions check `request.user.role` from the PostgreSQL database, not the JWT payload. The database record still says `AMBULANCE_DRIVER`, so admin endpoints remain completely locked.

---

### 6. Step 3.5 Boundary Enforcement
* **No Views or URLs:** No view functions, ViewSets, APIViews, or URL patterns were created.
* **No Serializer Modifications:** Serializers were verified and preserved intact.
* **No Settings or Migrations:** `settings.py` was not modified. No migrations were generated or run.
* **Step 3.6 Status:** Step 3.6 has not been started.

---

## Section T: Phase 3 – Step 3.6: Authentication API Views Record

### 1. View Classes Implemented (`apps/accounts/views.py`)
1. **`LoginView` (`POST /api/auth/login/`):**
   * Permissions: `[AllowAny]`.
   * Serializer: `CustomTokenObtainPairSerializer`.
   * Authenticates username and password; enforces verification gate.
   * Returns HTTP 200 with `access` token, `refresh` token, and minimal user metadata inside the standard response envelope.
   * Rejects unverified or invalid accounts with HTTP 401.
2. **`TokenRefreshView` (`POST /api/auth/token/refresh/`):**
   * Permissions: `[AllowAny]`.
   * Replaces expired access tokens using a valid refresh token.
   * Enforces refresh token rotation and blacklisting.
   * Returns HTTP 200 with new tokens wrapped in the project envelope.
3. **`LogoutView` (`POST /api/auth/logout/`):**
   * Permissions: `[IsAuthenticated]`.
   * Accepts `{"refresh": "<token>"}`.
   * Enforces token ownership: verifies `token.payload['user_id'] == request.user.pk`. Submitting another user's token returns HTTP 403 Forbidden.
   * Blacklists the token via SimpleJWT's blacklist table. Returns HTTP 200.
4. **`RegisterView` (`POST /api/auth/register/`):**
   * Permissions: `[AllowAny]`.
   * Serializer: `UserRegistrationSerializer`.
   * Creates unverified `AMBULANCE_DRIVER` accounts only. Neutralizes role injection.
   * Returns HTTP 201 Created with standard envelope.
5. **`ProfileView` (`GET/PATCH /api/auth/profile/`):**
   * Permissions: `[IsAuthenticated]`.
   * `GET`: Returns authenticated user's profile.
   * `PATCH`: Allows updating ordinary profile fields (`email`, `phone_number`, `badge_or_employee_id`). Immutability of role and verification status is strictly maintained.

### 2. Standard Response Envelope Implementation
Every view uses the `standard_response()` utility:
```json
{
  "success": true,
  "data": { ... },
  "message": "Operation completed successfully.",
  "timestamp": "2026-11-13T05:15:33Z"
}
```
Error responses consistently include `errors` and `success: false`.

### 3. Automated Test Execution & Results (`apps/accounts/tests.py`)
Command: `.\.venv\Scripts\python.exe manage.py test apps.accounts -v 2`
```text
Ran 31 tests in 38.556s
OK
System check identified no issues (0 silenced).
```
* **Coverage:** 10 Serializer tests (TEST-01 to TEST-10), 7 Permission tests (TEST-11 to TEST-17), and 14 API View tests (TEST-18 to TEST-31).

### 4. Mentor Viva Questions & Answers (Q35 to Q38)

#### Q35: Why does LogoutView require token ownership verification?
**Answer:** Without ownership verification (`token.payload['user_id'] == request.user.pk`), an authenticated attacker who intercepts another user's refresh token could submit it to `/api/auth/logout/` to maliciously invalidate the victim's session (Denial of Service). Checking ownership ensures users can only blacklist their own tokens.

#### Q36: Why do public endpoints explicitly declare `permission_classes = [AllowAny]`?
**Answer:** In `settings.py`, the project-wide default permission is set to `IsAuthenticated` for security. Unless a view explicitly overrides this setting with `permission_classes = [AllowAny]`, Django REST Framework will reject unauthenticated users with HTTP 401 before they can reach the login or registration logic.

#### Q37: How does TokenRefreshView work with rotation and blacklisting enabled?
**Answer:** When a client sends a valid refresh token, SimpleJWT generates a brand-new access token and a brand-new refresh token. SimpleJWT immediately blacklists the old refresh token in PostgreSQL (`token_blacklist_blacklistedtoken`). If the old token is re-sent, the server rejects it with HTTP 401.

#### Q38: Why is the standard response envelope important for frontend integrations?
**Answer:** Heterogeneous clients (Android, React dashboards, ESP32 nodes) need a predictable response format. Wrapping every response with `success`, `data`, `message`, and `timestamp` allows frontend clients to write universal network interceptors that handle errors and payloads uniformly.

---

## Section P: Phase 3 — Step 3.7: URL Routing, Wire-up & Security Hardening

### 1. Architectural Overview & Objective
In Step 3.7, we wired all five authentication and profile views into Django's URL routing table:
* Created `apps/accounts/urls.py` containing modular, named routes.
* Mounted `apps/accounts/urls.py` into the root URL configuration `config/urls.py` under the prefix `api/auth/`.
* Audited the token refresh lifecycle and discovered a critical security vulnerability in SimpleJWT's default behavior where unverified/revoked accounts could indefinitely renew access tokens.
* Developed and deployed the smallest safe correction: `CustomTokenRefreshSerializer` in `apps/accounts/serializers.py` coupled with `TokenRefreshView`.
* Implemented 11 integration and routing unit tests (bringing the accounts test suite to 42 passing tests).

---

### 2. Deep Dive: URL Routing & Django HTTP Request Lifecycle

Understanding how an incoming HTTP request reaches our code is vital for debugging and architectural comprehension.

```
+---------------------------------------------------------------------------------------+
|                              Django HTTP Request Lifecycle                             |
+---------------------------------------------------------------------------------------+
|  1. Incoming HTTP Request (e.g. POST /api/auth/login/)                                 |
|     |                                                                                 |
|     v                                                                                 |
|  2. WSGI / ASGI Handler (config/wsgi.py)                                              |
|     |                                                                                 |
|     v                                                                                 |
|  3. Middleware Pipeline (SecurityMiddleware, CorsMiddleware, CommonMiddleware, etc.) |
|     |                                                                                 |
|     v                                                                                 |
|  4. Root URL Resolver (config/urls.py -> ROOT_URLCONF)                                |
|     Matches prefix 'api/auth/' via include('apps.accounts.urls')                       |
|     |                                                                                 |
|     v                                                                                 |
|  5. App URL Resolver (apps/accounts/urls.py)                                          |
|     Matches subpath 'login/' via path('login/', LoginView.as_view(), name='login')     |
|     |                                                                                 |
|     v                                                                                 |
|  6. as_view() Callable Factory                                                        |
|     Instantiates LoginView(), sets request, args, kwargs, calls dispatch()           |
|     |                                                                                 |
|     v                                                                                 |
|  7. DRF initial() Pipeline                                                            |
|     * Content Negotiation (JSONRenderer, BrowsableAPIRenderer)                        |
|     * Authentication (JWTAuthentication, SessionAuthentication)                       |
|     * Permission Check (Evaluates permission_classes = [AllowAny])                    |
|     |                                                                                 |
|     v                                                                                 |
|  8. View Method Handler: LoginView.post(request)                                      |
|     * Passes request.data to CustomTokenObtainPairSerializer                          |
|     * Validates credentials and verifies user.is_verified in PostgreSQL               |
|     |                                                                                 |
|     v                                                                                 |
|  9. standard_response() Envelope Formatting                                           |
|     Wraps payload into {"success": true, "data": ..., "message": ..., "timestamp": ..}|
|     |                                                                                 |
|     v                                                                                 |
| 10. HTTP Response (Status 200 OK sent back through Middleware to Client)               |
+---------------------------------------------------------------------------------------+
```

#### Key Technical Concepts Explained:
1. **`ROOT_URLCONF` & `config/urls.py`:**
   Django uses the setting `ROOT_URLCONF = "config.urls"` as the entry point for all URL routing. When an HTTP request arrives, Django attempts to match the requested URL against the `urlpatterns` list defined in this file.
2. **`path()`:**
   The `path(route, view, kwargs=None, name=None)` function creates a `URLPattern` object. It takes a route string pattern and associates it with a callable view. Giving each route a unique `name` parameter allows reverse URL resolution using `reverse('name')` rather than hardcoding URL strings in templates and code.
3. **`include()`:**
   `include('apps.accounts.urls')` allows modular and decoupled routing. The root URLconf chops off the matched portion of the URL (`api/auth/`) and passes the remaining path string to the included app-level `urls.py`. This prevents monolithic URL files and keeps app domain logic self-contained.
4. **`as_view()`:**
   Django's URL dispatcher fundamentally expects a callable function that takes `request` and returns `response`. Class-based views (`CBVs`) inherit from `APIView`. The class method `as_view()` acts as a factory: it returns a closure function that instantiates the view class per request, copies request metadata, and invokes `self.dispatch(request, *args, **kwargs)` to delegate execution to the appropriate HTTP verb method (`get`, `post`, `patch`, `put`, `delete`).

---

### 3. Security Inspection: Refresh Token Verification Revocation

#### The Security Flaw in Default SimpleJWT
During our Task 1 pre-implementation security audit, we analyzed the token refresh lifecycle under this critical scenario:
1. An ambulance driver or hospital staff member is verified and logs in.
2. The user receives a valid JWT access token (lifetime: 15 minutes) and a refresh token (lifetime: 7 days).
3. Due to a safety infraction or credential revocation, an administrator sets `user.is_verified = False` (or `user.is_active = False`) in PostgreSQL.
4. When the user's access token expires, their client sends `POST /api/auth/token/refresh/` with their refresh token.

**The Flaw:** SimpleJWT's default `TokenRefreshSerializer` validates only the cryptographic signature, expiration time, and blacklist database table (`OutstandingToken`/`BlacklistedToken`). **It never inspects the user in PostgreSQL.** As a result:
* The revoked user would be granted a brand-new access token.
* Because token rotation is enabled, they would also receive a brand-new refresh token.
* They could indefinitely renew sessions, bypassing administrative revoking.

#### The Smallest Safe Correction Implemented
We implemented `CustomTokenRefreshSerializer` in `apps/accounts/serializers.py` subclassing SimpleJWT's `TokenRefreshSerializer`:
1. It parses the incoming refresh token to extract `user_id`.
2. It queries PostgreSQL: `user = User.objects.get(pk=user_id)`.
3. It validates:
   * `if not user.is_active: raise AuthenticationFailed("User account is inactive.")`
   * `if not user.is_verified: raise AuthenticationFailed("Account verification has been revoked or is pending administrative approval.")`
4. Only if the user is active and verified in PostgreSQL does it call `super().validate(attrs)` to rotate and issue tokens.
5. In `TokenRefreshView`, `serializer_class = CustomTokenRefreshSerializer` was set, and `AuthenticationFailed` exceptions are caught to return a clean `HTTP 401 Unauthorized` with the `standard_response` envelope.

---

### 4. Exact Route & View Mapping Table

| Method | Endpoint | View Class | Route Name | Permissions | Description |
|---|---|---|---|---|---|
| `POST` | `/api/auth/login/` | `LoginView` | `login` | `AllowAny` | Authenticates username/password; returns tokens & metadata; rejects unverified. |
| `POST` | `/api/auth/token/refresh/` | `TokenRefreshView` | `token_refresh` | `AllowAny` | Renews access token; verifies live DB active & verification status. |
| `POST` | `/api/auth/logout/` | `LogoutView` | `logout` | `IsAuthenticated` | Verifies token ownership and blacklists refresh token. |
| `POST` | `/api/auth/register/` | `RegisterView` | `register` | `AllowAny` | Self-registration for unverified ambulance drivers. |
| `GET` | `/api/auth/profile/` | `ProfileView` | `profile` | `IsAuthenticated` | Retrieves authenticated user profile. |
| `PATCH` | `/api/auth/profile/` | `ProfileView` | `profile` | `IsAuthenticated` | Updates non-critical user profile fields (immutable role). |

---

### 5. Practical Testing Guide: Testing the Endpoints via curl

Clients (Android app, React dashboards, curl, Postman) interact with the endpoints as follows:

#### 1. Register a New Ambulance Driver
```bash
curl -X POST http://127.0.0.1:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "driver_rahul",
    "email": "rahul@sertos.local",
    "password": "StrongPassword123!@#",
    "phone_number": "+91-9876543210",
    "badge_or_employee_id": "AMB-DL-101"
  }'
```
*Expected Response:* HTTP 201 Created with `is_verified: false` and `role: "AMBULANCE_DRIVER"`.

#### 2. Log In
*(Note: Account must have `is_verified = True` set in DB to log in)*
```bash
curl -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "driver_rahul",
    "password": "StrongPassword123!@#"
  }'
```
*Expected Response:* HTTP 200 OK with `access` token, `refresh` token, and `user` object.

#### 3. Retrieve User Profile
```bash
curl -X GET http://127.0.0.1:8000/api/auth/profile/ \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```
*Expected Response:* HTTP 200 OK with user profile details.

#### 4. Refresh Access Token
```bash
curl -X POST http://127.0.0.1:8000/api/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{
    "refresh": "<REFRESH_TOKEN>"
  }'
```
*Expected Response:* HTTP 200 OK with new `access` token (and new rotated `refresh` token).

#### 5. Log Out & Blacklist Token
```bash
curl -X POST http://127.0.0.1:8000/api/auth/logout/ \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh": "<REFRESH_TOKEN>"
  }'
```
*Expected Response:* HTTP 200 OK with `"message": "Logout successful. Token blacklisted."`.

---

### 6. Automated Test Suite Results
Command executed:
```powershell
.\.venv\Scripts\python.exe manage.py test apps.accounts --verbosity 2
```

**Results:**
```text
Ran 42 tests in 49.360s
OK
Destroying test database for alias 'default' ('test_sertos_db')...
System check identified no issues (0 silenced).
```
* **Test Breakdown:**
  * 10 Serializer Unit Tests (`test_01` to `test_10`)
  * 7 Permission Class Tests (`test_11` to `test_17`)
  * 14 View Unit Tests (`test_18` to `test_31`)
  * 11 URL Routing & Integration Tests (`test_32` to `test_42`)

---

### 7. Mentor Viva Questions & Answers (Q39 to Q43)

#### Q39: What is the purpose of `include()` in URL configuration?
**Answer:** `include()` decouples route definitions across applications. Rather than maintaining a monolithic list of every route in the root `config/urls.py`, each app defines its own `urls.py`. The root configuration mounts the app under a namespace/prefix (e.g. `api/auth/`), promoting modularity, reusability, and team scalability.

#### Q40: What happens under the hood when `as_view()` is called in `path()`?
**Answer:** `as_view()` is a class method that returns a callable view function. When invoked by Django's URL resolver during a request, it creates a fresh instance of the class-based view, binds the `request`, `args`, and `kwargs` onto `self`, and calls `self.dispatch()`. `dispatch()` runs DRF's authentication, permission, and throttling checks before delegating to the appropriate HTTP verb method handler (such as `.get()` or `.post()`).

#### Q41: Why did standard SimpleJWT token refresh allow revoked users to refresh, and how did we fix it?
**Answer:** Standard SimpleJWT is designed for statelessness: `TokenRefreshSerializer` validates only the cryptographically signed claims inside the refresh token string and checks the blacklist table. It does not perform a database query against the `User` table. If an administrator revokes a user's verification or deactivates them, SimpleJWT continues to issue access tokens. We resolved this by creating `CustomTokenRefreshSerializer`, which extracts `user_id` from the token and verifies that `user.is_active` and `user.is_verified` are `True` in PostgreSQL before permitting token issuance.

#### Q42: How does `resolve()` differ from `reverse()` in Django testing?
**Answer:** `resolve(path)` takes a URL path string (like `"/api/auth/login/"`) and maps it to the matching `ResolverMatch` object containing the view callable and URL name. `reverse(viewname)` does the opposite: it takes a view name or route identifier (like `"login"`) and generates the corresponding URL path string. Testing both ensures bidirectional URL integrity.

#### Q43: How does SERTOS prevent unverified users from abusing the refresh token endpoint?
**Answer:** In `CustomTokenRefreshSerializer`, before any token is rotated or generated, a query is executed against the `User` model. If `user.is_verified` is `False`, the serializer raises `AuthenticationFailed`. `TokenRefreshView` catches this exception and returns an `HTTP 401 Unauthorized` with our standard JSON error envelope, blocking token issuance.

---

## Section Q: Phase 3 — Step 3.8: End-to-End Authentication & RBAC Validation

### 1. Architectural Overview & Objective
In **Step 3.8**, we executed the final validation phase of Phase 3. Having verified serializers (Step 3.4), permissions (Step 3.5), views (Step 3.6), and URL routing (Step 3.7), Step 3.8 performed comprehensive end-to-end integration and security boundary testing.

We implemented `AccountsEndToEndValidationTestCase` in `apps/accounts/tests.py` containing 10 automated test methods (TEST-43 through TEST-52), expanding the accounts test suite from 42 to **52 tests**. All 52 tests passed cleanly with 100% test database isolation (`test_sertos_db`).

---

### 2. Comprehensive Validation Scenarios (TEST-43 to TEST-52)

| Test ID | Scenario Description | Tested Endpoints & Classes | Key Verifications & Outcomes |
|---|---|---|---|
| **TEST-43** | Multi-Role E2E: `ADMIN` | `/api/auth/login/`, `/api/auth/profile/` | Successful login (HTTP 200), `role="ADMIN"` embedded in JWT claims, profile retrieved with Bearer token, password hash strictly omitted. |
| **TEST-44** | Multi-Role E2E: `HOSPITAL_STAFF` | `/api/auth/login/`, `/api/auth/profile/` | Successful login (HTTP 200), `role="HOSPITAL_STAFF"` claims, profile inspection via Bearer token, zero credential exposure. |
| **TEST-45** | Multi-Role E2E: `POLICE_DISPATCHER` | `/api/auth/login/`, `/api/auth/profile/` | Successful login (HTTP 200), `role="POLICE_DISPATCHER"` claims, profile inspection via Bearer token, zero credential exposure. |
| **TEST-46** | Cross-Role Gating: Driver accessing Hospital View | `_TestHospitalOnlyView`, `IsHospitalStaff` | Direct permission check returns `False` (`message="Access denied: Hospital Emergency Staff credentials required."`). View execution returns HTTP 403 Forbidden with exact error detail. Verified hospital staff granted HTTP 200. |
| **TEST-47** | Cross-Role Gating: Hospital accessing Police View | `_TestPoliceOnlyView`, `IsPoliceDispatcher` | Direct permission check returns `False` (`message="Access denied: Police Traffic Dispatcher credentials required."`). View execution returns HTTP 403 Forbidden. Verified police dispatcher granted HTTP 200. |
| **TEST-48** | Cross-Role Gating: Police accessing Admin View | `_TestAdminOnlyView`, `IsSystemAdmin` | Direct permission check returns `False` (`message="Access denied: System Administrator privileges required."`). View execution returns HTTP 403 Forbidden. Verified admin granted HTTP 200. |
| **TEST-49** | Token Rotation Replay Prevention | `/api/auth/token/refresh/` | First refresh rotates token and returns `refresh_2 != refresh_1`. Replay attempt with `refresh_1` fails with HTTP 401 Unauthorized (`"Token is blacklisted"`). `refresh_2` remains fully functional. |
| **TEST-50** | Independent Multi-Device Sessions | `/api/auth/login/`, `/api/auth/logout/`, `/api/auth/token/refresh/` | User logs in on Device 1 and Device 2. Device 1 logs out (blacklisting `refresh_dev1`). Device 1 retry is rejected (HTTP 401). Device 2 `refresh_dev2` remains valid and successfully refreshes (HTTP 200). |
| **TEST-51** | Malformed & Tampered Bearer Tokens | `/api/auth/profile/` | Tested bogus strings, non-Bearer headers (`Basic ...`), empty `Bearer `, and cryptographically tampered signatures. All return HTTP 401 Unauthorized without leaking server internals or passwords. |
| **TEST-52** | Empty & Malformed Request Boundaries | All 4 auth endpoints | Tested `{}` payloads on login (HTTP 401), register (HTTP 400), refresh (HTTP 400), logout (HTTP 400), and invalid types (HTTP 401). All return structured validation errors under standard envelope; zero 500 errors. |

---

### 3. Automated Test Execution Evidence

Command executed:
```powershell
.\.venv\Scripts\python.exe manage.py test apps.accounts --verbosity 2
```

**Output Excerpt:**
```text
Creating test database for alias 'default' ('test_sertos_db')...
Found 52 test(s).
...
test_43_admin_login_and_profile_retrieval ... ok
test_44_hospital_staff_login_and_profile_retrieval ... ok
test_45_police_dispatcher_login_and_profile_retrieval ... ok
test_46_ambulance_driver_denied_hospital_permission ... ok
test_47_hospital_staff_denied_police_permission ... ok
test_48_police_dispatcher_denied_admin_permission ... ok
test_49_refresh_token_rotation_replay_prevention ... ok
test_50_independent_multi_device_refresh_sessions ... ok
test_51_malformed_and_tampered_bearer_tokens ... ok
test_52_empty_and_malformed_request_payloads ... ok
...
----------------------------------------------------------------------
Ran 52 tests in 65.950s

OK
Destroying test database for alias 'default' ('test_sertos_db')...
System check identified no issues (0 silenced).
```

---

### 4. Recorded Security Findings (Unresolved by Design)

In strict accordance with project boundaries, the following two security findings were audited, recorded, and intentionally left untouched for separate review:

#### Finding A: Model Default Role (`apps/accounts/models.py`, Line 35)
* **Description:** The `User` model defines `role = models.CharField(..., default=UserRole.ADMIN, ...)`.
* **Risk Assessment:** While public self-registration (`UserRegistrationSerializer`) strictly hardcodes `AMBULANCE_DRIVER` and cannot be bypassed from the API, internal code calling `User.objects.create_user()` without specifying a `role` will default to `ADMIN`.
* **Resolution Plan:** Schedule a separate security-hardening task to update the model default to `UserRole.AMBULANCE_DRIVER` or remove the default entirely, accompanied by a database migration upon separate user approval.

#### Finding B: Framework-Level Exception Envelope Uniformity
* **Description:** When an unauthenticated client accesses a protected endpoint (e.g. `GET /api/auth/profile/`), Django REST Framework rejects the request during authentication middleware *before* it reaches the view method. DRF's default exception handler outputs `{"detail": "Authentication credentials were not provided."}` without our outer envelope (`success`, `data`, `message`, `timestamp`).
* **Risk Assessment:** This creates a minor contract inconsistency for frontend network interceptors expecting `response.data.success` on all responses.
* **Resolution Plan:** In a future hardening step, implement a custom DRF exception handler (`apps.accounts.exceptions.custom_exception_handler`) and register it in `config/settings.py` under `REST_FRAMEWORK["EXCEPTION_HANDLER"]`.

---

### 5. Mentor Viva Questions & Answers (Q44 to Q48)

#### Q44: How does multi-device session management work in SimpleJWT with rotation enabled?
**Answer:** Each time a user logs in (regardless of device), SimpleJWT generates a fresh pair of tokens with a unique `jti` (JWT ID). Because rotation and blacklisting track individual `jti` identifiers rather than user IDs, logging out on Device 1 blacklists only `refresh_dev1`'s `jti`. Device 2's refresh token carries a distinct `jti` and remains fully valid in PostgreSQL until it is rotated or explicitly logged out.

#### Q45: How does SERTOS prevent token replay attacks on refresh tokens?
**Answer:** SERTOS enables `ROTATE_REFRESH_TOKENS = True` and `BLACKLIST_AFTER_ROTATION = True`. When a client submits a valid refresh token, SimpleJWT's blacklist table records that token's `jti`. If an attacker intercepts and replays that same refresh token, the server checks `BlacklistedToken` in PostgreSQL, detects the replay, and immediately rejects the request with HTTP 401 Unauthorized.

#### Q46: Why did we test cross-role permissions using test-only views rather than production endpoints?
**Answer:** In Step 3.8, production emergency and dispatch endpoints (e.g., Hospital triage or Police corridor APIs) have not yet been built. Creating dummy production endpoints would pollute our routing table. Using isolated test-only class-based views within `apps/accounts/tests.py` allowed us to test real DRF HTTP 403 request-response dispatching and permission message formatting without violating architectural boundaries.

#### Q47: What happens when an attacker tampers with a JWT signature?
**Answer:** SimpleJWT validates the HMAC-SHA256 signature of every Bearer token against `settings.SECRET_KEY`. If even a single byte of the header, payload, or signature is altered, cryptographic verification fails. DRF's authenticator immediately raises `InvalidToken`, terminating request processing and returning HTTP 401 Unauthorized without executing view logic or database queries.

#### Q48: Why is Phase 3 now considered complete?
**Answer:** Phase 3 successfully delivered the entire identity, authentication, and role-based access control subsystem: custom User model with 4 distinct roles, SimpleJWT integration with rotation and blacklisting, custom serializers with anti-escalation safeguards, live database permission evaluation, standardized API views, secure URL routing, and a comprehensive 52-test automated verification suite with 0 failures and 0 security regressions.

---

## Section R: Phase 3 Security Hardening — Task 3.9: Default Role Hardening & Universal Exception Envelope

### 1. Architectural Overview & Objective
In **Task 3.9**, we addressed and resolved both security findings identified during Step 3.8:
1. **Finding A (Default Role Hardening):** Changed `User.role` default from `ADMIN` to `AMBULANCE_DRIVER` in [apps/accounts/models.py](file:///e:/sertos/apps/accounts/models.py). Generated and applied migration `0002_alter_user_role.py`.
2. **Finding B (Universal Exception Envelope):** Implemented `sertos_exception_handler` in [apps/accounts/exceptions.py](file:///e:/sertos/apps/accounts/exceptions.py) and registered it in [config/settings.py](file:///e:/sertos/config/settings.py). This guarantees that framework-level 400, 401, 403, 404, and 405 errors strictly conform to the SERTOS JSON response envelope while retaining backwards compatibility with `detail`.

We expanded the automated test suite with 5 new tests (`TEST-53` to `TEST-57`), bringing total accounts test coverage to **57 passing unit and integration tests**.

---

### 2. Deep Dive: Model Default Role Hardening

#### Security Rationale
In security-critical emergency architectures, the **Principle of Least Privilege** requires that default assignments grant the minimal necessary privileges. Having `default=UserRole.ADMIN` on the `User` model meant that any internal programmatic invocation of `User.objects.create_user()` that omitted `role` would produce a full system administrator.

#### Implementation & Migration Behavior
* **Model Change:** Updated `default=UserRole.AMBULANCE_DRIVER` in `apps/accounts/models.py`.
* **Migration Generated:** `apps/accounts/migrations/0002_alter_user_role.py`.
* **Database Schema Effect (`sqlmigrate`):**
  In Django's PostgreSQL backend, Python-level model defaults are evaluated by Django's ORM before writing to the database rather than as a hardcoded PostgreSQL `DEFAULT` constraint. As verified by `sqlmigrate accounts 0002`, the migration is `-- (no-op)` in PostgreSQL DDL while updating Django's migration state. Existing user records, roles, and administrative accounts remain 100% unaltered.

---

### 3. Deep Dive: Universal DRF Exception Handler

#### Architecture of `sertos_exception_handler`
Implemented in `apps/accounts/exceptions.py` and registered in `config/settings.py`:
```python
def sertos_exception_handler(exc, context):
    # Call DRF's standard exception handler first
    response = exception_handler(exc, context)

    # If response is None, an unhandled 500 occurred; let Django handle/log it
    if response is None:
        return None

    # Construct uniform envelope
    response.data = {
        "success": False,
        "data": {},
        "message": message,
        "errors": errors,
        "detail": message,  # Preserves DRF client compatibility
        "timestamp": timezone.now().isoformat(),
    }
    return response
```

#### Key Guarantees:
1. **Preserves HTTP Status Codes:** 400, 401, 403, 404, 405 are untouched.
2. **Backwards Compatibility:** Retains `"detail"` inside `response.data` so legacy DRF clients and existing tests expecting `response.data["detail"]` continue to pass.
3. **No 500 Masking:** Returns `None` for unhandled exceptions so Django's logging and debug tracebacks are never suppressed or converted into 200s.
4. **Information Disclosure Protection:** Never leaks database queries, passwords, or raw stack traces in error envelopes.

---

### 4. Automated Test Suite Results (57/57 Tests Passing)
Command executed:
```powershell
.\.venv\Scripts\python.exe manage.py test apps.accounts --verbosity 2
```

**New Tests Added in Task 3.9:**
* `TEST-53`: Verifies that `User.objects.create_user()` without `role` creates an `AMBULANCE_DRIVER`, while explicit `ADMIN` creation retains the admin role.
* `TEST-54`: Verifies that framework-level 401 Unauthorized errors (anonymous access to protected endpoints) are formatted in the SERTOS envelope.
* `TEST-55`: Verifies that framework-level 403 Forbidden errors (permission class denial) are formatted in the SERTOS envelope.
* `TEST-56`: Verifies that framework-level 405 Method Not Allowed errors (e.g. GET on login) return 405 inside the SERTOS envelope.
* `TEST-57`: Verifies that framework-level 404 Not Found errors return 404 inside the SERTOS envelope.

**Execution Result:**
```text
Ran 57 tests in 72.513s
OK
Destroying test database for alias 'default' ('test_sertos_db')...
System check identified no issues (0 silenced).
```

---

### 5. Mentor Viva Questions & Answers (Q49 to Q52)

#### Q49: Why is `AMBULANCE_DRIVER` safer than removing the default role entirely?
**Answer:** Removing the default role on a non-nullable column breaks Django's built-in `createsuperuser` command because `createsuperuser` only prompts for fields in `USERNAME_FIELD` and `REQUIRED_FIELDS`. Without a default on `role`, `createsuperuser` attempts to insert `NULL` into `accounts_user.role`, causing a database `NotNullViolation`. Setting the default to `AMBULANCE_DRIVER` enforces least privilege for programmatic creation while allowing `createsuperuser` to operate cleanly (superusers automatically pass `IsSystemAdmin` via `is_superuser`).

#### Q50: Why did `sqlmigrate accounts 0002` show `-- (no-op)` for altering the default?
**Answer:** Django handles Python-level `default=...` arguments in the application layer during model instantiation. Django does not generate a PostgreSQL `ALTER COLUMN SET DEFAULT` statement unless `db_default` is explicitly declared. The migration modifies Django's serialized migration state without altering database table constraints, ensuring zero table locking or data risk.

#### Q51: How does `sertos_exception_handler` maintain backwards compatibility for existing clients?
**Answer:** Many DRF frontend libraries and unit tests look for `response.data["detail"]`. Our custom exception handler populates both the SERTOS standard envelope (`success`, `data`, `message`, `errors`, `timestamp`) and includes `"detail": message` directly on `response.data`, ensuring dual compatibility with both SERTOS universal interceptors and standard DRF consumers.

#### Q52: Why must a custom DRF exception handler return `None` when `response is None`?
**Answer:** In DRF, `exception_handler` returns `None` for any unhandled exception (such as unexpected `RuntimeError`, `KeyError`, or database operational errors). If our handler converted `None` into an HTTP 200 or generic 400 response, it would swallow 500 errors, hide critical stack traces from server logs, and mask severe backend bugs. Returning `None` ensures Django's standard 500 error machinery executes properly.

---

## Section S: Task 4.1C Execution Record: Hospital and Ambulance Database Models Implementation

### 1. Architectural Objective
Implement the foundational medical infrastructure and transport fleet database models in `apps/emergencies/models.py`:
- `Hospital`: Medical facility capable of receiving emergency triage cases with verified geographic coordinates.
- `Ambulance`: Emergency response vehicle linked to verified ambulance drivers with operational availability flags.

### 2. Model Design & Implementation

#### 2.1 `Hospital` Model (`emergencies_hospital`)
* **Fields:**
  - `id`: `UUIDField(primary_key=True, default=uuid.uuid4, editable=False)` — Prevents sequential enumeration.
  - `name`: `CharField(max_length=150)` — Full facility name.
  - `hospital_code`: `CharField(max_length=30, unique=True)` — Unique institutional identifier (e.g. `HOSP-BLR-001`).
  - `address`: `TextField()` — Street address and landmark details.
  - `latitude`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)` — GPS latitude.
  - `longitude`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)` — GPS longitude.
  - `contact_number`: `CharField(max_length=15, null=True, blank=True)`.
  - `is_active`: `BooleanField(default=True)` — Indexed via `idx_hosp_is_active`.
  - `created_at`, `updated_at`: `DateTimeField`.
* **Validation Rules:**
  - Coordinate bounds: Latitude must be between $-90.0$ and $90.0$; Longitude between $-180.0$ and $180.0$.
  - Coordinate pairing: Either both coordinates are supplied, or both must be omitted. Supplying only one raises `ValidationError`.

#### 2.2 `Ambulance` Model (`emergencies_ambulance`)
* **Fields:**
  - `id`: `UUIDField(primary_key=True, default=uuid.uuid4, editable=False)`.
  - `vehicle_number`: `CharField(max_length=20, unique=True)` — License plate/fleet number (e.g. `KA-01-EQ-1234`).
  - `vehicle_type`: `CharField(max_length=50)` — Classification (e.g. Advanced Life Support, Basic Life Support).
  - `assigned_driver`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL, related_name="assigned_ambulances")`.
  - `is_available`: `BooleanField(default=True)` — Availability flag.
  - `is_active`: `BooleanField(default=True)` — Fleet active status flag.
  - `created_at`, `updated_at`: `DateTimeField`.
* **Validation & Security Rules:**
  - Role verification: The assigned user must have `role == UserRole.AMBULANCE_DRIVER`.
  - Active check: Inactive users cannot be assigned as ambulance drivers.
  - Unassigned support: Ambulances may exist without an assigned driver (`assigned_driver=None`).
  - Dispatch eligibility: Helper property `is_eligible_for_dispatch` requires `is_active=True`, `is_available=True`, and an assigned, active, verified driver.

#### 2.3 Driver Assignment Safety: Model Validation vs. Database Constraint
To ensure a driver cannot be assigned to multiple active ambulances simultaneously:
1. **Model Validation (`clean()`):** Queries existing ambulances where `assigned_driver == driver` and `is_active == True`. If another active ambulance exists, raises `ValidationError({"assigned_driver": "..."})` before reaching the database.
2. **Database Partial Unique Index (`UniqueConstraint`):**
   ```python
   models.UniqueConstraint(
       fields=["assigned_driver"],
       condition=models.Q(assigned_driver__isnull=False, is_active=True),
       name="unique_active_ambulance_driver",
   )
   ```
   Generates PostgreSQL DDL:
   ```sql
   CREATE UNIQUE INDEX "unique_active_ambulance_driver" 
   ON "emergencies_ambulance" ("assigned_driver_id") 
   WHERE ("assigned_driver_id" IS NOT NULL AND "is_active");
   ```
3. **Difference & Limitations:**
   - **Model Validation:** Operates at the Python application layer. Executed during `full_clean()` in forms and DRF serializers. Cannot prevent concurrent race conditions across separate HTTP worker threads by itself.
   - **Database Constraint:** Enforced atomically by PostgreSQL at the engine level. Prevents race conditions completely.
   - **Service-Layer Consideration:** The partial index only constrains active ambulances (`is_active=True`). Decommissioning an ambulance (`is_active=False`) frees the driver in the database. If the driver is currently mid-transit in an active emergency, state-machine service locks must prevent mid-trip driver reassignment (enforced in Phase 5).

### 3. Migration Generation & Application Details
* **Migration Generated & Applied:** `apps/emergencies/migrations/0001_initial.py`.
* **Dependency:** `migrations.swappable_dependency(settings.AUTH_USER_MODEL)`.
* **Database Verification:** Migration was explicitly authorized by the user and applied to `sertos_db` via `python manage.py migrate emergencies`. PostgreSQL introspection confirmed the creation of `emergencies_hospital` and `emergencies_ambulance`, expanding the database to exactly 14 tables while preserving 0 business records. Tests ran and passed cleanly.

### 4. Automated Testing Results
* `apps.emergencies`: 19/19 tests passed (1 scaffolding + 9 Hospital + 9 Ambulance tests).
* `apps.accounts`: 57/57 regression tests passed (0 failures, 0 errors).

---

### 5. Mentor Viva Questions & Answers (Q53 to Q56)

#### Q53: Why did we use `DecimalField` instead of `FloatField` for GPS coordinates?
**Answer:** `FloatField` uses IEEE 754 binary floating-point representation, which introduces rounding errors and precision drift in decimal fractions. `DecimalField(max_digits=9, decimal_places=6)` uses exact fixed-point arithmetic in PostgreSQL (`numeric(9, 6)`), guaranteeing 6 decimal places of precision (~0.11 meters at the equator), which is the international standard for civilian GPS accuracy without spatial drift.

#### Q54: Why is a partial unique index preferred over a standard unique constraint for `assigned_driver`?
**Answer:** A standard `unique=True` on `assigned_driver` would prevent multiple ambulances from having `assigned_driver = NULL` (unassigned ambulances), or prevent a driver from being assigned to a new ambulance if they were historically linked to an old, decommissioned ambulance (`is_active=False`). A partial unique index (`WHERE assigned_driver_id IS NOT NULL AND is_active`) ensures uniqueness only for currently active vehicles while allowing unlimited unassigned ambulances.

#### Q55: Why must unit tests wrap expected `IntegrityError` in `with transaction.atomic():` when testing PostgreSQL?
**Answer:** In PostgreSQL, when an SQL statement fails with a constraint violation (like a duplicate key in a unique index), PostgreSQL marks the transaction as aborted (`ERROR: current transaction is aborted, commands ignored until end of transaction block`). In Django's `TestCase`, the entire test runs in an atomic transaction. Wrapping the failing query in `with transaction.atomic():` creates a database savepoint that rolls back only the failed statement, leaving the outer transaction valid so subsequent test assertions can run without raising `TransactionManagementError`.

#### Q56: What is the difference between model-level validation (`clean()`) and database-level constraints?
**Answer:** Model validation (`clean()`) runs in Python memory during `full_clean()` (invoked by forms, serializers, and test suites). It provides human-readable, field-mapped error messages before sending SQL to the database. However, it cannot prevent race conditions where two concurrent requests read the same state and both write simultaneously. Database constraints (`CHECK`, `UNIQUE`, `FOREIGN KEY`) are enforced by the database engine at write time, providing ACID guarantees against concurrency races but raising lower-level `IntegrityError` exceptions. Enterprise systems use both: `clean()` for user feedback and constraints for bulletproof integrity.

---

## Section T: Task 4.1D Execution Record: Emergency Incident & Patient Models Implementation

### 1. Architectural Objective
Implement the core transactional and clinical emergency models in `apps/emergencies/models.py`:
- `EmergencyIncident`: The central operational entity representing an active emergency dispatch, linking the reporting paramedic/driver, dispatched vehicle, destination hospital facility, clinical severity, and strict lifecycle status tracking.
- `Patient`: Demographics, triage medical notes, and physiological profile linked to an emergency incident.

### 2. Model Design & Implementation

#### 2.1 Choice Enums
* **`IncidentSeverity`:** `CRITICAL` (Immediate life threat), `HIGH` (Severe/urgent), `MEDIUM` (Moderate urgency), `LOW` (Non-urgent).
* **`IncidentStatus`:** `REPORTED` (Initial alert), `ASSIGNED` (Vehicle dispatched), `IN_TRANSIT` (En route with preemption), `ARRIVED` (At hospital emergency department), `CLOSED` (Triage complete and closed), `CANCELLED` (Aborted before arrival).
* **`Gender`:** `MALE`, `FEMALE`, `OTHER`, `UNKNOWN`.
* **`BloodGroup`:** `A+`, `A-`, `B+`, `B-`, `AB+`, `AB-`, `O+`, `O-`, `UNKNOWN`.

#### 2.2 `EmergencyIncident` Model (`emergencies_incident`)
* **Fields:**
  - `id`: `UUIDField(primary_key=True, default=uuid.uuid4, editable=False)` — Prevents incident enumeration.
  - `incident_number`: `CharField(max_length=50, unique=True, db_index=True)` — Human-readable operational code (e.g. `INC-20261114-1234`).
  - `reporting_driver`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reported_incidents")` — The authenticated paramedic/driver initiating dispatch.
  - `ambulance`: `ForeignKey("Ambulance", on_delete=models.PROTECT, related_name="incidents")` — The dispatched vehicle.
  - `hospital`: `ForeignKey("Hospital", on_delete=models.PROTECT, null=True, blank=True, related_name="incoming_incidents")` — Destination medical facility.
  - `severity`: `CharField(max_length=20, choices=IncidentSeverity.choices, default=IncidentSeverity.HIGH)`.
  - `status`: `CharField(max_length=20, choices=IncidentStatus.choices, default=IncidentStatus.REPORTED, db_index=True)`.
  - `description`: `TextField(blank=True, default="")` — Contextual incident details.
  - **Milestone Timestamps:**
    - `assigned_at`: `DateTimeField(null=True, blank=True)` — When ambulance was dispatched.
    - `in_transit_at`: `DateTimeField(null=True, blank=True)` — When vehicle entered green corridor transit.
    - `arrived_at`: `DateTimeField(null=True, blank=True)` — When ambulance reached hospital emergency intake.
    - `closed_at`: `DateTimeField(null=True, blank=True)` — When incident was officially closed.
    - `cancelled_at`: `DateTimeField(null=True, blank=True)` — When incident was aborted.
  - `created_at`, `updated_at`: `DateTimeField`.
* **Validation & Security Rules (`clean()`):**
  - **Driver Role:** `reporting_driver.role` must strictly equal `UserRole.AMBULANCE_DRIVER`.
  - **Active Driver:** `reporting_driver.is_active` must be `True`.
  - **Active Ambulance:** Dispatched ambulance must have `is_active=True`.
  - **Driver Ownership:** The dispatched ambulance must be assigned to the reporting driver (`ambulance.assigned_driver_id == reporting_driver_id`), preventing cross-fleet spoofing.
  - **Active Destination Hospital:** If a destination hospital is assigned, it must be active (`hospital.is_active=True`).
  - **Finite State Machine (FSM):** Strict transition validation based on `VALID_TRANSITIONS` matrix:
    - `REPORTED` $\to$ `ASSIGNED`, `CANCELLED`
    - `ASSIGNED` $\to$ `IN_TRANSIT`, `CANCELLED`
    - `IN_TRANSIT` $\to$ `ARRIVED`, `CANCELLED`
    - `ARRIVED` $\to$ `CLOSED`
    - `CLOSED` $\to$ Terminal (no transitions permitted)
    - `CANCELLED` $\to$ Terminal (no transitions permitted)
  - **Automatic Milestone Timestamps (`save()`):** Automatically populates `assigned_at`, `in_transit_at`, `arrived_at`, `closed_at`, or `cancelled_at` with `timezone.now()` upon entering respective states if not already recorded.

#### 2.3 `Patient` Model (`emergencies_patient`)
* **Fields:**
  - `id`: `UUIDField(primary_key=True, default=uuid.uuid4, editable=False)`.
  - `incident`: `ForeignKey(EmergencyIncident, null=True, blank=True, on_delete=models.CASCADE, related_name="patients")` — Decoupled foreign key allowing pre-intake patient creation and multi-patient casualty management.
  - `name`: `CharField(max_length=150, blank=True, default="Unknown")` — Protects unverified identity during trauma intake.
  - `age`: `PositiveSmallIntegerField(null=True, blank=True)` — Validated between 0 and 150.
  - `gender`: `CharField(max_length=10, choices=Gender.choices, default=Gender.UNKNOWN)`.
  - `blood_group`: `CharField(max_length=10, choices=BloodGroup.choices, default=BloodGroup.UNKNOWN)`.
  - `medical_notes`: `TextField(blank=True, default="")` — Vital paramedic and triage observations.
  - `created_at`, `updated_at`: `DateTimeField`.
* **Validation Rules:**
  - Age bounds: $0 \le \text{age} \le 150$. Negative or implausible values raise `ValidationError`.

### 3. Migration Generation & Forensics
* **Migration Generated:** `apps/emergencies/migrations/0002_emergencyincident_patient_and_more.py`.
* **Inspection (`sqlmigrate emergencies 0002`):**
  - Creates table `emergencies_incident` with UUID primary key, indexed `incident_number`, indexed `status`, foreign keys to `accounts_user`, `emergencies_ambulance`, and `emergencies_hospital` with `ON DELETE RESTRICT` (PostgreSQL representation of `PROTECT`).
  - Creates table `emergencies_patient` with UUID primary key, foreign key to `emergencies_incident` with `ON DELETE CASCADE`.
  - Adds compound index `idx_inc_status_severity` on `(status, severity)`.
  - Adds index `idx_hosp_code` on `emergencies_hospital(hospital_code)`.
  - Adds compound index `idx_amb_avail_active` on `emergencies_ambulance(is_available, is_active)`.
* **Migration Applied & Database Verification:** Following explicit user review and authorization, migration `0002_emergencyincident_patient_and_more.py` was applied to `sertos_db` via `python manage.py migrate emergencies`. PostgreSQL introspection confirmed the creation of `emergencies_incident` and `emergencies_patient`, expanding the live database schema to exactly 16 tables. Foreign key constraints to `accounts_user`, `emergencies_ambulance`, `emergencies_hospital`, and `emergencies_incident` were verified along with UUID primary keys and performance indexes (`idx_inc_status_sev`, `idx_patient_created_at`, `idx_inc_created_at`). Existing tables and permissions were fully preserved, with business row counts remaining at 0 records.

### 4. Automated Testing Results
* `apps.emergencies`: 34/34 tests passed:
  - 1 scaffold test (`TEST-SCAFFOLD`)
  - 9 hospital tests (`HOSP-01` to `HOSP-09`)
  - 9 ambulance tests (`AMB-01` to `AMB-09`)
  - 10 emergency incident tests (`INC-01` to `INC-10`)
  - 5 patient tests (`PAT-01` to `PAT-05`)
* `apps.accounts`: 57/57 regression tests passed (0 failures, 0 errors).
* Total project test suite: **91/91 passing tests**.

---

### 5. Mentor Viva Questions & Answers (Q57 to Q60)

#### Q57: Why does `EmergencyIncident` enforce a finite state machine (FSM) in `clean()` instead of allowing arbitrary status updates?
**Answer:** In mission-critical emergency response, lifecycle states represent physical, legal, and operational realities. An ambulance cannot arrive at a hospital (`ARRIVED`) before it has even been dispatched (`ASSIGNED`) or traversed traffic (`IN_TRANSIT`). Allowing arbitrary state transitions could trigger automated green-corridor traffic signal preemption for ambulances that are already at the hospital, or close incidents without hospital handoff. By enforcing `VALID_TRANSITIONS` in `clean()`, we guarantee that state flow is strictly forward and auditable, while still allowing cancellation from any active state.

#### Q58: Why are foreign keys for `reporting_driver`, `ambulance`, and `hospital` configured with `on_delete=models.PROTECT`?
**Answer:** In medical and emergency transport systems, legal and clinical audit trails must be permanently preserved. If an administrator deactivates or removes a user account, ambulance fleet vehicle, or hospital record, cascading deletions (`CASCADE`) would permanently destroy all historical incident records associated with that entity, violating medical compliance laws and hindering forensic accident investigations. `models.PROTECT` raises a `ProtectedError`, preventing any referenced entity from being deleted while emergency incidents reference it.

#### Q59: Why is `Patient.incident` nullable (`null=True, blank=True`), and how does this support the emergency workflow?
**Answer:** In real-world emergency medicine, triage intake often begins before a formal incident dispatch is finalized in the system (e.g. walk-in trauma or emergency phone intake by dispatchers prior to vehicle assignment). Additionally, decoupling the patient model allows multi-patient mass-casualty incidents (a single incident linking to multiple patients via `related_name="patients"`), as well as creating patient records in advance that are linked to an incident as soon as dispatch occurs.

#### Q60: Why was migration `0002` initially kept unapplied in `sertos_db` before execution, and how was it verified?
**Answer:** SERTOS follows a strict enterprise database governance protocol: PLAN → INSPECT → BUILD → TEST → REPORT → STOP FOR USER APPROVAL. Unit tests execute inside Django's isolated test runner, which creates a temporary ephemeral database (`test_sertos_db`), applies all pending migrations, executes tests, and tears the database down. This allowed 100% verification of migration DDL, model constraints, and queries without touching the production/development database (`sertos_db`). Migration `0002` remained unapplied until the client/user inspected the SQL migration plan and granted explicit authorization. Once authorized, `migrate emergencies` was executed, and PostgreSQL schema introspection confirmed the creation of `emergencies_incident` and `emergencies_patient` (bringing the total to 16 live tables) with intact constraints and 0 business records.
