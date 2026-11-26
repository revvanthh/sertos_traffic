import { useCallback, useEffect, useState, type FormEvent } from "react";
import { CheckCircle2, RefreshCw, UserRound } from "lucide-react";
import { api, type UserProfile } from "../../lib/api";
import { useLiveQuery } from "../../lib/useLiveQuery";
import "./operations.css";

export default function ProfilePage() {
    const loadProfile = useCallback(() => api.getProfile(), []);
    const { data: profile, loading, error, refresh } = useLiveQuery<UserProfile>(loadProfile, 60_000);
    const [form, setForm] = useState({ first_name: "", last_name: "", email: "", phone_number: "", badge_or_employee_id: "" });
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState("");
    const [saveError, setSaveError] = useState("");

    useEffect(() => {
        if (!profile) return;
        setForm({ first_name: profile.first_name ?? "", last_name: profile.last_name ?? "", email: profile.email ?? "", phone_number: profile.phone_number ?? "", badge_or_employee_id: profile.badge_or_employee_id ?? "" });
    }, [profile?.id]);

    const save = async (event: FormEvent) => {
        event.preventDefault();
        setSaving(true);
        setMessage("");
        setSaveError("");
        try {
            await api.updateProfile(form);
            setMessage("Profile saved.");
            refresh();
        } catch (cause: unknown) {
            setSaveError(cause instanceof Error ? cause.message : "Unable to save profile.");
        } finally {
            setSaving(false);
        }
    };

    return <div className="op-page"><header className="op-header"><div><div className="op-breadcrumb">Account / Profile</div><h1>My Profile</h1><p>Review and update the contact details attached to your SERTOS account.</p></div><button type="button" className="op-refresh" onClick={refresh}><RefreshCw size={16} /> Refresh</button></header>
        {error && <div className="op-error" role="alert">Profile load failed: {error}</div>}{saveError && <div className="op-error" role="alert">{saveError}</div>}{message && <div className="op-success"><CheckCircle2 size={16} />{message}</div>}
        <section className="op-profile-card"><div className="op-profile-heading"><span><UserRound size={22} /></span><div><strong>{profile ? `${profile.first_name} ${profile.last_name}`.trim() || profile.username : loading ? "Loading profile…" : "Profile unavailable"}</strong><small>{profile?.role?.replaceAll("_", " ") || ""} · {profile?.is_verified ? "Verified account" : "Verification required"}</small></div></div>
            {profile && <form className="op-profile-form" onSubmit={save}><label>First name<input value={form.first_name} onChange={(event) => setForm({ ...form, first_name: event.target.value })} /></label><label>Last name<input value={form.last_name} onChange={(event) => setForm({ ...form, last_name: event.target.value })} /></label><label>Email<input type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} /></label><label>Phone<input value={form.phone_number} onChange={(event) => setForm({ ...form, phone_number: event.target.value })} /></label><label>Badge / employee ID<input value={form.badge_or_employee_id} onChange={(event) => setForm({ ...form, badge_or_employee_id: event.target.value })} /></label><div className="op-profile-actions"><span>Username: {profile.username}</span><button type="submit" disabled={saving}>{saving ? "Saving…" : "Save profile"}</button></div></form>}
        </section>
    </div>;
}
