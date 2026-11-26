import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import {
  Circle,
  MapContainer,
  Marker,
  Polyline,
  Popup,
  TileLayer,
  Tooltip,
  useMap,
} from "react-leaflet";
import {
  Crosshair,
  KeyRound,
  Layers,
  MapPin,
  Minus,
  Navigation,
  Plus,
  Radio,
  RotateCcw,
  Route,
  Shield,
  TriangleAlert,
  X,
} from "lucide-react";
import { BENGALURU_CENTER } from "../../data/bengaluruDemoData";
import { usePoliceControl } from "../../context/PoliceControlContext";
import type { LatLng } from "../../types/police";
import { StatusBadge } from "../common/StatusBadge";
import { useRealLocation } from "../../hooks/useRealLocation";
import { getGoogleMapsApiKey, setGoogleMapsApiKey } from "../../config/env";
import { GoogleMapView } from "./GoogleMapView";

interface BengaluruTrafficMapProps {
  heightClass?: string;
  focusPosition?: LatLng | null;
  onSelectEmergency?: (incidentId: string) => void;
}

function createAmbulanceIcon(ambulanceId: string, isSelected: boolean) {
  return L.divIcon({
    className: "sertos-div-icon",
    iconSize: [44, 44],
    iconAnchor: [22, 22],
    html: `
      <div style="
        width:40px;height:40px;border-radius:12px;
        background:#0A1729;border:2px solid ${isSelected ? "#24A8FF" : "#20E39A"};
        box-shadow:0 0 18px ${isSelected ? "rgba(36,168,255,0.65)" : "rgba(32,227,154,0.5)"};
        display:flex;align-items:center;justify-content:center;color:#F1F5F9;font-size:18px;
      ">🚑</div>
      <span style="
        position:absolute;top:-7px;right:-7px;padding:1px 5px;border-radius:999px;
        background:#00D084;color:#020B18;font-size:9px;font-weight:800;
      ">${ambulanceId.replace("SRT-", "")}</span>
    `,
  });
}

function createHospitalIcon() {
  return L.divIcon({
    className: "sertos-div-icon",
    iconSize: [38, 38],
    iconAnchor: [19, 34],
    html: `
      <div style="
        width:36px;height:36px;border-radius:10px;
        background:#0D1D32;border:2px solid #EF4444;
        box-shadow:0 0 14px rgba(239,68,68,0.55);
        display:flex;align-items:center;justify-content:center;color:#F1F5F9;font-weight:800;font-size:15px;
      ">🏥</div>
    `,
  });
}

function createPoliceUnitIcon() {
  return L.divIcon({
    className: "sertos-div-icon",
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    html: `
      <div style="
        width:26px;height:26px;border-radius:50%;
        background:#0A1729;border:2px solid #24A8FF;
        box-shadow:0 0 10px rgba(36,168,255,0.45);
        display:flex;align-items:center;justify-content:center;color:#24A8FF;font-size:11px;font-weight:800;
      ">P</div>
    `,
  });
}

function createIncidentIcon() {
  return L.divIcon({
    className: "sertos-div-icon",
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    html: `
      <div style="
        width:26px;height:26px;border-radius:8px;
        background:#451A03;border:2px solid #F59E0B;
        box-shadow:0 0 10px rgba(245,158,11,0.45);
        display:flex;align-items:center;justify-content:center;color:#FBBF24;font-size:12px;font-weight:900;
      ">!</div>
    `,
  });
}

function createRealUserIcon() {
  return L.divIcon({
    className: "sertos-user-gps-icon",
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    html: `
      <div style="position:relative;width:32px;height:32px;display:flex;align-items:center;justify-content:center;">
        <div style="position:absolute;inset:0;border-radius:50%;background:#24A8FF;opacity:0.4;animation:ping 1.6s cubic-bezier(0,0,0.2,1) infinite;"></div>
        <div style="width:16px;height:16px;border-radius:50%;background:#24A8FF;border:3px solid #FFFFFF;box-shadow:0 0 14px rgba(36,168,255,0.95);z-index:2;"></div>
      </div>
    `,
  });
}

