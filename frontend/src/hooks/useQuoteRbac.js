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
    const showButtons = canEdit && (isAdm || hasAnyImpl || hasEquipos || hasReparaciones);
    return { hasImplPyme, hasImplCorp, hasEquipos, hasReparaciones, hasAnyImpl, hasAnyCotPerm, showButtons, isAdm };
  }, [currentUser, canEdit]);

  const rbacFilteredQuotes = useMemo(() => {
    if (rbac.isAdm || !rbac.hasAnyCotPerm) return quotes;
    const allowed = [];
    if (rbac.hasImplPyme || rbac.hasImplCorp) allowed.push('implementation', 'fast_track');
    if (rbac.hasEquipos) allowed.push('equipment');
    if (rbac.hasReparaciones) allowed.push('repair');
    return quotes.filter(q => allowed.includes(q.quote_category));
  }, [quotes, rbac]);

  return { rbac, rbacFilteredQuotes };
}
