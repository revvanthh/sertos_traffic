import { useEffect, useRef, useState } from "react";
import {
  Camera,
  ChevronRight,
  Maximize2,
  Pause,
  Play,
  RefreshCw,
  X,
} from "lucide-react";
import { usePoliceControl } from "../../context/PoliceControlContext";
import { StatusBadge } from "../common/StatusBadge";

function getIstTimestamp(): string {
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date());
}

function SimulatedRoadCanvas({
  playing,
  cameraLocation,
  density,
  height = 176,
}: {
  playing: boolean;
  cameraLocation: string;
  density: string;
  height?: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const offsetRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let rafId = 0;

    const vehicles = [
      { lane: 0.34, speed: 1.4, w: 32, h: 14, color: "#38BDF8", offset: 10 },
      { lane: 0.44, speed: 1.9, w: 46, h: 16, color: "#2563EB", offset: 140 },
      { lane: 0.56, speed: 1.1, w: 28, h: 13, color: "#F8FAFC", offset: 80 },
      { lane: 0.66, speed: 2.2, w: 34, h: 14, color: "#F59E0B", offset: 220 },
      { lane: 0.44, speed: 1.9, w: 30, h: 14, color: "#94A3B8", offset: 310 },
      { lane: 0.56, speed: 1.5, w: 44, h: 16, color: "#EF4444", offset: 260 },
    ];

    const render = () => {
      const w = canvas.width;
      const h = canvas.height;

      // Sky & trees backdrop
      const sky = ctx.createLinearGradient(0, 0, 0, h * 0.4);
      sky.addColorStop(0, "#0A1B33");
      sky.addColorStop(1, "#132B4C");
      ctx.fillStyle = sky;
      ctx.fillRect(0, 0, w, h);

      // Bengaluru roadside greenery
      ctx.fillStyle = "#0F342E";
      ctx.fillRect(0, h * 0.14, w * 0.16, h * 0.86);
      ctx.fillRect(w * 0.84, h * 0.14, w * 0.16, h * 0.86);

      // Perspective asphalt road
      ctx.fillStyle = "#1E293B";
      ctx.beginPath();
      ctx.moveTo(w * 0.3, h * 0.22);
      ctx.lineTo(w * 0.7, h * 0.22);
      ctx.lineTo(w * 0.94, h);
      ctx.lineTo(w * 0.06, h);
      ctx.closePath();
      ctx.fill();

      // Road lane markings
      ctx.strokeStyle = "rgba(241, 245, 249, 0.35)";
      ctx.lineWidth = 2;
      ctx.setLineDash([12, 12]);
      ctx.lineDashOffset = -offsetRef.current * 2;
      ctx.beginPath();
      ctx.moveTo(w * 0.5, h * 0.22);
      ctx.lineTo(w * 0.5, h);
      ctx.stroke();
      ctx.setLineDash([]);

      // Moving simulated vehicles
      vehicles.forEach((v) => {
        const yProgress = ((v.offset + offsetRef.current * v.speed * 1.6) % (h * 0.85)) / (h * 0.85);
        const y = h * 0.24 + yProgress * (h * 0.72);
        const scale = 0.45 + yProgress * 0.75;
        const spread = (v.lane - 0.5) * (0.4 + yProgress * 0.65) * w;
        const x = w * 0.5 + spread - (v.w * scale) / 2;

        ctx.fillStyle = v.color;
        ctx.fillRect(x, y, v.w * scale, v.h * scale);

        // Headlights / taillights glow
        ctx.fillStyle = "rgba(253, 224, 71, 0.8)";
        ctx.fillRect(x + 2, y + v.h * scale - 3, 4 * scale, 2 * scale);
        ctx.fillRect(x + v.w * scale - 6 * scale, y + v.h * scale - 3, 4 * scale, 2 * scale);
      });

      // Subtle scanline overlay
      ctx.fillStyle = "rgba(2, 11, 24, 0.14)";
      for (let y = 0; y < h; y += 4) {
        ctx.fillRect(0, y, w, 1);
      }

      if (playing) {
        offsetRef.current += 0.9;
        rafId = window.requestAnimationFrame(render);
      }
    };

    render();
    return () => {
      if (rafId) window.cancelAnimationFrame(rafId);
    };
  }, [playing, cameraLocation, density]);

  return (
    <canvas
      ref={canvasRef}
      width={440}
      height={height}
      className="h-full w-full object-cover"
      aria-label={`Simulated traffic camera view for ${cameraLocation}`}
    />
  );
}

