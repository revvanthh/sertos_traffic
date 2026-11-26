import { useEffect, useRef, useState } from "react";
import { importLibrary } from "@googlemaps/js-api-loader";
import { Ambulance, Clock3, MapPin, Navigation, Radio, RefreshCw, ShieldAlert, X } from "lucide-react";
import { api, type RouteSummary, type TrafficDeviceOverview } from "../../lib/api";
import "./traffic-police.css";

type AmbulanceData = {
    id: string;
    incidentId: string;
    condition: string;
    lat: number;
    lng: number;
    eta: string;
    priority: "High" | "Normal";
    destination: string;
    recordedAt: string;
    route: RouteSummary | null;
    destinationPosition: { lat: number; lng: number } | null;
};

export default function PoliceTracking() {
    const mapElementRef = useRef<HTMLDivElement>(null);
    const mapRef = useRef<google.maps.Map | null>(null);
    const markersRef = useRef<google.maps.Marker[]>([]);
    const junctionMarkersRef = useRef<google.maps.Marker[]>([]);
    const hospitalMarkersRef = useRef<google.maps.Marker[]>([]);
    const routeLineRef = useRef<google.maps.Polyline | null>(null);
    const [mapReady, setMapReady] = useState(false);
    const [mapStatus, setMapStatus] = useState("Loading map…");
    const [ambulances, setAmbulances] = useState<AmbulanceData[]>([]);
    const [junctions, setJunctions] = useState<TrafficDeviceOverview[]>([]);
    const [selected, setSelected] = useState<AmbulanceData | null>(null);
    const [apiError, setApiError] = useState("");
    const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

    useEffect(() => {
        let active = true;
        const refreshTracking = async () => {
            try {
                const [incidents, traffic] = await Promise.all([
                    api.getPoliceIncidents(),
                    api.getPoliceTrafficOverview(),
                ]);
                const inTransit = incidents.filter((incident) => incident.status === "IN_TRANSIT");
                const results = await Promise.all(inTransit.map(async (incident) => {
                    const location = await api.getLocation(incident.id).catch(() => null);
                    if (!location) return null;
                    const route: RouteSummary | null = await api.getRoute(incident.id).catch(() => null);
                    return {
                        id: incident.ambulance_vehicle_number || incident.incident_number,
                        incidentId: incident.id,
                        condition: incident.description || "Emergency response",
                        lat: Number(location.latitude),
                        lng: Number(location.longitude),
                        eta: route?.duration_formatted || "Not available",
                        priority: incident.severity === "CRITICAL" || incident.severity === "HIGH" ? "High" as const : "Normal" as const,
                        destination: incident.hospital_name || "Destination not assigned",
                        recordedAt: location.recorded_at,
                        route,
                        destinationPosition: incident.hospital?.latitude && incident.hospital.longitude
                            ? { lat: Number(incident.hospital.latitude), lng: Number(incident.hospital.longitude) }
                            : null,
                    };
                }));
                if (!active) return;
                setJunctions(traffic.devices);
                const records = results.filter((record): record is AmbulanceData => Boolean(record));
                setAmbulances(records);
                setSelected((current) => current ? records.find((record) => record.id === current.id) ?? records[0] ?? null : records[0] ?? null);
                setUpdatedAt(new Date());
                setApiError("");
            } catch (cause: unknown) {
                if (active) setApiError(cause instanceof Error ? cause.message : "Unable to load ambulance positions.");
            }
        };
        void refreshTracking();
        const interval = window.setInterval(refreshTracking, 5_000);
        return () => { active = false; window.clearInterval(interval); };
    }, []);

    useEffect(() => {
        let cancelled = false;
        const initializeMap = async () => {
            try {
                const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;
                if (!apiKey) throw new Error("Google Maps key is not configured for this build.");
                const mapsLibrary = await importLibrary("maps") as google.maps.MapsLibrary;
                await importLibrary("geometry") as google.maps.GeometryLibrary;
                if (cancelled || !mapElementRef.current) return;
                const map = new mapsLibrary.Map(mapElementRef.current, {
                    center: { lat: 0, lng: 0 },
                    zoom: 2,
                    mapTypeControl: false,
                    streetViewControl: false,
                    fullscreenControl: false,
                    clickableIcons: false,
                    gestureHandling: "greedy",
                });
                mapRef.current = map;
                setMapReady(true);
                setMapStatus("Map connected; waiting for GPS reports");
            } catch (cause: unknown) {
                if (!cancelled) setMapStatus(cause instanceof Error ? cause.message : "Unable to load map.");
            }
        };
        void initializeMap();
        return () => { cancelled = true; };
    }, []);

    useEffect(() => {
        const map = mapRef.current;
        if (!mapReady || !map) return;
        markersRef.current.forEach((marker) => marker.setMap(null));
        markersRef.current = [];
        hospitalMarkersRef.current.forEach((marker) => marker.setMap(null));
        hospitalMarkersRef.current = [];
        if (!ambulances.length) {
            setMapStatus(apiError ? "Tracking API unavailable" : "Waiting for ambulance GPS reports");
            return;
        }
        const bounds = new google.maps.LatLngBounds();
        ambulances.forEach((ambulance) => {
            const marker = new google.maps.Marker({ map, position: { lat: ambulance.lat, lng: ambulance.lng }, title: `${ambulance.id} · ${ambulance.priority} priority` });
            marker.addListener("click", () => setSelected(ambulance));
            markersRef.current.push(marker);
            bounds.extend({ lat: ambulance.lat, lng: ambulance.lng });
            if (ambulance.destinationPosition && Number.isFinite(ambulance.destinationPosition.lat) && Number.isFinite(ambulance.destinationPosition.lng)) {
                const hospitalMarker = new google.maps.Marker({ map, position: ambulance.destinationPosition, title: `Destination hospital: ${ambulance.destination}`, label: { text: "H", color: "#fff" } });
                hospitalMarkersRef.current.push(hospitalMarker);
                bounds.extend(ambulance.destinationPosition);
            }
        });
        map.fitBounds(bounds, 65);
        setMapStatus(`${ambulances.length} live GPS position${ambulances.length === 1 ? "" : "s"}`);
    }, [ambulances, mapReady, apiError]);

    useEffect(() => {
        const map = mapRef.current;
        if (!mapReady || !map) return;
        junctionMarkersRef.current.forEach((marker) => marker.setMap(null));
        junctionMarkersRef.current = [];
        const bounds = new google.maps.LatLngBounds();
        let markerCount = 0;

        junctions.forEach((junction) => {
            const position = { lat: Number(junction.latitude), lng: Number(junction.longitude) };
            if (!Number.isFinite(position.lat) || !Number.isFinite(position.lng)) return;
            const online = junction.is_active && Boolean(junction.last_heartbeat_at && Date.now() - Date.parse(junction.last_heartbeat_at) < 90_000);
            const phase = junction.latest_signal_state?.current_phase || junction.current_signal_phase;
            const marker = new google.maps.Marker({
                map,
                position,
                title: `${junction.intersection_name} · ${online ? "reporting" : "offline or stale"} · ${phase}`,
                label: { text: "J", color: "#fff" },
            });
            junctionMarkersRef.current.push(marker);
            bounds.extend(position);
            markerCount += 1;
        });

        if (!ambulances.length && markerCount) {
            map.fitBounds(bounds, 65);
            setMapStatus(`Showing ${markerCount} registered junction${markerCount === 1 ? "" : "s"}; no ambulance GPS reports`);
        }
    }, [junctions, mapReady, ambulances.length]);

    useEffect(() => {
        const map = mapRef.current;
        const polyline = selected?.route?.polyline;
        if (!mapReady || !map || !polyline || !google.maps.geometry?.encoding) {
            routeLineRef.current?.setMap(null);
            routeLineRef.current = null;
            return;
        }
        const path = google.maps.geometry.encoding.decodePath(polyline);
        if (!routeLineRef.current) {
            routeLineRef.current = new google.maps.Polyline({ map, path, strokeColor: "#dc2626", strokeOpacity: 0.9, strokeWeight: 5, geodesic: true });
        } else {
            routeLineRef.current.setPath(path);
            routeLineRef.current.setMap(map);
        }
    }, [mapReady, selected?.incidentId, selected?.route?.polyline]);

    useEffect(() => () => {
        markersRef.current.forEach((marker) => marker.setMap(null));
        markersRef.current = [];
        hospitalMarkersRef.current.forEach((marker) => marker.setMap(null));
        hospitalMarkersRef.current = [];
        junctionMarkersRef.current.forEach((marker) => marker.setMap(null));
        junctionMarkersRef.current = [];
        routeLineRef.current?.setMap(null);
        routeLineRef.current = null;
        mapRef.current = null;
    }, []);

    const focusAmbulance = (ambulance: AmbulanceData) => {
        setSelected(ambulance);
        mapRef.current?.panTo({ lat: ambulance.lat, lng: ambulance.lng });
        mapRef.current?.setZoom(16);
    };

    const showAllAmbulances = () => {
        if (!mapRef.current || !ambulances.length) return;
        const bounds = new google.maps.LatLngBounds();
        ambulances.forEach((ambulance) => bounds.extend({ lat: ambulance.lat, lng: ambulance.lng }));
        mapRef.current.fitBounds(bounds, 65);
    };

    return <div className="police-tracking-page">
        <div className="police-tracking-header"><div><h1>Live Ambulance Tracking</h1><p>Latest GPS report for each ambulance marked in transit.</p></div><div className="police-fleet-status"><span className="police-live-dot" />{apiError ? "API UNAVAILABLE" : ambulances.length ? "LIVE GPS REPORTS" : "WAITING FOR GPS"}</div></div>
        {apiError && <div className="tp-action-error" role="alert">Tracking refresh failed: {apiError}</div>}
        <section className="police-tracking-map"><div ref={mapElementRef} className="police-google-map" />{(!mapReady || !ambulances.length) && <div className="police-map-loading">{mapReady ? mapStatus : mapStatus}</div>}
            <div className="police-map-topbar"><div className="police-map-count"><Ambulance size={17} /><strong>{ambulances.length} GPS positions · {junctions.length} junctions</strong></div><button type="button" onClick={showAllAmbulances} className="police-map-control" disabled={!ambulances.length}><RefreshCw size={15} />Show all</button></div>
            <div className="police-map-legend"><span><i className="ambulance" /> Ambulance GPS</span><span><i className="hospital" /> Destination</span><span><i className="junction" /> Junction</span><span>Red line: backend route geometry</span></div>
            {selected && <div className="police-selected-panel"><div className="police-selected-header"><div><span className="police-selected-label">SELECTED AMBULANCE</span><h2>{selected.id}</h2></div><button type="button" onClick={() => setSelected(null)} aria-label="Close ambulance details"><X size={18} /></button></div><div className="police-selected-condition"><ShieldAlert size={16} />{selected.condition}</div><div className="police-selected-details"><div><span>Driver</span><strong>Not included in live incident feed</strong></div><div><span>ETA</span><strong>{selected.eta}</strong></div><div><span>GPS report</span><strong>{new Intl.DateTimeFormat(undefined, { timeStyle: "short" }).format(new Date(selected.recordedAt))}</strong></div><div><span>Priority</span><strong className={selected.priority === "High" ? "police-high-text" : "police-normal-text"}>{selected.priority}</strong></div></div><div className="police-selected-destination"><MapPin size={15} />{selected.destination} · {selected.lat.toFixed(5)}, {selected.lng.toFixed(5)}</div><button type="button" className="police-focus-button" onClick={() => focusAmbulance(selected)}><Navigation size={15} />Focus on ambulance</button></div>}
            <div className="police-map-footer"><span><Radio size={14} />{mapStatus}</span><span><Clock3 size={14} />{updatedAt ? `API refreshed ${new Intl.DateTimeFormat(undefined, { timeStyle: "short" }).format(updatedAt)}` : "Waiting for API"}</span></div>
        </section>
        <section className="police-fleet-panel"><div className="police-fleet-heading"><div><h2>Ambulances with GPS</h2><p>Choose a vehicle to focus its reported position.</p></div><span>{ambulances.length} vehicles</span></div><div className="police-fleet-list">{ambulances.map((ambulance) => <button type="button" key={ambulance.id} className={`police-fleet-item ${selected?.id === ambulance.id ? "selected" : ""}`} onClick={() => focusAmbulance(ambulance)}><div className="police-fleet-icon"><Ambulance size={21} /></div><div className="police-fleet-info"><strong>{ambulance.id}</strong><span>{ambulance.condition}</span></div><div className="police-fleet-meta"><strong>{ambulance.eta}</strong><span>{ambulance.priority} priority</span></div></button>)}{!ambulances.length && <div className="tp-empty-state">{apiError || "No ambulance GPS points have arrived for incidents in transit."}</div>}</div></section>
    </div>;
}
