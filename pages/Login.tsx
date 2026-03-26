import React, { useState, useEffect } from 'react';
import { Shield, Key, AlertCircle, ArrowRight, Eye, EyeOff } from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';

export const Login: React.FC = () => {
    const { login } = useAuth();
    const [isSetup, setIsSetup] = useState<boolean | null>(null);
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        const checkStatus = async () => {
            try {
                const data = await api.getAuthStatus();
                console.log('Auth status check:', data);
                setIsSetup(data.is_setup);
            } catch (e) {
                console.error('Failed to get auth status, defaulting to setup mode:', e);
                setIsSetup(false); // Default to setup mode if we can't tell
            }
        };
        checkStatus();
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            if (!isSetup) {
                // Setup flow
                if (password.length < 8) {
                    throw new Error('Password must be at least 8 characters');
                }
                if (password !== confirmPassword) {
                    throw new Error('Passwords do not match');
                }
                await api.setupAuth(password);
                setIsSetup(true);
                setPassword('');
                setConfirmPassword('');
                setError('Password set successfully! Please login.');
            } else {
                // Login flow
                await login(password);
                window.location.href = '/';
            }
        } catch (err: any) {
            setError(err.message || 'Authentication failed');
        } finally {
            setLoading(false);
        }
    };

    if (isSetup === null) return null;

    return (
        <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center p-6 relative overflow-hidden">
            {/* Background Glow */}
            <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-plex-orange/10 rounded-full blur-[120px] -z-10" />
            <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-[120px] -z-10" />

            <div className="w-full max-w-md">
                {/* Brand Header */}
                <div className="text-center mb-10">
                    <div className="inline-flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-slate-800 shadow-2xl mb-6 ring-1 ring-slate-800/50">
                        <Shield className="w-10 h-10 text-plex-orange drop-shadow-[0_0_15px_rgba(231,166,26,0.3)]" />
                    </div>
                    <h1 className="text-4xl font-extrabold text-white tracking-tight mb-3">
                        ColleXions <span className="text-plex-orange">Manager</span>
                    </h1>
                    <p className="text-slate-400 font-medium">
                        {isSetup ? 'Administrator Secure Access' : 'Initial Configuration'}
                    </p>
                </div>

                {/* Login/Setup Card */}
                <div className="bg-slate-900/40 backdrop-blur-2xl p-8 rounded-[2.5rem] border border-white/5 shadow-3xl ring-1 ring-white/10 relative">
                    {!isSetup ? (
                        <div className="space-y-6 text-center py-4">
                            <div className="flex items-start gap-3 p-4 bg-blue-500/10 border border-blue-500/20 rounded-2xl text-left">
                                <AlertCircle className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
                                <p className="text-xs text-blue-200/80 leading-relaxed font-medium">
                                    Welcome! This is your first run. Let's get your environment secured and configured.
                                </p>
                            </div>
                            <button
                                onClick={() => window.location.href = '/onboarding'}
                                className="w-full flex items-center justify-center gap-3 py-4 bg-gradient-to-r from-plex-orange to-orange-400 text-white font-bold rounded-2xl shadow-xl shadow-orange-950/20 hover:shadow-orange-500/20 hover:scale-[1.02] active:scale-[0.98] transition-all duration-300 group"
                            >
                                <span>Get Started</span>
                                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                            </button>
                        </div>
                    ) : (
                        <form onSubmit={handleSubmit} className="space-y-6">
                            <div className="space-y-2">
                                <label className="text-sm font-semibold text-slate-300 ml-1">
                                    Admin Password
                                </label>
                                <div className="relative group">
                                    <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                                        <Key className="w-5 h-5 text-slate-500 group-focus-within:text-plex-orange transition-colors" />
                                    </div>
                                    <input
                                        type={showPassword ? 'text' : 'password'}
                                        required
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        className="block w-full pl-12 pr-12 py-4 bg-slate-950/50 border border-slate-800/60 rounded-2xl text-white placeholder-slate-600 focus:ring-2 focus:ring-plex-orange/50 focus:border-plex-orange transition-all duration-300 outline-none font-medium"
                                        placeholder="Enter your password"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowPassword(!showPassword)}
                                        className="absolute inset-y-0 right-0 pr-4 flex items-center text-slate-500 hover:text-slate-300 transition-colors"
                                    >
                                        {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                                    </button>
                                </div>
                            </div>

                            {error && (
                                <div className={`flex items-center gap-3 p-4 rounded-2xl animate-in fade-in zoom-in duration-300 border ${error.includes('successfully')
                                    ? 'bg-green-500/10 border-green-500/20 text-green-400'
                                    : 'bg-red-500/10 border-red-500/20 text-red-400'
                                    }`}>
                                    <AlertCircle className="w-5 h-5 shrink-0" />
                                    <p className="text-sm font-medium">{error}</p>
                                </div>
                            )}

                            <button
                                type="submit"
                                disabled={loading}
                                className="w-full flex items-center justify-center gap-3 py-4 bg-gradient-to-r from-plex-orange to-orange-400 text-white font-bold rounded-2xl shadow-xl shadow-orange-950/20 hover:shadow-orange-500/20 hover:scale-[1.02] active:scale-[0.98] transition-all duration-300 disabled:opacity-50 disabled:scale-100 disabled:cursor-not-allowed group"
                            >
                                {loading ? (
                                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                ) : (
                                    <>
                                        <span>Unlock Dashboard</span>
                                        <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                                    </>
                                )}
                            </button>
                        </form>
                    )}
                </div>

                {/* Footer info */}
                <p className="mt-8 text-center text-slate-500 text-sm font-medium">
                    &copy; 2026 ColleXions Manager &bull; v1.1.0
                </p>
            </div>
        </div>
    );
};
