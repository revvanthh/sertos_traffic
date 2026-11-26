import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Activity, Ambulance, AlertTriangle, BedDouble, CheckCircle2, Clock3, MapPin, RefreshCw, X, XCircle } from "lucide-react";
import { api, type Incident } from "../../lib/api";
import { useLiveQuery } from "../../lib/useLiveQuery";
import "./hospital.css";

function formatTime(value?: string | null) {
    if (!value) return "Not recorded";
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export default function EmergencyAlerts() {
    const navigate = useNavigate();
    const [searchParams, setSearchParams] = useSearchParams();
    const { data: incidents = [], loading, error, lastUpdated, refresh } = useLiveQuery(api.getHospitalIncidents, 8_000);
    const [decisionOverrides, setDecisionOverrides] = useState<Record<string, "ACCEPTED" | "REJECTED">>({});
    const [rejectingId, setRejectingId] = useState<string | null>(null);
    const [reason, setReason] = useState("");
    const [actionError, setActionError] = useState("");
    const [saving, setSaving] = useState(false);
    const [patientDetail, setPatientDetail] = useState<{ id: string; detail: Incident | null; error: string }>({ id: "", detail: null, error: "" });

    const selected = incidents.find((incident) => incident.id === searchParams.get("incident")) ?? incidents[0];
    const decisionFor = (incident: Incident) => decisionOverrides[incident.id] ?? incident.hospital_decision ?? null;
    const pendingCount = incidents.filter((incident) => !decisionFor(incident) && !["CLOSED", "CANCELLED"].includes(incident.status)).length;
    const acceptedCount = incidents.filter((incident) => decisionFor(incident) === "ACCEPTED").length;
    const criticalCount = incidents.filter((incident) => (incident.severity === "CRITICAL" || incident.severity === "HIGH") && !decisionFor(incident)).length;

    useEffect(() => {
        if (!selected) return;
        const incidentId = selected.id;
        let active = true;
        const loadDetail = async () => {
            try {
                const detail = await api.getHospitalIncident(incidentId);
                if (active) setPatientDetail({ id: incidentId, detail, error: "" });
            } catch (cause: unknown) {
                if (active) setPatientDetail({ id: incidentId, detail: null, error: cause instanceof Error ? cause.message : "Patient details are unavailable." });
            }
        };
        void loadDetail();
        const interval = window.setInterval(() => void loadDetail(), 15_000);
        return () => { active = false; window.clearInterval(interval); };
    }, [selected?.id]);

    const selectedPatientDetail = patientDetail.id === selected?.id ? patientDetail.detail : null;
    const patientDetailLoading = Boolean(selected && patientDetail.id !== selected.id);

    const selectIncident = (incident: Incident) => setSearchParams({ incident: incident.id });
    const acceptCase = async (incident: Incident) => {
        setSaving(true);
        setActionError("");
        try {
            await api.decideHospitalIncident(incident.id, "ACCEPTED");
            setDecisionOverrides((current) => ({ ...current, [incident.id]: "ACCEPTED" }));
            refresh();
        } catch (cause: unknown) {
            setActionError(cause instanceof Error ? cause.message : "Unable to accept this incident.");
        } finally {
            setSaving(false);
        }
    };
    const rejectCase = async () => {
        if (!rejectingId || !reason.trim()) return;
        setSaving(true);
        setActionError("");
        try {
            await api.decideHospitalIncident(rejectingId, "REJECTED", reason.trim());
            setDecisionOverrides((current) => ({ ...current, [rejectingId]: "REJECTED" }));
            setRejectingId(null);
            setReason("");
            refresh();
        } catch (cause: unknown) {
            setActionError(cause instanceof Error ? cause.message : "Unable to reject this incident.");
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="hd-dashboard hea-page">
            <div className="hd-page-heading">
                <div><div className="hd-breadcrumb">Hospital / Emergency Alerts</div><h1>Emergency Alerts</h1><p>Review assigned incidents and record the hospital response.</p></div>
                <div className="hea-live-indicator"><span />{lastUpdated ? `Updated ${formatTime(lastUpdated.toISOString())}` : loading ? "Connecting…" : "Live queue"}<button type="button" onClick={refresh} aria-label="Refresh incidents"><RefreshCw size={15} /></button></div>
            </div>

            {error && <div className="hd-live-error" role="alert">Incident refresh failed: {error}</div>}
            {actionError && <div className="hd-live-error" role="alert">{actionError}</div>}
            <div className="hea-summary-grid">
                <div className="hea-summary-card"><div className="hea-summary-icon pending"><AlertTriangle size={21} /></div><div><span>Awaiting Response</span><strong>{pendingCount.toString().padStart(2, "0")}</strong></div></div>
                <div className="hea-summary-card"><div className="hea-summary-icon accepted"><CheckCircle2 size={21} /></div><div><span>Accepted</span><strong>{acceptedCount.toString().padStart(2, "0")}</strong></div></div>
                <div className="hea-summary-card"><div className="hea-summary-icon critical"><AlertTriangle size={21} /></div><div><span>High/Critical Pending</span><strong>{criticalCount.toString().padStart(2, "0")}</strong></div></div>
            </div>

            <div className="hea-layout">
                <section className="hea-list-panel">
                    <div className="hea-section-heading"><div><h2>Assigned Incidents</h2><p>Refreshes automatically every 8 seconds</p></div><span className="hea-count">{incidents.length} total</span></div>
                    <div className="hea-case-list">
                        {incidents.map((incident) => {
                            const decision = decisionFor(incident);
                            const responseLabel = decision === "ACCEPTED" ? "Accepted" : decision === "REJECTED" ? "Rejected" : "Awaiting Response";
                            return <button type="button" key={incident.id} className={`hea-case-item ${selected?.id === incident.id ? "selected" : ""}`} onClick={() => selectIncident(incident)}>
                                <div className="hea-case-top"><span className="hea-case-id">{incident.incident_number}</span><span className={`hea-severity ${(incident.severity_display || incident.severity).toLowerCase()}`}>{incident.severity_display || incident.severity}</span></div>
                                <strong>{incident.description || "Emergency response required"}</strong>
                                <span className="hea-condition">{incident.patient_count} patient{incident.patient_count === 1 ? "" : "s"} · {incident.hospital_name || "Assigned hospital"}</span>
                                <div className="hea-case-bottom"><span><Ambulance size={14} /> {incident.ambulance_vehicle_number || "Ambulance unassigned"}</span><span><Clock3 size={14} /> {formatTime(incident.created_at)}</span></div>
                                <div className={`hea-case-status ${responseLabel.toLowerCase().replaceAll(" ", "-")}`}>{responseLabel}</div>
                            </button>;
                        })}
                        {!incidents.length && <div className="hd-live-empty">{loading ? "Loading assigned incidents…" : "No incidents are currently assigned to this hospital."}</div>}
                    </div>
                </section>

                <section className="hea-details-panel">
                    {selected ? <>
                        <div className="hea-detail-header"><div><span className="hea-overline">LIVE INCIDENT DETAILS</span><h2>{selected.incident_number}</h2></div><span className={`hea-severity ${(selected.severity_display || selected.severity).toLowerCase()}`}>{selected.severity_display || selected.severity}</span></div>
                        <div className="hea-patient-banner"><div className="hea-patient-avatar"><Ambulance size={24} /></div><div><h3>{selected.ambulance_vehicle_number || "Ambulance not assigned"}</h3><p>{selected.patient_count} patient{selected.patient_count === 1 ? "" : "s"} · Reported {formatTime(selected.created_at)}</p></div><span className={`hea-case-status ${(decisionFor(selected) || "pending").toLowerCase()}`}>{decisionFor(selected) || "Awaiting Response"}</span></div>
                        <div className="hea-condition-box"><div className="hea-condition-icon"><Activity size={21} /></div><div><span>Reported emergency details</span><strong>{selected.description || "No additional description supplied."}</strong></div></div>
                        <div className="hea-detail-section"><h3>Patient information</h3>{selectedPatientDetail?.patients?.length ? selectedPatientDetail.patients.map((patient) => <div className="hea-patient-record" key={patient.id}><strong>{patient.name}</strong><span>{patient.age == null ? "Age not supplied" : `${patient.age} years`} · {patient.gender.toLowerCase()} · {patient.blood_group || "Blood group unknown"}</span>{patient.medical_notes && <p>{patient.medical_notes}</p>}</div>) : <p className="hea-medical-summary">{patientDetailLoading ? "Loading authorized patient details…" : patientDetail.error || "No patient triage details were recorded for this incident."}</p>}</div>
                        <div className="hea-detail-section"><h3>Operational status</h3><div className="hea-resource-row"><span>Incident status</span><strong>{selected.status_display || selected.status}</strong></div><div className="hea-resource-row"><span>Hospital response</span><strong>{decisionFor(selected) || "Awaiting response"}</strong></div><div className="hea-resource-row"><span>Facility</span><strong>{selected.hospital_name || "Assigned hospital"}</strong></div><div className="hea-resource-row"><span>Ambulance</span><strong>{selected.ambulance_vehicle_number || "Not assigned"}</strong></div></div>
                        <div className="hea-detail-section"><h3><BedDouble size={17} /> Bed coordination</h3><p className="hea-medical-summary">Review current capacity in Bed Management. Acceptance records the hospital decision in the incident system.</p><button type="button" className="hea-call-driver" onClick={() => navigate("/hospital/beds")}><BedDouble size={15} /> Open Bed Management</button></div>
                        <div className="hea-detail-section"><h3><MapPin size={17} /> Incident timeline</h3><div className="hea-resource-row"><span>Reported</span><strong>{formatTime(selected.created_at)}</strong></div><div className="hea-resource-row"><span>Assigned</span><strong>{formatTime(selected.assigned_at)}</strong></div><div className="hea-resource-row"><span>In transit</span><strong>{formatTime(selected.in_transit_at)}</strong></div><div className="hea-resource-row"><span>Arrival</span><strong>{formatTime(selected.arrived_at)}</strong></div></div>
                        {decisionFor(selected) ? <div className={`hea-response-message ${decisionFor(selected)?.toLowerCase()}`}><CheckCircle2 size={19} /> Response saved as {decisionFor(selected)}.</div> : <div className="hea-action-area"><p>Choose a response for this assigned incident.</p><div className="hea-action-buttons"><button type="button" className="hea-accept-button" disabled={saving} onClick={() => void acceptCase(selected)}><CheckCircle2 size={17} /> {saving ? "Saving…" : "Accept incident"}</button><button type="button" className="hea-reject-button" disabled={saving} onClick={() => { setRejectingId(selected.id); setReason(""); }}><XCircle size={17} /> Reject</button></div></div>}
                    </> : <div className="hd-live-empty">{loading ? "Loading incident details…" : "Select an assigned incident to review."}</div>}
                </section>
            </div>

            {rejectingId && <div className="hea-modal-overlay" role="presentation"><div className="hea-reject-modal" role="dialog" aria-modal="true" aria-labelledby="hea-reject-title"><button type="button" className="hea-modal-close" onClick={() => setRejectingId(null)} aria-label="Close rejection dialog"><X size={19} /></button><div className="hea-modal-icon"><AlertTriangle size={23} /></div><h2 id="hea-reject-title">Reject incident?</h2><p>Choose a reason so dispatch can continue coordination.</p><label htmlFor="hea-rejection-reason">Reason</label><select id="hea-rejection-reason" value={reason} onChange={(event) => setReason(event.target.value)}><option value="">Select a reason</option><option value="No suitable bed available">No suitable bed available</option><option value="Required specialist unavailable">Required specialist unavailable</option><option value="Emergency department at capacity">Emergency department at capacity</option><option value="Required medical equipment unavailable">Required medical equipment unavailable</option><option value="Other operational reason">Other operational reason</option></select><div className="hea-modal-actions"><button type="button" onClick={() => setRejectingId(null)}>Cancel</button><button type="button" disabled={!reason || saving} onClick={() => void rejectCase()}>{saving ? "Saving…" : "Confirm Rejection"}</button></div></div></div>}
        </div>
    );
}
