# SERTOS frontend

This React/Vite app is the frontend for the Django project in the workspace root. The Django API, frontend source, and ESP32 prototypes are maintained together here.

## Local development

```powershell
cd frontend
npm ci
Copy-Item .env.example .env.local
```

To use the local Django server, set `VITE_API_BASE_URL=` in `.env.local`. Vite then proxies `/api` and `/health` to `http://127.0.0.1:8000`. Set `VITE_GOOGLE_MAPS_API_KEY` only if you have a browser-restricted Maps key; without it, map panels show the available location data and a clear unavailable state.

Start the app with `npm run dev`. Build and lint with `npm run build` and `npm run lint`.

## Separate frontend hosting

Set `VITE_API_BASE_URL=https://sertos.onrender.com` in the frontend host's build environment, or use `frontend/.env.example` as the starting point. The frontend calls that API directly, so add the exact frontend origin to the backend's `CORS_ALLOWED_ORIGINS` setting. Do not use a broad wildcard. Keep Maps browser keys restricted to the exact frontend origins.

An empty API base is appropriate when Django serves both the frontend and API on one origin. The production API client ignores stale localhost API URLs and falls back to the SERTOS Render API if no production API origin was supplied.

The production bundle uses `/static/` so Django/WhiteNoise can serve its hashed assets. See the root README for backend setup and Django-hosted production build instructions.
