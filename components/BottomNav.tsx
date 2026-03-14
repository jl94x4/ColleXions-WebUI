import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Image, Sparkles, Clock, BarChart3, MoreHorizontal, Settings, ScrollText } from 'lucide-react';

const primaryItems = [
    { to: '/', label: 'Dash', icon: LayoutDashboard, end: true },
    { to: '/gallery', label: 'Gallery', icon: Image },
    { to: '/creator', label: 'Creator', icon: Sparkles },
    { to: '/jobs', label: 'Jobs', icon: Clock },
    { to: '/stats', label: 'Stats', icon: BarChart3 },
];

const overflowItems = [
    { to: '/config', label: 'Configuration', icon: Settings },
    { to: '/logs', label: 'Logs', icon: ScrollText },
];

const BottomNav: React.FC = () => {
    const [isMenuOpen, setIsMenuOpen] = useState(false);

    return (
        <nav className="fixed bottom-0 left-0 right-0 bg-slate-900/95 backdrop-blur-xl border-t border-slate-800/60 z-50 md:hidden">
            <div className="flex items-center justify-around h-16 px-2">
                {primaryItems.map((item) => {
                    const Icon = item.icon;
                    return (
                        <NavLink
                            key={item.to}
                            to={item.to}
                            end={item.end}
                            onClick={() => setIsMenuOpen(false)}
                            className={({ isActive }) =>
                                `flex flex-col items-center justify-center flex-1 h-full gap-1 transition-all ${isActive ? 'text-plex-orange' : 'text-slate-400 hover:text-slate-200'}`
                            }
                        >
                            {({ isActive }) => (
                                <>
                                    <Icon className={`w-5 h-5 ${isActive ? 'scale-110' : ''}`} />
                                    <span className="text-[10px] font-medium uppercase tracking-tighter">{item.label}</span>
                                </>
                            )}
                        </NavLink>
                    );
                })}

                <button
                    onClick={() => setIsMenuOpen(!isMenuOpen)}
                    className={`flex flex-col items-center justify-center flex-1 h-full gap-1 transition-all ${isMenuOpen ? 'text-plex-orange' : 'text-slate-400'}`}
                >
                    <MoreHorizontal className={`w-5 h-5 ${isMenuOpen ? 'scale-110' : ''}`} />
                    <span className="text-[10px] font-medium uppercase tracking-tighter">More</span>
                </button>
            </div>

            {/* Overflow Menu */}
            {isMenuOpen && (
                <>
                    <div
                        className="fixed inset-0 z-[-1] animate-in fade-in duration-200"
                        onClick={() => setIsMenuOpen(false)}
                    />
                    <div className="absolute bottom-full right-4 mb-2 w-48 bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden animate-in slide-in-from-bottom-4 duration-200">
                        {overflowItems.map((item) => {
                            const Icon = item.icon;
                            return (
                                <NavLink
                                    key={item.to}
                                    to={item.to}
                                    onClick={() => setIsMenuOpen(false)}
                                    className={({ isActive }) =>
                                        `w-full flex items-center gap-3 px-4 py-4 transition-colors ${isActive ? 'bg-plex-orange/10 text-plex-orange' : 'text-slate-300 hover:bg-slate-800'}`
                                    }
                                >
                                    <Icon className="w-5 h-5" />
                                    <span className="text-sm font-bold">{item.label}</span>
                                </NavLink>
                            );
                        })}
                    </div>
                </>
            )}
        </nav>
    );
};

export default BottomNav;
