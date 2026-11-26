import { useCallback, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Clipboard, Cpu, Power, RefreshCw, Router, ShieldAlert } from "lucide-react";
import { api, type TrafficDeviceRecord, type TrafficDeviceRegistration } from "../../lib/api";
import { useLiveQuery } from "../../lib/useLiveQuery";
import "../shared/operations.css";

function formatTime(value: string | null) {
    if (!value) return "Never reported";
    const timestamp = Date.parse(value);
    if (!Number.isFinite(timestamp)) return "Invalid timestamp";
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(timestamp));
}

function isRecent(value: string | null) {
    if (!value) return false;
    const age = Date.now() - Date.parse(value);
    return Number.isFinite(age) && age >= 0 && age < 90_000;
}

export default function TrafficDeviceManagement() {
    const navigate = useNavigate();
    const loadDevices = useCallback(() => api.getTrafficDevices(), []);
    const { data: devices = [], loading, error, lastUpdated, refresh } = useLiveQuery<TrafficDeviceRecord[]>(loadDevices, 15_000);
    const [form, setForm] = useState({ device_id: "", name: "", intersection_name: "", latitude: "", longitude: "" });
    const [saving, setSaving] = useState(false);
    const [savingDevice, setSavingDevice] = useState<string | null>(null);
    const [actionError, setActionError] = useState("");
    const [newDevice, setNewDevice] = useState<TrafficDeviceRegistration | null>(null);
    const [copied, setCopied] = useState(false);

    const register = async (event: FormEvent) => {
        event.preventDefault();
        setSaving(true);
        setActionError("");
        setNewDevice(null);
        try {
            const created = await api.registerTrafficDevice({
                device_id: form.device_id.trim(),
                name: form.name.trim(),
                intersection_name: form.intersection_name.trim(),
                latitude: Number(form.latitude),
                longitude: Number(form.longitude),
            });
            setNewDevice(created);
            setForm({ device_id: "", name: "", intersection_name: "", latitude: "", longitude: "" });
            refresh();
        } catch (cause: unknown) {
            setActionError(cause instanceof Error ? cause.message : "Unable to register this controller.");
        } finally {
            setSaving(false);
        }
    };

    const copyToken = async () => {
        if (!newDevice) return;
        try {
            await navigator.clipboard.writeText(newDevice.raw_token);
            setCopied(true);
        } catch {
            setActionError("Clipboard access was blocked. Copy the token from the one-time field before closing this notice.");
        }
    };

    const toggleDevice = async (device: TrafficDeviceRecord) => {
        const nextActive = !device.is_active;
        const verb = nextActive ? "activate" : "deactivate";
        if (!window.confirm(`Do you want to ${verb} ${device.device_id}?`)) return;
        setSavingDevice(device.device_id);
        setActionError("");
        try {
            await api.updateTrafficDevice(device.device_id, { is_active: nextActive });
            refresh();
        } catch (cause: unknown) {
            setActionError(cause instanceof Error ? cause.message : `Unable to ${verb} this controller.`);
        } finally {
            setSavingDevice(null);
        }
    };

    return <div className="op-page td-page">
        <header className="op-header">
            <div><div className="op-breadcrumb">Administrator / Traffic Controllers</div><h1>Traffic Controllers</h1><p>Register ESP32 devices and inspect their reported health and telemetry.</p></div>
            <div className="td-header-actions"><button type="button" className="op-refresh" onClick={() => navigate("/admin")}><ArrowLeft size={16} /> Overview</button><button type="button" className="op-refresh" onClick={refresh}><RefreshCw size={16} />{lastUpdated ? `Updated ${formatTime(lastUpdated.toISOString())}` : "Refresh"}</button></div>
        </header>

        {error && <div className="op-error" role="alert">Controller list refresh failed: {error}</div>}
        {actionError && <div className="op-error" role="alert">{actionError}</div>}

        <section className="op-panel">
            <div className="op-panel-head"><div><h2>Register a controller</h2><p>Registration returns a device token once. Keep it private and load it into the firmware secrets file.</p></div></div>
            <form className="td-form" onSubmit={(event) => void register(event)}>
                <label>Device ID<input required value={form.device_id} onChange={(event) => setForm({ ...form, device_id: event.target.value })} placeholder="ESP32-CITY-JNC-01" /></label>
                <label>Controller name<input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="North junction controller" /></label>
                <label>Intersection<input required value={form.intersection_name} onChange={(event) => setForm({ ...form, intersection_name: event.target.value })} placeholder="Main Road & 2nd Street" /></label>
                <label>Latitude<input required type="number" min="-90" max="90" step="any" value={form.latitude} onChange={(event) => setForm({ ...form, latitude: event.target.value })} /></label>
                <label>Longitude<input required type="number" min="-180" max="180" step="any" value={form.longitude} onChange={(event) => setForm({ ...form, longitude: event.target.value })} /></label>
                <button type="submit" disabled={saving}>{saving ? "Registering…" : "Register controller"}</button>
            </form>
        </section>

        {newDevice && <section className="td-token-panel" role="status"><ShieldAlert size={20} /><div><strong>Save the device token now</strong><p>{newDevice.raw_token_warning || "This token will not be shown again."}</p><label htmlFor="td-token">One-time token</label><textarea id="td-token" readOnly value={newDevice.raw_token} rows={3} /><div className="td-token-actions"><button type="button" onClick={() => void copyToken()}><Clipboard size={15} />{copied ? "Copied" : "Copy token"}</button><button type="button" onClick={() => { setNewDevice(null); setCopied(false); }}>Dismiss token</button></div></div></section>}

        <section className="op-panel">
            <div className="op-panel-head"><div><h2>Registered devices</h2><p>{devices.length} controller{devices.length === 1 ? "" : "s"} · status is fresh for 90 seconds after heartbeat</p></div></div>
            <div className="td-device-list">
                {devices.map((device) => {
                    const online = device.is_active && isRecent(device.last_heartbeat_at);
                    return <article className="td-device" key={device.id}>
                        <span className={`td-device-dot ${online ? "online" : "offline"}`} />
                        <div className="td-device-info"><strong>{device.intersection_name}</strong><span>{device.name} · {device.device_id}</span></div>
                        <span className={`td-device-status ${online ? "online" : "offline"}`}>{online ? "Reporting" : device.is_active ? "No recent heartbeat" : "Inactive"}</span>
                        <div className="td-device-meta">
                            <span><Router size={14} />{device.latest_signal_state?.current_phase || (online ? device.current_signal_phase : "Stale / unknown")}{device.latest_signal_state?.is_preempted ? " · Preemption reported" : ""}</span>
                            <span><Cpu size={14} />Firmware {device.firmware_version || "Not reported"}</span>
                            <span>Entry sensor: {device.sensor_1_detected == null ? "Not reported" : device.sensor_1_detected ? "Obstacle detected" : "Clear"}</span>
                            <span>Exit sensor: {device.sensor_2_detected == null ? "Not reported" : device.sensor_2_detected ? "Obstacle detected" : "Clear"}</span>
                            <span>{device.operational_mode || "Mode not reported"} · Wi-Fi {device.wifi_rssi == null ? "RSSI unavailable" : `${device.wifi_rssi} dBm`}</span>
                            <span>Location {Number(device.latitude).toFixed(5)}, {Number(device.longitude).toFixed(5)}</span>
                            <span>Signal report {formatTime(device.latest_signal_state?.reported_at ?? null)}</span>
                            <span>Heartbeat {formatTime(device.last_heartbeat_at)}</span>
                            <button type="button" className="td-device-toggle" disabled={savingDevice === device.device_id} onClick={() => void toggleDevice(device)}><Power size={14} />{savingDevice === device.device_id ? "Saving…" : device.is_active ? "Deactivate" : "Activate"}</button>
                        </div>
                    </article>;
                })}
                {!devices.length && <div className="op-empty"><Cpu size={23} /><strong>{loading ? "Loading controllers…" : "No traffic controllers registered"}</strong><span>Register a device above to enable telemetry and corridor evaluation.</span></div>}
            </div>
        </section>
        <p className="td-safety-note">Sensor readings show obstacle detection only; they do not identify an ambulance. This controller is for supervised low-voltage bench demonstrations and must not control public-road signals.</p>
    </div>;
}
