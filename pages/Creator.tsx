import React, { useEffect, useState } from 'react';
import { Card } from '../components/ui/Card';
import { Plus, Search, ListMusic, Globe, Loader2, List, Trash2, Sparkles, Filter, ExternalLink, Compass, Clock } from 'lucide-react';
import { api } from '../services/api';
import { CustomSelect } from '../components/ui/Inputs';
import { AppConfig } from '../types';

const Creator: React.FC = () => {
    const [activeSubTab, setActiveSubTab] = useState<'trending' | 'discover' | 'search' | 'import' | 'manual'>('trending');
    const [config, setConfig] = useState<AppConfig | null>(null);
    // Trending State
    const [trendingPresets, setTrendingPresets] = useState<any[]>([]);
    const [viewingPreset, setViewingPreset] = useState<any | null>(null);
    const [loading, setLoading] = useState(true);
    const [toast, setToast] = useState<{ message: string, type: 'success' | 'error' | 'info' } | null>(null);

    const showToast = (message: string, type: 'success' | 'error' | 'info' = 'info') => {
        setToast({ message, type });
        setTimeout(() => setToast(null), 5000);
    };

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        setLoading(true);
        try {
            const [cfg, presets] = await Promise.all([
                api.getConfig(),
                api.getTrending()
            ]);
            setConfig(cfg);
            setTrendingPresets(presets);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    // Shared State
    const [targetLibrary, setTargetLibrary] = useState<string>('');
    const [collectionTitle, setCollectionTitle] = useState('');
    const [sortOrder, setSortOrder] = useState<'custom' | 'random' | 'release'>('custom');
    const [autoSync, setAutoSync] = useState(true);
    const [creating, setCreating] = useState(false);

    const handleCreatePreset = async (preset: any) => {
        if (!targetLibrary) {
            showToast("Please select a target library first!", "error");
            return;
        }
        setCreating(true);
        try {
            // Source ID for trending is the preset ID
            const res = await api.createFromExternal(
                targetLibrary,
                preset.name,
                preset.items,
                sortOrder,
                autoSync,
                `tmdb_trending_${preset.type}`,
                preset.id
            );

            setSelectionPool([]);
            if (res.success) {
                showToast(`Successfully created '${preset.name}'! Matched ${res.matched}/${res.total} items.`, "success");
                setViewingPreset(null);
                setActiveSubTab('trending');
            } else showToast("Error: " + res.error, "error");
        } catch (e) {
            showToast("Failed to create collection.", "error");
        } finally {
            setCreating(false);
        }
    };

    // Manual Build State
    const [localSearchQuery, setLocalSearchQuery] = useState('');
    const [localSearchYear, setLocalSearchYear] = useState('');
    const [localSearchGenre, setLocalSearchGenre] = useState('');
    const [localResults, setLocalResults] = useState<any[]>([]);
    const [searching, setSearching] = useState(false);

    // Unified Selection Pool (The "Cart")
    const [selectionPool, setSelectionPool] = useState<any[]>([]);

    // Import State
    const [importUrl, setImportUrl] = useState('');
    const [importedItems, setImportedItems] = useState<any[]>([]);
    const [importing, setImporting] = useState(false);

    // Global Search State
    const [externalQuery, setExternalQuery] = useState('');
    const [externalResults, setExternalResults] = useState<any[]>([]);
    const [searchingExternal, setSearchingExternal] = useState(false);

    // Discover State
    const [discoverType, setDiscoverType] = useState<'movie' | 'tv'>('movie');
    const [discoverGenres, setDiscoverGenres] = useState<any[]>([]);
    const [selectedGenre, setSelectedGenre] = useState('');
    const [discoverYear, setDiscoverYear] = useState('');
    const [discoverRating, setDiscoverRating] = useState('');
    const [discoverVoteCount, setDiscoverVoteCount] = useState('');
    const [discoverLanguage, setDiscoverLanguage] = useState('');
    const [discoverNetwork, setDiscoverNetwork] = useState('');
    const [discoverCompany, setDiscoverCompany] = useState('');
    const [discoverKeywords, setDiscoverKeywords] = useState('');
    const [discoverYearMode, setDiscoverYearMode] = useState<'exact' | 'before' | 'after'>('exact');
    const [discoverSort, setDiscoverSort] = useState('popularity.desc');
    const [discoverResults, setDiscoverResults] = useState<any[]>([]);
    const [discovering, setDiscovering] = useState(false);
    const [showPoolDetails, setShowPoolDetails] = useState(false);

    useEffect(() => {
        if (activeSubTab === 'discover') {
            api.getTmdbGenres(discoverType).then(setDiscoverGenres).catch(console.error);
        }
    }, [discoverType, activeSubTab]);

    const handleDiscover = async () => {
        setDiscovering(true);
        try {
            const params = {
                type: discoverType,
                with_genres: selectedGenre,
                year: discoverYear,
                year_mode: discoverYearMode,
                with_keywords: discoverKeywords,
                'vote_average.gte': discoverRating,
                'vote_count.gte': discoverVoteCount,
                with_original_language: discoverLanguage,
                with_networks: discoverType === 'tv' ? discoverNetwork : undefined,
                with_companies: discoverType === 'movie' ? discoverCompany : undefined,
                sort_by: discoverSort
            };
            const results = await api.discoverTmdb(params);
            setDiscoverResults(results);
        } catch (e) {
            showToast("Failed to discover content.", "error");
        } finally {
            setDiscovering(false);
        }
    };


    const handleListImport = async () => {
        if (!importUrl) return;
        setImporting(true);
        try {
            let items = [];
            let sourceType = '';

            if (importUrl.includes('mdblist.com')) {
                items = await api.getMdbList(importUrl);
                sourceType = 'mdblist';
            } else {
                items = await api.getTraktList(importUrl);
                sourceType = 'trakt';
            }

            setImportedItems(items);

            // Extract a reasonable title from the URL
            const urlParts = importUrl.split('/').filter(Boolean);
            let slug = '';

            if (sourceType === 'mdblist') {
                // e.g. https://mdblist.com/lists/mojoard_pk/vintage-british-tv/
                const listIndex = urlParts.indexOf('lists');
                if (listIndex !== -1 && urlParts.length > listIndex + 2) {
                    slug = urlParts[listIndex + 2].replace(/-/g, ' ');
                }
            } else {
                // e.g. https://trakt.tv/users/mojoard_pk/lists/vintage-british-tv
                slug = urlParts[urlParts.length - 1].replace(/-/g, ' ');
            }

            if (slug && !collectionTitle) {
                setCollectionTitle(slug.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' '));
            }
        } catch (e) {
            showToast("Failed to fetch list. Check URL or API keys.", "error");
        } finally {
            setImporting(false);
        }
    };

    const handleExternalSearch = async () => {
        if (!externalQuery) return;
        setSearchingExternal(true);
        try {
            const results = await api.searchExternal(externalQuery, 'movie');
            setExternalResults(results);
        } catch (e) {
            console.error(e);
        } finally {
            setSearchingExternal(false);
        }
    };

    const handleLocalSearch = async () => {
        if (!targetLibrary) return;
        setSearching(true);
        try {
            const res = await api.searchLibrary(targetLibrary, localSearchQuery, localSearchGenre, localSearchYear);
            setLocalResults(res);
        } catch (e) {
            showToast("Failed to search library.", "error");
        } finally {
            setSearching(false);
        }
    };

    const toggleSelection = (item: any) => {
        setSelectionPool(prev => {
            const exists = prev.find(i => (i.id || i.guid) === (item.id || item.guid));
            if (exists) {
                return prev.filter(i => (i.id || i.guid) !== (item.id || i.guid));
            }
            return [...prev, item];
        });
    };

    const handleCreate = async () => {
        if (!targetLibrary || !collectionTitle || selectionPool.length === 0) return;
        setCreating(true);
        try {
            // Check if items are from library (ratingKey) or external (id)
            const hasExternal = selectionPool.some(i => i.id && !i.ratingKey);

            let res;
            if (hasExternal) {
                // If there are external items, we use the external creation logic
                res = await api.createFromExternal(
                    targetLibrary,
                    collectionTitle,
                    selectionPool,
                    sortOrder,
                    autoSync,
                    'manual_custom',
                    'custom_selection'
                );
            } else {
                // All items are local library keys
                const keys = selectionPool.map(i => i.ratingKey);
                res = await api.createCollection(targetLibrary, collectionTitle, keys, sortOrder);
            }

            if (res.success) {
                showToast("Collection created!", "success");
                setSelectionPool([]);
                setCollectionTitle('');
                setLocalSearchQuery('');
                setLocalResults([]);
                setDiscoverResults([]);
                setActiveSubTab('trending');
            } else showToast("Error: " + res.error, "error");
        } catch (e) {
            showToast("Failed to create collection.", "error");
        } finally {
            setCreating(false);
        }
    };


    const handleCreateFromExternal = async () => {
        if (!targetLibrary || !collectionTitle) return;
        setCreating(true);
        try {
            const isDiscover = activeSubTab === 'discover';
            const isMdbList = importUrl.includes('mdblist.com');
            const sourceType = activeSubTab === 'import' ? (isMdbList ? 'mdblist' : 'trakt_list') :
                (isDiscover ? 'tmdb_discover' : 'trakt_trending_movie');
            const sourceId = activeSubTab === 'import' ? importUrl :
                (isDiscover ? JSON.stringify({
                    type: discoverType,
                    with_genres: selectedGenre,
                    primary_release_year: discoverType === 'movie' ? discoverYear : undefined,
                    first_air_date_year: discoverType === 'tv' ? discoverYear : undefined,
                    'vote_average.gte': discoverRating,
                    'vote_count.gte': discoverVoteCount,
                    with_original_language: discoverLanguage,
                    with_networks: discoverType === 'tv' ? discoverNetwork : undefined,
                    with_companies: discoverType === 'movie' ? discoverCompany : undefined,
                    sort_by: discoverSort
                }) : externalQuery);

            const itemsToUse = isDiscover ? discoverResults : importedItems;

            const res = await api.createFromExternal(
                targetLibrary,
                collectionTitle,
                itemsToUse,
                sortOrder,
                autoSync,
                sourceType,
                sourceId
            );
            if (res.success) {
                showToast(`Success! Matched ${res.matched}/${res.total} items.`, "success");
                // Clear state
                setImportedItems([]);
                setCollectionTitle('');
                setImportUrl('');
                setExternalQuery('');
                setExternalResults([]);
                setDiscoverResults([]);
                setActiveSubTab('trending');
            } else showToast("Error: " + res.error, "error");
        } catch (e) {
            showToast("Failed to create collection.", "error");
        } finally {
            setCreating(false);
        }
    };

    if (loading) {
        return (
            <div className="flex h-96 items-center justify-center text-slate-400 flex-col gap-4">
                <Loader2 className="w-8 h-8 border-t-plex-orange animate-spin" />
                <p>Connecting to external services... This may take a while on the first run.</p>
            </div>
        );
    }

    const hasKeys = config?.tmdb_api_key || config?.trakt_client_id;

    return (
        <div className="space-y-8 pb-20 animate-in fade-in duration-500">
            {/* Custom Toast Notification */}
            {toast && (
                <div className={`fixed bottom-8 right-8 z-[110] flex items-center gap-3 px-6 py-4 rounded-2xl shadow-2xl border animate-in slide-in-from-right-10 duration-500 ${toast.type === 'success' ? 'bg-emerald-950/90 border-emerald-500/50 text-emerald-100' :
                    toast.type === 'error' ? 'bg-rose-950/90 border-rose-500/50 text-rose-100' :
                        'bg-slate-900/90 border-slate-700/50 text-slate-100'
                    }`}>
                    {toast.type === 'success' && <div className="bg-emerald-500 rounded-full p-1"><Plus className="w-4 h-4 text-emerald-950 rotate-0" /></div>}
                    {toast.type === 'error' && <div className="bg-rose-500 rounded-full p-1"><Plus className="w-4 h-4 text-rose-950 rotate-45" /></div>}
                    <span className="font-bold">{toast.message}</span>
                    <button onClick={() => setToast(null)} className="ml-4 text-white/50 hover:text-white transition-colors">
                        <Plus className="w-4 h-4 rotate-45" />
                    </button>
                </div>
            )}
            {/* Modal for viewing all items in a preset */}
            {viewingPreset && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-in fade-in duration-300">
                    <div className="bg-slate-900 border border-slate-800 w-full max-w-4xl max-h-[80vh] rounded-3xl overflow-hidden shadow-2xl flex flex-col scale-in-center">
                        <div className="p-6 border-b border-slate-800 flex items-center justify-between bg-slate-900/50">
                            <div>
                                <h2 className="text-2xl font-bold text-white">{viewingPreset.name}</h2>
                                <p className="text-slate-400">{viewingPreset.items.length} items to match</p>
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => handleCreatePreset(viewingPreset)}
                                    disabled={creating}
                                    className="bg-plex-orange hover:bg-plex-orange/80 disabled:opacity-50 text-white px-6 py-2 rounded-xl font-bold transition-all shadow-lg flex items-center gap-2"
                                >
                                    {creating ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <Plus className="w-5 h-5" />}
                                    Create Collection
                                </button>
                                <button
                                    onClick={() => setViewingPreset(null)}
                                    className="p-2 hover:bg-slate-800 rounded-xl text-slate-400 hover:text-white transition-all"
                                >
                                    <Plus className="w-6 h-6 rotate-45" />
                                </button>
                            </div>
                        </div>
                        <div className="flex-1 overflow-y-auto p-6">
                            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                                {viewingPreset.items.map((itm: any, idx: number) => (
                                    <div key={idx} className="space-y-2 group">
                                        <div className="aspect-[2/3] bg-slate-800 rounded-xl overflow-hidden ring-1 ring-slate-700/50 group-hover:ring-plex-orange/50 transition-all">
                                            {itm.poster ? (
                                                <img src={itm.poster} alt="" className="w-full h-full object-cover" />
                                            ) : (
                                                <div className="w-full h-full flex items-center justify-center text-slate-600">
                                                    <Globe className="w-8 h-8 opacity-20" />
                                                </div>
                                            )}
                                        </div>
                                        <p className="text-xs font-bold text-slate-200 truncate px-1">{itm.title}</p>
                                        <p className="text-[10px] text-slate-500 px-1">{itm.year || 'Unknown'}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                        <div className="p-6 border-t border-slate-800 bg-slate-900/50 flex justify-end gap-3">
                            <button
                                onClick={() => setViewingPreset(null)}
                                className="px-6 py-2 rounded-xl font-bold text-slate-300 hover:bg-slate-800 transition-colors"
                            >
                                Close
                            </button>
                            <button
                                onClick={() => {
                                    handleCreatePreset(viewingPreset);
                                    setViewingPreset(null);
                                }}
                                disabled={creating || !targetLibrary}
                                className="bg-plex-orange hover:bg-orange-600 text-white px-8 py-2 rounded-xl font-bold flex items-center gap-2 shadow-lg disabled:opacity-50"
                            >
                                <Sparkles className="w-4 h-4" />
                                Create Collection
                            </button>
                        </div>
                    </div>
                </div>
            )}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 className="text-2xl md:text-3xl font-bold text-white tracking-tight">Collection Creator</h2>
                    <p className="text-slate-400 mt-1 flex items-center gap-2 text-sm md:text-base">
                        <Plus className="w-5 h-5 text-plex-orange" />
                        Create and sync collections from external sources or your library
                    </p>
                </div>
            </div>

            {/* Global Creation Settings */}
            <section className="bg-slate-900/60 border border-slate-800/60 p-6 rounded-2xl flex flex-col xl:flex-row items-center justify-between gap-6 shadow-xl sticky top-0 z-40 backdrop-blur-md">
                <div className="flex flex-wrap items-center gap-6 w-full xl:w-auto">
                    <div className="flex items-center gap-4">
                        <div className="bg-plex-orange/20 p-3 rounded-xl text-plex-orange">
                            <ListMusic className="w-6 h-6" />
                        </div>
                        <div>
                            <h3 className="text-lg font-bold text-white whitespace-nowrap">Target Library</h3>
                            <p className="text-sm text-slate-400">Creation destination</p>
                        </div>
                    </div>
                    <CustomSelect
                        label="Target Library"
                        className="w-full md:w-56"
                        value={targetLibrary}
                        options={config?.library_names.map(lib => ({ value: lib, label: lib })) || []}
                        onChange={setTargetLibrary}
                        placeholder="Select a library..."
                    />

                </div>

                <div className="flex flex-wrap items-center gap-6 w-full xl:w-auto xl:border-l xl:border-slate-800 xl:pl-6">
                    <div className="flex items-center gap-4">
                        <div className="bg-blue-500/20 p-3 rounded-xl text-blue-400">
                            <Sparkles className="w-6 h-6" />
                        </div>
                        <div>
                            <h3 className="text-lg font-bold text-white whitespace-nowrap">Sort Order</h3>
                            <p className="text-sm text-slate-400">Plex collection sorting</p>
                        </div>
                    </div>
                    <CustomSelect
                        label="Sort Order"
                        className="w-full md:w-48"
                        value={sortOrder}
                        options={[
                            { value: 'custom', label: 'Manual (Default)' },
                            { value: 'random', label: 'Random 🎲' },
                            { value: 'release', label: 'Release Date 📅' }
                        ]}
                        onChange={setSortOrder}
                    />

                </div>

                <div className="flex flex-wrap items-center gap-6 w-full xl:w-auto xl:border-l xl:border-slate-800 xl:pl-6">
                    <div className="flex items-center gap-4">
                        <div className="bg-emerald-500/20 p-3 rounded-xl text-emerald-400">
                            <Clock className="w-6 h-6" />
                        </div>
                        <div>
                            <h3 className="text-lg font-bold text-white whitespace-nowrap">Auto-Sync</h3>
                            <p className="text-sm text-slate-400">Sync every 6 hours</p>
                        </div>
                    </div>
                    <button
                        onClick={() => setAutoSync(!autoSync)}
                        className={`px-6 py-2 rounded-xl border font-bold transition-all ${autoSync ? 'bg-emerald-600 border-emerald-500 text-white' : 'bg-slate-950/50 border-slate-700/60 text-slate-400'}`}
                    >
                        {autoSync ? 'Enabled' : 'Disabled'}
                    </button>
                </div>
            </section>

            <div className="flex border-b border-slate-800/60 overflow-x-auto no-scrollbar -mx-4 px-4 md:mx-0 md:px-0">
                {[
                    { id: 'trending', label: 'Trending', icon: <Globe className="w-4 h-4" /> },
                    { id: 'discover', label: 'Discover', icon: <Compass className="w-4 h-4" /> },
                    { id: 'search', label: 'Global Search', icon: <Search className="w-4 h-4" /> },
                    { id: 'import', label: 'Import List', icon: <ExternalLink className="w-4 h-4" /> },
                    { id: 'manual', label: 'Manual Build', icon: <ListMusic className="w-4 h-4" /> }
                ].map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveSubTab(tab.id as any)}
                        className={`px-6 py-4 font-medium capitalize transition-all border-b-2 whitespace-nowrap text-sm flex items-center gap-2 ${activeSubTab === tab.id ? 'text-plex-orange border-plex-orange bg-slate-900/20' : 'text-slate-400 border-transparent hover:text-slate-200 hover:bg-slate-900/10'
                            }`}
                    >
                        {tab.icon}
                        {tab.label}
                    </button>
                ))}
            </div>

            <div className="grid gap-6">
                {activeSubTab === 'trending' && (
                    <div className="space-y-6 animate-in slide-in-from-bottom-2 duration-300">
                        {!hasKeys ? (
                            <Card title="Global Trending Integration">
                                <div className="bg-slate-900/40 border border-slate-800/60 p-8 rounded-2xl text-center space-y-4">
                                    <Globe className="w-12 h-12 text-slate-700 mx-auto" />
                                    <div className="max-w-md mx-auto">
                                        <h3 className="text-lg font-bold text-white">External Integration Required</h3>
                                        <p className="text-slate-400 text-sm mt-2">Add your API keys in Settings to see what's trending.</p>
                                    </div>
                                </div>
                            </Card>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                {trendingPresets.map(preset => (
                                    <div key={preset.id} className="bg-slate-900/40 border border-slate-800/60 p-6 rounded-2xl flex flex-col justify-between hover:border-plex-orange/30 transition-all group shadow-lg">
                                        <div>
                                            <div className="flex items-center justify-between mb-4">
                                                <span className="text-[10px] font-bold uppercase tracking-widest text-plex-orange bg-plex-orange/10 px-2 py-1 rounded-md border border-plex-orange/20">
                                                    {preset.source}
                                                </span>
                                                <span className="text-xs text-slate-500 font-medium">{preset.items.length} titles</span>
                                            </div>
                                            <h3 className="text-xl font-bold text-white group-hover:text-plex-orange transition-colors">{preset.name}</h3>
                                            <p className="text-slate-400 text-sm mt-2 leading-relaxed">{preset.description}</p>

                                            <div
                                                className="mt-6 flex flex-wrap gap-3 cursor-pointer p-2 -m-2 rounded-xl hover:bg-white/5 transition-colors"
                                                onClick={() => setViewingPreset(preset)}
                                            >
                                                {preset.items.slice(0, 5).map((itm: any, idx: number) => (
                                                    <div key={idx} className="w-12 h-18 bg-slate-800 rounded-lg overflow-hidden ring-1 ring-slate-700 shadow-sm transition-transform group-hover:scale-105">
                                                        {itm.poster && <img src={itm.poster} alt="" className="w-full h-full object-cover" />}
                                                    </div>
                                                ))}
                                                {preset.items.length > 5 && (
                                                    <div className="w-12 h-18 bg-slate-800/50 rounded-lg flex items-center justify-center text-[10px] font-bold text-slate-500 border border-slate-700/50 transition-transform group-hover:scale-105">
                                                        +{preset.items.length - 5}
                                                    </div>
                                                )}
                                            </div>
                                        </div>

                                        <button
                                            onClick={() => handleCreatePreset(preset)}
                                            disabled={creating || !targetLibrary}
                                            className="mt-8 w-full bg-slate-800 hover:bg-plex-orange text-white py-3 rounded-xl font-bold flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:hover:bg-slate-800 shadow-md transform group-hover:-translate-y-1"
                                        >
                                            <Sparkles className="w-4 h-4" />
                                            Create Collection
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {activeSubTab === 'discover' && (
                    <div className="space-y-6 animate-in slide-in-from-bottom-2 duration-300 relative z-30">
                        <Card title="Discover Curated Collections">
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                <div className="relative z-50">
                                    <CustomSelect
                                        label="Media Type"
                                        value={discoverType}
                                        onChange={v => setDiscoverType(v as 'movie' | 'tv')}
                                        options={[
                                            { value: 'movie', label: 'Movies' },
                                            { value: 'tv', label: 'TV Shows' }
                                        ]}
                                    />

                                </div>

                                <div className="relative z-40">
                                    <CustomSelect
                                        label="Genre"
                                        value={selectedGenre}
                                        onChange={setSelectedGenre}
                                        options={[
                                            { value: '', label: 'Any Genre' },
                                            ...discoverGenres.map(g => ({ value: g.id.toString(), label: g.name }))
                                        ]}
                                    />

                                </div>

                                <div className="relative z-30">
                                    <CustomSelect
                                        label="Sort By"
                                        value={discoverSort}
                                        onChange={setDiscoverSort}
                                        options={[
                                            { value: 'popularity.desc', label: 'Most Popular' },
                                            { value: 'vote_average.desc', label: 'Highest Rated' },
                                            { value: 'primary_release_date.desc', label: 'Newest First' },
                                            { value: 'primary_release_date.asc', label: 'Oldest First' }
                                        ]}
                                    />

                                </div>

                                {discoverType === 'tv' ? (
                                    <div className="relative z-20">
                                        <CustomSelect
                                            label="Network"
                                            value={discoverNetwork}
                                            onChange={setDiscoverNetwork}
                                            options={[
                                                { value: '', label: 'Any Network' },
                                                { value: '213', label: 'Netflix' },
                                                { value: '1024', label: 'Amazon' },
                                                { value: '453', label: 'Hulu' },
                                                { value: '2739', label: 'Disney+' },
                                                { value: '2552', label: 'Apple TV+' },
                                                { value: '3353', label: 'Paramount+' },
                                                { value: '318', label: 'Peacock' },
                                                { value: '49', label: 'HBO' },
                                                { value: '67', label: 'Showtime' },
                                                { value: '88', label: 'FX' },
                                                { value: '174', label: 'AMC' },
                                                { value: '3743', label: 'AMC+' },
                                                { value: '71', label: 'The CW' },
                                                { value: '19', label: 'FOX' },
                                                { value: '6', label: 'NBC' },
                                                { value: '2', label: 'ABC' },
                                                { value: '16', label: 'CBS' },
                                                { value: '43', label: 'Nat Geo' },
                                                { value: '64', label: 'Discovery' },
                                                { value: '65', label: 'History' },
                                                { value: '596', label: 'Shudder' },
                                                { value: '351', label: 'Crunchyroll' },
                                                { value: '53', label: 'MTV' },
                                                { value: '56', label: 'Cartoon Network' },
                                                { value: '13', label: 'Nickelodeon' },
                                                { value: '4', label: 'BBC One' },
                                                { value: '21', label: 'BBC Two' },
                                                { value: '270', label: 'ITV' },
                                                { value: '26', label: 'Channel 4' }
                                            ]}
                                        />

                                    </div>
                                ) : (
                                    <div className="relative z-20">
                                        <CustomSelect
                                            label="Studio / Company"
                                            value={discoverCompany}
                                            onChange={setDiscoverCompany}
                                            options={[
                                                { value: '', label: 'Any Studio' },
                                                { value: '420', label: 'Marvel Studios' },
                                                { value: '128066', label: 'DC Studios' },
                                                { value: '3166', label: 'A24' },
                                                { value: '2', label: 'Walt Disney Pictures' },
                                                { value: '174', label: 'Warner Bros. Pictures' },
                                                { value: '33', label: 'Universal Pictures' },
                                                { value: '4', label: 'Paramount' },
                                                { value: '453', label: 'Hulu' },
                                                { value: '24531', label: 'Amazon MGM' },
                                                { value: '2', label: 'Walt Disney' },
                                                { value: '12', label: 'New Line Cinema' },
                                                { value: '5', label: 'Columbia Pictures' },
                                                { value: '1632', label: 'Lionsgate' },
                                                { value: '14', label: 'Miramax' },
                                                { value: '10342', label: 'Studio Ghibli' }
                                            ]}
                                        />

                                    </div>
                                )}

                                <div className="relative z-10">
                                    <CustomSelect
                                        label="Language"
                                        value={discoverLanguage}
                                        onChange={setDiscoverLanguage}
                                        options={[
                                            { value: '', label: 'Any' },
                                            { value: 'en', label: 'English' },
                                            { value: 'ko', label: 'Korean' },
                                            { value: 'ja', label: 'Japanese' },
                                            { value: 'es', label: 'Spanish' },
                                            { value: 'fr', label: 'French' },
                                            { value: 'hi', label: 'Hindi' }
                                        ]}
                                    />

                                </div>

                                <div className="space-y-1.5">
                                    <label className="block text-sm font-medium text-slate-300">Release Year</label>
                                    <div className="flex gap-2">
                                        <div className="w-24">
                                            <CustomSelect
                                                label=""
                                                value={discoverYearMode}
                                                onChange={v => setDiscoverYearMode(v as any)}
                                                options={[
                                                    { value: 'exact', label: 'Exact' },
                                                    { value: 'before', label: 'Before' },
                                                    { value: 'after', label: 'After' }
                                                ]}
                                            />
                                        </div>
                                        <input
                                            type="number" placeholder="1999"
                                            className="flex-1 bg-slate-950/50 border border-slate-700/60 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:border-plex-orange/50 transition-all placeholder-slate-600"
                                            value={discoverYear} onChange={e => setDiscoverYear(e.target.value)}
                                        />
                                    </div>
                                </div>

                                <div className="space-y-1.5">
                                    <label className="block text-sm font-medium text-slate-300">Keywords / Text</label>
                                    <input
                                        type="text" placeholder="e.g. superhero, mystery"
                                        className="w-full bg-slate-950/50 border border-slate-700/60 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:border-plex-orange/50 transition-all placeholder-slate-600 font-mono"
                                        value={discoverKeywords} onChange={e => setDiscoverKeywords(e.target.value)}
                                    />
                                </div>

                                <div className="space-y-1.5">
                                    <label className="block text-sm font-medium text-slate-300">Min Rating (0-10)</label>
                                    <input
                                        type="number" step="0.1" min="0" max="10" placeholder="e.g. 7.5"
                                        className="w-full bg-slate-950/50 border border-slate-700/60 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:border-plex-orange/50 transition-all placeholder-slate-600"
                                        value={discoverRating} onChange={e => setDiscoverRating(e.target.value)}
                                    />
                                </div>

                                <div className="space-y-1.5">
                                    <label className="block text-sm font-medium text-slate-300">Min Votes</label>
                                    <input
                                        type="number" step="10" min="0" placeholder="e.g. 500"
                                        className="w-full bg-slate-950/50 border border-slate-700/60 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:border-plex-orange/50 transition-all placeholder-slate-600"
                                        value={discoverVoteCount} onChange={e => setDiscoverVoteCount(e.target.value)}
                                    />
                                </div>

                                <div className="md:col-span-2 lg:col-span-3 flex items-end">
                                    <button onClick={handleDiscover} disabled={discovering} className="w-full bg-plex-orange hover:bg-orange-600 text-white px-8 py-3 rounded-xl font-bold disabled:opacity-50 flex items-center justify-center gap-2 transition-transform active:scale-[0.98]">
                                        <Filter className="w-5 h-5" /> Search TMDb
                                    </button>
                                </div>
                            </div>
                        </Card>

                        {discoverResults.length > 0 && (
                            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4 relative -z-10">
                                {discoverResults.map(item => {
                                    const isSelected = !!selectionPool.find(p => p.id === item.id);
                                    return (
                                        <div
                                            key={item.id}
                                            onClick={() => toggleSelection(item)}
                                            className={`group relative aspect-[2/3] rounded-2xl border-2 overflow-hidden cursor-pointer transition-all duration-300 ${isSelected
                                                ? 'border-plex-orange shadow-[0_0_20px_rgba(231,155,23,0.2)]'
                                                : 'border-slate-800 hover:border-slate-700'
                                                }`}
                                        >
                                            <img
                                                src={item.poster}
                                                alt=""
                                                className={`w-full h-full object-cover transition-transform duration-500 group-hover:scale-110 ${isSelected ? 'opacity-60' : ''}`}
                                            />
                                            <div className={`absolute inset-0 flex flex-col justify-end p-3 bg-gradient-to-t from-black/90 via-black/20 to-transparent transition-opacity ${isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}>
                                                <h4 className="text-sm font-bold text-white truncate">{item.title}</h4>
                                                <p className="text-[10px] text-slate-400 font-medium uppercase">{item.year}</p>
                                            </div>
                                            {isSelected && (
                                                <div className="absolute top-2 right-2 bg-plex-orange text-white p-1 rounded-lg shadow-lg">
                                                    <Plus className="w-4 h-4" />
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        )}

                        {discoverResults.length > 0 && (
                            <div className="px-1 space-y-4">
                                <div>
                                    <label className="text-sm text-slate-400 mb-2 block font-medium">Collection Title</label>
                                    <input
                                        type="text"
                                        placeholder="e.g. Best Sci-Fi Movies..."
                                        className="w-full md:w-96 bg-slate-950/50 border border-slate-700/60 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-plex-orange/50 transition-colors"
                                        value={collectionTitle}
                                        onChange={e => setCollectionTitle(e.target.value)}
                                    />
                                    <p className="text-xs text-slate-500 mt-2">Set a Title & Target Library, then click to Create & Auto-Sync.</p>
                                </div>
                                <button
                                    onClick={() => handleCreateFromExternal()}
                                    disabled={creating || !targetLibrary || !collectionTitle}
                                    className="bg-plex-orange hover:bg-orange-600 text-white px-8 py-3 rounded-xl font-bold flex items-center justify-center gap-2 shadow-lg disabled:opacity-50 w-full md:w-auto"
                                >
                                    <Sparkles className="w-5 h-5" />
                                    {creating ? 'Creating...' : 'Create Auto-Syncing Collection'}
                                </button>
                            </div>
                        )}
                    </div>
                )}

                {activeSubTab === 'search' && (
                    <div className="space-y-6 animate-in slide-in-from-bottom-2 duration-300">
                        <Card title="Global Content Search">
                            <div className="flex gap-2">
                                <div className="relative flex-1">
                                    <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-500" />
                                    <input className="w-full bg-slate-950/50 border border-slate-700/60 rounded-lg pl-10 pr-4 py-2 text-sm text-white focus:outline-none focus:border-plex-orange/50" placeholder="Search TMDb..." value={externalQuery} onChange={(e) => setExternalQuery(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleExternalSearch()} />
                                </div>
                                <button onClick={handleExternalSearch} disabled={searchingExternal || !externalQuery} className="bg-slate-800 hover:bg-slate-700 text-white px-6 py-2 rounded-lg border border-slate-700 disabled:opacity-50">Search</button>
                            </div>
                        </Card>
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                            {externalResults.map(item => (
                                <div key={item.id} className="bg-slate-900/40 border border-slate-800/60 rounded-2xl overflow-hidden group hover:border-plex-orange/40 transition-all">
                                    <div className="aspect-[2/3] relative">
                                        {item.poster && <img src={item.poster} alt="" className="w-full h-full object-cover" />}
                                        <button onClick={() => setImportedItems(prev => [...prev, item])} className="absolute top-3 right-3 p-2 bg-slate-900/80 backdrop-blur-md rounded-xl text-white opacity-0 group-hover:opacity-100 transition-all hover:bg-plex-orange"><Plus className="w-5 h-5" /></button>
                                    </div>
                                    <div className="p-4">
                                        <h4 className="font-bold text-slate-100 truncate">{item.title}</h4>
                                        <p className="text-xs text-slate-500 mt-1 uppercase">{item.year} • {item.type}</p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {activeSubTab === 'import' && (
                    <div className="space-y-6 animate-in slide-in-from-bottom-2 duration-300">
                        <Card title="Import from Trakt.tv or MDBList.com">
                            <div className="flex gap-2">
                                <div className="relative flex-1">
                                    <ExternalLink className="absolute left-3 top-2.5 w-4 h-4 text-slate-500" />
                                    <input className="w-full bg-slate-950/50 border border-slate-700/60 rounded-lg pl-10 pr-4 py-2 text-sm text-white focus:outline-none focus:border-plex-orange/50" placeholder="Trakt or MDBList URL..." value={importUrl} onChange={(e) => setImportUrl(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleListImport()} />
                                </div>
                                <button onClick={handleListImport} disabled={importing || !importUrl} className="bg-plex-orange hover:bg-orange-600 text-white px-6 py-2 rounded-lg font-bold disabled:opacity-50">Fetch</button>
                            </div>
                        </Card>
                        {importedItems.length > 0 && (
                            <Card
                                title={`Import Preview (${importedItems.length} items)`}
                                actions={
                                    <button
                                        onClick={() => setImportedItems([])}
                                        className="p-1.5 hover:bg-slate-800 rounded-lg text-slate-500 hover:text-white transition-all"
                                        title="Clear Import"
                                    >
                                        <Plus className="w-5 h-5 rotate-45" />
                                    </button>
                                }
                            >
                                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 max-h-96 overflow-y-auto">
                                    {importedItems.map((item, idx) => (
                                        <div key={idx} className="p-3 bg-slate-950/30 border border-slate-800 rounded-xl flex items-center justify-between group">
                                            <div className="min-w-0"><h4 className="text-sm font-bold text-slate-200 truncate">{item.title}</h4><p className="text-xs text-slate-500">{item.year} • {item.type}</p></div>
                                            <button onClick={() => setImportedItems(prev => prev.filter((_, i) => i !== idx))} className="text-slate-600 hover:text-red-400 opacity-0 group-hover:opacity-100"><Plus className="w-4 h-4 rotate-45" /></button>
                                        </div>
                                    ))}
                                </div>
                            </Card>
                        )}
                    </div>
                )}

                {activeSubTab === 'manual' && (
                    <div className="space-y-6 animate-in slide-in-from-bottom-2 duration-300">
                        <Card title="1. Search Library Items">
                            <div className="flex flex-col gap-4">
                                <div className="flex gap-2">
                                    <div className="relative flex-1">
                                        <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-500" />
                                        <input
                                            className="w-full bg-slate-950/50 border border-slate-700/60 rounded-lg pl-10 pr-4 py-2 text-sm text-white focus:outline-none focus:border-plex-orange/50"
                                            placeholder="Search title..."
                                            value={localSearchQuery}
                                            onChange={(e) => setLocalSearchQuery(e.target.value)}
                                            onKeyDown={(e) => e.key === 'Enter' && handleLocalSearch()}
                                        />
                                    </div>
                                    <button
                                        onClick={handleLocalSearch}
                                        disabled={searching || !targetLibrary || (!localSearchQuery && !localSearchYear && !localSearchGenre)}
                                        className="bg-slate-800 hover:bg-slate-700 text-white px-6 py-2 rounded-lg font-bold disabled:opacity-50 transition-all border border-slate-700"
                                    >
                                        {searching ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Search'}
                                    </button>
                                </div>

                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-1.5">
                                        <label className="text-xs text-slate-500 font-medium ml-1">Year</label>
                                        <input
                                            type="number"
                                            placeholder="e.g. 2024"
                                            className="w-full bg-slate-950/50 border border-slate-700/60 rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:border-plex-orange/50"
                                            value={localSearchYear}
                                            onChange={(e) => setLocalSearchYear(e.target.value)}
                                        />
                                    </div>
                                    <div className="space-y-1.5">
                                        <label className="text-xs text-slate-500 font-medium ml-1">Genre</label>
                                        <input
                                            placeholder="e.g. Action"
                                            className="w-full bg-slate-950/50 border border-slate-700/60 rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:border-plex-orange/50"
                                            value={localSearchGenre}
                                            onChange={(e) => setLocalSearchGenre(e.target.value)}
                                        />
                                    </div>
                                </div>
                            </div>
                        </Card>

                        {localResults.length > 0 && (
                            <Card
                                title="2. Pick Items to Add"
                                actions={
                                    <div className="flex gap-2">
                                        <button
                                            onClick={() => {
                                                const toAdd = localResults.filter(r => !selectionPool.find(p => p.ratingKey === r.ratingKey));
                                                setSelectionPool(prev => [...prev, ...toAdd]);
                                            }}
                                            className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 px-3 py-1.5 rounded-lg border border-slate-700 transition-all font-medium"
                                        >
                                            Select All
                                        </button>
                                        <button
                                            onClick={() => {
                                                const resultKeys = localResults.map(r => r.ratingKey);
                                                setSelectionPool(prev => prev.filter(p => !resultKeys.includes(p.ratingKey)));
                                            }}
                                            className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 px-3 py-1.5 rounded-lg border border-slate-700 transition-all font-medium"
                                        >
                                            Clear Results
                                        </button>
                                    </div>

                                }
                            >
                                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                                    {localResults.map(item => {
                                        const isSelected = !!selectionPool.find(p => p.ratingKey === item.ratingKey);
                                        return (
                                            <div
                                                key={item.ratingKey}
                                                onClick={() => toggleSelection(item)}
                                                className={`group relative aspect-[2/3] rounded-2xl border-2 overflow-hidden cursor-pointer transition-all duration-300 ${isSelected
                                                    ? 'border-plex-orange shadow-[0_0_20px_rgba(231,155,23,0.2)]'
                                                    : 'border-slate-800 hover:border-slate-700'
                                                    }`}
                                            >
                                                {item.thumb ? (
                                                    <img
                                                        src={`/api/proxy/image?thumb=${encodeURIComponent(item.thumb)}`}
                                                        alt=""
                                                        className={`w-full h-full object-cover transition-transform duration-500 group-hover:scale-110 ${isSelected ? 'opacity-60' : ''}`}
                                                    />
                                                ) : (
                                                    <div className="w-full h-full bg-slate-900 flex items-center justify-center">
                                                        <Search className="w-8 h-8 text-slate-800" />
                                                    </div>
                                                )}

                                                <div className={`absolute inset-0 flex flex-col justify-end p-3 bg-gradient-to-t from-black/90 via-black/20 to-transparent transition-opacity ${isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}>
                                                    <h4 className="text-sm font-bold text-white truncate">{item.title}</h4>
                                                    <p className="text-[10px] text-slate-400 font-medium uppercase">{item.year} • {item.type}</p>
                                                </div>

                                                {isSelected && (
                                                    <div className="absolute top-2 right-2 bg-plex-orange text-white p-1 rounded-lg shadow-lg">
                                                        <Plus className="w-4 h-4" />
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    })}

                                </div>
                            </Card>
                        )}
                    </div>
                )}
            </div>

            {showPoolDetails && selectionPool.length > 0 && (
                <div className="fixed inset-x-0 bottom-[120px] max-w-2xl mx-auto px-4 z-[45] animate-in slide-in-from-bottom-4">
                    <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
                        <div className="p-4 border-b border-slate-800 flex justify-between items-center bg-slate-800/50">
                            <h4 className="font-bold text-white flex items-center gap-2 text-sm">
                                <List className="w-4 h-4 text-plex-orange" />
                                Current Selection ({selectionPool.length})
                            </h4>
                            <button onClick={() => setSelectionPool([])} className="text-[10px] text-slate-400 hover:text-red-400 transition-colors uppercase font-bold tracking-wider">
                                Clear All
                            </button>
                        </div>
                        <div className="max-h-60 overflow-y-auto p-2 custom-scrollbar grid grid-cols-1 gap-1">
                            {selectionPool.map((item, idx) => (
                                <div key={idx} className="flex items-center justify-between p-2 rounded-lg hover:bg-slate-800/80 transition-colors group">
                                    <div className="flex items-center gap-3 min-w-0">
                                        <div className="w-8 h-12 rounded bg-slate-800 flex-shrink-0 overflow-hidden">
                                            {item.poster || item.thumb ? (
                                                <img
                                                    src={item.poster || `/api/proxy/image?thumb=${encodeURIComponent(item.thumb)}`}
                                                    alt=""
                                                    className="w-full h-full object-cover"
                                                />
                                            ) : <ListMusic className="w-4 h-4 m-2 text-slate-600" />}
                                        </div>
                                        <div className="min-w-0">
                                            <p className="text-sm font-bold text-slate-200 truncate">{item.title}</p>
                                            <p className="text-[10px] text-slate-500 uppercase">{item.year} • {item.type || (item.id ? 'External' : 'Library')}</p>
                                        </div>
                                    </div>
                                    <button
                                        onClick={() => toggleSelection(item)}
                                        className="p-1.5 text-slate-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            )}

            {selectionPool.length > 0 && (
                <div className="fixed bottom-8 left-1/2 -translate-x-1/2 w-full max-w-2xl px-4 z-50 animate-in slide-in-from-bottom-8">
                    <div className="bg-slate-900/90 backdrop-blur-xl border border-plex-orange/30 p-4 rounded-2xl shadow-2xl flex flex-col sm:flex-row items-center gap-4">
                        <div className="flex-1 flex gap-4 items-center">
                            <div className="bg-plex-orange/20 p-2 rounded-lg text-plex-orange cursor-pointer hover:bg-plex-orange/30 transition-colors" onClick={() => setShowPoolDetails(!showPoolDetails)}>
                                <ListMusic className={`w-6 h-6 transition-transform ${showPoolDetails ? 'rotate-180' : ''}`} />
                            </div>
                            <div>
                                <p className="text-white font-bold">{selectionPool.length} items selected</p>
                                <p className="text-xs text-slate-400">{targetLibrary ? `Library: ${targetLibrary}` : 'Select a library above'}</p>
                            </div>
                        </div>
                        <div className="flex gap-2 w-full sm:w-auto">
                            <input className="flex-1 sm:w-48 bg-slate-950/50 border border-slate-700/60 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-plex-orange/50" placeholder="Collection Title..." value={collectionTitle} onChange={(e) => setCollectionTitle(e.target.value)} />
                            <div className="flex gap-2">
                                <button onClick={handleCreate} disabled={creating || !collectionTitle || !targetLibrary} className="bg-plex-orange hover:bg-orange-600 text-white px-6 py-2 rounded-lg font-bold disabled:opacity-50 flex items-center gap-2">
                                    {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                                    Create
                                </button>
                                <button
                                    onClick={() => {
                                        setSelectionPool([]);
                                        setCollectionTitle('');
                                        setShowPoolDetails(false);
                                    }}
                                    className="p-2 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-all"
                                    title="Clear All"
                                >
                                    <Plus className="w-6 h-6 rotate-45" />
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}


        </div>
    );
};

export default Creator;
