import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Toaster } from 'sonner';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Clients from './pages/Clients';
import Banks from './pages/Banks';
import Hardware from './pages/Hardware';
import MediosPago from './pages/MediosPago';
import Integrators from './pages/Integrators';
import Quotes from './pages/Quotes';
import ExchangeRate from './pages/ExchangeRate';
import Settings from './pages/Settings';
import AuthCallback from './components/AuthCallback';
import ProtectedRoute from './components/ProtectedRoute';

function AppRouter() {
  const location = useLocation();
  
  if (location.hash?.includes('session_id=')) {
    return <AuthCallback />;
  }
  
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
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
