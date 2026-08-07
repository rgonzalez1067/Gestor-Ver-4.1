import { useState, useEffect, useRef } from 'react';
import { formatDateTime, formatDate, formatTime } from '../utils/dateFormat';
import { Bell, BellRing, Check, CheckCheck, X } from 'lucide-react';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import useNotifications from '../hooks/useNotifications';
import IntenseAlertToast from './IntenseAlertToast';
import AlertsCenterModal from './AlertsCenterModal';
import { playNotifBeep } from '../utils/notificationSound';

const PRIORITY_COLORS = {
  high: { bar: 'bg-red-500', pill: 'bg-red-100 text-red-700', dot: 'bg-red-500' },
  medium: { bar: 'bg-amber-500', pill: 'bg-amber-100 text-amber-700', dot: 'bg-amber-500' },
  low: { bar: 'bg-slate-300', pill: 'bg-slate-100 text-slate-600', dot: 'bg-slate-400' },
};

const PRIORITY_LABEL = { high: 'Alta', medium: 'Media', low: 'Baja' };

function timeAgo(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const s = Math.floor((Date.now() - d.getTime()) / 1000);
  if (s < 60) return 'ahora';
  if (s < 3600) return `hace ${Math.floor(s / 60)} min`;
  if (s < 86400) return `hace ${Math.floor(s / 3600)} h`;
  const days = Math.floor(s / 86400);
  if (days < 7) return `hace ${days} día${days === 1 ? '' : 's'}`;
  return formatDate(iso);
}

