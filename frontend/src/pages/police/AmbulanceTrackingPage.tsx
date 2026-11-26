import { useMemo, useState } from "react";
import {
  Ambulance,
  Crosshair,
  Eye,
  Gauge,
  Hospital,
  MapPin,
  Search,
} from "lucide-react";
import { usePoliceControl } from "../../context/PoliceControlContext";
import { EmergencyDetailDrawer } from "../../components/dashboard/EmergencyDetailDrawer";
import { RouteStatusPanel } from "../../components/dashboard/RouteStatusPanel";
import { BengaluruTrafficMap } from "../../components/map/BengaluruTrafficMap";
import { StatusBadge } from "../../components/common/StatusBadge";
import type { AmbulanceStage, LatLng } from "../../types/police";

const STAGES: ("ALL" | AmbulanceStage)[] = [
  "ALL",
  "Dispatched",
  "En Route",
  "Approaching Hospital",
  "Arrived",
  "Completed",
];

export default function AmbulanceTrackingPage() {
  const {
    ambulances,
    selectedAmbulance,
    setSelectedAmbulanceId,
    setSelectedEmergencyId,
    alerts,
  } = usePoliceControl();

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"ALL" | AmbulanceStage>("ALL");
  const [focusPos, setFocusPos] = useState<LatLng | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return ambulances.filter((amb) => {
      if (statusFilter !== "ALL" && amb.status !== statusFilter) return false;
      if (
        q &&
        !`${amb.ambulanceId} ${amb.incidentId} ${amb.destinationHospitalName} ${amb.emergencyType}`
          .toLowerCase()
          .includes(q)
      ) {
        return false;
      }
      return true;
    });
  }, [ambulances, search, statusFilter]);

  const matchedAlert =
    alerts.find((a) => a.incidentId === selectedAmbulance.incidentId) ?? alerts[0];

  const handleSelect = (ambId: string, incId: string, pos: LatLng) => {
    setSelectedAmbulanceId(ambId);
    setSelectedEmergencyId(incId);
    setFocusPos({ ...pos });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4">
        <div>
          <h1 className="text-[22px] font-bold text-[#F1F5F9]">Ambulance Tracking</h1>
          <p className="text-[13px] text-[#94A3B8]">
            Synchronized live GPS corridor view, fleet status, and hospital arrival timelines.
          </p>
        </div>
        <StatusBadge
          label={
            selectedAmbulance.source === "demo"
              ? "DEMO MOVEMENT SIMULATION"
              : "LIVE GPS TELEMETRY"
          }
          tone={selectedAmbulance.source === "demo" ? "demo" : "live"}
          pulse
        />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        {/* Interactive Map & Timeline */}
        <div className="flex flex-col gap-4 xl:col-span-8">
          <BengaluruTrafficMap
            heightClass="h-[430px]"
            focusPosition={focusPos}
            onSelectEmergency={(incId) => setSelectedEmergencyId(incId)}
          />

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {/* Selected Ambulance Info Card */}
            <section className="rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4 shadow-lg">
              <div className="flex items-center justify-between border-b border-[#1D3552] pb-2.5">
                <div className="flex items-center gap-2">
                  <Ambulance size={18} className="text-[#20E39A]" />
                  <h2 className="text-[16px] font-semibold text-[#F1F5F9]">
                    {selectedAmbulance.ambulanceId}
                  </h2>
                </div>
                <StatusBadge label={selectedAmbulance.status} tone="blue" />
              </div>

              <div className="mt-3 grid grid-cols-2 gap-3 text-[12px]">
                <div>
                  <span className="text-[#94A3B8]">Incident ID</span>
                  <div className="font-mono font-semibold text-[#F1F5F9]">
                    {selectedAmbulance.incidentId}
                  </div>
                </div>
                <div>
                  <span className="text-[#94A3B8]">Emergency Type</span>
                  <div className="font-medium text-[#F1F5F9]">
                    {selectedAmbulance.emergencyType}
                  </div>
                </div>
                <div>
                  <span className="text-[#94A3B8]">Current Speed</span>
                  <div className="flex items-center gap-1 font-semibold text-[#20E39A]">
                    <Gauge size={13} />
                    {selectedAmbulance.speedKmh} km/h
                  </div>
                </div>
                <div>
                  <span className="text-[#94A3B8]">ETA / Distance</span>
                  <div className="font-semibold text-[#24A8FF]">
                    {selectedAmbulance.etaMinutes} min • {selectedAmbulance.distanceKm} km
                  </div>
                </div>
              </div>

              <div className="mt-3 flex items-center gap-1.5 text-[12px] text-[#94A3B8]">
                <Hospital size={14} className="text-[#EF4444]" />
                Destination: <strong className="text-[#F1F5F9]">{selectedAmbulance.destinationHospitalName}</strong>
              </div>
              <div className="mt-1 flex items-center gap-1.5 text-[11px] text-[#94A3B8]">
                <MapPin size={13} className="text-[#24A8FF]" />
                Coords: {selectedAmbulance.position.lat.toFixed(5)}, {selectedAmbulance.position.lng.toFixed(5)}
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setFocusPos({ ...selectedAmbulance.position })}
                  className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-[#00D084] py-2 text-[12px] font-semibold text-[#020B18] hover:bg-[#20E39A]"
                >
                  <Crosshair size={14} />
                  Focus on Map
                </button>
                <button
                  type="button"
                  onClick={() => setDrawerOpen(true)}
                  className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-[#1D3552] bg-[#0D1D32] py-2 text-[12px] font-medium text-[#F1F5F9] hover:border-[#24A8FF]"
                >
                  <Eye size={14} />
                  Emergency Details
                </button>
              </div>
            </section>

            {/* Route Timeline */}
            <RouteStatusPanel />
          </div>
        </div>

        {/* Active Ambulance List & Filters */}
        <aside className="flex flex-col gap-3 rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4 xl:col-span-4">
          <div>
            <h2 className="text-[16px] font-semibold text-[#F1F5F9]">Active Fleet</h2>
            <p className="text-[12px] text-[#94A3B8]">
              Select a unit to synchronize map marker, route, and timeline.
            </p>
          </div>

          <div className="flex items-center gap-2 rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-2">
            <Search size={14} className="text-[#94A3B8]" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search ambulance, incident, hospital..."
              aria-label="Search ambulances"
              className="w-full bg-transparent text-[12px] text-[#F1F5F9] placeholder-[#94A3B8]/60 outline-none"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as "ALL" | AmbulanceStage)}
            aria-label="Filter ambulances by status"
            className="rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-2 text-[12px] text-[#F1F5F9] outline-none"
          >
            {STAGES.map((st) => (
              <option key={st} value={st}>
                {st === "ALL" ? "All Ambulance Statuses" : st}
              </option>
            ))}
          </select>

          <div className="flex-1 space-y-2.5 overflow-y-auto pr-1">
            {filtered.length === 0 ? (
              <div className="rounded-xl border border-dashed border-[#1D3552] py-10 text-center text-[12px] text-[#94A3B8]">
                No ambulances match the filter.
              </div>
            ) : (
              filtered.map((amb) => {
                const isSelected = amb.ambulanceId === selectedAmbulance.ambulanceId;
                return (
                  <button
                    key={amb.id}
                    type="button"
                    onClick={() => handleSelect(amb.ambulanceId, amb.incidentId, amb.position)}
                    className={`w-full rounded-xl border p-3.5 text-left transition ${
                      isSelected
                        ? "border-[#24A8FF] bg-[#0D1D32] shadow-[0_0_16px_rgba(36,168,255,0.18)]"
                        : "border-[#1D3552] bg-[#061326] hover:border-[#24A8FF]/50"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-[14px] font-bold text-[#F1F5F9]">
                        {amb.ambulanceId}
                      </span>
                      <StatusBadge
                        label={amb.status}
                        tone={
                          amb.status === "Approaching Hospital"
                            ? "live"
                            : amb.status === "Completed"
                              ? "active"
                              : "blue"
                        }
                      />
                    </div>
                    <div className="mt-1 text-[12px] font-medium text-[#24A8FF]">
                      {amb.emergencyType} ({amb.incidentId})
                    </div>
                    <div className="mt-2 flex items-center justify-between text-[11px] text-[#94A3B8]">
                      <span>{amb.destinationHospitalName}</span>
                      <span className="font-semibold text-[#F1F5F9]">
                        {amb.speedKmh} km/h • {amb.etaMinutes}m
                      </span>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </aside>
      </div>

      <EmergencyDetailDrawer
        alert={drawerOpen ? matchedAlert : null}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  );
}
