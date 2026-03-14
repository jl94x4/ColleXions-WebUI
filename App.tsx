import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import Layout from './components/Layout';
import { api } from './services/api';
import Dashboard from './pages/Dashboard';
import ConfigPage from './pages/Config';
import LogsPage from './pages/Logs';
import StatsPage from './pages/Stats';
import Creator from './pages/Creator';
import JobsPage from './pages/Jobs';
import Gallery from './pages/Gallery';
import { Login } from './pages/Login';
import Onboarding from './pages/Onboarding';
import { ProtectedRoute } from './components/ProtectedRoute';
import { AuthProvider, useAuth } from './context/AuthContext';

// Wraps all authenticated pages inside the Layout shell
const AppLayout: React.FC = () => (
  <Layout>
    <Outlet />
  </Layout>
);

const AppContent: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const [needsOnboarding, setNeedsOnboarding] = useState<boolean | null>(null);

  useEffect(() => {
    const checkSetup = async () => {
      if (isAuthenticated) {
        try {
          const status = await api.getAuthStatus();
          setNeedsOnboarding(status.needs_onboarding ?? false);
        } catch (e) {
          setNeedsOnboarding(false);
        }
      }
    };
    checkSetup();
  }, [isAuthenticated]);

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/onboarding" element={<Onboarding />} />
        {/* Protected + Layout shell */}
        <Route element={<AppLayout />}>
          <Route index element={
            needsOnboarding === true
              ? <Navigate to="/onboarding" replace />
              : <Dashboard />
          } />
          <Route path="gallery" element={<Gallery />} />
          <Route path="creator" element={<Creator />} />
          <Route path="jobs" element={<JobsPage />} />
          <Route path="stats" element={<StatsPage />} />
          <Route path="config" element={<ConfigPage />} />
          <Route path="logs" element={<LogsPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

const App: React.FC = () => (
  <Router>
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  </Router>
);

export default App;
