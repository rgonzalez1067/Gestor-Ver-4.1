import { useState, useEffect, useRef } from 'react';
import { Bell, BellRing } from 'lucide-react';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import useNotifications from '../hooks/useNotifications';
import IntenseAlertToast from './IntenseAlertToast';
import AlertsCenterModal from './AlertsCenterModal';
import { playNotifBeep } from '../utils/notificationSound';

export const NotificationBell = () => {
  const navigate = useNavigate();
  const { unread, connected, refresh, setOnIncoming } = useNotifications();
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
              if (link) navigate(link);
            } : undefined}
            onClose={() => toast.dismiss(id)}
          />
        ),
        { duration: Infinity }
      );
    });
  }, [setOnIncoming, navigate]);

  const BellIcon = pulse ? BellRing : Bell;

  return (
    <div className="relative" data-bell-container data-testid="notification-bell-container">
      <button
        onClick={() => setCenterOpen(true)}
        className={`relative p-2 rounded-lg hover:bg-slate-100 transition-colors ${pulse ? 'animate-pulse' : ''}`}
        data-testid="notification-bell-btn"
        aria-label="Centro de Alertas"
        title={connected ? 'Centro de Alertas (en vivo)' : 'Centro de Alertas (desconectado)'}
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

      <AlertsCenterModal
        open={centerOpen}
        onClose={() => setCenterOpen(false)}
        onChanged={refresh}
      />
    </div>
  );
};

export default NotificationBell;
