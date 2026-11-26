import { useEffect, useRef, useState, type ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  Ambulance,
  BarChart3,
  Bell,
  ChevronDown,
  LayoutDashboard,
  LogOut,
  Menu,
  Radio,
  Settings,
  Shield,
  Siren,
  TrafficCone,
  UserCheck,
  X,
} from "lucide-react";
import { usePoliceControl } from "../../context/PoliceControlContext";
import { ConfirmModal } from "../common/ConfirmModal";
import {
  BengaluruPoliceEmblem,
  SertosEcgLogo,
  VidhanaSoudhaVisual,
} from "../common/SertosBranding";
import { ToastContainer } from "../common/ToastContainer";
import { NotificationDrawer } from "./NotificationDrawer";

interface PoliceShellProps {
  children: ReactNode;
}

const NAV_ITEMS = [
  { label: "Dashboard", path: "/dashboard", aliases: ["/police"], icon: LayoutDashboard },
  { label: "Traffic Control", path: "/traffic-control", aliases: ["/police/junctions"], icon: TrafficCone },
  { label: "Emergency Alerts", path: "/emergency-alerts", aliases: ["/police/alerts"], icon: Bell, showBadge: true },
  { label: "Ambulance Tracking", path: "/ambulance-tracking", aliases: ["/police/tracking"], icon: Ambulance },
  { label: "Reports", path: "/reports", aliases: ["/police/reports", "/police/history"], icon: BarChart3 },
  { label: "Settings", path: "/settings", aliases: ["/police/settings", "/police/profile"], icon: Settings },
];

const ROUTE_TITLES: Record<string, { title: string; breadcrumb: string }> = {
  "/dashboard": { title: "Traffic Control Dashboard", breadcrumb: "Operations / Dashboard" },
  "/police": { title: "Traffic Control Dashboard", breadcrumb: "Operations / Dashboard" },
  "/traffic-control": { title: "Traffic Signal Control", breadcrumb: "Operations / Traffic Control" },
  "/police/junctions": { title: "Traffic Signal Control", breadcrumb: "Operations / Traffic Control" },
  "/emergency-alerts": { title: "Emergency Alerts", breadcrumb: "Operations / Emergency Alerts" },
  "/police/alerts": { title: "Emergency Alerts", breadcrumb: "Operations / Emergency Alerts" },
  "/ambulance-tracking": { title: "Ambulance Tracking", breadcrumb: "Operations / Ambulance Tracking" },
  "/police/tracking": { title: "Ambulance Tracking", breadcrumb: "Operations / Ambulance Tracking" },
  "/reports": { title: "Reports & Analytics", breadcrumb: "Operations / Reports" },
  "/police/reports": { title: "Reports & Analytics", breadcrumb: "Operations / Reports" },
  "/police/history": { title: "Reports & Analytics", breadcrumb: "Operations / Reports" },
  "/settings": { title: "System & Officer Settings", breadcrumb: "Operations / Settings" },
  "/police/settings": { title: "System & Officer Settings", breadcrumb: "Operations / Settings" },
  "/police/profile": { title: "System & Officer Settings", breadcrumb: "Operations / Settings" },
};

function getIstClock(): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date());
}

