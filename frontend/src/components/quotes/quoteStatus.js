// Lógica compartida de estatus y filtrado de cotizaciones.
// Se usa tanto en la grilla (QuotesTable) como en las tarjetas de KPI
// (QuotesKpiCards) para garantizar que los contadores de los KPIs coincidan
// EXACTAMENTE con las filas visibles al aplicar el filtro de estado.

// Estatus efectivo (estado real más avanzado del flujo) calculado a partir de
// los timestamps del documento. Prioridad (de más avanzado a menos):
//   Entregada > Implementada > Validar Pago > Pagada > Facturada > Reparada >
//   Configurada > Preasign > Aprobada > Enviada > quote_status (fallback)
// Los estados FINANCIEROS (Validar Pago / Pagada / Facturada) tienen prioridad
// sobre 'Reparada': una reparación que avanzó a facturación/cobro refleja su
// estatus financiero real.
export function getEffectiveStatus(q) {
  if (q.delivered_at) return 'Entregada';
  if (q.implementation_completed_at) return 'Implementada';
  const ex = q.custom_actions_executed || {};
  if (ex.pago_validado || ex.pago_validado_eq || ex.pago_validado_rep) return 'Validar Pago';
  if (q.paid_at) return 'Pagada';
  if (q.invoice_number || q.invoiced_at) return 'Facturada';
  if (q.repaired_at) return 'Reparada';
  if (q.configured_at) return 'Configurada';
  if (q.preassigned_at || (q.preassigned_serials && q.preassigned_serials.length > 0)) return 'Preasign';
  if (q.approved_at) return 'Aprobada';
  if (q.sent_at) return 'Enviada';
  return q.quote_status || 'Borrador';
}

// Predicado de filtrado de la grilla. `includeStatus=false` omite el filtro de
// estado (usado por los KPIs para que cada tarjeta cuente el universo por
// período/categoría/segmento/cliente y coincida con la grilla al filtrar por
// ese estado).
export function quoteMatchesFilters(quote, filters, { includeStatus = true } = {}) {
  const {
    filterClient, filterStatus, filterCategory,
    filterSegment, filterDateFrom, filterDateTo,
  } = filters;

  if (filterClient && filterClient !== 'all') {
    const allowedIds = filterClient.split(',');
    if (!allowedIds.includes(quote.client_id)) return false;
  }
  if (includeStatus && filterStatus && filterStatus !== 'all' && getEffectiveStatus(quote) !== filterStatus) return false;
  if (filterCategory && filterCategory !== 'all') {
    const cat = quote.quote_category || 'implementation';
    const [baseCat, subType, variant] = filterCategory.split(':');
    if (subType === 'FAST_TRACK') {
      const qt = (quote.quote_type || '').toUpperCase();
      if (cat !== 'fast_track' && !(cat === 'implementation' && qt === 'FAST_TRACK')) return false;
    } else if (baseCat === 'implementation' && !subType) {
      if (cat !== 'implementation' && cat !== 'fast_track') return false;
    } else {
      if (baseCat !== cat) return false;
      if (subType) {
        const qt = (quote.quote_type || '').toUpperCase();
        if (qt !== subType.toUpperCase()) return false;
      }
      // Sub-sub filtro por variante de Link de Pago (link_pago / tokenizador / ambos)
      if (variant) {
        const qv = String(quote.link_pago_variant || 'link_pago').toLowerCase();
        if (qv !== variant.toLowerCase()) return false;
      }
    }
  }
  if (filterSegment && filterSegment !== 'all' && (quote.client_segment || 'PYME') !== filterSegment) return false;
  if (filterDateFrom) {
    const fromDate = new Date(filterDateFrom + 'T00:00:00');
    if (new Date(quote.created_at) < fromDate) return false;
  }
  if (filterDateTo) {
    const toDate = new Date(filterDateTo + 'T23:59:59.999');
    if (new Date(quote.created_at) > toDate) return false;
  }
  return true;
}
