import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { AdminLayout } from './components/AdminLayout';
import { Home } from './pages/Home';
import { EventDetail } from './pages/EventDetail';

import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { Profile } from './pages/Profile';
import { AdminDashboard } from './pages/admin/Dashboard';
import { AdminSources } from './pages/admin/Sources';
import { AdminArticles } from './pages/admin/Articles';
import { AdminEvents } from './pages/admin/Events';
import { AdminEventManage } from './pages/admin/EventManage';
import { AdminSettings } from './pages/admin/Settings';
import { PipelineViz } from './pages/admin/PipelineViz';
import { PipelineLog } from './pages/admin/PipelineLog';
import { useAuth } from './stores/auth';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const auth = useAuth();
  if (!auth.token) return <Navigate to="/login" />;
  return <>{children}</>;
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const auth = useAuth();
  if (!auth.token) return <Navigate to="/login" />;
  if (auth.role !== 'admin') return <Navigate to="/" />;
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Home />} />
          <Route path="/event/:id" element={<EventDetail />} />

          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />
        </Route>
        <Route path="/admin" element={<AdminRoute><AdminLayout /></AdminRoute>}>
          <Route index element={<AdminDashboard />} />
          <Route path="pipeline" element={<PipelineViz />} />
          <Route path="logs" element={<PipelineLog />} />
          <Route path="sources" element={<AdminSources />} />
          <Route path="articles" element={<AdminArticles />} />
          <Route path="events" element={<AdminEvents />} />
          <Route path="manage" element={<AdminEventManage />} />
          <Route path="settings" element={<AdminSettings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
