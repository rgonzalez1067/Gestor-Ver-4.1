/**
 * Hook RBAC para validar permisos por módulo.
 * Retorna { canView, canEdit, canCreate, level } según los permisos del usuario actual.
 * - canView: true si el nivel es "read" o "edit" Y el grupo padre del módulo está activo
 * - canEdit: true si el nivel es "edit" Y el grupo padre está activo
 * - canCreate: true si canEdit O tiene special_permission "modulo:create"
 * - level: "none" | "read" | "edit"
 * - hasSpecial(flag): helper para consultar cualquier flag especial.
 * - groupActive: true si el grupo padre del módulo está activo.
 */
export function usePermission(module) {
  const userStr = localStorage.getItem('user');
  let user = null;
  try { user = userStr ? JSON.parse(userStr) : null; } catch { user = null; }

  const specialPerms = user?.special_permissions || [];
  const hasSpecial = (flag) => specialPerms.includes(flag);

  // Admin tiene acceso total
  if (user?.role === 'admin') {
    return {
      canView: true, canEdit: true, canCreate: true,
      level: 'edit', user, hasSpecial, groupActive: true,
      isAdmin: true,
    };
  }

  const permissions = user?.permissions || {};
  const level = permissions[module] || 'none';
  const menuGroups = user?.menu_groups || {};
  const groupId = MODULE_TO_GROUP[module];
  // Si el usuario no tiene menu_groups aún (legacy), se consideran activos.
  const groupActive = groupId
    ? (Object.keys(menuGroups).length === 0 ? true : !!menuGroups[groupId])
    : true;

  const hasCreateOverride = hasSpecial(`${module}:create`);

  return {
    canView: groupActive && (level === 'read' || level === 'edit'),
    canEdit: groupActive && level === 'edit',
    canCreate: groupActive && (level === 'edit' || hasCreateOverride),
    level,
    user,
    hasSpecial,
    groupActive,
    isAdmin: false,
  };
}

/**
 * Mapeo de rutas del frontend a módulos de permisos.
 * Usado por ProtectedRoute y Sidebar para filtrar accesos.
 */
export const ROUTE_MODULE_MAP = {
  '/initial-contacts': 'initial_contacts',
  '/quotes': 'cotizaciones',
  '/reports/sales': 'reportes_ventas',
  '/reports/sponsors': 'reportes_patrocinador',
  '/historical-quotes': 'quote_history',
  '/clients': 'clientes',
  '/banks': 'bancos',
  '/medios-pago': 'medios_pago',
  '/hardware': 'dispositivos',
  '/commercial-categories': 'commercial_categories',
  '/exchange-rate': 'exchange_rate',
  '/integrators': 'integradores',
  '/datos-imple': 'datos_imple',
  '/condiciones-banco-mediopago': 'condiciones_banco_mediopago',
  '/settings': 'configuracion',
  '/projects': 'proyectos',
  '/direct-projects': 'proyectos_directos',
  '/inventory': 'inventarios',
  '/inventory/accounting-report': 'reportes_contables',
  '/inventory/asset-ledger': 'reportes_contables',
  '/inventory/invoiced-exits': 'reportes_contables',
  '/taller-equipos': 'taller_equipos',
  '/taller-recepcion': 'taller_recepcion',
  '/new-products': 'nuevos_productos',
};

/**
 * Mapeo de módulo -> grupo principal (Nivel 1).
 * Debe permanecer sincronizado con /app/backend/permissions_catalog.py (MODULE_TO_GROUP).
 */
export const MODULE_TO_GROUP = {
  initial_contacts: 'gestion_comercial',
  clientes: 'gestion_comercial',
  cotizaciones: 'gestion_comercial',
  reportes_ventas: 'gestion_comercial',
  quote_history: 'gestion_comercial',
  bancos: 'catalogos',
  medios_pago: 'catalogos',
  dispositivos: 'catalogos',
  commercial_categories: 'catalogos',
  exchange_rate: 'catalogos',
  proyectos: 'gestion_implementacion',
  proyectos_directos: 'gestion_implementacion',
  integradores: 'gestion_implementacion',
  datos_imple: 'gestion_implementacion',
  condiciones_banco_mediopago: 'gestion_implementacion',
  nuevos_productos: 'nuevos_productos',
  inventarios: 'gestion_administrativa',
  reportes_contables: 'gestion_administrativa',
  taller_equipos: 'gestion_taller',
  taller_recepcion: 'gestion_taller',
  configuracion: 'gestion_administrativa',
  dashboard: 'dashboard',
};

/**
 * Helper: verifica si un grupo del sidebar está activo para el usuario logueado.
 */
export function isGroupActive(groupId) {
  const userStr = localStorage.getItem('user');
  let user = null;
  try { user = userStr ? JSON.parse(userStr) : null; } catch { user = null; }
  if (user?.role === 'admin') return true;
  const groups = user?.menu_groups || {};
  // Legacy fallback: si no tiene groups (usuario viejo), todos activos.
  if (Object.keys(groups).length === 0) return true;
  return !!groups[groupId];
}
