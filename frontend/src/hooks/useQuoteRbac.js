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
    // Admin y usuarios SIN ningún permiso de cotizaciones (ej. Admin Pyme /
    // Administración por sede, que el backend ya segmenta) no se filtran aquí.
    if (rbac.isAdm || !rbac.hasAnyCotPerm) {
      return quotes;
    }
    // Gobierno de Datos (Feb 2026): la categoría Implementación se segmenta por
    // SEGMENTO Pyme/Corp según el permiso del usuario. Un Ejecutivo Corp solo
    // ve cotizaciones de Implementación Corp y un Pyme solo Pyme — evita el
    // cruce de cartera entre las fuerzas de venta. Excepciones (Admin Pyme,
    // Operaciones) se manejan arriba o por categoría.
    return quotes.filter(q => {
      const cat = q.quote_category;
      const seg = (q.client_segment || q.sede || 'PYME').toString().toUpperCase();
      if (cat === 'implementation') {
        return seg === 'CORP' ? rbac.hasImplCorp : rbac.hasImplPyme;
      }
      // Fast Track (MPOS Imple+POS): es siempre PYME. Visible con impl_pyme o
      // por Operaciones (lectura sobre MPOS PYME para la fase técnica).
      if (cat === 'fast_track') {
        return rbac.hasImplPyme || rbac.isOpsReadonly;
      }
      if (cat === 'equipment') return rbac.hasEquipos;
      if (cat === 'repair') return rbac.hasReparaciones;
      return false;
    });
  }, [quotes, rbac]);

  return { rbac, rbacFilteredQuotes };
}
