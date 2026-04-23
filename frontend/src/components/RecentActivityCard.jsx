import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity, ChevronRight, RefreshCw } from 'lucide-react';
import api from '../utils/api';

const PRIORITY_META = {
  high: { dot: 'bg-red-500', pill: 'bg-red-100 text-red-700', label: 'Alta' },
  medium: { dot: 'bg-amber-500', pill: 'bg-amber-100 text-amber-700', label: 'Media' },
  low: { dot: 'bg-slate-400', pill: 'bg-slate-100 text-slate-600', label: 'Baja' },
};

function timeAgo(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const s = Math.floor((Date.now() - d.getTime()) / 1000);
  if (s < 60) return 'ahora';
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

/**
 * RecentActivityCard — feed global de las últimas 5 notificaciones empresa-wide.
 * Visible sólo para admin/director. Se auto-oculta si el endpoint devuelve 403.
 */
export const RecentActivityCard = ({ limit = 5 }) => {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [allowed, setAllowed] = useState(true);

  const fetchActivity = async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/notifications/recent-activity?limit=${limit}`);
      setItems(data.items || []);
      setAllowed(true);
    } catch (e) {
      if (e?.response?.status === 403) {
        setAllowed(false);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchActivity();
    // Refresh cada 60s para que se mantenga vivo sin hacerlo demasiado pesado
    const id = setInterval(fetchActivity, 60000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [limit]);

  if (!allowed) return null;

  return (
    <div className="bg-white rounded-lg border border-slate-200 overflow-hidden" data-testid="dashboard-recent-activity">
      <header className="px-5 py-3 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-white flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center">
            <Activity size={16} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-800">Actividad Reciente</h3>
            <p className="text-[11px] text-slate-400">Últimos {limit} eventos · empresa completa</p>
          </div>
        </div>
        <button
          onClick={fetchActivity}
          disabled={loading}
          className="p-1.5 rounded hover:bg-slate-100 text-slate-500"
          title="Refrescar"
          data-testid="dashboard-activity-refresh"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </header>

      {loading && items.length === 0 ? (
        <div className="py-8 text-center text-xs text-slate-400">Cargando...</div>
      ) : items.length === 0 ? (
        <div className="py-10 text-center text-xs text-slate-400 px-4">
          <Activity size={24} className="mx-auto mb-2 text-slate-300" />
          Aún no hay actividad registrada en el sistema.
        </div>
      ) : (
        <ul className="divide-y divide-slate-100">
          {items.map((n) => {
            const meta = PRIORITY_META[n.priority] || PRIORITY_META.medium;
            const clickable = !!n.link;
            return (
              <li
                key={n.notification_id}
                className={`px-5 py-3 flex items-start gap-3 ${clickable ? 'cursor-pointer hover:bg-slate-50' : ''}`}
                onClick={clickable ? () => navigate(n.link) : undefined}
                data-testid={`dashboard-activity-item-${n.notification_id}`}
              >
                <span className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${meta.dot}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium text-slate-800 line-clamp-1">{n.title}</p>
                    <span className="text-[10px] text-slate-400 shrink-0">{timeAgo(n.created_at)}</span>
                  </div>
                  {n.message && (
                    <p className="text-xs text-slate-500 line-clamp-1 mt-0.5">{n.message}</p>
                  )}
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${meta.pill}`}>
                      {meta.label}
                    </span>
                    <span className="text-[10px] text-slate-400">{n.category}</span>
                  </div>
                </div>
                {clickable && <ChevronRight size={14} className="text-slate-300 shrink-0 mt-1" />}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};

export default RecentActivityCard;
