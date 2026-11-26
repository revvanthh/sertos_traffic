export type AuthMode = "live" | "demo";

export type AlertSeverity = "Critical" | "High" | "Medium" | "Low";
export type AlertStatus = "New" | "Acknowledged" | "In Progress" | "Resolved";
export type AmbulanceStage =
  | "Dispatched"
  | "En Route"
  | "Approaching Hospital"
  | "Arrived"
  | "Completed";

export type SignalLight = "RED" | "YELLOW" | "GREEN";
export type SignalMode = "Automatic" | "Emergency Priority" | "Manual Override";
export type SignalConnectivity = "Active" | "Simulated" | "Offline";
export type TrafficDensityLevel = "Smooth" | "Moderate" | "Heavy";

export interface LatLng {
  lat: number;
  lng: number;
}

export interface TimelineEvent {
  id: string;
  label: string;
  timestamp: string;
  status: "completed" | "active" | "pending";
  detail?: string;
}

export interface EmergencyAlert {
  id: string;
  incidentId: string;
  type: string;
  condition: string;
  patientLabel: string;
  location: string;
  zone: string;
  ambulanceId: string;
  hospitalId: string;
  hospitalName: string;
  priority: AlertSeverity;
  status: AlertStatus;
  etaMinutes: number;
  distanceKm: number;
  timeReceived: string;
  acknowledgedBy?: string;
  assignedUnitId?: string;
  nearbyUnitsNotified: boolean;
  policeResponseStatus: string;
  timeline: TimelineEvent[];
  source: "live" | "demo";
}

export interface HospitalMarkerData {
  id: string;
  name: string;
  shortName: string;
  position: LatLng;
  availableBeds: number | null;
  icuBeds: number | null;
  destinationStatus: string;
  estimatedArrival: string;
}

export interface TrackedAmbulance {
  id: string;
  ambulanceId: string;
  incidentId: string;
  emergencyType: string;
  status: AmbulanceStage;
  speedKmh: number;
  etaMinutes: number;
  distanceKm: number;
  destinationHospitalId: string;
  destinationHospitalName: string;
  priority: AlertSeverity;
  position: LatLng;
  routeWaypoints: LatLng[];
  routeProgress: number; // 0 to 1
  timestamps: {
    dispatched: string;
    onRoute: string;
    arrivingSoon: string;
    hospitalArrived: string;
  };
  source: "live" | "demo";
}

export interface TrafficSignal {
  id: string;
  signalId: string;
  location: string;
  zone: string;
  position: LatLng;
  currentLight: SignalLight;
  trafficDensity: TrafficDensityLevel;
  trafficVolumePerHour: number;
  mode: SignalMode;
  status: SignalConnectivity;
  countdownSeconds: number;
  cycleTiming: { green: number; yellow: number; red: number };
  lastUpdate: string;
  lastMaintenance: string;
  affectedRoutes: string[];
  hardwareConnected: boolean;
}

export interface PoliceUnit {
  id: string;
  callSign: string;
  officerName: string;
  zone: string;
  status: "Patrolling" | "Escorting" | "Dispatched" | "Standby";
  position: LatLng;
  assignedIncidentId?: string;
}

export interface MapIncidentMarker {
  id: string;
  title: string;
  severity: "High" | "Moderate" | "Low";
  description: string;
  location: string;
  position: LatLng;
  reportedAt: string;
}

export interface RoadFlowSegment {
  id: string;
  name: string;
  density: TrafficDensityLevel;
  speedKmh: number;
  coordinates: LatLng[];
}

export interface PoliceActionItem {
  id: string;
  title: string;
  status: "completed" | "pending";
  timestamp: string;
  incidentId?: string;
  performedBy: string;
  details: string;
  affectedSignals?: string[];
  notifiedUnits?: string[];
}

export type NotificationCategory =
  | "New emergency"
  | "Ambulance approaching"
  | "Traffic congestion"
  | "Route cleared"
  | "Police unit assigned"
  | "Signal update";

export interface PoliceNotification {
  id: string;
  category: NotificationCategory;
  title: string;
  message: string;
  timestamp: string;
  isRead: boolean;
  incidentId?: string;
  severity?: AlertSeverity;
}

export interface CctvCamera {
  id: string;
  cameraId: string;
  location: string;
  zone: string;
  status: "Demo Simulation" | "Live Stream" | "Offline";
  vehicleDensity: TrafficDensityLevel;
  signalId: string;
  isLiveSource: boolean;
}

export interface TrafficMetricPoint {
  time: string;
  speed: number;
  density: number;
  delay: number;
}

export interface OfficerProfileState {
  name: string;
  officerId: string;
  role: string;
  trafficDivision: string;
  assignedZone: string;
  email: string;
  phone: string;
  accountStatus: "Active (Verified)" | "Demo Officer";
}

export interface PoliceSettingsState {
  defaultMapLayers: {
    traffic: boolean;
    emergencyRoutes: boolean;
    policeUnits: boolean;
    incidents: boolean;
  };
  alertSound: boolean;
  desktopPopups: boolean;
  autoFocusEmergency: boolean;
  defaultCctvId: string;
  refreshIntervalSec: number;
  notifications: {
    emergencyAlerts: boolean;
    routeCleared: boolean;
    ambulanceNearingHospital: boolean;
    signalStatusChanges: boolean;
    policeUnitUpdates: boolean;
  };
}

export interface SystemServiceStatus {
  backend: "Connected" | "Disconnected" | "Demo Mode";
  database: "Connected" | "Unavailable" | "Demo Mode";
  gps: "Live Feed" | "Simulated (Demo)" | "Offline";
  mapService: "OpenStreetMap / Vector" | "Offline Fallback";
  signalIntegration: "ESP32 Telemetry" | "Simulated Only";
  cctv: "Demo Feed (No Hardware Stream)";
}
