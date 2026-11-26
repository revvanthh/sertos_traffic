import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Calendar, Download, FileSpreadsheet, FileText } from "lucide-react";
import { usePoliceControl } from "../../context/PoliceControlContext";
import { StatusBadge } from "../../components/common/StatusBadge";

type DateRangeKey = "today" | "7d" | "30d" | "custom";

const RANGE_MULTIPLIER: Record<DateRangeKey, number> = {
  today: 1,
  "7d": 6.4,
  "30d": 26.2,
  custom: 3.2,
};

const PIE_COLORS = ["#EF4444", "#F59E0B", "#24A8FF", "#20E39A"];

export default function ReportsPage() {
  const { alerts, policeActions, pushToast, authMode } = usePoliceControl();

  const [range, setRange] = useState<DateRangeKey>("today");
  const [customStart, setCustomStart] = useState("2026-11-18");
  const [customEnd, setCustomEnd] = useState("2026-11-25");

  const mult = RANGE_MULTIPLIER[range];

  const kpis = useMemo(() => {
    const baseEmergencies = Math.max(alerts.length, 6);
    const routesCleared = Math.max(
      policeActions.filter((a) => a.title.toLowerCase().includes("route")).length + 11,
      12,
    );
    const signalOpts = Math.max(policeActions.length + 25, 28);
    return {
      emergenciesToday: Math.round(baseEmergencies * mult),
      avgResponseMin: range === "today" ? "4.6 min" : range === "7d" ? "4.9 min" : "5.1 min",
      routesCleared: Math.round(routesCleared * mult),
      signalOptimizations: Math.round(signalOpts * mult),
    };
  }, [alerts.length, policeActions, mult, range]);

  const emergenciesByHour = useMemo(
    () => [
      { hour: "06:00", count: Math.round(2 * mult) },
      { hour: "09:00", count: Math.round(5 * mult) },
      { hour: "12:00", count: Math.round(4 * mult) },
      { hour: "15:00", count: Math.round(7 * mult) },
      { hour: "18:00", count: Math.round(8 * mult) },
      { hour: "21:00", count: Math.round(4 * mult) },
    ],
    [mult],
  );

  const speedTrend = useMemo(
    () => [
      { slot: "10:00", speed: range === "today" ? 31 : 29 },
      { slot: "11:00", speed: range === "today" ? 28 : 27 },
      { slot: "12:00", speed: range === "today" ? 34 : 32 },
      { slot: "13:00", speed: range === "today" ? 36 : 33 },
      { slot: "14:00", speed: range === "today" ? 32 : 31 },
      { slot: "15:00", speed: range === "today" ? 35 : 34 },
    ],
    [range],
  );

  const densityByZone = useMemo(
    () => [
      { zone: "Central", density: range === "today" ? 48 : 54 },
      { zone: "East", density: range === "today" ? 62 : 66 },
      { zone: "South", density: range === "today" ? 71 : 68 },
      { zone: "West", density: range === "today" ? 78 : 74 },
    ],
    [range],
  );

  const responseTimes = useMemo(
    () => [
      { label: "P1", minutes: 3.8 },
      { label: "P2", minutes: 4.4 },
      { label: "P3", minutes: 4.9 },
      { label: "P4", minutes: 4.2 },
      { label: "P5", minutes: 3.6 },
    ],
    [],
  );

  const emergencyDistribution = useMemo(
    () => [
      { name: "Cardiac", value: Math.round(14 * mult) },
      { name: "Road Trauma", value: Math.round(19 * mult) },
      { name: "Stroke", value: Math.round(8 * mult) },
      { name: "Respiratory", value: Math.round(11 * mult) },
    ],
    [mult],
  );

  const policeUnitResponse = useMemo(
    () => [
      { unit: "PCR-04", dispatches: Math.round(9 * mult) },
      { unit: "TP-MGR-12", dispatches: Math.round(7 * mult) },
      { unit: "TP-IND-07", dispatches: Math.round(11 * mult) },
      { unit: "TP-TRN-03", dispatches: Math.round(6 * mult) },
    ],
    [mult],
  );

  const triggerDownload = (filename: string, content: string, mime: string) => {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const handleDownloadCsv = () => {
    const header = "IncidentID,Type,Location,Ambulance,Hospital,Priority,Status,TimeReceived\n";
    const rows = alerts
      .map(
        (a) =>
          `"${a.incidentId}","${a.type}","${a.location}","${a.ambulanceId}","${a.hospitalName}","${a.priority}","${a.status}","${a.timeReceived}"`,
      )
      .join("\n");
    triggerDownload(`sertos-traffic-report-${range}.csv`, header + rows, "text/csv;charset=utf-8");
    pushToast({
      title: "CSV Exported",
      description: `Downloaded sertos-traffic-report-${range}.csv`,
      variant: "success",
    });
  };

  const handleExportReport = () => {
    const report = {
      generatedAt: new Date().toISOString(),
      mode: authMode,
      dateRange: range === "custom" ? `${customStart} to ${customEnd}` : range,
      kpis,
      emergenciesByHour,
      densityByZone,
      incidents: alerts,
    };
    triggerDownload(
      `sertos-operations-summary-${range}.json`,
      JSON.stringify(report, null, 2),
      "application/json",
    );
    pushToast({
      title: "Operations Report Exported",
      description: `Downloaded summary for ${range}.`,
      variant: "success",
    });
  };

  return (
    <div className="space-y-4">
      {/* Header & Exports */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-[22px] font-bold text-[#F1F5F9]">Reports &amp; Analytics</h1>
            <StatusBadge label={authMode === "live" ? "LIVE + ANALYTICS" : "DEMO ANALYTICS"} tone="demo" />
          </div>
          <p className="text-[13px] text-[#94A3B8]">
            Corridor response metrics, signal optimization volume, and Bengaluru zone traffic trends.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={handleDownloadCsv}
            className="inline-flex items-center gap-1.5 rounded-xl border border-[#1D3552] bg-[#0D1D32] px-3.5 py-2 text-[12px] font-semibold text-[#F1F5F9] hover:border-[#24A8FF]"
          >
            <FileSpreadsheet size={15} className="text-[#20E39A]" />
            Download CSV
          </button>
          <button
            type="button"
            onClick={handleExportReport}
            className="inline-flex items-center gap-1.5 rounded-xl bg-[#00D084] px-3.5 py-2 text-[12px] font-semibold text-[#020B18] hover:bg-[#20E39A]"
          >
            <Download size={15} />
            Export Report
          </button>
        </div>
      </div>

      {/* Date Range Filters */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#1D3552] bg-[#0A1729] p-3.5">
        <div className="flex flex-wrap items-center gap-2">
          <Calendar size={16} className="text-[#24A8FF]" />
          {(
            [
              { key: "today", label: "Today" },
              { key: "7d", label: "Last 7 Days" },
              { key: "30d", label: "Last 30 Days" },
              { key: "custom", label: "Custom Date Range" },
            ] as const
          ).map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setRange(item.key)}
              className={`rounded-xl px-3 py-1.5 text-[12px] font-medium transition ${
                range === item.key
                  ? "border border-[#00D084]/45 bg-[#00D084]/15 text-[#20E39A]"
                  : "border border-[#1D3552] bg-[#061326] text-[#94A3B8] hover:text-[#F1F5F9]"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>

        {range === "custom" && (
          <div className="flex flex-wrap items-center gap-2 text-[12px]">
            <input
              type="date"
              value={customStart}
              onChange={(e) => setCustomStart(e.target.value)}
              aria-label="Custom start date"
              className="rounded-lg border border-[#1D3552] bg-[#061326] px-2.5 py-1 text-[#F1F5F9]"
            />
            <span className="text-[#94A3B8]">to</span>
            <input
              type="date"
              value={customEnd}
              onChange={(e) => setCustomEnd(e.target.value)}
              aria-label="Custom end date"
              className="rounded-lg border border-[#1D3552] bg-[#061326] px-2.5 py-1 text-[#F1F5F9]"
            />
          </div>
        )}
      </div>

      {/* 4 Report KPI Cards */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4">
          <div className="text-[12px] text-[#94A3B8]">Emergencies ({range})</div>
          <div className="mt-1 text-[28px] font-bold text-[#F1F5F9]">{kpis.emergenciesToday}</div>
          <div className="text-[11px] text-[#20E39A]">100% dispatched with corridor tracking</div>
        </div>
        <div className="rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4">
          <div className="text-[12px] text-[#94A3B8]">Average Ambulance Response</div>
          <div className="mt-1 text-[28px] font-bold text-[#24A8FF]">{kpis.avgResponseMin}</div>
          <div className="text-[11px] text-[#94A3B8]">Dispatch to hospital arrival delta</div>
        </div>
        <div className="rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4">
          <div className="text-[12px] text-[#94A3B8]">Routes Cleared</div>
          <div className="mt-1 text-[28px] font-bold text-[#20E39A]">{kpis.routesCleared}</div>
          <div className="text-[11px] text-[#94A3B8]">Priority emergency corridors</div>
        </div>
        <div className="rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4">
          <div className="text-[12px] text-[#94A3B8]">Signal Optimizations</div>
          <div className="mt-1 text-[28px] font-bold text-[#F59E0B]">{kpis.signalOptimizations}</div>
          <div className="text-[11px] text-[#94A3B8]">Simulated &amp; telemetry phases</div>
        </div>
      </div>

      {/* 6 Charts Grid */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* 1. Emergencies by Hour */}
        <section className="rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4">
          <h2 className="mb-3 text-[15px] font-semibold text-[#F1F5F9]">Emergencies by Hour</h2>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={emergenciesByHour}>
                <CartesianGrid stroke="#1D3552" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="hour" stroke="#94A3B8" tick={{ fontSize: 11 }} />
                <YAxis stroke="#94A3B8" tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ backgroundColor: "#061326", borderColor: "#1D3552" }} />
                <Bar dataKey="count" fill="#EF4444" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* 2. Traffic Speed Trend */}
        <section className="rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4">
          <h2 className="mb-3 text-[15px] font-semibold text-[#F1F5F9]">Traffic Speed Trend (km/h)</h2>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={speedTrend}>
                <CartesianGrid stroke="#1D3552" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="slot" stroke="#94A3B8" tick={{ fontSize: 11 }} />
                <YAxis stroke="#94A3B8" tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ backgroundColor: "#061326", borderColor: "#1D3552" }} />
                <Area type="monotone" dataKey="speed" stroke="#20E39A" fill="#20E39A" fillOpacity={0.2} strokeWidth={2.5} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* 3. Traffic Density by Zone */}
        <section className="rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4">
          <h2 className="mb-3 text-[15px] font-semibold text-[#F1F5F9]">Traffic Density by Zone (%)</h2>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={densityByZone}>
                <CartesianGrid stroke="#1D3552" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="zone" stroke="#94A3B8" tick={{ fontSize: 11 }} />
                <YAxis stroke="#94A3B8" tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ backgroundColor: "#061326", borderColor: "#1D3552" }} />
                <Bar dataKey="density" fill="#F59E0B" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* 4. Ambulance Response Time */}
        <section className="rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4">
          <h2 className="mb-3 text-[15px] font-semibold text-[#F1F5F9]">Ambulance Response Time (min)</h2>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={responseTimes}>
                <CartesianGrid stroke="#1D3552" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" stroke="#94A3B8" tick={{ fontSize: 11 }} />
                <YAxis stroke="#94A3B8" tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ backgroundColor: "#061326", borderColor: "#1D3552" }} />
                <Line type="monotone" dataKey="minutes" stroke="#24A8FF" strokeWidth={2.5} dot={{ r: 4, fill: "#24A8FF" }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* 5. Emergency Type Distribution */}
        <section className="rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4">
          <h2 className="mb-3 text-[15px] font-semibold text-[#F1F5F9]">Emergency Type Distribution</h2>
          <div className="h-56 flex items-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={emergencyDistribution}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={45}
                  outerRadius={78}
                  paddingAngle={3}
                >
                  {emergencyDistribution.map((entry, idx) => (
                    <Cell key={entry.name} fill={PIE_COLORS[idx % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ backgroundColor: "#061326", borderColor: "#1D3552" }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* 6. Police Unit Response */}
        <section className="rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-[15px] font-semibold text-[#F1F5F9]">Police Unit Response Activity</h2>
            <FileText size={15} className="text-[#94A3B8]" />
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={policeUnitResponse}>
                <CartesianGrid stroke="#1D3552" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="unit" stroke="#94A3B8" tick={{ fontSize: 11 }} />
                <YAxis stroke="#94A3B8" tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ backgroundColor: "#061326", borderColor: "#1D3552" }} />
                <Bar dataKey="dispatches" fill="#24A8FF" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>
    </div>
  );
}
