import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Ambulance,
  ArrowUpDown,
  BellRing,
  Check,
  CheckCircle2,
  Clock,
  Eye,
  Hospital,
  MapPin,
  Navigation,
  RefreshCw,
  Search,
  Shield,
} from "lucide-react";
import { usePoliceControl } from "../../context/PoliceControlContext";
import { EmergencyDetailDrawer } from "../../components/dashboard/EmergencyDetailDrawer";
import { StatusBadge } from "../../components/common/StatusBadge";
import type { AlertSeverity, AlertStatus, EmergencyAlert } from "../../types/police";

export default function EmergencyAlertsPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const {
    alerts,
    policeUnits,
    setSelectedEmergencyId,
    setSelectedAmbulanceId,
    acknowledgeAlert,
    assignPoliceUnit,
    notifyNearbyUnits,
    resolveAlert,
    refreshAllData,
    isSyncing,
  } = usePoliceControl();

  const [search, setSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState<"ALL" | AlertSeverity>("ALL");
  const [statusFilter, setStatusFilter] = useState<"ALL" | AlertStatus>("ALL");
  const [locationFilter, setLocationFilter] = useState("ALL");
  const [sortOrder, setSortOrder] = useState<"newest" | "oldest" | "priority">("newest");
  const [drawerAlert, setDrawerAlert] = useState<EmergencyAlert | null>(null);
  const [unitSelection, setUnitSelection] = useState<Record<string, string>>({});

  // Sync if ?incident= is passed from notifications or dashboard
  useEffect(() => {
    const paramId = searchParams.get("incident");
    if (!paramId) return;
    const match = alerts.find(
      (a) => a.incidentId === paramId || a.id === paramId,
    );
    if (match) {
      setDrawerAlert(match);
    }
  }, [searchParams, alerts]);

  const zones = useMemo(
    () => Array.from(new Set(alerts.map((a) => a.zone))),
    [alerts],
  );

  const priorityRank: Record<AlertSeverity, number> = {
    Critical: 0,
    High: 1,
    Medium: 2,
    Low: 3,
  };

  const filteredAlerts = useMemo(() => {
    const q = search.trim().toLowerCase();
    const list = alerts.filter((a) => {
      if (severityFilter !== "ALL" && a.priority !== severityFilter) return false;
      if (statusFilter !== "ALL" && a.status !== statusFilter) return false;
      if (locationFilter !== "ALL" && a.zone !== locationFilter) return false;
      if (
        q &&
        !`${a.incidentId} ${a.type} ${a.location} ${a.ambulanceId} ${a.hospitalName}`
          .toLowerCase()
          .includes(q)
      ) {
        return false;
      }
      return true;
    });

    if (sortOrder === "oldest") return [...list].reverse();
    if (sortOrder === "priority") {
      return [...list].sort((a, b) => priorityRank[a.priority] - priorityRank[b.priority]);
    }
    return list;
  }, [alerts, search, severityFilter, statusFilter, locationFilter, sortOrder]);

  const handleViewRoute = (alert: EmergencyAlert) => {
    setSelectedEmergencyId(alert.incidentId);
    setSelectedAmbulanceId(alert.ambulanceId);
    navigate("/ambulance-tracking");
  };

  return (
    <div className="space-y-4">
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4">
        <div>
          <h1 className="text-[22px] font-bold text-[#F1F5F9]">Emergency Alerts</h1>
          <p className="text-[13px] text-[#94A3B8]">
            Monitor incoming emergencies, assign traffic escort units, and coordinate hospital routes.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void refreshAllData()}
          className="inline-flex items-center gap-2 rounded-xl border border-[#1D3552] bg-[#0D1D32] px-4 py-2 text-[13px] font-medium text-[#F1F5F9] hover:border-[#24A8FF]"
        >
          <RefreshCw size={15} className={isSyncing ? "animate-spin text-[#20E39A]" : ""} />
          Refresh Alerts
        </button>
      </div>

      {/* Filters Toolbar */}
      <div className="grid grid-cols-1 gap-3 rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4 sm:grid-cols-2 lg:grid-cols-5">
        <div className="flex items-center gap-2 rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-2">
          <Search size={15} className="text-[#94A3B8]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search ID, hospital, ambulance..."
            aria-label="Search emergency alerts"
            className="w-full bg-transparent text-[13px] text-[#F1F5F9] placeholder-[#94A3B8]/60 outline-none"
          />
        </div>

        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value as "ALL" | AlertSeverity)}
          aria-label="Filter by severity"
          className="rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-2 text-[13px] text-[#F1F5F9] outline-none"
        >
          <option value="ALL">All Severities</option>
          <option value="Critical">Critical</option>
          <option value="High">High</option>
          <option value="Medium">Medium</option>
          <option value="Low">Low</option>
        </select>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as "ALL" | AlertStatus)}
          aria-label="Filter by status"
          className="rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-2 text-[13px] text-[#F1F5F9] outline-none"
        >
          <option value="ALL">All Statuses</option>
          <option value="New">New</option>
          <option value="Acknowledged">Acknowledged</option>
          <option value="In Progress">In Progress</option>
          <option value="Resolved">Resolved</option>
        </select>

        <select
          value={locationFilter}
          onChange={(e) => setLocationFilter(e.target.value)}
          aria-label="Filter by zone"
          className="rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-2 text-[13px] text-[#F1F5F9] outline-none"
        >
          <option value="ALL">All Divisions / Zones</option>
          {zones.map((z) => (
            <option key={z} value={z}>
              {z}
            </option>
          ))}
        </select>

        <div className="flex items-center gap-2 rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-2">
          <ArrowUpDown size={14} className="text-[#94A3B8]" />
          <select
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value as "newest" | "oldest" | "priority")}
            aria-label="Sort alerts"
            className="w-full bg-transparent text-[13px] text-[#F1F5F9] outline-none"
          >
            <option value="newest">Newest First</option>
            <option value="oldest">Oldest First</option>
            <option value="priority">Highest Severity</option>
          </select>
        </div>
      </div>

      {/* Emergency Alert List */}
      <div className="space-y-3">
        {filteredAlerts.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-[#1D3552] bg-[#0A1729] py-14 text-center text-[13px] text-[#94A3B8]">
            No emergency alerts match the active filters.
          </div>
        ) : (
          filteredAlerts.map((alert) => {
            const selectedUnit =
              unitSelection[alert.id] ?? alert.assignedUnitId ?? policeUnits[0]?.callSign ?? "PCR-BLR-04";
            return (
              <article
                key={alert.id}
                className="rounded-2xl border border-[#1D3552] bg-[#0A1729] p-4 transition hover:border-[#24A8FF]/50"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-[14px] font-bold text-[#F1F5F9]">
                        {alert.incidentId}
                      </span>
                      <StatusBadge
                        label={alert.priority}
                        tone={
                          alert.priority === "Critical"
                            ? "critical"
                            : alert.priority === "High"
                              ? "warning"
                              : alert.priority === "Medium"
                                ? "blue"
                                : "neutral"
                        }
                      />
                      <StatusBadge
                        label={alert.status}
                        tone={
                          alert.status === "Resolved"
                            ? "active"
                            : alert.status === "In Progress"
                              ? "live"
                              : alert.status === "New"
                                ? "warning"
                                : "blue"
                        }
                      />
                      <StatusBadge
                        label={alert.source === "live" ? "LIVE" : "DEMO"}
                        tone={alert.source === "live" ? "live" : "demo"}
                      />
                    </div>
                    <h2 className="text-[16px] font-semibold text-[#F1F5F9]">{alert.type}</h2>
                  </div>

                  <div className="flex items-center gap-2 text-[12px] text-[#94A3B8]">
                    <Clock size={14} />
                    <span>Received: {alert.timeReceived}</span>
                  </div>
                </div>

                {/* Metadata Grid */}
                <div className="mt-3 grid grid-cols-1 gap-2.5 rounded-xl border border-[#1D3552] bg-[#061326] p-3 text-[12px] sm:grid-cols-2 lg:grid-cols-4">
                  <div className="flex items-center gap-2">
                    <MapPin size={14} className="shrink-0 text-[#24A8FF]" />
                    <span className="truncate text-[#F1F5F9]">{alert.location}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Ambulance size={14} className="shrink-0 text-[#20E39A]" />
                    <span className="text-[#F1F5F9]">
                      {alert.ambulanceId} • ETA {alert.etaMinutes} min
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Hospital size={14} className="shrink-0 text-[#EF4444]" />
                    <span className="truncate text-[#F1F5F9]">{alert.hospitalName}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Shield size={14} className="shrink-0 text-[#24A8FF]" />
                    <span className="truncate text-[#94A3B8]">
                      {alert.assignedUnitId ? `Unit: ${alert.assignedUnitId}` : "No unit assigned"}
                    </span>
                  </div>
                </div>

                {/* Functional Actions */}
                <div className="mt-3 flex flex-wrap items-center justify-between gap-2.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => void acknowledgeAlert(alert.id)}
                      disabled={alert.status !== "New"}
                      className="inline-flex items-center gap-1.5 rounded-xl bg-[#00D084] px-3 py-1.5 text-[12px] font-semibold text-[#020B18] transition hover:bg-[#20E39A] disabled:opacity-40"
                    >
                      <Check size={14} />
                      {alert.status === "New" ? "Acknowledge" : "Acknowledged"}
                    </button>

                    <div className="flex items-center gap-1 rounded-xl border border-[#1D3552] bg-[#0D1D32] p-1">
                      <select
                        value={selectedUnit}
                        onChange={(e) =>
                          setUnitSelection((prev) => ({ ...prev, [alert.id]: e.target.value }))
                        }
                        aria-label={`Select police unit for ${alert.incidentId}`}
                        className="bg-transparent px-2 text-[12px] text-[#F1F5F9] outline-none"
                      >
                        {policeUnits.map((u) => (
                          <option key={u.id} value={u.callSign} className="bg-[#061326]">
                            {u.callSign} ({u.zone})
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        onClick={() => assignPoliceUnit(alert.id, selectedUnit)}
                        className="rounded-lg bg-[#24A8FF]/20 px-2.5 py-1 text-[11px] font-semibold text-[#24A8FF] hover:bg-[#24A8FF]/30"
                      >
                        Assign Unit
                      </button>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleViewRoute(alert)}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-[#1D3552] bg-[#0D1D32] px-3 py-1.5 text-[12px] font-medium text-[#F1F5F9] hover:border-[#24A8FF]"
                    >
                      <Navigation size={13} className="text-[#24A8FF]" />
                      View Route
                    </button>

                    <button
                      type="button"
                      onClick={() => notifyNearbyUnits(alert.id)}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-[#1D3552] bg-[#0D1D32] px-3 py-1.5 text-[12px] font-medium text-[#FBBF24] hover:border-[#F59E0B]"
                    >
                      <BellRing size={13} />
                      {alert.nearbyUnitsNotified ? "Units Alerted" : "Notify Nearby Units"}
                    </button>

                    <button
                      type="button"
                      onClick={() => resolveAlert(alert.id)}
                      disabled={alert.status === "Resolved"}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-[#1D3552] bg-[#0D1D32] px-3 py-1.5 text-[12px] font-medium text-[#20E39A] hover:border-[#00D084] disabled:opacity-40"
                    >
                      <CheckCircle2 size={13} />
                      Mark Resolved
                    </button>
                  </div>

                  <button
                    type="button"
                    onClick={() => setDrawerAlert(alert)}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-[#1D3552] bg-[#061326] px-3 py-1.5 text-[12px] font-medium text-[#24A8FF] hover:border-[#24A8FF]"
                  >
                    <Eye size={14} />
                    Open Drawer
                  </button>
                </div>
              </article>
            );
          })
        )}
      </div>

      <EmergencyDetailDrawer
        alert={
          drawerAlert
            ? alerts.find((a) => a.id === drawerAlert.id) ?? drawerAlert
            : null
        }
        onClose={() => setDrawerAlert(null)}
      />
    </div>
  );
}
