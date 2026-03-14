import React from 'react';

interface CardProps {
  title?: string;
  children: React.ReactNode;
  className?: string;
  actions?: React.ReactNode;
}

export const Card: React.FC<CardProps> = ({ title, children, className = '', actions }) => {
  return (
    <div className={`bg-slate-900/50 border border-slate-800 backdrop-blur-md rounded-xl shadow-lg transition-all hover:border-slate-700 group ${className}`}>
      {title && (
        <div className="px-6 py-4 border-b border-slate-800/50 flex justify-between items-center bg-slate-900/20">
          <h3 className="text-lg font-bold text-slate-100 tracking-tight flex items-center gap-2">{title}</h3>
          {actions && <div>{actions}</div>}
        </div>
      )}
      <div className="p-6">
        {children}
      </div>
    </div>
  );
};