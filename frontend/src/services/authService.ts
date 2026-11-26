import { ENV } from "../config/env";
import { ApiError, api, login as backendLogin } from "../lib/api";
import { clearSession, getSession, saveSession, type AuthSession } from "../lib/auth";
import type { AuthMode, OfficerProfileState } from "../types/police";

const AUTH_MODE_KEY = "sertos_auth_mode";
const OFFICER_OVERRIDE_KEY = "sertos_demo_officer_profile";
const LOGIN_HISTORY_KEY = "sertos_login_history";

export interface LoginResult {
  session: AuthSession;
  mode: AuthMode;
  redirectTo: string;
}

export interface LoginHistoryEntry {
  id: string;
  timestamp: string;
  mode: AuthMode;
  identifier: string;
  status: "Success" | "Failed";
  note: string;
}

export function getAuthMode(): AuthMode {
  const stored =
    sessionStorage.getItem(AUTH_MODE_KEY) || localStorage.getItem(AUTH_MODE_KEY);
  return stored === "demo" ? "demo" : "live";
}

export function isAuthenticated(): boolean {
  return Boolean(getSession());
}

export function getLoginHistory(): LoginHistoryEntry[] {
  try {
    const raw = localStorage.getItem(LOGIN_HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as LoginHistoryEntry[]) : [];
  } catch {
    return [];
  }
}

function recordLoginHistory(entry: Omit<LoginHistoryEntry, "id" | "timestamp">) {
  const next: LoginHistoryEntry[] = [
    {
      ...entry,
      id: `lh-${Date.now()}`,
      timestamp: new Date().toISOString(),
    },
    ...getLoginHistory(),
  ].slice(0, 10);
  localStorage.setItem(LOGIN_HISTORY_KEY, JSON.stringify(next));
}

function persistSession(session: AuthSession, mode: AuthMode, rememberMe: boolean) {
  saveSession(session, rememberMe);
  if (rememberMe) {
    localStorage.setItem(AUTH_MODE_KEY, mode);
    sessionStorage.removeItem(AUTH_MODE_KEY);
  } else {
    sessionStorage.setItem(AUTH_MODE_KEY, mode);
    localStorage.removeItem(AUTH_MODE_KEY);
  }
}

export function getRoleDestination(role: string): string {
  const destinations: Record<string, string> = {
    AMBULANCE_DRIVER: "/driver",
    POLICE_DISPATCHER: "/dashboard",
    HOSPITAL_STAFF: "/hospital",
    ADMIN: "/admin",
  };
  return destinations[role] ?? "/dashboard";
}

export async function checkBackendHealth(): Promise<{
  reachable: boolean;
  databaseConnected: boolean;
}> {
  try {
    const res = await fetch(`${ENV.API_BASE_URL}/api/health/`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      return { reachable: false, databaseConnected: false };
    }
    const body = (await res.json()) as { status?: string; database?: string };
    return {
      reachable: true,
      databaseConnected: body.database === "connected" || body.status === "healthy",
    };
  } catch {
    return { reachable: false, databaseConnected: false };
  }
}

export function matchesDemoCredentials(identifier: string, password: string): boolean {
  if (!ENV.DEMO_MODE_ENABLED) return false;
  const cleanId = identifier.trim().toLowerCase();
  const validIds = [
    ENV.DEMO_OFFICER_ID.toLowerCase(),
    ENV.DEMO_OFFICER_EMAIL.toLowerCase(),
    "demo_police_sharma",
  ];
  return validIds.includes(cleanId) && password === ENV.DEMO_OFFICER_PASSWORD;
}

