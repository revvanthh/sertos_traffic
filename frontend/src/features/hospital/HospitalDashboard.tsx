import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
    Activity,
    Ambulance,
    ArrowRight,
    BedDouble,
    CheckCircle2,
    Clock3,
    MapPin,
    RefreshCw,
    Siren,
} from "lucide-react";
import { api, type HospitalBed, type Incident, type Notification, type RouteSummary } from "../../lib/api";
import { useLiveQuery } from "../../lib/useLiveQuery";
import "./hospital.css";

type HospitalDashboardData = {
    incidents: Incident[];
    beds: HospitalBed[];
    notifications: Notification[];
};

function formatTime(value?: string | null) {
    if (!value) return "Not recorded";
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function averageArrivalMinutes(incidents: Incident[]) {
    const values = incidents.flatMap((incident) => {
        if (!incident.arrived_at) return [];
        const minutes = (Date.parse(incident.arrived_at) - Date.parse(incident.created_at)) / 60_000;
        return Number.isFinite(minutes) && minutes >= 0 ? [minutes] : [];
    });
    return values.length ? (values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(1) : null;
}

export default function HospitalDashboard() {
    const navigate = useNavigate();
    const [tracking, setTracking] = useState<{ incidentId: string; latitude: string; longitude: string; route: RouteSummary | null } | null>(null);
    const loadDashboard = useCallback(async (): Promise<HospitalDashboardData> => {
        const [incidents, beds, notificationPage] = await Promise.all([
            api.getHospitalIncidents(),
            api.getHospitalBeds(),
            api.getNotifications().catch(() => null),
        ]);
        return { incidents, beds, notifications: notificationPage?.results ?? [] };
    }, []);
    const { data, loading, error, lastUpdated, refresh } = useLiveQuery(loadDashboard, 10_000);

    const incidents = data?.incidents ?? [];
    const beds = data?.beds ?? [];
    const activeIncidents = incidents.filter((incident) => !["CLOSED", "CANCELLED"].includes(incident.status));
    const latestIncident = activeIncidents[0];
    const inTransitIncident = activeIncidents.find((incident) => incident.status === "IN_TRANSIT");
    const availableBeds = beds.filter((bed) => bed.status === "AVAILABLE").length;
    const occupiedBeds = beds.filter((bed) => bed.status === "OCCUPIED").length;
    const reservedBeds = beds.filter((bed) => bed.status === "RESERVED").length;
    const availablePercent = beds.length ? Math.round((availableBeds / beds.length) * 100) : 0;
    const assignedAmbulances = new Set(activeIncidents
        .filter((incident) => incident.status === "IN_TRANSIT" && incident.ambulance_vehicle_number)
        .map((incident) => incident.ambulance_vehicle_number)).size;
    const avgArrival = averageArrivalMinutes(incidents);

    useEffect(() => {
        let active = true;
        if (!inTransitIncident) {
            setTracking(null);
            return () => { active = false; };
        }

        const incidentId = inTransitIncident.id;
        const pollLocation = async () => {
            const [locationResult, routeResult] = await Promise.allSettled([
                api.getLocation(incidentId),
                api.getRoute(incidentId),
            ]);
            if (!active) return;
            const location = locationResult.status === "fulfilled" ? locationResult.value : null;
            const route = routeResult.status === "fulfilled" ? routeResult.value : null;
            setTracking(location ? { incidentId, latitude: location.latitude, longitude: location.longitude, route } : null);
        };

        void pollLocation();
        const interval = window.setInterval(pollLocation, 5_000);
        return () => {
            active = false;
            window.clearInterval(interval);
        };
    }, [inTransitIncident?.id]);

    const openAlert = () => {
        if (latestIncident) navigate(`/hospital/alerts?incident=${encodeURIComponent(latestIncident.id)}`);
        else navigate("/hospital/alerts");
    };

    return (
        <div className="hd-dashboard">
            <div className="hd-page-header">
                <div>
                    <div className="hd-breadcrumb">Hospital Operations <span>/</span> Dashboard</div>
                    <h1>Hospital Dashboard</h1>
                    <p>Live incident queue, bed capacity, and ambulance arrivals.</p>
                </div>
                <div className="hd-date">
                    <Activity size={17} />
                    {loading && !data ? "Connecting to SERTOS…" : `Updated ${formatTime(lastUpdated?.toISOString())}`}
                    <button type="button" className="hd-refresh-button" onClick={refresh} aria-label="Refresh hospital data">
                        <RefreshCw size={15} />
                    </button>
                </div>
            </div>

            {error && <div className="hd-live-error" role="alert">Live data refresh failed: {error}</div>}

            <section className="hd-stats-grid">
                <article className="hd-stat-card"><div className="hd-stat-icon red"><Siren size={23} /></div><div><p>Active Emergencies</p><h2>{activeIncidents.length.toString().padStart(2, "0")}</h2><span className="hd-stat-note red-text">From hospital incident queue</span></div></article>
                <article className="hd-stat-card"><div className="hd-stat-icon green"><BedDouble size={23} /></div><div><p>Available Beds</p><h2>{availableBeds} <small>/ {beds.length}</small></h2><span className="hd-stat-note green-text">{beds.length ? `${availablePercent}% of registered beds` : "No beds registered"}</span></div></article>
                <article className="hd-stat-card"><div className="hd-stat-icon blue"><Ambulance size={23} /></div><div><p>Ambulances En Route</p><h2>{assignedAmbulances.toString().padStart(2, "0")}</h2><span className="hd-stat-note blue-text">Incidents marked in transit</span></div></article>
                <article className="hd-stat-card"><div className="hd-stat-icon purple"><Clock3 size={23} /></div><div><p>Average Arrival</p><h2>{avgArrival ? <>{avgArrival} <small>min</small></> : "—"}</h2><span className="hd-stat-note purple-text">Based on recorded arrivals</span></div></article>
            </section>

            <section className="hd-main-grid">
                <article className="hd-panel hd-emergency-panel">
                    <div className="hd-panel-header emergency-header"><div><Siren size={20} /><h3>Latest Emergency</h3></div>
                        {latestIncident && <span className="hd-priority-badge"><span />{latestIncident.severity_display || latestIncident.severity}</span>}
                    </div>
                    <div className="hd-emergency-body">
                        {latestIncident ? <>
                            <div className="hd-patient-row">
                                <div className="hd-patient-avatar"><Ambulance size={30} /></div>
                                <div className="hd-patient-details">
                                    <h3>{latestIncident.incident_number}</h3>
                                    <p>Status: <strong>{latestIncident.status_display || latestIncident.status}</strong></p>
                                    <p>Patients reported: <strong>{latestIncident.patient_count}</strong></p>
                                    <p>Condition: <strong className="hd-condition">{latestIncident.description || "No description supplied"}</strong></p>
                                </div>
                                <div className="hd-ambulance-info"><span>Ambulance</span><strong>{latestIncident.ambulance_vehicle_number || "Not assigned"}</strong><span className="hd-eta-label">Hospital</span><strong>{latestIncident.hospital_name || "Assigned facility"}</strong></div>
                            </div>
                            <div className="hd-emergency-actions">
                                {latestIncident.hospital_decision == null && <button className="hd-confirm-button" type="button" onClick={openAlert}><CheckCircle2 size={18} /> Review & Respond</button>}
                                <button className="hd-reject-button" type="button" onClick={openAlert}>Open incident <ArrowRight size={16} /></button>
                            </div>
                        </> : <div className="hd-live-empty">{loading ? "Loading assigned incidents…" : "No active emergencies are assigned to this hospital."}</div>}
                    </div>
                </article>

                <article className="hd-panel hd-tracking-panel">
                    <div className="hd-panel-header"><div><MapPin size={20} /><h3>Ambulance Tracking</h3></div><span className="hd-live-badge"><span />{tracking ? "GPS received" : "Waiting for GPS"}</span></div>
                    <div className="hd-live-map-data">
                        {inTransitIncident ? <>
                            <strong>{inTransitIncident.ambulance_vehicle_number || inTransitIncident.incident_number}</strong>
                            <span>Incident {inTransitIncident.incident_number}</span>
                            {tracking ? <><span>GPS: {Number(tracking.latitude).toFixed(5)}, {Number(tracking.longitude).toFixed(5)}</span><span>ETA: {tracking.route?.duration_formatted || "Route unavailable"} · Distance: {tracking.route ? `${tracking.route.distance_km.toFixed(1)} km` : "Not available"}</span><a href={`https://www.google.com/maps?q=${tracking.latitude},${tracking.longitude}`} target="_blank" rel="noreferrer">Open current location in Maps</a></> : <span>No GPS point received for this ambulance yet.</span>}
                        </> : <span>No active ambulance is marked in transit.</span>}
                    </div>
                    <div className="hd-tracking-footer"><span>Position refreshes every 5 seconds</span><button type="button" onClick={() => navigate("/hospital/tracking")}>View tracking <ArrowRight size={15} /></button></div>
                </article>
            </section>

            <section className="hd-bottom-grid">
                <article className="hd-panel hd-bed-panel">
                    <div className="hd-panel-header"><div><BedDouble size={20} /><h3>Bed Availability</h3></div><button className="hd-view-all" type="button" onClick={() => navigate("/hospital/beds")}>Manage beds <ArrowRight size={15} /></button></div>
                    <div className="hd-bed-content">
                        <div className="hd-bed-chart"><div className="hd-donut" style={{ background: `conic-gradient(#16a05a 0% ${availablePercent}%, #dce7f3 ${availablePercent}% 100%)` }}><div><strong>{beds.length ? `${availablePercent}%` : "—"}</strong><span>Available</span></div></div></div>
                        <div className="hd-bed-legend"><div><span className="green-dot" />Available<strong>{availableBeds}</strong></div><div><span className="blue-dot" />Occupied<strong>{occupiedBeds}</strong></div><div><span className="orange-dot" />Reserved<strong>{reservedBeds}</strong></div></div>
                    </div>
                </article>

                <article className="hd-panel hd-activity-panel">
                    <div className="hd-panel-header"><div><Activity size={20} /><h3>Recent Notifications</h3></div><button className="hd-view-all" type="button" onClick={() => navigate("/hospital/alerts")}>Open alerts <ArrowRight size={15} /></button></div>
                    <div className="hd-activity-list">
                        {(data?.notifications ?? []).slice(0, 5).map((notification) => <div className="hd-activity-item" key={notification.id}><div className="hd-activity-dot info" /><span className="hd-activity-time">{formatTime(notification.created_at)}</span><div><strong>{notification.title}</strong><p>{notification.message}</p></div></div>)}
                        {!loading && !data?.notifications.length && <div className="hd-live-empty">No recent notifications.</div>}
                    </div>
                </article>
            </section>
        </div>
    );
}
