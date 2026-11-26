import { AlertOctagon, ClipboardList, ExternalLink } from "lucide-react";
import { usePoliceControl } from "../../context/PoliceControlContext";
import { StatusBadge } from "../common/StatusBadge";

interface EmergencyDetailsPanelProps {
  onOpenDetails: () => void;
}

export function EmergencyDetailsPanel({ onOpenDetails }: EmergencyDetailsPanelProps) {
  const { selectedEmergency, selectedAmbulance, authMode } = usePoliceControl();

  const isLive = authMode === "live" && selectedEmergency.source === "live";

  return (
    <section className="rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4 shadow-lg">
      <div className="flex items-center justify-between gap-2 border-b border-[#1D3552] pb-2.5">
        <div className="flex items-center gap-2">
          <ClipboardList size={17} className="text-[#94A3B8]" />
          <h2 className="text-[15px] font-semibold text-[#F1F5F9]">Emergency Details</h2>
        </div>
        <StatusBadge
          label={isLive ? "LIVE" : "DEMO"}
          tone={isLive ? "critical" : "demo"}
          pulse
        />
      </div>

      <div className="mt-3 flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[#EF4444]/40 bg-[#EF4444] text-white shadow-[0_0_14px_rgba(239,68,68,0.35)]">
          <AlertOctagon size={20} />
        </div>

        <dl className="min-w-0 flex-1 space-y-1 text-[12px]">
          <div className="grid grid-cols-[88px_1fr] gap-2">
            <dt className="text-[#94A3B8]">Incident ID</dt>
            <dd className="truncate font-semibold text-[#F1F5F9]">
              : {selectedEmergency.incidentId}
            </dd>
          </div>
          <div className="grid grid-cols-[88px_1fr] gap-2">
            <dt className="text-[#94A3B8]">Type</dt>
            <dd className="truncate font-medium text-[#F1F5F9]">: {selectedEmergency.type}</dd>
          </div>
          <div className="grid grid-cols-[88px_1fr] gap-2">
            <dt className="text-[#94A3B8]">Patient</dt>
            <dd className="truncate text-[#F1F5F9]">: {selectedEmergency.patientLabel}</dd>
          </div>
          <div className="grid grid-cols-[88px_1fr] gap-2">
            <dt className="text-[#94A3B8]">Hospital</dt>
            <dd className="truncate font-medium text-[#F1F5F9]">
              : {selectedEmergency.hospitalName}
            </dd>
          </div>
          <div className="grid grid-cols-[88px_1fr] items-center gap-2">
            <dt className="text-[#94A3B8]">Priority</dt>
            <dd className="flex items-center gap-1.5">
              <span>:</span>
              <span
                className={`rounded px-2 py-0.5 text-[11px] font-semibold ${
                  selectedEmergency.priority === "Critical"
                    ? "bg-[#EF4444] text-white"
                    : selectedEmergency.priority === "High"
                      ? "bg-[#F59E0B] text-[#020B18]"
                      : "bg-[#24A8FF]/20 text-[#24A8FF]"
                }`}
              >
                {selectedEmergency.priority}
              </span>
            </dd>
          </div>
          <div className="grid grid-cols-[88px_1fr] gap-2">
            <dt className="text-[#94A3B8]">Ambulance</dt>
            <dd className="truncate text-[#24A8FF] font-semibold">
              : {selectedEmergency.ambulanceId} • {selectedAmbulance.etaMinutes} min •{" "}
              {selectedAmbulance.distanceKm} km
            </dd>
          </div>
        </dl>
      </div>

      <button
        type="button"
        onClick={onOpenDetails}
        className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl border border-[#1D3552] bg-[#0D1D32] py-2 text-[12px] font-semibold text-[#F1F5F9] transition hover:border-[#24A8FF]/60 hover:text-[#24A8FF]"
      >
        View Details
        <ExternalLink size={13} />
      </button>
    </section>
  );
}
