import { useState } from "react";
import { AlertTriangle, Info, ShieldAlert, SlidersHorizontal, X } from "lucide-react";
import { usePoliceControl } from "../../context/PoliceControlContext";
import type { SignalLight } from "../../types/police";
import { ConfirmModal } from "../common/ConfirmModal";
import { StatusBadge } from "../common/StatusBadge";

function formatCountdown(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function TrafficSignalControlPanel() {
  const { signals, toggleSignalEmergencyMode, switchSignalLight } = usePoliceControl();
  const mgSignal = signals.find((s) => s.id === "sig-mg-road") ?? signals[0];

  const [detailsOpen, setDetailsOpen] = useState(false);
  const [confirmState, setConfirmState] = useState<{
    open: boolean;
    type: "priority_on" | "priority_off" | "switch_light";
    light?: SignalLight;
  }>({ open: false, type: "priority_on" });

  if (!mgSignal) return null;

  const isEmergencyMode = mgSignal.mode === "Emergency Priority";

  const handleConfirm = () => {
    if (confirmState.type === "priority_on") {
      toggleSignalEmergencyMode(mgSignal.id, true);
    } else if (confirmState.type === "priority_off") {
      toggleSignalEmergencyMode(mgSignal.id, false);
    } else if (confirmState.type === "switch_light" && confirmState.light) {
      switchSignalLight(mgSignal.id, confirmState.light);
    }
    setConfirmState({ open: false, type: "priority_on" });
  };

  return (
    <section className="rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4 shadow-lg">
      <div className="flex items-center justify-between gap-2 border-b border-[#1D3552] pb-2.5">
        <div className="flex items-center gap-2">
          <h2 className="text-[15px] font-semibold text-[#F1F5F9]">
            Traffic Signal Control
          </h2>
        </div>
        <div className="flex items-center gap-1.5">
          {!mgSignal.hardwareConnected && (
            <span className="rounded border border-[#F59E0B]/40 bg-[#F59E0B]/10 px-1.5 py-0.5 text-[10px] font-semibold text-[#FBBF24]">
              SIM
            </span>
          )}
          <StatusBadge label={mgSignal.status} tone="active" />
        </div>
      </div>

      {/* Main Signal Row matching reference image */}
      <div className="mt-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          {/* Vertical 3-bulb Traffic Light Visual */}
          <div
            className="flex flex-col items-center gap-1.5 rounded-xl border border-[#1D3552] bg-[#040E1E] p-1.5"
            aria-label={`Traffic light currently ${mgSignal.currentLight}`}
          >
            <span
              className={`h-3.5 w-3.5 rounded-full transition ${
                mgSignal.currentLight === "RED"
                  ? "bg-[#EF4444] shadow-[0_0_10px_#EF4444]"
                  : "bg-[#EF4444]/20"
              }`}
            />
            <span
              className={`h-3.5 w-3.5 rounded-full transition ${
                mgSignal.currentLight === "YELLOW"
                  ? "bg-[#F59E0B] shadow-[0_0_10px_#F59E0B]"
                  : "bg-[#F59E0B]/20"
              }`}
            />
            <span
              className={`h-3.5 w-3.5 rounded-full transition ${
                mgSignal.currentLight === "GREEN"
                  ? "bg-[#20E39A] shadow-[0_0_10px_#20E39A]"
                  : "bg-[#20E39A]/20"
              }`}
            />
          </div>

          <div className="min-w-0">
            <div className="truncate text-[13px] font-semibold text-[#F1F5F9]">
              Signal at {mgSignal.location}
            </div>
            <div className="mt-0.5 text-[12px] text-[#94A3B8]">
              {isEmergencyMode ? (
                <span className="font-medium text-[#20E39A]">
                  Priority Green — Emergency Route
                </span>
              ) : (
                <span>
                  Set to{" "}
                  <strong className="text-[#F1F5F9]">{mgSignal.currentLight}</strong> (
                  {mgSignal.mode})
                </span>
              )}
            </div>
            <div className="mt-0.5 text-[10px] text-[#94A3B8]">
              ID: {mgSignal.signalId} •{" "}
              {mgSignal.hardwareConnected ? "ESP32 Telemetry" : "Simulation Mode"}
            </div>
          </div>
        </div>

        {/* Digital Countdown */}
        <div className="shrink-0 rounded-xl border border-[#1D3552] bg-[#0D1D32] px-3 py-2 text-center">
          <div className="font-mono text-[16px] font-bold tracking-wider text-[#F1F5F9]">
            {formatCountdown(mgSignal.countdownSeconds)}
          </div>
        </div>
      </div>

      {/* Simulation Warning */}
      {!mgSignal.hardwareConnected && (
        <div className="mt-3 flex items-center gap-2 rounded-lg border border-[#F59E0B]/30 bg-[#F59E0B]/10 px-2.5 py-1.5 text-[11px] text-[#FBBF24]">
          <AlertTriangle size={13} className="shrink-0" />
          <span>Simulation active — no physical road signal hardware connected.</span>
        </div>
      )}

      {/* Safe Interactive Controls */}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() =>
            setConfirmState({
              open: true,
              type: isEmergencyMode ? "priority_off" : "priority_on",
            })
          }
          className={`flex-1 rounded-xl px-3 py-1.5 text-[12px] font-semibold transition ${
            isEmergencyMode
              ? "border border-[#F59E0B]/50 bg-[#F59E0B]/15 text-[#FBBF24] hover:bg-[#F59E0B]/25"
              : "bg-[#00D084] text-[#020B18] hover:bg-[#20E39A]"
          }`}
        >
          {isEmergencyMode ? "Disable Priority Sim" : "Activate Priority Green"}
        </button>
        <button
          type="button"
          onClick={() => setDetailsOpen(true)}
          className="inline-flex items-center gap-1 rounded-xl border border-[#1D3552] bg-[#0D1D32] px-3 py-1.5 text-[12px] font-medium text-[#F1F5F9] hover:border-[#24A8FF]"
        >
          <SlidersHorizontal size={13} />
          Controls
        </button>
      </div>

      {/* Signal Detail & Safe State Switch Modal */}
      {detailsOpen && (
        <div
          className="fixed inset-0 z-[1190] flex items-center justify-center bg-[#020B18]/80 p-4 backdrop-blur-xs"
          role="dialog"
          aria-modal="true"
          aria-label="Signal Control Details"
        >
          <div className="w-full max-w-md rounded-2xl border border-[#1D3552] bg-[#0A1729] p-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#1D3552] pb-3">
              <div>
                <h3 className="text-[16px] font-semibold text-[#F1F5F9]">
                  {mgSignal.location} ({mgSignal.signalId})
                </h3>
                <p className="text-[12px] text-[#94A3B8]">{mgSignal.zone}</p>
              </div>
              <button
                type="button"
                onClick={() => setDetailsOpen(false)}
                aria-label="Close signal details"
                className="rounded-lg p-1 text-[#94A3B8] hover:bg-[#0D1D32]"
              >
                <X size={18} />
              </button>
            </div>

            <div className="mt-4 space-y-2.5 text-[12px]">
              <div className="flex justify-between">
                <span className="text-[#94A3B8]">Status</span>
                <span className="font-semibold text-[#20E39A]">{mgSignal.status}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#94A3B8]">Current Phase</span>
                <span className="font-semibold text-[#F1F5F9]">{mgSignal.currentLight}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#94A3B8]">Mode</span>
                <span className="font-semibold text-[#24A8FF]">{mgSignal.mode}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#94A3B8]">Remaining Countdown</span>
                <span className="font-mono font-bold text-[#F1F5F9]">
                  {formatCountdown(mgSignal.countdownSeconds)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#94A3B8]">GPS Coordinates</span>
                <span className="text-[#F1F5F9]">
                  {mgSignal.position.lat.toFixed(4)}, {mgSignal.position.lng.toFixed(4)}
                </span>
              </div>
            </div>

            <div className="mt-4 rounded-xl border border-[#1D3552] bg-[#0D1D32] p-3">
              <div className="mb-2 flex items-center gap-1.5 text-[12px] font-semibold text-[#F1F5F9]">
                <Info size={14} className="text-[#24A8FF]" />
                Simulate Signal State Change
              </div>
              <div className="grid grid-cols-3 gap-2">
                {(["RED", "YELLOW", "GREEN"] as SignalLight[]).map((light) => (
                  <button
                    key={light}
                    type="button"
                    onClick={() => {
                      setDetailsOpen(false);
                      setConfirmState({ open: true, type: "switch_light", light });
                    }}
                    className={`rounded-lg border py-2 text-[12px] font-semibold transition ${
                      mgSignal.currentLight === light
                        ? "border-[#20E39A] bg-[#00D084]/20 text-[#20E39A]"
                        : "border-[#1D3552] bg-[#0A1729] text-[#F1F5F9] hover:border-[#24A8FF]"
                    }`}
                  >
                    {light}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-3 flex items-start gap-2 rounded-xl border border-[#F59E0B]/35 bg-[#F59E0B]/10 p-3 text-[11px] text-[#FBBF24]">
              <ShieldAlert size={15} className="mt-0.5 shrink-0" />
              <span>
                This action updates the SERTOS digital simulation only. Physical road intersections require certified hardware integration.
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Dialog */}
      <ConfirmModal
        open={confirmState.open}
        title={
          confirmState.type === "priority_on"
            ? `Simulate Priority Green at ${mgSignal.location}?`
            : confirmState.type === "priority_off"
              ? `Restore Automatic Cycle at ${mgSignal.location}?`
              : `Switch Simulated Phase to ${confirmState.light}?`
        }
        description={
          confirmState.type === "priority_on"
            ? "This activates a 45-second Emergency Priority Green simulation for the MG Road emergency corridor."
            : confirmState.type === "priority_off"
              ? "This disables the emergency priority simulation and returns the intersection to standard cycle timing."
              : `Confirm simulated transition of ${mgSignal.signalId} (${mgSignal.location}) to ${confirmState.light}.`
        }
        warning="Simulation Notice: No physical traffic signal hardware is directly controlled unless verified ESP32/controller hardware is connected."
        confirmLabel="Confirm Simulation Action"
        variant="warning"
        onConfirm={handleConfirm}
        onCancel={() => setConfirmState({ open: false, type: "priority_on" })}
      />
    </section>
  );
}
