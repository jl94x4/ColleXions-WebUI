import React, { useEffect, useState, useRef } from 'react';
import { api } from '../services/api';
import { Card } from '../components/ui/Card';
import { RefreshCw, Download, ScrollText, Terminal, ToggleLeft, ToggleRight, ArrowDownCircle, AlertTriangle, Ban } from 'lucide-react';

const LogsPage: React.FC = () => {
    const [logs, setLogs] = useState<string>('Loading logs...');
    const [autoScroll, setAutoScroll] = useState(true);
    const [isLive, setIsLive] = useState(true); // Default ON to auto-stream logs

    // Persistence
    useEffect(() => {
        const saved = localStorage.getItem('collexions_logs_state');
        if (saved) {
            try {
                const state = JSON.parse(saved);
                if (state.autoScroll !== undefined) setAutoScroll(state.autoScroll);
                if (state.isLive !== undefined) setIsLive(state.isLive);
            } catch (e) { console.error(e); }
        }
    }, []);

    useEffect(() => {
        localStorage.setItem('collexions_logs_state', JSON.stringify({ autoScroll, isLive }));
    }, [autoScroll, isLive]);

    const logEndRef = useRef<HTMLDivElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    const fetchLogs = async () => {
        try {
            const l = await api.getLogs();
            setLogs(l);
        } catch (e) {
            setLogs("Error fetching logs or backend offline.");
        }
    };

    useEffect(() => {
        fetchLogs(); // Always fetch once on mount
    }, []);

    useEffect(() => {
        if (isLive) {
            const interval = setInterval(fetchLogs, 10000); // 10s interval
            return () => clearInterval(interval);
        }
    }, [isLive]);

    useEffect(() => {
        if (autoScroll && logEndRef.current) {
            logEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [logs, autoScroll]);

    const downloadLogs = () => {
        const element = document.createElement("a");
        const file = new Blob([logs], { type: 'text/plain' });
        element.href = URL.createObjectURL(file);
        element.download = "collexions.log";
        document.body.appendChild(element);
        element.click();
    };

    const scrollToBottom = () => {
        logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    return (
        <div className="h-[calc(100vh-80px)] flex flex-col animate-in fade-in duration-500">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
                <div>
                    <h2 className="text-3xl font-bold text-white tracking-tight">System Logs</h2>
                    <p className="text-slate-400 mt-1 flex items-center gap-2">
                        <ScrollText className="w-4 h-4" />
                        Full script execution output
                    </p>
                </div>

                <div className="flex flex-wrap gap-3">
                    <div className="bg-amber-500/10 text-amber-500 border border-amber-500/20 px-3 py-2 rounded-lg text-xs flex items-center gap-2">
                        <AlertTriangle className="w-3 h-3" /> Showing last 2000 lines
                    </div>
                    <button
                        onClick={() => setIsLive(!isLive)}
                        className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-bold border transition-all ${isLive ? 'bg-green-500/20 text-green-400 border-green-500/30' : 'bg-slate-800 text-slate-400 border-slate-700'}`}
                    >
                        {isLive ? <ToggleRight className="w-4 h-4" /> : <ToggleLeft className="w-4 h-4" />}
                        {isLive ? 'Live Tail ON' : 'Live Tail OFF'}
                    </button>

                    <button
                        onClick={() => setAutoScroll(!autoScroll)}
                        className={`px-4 py-2 rounded-lg text-sm font-medium border transition-all ${autoScroll ? 'bg-plex-orange text-white border-transparent shadow-lg shadow-orange-900/20' : 'bg-transparent text-slate-400 border-slate-700 hover:text-white'}`}>
                        Auto-scroll: {autoScroll ? 'ON' : 'OFF'}
                    </button>
                    <button onClick={async () => {
                        if (confirm("Clear log file? This cannot be undone.")) {
                            try { await api.clearLogs(); fetchLogs(); } catch (e) { alert("Failed to clear"); }
                        }
                    }} className="bg-red-500/10 hover:bg-red-500/20 text-red-500 px-3 py-2 rounded-lg text-sm transition-colors border border-red-500/30" title="Clear Logs">
                        <Ban className="w-4 h-4" />
                    </button>
                    <button onClick={scrollToBottom} className="bg-slate-800 hover:bg-slate-700 text-white px-3 py-2 rounded-lg text-sm transition-colors border border-slate-700" title="Jump to Bottom">
                        <ArrowDownCircle className="w-4 h-4" />
                    </button>
                    <button onClick={downloadLogs} className="bg-slate-800 hover:bg-slate-700 text-white px-4 py-2 rounded-lg text-sm flex items-center gap-2 transition-colors border border-slate-700">
                        <Download className="w-4 h-4" /> Export
                    </button>
                    <button onClick={fetchLogs} className="bg-slate-800 hover:bg-slate-700 text-white px-3 py-2 rounded-lg text-sm transition-colors border border-slate-700">
                        <RefreshCw className="w-4 h-4" />
                    </button>
                </div>
            </div>

            <Card className="flex-1 overflow-hidden flex flex-col p-0 border-slate-800/60 shadow-2xl relative">
                <div ref={containerRef} className="flex-1 overflow-y-auto bg-black/80 p-6 font-mono text-xs md:text-sm text-slate-300 scrollbar-thin leading-relaxed">
                    {logs ? (
                        <pre className="whitespace-pre-wrap break-all">{logs}</pre>
                    ) : (
                        <div className="h-full flex items-center justify-center text-slate-600 flex-col gap-4">
                            <Terminal className="w-12 h-12 opacity-20" />
                            <p>No logs available</p>
                        </div>
                    )}
                    <div ref={logEndRef} />
                </div>
                {!autoScroll && logs.length > 2000 && (
                    <div className="absolute bottom-6 right-8 animate-bounce">
                        <button onClick={scrollToBottom} className="bg-plex-orange text-white p-3 rounded-full shadow-lg hover:bg-orange-600 transition-colors">
                            <ArrowDownCircle className="w-6 h-6" />
                        </button>
                    </div>
                )}
            </Card>
        </div>
    );
};

export default LogsPage;