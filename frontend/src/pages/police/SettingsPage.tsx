import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  Bell,
  KeyRound,
  LogOut,
  Save,
  ShieldCheck,
  Sliders,
  UserRound,
} from "lucide-react";
import { usePoliceControl } from "../../context/PoliceControlContext";
import { getLoginHistory } from "../../services/authService";
import { ConfirmModal } from "../../components/common/ConfirmModal";
import { StatusBadge } from "../../components/common/StatusBadge";

export default function SettingsPage() {
  const navigate = useNavigate();
  const {
    authMode,
    systemStatus,
    officerProfile,
    updateOfficerProfile,
    settings,
    updateSettings,
    cctvCameras,
    performLogout,
    pushToast,
  } = usePoliceControl();

  const [profileForm, setProfileForm] = useState(officerProfile);
  const [settingsForm, setSettingsForm] = useState(settings);
  const [savingProfile, setSavingProfile] = useState(false);
  const [logoutOpen, setLogoutOpen] = useState(false);
  const loginHistory = getLoginHistory();

  const handleSaveProfile = async (e: FormEvent) => {
    e.preventDefault();
    setSavingProfile(true);
    try {
      await updateOfficerProfile(profileForm);
    } catch (err) {
      pushToast({
        title: "Profile Update Failed",
        description: err instanceof Error ? err.message : "Could not save profile.",
        variant: "error",
      });
    } finally {
      setSavingProfile(false);
    }
  };

  const handleSaveDashboardSettings = (e: FormEvent) => {
    e.preventDefault();
    updateSettings(settingsForm);
  };

  const handleConfirmLogout = async () => {
    await performLogout();
    setLogoutOpen(false);
    navigate("/login", {
      replace: true,
      state: { loggedOutMessage: "Logged out successfully" },
    });
  };

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4">
        <h1 className="text-[22px] font-bold text-[#F1F5F9]">Settings &amp; Officer Profile</h1>
        <p className="text-[13px] text-[#94A3B8]">
          Configure Bengaluru Traffic Police control preferences, notification triggers, and inspect live system connectivity.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        {/* Officer Profile */}
        <section className="rounded-2xl border border-[#1D3552] bg-[#0A1729] p-5 xl:col-span-6">
          <div className="flex items-center justify-between border-b border-[#1D3552] pb-3">
            <div className="flex items-center gap-2">
              <UserRound size={18} className="text-[#24A8FF]" />
              <h2 className="text-[16px] font-semibold text-[#F1F5F9]">Officer Profile</h2>
            </div>
            <StatusBadge
              label={officerProfile.accountStatus}
              tone={authMode === "live" ? "live" : "demo"}
            />
          </div>

          <form onSubmit={(e) => void handleSaveProfile(e)} className="mt-4 space-y-3">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="text-[12px] text-[#94A3B8]">
                Officer Name
                <input
                  value={profileForm.name}
                  onChange={(e) => setProfileForm({ ...profileForm, name: e.target.value })}
                  className="mt-1 w-full rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-2 text-[13px] text-[#F1F5F9] outline-none focus:border-[#24A8FF]"
                />
              </label>
              <label className="text-[12px] text-[#94A3B8]">
                Officer ID
                <input
                  value={profileForm.officerId}
                  onChange={(e) => setProfileForm({ ...profileForm, officerId: e.target.value })}
                  className="mt-1 w-full rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-2 text-[13px] text-[#F1F5F9] outline-none focus:border-[#24A8FF]"
                />
              </label>
              <label className="text-[12px] text-[#94A3B8]">
                Role
                <input
                  value={profileForm.role}
                  onChange={(e) => setProfileForm({ ...profileForm, role: e.target.value })}
                  className="mt-1 w-full rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-2 text-[13px] text-[#F1F5F9] outline-none focus:border-[#24A8FF]"
                />
              </label>
              <label className="text-[12px] text-[#94A3B8]">
                Traffic Division
                <input
                  value={profileForm.trafficDivision}
                  onChange={(e) =>
                    setProfileForm({ ...profileForm, trafficDivision: e.target.value })
                  }
                  className="mt-1 w-full rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-2 text-[13px] text-[#F1F5F9] outline-none focus:border-[#24A8FF]"
                />
              </label>
              <label className="text-[12px] text-[#94A3B8] sm:col-span-2">
                Assigned Control Zone
                <input
                  value={profileForm.assignedZone}
                  onChange={(e) =>
                    setProfileForm({ ...profileForm, assignedZone: e.target.value })
                  }
                  className="mt-1 w-full rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-2 text-[13px] text-[#F1F5F9] outline-none focus:border-[#24A8FF]"
                />
              </label>
              <label className="text-[12px] text-[#94A3B8]">
                Email
                <input
                  type="email"
                  value={profileForm.email}
                  onChange={(e) => setProfileForm({ ...profileForm, email: e.target.value })}
                  className="mt-1 w-full rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-2 text-[13px] text-[#F1F5F9] outline-none focus:border-[#24A8FF]"
                />
              </label>
              <label className="text-[12px] text-[#94A3B8]">
                Contact Phone
                <input
                  type="tel"
                  value={profileForm.phone}
                  onChange={(e) => setProfileForm({ ...profileForm, phone: e.target.value })}
                  className="mt-1 w-full rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-2 text-[13px] text-[#F1F5F9] outline-none focus:border-[#24A8FF]"
                />
              </label>
            </div>

            <button
              type="submit"
              disabled={savingProfile}
              className="inline-flex items-center gap-2 rounded-xl bg-[#00D084] px-4 py-2 text-[13px] font-semibold text-[#020B18] hover:bg-[#20E39A] disabled:opacity-50"
            >
              <Save size={15} />
              {savingProfile ? "Saving..." : "Save Officer Profile"}
            </button>
          </form>
        </section>

        {/* Dashboard & Notification Settings */}
        <section className="rounded-2xl border border-[#1D3552] bg-[#0A1729] p-5 xl:col-span-6">
          <div className="flex items-center gap-2 border-b border-[#1D3552] pb-3">
            <Sliders size={18} className="text-[#20E39A]" />
            <h2 className="text-[16px] font-semibold text-[#F1F5F9]">
              Dashboard &amp; Notification Settings
            </h2>
          </div>

          <form onSubmit={handleSaveDashboardSettings} className="mt-4 space-y-4">
            <div>
              <div className="mb-2 text-[12px] font-semibold text-[#F1F5F9]">
                Default Map Layers
              </div>
              <div className="grid grid-cols-2 gap-2 text-[12px]">
                {(
                  [
                    { key: "traffic", label: "Traffic Flow Overlay" },
                    { key: "emergencyRoutes", label: "Emergency Routes" },
                    { key: "policeUnits", label: "Police Units" },
                    { key: "incidents", label: "Incident Markers" },
                  ] as const
                ).map((item) => (
                  <label
                    key={item.key}
                    className="flex cursor-pointer items-center gap-2 rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-2 text-[#F1F5F9]"
                  >
                    <input
                      type="checkbox"
                      checked={settingsForm.defaultMapLayers[item.key]}
                      onChange={(e) =>
                        setSettingsForm({
                          ...settingsForm,
                          defaultMapLayers: {
                            ...settingsForm.defaultMapLayers,
                            [item.key]: e.target.checked,
                          },
                        })
                      }
                      className="accent-[#00D084]"
                    />
                    <span>{item.label}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="text-[12px] text-[#94A3B8]">
                CCTV Default Camera
                <select
                  value={settingsForm.defaultCctvId}
                  onChange={(e) =>
                    setSettingsForm({ ...settingsForm, defaultCctvId: e.target.value })
                  }
                  className="mt-1 w-full rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-2 text-[13px] text-[#F1F5F9]"
                >
                  {cctvCameras.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.cameraId} — {c.location}
                    </option>
                  ))}
                </select>
              </label>

              <label className="text-[12px] text-[#94A3B8]">
                Refresh Frequency
                <select
                  value={settingsForm.refreshIntervalSec}
                  onChange={(e) =>
                    setSettingsForm({
                      ...settingsForm,
                      refreshIntervalSec: Number(e.target.value),
                    })
                  }
                  className="mt-1 w-full rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-2 text-[13px] text-[#F1F5F9]"
                >
                  <option value={5}>Every 5 seconds</option>
                  <option value={8}>Every 8 seconds</option>
                  <option value={15}>Every 15 seconds</option>
                  <option value={30}>Every 30 seconds</option>
                </select>
              </label>
            </div>

            <div>
              <div className="mb-2 flex items-center gap-1.5 text-[12px] font-semibold text-[#F1F5F9]">
                <Bell size={14} className="text-[#24A8FF]" />
                Alert &amp; Notification Preferences
              </div>
              <div className="grid grid-cols-1 gap-2 text-[12px] sm:grid-cols-2">
                {(
                  [
                    { key: "emergencyAlerts", label: "Emergency Alerts" },
                    { key: "routeCleared", label: "Route Cleared" },
                    { key: "ambulanceNearingHospital", label: "Ambulance Nearing Hospital" },
                    { key: "signalStatusChanges", label: "Signal Status Changes" },
                    { key: "policeUnitUpdates", label: "Police Unit Updates" },
                  ] as const
                ).map((item) => (
                  <label
                    key={item.key}
                    className="flex cursor-pointer items-center gap-2 rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-2 text-[#F1F5F9]"
                  >
                    <input
                      type="checkbox"
                      checked={settingsForm.notifications[item.key]}
                      onChange={(e) =>
                        setSettingsForm({
                          ...settingsForm,
                          notifications: {
                            ...settingsForm.notifications,
                            [item.key]: e.target.checked,
                          },
                        })
                      }
                      className="accent-[#00D084]"
                    />
                    <span>{item.label}</span>
                  </label>
                ))}
                <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-2 text-[#F1F5F9]">
                  <input
                    type="checkbox"
                    checked={settingsForm.alertSound}
                    onChange={(e) =>
                      setSettingsForm({ ...settingsForm, alertSound: e.target.checked })
                    }
                    className="accent-[#00D084]"
                  />
                  <span>Alert Sound Cues</span>
                </label>
              </div>
            </div>

            <button
              type="submit"
              className="inline-flex items-center gap-2 rounded-xl bg-[#00D084] px-4 py-2 text-[13px] font-semibold text-[#020B18] hover:bg-[#20E39A]"
            >
              <Save size={15} />
              Save Settings
            </button>
          </form>
        </section>

        {/* System Status */}
        <section className="rounded-2xl border border-[#1D3552] bg-[#0A1729] p-5 xl:col-span-6">
          <div className="flex items-center gap-2 border-b border-[#1D3552] pb-3">
            <Activity size={18} className="text-[#20E39A]" />
            <h2 className="text-[16px] font-semibold text-[#F1F5F9]">System Status</h2>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-2.5 sm:grid-cols-2 text-[12px]">
            {[
              { label: "Backend API", value: systemStatus.backend, ok: systemStatus.backend === "Connected" },
              { label: "Database", value: systemStatus.database, ok: systemStatus.database === "Connected" },
              { label: "GPS Feed", value: systemStatus.gps, ok: systemStatus.gps === "Live Feed" },
              { label: "Map Service", value: systemStatus.mapService, ok: true },
              { label: "Signal Integration", value: systemStatus.signalIntegration, ok: systemStatus.signalIntegration === "ESP32 Telemetry" },
              { label: "CCTV Stream", value: systemStatus.cctv, ok: false },
            ].map((row) => (
              <div
                key={row.label}
                className="flex items-center justify-between rounded-xl border border-[#1D3552] bg-[#061326] px-3.5 py-2.5"
              >
                <span className="text-[#94A3B8]">{row.label}</span>
                <StatusBadge
                  label={row.value}
                  tone={row.ok ? "live" : "demo"}
                />
              </div>
            ))}
          </div>
        </section>

        {/* Security & Session */}
        <section className="rounded-2xl border border-[#1D3552] bg-[#0A1729] p-5 xl:col-span-6">
          <div className="flex items-center justify-between border-b border-[#1D3552] pb-3">
            <div className="flex items-center gap-2">
              <ShieldCheck size={18} className="text-[#24A8FF]" />
              <h2 className="text-[16px] font-semibold text-[#F1F5F9]">Security &amp; Session</h2>
            </div>
            <button
              type="button"
              onClick={() => setLogoutOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-xl border border-[#EF4444]/40 bg-[#EF4444]/15 px-3 py-1.5 text-[12px] font-semibold text-[#EF4444] hover:bg-[#EF4444]/25"
            >
              <LogOut size={14} />
              Logout
            </button>
          </div>

          <div className="mt-4 space-y-3 text-[12px]">
            <div className="flex items-center justify-between rounded-xl border border-[#1D3552] bg-[#061326] px-3.5 py-2.5">
              <span className="text-[#94A3B8]">Authentication Mode</span>
              <span className="font-semibold text-[#F1F5F9]">
                {authMode === "live" ? "Django SimpleJWT Bearer Auth" : "Demo Mode (Simulated Session)"}
              </span>
            </div>

            <div className="flex items-center justify-between rounded-xl border border-[#1D3552] bg-[#061326] px-3.5 py-2.5">
              <div className="flex items-center gap-2 text-[#94A3B8]">
                <KeyRound size={14} />
                <span>Password Change</span>
              </div>
              <button
                type="button"
                disabled
                title="Password changes are handled by SERTOS IT Administration; no self-service password endpoint is exposed."
                className="cursor-not-allowed rounded-lg border border-[#1D3552] bg-[#0D1D32] px-2.5 py-1 text-[11px] text-[#94A3B8] opacity-60"
              >
                Admin Managed (Disabled)
              </button>
            </div>

            <div>
              <div className="mb-2 text-[12px] font-semibold text-[#F1F5F9]">
                Recent Login Activity
              </div>
              <div className="max-h-32 space-y-1.5 overflow-y-auto">
                {loginHistory.length === 0 ? (
                  <div className="text-[#94A3B8]">No recent sign-in events recorded.</div>
                ) : (
                  loginHistory.slice(0, 5).map((entry) => (
                    <div
                      key={entry.id}
                      className="flex items-center justify-between rounded-lg border border-[#1D3552]/70 bg-[#061326] px-3 py-1.5 text-[11px]"
                    >
                      <span className="text-[#F1F5F9]">
                        {entry.identifier} ({entry.mode.toUpperCase()})
                      </span>
                      <span
                        className={
                          entry.status === "Success" ? "text-[#20E39A]" : "text-[#EF4444]"
                        }
                      >
                        {entry.status}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </section>
      </div>

      <ConfirmModal
        open={logoutOpen}
        title="Confirm Officer Logout"
        description="End your active SERTOS Traffic Police session and clear stored session tokens?"
        confirmLabel="Logout"
        variant="danger"
        onConfirm={() => void handleConfirmLogout()}
        onCancel={() => setLogoutOpen(false)}
      />
    </div>
  );
}
