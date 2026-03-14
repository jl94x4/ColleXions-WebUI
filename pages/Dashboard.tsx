import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { Card } from '../components/ui/Card';
import {
    Play,
    Square,
    Clock,
    Activity,
    Terminal,
    WifiOff,
    CalendarClock,
    RefreshCw,
    ToggleLeft,
    ToggleRight,
    Power,
    Cpu,
    Hourglass,
    AlertTriangle,
    CheckCircle2,
    Filter,
    Settings
} from 'lucide-react';
import { api } from '../services/api';
import { AppConfig, AppStatus } from '../types';

interface LibraryRunStats {
    name: string;
    found: number;
    eligible: number;
    pinned: number;
    blockedByTimer: number;
    blockedByCategory: boolean;
}

interface RunAnalysis {
    status: 'RUNNING' | 'COMPLETED' | 'FAILED' | 'UNKNOWN';
    startTime: string;
    duration: string;
    intervalConfig: string;
    totalPins: number;
    libraries: LibraryRunStats[];
    errors: string[];
}

const Dashboard: React.FC = () => {
    const [status, setStatus] = useState<AppStatus | null>(null);
    const [config, setConfig] = useState<AppConfig | null>(null);
    const [nextRun, setNextRun] = useState<string>('--:--');
    const [logs, setLogs] = useState<string>('');
    const [loading, setLoading] = useState(false);
    const [isRefreshing, setIsRefreshing] = useState(false);

    // Default Settings
    const [autoRefresh] = useState(true);
    const [liveLogs, setLiveLogs] = useState(true);

    // Persistence
    useEffect(() => {
        const saved = localStorage.getItem('collexions_dashboard_state');
        if (saved) {
            try {
                const state = JSON.parse(saved);
                if (state.liveLogs !== undefined) setLiveLogs(state.liveLogs);
            } catch (e) { console.error(e); }
        }
    }, []);

    useEffect(() => {
        localStorage.setItem('collexions_dashboard_state', JSON.stringify({ liveLogs }));
    }, [liveLogs]);

    const logContainerRef = useRef<HTMLDivElement>(null);

    // --- Helpers ---
    const safeParseDate = (dateStr: string): Date | null => {
        if (!dateStr) return null;
        try {
            // Handle ISO-like formats with ' ' instead of 'T'
            let cleanStr = dateStr.replace(' ', 'T');

            let d = new Date(cleanStr);
            if (!isNaN(d.getTime())) return d;

            // Handle microsecond timestamps (strip extra decimals)
            d = new Date(cleanStr.replace(/(\.\d{3})\d+/, '$1'));
            if (!isNaN(d.getTime())) return d;

            d = new Date(cleanStr.split('.')[0]);
            if (!isNaN(d.getTime())) return d;

            // Final fallback: try the original string directly 
            // This handles formats like 'Thu Mar 12 01:02:35 2026' (ctime)
            d = new Date(dateStr);
            if (!isNaN(d.getTime())) return d;

        } catch (e) {
            console.warn("Date parse error", e);
        }
        return null;
    };

    const calculateNextRun = (s: AppStatus) => {
        if (s.next_run_timestamp && s.next_run_timestamp > 0) {
            const targetDate = new Date(s.next_run_timestamp * 1000);
            const timeStr = targetDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            const diff = targetDate.getTime() - Date.now();
            const mins = Math.ceil(diff / 60000);

            if (diff > 0) {
                setNextRun(`${timeStr} (in ${mins}m)`);
            } else {
                setNextRun("Due Now / Processing");
            }
        } else {
            setNextRun('--:--');
        }
    };

    // --- Deep Log Analysis ---
    const analyzeLastRun = useMemo((): RunAnalysis | null => {
        if (!logs) return null;

        const lines = logs.split('\n');
        let startIndex = -1;

        // Find start of last run
        for (let i = lines.length - 1; i >= 0; i--) {
            if (lines[i].includes('====== Starting')) {
                startIndex = i;
                break;
            }
        }

        if (startIndex === -1) return null;

        const runLines = lines.slice(startIndex);
        const analysis: RunAnalysis = {
            status: 'RUNNING',
            startTime: 'Unknown',
            duration: '...',
            intervalConfig: '?',
            totalPins: 0,
            libraries: [],
            errors: []
        };

        const startMatch = runLines[0].match(/(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2})/);
        if (startMatch) analysis.startTime = startMatch[1];

        let currentLib: LibraryRunStats | null = null;

        runLines.forEach(line => {
            if (line.includes('====== Run Finished') || line.includes('====== Collexions Script Run Finished')) {
                analysis.status = 'COMPLETED';
            }

            if (line.includes('Duration:') || line.includes('Total run duration:')) {
                const durMatch = line.match(/Duration: ([\d:.]+)/) || line.match(/Total run duration: ([\d:.]+)/);
                if (durMatch) analysis.duration = durMatch[1];
            }

            if (line.includes('CRITICAL') || line.includes('Traceback') || (line.includes('ERROR') && !line.includes('404'))) {
                if (!analysis.errors.includes(line)) analysis.errors.push(line);
                analysis.status = 'FAILED';
            }

            if (line.includes('Pinning interval set to')) {
                const match = line.match(/(?:CONFIG: )?Pinning interval set to (\d+) minutes/);
                if (match) analysis.intervalConfig = match[1] + ' min';
            }

            if (line.includes('Sleeping for approximately')) {
                // We no longer overwrite intervalConfig with the transient sleep duration
                // unless we want to show it elsewhere. For now, we prioritize the CONFIG line.
                const match = line.match(/maintain (\d+)m frequency/);
                if (match) analysis.intervalConfig = match[1] + ' min';
            }

            const libStart = line.match(/===== Processing Library: '(.+?)'/);
            if (libStart) {
                if (currentLib) analysis.libraries.push(currentLib);
                currentLib = {
                    name: libStart[1],
                    found: 0,
                    eligible: 0,
                    pinned: 0,
                    blockedByTimer: 0,
                    blockedByCategory: false
                };
            }

            if (currentLib) {
                const foundMatch = line.match(/Found (\d+) collections/);
                if (foundMatch) currentLib.found = parseInt(foundMatch[1]);

                if (line.includes('excluded due to') && line.includes('block')) {
                    const listContent = line.match(/\[(.*?)\]/);
                    if (listContent) {
                        currentLib.blockedByTimer = listContent[1].split(',').length;
                    }
                }

                const eligMatch = line.match(/Found (\d+) eligible collections/);
                if (eligMatch) currentLib.eligible = parseInt(eligMatch[1]);

                if (line.includes("Pinned '")) {
                    currentLib.pinned++;
                    analysis.totalPins++;
                }

                if (line.includes('EXCLUDING ALL collections')) {
                    currentLib.blockedByCategory = true;
                }
            }
        });

        if (currentLib) analysis.libraries.push(currentLib);

        return analysis;
    }, [logs]);

    useEffect(() => {
        const loadConfig = async () => {
            try {
                const c = await api.getConfig();
                setConfig(c);
            } catch (e) {
                console.error("Failed to load config", e);
            }
        };
        loadConfig();
    }, []);

    const fetchStatusOnly = useCallback(async () => {
        try {
            const s = await api.getStatus();
            setStatus(s);
            calculateNextRun(s);
        } catch (e) { /* ignore */ }
    }, []);

    const fetchLogsOnly = useCallback(async () => {
        try {
            const l = await api.getLogs();
            setLogs(l);
        } catch (e) { /* ignore */ }
    }, []);

    useEffect(() => {
        fetchStatusOnly();
        fetchLogsOnly();
    }, []);

    useEffect(() => {
        if (autoRefresh) {
            const interval = setInterval(fetchStatusOnly, 5000);
            return () => clearInterval(interval);
        }
    }, [autoRefresh, fetchStatusOnly]);

    useEffect(() => {
        if (liveLogs) {
            const interval = setInterval(fetchLogsOnly, 5000);
            return () => clearInterval(interval);
        }
    }, [liveLogs, fetchLogsOnly]);

    useEffect(() => {
        if (logContainerRef.current && liveLogs) {
            logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
        }
    }, [logs, liveLogs]);

    // --- Actions ---
    const currentStatus = status?.status || 'Connecting...';
    const statusLower = currentStatus.toLowerCase();
    const isLoopActive = statusLower.includes('running') || statusLower.includes('sleeping') || statusLower.includes('processing') || statusLower.includes('waiting');
    const isWorking = statusLower.includes('processing') || statusLower.includes('pinning');
    const isOffline = statusLower === 'offline' || status === null;
    const lastUpdateDate = status?.last_update ? safeParseDate(status.last_update) : null;
    const isDryRun = config?.dry_run === true;

    const handleStartService = async () => {
        if (loading) return;
        if (isLoopActive) return alert("Service is already active.");
        setLoading(true);
        try { await api.runNow(); setTimeout(fetchStatusOnly, 1000); } catch (error) { alert("Failed to start."); }
        setLoading(false);
    };

    const handleStopService = async () => {
        if (loading) return;
        if (!confirm("Stop the Automation Service?")) return;
        setLoading(true);
        try { await api.stopScript(); setTimeout(fetchStatusOnly, 1000); } catch (error) { console.error(error); }
        setLoading(false);
    };

    const manualRefresh = async () => {
        setIsRefreshing(true);
        await fetchStatusOnly();
        await fetchLogsOnly();
        setTimeout(() => setIsRefreshing(false), 500);
    };

    return (
        <div className="space-y-6 animate-in fade-in duration-500 pb-10">

            {/* Config Warnings */}
            {config && isDryRun && (
                <div className="bg-amber-500/20 border border-amber-500/50 p-4 rounded-xl flex items-center gap-4 animate-pulse">
                    <div className="bg-amber-500 text-black p-2 rounded-lg"><AlertTriangle className="w-6 h-6" /></div>
                    <div className="flex-1">
                        <h3 className="font-bold text-amber-200">SIMULATION MODE ACTIVE</h3>
                        <p className="text-amber-100/80 text-sm">"Dry Run" is enabled. No changes will be made to Plex.</p>
                    </div>
                </div>
            )}

            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 className="text-3xl font-bold text-white tracking-tight flex items-center gap-3">
                        Dashboard
                        {isOffline && <span className="text-xs bg-red-900/50 text-red-400 px-2 py-1 rounded border border-red-800">OFFLINE</span>}
                    </h2>
                    <p className="text-slate-400 mt-1 flex items-center gap-2 text-sm">
                        <Activity className="w-4 h-4 text-plex-orange" /> Real-time automation overview
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    <button
                        onClick={manualRefresh}
                        className={`p-2.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-white hover:border-slate-700 transition-all ${isRefreshing ? 'animate-spin' : ''}`}
                        title="Manual Refresh"
                    >
                        <RefreshCw className="w-5 h-5" />
                    </button>

                    {isLoopActive ? (
                        <button
                            onClick={handleStopService}
                            disabled={loading || isOffline}
                            className="flex items-center gap-2 px-5 py-2.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/50 rounded-xl font-bold transition-all active:scale-95 disabled:opacity-50"
                        >
                            <Square className="w-4 h-4 fill-current" />
                            STOP SERVICE
                        </button>
                    ) : (
                        <button
                            onClick={handleStartService}
                            disabled={loading || isOffline}
                            className="flex items-center gap-2 px-5 py-2.5 bg-emerald-500 hover:bg-emerald-400 text-white border border-emerald-400/50 rounded-xl font-bold transition-all shadow-lg shadow-emerald-900/20 active:scale-95 disabled:opacity-50"
                        >
                            <Play className="w-4 h-4 fill-current" />
                            START SERVICE
                        </button>
                    )}
                </div>
            </div>

            {/* Premium Stats Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* Status Card */}
                <Card className="p-6 border-slate-800/80 bg-slate-900/40 relative overflow-hidden group hover:border-slate-700/80 transition-all duration-300">
                    <div className="flex flex-col h-full relative z-10">
                        <div className="flex justify-between items-start mb-6">
                            <div className={`p-2.5 rounded-xl ${isOffline ? 'bg-slate-800 text-slate-500' : isWorking ? 'bg-emerald-500/20 text-emerald-400' : isLoopActive ? 'bg-blue-500/20 text-blue-400' : 'bg-amber-500/20 text-amber-400 shadow-lg shadow-amber-900/20'}`}>
                                {isOffline ? <WifiOff className="w-5 h-5" /> : isWorking ? <Cpu className="w-5 h-5 animate-spin" /> : isLoopActive ? <Hourglass className="w-5 h-5" /> : <Power className="w-5 h-5" />}
                            </div>
                            <span className="text-[9px] font-black uppercase tracking-[0.25em] text-slate-500 opacity-60">System</span>
                        </div>
                        <div className="space-y-1">
                            <h3 className={`text-xl font-bold tracking-tight ${isWorking ? 'text-emerald-400' : 'text-white'}`}>
                                {isOffline ? 'Offline' : isWorking ? 'Processing' : isLoopActive ? 'Service Active' : 'Service Stopped'}
                            </h3>
                            <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">
                                {isOffline ? 'Check connection' : isWorking ? 'Performing sync' : isLoopActive ? 'Idle & Monitoring' : 'Requires start'}
                            </p>
                        </div>
                    </div>
                    <div className={`absolute -right-8 -bottom-8 w-32 h-32 blur-[80px] opacity-10 rounded-full transition-all duration-700 group-hover:opacity-30 ${isOffline ? 'bg-slate-500' : isWorking ? 'bg-emerald-500' : isLoopActive ? 'bg-blue-500' : 'bg-amber-500'}`}></div>
                </Card>

                {/* Last Activity Card */}
                <Card className="p-6 border-slate-800/80 bg-slate-900/40 relative overflow-hidden group hover:border-slate-700/80 transition-all duration-300">
                    <div className="flex flex-col h-full relative z-10">
                        <div className="flex justify-between items-start mb-6">
                            <div className="p-2.5 bg-slate-800/50 text-slate-400 rounded-xl">
                                <Clock className="w-5 h-5" />
                            </div>
                            <span className="text-[9px] font-black uppercase tracking-[0.25em] text-slate-500 opacity-60">Activity</span>
                        </div>
                        <div className="space-y-1">
                            <h3 className="text-xl font-bold font-mono tracking-tighter text-white tabular-nums">
                                {lastUpdateDate ? lastUpdateDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) : '--:--:--'}
                            </h3>
                            <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Last Run</p>
                        </div>
                    </div>
                </Card>

                {/* Next Run Card */}
                <Card className="p-6 border-slate-800/80 bg-slate-900/40 relative overflow-hidden group hover:border-slate-700/80 transition-all duration-300">
                    <div className="flex flex-col h-full relative z-10">
                        <div className="flex justify-between items-start mb-6">
                            <div className={`p-2.5 rounded-xl ${isLoopActive ? 'bg-plex-orange/20 text-plex-orange shadow-lg shadow-plex-orange/10' : 'bg-slate-800/50 text-slate-600'}`}>
                                <CalendarClock className="w-5 h-5" />
                            </div>
                            <span className="text-[9px] font-black uppercase tracking-[0.25em] text-slate-500 opacity-60">Scheduling</span>
                        </div>
                        <div className="space-y-1">
                            <h3 className={`text-xl font-bold font-mono tracking-tighter tabular-nums ${isLoopActive ? 'text-plex-orange' : 'text-slate-600'}`}>
                                {isLoopActive ? (nextRun.includes('(') ? nextRun.split(' (')[0] : nextRun) : 'Inactive'}
                            </h3>
                            <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">
                                {isLoopActive && nextRun.includes('in ') ? `Next Run in ${(nextRun.split('in ')[1] ?? '').replace(')', '')}` : 'Auto-Sync Paused'}
                            </p>
                        </div>
                    </div>
                </Card>

                {/* Frequency Card */}
                <Card className="p-6 border-slate-800/80 bg-slate-900/40 relative overflow-hidden group hover:border-slate-700/80 transition-all duration-300">
                    <div className="flex flex-col h-full relative z-10">
                        <div className="flex justify-between items-start mb-6">
                            <div className="p-2.5 bg-slate-800/50 text-slate-400 rounded-xl">
                                <Settings className="w-5 h-5" />
                            </div>
                            <span className="text-[9px] font-black uppercase tracking-[0.25em] text-slate-500 opacity-60">Frequency</span>
                        </div>
                        <div className="space-y-1">
                            <div className="flex items-baseline gap-1.5">
                                <h3 className="text-xl font-bold font-mono tracking-tighter text-white">
                                    {config?.pinning_interval || 0}
                                </h3>
                                <span className="text-[9px] font-black text-slate-500 uppercase tracking-widest">min interval</span>
                            </div>
                            {analyzeLastRun?.intervalConfig ? (
                                <p className="text-[10px] text-blue-400 font-black uppercase tracking-wider">Active: {analyzeLastRun?.intervalConfig}</p>
                            ) : (
                                <p className="text-[10px] text-slate-600 font-bold uppercase tracking-wider">Standard Cycle</p>
                            )}
                        </div>
                    </div>
                </Card>
            </div>

            {/* --- RUN INSPECTOR --- */}
            {analyzeLastRun && (
                <div className="animate-in slide-in-from-bottom-4 duration-500">
                    <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2"><Activity className="w-5 h-5 text-plex-orange" /> Run Inspector <span className="text-xs font-normal text-slate-500 ml-2">(Analyzed from latest logs)</span></h3>
                    <div className="grid grid-cols-1 gap-6">
                        <div className={`border rounded-xl overflow-hidden ${analyzeLastRun.status === 'FAILED' ? 'border-red-900/50 bg-red-950/10' : 'border-slate-800/80 bg-slate-900/40'}`}>
                            {/* Run Header */}
                            <div className="p-4 border-b border-white/5 flex flex-wrap gap-4 items-center justify-between bg-slate-950/30">
                                <div className="flex items-center gap-4">
                                    <div className={`px-3 py-1 rounded text-xs font-bold uppercase ${analyzeLastRun.status === 'COMPLETED' ? 'bg-emerald-500/20 text-emerald-400' :
                                        analyzeLastRun.status === 'RUNNING' ? 'bg-blue-500/20 text-blue-400' :
                                            'bg-red-500/20 text-red-400'
                                        }`}>
                                        {analyzeLastRun.status}
                                    </div>
                                    <div className="text-sm text-slate-400 flex items-center gap-2">
                                        <Clock className="w-4 h-4" /> Started: <span className="text-slate-200 font-mono">{analyzeLastRun.startTime}</span>
                                    </div>
                                    <div className="text-sm text-slate-400">
                                        Duration: <span className="text-slate-200 font-mono">{analyzeLastRun.duration}</span>
                                    </div>
                                </div>
                                <div className="text-sm font-bold text-white bg-slate-800 px-3 py-1 rounded-lg border border-slate-700">
                                    Total Pinned: {analyzeLastRun.totalPins}
                                </div>
                            </div>

                            {/* Library Breakdown Table */}
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm text-left">
                                    <thead className="text-xs text-slate-500 uppercase bg-slate-950/50 border-b border-slate-800">
                                        <tr>
                                            <th className="px-6 py-3">Library</th>
                                            <th className="px-6 py-3 text-center">Found</th>
                                            <th className="px-6 py-3 text-center">Eligible</th>
                                            <th className="px-6 py-3 text-center">Pinned</th>
                                            <th className="px-6 py-3">Status / Reason</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-800/50">
                                        {analyzeLastRun.libraries.map((lib, idx) => (
                                            <tr key={idx} className="hover:bg-slate-800/20 transition-colors">
                                                <td className="px-6 py-4 font-medium text-slate-200">{lib.name}</td>
                                                <td className="px-6 py-4 text-center text-slate-400">{lib.found}</td>
                                                <td className="px-6 py-4 text-center">
                                                    <span className={`px-2 py-1 rounded ${lib.eligible > 0 ? 'bg-blue-900/30 text-blue-300' : 'bg-slate-800 text-slate-500'}`}>
                                                        {lib.eligible}
                                                    </span>
                                                </td>
                                                <td className="px-6 py-4 text-center">
                                                    {lib.pinned > 0 ? (
                                                        <span className="text-emerald-400 font-bold">{lib.pinned}</span>
                                                    ) : (
                                                        <span className="text-slate-600">-</span>
                                                    )}
                                                </td>
                                                <td className="px-6 py-4">
                                                    {lib.pinned > 0 ? (
                                                        <span className="text-emerald-400 flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> Success</span>
                                                    ) : lib.found === 0 ? (
                                                        <span className="text-slate-500">Empty Library</span>
                                                    ) : lib.blockedByTimer > 0 && lib.eligible === 0 ? (
                                                        <span className="text-amber-400 flex items-center gap-1"><Clock className="w-3 h-3" /> {lib.blockedByTimer} items blocked by timer</span>
                                                    ) : lib.eligible === 0 ? (
                                                        <span className="text-slate-500">All filtered out (Exclusions)</span>
                                                    ) : lib.blockedByCategory ? (
                                                        <span className="text-blue-400 flex items-center gap-1"><Filter className="w-3 h-3" /> Category Mode Restricted</span>
                                                    ) : (
                                                        <span className="text-slate-500">Skipped (Random chance)</span>
                                                    )}
                                                </td>
                                            </tr>
                                        ))}
                                        {analyzeLastRun.libraries.length === 0 && (
                                            <tr>
                                                <td colSpan={5} className="px-6 py-8 text-center text-slate-500 italic">
                                                    No libraries processed yet in this run.
                                                </td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Log Console */}
            <Card
                title="Live Logs"
                className="flex flex-col min-h-[400px] border-slate-800/80 bg-slate-900/40"
                actions={
                    <div className="flex gap-3">
                        <button onClick={() => setLiveLogs(!liveLogs)} className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold border transition-all ${liveLogs ? 'bg-green-500/20 text-green-400 border-green-500/30' : 'bg-slate-800 text-slate-400 border-slate-700'}`}>
                            {liveLogs ? <ToggleRight className="w-4 h-4" /> : <ToggleLeft className="w-4 h-4" />}
                            {liveLogs ? 'Live Stream ON' : 'Live Stream OFF'}
                        </button>
                    </div>
                }
            >
                <div ref={logContainerRef} className="bg-black/80 rounded-xl p-4 font-mono text-xs text-slate-300 overflow-y-auto h-80 border border-slate-800 shadow-inner leading-relaxed scrollbar-thin">
                    {logs ? <pre className="whitespace-pre-wrap break-all">{logs}</pre> : <div className="h-full flex items-center justify-center text-slate-600 flex-col gap-3"><Terminal className="w-10 h-10 opacity-30" /><p>Waiting for logs...</p></div>}
                </div>
            </Card>
        </div>
    );
};

export default Dashboard;