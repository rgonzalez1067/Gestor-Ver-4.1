import { useEffect, useState, useCallback } from 'react';
import { toast } from 'sonner';
import { AlertTriangle, Info, Megaphone } from 'lucide-react';

/**
 * Componente GLOBAL que recibe los "Mensajes Directos" del Administrador
 * (evento window 'direct-message') y los renderiza según su nivel:
 *  - low    → toast sutil (banner superior)
 *  - medium → modal bloqueante azul institucional, texto blanco
 *  - high   → modal bloqueante rojo alerta, texto blanco
 * Los niveles medium/high congelan el fondo (backdrop) y exigen confirmación.
 */
export default function DirectMessageAlert() {
  const [queue, setQueue] = useState([]);

  useEffect(() => {
    const handler = (ev) => {
      const msg = ev.detail || {};
      if ((msg.level || 'medium') === 'low') {
        toast(msg.body, {
          description: msg.from ? `De: ${msg.from}` : undefined,
          duration: 8000,
          className: 'bg-blue-600 text-white border-blue-700',
        });
        return;
      }
      setQueue((q) => [...q, msg]);
    };
    window.addEventListener('direct-message', handler);
    return () => window.removeEventListener('direct-message', handler);
  }, []);

  const dismiss = useCallback(() => setQueue((q) => q.slice(1)), []);

  const current = queue[0];
  if (!current) return null;

  const isHigh = current.level === 'high';
  const bg = isHigh ? 'bg-red-600' : 'bg-blue-700';
  const btn = isHigh ? 'bg-white text-red-700 hover:bg-red-50' : 'bg-white text-blue-800 hover:bg-blue-50';

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      data-testid="direct-message-overlay"
    >
      <div
        className={`${bg} text-white rounded-2xl shadow-2xl w-[60vw] max-w-3xl min-w-[320px] max-h-[85vh] overflow-y-auto p-8 sm:p-10 animate-in fade-in zoom-in-95 duration-200`}
        data-testid="direct-message-modal"
        role="alertdialog"
        aria-modal="true"
      >
        <div className="flex items-center gap-3 mb-5">
          {isHigh
            ? <AlertTriangle size={40} className="text-white shrink-0" />
            : <Megaphone size={40} className="text-white shrink-0" />}
          <div className="min-w-0">
            <h2 className="text-2xl sm:text-3xl font-bold leading-tight">
              {isHigh ? 'Mensaje Urgente' : 'Mensaje del Administrador'}
            </h2>
            {current.from && (
              <p className="text-white/80 text-sm mt-0.5">De: {current.from}</p>
            )}
          </div>
        </div>

        <p
          className="text-lg sm:text-xl leading-relaxed whitespace-pre-wrap text-white"
          data-testid="direct-message-body"
        >
          {current.body}
        </p>

        {queue.length > 1 && (
          <p className="mt-4 text-white/70 text-xs flex items-center gap-1">
            <Info size={13} /> Hay {queue.length - 1} mensaje(s) más en cola.
          </p>
        )}

        <div className="mt-8 flex justify-end">
          <button
            onClick={dismiss}
            className={`${btn} font-bold px-8 py-3 rounded-xl transition-colors text-base shadow-lg`}
            data-testid="direct-message-close"
            autoFocus
          >
            Entendido / Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}
