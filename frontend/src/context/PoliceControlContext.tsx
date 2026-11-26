import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  BENGALURU_CENTER,
  DEFAULT_POLICE_SETTINGS,
  DEMO_ALERTS,
  DEMO_AMBULANCES,
  DEMO_ANALYTICS_SERIES,
  DEMO_CCTV_CAMERAS,
  DEMO_HOSPITALS,
  DEMO_INCIDENT_MARKERS,
  DEMO_NOTIFICATIONS,
  DEMO_POLICE_ACTIONS,
  DEMO_POLICE_UNITS,
  DEMO_ROAD_SEGMENTS,
  DEMO_SIGNALS,
} from "../data/bengaluruDemoData";
import { api, type Incident } from "../lib/api";
import { decodePolyline } from "../lib/geoUtils";
import { getSession } from "../lib/auth";
import {
  checkBackendHealth,
  getAuthMode,
  getDefaultDemoProfile,
  logoutOfficer,
  saveDemoProfile,
} from "../services/authService";
import { policeApiService } from "../services/policeApiService";
import type {
  AmbulanceStage,
  AuthMode,
  CctvCamera,
  EmergencyAlert,
  HospitalMarkerData,
  LatLng,
  MapIncidentMarker,
  OfficerProfileState,
  PoliceActionItem,
  PoliceNotification,
  PoliceSettingsState,
  PoliceUnit,
  RoadFlowSegment,
  SignalLight,
  SystemServiceStatus,
  TrackedAmbulance,
  TrafficMetricPoint,
  TrafficSignal,
} from "../types/police";

const SETTINGS_STORAGE_KEY = "sertos_police_settings";

export interface ToastMessage {
  id: string;
  title: string;
  description?: string;
  variant: "success" | "info" | "warning" | "error";
}

interface PoliceControlContextValue {
  authMode: AuthMode;
  systemStatus: SystemServiceStatus;
  officerProfile: OfficerProfileState;
  alerts: EmergencyAlert[];
  selectedEmergencyId: string;
  setSelectedEmergencyId: (id: string) => void;
  selectedEmergency: EmergencyAlert;
  ambulances: TrackedAmbulance[];
  selectedAmbulanceId: string;
  setSelectedAmbulanceId: (id: string) => void;
  selectedAmbulance: TrackedAmbulance;
  hospitals: HospitalMarkerData[];
  signals: TrafficSignal[];
  policeUnits: PoliceUnit[];
  incidentMarkers: MapIncidentMarker[];
  roadSegments: RoadFlowSegment[];
  policeActions: PoliceActionItem[];
  notifications: PoliceNotification[];
  unreadNotificationCount: number;
  cctvCameras: CctvCamera[];
  analyticsSeries: TrafficMetricPoint[];
  settings: PoliceSettingsState;
  toasts: ToastMessage[];
  dismissToast: (id: string) => void;
  pushToast: (toast: Omit<ToastMessage, "id">) => void;
  refreshAllData: () => Promise<void>;
  acknowledgeAlert: (alertId: string) => Promise<void>;
  assignPoliceUnit: (alertId: string, unitCallSign: string) => void;
  notifyNearbyUnits: (alertId: string) => void;
  resolveAlert: (alertId: string) => void;
  toggleSignalEmergencyMode: (signalId: string, enable: boolean) => void;
  switchSignalLight: (signalId: string, light: SignalLight) => void;
  executeClearRouteAction: (incidentId: string) => Promise<{
    affectedSignals: string[];
    notifiedUnits: string[];
    actionItem: PoliceActionItem;
  }>;
  markNotificationRead: (id: string) => Promise<void>;
  markAllNotificationsRead: () => Promise<void>;
  clearAllNotifications: () => void;
  updateSettings: (next: PoliceSettingsState) => void;
  updateOfficerProfile: (patch: Partial<OfficerProfileState>) => Promise<void>;
  performLogout: () => Promise<void>;
  lastSyncedAt: Date | null;
  isSyncing: boolean;
  syncError: string;
}

const PoliceControlContext = createContext<PoliceControlContextValue | null>(null);

function interpolateRoute(waypoints: LatLng[], progress: number): LatLng {
  if (waypoints.length === 0) return BENGALURU_CENTER;
  if (waypoints.length === 1 || progress <= 0) return waypoints[0];
  if (progress >= 1) return waypoints[waypoints.length - 1];

  const totalSegments = waypoints.length - 1;
  const scaled = progress * totalSegments;
  const idx = Math.min(Math.floor(scaled), totalSegments - 1);
  const localT = scaled - idx;
  const p1 = waypoints[idx];
  const p2 = waypoints[idx + 1];
  return {
    lat: Number((p1.lat + (p2.lat - p1.lat) * localT).toFixed(6)),
    lng: Number((p1.lng + (p2.lng - p1.lng) * localT).toFixed(6)),
  };
}