export const NotificationBell = () => {
  const navigate = useNavigate();
  const { items, unread, connected, markRead, markAllRead, refresh, setOnIncoming } = useNotifications();
  const [open, setOpen] = useState(false);
  const [centerOpen, setCenterOpen] = useState(false);
  const [pulse, setPulse] = useState(false);
  const seenRef = useRef(new Set());

  // Alerta intensa persistente cuando llega una notificación o mensaje interno.
  // Color por prioridad: rojo=alta, naranja=media, amarillo=baja, morado=mensaje interno.
  useEffect(() => {
    setOnIncoming((payload) => {
      const isInternal = payload?.kind === 'internal';
      const isReminder = payload?.kind === 'reminder';

      // Dedupe: evita toasts repetidos si el mismo evento llega por varias
      // conexiones WS del mismo usuario.
      const key = isInternal
        ? `int:${payload?.conversation_id || ''}:${payload?.created_at || ''}`
        : isReminder
          ? `rem:${payload?.message_id || ''}`
          : `ntf:${payload?.notification_id || ''}`;
      if (seenRef.current.has(key)) return;
      seenRef.current.add(key);
      if (seenRef.current.size > 200) {
        seenRef.current = new Set(Array.from(seenRef.current).slice(-100));
      }

      const priority = payload?.priority || 'medium';

      let variant;
      let title;
      let message;
      let link;

      if (isInternal) {
        variant = 'purple';
        title = `Nuevo mensaje de ${payload.from_user_name || 'un usuario'}`;
        message = payload.preview || payload.subject || '';
        // Deep-link directo a la conversación dentro del Centro de Mensajes.
        link = payload.conversation_id
          ? `/dashboard?conv=${encodeURIComponent(payload.conversation_id)}`
          : '/dashboard';
      } else if (isReminder) {
        variant = 'red';
        title = '⏰ Recordatorio vencido';
        message = payload.subject
          ? `${payload.subject}${payload.quote_number ? ` · ${payload.quote_number}` : ''}`
          : 'Tienes un recordatorio pendiente en tu Centro de Mensajes.';
        link = payload.link || '/dashboard';
      } else {
        variant = priority === 'high' ? 'red' : priority === 'low' ? 'amber' : 'orange';
        title = payload?.title || 'Nueva notificación';
        message = payload?.message || '';
        link = payload?.link || null;
      }

      playNotifBeep();

      if (isInternal || isReminder || priority === 'high') {
        setPulse(true);
        setTimeout(() => setPulse(false), 3000);
      }

      // Toast intenso persistente (no se auto-cierra). El CTA "Ver mensaje"
      // aplica a mensajes internos (lleva a la conversación) y a recordatorios
      // (lleva al Centro de Mensajes). Para notificaciones de eventos del
      // sistema NO se muestra, porque el enlace lleva a una pantalla operativa.
      const showView = isInternal || isReminder;
      toast.custom(
        (id) => (
          <IntenseAlertToast
            variant={variant}
            title={title}
            message={message}
            onView={showView ? () => {
              toast.dismiss(id);
              setOpen(false);
              if (link) navigate(link);
            } : undefined}
            onClose={() => toast.dismiss(id)}
          />
        ),
        { duration: Infinity }
      );
    });
  }, [setOnIncoming, navigate]);

  // Cerrar al clickear afuera
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (!e.target.closest('[data-bell-container]')) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const onClickItem = async (n) => {
    if (!n.is_read) await markRead(n.notification_id);
    setOpen(false);
    if (n.link) navigate(n.link);
  };

  const BellIcon = pulse ? BellRing : Bell;

  return (
    <div className="relative" data-bell-container data-testid="notification-bell-container">
      <button
        onClick={() => setOpen((v) => !v)}
        className={`relative p-2 rounded-lg hover:bg-slate-100 transition-colors ${pulse ? 'animate-pulse' : ''}`}
        data-testid="notification-bell-btn"
        aria-label="Notificaciones"
        title={connected ? 'Notificaciones (en vivo)' : 'Notificaciones (desconectado)'}
      >
        <BellIcon size={20} className={pulse ? 'text-red-600' : 'text-slate-700'} />
        {unread > 0 && (
          <span
            className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 rounded-full bg-red-600 text-white text-[10px] font-bold flex items-center justify-center"
            data-testid="notification-unread-badge"
          >
            {unread > 99 ? '99+' : unread}
          </span>
        )}
        {/* Indicador de conexión WS */}
        <span
          className={`absolute bottom-0.5 right-0.5 w-2 h-2 rounded-full border border-white ${connected ? 'bg-emerald-500' : 'bg-slate-400'}`}
          aria-hidden
        />
      </button>

      {open && (
        <div
          className="absolute right-0 mt-2 w-[400px] max-h-[70vh] bg-white rounded-lg shadow-2xl border border-slate-200 overflow-hidden z-50 flex flex-col"
          data-testid="notification-dropdown"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-slate-50">
            <h3 className="font-semibold text-slate-900 text-sm">Notificaciones</h3>
            <div className="flex items-center gap-1">
              {unread > 0 && (
                <button
                  onClick={markAllRead}
                  className="text-xs text-indigo-600 hover:text-indigo-800 px-2 py-1 rounded hover:bg-indigo-50 flex items-center gap-1"
                  data-testid="notification-mark-all-read"
                  title="Marcar todas como leídas"
                >
                  <CheckCheck size={14} />
                  Marcar leídas
                </button>
              )}
              <button
                onClick={() => setOpen(false)}
                className="p-1 rounded hover:bg-slate-200 text-slate-500"
                aria-label="Cerrar"
              >
                <X size={14} />
              </button>
            </div>
          </div>

          {/* Lista scrollable */}
          <div className="overflow-y-auto flex-1">
            {items.length === 0 ? (
              <div className="py-12 text-center text-sm text-slate-400 px-6">
                <Bell size={32} className="mx-auto mb-2 text-slate-300" />
                No tienes notificaciones aún.
              </div>
            ) : (
              <ul className="divide-y divide-slate-100">
                {items.map((n) => {
                  const colors = PRIORITY_COLORS[n.priority] || PRIORITY_COLORS.medium;
                  return (
                    <li
                      key={n.notification_id}
                      className={`flex gap-3 px-4 py-3 cursor-pointer hover:bg-slate-50 transition-colors ${!n.is_read ? 'bg-indigo-50/30' : ''}`}
                      onClick={() => onClickItem(n)}
                      data-testid={`notification-item-${n.notification_id}`}
                    >
                      <div className={`w-1 rounded-full ${colors.bar}`} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2">
                          <p className={`text-sm ${!n.is_read ? 'font-semibold text-slate-900' : 'font-medium text-slate-700'}`}>
                            {n.title}
                          </p>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-full shrink-0 ${colors.pill}`}>
                            {PRIORITY_LABEL[n.priority] || n.priority}
                          </span>
                        </div>
                        {n.message && (
                          <p className="text-xs text-slate-600 mt-0.5 line-clamp-2">{n.message}</p>
                        )}
                        <div className="flex items-center justify-between mt-1">
                          <span className="text-[10px] text-slate-400">{timeAgo(n.created_at)} · {n.category}</span>
                          {!n.is_read && <span className={`w-2 h-2 rounded-full ${colors.dot}`} />}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {/* Footer */}
          <div className="border-t border-slate-200 px-3 py-2 flex items-center justify-between gap-2">
            <span className={`text-[10px] ${connected ? 'text-emerald-600' : 'text-slate-400'}`}>
              {connected ? '● En vivo' : '○ Sin conexión'}
            </span>
            <button
              onClick={() => { setOpen(false); setCenterOpen(true); }}
              className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 px-2 py-1 rounded hover:bg-indigo-50"
              data-testid="notification-open-center"
            >
              Ver todas las alertas
            </button>
          </div>
        </div>
      )}

      <AlertsCenterModal
        open={centerOpen}
        onClose={() => setCenterOpen(false)}
        onChanged={refresh}
      />
    </div>
  );
};

export default NotificationBell;
