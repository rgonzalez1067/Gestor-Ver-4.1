/**
 * Hook RBAC para validar permisos por módulo.
 * Retorna { canView, canEdit, level } según los permisos del usuario actual.
 * - canView: true si el nivel es "read" o "edit"
 * - canEdit: true si el nivel es "edit"
 * - level: "none" | "read" | "edit"
 */
export function usePermission(module) {
  const userStr = localStorage.getItem('user');
  let user = null;
  try { user = userStr ? JSON.parse(userStr) : null; } catch { user = null; }

  // Admin tiene acceso total
  if (user?.role === 'admin') {
    return { canView: true, canEdit: true, level: 'edit' };
  }

  const permissions = user?.permissions || {};
  const level = permissions[module] || 'none';

  return {
    canView: level === 'read' || level === 'edit',
    canEdit: level === 'edit',
    level,
  };
}

/**
 * Mapeo de rutas del frontend a módulos de permisos.
 * Usado por ProtectedRoute y Sidebar para filtrar accesos.
 */
export const ROUTE_MODULE_MAP = {
  '/quotes': 'cotizaciones',
  '/clients': 'clientes',
  '/banks': 'bancos',
  '/medios-pago': 'medios_pago',
  '/hardware': 'dispositivos',
  '/integrators': 'integradores',
  '/settings': 'configuracion',
  '/projects': 'proyectos',
  '/inventory': 'inventarios',
  '/taller-equipos': 'taller_equipos',
  '/new-products': 'nuevos_productos',
};
