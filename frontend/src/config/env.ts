/**
 * Centralized environment and mode configuration for SERTOS.
 */

const rawApiBaseUrl = import.meta.env.VITE_API_BASE_URL as string | undefined;
const configuredApiBaseUrl = rawApiBaseUrl?.replace(/\/$/, "") ?? "";
const pointsToLocalMachine = /^https?:\/\/(localhost|127(?:\.\d{1,3}){3}|\[::1\])(?::\d+)?$/i.test(
  configuredApiBaseUrl,
);

const productionApiFallback = "https://sertos.onrender.com";

const STORAGE_MAPS_KEY = "sertos_google_maps_api_key";

export function getGoogleMapsApiKey(): string {
  const envKey = (import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string | undefined)?.trim();
  if (envKey) return envKey;
  try {
    const saved = localStorage.getItem(STORAGE_MAPS_KEY)?.trim();
    if (saved) return saved;
  } catch {
    // ignore storage access errors
  }
  return "";
}

export function setGoogleMapsApiKey(key: string): void {
  try {
    if (key.trim()) {
      localStorage.setItem(STORAGE_MAPS_KEY, key.trim());
    } else {
      localStorage.removeItem(STORAGE_MAPS_KEY);
    }
  } catch {
    // ignore storage access errors
  }
}

export const ENV = {
  API_BASE_URL: import.meta.env.PROD
    ? pointsToLocalMachine || rawApiBaseUrl === undefined
      ? productionApiFallback
      : configuredApiBaseUrl
    : configuredApiBaseUrl,
  DEMO_MODE_ENABLED:
    String(import.meta.env.VITE_ENABLE_DEMO_MODE ?? "true").toLowerCase() !== "false",
  DEMO_OFFICER_ID:
    (import.meta.env.VITE_DEMO_OFFICER_ID as string | undefined) || "BTP-INSP-1047",
  DEMO_OFFICER_EMAIL:
    (import.meta.env.VITE_DEMO_OFFICER_EMAIL as string | undefined) ||
    "inspector.karthik@btp.gov.in",
  DEMO_OFFICER_PASSWORD:
    (import.meta.env.VITE_DEMO_OFFICER_PASSWORD as string | undefined) ||
    "SertosDemo@2026",
  DEMO_OFFICER_NAME:
    (import.meta.env.VITE_DEMO_OFFICER_NAME as string | undefined) ||
    "Inspector Karthik Gowda",
  DEMO_CONTROL_ZONE:
    (import.meta.env.VITE_DEMO_CONTROL_ZONE as string | undefined) ||
    "Central Division — MG Road & Indiranagar Corridor",
  GOOGLE_MAPS_API_KEY: getGoogleMapsApiKey(),
} as const;
