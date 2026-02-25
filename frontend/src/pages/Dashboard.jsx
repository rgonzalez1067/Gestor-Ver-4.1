import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { FileText, Users, Building2, TrendingUp, CreditCard, Package, Bell, AlertTriangle, Clock, CalendarCheck } from 'lucide-react';
import { Button } from '../components/ui/button';
import api from '../utils/api';
import { toast } from 'sonner';

export const Dashboard = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState({
    totalQuotes: 0, totalClients: 0, totalBanks: 0,
    totalMediosPago: 0, totalHardware: 0, exchangeRate: 0
  });
  const [recentQuotes, setRecentQuotes] = useState([]);
  const [alerts, setAlerts] = useState({ overdue: [], today: [], upcoming: [], total: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchDashboardData(); }, []);

  const fetchDashboardData = async () => {
    try {
      let quotesCount = 0, clientsCount = 0, banksCount = 0, servicesCount = 0, hardwareCount = 0, exchangeRate = 0;

      try { const r = await api.get('/quotes'); quotesCount = Array.isArray(r.data) ? r.data.length : 0; setRecentQuotes(Array.isArray(r.data) ? r.data.slice(0, 5) : []); } catch {}
      try { const r = await api.get('/clients'); clientsCount = Array.isArray(r.data) ? r.data.length : 0; } catch {}
      try { const r = await api.get('/banks'); banksCount = Array.isArray(r.data) ? r.data.length : 0; } catch {}
      try { const r = await api.get('/services'); servicesCount = Array.isArray(r.data) ? r.data.length : 0; } catch {}
      try { const r = await api.get('/hardware'); hardwareCount = Array.isArray(r.data) ? r.data.length : 0; } catch {}
      try { const r = await api.get('/exchange-rate/current'); exchangeRate = r.data?.rate || 0; } catch {}
      try { const r = await api.get('/dashboard/alerts'); setAlerts(r.data); } catch {}

      setStats({ totalQuotes: quotesCount, totalClients: clientsCount, totalBanks: banksCount,
        totalMediosPago: servicesCount, totalHardware: hardwareCount, exchangeRate });
    } catch {
      toast.error('Error al cargar datos del dashboard');
    } finally {
      setLoading(false);
    }
  };

  const statCards = [
    { title: 'Cotizaciones', value: stats.totalQuotes, icon: FileText, color: 'bg-sky-100 text-sky-700' },
    { title: 'Clientes', value: stats.totalClients, icon: Users, color: 'bg-emerald-100 text-emerald-700' },
    { title: 'Bancos', value: stats.totalBanks, icon: Building2, color: 'bg-purple-100 text-purple-700' },
    { title: 'Medios de Pago', value: stats.totalMediosPago, icon: CreditCard, color: 'bg-rose-100 text-rose-700' },
    { title: 'Dispositivos', value: stats.totalHardware, icon: Package, color: 'bg-orange-100 text-orange-700' },
    { title: 'Tasa BCV', value: stats.exchangeRate ? `${stats.exchangeRate.toFixed(2)} Bs/$` : '-', icon: TrendingUp, color: 'bg-amber-100 text-amber-700' }
  ];

  const chartData = [
    { name: 'Ene', cotizaciones: 12 }, { name: 'Feb', cotizaciones: 19 },
    { name: 'Mar', cotizaciones: 15 }, { name: 'Abr', cotizaciones: 22 },
    { name: 'May', cotizaciones: 18 }, { name: 'Jun', cotizaciones: 25 }
  ];

  const handleAlertClick = (alert) => {
    navigate(`/clients?bitacora=${alert.client_id}`);
  };

  if (loading) {
    return (
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center bg-white">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-green-600 mx-auto"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-white">
      <Sidebar />
      <main className="flex-1 p-8" data-testid="dashboard">
        <div className="max-w-7xl mx-auto">
          <div className="mb-8">
            <h1 className="text-4xl font-bold text-slate-900 font-manrope mb-2">Dashboard</h1>
            <p className="text-slate-600">Vista general del sistema</p>
          </div>

          {/* Stat Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-4 mb-8">
            {statCards.map((stat, index) => {
              const Icon = stat.icon;
              return (
                <div key={index} data-testid={`stat-${stat.title.toLowerCase().replace(/\s/g, '-')}`}
                  className="bg-white rounded-lg border border-slate-200 p-6 card-hover">
                  <div className="flex items-center justify-between mb-4">
                    <div className={`p-3 rounded-lg ${stat.color}`}><Icon size={24} /></div>
                  </div>
                  <h3 className="text-sm font-medium text-slate-500 uppercase tracking-wide mb-1">{stat.title}</h3>
                  <p className="text-3xl font-bold text-slate-900 font-manrope">{stat.value}</p>
                </div>
              );
            })}
          </div>

          {/* Alerts Widget */}
          {alerts.total > 0 && (
            <div className="mb-8 bg-white rounded-lg border border-slate-200 overflow-hidden" data-testid="alerts-widget">
              <div className="flex items-center gap-2 px-6 py-4 border-b border-slate-100 bg-slate-50">
                <Bell size={18} className="text-slate-700" />
                <h2 className="text-base font-semibold text-slate-900">Alertas de Seguimiento</h2>
                <span className="text-xs bg-slate-200 text-slate-700 rounded-full px-2 py-0.5 ml-1">{alerts.total}</span>
              </div>
              <div className="divide-y divide-slate-100 max-h-80 overflow-y-auto">
                {/* Overdue - Red */}
                {alerts.overdue.map(a => (
                  <button key={a.log_id} onClick={() => handleAlertClick(a)}
                    className="w-full flex items-center gap-3 px-6 py-3 hover:bg-red-50/50 transition-colors text-left"
                    data-testid={`alert-overdue-${a.log_id}`}>
                    <div className="w-2.5 h-2.5 rounded-full bg-red-500 shrink-0"></div>
                    <AlertTriangle size={14} className="text-red-500 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-900 truncate">{a.client_name} <span className="text-slate-400 font-normal">({a.client_rif})</span></p>
                      <p className="text-xs text-slate-500 truncate">{a.action || a.detail}</p>
                    </div>
                    <span className="text-xs text-red-600 font-medium shrink-0 bg-red-50 px-2 py-0.5 rounded">{a.follow_up_date}</span>
                  </button>
                ))}
                {/* Today - Yellow */}
                {alerts.today.map(a => (
                  <button key={a.log_id} onClick={() => handleAlertClick(a)}
                    className="w-full flex items-center gap-3 px-6 py-3 hover:bg-amber-50/50 transition-colors text-left"
                    data-testid={`alert-today-${a.log_id}`}>
                    <div className="w-2.5 h-2.5 rounded-full bg-amber-500 shrink-0"></div>
                    <Clock size={14} className="text-amber-500 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-900 truncate">{a.client_name} <span className="text-slate-400 font-normal">({a.client_rif})</span></p>
                      <p className="text-xs text-slate-500 truncate">{a.action || a.detail}</p>
                    </div>
                    <span className="text-xs text-amber-600 font-medium shrink-0 bg-amber-50 px-2 py-0.5 rounded">Hoy</span>
                  </button>
                ))}
                {/* Upcoming - Green */}
                {alerts.upcoming.map(a => (
                  <button key={a.log_id} onClick={() => handleAlertClick(a)}
                    className="w-full flex items-center gap-3 px-6 py-3 hover:bg-green-50/50 transition-colors text-left"
                    data-testid={`alert-upcoming-${a.log_id}`}>
                    <div className="w-2.5 h-2.5 rounded-full bg-green-500 shrink-0"></div>
                    <CalendarCheck size={14} className="text-green-500 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-900 truncate">{a.client_name} <span className="text-slate-400 font-normal">({a.client_rif})</span></p>
                      <p className="text-xs text-slate-500 truncate">{a.action || a.detail}</p>
                    </div>
                    <span className="text-xs text-green-600 font-medium shrink-0 bg-green-50 px-2 py-0.5 rounded">{a.follow_up_date}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-lg border border-slate-200 p-6">
              <h2 className="text-xl font-semibold text-slate-900 font-manrope mb-4">Cotizaciones por Mes</h2>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="name" stroke="#64748b" />
                  <YAxis stroke="#64748b" />
                  <Tooltip contentStyle={{ backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '8px' }} />
                  <Bar dataKey="cotizaciones" fill="#0284c7" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="bg-white rounded-lg border border-slate-200 p-6">
              <h2 className="text-xl font-semibold text-slate-900 font-manrope mb-4">Últimas Cotizaciones</h2>
              <div className="space-y-3">
                {recentQuotes.length > 0 ? recentQuotes.map((quote) => (
                  <div key={quote.quote_id} className="flex items-center justify-between p-3 rounded-lg border border-slate-100 hover:border-sky-200 transition-colors">
                    <div>
                      <p className="font-medium text-slate-900">{quote.quote_number}</p>
                      <p className="text-sm text-slate-500">{new Date(quote.created_at).toLocaleDateString('es-VE')}</p>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold text-slate-900">${quote.total_usd?.toFixed(2)}</p>
                      <p className="text-sm text-slate-500">{quote.total_bs?.toFixed(2)} Bs</p>
                    </div>
                  </div>
                )) : (
                  <p className="text-center text-slate-500 py-8">No hay cotizaciones recientes</p>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};
