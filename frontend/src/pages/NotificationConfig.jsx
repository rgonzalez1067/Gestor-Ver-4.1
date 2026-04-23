import { useState, useEffect, useCallback, useMemo } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Switch } from '../components/ui/switch';
import { ArrowLeft, Bell, RefreshCw, Save } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import { usePermission } from '../hooks/usePermission';

const PRIORITY_META = {
  high:   { label: 'Alta', icon: '🔴', pill: 'bg-red-100 text-red-700 border-red-200' },
  medium: { label: 'Media', icon: '🟡', pill: 'bg-amber-100 text-amber-700 border-amber-200' },
  low:    { label: 'Baja', icon: '🟢', pill: 'bg-emerald-100 text-emerald-700 border-emerald-200' },
};

export const NotificationConfig = () => {
  const navigate = useNavigate();
  const { user } = usePermission('configuracion');
  const isAdmin = user?.role === 'admin';

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState(null);

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/notifications/config');
      setItems(data.items || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'No se pudo cargar la configuración');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchConfig(); }, [fetchConfig]);

  const updateItem = async (eventType, patch) => {
    setSavingKey(eventType);
    try {
      const { data } = await api.put(`/notifications/config/${eventType}`, patch);
      setItems((prev) => prev.map((it) => it.event_type === eventType ? data : it));
      toast.success('Configuración actualizada');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error al actualizar');
    } finally {
      setSavingKey(null);
    }
  };

  const grouped = useMemo(() => {
    const map = {};
    for (const it of items) {
      const cat = it.category || 'General';
      if (!map[cat]) map[cat] = [];
      map[cat].push(it);
    }
    return map;
  }, [items]);

  const totalActive = items.filter((it) => it.is_active).length;

  return (
    <div className="flex h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto p-6 lg:p-8">
          <div className="flex items-center gap-3 mb-6">
            <Button variant="ghost" size="sm" onClick={() => navigate('/settings')} data-testid="nc-back-btn">
              <ArrowLeft size={18} className="mr-1" />
              Configuración
            </Button>
          </div>

          <div className="mb-6">
            <h1 className="text-3xl font-bold text-slate-900 font-manrope flex items-center gap-2" data-testid="nc-page-title">
              <Bell size={28} className="text-indigo-600" />
              Configuración de Notificaciones Push
            </h1>
            <p className="text-sm text-slate-600 mt-1">
              Controla qué eventos del sistema generan notificaciones en vivo para los usuarios.
              Solo los eventos activos aparecerán en la campana y como toast. Todas las notificaciones
              llegan automáticamente a los administradores.
            </p>
            <div className="mt-3 flex items-center gap-4 text-xs">
              <span className="px-2 py-1 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
                {totalActive} de {items.length} eventos activos
              </span>
              <button
                onClick={fetchConfig}
                disabled={loading}
                className="text-slate-500 hover:text-slate-800 flex items-center gap-1"
                data-testid="nc-refresh-btn"
              >
                <RefreshCw size={14} />
                Recargar
              </button>
            </div>
          </div>

          {!isAdmin && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-amber-700 mb-4" data-testid="nc-admin-warning">
              Solo los administradores pueden modificar esta configuración.
            </div>
          )}

          {loading ? (
            <div className="py-16 text-center text-sm text-slate-400">Cargando eventos...</div>
          ) : (
            <div className="space-y-6">
              {Object.entries(grouped).map(([cat, list]) => (
                <section key={cat} className="bg-white rounded-lg border border-slate-200 overflow-hidden" data-testid={`nc-category-${cat.toLowerCase().replace(/\s+/g, '-')}`}>
                  <header className="px-5 py-3 border-b border-slate-200 bg-slate-50">
                    <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wider">{cat}</h2>
                  </header>
                  <ul className="divide-y divide-slate-100">
                    {list.map((it) => {
                      const meta = PRIORITY_META[it.priority] || PRIORITY_META.medium;
                      return (
                        <li key={it.event_type} className="flex items-center gap-4 px-5 py-4" data-testid={`nc-item-${it.event_type}`}>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <p className="text-sm font-medium text-slate-800">{it.label}</p>
                              {it.scheduled && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                                  ⏰ Programado
                                </span>
                              )}
                            </div>
                            <p className="text-[11px] text-slate-400 mt-0.5">{it.event_type}</p>
                          </div>

                          {/* Priority selector */}
                          <div className="flex items-center gap-1" data-testid={`nc-priority-${it.event_type}`}>
                            {['high', 'medium', 'low'].map((p) => {
                              const pmeta = PRIORITY_META[p];
                              const selected = it.priority === p;
                              return (
                                <button
                                  key={p}
                                  onClick={() => isAdmin && !savingKey && updateItem(it.event_type, { priority: p })}
                                  disabled={!isAdmin || savingKey === it.event_type || !it.is_active}
                                  className={`px-2 py-1 rounded-full text-[11px] border font-medium transition-colors ${
                                    selected ? pmeta.pill : 'bg-white text-slate-400 border-slate-200 hover:bg-slate-50'
                                  } ${(!isAdmin || !it.is_active) ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}`}
                                  data-testid={`nc-priority-${it.event_type}-${p}`}
                                  title={`Prioridad ${pmeta.label}`}
                                >
                                  {pmeta.icon} {pmeta.label}
                                </button>
                              );
                            })}
                          </div>

                          {/* Active toggle */}
                          <div className="flex items-center gap-2 min-w-[110px] justify-end">
                            <span className="text-xs text-slate-600 w-[52px] text-right">
                              {it.is_active ? 'Activo' : 'Inactivo'}
                            </span>
                            <Switch
                              checked={!!it.is_active}
                              onCheckedChange={(v) => isAdmin && updateItem(it.event_type, { is_active: !!v })}
                              disabled={!isAdmin || savingKey === it.event_type}
                              data-testid={`nc-toggle-${it.event_type}`}
                            />
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ))}
            </div>
          )}

          <p className="text-xs text-slate-500 mt-6">
            💡 Los eventos marcados como ⏰ Programado se evalúan una vez al día a las 08:00 (Caracas).
            Los demás son instantáneos vía WebSocket.
          </p>
        </div>
      </main>
    </div>
  );
};

export default NotificationConfig;
