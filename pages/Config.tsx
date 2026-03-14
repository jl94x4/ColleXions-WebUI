import React, { useEffect, useState } from 'react';
import { Card } from '../components/ui/Card';
import { Input, Switch, CustomSelect } from '../components/ui/Inputs';
import { AppConfig, CategoryConfig, SpecialCollection } from '../types';
import { api } from '../services/api';
import { Save, Plus, Trash2, AlertCircle, ShieldAlert, CheckCircle, Sliders, RefreshCw, Power, Info, Lock, HelpCircle } from 'lucide-react';
import { DEFAULT_CONFIG } from '../constants';

const ConfigPage: React.FC = () => {
    const [config, setConfig] = useState<AppConfig>(DEFAULT_CONFIG);
    const [originalConfig, setOriginalConfig] = useState<AppConfig | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [restarting, setRestarting] = useState(false);
    const [showRestartBanner, setShowRestartBanner] = useState(false);
    const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle');
    const [activeTab, setActiveTab] = useState<'general' | 'libraries' | 'exclusions' | 'specials' | 'categories' | 'integrations' | 'security'>('general');

    const isDirty = originalConfig && JSON.stringify(config) !== JSON.stringify(originalConfig);

    // Handle browser refresh/close
    useEffect(() => {
        const handleBeforeUnload = (e: BeforeUnloadEvent) => {
            if (isDirty) {
                e.preventDefault();
                e.returnValue = '';
            }
        };
        window.addEventListener('beforeunload', handleBeforeUnload);
        return () => window.removeEventListener('beforeunload', handleBeforeUnload);
    }, [isDirty]);

    // Password change state
    const [currentPassword, setCurrentPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [passwordStatus, setPasswordStatus] = useState<{ type: 'idle' | 'success' | 'error', message: string }>({ type: 'idle', message: '' });
    const [changingPassword, setChangingPassword] = useState(false);

    // Load config & status on mount
    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        setLoading(true);
        try {
            const [c] = await Promise.all([api.getConfig(), api.getStatus()]);
            setConfig(c);
            setOriginalConfig(c);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async () => {
        setSaving(true);
        setSaveStatus('idle');
        try {
            await api.saveConfig(config);

            // Re-check status to see if we need to warn user
            const s = await api.getStatus();
            const lower = s.status.toLowerCase();
            const active = lower.includes('running') || lower.includes('sleeping') || lower.includes('processing');

            if (active) {
                setShowRestartBanner(true);
                setOriginalConfig(config);
            } else {
                setSaveStatus('success');
                setOriginalConfig(config);
                setTimeout(() => setSaveStatus('idle'), 3000);
            }
        } catch (e) {
            console.error(e);
            setSaveStatus('error');
        }
        setSaving(false);
    };

    const handlePasswordChange = async (e: React.FormEvent) => {
        e.preventDefault();
        if (newPassword !== confirmPassword) {
            setPasswordStatus({ type: 'error', message: 'New passwords do not match' });
            return;
        }
        if (newPassword.length < 8) {
            setPasswordStatus({ type: 'error', message: 'Password must be at least 8 characters' });
            return;
        }

        setChangingPassword(true);
        setPasswordStatus({ type: 'idle', message: '' });
        try {
            await api.changePassword(currentPassword, newPassword);
            setPasswordStatus({ type: 'success', message: 'Password updated successfully!' });
            setCurrentPassword('');
            setNewPassword('');
            setConfirmPassword('');
        } catch (e: any) {
            setPasswordStatus({ type: 'error', message: e.message || 'Failed to update password' });
        } finally {
            setChangingPassword(false);
        }
    };

    const handleRestartService = async () => {
        setRestarting(true);
        try {
            await api.stopScript();
            // Give it a moment to stop
            await new Promise(resolve => setTimeout(resolve, 2000));
            await api.runNow();

            setShowRestartBanner(false);
            setSaveStatus('success'); // Show success after restart
            setTimeout(() => setSaveStatus('idle'), 5000);
        } catch (e) {
            alert("Failed to restart service automatically. Please use the Dashboard.");
        }
        setRestarting(false);
    };

    const updateField = (field: keyof AppConfig, value: any) => {
        setConfig(prev => ({ ...prev, [field]: value }));
    };

    // Safe accessors
    const libraries = config.library_names || [];
    const pins = config.number_of_collections_to_pin || {};
    const specials = config.special_collections || [];
    const exclusions = config.exclusion_list || [];
    const regexExclusions = config.regex_exclusion_patterns || [];

    // --- SUB-EDITORS ---

    // Library List Editor
    const handleAddLibrary = () => {
        const name = prompt("Enter Library Name (exact match from Plex):");
        if (name && !libraries.includes(name)) {
            setConfig(prev => ({
                ...prev,
                library_names: [...(prev.library_names || []), name],
                number_of_collections_to_pin: { ...(prev.number_of_collections_to_pin || {}), [name]: 0 }
            }));
        }
    };

    const handleRemoveLibrary = (name: string) => {
        if (confirm(`Remove library "${name}"?`)) {
            setConfig(prev => {
                const newLibs = (prev.library_names || []).filter(l => l !== name);
                const newPins = { ...(prev.number_of_collections_to_pin || {}) };
                delete newPins[name];
                return { ...prev, library_names: newLibs, number_of_collections_to_pin: newPins };
            });
        }
    };

    const handlePinCountChange = (lib: string, val: string) => {
        const num = parseInt(val) || 0;
        setConfig(prev => ({
            ...prev,
            number_of_collections_to_pin: { ...(prev.number_of_collections_to_pin || {}), [lib]: num }
        }));
    };

    // Array String Editor (Exclusions/Regex)
    const ArrayEditor = ({ list = [], onChange, placeholder }: { list: string[], onChange: (l: string[]) => void, placeholder: string }) => {
        const [input, setInput] = useState('');
        const safeList = list || [];

        const add = () => { if (input) { onChange([...safeList, input]); setInput(''); } };
        const remove = (idx: number) => { onChange(safeList.filter((_, i) => i !== idx)); };

        return (
            <div className="space-y-3">
                <div className="flex gap-2">
                    <input
                        className="flex-1 bg-slate-950/50 border border-slate-700/60 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-plex-orange/50 min-w-0"
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        placeholder={placeholder}
                        onKeyDown={e => e.key === 'Enter' && add()}
                    />
                    <button onClick={add} className="bg-slate-800 hover:bg-slate-700 text-white px-3 rounded border border-slate-700/50 flex-shrink-0"><Plus className="w-4 h-4" /></button>
                </div>
                <div className="flex flex-wrap gap-2">
                    {safeList.map((item, idx) => (
                        <span key={idx} className="bg-slate-900/50 border border-slate-800 text-slate-300 text-xs md:text-sm px-2 py-1 rounded flex items-center gap-2 max-w-full truncate">
                            <span className="truncate">{item}</span>
                            <button onClick={() => remove(idx)} className="text-red-400 hover:text-red-300 flex-shrink-0"><Trash2 className="w-3 h-3" /></button>
                        </span>
                    ))}
                    {safeList.length === 0 && <span className="text-slate-600 text-sm italic">No items</span>}
                </div>
            </div>
        );
    };

    // Special Collections Editor
    const handleAddSpecial = () => {
        const newItem: SpecialCollection = { start_date: '12-01', end_date: '12-25', collection_names: ['Christmas Movies'] };
        setConfig(prev => ({ ...prev, special_collections: [...(prev.special_collections || []), newItem] }));
    };

    const updateSpecial = (idx: number, field: keyof SpecialCollection, val: any) => {
        const updated = [...(config.special_collections || [])];
        updated[idx] = { ...updated[idx], [field]: val };
        setConfig(prev => ({ ...prev, special_collections: updated }));
    };

    const updateSpecialCollNames = (idx: number, namesStr: string) => {
        const names = namesStr.split(',').map(s => s.trim());
        updateSpecial(idx, 'collection_names', names);
    };

    // Categories Editor
    const CategoryEditor = () => {
        const safeLibs = config.library_names || [];
        const [selectedLib, setSelectedLib] = useState<string>('');

        useEffect(() => {
            if (!selectedLib && safeLibs.length > 0) {
                setSelectedLib(safeLibs[0]);
            }
        }, [safeLibs, selectedLib]);

        const currentLib = selectedLib || safeLibs[0] || '';

        if (!currentLib) return <div className="text-slate-500 italic p-6 text-center border border-slate-800/50 rounded bg-slate-900/30">Please add libraries in the "Libraries" tab first.</div>;

        const safeCats = config.categories || {};
        const categories = safeCats[currentLib] || [];

        const addCategory = () => {
            const newCat: CategoryConfig = { category_name: 'New Category', pin_count: 1, collections: [] };
            const updatedCats = [...categories, newCat];
            setConfig(prev => ({ ...prev, categories: { ...(prev.categories || {}), [currentLib]: updatedCats } }));
        };

        const removeCategory = (idx: number) => {
            const updatedCats = categories.filter((_, i) => i !== idx);
            setConfig(prev => ({ ...prev, categories: { ...(prev.categories || {}), [currentLib]: updatedCats } }));
        };

        const updateCatField = (idx: number, field: keyof CategoryConfig, val: any) => {
            const updatedCats = [...categories];
            updatedCats[idx] = { ...updatedCats[idx], [field]: val };
            setConfig(prev => ({ ...prev, categories: { ...(prev.categories || {}), [currentLib]: updatedCats } }));
        };

        return (
            <div className="space-y-6">
                <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
                    <div className="flex-1 w-full">
                        <CustomSelect
                            label="Select Library"
                            value={currentLib}
                            onChange={setSelectedLib}
                            options={safeLibs.map(l => ({ label: l, value: l }))}
                            tooltip="Choose which Plex library to manage categories for."
                        />
                    </div>
                    <button onClick={addCategory} className="w-full sm:w-auto mt-auto flex items-center justify-center gap-2 bg-plex-orange text-white px-4 py-2 rounded-lg hover:bg-orange-600 shadow-lg shadow-orange-900/20 text-sm font-medium h-[42px]">
                        <Plus className="w-4 h-4" /> Add Category
                    </button>
                </div>

                <div className="space-y-4">
                    {categories.length === 0 && <div className="p-8 text-center bg-slate-900/30 rounded border border-slate-800/50 border-dashed text-slate-500">No categories defined for {currentLib}</div>}

                    {categories.map((cat, idx) => (
                        <div key={idx} className="bg-slate-950/30 border border-slate-800/60 rounded-xl p-4 md:p-6 space-y-4">
                            <div className="flex gap-4 items-start">
                                <div className="flex-1 space-y-4">
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
                                        <Input
                                            label="Category Name"
                                            value={cat.category_name}
                                            onChange={e => updateCatField(idx, 'category_name', e.target.value)}
                                            tooltip="A descriptive name for this category (e.g. 'Heroes', 'Scary Movies')."
                                        />
                                        <Input
                                            label="Pin Count"
                                            type="number"
                                            value={cat.pin_count}
                                            onChange={e => updateCatField(idx, 'pin_count', parseInt(e.target.value))}
                                            tooltip="The maximum number of collections from this category to have pinned on your home screen at once."
                                        />
                                    </div>
                                    <div>
                                        <div className="flex items-center gap-1.5 mb-1">
                                            <label className="block text-sm font-medium text-slate-300">Collections (comma separated)</label>
                                            <div className="relative leading-none">
                                                <HelpCircle className="peer w-3.5 h-3.5 text-slate-500 hover:text-plex-orange cursor-help transition-colors" />
                                                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2 bg-slate-900/95 border border-slate-700/50 rounded-lg text-[10px] text-slate-300 opacity-0 peer-hover:opacity-100 transition-all duration-200 pointer-events-none z-[100] shadow-2xl backdrop-blur-md font-normal leading-normal">
                                                    Comma-separated list of collection names that belong to this category. Case sensitive.
                                                    <div className="absolute top-full left-1/2 -translate-x-1/2 border-8 border-transparent border-t-slate-900/95" />
                                                </div>
                                            </div>
                                        </div>
                                        <textarea
                                            className="w-full bg-slate-950/50 border border-slate-700/60 rounded-lg p-3 text-sm text-slate-200 focus:outline-none focus:border-plex-orange/50"
                                            rows={2}
                                            value={cat.collections.join(', ')}
                                            onChange={e => updateCatField(idx, 'collections', e.target.value.split(',').map(s => s.trim()))}
                                        />
                                    </div>
                                </div>
                                <button onClick={() => removeCategory(idx)} className="text-slate-500 hover:text-red-500 mt-2 p-2 hover:bg-red-500/10 rounded-lg transition-colors"><Trash2 className="w-5 h-5" /></button>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        );
    };

    if (loading) return (
        <div className="flex h-96 items-center justify-center text-slate-400 flex-col gap-4">
            <div className="w-8 h-8 border-2 border-slate-600 border-t-plex-orange rounded-full animate-spin" />
            <p>Loading Configuration...</p>
        </div>
    );

    return (
        <div className="space-y-8 pb-20 animate-in fade-in duration-500">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 className="text-2xl md:text-3xl font-bold text-white tracking-tight">Configuration</h2>
                    <p className="text-slate-400 mt-1 flex items-center gap-2 text-sm md:text-base">
                        <Sliders className="w-4 h-4" />
                        Manage libraries, exclusions and scheduling
                    </p>
                </div>
                <div className="flex flex-col sm:flex-row w-full md:w-auto gap-3">
                    <button
                        onClick={handleSave}
                        disabled={saving || restarting}
                        className="flex-1 md:flex-none justify-center flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-white px-5 py-2.5 rounded-xl font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed border border-slate-700 shadow-sm w-full md:w-40">
                        <Save className="w-4 h-4" /> {saving ? 'Saving...' : 'Save Config'}
                    </button>
                </div>
            </div>

            {/* Alerts / Feedback Banners */}
            {showRestartBanner && (
                <div className="bg-amber-500/10 border border-amber-500/20 text-amber-200 p-4 rounded-xl flex flex-col md:flex-row items-center gap-4 animate-in fade-in slide-in-from-top-2 shadow-lg">
                    <div className="bg-amber-500/20 p-2 rounded-full hidden md:block">
                        <RefreshCw className="w-6 h-6 text-amber-500 animate-[spin_3s_linear_infinite]" />
                    </div>
                    <div className="flex-1 text-center md:text-left">
                        <p className="font-bold text-lg">Restart Required</p>
                        <p className="text-sm opacity-80">The service is currently active with old settings. You must restart it for changes to take effect.</p>
                    </div>
                    <button
                        onClick={handleRestartService}
                        disabled={restarting}
                        className="w-full md:w-auto bg-amber-600 hover:bg-amber-500 text-white px-6 py-2 rounded-lg font-bold shadow-lg transition-colors flex items-center justify-center gap-2 whitespace-nowrap"
                    >
                        {restarting ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Power className="w-4 h-4" />}
                        {restarting ? 'Restarting...' : 'Restart Service Now'}
                    </button>
                </div>
            )}

            {saveStatus === 'success' && !showRestartBanner && (
                <div className="bg-green-500/10 border border-green-500/20 text-green-400 px-4 py-3 rounded-xl flex items-center gap-2 animate-in fade-in slide-in-from-top-2">
                    <CheckCircle className="w-5 h-5" /> Changes saved successfully.
                </div>
            )}

            {saveStatus === 'error' && (
                <div className="bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-3 rounded-xl flex items-center gap-2 animate-in fade-in slide-in-from-top-2">
                    <AlertCircle className="w-5 h-5" /> Error saving configuration. Check console.
                </div>
            )}

            {isDirty && !showRestartBanner && (
                <div className="bg-plex-orange/10 border border-plex-orange/30 text-plex-orange px-4 py-3 rounded-xl flex flex-col sm:flex-row items-center justify-between gap-3 animate-in fade-in slide-in-from-top-2">
                    <div className="flex items-center gap-2">
                        <ShieldAlert className="w-5 h-5 flex-shrink-0" />
                        <span className="font-medium text-sm">You have unsaved changes.</span>
                    </div>
                    <div className="flex gap-2">
                        <button
                            onClick={() => { setConfig(originalConfig!); }}
                            className="px-4 py-1.5 rounded-lg text-sm font-bold text-slate-400 hover:bg-slate-800 hover:text-white transition-colors border border-slate-700"
                        >
                            Discard
                        </button>
                        <button
                            onClick={handleSave}
                            disabled={saving}
                            className="px-4 py-1.5 rounded-lg text-sm font-bold bg-plex-orange text-white hover:bg-orange-600 transition-colors shadow-lg disabled:opacity-50"
                        >
                            {saving ? 'Saving...' : 'Save Now'}
                        </button>
                    </div>
                </div>
            )}

            {/* Tabs - Make scrollable on mobile */}
            <div className="border-b border-slate-800/60 flex overflow-x-auto no-scrollbar -mx-4 px-4 md:mx-0 md:px-0">
                {['general', 'libraries', 'exclusions', 'specials', 'categories', 'integrations', 'security'].map(t => (
                    <button
                        key={t}
                        onClick={() => setActiveTab(t as any)}
                        className={`px-4 md:px-6 py-4 font-medium capitalize transition-all border-b-2 whitespace-nowrap text-sm md:text-base ${activeTab === t
                            ? 'text-plex-orange border-plex-orange bg-slate-900/20'
                            : 'text-slate-400 border-transparent hover:text-slate-200 hover:bg-slate-900/10'
                            }`}
                    >
                        {t}
                    </button>
                ))}
            </div>

            <div className="animate-in fade-in duration-300">
                {activeTab === 'general' && (
                    <div className="grid gap-6">
                        <Card title="Plex Connection">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <Input label="Plex URL" value={config.plex_url} onChange={e => updateField('plex_url', e.target.value)} placeholder="http://localhost:32400" tooltip="The local or remote address of your Plex server. Include the port (default 32400)." />
                                <Input label="Plex Token" type="password" value={config.plex_token} onChange={e => updateField('plex_token', e.target.value)} tooltip="Your X-Plex-Token used for authentication. Can be found in the URL of any XML page on your Plex server." />
                            </div>
                        </Card>

                        <Card title="Execution Controls">
                            <div className={`border rounded-xl p-4 md:p-6 mb-6 transition-all duration-300 flex flex-col md:flex-row gap-4 items-start ${config.dry_run ? 'bg-plex-orange/10 border-plex-orange/30' : 'bg-slate-950/30 border-slate-800/60'}`}>
                                <div className={`p-3 rounded-full hidden md:block ${config.dry_run ? 'bg-plex-orange/20 text-plex-orange' : 'bg-slate-900 text-slate-500'}`}>
                                    <ShieldAlert className="w-6 h-6" />
                                </div>
                                <div className="flex-1 w-full">
                                    <Switch
                                        label="Dry Run Mode"
                                        checked={config.dry_run}
                                        onChange={v => updateField('dry_run', v)}
                                        description="When enabled, the script will only LOG what it would do. No changes will be made to your Plex server."
                                        tooltip="Simulate actions without making any changes to Plex. Check logs to see what would have happened."
                                    />
                                    {config.dry_run && (
                                        <p className="text-sm text-plex-orange mt-2 font-medium">
                                            ⚠️ Actions are currently simulated. Turn this OFF to apply changes.
                                        </p>
                                    )}
                                </div>
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6 mb-6">
                                <Input label="Check Interval (min)" type="number" value={config.pinning_interval} onChange={e => updateField('pinning_interval', parseInt(e.target.value) || 0)} tooltip="How often (in minutes) the script checks for new pinning opportunities." />
                                <Input label="Repeat Block (hours)" type="number" value={config.repeat_block_hours} onChange={e => updateField('repeat_block_hours', parseInt(e.target.value))} tooltip="Hours to wait before pinning the same collection again after it has been unpinned." />
                                <Input label="Min Items in Collection" type="number" value={config.min_items_for_pinning} onChange={e => updateField('min_items_for_pinning', parseInt(e.target.value))} tooltip="Minimum number of items required in a collection for it to be considered for pinning." />
                            </div>
                            <div className="space-y-4 pt-4 border-t border-slate-800/50">
                                <Input label="Collection Label" value={config.collexions_label} onChange={e => updateField('collexions_label', e.target.value)} tooltip="The label added to all collections managed by ColleXions for easy identification." />
                                <Input label="Discord Webhook URL" value={config.discord_webhook_url} onChange={e => updateField('discord_webhook_url', e.target.value)} placeholder="https://discord.com/api/webhooks/..." tooltip="Post notifications to a Discord channel when collections are pinned or unpinned." />
                            </div>
                        </Card>

                        <Card title="Random Category Mode">
                            <div className="space-y-6">
                                <Switch
                                    label="Enable Random Category Mode"
                                    checked={config.use_random_category_mode}
                                    onChange={v => updateField('use_random_category_mode', v)}
                                    description="If enabled, picks one category at random instead of filling all slots sequentially."
                                    tooltip="Instead of rotating through all categories, pick one at random each run to keep your home screen fresh."
                                />
                                <div className={`transition-opacity ${config.use_random_category_mode ? 'opacity-100' : 'opacity-40 pointer-events-none'}`}>
                                    <div className="mb-2 flex justify-between">
                                        <label className="text-sm font-medium text-slate-300">Skip Percent ({config.random_category_skip_percent}%)</label>
                                    </div>
                                    <input
                                        type="range" min="0" max="100"
                                        value={config.random_category_skip_percent}
                                        onChange={e => updateField('random_category_skip_percent', parseInt(e.target.value))}
                                        className="w-full accent-plex-orange cursor-pointer"
                                    />
                                    <p className="text-xs text-slate-500 mt-1">Chance to skip selecting a category entirely in a cycle.</p>
                                </div>
                            </div>
                        </Card>
                    </div>
                )}

                {activeTab === 'libraries' && (
                    <Card title="Managed Libraries" actions={<button onClick={handleAddLibrary} className="text-plex-orange hover:text-orange-400 text-sm font-bold flex items-center gap-1 transition-colors"><Plus className="w-4 h-4" /> Add Lib</button>}>
                        <div className="space-y-4">
                            {libraries.length === 0 && <p className="text-slate-500 italic text-center py-4">No libraries added yet.</p>}
                            {libraries.map(lib => (
                                <div key={lib} className="flex flex-col sm:flex-row sm:items-center justify-between bg-slate-950/30 border border-slate-800/60 p-4 rounded-xl hover:border-slate-700/60 transition-colors gap-3">
                                    <span className="font-medium text-slate-200 truncate">{lib}</span>
                                    <div className="flex items-center gap-4 self-end sm:self-auto">
                                        <div className="flex items-center gap-2 bg-slate-900/50 px-3 py-1.5 rounded-lg border border-slate-800/50">
                                            <span className="text-xs text-slate-500 uppercase font-bold tracking-wider">Pins</span>
                                            <input
                                                type="number"
                                                className="w-12 bg-transparent border-none p-0 text-center text-white text-sm focus:ring-0"
                                                value={pins[lib] || 0}
                                                onChange={(e) => handlePinCountChange(lib, e.target.value)}
                                            />
                                        </div>
                                        <button onClick={() => handleRemoveLibrary(lib)} className="text-slate-500 hover:text-red-500 p-2 hover:bg-red-500/10 rounded-lg transition-colors"><Trash2 className="w-4 h-4" /></button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </Card>
                )}

                {activeTab === 'exclusions' && (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <Card title="Global Exclusion List">
                            <div className="flex items-center gap-1.5 mb-4">
                                <p className="text-xs text-slate-500">Exact collection names to never pin.</p>
                                <div className="relative">
                                    <Info className="peer w-3 h-3 text-slate-600 hover:text-plex-orange cursor-help transition-colors" />
                                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2 bg-slate-900 border border-slate-700/50 rounded-lg text-[10px] text-slate-300 opacity-0 peer-hover:opacity-100 transition-all duration-200 pointer-events-none z-[100] shadow-2xl backdrop-blur-md">
                                        Use this to prevent specific collections from ever being pinned to your home screen, even if they match categories or trending data.
                                        <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-900" />
                                    </div>
                                </div>
                            </div>
                            <ArrayEditor
                                list={exclusions}
                                onChange={l => updateField('exclusion_list', l)}
                                placeholder="Collection Name"
                            />
                        </Card>
                        <Card title="Regex Exclusions">
                            <div className="flex items-center gap-1.5 mb-4">
                                <p className="text-xs text-slate-500">Python Regex patterns to exclude.</p>
                                <div className="relative">
                                    <Info className="peer w-3 h-3 text-slate-600 hover:text-plex-orange cursor-help transition-colors" />
                                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2 bg-slate-900 border border-slate-700/50 rounded-lg text-[10px] text-slate-300 opacity-0 peer-hover:opacity-100 transition-all duration-200 pointer-events-none z-[100] shadow-2xl backdrop-blur-md">
                                        Exclude collections based on name patterns (e.g. ^.*-4K$ to exclude any collection ending with -4K).
                                        <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-900" />
                                    </div>
                                </div>
                            </div>
                            <ArrayEditor
                                list={regexExclusions}
                                onChange={l => updateField('regex_exclusion_patterns', l)}
                                placeholder="^.*(4K|Remux).*$"
                            />
                        </Card>
                    </div>
                )}

                {activeTab === 'specials' && (
                    <Card title="Special Event Collections" actions={<button onClick={handleAddSpecial} className="text-plex-orange hover:text-orange-400 text-sm font-bold flex items-center gap-1"><Plus className="w-4 h-4" /> Add Event</button>}>
                        <div className="space-y-4">
                            {specials.map((spec, idx) => (
                                <div key={idx} className="bg-slate-950/30 border border-slate-800/60 p-4 md:p-6 rounded-xl space-y-4 relative group hover:border-slate-700/60 transition-colors">
                                    <button
                                        onClick={() => {
                                            const updated = specials.filter((_, i) => i !== idx);
                                            setConfig(prev => ({ ...prev, special_collections: updated }));
                                        }}
                                        className="absolute top-4 right-4 text-slate-600 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity p-2 hover:bg-red-500/10 rounded-lg">
                                        <Trash2 className="w-4 h-4" />
                                    </button>

                                    <div className="flex flex-col md:flex-row gap-4 md:gap-6">
                                        <div className="md:w-1/3 space-y-4">
                                            <Input label="Start Date (MM-DD)" value={spec.start_date} onChange={e => updateSpecial(idx, 'start_date', e.target.value)} />
                                            <Input label="End Date (MM-DD)" value={spec.end_date} onChange={e => updateSpecial(idx, 'end_date', e.target.value)} />
                                        </div>
                                        <div className="md:w-2/3">
                                            <label className="block text-sm font-medium text-slate-300 mb-1.5">Collection Names (comma separated)</label>
                                            <textarea
                                                className="w-full bg-slate-950/50 border border-slate-700/60 rounded-lg p-3 text-sm text-slate-200 h-28 focus:outline-none focus:border-plex-orange/50"
                                                value={(spec.collection_names || []).join(', ')}
                                                onChange={e => updateSpecialCollNames(idx, e.target.value)}
                                            />
                                        </div>
                                    </div>
                                </div>
                            ))}
                            {specials.length === 0 && <div className="text-center text-slate-500 py-8">No special events configured.</div>}
                        </div>
                    </Card>
                )}

                {activeTab === 'categories' && (
                    <Card title="Library Categories">
                        <div className="bg-blue-900/10 border border-blue-500/20 p-4 rounded-xl mb-6 flex items-start gap-4">
                            <AlertCircle className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
                            <p className="text-sm text-blue-200/80 leading-relaxed">
                                Categories allow you to group collections and force specific numbers of pins from that group.
                                In "Random Category Mode", the script will randomly pick one of these categories per run.
                            </p>
                        </div>
                        <CategoryEditor />
                    </Card>
                )}

                {activeTab === 'integrations' && (
                    <div className="space-y-6">
                        <Card title="External Services">
                            <div className="bg-amber-500/10 border border-amber-500/20 p-4 rounded-xl mb-6 flex items-start gap-4">
                                <AlertCircle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
                                <div className="space-y-1">
                                    <p className="text-sm text-amber-200/90 font-bold">API Keys Required</p>
                                    <p className="text-xs text-amber-200/70 leading-relaxed">
                                        To use Trending & Creation features, you need TMDb, Trakt, and/or MDBList credentials.
                                        You can get a TMDb API key for free from their developer portal, a Trakt Client ID by creating an "API App" on Trakt.tv, or an MDBList API key from MDBList.com.
                                    </p>
                                </div>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                                <Input
                                    label="TMDb API Key"
                                    value={config.tmdb_api_key || ''}
                                    onChange={e => updateField('tmdb_api_key', e.target.value)}
                                    placeholder="Your v3 API Key"
                                    type="password"
                                    tooltip="Required for identifying trending movies and shows from The Movie Database."
                                />
                                <Input
                                    label="Trakt Client ID"
                                    value={config.trakt_client_id || ''}
                                    onChange={e => updateField('trakt_client_id', e.target.value)}
                                    placeholder="Client ID / API Key"
                                    type="password"
                                    tooltip="Required for identifying trending lists from Trakt.tv."
                                />
                                <Input
                                    label="MDBList API Key"
                                    value={config.mdblist_api_key || ''}
                                    onChange={e => updateField('mdblist_api_key', e.target.value)}
                                    placeholder="Your API Key"
                                    type="password"
                                    tooltip="Used to enhance metadata and filtering for collection creation."
                                />
                            </div>
                        </Card>

                        <Card title="Smart Pinning Logic">
                            <Switch
                                label="Enable Smart Pinning"
                                checked={config.enable_trending_pinning || false}
                                onChange={v => updateField('enable_trending_pinning', v)}
                                description="Automatically identify and pin collections that match global trending results from Trakt and TMDb."
                                tooltip="Matches your local collections against current global trending data to elevate relevant content automatically."
                            />
                            <p className="text-xs text-slate-500 mt-4 border-t border-slate-800 pt-4">
                                Note: This will prioritize your local collections that match trending titles. It will NOT create new collections automatically yet.
                            </p>
                        </Card>
                    </div>
                )}

                {activeTab === 'security' && (
                    <div className="max-w-xl mx-auto py-8">
                        <Card title="Change Admin Password">
                            <form onSubmit={handlePasswordChange} className="space-y-6">
                                <div className="flex items-center gap-4 mb-6 p-4 bg-slate-950/40 border border-slate-800 rounded-xl">
                                    <div className="p-3 bg-plex-orange/10 rounded-lg text-plex-orange">
                                        <Lock className="w-6 h-6" />
                                    </div>
                                    <div>
                                        <p className="text-sm font-medium text-white">Security Settings</p>
                                        <p className="text-xs text-slate-500">Update your dashboard administrator password.</p>
                                    </div>
                                </div>

                                <Input
                                    label="Current Password"
                                    type="password"
                                    value={currentPassword}
                                    onChange={e => setCurrentPassword(e.target.value)}
                                    placeholder="••••••••"
                                    required
                                />

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <Input
                                        label="New Password"
                                        type="password"
                                        value={newPassword}
                                        onChange={e => setNewPassword(e.target.value)}
                                        placeholder="••••••••"
                                        required
                                        tooltip="Must be at least 8 characters long."
                                    />
                                    <Input
                                        label="Confirm New Password"
                                        type="password"
                                        value={confirmPassword}
                                        onChange={e => setConfirmPassword(e.target.value)}
                                        placeholder="••••••••"
                                        required
                                    />
                                </div>

                                {passwordStatus.type !== 'idle' && (
                                    <div className={`p-4 rounded-xl text-sm flex items-center gap-3 animate-in fade-in zoom-in-95 ${passwordStatus.type === 'success'
                                        ? 'bg-green-500/10 border border-green-500/20 text-green-400'
                                        : 'bg-red-500/10 border border-red-500/20 text-red-400'
                                        }`}>
                                        {passwordStatus.type === 'success' ? <CheckCircle className="w-5 h-5 flex-shrink-0" /> : <ShieldAlert className="w-5 h-5 flex-shrink-0" />}
                                        {passwordStatus.message}
                                    </div>
                                )}

                                <button
                                    type="submit"
                                    disabled={changingPassword || !currentPassword || !newPassword || !confirmPassword}
                                    className="w-full bg-plex-orange hover:bg-plex-orange/80 text-white font-bold py-3 rounded-xl transition-all disabled:opacity-50 flex items-center justify-center gap-2 shadow-lg shadow-plex-orange/10"
                                >
                                    {changingPassword ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                                    Update Password
                                </button>
                            </form>
                        </Card>
                    </div>
                )}
            </div>
        </div>
    );
};

export default ConfigPage;
