import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Settings, ScrollText, BarChart3, X, Image, Sparkles, Clock, LogOut, Activity } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/gallery', label: 'Gallery', icon: Image },
  { to: '/creator', label: 'Collection Creator', icon: Sparkles },
  { to: '/jobs', label: 'Jobs', icon: Clock },
  { to: '/stats', label: 'Statistics', icon: BarChart3 },
  { to: '/config', label: 'Configuration', icon: Settings },
  { to: '/logs', label: 'Logs', icon: ScrollText },
];

const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const { logout } = useAuth();

  return (
    <>
      {/* Mobile Backdrop Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 md:hidden animate-in fade-in duration-200"
          onClick={onClose}
        />
      )}

      <aside className={`
        fixed top-0 left-0 z-50 h-screen w-64 
        bg-slate-950/95 backdrop-blur-xl md:backdrop-blur-none md:bg-slate-950/50 border-r border-slate-800/60 
        flex flex-col transition-transform duration-300 ease-in-out shadow-2xl md:shadow-none
        ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
      `}>
        <div className="p-6 flex items-center justify-between border-b border-slate-800/60 min-h-[80px]">
          <div className="flex items-center gap-3">
            <div className="bg-plex-orange p-2 rounded-lg shadow-lg shadow-orange-500/20">
              <Activity className="w-6 h-6 text-white" />
            </div>
            <h1 className="text-xl font-bold text-slate-100 tracking-tight">Collexions</h1>
          </div>
          <button onClick={onClose} className="md:hidden text-slate-400 hover:text-white p-1 rounded-md hover:bg-slate-800 transition-colors">
            <X className="w-6 h-6" />
          </button>
        </div>

        <nav className="flex-1 p-4 space-y-2 overflow-y-auto scrollbar-thin">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={onClose}
                className={({ isActive }) =>
                  `w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300 ${isActive
                    ? 'bg-plex-orange text-white shadow-lg shadow-orange-900/20 font-medium'
                    : 'text-slate-400 hover:bg-slate-900/50 hover:text-slate-200'
                  }`
                }
              >
                <Icon className="w-5 h-5 flex-shrink-0" />
                <span className="truncate">{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="p-4 border-t border-slate-800/60 bg-slate-900/20 mt-auto">
          <button
            onClick={logout}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-slate-400 hover:bg-red-500/10 hover:text-red-400 transition-all duration-300 group"
          >
            <LogOut className="w-5 h-5 flex-shrink-0 group-hover:-translate-x-1 transition-transform" />
            <span className="font-medium">Logout</span>
          </button>

          <p className="text-[10px] text-slate-600 text-center font-medium mt-4 uppercase tracking-widest">
            v1.1.0 &bull; Collexions Manager
          </p>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;