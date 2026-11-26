import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
    Activity,
    Ambulance,
    Building2,
    Cpu,
    LogOut,
    RefreshCw,
    ShieldCheck,
    Users,
} from "lucide-react";
import { api, type AdminOverview as DirectoryData, type Incident, type Hospital, type TrafficDeviceRecord } from "../../lib/api";
import { clearSession, getSession } from "../../lib/auth";
import { useLiveQuery } from "../../lib/useLiveQuery";
import "../hospital/hospital.css";
import "./admin.css";

type AdminOverview = {
    incidents: Incident[];
    hospitals: Hospital[];
    devices: TrafficDeviceRecord[];
    directory: DirectoryData | null;
    directoryError: string;
};

function isRecentlyReporting(device: TrafficDeviceRecord, now: number) {
    if (!device.is_active || !device.last_heartbeat_at) return false;
    const age = now - Date.parse(device.last_heartbeat_at);
    return Number.isFinite(age) && age >= 0 && age < 90_000;
}

function formatDate(value: string) {
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
}

export default function AdminDashboard() {
    const navigate = useNavigate();
    const loadOverview = useCallback(async (): Promise<AdminOverview> => {
        const [incidents, hospitals, devices, directoryResult] = await Promise.all([
            api.getDriverIncidents(),
            api.getHospitals(),
            api.getTrafficDevices(),
            api.getAdminOverview()
                .then((directory) => ({ directory, error: "" }))
                .catch((reason: unknown) => ({
                    directory: null,
                    error: reason instanceof Error ? reason.message : "Administrator directory is unavailable.",
                })),
        ]);
        return {
            incidents,
            hospitals,
            devices,
            directory: directoryResult.directory,
            directoryError: directoryResult.error,
        };
    }, []);
    const { data, loading, error, lastUpdated, refresh } = useLiveQuery(loadOverview, 10_000);
    const [actionError, setActionError] = useState("");
    const [verifyingUser, setVerifyingUser] = useState<number | null>(null);

    const incidents = data?.incidents ?? [];
    const activeIncidents = incidents.filter((incident) => !["CLOSED", "CANCELLED"].includes(incident.status));
    const inTransitAmbulances = new Set(
        incidents
            .filter((incident) => incident.status === "IN_TRANSIT")
            .map((incident) => incident.ambulance_vehicle_number || incident.ambulance?.vehicle_number)
            .filter((vehicle): vehicle is string => Boolean(vehicle)),
    ).size;
    const now = lastUpdated?.getTime() ?? 0;
    const reportingDevices = (data?.devices ?? []).filter((device) => isRecentlyReporting(device, now)).length;
    const personnel = data?.directory?.users ?? [];
    const ambulances = data?.directory?.ambulances ?? [];

    const logout = async () => {
        const refreshToken = getSession()?.refresh;
        if (refreshToken) {
            try {
                await api.logout(refreshToken);
            } catch {
                // Local cleanup remains effective if the API is unavailable.
            }
        }
        clearSession();
        navigate("/", { replace: true });
    };

    const verifyUser = async (userId: number) => {
        setVerifyingUser(userId);
        setActionError("");
        try {
            await api.setUserVerification(userId, true);
            refresh();
        } catch (reason: unknown) {
            setActionError(reason instanceof Error ? reason.message : "Unable to verify this account.");
        } finally {
            setVerifyingUser(null);
        }
    };

    const cards = [
        { label: "Active Emergencies", value: activeIncidents.length, icon: Activity },
        { label: "Ambulances En Route", value: inTransitAmbulances, icon: Ambulance },
        { label: "Registered Personnel", value: data?.directory?.summary.registered_users ?? "—", icon: Users },
        { label: "Active Hospitals", value: data?.directory?.summary.active_hospitals ?? data?.hospitals.length ?? "—", icon: Building2 },
        { label: "Controllers Reporting", value: `${reportingDevices} / ${data?.devices.length ?? "—"}`, icon: Cpu },
    ];

    return (
        <main className="hd-dashboard ad-dashboard">
            <div className="hd-page-header">
                <div>
                    <div className="hd-breadcrumb">SERTOS / Administrator</div>
                    <h1>System Overview</h1>
                    <p>Live emergency, personnel, fleet, hospital, and controller records.</p>
                </div>
                <div className="ad-header-actions">
                    <span>{lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : loading ? "Connecting…" : "Not connected"}</span>
                    <button type="button" className="hb-primary-button" onClick={refresh}><RefreshCw size={16} /> Refresh</button>
                    <button type="button" className="hb-primary-button ad-logout" onClick={() => void logout()}><LogOut size={16} /> Logout</button>
                </div>
            </div>

            {error && <div className="hb-demo-note" role="alert">Live data refresh failed: {error}</div>}
            {actionError && <div className="hb-demo-note" role="alert">Account update failed: {actionError}</div>}
            {data?.directoryError && <div className="hb-demo-note" role="status">Personnel and ambulance records are not exposed by the connected API ({data.directoryError}). The workspace backend includes the protected administrator overview endpoint; deploy that backend change to enable this panel on the hosted service.</div>}

            <section className="hd-stats-grid">
                {cards.map(({ label, value, icon: Icon }) => (
                    <article className="hd-stat-card" key={label}>
                        <div className="hd-stat-icon blue"><Icon size={23} /></div>
                        <div><p>{label}</p><h2>{value}</h2></div>
                    </article>
                ))}
            </section>

            <section className="hd-panel">
                <div className="hd-panel-header">
                    <div><ShieldCheck size={20} /><h3>Active Emergency Operations</h3></div>
                    <button type="button" className="ad-device-link" onClick={() => navigate("/admin/traffic-devices")}><Cpu size={16} /> Manage traffic controllers</button>
                </div>
                <div className="hd-activity-list">
                    {activeIncidents.length === 0 ? (
                        <div className="hb-empty"><Activity size={25} /><strong>{loading ? "Loading operations…" : "No active emergencies"}</strong><span>New incidents will appear here when reported.</span></div>
                    ) : activeIncidents.map((incident) => (
                        <div className="hd-activity-item" key={incident.id}>
                            <div className="hd-activity-dot danger" />
                            <div><strong>{incident.incident_number}</strong><p>{incident.ambulance_vehicle_number || incident.ambulance?.vehicle_number || "Ambulance unassigned"} · {incident.hospital_name || incident.hospital?.name || "Hospital pending"} · {incident.status_display || incident.status}</p></div>
                        </div>
                    ))}
                </div>
            </section>

            <section className="ad-operations-grid">
                <article className="hd-panel ad-personnel-panel">
                    <div className="hd-panel-header"><div><Users size={20} /><h3>Registered Personnel</h3></div><span>{data?.directory?.summary.pending_verification ?? "—"} awaiting verification</span></div>
                    <div className="ad-table-wrap">
                        <table className="ad-table">
                            <thead><tr><th>Account</th><th>Role</th><th>Status</th><th>Joined</th><th>Review</th></tr></thead>
                            <tbody>{personnel.map((person) => <tr key={person.id}><td><strong>{person.first_name || person.last_name ? `${person.first_name} ${person.last_name}`.trim() : person.username}</strong><small>{person.email || person.username}</small></td><td>{person.role.replaceAll("_", " ")}</td><td><span className={`ad-user-status ${person.is_active && person.is_verified ? "verified" : "pending"}`}>{!person.is_active ? "Inactive" : person.is_verified ? "Verified" : "Pending review"}</span></td><td>{formatDate(person.date_joined)}</td><td>{person.is_active && !person.is_verified && <button type="button" className="ad-verify-button" disabled={verifyingUser === person.id} onClick={() => void verifyUser(person.id)}>{verifyingUser === person.id ? "Saving…" : "Verify"}</button>}</td></tr>)}</tbody>
                        </table>
                        {!personnel.length && <div className="hb-empty"><Users size={22} /><strong>{loading ? "Loading personnel…" : "No user records available"}</strong><span>{data?.directoryError || "Registered personnel will appear here."}</span></div>}
                    </div>
                </article>

                <article className="hd-panel ad-fleet-panel">
                    <div className="hd-panel-header"><div><Ambulance size={20} /><h3>Ambulance Fleet</h3></div><span>{data?.directory?.summary.active_ambulances ?? "—"} active</span></div>
                    <div className="ad-fleet-list">
                        {ambulances.map((vehicle) => <div className="ad-fleet-row" key={vehicle.id}><span className={`ad-fleet-dot ${vehicle.is_active ? vehicle.is_available ? "available" : "busy" : "inactive"}`} /><div><strong>{vehicle.vehicle_number}</strong><small>{vehicle.vehicle_type} · {vehicle.assigned_driver || "No driver assigned"}</small></div><span>{!vehicle.is_active ? "Inactive" : vehicle.is_available ? "Available" : "Unavailable"}</span></div>)}
                        {!ambulances.length && <div className="hb-empty"><Ambulance size={22} /><strong>{loading ? "Loading fleet…" : "No ambulance records available"}</strong><span>{data?.directoryError || "Fleet records will appear here when registered."}</span></div>}
                    </div>
                </article>
            </section>

            <section className="hd-panel ad-command-panel">
                <div className="hd-panel-header"><div><Cpu size={20} /><h3>Traffic Command History</h3></div><span>{data?.directory?.commands.length ?? "—"} recent records</span></div>
                <div className="ad-command-list">
                    {(data?.directory?.commands ?? []).map((command) => <article className="ad-command-row" key={command.id}><div><strong>{command.action.replaceAll("_", " ")}</strong><small>{command.incident_number} · {command.device_id} · {formatDate(command.created_at)}</small>{command.failure_reason && <small className="ad-command-failure">{command.failure_reason}</small>}</div><span className={`ad-command-status ${command.status.toLowerCase()}`}>{command.status}</span></article>)}
                    {!data?.directory?.commands.length && <div className="hb-empty"><Cpu size={22} /><strong>{loading ? "Loading command history…" : "No command records available"}</strong><span>Commands appear here when the backend creates them for a corridor.</span></div>}
                </div>
            </section>
        </main>
    );
}
