
import { useCallback, useMemo, useState } from "react";
import {
    BedDouble,
    Search,
    Filter,
    UserRound,
    Clock3,
    CheckCircle2,
    XCircle,
    CalendarDays,
    Plus,
} from "lucide-react";
import { api, type HospitalBed } from "../../lib/api";
import { useLiveQuery } from "../../lib/useLiveQuery";
import "./hospital.css";

type BedStatus = "Available" | "Occupied" | "Reserved";

type Bed = {
    id: string;
    category: "General" | "ICU" | "Emergency";
    status: BedStatus;
    patient?: string;
    admittedAt?: string;
};

const categories = ["All Beds", "General", "ICU", "Emergency"] as const;
type CategoryFilter = (typeof categories)[number];

function BedManagement() {
    const loadBeds = useCallback(() => api.getHospitalBeds(), []);
    const { data: bedRecords = [], error: loadError, lastUpdated, refresh } = useLiveQuery<HospitalBed[]>(loadBeds, 12_000);
    const beds: Bed[] = bedRecords.map((bed) => ({
        id: bed.bed_number,
        category: bed.category === "GENERAL" ? "General" : bed.category === "ICU" ? "ICU" : "Emergency",
        status: bed.status === "AVAILABLE" ? "Available" : bed.status === "OCCUPIED" ? "Occupied" : "Reserved",
        patient: bed.patient_label || undefined,
    }));
    const [error, setError] = useState("");
    const [category, setCategory] = useState<CategoryFilter>("All Beds");
    const [status, setStatus] = useState("All Status");
    const [search, setSearch] = useState("");
    const [showAddBed, setShowAddBed] = useState(false);
    const [newBedNumber, setNewBedNumber] = useState("");
    const [newBedCategory, setNewBedCategory] = useState<"GENERAL" | "ICU" | "EMERGENCY">("GENERAL");
    const [savingBed, setSavingBed] = useState(false);
    const [busyBed, setBusyBed] = useState("");

    const counts = useMemo(() => ({
        total: beds.length,
        available: beds.filter((bed) => bed.status === "Available").length,
        occupied: beds.filter((bed) => bed.status === "Occupied").length,
        reserved: beds.filter((bed) => bed.status === "Reserved").length,
    }), [beds]);

    const filteredBeds = beds.filter((bed) => {
        const matchesCategory = category === "All Beds" || bed.category === category;
        const matchesStatus = status === "All Status" || bed.status === status;
        const matchesSearch =
            bed.id.toLowerCase().includes(search.toLowerCase()) ||
            (bed.patient || "").toLowerCase().includes(search.toLowerCase());

        return matchesCategory && matchesStatus && matchesSearch;
    });

    const reserveBed = async (bedId: string) => {
        const record = bedRecords.find((bed) => bed.bed_number === bedId);
        if (!record) return;
        setBusyBed(bedId);
        setError("");
        try {
            await api.updateHospitalBed(record.id, { status: "RESERVED" });
            refresh();
        } catch (reason: unknown) {
            setError(reason instanceof Error ? reason.message : "Unable to reserve this bed.");
        } finally {
            setBusyBed("");
        }
    };

    const releaseBed = async (bedId: string) => {
        const record = bedRecords.find((bed) => bed.bed_number === bedId);
        if (!record) return;
        setBusyBed(bedId);
        setError("");
        try {
            await api.updateHospitalBed(record.id, { status: "AVAILABLE", patient_label: "" });
            refresh();
        } catch (reason: unknown) {
            setError(reason instanceof Error ? reason.message : "Unable to update this bed.");
        } finally {
            setBusyBed("");
        }
    };

    const addBed = async () => {
        if (!newBedNumber.trim()) {
            setError("Enter a bed number.");
            return;
        }
        setSavingBed(true);
        setError("");
        try {
            const created = await api.createHospitalBed({
                bed_number: newBedNumber.trim(),
                category: newBedCategory,
                status: "AVAILABLE",
            });
            void created;
            refresh();
            setShowAddBed(false);
            setNewBedNumber("");
            setNewBedCategory("GENERAL");
        } catch (reason: unknown) {
            setError(reason instanceof Error ? reason.message : "Unable to add bed.");
        } finally {
            setSavingBed(false);
        }
    };

    return (
        <div className="hd-dashboard hb-page">
            <div className="hd-page-heading">
                <div>
                    <div className="hd-breadcrumb">Hospital / Bed Management</div>
                    <h1>Bed Management</h1>
                    <p>Monitor bed availability and manage patient allocations.</p>
                </div>

                <div className="hb-heading-actions">
                    <span className="hb-updated">
                        <Clock3 size={15} /> {lastUpdated ? `Updated ${new Intl.DateTimeFormat(undefined, { timeStyle: "short" }).format(lastUpdated)}` : "Connecting…"}
                    </span>
                    <button
                        className="hb-primary-button"
                        type="button"
                        onClick={() => setShowAddBed(true)}
                    >
                        <Plus size={17} /> Add Bed
                    </button>
                </div>
            </div>

            <div className="hb-summary-grid">
                <div className="hb-summary-card">
                    <div className="hb-summary-icon hb-icon-blue"><BedDouble size={21} /></div>
                    <span>Total Beds</span>
                    <strong>{counts.total}</strong>
                    <small>Registered beds</small>
                </div>
                <div className="hb-summary-card">
                    <div className="hb-summary-icon hb-icon-green"><CheckCircle2 size={21} /></div>
                    <span>Available Beds</span>
                    <strong>{counts.available}</strong>
                    <small>Ready for allocation</small>
                </div>
                <div className="hb-summary-card">
                    <div className="hb-summary-icon hb-icon-red"><UserRound size={21} /></div>
                    <span>Occupied Beds</span>
                    <strong>{counts.occupied}</strong>
                    <small>Currently in use</small>
                </div>
                <div className="hb-summary-card">
                    <div className="hb-summary-icon hb-icon-orange"><CalendarDays size={21} /></div>
                    <span>Reserved Beds</span>
                    <strong>{counts.reserved}</strong>
                    <small>Awaiting patient arrival</small>
                </div>
            </div>

            <section className="hb-panel">
                <div className="hb-panel-heading">
                    <div>
                        <h2>Bed Availability</h2>
                        <p>Select a category to view its beds and current status.</p>
                    </div>
                    <div className="hb-legend">
                        <span><i className="hb-dot available" /> Available</span>
                        <span><i className="hb-dot occupied" /> Occupied</span>
                        <span><i className="hb-dot reserved" /> Reserved</span>
                    </div>
                </div>

                <div className="hb-category-tabs">
                    {categories.map((item) => (
                        <button
                            type="button"
                            key={item}
                            className={category === item ? "active" : ""}
                            onClick={() => setCategory(item)}
                        >
                            {item}
                            <span>
                                {item === "All Beds"
                                    ? beds.length
                                    : beds.filter((bed) => bed.category === item).length}
                            </span>
                        </button>
                    ))}
                </div>

                <div className="hb-toolbar">
                    <div className="hb-search">
                        <Search size={17} />
                        <input
                            value={search}
                            onChange={(event) => setSearch(event.target.value)}
                            placeholder="Search bed number or patient..."
                        />
                    </div>
                    <div className="hb-filter">
                        <Filter size={16} />
                        <select value={status} onChange={(event) => setStatus(event.target.value)}>
                            <option>All Status</option>
                            <option>Available</option>
                            <option>Occupied</option>
                            <option>Reserved</option>
                        </select>
                    </div>
                </div>

                <div className="hb-bed-grid">
                    {filteredBeds.map((bed) => (
                        <article className={`hb-bed-card ${bed.status.toLowerCase()}`} key={bed.id}>
                            <div className="hb-bed-card-top">
                                <span className="hb-bed-category">{bed.category}</span>
                                <span className={`hb-status ${bed.status.toLowerCase()}`}>
                                    {bed.status}
                                </span>
                            </div>
                            <div className="hb-bed-illustration">
                                <BedDouble size={37} strokeWidth={1.6} />
                            </div>
                            <h3>{bed.id}</h3>
                            {bed.patient ? (
                                <p className="hb-bed-patient">
                                    <UserRound size={14} /> {bed.patient}
                                </p>
                            ) : (
                                <p className="hb-bed-patient muted">No patient assigned</p>
                            )}
                            {bed.admittedAt && (
                                <p className="hb-bed-time">Admitted today · {bed.admittedAt}</p>
                            )}
                            {bed.status === "Available" && (
                                <button
                                    type="button"
                                    className="hb-bed-action reserve"
                                    disabled={busyBed === bed.id}
                                    onClick={() => reserveBed(bed.id)}
                                >
                                    {busyBed === bed.id ? "Saving…" : "Reserve Bed"}
                                </button>
                            )}
                            {bed.status === "Reserved" && (
                                <button
                                    type="button"
                                    className="hb-bed-action release"
                                    disabled={busyBed === bed.id}
                                    onClick={() => releaseBed(bed.id)}
                                >
                                    {busyBed === bed.id ? "Saving…" : "Release Reservation"}
                                </button>
                            )}
                            {bed.status === "Occupied" && (
                                <button
                                    type="button"
                                    className="hb-bed-action release"
                                    disabled={busyBed === bed.id}
                                    onClick={() => releaseBed(bed.id)}
                                >
                                    {busyBed === bed.id ? "Saving…" : "Mark as Available"}
                                </button>
                            )}
                        </article>
                    ))}
                    {filteredBeds.length === 0 && (
                        <div className="hb-empty">
                            <XCircle size={25} />
                            <strong>No beds found</strong>
                            <span>Try changing your search or filters.</span>
                        </div>
                    )}
                </div>
            </section>

            {(loadError || error) && <div className="hb-demo-note">{error || loadError}</div>}
            {showAddBed && (
                <div className="hb-modal-overlay" role="presentation">
                    <div className="hb-add-bed-modal" role="dialog" aria-modal="true" aria-labelledby="hb-add-bed-title">
                        <button
                            type="button"
                            className="hb-modal-close"
                            onClick={() => setShowAddBed(false)}
                            aria-label="Close add bed dialog"
                        >
                            <XCircle size={19} />
                        </button>
                        <h2 id="hb-add-bed-title">Add Hospital Bed</h2>
                        <label htmlFor="hb-bed-number">Bed number</label>
                        <input
                            id="hb-bed-number"
                            value={newBedNumber}
                            onChange={(event) => setNewBedNumber(event.target.value)}
                            placeholder="e.g. ICU-01"
                        />
                        <label htmlFor="hb-bed-category">Category</label>
                        <select
                            id="hb-bed-category"
                            value={newBedCategory}
                            onChange={(event) =>
                                setNewBedCategory(event.target.value as "GENERAL" | "ICU" | "EMERGENCY")
                            }
                        >
                            <option value="GENERAL">General</option>
                            <option value="ICU">ICU</option>
                            <option value="EMERGENCY">Emergency</option>
                        </select>
                        <div className="hb-modal-actions">
                            <button type="button" onClick={() => setShowAddBed(false)}>Cancel</button>
                            <button type="button" disabled={savingBed} onClick={addBed}>
                                {savingBed ? "Adding..." : "Add Bed"}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default BedManagement;
