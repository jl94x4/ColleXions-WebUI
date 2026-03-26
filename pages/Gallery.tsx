import React, { useEffect, useState, useMemo } from 'react';
import { api } from '../services/api';
import { PlexCollection } from '../types';
import {
    Image as ImageIcon,
    Pin,
    PinOff,
    Search,
    RefreshCw,
    Library,
    CheckCircle2,
    Info,
    ChevronDown,
    Check,
    LayoutGrid
} from 'lucide-react';

const Gallery: React.FC = () => {
    const [collections, setCollections] = useState<PlexCollection[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedLibrary, setSelectedLibrary] = useState<string>('All');
    const [showPinnedOnly, setShowPinnedOnly] = useState(false);
    const [gridSize, setGridSize] = useState<'sm' | 'md' | 'lg'>('md');
    const [pinningId, setPinningId] = useState<string | null>(null);
    const [isLibraryOpen, setIsLibraryOpen] = useState(false);

    // Initial load from localStorage
    useEffect(() => {
        const savedState = localStorage.getItem('collexions_gallery_state');
        if (savedState) {
            try {
                const state = JSON.parse(savedState);
                if (state.searchQuery !== undefined) setSearchQuery(state.searchQuery);
                if (state.selectedLibrary !== undefined) setSelectedLibrary(state.selectedLibrary);
                if (state.showPinnedOnly !== undefined) setShowPinnedOnly(state.showPinnedOnly);
                if (state.gridSize !== undefined) setGridSize(state.gridSize);
            } catch (e) {
                console.error("Failed to parse saved gallery state", e);
            }
        }
    }, []);

    // Save state to localStorage whenever it changes
    useEffect(() => {
        const stateToSave = {
            searchQuery,
            selectedLibrary,
            showPinnedOnly,
            gridSize
        };
        localStorage.setItem('collexions_gallery_state', JSON.stringify(stateToSave));
    }, [searchQuery, selectedLibrary, showPinnedOnly, gridSize]);

    const libraries = useMemo(() => {
        const libs = ['All', ...new Set(collections.map(c => c.library))];
        return libs.sort();
    }, [collections]);

    useEffect(() => {
        fetchCollections();
    }, []);

    const fetchCollections = async (isManual = false) => {
        setLoading(true);
        try {
            const data = await api.getCollections(isManual);
            setCollections(data);
        } catch (e) {
            console.error("Failed to fetch collections", e);
        } finally {
            setLoading(false);
        }
    };

    const handlePinToggle = async (coll: PlexCollection) => {
        const id = `${coll.library}-${coll.title}`;
        setPinningId(id);

        try {
            if (coll.is_pinned) {
                await api.unpinCollection(coll.title, coll.library);
            } else {
                await api.pinCollection(coll.title, coll.library);
            }
            // Refresh local state
            await fetchCollections();
        } catch (e) {
            alert("Action failed. Check Plex connection.");
        } finally {
            setPinningId(null);
        }
    };

    const filteredCollections = useMemo(() => {
        return collections.filter(c => {
            const matchSearch = c.title.toLowerCase().includes(searchQuery.toLowerCase());
            const matchLib = selectedLibrary === 'All' || c.library === selectedLibrary;
            const matchPinned = !showPinnedOnly || c.is_pinned;
            return matchSearch && matchLib && matchPinned;
        });
    }, [collections, searchQuery, selectedLibrary, showPinnedOnly]);

    if (loading && collections.length === 0) {
        return (
            <div className="flex flex-col h-96 items-center justify-center text-slate-500 animate-pulse">
                <ImageIcon className="w-12 h-12 mb-4 opacity-50" />
                <p>Scanning Plex Libraries...</p>
            </div>
        );
    }

    return (
        <div className="space-y-6 animate-in fade-in duration-500 pb-10">
            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 className="text-2xl md:text-3xl font-bold text-white tracking-tight">Collection Gallery</h2>
                    <p className="text-slate-400 mt-1 flex items-center gap-2 text-sm">
                        <Library className="w-4 h-4" />
                        Explore and manually pin collections to your Home Screen
                    </p>
                </div>
                <button
                    onClick={() => fetchCollections(true)}
                    className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-white transition-colors"
                >
                    <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
                </button>
            </div>

            {/* Filters */}
            <div className="flex flex-col md:flex-row gap-4">
                <div className="flex-1 relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                    <input
                        type="text"
                        placeholder="Search collections..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full bg-slate-900/50 border border-slate-800 rounded-xl py-2.5 pl-10 pr-4 text-white focus:outline-none focus:border-plex-orange transition-colors"
                    />
                </div>

                {/* Custom Library Dropdown */}
                <div className="relative w-full md:w-64">
                    <button
                        onClick={() => setIsLibraryOpen(!isLibraryOpen)}
                        className="w-full bg-slate-900/50 border border-slate-800 rounded-xl py-2.5 pl-4 pr-10 text-white flex items-center justify-between focus:outline-none focus:border-plex-orange transition-all hover:bg-slate-800/50"
                    >
                        <div className="flex items-center gap-2 truncate">
                            <Library className="w-4 h-4 text-slate-500" />
                            <span className="truncate">{selectedLibrary}</span>
                        </div>
                        <ChevronDown className={`w-4 h-4 text-slate-500 transition-transform ${isLibraryOpen ? 'rotate-180' : ''}`} />
                    </button>

                    {isLibraryOpen && (
                        <>
                            <div
                                className="fixed inset-0 z-10"
                                onClick={() => setIsLibraryOpen(false)}
                            />
                            <div className="absolute top-full left-0 right-0 mt-2 bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-2xl z-20 animate-in fade-in slide-in-from-top-2 duration-200">
                                <div className="max-h-60 overflow-y-auto scrollbar-thin">
                                    {libraries.map(lib => (
                                        <button
                                            key={lib}
                                            onClick={() => {
                                                setSelectedLibrary(lib);
                                                setIsLibraryOpen(false);
                                            }}
                                            className={`w-full px-4 py-2.5 text-sm text-left flex items-center justify-between transition-colors hover:bg-slate-800 ${selectedLibrary === lib ? 'text-plex-orange bg-plex-orange/5' : 'text-slate-300'
                                                }`}
                                        >
                                            {lib}
                                            {selectedLibrary === lib && <Check className="w-4 h-4" />}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </>
                    )}
                </div>

                {/* Pinned Filter Toggle and Grid Size Selector */}
                <div className="flex bg-slate-900/50 border border-slate-800 rounded-xl p-1 gap-1">
                    <button
                        onClick={() => setShowPinnedOnly(!showPinnedOnly)}
                        className={`flex items-center justify-center gap-2 px-4 py-1.5 rounded-lg font-bold transition-all ${showPinnedOnly
                            ? 'bg-plex-orange text-white shadow-lg'
                            : 'text-slate-500 hover:text-slate-300'
                            }`}
                        title="Show Pinned Only"
                    >
                        <Pin className={`w-4 h-4 ${showPinnedOnly ? 'fill-current' : ''}`} />
                        <span className="hidden lg:inline text-xs">Pinned Only</span>
                    </button>
                    <div className="w-px h-8 bg-slate-800 self-center" />
                    <div className="flex gap-1 px-1 items-center">
                        {(['sm', 'md', 'lg'] as const).map((size) => (
                            <button
                                key={size}
                                onClick={() => setGridSize(size)}
                                className={`w-8 h-8 flex items-center justify-center rounded-lg transition-all ${gridSize === size
                                    ? 'bg-slate-700 text-white'
                                    : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800'
                                    }`}
                                title={`Grid Size: ${size === 'sm' ? 'Small' : size === 'md' ? 'Medium' : 'Large'}`}
                            >
                                <LayoutGrid className={size === 'sm' ? 'w-3 h-3' : size === 'md' ? 'w-4 h-4' : 'w-5 h-5'} />
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Grid */}
            <div className={`grid gap-6 ${gridSize === 'sm'
                ? 'grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8'
                : gridSize === 'md'
                    ? 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5'
                    : 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4'
                }`}>
                {filteredCollections.map((coll, idx) => {
                    const id = `${coll.library}-${coll.title}`;
                    const uniqueKey = `${id}-${idx}`;
                    const isProcessing = pinningId === id;

                    return (
                        <div key={uniqueKey} className={`group relative flex flex-col bg-slate-900/40 border border-slate-800 rounded-2xl overflow-hidden hover:border-slate-600 transition-all hover:shadow-2xl hover:shadow-black/50 ${gridSize === 'sm' ? 'rounded-xl' : 'rounded-2xl'}`}>
                            {/* Poster */}
                            <div className="aspect-[2/3] bg-slate-800 relative overflow-hidden">
                                {coll.thumb ? (
                                    <img
                                        src={`/api/proxy/image?thumb=${encodeURIComponent(coll.thumb)}`}
                                        alt={coll.title}
                                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                                        loading="lazy"
                                        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                                    />
                                ) : (
                                    <div className="w-full h-full flex items-center justify-center bg-slate-800 text-slate-600">
                                        <ImageIcon className="w-10 h-10 opacity-30" />
                                    </div>
                                )}
                                {coll.is_pinned && (
                                    <div className={`absolute top-2 right-2 bg-plex-orange text-white font-bold rounded flex items-center gap-1 shadow-lg ring-1 ring-white/20 ${gridSize === 'sm' ? 'px-1 py-0.5 text-[8px]' : 'px-2 py-1 text-[10px]'}`}>
                                        <Pin className={`${gridSize === 'sm' ? 'w-2 h-2' : 'w-3 h-3'} fill-current`} /> PINNED
                                    </div>
                                )}
                                {coll.has_label && !coll.is_pinned && (
                                    <div className={`absolute top-2 right-2 bg-blue-600 text-white font-bold rounded flex items-center gap-1 shadow-lg ring-1 ring-white/20 ${gridSize === 'sm' ? 'px-1 py-0.5 text-[8px]' : 'px-2 py-1 text-[10px]'}`}>
                                        <CheckCircle2 className={`${gridSize === 'sm' ? 'w-2 h-2' : 'w-3 h-3'}`} /> TRACKED
                                    </div>
                                )}
                            </div>

                            {/* Info */}
                            <div className={`${gridSize === 'sm' ? 'p-2' : 'p-4'} flex-1 flex flex-col justify-between`}>
                                <div className={gridSize === 'sm' ? 'mb-1' : 'mb-3'}>
                                    <h3 className={`font-bold text-white line-clamp-2 leading-snug group-hover:text-plex-orange transition-colors ${gridSize === 'sm' ? 'text-[10px]' : 'text-sm'}`}>
                                        {coll.title}
                                    </h3>
                                    {gridSize !== 'sm' && (
                                        <p className="text-[10px] text-slate-500 font-medium uppercase mt-1">
                                            {coll.library}
                                        </p>
                                    )}
                                </div>

                                <button
                                    onClick={() => handlePinToggle(coll)}
                                    disabled={isProcessing}
                                    className={`w-full rounded-lg font-bold flex items-center justify-center gap-2 transition-all border ${gridSize === 'sm' ? 'py-1 text-[10px]' : 'py-2 text-xs'} ${coll.is_pinned
                                        ? 'bg-red-500/10 text-red-400 border-red-500/30 hover:bg-red-500/20'
                                        : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20'
                                        } disabled:opacity-50`}
                                >
                                    {isProcessing ? (
                                        <RefreshCw className={`${gridSize === 'sm' ? 'w-2 h-2' : 'w-3 h-3'} animate-spin`} />
                                    ) : coll.is_pinned ? (
                                        <>
                                            <PinOff className={gridSize === 'sm' ? 'w-2 h-2' : 'w-3 h-3'} />
                                            <span className={gridSize === 'sm' ? 'hidden' : ''}>Unpin from Home</span>
                                            {gridSize === 'sm' && <span>Unpin</span>}
                                        </>
                                    ) : (
                                        <>
                                            <Pin className={gridSize === 'sm' ? 'w-2 h-2' : 'w-3 h-3'} />
                                            <span className={gridSize === 'sm' ? 'hidden' : ''}>Pin to Home</span>
                                            {gridSize === 'sm' && <span>Pin</span>}
                                        </>
                                    )}
                                </button>
                            </div>
                        </div>
                    );
                })}
            </div>

            {filteredCollections.length === 0 && (
                <div className="h-64 flex flex-col items-center justify-center text-slate-600 border-2 border-dashed border-slate-800 rounded-3xl">
                    <Search className="w-12 h-12 mb-2 opacity-10" />
                    <p>No collections match your filters</p>
                </div>
            )}

            {/* Legend / Info Footer */}
            <div className="p-4 bg-slate-900/20 border border-slate-800 rounded-2xl flex items-start gap-3 text-xs text-slate-500">
                <Info className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
                <div className="space-y-1">
                    <p><b className="text-slate-300">Pinned</b>: Visible on your Plex Home Screen and Shared Home Screens.</p>
                    <p><b className="text-slate-300">Tracked</b>: Has the script label but currently hidden from Home.</p>
                    <p><b className="text-slate-300">Manual Pinning</b>: Overrides schedule until the next run unpins it (unless excluded).</p>
                </div>
            </div>
        </div>
    );
};

export default Gallery;