function MapController({
  zoomAction,
  centerTarget,
  focusPosition,
  realPosition,
  followRealLocation,
}: {
  zoomAction: { type: "in" | "out" | "reset" | "locate" | "locate-user"; seq: number } | null;
  centerTarget: LatLng | null;
  focusPosition?: LatLng | null;
  realPosition: LatLng | null;
  followRealLocation: boolean;
}) {
  const map = useMap();

  useEffect(() => {
    if (!zoomAction) return;
    if (zoomAction.type === "in") {
      map.zoomIn();
    } else if (zoomAction.type === "out") {
      map.zoomOut();
    } else if (zoomAction.type === "reset") {
      map.setView([BENGALURU_CENTER.lat, BENGALURU_CENTER.lng], 14, { animate: true });
    } else if (zoomAction.type === "locate" && centerTarget) {
      map.setView([centerTarget.lat, centerTarget.lng], 15, { animate: true });
    } else if (zoomAction.type === "locate-user" && realPosition) {
      map.setView([realPosition.lat, realPosition.lng], 16, { animate: true });
    }
  }, [zoomAction, centerTarget, realPosition, map]);

  useEffect(() => {
    if (focusPosition) {
      map.setView([focusPosition.lat, focusPosition.lng], 15, { animate: true });
    }
  }, [focusPosition, map]);

  useEffect(() => {
    if (followRealLocation && realPosition) {
      map.panTo([realPosition.lat, realPosition.lng], { animate: true });
    }
  }, [followRealLocation, realPosition, map]);

  return null;
}

