import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../services/api';

interface AuthContextType {
    isAuthenticated: boolean;
    isLoading: boolean;
    user: any | null;
    login: (password: string) => Promise<void>;
    logout: () => void;
    checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [user, setUser] = useState<any | null>(null);

    const checkAuth = async () => {
        const token = localStorage.getItem('collexions_token');
        if (!token) {
            setIsAuthenticated(false);
            setIsLoading(false);
            return;
        }

        try {
            const isValid = await api.verifyToken(token);
            if (isValid) {
                setIsAuthenticated(true);
                // We don't have a full user object from this simple auth, but we can set a dummy one
                setUser({ username: 'Admin' });
            } else {
                localStorage.removeItem('collexions_token');
                setIsAuthenticated(false);
            }
        } catch (error) {
            console.error('Auth verification failed:', error);
            setIsAuthenticated(false);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        checkAuth();
    }, []);

    const login = async (password: string) => {
        const data = await api.login(password);
        if (data.token) {
            localStorage.setItem('collexions_token', data.token);
            setIsAuthenticated(true);
            setUser(data.user);
        }
    };

    const logout = () => {
        localStorage.removeItem('collexions_token');
        setIsAuthenticated(false);
        setUser(null);
        window.location.href = '/login';
    };

    return (
        <AuthContext.Provider value={{ isAuthenticated, isLoading, user, login, logout, checkAuth }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};