export function PoliceShell({ children }: PoliceShellProps) {
  const {
    authMode,
    systemStatus,
    officerProfile,
    alerts,
    unreadNotificationCount,
    performLogout,
  } = usePoliceControl();

  const location = useLocation();
  const navigate = useNavigate();

  const [clock, setClock] = useState<string>(() => getIstClock());
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const [statusMenuOpen, setStatusMenuOpen] = useState(false);
  const [logoutModalOpen, setLogoutModalOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);

  const profileRef = useRef<HTMLDivElement>(null);
  const statusRef = useRef<HTMLDivElement>(null);

  // Live IST digital clock updating every second
  useEffect(() => {
    const timer = window.setInterval(() => {
      setClock(getIstClock());
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  // Close popovers on outside click / Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setSidebarOpen(false);
        setProfileMenuOpen(false);
        setStatusMenuOpen(false);
      }
    };
    const onPointerDown = (e: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileMenuOpen(false);
      }
      if (statusRef.current && !statusRef.current.contains(e.target as Node)) {
        setStatusMenuOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onPointerDown);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onPointerDown);
    };
  }, []);

  const activeAlertsCount = alerts.filter((a) => a.status !== "Resolved").length;
  const routeInfo = ROUTE_TITLES[location.pathname] ?? {
    title: "Traffic Control Dashboard",
    breadcrumb: "Operations / Control",
  };

  const handleConfirmLogout = async () => {
    setLoggingOut(true);
    await performLogout();
    setLoggingOut(false);
    setLogoutModalOpen(false);
    navigate("/login", {
      replace: true,
      state: { loggedOutMessage: "Logged out successfully" },
    });
  };

  return (
    <div className="min-h-screen bg-[#020B18] text-[#F1F5F9] font-['Inter',sans-serif] flex flex-col overflow-x-hidden">
      {/* Top Command Header matching Reference Image */}
      <header className="sticky top-0 z-[1050] border-b border-[#1D3552] bg-[#061326]/95 backdrop-blur-md">
        <div className="flex min-h-[66px] items-center justify-between gap-3 px-4 lg:px-6">
          {/* Left Branding + Mobile Drawer Trigger */}
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open navigation menu"
              className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#1D3552] bg-[#0A1729] text-[#F1F5F9] lg:hidden"
            >
              <Menu size={20} />
            </button>

            {/* Bengaluru Traffic Police Emblem */}
            <div className="flex items-center gap-2.5 shrink-0">
              <BengaluruPoliceEmblem size={42} />
              <div className="hidden sm:block leading-tight">
                <div className="text-[13px] font-extrabold tracking-wide text-[#F1F5F9]">
                  BENGALURU
                </div>
                <div className="text-[13px] font-extrabold tracking-wide text-[#F1F5F9]">
                  TRAFFIC POLICE
                </div>
              </div>
            </div>

            <div className="hidden md:block h-8 w-[1px] bg-[#1D3552] mx-1" />

            <div className="hidden md:block">
              <SertosEcgLogo />
            </div>

            <div className="md:hidden">
              <SertosEcgLogo compact />
            </div>
          </div>

          {/* Right Header Controls: Page Context (compact), Live/Demo + Clock, Notification Bell, Officer Dropdown */}
          <div className="flex items-center gap-2.5 sm:gap-3">
            <div className="hidden xl:flex flex-col items-end pr-2 text-right">
              <span className="text-[12px] font-semibold text-[#F1F5F9]">{routeInfo.title}</span>
              <span className="text-[11px] text-[#94A3B8]">{routeInfo.breadcrumb}</span>
            </div>

            {/* Live / Demo System Status & IST Digital Clock */}
            <div className="relative" ref={statusRef}>
              <button
                type="button"
                onClick={() => setStatusMenuOpen((v) => !v)}
                aria-label="System connection status"
                className="flex items-center gap-2 rounded-xl border border-[#1D3552] bg-[#0A1729] px-3 py-2 text-[13px] font-medium transition hover:border-[#00D084]/50"
              >
                <span
                  className={`h-2.5 w-2.5 rounded-full ${
                    authMode === "live" && systemStatus.backend === "Connected"
                      ? "bg-[#20E39A] shadow-[0_0_8px_#20E39A]"
                      : "bg-[#F59E0B] shadow-[0_0_8px_#F59E0B]"
                  }`}
                />
                <span className="text-[#20E39A] font-semibold">
                  {authMode === "live" && systemStatus.backend === "Connected" ? "Live" : "Demo"}
                </span>
                <span className="text-[#94A3B8]">•</span>
                <span className="font-mono text-[13px] font-semibold tracking-wider text-[#F1F5F9]">
                  {clock}
                </span>
              </button>

              {statusMenuOpen && (
                <div className="absolute right-0 mt-2 w-72 rounded-xl border border-[#1D3552] bg-[#0A1729] p-3.5 shadow-2xl z-50">
                  <div className="flex items-center justify-between border-b border-[#1D3552] pb-2">
                    <span className="text-[12px] font-semibold text-[#F1F5F9]">
                      System Telemetry Status
                    </span>
                    <span className="text-[11px] text-[#94A3B8]">IST (Bengaluru)</span>
                  </div>
                  <div className="mt-2.5 space-y-2 text-[12px]">
                    <div className="flex items-center justify-between">
                      <span className="text-[#94A3B8]">System Online</span>
                      <span className="font-medium text-[#20E39A]">Operational</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[#94A3B8]">Backend Mode</span>
                      <span
                        className={`font-medium ${
                          systemStatus.backend === "Connected"
                            ? "text-[#20E39A]"
                            : "text-[#FBBF24]"
                        }`}
                      >
                        {systemStatus.backend}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[#94A3B8]">GPS Feed</span>
                      <span
                        className={`font-medium ${
                          systemStatus.gps === "Live Feed"
                            ? "text-[#20E39A]"
                            : "text-[#FBBF24]"
                        }`}
                      >
                        {systemStatus.gps}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[#94A3B8]">Signal Network</span>
                      <span
                        className={`font-medium ${
                          systemStatus.signalIntegration === "ESP32 Telemetry"
                            ? "text-[#20E39A]"
                            : "text-[#FBBF24]"
                        }`}
                      >
                        {systemStatus.signalIntegration}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Notification Bell */}
            <button
              type="button"
              onClick={() => setNotifOpen(true)}
              aria-label={`Open notifications (${unreadNotificationCount} unread)`}
              className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-[#1D3552] bg-[#0A1729] text-[#F1F5F9] transition hover:border-[#24A8FF]/60"
            >
              <Bell size={18} />
              {unreadNotificationCount > 0 && (
                <span className="absolute -right-1 -top-1 flex h-5 min-w-[20px] items-center justify-center rounded-full bg-[#EF4444] px-1 text-[10px] font-bold text-white shadow">
                  {unreadNotificationCount}
                </span>
              )}
            </button>

            {/* Officer Profile Dropdown */}
            <div className="relative" ref={profileRef}>
              <button
                type="button"
                onClick={() => setProfileMenuOpen((v) => !v)}
                aria-expanded={profileMenuOpen}
                aria-label="Officer profile menu"
                className="flex items-center gap-2.5 rounded-xl border border-[#1D3552] bg-[#0A1729] px-3 py-1.5 transition hover:border-[#24A8FF]/60"
              >
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#0D1D32] border border-[#1D3552] text-[#24A8FF]">
                  <Shield size={15} />
                </div>
                <span className="hidden sm:inline text-[13px] font-medium text-[#F1F5F9]">
                  {officerProfile.role}
                </span>
                <ChevronDown size={15} className="text-[#94A3B8]" />
              </button>

              {profileMenuOpen && (
                <div className="absolute right-0 mt-2 w-72 rounded-xl border border-[#1D3552] bg-[#0A1729] p-3 shadow-2xl z-50">
                  <div className="border-b border-[#1D3552] pb-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[14px] font-semibold text-[#F1F5F9]">
                        {officerProfile.name}
                      </span>
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                          authMode === "live"
                            ? "bg-[#00D084]/20 text-[#20E39A]"
                            : "bg-[#F59E0B]/20 text-[#FBBF24]"
                        }`}
                      >
                        {officerProfile.accountStatus}
                      </span>
                    </div>
                    <div className="mt-1 text-[12px] text-[#94A3B8]">{officerProfile.role}</div>
                    <div className="mt-2 space-y-1 text-[11px] text-[#94A3B8]">
                      <div>Officer ID: <span className="text-[#F1F5F9]">{officerProfile.officerId}</span></div>
                      <div>Zone: <span className="text-[#F1F5F9]">{officerProfile.assignedZone}</span></div>
                    </div>
                  </div>
                  <div className="mt-2 space-y-1">
                    <button
                      type="button"
                      onClick={() => {
                        setProfileMenuOpen(false);
                        navigate("/settings");
                      }}
                      className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-[13px] text-[#F1F5F9] hover:bg-[#0D1D32]"
                    >
                      <UserCheck size={15} className="text-[#24A8FF]" />
                      Officer Profile &amp; Settings
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setProfileMenuOpen(false);
                        setLogoutModalOpen(true);
                      }}
                      className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-[13px] text-[#EF4444] hover:bg-[#EF4444]/10"
                    >
                      <LogOut size={15} />
                      Logout
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Layout: Fixed Sidebar + Content */}
      <div className="flex flex-1 min-h-0 relative">
        {/* Mobile Sidebar Backdrop */}
        {sidebarOpen && (
          <button
            type="button"
            aria-label="Close sidebar"
            onClick={() => setSidebarOpen(false)}
            className="fixed inset-0 z-[1060] bg-[#020B18]/75 backdrop-blur-xs lg:hidden"
          />
        )}

        {/* Sidebar */}
        <aside
          className={`fixed inset-y-0 left-0 z-[1070] flex w-[230px] shrink-0 flex-col border-r border-[#1D3552] bg-[#061326] p-3.5 transition-transform duration-200 lg:static lg:translate-x-0 ${
            sidebarOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <div className="mb-3 flex items-center justify-between lg:hidden">
            <span className="text-[13px] font-bold tracking-wider text-[#20E39A]">
              NAVIGATION
            </span>
            <button
              type="button"
              onClick={() => setSidebarOpen(false)}
              aria-label="Close navigation menu"
              className="rounded-lg p-1 text-[#94A3B8] hover:bg-[#0D1D32]"
            >
              <X size={18} />
            </button>
          </div>

          <nav className="flex flex-col gap-1.5" aria-label="Traffic Police Navigation">
            {NAV_ITEMS.map(({ label, path, aliases, icon: Icon, showBadge }) => {
              const isAliasActive = aliases.includes(location.pathname);
              return (
                <NavLink
                  key={path}
                  to={path}
                  onClick={() => setSidebarOpen(false)}
                  className={({ isActive }) => {
                    const active = isActive || isAliasActive;
                    return `group flex items-center justify-between rounded-xl border px-3.5 py-2.5 text-[13px] font-medium transition ${
                      active
                        ? "border-[#00D084]/45 bg-[#0A2530] text-[#F1F5F9] shadow-[inset_3px_0_0_#20E39A]"
                        : "border-transparent text-[#94A3B8] hover:border-[#1D3552] hover:bg-[#0A1729] hover:text-[#F1F5F9]"
                    }`;
                  }}
                >
                  {({ isActive }) => {
                    const active = isActive || isAliasActive;
                    return (
                      <>
                        <span className="flex items-center gap-3">
                          <Icon
                            size={18}
                            className={
                              active
                                ? "text-[#20E39A]"
                                : "text-[#94A3B8] group-hover:text-[#F1F5F9]"
                            }
                          />
                          <span>{label}</span>
                        </span>
                        {showBadge && activeAlertsCount > 0 && (
                          <span className="flex h-5 min-w-[20px] items-center justify-center rounded-full bg-[#EF4444] px-1.5 text-[11px] font-bold text-white">
                            {activeAlertsCount}
                          </span>
                        )}
                      </>
                    );
                  }}
                </NavLink>
              );
            })}
          </nav>

          {/* Compact System Mode Card in Sidebar */}
          <div className="mt-4 rounded-xl border border-[#1D3552] bg-[#0A1729]/80 p-3 text-[11px]">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 font-semibold text-[#F1F5F9]">
                <Radio size={13} className="text-[#20E39A]" />
                {authMode === "live" ? "Live API Mode" : "Demo Control Mode"}
              </span>
              <Siren size={13} className="text-[#F59E0B]" />
            </div>
            <p className="mt-1 text-[#94A3B8] leading-snug">
              {authMode === "live"
                ? "Connected to SERTOS Django REST backend."
                : "Running simulated Bengaluru traffic & GPS telemetry."}
            </p>
          </div>

          {/* Bottom Bengaluru Vidhana Soudha Branding */}
          <div className="mt-auto pt-4">
            <VidhanaSoudhaVisual />
          </div>
        </aside>

        {/* Main Scrollable Content */}
        <main className="min-w-0 flex-1 overflow-y-auto p-4 lg:p-5">
          <div className="mx-auto max-w-[1600px]">{children}</div>
        </main>
      </div>

      {/* Notification Center Drawer */}
      <NotificationDrawer open={notifOpen} onClose={() => setNotifOpen(false)} />

      {/* Logout Confirmation Dialog */}
      <ConfirmModal
        open={logoutModalOpen}
        title="Confirm Officer Logout"
        description="Are you sure you want to end your SERTOS Traffic Police session? All active dashboard polling and protected cached data will be cleared."
        confirmLabel="Logout"
        cancelLabel="Stay Signed In"
        variant="danger"
        loading={loggingOut}
        onConfirm={() => void handleConfirmLogout()}
        onCancel={() => setLogoutModalOpen(false)}
      />

      <ToastContainer />
    </div>
  );
}
