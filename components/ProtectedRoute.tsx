import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';

export const ProtectedRoute: React.FC = () => {
    const { isAuthenticated, isLoading } = useAuth();
    const [isSetup, setIsSetup] = React.useState<boolean | null>(null);

    React.useEffect(() => {
        const checkSetup = async () => {
            try {
                const data = await api.getAuthStatus();
                setIsSetup(data.is_setup);
            } catch (e) {
                setIsSetup(false);
            }
        };
        checkSetup();
    }, []);

    if (isLoading || isSetup === null) {
        return (
            <div className="min-h-screen bg-slate-950 flex items-center justify-center">
                <div className="flex flex-col items-center gap-4">
                    <div className="w-12 h-12 border-4 border-plex-orange border-t-transparent rounded-full animate-spin"></div>
                    <p className="text-slate-400 font-medium">Authenticating...</p>
                </div>
            </div>
        );
    }

    // Special case: if not setup, allow access to /onboarding even if not authenticated
    const isAtOnboarding = window.location.pathname === '/onboarding';
    if (!isAuthenticated && (!isAtOnboarding || isSetup)) {
        return <Navigate to="/login" replace />;
    }

    return <Outlet />;
};
