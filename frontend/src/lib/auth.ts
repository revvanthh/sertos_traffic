import type { LoginData } from "./api";

const SESSION_KEY = "sertos_auth_session";

export type AuthSession = LoginData;

export function getSession(): AuthSession | null {
  const stored =
    sessionStorage.getItem(SESSION_KEY) ?? localStorage.getItem(SESSION_KEY);
  if (!stored) return null;

  try {
    return JSON.parse(stored) as AuthSession;
  } catch {
    localStorage.removeItem(SESSION_KEY);
    sessionStorage.removeItem(SESSION_KEY);
    return null;
  }
}

export function getStoredToken(key: "sertos_access_token" | "sertos_refresh_token"): string | null {
  return sessionStorage.getItem(key) ?? localStorage.getItem(key);
}

export function saveSession(session: AuthSession, rememberMe = true) {
  const primary = rememberMe ? localStorage : sessionStorage;
  const secondary = rememberMe ? sessionStorage : localStorage;

  primary.setItem(SESSION_KEY, JSON.stringify(session));
  primary.setItem("sertos_access_token", session.access);
  primary.setItem("sertos_refresh_token", session.refresh);

  secondary.removeItem(SESSION_KEY);
  secondary.removeItem("sertos_access_token");
  secondary.removeItem("sertos_refresh_token");
}

export function updateSessionTokens(tokens: { access: string; refresh?: string }) {
  const session = getSession();
  const useSessionStorage = Boolean(sessionStorage.getItem(SESSION_KEY));
  const storage = useSessionStorage ? sessionStorage : localStorage;

  if (!session) {
    storage.setItem("sertos_access_token", tokens.access);
    if (tokens.refresh) storage.setItem("sertos_refresh_token", tokens.refresh);
    return;
  }

  const updated = {
    ...session,
    access: tokens.access,
    refresh: tokens.refresh ?? session.refresh,
  };
  saveSession(updated, !useSessionStorage);
}

export function clearSession() {
  localStorage.removeItem(SESSION_KEY);
  localStorage.removeItem("sertos_access_token");
  localStorage.removeItem("sertos_refresh_token");
  sessionStorage.removeItem(SESSION_KEY);
  sessionStorage.removeItem("sertos_access_token");
  sessionStorage.removeItem("sertos_refresh_token");
}
