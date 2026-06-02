import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Users, RefreshCw, Wifi, Building2, Shield } from 'lucide-react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import api from '../utils/api';

/**
 * ConnectedUsers — Iter57.
 *
 * Vista admin que lista en tiempo real los usuarios con conexión WebSocket
 * activa al backend. Se nutre del `ConnectionManager` interno del
 * `notification_service` (en memoria). Auto-refresh cada 15s + botón manual.
 */
export default function ConnectedUsers() {
  const navigate = useNavigate();
  const [data, setData] = useState({ items: [], total_users: 0, total_connections: 0 });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data: res } = await api.get('/admin/connected-users');
      setData(res || { items: [], total_users: 0, total_connections: 0 });
    } catch (err) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail || err?.message || 'Error';
      if (status === 403) {
        toast.error('Solo administradores pueden ver esta sección');
        navigate('/settings');
      } else {
        toast.error(`No se pudo cargar: ${detail}`);
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [navigate]);

  useEffect(() => {
    load();
    // Auto-refresh cada 15s para reflejar conexiones/desconexiones casi en vivo.
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [load]);

  const handleRefresh = () => { setRefreshing(true); load(); };

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 p-8" data-testid="connected-users-page">
        <div className="max-w-5xl mx-auto">
          <Button variant="ghost" size="sm" onClick={() => navigate('/settings')} className="mb-4 -ml-3" data-testid="back-to-settings">
            <ArrowLeft size={16} className="mr-2" /> Volver a Configuración
          </Button>

          {/* Header */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden mb-6">
            <div className="px-6 py-5 bg-gradient-to-r from-indigo-600 via-violet-600 to-fuchsia-600 text-white flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-lg bg-white/20"><Users size={22} /></div>
                <div>
                  <h1 className="text-lg font-bold font-manrope">Usuarios Conectados</h1>
                  <p className="text-xs text-indigo-100">Sesiones activas en tiempo real (auto-refresh cada 15s)</p>
                </div>
              </div>
              <Button variant="ghost" size="sm" onClick={handleRefresh} disabled={refreshing} className="text-white hover:bg-white/15 hover:text-white" data-testid="refresh-connected-btn">
                <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
              </Button>
            </div>

            {/* Métricas */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-px bg-slate-100">
              <div className="bg-white px-5 py-4">
                <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Usuarios en línea</p>
                <p className="text-2xl font-bold text-slate-900 font-manrope" data-testid="total-users">{data.total_users}</p>
              </div>
              <div className="bg-white px-5 py-4">
                <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Conexiones abiertas</p>
                <p className="text-2xl font-bold text-slate-900 font-manrope" data-testid="total-connections">{data.total_connections}</p>
              </div>
              <div className="bg-white px-5 py-4">
                <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Estado</p>
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="text-sm font-semibold text-emerald-700">En vivo</span>
                </div>
              </div>
            </div>
          </div>

          {/* Listado */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-5 py-3 border-b border-slate-100 bg-slate-50">
              <p className="text-xs font-bold uppercase tracking-wider text-slate-600">Sesiones activas</p>
            </div>
            {loading ? (
              <div className="px-6 py-10 text-center text-slate-500 text-sm">Cargando…</div>
            ) : data.items.length === 0 ? (
              <div className="px-6 py-10 text-center">
                <Wifi size={36} className="mx-auto text-slate-300 mb-2" />
                <p className="text-sm text-slate-500">Ningún usuario tiene sesión WebSocket activa en este momento.</p>
              </div>
            ) : (
              <ul className="divide-y divide-slate-100" data-testid="connected-users-list">
                {data.items.map((u) => (
                  <li key={u.user_id} className="px-5 py-3 flex items-center gap-4 hover:bg-slate-50 transition-colors" data-testid={`connected-${u.user_id}`}>
                    <div className="relative shrink-0">
                      {u.picture ? (
                        <img src={u.picture} alt="" className="w-10 h-10 rounded-full object-cover" />
                      ) : (
                        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-400 to-fuchsia-500 text-white flex items-center justify-center font-bold text-sm">
                          {(u.full_name || '?').slice(0, 1).toUpperCase()}
                        </div>
                      )}
                      <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-emerald-500 ring-2 ring-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="text-sm font-semibold text-slate-900 truncate">{u.full_name}</p>
                        {u.role === 'admin' && (
                          <Badge className="bg-fuchsia-100 text-fuchsia-700 text-[10px] gap-1"><Shield size={10} /> Admin</Badge>
                        )}
                        {u.sede && (
                          <Badge variant="outline" className="text-[10px]">{u.sede}</Badge>
                        )}
                      </div>
                      <p className="text-xs text-slate-500 truncate flex items-center gap-2">
                        {u.email}
                        {u.department && (<><span className="text-slate-300">·</span><span className="inline-flex items-center gap-1"><Building2 size={11} />{u.department}</span></>)}
                      </p>
                    </div>
                    <div className="shrink-0 text-right">
                      <p className="text-[11px] font-semibold text-slate-600">{u.connections} conexión{u.connections === 1 ? '' : 'es'}</p>
                      <p className="text-[10px] text-slate-400">Multi-tab</p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
