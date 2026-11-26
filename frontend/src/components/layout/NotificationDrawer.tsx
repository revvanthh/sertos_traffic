import { useNavigate } from "react-router-dom";
import { Bell, CheckCheck, ExternalLink, Trash2, X } from "lucide-react";
import { usePoliceControl } from "../../context/PoliceControlContext";
import { StatusBadge } from "../common/StatusBadge";

interface NotificationDrawerProps {
  open: boolean;
  onClose: () => void;
}

export function NotificationDrawer({ open, onClose }: NotificationDrawerProps) {
  const navigate = useNavigate();
  const {
    notifications,
    unreadNotificationCount,
    markNotificationRead,
    markAllNotificationsRead,
    clearAllNotifications,
    setSelectedEmergencyId,
  } = usePoliceControl();

  if (!open) return null;

  const handleOpenIncident = async (notifId: string, incidentId?: string) => {
    await markNotificationRead(notifId);
    if (incidentId) {
      setSelectedEmergencyId(incidentId);
      onClose();
      navigate(`/emergency-alerts?incident=${encodeURIComponent(incidentId)}`);
    }
  };

  return (
    <div className="fixed inset-0 z-[1150] flex justify-end bg-[#020B18]/65 backdrop-blur-[2px]">
      <div
        className="flex h-full w-full max-w-md flex-col border-l border-[#1D3552] bg-[#061326] shadow-2xl"
        role="dialog"
        aria-label="Notification Center"
      >
        <div className="flex items-center justify-between border-b border-[#1D3552] px-5 py-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-[#1D3552] bg-[#0A1729] text-[#20E39A]">
              <Bell size={18} />
            </div>
            <div>
              <h2 className="text-[16px] font-semibold text-[#F1F5F9]">Notification Center</h2>
              <p className="text-[12px] text-[#94A3B8]">
                {unreadNotificationCount} unread operational alert{unreadNotificationCount === 1 ? "" : "s"}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close notification center"
            className="rounded-lg p-1.5 text-[#94A3B8] hover:bg-[#0D1D32] hover:text-[#F1F5F9]"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex items-center justify-between gap-2 border-b border-[#1D3552] bg-[#0A1729]/60 px-5 py-2.5">
          <button
            type="button"
            onClick={() => void markAllNotificationsRead()}
            disabled={unreadNotificationCount === 0}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[#1D3552] bg-[#0D1D32] px-3 py-1.5 text-[12px] font-medium text-[#20E39A] transition hover:border-[#00D084]/50 disabled:opacity-40"
          >
            <CheckCheck size={14} />
            Mark all as read
          </button>
          <button
            type="button"
            onClick={clearAllNotifications}
            disabled={notifications.length === 0}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[#1D3552] bg-[#0D1D32] px-3 py-1.5 text-[12px] font-medium text-[#94A3B8] transition hover:border-[#EF4444]/50 hover:text-[#EF4444] disabled:opacity-40"
          >
            <Trash2 size={14} />
            Clear all
          </button>
        </div>

        <div className="flex-1 space-y-2.5 overflow-y-auto p-4">
          {notifications.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[#1D3552] bg-[#0A1729]/50 py-14 text-center">
              <Bell size={28} className="mb-2 text-[#94A3B8]/50" />
              <div className="text-[14px] font-medium text-[#F1F5F9]">All caught up</div>
              <p className="mt-1 text-[12px] text-[#94A3B8]">
                Operational updates and emergency notifications will appear here.
              </p>
            </div>
          ) : (
            notifications.map((item) => (
              <article
                key={item.id}
                className={`rounded-xl border p-3.5 transition ${
                  item.isRead
                    ? "border-[#1D3552]/70 bg-[#0A1729]/70"
                    : "border-[#00D084]/40 bg-[#0D1D32]"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <StatusBadge
                    label={item.category}
                    tone={
                      item.severity === "Critical"
                        ? "critical"
                        : item.category === "Route cleared"
                          ? "live"
                          : item.category === "Traffic congestion"
                            ? "warning"
                            : "blue"
                    }
                  />
                  <span className="text-[11px] text-[#94A3B8]">{item.timestamp}</span>
                </div>
                <h3 className="mt-2 text-[13px] font-semibold text-[#F1F5F9]">{item.title}</h3>
                <p className="mt-1 text-[12px] leading-relaxed text-[#94A3B8]">{item.message}</p>
                <div className="mt-3 flex items-center justify-between gap-2">
                  {!item.isRead ? (
                    <button
                      type="button"
                      onClick={() => void markNotificationRead(item.id)}
                      className="text-[11px] font-medium text-[#20E39A] hover:underline"
                    >
                      Mark as read
                    </button>
                  ) : (
                    <span className="text-[11px] text-[#94A3B8]/70">Read</span>
                  )}
                  {item.incidentId && (
                    <button
                      type="button"
                      onClick={() => void handleOpenIncident(item.id, item.incidentId)}
                      className="inline-flex items-center gap-1 text-[11px] font-medium text-[#24A8FF] hover:underline"
                    >
                      View incident {item.incidentId}
                      <ExternalLink size={12} />
                    </button>
                  )}
                </div>
              </article>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
