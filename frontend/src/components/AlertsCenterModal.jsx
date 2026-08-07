import { useState, useEffect, useMemo, useCallback } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Bell, CheckCheck, Check, Search, Loader2, ExternalLink, RefreshCw } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { formatDateTime } from '../utils/dateFormat';
import api from '../utils/api';
import { toast } from 'sonner';

const PRIORITY_COLORS = {
  high: { bar: 'bg-red-500', pill: 'bg-red-100 text-red-700', dot: 'bg-red-500' },
  medium: { bar: 'bg-amber-500', pill: 'bg-amber-100 text-amber-700', dot: 'bg-amber-500' },
  low: { bar: 'bg-slate-300', pill: 'bg-slate-100 text-slate-600', dot: 'bg-slate-400' },
};
const PRIORITY_LABEL = { high: 'Alta', medium: 'Media', low: 'Baja' };

const FilterChip = ({ active, onClick, children, testid }) => (
  <button
    type="button"
    onClick={onClick}
    data-testid={testid}
    className={`px-3 py-1 rounded-full text-xs font-medium border transition ${
      active
        ? 'bg-indigo-600 text-white border-indigo-700 shadow-sm'
        : 'bg-white text-slate-700 border-slate-300 hover:border-indigo-400 hover:text-indigo-700'
    }`}
  >
    {children}
  </button>
);

/**
 * Centro de Alertas — vista amplia y centrada de las notificaciones del usuario.
 * Reemplaza la utilidad del popover pequeño de la esquina: permite filtrar por
 * estado (todas / no leídas), por prioridad, buscar por texto, marcar como
 * leídas (individual o todas) y navegar al recurso vinculado.
 */
