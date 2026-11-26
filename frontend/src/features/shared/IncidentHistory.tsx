import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, ArrowRight, Clock3, RefreshCw } from "lucide-react";
import { api } from "../../lib/api";
import { useLiveQuery } from "../../lib/useLiveQuery";
import "./operations.css";

type Props = { role: "hospital" | "police" };

function formatTime(value?: string | null) {
    if (!value) return "Not recorded";
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export default function IncidentHistory({ role }: Props) {
    const navigate = useNavigate();
    const [search, setSearch] = useState("");
    const load = useCallback(() => role === "hospital" ? api.getHospitalIncidents() : api.getPoliceIncidents(), [role]);
    const { data: incidents = [], loading, error, lastUpdated, refresh } = useLiveQuery(load, 15_000);
    const history = incidents.filter((incident) => ["CLOSED", "CANCELLED"].includes(incident.status))
        .filter((incident) => `${incident.incident_number} ${incident.description} ${incident.hospital_name ?? ""}`.toLowerCase().includes(search.toLowerCase()));

    return <div className="op-page"><header className="op-header"><div><div className="op-breadcrumb">{role === "hospital" ? "Hospital" : "Traffic Police"} / History</div><h1>Incident History</h1><p>Closed and cancelled incidents from the live dispatch database.</p></div><button type="button" className="op-refresh" onClick={refresh}><RefreshCw size={16} /> Refresh{lastUpdated ? ` · ${formatTime(lastUpdated.toISOString())}` : ""}</button></header>
        {error && <div className="op-error" role="alert">History refresh failed: {error}</div>}
        <section className="op-panel"><div className="op-panel-head"><div><h2>Resolved incidents</h2><p>{history.length} records</p></div><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search incident or hospital" aria-label="Search incident history" /></div>
            <div className="op-record-list">{history.map((incident) => <article className="op-record" key={incident.id}><div className="op-record-main"><span className={`op-severity ${incident.severity.toLowerCase()}`}>{incident.severity_display || incident.severity}</span><div><strong>{incident.incident_number}</strong><span>{incident.description || "Emergency response"}</span></div><span className="op-status">{incident.status_display || incident.status}</span></div><div className="op-record-meta"><span><Clock3 size={14} /> Reported {formatTime(incident.created_at)}</span><span>{role === "hospital" ? incident.ambulance_vehicle_number || "Ambulance not assigned" : incident.hospital_name || "Destination not recorded"}</span><button type="button" onClick={() => navigate(role === "hospital" ? `/hospital/alerts?incident=${incident.id}` : `/police/alerts?incident=${incident.id}`)}>Review record <ArrowRight size={14} /></button></div></article>)}
                {!history.length && <div className="op-empty"><Activity size={22} /><strong>{loading ? "Loading history…" : "No matching historical incidents"}</strong><span>Records appear here after an incident is closed or cancelled.</span></div>}</div>
        </section>
    </div>;
}
