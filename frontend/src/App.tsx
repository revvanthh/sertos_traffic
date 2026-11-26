import { useEffect, type ReactNode } from "react";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useNavigate,
} from "react-router-dom";

import DriverPage from "./features/driver/DriverPage";
import ConfirmationPage from "./features/driver/ConfirmationPage";
import HospitalLayout from "./features/hospital/HospitalLayout";
import HospitalDashboard from "./features/hospital/HospitalDashboard";
import BedManagement from "./features/hospital/BedManagement";
import EmergencyAlerts from "./features/hospital/EmergencyAlerts";
import HospitalTracking from "./features/hospital/HospitalTracking";
import HospitalReports from "./features/hospital/HospitalReports";
import AdminDashboard from "./features/admin/AdminDashboard";
import TrafficDeviceManagement from "./features/admin/TrafficDeviceManagement";
import IncidentHistory from "./features/shared/IncidentHistory";
import ProfilePage from "./features/shared/ProfilePage";
import { getSession } from "./lib/auth";

import { PoliceControlProvider } from "./context/PoliceControlContext";
import { PoliceShell } from "./components/layout/PoliceShell";
import LoginPage from "./pages/police/LoginPage";
import DashboardPage from "./pages/police/DashboardPage";
import TrafficControlPage from "./pages/police/TrafficControlPage";
import EmergencyAlertsPage from "./pages/police/EmergencyAlertsPage";
import AmbulanceTrackingPage from "./pages/police/AmbulanceTrackingPage";
import ReportsPage from "./pages/police/ReportsPage";
import SettingsPage from "./pages/police/SettingsPage";

type UserRole = "driver" | "traffic_police" | "hospital" | "admin";

function SessionExpiryRedirect() {
  const navigate = useNavigate();

  useEffect(() => {
    const redirect = () => navigate("/login", { replace: true });
    window.addEventListener("sertos:session-expired", redirect);
    return () => window.removeEventListener("sertos:session-expired", redirect);
  }, [navigate]);

  return null;
}

function ProtectedRoute({
  role,
  children,
}: {
  role: UserRole;
  children: ReactNode;
}) {
  const session = getSession();
  const roleMap: Record<UserRole, string> = {
    driver: "AMBULANCE_DRIVER",
    traffic_police: "POLICE_DISPATCHER",
    hospital: "HOSPITAL_STAFF",
    admin: "ADMIN",
  };

  if (!session) {
    return <Navigate to="/login" replace />;
  }

  if (session.user.role !== roleMap[role] && session.user.role !== "ADMIN") {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

function PoliceRouteWrapper({ children }: { children: ReactNode }) {
  return (
    <ProtectedRoute role="traffic_police">
      <PoliceControlProvider>
        <PoliceShell>{children}</PoliceShell>
      </PoliceControlProvider>
    </ProtectedRoute>
  );
}

function App() {
  return (
    <BrowserRouter>
      <SessionExpiryRedirect />
      <Routes>
        {/* Authentication */}
        <Route path="/" element={<LoginPage />} />
        <Route path="/login" element={<LoginPage />} />

        {/* Bengaluru Traffic Police Emergency Control Routes */}
        <Route
          path="/dashboard"
          element={
            <PoliceRouteWrapper>
              <DashboardPage />
            </PoliceRouteWrapper>
          }
        />
        <Route
          path="/traffic-control"
          element={
            <PoliceRouteWrapper>
              <TrafficControlPage />
            </PoliceRouteWrapper>
          }
        />
        <Route
          path="/emergency-alerts"
          element={
            <PoliceRouteWrapper>
              <EmergencyAlertsPage />
            </PoliceRouteWrapper>
          }
        />
        <Route
          path="/ambulance-tracking"
          element={
            <PoliceRouteWrapper>
              <AmbulanceTrackingPage />
            </PoliceRouteWrapper>
          }
        />
        <Route
          path="/reports"
          element={
            <PoliceRouteWrapper>
              <ReportsPage />
            </PoliceRouteWrapper>
          }
        />
        <Route
          path="/settings"
          element={
            <PoliceRouteWrapper>
              <SettingsPage />
            </PoliceRouteWrapper>
          }
        />

        {/* Backward-compatible /police/* route aliases */}
        <Route
          path="/police"
          element={
            <PoliceRouteWrapper>
              <DashboardPage />
            </PoliceRouteWrapper>
          }
        />
        <Route
          path="/police/alerts"
          element={
            <PoliceRouteWrapper>
              <EmergencyAlertsPage />
            </PoliceRouteWrapper>
          }
        />
        <Route
          path="/police/tracking"
          element={
            <PoliceRouteWrapper>
              <AmbulanceTrackingPage />
            </PoliceRouteWrapper>
          }
        />
        <Route
          path="/police/junctions"
          element={
            <PoliceRouteWrapper>
              <TrafficControlPage />
            </PoliceRouteWrapper>
          }
        />
        <Route
          path="/police/reports"
          element={
            <PoliceRouteWrapper>
              <ReportsPage />
            </PoliceRouteWrapper>
          }
        />
        <Route
          path="/police/history"
          element={
            <PoliceRouteWrapper>
              <ReportsPage />
            </PoliceRouteWrapper>
          }
        />
        <Route
          path="/police/settings"
          element={
            <PoliceRouteWrapper>
              <SettingsPage />
            </PoliceRouteWrapper>
          }
        />
        <Route
          path="/police/profile"
          element={
            <PoliceRouteWrapper>
              <SettingsPage />
            </PoliceRouteWrapper>
          }
        />

        {/* Existing Admin Routes */}
        <Route
          path="/admin"
          element={
            <ProtectedRoute role="admin">
              <AdminDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/traffic-devices"
          element={
            <ProtectedRoute role="admin">
              <TrafficDeviceManagement />
            </ProtectedRoute>
          }
        />

        {/* Existing Driver Routes */}
        <Route
          path="/driver"
          element={
            <ProtectedRoute role="driver">
              <DriverPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/driver/confirmation"
          element={
            <ProtectedRoute role="driver">
              <ConfirmationPage />
            </ProtectedRoute>
          }
        />

        {/* Existing Hospital Routes */}
        <Route
          path="/hospital"
          element={
            <ProtectedRoute role="hospital">
              <HospitalLayout>
                <HospitalDashboard />
              </HospitalLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/hospital/beds"
          element={
            <ProtectedRoute role="hospital">
              <HospitalLayout>
                <BedManagement />
              </HospitalLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/hospital/alerts"
          element={
            <ProtectedRoute role="hospital">
              <HospitalLayout>
                <EmergencyAlerts />
              </HospitalLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/hospital/tracking"
          element={
            <ProtectedRoute role="hospital">
              <HospitalLayout>
                <HospitalTracking />
              </HospitalLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/hospital/history"
          element={
            <ProtectedRoute role="hospital">
              <HospitalLayout>
                <IncidentHistory role="hospital" />
              </HospitalLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/hospital/reports"
          element={
            <ProtectedRoute role="hospital">
              <HospitalLayout>
                <HospitalReports />
              </HospitalLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/hospital/profile"
          element={
            <ProtectedRoute role="hospital">
              <HospitalLayout>
                <ProfilePage />
              </HospitalLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/hospital/settings"
          element={
            <ProtectedRoute role="hospital">
              <Navigate to="/hospital/profile" replace />
            </ProtectedRoute>
          }
        />

        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
