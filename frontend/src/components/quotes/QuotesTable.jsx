import { FileText, Search, X, FolderOpen, MoreHorizontal, RefreshCw, Mail, CheckCircle, Receipt, Banknote, Truck, Send, Trash2, Eye, Wrench, Settings, Package, Landmark, Sparkles } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import { Button } from '../ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '../ui/popover';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '../ui/dropdown-menu';
import QuoteStatusStepper from './QuoteStatusStepper';

import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip';

const STATUS_COLORS = {
  'Borrador': 'bg-slate-100 text-slate-600',
  'Enviada': 'bg-blue-100 text-blue-600',
  'Aprobada': 'bg-green-100 text-green-600',
  'Reparada': 'bg-cyan-100 text-cyan-700',
  'Configurada': 'bg-indigo-100 text-indigo-700',
  'Facturada': 'bg-purple-100 text-purple-600',
  'Pagada': 'bg-emerald-100 text-emerald-700',
  'Entregada': 'bg-teal-100 text-teal-700',
  'Enviada a Imple': 'bg-amber-100 text-amber-700',
};

const STATUS_DISPLAY_NAMES = {
  'Borrador': 'Borrador',
  'Enviada': 'Enviada',
  'Aprobada': 'Aprobada',
  'Reparada': 'Reparada',
  'Configurada': 'Configurada',
  'Facturada': 'Facturada',
  'Pagada': 'Pagada',
  'Entregada': 'Entregada',
  'Enviada a Imple': 'En Implementación',
};

const getQuoteTypeName = (type) => {
  const map = { 'VPOS': 'VPOS', 'MPOS': 'MPOS', 'VPOS_MPOS': 'VPOS/MPOS', 'GATEWAY': 'Payment Gateway', 'LINK_PAGO': 'Link de Pago' };
  return map[type] || type || 'N/A';
};

