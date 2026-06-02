import { Mail, AlertTriangle } from 'lucide-react';
import { useUnreadMessages } from '../context/UnreadMessagesContext';

/**
 * Banner global persistente (fixed, esquina superior derecha) que avisa de forma
 * permanente que hay mensajes sin leer en el Centro de Mensajes.
 * - Sin temporizador de auto-cierre y sin botón de cerrar manual.
 * - Desaparece de forma reactiva cuando `unread` vuelve a 0 (al leer los mensajes).
 */
export const GlobalUnreadBanner = () => {
  const { unread } = useUnreadMessages();

  if (!unread || unread <= 0) return null;

  return (
    <div
      className="fixed top-5 right-5 z-[2147483646] max-w-[360px]"
      data-testid="global-unread-banner"
      role="alert"
      aria-live="assertive"
    >
      <div className="flex items-center gap-3 rounded-xl bg-red-600 text-white px-4 py-3 shadow-2xl ring-2 ring-red-300/70">
        <span className="relative shrink-0 flex items-center justify-center">
          <span className="absolute inline-flex h-9 w-9 rounded-full bg-white/20 animate-ping" />
          <span className="relative inline-flex items-center justify-center h-9 w-9 rounded-lg bg-white/20">
            <Mail size={18} className="animate-pulse" />
          </span>
        </span>
        <div className="min-w-0">
          <p className="flex items-center gap-1 text-sm font-bold leading-snug">
            <AlertTriangle size={14} className="shrink-0" />
            ¡Atención!
          </p>
          <p className="text-xs text-white/95 leading-snug" data-testid="global-unread-banner-text">
            Tiene {unread === 1 ? 'un mensaje pendiente' : `${unread} mensajes pendientes`} por leer en su bandeja.
          </p>
        </div>
      </div>
    </div>
  );
};

export default GlobalUnreadBanner;
