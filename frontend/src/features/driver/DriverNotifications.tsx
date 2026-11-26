import { useCallback, useState } from "react";
import { Bell, CheckCheck, RefreshCw, X } from "lucide-react";
import { api } from "../../lib/api";
import { useLiveQuery } from "../../lib/useLiveQuery";

type DriverNotificationsProps = { onClose: () => void };

function formatTime(value: string) {
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export default function DriverNotifications({ onClose }: DriverNotificationsProps) {
    const loadNotifications = useCallback(() => api.getNotifications(), []);
    const { data, loading, error, lastUpdated, refresh } = useLiveQuery(loadNotifications, 15_000);
    const [actionError, setActionError] = useState("");
    const notifications = data?.results ?? [];
    const unreadCount = notifications.filter((notification) => !notification.is_read).length;

    const markAllRead = async () => {
        setActionError("");
        try {
            await api.markAllNotificationsRead();
            refresh();
        } catch (cause: unknown) {
            setActionError(cause instanceof Error ? cause.message : "Unable to mark notifications read.");
            refresh();
        }
    };

    return (
        <div className="fixed inset-0 z-[120] bg-slate-950/50 flex items-end sm:items-center justify-center p-0 sm:p-4" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
            <section className="w-full sm:max-w-lg max-h-[85dvh] rounded-t-3xl sm:rounded-2xl bg-white shadow-2xl flex flex-col" role="dialog" aria-modal="true" aria-labelledby="driver-notifications-heading">
                <header className="flex items-center gap-3 p-5 border-b border-slate-100">
                    <span className="w-10 h-10 rounded-xl bg-blue-50 text-blue-700 grid place-items-center"><Bell size={19} /></span>
                    <div className="flex-1"><h2 id="driver-notifications-heading" className="font-bold text-slate-900">Notifications</h2><p className="text-xs text-slate-500 mt-1">{unreadCount} unread · updates every 15 seconds</p></div>
                    <button type="button" className="p-2 text-slate-500 hover:bg-slate-100 rounded-lg" aria-label="Refresh notifications" onClick={refresh}><RefreshCw size={17} /></button>
                    <button type="button" className="p-2 text-slate-500 hover:bg-slate-100 rounded-lg" aria-label="Close notifications" onClick={onClose}><X size={19} /></button>
                </header>
                {error && <div className="mx-4 mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">Notification refresh failed: {error}</div>}
                {actionError && <div className="mx-4 mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">{actionError}</div>}
                <div className="overflow-y-auto p-4 space-y-3">
                    {notifications.map((notification) => (
                        <article key={notification.id} className={`rounded-xl border p-4 ${notification.is_read ? "border-slate-200 bg-white" : "border-blue-200 bg-blue-50/60"}`}>
                            <div className="flex items-start gap-3"><span className={`mt-1 w-2 h-2 rounded-full ${notification.is_read ? "bg-slate-300" : "bg-blue-600"}`} /><div className="flex-1"><strong className="text-sm text-slate-900">{notification.title}</strong><p className="text-sm text-slate-600 mt-1">{notification.message}</p><p className="text-xs text-slate-400 mt-2">{notification.incident_number} · {formatTime(notification.created_at)}</p></div></div>
                        </article>
                    ))}
                    {!notifications.length && <div className="py-10 text-center text-slate-500"><Bell size={25} className="mx-auto mb-2 text-slate-300" /><strong className="block text-sm">{loading ? "Loading notifications…" : "No notifications"}</strong><span className="text-xs">Backend updates for your account will appear here.</span></div>}
                </div>
                <footer className="flex items-center justify-between gap-3 border-t border-slate-100 p-4">
                    <span className="text-xs text-slate-400">{lastUpdated ? `Updated ${formatTime(lastUpdated.toISOString())}` : "Connecting to notifications"}</span>
                    <button type="button" disabled={!unreadCount} onClick={() => void markAllRead()} className="inline-flex items-center gap-2 rounded-lg bg-blue-700 px-3 py-2 text-xs font-bold text-white disabled:opacity-40"><CheckCheck size={15} />Mark all read</button>
                </footer>
            </section>
        </div>
    );
}
