import { useCallback } from "react";
import { Ambulance, Clock3, MapPin, RefreshCw, Route } from "lucide-react";
import { api, type Incident, type RouteSummary } from "../../lib/api";
import { useLiveQuery } from "../../lib/useLiveQuery";
import "./hospital.css";

type TrackedAmbulance = {
    incident: Incident;
    location: { latitude: string; longitude: string; recorded_at: string } | null;
    route: RouteSummary | null;
};

function formatTime(value: string) {
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export default function HospitalTracking() {
    const loadTracking = useCallback(async () => {
        const incidents = await api.getHospitalIncidents();
        const enRoute = incidents.filter((incident) => incident.status === "IN_TRANSIT");
        return Promise.all(enRoute.map(async (incident): Promise<TrackedAmbulance> => {
            const location = await api.getLocation(incident.id).catch(() => null);
            const route = location ? await api.getRoute(incident.id).catch(() => null) : null;
            return { incident, location, route };
        }));
    }, []);
    const { data = [], loading, error, lastUpdated, refresh } = useLiveQuery(loadTracking, 5_000);

    return (
        <div className="hd-dashboard hb-page">
            <div className="hd-page-heading">
                <div>
                    <div className="hd-breadcrumb">Hospital / Ambulance Tracking</div>
                    <h1>Ambulance Tracking</h1>
                    <p>Latest driver GPS reports and route estimates for your assigned incidents.</p>
                </div>
                <div className="hb-heading-actions"><span className="hb-updated"><Clock3 size={15} />{lastUpdated ? `Updated ${formatTime(lastUpdated.toISOString())}` : loading ? "Connecting…" : "Waiting for data"}</span><button className="hb-primary-button" type="button" onClick={refresh}><RefreshCw size={16} /> Refresh</button></div>
            </div>

            {error && <div className="hd-live-error" role="alert">Tracking refresh failed: {error}</div>}
            <section className="hb-panel">
                <div className="hb-panel-heading"><div><h2>Ambulances en route</h2><p>Position refreshes every 5 seconds while this page is open.</p></div><span className="hb-count">{data.length} in transit</span></div>
                {data.length ? <div className="ht-tracking-list">
                    {data.map(({ incident, location, route }) => <article className="ht-tracking-card" key={incident.id}>
                        <div className="ht-tracking-title"><span className="ht-tracking-icon"><Ambulance size={21} /></span><div><strong>{incident.ambulance_vehicle_number || "Ambulance not assigned"}</strong><span>{incident.incident_number} · {incident.severity_display || incident.severity}</span></div><span className="ht-status">{incident.status_display || incident.status}</span></div>
                        <div className="ht-tracking-details"><div><span><MapPin size={15} /> Latest GPS</span>{location ? <><strong>{Number(location.latitude).toFixed(5)}, {Number(location.longitude).toFixed(5)}</strong><small>Received {formatTime(location.recorded_at)}</small><a href={`https://www.google.com/maps?q=${location.latitude},${location.longitude}`} target="_blank" rel="noreferrer">Open location in Maps</a></> : <strong className="ht-muted">Waiting for first driver GPS update</strong>}</div><div><span><Route size={15} /> Route to hospital</span><strong>{route ? `${route.distance_km.toFixed(1)} km · ${route.duration_formatted}` : "Route estimate unavailable"}</strong>{route && <small>Estimated arrival {formatTime(route.estimated_arrival)}</small>}<small>{incident.hospital_name || "Assigned hospital"}</small></div></div>
                    </article>)}
                </div> : <div className="hd-live-empty">{loading ? "Loading live ambulance data…" : "No assigned incidents are currently marked in transit."}</div>}
            </section>
        </div>
    );
}
