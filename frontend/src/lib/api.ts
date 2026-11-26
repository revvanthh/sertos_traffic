import { clearSession, getStoredToken, updateSessionTokens } from "./auth";

// Empty means same-origin: Vite proxies /api in development and Django serves
// the API alongside the frontend in a same-origin deployment. A separately
// hosted frontend should set VITE_API_BASE_URL to its backend origin.
const rawApiBaseUrl = import.meta.env.VITE_API_BASE_URL as string | undefined;
const configuredApiBaseUrl =
  rawApiBaseUrl?.replace(/\/$/, "") ?? "";
const pointsToLocalMachine = /^https?:\/\/(localhost|127(?:\.\d{1,3}){3}|\[::1\])(?::\d+)?$/i.test(configuredApiBaseUrl);
// Avoid shipping a stale localhost build value to real users. If no API origin
// was supplied to a separate production frontend, use the known SERTOS API.
const productionApiFallback = "https://sertos.onrender.com";
const API_BASE_URL = import.meta.env.PROD
  ? pointsToLocalMachine || rawApiBaseUrl === undefined
    ? productionApiFallback
    : configuredApiBaseUrl
  : configuredApiBaseUrl;

type ApiEnvelope<T> = {
  success: boolean;
  data: T;
  message?: string;
  errors?: Record<string, string[]>;
};

export type LoginData = {
  access: string;
  refresh: string;
  user: {
    id: number;
    username: string;
    role: string;
    is_verified: boolean;
  };
};

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

function unwrapPayload<T>(payload: unknown, statusCode: number): T {
  const envelope = isRecord(payload) && "success" in payload && "data" in payload
    ? payload as ApiEnvelope<T>
    : undefined;
  const errors = envelope?.errors ?? (isRecord(payload) ? payload : undefined);
  const firstFieldError = Object.values(errors ?? {}).flatMap((value) =>
    Array.isArray(value) ? value : [value],
  ).find((value): value is string => typeof value === "string");
  const detail = (Array.isArray(errors?.detail) ? errors.detail[0] : undefined)
    ?? (isRecord(payload) && typeof payload.detail === "string" ? payload.detail : undefined)
    ?? (isRecord(payload) && Array.isArray(payload.detail) && typeof payload.detail[0] === "string" ? payload.detail[0] : undefined)
    ?? firstFieldError;
  const message = envelope?.message
    ?? (isRecord(payload) && typeof payload.message === "string" ? payload.message : undefined);

  if (envelope?.success === false) {
    throw new ApiError(detail ?? message ?? "The request could not be completed.", statusCode);
  }
  return envelope ? envelope.data : payload as T;
}

async function decodeResponse<T>(response: Response): Promise<T> {
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    const responseType = response.headers.get("content-type") ?? "a non-JSON response";
    const unavailable = response.status === 502 || response.status === 503 || response.status === 504;
    throw new ApiError(
      `The SERTOS API returned HTTP ${response.status} as ${responseType}.${unavailable ? " The API service may be starting or unavailable." : " Check the backend response format."}`,
      response.status,
    );
  }

  if (!response.ok) {
    try {
      unwrapPayload(payload, response.status);
    } catch (error) {
      if (error instanceof ApiError) throw error;
    }
    const message = isRecord(payload) && typeof payload.detail === "string"
      ? payload.detail
      : isRecord(payload) && typeof payload.message === "string"
        ? payload.message
        : `The request failed with HTTP ${response.status}.`;
    throw new ApiError(message, response.status);
  }

  return unwrapPayload<T>(payload, response.status);
}

async function fetchRequest(path: string, options: RequestInit, accessToken: string | null) {
  const target = API_BASE_URL || (typeof window === "undefined" ? "this site" : window.location.origin);
  try {
    return await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        ...options.headers,
      },
    });
  } catch (reason) {
    return Promise.reject(new ApiError(
      `Could not reach the SERTOS API at ${target}. Check the API service, deployment URL, and CORS settings.${reason instanceof Error && reason.message ? ` (${reason.message})` : ""}`,
      0,
    ));
  }
}

