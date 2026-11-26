import { useEffect } from "react";
import { AlertTriangle, X } from "lucide-react";

interface ConfirmModalProps {
  open: boolean;
  title: string;
  description: string;
  warning?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "warning" | "primary";
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmModal({
  open,
  title,
  description,
  warning,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "primary",
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !loading) onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, loading, onCancel]);

  if (!open) return null;

  const confirmColors =
    variant === "danger"
      ? "bg-[#EF4444] hover:bg-red-600 text-white"
      : variant === "warning"
        ? "bg-[#F59E0B] hover:bg-amber-600 text-[#020B18] font-semibold"
        : "bg-[#00D084] hover:bg-[#20E39A] text-[#020B18] font-semibold";

  return (
    <div
      className="fixed inset-0 z-[1200] flex items-center justify-center bg-[#020B18]/80 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-modal-title"
    >
      <div className="w-full max-w-md rounded-2xl border border-[#1D3552] bg-[#0A1729] p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div
              className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border ${
                variant === "danger"
                  ? "border-[#EF4444]/40 bg-[#EF4444]/15 text-[#EF4444]"
                  : variant === "warning"
                    ? "border-[#F59E0B]/40 bg-[#F59E0B]/15 text-[#F59E0B]"
                    : "border-[#00D084]/40 bg-[#00D084]/15 text-[#00D084]"
              }`}
            >
              <AlertTriangle size={20} />
            </div>
            <h3 id="confirm-modal-title" className="text-[17px] font-semibold text-[#F1F5F9]">
              {title}
            </h3>
          </div>
          <button
            type="button"
            onClick={onCancel}
            disabled={loading}
            aria-label="Close dialog"
            className="rounded-lg p-1 text-[#94A3B8] hover:bg-[#0D1D32] hover:text-[#F1F5F9]"
          >
            <X size={18} />
          </button>
        </div>

        <p className="mt-4 text-[13px] leading-relaxed text-[#94A3B8]">{description}</p>

        {warning && (
          <div className="mt-3 rounded-xl border border-[#F59E0B]/35 bg-[#F59E0B]/10 px-3.5 py-2.5 text-[12px] text-[#FBBF24]">
            {warning}
          </div>
        )}

        <div className="mt-6 flex items-center justify-end gap-2.5">
          <button
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="rounded-xl border border-[#1D3552] bg-[#0D1D32] px-4 py-2 text-[13px] font-medium text-[#F1F5F9] transition hover:border-[#24A8FF]/50 disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className={`rounded-xl px-4 py-2 text-[13px] transition disabled:opacity-50 ${confirmColors}`}
          >
            {loading ? "Processing..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
