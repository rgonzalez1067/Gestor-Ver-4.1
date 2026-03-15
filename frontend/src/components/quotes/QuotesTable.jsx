import { FileText, Search, X, FolderOpen, MoreHorizontal, Download, RefreshCw, Mail, CheckCircle, Receipt, Banknote, Truck, Send, Trash2, Eye } from 'lucide-react';
import { useState } from 'react';
import { Button } from '../ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '../ui/popover';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '../ui/dropdown-menu';

const STATUS_COLORS = {
  'Borrador': 'bg-slate-100 text-slate-600',
  'Enviada': 'bg-blue-100 text-blue-600',
  'Aprobada': 'bg-green-100 text-green-600',
  'Facturada': 'bg-purple-100 text-purple-600',
  'Pagada': 'bg-emerald-100 text-emerald-700',
  'Entregada': 'bg-teal-100 text-teal-700',
  'Enviada a Imple': 'bg-amber-100 text-amber-700',
};

const STATUS_DISPLAY_NAMES = {
  'Borrador': 'Borrador',
  'Enviada': 'Enviada',
  'Aprobada': 'Aprobada',
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
  actionLoading,
  onOpenAnexos, onDownloadPDF, onEditQuote, onSendToClient,
  onApprove, onInvoice, onCollect, onDeliver, onSendToImplementation, onDelete,
  onOpenBitacoraFlujo,
  clearFilters,
}) => {
  const filteredQuotes = quotes.filter(quote => {
    if (filterClient && filterClient !== 'all' && quote.client_id !== filterClient) return false;
    if (filterStatus && filterStatus !== 'all' && (quote.quote_status || 'Borrador') !== filterStatus) return false;
    if (filterCategory && filterCategory !== 'all') {
      const isEquipment = quote.quote_category === 'equipment';
      if (filterCategory === 'equipment' && !isEquipment) return false;
      if (filterCategory === 'implementation' && isEquipment) return false;
    }
    if (filterSegment && filterSegment !== 'all' && (quote.client_segment || 'PYME') !== filterSegment) return false;
    if (filterDateFrom) {
      if (new Date(quote.created_at) < new Date(filterDateFrom)) return false;
    }
    if (filterDateTo) {
      const toDate = new Date(filterDateTo);
      toDate.setHours(23, 59, 59, 999);
      if (new Date(quote.created_at) > toDate) return false;
    }
    return true;
  });

  return (
    <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
      <table className="w-full" data-testid="quotes-unified-table">
        <thead className="bg-slate-50 border-b border-slate-200">
          <tr>
            <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase">Número</th>
            <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase">Categoría</th>
            <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase">Segmento</th>
            <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase">Tipo</th>
            <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase">Cliente</th>
            <th className="px-6 py-4 text-right text-sm font-medium text-slate-700 uppercase">Total USD</th>
            <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase">Estado</th>
            <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase">Fecha</th>
            <th className="px-6 py-4 text-center text-sm font-medium text-slate-700 uppercase">Acciones</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {filteredQuotes.map((quote) => {
            const client = clients.find(c => c.client_id === quote.client_id);
            const statusColor = STATUS_COLORS[quote.quote_status] || STATUS_COLORS['Borrador'];
            const isLoading = actionLoading === quote.quote_id;
            const isEquipment = quote.quote_category === 'equipment';
            const displayType = isEquipment ? (quote.equipment_type || 'Equipos') : getQuoteTypeName(quote.quote_type);
            const categoryColor = isEquipment ? 'bg-amber-100 text-amber-700' : 'bg-green-100 text-green-700';
            const typeColor = isEquipment
              ? (quote.equipment_type === 'POS' || quote.equipment_type === 'Pinpad' ? 'bg-blue-100 text-blue-700' : 'bg-amber-100 text-amber-700')
              : 'bg-brand-blue-50 text-brand-blue-600';

            return (
              <tr key={quote.quote_id} className="hover:bg-slate-50" data-testid={`quote-row-${quote.quote_id}`}>
                <td className="px-6 py-4 text-sm font-mono font-medium text-slate-900">{quote.quote_number}</td>
                <td className="px-6 py-4 text-sm">
                  <span className={`px-2 py-1 text-xs font-medium rounded ${categoryColor}`}>
                    {isEquipment ? 'Equipos' : 'Implementación'}
                  </span>
                </td>
                <td className="px-6 py-4 text-sm">
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
                </td>
                <td className="px-6 py-4 text-sm">
                  <span className={`px-2 py-1 text-xs font-medium rounded ${typeColor}`}>{displayType}</span>
                </td>
                <td className="px-6 py-4 text-sm text-slate-900">{quote.client_name || client?.fantasy_name || client?.legal_name || 'N/A'}</td>
                <td className="px-6 py-4 text-sm font-mono text-right text-brand-green-600 font-semibold">${quote.total_usd?.toFixed(2) || '0.00'}</td>
                <td className="px-6 py-4 text-sm">
                  <div className="flex items-center gap-1.5">
                    <span className={`px-2 py-1 text-xs font-medium rounded ${statusColor}`}>
                      {STATUS_DISPLAY_NAMES[quote.quote_status] || 'Borrador'}
                    </span>
                    {quote.is_irregular && (
                      <Popover>
                        <PopoverTrigger asChild>
                          <button className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[9px] font-bold rounded bg-orange-100 text-orange-700 border border-orange-300 cursor-pointer hover:bg-orange-200 transition-colors"
                            data-testid={`irregular-badge-${quote.quote_id}`}>
                            Irregular <Eye size={10} />
                          </button>
                        </PopoverTrigger>
                        <PopoverContent className="w-72 p-0" align="start">
                          <div className="bg-orange-50 border-b border-orange-200 px-3 py-2">
                            <p className="text-xs font-bold text-orange-800">Historial de Excepciones</p>
                          </div>
                          <div className="max-h-48 overflow-y-auto p-2 space-y-2">
                            {(quote.irregular_exceptions || []).map((exc, idx) => {
                              const ACTION_NAMES = { approve: 'Aprobar', invoice: 'Facturar', collect: 'Cobrar', deliver: 'Entregar', 'send-to-implementation': 'Enviar a Imple.' };
                              return (
                                <div key={idx} className="border-l-2 border-orange-400 pl-2 py-1">
                                  <p className="text-[10px] font-semibold text-orange-700">{ACTION_NAMES[exc.action] || exc.action}</p>
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
                            <div className="border-t border-orange-200 px-3 py-1.5">
                              <button onClick={() => onOpenBitacoraFlujo(quote.quote_id, quote.quote_number)}
                                className="text-[10px] text-orange-600 hover:text-orange-800 font-medium w-full text-center"
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
                <td className="px-6 py-4 text-sm text-slate-600">{new Date(quote.created_at).toLocaleDateString('es-VE')}</td>
                <td className="px-6 py-4">
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
                        <DropdownMenuItem onSelect={() => onDownloadPDF(quote.quote_id)} className="cursor-pointer">
                          <Download size={16} className="mr-2 text-slate-500" /> Descargar PDF
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onSelect={() => onEditQuote(quote)} className="cursor-pointer">
                          <RefreshCw size={16} className="mr-2 text-slate-500" /> Modificar (Nueva Versión)
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onSelect={() => onSendToClient(quote.quote_id)} className="cursor-pointer"
                          disabled={quote.quote_status !== 'Borrador'}>
                          <Mail size={16} className="mr-2 text-blue-500" /> Enviar al Cliente
                          {quote.sent_to_client_at && <span className="ml-auto text-xs text-slate-400">&#10003;</span>}
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => onApprove(quote.quote_id)} className="cursor-pointer">
                          <CheckCircle size={16} className="mr-2 text-green-500" /> Aprobar
                          {quote.quote_status === 'Enviada' && <span className="ml-auto text-xs text-green-500">&#x25CF;</span>}
                          {quote.quote_status !== 'Enviada' && quote.quote_status !== 'Aprobada' && <span className="ml-auto text-[9px] text-orange-500">!</span>}
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => onInvoice(quote.quote_id)} className="cursor-pointer">
                          <Receipt size={16} className="mr-2 text-purple-500" /> Facturar
                          {quote.quote_status !== 'Aprobada' && quote.quote_status !== 'Facturada' && <span className="ml-auto text-[9px] text-orange-500">!</span>}
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => onCollect(quote.quote_id)} className="cursor-pointer">
                          <Banknote size={16} className="mr-2 text-emerald-500" /> Cobrar
                          {quote.quote_status === 'Facturada' && <span className="ml-auto text-xs text-emerald-500">&#x25CF;</span>}
                          {quote.quote_status !== 'Facturada' && quote.quote_status !== 'Pagada' && <span className="ml-auto text-[9px] text-orange-500">!</span>}
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        {isEquipment ? (
                          <DropdownMenuItem onSelect={() => onDeliver(quote.quote_id)} className="cursor-pointer">
                            <Truck size={16} className="mr-2 text-teal-500" /> Marcar como Entregada
                            {quote.quote_status !== 'Pagada' && quote.quote_status !== 'Entregada' && <span className="ml-auto text-[9px] text-orange-500">!</span>}
                          </DropdownMenuItem>
                        ) : (
                          <DropdownMenuItem onSelect={() => onSendToImplementation(quote.quote_id)} className="cursor-pointer">
                            <Send size={16} className="mr-2 text-amber-500" /> Enviar a Implementación
                            {quote.quote_status !== 'Pagada' && <span className="ml-auto text-[9px] text-orange-500">!</span>}
                          </DropdownMenuItem>
                        )}
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onSelect={() => onDelete(quote.quote_id, quote.quote_number)}
                          className="cursor-pointer text-red-600 hover:text-red-700 hover:bg-red-50">
                          <Trash2 size={16} className="mr-2" /> Eliminar Cotización
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

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
