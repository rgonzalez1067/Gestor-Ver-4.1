import { useState } from 'react';
import { MessageSquare, AlertTriangle, Bell, X, Volume2, VolumeX, ArrowRight } from 'lucide-react';
import { isNotifMuted, setNotifMuted } from '../utils/notificationSound';

const VARIANTS = {
  red: { bg: 'bg-red-600', ring: 'ring-red-300/70', Icon: AlertTriangle },
  orange: { bg: 'bg-orange-500', ring: 'ring-orange-300/70', Icon: Bell },
  amber: { bg: 'bg-amber-500', ring: 'ring-amber-300/70', Icon: Bell },
  purple: { bg: 'bg-purple-600', ring: 'ring-purple-300/70', Icon: MessageSquare },
};

export const IntenseAlertToast = ({ variant = 'orange', title, message, onView, onClose }) => {
  const v = VARIANTS[variant] || VARIANTS.orange;
  const Icon = v.Icon;
  const [muted, setMuted] = useState(isNotifMuted());

  const toggleMute = () => {
    const nv = !muted;
    setMuted(nv);
    setNotifMuted(nv);
  };

  return (
    <div
      className={`w-[360px] ${v.bg} text-white rounded-xl shadow-2xl ring-2 ${v.ring} overflow-hidden`}
      data-testid="intense-alert-toast"
      data-variant={variant}
    >
      <div className="flex items-start gap-3 p-4">
        <div className="shrink-0 mt-0.5 bg-white/20 rounded-lg p-2">
          <Icon size={20} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-bold text-sm leading-snug break-words" data-testid="intense-alert-title">{title}</p>
          {message && <p className="text-xs text-white/90 mt-0.5 break-words line-clamp-3">{message}</p>}
          <div className="flex items-center gap-2 mt-2.5">
            {onView && (
              <button
                onClick={onView}
                className="inline-flex items-center gap-1 bg-white text-slate-900 text-xs font-semibold px-3 py-1.5 rounded-lg hover:bg-white/90 transition-colors"
                data-testid="intense-alert-view-btn"
              >
                Ver mensaje <ArrowRight size={13} />
              </button>
            )}
            <button
              onClick={toggleMute}
              className="p-1.5 rounded-lg hover:bg-white/15 transition-colors"
              title={muted ? 'Activar sonido' : 'Silenciar sonido'}
              data-testid="intense-alert-mute-btn"
            >
              {muted ? <VolumeX size={15} /> : <Volume2 size={15} />}
            </button>
          </div>
        </div>
        <button
          onClick={onClose}
          className="shrink-0 p-1 rounded-lg hover:bg-white/15 transition-colors"
          aria-label="Cerrar"
          data-testid="intense-alert-close-btn"
        >
          <X size={16} />
        </button>
      </div>
    </div>
  );
};

export default IntenseAlertToast;
