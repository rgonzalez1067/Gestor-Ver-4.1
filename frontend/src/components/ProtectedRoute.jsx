import { Navigate, useLocation } from "react-router-dom";
import { usePermission, ROUTE_MODULE_MAP } from "../hooks/usePermission";

export const ProtectedRoute = ({ children }) => {
  const token = localStorage.getItem("session_token");
  const location = useLocation();

  if (!token) {
    return <Navigate to="/" replace />;
  }

  // Determinar módulo según la ruta actual
  const pathBase = '/' + (location.pathname.split('/')[1] || '');
  const module = ROUTE_MODULE_MAP[pathBase];

  // Si hay módulo mapeado, validar permiso
  if (module) {
    const { canView } = usePermission(module);
    if (!canView) {
      return <Navigate to="/quotes" replace />;
    }
  }

  return children;
};

export default ProtectedRoute;
