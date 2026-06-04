import { useState, useEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Archive, Download, Search, FileText, Eye, Lock, ShieldAlert, Trash2, FolderOpen } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';
import { HistoricalAnexosModal } from '../components/HistoricalAnexosModal';
import { ProjectTypeBadge } from '../components/projects/ProjectTypeBadge';
import { MigrationButtons } from '../components/MigrationButtons';

const CATEGORY_LABELS = {
  equipment: 'Equipos/Accesorios',
  implementation: 'Implementación (VPOS/MPOS)',
  repair: 'Reparaciones',
  fast_track: 'Fast Track',
};

const CATEGORY_COLORS = {
  equipment: 'bg-blue-100 text-blue-700 border-blue-200',
  implementation: 'bg-purple-100 text-purple-700 border-purple-200',
  repair: 'bg-amber-100 text-amber-700 border-amber-200',
  fast_track: 'bg-emerald-100 text-emerald-700 border-emerald-200',
};

export const HistoricalQuotes = () => {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [invoiceFilter, setInvoiceFilter] = useState('');
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailRecord, setDetailRecord] = useState(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const autoOpenedRef = useRef(false);
  const [deletingId, setDeletingId] = useState(null);
  const [anexosOpen, setAnexosOpen] = useState(false);
  const [anexosTarget, setAnexosTarget] = useState(null);
  const currentUser = (() => {
    try { return JSON.parse(localStorage.getItem('user') || '{}'); } catch { return {}; }
  })();
  const isAdmin = (currentUser?.role || '').toLowerCase() === 'admin';

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const params = {};
      if (search.trim()) params.search = search.trim();
      if (categoryFilter !== 'all') params.quote_category = categoryFilter;
      if (invoiceFilter.trim()) params.invoice_number = invoiceFilter.trim();
      const res = await api.get('/quote-history', { params });
      setRecords(res.data || []);
    } catch (err) {
      if (err.response?.status === 403) {
        setForbidden(true);
      } else {
        toast.error('Error al cargar histórico');
      }
    } finally { setLoading(false); }
  };

  useEffect(() => { fetchHistory(); /* eslint-disable-next-line */ }, [categoryFilter]);

  // Búsqueda en vivo (debounced) por nombre de cliente / nº cotización / factura:
  // la grilla se actualiza de inmediato al escribir, sin necesidad de "Aplicar filtros".
  const searchDebounceRef = useRef(null);
  const firstSearchRender = useRef(true);
  useEffect(() => {
    if (firstSearchRender.current) { firstSearchRender.current = false; return; }
    if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current);
    searchDebounceRef.current = setTimeout(() => { fetchHistory(); }, 400);
    return () => { if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current); };
    /* eslint-disable-next-line */
  }, [search, invoiceFilter]);

  // Auto-abrir detalle si llega ?quote_id=xxx en la URL (desde Reportes de Irregulares)
  useEffect(() => {
    const targetQuoteId = searchParams.get('quote_id');
    if (!targetQuoteId || autoOpenedRef.current || loading || records.length === 0) return;
    const match = records.find(r => r.quote_id === targetQuoteId);
    if (match) {
      autoOpenedRef.current = true;
      openDetail(match);
      // Limpiar el query param para evitar re-abrir si el usuario cierra y vuelve
      const next = new URLSearchParams(searchParams);
      next.delete('quote_id');
      setSearchParams(next, { replace: true });
    } else if (records.length > 0) {
      // Records cargados pero no se encontró la cotización
      autoOpenedRef.current = true;
      toast.info('La cotización no está en el histórico (puede que esté activa).');
    }
    // eslint-disable-next-line
  }, [records, loading, searchParams]);

  const filtered = useMemo(() => records, [records]);

  const openDetail = async (r) => {
    try {
      const res = await api.get(`/quote-history/${r.history_id}`);
      setDetailRecord(res.data);
      setDetailOpen(true);
    } catch { toast.error('No se pudo abrir el detalle'); }
  };

  const deleteRecord = async (r) => {
    const label = `${r.quote_number || ''} (${r.client_name || 'sin cliente'})`;
    const confirmed = window.confirm(
      `¿Eliminar permanentemente el registro ${label} del histórico?\n\n` +
      `Esta acción es IRREVERSIBLE y solo borra del repositorio de auditoría — no restaura la cotización al flujo activo.`
    );
    if (!confirmed) return;
    setDeletingId(r.history_id);
    try {
      const res = await api.delete(`/quote-history/${r.history_id}`);
      toast.success(res.data.message || 'Registro eliminado');
      // Remover de la lista local sin re-fetch
      setRecords(prev => prev.filter(x => x.history_id !== r.history_id));
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al eliminar registro');
    } finally {
      setDeletingId(null);
    }
  };

  if (forbidden) {
    return (
      <div className="flex min-h-screen bg-slate-50">
        <Sidebar />
        <main className="flex-1 p-10">
          <Card className="p-10 text-center max-w-md mx-auto">
            <ShieldAlert className="w-12 h-12 mx-auto text-rose-400 mb-4" />
            <h2 className="text-lg font-bold mb-2">Acceso Restringido</h2>
            <p className="text-sm text-slate-500">El Histórico de Cotizaciones está reservado a perfiles de Director o Administrador del Sistema para fines de auditoría.</p>
          </Card>
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 p-6 overflow-auto">
        <div className="flex items-center justify-between gap-3 mb-6">
          <div className="flex items-center gap-3">
            <Archive className="w-7 h-7 text-amber-500" />
            <div>
              <h1 className="text-xl font-bold text-slate-800" data-testid="quote-history-title">Histórico de Cotizaciones</h1>
              <p className="text-xs text-slate-500 flex items-center gap-1.5"><Lock size={11} /> Repositorio inmutable de auditoría — solo lectura</p>
            </div>
          </div>
          <MigrationButtons module="quote-history" label="Histórico de Cotizaciones" onImported={fetchHistory} />
        </div>

        {/* Filtros */}
        <Card className="p-4 mb-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
            <div>
              <Label className="text-xs">Búsqueda</Label>
              <div className="relative">
                <Search className="absolute left-2 top-2.5 w-3.5 h-3.5 text-slate-400" />
                <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Nro. cotización, cliente..." className="pl-8 text-sm" data-testid="qh-search" />
              </div>
            </div>
            <div>
              <Label className="text-xs">Categoría</Label>
              <Select value={categoryFilter} onValueChange={setCategoryFilter}>
                <SelectTrigger className="text-sm" data-testid="qh-category"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todas</SelectItem>
                  <SelectItem value="equipment">Equipos/Accesorios</SelectItem>
                  <SelectItem value="implementation">Implementación</SelectItem>
                  <SelectItem value="repair">Reparaciones</SelectItem>
                  <SelectItem value="fast_track">Fast Track</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Nº Factura</Label>
              <Input value={invoiceFilter} onChange={e => setInvoiceFilter(e.target.value)} placeholder="FAC-000123" className="text-sm" data-testid="qh-invoice" />
            </div>
            <Button onClick={fetchHistory} data-testid="qh-apply-filters">Aplicar filtros</Button>
          </div>
        </Card>

        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr className="text-xs text-slate-500 uppercase font-semibold">
                  <th className="px-4 py-3 text-left">Nº Cotización</th>
                  <th className="px-4 py-3 text-left">Tipo</th>
                  <th className="px-4 py-3 text-left">Cliente</th>
                  <th className="px-4 py-3 text-left">Categoría</th>
                  <th className="px-4 py-3 text-right">Total USD</th>
                  <th className="px-4 py-3 text-left">Nº Factura</th>
                  <th className="px-4 py-3 text-left">Responsable</th>
                  <th className="px-4 py-3 text-left">Archivada</th>
                  <th className="px-4 py-3 text-center">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={9} className="text-center py-8 text-slate-400">Cargando...</td></tr>
                ) : filtered.length === 0 ? (
                  <tr><td colSpan={9} className="text-center py-12">
                    <Archive className="w-10 h-10 mx-auto text-slate-300 mb-2" />
                    <p className="text-sm text-slate-400">No hay cotizaciones archivadas</p>
                  </td></tr>
                ) : filtered.map(r => (
                  <tr key={r.history_id} className="border-b border-slate-100 hover:bg-slate-50 text-sm" data-testid={`qh-row-${r.history_id}`}>
                    <td className="px-4 py-3 font-mono text-xs font-semibold text-blue-600">{r.quote_number}</td>
                    <td className="px-4 py-3"><ProjectTypeBadge quoteType={r.quote_type} size="xs" /></td>
                    <td className="px-4 py-3">{r.client_name || '—'}</td>
                    <td className="px-4 py-3">
                      <Badge variant="outline" className={`text-[10px] ${CATEGORY_COLORS[r.quote_category] || 'bg-slate-50'}`}>
                        {CATEGORY_LABELS[r.quote_category] || r.quote_category}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-xs">${(r.total_usd || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                    <td className="px-4 py-3 text-xs font-mono">{r.invoice_number || '—'}</td>
                    <td className="px-4 py-3 text-xs">{r.responsible?.name || '—'}</td>
                    <td className="px-4 py-3 text-xs text-slate-500">{r.archived_at?.substring(0, 19).replace('T', ' ') || '—'}</td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex gap-1 justify-center">
                        <Button size="sm" variant="ghost" onClick={() => openDetail(r)} data-testid={`qh-view-${r.history_id}`} title="Ver">
                          <Eye className="w-4 h-4 text-slate-500" />
                        </Button>
                        {isAdmin && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => { setAnexosTarget(r); setAnexosOpen(true); }}
                            data-testid={`qh-anexos-${r.history_id}`}
                            title="Anexos del histórico (solo administradores)"
                          >
                            <FolderOpen className="w-4 h-4 text-amber-500 hover:text-amber-700" />
                          </Button>
                        )}
                        {isAdmin && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => deleteRecord(r)}
                            disabled={deletingId === r.history_id}
                            data-testid={`qh-delete-${r.history_id}`}
                            title="Depurar registro (solo administradores)"
                          >
                            <Trash2 className={`w-4 h-4 ${deletingId === r.history_id ? 'text-slate-300 animate-pulse' : 'text-rose-500 hover:text-rose-700'}`} />
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
          <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><Archive className="w-5 h-5 text-amber-500" />
                {detailRecord?.quote_number || 'Detalle'}
              </DialogTitle>
            </DialogHeader>
            {detailRecord && (
              <div className="space-y-4 text-sm">
                <div className="grid grid-cols-2 gap-3">
                  <div><Label className="text-[10px] uppercase text-slate-400">Cliente</Label><p className="font-medium">{detailRecord.client_name || '—'}</p></div>
                  <div><Label className="text-[10px] uppercase text-slate-400">Categoría</Label><p>{CATEGORY_LABELS[detailRecord.quote_category] || detailRecord.quote_category}</p></div>
                  <div><Label className="text-[10px] uppercase text-slate-400">Total USD</Label><p className="font-mono">${(detailRecord.total_usd || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}</p></div>
                  <div><Label className="text-[10px] uppercase text-slate-400">Total Bs</Label><p className="font-mono">Bs. {(detailRecord.total_bs || 0).toLocaleString('es-VE', { minimumFractionDigits: 2 })}</p></div>
                  <div><Label className="text-[10px] uppercase text-slate-400">Tasa</Label><p className="font-mono">{detailRecord.exchange_rate || '—'}</p></div>
                  <div><Label className="text-[10px] uppercase text-slate-400">Nº Factura</Label><p className="font-mono">{detailRecord.invoice_number || '—'}</p></div>
                  <div><Label className="text-[10px] uppercase text-slate-400">Responsable</Label><p>{detailRecord.responsible?.name || '—'}</p></div>
                  <div><Label className="text-[10px] uppercase text-slate-400">Archivada por</Label><p>{detailRecord.archived_by_name || '—'}</p></div>
                </div>
                {detailRecord.attachments && detailRecord.attachments.length > 0 && (
                  <div>
                    <Label className="text-[10px] uppercase text-slate-400">Anexos ({detailRecord.attachments.length})</Label>
                    <div className="mt-1 space-y-1">
                      {detailRecord.attachments.map((a, i) => {
                        const rawUrl = a.url || a.file_url || a.path || '';
                        // Las URLs están guardadas como /uploads/... pero el mount es /api/uploads/...
                        const normalizedUrl = rawUrl.startsWith('/uploads') ? `/api${rawUrl}` : rawUrl;
                        const href = normalizedUrl
                          ? (normalizedUrl.startsWith('http') ? normalizedUrl : `${process.env.REACT_APP_BACKEND_URL}${normalizedUrl.startsWith('/') ? '' : '/'}${normalizedUrl}`)
                          : null;
                        const name = a.filename || a.name || `Anexo ${i+1}`;
                        return (
                          <div key={i} className="flex items-center justify-between gap-2 p-2 bg-slate-50 rounded text-xs border border-slate-100 hover:border-blue-200 transition">
                            <div className="flex items-center gap-2 min-w-0">
                              <FileText className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                              <div className="min-w-0">
                                <div className="truncate font-medium text-slate-700">{name}</div>
                                {a.category && <div className="text-[10px] text-slate-400">{a.category}{a.uploaded_by_name ? ` · ${a.uploaded_by_name}` : ''}</div>}
                              </div>
                            </div>
                            {href ? (
                              <a
                                href={href}
                                target="_blank"
                                rel="noopener noreferrer"
                                download={name}
                                className="text-blue-600 hover:text-blue-800 text-[11px] font-semibold shrink-0 flex items-center gap-1"
                                data-testid={`qh-attachment-download-${i}`}
                              >
                                <Download className="w-3 h-3" /> Descargar
                              </a>
                            ) : (
                              <span className="text-slate-300 text-[10px] shrink-0">Sin URL</span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}
          </DialogContent>
        </Dialog>
        {anexosOpen && anexosTarget && (
          <HistoricalAnexosModal
            open={anexosOpen}
            onClose={() => { setAnexosOpen(false); setAnexosTarget(null); }}
            historyId={anexosTarget.history_id}
            quoteNumber={anexosTarget.quote_number}
            onChange={fetchHistory}
          />
        )}
      </main>
    </div>
  );
};

export default HistoricalQuotes;