let refreshInFlight: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;
  const refreshToken = getStoredToken("sertos_refresh_token");
  if (!refreshToken) return false;

  refreshInFlight = (async () => {
    const response = await fetchRequest(
      "/api/auth/token/refresh/",
      { method: "POST", body: JSON.stringify({ refresh: refreshToken }) },
      null,
    );
    const tokens = await decodeResponse<LoginRefresh>(response);
    updateSessionTokens(tokens);
    return true;
  })()
    .catch(() => false)
    .finally(() => { refreshInFlight = null; });
  return refreshInFlight;
}

async function request<T>(path: string, options: RequestInit = {}, canRefresh = true): Promise<T> {
  let response = await fetchRequest(path, options, getStoredToken("sertos_access_token"));

  if (
    response.status === 401 &&
    canRefresh &&
    !["/api/auth/login/", "/api/auth/register/", "/api/auth/token/refresh/"].includes(path)
  ) {
    const hasStoredSession = Boolean(
      getStoredToken("sertos_access_token") || getStoredToken("sertos_refresh_token"),
    );
    if (await refreshSession()) {
      response = await fetchRequest(path, options, getStoredToken("sertos_access_token"));
    } else if (hasStoredSession) {
      clearSession();
      window.dispatchEvent(new Event("sertos:session-expired"));
    }
  }

  return decodeResponse<T>(response);
}

