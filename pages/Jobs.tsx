import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import {
    Play,
    Trash2,
    RefreshCcw,
    Clock,
    Calendar,
    Database,
    CheckCircle2,
    Activity,
    ChevronRight,
    Search,
    Settings2
} from 'lucide-react';

import { CustomSelect } from '../components/ui/Inputs';

interface ManagedJob {
    name: string;
    library: string;
    source_type: string;
    source_id: string;
    sort_order: string;
    last_run: string;
    next_run: string;
    created_at: string;
    auto_sync: boolean;
}

const JobsPage: React.FC = () => {
    const [jobs, setJobs] = useState<Record<string, ManagedJob>>({});
    const [loading, setLoading] = useState(true);
    const [runningJob, setRunningJob] = useState<string | null>(null);

    // Search & Filter State
    const [searchQuery, setSearchQuery] = useState('');
    const [serviceFilter, setServiceFilter] = useState<'all' | 'trakt' | 'mdblist'>('all');
    const [currentPage, setCurrentPage] = useState(1);
    const [itemsPerPage, setItemsPerPage] = useState(10);

    useEffect(() => {
        fetchJobs();
    }, []);

    const fetchJobs = async () => {
        setLoading(true);
        try {
            const data = await api.getJobs();
            setJobs(data);
        } catch (e) {
            console.error("Failed to fetch jobs", e);
        }
        setLoading(false);
    };

    const handleRunNow = async (id: string) => {
        setRunningJob(id);
        try {
            await api.runJobNow(id);
            await fetchJobs();
        } catch (e) {
            console.error("Failed to run job", e);
        }
        setRunningJob(null);
    };

    const handleDelete = async (id: string) => {
        if (window.confirm(`Are you sure you want to stop auto-syncing "${jobs[id].name}"?`)) {
            try {
                await api.deleteJob(id);
                await fetchJobs();
            } catch (e) {
                console.error("Failed to delete job", e);
            }
        }
    };

    const getSourceBadge = (type: string) => {
        if (type.includes('trakt')) return <span className="px-2 py-0.5 bg-red-900/40 text-red-400 border border-red-800/50 rounded text-[10px] font-bold uppercase tracking-wider">Trakt</span>;
        if (type.includes('tmdb')) return <span className="px-2 py-0.5 bg-blue-900/40 text-blue-400 border border-blue-800/50 rounded text-[10px] font-bold uppercase tracking-wider">TMDb</span>;
        if (type.includes('mdblist')) return <span className="px-2 py-0.5 bg-purple-900/40 text-purple-400 border border-purple-800/50 rounded text-[10px] font-bold uppercase tracking-wider">MdbList</span>;
        return <span className="px-2 py-0.5 bg-slate-800 text-slate-400 border border-slate-700 rounded text-[10px] font-bold uppercase tracking-wider">Other</span>;
    };

    // Filter Logic
    const filteredJobs = Object.entries(jobs).filter(([_, job]) => {
        const matchesSearch = job.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            job.library.toLowerCase().includes(searchQuery.toLowerCase());
        const matchesService = serviceFilter === 'all' ||
            (serviceFilter === 'trakt' && job.source_type.includes('trakt')) ||
            (serviceFilter === 'mdblist' && job.source_type.includes('mdblist'));
        return matchesSearch && matchesService;
    }).sort((a, b) => b[1].created_at.localeCompare(a[1].created_at));

    // Pagination Logic
    const totalPages = Math.ceil(filteredJobs.length / itemsPerPage);
    const paginatedJobs = filteredJobs.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);

    if (loading && Object.keys(jobs).length === 0) {
        return (
            <div className="flex flex-col h-96 items-center justify-center text-slate-500 animate-pulse">
                <Activity className="w-12 h-12 mb-4 opacity-50" />
                <p>loading auto-sync schedules...</p>
            </div>
        );
    }

    return (
        <div className="space-y-8 animate-in fade-in duration-500 pb-10">
            {/* Header Area */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 className="text-2xl md:text-3xl font-bold text-white tracking-tight">Active Jobs</h2>
                    <p className="text-slate-400 mt-1 flex items-center gap-2 text-sm md:text-base">
                        <Settings2 className="w-4 h-4 text-plex-orange" />
                        Managed Auto-Sync Collections
                    </p>
                </div>
                <div className="flex items-center gap-3 w-full md:w-auto">
                    <button
                        onClick={fetchJobs}
                        className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-white px-4 py-2.5 rounded-xl transition-colors border border-slate-700/50"
                    >
                        <RefreshCcw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                        <span className="hidden sm:inline">Refresh Status</span>
                    </button>
                </div>
            </div>

            {/* Filters Bar */}
            <div className="bg-slate-900/40 border border-slate-800 p-4 rounded-2xl flex flex-col md:flex-row gap-4 items-center justify-between">
                <div className="relative w-full md:w-96 group">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 group-focus-within:text-plex-orange transition-colors" />
                    <input
                        type="text"
                        placeholder="Search jobs or libraries..."
                        value={searchQuery}
                        onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(1); }}
                        className="w-full bg-slate-950/50 border border-slate-800 rounded-xl pl-10 pr-4 py-2.5 text-slate-200 focus:outline-none focus:ring-2 focus:ring-plex-orange/30 focus:border-plex-orange/50 transition-all"
                    />
                </div>

                <div className="flex items-center gap-4 w-full md:w-auto">
                    <div className="flex bg-slate-950/50 border border-slate-800 rounded-xl p-1">
                        {(['all', 'trakt', 'mdblist'] as const).map(f => (
                            <button
                                key={f}
                                onClick={() => { setServiceFilter(f); setCurrentPage(1); }}
                                className={`px-4 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-all ${serviceFilter === f ? 'bg-slate-800 text-white shadow-xl' : 'text-slate-500 hover:text-slate-300'
                                    }`}
                            >
                                {f}
                            </button>
                        ))}
                    </div>

                    <CustomSelect
                        label=""
                        value={itemsPerPage}
                        onChange={(v) => { setItemsPerPage(Number(v)); setCurrentPage(1); }}
                        options={[10, 25, 50, 75, 100].map(v => ({ value: v, label: `${v} per page` }))}
                        className="w-44"
                    />
                </div>
            </div>

            {Object.keys(jobs).length === 0 ? (
                <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-12 text-center flex flex-col items-center">
                    <div className="p-4 bg-slate-800 rounded-full mb-6 text-slate-600">
                        <Clock className="w-12 h-12" />
                    </div>
                    <h3 className="text-xl font-bold text-white mb-2">No Auto-Sync Jobs</h3>
                    <p className="text-slate-400 mb-8">
                        Collections created with the "Auto-Sync" option in the Creator tab will appear here. These jobs automatically refresh your collections every 6 hours.
                    </p>
                    <a
                        href="/creator"
                        className="inline-flex items-center gap-2 bg-plex-orange hover:bg-plex-orange/80 text-white px-6 py-3 rounded-xl font-bold transition-all transform hover:scale-105"
                    >
                        Go to Creator <ChevronRight className="w-5 h-5" />
                    </a>
                </div>
            ) : filteredJobs.length === 0 ? (
                <div className="text-center py-20 bg-slate-900/20 border border-dashed border-slate-800 rounded-3xl">
                    <Search className="w-12 h-12 text-slate-700 mx-auto mb-4" />
                    <p className="text-slate-500">No jobs found matching your filters.</p>
                </div>
            ) : (
                <div className="space-y-4">
                    <div className="grid grid-cols-1 gap-4">
                        {paginatedJobs.map(([id, job]) => (
                            <div key={id} className="bg-slate-900/40 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-all group">
                                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
                                    {/* Left: Job Info */}
                                    <div className="flex items-start gap-4">
                                        <div className="p-3 bg-slate-800 rounded-lg text-plex-orange">
                                            <Database className="w-6 h-6" />
                                        </div>
                                        <div className="min-w-0">
                                            <div className="flex items-center gap-2 flex-wrap">
                                                <h3 className="text-lg font-bold text-white uppercase tracking-tight truncate max-w-[200px] md:max-w-md">{job.name}</h3>
                                                {getSourceBadge(job.source_type)}
                                            </div>
                                            <div className="flex items-center gap-4 mt-1 text-sm text-slate-500">
                                                <span className="flex items-center gap-1">
                                                    <Database className="w-3 h-3" /> {job.library}
                                                </span>
                                                <span className="flex items-center gap-1">
                                                    <Activity className="w-3 h-3" /> {job.source_type.replace(/_/g, ' ')}
                                                </span>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Middle: Timing */}
                                    <div className="grid grid-cols-2 md:grid-cols-3 gap-6 flex-1 max-w-2xl">
                                        <div className="flex flex-col">
                                            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-1 flex items-center gap-1">
                                                <CheckCircle2 className="w-3 h-3 text-green-500" /> Last Sync
                                            </span>
                                            <span className="text-sm font-mono text-slate-300">{job.last_run}</span>
                                        </div>
                                        <div className="flex flex-col">
                                            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-1 flex items-center gap-1">
                                                <Clock className="w-3 h-3 text-blue-500" /> Next Sync
                                            </span>
                                            <span className="text-sm font-mono text-slate-300 uppercase">{job.next_run}</span>
                                        </div>
                                        <div className="flex flex-col hidden md:flex">
                                            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-1 flex items-center gap-1">
                                                <Calendar className="w-3 h-3" /> Created
                                            </span>
                                            <span className="text-xs text-slate-400">{job.created_at}</span>
                                        </div>
                                    </div>

                                    {/* Right: Actions */}
                                    <div className="flex items-center gap-2 border-t lg:border-t-0 pt-4 lg:pt-0">
                                        <button
                                            onClick={() => handleRunNow(id)}
                                            disabled={runningJob === id}
                                            className="flex-1 lg:flex-none flex items-center justify-center gap-2 px-4 py-2.5 bg-green-950/30 hover:bg-green-600 text-green-400 hover:text-white border border-green-900/50 rounded-lg text-sm font-bold transition-all disabled:opacity-50"
                                        >
                                            {runningJob === id ? <RefreshCcw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                                            {runningJob === id ? '...' : 'Run Now'}
                                        </button>
                                        <button
                                            onClick={() => handleDelete(id)}
                                            className="flex items-center justify-center p-2.5 bg-red-950/30 hover:bg-red-600 text-red-500 hover:text-white border border-red-950 rounded-lg transition-all"
                                            title="Stop Auto-Sync"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Pagination Controls */}
                    {totalPages > 1 && (
                        <div className="flex items-center justify-center gap-2 pt-6">
                            <button
                                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                                disabled={currentPage === 1}
                                className="px-4 py-2 bg-slate-900 border border-slate-800 rounded-xl text-slate-400 hover:text-white disabled:opacity-30 transition-all font-bold"
                            >
                                Prev
                            </button>
                            <div className="flex items-center gap-2">
                                {[...Array(totalPages)].map((_, i) => (
                                    <button
                                        key={i}
                                        onClick={() => setCurrentPage(i + 1)}
                                        className={`w-10 h-10 rounded-xl font-bold transition-all ${currentPage === i + 1
                                            ? 'bg-plex-orange text-white shadow-lg'
                                            : 'bg-slate-900 border border-slate-800 text-slate-400 hover:border-slate-700'
                                            }`}
                                    >
                                        {i + 1}
                                    </button>
                                ))}
                            </div>
                            <button
                                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                                disabled={currentPage === totalPages}
                                className="px-4 py-2 bg-slate-900 border border-slate-800 rounded-xl text-slate-400 hover:text-white disabled:opacity-30 transition-all font-bold"
                            >
                                Next
                            </button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default JobsPage;
