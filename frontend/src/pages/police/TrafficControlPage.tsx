import { useMemo, useState } from "react";
import {
  AlertTriangle,
  LayoutGrid,
  List,
  MapPin,
  Radio,
  Search,
  ShieldAlert,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { usePoliceControl } from "../../context/PoliceControlContext";
import { ConfirmModal } from "../../components/common/ConfirmModal";
import { StatusBadge } from "../../components/common/StatusBadge";
import type {
  SignalConnectivity,
  SignalLight,
  TrafficDensityLevel,
  TrafficSignal,
} from "../../types/police";

function formatSec(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export default function TrafficControlPage() {
  const { signals, toggleSignalEmergencyMode, switchSignalLight } = usePoliceControl();

  const [search, setSearch] = useState("");
  const [zoneFilter, setZoneFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState<"ALL" | SignalConnectivity>("ALL");
  const [densityFilter, setDensityFilter] = useState<"ALL" | TrafficDensityLevel>("ALL");
  const [viewMode, setViewMode] = useState<"table" | "grid">("table");
  const [selectedSignal, setSelectedSignal] = useState<TrafficSignal | null>(null);
  const [confirmAction, setConfirmAction] = useState<{
    open: boolean;
    signal: TrafficSignal | null;
    action: "priority_on" | "priority_off" | "phase";
    phase?: SignalLight;
  }>({ open: false, signal: null, action: "priority_on" });

  const zones = useMemo(
    () => Array.from(new Set(signals.map((s) => s.zone))),
    [signals],
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return signals.filter((s) => {
      if (zoneFilter !== "ALL" && s.zone !== zoneFilter) return false;
      if (statusFilter !== "ALL" && s.status !== statusFilter) return false;
      if (densityFilter !== "ALL" && s.trafficDensity !== densityFilter) return false;
      if (q && !`${s.signalId} ${s.location} ${s.zone}`.toLowerCase().includes(q)) {
        return false;
      }
      return true;
    });
  }, [signals, search, zoneFilter, statusFilter, densityFilter]);

  const activeModalSignal = selectedSignal
    ? signals.find((s) => s.id === selectedSignal.id) ?? selectedSignal
    : null;

  const executeConfirmedAction = () => {
    if (!confirmAction.signal) return;
    if (confirmAction.action === "priority_on") {
      toggleSignalEmergencyMode(confirmAction.signal.id, true);
    } else if (confirmAction.action === "priority_off") {
      toggleSignalEmergencyMode(confirmAction.signal.id, false);
    } else if (confirmAction.action === "phase" && confirmAction.phase) {
      switchSignalLight(confirmAction.signal.id, confirmAction.phase);
    }
    setConfirmAction({ open: false, signal: null, action: "priority_on" });
  };

  return (
    <div className="space-y-4">
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4">
        <div>
          <h1 className="text-[22px] font-bold text-[#F1F5F9]">Traffic Signal Control</h1>
          <p className="text-[13px] text-[#94A3B8]">
            Manage Bengaluru junction signals, monitor traffic density, and run safe emergency priority simulations.
          </p>
        </div>

        <div className="flex items-center gap-2 rounded-xl border border-[#1D3552] bg-[#061326] p-1">
          <button
            type="button"
            onClick={() => setViewMode("table")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-medium ${
              viewMode === "table"
                ? "bg-[#0D1D32] text-[#20E39A]"
                : "text-[#94A3B8] hover:text-[#F1F5F9]"
            }`}
          >
            <List size={14} />
            Table
          </button>
          <button
            type="button"
            onClick={() => setViewMode("grid")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-medium ${
              viewMode === "grid"
                ? "bg-[#0D1D32] text-[#20E39A]"
                : "text-[#94A3B8] hover:text-[#F1F5F9]"
            }`}
          >
            <LayoutGrid size={14} />
            Grid
          </button>
        </div>
      </div>

      {/* Simulation Safety Banner */}
      <div className="flex items-center gap-2.5 rounded-xl border border-[#F59E0B]/35 bg-[#F59E0B]/10 px-4 py-2.5 text-[12px] text-[#FBBF24]">
        <ShieldAlert size={16} className="shrink-0" />
        <span>
          <strong>Simulation Safety Notice:</strong> Signal phase switches and Priority Green overrides run in safe software simulation mode unless verified physical ESP32 hardware controllers are online.
        </span>
      </div>

      {/* Filters */}
      <div className="grid grid-cols-1 gap-3 rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="flex items-center gap-2 rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-2">
          <Search size={15} className="text-[#94A3B8]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search signal ID or junction..."
            aria-label="Search traffic signals"
            className="w-full bg-transparent text-[13px] text-[#F1F5F9] placeholder-[#94A3B8]/60 outline-none"
          />
        </div>

        <select
          value={zoneFilter}
          onChange={(e) => setZoneFilter(e.target.value)}
          aria-label="Filter signals by zone"
          className="rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-2 text-[13px] text-[#F1F5F9] outline-none"
        >
          <option value="ALL">All Zones</option>
          {zones.map((z) => (
            <option key={z} value={z}>
              {z}
            </option>
          ))}
        </select>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as "ALL" | SignalConnectivity)}
          aria-label="Filter signals by status"
          className="rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-2 text-[13px] text-[#F1F5F9] outline-none"
        >
          <option value="ALL">All Statuses</option>
          <option value="Active">Active</option>
          <option value="Simulated">Simulated</option>
          <option value="Offline">Offline</option>
        </select>

        <select
          value={densityFilter}
          onChange={(e) => setDensityFilter(e.target.value as "ALL" | TrafficDensityLevel)}
          aria-label="Filter signals by traffic density"
          className="rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-2 text-[13px] text-[#F1F5F9] outline-none"
        >
          <option value="ALL">All Traffic Densities</option>
          <option value="Smooth">Smooth</option>
          <option value="Moderate">Moderate</option>
          <option value="Heavy">Heavy</option>
        </select>
      </div>

      {/* Table or Grid View */}
      {viewMode === "table" ? (
        <div className="overflow-x-auto rounded-2xl border border-[#1D3552] bg-[#0A1729]">
          <table className="w-full min-w-[820px] text-left text-[13px]">
            <thead className="border-b border-[#1D3552] bg-[#061326] text-[11px] uppercase tracking-wider text-[#94A3B8]">
              <tr>
                <th className="px-4 py-3">Signal ID</th>
                <th className="px-4 py-3">Location</th>
                <th className="px-4 py-3">Current Light</th>
                <th className="px-4 py-3">Traffic Density</th>
                <th className="px-4 py-3">Mode</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Countdown</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1D3552]/70">
              {filtered.map((sig) => {
                const isEmergency = sig.mode === "Emergency Priority";
                return (
                  <tr key={sig.id} className="hover:bg-[#0D1D32]/70">
                    <td className="px-4 py-3 font-mono font-semibold text-[#24A8FF]">
                      {sig.signalId}
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-semibold text-[#F1F5F9]">{sig.location}</div>
                      <div className="text-[11px] text-[#94A3B8]">{sig.zone}</div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="inline-flex items-center gap-2 rounded-lg border border-[#1D3552] bg-[#061326] px-2.5 py-1">
                        <span
                          className={`h-2.5 w-2.5 rounded-full ${
                            sig.currentLight === "GREEN"
                              ? "bg-[#20E39A] shadow-[0_0_8px_#20E39A]"
                              : sig.currentLight === "YELLOW"
                                ? "bg-[#F59E0B] shadow-[0_0_8px_#F59E0B]"
                                : "bg-[#EF4444] shadow-[0_0_8px_#EF4444]"
                          }`}
                        />
                        <span className="text-[12px] font-semibold">{sig.currentLight}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge
                        label={sig.trafficDensity}
                        tone={
                          sig.trafficDensity === "Smooth"
                            ? "live"
                            : sig.trafficDensity === "Moderate"
                              ? "warning"
                              : "critical"
                        }
                      />
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`text-[12px] font-medium ${
                          isEmergency ? "text-[#20E39A]" : "text-[#94A3B8]"
                        }`}
                      >
                        {sig.mode}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge
                        label={sig.status}
                        tone={sig.status === "Offline" ? "neutral" : "active"}
                      />
                    </td>
                    <td className="px-4 py-3 font-mono text-[#F1F5F9]">
                      {sig.status === "Offline" ? "--:--" : formatSec(sig.countdownSeconds)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="inline-flex items-center gap-2">
                        <button
                          type="button"
                          disabled={sig.status === "Offline"}
                          onClick={() =>
                            setConfirmAction({
                              open: true,
                              signal: sig,
                              action: isEmergency ? "priority_off" : "priority_on",
                            })
                          }
                          className={`rounded-lg px-2.5 py-1 text-[11px] font-semibold transition disabled:opacity-40 ${
                            isEmergency
                              ? "border border-[#F59E0B]/40 bg-[#F59E0B]/15 text-[#FBBF24]"
                              : "bg-[#00D084] text-[#020B18] hover:bg-[#20E39A]"
                          }`}
                        >
                          {isEmergency ? "End Priority" : "Priority Sim"}
                        </button>
                        <button
                          type="button"
                          onClick={() => setSelectedSignal(sig)}
                          className="inline-flex items-center gap-1 rounded-lg border border-[#1D3552] bg-[#0D1D32] px-2.5 py-1 text-[11px] font-medium text-[#F1F5F9] hover:border-[#24A8FF]"
                        >
                          <SlidersHorizontal size={12} />
                          Details
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filtered.map((sig) => {
            const isEmergency = sig.mode === "Emergency Priority";
            return (
              <article
                key={sig.id}
                className="flex flex-col justify-between rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <span className="font-mono text-[11px] text-[#24A8FF]">{sig.signalId}</span>
                      <h2 className="text-[16px] font-semibold text-[#F1F5F9]">{sig.location}</h2>
                      <p className="text-[11px] text-[#94A3B8]">{sig.zone}</p>
                    </div>
                    <StatusBadge
                      label={sig.status}
                      tone={sig.status === "Offline" ? "neutral" : "active"}
                    />
                  </div>

                  <div className="mt-4 flex items-center justify-between rounded-xl border border-[#1D3552] bg-[#061326] p-3">
                    <div className="flex items-center gap-2">
                      {(["RED", "YELLOW", "GREEN"] as SignalLight[]).map((l) => (
                        <span
                          key={l}
                          className={`h-3.5 w-3.5 rounded-full ${
                            sig.currentLight === l
                              ? l === "GREEN"
                                ? "bg-[#20E39A] shadow-[0_0_8px_#20E39A]"
                                : l === "YELLOW"
                                  ? "bg-[#F59E0B] shadow-[0_0_8px_#F59E0B]"
                                  : "bg-[#EF4444] shadow-[0_0_8px_#EF4444]"
                              : "bg-[#1D3552]"
                          }`}
                        />
                      ))}
                    </div>
                    <span className="font-mono text-[15px] font-bold text-[#F1F5F9]">
                      {sig.status === "Offline" ? "--:--" : formatSec(sig.countdownSeconds)}
                    </span>
                  </div>

                  <div className="mt-3 flex items-center justify-between text-[12px]">
                    <span className="text-[#94A3B8]">Density: {sig.trafficDensity}</span>
                    <span className={isEmergency ? "text-[#20E39A] font-semibold" : "text-[#94A3B8]"}>
                      {sig.mode}
                    </span>
                  </div>
                </div>

                <div className="mt-4 flex gap-2">
                  <button
                    type="button"
                    disabled={sig.status === "Offline"}
                    onClick={() =>
                      setConfirmAction({
                        open: true,
                        signal: sig,
                        action: isEmergency ? "priority_off" : "priority_on",
                      })
                    }
                    className="flex-1 rounded-xl bg-[#00D084] py-1.5 text-[12px] font-semibold text-[#020B18] hover:bg-[#20E39A] disabled:opacity-40"
                  >
                    {isEmergency ? "Disable Priority" : "Priority Green"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedSignal(sig)}
                    className="rounded-xl border border-[#1D3552] bg-[#0D1D32] px-3 py-1.5 text-[12px] text-[#F1F5F9] hover:border-[#24A8FF]"
                  >
                    Inspect
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}

      {/* Signal Detail Modal */}
      {activeModalSignal && (
        <div
          className="fixed inset-0 z-[1190] flex items-center justify-center bg-[#020B18]/80 p-4 backdrop-blur-xs"
          role="dialog"
          aria-modal="true"
          aria-label={`Signal details for ${activeModalSignal.location}`}
        >
          <div className="w-full max-w-lg rounded-2xl border border-[#1D3552] bg-[#0A1729] p-6 shadow-2xl">
            <div className="flex items-start justify-between border-b border-[#1D3552] pb-3">
              <div>
                <span className="font-mono text-[12px] text-[#24A8FF]">
                  {activeModalSignal.signalId}
                </span>
                <h3 className="text-[18px] font-bold text-[#F1F5F9]">
                  {activeModalSignal.location} Junction
                </h3>
                <p className="text-[12px] text-[#94A3B8]">{activeModalSignal.zone}</p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedSignal(null)}
                aria-label="Close modal"
                className="rounded-lg p-1.5 text-[#94A3B8] hover:bg-[#0D1D32]"
              >
                <X size={18} />
              </button>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3 text-[12px]">
              <div className="rounded-xl border border-[#1D3552] bg-[#061326] p-3">
                <span className="text-[#94A3B8]">GPS Coordinates</span>
                <div className="mt-1 flex items-center gap-1 font-medium text-[#F1F5F9]">
                  <MapPin size={13} className="text-[#24A8FF]" />
                  {activeModalSignal.position.lat.toFixed(4)}, {activeModalSignal.position.lng.toFixed(4)}
                </div>
              </div>
              <div className="rounded-xl border border-[#1D3552] bg-[#061326] p-3">
                <span className="text-[#94A3B8]">Traffic Volume</span>
                <div className="mt-1 font-semibold text-[#F1F5F9]">
                  {activeModalSignal.trafficVolumePerHour} vehicles/hr
                </div>
              </div>
              <div className="rounded-xl border border-[#1D3552] bg-[#061326] p-3">
                <span className="text-[#94A3B8]">Current State &amp; Cycle</span>
                <div className="mt-1 font-semibold text-[#20E39A]">
                  {activeModalSignal.currentLight} • G:{activeModalSignal.cycleTiming.green}s / Y:{activeModalSignal.cycleTiming.yellow}s / R:{activeModalSignal.cycleTiming.red}s
                </div>
              </div>
              <div className="rounded-xl border border-[#1D3552] bg-[#061326] p-3">
                <span className="text-[#94A3B8]">Connected Status</span>
                <div className="mt-1 flex items-center gap-1.5 font-medium text-[#F1F5F9]">
                  <Radio size={13} className="text-[#F59E0B]" />
                  {activeModalSignal.hardwareConnected ? "ESP32 Connected" : "Simulation Only"}
                </div>
              </div>
            </div>

            <div className="mt-3 text-[12px] text-[#94A3B8]">
              Last Maintenance: <strong className="text-[#F1F5F9]">{activeModalSignal.lastMaintenance}</strong>
              {" • "}Affected Routes:{" "}
              <strong className="text-[#F1F5F9]">
                {activeModalSignal.affectedRoutes.join(", ")}
              </strong>
            </div>

            <div className="mt-4 rounded-xl border border-[#1D3552] bg-[#0D1D32] p-3">
              <div className="mb-2 text-[12px] font-semibold text-[#F1F5F9]">
                Safe Simulated Controls
              </div>
              <div className="grid grid-cols-3 gap-2">
                {(["RED", "YELLOW", "GREEN"] as SignalLight[]).map((phase) => (
                  <button
                    key={phase}
                    type="button"
                    disabled={activeModalSignal.status === "Offline"}
                    onClick={() =>
                      setConfirmAction({
                        open: true,
                        signal: activeModalSignal,
                        action: "phase",
                        phase,
                      })
                    }
                    className={`rounded-lg border py-2 text-[12px] font-semibold transition disabled:opacity-40 ${
                      activeModalSignal.currentLight === phase
                        ? "border-[#20E39A] bg-[#00D084]/20 text-[#20E39A]"
                        : "border-[#1D3552] bg-[#061326] text-[#F1F5F9] hover:border-[#24A8FF]"
                    }`}
                  >
                    Set {phase}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-3 flex items-center gap-2 rounded-xl border border-[#F59E0B]/35 bg-[#F59E0B]/10 p-2.5 text-[11px] text-[#FBBF24]">
              <AlertTriangle size={14} className="shrink-0" />
              <span>
                Simulated control only — no public road traffic signal hardware is modified.
              </span>
            </div>
          </div>
        </div>
      )}

      <ConfirmModal
        open={confirmAction.open}
        title={
          confirmAction.action === "priority_on"
            ? `Activate Emergency Priority Simulation?`
            : confirmAction.action === "priority_off"
              ? `Restore Automatic Signal Cycle?`
              : `Simulate ${confirmAction.phase} Phase?`
        }
        description={
          confirmAction.signal
            ? `Target Junction: ${confirmAction.signal.location} (${confirmAction.signal.signalId}).`
            : ""
        }
        warning="This executes a safe software simulation only. No physical road signal is controlled."
        confirmLabel="Confirm Simulation"
        variant="warning"
        onConfirm={executeConfirmedAction}
        onCancel={() => setConfirmAction({ open: false, signal: null, action: "priority_on" })}
      />
    </div>
  );
}
