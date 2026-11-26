
import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
    ShieldCheck,
    LayoutDashboard,
    Siren,
    MapPinned,
    GitBranch,
    History,
    UserRound,
    LogOut,
    Menu,
    X,
} from "lucide-react";

import "./traffic-police.css";
import { api } from "../../lib/api";
import { clearSession, getSession } from "../../lib/auth";

interface TrafficPoliceLayoutProps {
    children: ReactNode;
}

const navigation = [
    { label: "Dashboard", path: "/police", icon: LayoutDashboard, end: true },
    { label: "Alerts", path: "/police/alerts", icon: Siren },
    { label: "Tracking", path: "/police/tracking", icon: MapPinned },
    { label: "Junctions", path: "/police/junctions", icon: GitBranch },
    { label: "History", path: "/police/history", icon: History },
    { label: "Profile", path: "/police/profile", icon: UserRound },
];

export default function TrafficPoliceLayout({
    children,
}: TrafficPoliceLayoutProps) {
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const [officerName, setOfficerName] = useState(() => getSession()?.user.username || "Signed-in officer");
    const navigate = useNavigate();

    useEffect(() => {
        let mounted = true;
        api.getProfile()
            .then((profile) => {
                if (!mounted) return;
                const fullName = [profile.first_name, profile.last_name].filter(Boolean).join(" ");
                setOfficerName(fullName || profile.username);
            })
            .catch(() => undefined);
        return () => { mounted = false; };
    }, []);

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

    // Close sidebar when pressing Escape
    useEffect(() => {
        const handleEscape = (event: KeyboardEvent) => {
            if (event.key === "Escape") {
                setSidebarOpen(false);
            }
        };

        window.addEventListener("keydown", handleEscape);

        return () => {
            window.removeEventListener("keydown", handleEscape);
        };
    }, []);

    const closeSidebar = () => setSidebarOpen(false);

    return (
        <div className={`tp-app ${sidebarOpen ? "tp-sidebar-open" : ""}`}>

            {/* Mobile / Tablet Overlay */}
            {sidebarOpen && (
                <button
                    className="tp-sidebar-overlay"
                    type="button"
                    aria-label="Close navigation menu"
                    onClick={closeSidebar}
                />
            )}

            {/* Sidebar */}
            <aside
                className={`tp-sidebar ${sidebarOpen ? "tp-sidebar-visible" : ""}`}
            >

                <div className="tp-brand">
                    <div className="tp-brand-logo">
                        <ShieldCheck size={29} strokeWidth={1.8} />
                    </div>

                    <div className="tp-brand-name">SERTOS</div>
                    <div className="tp-brand-caption">
                        EMERGENCY RESPONSE
                    </div>

                    {/* Mobile / Tablet Close Button */}
                    <button
                        className="tp-sidebar-close"
                        type="button"
                        onClick={closeSidebar}
                        aria-label="Close sidebar"
                    >
                        <X size={22} />
                    </button>
                </div>

                <div className="tp-nav-heading">MAIN MENU</div>

                <nav className="tp-navigation">
                    {navigation.map(({ label, path, icon: Icon, end }) => (
                        <NavLink
                            key={path}
                            to={path}
                            end={end}
                            onClick={closeSidebar}
                            className={({ isActive }) =>
                                `tp-nav-link ${isActive ? "tp-nav-active" : ""}`
                            }
                        >
                            <Icon size={19} strokeWidth={1.9} />
                            <span>{label}</span>
                        </NavLink>
                    ))}
                </nav>

                <div className="tp-sidebar-bottom">
                    <div className="tp-officer-mini">
                        <div className="tp-officer-avatar">{officerName.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase()}</div>

                        <div className="tp-officer-info">
                            <strong>{officerName}</strong>
                            <span>Traffic Police</span>
                        </div>
                    </div>

                    <button
                        className="tp-logout-button"
                        type="button"
                        onClick={handleLogout}
                    >
                        <LogOut size={17} />
                        <span>Logout</span>
                    </button>
                </div>
            </aside>

            {/* Main Content */}
            <main className="tp-main">

                {/* Hamburger Button */}
                <button
                    className="tp-menu-button"
                    type="button"
                    onClick={() => setSidebarOpen(true)}
                    aria-label="Open navigation menu"
                    aria-expanded={sidebarOpen}
                >
                    <Menu size={24} />
                </button>

                <div className="tp-main-content">
                    {children}
                </div>
            </main>
        </div>
    );
}
