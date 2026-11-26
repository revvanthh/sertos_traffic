import { Ambulance, Check } from "lucide-react";
import { usePoliceControl } from "../../context/PoliceControlContext";
import type { AmbulanceStage } from "../../types/police";

const STAGE_ORDER: AmbulanceStage[] = [
  "Dispatched",
  "En Route",
  "Approaching Hospital",
  "Arrived",
];

export function RouteStatusPanel() {
  const { selectedAmbulance } = usePoliceControl();

  const activeIdx =
    selectedAmbulance.status === "Completed"
      ? 3
      : Math.max(0, STAGE_ORDER.indexOf(selectedAmbulance.status));

  const stages = [
    { label: "Dispatched", time: selectedAmbulance.timestamps.dispatched },
    { label: "On Route", time: selectedAmbulance.timestamps.onRoute },
    { label: "Arriving Soon", time: selectedAmbulance.timestamps.arrivingSoon },
    { label: "Hospital Arrived", time: selectedAmbulance.timestamps.hospitalArrived },
  ];

  return (
    <section className="rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4 shadow-lg">
      <div className="flex items-center justify-between border-b border-[#1D3552] pb-2">
        <h2 className="text-[15px] font-semibold text-[#F1F5F9]">Route Status</h2>
        <span className="text-[11px] font-medium text-[#20E39A]">
          {selectedAmbulance.ambulanceId}
        </span>
      </div>

      <div className="mt-4">
        {/* Progress bar & nodes */}
        <div className="relative flex items-center justify-between px-2">
          <div className="absolute left-6 right-6 top-1/2 h-[3px] -translate-y-1/2 rounded-full bg-[#1D3552]" />
          <div
            className="absolute left-6 top-1/2 h-[3px] -translate-y-1/2 rounded-full bg-[#20E39A] transition-all duration-500"
            style={{ width: `calc(${(activeIdx / 3) * 100}% - 24px)` }}
          />

          {stages.map((stage, idx) => {
            const isCompleted = idx < activeIdx || (idx === 3 && activeIdx === 3);
            const isCurrent = idx === activeIdx && idx < 3;
            const isFuture = idx > activeIdx;

            if (idx === 3 && activeIdx < 3) {
              return (
                <div
                  key={stage.label}
                  className="relative z-10 flex h-8 w-8 items-center justify-center rounded-xl border border-[#1D3552] bg-[#0D1D32] text-[#94A3B8]"
                  title="Destination Hospital"
                >
                  <Ambulance size={16} className="text-[#24A8FF]" />
                </div>
              );
            }

            return (
              <div
                key={stage.label}
                className={`relative z-10 flex h-6 w-6 items-center justify-center rounded-full border transition ${
                  isCompleted
                    ? "border-[#20E39A] bg-[#00D084] text-[#020B18]"
                    : isCurrent
                      ? "border-[#20E39A] bg-[#00D084] text-[#020B18] shadow-[0_0_12px_#20E39A]"
                      : isFuture
                        ? "border-[#1D3552] bg-[#0D1D32] text-[#94A3B8]"
                        : ""
                }`}
              >
                <Check size={13} strokeWidth={3} />
              </div>
            );
          })}
        </div>

        {/* Stage Labels & Timestamps */}
        <div className="mt-2.5 grid grid-cols-4 gap-1 text-center">
          {stages.map((stage, idx) => {
            const isFuture = idx > activeIdx;
            return (
              <div key={stage.label} className="min-w-0">
                <div
                  className={`truncate text-[11px] font-semibold ${
                    isFuture ? "text-[#94A3B8]/60" : "text-[#F1F5F9]"
                  }`}
                >
                  {stage.label}
                </div>
                <div className="text-[10px] text-[#94A3B8]">{stage.time}</div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
