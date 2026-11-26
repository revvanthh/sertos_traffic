import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, ArrowRight, Clock3, GitBranch, Radio, RefreshCw, ShieldAlert } from "lucide-react";
import { api, type Incident, type PoliceTrafficOverview } from "../../lib/api";
import { useLiveQuery } from "../../lib/useLiveQuery";
import "./traffic-police.css";

function formatTime(value: string | null) {
    if (!value) return "Never reported";
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function isRecent(value: string | null) {
    return Boolean(value && Date.now() - Date.parse(value) < 90_000);
}

export default function PoliceJunctions() {
    const navigate = useNavigate();
    const [selectedIncidentId, setSelectedIncidentId] = useState("");
    const [rechecking, setRechecking] = useState(false);
    const [resultMessage, setResultMessage] = useState("");
    const [actionError, setActionError] = useState("");
    const loadOverview = useCallback(async () => {
        const [traffic, incidents] = await Promise.all([api.getPoliceTrafficOverview(), api.getPoliceIncidents()]);
        return { ...traffic, incidents };
    }, []);
    const { data, loading, error, lastUpdated, refresh } = useLiveQuery<PoliceTrafficOverview & { incidents: Incident[] }>(loadOverview, 5_000);
    const devices = data?.devices ?? [];
    const commands = data?.commands ?? [];
    const inTransitIncidents = (data?.incidents ?? []).filter((incident) => incident.status === "IN_TRANSIT");
    const onlineCount = devices.filter((device) => device.is_active && isRecent(device.last_heartbeat_at)).length;
    const activeCommands = commands.filter((command) => ["PENDING", "ACKNOWLEDGED"].includes(command.status));

    useEffect(() => {
        if (!selectedIncidentId && inTransitIncidents[0]) setSelectedIncidentId(inTransitIncidents[0].id);
        if (selectedIncidentId && !inTransitIncidents.some((incident) => incident.id === selectedIncidentId)) {
            setSelectedIncidentId(inTransitIncidents[0]?.id ?? "");
        }
    }, [inTransitIncidents, selectedIncidentId]);

    const recheckCorridor = async () => {
        if (!selectedIncidentId) return;
        setRechecking(true);
        setActionError("");
        setResultMessage("");
        try {
            const result = await api.recheckTrafficCorridor(selectedIncidentId);
            setResultMessage(result.created_count ? `${result.created_count} new advisory command${result.created_count === 1 ? "" : "s"} created from the latest GPS report.` : "No new command matched the safe distance and movement rules. Existing active commands are not duplicated.");
            refresh();
        } catch (cause: unknown) {
            setActionError(cause instanceof Error ? cause.message : "Unable to evaluate this corridor.");
        } finally {
            setRechecking(false);
        }
    };

    return (
        <div className="tj-page">
            <header className="tj-header"><div><div className="tj-breadcrumb">Traffic Police / Junctions</div><h1>Junction Operations</h1><p>Controller telemetry and emergency corridor command status.</p></div><div className="tj-header-actions"><span><Activity size={15} />{lastUpdated ? `Updated ${formatTime(lastUpdated.toISOString())}` : loading ? "Connecting…" : "Waiting for data"}</span><button type="button" onClick={refresh} aria-label="Refresh junction data"><RefreshCw size={16} /></button></div></header>
            {error && <div className="tj-error" role="alert">Junction data refresh failed: {error}</div>}
            {actionError && <div className="tj-error" role="alert">{actionError}</div>}
            <section className="tj-stats"><article><span className="tj-icon"><GitBranch size={20} /></span><div><small>Registered junctions</small><strong>{devices.length}</strong></div></article><article><span className="tj-icon online"><Radio size={20} /></span><div><small>Reporting in last 90 sec</small><strong>{onlineCount}</strong></div></article><article><span className="tj-icon alert"><ShieldAlert size={20} /></span><div><small>Active corridor requests</small><strong>{activeCommands.length}</strong></div></article></section>

            <section className="tj-panel"><div className="tj-panel-heading"><div><h2>Registered Controllers</h2><p>Heartbeat and signal state come from registered device reports.</p></div><button type="button" onClick={() => navigate("/police/tracking")}>View ambulances <ArrowRight size={15} /></button></div>
                <div className="tj-device-list">
                    {devices.map((device) => {
                        const online = device.is_active && isRecent(device.last_heartbeat_at);
                        return <article className="tj-device" key={device.id}><div className="tj-device-main"><div className={`tj-device-indicator ${online ? "online" : "offline"}`} /><div><strong>{device.intersection_name}</strong><span>{device.name} · {device.device_id}</span></div><span className={`tj-pill ${online ? "online" : "offline"}`}>{online ? "Reporting" : device.is_active ? "No recent heartbeat" : "Inactive"}</span></div><div className="tj-device-details"><span>Signal phase<strong>{device.latest_signal_state?.current_phase || (online ? device.current_signal_phase : "Stale / unknown")}</strong></span><span>Last heartbeat<strong>{formatTime(device.last_heartbeat_at)}</strong></span><span>Latest telemetry<strong>{formatTime(device.latest_signal_state?.reported_at ?? null)}</strong></span><span>Sensors<strong>{device.sensor_1_detected == null && device.sensor_2_detected == null ? "Not reported" : `1: ${device.sensor_1_detected ? "occupied" : "clear"} · 2: ${device.sensor_2_detected ? "occupied" : "clear"}`}</strong></span></div></article>;
                    })}
                    {!devices.length && <div className="tj-empty">{loading ? "Loading controller status…" : "No traffic controllers are registered. An administrator must register a device before this screen can show junction telemetry."}</div>}
                </div>
            </section>

            <section className="tj-panel"><div className="tj-panel-heading"><div><h2>Emergency Corridor Requests</h2><p>Evaluate the latest GPS report. Commands are created only when the backend's distance, direction, and safety rules match.</p></div><span className="tj-command-count">{commands.length} recent</span></div>
                <div className="tj-recheck"><label htmlFor="tj-incident">Incident in transit<select id="tj-incident" value={selectedIncidentId} onChange={(event) => setSelectedIncidentId(event.target.value)} disabled={!inTransitIncidents.length}><option value="">{inTransitIncidents.length ? "Select an incident" : "No incident in transit"}</option>{inTransitIncidents.map((incident) => <option key={incident.id} value={incident.id}>{incident.incident_number} · {incident.ambulance_vehicle_number || "Ambulance"}</option>)}</select></label><button type="button" onClick={() => void recheckCorridor()} disabled={!selectedIncidentId || !devices.length || rechecking}>{rechecking ? "Evaluating…" : "Evaluate corridor"}</button></div>
                {resultMessage && <div className="tj-result" role="status">{resultMessage}</div>}
                <div className="tj-command-list">{commands.map((command) => <article className="tj-command" key={command.id}><div><strong>{command.action.replaceAll("_", " ")}</strong><span>{command.incident_number} · {command.device_id}</span></div><span className={`tj-pill ${command.status.toLowerCase()}`}>{command.status}</span><small><Clock3 size={14} /> Requested {formatTime(command.created_at)} · Expires {formatTime(command.expires_at)}</small>{command.failure_reason && <p className="tj-command-failure">{command.failure_reason}</p>}{command.execution_notes && <p>{command.execution_notes}</p>}</article>)}{!commands.length && <div className="tj-empty">{loading ? "Loading corridor requests…" : "No corridor requests have been created yet. A registered controller and an active ambulance GPS route are required."}</div>}</div>
            </section>
            <aside className="tj-safety-note"><ShieldAlert size={18} /><div><strong>Supervised bench demonstration</strong><p>Authenticated commands drive only low-voltage indicator LEDs on the ESP32 prototype. This is not a certified traffic controller and must never connect to public-road traffic signals. IR sensors detect obstacles and do not identify ambulances.</p></div></aside>
        </div>
    );
}
