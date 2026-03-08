import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { FileText, Users, Building2, TrendingUp, CreditCard, Package, Bell, AlertTriangle, Clock, CalendarCheck, RefreshCw, FileWarning, FolderKanban } from 'lucide-react';
import { Button } from '../components/ui/button';
import api from '../utils/api';
import { toast } from 'sonner';

export const Dashboard = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState({
    totalQuotes: 0, totalClients: 0, totalBanks: 0,
    totalMediosPago: 0, totalHardware: 0, exchangeRate: 0
  });
  const [projectStats, setProjectStats] = useState({ total: 0, pending: 0, in_progress: 0, blocked: 0, completed: 0 });
  const [recentQuotes, setRecentQuotes] = useState([]);
  const [alerts, setAlerts] = useState({ overdue: [], today: [], upcoming: [], total: 0 });
  const [missingPdfs, setMissingPdfs] = useState([]);
  const [regenerating, setRegenerating] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchDashboardData(); }, []);

  const fetchDashboardData = async () => {
    try {
      const [statsRes, quotesRes, alertsRes, missingRes, projStatsRes] = await Promise.allSettled([
        api.get('/dashboard/stats'),
        api.get('/quotes'),
        api.get('/dashboard/alerts'),
        api.get('/dashboard/missing-pdfs'),
        api.get('/projects/stats')
      ]);

      if (statsRes.status === 'fulfilled') {
        setStats(statsRes.value.data);
      }
      if (quotesRes.status === 'fulfilled') {
        setRecentQuotes(Array.isArray(quotesRes.value.data) ? quotesRes.value.data.slice(0, 5) : []);
      }
      if (alertsRes.status === 'fulfilled') {
        setAlerts(alertsRes.value.data);
      }
      if (missingRes.status === 'fulfilled') {
        setMissingPdfs(missingRes.value.data.missing_pdfs || []);
      }
      if (projStatsRes.status === 'fulfilled') {
        setProjectStats(projStatsRes.value.data);
      }
    } catch {
      toast.error('Error al cargar datos del dashboard');
    } finally {
      setLoading(false);
    }
  };

  const handleRegeneratePdf = async (quoteId, quoteNumber) => {
    setRegenerating(prev => ({ ...prev, [quoteId]: true }));
    try {
      await api.post(`/quotes/${quoteId}/regenerate-pdf`);
      toast.success(`PDF regenerado: ${quoteNumber}`);
      setMissingPdfs(prev => prev.filter(q => q.quote_id !== quoteId));
    } catch (err) {
      toast.error(`Error regenerando PDF: ${err.response?.data?.detail || 'Error desconocido'}`);
    } finally {
      setRegenerating(prev => ({ ...prev, [quoteId]: false }));
    }
  };

  const handleRegenerateAll = async () => {
    const toRegenerate = [...missingPdfs];
    let successCount = 0;
    for (const quote of toRegenerate) {
      setRegenerating(prev => ({ ...prev, [quote.quote_id]: true }));
      try {
        await api.post(`/quotes/${quote.quote_id}/regenerate-pdf`);
        successCount++;
        setMissingPdfs(prev => prev.filter(q => q.quote_id !== quote.quote_id));
      } catch {
        // continue with next
      } finally {
        setRegenerating(prev => ({ ...prev, [quote.quote_id]: false }));
      }
    }
    if (successCount > 0) toast.success(`${successCount} PDF(s) regenerado(s)`);
  };

  const statCards = [
    { title: 'Cotizaciones', value: stats.totalQuotes, icon: FileText, color: 'bg-sky-100 text-sky-700' },
    { title: 'Clientes', value: stats.totalClients, icon: Users, color: 'bg-emerald-100 text-emerald-700' },
    { title: 'Bancos', value: stats.totalBanks, icon: Building2, color: 'bg-purple-100 text-purple-700' },
    { title: 'Medios de Pago', value: stats.totalMediosPago, icon: CreditCard, color: 'bg-rose-100 text-rose-700' },
    { title: 'Bienes y Servicios', value: stats.totalHardware, icon: Package, color: 'bg-orange-100 text-orange-700' },
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

          {/* Project KPI Card */}
          <div className="mb-8 bg-white rounded-lg border border-slate-200 p-6 card-hover cursor-pointer"
            onClick={() => navigate('/projects')} data-testid="projects-kpi-card">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-lg bg-indigo-100 text-indigo-700">
                  <FolderKanban size={24} />
                </div>
                <div>
                  <h3 className="text-sm font-medium text-slate-500 uppercase tracking-wide">Proyectos Activos</h3>
                  <p className="text-3xl font-bold text-slate-900 font-manrope">
                    {projectStats.total - projectStats.completed}
                  </p>
                </div>
              </div>
              <div className="text-right text-sm text-slate-500">
                Total: <span className="font-semibold text-slate-700">{projectStats.total}</span>
              </div>
            </div>
            <div className="grid grid-cols-4 gap-3">
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-center" data-testid="kpi-pending">
                <p className="text-2xl font-bold text-amber-700">{projectStats.pending}</p>
                <p className="text-xs text-amber-600 font-medium mt-1">Por Asignar</p>
              </div>
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-center" data-testid="kpi-in-progress">
                <p className="text-2xl font-bold text-blue-700">{projectStats.in_progress}</p>
                <p className="text-xs text-blue-600 font-medium mt-1">En Proceso</p>
              </div>
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-center" data-testid="kpi-blocked">
                <p className="text-2xl font-bold text-red-700">{projectStats.blocked}</p>
                <p className="text-xs text-red-600 font-medium mt-1">Detenidos</p>
              </div>
              <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 text-center" data-testid="kpi-completed">
                <p className="text-2xl font-bold text-emerald-700">{projectStats.completed}</p>
                <p className="text-xs text-emerald-600 font-medium mt-1">Finalizados</p>
              </div>
            </div>
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

          {/* Missing PDFs Alert */}
          {missingPdfs.length > 0 && (
            <div className="mb-8 bg-white rounded-lg border border-amber-200 overflow-hidden" data-testid="missing-pdfs-widget">
              <div className="flex items-center justify-between px-6 py-4 border-b border-amber-100 bg-amber-50">
                <div className="flex items-center gap-2">
                  <FileWarning size={18} className="text-amber-600" />
                  <h2 className="text-base font-semibold text-slate-900">Cotizaciones sin PDF</h2>
                  <span className="text-xs bg-amber-200 text-amber-800 rounded-full px-2 py-0.5 ml-1">{missingPdfs.length}</span>
                </div>
                <Button
                  size="sm"
                  onClick={handleRegenerateAll}
                  className="bg-amber-600 hover:bg-amber-700 text-white text-xs h-8"
                  data-testid="regenerate-all-pdfs-btn"
                >
                  <RefreshCw size={14} className="mr-1" />
                  Regenerar Todos
                </Button>
              </div>
              <div className="divide-y divide-amber-100 max-h-64 overflow-y-auto">
                {missingPdfs.map(q => (
                  <div key={q.quote_id} className="flex items-center justify-between px-6 py-3 hover:bg-amber-50/30 transition-colors"
                    data-testid={`missing-pdf-${q.quote_id}`}>
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <FileText size={16} className="text-amber-500 shrink-0" />
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-slate-900">{q.quote_number}</p>
                        <p className="text-xs text-slate-500 truncate">
                          {q.client_name || 'Sin cliente'} · {q.quote_type} · {q.quote_status || 'Borrador'}
                        </p>
                      </div>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleRegeneratePdf(q.quote_id, q.quote_number)}
                      disabled={regenerating[q.quote_id]}
                      className="text-xs h-7 border-amber-300 text-amber-700 hover:bg-amber-50"
                      data-testid={`regenerate-pdf-${q.quote_id}`}
                    >
                      <RefreshCw size={12} className={`mr-1 ${regenerating[q.quote_id] ? 'animate-spin' : ''}`} />
                      {regenerating[q.quote_id] ? 'Generando...' : 'Regenerar'}
                    </Button>
                  </div>
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
