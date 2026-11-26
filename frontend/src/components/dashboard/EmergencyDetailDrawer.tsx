import { useEffect } from "react";
import {
  Ambulance,
  CheckCircle2,
  Clock,
  Hospital,
  MapPin,
  ShieldCheck,
  User,
  X,
} from "lucide-react";
import { usePoliceControl } from "../../context/PoliceControlContext";
import type { EmergencyAlert } from "../../types/police";
import { StatusBadge } from "../common/StatusBadge";

interface EmergencyDetailDrawerProps {
  alert: EmergencyAlert | null;
  onClose: () => void;
}

export function EmergencyDetailDrawer({ alert, onClose }: EmergencyDetailDrawerProps) {
  const {
    ambulances,
    policeUnits,
    acknowledgeAlert,
    assignPoliceUnit,
    notifyNearbyUnits,
  } = usePoliceControl();

  useEffect(() => {
    if (!alert) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [alert, onClose]);

  if (!alert) return null;

  const matchedAmbulance =
    ambulances.find((a) => a.incidentId === alert.incidentId) ?? ambulances[0];

  return (
    <div className="fixed inset-0 z-[1180] flex justify-end bg-[#020B18]/75 backdrop-blur-xs">
      <div
        className="flex h-full w-full max-w-lg flex-col border-l border-[#1D3552] bg-[#061326] shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-label={`Emergency details for ${alert.incidentId}`}
      >
        <div className="flex items-center justify-between border-b border-[#1D3552] px-5 py-4">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-[18px] font-bold text-[#F1F5F9]">{alert.incidentId}</h2>
              <StatusBadge
                label={alert.priority}
                tone={alert.priority === "Critical" ? "critical" : "warning"}
              />
              <StatusBadge
                label={alert.source === "live" ? "LIVE" : "DEMO"}
                tone={alert.source === "live" ? "live" : "demo"}
              />
            </div>
            <p className="mt-0.5 text-[12px] text-[#94A3B8]">{alert.type}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close details drawer"
            className="rounded-lg p-1.5 text-[#94A3B8] hover:bg-[#0D1D32] hover:text-[#F1F5F9]"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          {/* Patient & Condition */}
          <div className="rounded-xl border border-[#1D3552] bg-[#0A1729] p-4 space-y-2.5">
            <div className="flex items-center gap-2 text-[13px] font-semibold text-[#F1F5F9]">
              <User size={16} className="text-[#24A8FF]" />
              Patient &amp; Condition Summary
            </div>
            <div className="grid grid-cols-2 gap-3 text-[12px]">
              <div>
                <span className="text-[#94A3B8]">Patient:</span>
                <div className="font-medium text-[#F1F5F9]">{alert.patientLabel}</div>
              </div>
              <div>
                <span className="text-[#94A3B8]">Alert Status:</span>
                <div className="font-medium text-[#20E39A]">{alert.status}</div>
              </div>
            </div>
            <p className="text-[12px] leading-relaxed text-[#94A3B8]">{alert.condition}</p>
          </div>

          {/* Ambulance, Hospital & Route */}
          <div className="rounded-xl border border-[#1D3552] bg-[#0A1729] p-4 space-y-3">
            <div className="flex items-center gap-2 text-[13px] font-semibold text-[#F1F5F9]">
              <Ambulance size={16} className="text-[#20E39A]" />
              Ambulance &amp; Route Information
            </div>
            <div className="grid grid-cols-2 gap-3 text-[12px]">
              <div>
                <span className="text-[#94A3B8]">Ambulance ID</span>
                <div className="font-semibold text-[#F1F5F9]">{alert.ambulanceId}</div>
              </div>
              <div>
                <span className="text-[#94A3B8]">Ambulance Status</span>
                <div className="font-semibold text-[#20E39A]">
                  {matchedAmbulance?.status ?? alert.status}
                </div>
              </div>
              <div>
                <span className="text-[#94A3B8]">Destination Hospital</span>
                <div className="flex items-center gap-1 font-medium text-[#F1F5F9]">
                  <Hospital size={13} className="text-[#EF4444]" />
                  {alert.hospitalName}
                </div>
              </div>
              <div>
                <span className="text-[#94A3B8]">ETA / Distance</span>
                <div className="font-semibold text-[#24A8FF]">
                  {matchedAmbulance?.etaMinutes ?? alert.etaMinutes} min •{" "}
                  {matchedAmbulance?.distanceKm ?? alert.distanceKm} km
                </div>
              </div>
            </div>
            <div className="flex items-center gap-1.5 text-[12px] text-[#94A3B8]">
              <MapPin size={14} className="text-[#24A8FF]" />
              Corridor: {alert.location} ({alert.zone})
            </div>
          </div>

          {/* Police Response Status & Actions */}
          <div className="rounded-xl border border-[#1D3552] bg-[#0A1729] p-4 space-y-3">
            <div className="flex items-center gap-2 text-[13px] font-semibold text-[#F1F5F9]">
              <ShieldCheck size={16} className="text-[#20E39A]" />
              Police Response Status
            </div>
            <div className="text-[12px] text-[#F1F5F9]">{alert.policeResponseStatus}</div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => void acknowledgeAlert(alert.id)}
                disabled={alert.status !== "New"}
                className="rounded-lg bg-[#00D084] px-3 py-1.5 text-[12px] font-semibold text-[#020B18] transition hover:bg-[#20E39A] disabled:opacity-40"
              >
                {alert.status === "New" ? "Acknowledge Alert" : "Acknowledged"}
              </button>
              <button
                type="button"
                onClick={() => assignPoliceUnit(alert.id, policeUnits[0]?.callSign || "PCR-BLR-04")}
                className="rounded-lg border border-[#1D3552] bg-[#0D1D32] px-3 py-1.5 text-[12px] font-medium text-[#F1F5F9] hover:border-[#24A8FF]"
              >
                Assign Escort ({policeUnits[0]?.callSign || "PCR-BLR-04"})
              </button>
              <button
                type="button"
                onClick={() => notifyNearbyUnits(alert.id)}
                className="rounded-lg border border-[#1D3552] bg-[#0D1D32] px-3 py-1.5 text-[12px] font-medium text-[#24A8FF] hover:border-[#24A8FF]"
              >
                Notify Nearby Units
              </button>
            </div>
          </div>

          {/* Timeline of Events */}
          <div className="rounded-xl border border-[#1D3552] bg-[#0A1729] p-4">
            <div className="mb-3 flex items-center gap-2 text-[13px] font-semibold text-[#F1F5F9]">
              <Clock size={16} className="text-[#24A8FF]" />
              Timeline of Events
            </div>
            <div className="space-y-3">
              {alert.timeline.map((ev) => (
                <div key={ev.id} className="flex items-start gap-3">
                  <CheckCircle2
                    size={16}
                    className={`mt-0.5 shrink-0 ${
                      ev.status === "completed"
                        ? "text-[#20E39A]"
                        : ev.status === "active"
                          ? "text-[#24A8FF]"
                          : "text-[#94A3B8]/50"
                    }`}
                  />
                  <div className="min-w-0 flex-1 text-[12px]">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-[#F1F5F9]">{ev.label}</span>
                      <span className="text-[11px] text-[#94A3B8]">{ev.timestamp}</span>
                    </div>
                    {ev.detail && <p className="mt-0.5 text-[#94A3B8]">{ev.detail}</p>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
