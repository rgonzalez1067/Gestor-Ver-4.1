import { useState, useEffect, useCallback } from 'react';
import { Inbox, Trash2, Mail, MailOpen, ChevronDown, ChevronUp, RefreshCw } from 'lucide-react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from './ui/alert-dialog';
import { toast } from 'sonner';
import api from '../utils/api';

/**
 * Centro de Mensajes — Bandeja Interna del Usuario.
 *
 * Iter42: módulo full-width que se ubica en Dashboard entre los KPIs y la
 * tarjeta de Actividad Reciente. Renderiza HTML idéntico al correo
 * (campo `body_html` del backend) y aplica un semáforo visual por SLA:
 *   - ≤24h: verde
 *   - 24-48h: amarillo
 *   - >48h: rojo
 *
 * Decisiones de UX:
 *   - "Leído" solo se marca al expandir el mensaje (no auto-leído al cargar).
 *     Así el contador de no leídos refleja revisiones reales.
 *   - "Eliminar" es soft-delete en backend; persiste en DB para auditoría
 *     pero deja de aparecer aquí.
 *   - Render del body usa `dangerouslySetInnerHTML` porque el HTML proviene
 *     del motor interno (plantillas controladas por el admin). No se
 *     reciben mensajes desde fuentes externas.
 */
const SLA_STYLES = {
  green: {
    border: 'border-l-emerald-500',
    bg: 'bg-emerald-50/40',
    chip: 'bg-emerald-100 text-emerald-700',
    label: 'A tiempo',
  },
  yellow: {
    border: 'border-l-amber-500',
    bg: 'bg-amber-50/50',
    chip: 'bg-amber-100 text-amber-700',
    label: 'Atención',
  },
  red: {
    border: 'border-l-rose-600',
    bg: 'bg-rose-50/60',
    chip: 'bg-rose-100 text-rose-700',
    label: 'Retraso',
  },
};

