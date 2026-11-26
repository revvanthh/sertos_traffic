import { useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { TrendingUp } from "lucide-react";
import { usePoliceControl } from "../../context/PoliceControlContext";

type MetricKey = "speed" | "density" | "delay";

const METRIC_META: Record<
  MetricKey,
  { label: string; unit: string; color: string; gradientId: string }
> = {
  speed: {
    label: "Speed",
    unit: "km/h",
    color: "#20E39A",
    gradientId: "sertosSpeedGrad",
  },
  density: {
    label: "Traffic Density",
    unit: "%",
    color: "#24A8FF",
    gradientId: "sertosDensityGrad",
  },
  delay: {
    label: "Delay",
    unit: "min",
    color: "#F59E0B",
    gradientId: "sertosDelayGrad",
  },
};

export function TrafficOverviewChart() {
  const { analyticsSeries } = usePoliceControl();
  const [metric, setMetric] = useState<MetricKey>("speed");

  const meta = METRIC_META[metric];
  const values = analyticsSeries.map((pt) => pt[metric]);
  const current = values[values.length - 1] ?? 0;
  const peak = Math.max(...values);
  const lowest = Math.min(...values);

  return (
    <section className="flex flex-col rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4 shadow-lg">
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2">
        <div className="flex items-center gap-2">
          <TrendingUp size={17} className="text-[#20E39A]" />
          <h2 className="text-[15px] font-semibold text-[#F1F5F9]">Traffic Overview</h2>
        </div>

        {/* Metric Switcher */}
        <div className="flex items-center gap-1 rounded-xl border border-[#1D3552] bg-[#061326] p-1">
          {(["speed", "density", "delay"] as MetricKey[]).map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => setMetric(key)}
              className={`rounded-lg px-2.5 py-1 text-[11px] font-medium transition ${
                metric === key
                  ? "bg-[#0D1D32] text-[#20E39A] border border-[#00D084]/40"
                  : "text-[#94A3B8] hover:text-[#F1F5F9]"
              }`}
            >
              {METRIC_META[key].label}
            </button>
          ))}
        </div>
      </div>

      {/* Current Value & Peak / Lowest Summary */}
      <div className="mb-1 flex flex-wrap items-center justify-between gap-2 text-[11px]">
        <div className="flex items-center gap-3">
          <span className="text-[#94A3B8]">
            Peak: <strong className="text-[#F1F5F9]">{peak} {meta.unit}</strong>
          </span>
          <span className="text-[#94A3B8]">
            Lowest: <strong className="text-[#F1F5F9]">{lowest} {meta.unit}</strong>
          </span>
        </div>
        <div className="rounded-lg border border-[#1D3552] bg-[#0D1D32] px-2.5 py-0.5 text-[12px] font-bold text-[#F1F5F9]">
          {current} {meta.unit}
        </div>
      </div>

      {/* Recharts Area Chart */}
      <div className="h-[145px] w-full min-w-0">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={analyticsSeries} margin={{ top: 8, right: 10, left: -18, bottom: 0 }}>
            <defs>
              <linearGradient id={meta.gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={meta.color} stopOpacity={0.35} />
                <stop offset="95%" stopColor={meta.color} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#1D3552" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="time"
              stroke="#94A3B8"
              tick={{ fill: "#94A3B8", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              stroke="#94A3B8"
              tick={{ fill: "#94A3B8", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#061326",
                borderColor: "#1D3552",
                borderRadius: "10px",
                fontSize: "12px",
                color: "#F1F5F9",
              }}
              formatter={(value) => [`${value} ${meta.unit}`, meta.label]}
            />
            <Area
              type="monotone"
              dataKey={metric}
              stroke={meta.color}
              strokeWidth={2.5}
              fill={`url(#${meta.gradientId})`}
              dot={{ r: 3, fill: meta.color, strokeWidth: 0 }}
              activeDot={{ r: 5, fill: meta.color, stroke: "#F1F5F9", strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
