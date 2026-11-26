import { useEffect, useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  AlertCircle,
  CheckCircle2,
  Eye,
  EyeOff,
  KeyRound,
  Lock,
  Radio,
  ShieldCheck,
  X,
} from "lucide-react";
import { ENV } from "../../config/env";
import { ApiError, api } from "../../lib/api";
import { getSession } from "../../lib/auth";
import {
  authenticateOfficer,
  checkBackendHealth,
  getRoleDestination,
} from "../../services/authService";
import {
  BengaluruPoliceEmblem,
  SertosEcgLogo,
} from "../../components/common/SertosBranding";

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const routeState = (location.state as { loggedOutMessage?: string } | null) ?? null;

  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [registration, setRegistration] = useState({
    email: "",
    phone_number: "",
    badge_or_employee_id: "",
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(routeState?.loggedOutMessage ?? "");
  const [backendStatus, setBackendStatus] = useState<"checking" | "online" | "offline">(
    "checking",
  );
  const [forgotModalOpen, setForgotModalOpen] = useState(false);

  // Redirect already-authenticated users to their dashboard
  useEffect(() => {
    const existing = getSession();
    if (existing) {
      navigate(getRoleDestination(existing.user.role), { replace: true });
    }
  }, [navigate]);

  useEffect(() => {
    let mounted = true;
    checkBackendHealth().then((res) => {
      if (!mounted) return;
      setBackendStatus(res.reachable ? "online" : "offline");
    });
    return () => {
      mounted = false;
    };
  }, []);

  const handleSubmitLogin = async (e: FormEvent, preferDemo = false) => {
    e.preventDefault();
    if (loading) return;

    setError("");
    setNotice("");

    const trimmedId = identifier.trim();
    if (!trimmedId) {
      setError("Please enter your Email or Officer ID.");
      return;
    }
    if (!password.trim()) {
      setError("Please enter your password.");
      return;
    }

    setLoading(true);
    try {
      const result = await authenticateOfficer({
        identifier: trimmedId,
        password,
        rememberMe,
        preferDemo,
      });
      navigate(result.redirectTo, { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Authentication failed. Verify your credentials and try again.",
      );
    } finally {
      setLoading(false);
    }
  };

  const handleDriverRegistration = async (e: FormEvent) => {
    e.preventDefault();
    if (loading) return;
    setError("");
    setNotice("");
    setLoading(true);
    try {
      const result = await api.registerDriver({
        username: identifier.trim(),
        email: registration.email.trim(),
        password,
        phone_number: registration.phone_number.trim(),
        badge_or_employee_id: registration.badge_or_employee_id.trim(),
      });
      setIdentifier(result.username);
      setPassword("");
      setNotice(
        "Driver account request received. Sign-in stays locked until an administrator verifies the account.",
      );
      setMode("login");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Unable to submit driver registration.",
      );
    } finally {
      setLoading(false);
    }
  };

  const fillDemoCredentials = () => {
    setIdentifier(ENV.DEMO_OFFICER_ID);
    setPassword(ENV.DEMO_OFFICER_PASSWORD);
    setError("");
  };

  return (
    <div className="min-h-screen bg-[#020B18] text-[#F1F5F9] font-['Inter',sans-serif] flex flex-col justify-between">
      <div className="mx-auto flex w-full max-w-6xl flex-1 items-center px-4 py-8 sm:px-6 lg:px-8">
        <div className="grid w-full grid-cols-1 overflow-hidden rounded-3xl border border-[#1D3552] bg-[#061326] shadow-2xl lg:grid-cols-[1.1fr_0.95fr]">
          {/* Left Branding & Emergency Network Panel */}
          <section className="relative flex flex-col justify-between border-b border-[#1D3552] bg-gradient-to-br from-[#061326] via-[#0A1729] to-[#040E1E] p-7 sm:p-10 lg:border-b-0 lg:border-r">
            <div>
              <div className="flex items-center gap-3">
                <BengaluruPoliceEmblem size={48} />
                <div>
                  <div className="text-[12px] font-bold tracking-[0.14em] text-[#20E39A]">
                    BENGALURU TRAFFIC POLICE
                  </div>
                  <div className="text-[12px] text-[#94A3B8]">
                    Emergency Operations Command Portal
                  </div>
                </div>
              </div>

              <div className="mt-8">
                <SertosEcgLogo />
              </div>

              <h1 className="mt-7 text-[26px] font-bold leading-snug tracking-tight text-[#F1F5F9] sm:text-[30px]">
                Protecting Bengaluru.
                <br />
                <span className="text-[#20E39A]">Clearing the Way.</span>
              </h1>

              <p className="mt-3 max-w-md text-[13px] leading-relaxed text-[#94A3B8]">
                Unified real-time coordination connecting emergency ambulances, hospitals, traffic signal networks, and Bengaluru Traffic Police dispatch units.
              </p>
            </div>

            {/* Subtle Emergency Network SVG Visual */}
            <div className="my-7 rounded-2xl border border-[#1D3552] bg-[#040E1E]/85 p-4">
              <div className="mb-2 flex items-center justify-between text-[11px] text-[#94A3B8]">
                <span className="flex items-center gap-1.5 font-medium text-[#F1F5F9]">
                  <Radio size={13} className="text-[#20E39A]" />
                  Bengaluru Corridor Telemetry Grid
                </span>
                <span className="text-[#24A8FF] font-semibold">MG Rd • Indiranagar • VVIT</span>
              </div>
              <svg
                viewBox="0 0 420 120"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                className="h-24 w-full"
                aria-hidden="true"
              >
                <path
                  d="M20 88L96 68L178 72L265 44L345 34L400 22"
                  stroke="#24A8FF"
                  strokeWidth="3"
                  strokeLinecap="round"
                />
                <path
                  d="M20 38L120 48L210 92L310 78L400 84"
                  stroke="#1D3552"
                  strokeWidth="1.8"
                  strokeDasharray="4 4"
                />
                <path
                  d="M96 68L120 48M178 72L210 92M265 44L310 78"
                  stroke="#00D084"
                  strokeOpacity="0.45"
                  strokeWidth="1.5"
                />
                {[
                  { x: 96, y: 68, color: "#00D084" },
                  { x: 178, y: 72, color: "#20E39A" },
                  { x: 265, y: 44, color: "#24A8FF" },
                  { x: 345, y: 34, color: "#EF4444" },
                ].map((node, i) => (
                  <g key={i}>
                    <circle cx={node.x} cy={node.y} r="8" fill={node.color} fillOpacity="0.18" />
                    <circle cx={node.x} cy={node.y} r="3.5" fill={node.color} />
                  </g>
                ))}
              </svg>
            </div>

            {/* Connection & Security Indicator */}
            <div className="flex flex-wrap items-center justify-between gap-2 text-[12px] text-[#94A3B8]">
              <div className="flex items-center gap-2">
                <Lock size={14} className="text-[#20E39A]" />
                <span>Protected JWT &amp; Role-Based Access</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span
                  className={`h-2 w-2 rounded-full ${
                    backendStatus === "online"
                      ? "bg-[#20E39A]"
                      : backendStatus === "offline"
                        ? "bg-[#F59E0B]"
                        : "bg-[#94A3B8] animate-pulse"
                  }`}
                />
                <span>
                  {backendStatus === "online"
                    ? "Django Backend Connected"
                    : backendStatus === "offline"
                      ? "Backend Offline — Demo Mode Available"
                      : "Checking API status..."}
                </span>
              </div>
            </div>
          </section>

          {/* Right Login Form Panel */}
          <section className="flex flex-col justify-center bg-[#0A1729] p-7 sm:p-10">
            <div className="mb-6">
              <div className="inline-flex items-center gap-1.5 rounded-full border border-[#00D084]/35 bg-[#00D084]/10 px-3 py-1 text-[11px] font-semibold text-[#20E39A]">
                <ShieldCheck size={13} />
                Secure Officer Sign-In
              </div>
              <h2 className="mt-3 text-[22px] font-bold text-[#F1F5F9]">
                {mode === "login" ? "Control Center Login" : "Request Ambulance Driver Access"}
              </h2>
              <p className="mt-1 text-[13px] text-[#94A3B8]">
                {mode === "login"
                  ? "Sign in with your Bengaluru Traffic Police credentials or authorized SERTOS account."
                  : "Creates an unverified ambulance driver account pending administrator approval."}
              </p>
            </div>

            {notice && (
              <div
                role="status"
                className="mb-4 flex items-center gap-2 rounded-xl border border-[#00D084]/40 bg-[#00D084]/12 px-3.5 py-2.5 text-[13px] text-[#20E39A]"
              >
                <CheckCircle2 size={16} className="shrink-0" />
                <span>{notice}</span>
              </div>
            )}

            {error && (
              <div
                role="alert"
                className="mb-4 flex items-center gap-2 rounded-xl border border-[#EF4444]/40 bg-[#EF4444]/12 px-3.5 py-2.5 text-[13px] text-[#FCA5A5]"
              >
                <AlertCircle size={16} className="shrink-0 text-[#EF4444]" />
                <span>{error}</span>
              </div>
            )}

            <form
              onSubmit={
                mode === "login"
                  ? (e) => void handleSubmitLogin(e, false)
                  : (e) => void handleDriverRegistration(e)
              }
              noValidate
              className="space-y-4"
            >
              <div>
                <label
                  htmlFor="login-identifier"
                  className="mb-1.5 block text-[12px] font-medium text-[#F1F5F9]"
                >
                  {mode === "login" ? "Email or Officer ID" : "Username"}
                </label>
                <input
                  id="login-identifier"
                  type="text"
                  autoComplete="username"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder={
                    mode === "login" ? "e.g. BTP-INSP-1047 or officer email" : "Choose a username"
                  }
                  disabled={loading}
                  className="w-full rounded-xl border border-[#1D3552] bg-[#061326] px-3.5 py-2.5 text-[13px] text-[#F1F5F9] placeholder-[#94A3B8]/60 outline-none transition focus:border-[#24A8FF]"
                />
              </div>

              {mode === "register" && (
                <>
                  <div>
                    <label
                      htmlFor="reg-email"
                      className="mb-1.5 block text-[12px] font-medium text-[#F1F5F9]"
                    >
                      Email
                    </label>
                    <input
                      id="reg-email"
                      type="email"
                      value={registration.email}
                      onChange={(e) =>
                        setRegistration({ ...registration, email: e.target.value })
                      }
                      placeholder="you@hospital.org"
                      disabled={loading}
                      className="w-full rounded-xl border border-[#1D3552] bg-[#061326] px-3.5 py-2.5 text-[13px] text-[#F1F5F9] placeholder-[#94A3B8]/60 outline-none focus:border-[#24A8FF]"
                    />
                  </div>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div>
                      <label
                        htmlFor="reg-phone"
                        className="mb-1.5 block text-[12px] font-medium text-[#F1F5F9]"
                      >
                        Phone Number
                      </label>
                      <input
                        id="reg-phone"
                        type="tel"
                        value={registration.phone_number}
                        onChange={(e) =>
                          setRegistration({ ...registration, phone_number: e.target.value })
                        }
                        placeholder="+91..."
                        disabled={loading}
                        className="w-full rounded-xl border border-[#1D3552] bg-[#061326] px-3.5 py-2.5 text-[13px] text-[#F1F5F9] placeholder-[#94A3B8]/60 outline-none focus:border-[#24A8FF]"
                      />
                    </div>
                    <div>
                      <label
                        htmlFor="reg-badge"
                        className="mb-1.5 block text-[12px] font-medium text-[#F1F5F9]"
                      >
                        Fleet / Employee ID
                      </label>
                      <input
                        id="reg-badge"
                        type="text"
                        value={registration.badge_or_employee_id}
                        onChange={(e) =>
                          setRegistration({
                            ...registration,
                            badge_or_employee_id: e.target.value,
                          })
                        }
                        placeholder="KA-01-..."
                        disabled={loading}
                        className="w-full rounded-xl border border-[#1D3552] bg-[#061326] px-3.5 py-2.5 text-[13px] text-[#F1F5F9] placeholder-[#94A3B8]/60 outline-none focus:border-[#24A8FF]"
                      />
                    </div>
                  </div>
                </>
              )}

              <div>
                <label
                  htmlFor="login-password"
                  className="mb-1.5 block text-[12px] font-medium text-[#F1F5F9]"
                >
                  Password
                </label>
                <div className="flex items-center rounded-xl border border-[#1D3552] bg-[#061326] px-3.5 focus-within:border-[#24A8FF]">
                  <input
                    id="login-password"
                    type={showPassword ? "text" : "password"}
                    autoComplete={mode === "login" ? "current-password" : "new-password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    disabled={loading}
                    className="w-full bg-transparent py-2.5 text-[13px] text-[#F1F5F9] placeholder-[#94A3B8]/60 outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    className="ml-2 text-[#94A3B8] hover:text-[#F1F5F9]"
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              {mode === "login" && (
                <div className="flex items-center justify-between text-[12px]">
                  <label className="flex cursor-pointer items-center gap-2 text-[#94A3B8]">
                    <input
                      type="checkbox"
                      checked={rememberMe}
                      onChange={(e) => setRememberMe(e.target.checked)}
                      className="h-4 w-4 rounded border-[#1D3552] bg-[#061326] accent-[#00D084]"
                    />
                    <span>Remember me</span>
                  </label>
                  <button
                    type="button"
                    onClick={() => setForgotModalOpen(true)}
                    className="font-medium text-[#24A8FF] hover:underline"
                  >
                    Forgot password?
                  </button>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#00D084] py-2.5 text-[14px] font-semibold text-[#020B18] shadow-[0_0_18px_rgba(0,208,132,0.28)] transition hover:bg-[#20E39A] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading ? (
                  <>
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-[#020B18]/30 border-t-[#020B18]" />
                    Authenticating...
                  </>
                ) : mode === "login" ? (
                  "Login to Control Center"
                ) : (
                  "Submit Driver Request"
                )}
              </button>
            </form>

            {/* Configurable Demo Mode Credentials Card — displayed ONLY when DEMO MODE is enabled */}
            {mode === "login" && ENV.DEMO_MODE_ENABLED && (
              <div className="mt-5 rounded-2xl border border-[#F59E0B]/35 bg-[#0D1D32] p-4">
                <div className="flex items-center justify-between gap-2">
                  <span className="inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-[#FBBF24]">
                    <KeyRound size={13} />
                    DEMO MODE (Simulated Session)
                  </span>
                  <button
                    type="button"
                    onClick={fillDemoCredentials}
                    className="rounded-lg border border-[#1D3552] bg-[#061326] px-2.5 py-1 text-[11px] font-semibold text-[#20E39A] hover:border-[#00D084]"
                  >
                    Use Demo Credentials
                  </button>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-[#94A3B8]">
                  <div>
                    Officer ID:{" "}
                    <code className="text-[#F1F5F9]">{ENV.DEMO_OFFICER_ID}</code>
                  </div>
                  <div>
                    Password:{" "}
                    <code className="text-[#F1F5F9]">{ENV.DEMO_OFFICER_PASSWORD}</code>
                  </div>
                </div>
                <button
                  type="button"
                  disabled={loading}
                  onClick={(e) => void handleSubmitLogin(e, true)}
                  className="mt-2.5 w-full rounded-xl border border-[#F59E0B]/40 bg-[#F59E0B]/15 py-1.5 text-[12px] font-semibold text-[#FBBF24] transition hover:bg-[#F59E0B]/25 disabled:opacity-50"
                >
                  Sign In via Demo Mode
                </button>
              </div>
            )}

            <button
              type="button"
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError("");
                setNotice("");
              }}
              className="mt-4 text-center text-[12px] font-medium text-[#94A3B8] hover:text-[#20E39A]"
            >
              {mode === "login"
                ? "Ambulance Driver? Request driver verification access"
                : "Back to Traffic Control Login"}
            </button>
          </section>
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-[#1D3552]/60 bg-[#061326]/60 py-3.5 text-center text-[11px] text-[#94A3B8]">
        <span className="font-semibold text-[#F1F5F9]">Authorized Personnel Only</span>
        <span className="mx-2">•</span>
        <span>Bengaluru Traffic Police Emergency Control</span>
      </footer>

      {/* Forgot Password Modal */}
      {forgotModalOpen && (
        <div
          className="fixed inset-0 z-[1200] flex items-center justify-center bg-[#020B18]/80 p-4 backdrop-blur-xs"
          role="dialog"
          aria-modal="true"
          aria-label="Password Reset Guidance"
        >
          <div className="w-full max-w-md rounded-2xl border border-[#1D3552] bg-[#0A1729] p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#1D3552] pb-3">
              <h3 className="text-[16px] font-semibold text-[#F1F5F9]">
                Password Recovery Protocol
              </h3>
              <button
                type="button"
                onClick={() => setForgotModalOpen(false)}
                aria-label="Close modal"
                className="rounded-lg p-1 text-[#94A3B8] hover:bg-[#0D1D32]"
              >
                <X size={18} />
              </button>
            </div>
            <p className="mt-3 text-[13px] leading-relaxed text-[#94A3B8]">
              SERTOS officer credentials are managed centrally by Bengaluru Traffic Police IT Command. Self-service password reset is disabled for security. Contact your Division System Administrator to reset your credentials or use Demo Mode when enabled.
            </p>
            <div className="mt-5 flex justify-end">
              <button
                type="button"
                onClick={() => setForgotModalOpen(false)}
                className="rounded-xl bg-[#00D084] px-4 py-2 text-[13px] font-semibold text-[#020B18]"
              >
                Understood
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
