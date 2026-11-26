import { useState } from "react";
import {
  CheckCircle2,
  Loader2,
  Navigation,
  Radio,
  ShieldCheck,
  X,
} from "lucide-react";
import { usePoliceControl } from "../../context/PoliceControlContext";
import type { PoliceActionItem } from "../../types/police";
import { ConfirmModal } from "../common/ConfirmModal";

export function PoliceActionsPanel() {
  const {
    policeActions,
    selectedEmergency,
    executeClearRouteAction,
  } = usePoliceControl();

  const [selectedAction, setSelectedAction] = useState<PoliceActionItem | null>(null);
  const [confirmClearOpen, setConfirmClearOpen] = useState(false);
  const [simulationModal, setSimulationModal] = useState<{
    open: boolean;
    step: number;
    affectedSignals: string[];
    notifiedUnits: string[];
  }>({
    open: false,
    step: 0,
    affectedSignals: ["MG Road (BLR-SIG-01)", "Trinity Circle (BLR-SIG-03)", "Indiranagar (BLR-SIG-06)"],
    notifiedUnits: ["PCR-BLR-04", "TP-MGR-12", "TP-IND-07"],
  });

  const handleConfirmClearRoute = async () => {
    setConfirmClearOpen(false);
    setSimulationModal({
      open: true,
      step: 1,
      affectedSignals: ["MG Road (BLR-SIG-01)", "Trinity Circle (BLR-SIG-03)", "Indiranagar (BLR-SIG-06)"],
      notifiedUnits: ["PCR-BLR-04", "TP-MGR-12", "TP-IND-07"],
    });

    window.setTimeout(() => {
      setSimulationModal((prev) => ({ ...prev, step: 2 }));
    }, 550);

    window.setTimeout(async () => {
      const result = await executeClearRouteAction(selectedEmergency.incidentId);
      setSimulationModal({
        open: true,
        step: 3,
        affectedSignals: result.affectedSignals,
        notifiedUnits: result.notifiedUnits,
      });
    }, 1150);
  };

  return (
    <section className="rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4 shadow-lg">
      <div className="flex items-center justify-between border-b border-[#1D3552] pb-2.5">
        <div className="flex items-center gap-2">
          <ShieldCheck size={17} className="text-[#94A3B8]" />
          <h2 className="text-[15px] font-semibold text-[#F1F5F9]">Police Actions</h2>
        </div>
        <span className="text-[11px] text-[#94A3B8]">{policeActions.length} logged</span>
      </div>

      {/* Action History List */}
      <div className="mt-2.5 max-h-[145px] space-y-1.5 overflow-y-auto pr-1">
        {policeActions.slice(0, 5).map((action) => (
          <button
            key={action.id}
            type="button"
            onClick={() => setSelectedAction(action)}
            className="flex w-full items-center gap-2.5 rounded-xl border border-transparent px-2 py-1.5 text-left transition hover:border-[#1D3552] hover:bg-[#0D1D32]"
          >
            {action.status === "completed" ? (
              <CheckCircle2 size={17} className="shrink-0 text-[#20E39A]" />
            ) : (
              <Loader2 size={17} className="shrink-0 animate-spin text-[#24A8FF]" />
            )}
            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] font-medium text-[#F1F5F9]">
                {action.title}
              </div>
            </div>
            <span className="shrink-0 text-[10px] text-[#94A3B8]">Details</span>
          </button>
        ))}
      </div>

      {/* Clear Emergency Route CTA */}
      <button
        type="button"
        onClick={() => setConfirmClearOpen(true)}
        className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-[#00D084] py-2 text-[13px] font-semibold text-[#020B18] shadow-[0_0_16px_rgba(0,208,132,0.25)] transition hover:bg-[#20E39A]"
      >
        <Navigation size={15} />
        Clear Emergency Route
      </button>

      {/* Action Details Modal */}
      {selectedAction && (
        <div
          className="fixed inset-0 z-[1190] flex items-center justify-center bg-[#020B18]/80 p-4 backdrop-blur-xs"
          role="dialog"
          aria-modal="true"
          aria-label="Police Action Details"
        >
          <div className="w-full max-w-md rounded-2xl border border-[#1D3552] bg-[#0A1729] p-5 shadow-2xl">
            <div className="flex items-start justify-between gap-2 border-b border-[#1D3552] pb-3">
              <div>
                <h3 className="text-[16px] font-semibold text-[#F1F5F9]">
                  {selectedAction.title}
                </h3>
                <p className="text-[11px] text-[#94A3B8]">
                  {selectedAction.timestamp} • {selectedAction.performedBy}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedAction(null)}
                aria-label="Close action details"
                className="rounded-lg p-1 text-[#94A3B8] hover:bg-[#0D1D32]"
              >
                <X size={18} />
              </button>
            </div>
            <p className="mt-3 text-[13px] leading-relaxed text-[#94A3B8]">
              {selectedAction.details}
            </p>
            {selectedAction.affectedSignals && selectedAction.affectedSignals.length > 0 && (
              <div className="mt-3">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-[#94A3B8]">
                  Affected Signals
                </div>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {selectedAction.affectedSignals.map((sig) => (
                    <span
                      key={sig}
                      className="rounded-md border border-[#1D3552] bg-[#0D1D32] px-2 py-0.5 text-[11px] text-[#20E39A]"
                    >
                      {sig}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {selectedAction.notifiedUnits && selectedAction.notifiedUnits.length > 0 && (
              <div className="mt-3">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-[#94A3B8]">
                  Police Units Notified
                </div>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {selectedAction.notifiedUnits.map((unit) => (
                    <span
                      key={unit}
                      className="rounded-md border border-[#1D3552] bg-[#0D1D32] px-2 py-0.5 text-[11px] text-[#24A8FF]"
                    >
                      {unit}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Step 1: Confirmation Modal */}
      <ConfirmModal
        open={confirmClearOpen}
        title="Confirm Emergency Route Clearance"
        description={`Execute simulated green corridor optimization for ${selectedEmergency.incidentId} (${selectedEmergency.ambulanceId} -> ${selectedEmergency.hospitalName})?`}
        warning="Demo / Simulation Action: Evaluates affected corridor junctions and dispatches simulated priority advisories without controlling physical street signals."
        confirmLabel="Execute Route Clearance"
        variant="primary"
        onConfirm={() => void handleConfirmClearRoute()}
        onCancel={() => setConfirmClearOpen(false)}
      />

      {/* Steps 2-7: Simulated Route Analysis & Progress Modal */}
      {simulationModal.open && (
        <div
          className="fixed inset-0 z-[1195] flex items-center justify-center bg-[#020B18]/80 p-4 backdrop-blur-xs"
          role="dialog"
          aria-modal="true"
          aria-label="Route Clearance Simulation Progress"
        >
          <div className="w-full max-w-lg rounded-2xl border border-[#1D3552] bg-[#0A1729] p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#1D3552] pb-3">
              <div className="flex items-center gap-2.5">
                <Radio size={18} className="text-[#20E39A]" />
                <h3 className="text-[16px] font-semibold text-[#F1F5F9]">
                  Corridor Optimization Progress
                </h3>
              </div>
              {simulationModal.step >= 3 && (
                <button
                  type="button"
                  onClick={() => setSimulationModal((p) => ({ ...p, open: false }))}
                  aria-label="Close progress modal"
                  className="rounded-lg p-1 text-[#94A3B8] hover:bg-[#0D1D32]"
                >
                  <X size={18} />
                </button>
              )}
            </div>

            <div className="mt-4 space-y-3 text-[12px]">
              <div className="flex items-center gap-2.5">
                {simulationModal.step >= 2 ? (
                  <CheckCircle2 size={16} className="text-[#20E39A]" />
                ) : (
                  <Loader2 size={16} className="animate-spin text-[#24A8FF]" />
                )}
                <span className="text-[#F1F5F9]">
                  Analyzing active corridor route for {selectedEmergency.ambulanceId}...
                </span>
              </div>

              <div className="rounded-xl border border-[#1D3552] bg-[#0D1D32] p-3">
                <div className="font-semibold text-[#F1F5F9]">Affected Signal Locations</div>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {simulationModal.affectedSignals.map((sig) => (
                    <span
                      key={sig}
                      className="rounded-md border border-[#00D084]/40 bg-[#00D084]/15 px-2 py-0.5 text-[11px] text-[#20E39A]"
                    >
                      {sig}
                    </span>
                  ))}
                </div>
              </div>

              <div className="rounded-xl border border-[#1D3552] bg-[#0D1D32] p-3">
                <div className="font-semibold text-[#F1F5F9]">Police Units Notified</div>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {simulationModal.notifiedUnits.map((unit) => (
                    <span
                      key={unit}
                      className="rounded-md border border-[#24A8FF]/40 bg-[#24A8FF]/15 px-2 py-0.5 text-[11px] text-[#24A8FF]"
                    >
                      {unit}
                    </span>
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-2.5">
                {simulationModal.step >= 3 ? (
                  <CheckCircle2 size={16} className="text-[#20E39A]" />
                ) : (
                  <Loader2 size={16} className="animate-spin text-[#24A8FF]" />
                )}
                <span className="font-medium text-[#20E39A]">
                  {simulationModal.step >= 3
                    ? "Simulated green corridor completed and logged to Police Actions."
                    : "Applying simulated phase optimization..."}
                </span>
              </div>
            </div>

            {simulationModal.step >= 3 && (
              <div className="mt-5 flex justify-end">
                <button
                  type="button"
                  onClick={() => setSimulationModal((p) => ({ ...p, open: false }))}
                  className="rounded-xl bg-[#00D084] px-4 py-2 text-[13px] font-semibold text-[#020B18] hover:bg-[#20E39A]"
                >
                  Done
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
