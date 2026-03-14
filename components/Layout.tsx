import React, { useState } from 'react';
import Sidebar from './Sidebar';
import BottomNav from './BottomNav';
import { Activity } from 'lucide-react';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      {/* Mobile Header */}
      <div className="md:hidden fixed top-0 left-0 right-0 bg-slate-950/80 backdrop-blur-md border-b border-slate-800/60 z-40 px-4 py-3 flex items-center justify-center">
        <div className="flex items-center gap-2">
          <div className="bg-plex-orange p-1.5 rounded-lg">
            <Activity className="w-5 h-5 text-white" />
          </div>
          <span className="font-bold text-lg tracking-tight text-white uppercase italic">Collexions</span>
        </div>
      </div>

      <Sidebar
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
      />

      {/* Main Content Area */}
      <main className="flex-1 px-4 md:px-8 pt-20 md:pt-8 md:ml-64 w-full overflow-x-hidden pb-24 md:pb-8">
        <div className="max-w-[2400px] mx-auto">
          {children}
        </div>
      </main>

      {/* Bottom Nav Mobile */}
      <BottomNav />
    </div>
  );
};

export default Layout;