export const QuotesTable = ({
  quotes, clients,
  filterClient, filterStatus, filterCategory, filterSegment, filterDateFrom, filterDateTo,
  actionLoading, canEdit,
  highlightedQuoteNumber,
  onOpenAnexos, onEditQuote, onSendToClient,
  onApprove, onInvoice, onCollect, onDeliver, onSendToImplementation, onRepairComplete, onConfigure, onDelete,
  onOpenBitacoraFlujo, onOpenFtConfig, onPreassignSerials,
  actionOverrides = {}, customActions = [], currentUserId = '', currentUserCargo = '', currentUserRole = '', onCustomAction,
  opsReadonly = false,
  clearFilters,
}) => {
  // Helper: mapea quote → (biz_type, sub_cat) para resolver overrides.
  const resolveBizSub = (q) => {
    const cat = q.quote_category;
    if (cat === 'equipment') return { biz: 'equipos', sub: null };
    if (cat === 'repair') return { biz: 'reparaciones', sub: null };
    const sede = (q.sede || q.client_segment || 'PYME').toUpperCase();
    const biz = sede === 'CORP' ? 'implementacion_corp' : 'implementacion_pyme';
    // Fast Track (MPOS Imple+POS) — siempre mpos_imple_pos para coincidir con
    // el catálogo del Motor de Notificaciones, sin importar quote_type
    // (puede venir como "FAST_TRACK" o "MPOS" según versión).
    if (cat === 'fast_track') return { biz, sub: 'mpos_imple_pos' };
    let sub = null;
    const qt = (q.quote_type || '').toUpperCase();
    if (qt === 'VPOS') sub = 'vpos';
    else if (qt === 'GATEWAY') sub = 'payment_gateway';
    else if (qt === 'LINK_PAGO') sub = 'link_pago';
    else if (qt === 'MPOS') sub = (q.sub_quote_type === 'IMPLE_POS') ? 'mpos_imple_pos' : 'mpos_tablet';
    return { biz, sub };
  };

  // Helper: aplica override a (quote, action_id) → { label, hidden, disabled, tooltip }
  const getActionMeta = (quote, actionId, defaultLabel) => {
    const { biz, sub } = resolveBizSub(quote);
    const ov = actionOverrides[`${biz}|${sub || '_'}|${actionId}`] || actionOverrides[`${biz}|_|${actionId}`];
    if (!ov) return { label: defaultLabel, hidden: false, disabled: false, tooltip: null };
    if (!ov.enabled) return { label: ov.custom_label || defaultLabel, hidden: true, disabled: true, tooltip: 'Acción desactivada' };
    const isAdmin = (currentUserRole || '').toLowerCase() === 'admin';
    const allowedUserIds = ov.allowed_user_ids || [];
    if (allowedUserIds.length && !isAdmin && !allowedUserIds.includes(currentUserId)) {
      return { label: ov.custom_label || defaultLabel, hidden: false, disabled: true, tooltip: 'No autorizado para esta acción' };
    }
    // Fallback legacy: algunos overrides viejos pueden tener required_cargos
    const cargosReq = ov.required_cargos || [];
    if (!allowedUserIds.length && cargosReq.length && !isAdmin && !cargosReq.includes(currentUserCargo)) {
      return { label: ov.custom_label || defaultLabel, hidden: false, disabled: true, tooltip: `Solo cargos: ${cargosReq.join(', ')}` };
    }
    return { label: ov.custom_label || defaultLabel, hidden: false, disabled: false, tooltip: null };
  };

  // Helper: lista de acciones custom EJECUTABLES por el usuario actual
  // (filtra por allowed_user_ids/required_cargos). Se usa para el dropdown
  // de acciones donde el usuario realmente puede disparar la acción.
  const getCustomActionsFor = (quote) => {
    const { biz, sub } = resolveBizSub(quote);
    const isAdmin = (currentUserRole || '').toLowerCase() === 'admin';
    return customActions.filter((ca) => {
      if (!ca.enabled) return false;
      if (ca.business_type !== biz) return false;
      if (ca.product_subcategory && ca.product_subcategory !== sub) return false;
      const allowedUserIds = ca.allowed_user_ids || [];
      if (allowedUserIds.length) {
        if (!isAdmin && !allowedUserIds.includes(currentUserId)) return false;
        return true;
      }
      // Fallback legacy
      const cargosReq = ca.required_cargos || [];
      if (cargosReq.length && !isAdmin && !cargosReq.includes(currentUserCargo)) return false;
      return true;
    });
  };

  // Helper: lista de acciones custom VISIBLES en el stepper para trazabilidad.
  // Feb 2026 — Requerimiento: las acciones personalizadas asignadas a un usuario
  // específico NO deben desaparecer de la grilla para el resto del equipo.
  // Los demás usuarios pierden la facultad de ejecutarlas (no aparecen en su
  // dropdown) pero conservan visibilidad del estado actual en el stepper.
  // Por eso este filtro IGNORA allowed_user_ids/required_cargos — solo aplica
  // criterios de aplicabilidad por tipo de negocio/subcategoría.
  const getCustomActionsForVisualization = (quote) => {
    const { biz, sub } = resolveBizSub(quote);
    return customActions.filter((ca) => {
      if (!ca.enabled) return false;
      if (ca.business_type !== biz) return false;
      if (ca.product_subcategory && ca.product_subcategory !== sub) return false;
      return true;
    });
  };

  // Agrupa las custom actions aplicables por su "ancla" (position_after).
  // Las que no tienen position_after van al bucket '__end__' y se muestran
  // al final en la sección "Personalizadas".
  const getCustomActionsByAnchor = (quote) => {
    const cas = getCustomActionsFor(quote);
    const byAnchor = {};
    for (const ca of cas) {
      const anchor = ca.position_after || '__end__';
      if (!byAnchor[anchor]) byAnchor[anchor] = [];
      byAnchor[anchor].push(ca);
    }
    return byAnchor;
  };

  // Renderiza las custom actions ancladas a un legacy action_id (inline).
  const renderAnchoredCustomActions = (quote, anchorId, byAnchor) => {
    const items = byAnchor[anchorId];
    if (!items || !items.length) return null;
    return items.map((ca) => (
      <DropdownMenuItem
        key={ca.action_id}
        onSelect={() => onCustomAction?.(quote.quote_id, ca.action_id, ca.label)}
        className="cursor-pointer"
        data-testid={`custom-action-${ca.action_id}-${quote.quote_id}`}
        title={ca.description || null}
      >
        <Sparkles size={16} className="mr-2 text-violet-500" /> {ca.label}
      </DropdownMenuItem>
    ));
  };

  // Estatus efectivo (estado real más avanzado del flujo) calculado a partir
  // de los timestamps de cada fase. Resuelve el caso de cotizaciones
  // facturadas via "regularización" cuyo `quote_status` no avanzó a
  // "Facturada" (se quedó en "Aprobada"). El filtro y la grilla usan este
  // valor calculado para reflejar el estatus instantáneo real del registro.
  //
  // Orden de prioridad (de más avanzado a menos):
  //   Entregada > Reparada > Implementada >
  //   Validar Pago (custom action post-Cobrar) > Pagada > Facturada >
  //   Configurada > Preasign > Aprobada > Enviada > quote_status (fallback)
  //
  // NOTA Validar Pago (Feb 2026): la acción `pago_validado*` se ejecuta
  // OPERATIVAMENTE DESPUÉS de "Cobrar" (paid_at) como una validación
  // financiera adicional del pago. Por eso se considera un estado MÁS
  // avanzado que Pagada — un quote con paid_at+pago_validado está
  // "en Validar Pago", no "en Pagada".
  const getEffectiveStatus = (q) => {
    if (q.delivered_at) return 'Entregada';
    if (q.repaired_at) return 'Reparada';
    if (q.implementation_completed_at) return 'Implementada';
    // "Validar Pago": custom_action ejecutada (pago_validado / *_eq / *_rep).
    // Está DESPUÉS de Pagada porque la validación bancaria ocurre tras
    // el cobro. Si existe la marca, el estado actual es Validar Pago aunque
    // paid_at también esté presente.
    const ex = q.custom_actions_executed || {};
    if (ex.pago_validado || ex.pago_validado_eq || ex.pago_validado_rep) return 'Validar Pago';
    if (q.paid_at) return 'Pagada';
    if (q.invoice_number || q.invoiced_at) return 'Facturada';
    if (q.configured_at) return 'Configurada';
    // "Preasign": seriales reservados (preasignados) pero aún sin Configuración técnica.
    // Aplica al flujo MPOS (fast_track) entre Aprobada y Configurada.
    if (q.preassigned_at || (q.preassigned_serials && q.preassigned_serials.length > 0)) return 'Preasign';
    if (q.approved_at) return 'Aprobada';
    if (q.sent_at) return 'Enviada';
    return q.quote_status || 'Borrador';
  };

  const filteredQuotes = quotes.filter(quote => {
    if (filterClient && filterClient !== 'all') {
      // Soporta multi-id (varios client_id agrupados por nombre, separados por coma)
      // para que cuando el usuario filtra por un cliente con duplicados en BD,
      // se traigan las cotizaciones de TODOS sus client_id.
      const allowedIds = filterClient.split(',');
      if (!allowedIds.includes(quote.client_id)) return false;
    }
    if (filterStatus && filterStatus !== 'all' && getEffectiveStatus(quote) !== filterStatus) return false;
    if (filterCategory && filterCategory !== 'all') {
      // Categorías: 'implementation' (Implementación), 'equipment', 'repair'.
      // Adicionalmente se admite el sufijo ':<TYPE>' para filtrar dentro de
      // Implementación por tipo de cotización (VPOS/MPOS/FAST_TRACK/GATEWAY).
      const cat = quote.quote_category || 'implementation';
      const [baseCat, subType] = filterCategory.split(':');

      // Caso especial: 'implementation:FAST_TRACK' (MPOS Imple+POS) debe
      // coincidir tanto con cotizaciones nuevas (quote_category='fast_track')
      // como con las legacy (quote_category='implementation' + quote_type='FAST_TRACK').
      if (subType === 'FAST_TRACK') {
        const qt = (quote.quote_type || '').toUpperCase();
        if (cat !== 'fast_track' && !(cat === 'implementation' && qt === 'FAST_TRACK')) return false;
      } else if (baseCat === 'implementation' && !subType) {
        // "Implementación (todas)" — incluye TODOS los tipos de implementación,
        // incluidas las MPOS (Imple + POS) que viven en `quote_category='fast_track'`.
        // Antes la condición `baseCat !== cat` dejaba a las fast_track fuera.
        if (cat !== 'implementation' && cat !== 'fast_track') return false;
      } else {
        if (baseCat !== cat) return false;
        if (subType) {
          const qt = (quote.quote_type || '').toUpperCase();
          if (qt !== subType.toUpperCase()) return false;
        }
      }
    }
    if (filterSegment && filterSegment !== 'all' && (quote.client_segment || 'PYME') !== filterSegment) return false;
    if (filterDateFrom) {
      // Interpretar fecha en zona local (no UTC) para evitar pérdida de registros
      // por desplazamientos de zona horaria. "Desde" → inicio del día local.
      const fromDate = new Date(filterDateFrom + 'T00:00:00');
      if (new Date(quote.created_at) < fromDate) return false;
    }
    if (filterDateTo) {
      // "Hasta" → fin del día local (23:59:59.999) para que sea inclusivo:
      // un quote creado a las 18:00 del 15-ene SIEMPRE entra cuando se filtra "hasta 15-ene".
      const toDate = new Date(filterDateTo + 'T23:59:59.999');
      if (new Date(quote.created_at) > toDate) return false;
    }
    return true;
  });

  // === Doble scrollbar sincronizado (arriba + abajo) ===
  // Necesario porque la tabla es muy ancha (min-w-[1200px]) y el usuario tiene
  // que llegar al final de la lista para encontrar el scrollbar inferior.
  // El scrollbar superior es un div delgado con un spacer del mismo ancho
  // que la tabla, y los listeners onScroll sincronizan ambos sin loop.
  const topScrollRef = useRef(null);
  const bottomScrollRef = useRef(null);
  const [tableScrollWidth, setTableScrollWidth] = useState(0);
  const syncingRef = useRef(false);

  // Recalcular ancho del scroll cuando cambian filas (al filtrar/recargar)
  useEffect(() => {
    if (bottomScrollRef.current) {
      setTableScrollWidth(bottomScrollRef.current.scrollWidth);
    }
  }, [quotes, filterClient, filterStatus, filterCategory, filterSegment]);

  const onTopScroll = (e) => {
    if (syncingRef.current) return;
    syncingRef.current = true;
    if (bottomScrollRef.current) bottomScrollRef.current.scrollLeft = e.target.scrollLeft;
    requestAnimationFrame(() => { syncingRef.current = false; });
  };
  const onBottomScroll = (e) => {
    if (syncingRef.current) return;
    syncingRef.current = true;
    if (topScrollRef.current) topScrollRef.current.scrollLeft = e.target.scrollLeft;
    requestAnimationFrame(() => { syncingRef.current = false; });
  };

  return (
    <div className="bg-white rounded-lg border border-slate-200">
      {/* Scrollbar superior — espejo del inferior */}
      <div
        ref={topScrollRef}
        onScroll={onTopScroll}
        className="overflow-x-auto overflow-y-hidden border-b border-slate-100"
        style={{ height: '14px' }}
        data-testid="quotes-table-top-scrollbar"
      >
        <div style={{ width: tableScrollWidth || 1200, height: '1px' }} />
      </div>
      {/* Tabla con scrollbar inferior nativo */}
      <div ref={bottomScrollRef} onScroll={onBottomScroll} className="overflow-x-auto">
      <table className="w-full min-w-[1200px]" data-testid="quotes-unified-table">
        <thead className="bg-slate-50 border-b border-slate-200">
          <tr>
            <th className="px-3 py-4 text-left text-xs font-medium text-slate-700 uppercase sticky left-0 bg-slate-50 z-20 border-r-2 border-slate-200" style={{minWidth: '140px'}}>Número</th>
            <th className="px-3 py-4 text-left text-xs font-medium text-slate-700 uppercase">Categoría</th>
            <th className="px-3 py-4 text-left text-xs font-medium text-slate-700 uppercase">Segmento</th>
            <th className="px-3 py-4 text-left text-xs font-medium text-slate-700 uppercase">Tipo</th>
            <th className="px-3 py-4 text-left text-xs font-medium text-slate-700 uppercase">Cliente</th>
            <th className="px-3 py-4 text-right text-xs font-medium text-slate-700 uppercase whitespace-nowrap">Total USD</th>
            <th className="px-3 py-4 text-left text-xs font-medium text-slate-700 uppercase" style={{minWidth: '220px'}}>Estado</th>
            <th className="px-3 py-4 text-left text-xs font-medium text-slate-700 uppercase">Fecha</th>
            <th className="px-3 py-4 text-center text-xs font-medium text-slate-700 uppercase sticky right-0 bg-slate-50 z-10 shadow-[-4px_0_8px_-4px_rgba(0,0,0,0.08)]">Acciones</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {filteredQuotes.map((quote) => {
            const client = clients.find(c => c.client_id === quote.client_id);
            const statusColor = STATUS_COLORS[quote.quote_status] || STATUS_COLORS['Borrador'];
            const isLoading = actionLoading === quote.quote_id;
            const isEquipment = quote.quote_category === 'equipment';
            const isRepair = quote.quote_category === 'repair';
            const isFastTrack = quote.quote_category === 'fast_track';
            // Modo Operaciones (Feb 2026): solo el botón "Configuración" debe
            // permanecer habilitado para usuarios del Departamento Operaciones.
            // Definimos un canEdit alterno que se aplica a TODO el resto de
            // acciones (Aprobar, Enviar, Facturar, Cobrar, Entregar, etc.).
            const canEditNonConfig = canEdit && !opsReadonly;
            const displayType = isRepair ? 'Reparación' : isFastTrack ? 'MPOS (Imple + POS)' : isEquipment ? (quote.equipment_type || 'Equipos') : getQuoteTypeName(quote.quote_type);
            const categoryColor = isRepair ? 'bg-orange-100 text-orange-700' : isFastTrack ? 'bg-violet-100 text-violet-700' : isEquipment ? 'bg-amber-100 text-amber-700' : 'bg-green-100 text-green-700';
            const typeColor = isEquipment
              ? (quote.equipment_type === 'POS' || quote.equipment_type === 'Pinpad' ? 'bg-blue-100 text-blue-700' : 'bg-amber-100 text-amber-700')
              : 'bg-brand-blue-50 text-brand-blue-600';

            const isHighlighted = highlightedQuoteNumber && quote.quote_number === highlightedQuoteNumber;
            const customByAnchor = getCustomActionsByAnchor(quote);

            return (
              <tr
                key={quote.quote_id}
                className={`hover:bg-slate-50 group transition-colors ${isHighlighted ? 'ring-2 ring-amber-400 bg-amber-50 animate-pulse' : ''}`}
                data-testid={`quote-row-${quote.quote_id}`}
                data-quote-row={quote.quote_number}
              >
                <td className={`px-3 py-4 text-sm font-mono font-medium text-slate-900 whitespace-nowrap sticky left-0 z-10 border-r-2 border-slate-200 ${isHighlighted ? 'bg-amber-50 group-hover:bg-amber-50' : 'bg-white group-hover:bg-slate-50'}`}>{quote.quote_number}</td>
                <td className="px-3 py-4 text-sm">
                  <span className={`px-2 py-1 text-xs font-medium rounded ${categoryColor}`}>
                    {isRepair ? 'Reparaciones' : isFastTrack ? 'MPOS (Imple + POS)' : isEquipment ? 'Equipos' : 'Implementación'}
                  </span>
                </td>
                <td className="px-3 py-4 text-sm">
                  <div className="flex items-center gap-1.5">
                    {quote.client_segment ? (
                      <span className={`px-2 py-1 text-xs font-medium rounded ${
                        quote.client_segment === 'CORP'
                          ? 'bg-blue-100 text-blue-700'
                          : 'bg-emerald-100 text-emerald-700'
                      }`} data-testid={`segment-tag-${quote.quote_id}`}>
                        {quote.client_segment === 'CORP' ? 'Corp' : 'Pyme'}
                      </span>
                    ) : (
                      <span className="text-xs text-slate-400">—</span>
                    )}
                    {quote.sponsored_implementation && (
                      <TooltipProvider delayDuration={200}>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span
                              className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-semibold rounded bg-amber-100 text-amber-800 border border-amber-300 max-w-[140px] truncate cursor-default"
                              data-testid={`sponsored-badge-${quote.quote_id}`}
                            >
                              <Landmark size={11} className="shrink-0" />
                              <span className="truncate">{quote.sponsoring_bank_name || 'Patrocinado'}</span>
                            </span>
                          </TooltipTrigger>
                          <TooltipContent side="top">
                            <p className="text-xs">
                              Patrocinado por {quote.sponsoring_bank_name || 'banco no especificado'}
                            </p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    )}
                    {quote.creator_initials && (
                      <TooltipProvider delayDuration={200}>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span
                              className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-slate-200 text-slate-600 text-[11px] font-bold shrink-0 cursor-default"
                              data-testid={`creator-badge-${quote.quote_id}`}
                            >
                              {quote.creator_initials}
                            </span>
                          </TooltipTrigger>
                          <TooltipContent side="top">
                            <p className="text-xs">{quote.creator_name || 'Usuario'}</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    )}
                  </div>
                </td>
                <td className="px-3 py-4 text-sm">
                  <span className={`px-2 py-1 text-xs font-medium rounded ${typeColor}`}>{displayType}</span>
                </td>
                <td className="px-3 py-4 text-sm text-slate-900">
                  {(() => {
                    // Mostrar Razón Social (legal_name) en la celda. En el
                    // hover mostramos el Nombre de Fantasía como dato
                    // complementario.
                    const legal = client?.legal_name || '';
                    const fantasy = client?.fantasy_name || '';
                    const display = legal || quote.client_name || fantasy || 'N/A';
                    const clientId = quote.client_id;
                    const linkClass = "text-blue-700 hover:text-blue-900 hover:underline cursor-pointer";
                    if (!fantasy) {
                      return clientId ? (
                        <a
                          href={`/clients?open=${clientId}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className={linkClass}
                          data-testid={`quote-client-link-${quote.quote_id}`}
                        >
                          {display}
                        </a>
                      ) : (
                        <span data-testid={`quote-client-${quote.quote_id}`}>{display}</span>
                      );
                    }
                    return (
                      <TooltipProvider delayDuration={200}>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            {clientId ? (
                              <a
                                href={`/clients?open=${clientId}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className={`${linkClass} decoration-dotted underline-offset-2`}
                                data-testid={`quote-client-link-${quote.quote_id}`}
                              >
                                {display}
                              </a>
                            ) : (
                              <span
                                className="cursor-help underline decoration-dotted decoration-slate-300 underline-offset-2 hover:decoration-slate-500"
                                data-testid={`quote-client-${quote.quote_id}`}
                              >
                                {display}
                              </span>
                            )}
                          </TooltipTrigger>
                          <TooltipContent side="top" className="bg-slate-900 text-white text-xs max-w-[280px] border-slate-700">
                            <p className="font-semibold mb-0.5 text-slate-300">Nombre de Fantasía</p>
                            <p className="font-normal">{fantasy}</p>
                            {clientId && <p className="text-[10px] text-blue-300 mt-1">Click para abrir ficha</p>}
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    );
                  })()}
                </td>
                <td className="px-3 py-4 text-right whitespace-nowrap">
                  <span className="text-sm font-mono text-brand-green-600 font-semibold">
                    ${(quote.total_usd || 0).toFixed(2)}
                  </span>
                  <div className="text-[9px] text-slate-400 leading-tight">Inversión Inicial</div>
                </td>
                <td className="px-3 py-4 text-sm">
                  <div className="flex items-center gap-1.5">
                    <QuoteStatusStepper
                      quote={quote}
                      onOpenBitacoraFlujo={onOpenBitacoraFlujo}
                      customActions={getCustomActionsForVisualization(quote)}
                    />
                    {quote.is_irregular && (
                      <Popover>
                        <PopoverTrigger asChild>
                          <button className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[9px] font-bold rounded bg-red-100 text-red-700 border border-red-300 cursor-pointer hover:bg-red-200 transition-colors shrink-0"
                            data-testid={`irregular-badge-${quote.quote_id}`}>
                            Irregular <Eye size={10} />
                          </button>
                        </PopoverTrigger>
                        <PopoverContent className="w-72 p-0" align="start">
                          <div className="bg-red-50 border-b border-red-200 px-3 py-2">
                            <p className="text-xs font-bold text-red-800">Historial de Excepciones</p>
                          </div>
                          <div className="max-h-48 overflow-y-auto p-2 space-y-2">
                            {(quote.irregular_exceptions || []).map((exc, idx) => {
                              const ACTION_NAMES = { approve: 'Aprobación', invoice: 'Factura / Proforma', collect: 'Cobranza', deliver: 'Entregar', 'send-to-implementation': 'Enviar a Imple.', 'repair-deliver': 'Entrega Rep.', 'repair-complete': 'Reparación' };
                              return (
                                <div key={idx} className="border-l-2 border-red-400 pl-2 py-1">
                                  <p className="text-[10px] font-semibold text-red-700">{ACTION_NAMES[exc.action] || exc.action}</p>
                                  <p className="text-[10px] text-slate-700 mt-0.5">{exc.reason}</p>
                                  <div className="flex items-center gap-2 mt-1">
                                    <span className="text-[9px] text-slate-400">{exc.created_at?.slice(0, 10)}</span>
                                    {exc.regularization_date && (
                                      <span className="text-[9px] text-red-500 font-medium">Tope: {exc.regularization_date}</span>
                                    )}
                                  </div>
                                </div>
                              );
                            })}
                            {(!quote.irregular_exceptions || quote.irregular_exceptions.length === 0) && (
                              <p className="text-[10px] text-slate-400 italic py-2 text-center">Sin detalles disponibles</p>
                            )}
                          </div>
                          {onOpenBitacoraFlujo && (
                            <div className="border-t border-red-200 px-3 py-1.5">
                              <button onClick={() => onOpenBitacoraFlujo(quote.quote_id, quote.quote_number)}
                                className="text-[10px] text-red-600 hover:text-red-800 font-medium w-full text-center"
                                data-testid={`open-bitacora-flujo-${quote.quote_id}`}>
                                Ver historial completo
                              </button>
                            </div>
                          )}
                        </PopoverContent>
                      </Popover>
                    )}
                  </div>
                </td>
                <td className="px-3 py-4 text-sm text-slate-600 whitespace-nowrap">{new Date(quote.created_at).toLocaleDateString('es-VE')}</td>
                <td className="px-3 py-4 sticky right-0 bg-white group-hover:bg-slate-50 z-10 shadow-[-4px_0_8px_-4px_rgba(0,0,0,0.08)]">
                  <div className="flex items-center justify-center gap-2">
                    <Button size="sm" variant="outline" onClick={() => onOpenAnexos(quote)}
                      className="text-brand-blue-600" disabled={isLoading}
                      data-testid={`quote-anexos-btn-${quote.quote_id}`}>
                      <FolderOpen size={16} className="mr-1" />Anexos
                    </Button>

                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button size="sm" variant="outline" className="px-2" disabled={isLoading}
                          data-testid={`quote-actions-${quote.quote_id}`}>
                          {isLoading ? (
                            <div className="animate-spin h-4 w-4 border-2 border-slate-400 border-t-transparent rounded-full" />
                          ) : (
                            <MoreHorizontal size={16} />
                          )}
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-56">
                        {canEditNonConfig && <DropdownMenuItem onSelect={() => onEditQuote(quote)} className="cursor-pointer" data-testid={`modify-quote-btn-${quote.quote_id}`}>
                          <RefreshCw size={16} className="mr-2 text-slate-500" /> Modificar Cotización
                        </DropdownMenuItem>}

                        {/* ── FASE COMERCIAL ── */}
                        {canEditNonConfig && <DropdownMenuSeparator />}
                        {canEditNonConfig && (
                          <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400 select-none">Comercial</p>
                        )}
                        {(() => { const m = getActionMeta(quote, 'send_to_client', 'Enviar al Cliente'); return canEditNonConfig && !m.hidden && <DropdownMenuItem onSelect={() => !m.disabled && onSendToClient(quote.quote_id)} disabled={m.disabled} title={m.tooltip} className="cursor-pointer"
                          data-testid={`send-to-client-btn-${quote.quote_id}`}>
                          <Mail size={16} className="mr-2 text-blue-500" /> {m.label}
                          {quote.sent_to_client_at && <span className="ml-auto text-xs text-blue-500">&#10003;</span>}
                        </DropdownMenuItem>; })()}
                        {renderAnchoredCustomActions(quote, 'send_to_client', customByAnchor)}
                        {(() => { const m = getActionMeta(quote, 'approve', 'Aprobación'); return canEditNonConfig && !m.hidden && <DropdownMenuItem onSelect={() => !m.disabled && onApprove(quote.quote_id)} disabled={m.disabled} title={m.tooltip} className="cursor-pointer">
                          <CheckCircle size={16} className="mr-2 text-green-500" /> {m.label}
                          {quote.approved_at && <span className="ml-auto text-xs text-green-500">&#10003;</span>}
                          {!quote.approved_at && quote.quote_status === 'Enviada' && <span className="ml-auto text-xs text-green-500">&#x25CF;</span>}
                          {!quote.approved_at && quote.quote_status !== 'Enviada' && quote.quote_status !== 'Borrador' && <span className="ml-auto text-[9px] bg-amber-100 text-amber-700 px-1 rounded">Regularizar</span>}
                        </DropdownMenuItem>; })()}
                        {renderAnchoredCustomActions(quote, 'approve', customByAnchor)}
                        {canEditNonConfig && isRepair && quote.quote_status === 'Aprobada' && (
                          <DropdownMenuItem onSelect={() => onRepairComplete(quote.quote_id)} className="cursor-pointer"
                            data-testid={`repair-complete-btn-${quote.quote_id}`}>
                            <Wrench size={16} className="mr-2 text-cyan-600" /> Reparada
                            <span className="ml-auto text-xs text-cyan-500">&#x25CF;</span>
                          </DropdownMenuItem>
                        )}
                        {canEditNonConfig && isRepair && renderAnchoredCustomActions(quote, 'repair_complete', customByAnchor)}

                        {/* ── FASE LOGÍSTICA (Fast Track) ── */}
                        {canEditNonConfig && isFastTrack && <DropdownMenuSeparator />}
                        {canEditNonConfig && isFastTrack && (
                          <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400 select-none">Logística</p>
                        )}
                        {canEditNonConfig && isFastTrack && (
                          <DropdownMenuItem onSelect={() => onPreassignSerials(quote)} className="cursor-pointer"
                            data-testid={`preassign-btn-${quote.quote_id}`}>
                            <Package size={16} className="mr-2 text-blue-600" /> Preasignación de Seriales
                            {quote.preassigned_serials?.length > 0 && <span className="ml-auto text-xs text-blue-500">&#10003;</span>}
                            {!quote.preassigned_serials?.length && quote.approved_at && <span className="ml-auto text-xs text-blue-500">&#x25CF;</span>}
                          </DropdownMenuItem>
                        )}

                        {/* ── FASE TÉCNICA (Fast Track) ── */}
                        {canEdit && isFastTrack && <DropdownMenuSeparator />}
                        {canEdit && isFastTrack && (
                          <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400 select-none">Técnica</p>
                        )}
                        {canEdit && isFastTrack && (() => {
                          const hasPreassigned = quote.preassigned_serials?.length > 0;
                          const defaultLabel = quote.quote_status === 'Aprobada' ? 'Marcar como Configurada' : 'Configuración';
                          // Aplicar overrides del catálogo (action_id = 'configure'):
                          // permite renombrar el botón, ocultarlo o restringir
                          // por usuarios. Si el override desactiva la acción,
                          // hidden=true y no se renderiza.
                          const m = getActionMeta(quote, 'configure', defaultLabel);
                          if (m.hidden) return null;
                          // MPOS (Imple + POS): "Configuración" siempre habilitada por
                          // defecto. El sistema no fuerza el orden Preasign→Configuración;
                          // el usuario decide la secuencia.
                          const isDisabled = m.disabled;
                          const tooltip = m.tooltip || '';
                          return (
                            <DropdownMenuItem
                              onSelect={() => {
                                if (isDisabled) return;
                                // Para MPOS (fast_track), la acción "Configuración"
                                // siempre debe abrir el modal de correo y ejecutar
                                // handleConfigure (marca verde en grilla + email),
                                // NO el modal de edición de la cotización.
                                onConfigure(quote.quote_id);
                              }}
                              className={`cursor-pointer ${isDisabled ? 'opacity-50 cursor-not-allowed' : ''}`}
                              disabled={isDisabled}
                              title={tooltip}
                              data-testid={`configure-btn-${quote.quote_id}`}>
                              <Settings size={16} className={`mr-2 ${isDisabled ? 'text-slate-400' : 'text-indigo-600'}`} />
                              {m.label}
                              {quote.configured_at && <span className="ml-auto text-xs text-indigo-500">&#10003;</span>}
                              {!quote.configured_at && !isDisabled && <span className="ml-auto text-xs text-indigo-500">&#x25CF;</span>}
                              {!hasPreassigned && !quote.configured_at && <span className="ml-auto text-[9px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded">Sin preasignación</span>}
                            </DropdownMenuItem>
                          );
                        })()}

                        {/* ── ENVIAR A IMPLEMENTACIÓN (MPOS Imple+POS / fast_track) ──
                            Reingeniería: para MPOS la acción "Enviar a Implementación"
                            se posiciona DESPUÉS de Configuración. Crea el Proyecto
                            pero la cotización permanece activa en la grilla; el cierre
                            al histórico lo hace "Marcar como Entregada" posteriormente. */}
                        {canEditNonConfig && isFastTrack && (() => {
                          const m = getActionMeta(quote, 'send_to_implementation', 'Enviar a Implementación');
                          if (m.hidden) return null;
                          const alreadySent = !!quote.sent_to_implementation_at;
                          // MPOS (Imple + POS): "Enviar a Implementación" siempre habilitada
                          // por defecto (no se exige Configuración previa). La única razón
                          // para deshabilitarla es que ya se haya enviado (proyecto creado).
                          const isDisabled = alreadySent || m.disabled;
                          const tooltip = alreadySent
                            ? 'Ya se envió a Implementación (proyecto creado)'
                            : (m.tooltip || '');
                          return (
                            <DropdownMenuItem
                              onSelect={() => !isDisabled && onSendToImplementation(quote.quote_id)}
                              className={`cursor-pointer ${isDisabled ? 'opacity-50 cursor-not-allowed' : ''}`}
                              disabled={isDisabled}
                              title={tooltip}
                              data-testid={`send-to-impl-mpos-btn-${quote.quote_id}`}>
                              <Send size={16} className={`mr-2 ${isDisabled ? 'text-slate-400' : 'text-amber-600'}`} />
                              {m.label}
                              {alreadySent && <span className="ml-auto text-xs text-amber-500">&#10003;</span>}
                              {!alreadySent && <span className="ml-auto text-xs text-amber-500">&#x25CF;</span>}
                            </DropdownMenuItem>
                          );
                        })()}

                        {/* ── FASE FINANCIERA ── */}
                        {canEditNonConfig && <DropdownMenuSeparator />}
                        {canEditNonConfig && (
                          <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400 select-none">Financiera</p>
                        )}
                        {(() => { const m = getActionMeta(quote, 'invoice', 'Factura / Proforma'); return canEditNonConfig && !m.hidden && <DropdownMenuItem onSelect={() => !m.disabled && onInvoice(quote.quote_id)} disabled={m.disabled} title={m.tooltip} className="cursor-pointer">
                          <Receipt size={16} className="mr-2 text-purple-500" /> {m.label}
                          {quote.invoiced_at && <span className="ml-auto text-xs text-purple-500">&#10003;</span>}
                          {!quote.invoiced_at && quote.quote_status === 'Aprobada' && <span className="ml-auto text-xs text-purple-500">&#x25CF;</span>}
                          {!quote.invoiced_at && !['Borrador', 'Enviada', 'Aprobada'].includes(quote.quote_status) && <span className="ml-auto text-[9px] bg-amber-100 text-amber-700 px-1 rounded">Regularizar</span>}
                        </DropdownMenuItem>; })()}
                        {renderAnchoredCustomActions(quote, 'invoice', customByAnchor)}
                        {(() => { const m = getActionMeta(quote, 'collect', 'Cobranza'); return canEditNonConfig && !m.hidden && <DropdownMenuItem onSelect={() => !m.disabled && onCollect(quote.quote_id)} disabled={m.disabled} title={m.tooltip} className="cursor-pointer">
                          <Banknote size={16} className="mr-2 text-emerald-500" /> {m.label}
                          {quote.paid_at && <span className="ml-auto text-xs text-emerald-500">&#10003;</span>}
                          {!quote.paid_at && quote.quote_status === 'Facturada' && <span className="ml-auto text-xs text-emerald-500">&#x25CF;</span>}
                          {!quote.paid_at && !['Borrador', 'Enviada', 'Aprobada', 'Facturada'].includes(quote.quote_status) && <span className="ml-auto text-[9px] bg-amber-100 text-amber-700 px-1 rounded">Regularizar</span>}
                        </DropdownMenuItem>; })()}
                        {renderAnchoredCustomActions(quote, 'collect', customByAnchor)}

                        {/* ── ENTREGA / IMPLEMENTACIÓN ── */}
                        {canEditNonConfig && <DropdownMenuSeparator />}
                        {canEditNonConfig && (isEquipment || isRepair || isFastTrack) && (
                          <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400 select-none">Entrega</p>
                        )}
                        {canEditNonConfig && (isEquipment || isRepair || isFastTrack) && (
                          <DropdownMenuItem onSelect={() => onDeliver(quote.quote_id)} className="cursor-pointer">
                            <Truck size={16} className="mr-2 text-teal-500" /> Marcar como Entregada
                            {quote.delivered_at && <span className="ml-auto text-xs text-teal-500">&#10003;</span>}
                            {!quote.delivered_at && quote.quote_status === 'Pagada' && <span className="ml-auto text-xs text-teal-500">&#x25CF;</span>}
                          </DropdownMenuItem>
                        )}
                        {canEditNonConfig && (isEquipment || isRepair || isFastTrack) && renderAnchoredCustomActions(quote, 'deliver', customByAnchor)}
                        {canEditNonConfig && (!isEquipment && !isRepair && !isFastTrack) && (
                          <DropdownMenuItem onSelect={() => onSendToImplementation(quote.quote_id)} className="cursor-pointer">
                            <Send size={16} className="mr-2 text-amber-500" /> Enviar a Implementación
                            {isFastTrack && !quote.delivered_at && <span className="ml-auto text-[9px] bg-amber-100 text-amber-700 px-1 rounded">Entregar primero</span>}
                          </DropdownMenuItem>
                        )}
                        {canEditNonConfig && (!isEquipment && !isRepair && !isFastTrack) && renderAnchoredCustomActions(quote, 'send_to_implementation', customByAnchor)}
                        <DropdownMenuSeparator />
                        {/* ── ACCIONES PERSONALIZADAS SIN ANCLA (Fase A) ── */}
                        {(() => {
                          const unanchored = customByAnchor['__end__'] || [];
                          if (!unanchored.length) return null;
                          return (
                            <>
                              <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-violet-500 select-none">Personalizadas</p>
                              {unanchored.map((ca) => (
                                <DropdownMenuItem
                                  key={ca.action_id}
                                  onSelect={() => onCustomAction?.(quote.quote_id, ca.action_id, ca.label)}
                                  className="cursor-pointer"
                                  data-testid={`custom-action-${ca.action_id}-${quote.quote_id}`}
                                  title={ca.description || null}
                                >
                                  <Sparkles size={16} className="mr-2 text-violet-500" /> {ca.label}
                                </DropdownMenuItem>
                              ))}
                              <DropdownMenuSeparator />
                            </>
                          );
                        })()}
                        {canEditNonConfig && <DropdownMenuItem onSelect={() => onDelete(quote.quote_id, quote.quote_number)}
                          className="cursor-pointer text-red-600 hover:text-red-700 hover:bg-red-50">
                          <Trash2 size={16} className="mr-2" /> Eliminar Cotización
                        </DropdownMenuItem>}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      </div>{/* /bottom scrollable */}

      {/* Empty states */}
      {quotes.length === 0 ? (
        <div className="text-center py-12 text-slate-500">
          <FileText size={48} className="mx-auto mb-4 text-slate-300" />
          <p>No hay cotizaciones registradas</p>
          <p className="text-sm mt-2">Cree una cotización de Implementación o Equipos para comenzar</p>
        </div>
      ) : filteredQuotes.length === 0 ? (
        <div className="text-center py-12 text-slate-500">
          <Search size={48} className="mx-auto mb-4 text-slate-300" />
          <p>No se encontraron cotizaciones</p>
          <p className="text-sm mt-2">Intente ajustar los filtros de búsqueda</p>
          <Button variant="outline" className="mt-4" onClick={clearFilters}>
            <X size={16} className="mr-2" /> Limpiar filtros
          </Button>
        </div>
      ) : null}
    </div>
  );
};
