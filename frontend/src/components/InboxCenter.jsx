import { useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Inbox, Trash2, Mail, MailOpen, ChevronDown, ChevronUp, RefreshCw, Paperclip, Download, Send, UserCircle2, Reply, BellRing, BellOff, AlarmClock } from 'lucide-react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Input } from './ui/input';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';
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
import { EmailHtmlFrame } from './EmailHtmlFrame';
import { NewMessageDialog } from './NewMessageDialog';
import { ChatThread } from './ChatThread';
import { emitInboxChanged } from '../utils/inboxEvents';
import { INBOX_RELOAD_LIST } from '../utils/inboxEvents';

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

function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return '';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  let v = bytes;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(v >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
}

/** Convierte una fecha ISO (UTC) al formato `YYYY-MM-DDThh:mm` que requiere
 * un <input type="datetime-local"> (hora local del navegador). */
function isoToLocalInput(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function formatRemindLabel(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString('es-VE', {
      day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

/**
 * "Recuérdame" — control por notificación del sistema. Permite fijar (o quitar)
 * una fecha/hora de recordatorio. Al vencer, el backend dispara una alerta en
 * vivo (toast WS) y aquí se marca con un badge "Vencido".
 */
function ReminderControl({ msg, onSave }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(isoToLocalInput(msg.remind_at));
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) setDraft(isoToLocalInput(msg.remind_at));
  }, [open, msg.remind_at]);

  const hasReminder = !!msg.remind_at;
  const due = !!msg.remind_due;

  const save = async (clear = false) => {
    if (!clear && !draft) {
      toast.error('Selecciona una fecha y hora');
      return;
    }
    setSaving(true);
    try {
      const isoUtc = clear ? null : new Date(draft).toISOString();
      await onSave(msg.message_id, isoUtc);
      setOpen(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex items-center gap-1.5 shrink-0">
      {hasReminder && (
        <Badge
          className={`text-[10px] font-semibold gap-1 ${
            due ? 'bg-rose-600 text-white animate-pulse' : 'bg-indigo-100 text-indigo-700'
          }`}
          data-testid={`inbox-remind-chip-${msg.message_id}`}
          data-remind-due={due ? 'true' : 'false'}
        >
          <AlarmClock size={10} />
          {due ? 'Vencido' : formatRemindLabel(msg.remind_at)}
        </Badge>
      )}
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className={`shrink-0 ${hasReminder ? 'text-indigo-600 hover:bg-indigo-50' : 'text-slate-400 hover:bg-slate-100 hover:text-indigo-600'}`}
            title="Recuérdame"
            data-testid={`inbox-remind-btn-${msg.message_id}`}
          >
            <BellRing size={16} />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-72" align="end" data-testid={`inbox-remind-popover-${msg.message_id}`}>
          <div className="space-y-3">
            <div>
              <p className="text-sm font-semibold text-slate-800 flex items-center gap-1.5">
                <BellRing size={14} className="text-indigo-600" />
                Recuérdame
              </p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Recibirás una alerta cuando llegue la fecha.
              </p>
            </div>
            <Input
              type="datetime-local"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              className="text-sm"
              data-testid={`inbox-remind-input-${msg.message_id}`}
            />
            <div className="flex items-center justify-between gap-2">
              {hasReminder ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => save(true)}
                  disabled={saving}
                  className="text-rose-600 border-rose-200 hover:bg-rose-50"
                  data-testid={`inbox-remind-clear-${msg.message_id}`}
                >
                  <BellOff size={13} className="mr-1" />
                  Quitar
                </Button>
              ) : <span />}
              <Button
                size="sm"
                onClick={() => save(false)}
                disabled={saving}
                className="bg-indigo-600 hover:bg-indigo-700 text-white"
                data-testid={`inbox-remind-save-${msg.message_id}`}
              >
                {saving ? 'Guardando…' : 'Guardar'}
              </Button>
            </div>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
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
      // Mantiene el banner global sincronizado con el estado de la bandeja.
      emitInboxChanged();
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

  // Recarga la bandeja cuando otro componente (ChatThread al leer, WS al recibir)
  // solicita refrescar el listado, para mantener los badges sincronizados.
  useEffect(() => {
    const onReload = () => load();
    window.addEventListener(INBOX_RELOAD_LIST, onReload);
    return () => window.removeEventListener(INBOX_RELOAD_LIST, onReload);
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
        emitInboxChanged();
      } catch {
        /* silencio: lectura es best-effort */
      }
    }
  };

  const confirmDelete = async () => {
    if (!deletingTarget) return;
    try {
      if (deletingTarget._isConversation) {
        await api.delete(`/inbox/conversations/${deletingTarget.message_id}`);
      } else {
        await api.delete(`/inbox/${deletingTarget.message_id}`);
      }
      // Refrescar el listado para reflejar el cambio (conv archivada, msg borrado)
      await load();
      toast.success(deletingTarget._isConversation ? 'Conversación archivada' : 'Mensaje eliminado');
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Error';
      toast.error(`No se pudo eliminar: ${detail}`);
    } finally {
      setDeletingTarget(null);
    }
  };

  const handleSetReminder = useCallback(async (messageId, isoUtcOrNull) => {
    try {
      await api.patch(`/inbox/${messageId}/remind`, { remind_at: isoUtcOrNull });
      // Optimista: reflejar el cambio sin recargar todo el listado.
      setMessages((prev) =>
        prev.map((m) =>
          m.message_id === messageId
            ? {
                ...m,
                remind_at: isoUtcOrNull,
                remind_due: isoUtcOrNull ? new Date(isoUtcOrNull) <= new Date() : false,
              }
            : m,
        ),
      );
      toast.success(isoUtcOrNull ? 'Recordatorio guardado' : 'Recordatorio eliminado');
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Error';
      toast.error(`No se pudo guardar el recordatorio: ${detail}`);
    }
  }, []);

  const [downloading, setDownloading] = useState({}); // { 'msg_id-idx': true }
  const [composeOpen, setComposeOpen] = useState(false);
  const [composeInitial, setComposeInitial] = useState(null);
  const [chatConvId, setChatConvId] = useState(null);
  const [chatOpen, setChatOpen] = useState(false);

  const openChatThread = (convId) => {
    setChatConvId(convId);
    setChatOpen(true);
  };

  // Deep-link: si llegamos con ?conv=<id> (p.ej. desde el toast de un mensaje
  // interno), abrimos esa conversación y limpiamos el query param para no
  // reabrirla al refrescar.
  const location = useLocation();
  const navigate = useNavigate();
  useEffect(() => {
    const conv = new URLSearchParams(location.search).get('conv');
    if (conv) {
      setChatConvId(conv);
      setChatOpen(true);
      navigate('/dashboard', { replace: true });
    }
  }, [location.search, navigate]);

  /**
   * Iter47: abrir el modal de composición con pre-relleno para responder
   * un mensaje user-to-user. Recipient = remitente original, asunto con
   * prefijo "Re:" (sin duplicarlo) y body con cita del original.
   */
  const handleReply = (msg) => {
    if (!msg?.is_user_message || !msg?.from_user_id) return;
    const senderEmail = msg.from_user_email || '';
    const senderName = msg.from_user_name || senderEmail || 'Usuario';
    const subj = msg.subject || '';
    const replySubject = /^re:\s*/i.test(subj) ? subj : `Re: ${subj}`;
    // Cita estilo email: prefijar cada línea con "> "
    const originalBody = msg.body_plain || '';
    const quoted = originalBody
      .split('\n')
      .map((l) => `> ${l}`)
      .join('\n');
    const replyBody = `\n\n\n----- Mensaje original -----\nDe: ${senderName}\n${quoted}`;
    setComposeInitial({
      recipients: [{ user_id: msg.from_user_id, full_name: senderName, email: senderEmail }],
      subject: replySubject,
      body: replyBody,
    });
    setComposeOpen(true);
  };

  const handleDownloadAttachment = async (messageId, index, filename) => {
    const key = `${messageId}-${index}`;
    if (downloading[key]) return; // evita doble click
    setDownloading((prev) => ({ ...prev, [key]: true }));
    let blobUrl = null;
    let anchor = null;
    try {
      // Usar fetch directo (no axios) — axios tiene un bug conocido al
      // procesar respuestas de error 4xx cuando `responseType` es 'blob':
      // intenta leer `responseText` del XHR y lanza un TypeError que rebota
      // a `window.onerror` como "Script error." opaco. fetch nos da control
      // total y maneja blobs correctamente.
      const token = localStorage.getItem('session_token') || '';
      const url = `${process.env.REACT_APP_BACKEND_URL}/api/inbox/${messageId}/attachments/${index}`;
      const res = await fetch(url, {
        method: 'GET',
        credentials: 'include',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) {
        if (res.status === 410) {
          toast.error('Este adjunto pertenece a un mensaje antiguo y ya no está disponible.');
        } else if (res.status === 404) {
          toast.error('Adjunto no encontrado.');
        } else if (res.status === 401) {
          toast.error('Sesión expirada. Vuelve a iniciar sesión.');
        } else {
          toast.error(`No se pudo descargar (HTTP ${res.status})`);
        }
        return;
      }
      const mime = res.headers.get('content-type') || 'application/octet-stream';
      const data = await res.arrayBuffer();
      const blob = new Blob([data], { type: mime });
      blobUrl = window.URL.createObjectURL(blob);
      anchor = document.createElement('a');
      anchor.style.display = 'none';
      anchor.href = blobUrl;
      anchor.download = filename || `adjunto-${index}`;
      anchor.rel = 'noopener';
      document.body.appendChild(anchor);
      anchor.click();
      toast.success(`Descargando ${filename}`);
    } catch (err) {
      toast.error(`No se pudo descargar: ${err?.message || 'Error de red'}`);
    } finally {
      // Limpieza diferida — el navegador todavía está procesando el click.
      setTimeout(() => {
        if (blobUrl) {
          try { window.URL.revokeObjectURL(blobUrl); } catch { /* noop */ }
        }
        if (anchor && anchor.parentNode) {
          try { anchor.parentNode.removeChild(anchor); } catch { /* noop */ }
        }
      }, 250);
      setDownloading((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    }
  };

  const unreadCount = messages.filter((m) =>
    m.type === 'conversation' ? (m.unread_count || 0) > 0 : !m.read_at,
  ).length;

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
      {/* Cabecera — gradiente índigo/violeta vibrante para destacar el centro de mensajes
          como el canal principal de comunicación interna. */}
      <div className="flex items-center justify-between px-6 py-5 bg-gradient-to-r from-indigo-600 via-violet-600 to-fuchsia-600 text-white relative overflow-hidden">
        {/* Sutil "brillo" decorativo */}
        <div className="absolute -top-12 -right-8 w-48 h-48 bg-white/10 rounded-full blur-3xl pointer-events-none" />
        <div className="flex items-center gap-3 relative z-10">
          <div className="p-2.5 rounded-lg bg-white/20 backdrop-blur-sm">
            <Inbox size={22} className="text-white" />
          </div>
          <div>
            <h2 className="text-lg font-bold font-manrope tracking-tight">Centro de Mensajes</h2>
            <p className="text-xs text-indigo-100">
              Bandeja interna · {messages.length} mensaje{messages.length === 1 ? '' : 's'}
              {unreadCount > 0 && (
                <span className="ml-2 font-bold text-white">
                  · {unreadCount} sin leer
                </span>
              )}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 relative z-10">
          <Button
            onClick={() => { setComposeInitial(null); setComposeOpen(true); }}
            size="sm"
            className="bg-white text-violet-700 hover:bg-violet-50 hover:text-violet-800 font-semibold shadow-sm"
            data-testid="inbox-new-message-btn"
          >
            <Send size={14} className="mr-1.5" />
            Nuevo mensaje
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleRefresh}
            disabled={refreshing}
            className="text-white hover:bg-white/15 hover:text-white"
            data-testid="inbox-refresh-btn"
          >
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
          </Button>
        </div>
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
            // Iter48: conversaciones se renderizan diferente que las notificaciones
            // del sistema. La fila abre un panel de chat al hacer click; el
            // botón eliminar archiva el hilo completo (no un mensaje).
            if (msg.type === 'conversation') {
              const sla = SLA_STYLES[msg.sla_color] || SLA_STYLES.green;
              const unread = (msg.unread_count || 0) > 0;
              return (
                <li
                  key={msg.conversation_id}
                  className={`border-l-4 ${sla.border} ${sla.bg} transition-colors`}
                  data-testid={`inbox-conv-${msg.conversation_id}`}
                  data-sla={msg.sla_color}
                  data-type="conversation"
                >
                  <div className="px-6 py-4 flex items-start gap-4">
                    <button
                      type="button"
                      onClick={() => openChatThread(msg.conversation_id)}
                      className="flex-1 text-left flex items-start gap-3 group"
                      data-testid={`inbox-conv-open-${msg.conversation_id}`}
                    >
                      <div className="pt-0.5 relative">
                        <UserCircle2 size={22} className="text-violet-600" />
                        {unread && (
                          <span className="absolute -top-1 -right-1 bg-rose-500 text-white text-[9px] font-bold rounded-full min-w-[16px] h-[16px] flex items-center justify-center px-1">
                            {msg.unread_count > 9 ? '9+' : msg.unread_count}
                          </span>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span
                            className={`text-sm ${
                              unread ? 'font-bold text-slate-900' : 'font-medium text-slate-700'
                            } truncate`}
                          >
                            {msg.other_user_name}
                          </span>
                          <Badge className={`${sla.chip} text-[10px] font-bold uppercase`}>
                            {sla.label}
                          </Badge>
                          <Badge className="bg-violet-100 text-violet-700 text-[10px] font-semibold">
                            Chat · {msg.subject}
                          </Badge>
                        </div>
                        <p
                          className={`text-xs mt-0.5 truncate ${
                            unread ? 'text-slate-700 font-medium' : 'text-slate-500'
                          }`}
                          data-testid={`inbox-conv-preview-${msg.conversation_id}`}
                        >
                          {msg.last_preview || <span className="italic">Sin mensajes aún</span>}
                        </p>
                      </div>
                      <div className="text-slate-400 group-hover:text-violet-600 transition-colors text-[10px] self-center">
                        Abrir →
                      </div>
                    </button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-rose-500 hover:bg-rose-50 hover:text-rose-700 shrink-0"
                      onClick={() =>
                        setDeletingTarget({
                          message_id: msg.conversation_id,
                          subject: `Conversación con ${msg.other_user_name}`,
                          _isConversation: true,
                        })
                      }
                      data-testid={`inbox-conv-delete-${msg.conversation_id}`}
                      title="Archivar conversación"
                    >
                      <Trash2 size={16} />
                    </Button>
                  </div>
                </li>
              );
            }

            // --- Notificación del sistema (comportamiento original) ---
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
                        {msg.is_user_message && msg.from_user_name && (
                          <Badge
                            className="bg-violet-100 text-violet-700 text-[10px] font-semibold gap-1"
                            data-testid={`inbox-msg-from-${msg.message_id}`}
                          >
                            <UserCircle2 size={10} />
                            De: {msg.from_user_name}
                          </Badge>
                        )}
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
                  <ReminderControl msg={msg} onSave={handleSetReminder} />
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
                    <EmailHtmlFrame
                      html={msg.body_html || ''}
                      title={msg.subject}
                      testId={`inbox-msg-body-${msg.message_id}`}
                    />
                    {msg.is_user_message && msg.from_user_id && (
                      <div className="mt-3 flex justify-end">
                        <Button
                          size="sm"
                          onClick={() => handleReply(msg)}
                          className="bg-violet-600 hover:bg-violet-700 text-white"
                          data-testid={`inbox-msg-reply-${msg.message_id}`}
                        >
                          <Reply size={14} className="mr-1.5" />
                          Responder
                        </Button>
                      </div>
                    )}
                    {msg.attachments_meta && msg.attachments_meta.length > 0 && (
                      <div className="mt-4">
                        <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                          <Paperclip size={12} />
                          Adjuntos ({msg.attachments_meta.length})
                        </div>
                        <div className="flex flex-wrap gap-2" data-testid={`inbox-msg-attachments-${msg.message_id}`}>
                          {msg.attachments_meta.map((a, idx) => {
                            const dlKey = `${msg.message_id}-${idx}`;
                            const isDownloading = !!downloading[dlKey];
                            return (
                              <button
                                key={`${msg.message_id}-att-${idx}`}
                                type="button"
                                onClick={() => handleDownloadAttachment(msg.message_id, idx, a.filename)}
                                disabled={isDownloading}
                                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md border border-slate-200 bg-white hover:bg-blue-50 hover:border-blue-300 transition-colors group disabled:opacity-60 disabled:cursor-wait"
                                data-testid={`inbox-att-download-${msg.message_id}-${idx}`}
                                title={`Descargar ${a.filename}`}
                              >
                                {isDownloading ? (
                                  <RefreshCw size={14} className="animate-spin text-blue-600" />
                                ) : (
                                  <Download size={14} className="text-slate-400 group-hover:text-blue-600" />
                                )}
                                <span className="text-xs font-medium text-slate-700 group-hover:text-blue-700 truncate max-w-[260px]">
                                  {a.filename}
                                </span>
                                {a.size_bytes > 0 && (
                                  <span className="text-[10px] text-slate-400">{formatBytes(a.size_bytes)}</span>
                                )}
                              </button>
                            );
                          })}
                        </div>
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

      <NewMessageDialog
        open={composeOpen}
        onOpenChange={setComposeOpen}
        onSent={() => load()}
        initialData={composeInitial}
      />

      <ChatThread
        conversationId={chatConvId}
        open={chatOpen}
        onOpenChange={setChatOpen}
        onChanged={() => load()}
      />
    </div>
  );
}
