import { useEffect } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { ROUTE_MODULE_MAP } from "../hooks/usePermission";
import api from "../utils/api";

// Refresca `localStorage.user` desde el backend UNA vez por carga de la app.
// Evita que tras un deploy el usuario quede con datos viejos en caché del
// navegador (user_id/permissions/email), lo que rompía la visibilidad de
// acciones del Override sin necesidad de limpiar caché ni reiniciar el server.
let _userRefreshed = false;

export const ProtectedRoute = ({ children }) => {
  const token = localStorage.getItem("session_token");
  const location = useLocation();

  useEffect(() => {
    if (token && !_userRefreshed) {
      _userRefreshed = true;
      api.get('/auth/me')
        .then((res) => { if (res?.data) localStorage.setItem('user', JSON.stringify(res.data)); })
        .catch(() => { _userRefreshed = false; });
    }
  }, [token]);

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