export function LiveCctvPanel() {
  const { cctvCameras, settings, pushToast } = usePoliceControl();
  const [selectedId, setSelectedId] = useState(settings.defaultCctvId || cctvCameras[0]?.id);
  const [playing, setPlaying] = useState(true);
  const [fullscreenOpen, setFullscreenOpen] = useState(false);
  const [timestamp, setTimestamp] = useState(() => getIstTimestamp());
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    const t = window.setInterval(() => {
      if (playing) setTimestamp(getIstTimestamp());
    }, 1000);
    return () => window.clearInterval(t);
  }, [playing]);

  const activeCam = cctvCameras.find((c) => c.id === selectedId) ?? cctvCameras[0];

  const handleSwitchCamera = () => {
    const idx = cctvCameras.findIndex((c) => c.id === activeCam.id);
    const next = cctvCameras[(idx + 1) % cctvCameras.length];
    setSelectedId(next.id);
  };

  const handleRefresh = () => {
    setRefreshing(true);
    setTimestamp(getIstTimestamp());
    window.setTimeout(() => {
      setRefreshing(false);
      pushToast({
        title: "CCTV Demo Feed Refreshed",
        description: `${activeCam.cameraId} (${activeCam.location}) synced.`,
        variant: "info",
      });
    }, 450);
  };

  return (
    <section className="flex flex-col rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4 shadow-lg">
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5">
        <div className="flex items-center gap-2">
          <Camera size={17} className="text-[#F1F5F9]" />
          <h2 className="text-[15px] font-semibold text-[#F1F5F9]">Live CCTV Feed</h2>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={activeCam.id}
            onChange={(e) => setSelectedId(e.target.value)}
            aria-label="Select CCTV camera location"
            className="max-w-[165px] truncate rounded-lg border border-[#1D3552] bg-[#0D1D32] px-2 py-1 text-[11px] text-[#F1F5F9] outline-none focus:border-[#24A8FF]"
          >
            {cctvCameras.map((cam) => (
              <option key={cam.id} value={cam.id}>
                {cam.location}
              </option>
            ))}
          </select>
          <StatusBadge
            label={activeCam.isLiveSource ? "LIVE" : "DEMO"}
            tone={activeCam.isLiveSource ? "critical" : "demo"}
            pulse
          />
        </div>
      </div>

      {/* Video / Simulation Viewport */}
      <div className="relative h-[165px] overflow-hidden rounded-xl border border-[#1D3552] bg-[#040E1E]">
        <SimulatedRoadCanvas
          playing={playing}
          cameraLocation={activeCam.location}
          density={activeCam.vehicleDensity}
        />

        {/* HUD Top Overlay */}
        <div className="absolute left-2.5 right-2.5 top-2 flex items-center justify-between text-[10px]">
          <span className="rounded bg-[#020B18]/80 px-2 py-0.5 font-mono font-semibold text-[#F1F5F9]">
            {activeCam.cameraId} • {activeCam.location}
          </span>
          <span className="rounded bg-[#020B18]/80 px-2 py-0.5 font-mono text-[#20E39A]">
            {timestamp} IST
          </span>
        </div>

        {/* HUD Bottom Controls */}
        <div className="absolute bottom-2 left-2.5 right-2.5 flex items-center justify-between gap-2">
          <span className="rounded bg-[#020B18]/85 px-2 py-0.5 text-[10px] text-[#94A3B8]">
            {activeCam.status} • Density: <strong className="text-[#F1F5F9]">{activeCam.vehicleDensity}</strong>
          </span>

          <div className="flex items-center gap-1 rounded-lg border border-[#1D3552] bg-[#061326]/90 p-1">
            <button
              type="button"
              onClick={() => setPlaying((p) => !p)}
              aria-label={playing ? "Pause CCTV feed" : "Play CCTV feed"}
              title={playing ? "Pause" : "Play"}
              className="rounded p-1 text-[#F1F5F9] hover:bg-[#0D1D32]"
            >
              {playing ? <Pause size={13} /> : <Play size={13} />}
            </button>
            <button
              type="button"
              onClick={handleSwitchCamera}
              aria-label="Switch camera"
              title="Next camera"
              className="rounded p-1 text-[#F1F5F9] hover:bg-[#0D1D32]"
            >
              <ChevronRight size={13} />
            </button>
            <button
              type="button"
              onClick={handleRefresh}
              aria-label="Refresh camera feed"
              title="Refresh feed"
              className="rounded p-1 text-[#F1F5F9] hover:bg-[#0D1D32]"
            >
              <RefreshCw size={13} className={refreshing ? "animate-spin" : ""} />
            </button>
            <button
              type="button"
              onClick={() => setFullscreenOpen(true)}
              aria-label="Fullscreen CCTV view"
              title="Fullscreen"
              className="rounded p-1 text-[#F1F5F9] hover:bg-[#0D1D32]"
            >
              <Maximize2 size={13} />
            </button>
          </div>
        </div>
      </div>

      {/* Fullscreen CCTV Modal */}
      {fullscreenOpen && (
        <div
          className="fixed inset-0 z-[1200] flex items-center justify-center bg-[#020B18]/90 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-label="Fullscreen CCTV Demo Feed"
        >
          <div className="w-full max-w-3xl rounded-2xl border border-[#1D3552] bg-[#0A1729] p-5 shadow-2xl">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <Camera size={18} className="text-[#20E39A]" />
                <div>
                  <h3 className="text-[16px] font-semibold text-[#F1F5F9]">
                    {activeCam.cameraId} — {activeCam.location}
                  </h3>
                  <p className="text-[11px] text-[#94A3B8]">
                    Simulated Bengaluru traffic demonstration feed (no external RTSP stream connected)
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setFullscreenOpen(false)}
                aria-label="Close fullscreen CCTV"
                className="rounded-lg p-1.5 text-[#94A3B8] hover:bg-[#0D1D32] hover:text-[#F1F5F9]"
              >
                <X size={18} />
              </button>
            </div>
            <div className="h-[360px] overflow-hidden rounded-xl border border-[#1D3552] bg-[#040E1E]">
              <SimulatedRoadCanvas
                playing={playing}
                cameraLocation={activeCam.location}
                density={activeCam.vehicleDensity}
                height={360}
              />
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
