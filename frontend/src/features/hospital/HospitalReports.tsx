import { useCallback } from "react";
import { Activity, BedDouble, RefreshCw, Siren } from "lucide-react";
import { api, type HospitalBed, type Incident } from "../../lib/api";
import { useLiveQuery } from "../../lib/useLiveQuery";
import "../shared/operations.css";

export default function HospitalReports() {
    const load = useCallback(async () => {
        const [incidents, beds] = await Promise.all([api.getHospitalIncidents(), api.getHospitalBeds()]);
        return { incidents, beds };
    }, []);
    const { data, loading, error, lastUpdated, refresh } = useLiveQuery(load, 15_000);
    const incidents: Incident[] = data?.incidents ?? [];
    const beds: HospitalBed[] = data?.beds ?? [];
    const inTransit = incidents.filter((incident) => incident.status === "IN_TRANSIT").length;
    const closed = incidents.filter((incident) => incident.status === "CLOSED").length;
    const available = beds.filter((bed) => bed.status === "AVAILABLE").length;

    return <div className="op-page"><header className="op-header"><div><div className="op-breadcrumb">Hospital / Reports</div><h1>Operations Report</h1><p>Summary generated from current hospital incident and bed records.</p></div><button type="button" className="op-refresh" onClick={refresh}><RefreshCw size={16} />{lastUpdated ? `Updated ${new Intl.DateTimeFormat(undefined, { timeStyle: "short" }).format(lastUpdated)}` : "Refresh"}</button></header>
        {error && <div className="op-error" role="alert">Report refresh failed: {error}</div>}
        <section className="op-report-grid"><article><Siren size={20} /><span>Assigned incidents</span><strong>{incidents.length}</strong></article><article><Activity size={20} /><span>Ambulances in transit</span><strong>{inTransit}</strong></article><article><BedDouble size={20} /><span>Available beds</span><strong>{available} / {beds.length}</strong></article><article><Activity size={20} /><span>Closed incidents</span><strong>{closed}</strong></article></section>
        <section className="op-panel"><div className="op-panel-head"><div><h2>Incident records</h2><p>Live hospital queue · refreshes every 15 seconds</p></div></div><div className="op-record-list">{incidents.slice(0, 20).map((incident) => <article className="op-record" key={incident.id}><div className="op-record-main"><span className={`op-severity ${incident.severity.toLowerCase()}`}>{incident.severity_display || incident.severity}</span><div><strong>{incident.incident_number}</strong><span>{incident.description || "Emergency response"}</span></div><span className="op-status">{incident.status_display || incident.status}</span></div><div className="op-record-meta"><span>{incident.ambulance_vehicle_number || "Ambulance unassigned"}</span><span>{incident.patient_count} patients reported</span></div></article>)}{!incidents.length && <div className="op-empty"><strong>{loading ? "Loading report…" : "No incident data available"}</strong><span>New hospital assignments will appear here.</span></div>}</div></section>
    </div>;
}
