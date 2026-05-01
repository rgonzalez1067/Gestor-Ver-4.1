import { Navigate, useLocation } from "react-router-dom";
import { ROUTE_MODULE_MAP } from "../hooks/usePermission";

export const ProtectedRoute = ({ children }) => {
  const token = localStorage.getItem("session_token");
  const location = useLocation();

  if (!token) {
    return <Navigate to="/login" replace />;
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
        // Fallback siempre accesible: /dashboard no está en ROUTE_MODULE_MAP,
        // por lo que cualquier usuario autenticado puede entrar y evita el
        // bucle infinito de redirección que dejaba la app en blanco cuando
        // un módulo (ej. Cotizaciones) estaba inactivo.
        return <Navigate to="/dashboard" replace />;
      }
    }
  }

  return children;
};

export default ProtectedRoute;
