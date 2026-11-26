interface StatusBadgeProps {
  label: string;
  tone?: "live" | "demo" | "critical" | "warning" | "active" | "neutral" | "blue";
  pulse?: boolean;
}

export function StatusBadge({ label, tone = "neutral", pulse = false }: StatusBadgeProps) {
  const styles: Record<NonNullable<StatusBadgeProps["tone"]>, string> = {
    live: "border-[#00D084]/40 bg-[#00D084]/15 text-[#20E39A]",
    demo: "border-[#F59E0B]/40 bg-[#F59E0B]/15 text-[#FBBF24]",
    critical: "border-[#EF4444]/40 bg-[#EF4444] text-white",
    warning: "border-[#F59E0B]/40 bg-[#F59E0B]/15 text-[#F59E0B]",
    active: "border-[#00D084]/40 bg-[#00D084]/20 text-[#20E39A]",
    blue: "border-[#24A8FF]/40 bg-[#24A8FF]/15 text-[#24A8FF]",
    neutral: "border-[#1D3552] bg-[#0D1D32] text-[#94A3B8]",
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11px] font-semibold tracking-wide ${styles[tone]}`}
    >
      {pulse && (
        <span
          className={`h-1.5 w-1.5 rounded-full ${
            tone === "critical"
              ? "bg-white animate-pulse"
              : tone === "demo"
                ? "bg-[#F59E0B] animate-pulse"
                : "bg-[#20E39A] animate-pulse"
          }`}
        />
      )}
      {label}
    </span>
  );
}
