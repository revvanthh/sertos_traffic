import { CheckCircle2, Info, AlertTriangle, X, XCircle } from "lucide-react";
import { usePoliceControl } from "../../context/PoliceControlContext";

export function ToastContainer() {
  const { toasts, dismissToast } = usePoliceControl();

  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed bottom-4 right-4 z-[1300] flex w-full max-w-sm flex-col gap-2 px-4 sm:px-0"
      aria-live="polite"
    >
      {toasts.map((toast) => {
        const icon =
          toast.variant === "success" ? (
            <CheckCircle2 size={18} className="text-[#20E39A]" />
          ) : toast.variant === "warning" ? (
            <AlertTriangle size={18} className="text-[#F59E0B]" />
          ) : toast.variant === "error" ? (
            <XCircle size={18} className="text-[#EF4444]" />
          ) : (
            <Info size={18} className="text-[#24A8FF]" />
          );

        return (
          <div
            key={toast.id}
            className="flex items-start gap-3 rounded-xl border border-[#1D3552] bg-[#0A1729]/95 p-3.5 shadow-xl backdrop-blur"
          >
            <div className="mt-0.5 shrink-0">{icon}</div>
            <div className="min-w-0 flex-1">
              <div className="text-[13px] font-semibold text-[#F1F5F9]">{toast.title}</div>
              {toast.description && (
                <div className="mt-0.5 text-[12px] text-[#94A3B8]">{toast.description}</div>
              )}
            </div>
            <button
              type="button"
              onClick={() => dismissToast(toast.id)}
              aria-label="Dismiss notification"
              className="rounded p-1 text-[#94A3B8] hover:bg-[#0D1D32] hover:text-[#F1F5F9]"
            >
              <X size={14} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