export function login(username: string, password: string) {
  return request<LoginData>("/api/auth/login/", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export type LoginRefresh = {
  access: string;
  refresh?: string;
};

export type DriverRegistration = {
  id: number;
  username: string;
  email: string;
  role: "AMBULANCE_DRIVER";
  phone_number: string;
  badge_or_employee_id: string;
  is_verified: false;
};

export type UserProfile = {
  id: number;
  username: string;
  email: string;
  role: string;
  phone_number: string;
  badge_or_employee_id: string;
  ambulance_vehicle_number?: string | null;
  age: number | null;
  is_verified: boolean;
  date_joined: string;
  first_name?: string;
  last_name?: string;
};

export type Incident = {
  id: string;
  incident_number: string;
  severity: string;
  severity_display: string;
  status: string;
  status_display: string;
  description: string;
  patient_count: number;
  hospital_decision?: "ACCEPTED" | "REJECTED" | null;
  police_acknowledged?: boolean;
  hospital?: {
    id: string;
    name: string;
    address: string;
    latitude?: string | null;
    longitude?: string | null;
  };
  hospital_name?: string;
  hospital_code?: string;
  ambulance?: {
    vehicle_number: string;
  };
  patients?: PatientRecord[];
  reporting_driver?: { id: number; username: string; first_name: string; last_name: string };
  ambulance_vehicle_number?: string;
  created_at: string;
  updated_at: string;
  assigned_at?: string | null;
  in_transit_at?: string | null;
  arrived_at?: string | null;
  closed_at?: string | null;
  cancelled_at?: string | null;
};

export type PatientRecord = {
  id: string;
  name: string;
  age: number | null;
  gender: "MALE" | "FEMALE" | "OTHER" | "UNKNOWN";
  blood_group: string;
  medical_notes: string;
  created_at: string;
};

export type Hospital = {
  id: string;
  name: string;
  hospital_code: string;
  address: string;
  latitude: string | null;
  longitude: string | null;
  is_active: boolean;
};

export type RouteSummary = {
  distance_km: number;
  duration_formatted: string;
  estimated_arrival: string;
  polyline?: string;
};

export type HospitalBed = {
  id: string;
  hospital: string;
  bed_number: string;
  category: "GENERAL" | "ICU" | "EMERGENCY";
  status: "AVAILABLE" | "OCCUPIED" | "RESERVED";
  patient_label: string;
  updated_at: string;
};

export type Notification = {
  id: string;
  incident_id: string;
  incident_number: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
  read_at: string | null;
};

export type NotificationsPage = {
  count: number;
  next: string | null;
  previous: string | null;
  results: Notification[];
};

export type TrafficDeviceOverview = {
  id: string;
  device_id: string;
  name: string;
  intersection_name: string;
  latitude: string;
  longitude: string;
  is_active: boolean;
  last_heartbeat_at: string | null;
  current_signal_phase: string;
  firmware_version: string;
  sensor_1_detected: boolean | null;
  sensor_2_detected: boolean | null;
  latest_signal_state: {
    current_phase: string;
    is_preempted: boolean;
    reported_at: string;
  } | null;
};

export type TrafficDeviceRecord = {
  id: string;
  device_id: string;
  name: string;
  intersection_name: string;
  latitude: string;
  longitude: string;
  is_active: boolean;
  last_heartbeat_at: string | null;
  current_signal_phase: string;
  firmware_version: string;
  sensor_1_detected?: boolean | null;
  sensor_2_detected?: boolean | null;
  wifi_rssi?: number | null;
  operational_mode?: string | null;
  latest_signal_state?: {
    current_phase: string;
    is_preempted: boolean;
    reported_at: string;
  } | null;
  ip_address: string | null;
  mac_address: string;
  created_at: string;
  updated_at: string;
};

export type TrafficDeviceRegistration = Pick<TrafficDeviceRecord,
  "id" | "device_id" | "name" | "intersection_name" | "latitude" | "longitude" | "is_active"
> & {
  created_at: string;
  raw_token: string;
  raw_token_warning: string;
};

export type TrafficCommand = {
  id: string;
  device_id: string;
  incident_id: string;
  incident_number: string;
  action: string;
  status: string;
  created_at: string;
  expires_at: string;
  acknowledged_at: string | null;
  executed_at: string | null;
  execution_notes: string;
  failure_reason: string;
  distance_meters_at_creation: number | null;
  eta_seconds_at_creation: number | null;
};

export type AdminUserSummary = Pick<
  UserProfile,
  "id" | "username" | "email" | "role" | "is_verified" | "date_joined"
> & {
  first_name: string;
  last_name: string;
  is_active: boolean;
};

export type AdminAmbulance = {
  id: string;
  vehicle_number: string;
  vehicle_type: string;
  is_available: boolean;
  is_active: boolean;
  assigned_driver: string | null;
};

export type AdminOverview = {
  summary: {
    registered_users: number;
    pending_verification: number;
    active_ambulances: number;
    active_hospitals: number;
    active_junctions: number;
    pending_commands: number;
  };
  users: AdminUserSummary[];
  ambulances: AdminAmbulance[];
  commands: TrafficCommand[];
};

export type PoliceTrafficOverview = {
  devices: TrafficDeviceOverview[];
  commands: TrafficCommand[];
};

export const api = {
  registerDriver: (payload: {
    username: string;
    email: string;
    password: string;
    phone_number: string;
    badge_or_employee_id: string;
  }) =>
    request<DriverRegistration>("/api/auth/register/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getAdminOverview: () => request<AdminOverview>("/api/admin/overview/"),
  setUserVerification: (userId: number, is_verified: boolean) =>
    request<{ id: number; username: string; role: string; is_verified: boolean }>(
      `/api/admin/users/${userId}/verification/`,
      { method: "PATCH", body: JSON.stringify({ is_verified }) },
    ),
  getDriverIncident: (incidentId: string) =>
    request<Incident>(`/api/emergencies/${incidentId}/`),
  getHospitalIncident: (incidentId: string) =>
    request<Incident>(`/api/hospital/incidents/${incidentId}/`),
  getProfile: () =>
    request<UserProfile>("/api/auth/profile/"),
  updateProfile: (payload: Partial<{
    first_name: string;
    last_name: string;
    email: string;
    age: number;
    phone_number: string;
    badge_or_employee_id: string;
  }>) =>
    request<UserProfile>("/api/auth/profile/", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  getPoliceIncidents: () =>
    request<Incident[]>("/api/police/incidents/"),
  getHospitalIncidents: () =>
    request<Incident[]>("/api/hospital/incidents/"),
  getDriverIncidents: () =>
    request<Incident[]>("/api/emergencies/"),
  getHospitals: () =>
    request<Hospital[]>("/api/emergencies/hospitals/"),
  createEmergency: (payload: {
    hospital_id: string;
    severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
    description: string;
    patient: {
      name: string;
      age?: number;
      gender: "MALE" | "FEMALE" | "OTHER" | "UNKNOWN";
      blood_group?: string;
      medical_notes: string;
    };
  }) =>
    request<Incident>("/api/emergencies/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateIncidentStatus: (incidentId: string, status: string) =>
    request<Incident>(`/api/emergencies/${incidentId}/status/`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  sendLocation: (incidentId: string, latitude: number, longitude: number) =>
    request(`/api/emergencies/${incidentId}/location/`, {
      method: "POST",
      body: JSON.stringify({ latitude, longitude }),
    }),
  getRoute: (incidentId: string) =>
    request<RouteSummary>(`/api/emergencies/${incidentId}/route/`),
  getHospitalBeds: () =>
    request<HospitalBed[]>("/api/emergencies/hospital-beds/"),
  updateHospitalBed: (bedId: string, payload: Partial<Pick<HospitalBed, "status" | "patient_label">>) =>
    request<HospitalBed>(`/api/emergencies/hospital-beds/${bedId}/`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  createHospitalBed: (payload: {
    bed_number: string;
    category: "GENERAL" | "ICU" | "EMERGENCY";
    status?: "AVAILABLE" | "OCCUPIED" | "RESERVED";
  }) =>
    request<HospitalBed>("/api/emergencies/hospital-beds/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  decideHospitalIncident: (incidentId: string, decision: "ACCEPTED" | "REJECTED", reason = "") =>
    request("/api/emergencies/hospital/incidents/" + incidentId + "/decision/", {
      method: "PATCH",
      body: JSON.stringify({ decision, reason }),
    }),
  acknowledgePoliceIncident: (incidentId: string) =>
    request<{ incident_id: string; acknowledged: boolean; acknowledged_at: string }>(
      `/api/police/incidents/${incidentId}/acknowledge/`,
      { method: "POST" },
    ),
  getNotifications: () =>
    request<NotificationsPage>("/api/notifications/"),
  getPoliceTrafficOverview: () =>
    request<PoliceTrafficOverview>("/api/traffic/police/overview/"),
  recheckTrafficCorridor: (incidentId: string) =>
    request<{ created_count: number; commands: TrafficCommand[] }>(`/api/traffic/police/incidents/${incidentId}/recheck-corridor/`, {
      method: "POST",
    }),
  getTrafficDevices: () =>
    request<TrafficDeviceRecord[]>("/api/traffic/devices/"),
  registerTrafficDevice: (payload: {
    device_id: string;
    name: string;
    intersection_name: string;
    latitude: number;
    longitude: number;
  }) =>
    request<TrafficDeviceRegistration>("/api/traffic/devices/register/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateTrafficDevice: (deviceId: string, payload: Partial<Pick<TrafficDeviceRecord, "name" | "intersection_name" | "latitude" | "longitude" | "is_active">>) =>
    request<TrafficDeviceRecord>(`/api/traffic/devices/${encodeURIComponent(deviceId)}/`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  markAllNotificationsRead: () =>
    request<{ updated_count: number }>("/api/notifications/read-all/", {
      method: "PATCH",
    }),
  getLocation: (incidentId: string) =>
    request<{
      latitude: string;
      longitude: string;
      recorded_at: string;
    } | null>(`/api/emergencies/${incidentId}/location/`),
  logout: (refresh: string) =>
    request("/api/auth/logout/", {
      method: "POST",
      body: JSON.stringify({ refresh }),
    }, false),
};
