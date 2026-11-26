import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, Ambulance, Bell, CheckCircle2, Clock3, GitBranch, MapPin, RefreshCw, Siren, TrendingUp } from "lucide-react";
import { api, type Incident, type Notification, type PoliceTrafficOverview } from "../../lib/api";
import { useLiveQuery } from "../../lib/useLiveQuery";

type PoliceDashboardData = { incidents: Incident[]; notifications: Notification[]; traffic: PoliceTrafficOverview };

function formatTime(value: string) {
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function isRecent(value: string | null) {
    return Boolean(value && Date.now() - Date.parse(value) < 90_000);
}

export default function PoliceDashboard() {
    const navigate = useNavigate();
    const loadDashboard = useCallback(async (): Promise<PoliceDashboardData> => {
        const [incidents, notifications, traffic] = await Promise.all([
            api.getPoliceIncidents(),
            api.getNotifications().catch(() => null),
            api.getPoliceTrafficOverview(),
        ]);
        return { incidents, notifications: notifications?.results ?? [], traffic };
    }, []);
    const { data, loading, error, lastUpdated, refresh } = useLiveQuery(loadDashboard, 8_000);
    const incidents = data?.incidents ?? [];
    const activeIncidents = incidents.filter((incident) => !["CLOSED", "CANCELLED"].includes(incident.status));
    const inTransit = activeIncidents.filter((incident) => incident.status === "IN_TRANSIT");
    const ambulanceCount = new Set(inTransit.map((incident) => incident.ambulance_vehicle_number).filter(Boolean)).size;
    const unacknowledged = activeIncidents.filter((incident) => !incident.police_acknowledged).length;
    const devices = data?.traffic.devices ?? [];
    const onlineJunctions = devices.filter((device) => device.is_active && isRecent(device.last_heartbeat_at)).length;
    const today = new Date().toDateString();
    const resolvedToday = incidents.filter((incident) => incident.status === "CLOSED" && incident.closed_at && new Date(incident.closed_at).toDateString() === today).length;
    const activity = (data?.notifications ?? []).slice(0, 4);

    return (
        <div className="tp-dashboard">
            <header className="tp-page-header"><div><div className="tp-breadcrumb">Traffic Police / Dashboard</div><h1>Operations Overview</h1><p>Live incidents, ambulance movement, and registered junction telemetry.</p></div><div className="tp-header-actions"><div className={`tp-live-indicator ${error ? "tp-api-error" : ""}`}><span />{error ? "API unavailable" : lastUpdated ? "API connected" : "Connecting"}</div><button className="tp-icon-button" type="button" onClick={refresh} aria-label="Refresh operations"><RefreshCw size={18} /></button><div className="tp-header-officer"><div className="tp-officer-avatar">TP</div><div><strong>Traffic Operations</strong><span>{lastUpdated ? `Updated ${formatTime(lastUpdated.toISOString())}` : "Awaiting backend"}</span></div></div></div></header>
            {error && <div className="tp-panel-footer tp-api-error-message" role="alert">Live refresh failed: {error}</div>}
            <section className="tp-welcome-panel"><div className="tp-welcome-icon"><Activity size={25} /></div><div><h2>Live response coordination</h2><p>Incident and controller status refresh automatically while this page is open.</p></div><div className="tp-welcome-status"><span />{loading && !data ? "Connecting" : "Polling"}</div></section>

            <section className="tp-stat-grid">
                {[{ title: "Ambulances en route", value: ambulanceCount, detail: "Unique vehicles in transit", icon: Ambulance, color: "blue" }, { title: "Unacknowledged alerts", value: unacknowledged, detail: "Require officer review", icon: Bell, color: "orange" }, { title: "Reporting junctions", value: onlineJunctions, detail: `${devices.length} registered controllers`, icon: GitBranch, color: "green" }, { title: "Incidents closed today", value: resolvedToday, detail: "Based on recorded close time", icon: CheckCircle2, color: "purple" }].map((item) => {
                    const Icon = item.icon;
                    return <article className="tp-stat-card" key={item.title}><div className={`tp-stat-icon tp-stat-${item.color}`}><Icon size={21} /></div><div className="tp-stat-content"><span>{item.title}</span><strong>{item.value.toString().padStart(2, "0")}</strong><small>{item.detail}</small></div><TrendingUp className="tp-stat-trend" size={17} /></article>;
                })}
            </section>

            <section className="tp-dashboard-grid">
                <article className="tp-card tp-alerts-panel"><div className="tp-section-header"><div><h2><Siren size={19} />Active Incidents</h2><p>Dispatch and acknowledgement status from the API</p></div><span className="tp-count-badge">{activeIncidents.length} Active</span></div>
                    <div className="tp-alert-list">{activeIncidents.slice(0, 6).map((incident) => <div className="tp-alert-row" key={incident.id}><div className="tp-alert-symbol"><Ambulance size={21} /></div><div className="tp-alert-main"><div className="tp-alert-title"><strong>{incident.incident_number}</strong><span className={incident.severity === "CRITICAL" ? "tp-priority-critical" : "tp-priority-high"}>{incident.severity_display || incident.severity}</span></div><p><MapPin size={13} />{incident.hospital_name || "Destination pending"}</p><small>{incident.ambulance_vehicle_number || "Ambulance unassigned"} · {incident.status_display || incident.status}</small></div><div className="tp-alert-meta"><strong><Clock3 size={14} />{incident.police_acknowledged ? "Acknowledged" : "Needs review"}</strong><button type="button" className="tp-view-button" onClick={() => navigate(`/police/alerts?incident=${encodeURIComponent(incident.id)}`)}>View details</button></div></div>)}{!activeIncidents.length && <div className="tp-empty-state">{loading ? "Loading incidents…" : "No active incidents are in the dispatch queue."}</div>}</div>
                    <div className="tp-panel-footer"><span>Showing {Math.min(activeIncidents.length, 6)} of {activeIncidents.length} active incidents</span><button type="button" onClick={() => navigate("/police/alerts")}>Open alerts →</button></div>
                </article>

                <article className="tp-card tp-activity-panel"><div className="tp-section-header"><div><h2><Activity size={19} />Recent Notifications</h2><p>Events delivered to this officer account</p></div></div><div className="tp-activity-list">{activity.map((item, index) => <div className="tp-activity-item" key={item.id}><div className="tp-activity-marker"><span />{index !== activity.length - 1 && <div className="tp-activity-line" />}</div><div className="tp-activity-content"><strong>{item.title}</strong><p>{item.message}</p><small>{formatTime(item.created_at)}</small></div></div>)}{!activity.length && <div className="tp-empty-state">{loading ? "Loading notifications…" : "No recent notifications."}</div>}</div><div className="tp-panel-footer"><span>Controller requests: {data?.traffic.commands.length ?? 0}</span><button type="button" onClick={() => navigate("/police/junctions")}>View junctions →</button></div></article>
            </section>
            <footer className="tp-dashboard-footer"><span>SERTOS Emergency Response System</span><span>Data refreshes every 8 seconds</span></footer>
        </div>
    );
}
