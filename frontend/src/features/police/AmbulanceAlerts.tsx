import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Ambulance, Bell, Check, Clock3, Gauge, MapPin, Navigation, RefreshCw, Route, ShieldAlert } from "lucide-react";
import { api, type Incident, type RouteSummary } from "../../lib/api";
import { useLiveQuery } from "../../lib/useLiveQuery";
import "./traffic-police.css";

function formatTime(value: string) {
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export default function AmbulanceAlerts() {
    const [searchParams, setSearchParams] = useSearchParams();
    const { data: incidents = [], loading, error, refresh, lastUpdated } = useLiveQuery(api.getPoliceIncidents, 8_000);
    const [location, setLocation] = useState<{ latitude: string; longitude: string; recorded_at: string } | null>(null);
    const [route, setRoute] = useState<RouteSummary | null>(null);
    const [actionError, setActionError] = useState("");
    const [saving, setSaving] = useState(false);
    const activeIncidents = incidents.filter((incident) => !["CLOSED", "CANCELLED"].includes(incident.status));
    const selected: Incident | undefined = activeIncidents.find((incident) => incident.id === searchParams.get("incident")) ?? activeIncidents[0];

    useEffect(() => {
        if (!selected || selected.status !== "IN_TRANSIT") {
            setLocation(null);
            setRoute(null);
            return;
        }
        const incidentId = selected.id;
        let active = true;
        const poll = async () => {
            const [locationResult, routeResult] = await Promise.allSettled([api.getLocation(incidentId), api.getRoute(incidentId)]);
            if (!active) return;
            setLocation(locationResult.status === "fulfilled" ? locationResult.value : null);
            setRoute(routeResult.status === "fulfilled" ? routeResult.value : null);
        };
        void poll();
        const interval = window.setInterval(poll, 5_000);
        return () => { active = false; window.clearInterval(interval); };
    }, [selected?.id, selected?.status]);

    const acknowledge = async () => {
        if (!selected) return;
        setSaving(true);
        setActionError("");
        try {
            await api.acknowledgePoliceIncident(selected.id);
            refresh();
        } catch (cause: unknown) {
            setActionError(cause instanceof Error ? cause.message : "Unable to acknowledge this incident.");
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="tp-ambulance-alerts">
            <header className="tp-alerts-page-header"><div><div className="tp-alerts-breadcrumb">Traffic Police / Alerts</div><h1>Ambulance Alerts</h1><p>Review live dispatch incidents and acknowledge officer response.</p></div><div className="tp-alerts-notification"><RefreshCw size={17} />{lastUpdated ? formatTime(lastUpdated.toISOString()) : loading ? "Connecting…" : "Waiting"}<button type="button" onClick={refresh} aria-label="Refresh alerts"><Bell size={17} /></button></div></header>
            {error && <div className="tp-action-error" role="alert">Incident refresh failed: {error}</div>}
            {actionError && <div className="tp-action-error" role="alert">{actionError}</div>}
            {activeIncidents.length > 1 && <label className="tp-alert-select-label">Select incident<select value={selected?.id ?? ""} onChange={(event) => setSearchParams({ incident: event.target.value })}>{activeIncidents.map((incident) => <option key={incident.id} value={incident.id}>{incident.incident_number} · {incident.status_display || incident.status}</option>)}</select></label>}

            {selected ? <>
                <section className="tp-emergency-card"><div className="tp-emergency-top"><div className="tp-emergency-vehicle"><Ambulance size={48} strokeWidth={1.5} /></div><div className="tp-emergency-information"><h2>{selected.incident_number}</h2><p>{selected.description || "Emergency response required"}</p><div className="tp-emergency-metrics"><span>Status: <strong>{selected.status_display || selected.status}</strong></span><span className="tp-metric-divider" /><span>Severity: <strong>{selected.severity_display || selected.severity}</strong></span></div></div><span className="tp-emergency-priority"><ShieldAlert size={12} />{selected.severity_display || selected.severity}</span></div>
                    <button type="button" className={`tp-acknowledge-button ${selected.police_acknowledged ? "is-acknowledged" : ""}`} onClick={() => void acknowledge()} disabled={Boolean(selected.police_acknowledged) || saving}><Check size={17} />{saving ? "Saving…" : selected.police_acknowledged ? "Alert Acknowledged" : "Acknowledge Incident"}</button>
                    <div className="tp-emergency-route"><Route size={13} /><span>Destination: {selected.hospital_name || "Pending"} · Vehicle: {selected.ambulance_vehicle_number || "Unassigned"}</span></div>
                </section>
                <section className="tp-alert-details-card"><h3>Live Details</h3><div className="tp-alert-detail-row"><Clock3 size={14} /><span>Reported:</span><strong>{formatTime(selected.created_at)}</strong></div><div className="tp-alert-detail-row"><Gauge size={14} /><span>Vehicle speed:</span><strong>Not provided by GPS feed</strong></div><div className="tp-alert-detail-row"><MapPin size={14} /><span>Latest GPS:</span><strong>{location ? `${Number(location.latitude).toFixed(5)}, ${Number(location.longitude).toFixed(5)}` : selected.status === "IN_TRANSIT" ? "Waiting for GPS report" : "Ambulance not in transit"}</strong></div>{location && <div className="tp-alert-detail-row"><Clock3 size={14} /><span>GPS received:</span><strong>{formatTime(location.recorded_at)}</strong></div>}<div className="tp-alert-detail-row"><Navigation size={14} /><span>Route estimate:</span><strong>{route ? `${route.distance_km.toFixed(1)} km · ${route.duration_formatted}` : "Not available"}</strong></div>{location && <a className="tp-map-link" href={`https://www.google.com/maps?q=${location.latitude},${location.longitude}`} target="_blank" rel="noreferrer">Open current location in Maps</a>}</section>
            </> : <div className="tp-empty-state">{loading ? "Loading active alerts…" : "No active ambulance incidents."}</div>}
        </div>
    );
}
