import { useNavigate } from "react-router-dom";
import {
  AlertCircle,
  Ambulance,
  ArrowDown,
  Car,
  CheckCircle2,
  ChevronUp,
  Clock,
  Radio,
} from "lucide-react";
import { usePoliceControl } from "../../context/PoliceControlContext";

export function KpiRow() {
  const navigate = useNavigate();
  const { alerts, signals, analyticsSeries, authMode } = usePoliceControl();

  const totalSignals = authMode === "demo" ? 52 : Math.max(signals.length, 1);
  const offlineCount = signals.filter((s) => s.status === "Offline").length;
  const activeSignals =
    authMode === "demo"
      ? 52 - (offlineCount > 0 ? 4 : 0)
      : signals.filter((s) => s.status !== "Offline").length;
  const activeEmergenciesCount =
    authMode === "demo"
      ? Math.max(1, alerts.filter((a) => a.status === "In Progress").length)
      : alerts.filter((a) => a.status !== "Resolved").length;

  const latestMetric = analyticsSeries[analyticsSeries.length - 1] ?? {
    speed: 32,
    delay: 2.8,
  };

  return (
    <section
      className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4"
      aria-label="Key Performance Indicators"
    >
      {/* Card 1 — Active Signals */}
      <button
        type="button"
        onClick={() => navigate("/traffic-control")}
        className="group flex items-center justify-between rounded-xl border border-[#1D3552] bg-[#0A1729] px-4 py-3 text-left transition hover:border-[#00D084]/60 hover:bg-[#0D1D32]"
      >
        <div className="flex items-center gap-3.5 min-w-0">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-[#00D084]/35 bg-[#00D084]/12 text-[#20E39A]">
            <Radio size={22} />
          </div>
          <div className="min-w-0">
            <div className="text-[12px] font-medium text-[#94A3B8]">Active Signals</div>
            <div className="mt-0.5 text-[24px] font-bold leading-tight tracking-tight text-[#F1F5F9]">
              {activeSignals} / {totalSignals}
            </div>
            <div className="text-[11px] text-[#94A3B8]">
              {authMode === "demo" ? "4 Signals Offline" : `${offlineCount} Signals Offline`}
            </div>
          </div>
        </div>
        <CheckCircle2
          size={20}
          className="shrink-0 text-[#20E39A] transition-transform group-hover:scale-110"
        />
      </button>

      {/* Card 2 — Active Emergencies */}
      <button
        type="button"
        onClick={() => navigate("/emergency-alerts")}
        className="group flex items-center justify-between rounded-xl border border-[#1D3552] bg-[#0A1729] px-4 py-3 text-left transition hover:border-[#EF4444]/60 hover:bg-[#0D1D32]"
      >
        <div className="flex items-center gap-3.5 min-w-0">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-[#EF4444]/35 bg-[#EF4444]/12 text-[#EF4444]">
            <Ambulance size={22} />
          </div>
          <div className="min-w-0">
            <div className="text-[12px] font-medium text-[#94A3B8]">Active Emergencies</div>
            <div className="mt-0.5 text-[24px] font-bold leading-tight tracking-tight text-[#F1F5F9]">
              {activeEmergenciesCount}
            </div>
            <div className="text-[11px] text-[#94A3B8]">
              {alerts.filter((a) => a.status !== "Resolved").length} total open alerts
            </div>
          </div>
        </div>
        <AlertCircle
          size={20}
          className="shrink-0 text-[#EF4444] transition-transform group-hover:scale-110"
        />
      </button>

      {/* Card 3 — Average Traffic Speed */}
      <button
        type="button"
        onClick={() => navigate("/reports")}
        className="group flex items-center justify-between rounded-xl border border-[#1D3552] bg-[#0A1729] px-4 py-3 text-left transition hover:border-[#24A8FF]/60 hover:bg-[#0D1D32]"
      >
        <div className="flex items-center gap-3.5 min-w-0">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-[#24A8FF]/35 bg-[#24A8FF]/12 text-[#24A8FF]">
            <Car size={22} />
          </div>
          <div className="min-w-0">
            <div className="text-[12px] font-medium text-[#94A3B8]">Avg Traffic Speed</div>
            <div className="mt-0.5 text-[24px] font-bold leading-tight tracking-tight text-[#F1F5F9]">
              {latestMetric.speed} km/h
            </div>
            <div className="text-[11px] text-[#20E39A]">+4% vs last hour</div>
          </div>
        </div>
        <ChevronUp
          size={22}
          className="shrink-0 text-[#20E39A] transition-transform group-hover:-translate-y-0.5"
        />
      </button>

      {/* Card 4 — Average Delay */}
      <button
        type="button"
        onClick={() => navigate("/reports")}
        className="group flex items-center justify-between rounded-xl border border-[#1D3552] bg-[#0A1729] px-4 py-3 text-left transition hover:border-[#24A8FF]/60 hover:bg-[#0D1D32]"
      >
        <div className="flex items-center gap-3.5 min-w-0">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-[#24A8FF]/35 bg-[#24A8FF]/12 text-[#24A8FF]">
            <Clock size={22} />
          </div>
          <div className="min-w-0">
            <div className="text-[12px] font-medium text-[#94A3B8]">Avg Delay</div>
            <div className="mt-0.5 text-[24px] font-bold leading-tight tracking-tight text-[#F1F5F9]">
              {latestMetric.delay.toFixed(1)} min
            </div>
            <div className="text-[11px] text-[#20E39A]">Improved corridor flow</div>
          </div>
        </div>
        <ArrowDown
          size={20}
          className="shrink-0 text-[#20E39A] transition-transform group-hover:translate-y-0.5"
        />
      </button>
    </section>
  );
}
