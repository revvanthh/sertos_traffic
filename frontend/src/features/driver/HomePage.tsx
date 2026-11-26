
import {
    Activity,
    Ambulance,
    Bell,
    Clock3,
    Hospital,
    Navigation,
    ShieldCheck,
    Mic,
    UserRound,
    Siren,
    ChevronDown,
    ChevronRight,
    Radio,
} from 'lucide-react'

import { useState } from 'react'

interface HomePageProps {
    driverName: string
    driverPhoto?: string
    ambulanceNumber: string
    isOnDuty: boolean

    patientReport: string
    showDetails: boolean
    onTogglePatientReport: () => void

    hospitalETA?: string
    destination?: string
    gpsStatus?: string
    emergencyStatus?: string
    trafficStatus?: string
    hasActiveIncident?: boolean
    notificationCount?: number

    onStartEmergency: () => void
    onNotificationClick?: () => void
    onTrafficClick?: () => void
}

export default function HomePage({
    driverName,
    driverPhoto,
    ambulanceNumber,
    isOnDuty,
    patientReport,
    onTogglePatientReport,
    hospitalETA = '-- min',
    destination = 'Not selected',
    gpsStatus = 'Waiting for GPS',
    emergencyStatus = 'READY',
    trafficStatus = 'Waiting',
    hasActiveIncident = false,
    notificationCount = 0,
    onStartEmergency,
    onNotificationClick,
    onTrafficClick,
}: HomePageProps) {

    const [reportExpanded, setReportExpanded] = useState(false)

    return (
        <div className="max-w-lg mx-auto px-4 pt-4 pb-28 space-y-4">

            {/* WELCOME SECTION */}

            <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[#101B2D] via-[#172C49] to-[#10264D] p-5 text-white shadow-lg">

                <div className="absolute -right-12 -top-12 w-40 h-40 rounded-full bg-white/5" />
                <div className="absolute -right-5 bottom-[-65px] w-40 h-40 rounded-full bg-[#14B8A6]/10" />

                <div className="relative z-10 flex items-center justify-between">

                    <div className="flex items-center gap-3">

                        <div className="w-14 h-14 rounded-2xl overflow-hidden bg-white/10 border border-white/20 flex items-center justify-center">

                            {driverPhoto ? (
                                <img
                                    src={driverPhoto}
                                    alt="Driver"
                                    className="w-full h-full object-cover"
                                />
                            ) : (
                                <UserRound size={29} className="text-white/80" />
                            )}

                        </div>

                        <div>
                            <p className="text-xs text-slate-300">
                                Welcome back,
                            </p>

                            <h2 className="text-lg font-bold mt-1">
                                {driverName}
                            </h2>

                            <div className="flex items-center gap-1.5 mt-1">

                                <span
                                    className={`w-2 h-2 rounded-full ${isOnDuty ? 'bg-[#14B8A6]' : 'bg-slate-400'
                                        }`}
                                />

                                <span className="text-[11px] text-slate-300">
                                    {isOnDuty ? 'Ready for dispatch' : 'Unavailable'}
                                </span>

                            </div>
                        </div>

                    </div>

                    <button
                        onClick={onNotificationClick}
                        aria-label="Notifications"
                        className="relative w-10 h-10 rounded-xl bg-white/10 border border-white/10 flex items-center justify-center"
                    >
                        <Bell size={19} />
                        {notificationCount > 0 && <span className="absolute -right-1 -top-1 min-w-4 h-4 px-1 rounded-full bg-red-500 text-[9px] font-bold flex items-center justify-center">{notificationCount > 9 ? '9+' : notificationCount}</span>}
                    </button>

                </div>

                <div className="relative z-10 mt-6 pt-4 border-t border-white/10 flex items-center justify-between">

                    <div>
                        <p className="text-[10px] uppercase tracking-widest text-slate-400">
                            Your responsibility
                        </p>

                        <p className="text-sm font-semibold mt-1">
                            Every Second Matters.
                        </p>
                    </div>

                    <div className="bg-[#14B8A6]/15 border border-[#14B8A6]/20 rounded-xl p-2.5">
                        <ShieldCheck size={23} className="text-[#14B8A6]" />
                    </div>

                </div>

            </section>


            {/* ASSIGNED AMBULANCE */}

            <section className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">

                <div className="flex items-center justify-between">

                    <div className="flex items-center gap-3">

                        <div className="w-11 h-11 rounded-xl bg-red-50 flex items-center justify-center">
                            <Ambulance size={24} className="text-[#EF4444]" />
                        </div>

                        <div>
                            <p className="text-[11px] text-slate-400 font-semibold uppercase tracking-wide">
                                Assigned ambulance
                            </p>

                            <h3 className="text-base font-bold text-[#101B2D] mt-1">
                                {ambulanceNumber}
                            </h3>
                        </div>

                    </div>

                    <div className={`${ambulanceNumber === 'Not assigned' ? 'bg-slate-100' : 'bg-teal-50'} px-3 py-1.5 rounded-full`}>
                        <span className={`text-[10px] font-bold ${ambulanceNumber === 'Not assigned' ? 'text-slate-600' : 'text-teal-700'}`}>
                            {ambulanceNumber === 'Not assigned' ? 'NO ASSIGNMENT' : 'ASSIGNED'}
                        </span>
                    </div>

                </div>

            </section>


            {/* EMERGENCY ALERT */}

            <section className="bg-white border border-red-100 rounded-2xl overflow-hidden shadow-sm">

                <div className="p-4">

                    <div className="flex items-center gap-3">

                        <div className="w-11 h-11 rounded-xl bg-red-50 flex items-center justify-center">
                            <Siren size={23} className="text-[#EF4444]" />
                        </div>

                        <div className="flex-1">
                            <h3 className="text-sm font-bold text-[#101B2D]">
                                Emergency Response
                            </h3>

                            <p className="text-xs text-slate-500 mt-1">
                                Start an emergency response mission
                            </p>
                        </div>

                        <span className={`text-[10px] font-bold px-2.5 py-1.5 rounded-full ${hasActiveIncident
                            ? 'text-red-700 bg-red-50'
                            : 'text-teal-700 bg-teal-50'
                            }`}>
                            {emergencyStatus}
                        </span>

                    </div>

                    <button
                        onClick={onStartEmergency}
                        disabled={!isOnDuty || hasActiveIncident}
                        className="w-full mt-4 bg-[#EF4444] hover:bg-red-600 disabled:opacity-50 text-white rounded-xl py-3.5 flex items-center justify-center gap-2 font-bold text-sm shadow-md shadow-red-500/15 active:scale-[0.98] transition-all"
                    >
                        <Siren size={18} />
                        {hasActiveIncident
                            ? 'Emergency Active'
                            : 'Start Emergency'
                        }
                    </button>

                </div>

            </section>


            {/* LIVE INFORMATION */}

            <section>

                <div className="flex items-center justify-between mb-3">

                    <h3 className="text-sm font-bold text-[#101B2D]">
                        Live Information
                    </h3>

                    <div className="flex items-center gap-1.5 text-teal-600">
                        <span className={`w-1.5 h-1.5 rounded-full ${hasActiveIncident ? 'bg-[#14B8A6]' : 'bg-amber-400'}`} />
                        <span className="text-[10px] font-semibold">
                            {hasActiveIncident ? 'MISSION ACTIVE' : 'AWAITING DISPATCH'}
                        </span>
                    </div>

                </div>

                <div className="grid grid-cols-2 gap-3">

                    {/* ETA */}

                    <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">

                        <div className="w-9 h-9 rounded-xl bg-blue-50 flex items-center justify-center">
                            <Clock3 size={19} className="text-[#2563EB]" />
                        </div>

                        <p className="text-[11px] text-slate-500 mt-3">
                            Hospital ETA
                        </p>

                        <h3 className="text-xl font-extrabold text-[#101B2D] mt-1">
                            {hospitalETA}
                        </h3>

                    </div>


                    {/* DESTINATION */}

                    <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">

                        <div className="w-9 h-9 rounded-xl bg-red-50 flex items-center justify-center">
                            <Hospital size={19} className="text-[#EF4444]" />
                        </div>

                        <p className="text-[11px] text-slate-500 mt-3">
                            Destination
                        </p>

                        <h3 className="text-sm font-bold text-[#101B2D] mt-1 truncate">
                            {destination}
                        </h3>

                    </div>


                    {/* GPS */}

                    <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">

                        <div className="w-9 h-9 rounded-xl bg-teal-50 flex items-center justify-center">
                            <Navigation size={19} className="text-[#14B8A6]" />
                        </div>

                        <p className="text-[11px] text-slate-500 mt-3">
                            GPS Tracking
                        </p>

                        <h3 className="text-sm font-bold text-[#101B2D] mt-1">
                            {gpsStatus}
                        </h3>

                    </div>


                    {/* RESPONSE */}

                    <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">

                        <div className="w-9 h-9 rounded-xl bg-blue-50 flex items-center justify-center">
                            <Radio size={19} className="text-[#2563EB]" />
                        </div>

                        <p className="text-[11px] text-slate-500 mt-3">
                            Emergency Status
                        </p>

                        <h3 className="text-sm font-bold text-[#101B2D] mt-1">
                            {emergencyStatus}
                        </h3>

                    </div>

                </div>

            </section>


            {/* TRAFFIC COORDINATION */}

            <button
                type="button"
                onClick={onTrafficClick}
                className="w-full text-left bg-white border border-slate-200 rounded-2xl p-4 shadow-sm active:scale-[0.99] transition-transform"
            >

                <div className="flex items-center gap-3">

                    <div className="w-11 h-11 rounded-xl bg-blue-50 flex items-center justify-center">
                        <ShieldCheck size={23} className="text-[#2563EB]" />
                    </div>

                    <div className="flex-1 min-w-0">

                        <h3 className="text-sm font-bold text-[#101B2D]">
                            Traffic Coordination
                        </h3>

                        <p className="text-xs text-slate-500 mt-1">
                            Traffic police clearance updates
                        </p>

                    </div>

                    <span className="text-[10px] font-semibold text-amber-600 bg-amber-50 px-2.5 py-1.5 rounded-full">
                        {trafficStatus}
                    </span>

                </div>
            </button>


            {/* PATIENT REPORT */}

            {patientReport && (

                <section className="bg-white border border-blue-100 rounded-2xl overflow-hidden shadow-sm">

                    <button
                        onClick={() => {
                            setReportExpanded(!reportExpanded)
                            onTogglePatientReport()
                        }}
                        className="w-full p-4 flex items-center gap-3 text-left"
                    >

                        <div className="w-11 h-11 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center">
                            <Activity size={22} />
                        </div>

                        <div className="flex-1 min-w-0">

                            <h3 className="font-bold text-sm text-[#101B2D]">
                                Patient Report
                            </h3>

                            <p className="text-xs text-slate-500 mt-1 truncate">
                                {patientReport}
                            </p>

                        </div>

                        {reportExpanded
                            ? <ChevronDown size={19} className="text-slate-400" />
                            : <ChevronRight size={19} className="text-slate-400" />
                        }

                    </button>

                    {reportExpanded && (

                        <div className="border-t border-slate-100 p-4">

                            <p className="text-xs text-slate-500 font-semibold uppercase mb-2">
                                Recorded patient report transcript
                            </p>

                            <div className="bg-blue-50 border border-blue-100 rounded-xl p-3">
                                <p className="text-sm text-slate-700 leading-6">
                                    {patientReport}
                                </p>
                            </div>

                            <p className="text-xs text-slate-400 mt-3">
                                The report is available for review. Emergency confirmation is handled on the separate confirmation page.
                            </p>

                        </div>

                    )}

                </section>

            )}


            {/* HANDS-FREE REPORTING */}

            <section className="bg-[#101B2D] rounded-2xl p-4 text-white shadow-md">

                <div className="flex items-center gap-3">

                    <div className="w-11 h-11 bg-white/10 rounded-xl flex items-center justify-center">
                        <Mic size={23} className="text-[#14B8A6]" />
                    </div>

                    <div className="flex-1">

                        <h3 className="text-sm font-bold">
                            Hands-free reporting
                        </h3>

                        <p className="text-xs text-slate-300 mt-1 leading-5">
                            Record and report patient condition using the microphone button. Press STOP when reporting is complete.
                        </p>

                    </div>

                </div>

            </section>

        </div>
    )
}