function stageFromProgress(progress: number): AmbulanceStage {
  if (progress < 0.25) return "Dispatched";
  if (progress < 0.6) return "En Route";
  if (progress < 0.96) return "Approaching Hospital";
  return "Arrived";
}

function mapBackendSeverity(sev: string): EmergencyAlert["priority"] {
  const s = sev.toUpperCase();
  if (s === "CRITICAL") return "Critical";
  if (s === "HIGH") return "High";
  if (s === "LOW") return "Low";
  return "Medium";
}

function mapBackendStatus(incident: Incident): EmergencyAlert["status"] {
  if (incident.status === "CLOSED" || incident.status === "CANCELLED" || incident.status === "ARRIVED") {
    return "Resolved";
  }
  if (incident.status === "IN_TRANSIT") return "In Progress";
  if (incident.police_acknowledged) return "Acknowledged";
  return "New";
}

function formatShortIst(isoOrNow?: string): string {
  const date = isoOrNow ? new Date(isoOrNow) : new Date();
  return (
    new Intl.DateTimeFormat("en-IN", {
      timeZone: "Asia/Kolkata",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).format(date) + " IST"
  );
}

function loadSavedSettings(): PoliceSettingsState {
  try {
    const raw = localStorage.getItem(SETTINGS_STORAGE_KEY);
    if (raw) {
      return { ...DEFAULT_POLICE_SETTINGS, ...(JSON.parse(raw) as Partial<PoliceSettingsState>) };
    }
  } catch {
    // ignore malformed saved settings
  }
  return DEFAULT_POLICE_SETTINGS;
}

export function PoliceControlProvider({ children }: { children: ReactNode }) {
  const [authMode, setAuthMode] = useState<AuthMode>(() => getAuthMode());
  const [alerts, setAlerts] = useState<EmergencyAlert[]>(DEMO_ALERTS);
  const [selectedEmergencyId, setSelectedEmergencyId] = useState<string>(DEMO_ALERTS[0].incidentId);
  const [ambulances, setAmbulances] = useState<TrackedAmbulance[]>(DEMO_AMBULANCES);
  const [selectedAmbulanceId, setSelectedAmbulanceId] = useState<string>(DEMO_AMBULANCES[0].ambulanceId);
  const [hospitals] = useState<HospitalMarkerData[]>(DEMO_HOSPITALS);
  const [signals, setSignals] = useState<TrafficSignal[]>(DEMO_SIGNALS);
  const [policeUnits, setPoliceUnits] = useState<PoliceUnit[]>(DEMO_POLICE_UNITS);
  const [incidentMarkers] = useState<MapIncidentMarker[]>(DEMO_INCIDENT_MARKERS);
  const [roadSegments] = useState<RoadFlowSegment[]>(DEMO_ROAD_SEGMENTS);
  const [policeActions, setPoliceActions] = useState<PoliceActionItem[]>(DEMO_POLICE_ACTIONS);
  const [notifications, setNotifications] = useState<PoliceNotification[]>(DEMO_NOTIFICATIONS);
  const [cctvCameras] = useState<CctvCamera[]>(DEMO_CCTV_CAMERAS);
  const [analyticsSeries, setAnalyticsSeries] = useState<TrafficMetricPoint[]>(DEMO_ANALYTICS_SERIES);
  const [settings, setSettings] = useState<PoliceSettingsState>(loadSavedSettings);
  const [officerProfile, setOfficerProfile] = useState<OfficerProfileState>(() =>
    getDefaultDemoProfile(),
  );
  const [systemStatus, setSystemStatus] = useState<SystemServiceStatus>(() => ({
    backend: getAuthMode() === "demo" ? "Demo Mode" : "Connected",
    database: getAuthMode() === "demo" ? "Demo Mode" : "Connected",
    gps: getAuthMode() === "demo" ? "Simulated (Demo)" : "Live Feed",
    mapService: "OpenStreetMap / Vector",
    signalIntegration: "Simulated Only",
    cctv: "Demo Feed (No Hardware Stream)",
  }));
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [lastSyncedAt, setLastSyncedAt] = useState<Date | null>(() => new Date());
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncError, setSyncError] = useState("");

  const pollingStoppedRef = useRef(false);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const pushToast = useCallback(
    (toast: Omit<ToastMessage, "id">) => {
      const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
      setToasts((prev) => [...prev.slice(-3), { ...toast, id }]);
      window.setTimeout(() => {
        dismissToast(id);
      }, 4500);
    },
    [dismissToast],
  );

  const addNotification = useCallback(
    (notif: Omit<PoliceNotification, "id" | "timestamp" | "isRead">) => {
      const next: PoliceNotification = {
        ...notif,
        id: `notif-${Date.now()}-${Math.random().toString(36).slice(2, 5)}`,
        timestamp: formatShortIst(),
        isRead: false,
      };
      setNotifications((prev) => [next, ...prev].slice(0, 30));
    },
    [],
  );

  const refreshAllData = useCallback(async () => {
    if (pollingStoppedRef.current || !getSession()) return;
    const mode = getAuthMode();
    setAuthMode(mode);

    if (mode === "demo") {
      setIsSyncing(true);
      const health = await checkBackendHealth();
      setSystemStatus({
        backend: health.reachable ? "Connected" : "Demo Mode",
        database: health.databaseConnected ? "Connected" : "Demo Mode",
        gps: "Simulated (Demo)",
        mapService: "OpenStreetMap / Vector",
        signalIntegration: "Simulated Only",
        cctv: "Demo Feed (No Hardware Stream)",
      });
      setLastSyncedAt(new Date());
      setSyncError("");
      setIsSyncing(false);
      return;
    }

    // LIVE MODE — query real SERTOS Django endpoints
    setIsSyncing(true);
    try {
      const [profile, snapshot, health] = await Promise.all([
        api.getProfile().catch(() => null),
        policeApiService.fetchDashboardSnapshot(),
        checkBackendHealth(),
      ]);

      if (profile) {
        const fullName = [profile.first_name, profile.last_name].filter(Boolean).join(" ");
        setOfficerProfile({
          name: fullName || profile.username,
          officerId: profile.badge_or_employee_id || `ID-${profile.id}`,
          role: profile.role === "ADMIN" ? "System Administrator" : "Traffic Inspector",
          trafficDivision: "Bengaluru City Traffic Police — SERTOS Command",
          assignedZone: "Bengaluru Metro Network",
          email: profile.email || "Not provided",
          phone: profile.phone_number || "Not provided",
          accountStatus: profile.is_verified ? "Active (Verified)" : "Demo Officer",
        });
      }

      const hasDevices = snapshot.traffic.devices.length > 0;
      const hasInTransit = snapshot.incidents.some((inc) => inc.status === "IN_TRANSIT");

      setSystemStatus({
        backend: "Connected",
        database: health.databaseConnected ? "Connected" : "Connected",
        gps: hasInTransit ? "Live Feed" : "Offline",
        mapService: "OpenStreetMap / Vector",
        signalIntegration: hasDevices ? "ESP32 Telemetry" : "Simulated Only",
        cctv: "Demo Feed (No Hardware Stream)",
      });

      if (snapshot.incidents.length > 0) {
        const mappedAlerts: EmergencyAlert[] = snapshot.incidents.map((inc) => ({
          id: inc.id,
          incidentId: inc.incident_number,
          type: inc.description || "Emergency Response",
          condition: inc.description || "Live emergency dispatch from SERTOS backend.",
          patientLabel: `${inc.patient_count ?? 1} Patient(s) Aboard`,
          location: inc.hospital?.address || inc.hospital_name || "Bengaluru Corridor",
          zone: "Bengaluru Metro",
          ambulanceId: inc.ambulance?.vehicle_number || inc.ambulance_vehicle_number || "Unassigned",
          hospitalId: inc.hospital?.id || "hosp-live",
          hospitalName: inc.hospital?.name || inc.hospital_name || "Destination Pending",
          priority: mapBackendSeverity(inc.severity),
          status: mapBackendStatus(inc),
          etaMinutes: 5,
          distanceKm: 2.2,
          timeReceived: formatShortIst(inc.created_at),
          acknowledgedBy: inc.police_acknowledged ? "Traffic Control" : undefined,
          nearbyUnitsNotified: false,
          policeResponseStatus: inc.police_acknowledged
            ? "Acknowledged by Police Control"
            : "Awaiting Police Acknowledgement",
          timeline: [
            { id: "c1", label: "Reported", timestamp: formatShortIst(inc.created_at), status: "completed" },
            ...(inc.in_transit_at
              ? [{ id: "c2", label: "In Transit", timestamp: formatShortIst(inc.in_transit_at), status: "active" as const }]
              : []),
            ...(inc.arrived_at
              ? [{ id: "c3", label: "Arrived", timestamp: formatShortIst(inc.arrived_at), status: "completed" as const }]
              : []),
          ],
          source: "live",
        }));
        setAlerts(mappedAlerts);
        setSelectedEmergencyId((curr) =>
          mappedAlerts.some((a) => a.incidentId === curr) ? curr : mappedAlerts[0].incidentId,
        );

        // Ingest real GPS coordinates reported by ambulance drivers
        const activeIncidents = snapshot.incidents.filter(
          (inc) =>
            inc.status === "IN_TRANSIT" ||
            inc.status === "DISPATCHED" ||
            inc.status === "ASSIGNED" ||
            inc.status === "REPORTED",
        );

        if (activeIncidents.length > 0) {
          const liveAmbulanceResults = await Promise.all(
            activeIncidents.map(async (inc): Promise<TrackedAmbulance | null> => {
              const location = await api.getLocation(inc.id).catch(() => null);
              if (!location) return null;
              const route = await api.getRoute(inc.id).catch(() => null);
              const waypoints = route?.polyline ? decodePolyline(route.polyline) : [];
              const lat = Number(location.latitude);
              const lng = Number(location.longitude);
              if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;

              return {
                id: `amb-live-${inc.id}`,
                ambulanceId:
                  inc.ambulance?.vehicle_number ||
                  inc.ambulance_vehicle_number ||
                  `SRT-${inc.incident_number.replace(/[^0-9]/g, "").slice(-4) || "1047"}`,
                incidentId: inc.incident_number,
                emergencyType: inc.description || "Emergency Telemetry",
                status: inc.status === "IN_TRANSIT" ? "En Route" : "Dispatched",
                speedKmh: 48,
                etaMinutes: route ? Math.max(1, Math.round(route.distance_km * 1.8)) : 4,
                distanceKm: route ? Number(route.distance_km.toFixed(1)) : 1.8,
                destinationHospitalId: inc.hospital?.id || "hosp-vvit",
                destinationHospitalName:
                  inc.hospital?.name || inc.hospital_name || "Assigned Medical Center",
                priority: mapBackendSeverity(inc.severity),
                position: { lat, lng },
                routeWaypoints:
                  waypoints.length > 0
                    ? waypoints
                    : [{ lat, lng }],
                routeProgress: inc.status === "ARRIVED" ? 1.0 : 0.65,
                timestamps: {
                  dispatched: formatShortIst(inc.assigned_at || inc.created_at).slice(0, 5),
                  onRoute: formatShortIst(inc.in_transit_at || inc.created_at).slice(0, 5),
                  arrivingSoon: "Pending",
                  hospitalArrived: inc.arrived_at
                    ? formatShortIst(inc.arrived_at).slice(0, 5)
                    : "Pending",
                },
                source: "live",
              };
            }),
          );

          const validLiveAmbulances = liveAmbulanceResults.filter(
            (a): a is TrackedAmbulance => Boolean(a),
          );

          if (validLiveAmbulances.length > 0) {
            setAmbulances(validLiveAmbulances);
            setSelectedAmbulanceId((curr) =>
              validLiveAmbulances.some((a) => a.ambulanceId === curr)
                ? curr
                : validLiveAmbulances[0].ambulanceId,
            );
          }
        }
      }

      if (snapshot.notifications.length > 0) {
        setNotifications(
          snapshot.notifications.map((n) => ({
            id: n.id,
            category: "New emergency",
            title: n.title,
            message: n.message,
            timestamp: formatShortIst(n.created_at),
            isRead: n.is_read,
            incidentId: n.incident_number,
          })),
        );
      }

      if (hasDevices) {
        setSignals(
          snapshot.traffic.devices.map((dev) => ({
            id: dev.id,
            signalId: dev.device_id,
            location: dev.intersection_name,
            zone: "ESP32 Network",
            position: {
              lat: Number(dev.latitude) || BENGALURU_CENTER.lat,
              lng: Number(dev.longitude) || BENGALURU_CENTER.lng,
            },
            currentLight:
              dev.current_signal_phase === "GREEN" ||
              dev.current_signal_phase === "YELLOW" ||
              dev.current_signal_phase === "RED"
                ? dev.current_signal_phase
                : "RED",
            trafficDensity:
              dev.sensor_1_detected || dev.sensor_2_detected ? "Heavy" : "Moderate",
            trafficVolumePerHour: 2100,
            mode: dev.latest_signal_state?.is_preempted
              ? "Emergency Priority"
              : "Automatic",
            status: dev.is_active ? "Active" : "Offline",
            countdownSeconds: 30,
            cycleTiming: { green: 45, yellow: 4, red: 40 },
            lastUpdate: dev.last_heartbeat_at
              ? formatShortIst(dev.last_heartbeat_at)
              : "No heartbeat",
            lastMaintenance: "Live ESP32 Node",
            affectedRoutes: [dev.name],
            hardwareConnected: true,
          })),
        );
      }

      setSyncError("");
      setLastSyncedAt(new Date());
    } catch (err) {
      setSyncError(err instanceof Error ? err.message : "Backend sync failed.");
      setSystemStatus((prev) => ({
        ...prev,
        backend: "Disconnected",
      }));
    } finally {
      setIsSyncing(false);
    }
  }, []);

  // Initial sync & periodic polling (cleaned up properly on unmount / logout)
  useEffect(() => {
    pollingStoppedRef.current = false;
    void refreshAllData();
    const interval = window.setInterval(() => {
      void refreshAllData();
    }, Math.max(4, settings.refreshIntervalSec) * 1000);

    return () => {
      window.clearInterval(interval);
    };
  }, [refreshAllData, settings.refreshIntervalSec]);

  // Signal countdown ticker (1s) + Demo ambulance movement (2.5s)
  useEffect(() => {
    const signalTick = window.setInterval(() => {
      if (pollingStoppedRef.current) return;
      setSignals((prev) =>
        prev.map((sig) => {
          if (sig.status === "Offline") return sig;
          if (sig.countdownSeconds > 1) {
            return { ...sig, countdownSeconds: sig.countdownSeconds - 1 };
          }
          // Cycle signal phase cleanly when countdown reaches 0
          if (sig.mode === "Emergency Priority") {
            return {
              ...sig,
              currentLight: "GREEN",
              countdownSeconds: sig.cycleTiming.green,
            };
          }
          const nextLight: SignalLight =
            sig.currentLight === "GREEN"
              ? "YELLOW"
              : sig.currentLight === "YELLOW"
                ? "RED"
                : "GREEN";
          const nextSeconds =
            nextLight === "GREEN"
              ? sig.cycleTiming.green
              : nextLight === "YELLOW"
                ? sig.cycleTiming.yellow
                : sig.cycleTiming.red;
          return {
            ...sig,
            currentLight: nextLight,
            countdownSeconds: nextSeconds,
            lastUpdate: "Just now",
          };
        }),
      );
    }, 1000);

    const demoMoveTick = window.setInterval(() => {
      if (pollingStoppedRef.current || authMode !== "demo") return;
      setAmbulances((prev) =>
        prev.map((amb) => {
          if (amb.status === "Completed") return amb;
          // Advance smoothly along route waypoints, looping gently once arrived for continuous demo
          let nextProgress = amb.routeProgress + 0.015;
          if (nextProgress > 1.08) {
            nextProgress = 0.25;
          }
          const clamped = Math.min(nextProgress, 1);
          const nextPos = interpolateRoute(amb.routeWaypoints, clamped);
          const nextStage = stageFromProgress(clamped);
          const remainingRatio = Math.max(0, 1 - clamped);
          const nextDistance = Number((Math.max(0.1, remainingRatio * 3.0)).toFixed(1));
          const nextEta = Math.max(1, Math.round(nextDistance * 1.8));
          return {
            ...amb,
            position: nextPos,
            routeProgress: nextProgress,
            status: nextStage,
            distanceKm: nextStage === "Arrived" ? 0 : nextDistance,
            etaMinutes: nextStage === "Arrived" ? 0 : nextEta,
            timestamps: {
              ...amb.timestamps,
              hospitalArrived:
                nextStage === "Arrived" ? formatShortIst().slice(0, 5) : "Pending",
            },
          };
        }),
      );
    }, 2500);

    return () => {
      window.clearInterval(signalTick);
      window.clearInterval(demoMoveTick);
    };
  }, [authMode]);

  const acknowledgeAlert = useCallback(
    async (alertId: string) => {
      const target = alerts.find((a) => a.id === alertId || a.incidentId === alertId);
      if (!target) return;

      if (authMode === "live" && target.source === "live") {
        await policeApiService.acknowledgeIncident(target.id);
      }

      setAlerts((prev) =>
        prev.map((a) =>
          a.id === target.id
            ? {
                ...a,
                status: a.status === "New" ? "Acknowledged" : a.status,
                acknowledgedBy: officerProfile.name,
                policeResponseStatus: `Acknowledged by ${officerProfile.name}`,
                timeline: [
                  ...a.timeline,
                  {
                    id: `ack-${Date.now()}`,
                    label: "Alert Acknowledged",
                    timestamp: formatShortIst(),
                    status: "completed",
                    detail: `Acknowledged by ${officerProfile.name}`,
                  },
                ],
              }
            : a,
        ),
      );

      setPoliceActions((prev) => [
        {
          id: `act-${Date.now()}`,
          title: `Alert ${target.incidentId} Acknowledged`,
          status: "completed",
          timestamp: formatShortIst(),
          incidentId: target.incidentId,
          performedBy: officerProfile.name,
          details: `Officer acknowledged ${target.type} (${target.ambulanceId} -> ${target.hospitalName}).`,
        },
        ...prev,
      ]);

      addNotification({
        category: "Police unit assigned",
        title: `Incident ${target.incidentId} Acknowledged`,
        message: `${officerProfile.name} acknowledged ${target.type} for ${target.ambulanceId}.`,
        incidentId: target.incidentId,
      });

      pushToast({
        title: "Alert Acknowledged",
        description: `${target.incidentId} updated across dashboard and alerts.`,
        variant: "success",
      });
    },
    [alerts, authMode, officerProfile.name, addNotification, pushToast],
  );

  const assignPoliceUnit = useCallback(
    (alertId: string, unitCallSign: string) => {
      const target = alerts.find((a) => a.id === alertId || a.incidentId === alertId);
      if (!target) return;

      setAlerts((prev) =>
        prev.map((a) =>
          a.id === target.id
            ? {
                ...a,
                status: a.status === "New" ? "In Progress" : a.status,
                assignedUnitId: unitCallSign,
                policeResponseStatus: `Unit ${unitCallSign} Assigned & Escorting`,
                timeline: [
                  ...a.timeline,
                  {
                    id: `unit-${Date.now()}`,
                    label: `Unit ${unitCallSign} Assigned`,
                    timestamp: formatShortIst(),
                    status: "completed",
                  },
                ],
              }
            : a,
        ),
      );

      setPoliceUnits((prev) =>
        prev.map((u) =>
          u.callSign === unitCallSign
            ? { ...u, status: "Escorting", assignedIncidentId: target.incidentId }
            : u,
        ),
      );

      setPoliceActions((prev) => [
        {
          id: `act-${Date.now()}`,
          title: `Police Unit ${unitCallSign} Assigned`,
          status: "completed",
          timestamp: formatShortIst(),
          incidentId: target.incidentId,
          performedBy: officerProfile.name,
          details: `Dispatched ${unitCallSign} to escort ${target.ambulanceId} along ${target.location}.`,
          notifiedUnits: [unitCallSign],
        },
        ...prev,
      ]);

      addNotification({
        category: "Police unit assigned",
        title: `Unit ${unitCallSign} Assigned`,
        message: `Assigned to ${target.incidentId} (${target.location}).`,
        incidentId: target.incidentId,
      });

      pushToast({
        title: "Police Unit Assigned",
        description: `${unitCallSign} dispatched to ${target.incidentId}.`,
        variant: "info",
      });
    },
    [alerts, officerProfile.name, addNotification, pushToast],
  );

  const notifyNearbyUnits = useCallback(
    (alertId: string) => {
      const target = alerts.find((a) => a.id === alertId || a.incidentId === alertId);
      if (!target) return;

      setAlerts((prev) =>
        prev.map((a) =>
          a.id === target.id ? { ...a, nearbyUnitsNotified: true } : a,
        ),
      );

      setPoliceActions((prev) => [
        {
          id: `act-${Date.now()}`,
          title: "Nearby Units Notified",
          status: "completed",
          timestamp: formatShortIst(),
          incidentId: target.incidentId,
          performedBy: officerProfile.name,
          details: `Priority corridor alert broadcast to patrol units near ${target.location}.`,
          notifiedUnits: policeUnits.map((u) => u.callSign),
        },
        ...prev,
      ]);

      addNotification({
        category: "Police unit assigned",
        title: "Nearby Patrol Units Alerted",
        message: `All division units near ${target.location} alerted for ${target.ambulanceId}.`,
        incidentId: target.incidentId,
      });

      pushToast({
        title: "Nearby Units Notified",
        description: `Broadcast sent for ${target.incidentId}.`,
        variant: "success",
      });
    },
    [alerts, officerProfile.name, policeUnits, addNotification, pushToast],
  );

  const resolveAlert = useCallback(
    (alertId: string) => {
      const target = alerts.find((a) => a.id === alertId || a.incidentId === alertId);
      if (!target) return;

      setAlerts((prev) =>
        prev.map((a) =>
          a.id === target.id
            ? {
                ...a,
                status: "Resolved",
                etaMinutes: 0,
                distanceKm: 0,
                policeResponseStatus: "Resolved — Normal Traffic Restored",
                timeline: [
                  ...a.timeline,
                  {
                    id: `res-${Date.now()}`,
                    label: "Incident Resolved",
                    timestamp: formatShortIst(),
                    status: "completed",
                  },
                ],
              }
            : a,
        ),
      );

      setAmbulances((prev) =>
        prev.map((amb) =>
          amb.incidentId === target.incidentId
            ? { ...amb, status: "Completed", etaMinutes: 0, distanceKm: 0 }
            : amb,
        ),
      );

      setPoliceActions((prev) => [
        {
          id: `act-${Date.now()}`,
          title: `Incident ${target.incidentId} Marked Resolved`,
          status: "completed",
          timestamp: formatShortIst(),
          incidentId: target.incidentId,
          performedBy: officerProfile.name,
          details: `Corridor restored to normal cycle after ${target.ambulanceId} completion.`,
        },
        ...prev,
      ]);

      pushToast({
        title: "Incident Resolved",
        description: `${target.incidentId} moved to resolved state.`,
        variant: "success",
      });
    },
    [alerts, officerProfile.name, pushToast],
  );

  const toggleSignalEmergencyMode = useCallback(
    (signalId: string, enable: boolean) => {
      let targetLocation = "";
      setSignals((prev) =>
        prev.map((sig) => {
          if (sig.id !== signalId && sig.signalId !== signalId) return sig;
          targetLocation = sig.location;
          return {
            ...sig,
            mode: enable ? "Emergency Priority" : "Automatic",
            currentLight: enable ? "GREEN" : sig.currentLight,
            countdownSeconds: enable ? 45 : sig.cycleTiming.green,
            lastUpdate: "Just now",
          };
        }),
      );

      if (targetLocation) {
        setPoliceActions((prev) => [
          {
            id: `act-${Date.now()}`,
            title: enable
              ? `Priority Green Simulated — ${targetLocation}`
              : `Normal Cycle Restored — ${targetLocation}`,
            status: "completed",
            timestamp: formatShortIst(),
            performedBy: officerProfile.name,
            details: enable
              ? `Simulated Emergency Priority green hold activated at ${targetLocation} (no physical road hardware controlled).`
              : `Simulated Emergency Priority disabled at ${targetLocation}.`,
            affectedSignals: [targetLocation],
          },
          ...prev,
        ]);

        addNotification({
          category: "Signal update",
          title: enable
            ? `Simulated Priority Green: ${targetLocation}`
            : `Signal Restored: ${targetLocation}`,
          message: `Demo simulation updated by ${officerProfile.name}.`,
        });

        pushToast({
          title: enable ? "Emergency Priority Simulated" : "Normal Cycle Restored",
          description: `${targetLocation} (${enable ? "Priority Green — 45s" : "Automatic cycle"}).`,
          variant: enable ? "warning" : "info",
        });
      }
    },
    [officerProfile.name, addNotification, pushToast],
  );

  const switchSignalLight = useCallback(
    (signalId: string, light: SignalLight) => {
      let targetLocation = "";
      setSignals((prev) =>
        prev.map((sig) => {
          if (sig.id !== signalId && sig.signalId !== signalId) return sig;
          targetLocation = sig.location;
          return {
            ...sig,
            currentLight: light,
            mode: "Manual Override",
            countdownSeconds:
              light === "GREEN"
                ? sig.cycleTiming.green
                : light === "YELLOW"
                  ? sig.cycleTiming.yellow
                  : sig.cycleTiming.red,
            lastUpdate: "Just now",
          };
        }),
      );

      if (targetLocation) {
        pushToast({
          title: `Signal Phase Simulated (${light})`,
          description: `${targetLocation} updated in simulation mode.`,
          variant: "info",
        });
      }
    },
    [pushToast],
  );

  const executeClearRouteAction = useCallback(
    async (incidentId: string) => {
      const targetAlert =
        alerts.find((a) => a.incidentId === incidentId || a.id === incidentId) ?? alerts[0];
      const affectedSignals = ["MG Road (BLR-SIG-01)", "Trinity Circle (BLR-SIG-03)", "Indiranagar (BLR-SIG-06)"];
      const notifiedUnits = ["PCR-BLR-04", "TP-MGR-12", "TP-IND-07"];

      if (authMode === "live" && targetAlert.source === "live") {
        await policeApiService.recheckCorridor(targetAlert.id).catch(() => null);
      }

      // Activate emergency priority simulation on route signals
      setSignals((prev) =>
        prev.map((sig) =>
          ["sig-mg-road", "sig-trinity", "sig-indiranagar"].includes(sig.id)
            ? {
                ...sig,
                mode: "Emergency Priority",
                currentLight: "GREEN",
                countdownSeconds: 45,
                lastUpdate: "Just now",
              }
            : sig,
        ),
      );

      // Update analytics slightly to reflect optimization
      setAnalyticsSeries((prev) =>
        prev.map((pt, idx) =>
          idx === prev.length - 1
            ? { ...pt, speed: Math.min(44, pt.speed + 2), delay: Math.max(1.8, Number((pt.delay - 0.3).toFixed(1))) }
            : pt,
        ),
      );

      const actionItem: PoliceActionItem = {
        id: `act-clr-${Date.now()}`,
        title: `Emergency Route Cleared (${targetAlert.incidentId})`,
        status: "completed",
        timestamp: formatShortIst(),
        incidentId: targetAlert.incidentId,
        performedBy: officerProfile.name,
        details: `Simulated corridor optimization across ${affectedSignals.join(", ")} and notified ${notifiedUnits.join(", ")}.`,
        affectedSignals,
        notifiedUnits,
      };

      setPoliceActions((prev) => [
        actionItem,
        ...prev.map((item) =>
          item.status === "pending" ? { ...item, status: "completed" as const } : item,
        ),
      ]);

      addNotification({
        category: "Route cleared",
        title: `Emergency Route Cleared — ${targetAlert.ambulanceId}`,
        message: `Simulated green corridor active across MG Road -> VVIT Hospital.`,
        incidentId: targetAlert.incidentId,
      });

      pushToast({
        title: "Emergency Route Cleared (Simulation)",
        description: `${affectedSignals.length} signals prioritized and ${notifiedUnits.length} patrol units notified.`,
        variant: "success",
      });

      return { affectedSignals, notifiedUnits, actionItem };
    },
    [alerts, authMode, officerProfile.name, addNotification, pushToast],
  );

  const markNotificationRead = useCallback(
    async (id: string) => {
      if (authMode === "live") {
        await policeApiService.markNotificationRead(id).catch(() => null);
      }
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, isRead: true } : n)),
      );
    },
    [authMode],
  );

  const markAllNotificationsRead = useCallback(async () => {
    if (authMode === "live") {
      await policeApiService.markAllNotificationsRead().catch(() => null);
    }
    setNotifications((prev) => prev.map((n) => ({ ...n, isRead: true })));
    pushToast({
      title: "Notifications Cleared",
      description: "All notifications marked as read.",
      variant: "info",
    });
  }, [authMode, pushToast]);

  const clearAllNotifications = useCallback(() => {
    setNotifications([]);
    pushToast({
      title: "Notification Center Empty",
      description: "Cleared notification feed for this session.",
      variant: "info",
    });
  }, [pushToast]);

  const updateSettings = useCallback(
    (next: PoliceSettingsState) => {
      setSettings(next);
      localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(next));
      pushToast({
        title: "Settings Saved",
        description: "Dashboard and alert preferences updated.",
        variant: "success",
      });
    },
    [pushToast],
  );

  const updateOfficerProfile = useCallback(
    async (patch: Partial<OfficerProfileState>) => {
      const next = { ...officerProfile, ...patch };
      if (authMode === "live") {
        const [first_name, ...rest] = (next.name || "").split(/\s+/);
        await api.updateProfile({
          first_name: first_name || "",
          last_name: rest.join(" "),
          email: next.email,
          phone_number: next.phone,
          badge_or_employee_id: next.officerId,
        });
      } else {
        saveDemoProfile(next);
      }
      setOfficerProfile(next);
      pushToast({
        title: "Officer Profile Updated",
        description: "Profile details saved successfully.",
        variant: "success",
      });
    },
    [authMode, officerProfile, pushToast],
  );

  const performLogout = useCallback(async () => {
    pollingStoppedRef.current = true;
    await logoutOfficer();
  }, []);

  const selectedEmergency = useMemo(
    () =>
      alerts.find((a) => a.incidentId === selectedEmergencyId || a.id === selectedEmergencyId) ??
      alerts[0],
    [alerts, selectedEmergencyId],
  );

  const selectedAmbulance = useMemo(
    () =>
      ambulances.find(
        (amb) =>
          amb.ambulanceId === selectedAmbulanceId ||
          amb.id === selectedAmbulanceId ||
          amb.incidentId === selectedEmergencyId,
      ) ?? ambulances[0],
    [ambulances, selectedAmbulanceId, selectedEmergencyId],
  );

  const unreadNotificationCount = useMemo(
    () => notifications.filter((n) => !n.isRead).length,
    [notifications],
  );

  const value: PoliceControlContextValue = {
    authMode,
    systemStatus,
    officerProfile,
    alerts,
    selectedEmergencyId,
    setSelectedEmergencyId,
    selectedEmergency,
    ambulances,
    selectedAmbulanceId,
    setSelectedAmbulanceId,
    selectedAmbulance,
    hospitals,
    signals,
    policeUnits,
    incidentMarkers,
    roadSegments,
    policeActions,
    notifications,
    unreadNotificationCount,
    cctvCameras,
    analyticsSeries,
    settings,
    toasts,
    dismissToast,
    pushToast,
    refreshAllData,
    acknowledgeAlert,
    assignPoliceUnit,
    notifyNearbyUnits,
    resolveAlert,
    toggleSignalEmergencyMode,
    switchSignalLight,
    executeClearRouteAction,
    markNotificationRead,
    markAllNotificationsRead,
    clearAllNotifications,
    updateSettings,
    updateOfficerProfile,
    performLogout,
    lastSyncedAt,
    isSyncing,
    syncError,
  };

  return (
    <PoliceControlContext.Provider value={value}>
      {children}
    </PoliceControlContext.Provider>
  );
}

export function usePoliceControl(): PoliceControlContextValue {
  const ctx = useContext(PoliceControlContext);
  if (!ctx) {
    throw new Error("usePoliceControl must be used inside PoliceControlProvider");
  }
  return ctx;
}