export function AlertsCenterModal({ open, onClose, onChanged }) {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState('all'); // 'all' | 'unread'
  const [priority, setPriority] = useState('all'); // 'all' | 'high' | 'medium' | 'low'
  const [search, setSearch] = useState('');
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/notifications?limit=200');
      setItems(Array.isArray(data.items) ? data.items : []);
    } catch {
      toast.error('No se pudieron cargar las alertas');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      load();
      setTab('all'); setPriority('all'); setSearch('');
    }
  }, [open, load]);

  const markOne = async (id) => {
    setBusyId(id);
    try {
      await api.post(`/notifications/${id}/read`);
      setItems((prev) => prev.map((n) => n.notification_id === id ? { ...n, is_read: true } : n));
      onChanged?.();
    } catch {
      toast.error('No se pudo marcar como leída');
    } finally {
      setBusyId(null);
    }
  };

  const markAll = async () => {
    try {
      await api.post('/notifications/mark-all-read');
      setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
      onChanged?.();
      toast.success('Todas las alertas marcadas como leídas');
    } catch {
      toast.error('No se pudieron marcar como leídas');
    }
  };

  const goToItem = async (n) => {
    if (!n.is_read) await markOne(n.notification_id);
    onClose();
    if (n.link) navigate(n.link);
  };

  const unreadCount = useMemo(() => items.filter((n) => !n.is_read).length, [items]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items.filter((n) => {
      if (tab === 'unread' && n.is_read) return false;
      if (priority !== 'all' && (n.priority || 'medium') !== priority) return false;
      if (q) {
        const hay = `${n.title || ''} ${n.message || ''} ${n.category || ''}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [items, tab, priority, search]);

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-3xl max-h-[88vh] overflow-hidden flex flex-col p-0" data-testid="alerts-center-modal">
        <DialogHeader className="px-6 pt-5 pb-3 border-b border-slate-200">
          <DialogTitle className="flex items-center gap-2 text-lg">
            <Bell size={20} className="text-indigo-600" />
            Centro de Alertas
            {unreadCount > 0 && (
              <span className="ml-1 text-xs font-semibold bg-red-600 text-white rounded-full px-2 py-0.5" data-testid="alerts-center-unread">
                {unreadCount} sin leer
              </span>
            )}
          </DialogTitle>
        </DialogHeader>

        {/* Toolbar de filtros */}
        <div className="px-6 py-3 border-b border-slate-100 space-y-3 bg-slate-50/60">
          <div className="flex flex-wrap items-center gap-2">
            <FilterChip active={tab === 'all'} onClick={() => setTab('all')} testid="alerts-tab-all">Todas</FilterChip>
            <FilterChip active={tab === 'unread'} onClick={() => setTab('unread')} testid="alerts-tab-unread">No leídas</FilterChip>
            <span className="mx-1 h-4 w-px bg-slate-300" />
            <FilterChip active={priority === 'all'} onClick={() => setPriority('all')} testid="alerts-prio-all">Prioridad: Todas</FilterChip>
            <FilterChip active={priority === 'high'} onClick={() => setPriority('high')} testid="alerts-prio-high">Alta</FilterChip>
            <FilterChip active={priority === 'medium'} onClick={() => setPriority('medium')} testid="alerts-prio-medium">Media</FilterChip>
            <FilterChip active={priority === 'low'} onClick={() => setPriority('low')} testid="alerts-prio-low">Baja</FilterChip>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <Input
                placeholder="Buscar por título, mensaje o categoría…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8 h-9"
                data-testid="alerts-search-input"
              />
            </div>
            <Button variant="outline" size="sm" onClick={load} disabled={loading} data-testid="alerts-refresh-btn" title="Actualizar">
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            </Button>
            <Button
              size="sm"
              onClick={markAll}
              disabled={unreadCount === 0}
              className="bg-indigo-600 hover:bg-indigo-700 text-white"
              data-testid="alerts-mark-all-btn"
            >
              <CheckCheck size={14} className="mr-1" />Marcar todas
            </Button>
          </div>
        </div>

        {/* Lista */}
        <div className="overflow-y-auto flex-1 px-2 py-2" data-testid="alerts-list">
          {loading ? (
            <div className="flex items-center justify-center py-16"><Loader2 size={24} className="animate-spin text-slate-400" /></div>
          ) : filtered.length === 0 ? (
            <div className="py-16 text-center text-sm text-slate-400 px-6">
              <Bell size={36} className="mx-auto mb-3 text-slate-300" />
              {items.length === 0 ? 'No tienes alertas.' : 'No hay alertas que coincidan con los filtros.'}
            </div>
          ) : (
            <ul className="space-y-1.5">
              {filtered.map((n) => {
                const colors = PRIORITY_COLORS[n.priority] || PRIORITY_COLORS.medium;
                return (
                  <li
                    key={n.notification_id}
                    className={`flex gap-3 rounded-lg border px-4 py-3 transition-colors ${
                      n.is_read ? 'bg-white border-slate-100' : 'bg-indigo-50/40 border-indigo-100'
                    }`}
                    data-testid={`alert-row-${n.notification_id}`}
                  >
                    <div className={`w-1.5 rounded-full shrink-0 ${colors.bar}`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <p className={`text-sm ${!n.is_read ? 'font-semibold text-slate-900' : 'font-medium text-slate-700'}`}>
                          {n.title}
                        </p>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full shrink-0 ${colors.pill}`}>
                          {PRIORITY_LABEL[n.priority] || n.priority || 'Media'}
                        </span>
                      </div>
                      {n.message && <p className="text-xs text-slate-600 mt-1 whitespace-pre-line">{n.message}</p>}
                      <div className="flex items-center flex-wrap gap-x-3 gap-y-1 mt-2">
                        <span className="text-[10px] text-slate-400">{formatDateTime(n.created_at)}</span>
                        {n.category && <span className="text-[10px] text-slate-400">· {n.category}</span>}
                        {!n.is_read && <span className={`w-2 h-2 rounded-full ${colors.dot}`} title="No leída" />}
                        <span className="flex-1" />
                        {n.link && (
                          <button
                            onClick={() => goToItem(n)}
                            className="text-[11px] text-indigo-600 hover:text-indigo-800 font-medium flex items-center gap-1"
                            data-testid={`alert-open-${n.notification_id}`}
                          >
                            <ExternalLink size={12} />Abrir
                          </button>
                        )}
                        {!n.is_read && (
                          <button
                            onClick={() => markOne(n.notification_id)}
                            disabled={busyId === n.notification_id}
                            className="text-[11px] text-slate-500 hover:text-emerald-700 font-medium flex items-center gap-1"
                            data-testid={`alert-markread-${n.notification_id}`}
                          >
                            {busyId === n.notification_id ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
                            Marcar leída
                          </button>
                        )}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-slate-200 px-6 py-2.5 text-center bg-slate-50">
          <span className="text-[11px] text-slate-500" data-testid="alerts-count-footer">
            Mostrando {filtered.length} de {items.length} alerta{items.length === 1 ? '' : 's'}
          </span>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default AlertsCenterModal;
