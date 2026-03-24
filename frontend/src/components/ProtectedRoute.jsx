import { Navigate, useLocation } from "react-router-dom";
import { ROUTE_MODULE_MAP } from "../hooks/usePermission";

export const ProtectedRoute = ({ children }) => {
  const token = localStorage.getItem("session_token");
  const location = useLocation();

  if (!token) {
    return <Navigate to="/" replace />;
  }

  // Determinar módulo según la ruta actual
  const pathBase = '/' + (location.pathname.split('/')[1] || '');
  const module = ROUTE_MODULE_MAP[pathBase];

  // Validar permiso sin hook (lectura directa de localStorage)
  if (module) {
    let user = null;
    try { user = JSON.parse(localStorage.getItem('user')); } catch {}
    if (user?.role !== 'admin') {
      const level = user?.permissions?.[module] || 'none';
      if (level === 'none') {
        return <Navigate to="/quotes" replace />;
      }
    }
  }

  return children;
};

export default ProtectedRoute;
