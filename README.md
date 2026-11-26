# SERTOS

**Smart Emergency Response and Traffic Override System** is a Django REST service, a React/Vite operations frontend, and a supervised ESP32 bench demonstration.

The local workspace contains the backend source, frontend, hardware prototypes, and API documentation in one folder. The original sensor-only ESP32 sketch is preserved. A separate REST controller sketch uses the supplied LED/sensor pin mapping; it is limited to low-voltage bench LEDs and must never connect to public-road traffic equipment.

## Requirements

- Python 3.12 or newer
- Node.js 20.19+ or 22.12+
- npm
- Optional: Google Maps browser key and backend Routes API key
- Optional: Arduino IDE 2.x, ESP32 board package, ArduinoJson 6.x, and LiquidCrystal_I2C for the bench firmware

## Run the Django backend

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Health check: <http://127.0.0.1:8000/api/health/>

The example environment uses SQLite for local development. Replace its development-only Django secret before using the backend outside a local machine. `.env` and local databases are ignored by Git.

## Run the frontend

In another PowerShell window:

```powershell
cd frontend
npm ci
Copy-Item .env.example .env.local
```

For the local Django server, edit `frontend/.env.local` and set:

```text
VITE_API_BASE_URL=
VITE_GOOGLE_MAPS_API_KEY=
```

An empty API base uses Vite's `/api` proxy to `http://127.0.0.1:8000`. Then start Vite:

```powershell
npm run dev
```

Open the URL printed by Vite. To use the deployed API directly instead, set `VITE_API_BASE_URL=https://sertos.onrender.com`. Google Maps stays in its honest fallback state until a browser Maps key is configured. Restrict a browser key to the exact frontend origins; it is public client configuration, not a private server key.

Production bundle and lint commands:

```powershell
npm run build
npm run lint
```

For Django-hosted production assets, build from the repository root with `npm ci --prefix frontend` and `npm run build --prefix frontend`; the Vite production base is `/static/` for WhiteNoise.

## Accounts and roles

The backend supports `AMBULANCE_DRIVER`, `POLICE_DISPATCHER`, `HOSPITAL_STAFF`, and `ADMIN`. Protected frontend routes mirror those roles, and the API remains the authority for permissions.

Public registration creates only an unverified ambulance-driver account. An administrator must verify it before login. Hospital, police, and administrator accounts require authorized provisioning; the browser cannot choose a privileged role. The workspace backend adds administrator-only user verification and overview endpoints at `/api/admin/overview/` and `/api/admin/users/<id>/verification/`.

## Main API integrations

- Authentication: `/api/auth/login/`, `/api/auth/token/refresh/`, `/api/auth/logout/`, `/api/auth/register/`, `/api/auth/profile/`
- Driver incidents, hospital choices, routes, and GPS: `/api/emergencies/`
- Hospital queue, patient detail, and bed records: `/api/hospital/` and `/api/emergencies/hospital-beds/`
- Police incidents and acknowledgements: `/api/police/`
- Notifications: `/api/notifications/`
- Traffic controller admin and police views: `/api/traffic/`
- ESP32 REST: `/api/traffic/esp32/config/`, `heartbeat/`, `status/`, `signal-state/`, `commands/pending/`, and `commands/<id>/ack/`

Browser authentication uses JWT access/refresh tokens. Device calls use `X-Device-ID` and `X-Device-Token`; device tokens never belong in frontend configuration. Dashboard refreshes use HTTP polling because the backend does not provide WebSockets.

The workspace adds `/api/admin/overview/`, `/api/admin/users/<id>/verification/`, and `PATCH /api/traffic/devices/<device_id>/` for user/fleet administration. These changes are local until the backend source is separately deployed. The hosted Render API cannot expose a route that has not been deployed.

## Maps and live data

Maps display backend coordinates only: browser GPS reports, hospital coordinates, registered junction coordinates, and route geometry returned by the configured backend routing service. Missing coordinates, route data, browser permission, or credentials are shown as unavailable. The driver map cannot submit manually selected/fabricated map coordinates as GPS.

An IR reading means an obstacle was detected. It is not an ambulance identity check. Command status in the backend is separate from the physical state of the bench LEDs; `EXECUTED` means the authenticated device reported the configured GPIO state, not that a public signal was independently verified.

## ESP32 bench demonstration

The original sensor-only REST prototype is in `hardware/esp32_traffic_node/`. The separate supplied-pin-map controller is in `hardware/esp32_traffic_node_rest_control/`. Read that folder's README before wiring or compiling.

The controller uses red/yellow/green LEDs on GPIO 25/26/27; entry/exit active-low sensors on GPIO 32/33; and a 16×2 I2C LCD on GPIO 21/22 at address `0x27`. It gets timing and poll intervals from the authenticated backend configuration endpoint, validates commands and expiry, and uses certificate-checked HTTPS. It does not use MQTT.

Register a device through an authorized administrator, save the one-time device token privately, copy `secrets.h.example` to `secrets.h`, then configure Wi-Fi, device credentials, and the verified trusted root CA for the backend TLS chain. Do not copy a previously exposed Wi-Fi password; rotate it first. No credentials are supplied in this workspace. Firmware is not flashed automatically.

## Backend configuration and CORS

`.env.example` contains local backend settings. `frontend/.env.example` contains the deployed API base. Private backend settings such as Django `SECRET_KEY`, `DATABASE_URL`, and `GOOGLE_MAPS_API_KEY` stay server-side.

For a separately hosted frontend, set the backend's `CORS_ALLOWED_ORIGINS` to the exact frontend origins (scheme and host only) in the backend environment. Do not guess an origin or use a broad wildcard. Same-origin Django hosting does not need a separate browser CORS origin. ESP32 requests are not browser CORS requests.

No Render environment variables, production database rows, external APIs, or hardware were changed during this workspace implementation.

## Checks

```powershell
python manage.py check
python manage.py test --verbosity 1
cd frontend
npm run build
npm run lint
```

Backend tests use Django's isolated test database. Hardware behavior still requires a supported ESP32 board, verified wiring, Arduino toolchain compilation, configured credentials, and supervised physical bench validation.
