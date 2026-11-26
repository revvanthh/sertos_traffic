import { useState } from "react";
import { usePoliceControl } from "../../context/PoliceControlContext";
import { EmergencyDetailDrawer } from "../../components/dashboard/EmergencyDetailDrawer";
import { EmergencyDetailsPanel } from "../../components/dashboard/EmergencyDetailsPanel";
import { KpiRow } from "../../components/dashboard/KpiRow";
import { LiveCctvPanel } from "../../components/dashboard/LiveCctvPanel";
import { PoliceActionsPanel } from "../../components/dashboard/PoliceActionsPanel";
import { RouteStatusPanel } from "../../components/dashboard/RouteStatusPanel";
import { TrafficOverviewChart } from "../../components/dashboard/TrafficOverviewChart";
import { TrafficSignalControlPanel } from "../../components/dashboard/TrafficSignalControlPanel";
import { BengaluruTrafficMap } from "../../components/map/BengaluruTrafficMap";

export default function DashboardPage() {
  const { selectedEmergency, setSelectedEmergencyId, syncError } = usePoliceControl();
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <div className="space-y-4">
      {syncError && (
        <div
          role="alert"
          className="rounded-xl border border-[#EF4444]/40 bg-[#EF4444]/10 px-4 py-2.5 text-[12px] text-[#FCA5A5]"
        >
          Backend sync warning: {syncError}
        </div>
      )}

      {/* Row 1: 4 Interactive KPI Cards */}
      <KpiRow />

      {/* Main Dashboard Grid matching Reference Image */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        {/* Left / Center Column (Map + CCTV + Traffic Overview) */}
        <div className="flex flex-col gap-4 xl:col-span-8">
          <BengaluruTrafficMap
            onSelectEmergency={(incId) => {
              setSelectedEmergencyId(incId);
            }}
          />

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
            <div className="lg:col-span-5">
              <LiveCctvPanel />
            </div>
            <div className="lg:col-span-7">
              <TrafficOverviewChart />
            </div>
          </div>
        </div>

        {/* Right Column (Emergency Details, Route Status, Signal Control, Police Actions) */}
        <div className="flex flex-col gap-4 xl:col-span-4">
          <EmergencyDetailsPanel onOpenDetails={() => setDrawerOpen(true)} />
          <RouteStatusPanel />
          <TrafficSignalControlPanel />
          <PoliceActionsPanel />
        </div>
      </div>

      <EmergencyDetailDrawer
        alert={drawerOpen ? selectedEmergency : null}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  );
}
