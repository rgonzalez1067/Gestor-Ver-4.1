import { useMemo } from 'react';

/**
 * Calcula los flags de RBAC de Cotizaciones a partir del usuario actual y
 * filtra el listado de quotes según los permisos especiales.
 *
 * Permisos reconocidos:
 *  - cotizaciones:impl_pyme
 *  - cotizaciones:impl_corp
 *  - cotizaciones:equipos
 *  - cotizaciones:reparaciones
 */
export function useQuoteRbac({ currentUser, canEdit, quotes }) {
  const rbac = useMemo(() => {
    const sp = currentUser?.special_permissions || [];
    const isAdm = currentUser?.role === 'admin';
    const hasImplPyme = isAdm || sp.includes('cotizaciones:impl_pyme');
    const hasImplCorp = isAdm || sp.includes('cotizaciones:impl_corp');
    const hasEquipos = isAdm || sp.includes('cotizaciones:equipos');
    const hasReparaciones = isAdm || sp.includes('cotizaciones:reparaciones');
    const hasAnyImpl = hasImplPyme || hasImplCorp;
    const hasAnyCotPerm = sp.some(p => p.startsWith('cotizaciones:'));
    // Departamento Operaciones (Feb 2026): lectura sobre MPOS PYME + acción
    // EXCLUSIVA "Configuración". Si el usuario es admin, no aplica el modo.
    const depto = ((currentUser?.departamento) || '').trim().toLowerCase();
    const isOpsReadonly = !isAdm && depto === 'operaciones';
    // showButtons activa la columna de acciones cuando el usuario tiene
    // CUALQUIER tipo de facultad operativa (incluido Operaciones para Configurar).
    const showButtons = (canEdit && (isAdm || hasAnyImpl || hasEquipos || hasReparaciones)) || isOpsReadonly;
    return { hasImplPyme, hasImplCorp, hasEquipos, hasReparaciones, hasAnyImpl, hasAnyCotPerm, showButtons, isAdm, isOpsReadonly };
  }, [currentUser, canEdit]);

  const rbacFilteredQuotes = useMemo(() => {
    if (rbac.isAdm || !rbac.hasAnyCotPerm) {
      return quotes;
    }
    const allowed = [];
    if (rbac.hasImplPyme || rbac.hasImplCorp) allowed.push('implementation', 'fast_track');
    if (rbac.hasEquipos) allowed.push('equipment');
    if (rbac.hasReparaciones) allowed.push('repair');
    // Operaciones (Feb 2026): la sede tiene acceso de lectura sobre MPOS PYME
    // aunque su perfil no incluya `cotizaciones:impl_pyme`. Sin esta excepción
    // el filtro descartaba las cotizaciones `fast_track` que el backend ya
    // había incluido en su scope, dejando al usuario "ciego" en esa categoría.
    if (rbac.isOpsReadonly && !allowed.includes('fast_track')) {
      allowed.push('fast_track');
    }
    return quotes.filter(q => allowed.includes(q.quote_category));
  }, [quotes, rbac]);

  return { rbac, rbacFilteredQuotes };
}
