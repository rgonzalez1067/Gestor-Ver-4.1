import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Toaster } from 'sonner';
import Auth from './pages/Auth';
import Login from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { Clients } from './pages/Clients';
import Banks from './pages/Banks';
import BankDetail from './pages/BankDetail';
import IntegrationReport from './pages/IntegrationReport';
import Hardware from './pages/Hardware';
import MediosPago from './pages/MediosPago';
import Integrators from './pages/Integrators';
import Quotes from './pages/Quotes';
import ExchangeRate from './pages/ExchangeRate';
import Settings from './pages/Settings';
import AdminUsers from './pages/AdminUsers';
import UserManagement from './pages/UserManagement';
import Projects from './pages/Projects';
import ProjectDetail from './pages/ProjectDetail';
import NewProducts from './pages/NewProducts';
import Inventory from './pages/Inventory';
import TallerEquipos from './pages/TallerEquipos';
import AuthCallback from './components/AuthCallback';
import ProtectedRoute from './components/ProtectedRoute';

function AppRouter() {
  const location = useLocation();
  
  if (location.hash?.includes('session_id=')) {
    return <AuthCallback />;
  }
  
  return (
    <Routes>
      <Route path="/login" element={<Auth />} />
      <Route path="/login-google" element={<Login />} />
      <Route path="/dashboard" element={
        <ProtectedRoute>
          <Dashboard />
        </ProtectedRoute>
      } />
      <Route path="/clients" element={
        <ProtectedRoute>
          <Clients />
        </ProtectedRoute>
      } />
      <Route path="/banks" element={
        <ProtectedRoute>
          <Banks />
        </ProtectedRoute>
      } />
      <Route path="/banks/integrations/report" element={
        <ProtectedRoute>
          <IntegrationReport />
        </ProtectedRoute>
      } />
      <Route path="/banks/:bankId" element={
        <ProtectedRoute>
          <BankDetail />
        </ProtectedRoute>
      } />
      <Route path="/hardware" element={
        <ProtectedRoute>
          <Hardware />
        </ProtectedRoute>
      } />
      <Route path="/medios-pago" element={
        <ProtectedRoute>
          <MediosPago />
        </ProtectedRoute>
      } />
      <Route path="/integrators" element={
        <ProtectedRoute>
          <Integrators />
        </ProtectedRoute>
      } />
      <Route path="/quotes" element={
        <ProtectedRoute>
          <Quotes />
        </ProtectedRoute>
      } />
      <Route path="/projects" element={
        <ProtectedRoute>
          <Projects />
        </ProtectedRoute>
      } />
      <Route path="/projects/:projectId" element={
        <ProtectedRoute>
          <ProjectDetail />
        </ProtectedRoute>
      } />
      <Route path="/new-products" element={
        <ProtectedRoute>
          <NewProducts />
        </ProtectedRoute>
      } />
      <Route path="/inventory" element={
        <ProtectedRoute>
          <Inventory />
        </ProtectedRoute>
      } />
      <Route path="/taller-equipos" element={
        <ProtectedRoute>
          <TallerEquipos />
        </ProtectedRoute>
      } />
      <Route path="/exchange-rate" element={
        <ProtectedRoute>
          <ExchangeRate />
        </ProtectedRoute>
      } />
      <Route path="/settings" element={
        <ProtectedRoute>
          <Settings />
        </ProtectedRoute>
      } />
      <Route path="/admin/users" element={
        <ProtectedRoute>
          <AdminUsers />
        </ProtectedRoute>
      } />
      <Route path="/users" element={
        <ProtectedRoute>
          <UserManagement />
        </ProtectedRoute>
      } />
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AppRouter />
      </BrowserRouter>
      <Toaster position="top-right" richColors />
    </div>
  );
}

export default App;
