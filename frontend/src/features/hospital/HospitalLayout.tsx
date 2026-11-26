
import { useCallback, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
    HeartPulse,
    LayoutDashboard,
    Bell,
    BedDouble,
    Ambulance,
    History,
    ChartColumnIncreasing,
    Building2,
    LogOut,
    Menu,
    X,
    Search,
    ChevronDown,
    CircleUserRound,
} from "lucide-react";

import "./hospital.css";
import { api } from "../../lib/api";
import { clearSession, getSession } from "../../lib/auth";
import { useLiveQuery } from "../../lib/useLiveQuery";
import type { Incident, UserProfile } from "../../lib/api";

interface HospitalLayoutProps {
    children: React.ReactNode;
}

const navigation = [
    {
        name: "Hospital Dashboard",
        path: "/hospital",
        icon: LayoutDashboard,
    },
    {
        name: "Emergency Alerts",
        path: "/hospital/alerts",
        icon: Bell,
    },
    {
        name: "Bed Management",
        path: "/hospital/beds",
        icon: BedDouble,
    },
    {
        name: "Ambulance Tracking",
        path: "/hospital/tracking",
        icon: Ambulance,
    },
    {
        name: "Emergency History",
        path: "/hospital/history",
        icon: History,
    },
    {
        name: "Reports",
        path: "/hospital/reports",
        icon: ChartColumnIncreasing,
    },
    {
        name: "Hospital Profile",
        path: "/hospital/profile",
        icon: Building2,
    },

];

type HospitalLayoutData = { profile: UserProfile; incidents: Incident[] };

export default function HospitalLayout({
    children,
}: HospitalLayoutProps) {
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const navigate = useNavigate();
    const loadLayoutData = useCallback(async (): Promise<HospitalLayoutData> => {
        const [profile, incidents] = await Promise.all([api.getProfile(), api.getHospitalIncidents()]);
        return { profile, incidents };
    }, []);
    const { data: layoutData, error: connectionError } = useLiveQuery(loadLayoutData, 12_000);
    const hospitalName = layoutData?.incidents[0]?.hospital_name || "Hospital Operations";
    const hospitalCode = layoutData?.incidents[0]?.hospital_code || "Assigned facility";
    const staffName = layoutData?.profile.first_name || layoutData?.profile.username || "Hospital staff";
    const pendingAlerts = layoutData?.incidents.filter((incident) => !incident.hospital_decision && !["CLOSED", "CANCELLED"].includes(incident.status)).length ?? 0;
    const connectionLabel = connectionError ? "API unavailable" : layoutData ? "Live connection" : "Connecting…";

    const handleLogout = async () => {
        const refresh = getSession()?.refresh;
        if (refresh) {
            try {
                await api.logout(refresh);
            } catch {
                // Clear the local session even if the backend cannot be reached.
            }
        }
        clearSession();
        navigate("/", { replace: true });
    };

    return (
        <div className="hospital-app">

            {/* Mobile overlay */}
            {sidebarOpen && (
                <button
                    className="hospital-overlay"
                    onClick={() => setSidebarOpen(false)}
                    aria-label="Close sidebar"
                />
            )}

            {/* Sidebar */}
            <aside
                className={`hospital-sidebar ${sidebarOpen ? "hospital-sidebar-open" : ""
                    }`}
            >
                <div className="hospital-brand">
                    <div className="hospital-brand-icon">
                        <HeartPulse size={32} />
                    </div>

                    <div>
                        <h1>SERTOS</h1>
                        <p>Smart Emergency Response</p>
                        <p>Through Optimal Selection</p>
                    </div>

                    <button
                        className="hospital-close"
                        onClick={() => setSidebarOpen(false)}
                        aria-label="Close navigation"
                    >
                        <X size={22} />
                    </button>
                </div>

                <div className="hospital-nav-section">
                    <p className="hospital-nav-label">HOSPITAL MANAGEMENT</p>

                    <nav className="hospital-navigation">
                        {navigation.map((item) => {
                            const Icon = item.icon;

                            return (
                                <NavLink
                                    key={item.path}
                                    to={item.path}
                                    end={item.path === "/hospital"}
                                    onClick={() => setSidebarOpen(false)}
                                    className={({ isActive }) =>
                                        `hospital-nav-link ${isActive ? "active" : ""
                                        }`
                                    }
                                >
                                    <Icon size={20} strokeWidth={2} />
                                    <span>{item.name}</span>

                                    {item.name === "Emergency Alerts" && pendingAlerts > 0 && (
                                        <span className="hospital-alert-count">{pendingAlerts}</span>
                                    )}
                                </NavLink>
                            );
                        })}
                    </nav>
                </div>

                {/* Hospital information */}
                <div className="hospital-sidebar-bottom">
                    <div className="hospital-info-card">
                        <div className="hospital-info-image">
                            <Building2 size={38} />
                        </div>

                        <h3>{hospitalName}</h3>
                        <p>{hospitalCode}</p>

                        <span className="hospital-online">
                            <span />
                            {connectionLabel}
                        </span>
                    </div>

                    <button className="hospital-logout" type="button" onClick={handleLogout}>
                        <LogOut size={19} />
                        <span>Logout</span>
                    </button>
                </div>
            </aside>

            {/* Main content */}
            <main className="hospital-main">

                {/* Top navigation */}
                <header className="hospital-topbar">

                    <button
                        className="hospital-menu-button"
                        onClick={() => setSidebarOpen(true)}
                        aria-label="Open navigation"
                    >
                        <Menu size={24} />
                    </button>

                    <button className="hospital-search" type="button" onClick={() => navigate("/hospital/alerts")}>
                        <Search size={19} />
                        <span>Open incident queue</span>
                    </button>

                    <div className="hospital-topbar-right">
                        <span className="hospital-status">
                            <span />
                            {connectionLabel}
                        </span>

                        <button className="hospital-notification-button" type="button" aria-label="Open emergency alerts" onClick={() => navigate("/hospital/alerts")}>
                            <Bell size={21} />
                            {pendingAlerts > 0 && <span>{pendingAlerts}</span>}
                        </button>

                        <button className="hospital-user" type="button" onClick={() => navigate("/hospital/profile")}>
                            <div className="hospital-avatar">
                                <CircleUserRound size={22} />
                            </div>

                            <div className="hospital-user-details">
                                <strong>{staffName}</strong>
                                <small>{hospitalName}</small>
                            </div>

                            <ChevronDown size={17} />
                        </button>
                    </div>
                </header>

                {/* Page content */}
                <div className="hospital-content">
                    {children}
                </div>

            </main>
        </div>
    );
}