export async function authenticateOfficer(params: {
  identifier: string;
  password: string;
  rememberMe: boolean;
  preferDemo?: boolean;
}): Promise<LoginResult> {
  const { identifier, password, rememberMe, preferDemo = false } = params;
  const cleanId = identifier.trim();

  if (preferDemo) {
    if (!ENV.DEMO_MODE_ENABLED) {
      throw new ApiError("Demo Mode is disabled in this environment.", 403);
    }
    if (!matchesDemoCredentials(cleanId, password)) {
      recordLoginHistory({
        mode: "demo",
        identifier: cleanId,
        status: "Failed",
        note: "Invalid demo officer credentials",
      });
      throw new ApiError(
        "Invalid Officer ID/Email or password for Demo Mode.",
        401,
      );
    }
    const demoSession: AuthSession = {
      access: "demo-mode-session-token",
      refresh: "demo-mode-refresh-token",
      user: {
        id: 9047,
        username: ENV.DEMO_OFFICER_ID,
        role: "POLICE_DISPATCHER",
        is_verified: true,
      },
    };
    persistSession(demoSession, "demo", rememberMe);
    recordLoginHistory({
      mode: "demo",
      identifier: cleanId,
      status: "Success",
      note: "Authenticated in Demo Mode (simulated session)",
    });
    return {
      session: demoSession,
      mode: "demo",
      redirectTo: "/dashboard",
    };
  }

  // Attempt real Django JWT backend authentication first
  try {
    const session = await backendLogin(cleanId, password);
    persistSession(session, "live", rememberMe);
    recordLoginHistory({
      mode: "live",
      identifier: cleanId,
      status: "Success",
      note: `Authenticated via SERTOS Django JWT (${session.user.role})`,
    });
    return {
      session,
      mode: "live",
      redirectTo: getRoleDestination(session.user.role),
    };
  } catch (err) {
    // Only fall back to Demo Mode if backend is unreachable (status 0 or 502/503/504)
    // AND the entered credentials match the configured demo officer credentials.
    const isBackendUnreachable =
      err instanceof ApiError && [0, 502, 503, 504].includes(err.status);
    if (
      isBackendUnreachable &&
      ENV.DEMO_MODE_ENABLED &&
      matchesDemoCredentials(cleanId, password)
    ) {
      const demoSession: AuthSession = {
        access: "demo-mode-session-token",
        refresh: "demo-mode-refresh-token",
        user: {
          id: 9047,
          username: ENV.DEMO_OFFICER_ID,
          role: "POLICE_DISPATCHER",
          is_verified: true,
        },
      };
      persistSession(demoSession, "demo", rememberMe);
      recordLoginHistory({
        mode: "demo",
        identifier: cleanId,
        status: "Success",
        note: "Backend unreachable — signed into Demo Mode",
      });
      return {
        session: demoSession,
        mode: "demo",
        redirectTo: "/dashboard",
      };
    }

    recordLoginHistory({
      mode: "live",
      identifier: cleanId,
      status: "Failed",
      note: err instanceof Error ? err.message : "Authentication failed",
    });
    throw err;
  }
}

export async function logoutOfficer(): Promise<void> {
  const session = getSession();
  const mode = getAuthMode();
  if (mode === "live" && session?.refresh && session.refresh !== "demo-mode-refresh-token") {
    try {
      await api.logout(session.refresh);
    } catch {
      // Clear local credentials even if the network/refresh blacklist fails
    }
  }
  clearSession();
  localStorage.removeItem(AUTH_MODE_KEY);
  sessionStorage.removeItem(AUTH_MODE_KEY);
  localStorage.removeItem(OFFICER_OVERRIDE_KEY);
  sessionStorage.removeItem("sertos_protected_cache");
}

export function getDefaultDemoProfile(): OfficerProfileState {
  try {
    const saved = localStorage.getItem(OFFICER_OVERRIDE_KEY);
    if (saved) {
      return JSON.parse(saved) as OfficerProfileState;
    }
  } catch {
    // ignore malformed override
  }
  return {
    name: ENV.DEMO_OFFICER_NAME,
    officerId: ENV.DEMO_OFFICER_ID,
    role: "Traffic Inspector",
    trafficDivision: "Bengaluru City Traffic Police — Emergency Corridor Unit",
    assignedZone: ENV.DEMO_CONTROL_ZONE,
    email: ENV.DEMO_OFFICER_EMAIL,
    phone: "+91 80 2294 3100",
    accountStatus: "Demo Officer",
  };
}

export function saveDemoProfile(profile: OfficerProfileState): void {
  localStorage.setItem(OFFICER_OVERRIDE_KEY, JSON.stringify(profile));
}
