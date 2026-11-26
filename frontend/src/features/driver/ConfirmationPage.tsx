import { useLocation, useNavigate } from "react-router-dom";
import { useState, type FormEvent } from "react";
import { Ambulance, ArrowLeft, CheckCircle2, Mic, ShieldAlert, XCircle } from "lucide-react";
import { api, type Hospital } from "../../lib/api";
import { useEffect } from "react";

type ConfirmationState = { patientReport?: string };
type Severity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
type Gender = "MALE" | "FEMALE" | "OTHER" | "UNKNOWN";

function ConfirmationPage() {
    const navigate = useNavigate();
    const location = useLocation();
    const state = location.state as ConfirmationState | null;
    const patientReport = state?.patientReport || "";
    const [hospitals, setHospitals] = useState<Hospital[]>([]);
    const [hospitalId, setHospitalId] = useState("");
    const [hospitalsLoading, setHospitalsLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");
    const [form, setForm] = useState(() => ({
        patientName: "",
        age: "",
        gender: "UNKNOWN" as Gender,
        bloodGroup: "",
        severity: "" as Severity | "",
        description: patientReport,
        medicalNotes: patientReport,
    }));

    useEffect(() => {
        let active = true;
        api.getHospitals()
            .then((items) => {
                if (!active) return;
                setHospitals(items);
                if (items[0]) setHospitalId(items[0].id);
            })
            .catch((reason: unknown) => {
                if (active) setError(reason instanceof Error ? reason.message : "Unable to load hospitals.");
            })
            .finally(() => { if (active) setHospitalsLoading(false); });
        return () => { active = false; };
    }, []);

    const handleCancel = () => {
        navigate("/driver", { state: { patientReport, returnFromConfirmation: true } });
    };

    const handleConfirm = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        if (!hospitalId || !form.severity || !form.patientName.trim()) return;
        if (form.age && (!Number.isInteger(Number(form.age)) || Number(form.age) < 0 || Number(form.age) > 150)) {
            setError("Enter a patient age between 0 and 150, or leave it blank.");
            return;
        }
        setSubmitting(true);
        setError("");
        try {
            const incident = await api.createEmergency({
                hospital_id: hospitalId,
                severity: form.severity,
                description: form.description.trim(),
                patient: {
                    name: form.patientName.trim(),
                    ...(form.age ? { age: Number(form.age) } : {}),
                    gender: form.gender,
                    ...(form.bloodGroup ? { blood_group: form.bloodGroup } : {}),
                    medical_notes: form.medicalNotes.trim(),
                },
            });
            navigate("/driver", { state: { patientReport, emergencyActivated: true, incident } });
        } catch (reason: unknown) {
            setError(reason instanceof Error ? reason.message : "Unable to activate emergency.");
        } finally {
            setSubmitting(false);
        }
    };

    const fieldClass = "mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100";

    return <div className="min-h-screen bg-slate-50 text-slate-900">
        <header className="border-b border-slate-200 bg-white px-4 py-4"><div className="mx-auto flex max-w-3xl items-center gap-3"><button type="button" onClick={handleCancel} className="rounded-xl bg-slate-100 p-2" aria-label="Return to driver dashboard"><ArrowLeft size={20} /></button><div><h1 className="text-lg font-extrabold">Emergency Report</h1><p className="text-xs text-slate-500">Review the details before sending to dispatch.</p></div></div></header>
        <main className="mx-auto grid max-w-3xl gap-5 px-4 py-6">
            <div className="rounded-2xl border border-red-200 bg-red-50 p-5">
                <div className="flex items-start gap-3"><span className="rounded-xl bg-red-100 p-2 text-red-700"><ShieldAlert size={22} /></span><div><h2 className="font-bold text-red-800">Confirm only for an active emergency</h2><p className="mt-1 text-sm leading-6 text-red-700">Submitting creates a real incident in the connected SERTOS backend and notifies its authorized hospital and dispatch workflows.</p></div></div>
            </div>

            <section className="rounded-2xl border border-slate-200 bg-white p-5">
                <div className="mb-4 flex items-center gap-3"><span className="rounded-xl bg-blue-50 p-2 text-blue-700"><Mic size={20} /></span><div><h2 className="font-bold">Reported emergency</h2><p className="text-xs text-slate-500">Voice transcription can be edited before submission.</p></div></div>
                <label className="block text-sm font-semibold" htmlFor="emergency-description">Incident description</label>
                <textarea id="emergency-description" className={`${fieldClass} min-h-24 resize-y`} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} required maxLength={2000} />
                <label className="mt-4 block text-sm font-semibold" htmlFor="patient-notes">Patient / triage notes</label>
                <textarea id="patient-notes" className={`${fieldClass} min-h-24 resize-y`} value={form.medicalNotes} onChange={(event) => setForm({ ...form, medicalNotes: event.target.value })} maxLength={2000} />
            </section>

            <form onSubmit={(event) => void handleConfirm(event)} className="grid gap-5">
                <section className="rounded-2xl border border-slate-200 bg-white p-5">
                    <div className="mb-4 flex items-center gap-3"><span className="rounded-xl bg-rose-50 p-2 text-rose-700"><Ambulance size={20} /></span><div><h2 className="font-bold">Primary patient</h2><p className="text-xs text-slate-500">The current emergency API accepts one patient record per report.</p></div></div>
                    <div className="grid gap-4 sm:grid-cols-2">
                        <label className="text-sm font-semibold">Patient name<input className={fieldClass} value={form.patientName} onChange={(event) => setForm({ ...form, patientName: event.target.value })} autoComplete="off" maxLength={120} required /></label>
                        <label className="text-sm font-semibold">Age (optional)<input className={fieldClass} type="number" min="0" max="150" step="1" value={form.age} onChange={(event) => setForm({ ...form, age: event.target.value })} /></label>
                        <label className="text-sm font-semibold">Gender<select className={fieldClass} value={form.gender} onChange={(event) => setForm({ ...form, gender: event.target.value as Gender })}><option value="UNKNOWN">Unknown</option><option value="FEMALE">Female</option><option value="MALE">Male</option><option value="OTHER">Other</option></select></label>
                        <label className="text-sm font-semibold">Blood group (optional)<select className={fieldClass} value={form.bloodGroup} onChange={(event) => setForm({ ...form, bloodGroup: event.target.value })}><option value="">Not known</option>{["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].map((group) => <option key={group} value={group}>{group}</option>)}</select></label>
                    </div>
                </section>

                <section className="rounded-2xl border border-slate-200 bg-white p-5">
                    <h2 className="font-bold">Dispatch details</h2>
                    <div className="mt-4 grid gap-4 sm:grid-cols-2">
                        <label className="text-sm font-semibold">Triage severity<select className={fieldClass} value={form.severity} onChange={(event) => setForm({ ...form, severity: event.target.value as Severity | "" })} required><option value="">Select severity</option><option value="CRITICAL">Critical</option><option value="HIGH">High</option><option value="MEDIUM">Medium</option><option value="LOW">Low</option></select></label>
                        <label className="text-sm font-semibold">Destination hospital<select className={fieldClass} value={hospitalId} onChange={(event) => setHospitalId(event.target.value)} disabled={hospitalsLoading || submitting} required><option value="">{hospitalsLoading ? "Loading hospitals…" : "Select a hospital"}</option>{hospitals.map((hospital) => <option key={hospital.id} value={hospital.id}>{hospital.name}</option>)}</select></label>
                    </div>
                    {error && <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
                    {hospitals.length === 0 && !hospitalsLoading && <p className="mt-3 text-sm text-amber-800">No destination hospital was returned by the backend. An incident cannot be submitted until a hospital is available.</p>}
                </section>

                <div className="grid gap-3 pb-5 sm:grid-cols-2">
                    <button type="submit" disabled={!form.patientName.trim() || !form.severity || !hospitalId || hospitalsLoading || submitting} className="flex items-center justify-center gap-2 rounded-2xl bg-red-600 py-4 font-extrabold text-white shadow-lg transition hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-slate-300">{submitting ? "SENDING REPORT…" : <><CheckCircle2 size={20} /> Confirm & send emergency</>}</button>
                    <button type="button" onClick={handleCancel} className="flex items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white py-4 font-bold text-slate-700"><XCircle size={18} /> Return without sending</button>
                </div>
                <p className="text-center text-xs text-slate-500">Only fields supported by the SERTOS emergency API are sent. Confirm only when the response is ready to begin.</p>
            </form>
        </main>
    </div>;
}

export default ConfirmationPage;