function formatDate(iso) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString('es-VE', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

export function InboxCenter() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedIds, setExpandedIds] = useState({}); // { msg_id: true }
  const [deletingTarget, setDeletingTarget] = useState(null); // {message_id, subject}
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await api.get('/inbox/me', { params: { limit: 50, include_read: true } });
      setMessages(res.data?.items || []);
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Error';
      toast.error(`No se pudo cargar el Centro de Mensajes: ${detail}`);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleRefresh = () => {
    setRefreshing(true);
    load();
  };

  const toggleExpand = async (msg) => {
    const next = !expandedIds[msg.message_id];
    setExpandedIds((prev) => ({ ...prev, [msg.message_id]: next }));
    // Marcar como leído al expandir por primera vez
    if (next && !msg.read_at) {
      try {
        await api.patch(`/inbox/${msg.message_id}/read`);
        setMessages((prev) =>
          prev.map((m) =>
            m.message_id === msg.message_id ? { ...m, read_at: new Date().toISOString() } : m,
          ),
        );
      } catch {
        /* silencio: lectura es best-effort */
      }
    }
  };

  const confirmDelete = async () => {
    if (!deletingTarget) return;
    try {
      await api.delete(`/inbox/${deletingTarget.message_id}`);
      setMessages((prev) => prev.filter((m) => m.message_id !== deletingTarget.message_id));
      toast.success('Mensaje eliminado');
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Error';
      toast.error(`No se pudo eliminar: ${detail}`);
    } finally {
      setDeletingTarget(null);
    }
  };

  const unreadCount = messages.filter((m) => !m.read_at).length;

  if (loading) {
    return (
      <div
        className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm"
        data-testid="inbox-center-loading"
      >
        <div className="flex items-center gap-3 text-slate-500 text-sm">
          <RefreshCw size={16} className="animate-spin" />
          Cargando Centro de Mensajes…
        </div>
      </div>
    );
  }

  return (
    <div
      className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden"
      data-testid="inbox-center"
    >
      {/* Cabecera */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-blue-100 text-blue-700">
            <Inbox size={20} />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-900 font-manrope">Centro de Mensajes</h2>
            <p className="text-xs text-slate-500">
              Bandeja interna · {messages.length} mensaje{messages.length === 1 ? '' : 's'}
              {unreadCount > 0 && (
                <span className="ml-2 font-semibold text-blue-700">
                  · {unreadCount} sin leer
                </span>
              )}
            </p>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleRefresh}
          disabled={refreshing}
          data-testid="inbox-refresh-btn"
        >
          <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
        </Button>
      </div>

      {/* Listado */}
      {messages.length === 0 ? (
        <div className="px-6 py-10 text-center" data-testid="inbox-empty">
          <Inbox size={36} className="mx-auto text-slate-300 mb-2" />
          <p className="text-sm text-slate-500">No tienes mensajes en tu bandeja.</p>
          <p className="text-xs text-slate-400 mt-1">
            Las acciones configuradas como “Centro de Mensajes” aparecerán aquí.
          </p>
        </div>
      ) : (
        <ul className="divide-y divide-slate-100" data-testid="inbox-message-list">
          {messages.map((msg) => {
            const sla = SLA_STYLES[msg.sla_color] || SLA_STYLES.green;
            const isExpanded = !!expandedIds[msg.message_id];
            const isUnread = !msg.read_at;
            return (
              <li
                key={msg.message_id}
                className={`border-l-4 ${sla.border} ${sla.bg} transition-colors`}
                data-testid={`inbox-msg-${msg.message_id}`}
                data-sla={msg.sla_color}
              >
                <div className="px-6 py-4 flex items-start gap-4">
                  <button
                    type="button"
                    onClick={() => toggleExpand(msg)}
                    className="flex-1 text-left flex items-start gap-3 group"
                    data-testid={`inbox-msg-toggle-${msg.message_id}`}
                  >
                    <div className="pt-0.5">
                      {isUnread ? (
                        <Mail size={18} className="text-blue-600" />
                      ) : (
                        <MailOpen size={18} className="text-slate-400" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span
                          className={`text-sm ${
                            isUnread ? 'font-bold text-slate-900' : 'font-medium text-slate-700'
                          } truncate`}
                          data-testid={`inbox-msg-subject-${msg.message_id}`}
                        >
                          {msg.subject}
                        </span>
                        <Badge className={`${sla.chip} text-[10px] font-bold uppercase`}>
                          {sla.label}
                        </Badge>
                        {msg.quote_number && (
                          <Badge variant="outline" className="text-[10px]">
                            {msg.quote_number}
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-slate-500 mt-0.5">
                        Recibido {formatDate(msg.created_at)}
                      </p>
                    </div>
                    <div className="text-slate-400 group-hover:text-slate-600 transition-colors">
                      {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                    </div>
                  </button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-rose-500 hover:bg-rose-50 hover:text-rose-700 shrink-0"
                    onClick={() => setDeletingTarget(msg)}
                    data-testid={`inbox-msg-delete-${msg.message_id}`}
                    title="Eliminar mensaje"
                  >
                    <Trash2 size={16} />
                  </Button>
                </div>
                {isExpanded && (
                  <div className="px-6 pb-5 pt-1">
                    <div
                      className="bg-white rounded-lg border border-slate-200 p-5 text-sm text-slate-800 leading-relaxed prose prose-sm max-w-none"
                      data-testid={`inbox-msg-body-${msg.message_id}`}
                      dangerouslySetInnerHTML={{ __html: msg.body_html || '' }}
                    />
                    {msg.attachments_meta && msg.attachments_meta.length > 0 && (
                      <div className="mt-3 text-xs text-slate-500">
                        <span className="font-semibold">Adjuntos originales:</span>{' '}
                        {msg.attachments_meta.map((a) => a.filename).join(', ')}
                      </div>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      <AlertDialog open={!!deletingTarget} onOpenChange={(o) => !o && setDeletingTarget(null)}>
        <AlertDialogContent data-testid="inbox-delete-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Eliminar mensaje</AlertDialogTitle>
            <AlertDialogDescription>
              ¿Confirmas eliminar <strong>{deletingTarget?.subject}</strong> de tu bandeja? El
              mensaje no podrá recuperarse desde esta pantalla.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="inbox-delete-cancel">Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              className="bg-rose-600 hover:bg-rose-700"
              data-testid="inbox-delete-confirm"
            >
              Eliminar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
