import { api, type Incident, type Notification, type PoliceTrafficOverview, type RouteSummary } from "../lib/api";

/**
 * Centralized Traffic Police API service wrapping verified SERTOS Django endpoints.
 * Never invents non-existent backend URLs.
 */
export const policeApiService = {
  fetchDashboardSnapshot: async (): Promise<{
    incidents: Incident[];
    notifications: Notification[];
    traffic: PoliceTrafficOverview;
  }> => {
    const [incidents, notificationsPage, traffic] = await Promise.all([
      api.getPoliceIncidents(),
      api.getNotifications().catch(() => null),
      api.getPoliceTrafficOverview(),
    ]);
    return {
      incidents,
      notifications: notificationsPage?.results ?? [],
      traffic,
    };
  },

  acknowledgeIncident: (incidentId: string) =>
    api.acknowledgePoliceIncident(incidentId),

  recheckCorridor: (incidentId: string) =>
    api.recheckTrafficCorridor(incidentId),

  getAmbulanceLocation: (incidentId: string) =>
    api.getLocation(incidentId),

  getIncidentRoute: (incidentId: string): Promise<RouteSummary> =>
    api.getRoute(incidentId),

  markNotificationRead: async (notificationId: string) => {
    const token =
      sessionStorage.getItem("sertos_access_token") ||
      localStorage.getItem("sertos_access_token");
    await fetch(`/api/notifications/${notificationId}/read/`, {
      method: "PATCH",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
  },

  markAllNotificationsRead: () => api.markAllNotificationsRead(),
};