export function BengaluruTrafficMap({
  heightClass = "h-[410px] xl:h-[435px]",
  focusPosition,
  onSelectEmergency,
}: BengaluruTrafficMapProps) {
  const {
    authMode,
    ambulances,
    selectedAmbulance,
    setSelectedAmbulanceId,
    setSelectedEmergencyId,
    hospitals,
    policeUnits,
    signals,
    incidentMarkers,
    roadSegments,
    settings,
  } = usePoliceControl();

  // Map Provider State: "google" or "leaflet"
  const [apiKey, setApiKey] = useState(() => getGoogleMapsApiKey());
  const [mapEngine, setMapEngine] = useState<"google" | "leaflet">(() =>
    getGoogleMapsApiKey() ? "google" : "leaflet",
  );
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [keyInput, setKeyInput] = useState(apiKey);
  const [keySaveMessage, setKeySaveMessage] = useState("");

  // Real-time Geolocation Hook
  const realLoc = useRealLocation();
  const [followUserLocation, setFollowUserLocation] = useState(false);

  // Layer Toggles
  const [showTraffic, setShowTraffic] = useState(settings.defaultMapLayers.traffic);
  const [showRoutes, setShowRoutes] = useState(settings.defaultMapLayers.emergencyRoutes);
  const [showPolice, setShowPolice] = useState(settings.defaultMapLayers.policeUnits);
  const [showIncidents, setShowIncidents] = useState(settings.defaultMapLayers.incidents);
  const [showSignals, setShowSignals] = useState(true);

  // Zoom / Recenter Actions
  const [zoomAction, setZoomAction] = useState<{
    type: "in" | "out" | "reset" | "locate" | "locate-user";
    seq: number;
  } | null>(null);
  const [tileError, setTileError] = useState(false);

  // Google Maps Instance Ref for manual controls
  const googleMapInstanceRef = useRef<google.maps.Map | null>(null);

  const activeTarget = focusPosition ?? selectedAmbulance.position;

  const hospitalIcons = useMemo(() => createHospitalIcon(), []);
  const policeIcon = useMemo(() => createPoliceUnitIcon(), []);
  const incidentIcon = useMemo(() => createIncidentIcon(), []);
  const realUserIcon = useMemo(() => createRealUserIcon(), []);

  const triggerMapAction = (type: "in" | "out" | "reset" | "locate" | "locate-user") => {
    if (mapEngine === "google" && googleMapInstanceRef.current) {
      const gMap = googleMapInstanceRef.current;
      if (type === "in") {
        gMap.setZoom((gMap.getZoom() ?? 14) + 1);
      } else if (type === "out") {
        gMap.setZoom((gMap.getZoom() ?? 14) - 1);
      } else if (type === "reset") {
        gMap.panTo({ lat: BENGALURU_CENTER.lat, lng: BENGALURU_CENTER.lng });
        gMap.setZoom(14);
      } else if (type === "locate" && activeTarget) {
        gMap.panTo({ lat: activeTarget.lat, lng: activeTarget.lng });
        gMap.setZoom(16);
      } else if (type === "locate-user" && realLoc.position) {
        gMap.panTo({ lat: realLoc.position.lat, lng: realLoc.position.lng });
        gMap.setZoom(17);
      }
    } else {
      setZoomAction((prev) => ({ type, seq: (prev?.seq ?? 0) + 1 }));
    }
  };

  const handleSaveApiKey = () => {
    const trimmed = keyInput.trim();
    setGoogleMapsApiKey(trimmed);
    setApiKey(trimmed);
    if (trimmed) {
      setMapEngine("google");
      setKeySaveMessage("Google Maps API key saved! Loading Google Maps...");
      setTimeout(() => {
        setShowKeyModal(false);
        setKeySaveMessage("");
      }, 1200);
    } else {
      setKeySaveMessage("Key removed. Switched to Dark Vector Map.");
      setMapEngine("leaflet");
      setTimeout(() => {
        setShowKeyModal(false);
        setKeySaveMessage("");
      }, 1200);
    }
  };

  const handleToggleRealLocation = () => {
    if (!realLoc.isTracking) {
      realLoc.startTracking();
      setFollowUserLocation(true);
    } else {
      realLoc.stopTracking();
      setFollowUserLocation(false);
    }
  };

  return (
    <div
      className={`relative overflow-hidden rounded-2xl border border-[#1D3552] bg-[#041022] shadow-xl ${heightClass}`}
    >
      {/* Background Grid Pattern or Fallback Backdrop */}
      <div
        className={`pointer-events-none absolute inset-0 z-[1] ${tileError ? "opacity-35" : "opacity-20"}`}
        style={{
          backgroundImage:
            "linear-gradient(to right, #1D3552 1px, transparent 1px), linear-gradient(to bottom, #1D3552 1px, transparent 1px)",
          backgroundSize: "36px 36px",
        }}
      />

      {/* RENDER ENGINE: GOOGLE MAPS OR LEAFLET */}
      {mapEngine === "google" && apiKey ? (
        <GoogleMapView
          center={activeTarget ?? BENGALURU_CENTER}
          zoom={14}
          realLocation={realLoc.position}
          realAccuracyMeters={realLoc.accuracyMeters}
          isRealLocationActive={realLoc.isTracking}
          followRealLocation={followUserLocation}
          ambulances={ambulances}
          selectedAmbulanceId={selectedAmbulance.ambulanceId}
          onSelectEmergency={(incId) => {
            setSelectedEmergencyId(incId);
            onSelectEmergency?.(incId);
          }}
          hospitals={hospitals}
          policeUnits={policeUnits}
          signals={signals}
          incidentMarkers={incidentMarkers}
          showTraffic={showTraffic}
          showRoutes={showRoutes}
          showPolice={showPolice}
          showIncidents={showIncidents}
          showSignals={showSignals}
          onMapReady={(gMap) => {
            googleMapInstanceRef.current = gMap;
          }}
          onError={() => {
            setMapEngine("leaflet");
          }}
        />
      ) : (
        <MapContainer
          center={[BENGALURU_CENTER.lat, BENGALURU_CENTER.lng]}
          zoom={14}
          zoomControl={false}
          className="h-full w-full z-0"
          style={{ background: "#041022" }}
        >
          <TileLayer
            url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
            attribution="&copy; Esri &copy; OpenStreetMap contributors"
            maxZoom={16}
            eventHandlers={{
              tileerror: () => setTileError(true),
            }}
          />

          <MapController
            zoomAction={zoomAction}
            centerTarget={activeTarget}
            focusPosition={focusPosition}
            realPosition={realLoc.position}
            followRealLocation={followUserLocation}
          />

          {/* Traffic Flow Road Overlays */}
          {showTraffic &&
            roadSegments.map((segment) => {
              const color =
                segment.density === "Smooth"
                  ? "#00D084"
                  : segment.density === "Moderate"
                    ? "#F59E0B"
                    : "#EF4444";
              return (
                <Polyline
                  key={segment.id}
                  positions={segment.coordinates.map((c): [number, number] => [c.lat, c.lng])}
                  pathOptions={{ color, weight: 4.5, opacity: 0.78 }}
                >
                  <Popup>
                    <div className="text-xs">
                      <div className="font-bold text-slate-900">{segment.name}</div>
                      <div>Traffic: {segment.density}</div>
                      <div>Avg Speed: {segment.speedKmh} km/h</div>
                    </div>
                  </Popup>
                </Polyline>
              );
            })}

          {/* Emergency Routes */}
          {showRoutes &&
            ambulances.map((amb) => {
              const isPrimary = amb.ambulanceId === selectedAmbulance.ambulanceId;
              return (
                <Polyline
                  key={`route-${amb.id}`}
                  positions={amb.routeWaypoints.map((w): [number, number] => [w.lat, w.lng])}
                  pathOptions={{
                    color: "#24A8FF",
                    weight: isPrimary ? 6 : 3.5,
                    opacity: isPrimary ? 0.95 : 0.45,
                    dashArray: isPrimary ? undefined : "6 6",
                  }}
                />
              );
            })}

          {/* Hospital Markers */}
          {hospitals.map((hosp) => (
            <Marker
              key={hosp.id}
              position={[hosp.position.lat, hosp.position.lng]}
              icon={hospitalIcons}
            >
              <Tooltip
                permanent={hosp.id === selectedAmbulance.destinationHospitalId}
                direction="right"
                offset={[12, -10]}
                className="sertos-map-tooltip"
              >
                <div className="rounded-lg border border-[#1D3552] bg-[#0A1729]/95 px-2.5 py-1 text-[11px] font-semibold text-[#F1F5F9] shadow-lg">
                  {hosp.shortName}
                </div>
              </Tooltip>
              <Popup>
                <div className="min-w-[200px] text-xs space-y-1 text-slate-800">
                  <div className="font-bold text-sm text-slate-900">{hosp.name}</div>
                  <div>
                    <span className="font-semibold">Available Beds:</span>{" "}
                    {hosp.availableBeds !== null ? `${hosp.availableBeds} (${hosp.icuBeds ?? 0} ICU)` : "Unavailable"}
                  </div>
                  <div>
                    <span className="font-semibold">Destination Status:</span> {hosp.destinationStatus}
                  </div>
                  <div>
                    <span className="font-semibold">Est. Ambulance Arrival:</span> {hosp.estimatedArrival}
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}

          {/* Ambulance Markers */}
          {ambulances.map((amb) => {
            const isSelected = amb.ambulanceId === selectedAmbulance.ambulanceId;
            return (
              <Marker
                key={amb.id}
                position={[amb.position.lat, amb.position.lng]}
                icon={createAmbulanceIcon(amb.ambulanceId, isSelected)}
                eventHandlers={{
                  click: () => {
                    setSelectedAmbulanceId(amb.ambulanceId);
                    setSelectedEmergencyId(amb.incidentId);
                    onSelectEmergency?.(amb.incidentId);
                  },
                }}
              >
                {isSelected && (
                  <Tooltip
                    permanent
                    direction="top"
                    offset={[0, -24]}
                    className="sertos-map-tooltip"
                  >
                    <div className="rounded-xl border border-[#1D3552] bg-[#0A1729]/95 px-3 py-1.5 shadow-2xl">
                      <div className="flex items-center gap-1.5 text-[12px] font-bold text-[#F1F5F9]">
                        <span className="h-2 w-2 rounded-full bg-[#20E39A]" />
                        Ambulance #{amb.ambulanceId}
                      </div>
                      <div className="text-[11px] text-[#94A3B8]">
                        ETA: {amb.etaMinutes} min • {amb.distanceKm} km
                      </div>
                    </div>
                  </Tooltip>
                )}
                <Popup>
                  <div className="min-w-[210px] text-xs space-y-1 text-slate-800">
                    <div className="font-bold text-sm text-slate-900">
                      Ambulance {amb.ambulanceId} ({amb.source === "demo" ? "DEMO" : "LIVE"})
                    </div>
                    <div><span className="font-semibold">Emergency ID:</span> {amb.incidentId}</div>
                    <div><span className="font-semibold">Speed:</span> {amb.speedKmh} km/h</div>
                    <div><span className="font-semibold">ETA:</span> {amb.etaMinutes} min ({amb.distanceKm} km)</div>
                    <div><span className="font-semibold">Status:</span> {amb.status}</div>
                    <div><span className="font-semibold">Hospital:</span> {amb.destinationHospitalName}</div>
                  </div>
                </Popup>
              </Marker>
            );
          })}

          {/* Police Unit Markers */}
          {showPolice &&
            policeUnits.map((unit) => (
              <Marker
                key={unit.id}
                position={[unit.position.lat, unit.position.lng]}
                icon={policeIcon}
              >
                <Popup>
                  <div className="text-xs space-y-1 text-slate-800">
                    <div className="font-bold text-slate-900">{unit.callSign}</div>
                    <div>{unit.officerName}</div>
                    <div>Zone: {unit.zone}</div>
                    <div>Status: {unit.status}</div>
                  </div>
                </Popup>
              </Marker>
            ))}

          {/* Incident Markers */}
          {showIncidents &&
            incidentMarkers.map((inc) => (
              <Marker
                key={inc.id}
                position={[inc.position.lat, inc.position.lng]}
                icon={incidentIcon}
              >
                <Popup>
                  <div className="text-xs space-y-1 text-slate-800">
                    <div className="font-bold text-slate-900">{inc.title}</div>
                    <div>Severity: {inc.severity}</div>
                    <div>{inc.description}</div>
                    <div className="text-slate-500">{inc.location} • {inc.reportedAt}</div>
                  </div>
                </Popup>
              </Marker>
            ))}

          {/* Real User GPS Location Marker & Accuracy Circle (Leaflet) */}
          {realLoc.isTracking && realLoc.position && (
            <>
              <Circle
                center={[realLoc.position.lat, realLoc.position.lng]}
                radius={realLoc.accuracyMeters ?? 20}
                pathOptions={{
                  color: "#24A8FF",
                  fillColor: "#24A8FF",
                  fillOpacity: 0.18,
                  weight: 1.5,
                }}
              />
              <Marker
                position={[realLoc.position.lat, realLoc.position.lng]}
                icon={realUserIcon}
              >
                <Popup>
                  <div className="text-xs space-y-1 text-slate-800">
                    <div className="font-bold text-blue-700">Your Real GPS Location</div>
                    <div>Lat: {realLoc.position.lat.toFixed(5)}</div>
                    <div>Lng: {realLoc.position.lng.toFixed(5)}</div>
                    <div>Accuracy: ±{realLoc.accuracyMeters ?? "--"} m</div>
                    {realLoc.speedKmh !== null && <div>Speed: {realLoc.speedKmh} km/h</div>}
                  </div>
                </Popup>
              </Marker>
            </>
          )}
        </MapContainer>
      )}

      {/* TOP OVERLAY: Engine Switcher, Mode Tag & Real Location Tracker */}
      <div className="pointer-events-none absolute left-3 right-3 top-3 z-[500] flex flex-wrap items-center justify-between gap-2">
        <div className="pointer-events-auto flex flex-wrap items-center gap-2">
          {/* Engine Selector: Google Maps vs Dark Vector */}
          <div className="flex items-center rounded-xl border border-[#1D3552] bg-[#061326]/90 p-1 backdrop-blur">
            <button
              type="button"
              onClick={() => {
                if (!apiKey) {
                  setShowKeyModal(true);
                } else {
                  setMapEngine("google");
                }
              }}
              className={`rounded-lg px-2.5 py-1 text-[11px] font-bold transition flex items-center gap-1.5 ${
                mapEngine === "google" && apiKey
                  ? "bg-[#24A8FF] text-[#020B18]"
                  : "text-[#94A3B8] hover:text-[#F1F5F9]"
              }`}
            >
              <span>🗺️ Google Maps</span>
              {!apiKey && (
                <span className="rounded bg-[#EF4444]/20 px-1 py-0.2 text-[9px] text-[#EF4444]">
                  Key needed
                </span>
              )}
            </button>
            <button
              type="button"
              onClick={() => setMapEngine("leaflet")}
              className={`rounded-lg px-2.5 py-1 text-[11px] font-bold transition ${
                mapEngine === "leaflet"
                  ? "bg-[#1D3552] text-[#F1F5F9]"
                  : "text-[#94A3B8] hover:text-[#F1F5F9]"
              }`}
            >
              Dark Vector
            </button>
          </div>

          {/* Real GPS Live Tracking Button */}
          <button
            type="button"
            onClick={handleToggleRealLocation}
            className={`pointer-events-auto flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-[11px] font-bold backdrop-blur transition shadow-lg ${
              realLoc.isTracking
                ? "border-[#00D084] bg-[#00D084]/20 text-[#20E39A] shadow-[#00D084]/20"
                : "border-[#1D3552] bg-[#061326]/90 text-[#94A3B8] hover:text-[#24A8FF] hover:border-[#24A8FF]/40"
            }`}
            title={realLoc.isTracking ? "Disable Real GPS tracking" : "Enable Real GPS device tracking"}
          >
            <Radio
              size={14}
              className={realLoc.isTracking ? "animate-pulse text-[#20E39A]" : "text-[#94A3B8]"}
            />
            <span>{realLoc.isTracking ? "REAL GPS: TRACKING" : "TRACK REAL LOCATION"}</span>
            {realLoc.isTracking && realLoc.accuracyMeters && (
              <span className="rounded-full bg-[#00D084]/30 px-1.5 py-0.5 text-[9px] font-semibold text-[#20E39A]">
                ±{realLoc.accuracyMeters}m
              </span>
            )}
          </button>

          {/* Follow Me Toggle (when tracking is on) */}
          {realLoc.isTracking && realLoc.position && (
            <button
              type="button"
              onClick={() => setFollowUserLocation((v) => !v)}
              className={`pointer-events-auto flex items-center gap-1 rounded-xl border px-2.5 py-1.5 text-[11px] font-semibold backdrop-blur transition ${
                followUserLocation
                  ? "border-[#24A8FF] bg-[#24A8FF]/20 text-[#24A8FF]"
                  : "border-[#1D3552] bg-[#061326]/90 text-[#94A3B8] hover:text-[#F1F5F9]"
              }`}
              title="Automatically keep map centered on your moving GPS coordinates"
            >
              <Navigation size={12} className={followUserLocation ? "text-[#24A8FF]" : ""} />
              <span>{followUserLocation ? "Following Me" : "Follow Me"}</span>
            </button>
          )}

          {/* Mode Tag */}
          <div className="hidden lg:flex items-center gap-2 rounded-xl border border-[#1D3552] bg-[#061326]/90 px-2.5 py-1.5 backdrop-blur">
            <StatusBadge
              label={authMode === "live" ? "LIVE TELEMETRY" : "DEMO ROUTE"}
              tone={authMode === "live" ? "live" : "demo"}
              pulse
            />
          </div>
        </div>

        {/* Top-Right: Layer Toggles & Google Key Settings */}
        <div className="pointer-events-auto flex flex-wrap items-center gap-1.5 rounded-xl border border-[#1D3552] bg-[#061326]/90 p-1 backdrop-blur">
          <button
            type="button"
            onClick={() => setShowTraffic((v) => !v)}
            className={`inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium transition ${
              showTraffic
                ? "bg-[#00D084]/20 text-[#20E39A] border border-[#00D084]/40"
                : "text-[#94A3B8] hover:text-[#F1F5F9]"
            }`}
          >
            <Layers size={12} />
            Traffic
          </button>
          <button
            type="button"
            onClick={() => setShowRoutes((v) => !v)}
            className={`inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium transition ${
              showRoutes
                ? "bg-[#24A8FF]/20 text-[#24A8FF] border border-[#24A8FF]/40"
                : "text-[#94A3B8] hover:text-[#F1F5F9]"
            }`}
          >
            <Route size={12} />
            Routes
          </button>
          <button
            type="button"
            onClick={() => setShowPolice((v) => !v)}
            className={`inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium transition ${
              showPolice
                ? "bg-[#24A8FF]/20 text-[#24A8FF] border border-[#24A8FF]/40"
                : "text-[#94A3B8] hover:text-[#F1F5F9]"
            }`}
          >
            <Shield size={12} />
            Police
          </button>
          <button
            type="button"
            onClick={() => setShowIncidents((v) => !v)}
            className={`inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium transition ${
              showIncidents
                ? "bg-[#F59E0B]/20 text-[#FBBF24] border border-[#F59E0B]/40"
                : "text-[#94A3B8] hover:text-[#F1F5F9]"
            }`}
          >
            <TriangleAlert size={12} />
            Incidents
          </button>
          <button
            type="button"
            onClick={() => setShowSignals((v) => !v)}
            className={`inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium transition ${
              showSignals
                ? "bg-[#00D084]/20 text-[#20E39A] border border-[#00D084]/40"
                : "text-[#94A3B8] hover:text-[#F1F5F9]"
            }`}
          >
            <Radio size={12} />
            Signals
          </button>

          {/* API Key Modal Button */}
          <button
            type="button"
            onClick={() => setShowKeyModal(true)}
            className={`inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium transition ${
              apiKey
                ? "text-[#94A3B8] hover:text-[#24A8FF]"
                : "bg-[#EF4444]/20 text-[#EF4444] border border-[#EF4444]/40 animate-pulse"
            }`}
            title="Configure Google Maps API Key"
          >
            <KeyRound size={12} />
            <span>API Key</span>
          </button>
        </div>
      </div>

      {/* Real-time GPS Error Notice if permission denied */}
      {realLoc.errorMessage && (
        <div className="pointer-events-auto absolute left-3 top-16 z-[500] max-w-sm rounded-xl border border-[#EF4444]/40 bg-[#0A1729]/95 p-3 text-xs text-[#F1F5F9] shadow-xl backdrop-blur">
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="font-bold text-[#EF4444]">GPS Notification</div>
              <div className="mt-0.5 text-[#94A3B8]">{realLoc.errorMessage}</div>
            </div>
            <button
              type="button"
              onClick={realLoc.stopTracking}
              className="text-[#94A3B8] hover:text-[#F1F5F9]"
            >
              <X size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Bottom-Left Traffic Flow / Live GPS Stats */}
      <div className="pointer-events-auto absolute bottom-3 left-3 z-[500] flex flex-col gap-2">
        {/* Real Location Live Telemetry Pill */}
        {realLoc.isTracking && realLoc.position && (
          <div className="rounded-xl border border-[#24A8FF]/40 bg-[#0A1729]/95 px-3 py-2 shadow-xl backdrop-blur">
            <div className="flex items-center gap-1.5 text-[11px] font-bold text-[#24A8FF]">
              <span className="h-2 w-2 rounded-full bg-[#20E39A] animate-ping" />
              Live Device GPS
            </div>
            <div className="mt-1 font-mono text-[10px] text-[#F1F5F9]">
              {realLoc.position.lat.toFixed(5)}° N, {realLoc.position.lng.toFixed(5)}° E
            </div>
            <div className="flex items-center gap-2 text-[10px] text-[#94A3B8]">
              <span>Acc: ±{realLoc.accuracyMeters ?? "--"}m</span>
              {realLoc.speedKmh !== null && <span>• Speed: {realLoc.speedKmh} km/h</span>}
            </div>
          </div>
        )}

        {/* Traffic Flow Legend */}
        <div className="rounded-xl border border-[#1D3552] bg-[#0A1729]/92 px-3.5 py-2.5 shadow-xl backdrop-blur">
          <div className="mb-1 text-[11px] font-semibold text-[#F1F5F9]">Traffic Flow</div>
          <div className="space-y-1 text-[10px] text-[#94A3B8]">
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-3.5 rounded-full bg-[#00D084]" />
              <span>Smooth</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-3.5 rounded-full bg-[#F59E0B]" />
              <span>Moderate</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-3.5 rounded-full bg-[#EF4444]" />
              <span>Heavy</span>
            </div>
          </div>
        </div>
      </div>

      {/* Center-Bottom City Pill */}
      <div className="pointer-events-none absolute bottom-3 left-1/2 z-[500] hidden -translate-x-1/2 sm:flex items-center gap-1.5 rounded-full border border-[#1D3552] bg-[#061326]/90 px-3 py-1 text-[11px] font-semibold text-[#F1F5F9] shadow">
        <span className="h-2 w-2 rounded-full bg-[#24A8FF]" />
        Bengaluru {mapEngine === "google" ? "• Google Maps" : "• Dark Vector"}
      </div>

      {/* Bottom-Right Map Controls */}
      <div className="pointer-events-auto absolute bottom-3 right-3 z-[500] flex flex-col overflow-hidden rounded-xl border border-[#1D3552] bg-[#0A1729]/95 shadow-xl backdrop-blur">
        <button
          type="button"
          onClick={() => triggerMapAction("in")}
          aria-label="Zoom in"
          title="Zoom in"
          className="flex h-9 w-9 items-center justify-center border-b border-[#1D3552] text-[#F1F5F9] transition hover:bg-[#0D1D32]"
        >
          <Plus size={16} />
        </button>
        <button
          type="button"
          onClick={() => triggerMapAction("out")}
          aria-label="Zoom out"
          title="Zoom out"
          className="flex h-9 w-9 items-center justify-center border-b border-[#1D3552] text-[#F1F5F9] transition hover:bg-[#0D1D32]"
        >
          <Minus size={16} />
        </button>
        {/* Recenter to User Real Location */}
        {realLoc.position && (
          <button
            type="button"
            onClick={() => triggerMapAction("locate-user")}
            aria-label="Recenter on My Real Location"
            title="Recenter on My Real Location"
            className="flex h-9 w-9 items-center justify-center border-b border-[#1D3552] text-[#20E39A] transition hover:bg-[#0D1D32]"
          >
            <MapPin size={16} />
          </button>
        )}
        <button
          type="button"
          onClick={() => triggerMapAction("locate")}
          aria-label="Locate primary ambulance"
          title="Locate primary ambulance"
          className="flex h-9 w-9 items-center justify-center border-b border-[#1D3552] text-[#24A8FF] transition hover:bg-[#0D1D32]"
        >
          <Crosshair size={16} />
        </button>
        <button
          type="button"
          onClick={() => triggerMapAction("reset")}
          aria-label="Reset map view"
          title="Reset map view"
          className="flex h-9 w-9 items-center justify-center text-[#94A3B8] transition hover:bg-[#0D1D32] hover:text-[#F1F5F9]"
        >
          <RotateCcw size={15} />
        </button>
      </div>

      {/* GOOGLE MAPS API KEY CONFIGURATION MODAL */}
      {showKeyModal && (
        <div className="absolute inset-0 z-[600] flex items-center justify-center bg-[#020B18]/85 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-[#1D3552] bg-[#0A1729] p-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#1D3552] pb-3">
              <div className="flex items-center gap-2 text-base font-bold text-[#F1F5F9]">
                <KeyRound size={18} className="text-[#24A8FF]" />
                Google Maps API Configuration
              </div>
              <button
                type="button"
                onClick={() => setShowKeyModal(false)}
                className="rounded-lg p-1 text-[#94A3B8] hover:bg-[#1D3552] hover:text-[#F1F5F9]"
              >
                <X size={16} />
              </button>
            </div>

            <div className="mt-4 space-y-3">
              <p className="text-xs text-[#94A3B8]">
                Paste your Google Maps API key below to enable real Google Maps rendering, Google live traffic, and high-accuracy route overlays.
              </p>

              <div>
                <label className="block text-[11px] font-semibold text-[#F1F5F9] mb-1">
                  Google Maps API Key
                </label>
                <input
                  type="text"
                  value={keyInput}
                  onChange={(e) => setKeyInput(e.target.value)}
                  placeholder="AIzaSy..."
                  className="w-full rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-2 text-xs font-mono text-[#F1F5F9] placeholder-[#475569] focus:border-[#24A8FF] focus:outline-none"
                />
              </div>

              <div className="rounded-xl border border-[#1D3552]/60 bg-[#061326]/60 p-2.5 text-[11px] text-[#94A3B8]">
                💡 You can also permanently configure this key in <code className="text-[#24A8FF]">frontend/.env.local</code> as:
                <pre className="mt-1 font-mono text-[10px] text-[#20E39A]">VITE_GOOGLE_MAPS_API_KEY=your_key_here</pre>
              </div>

              {keySaveMessage && (
                <div className="rounded-xl bg-[#00D084]/20 p-2 text-center text-xs font-semibold text-[#20E39A]">
                  {keySaveMessage}
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowKeyModal(false)}
                  className="rounded-xl border border-[#1D3552] px-3 py-1.5 text-xs font-semibold text-[#94A3B8] hover:bg-[#1D3552] hover:text-[#F1F5F9]"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSaveApiKey}
                  className="rounded-xl bg-[#24A8FF] px-4 py-1.5 text-xs font-bold text-[#020B18] hover:bg-[#38BDF8]"
                >
                  Save &amp; Apply
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
