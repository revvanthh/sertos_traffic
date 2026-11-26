export function BengaluruPoliceEmblem({ size = 44 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="Bengaluru Traffic Police Emblem"
      className="shrink-0"
    >
      {/* Wreath & Shield */}
      <path
        d="M32 6L52 13V30C52 44.5 43.2 54.5 32 59C20.8 54.5 12 44.5 12 30V13L32 6Z"
        fill="#0D1D32"
        stroke="#EAB308"
        strokeWidth="2.4"
      />
      <path
        d="M32 10.5L47.5 16V29.5C47.5 41.2 40.6 49.5 32 53.5C23.4 49.5 16.5 41.2 16.5 29.5V16L32 10.5Z"
        fill="#061326"
        stroke="#F59E0B"
        strokeWidth="1.2"
        strokeOpacity="0.7"
      />
      {/* Ashoka-inspired crest */}
      <circle cx="32" cy="24" r="6.5" stroke="#FBBF24" strokeWidth="1.8" />
      <circle cx="32" cy="24" r="2.2" fill="#FBBF24" />
      <path d="M32 17.5V30.5M25.5 24H38.5M27.4 19.4L36.6 28.6M36.6 19.4L27.4 28.6" stroke="#FBBF24" strokeWidth="1.1" />
      {/* Base ribbon */}
      <path d="M21 38H43L40 43.5H24L21 38Z" fill="#B91C1C" stroke="#FBBF24" strokeWidth="1" />
      <text
        x="32"
        y="42.2"
        textAnchor="middle"
        fill="#FEF08A"
        fontSize="4.8"
        fontWeight="700"
        fontFamily="Inter, sans-serif"
      >
        BTP
      </text>
      {/* Crown top */}
      <path d="M26 7.5L32 3L38 7.5" stroke="#FBBF24" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function SertosEcgLogo({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-3 select-none">
      <svg
        width={compact ? 40 : 48}
        height={compact ? 30 : 36}
        viewBox="0 0 56 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
        className="shrink-0 drop-shadow-[0_0_8px_rgba(32,227,154,0.45)]"
      >
        <path
          d="M2 22H12L16.5 9L22.5 34L28.5 5L34 26L38 22H54"
          stroke="#20E39A"
          strokeWidth="2.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <div className="leading-none">
        <div className="flex items-center font-extrabold tracking-wide text-[#F1F5F9]" style={{ fontSize: compact ? "20px" : "24px" }}>
          <span>SERT</span>
          <span className="relative mx-[1px] inline-flex items-center justify-center rounded-full border-[3px] border-[#20E39A] w-[20px] h-[20px] text-[#20E39A] shadow-[0_0_10px_rgba(32,227,154,0.35)]">
            <span className="text-[12px] font-black leading-none">+</span>
          </span>
          <span>S</span>
        </div>
        {!compact && (
          <p className="mt-1 text-[10px] font-medium tracking-wide text-[#94A3B8]">
            Smart Emergency Response &amp; Traffic Optimization System
          </p>
        )}
      </div>
    </div>
  );
}

export function VidhanaSoudhaVisual() {
  return (
    <div className="relative overflow-hidden rounded-xl border border-[#1D3552] bg-[#040E1E] p-3 text-center">
      <div className="relative mx-auto mb-2.5 h-24 w-full overflow-hidden rounded-lg bg-gradient-to-b from-[#0A1D38] via-[#0E2646] to-[#061326]">
        <svg
          viewBox="0 0 240 110"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="h-full w-full"
          aria-label="Vidhana Soudha Bengaluru Illustration"
        >
          {/* Night sky stars / horizon glow */}
          <ellipse cx="120" cy="86" rx="95" ry="20" fill="#F59E0B" fillOpacity="0.16" />
          {/* Main Vidhana Soudha structure */}
          <rect x="24" y="64" width="192" height="28" rx="1" fill="#1E293B" stroke="#FBBF24" strokeOpacity="0.45" strokeWidth="0.8" />
          {/* Left & Right Wings */}
          <rect x="30" y="54" width="42" height="10" fill="#273549" />
          <rect x="168" y="54" width="42" height="10" fill="#273549" />
          {/* Left & Right Domes */}
          <path d="M38 54C38 45 48 45 48 54Z" fill="#F59E0B" fillOpacity="0.85" />
          <path d="M192 54C192 45 202 45 202 54Z" fill="#F59E0B" fillOpacity="0.85" />
          {/* Central Facade */}
          <rect x="86" y="46" width="68" height="46" fill="#2B3B52" stroke="#FDE68A" strokeOpacity="0.55" strokeWidth="0.8" />
          {/* Grand Central Dome */}
          <path d="M98 46C98 25 142 25 142 46Z" fill="#FBBF24" fillOpacity="0.9" />
          <path d="M107 46C107 32 133 32 133 46Z" fill="#FDE68A" fillOpacity="0.7" />
          <line x1="120" y1="20" x2="120" y2="28" stroke="#FDE68A" strokeWidth="1.5" />
          <circle cx="120" cy="19" r="2" fill="#FDE68A" />
          {/* Illuminated Pillars */}
          {[92, 100, 108, 116, 124, 132, 140].map((x) => (
            <rect key={x} x={x} y="53" width="3" height="24" fill="#FDE68A" fillOpacity="0.75" />
          ))}
          {/* Wing Windows */}
          {[36, 46, 56, 66, 174, 184, 194, 204].map((x) => (
            <rect key={x} x={x} y="70" width="5" height="9" rx="1" fill="#FBBF24" fillOpacity="0.55" />
          ))}
          {/* Lawn / Road Foreground */}
          <path d="M0 92H240V110H0V92Z" fill="#061326" />
          <path d="M72 110L106 92H134L168 110H72Z" fill="#0F2942" />
          <path d="M0 92H240" stroke="#00D084" strokeOpacity="0.4" strokeWidth="1.2" />
        </svg>
      </div>
      <div className="text-[14px] font-bold tracking-tight text-[#F1F5F9]">
        Safer Bengaluru
      </div>
      <div className="text-[14px] font-bold tracking-tight text-[#F1F5F9]">
        Together
      </div>
      <div className="mx-auto mt-1.5 h-[2px] w-24 rounded-full bg-gradient-to-r from-transparent via-[#00D084] to-transparent" />
    </div>
  );
}
