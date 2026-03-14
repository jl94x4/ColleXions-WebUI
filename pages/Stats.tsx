import React, { useEffect, useState, useMemo } from 'react';
import { api } from '../services/api';
import { PinEvent } from '../types';
import {
  Trophy,
  History,
  Layers,
  RefreshCcw,
  Activity,
  Zap,
  Clock,
  Film,
  Tv,
  Music,
  BarChart3,
  TrendingUp,
  Database,
  ToggleLeft,
  ToggleRight,
  PieChart,
  Timer
} from 'lucide-react';

interface PinSession {
  id: string;
  timestamp: Date;
  library: string;
  collections: string[];
}

interface RunStat {
  timestamp: Date;
  durationSeconds: number;
  formattedDuration: string;
}

const StatsPage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [events, setEvents] = useState<PinEvent[]>([]);
  const [trueTotalPins, setTrueTotalPins] = useState(0);
  const [trueUniqueCount, setTrueUniqueCount] = useState(0);
  const [runStats, setRunStats] = useState<RunStat[]>([]);
  const [isLive, setIsLive] = useState(true);
  const [lastSyncTime, setLastSyncTime] = useState<string>('');

  // Persistence
  useEffect(() => {
    const saved = localStorage.getItem('collexions_stats_state');
    if (saved) {
      try {
        const state = JSON.parse(saved);
        if (state.isLive !== undefined) setIsLive(state.isLive);
      } catch (e) { console.error(e); }
    }
  }, []);

  useEffect(() => {
    localStorage.setItem('collexions_stats_state', JSON.stringify({ isLive }));
  }, [isLive]);

  // Initial Load
  useEffect(() => {
    syncData(false);
  }, []);

  // Live Poll
  useEffect(() => {
    if (isLive) {
      const interval = setInterval(() => {
        syncData(true);
      }, 30000); // Poll every 30s (Read only)
      return () => clearInterval(interval);
    }
  }, [isLive, syncData]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  async function syncData(isBackground = false) {
    if (!isBackground) setLoading(true);

    try {
      // 1. Fetch Source of Truth (Server History)
      // The backend now auto-syncs logs to history on this request
      const historyResponse = await api.getHistory(10000);
      setTrueTotalPins(historyResponse?.total_count || 0);
      setTrueUniqueCount(historyResponse?.unique_count || 0);

      // 2. Fetch Live Logs (Primarily for Run Performance stats)
      const logText = await api.getLogs();
      const { events: parsedLogEvents, runs: parsedRuns } = parseLogs(logText);
      setRunStats(parsedRuns);

      // 3. Merge In-Memory (Server + Live Logs)
      // Since server auto-syncs, merged will mostly be identical to historyResponse.events
      const merged = mergeEvents(historyResponse?.events || [], parsedLogEvents);
      setEvents(merged);

      setLastSyncTime(new Date().toLocaleTimeString());

    } catch (e) {
      console.error("Stats sync failed", e);
    }

    if (!isBackground) setLoading(false);
  }

  function parseLogs(logText: string): { events: PinEvent[], runs: RunStat[] } {
    const lines = logText.split('\n');
    const newEvents: PinEvent[] = [];
    const runs: RunStat[] = [];

    let currentLibrary = 'Unknown Library';

    const libRegex = /Processing Library:.*?['"](.+?)['"]/;
    const pinRegex = /(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?).*?(?:Pinning:|Pinned|Processing for pin:)\s+['"](.+?)['"]/;
    const runEndRegex = /(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{1,2}(?:[.,]\d+)?).*?(?:Duration:|Total run duration:)\s+([\d:.]+)/;

    lines.forEach(line => {
      const libMatch = line.match(libRegex);
      if (libMatch) {
        currentLibrary = libMatch[1];
        return;
      }

      const pinMatch = line.match(pinRegex);
      if (pinMatch) {
        const dateStr = pinMatch[1].trim().replace(' ', 'T').replace(',', '.').replace(/(\.\d{3})\d+/, '$1');
        const name = pinMatch[2];
        const d = new Date(dateStr);
        if (!isNaN(d.getTime())) {
          newEvents.push({
            timestamp: d.toISOString(),
            collectionName: name,
            library: currentLibrary
          });
        }
      }

      const runMatch = line.match(runEndRegex);
      if (runMatch) {
        const dateStr = runMatch[1].trim().replace(' ', 'T').replace(',', '.').replace(/(\.\d{3})\d+/, '$1');
        const durationStr = runMatch[2];
        const d = new Date(dateStr);
        let seconds = 0;
        if (durationStr.includes(':')) {
          const parts = durationStr.split(':');
          if (parts.length === 3) {
            seconds = (+parts[0]) * 3600 + (+parts[1]) * 60 + parseFloat(parts[2]);
          }
        } else {
          seconds = parseFloat(durationStr);
        }
        if (!isNaN(d.getTime()) && !isNaN(seconds)) {
          runs.push({
            timestamp: d,
            durationSeconds: seconds,
            formattedDuration: durationStr
          });
        }
      }
    });

    return { events: newEvents, runs: runs.reverse() };
  }

  function mergeEvents(server: PinEvent[], logs: PinEvent[]): PinEvent[] {
    const map = new Map<string, PinEvent>();
    const genKey = (e: PinEvent) => `${e.timestamp}|${e.library}|${e.collectionName}`;

    // Load server history first
    server.forEach(e => map.set(genKey(e), e));
    // Overlay live logs (duplicates overwrite same keys)
    logs.forEach(e => map.set(genKey(e), e));

    return Array.from(map.values())
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  }

  const handleClearStats = async () => {
    if (confirm("DANGER: This will wipe all statistical history from the SERVER. Continue?")) {
      setLoading(true);
      await api.saveHistory([]);
      setEvents([]);
      setLoading(false);
    }
  };

  const {
    collectionStats,
    sessions,
    totalPins,
    uniqueCount,
    mostActiveLibrary,
    hourlyActivity,
    libraryDistribution
  } = useMemo(() => {
    const counts: Record<string, { count: number, library: string }> = {};
    const libraryCounts: Record<string, number> = {};
    const hours = new Array(24).fill(0);

    events.forEach(e => {
      if (!counts[e.collectionName]) {
        counts[e.collectionName] = { count: 0, library: e.library };
      }
      counts[e.collectionName].count++;
      libraryCounts[e.library] = (libraryCounts[e.library] || 0) + 1;

      const date = new Date(e.timestamp);
      hours[date.getHours()]++;
    });

    const sortedCollections = Object.entries(counts)
      .sort(([, a], [, b]) => b.count - a.count)
      .map(([name, data]) => ({ name, ...data }));

    const sortedLibs = Object.entries(libraryCounts)
      .sort(([, a], [, b]) => b - a)
      .map(([name, count]) => ({ name, count }));

    const sessionMap = new Map<string, PinSession>();
    events.forEach(event => {
      const dateObj = new Date(event.timestamp);
      const timeKeyDate = new Date(dateObj);
      timeKeyDate.setSeconds(0);
      timeKeyDate.setMilliseconds(0);
      const timeKey = `${timeKeyDate.getTime()}-${event.library}`;

      const existingSession = sessionMap.get(timeKey);

      if (existingSession) {
        if (!existingSession.collections.includes(event.collectionName)) {
          existingSession.collections.push(event.collectionName);
        }
      } else {
        sessionMap.set(timeKey, {
          id: timeKey,
          timestamp: timeKeyDate,
          library: event.library,
          collections: [event.collectionName]
        });
      }
    });

    const groupedSessions = Array.from(sessionMap.values())
      .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());

    return {
      collectionStats: sortedCollections,
      sessions: groupedSessions,
      totalPins: events.length,
      uniqueCount: Object.keys(counts).length,
      mostActiveLibrary: sortedLibs[0] ? sortedLibs[0].name : 'None',
      hourlyActivity: hours,
      libraryDistribution: sortedLibs
    };
  }, [events]);

  const getLibraryIcon = (lib: string) => {
    const l = lib.toLowerCase();
    if (l.includes('movie')) return <Film className="w-4 h-4" />;
    if (l.includes('tv') || l.includes('show')) return <Tv className="w-4 h-4" />;
    if (l.includes('music')) return <Music className="w-4 h-4" />;
    return <Layers className="w-4 h-4" />;
  };

  const getLibraryColor = (lib: string) => {
    const l = lib.toLowerCase();
    if (l.includes('movie')) return 'text-blue-400 bg-blue-900/30 border-blue-800';
    if (l.includes('tv') || l.includes('show')) return 'text-purple-400 bg-purple-900/30 border-purple-800';
    if (l.includes('music')) return 'text-pink-400 bg-pink-900/30 border-pink-800';
    return 'text-slate-400 bg-slate-800 border-slate-700';
  };

  const getProgressBarColor = (lib: string) => {
    const l = lib.toLowerCase();
    if (l.includes('movie')) return 'bg-blue-600';
    if (l.includes('tv') || l.includes('show')) return 'bg-purple-600';
    if (l.includes('music')) return 'bg-pink-600';
    return 'bg-slate-600';
  };

  if (loading && events.length === 0) {
    return (
      <div className="flex flex-col h-96 items-center justify-center text-slate-500 animate-pulse">
        <Activity className="w-12 h-12 mb-4 opacity-50" />
        <p>Loading History...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500 pb-10">

      {/* Header Area */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-2xl md:text-3xl font-bold text-white tracking-tight">Data Hub</h2>
          <p className="text-slate-400 mt-1 flex items-center gap-2 text-sm md:text-base">
            <BarChart3 className="w-4 h-4" />
            Cross-Device Statistics & Insights
          </p>
        </div>
        <div className="flex flex-col sm:flex-row gap-3 w-full md:w-auto flex-wrap">

          <div className="px-3 py-2 text-xs text-slate-500 flex items-center gap-2 border border-slate-800 rounded-lg">
            <Clock className="w-3 h-3" /> Last Sync: {lastSyncTime || 'Pending'}
          </div>

          <button
            onClick={() => setIsLive(!isLive)}
            className={`flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm font-bold border transition-all ${isLive ? 'bg-green-500/20 text-green-400 border-green-500/30' : 'bg-slate-800 text-slate-400 border-slate-700'}`}
          >
            {isLive ? <ToggleRight className="w-4 h-4" /> : <ToggleLeft className="w-4 h-4" />}
            {isLive ? 'Live' : 'Live OFF'}
          </button>

          <button
            onClick={() => syncData(false)}
            className="flex-1 md:flex-none justify-center flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-white px-4 py-2.5 rounded-lg transition-colors border border-slate-700/50"
            title="Force refresh"
          >
            <RefreshCcw className="w-4 h-4" /> Refresh
          </button>

          <button
            onClick={handleClearStats}
            className="flex-1 md:flex-none justify-center flex items-center gap-2 bg-slate-900 hover:bg-red-950/50 text-slate-500 hover:text-red-400 border border-slate-800 hover:border-red-900 px-3 py-2.5 rounded-lg text-sm font-medium transition-all"
            title="Reset Database"
          >
            <Database className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Top Level Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900/50 border border-slate-800 p-5 rounded-xl flex flex-col justify-between hover:border-slate-700 transition-colors group">
          <div className="flex justify-between items-start mb-2">
            <span className="text-slate-500 text-xs font-bold uppercase tracking-wider">Total Pins</span>
            <div className="p-2 bg-slate-800 rounded-lg text-plex-orange group-hover:bg-plex-orange group-hover:text-white transition-colors">
              <Zap className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-bold text-white">{trueTotalPins}</div>
          <div className="text-xs text-slate-500 mt-2">Cumulative lifetime rotations</div>
        </div>

        <div className="bg-slate-900/50 border border-slate-800 p-5 rounded-xl flex flex-col justify-between hover:border-slate-700 transition-colors group">
          <div className="flex justify-between items-start mb-2">
            <span className="text-slate-500 text-xs font-bold uppercase tracking-wider">Unique Items</span>
            <div className="p-2 bg-slate-800 rounded-lg text-blue-500 group-hover:bg-blue-600 group-hover:text-white transition-colors">
              <Layers className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-bold text-white">{trueUniqueCount || uniqueCount}</div>
          <div className="text-xs text-slate-500 mt-2">Distinct collections pinned</div>
        </div>

        <div className="bg-slate-900/50 border border-slate-800 p-5 rounded-xl flex flex-col justify-between hover:border-slate-700 transition-colors group">
          <div className="flex justify-between items-start mb-2">
            <span className="text-slate-500 text-xs font-bold uppercase tracking-wider">Top Library</span>
            <div className="p-2 bg-slate-800 rounded-lg text-purple-500 group-hover:bg-purple-600 group-hover:text-white transition-colors">
              <Trophy className="w-4 h-4" />
            </div>
          </div>
          <div className="text-xl font-bold text-white truncate">{mostActiveLibrary}</div>
          <div className="text-xs text-slate-500 mt-2">Most frequently updated</div>
        </div>

        <div className="bg-slate-900/50 border border-slate-800 p-5 rounded-xl flex flex-col justify-between hover:border-slate-700 transition-colors group">
          <div className="flex justify-between items-start mb-2">
            <span className="text-slate-500 text-xs font-bold uppercase tracking-wider">Last Run</span>
            <div className="p-2 bg-slate-800 rounded-lg text-green-500 group-hover:bg-green-600 group-hover:text-white transition-colors">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div className="text-lg font-bold text-white">
            {sessions[0] ? (
              sessions[0].timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            ) : '--:--'}
          </div>
          <div className="text-xs text-slate-500 mt-2">
            {sessions[0] ? sessions[0].timestamp.toLocaleDateString() : 'No activity yet'}
          </div>
        </div>
      </div>

      {/* --- DEEP INSIGHTS SECTION --- */}
      <h3 className="text-xl font-bold text-white flex items-center gap-2 mt-8">
        <PieChart className="w-5 h-5 text-plex-orange" />
        Deep Insights
      </h3>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">

        {/* 1. Run Performance */}
        <div className="bg-slate-900/30 border border-slate-800 rounded-2xl p-5">
          <h4 className="text-sm font-bold text-slate-300 uppercase tracking-wider mb-4 flex items-center gap-2">
            <Timer className="w-4 h-4" /> Run Duration History
          </h4>
          <div className="flex items-end h-32 gap-1 overflow-hidden">
            {runStats.slice(0, 20).reverse().map((run, idx) => {
              const max = Math.max(...runStats.map(r => r.durationSeconds)) || 1;
              const height = Math.max((run.durationSeconds / max) * 100, 10);
              return (
                <div
                  key={idx}
                  className="flex-1 bg-emerald-600/60 rounded-sm hover:bg-emerald-400 relative group transition-all"
                  style={{ height: `${height}%` }}
                >
                  <div className="hidden group-hover:block absolute bottom-full left-1/2 -translate-x-1/2 mb-1 bg-black text-white text-[10px] px-2 py-1 rounded border border-slate-700 whitespace-nowrap z-10">
                    {run.durationSeconds.toFixed(1)}s <br /> {run.timestamp.toLocaleTimeString()}
                  </div>
                </div>
              );
            })}
            {runStats.length === 0 && <p className="text-slate-600 text-xs italic w-full text-center self-center">No run data yet</p>}
          </div>
          <div className="flex justify-between text-[10px] text-slate-600 mt-2 font-mono">
            <span>Oldest</span><span>Latest</span>
          </div>
        </div>

        {/* 2. Hourly Activity Heatmap */}
        <div className="bg-slate-900/30 border border-slate-800 rounded-2xl p-5">
          <h4 className="text-sm font-bold text-slate-300 uppercase tracking-wider mb-4 flex items-center gap-2">
            <Clock className="w-4 h-4" /> Hourly Activity (24h)
          </h4>
          <div className="flex items-end h-32 gap-1">
            {hourlyActivity.map((count, hour) => {
              const max = Math.max(...hourlyActivity) || 1;
              const height = Math.max((count / max) * 100, 5); // min 5% height
              return (
                <div
                  key={hour}
                  className={`flex-1 rounded-sm transition-all hover:bg-plex-orange relative group ${count > 0 ? 'bg-blue-600/60' : 'bg-slate-800/30'}`}
                  style={{ height: `${height}%` }}
                >
                  <div className="hidden group-hover:block absolute bottom-full left-1/2 -translate-x-1/2 mb-1 bg-black text-white text-[10px] px-1.5 py-0.5 rounded border border-slate-700 whitespace-nowrap z-10">
                    {hour}:00 ({count})
                  </div>
                </div>
              )
            })}
          </div>
          <div className="flex justify-between text-[10px] text-slate-600 mt-2 font-mono">
            <span>00</span><span>06</span><span>12</span><span>18</span><span>23</span>
          </div>
        </div>

        {/* 3. Library Distribution */}
        <div className="bg-slate-900/30 border border-slate-800 rounded-2xl p-5">
          <h4 className="text-sm font-bold text-slate-300 uppercase tracking-wider mb-4 flex items-center gap-2">
            <Layers className="w-4 h-4" /> Library Distribution
          </h4>
          <div className="space-y-4">
            {libraryDistribution.slice(0, 5).map((lib) => (
              <div key={lib.name} className="group">
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-300 font-medium">{lib.name}</span>
                  <span className="text-slate-500">{lib.count} ({Math.round(lib.count / totalPins * 100)}%)</span>
                </div>
                <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                  <div className={`h-full ${getProgressBarColor(lib.name)}`} style={{ width: `${(lib.count / totalPins * 100)}%` }}></div>
                </div>
              </div>
            ))}
            {libraryDistribution.length === 0 && <p className="text-slate-600 text-xs italic">No data yet</p>}
          </div>
        </div>
      </div>

      {/* --- EXISTING LISTS --- */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">

        {/* Left Column: Most Frequent */}
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-xl font-bold text-white flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-plex-orange" />
              Most Frequent Collections
            </h3>
          </div>

          <div className="bg-slate-900/30 border border-slate-800 rounded-2xl p-4 md:p-6 space-y-6 max-h-[600px] overflow-y-auto scrollbar-thin">
            {collectionStats.length === 0 ? (
              <div className="h-64 flex flex-col items-center justify-center text-slate-600">
                <BarChart3 className="w-12 h-12 mb-2 opacity-20" />
                <p>Not enough data to generate charts</p>
              </div>
            ) : (
              collectionStats.slice(0, 15).map((item, idx) => {
                const max = collectionStats[0].count;
                const percentage = (item.count / max) * 100;

                return (
                  <div key={idx} className="group">
                    <div className="flex justify-between items-end mb-2">
                      <div className="min-w-0 pr-4">
                        <div className="font-semibold text-slate-200 truncate">{item.name}</div>
                        <div className="text-xs text-slate-500 font-medium uppercase tracking-wider flex items-center gap-1 mt-0.5">
                          {item.library}
                        </div>
                      </div>
                      <div className="text-xl font-bold text-slate-200 flex-shrink-0">
                        {item.count} <span className="text-xs text-slate-500 font-normal">Pins</span>
                      </div>
                    </div>
                    <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full relative ${getProgressBarColor(item.library)}`}
                        style={{
                          width: `${percentage}%`,
                          transition: 'width 1s cubic-bezier(0.4, 0, 0.2, 1)'
                        }}
                      >
                        <div className="absolute inset-0 bg-white/20 animate-[shimmer_2s_infinite] -skew-x-12" style={{ transform: 'translateX(-100%)' }}></div>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Timeline History */}
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-xl font-bold text-white flex items-center gap-2">
              <History className="w-5 h-5 text-blue-500" />
              Pinned History
            </h3>
          </div>

          <div className="bg-slate-900/30 border border-slate-800 rounded-2xl p-4 md:p-6 h-[600px] overflow-y-auto scrollbar-thin">
            {sessions.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-slate-600">
                <History className="w-12 h-12 mb-2 opacity-20" />
                <p>No history available</p>
              </div>
            ) : (
              <div className="relative pl-2 md:pl-4 space-y-8">
                {/* Vertical Timeline Line */}
                <div className="absolute left-2 md:left-4 top-2 bottom-2 w-px bg-slate-800"></div>

                {sessions.slice(0, 100).map((session) => (
                  <div key={session.id} className="relative pl-6 md:pl-8 group">
                    {/* Timeline Dot */}
                    <div className="absolute left-[5px] md:left-[11px] top-1.5 w-3 h-3 rounded-full bg-slate-800 border-2 border-slate-600 group-hover:border-plex-orange group-hover:bg-plex-orange transition-colors z-10"></div>

                    {/* Date Header */}
                    <div className="text-xs font-mono text-slate-500 mb-1 flex items-center gap-2">
                      {session.timestamp.toLocaleDateString()}
                      <span className="w-1 h-1 rounded-full bg-slate-700"></span>
                      {session.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </div>

                    {/* Content Card */}
                    <div>
                      <div className="text-slate-200 font-medium text-sm mb-2">
                        Pinned <span className="text-white font-bold">{session.collections.length} collections</span> to <span className={getLibraryColor(session.library).split(' ')[0]}>{session.library}</span>
                      </div>

                      <div className="flex flex-wrap gap-2">
                        {session.collections.map((col, cIdx) => (
                          <span
                            key={cIdx}
                            className={`text-xs px-2.5 py-1 rounded-md border flex items-center gap-1.5 ${getLibraryColor(session.library)}`}
                          >
                            {cIdx === 0 && getLibraryIcon(session.library)}
                            {col}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default StatsPage;