import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { FileText, Users, Building2, TrendingUp, CreditCard, Package, Bell, AlertTriangle, Clock, CalendarCheck, RefreshCw, FileWarning, FolderKanban, Phone, UserPlus, Rocket, ArrowRightLeft, Trash2, Send, BookOpen, XCircle, RotateCcw } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Button } from '../components/ui/button';
import api from '../utils/api';
import { toast } from 'sonner';
import { RecentActivityCard } from '../components/RecentActivityCard';
import { InitialContactEmailDialog } from '../components/InitialContactEmailDialog';
import BitacoraModal from '../components/BitacoraModal';

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
  const [commitments, setCommitments] = useState([]);
  const [dashUsers, setDashUsers] = useState([]);
  const [currentUser, setCurrentUser] = useState(null);
  // Dashboard action modals
  const [dashConvertOpen, setDashConvertOpen] = useState(false);
  const [dashConvertContact, setDashConvertContact] = useState(null);
  const [dashAssignOpen, setDashAssignOpen] = useState(false);
  const [dashAssignContact, setDashAssignContact] = useState(null);
  const [dashAssignUserId, setDashAssignUserId] = useState('');
  const [dashAssignComment, setDashAssignComment] = useState('');
  // Transferir
  const [dashTransferOpen, setDashTransferOpen] = useState(false);
  const [dashTransferContact, setDashTransferContact] = useState(null);
  const [dashTransferUserId, setDashTransferUserId] = useState('');
  const [dashTransferReason, setDashTransferReason] = useState('');
  // Bitácora unificada (paridad funcional con la pantalla principal)
  const [dashBitacoraOpen, setDashBitacoraOpen] = useState(false);
  const [dashBitacoraContact, setDashBitacoraContact] = useState(null);

  // Cerrar / Reabrir gestión (disponibles para todos los usuarios)
  const [dashCloseOpen, setDashCloseOpen] = useState(false);
  const [dashCloseContact, setDashCloseContact] = useState(null);
  const [dashCloseReason, setDashCloseReason] = useState('');
  const [dashClosing, setDashClosing] = useState(false);

  const [dashReopenOpen, setDashReopenOpen] = useState(false);
  const [dashReopenContact, setDashReopenContact] = useState(null);
  const [dashReopenReason, setDashReopenReason] = useState('');
  const [dashReopening, setDashReopening] = useState(false);

  const [dashNotifyOpen, setDashNotifyOpen] = useState(false);
  const [dashNotifyContact, setDashNotifyContact] = useState(null);
  // Delete (admin only)
  const [dashDeleteContact, setDashDeleteContact] = useState(null);
  const [dashDeleting, setDashDeleting] = useState(false);

  useEffect(() => { fetchDashboardData(); }, []);

  const fetchDashboardData = async () => {
    try {
      const [statsRes, quotesRes, alertsRes, missingRes, projStatsRes, commitmentsRes, usersRes, meRes] = await Promise.allSettled([
        api.get('/dashboard/stats'),
        api.get('/quotes'),
        api.get('/dashboard/alerts'),
        api.get('/dashboard/missing-pdfs'),
        api.get('/projects/stats'),
        api.get('/initial-contacts/my-commitments/list'),
        api.get('/auth/users'),
        api.get('/auth/me')
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
      if (commitmentsRes.status === 'fulfilled') {
        setCommitments(commitmentsRes.value.data || []);
      }
      if (usersRes.status === 'fulfilled') {
        setDashUsers(usersRes.value.data || []);
      }
      if (meRes.status === 'fulfilled') {
        setCurrentUser(meRes.value.data);
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

  // SLA Semáforo
  const getSLAStatus = (dueDate) => {
    if (!dueDate) return { color: 'bg-slate-50', dot: 'bg-slate-300', label: 'Sin fecha', border: 'border-slate-200' };
    const now = new Date();
    const due = new Date(dueDate + 'T23:59:59');
    const diffMs = due.getTime() - now.getTime();
    const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
    if (diffDays >= 1) return { color: 'bg-green-50', dot: 'bg-green-500', label: 'En Tiempo', border: 'border-green-200' };
    if (diffDays >= 0) return { color: 'bg-yellow-50', dot: 'bg-yellow-500', label: 'Alerta', border: 'border-yellow-300' };
    return { color: 'bg-red-50', dot: 'bg-red-500', label: 'Vencido', border: 'border-red-300' };
  };

  const canDashAssign = currentUser?.role === 'admin' || ['Director', 'Gerente', 'Coordinador'].includes(currentUser?.cargo);
  const canDashTransfer = currentUser?.role === 'admin' || ['Director', 'Gerente'].includes(currentUser?.cargo);
  const dashAssignableUsers = dashUsers.filter(u => {
    if (!currentUser) return false;
    if (currentUser.role === 'admin') return u.user_id !== currentUser.user_id;
    const allowed = { Director: ['Gerente'], Gerente: ['Coordinador', 'Ejecutivo'], Coordinador: ['Ejecutivo'] };
    return (allowed[currentUser.cargo] || []).includes(u.cargo) && u.is_active !== false;
  });

  const handleDashConvert = async () => {
    try {
      const res = await api.post(`/initial-contacts/${dashConvertContact.contact_id}/convert`);
      toast.success(res.data.message);
      setDashConvertOpen(false);
      fetchDashboardData();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  const handleDashAssign = async () => {
    if (!dashAssignUserId) { toast.error('Seleccione un usuario'); return; }
    try {
      await api.post(`/initial-contacts/${dashAssignContact.contact_id}/assign`, {
        assigned_to_user_id: dashAssignUserId, comment: dashAssignComment || undefined
      });
      toast.success('Contacto asignado');
      setDashAssignOpen(false); setDashAssignUserId(''); setDashAssignComment('');
      fetchDashboardData();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  const handleDashTransfer = async () => {
    if (!dashTransferUserId) { toast.error('Seleccione un usuario destino'); return; }
    try {
      await api.post(`/initial-contacts/${dashTransferContact.contact_id}/transfer`, {
        target_user_id: dashTransferUserId,
        comment: dashTransferReason || undefined,
      });
      toast.success('Contacto transferido');
      setDashTransferOpen(false); setDashTransferUserId(''); setDashTransferReason('');
      fetchDashboardData();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al transferir'); }
  };

  const handleDashDelete = async () => {
    if (!dashDeleteContact) return;
    setDashDeleting(true);
    try {
      await api.delete(`/initial-contacts/${dashDeleteContact.contact_id}`);
      toast.success('Contacto eliminado');
      setDashDeleteContact(null);
      fetchDashboardData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al eliminar');
    } finally {
      setDashDeleting(false);
    }
  };

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

          {/* Actividad Reciente (admin/director) */}
          <div className="mb-8">
            <RecentActivityCard limit={5} />
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
          {/* Mis Compromisos - Central de Acciones */}
          {commitments.length > 0 && (
            <div className="mb-8 bg-white rounded-lg border border-blue-200 overflow-hidden" data-testid="commitments-widget">
              <div className="flex items-center justify-between px-6 py-4 border-b border-blue-100 bg-blue-50">
                <div className="flex items-center gap-2">
                  <Phone size={18} className="text-blue-700" />
                  <h2 className="text-base font-semibold text-blue-900">Contacto Inicial — Central de Acciones</h2>
                  <span className="text-xs bg-blue-200 text-blue-800 rounded-full px-2 py-0.5 ml-1">{commitments.length}</span>
                </div>
                <Button variant="outline" size="sm" className="h-7 text-xs border-blue-300 text-blue-700 hover:bg-blue-100" onClick={() => navigate('/initial-contacts')} data-testid="go-to-contacts">
                  Ver todos
                </Button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 border-b">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-slate-600">Contacto</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-slate-600">Razon Social</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-slate-600">Asignado</th>
                      <th className="px-4 py-2 text-center text-xs font-medium text-slate-600">Fecha Limite</th>
                      <th className="px-4 py-2 text-center text-xs font-medium text-slate-600">SLA</th>
                      <th className="px-4 py-2 text-center text-xs font-medium text-slate-600">Acciones</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {commitments.map(c => {
                      const sla = getSLAStatus(c.due_date);
                      const isClosed = c.status === 'closed';
                      return (
                        <tr key={c.contact_id} className={`${isClosed ? 'bg-blue-50 hover:bg-blue-100' : sla.color + ' hover:brightness-95'} transition-colors`} data-testid={`commitment-${c.contact_id}`}>
                          <td className="px-4 py-2.5">
                            <div className="flex items-center gap-2">
                              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 border ${sla.border} ${sla.dot === 'bg-red-500' ? 'bg-red-100 text-red-700' : sla.dot === 'bg-yellow-500' ? 'bg-yellow-100 text-yellow-700' : 'bg-blue-100 text-blue-700'}`}>
                                {(c.contact_name || '??').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()}
                              </div>
                              <div>
                                <p className="font-medium text-slate-800 text-xs">{c.contact_name}</p>
                                <p className="text-[10px] text-slate-500">{c.phone}</p>
                              </div>
                            </div>
                          </td>
                          <td className="px-4 py-2.5 text-xs text-slate-700 font-medium">{c.legal_name}</td>
                          <td className="px-4 py-2.5 text-xs text-slate-600">{c.assigned_to_name}</td>
                          <td className="px-4 py-2.5 text-center text-xs">
                            {c.due_date ? new Date(c.due_date + 'T12:00:00').toLocaleDateString('es-VE', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '—'}
                          </td>
                          <td className="px-4 py-2.5 text-center">
                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${sla.dot === 'bg-green-500' ? 'bg-green-200 text-green-800' : sla.dot === 'bg-yellow-500' ? 'bg-yellow-200 text-yellow-800' : sla.dot === 'bg-red-500' ? 'bg-red-200 text-red-800' : 'bg-slate-200 text-slate-600'}`}>
                              <span className={`w-2 h-2 rounded-full ${sla.dot}`} />
                              {sla.label}
                            </span>
                          </td>
                          <td className="px-4 py-2.5">
                            <div className="flex items-center justify-center gap-0.5">
                              <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-slate-500 hover:text-blue-600" title="Bitácora (registrar gestión / seguimiento)"
                                data-testid={`dash-bitacora-btn-${c.contact_id}`}
                                onClick={() => { setDashBitacoraContact(c); setDashBitacoraOpen(true); }}>
                                <BookOpen size={13} />
                              </Button>
                              {canDashAssign && (
                                <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-slate-500 hover:text-amber-600" title="Reasignar"
                                  onClick={() => { setDashAssignContact(c); setDashAssignUserId(''); setDashAssignComment(''); setDashAssignOpen(true); }}>
                                  <UserPlus size={13} />
                                </Button>
                              )}
                              {canDashTransfer && (
                                <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-slate-500 hover:text-purple-600" title="Transferir"
                                  onClick={() => { setDashTransferContact(c); setDashTransferUserId(''); setDashTransferReason(''); setDashTransferOpen(true); }}>
                                  <ArrowRightLeft size={13} />
                                </Button>
                              )}
                              <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-slate-500 hover:text-green-600" title="Convertir a Prospecto"
                                onClick={() => { setDashConvertContact(c); setDashConvertOpen(true); }}>
                                <Rocket size={13} />
                              </Button>
                              <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-slate-500 hover:text-indigo-600" title="Enviar Notificación"
                                data-testid={`dash-notify-btn-${c.contact_id}`}
                                onClick={() => { setDashNotifyContact(c); setDashNotifyOpen(true); }}>
                                <Send size={13} />
                              </Button>
                              {c.status !== 'closed' ? (
                                <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-slate-500 hover:text-blue-700" title="Cerrar Gestión"
                                  data-testid={`dash-close-btn-${c.contact_id}`}
                                  onClick={() => { setDashCloseContact(c); setDashCloseReason(''); setDashCloseOpen(true); }}>
                                  <XCircle size={13} />
                                </Button>
                              ) : (
                                <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-slate-500 hover:text-emerald-600" title="Reabrir Gestión"
                                  data-testid={`dash-reopen-btn-${c.contact_id}`}
                                  onClick={() => { setDashReopenContact(c); setDashReopenReason(''); setDashReopenOpen(true); }}>
                                  <RotateCcw size={13} />
                                </Button>
                              )}
                              {currentUser?.role === 'admin' && (
                                <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-slate-500 hover:text-red-600"
                                  title="Eliminar (solo Admin)"
                                  onClick={() => setDashDeleteContact(c)}
                                  data-testid={`dash-delete-btn-${c.contact_id}`}
                                >
                                  <Trash2 size={13} />
                                </Button>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

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

      {/* Dashboard Action Modals */}
      {/* Bitácora unificada — paridad con InitialContacts.jsx */}
      <BitacoraModal
        open={dashBitacoraOpen}
        onOpenChange={setDashBitacoraOpen}
        entityId={dashBitacoraContact?.contact_id}
        entityName={dashBitacoraContact?.legal_name || ''}
        contacts={dashBitacoraContact ? [{
          id: dashBitacoraContact.contact_id,
          name: dashBitacoraContact.contact_name || '',
          role: 'Contacto principal',
        }] : []}
        apiPrefix="initial-contacts"
      />

      <Dialog open={dashAssignOpen} onOpenChange={setDashAssignOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle className="flex items-center gap-2"><UserPlus size={20} className="text-amber-600" /> Reasignar Contacto</DialogTitle></DialogHeader>
          {dashAssignContact && <p className="text-sm text-slate-500">Contacto: <strong>{dashAssignContact.legal_name}</strong></p>}
          <div>
            <Label>Asignar a</Label>
            <Select value={dashAssignUserId} onValueChange={setDashAssignUserId}>
              <SelectTrigger data-testid="dash-assign-select"><SelectValue placeholder="Seleccione usuario..." /></SelectTrigger>
              <SelectContent>
                {dashAssignableUsers.map(u => (
                  <SelectItem key={u.user_id} value={u.user_id}>{u.first_name} {u.last_name} ({u.cargo} - {u.sede})</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Comentario (opcional)</Label>
            <Input value={dashAssignComment} onChange={(e) => setDashAssignComment(e.target.value)} placeholder="Nota..." data-testid="dash-assign-comment" />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setDashAssignOpen(false)}>Cancelar</Button>
            <Button onClick={handleDashAssign} className="bg-amber-500 hover:bg-amber-600" data-testid="dash-assign-submit">Asignar</Button>
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog open={dashConvertOpen} onOpenChange={setDashConvertOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2"><Rocket size={20} className="text-green-600" /> Convertir a Prospecto</AlertDialogTitle>
            <AlertDialogDescription>
              Se creara un registro en Clientes con estatus Prospecto.
              {dashConvertContact && (
                <span className="block mt-2 p-3 bg-green-50 border border-green-200 rounded-lg">
                  <span className="font-semibold block">{dashConvertContact.legal_name}</span>
                  <span className="text-xs text-slate-500">{dashConvertContact.contact_name}</span>
                </span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={handleDashConvert} className="bg-green-600 hover:bg-green-700" data-testid="dash-convert-confirm">Convertir</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Dashboard: Transferir */}
      <Dialog open={dashTransferOpen} onOpenChange={setDashTransferOpen}>
        <DialogContent className="max-w-md" data-testid="dash-transfer-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ArrowRightLeft size={18} className="text-purple-600" />
              Transferir contacto
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {dashTransferContact && (
              <div className="p-3 bg-purple-50 border border-purple-200 rounded-lg text-sm">
                <p className="font-semibold">{dashTransferContact.legal_name}</p>
                <p className="text-xs text-slate-500">{dashTransferContact.contact_name}</p>
                <p className="text-xs text-slate-500 mt-1">
                  Asignado a: <strong>{dashTransferContact.assigned_to_name || '—'}</strong>
                </p>
              </div>
            )}
            <div>
              <Label>Transferir a (Gerente) *</Label>
              <Select value={dashTransferUserId} onValueChange={setDashTransferUserId}>
                <SelectTrigger data-testid="dash-transfer-user"><SelectValue placeholder="Seleccione gerente destino..." /></SelectTrigger>
                <SelectContent>
                  {dashUsers
                    .filter(u => u.cargo === 'Gerente' && u.user_id !== currentUser?.user_id && u.user_id !== dashTransferContact?.assigned_to_user_id && u.is_active !== false)
                    .map(u => (
                      <SelectItem key={u.user_id} value={u.user_id}>
                        {u.first_name} {u.last_name} {u.departamento ? `(${u.departamento}` : ''}{u.sede ? ` - ${u.sede})` : (u.departamento ? ')' : '')}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Motivo (opcional)</Label>
              <Textarea
                placeholder="Ej. Reasignación por carga de trabajo..."
                value={dashTransferReason}
                onChange={(e) => setDashTransferReason(e.target.value)}
                rows={3}
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setDashTransferOpen(false)}>Cancelar</Button>
              <Button onClick={handleDashTransfer} className="bg-purple-600 hover:bg-purple-700" data-testid="dash-transfer-confirm">
                Transferir
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Cerrar Gestión desde Dashboard (todos los usuarios) */}
      <AlertDialog open={dashCloseOpen} onOpenChange={setDashCloseOpen}>
        <AlertDialogContent data-testid="dash-close-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-blue-700 flex items-center gap-2">
              <XCircle size={18} /> Cerrar Gestión
            </AlertDialogTitle>
            <AlertDialogDescription>
              El contacto <strong>{dashCloseContact?.legal_name}</strong> quedará marcado como GESTIONADO (fondo azul) y dejará de aparecer en la bandeja activa. La acción queda registrada en la bitácora.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="space-y-2 my-3">
            <Label className="text-xs">Motivo del cierre (obligatorio)</Label>
            <Textarea
              value={dashCloseReason}
              onChange={(e) => setDashCloseReason(e.target.value)}
              placeholder="Ej: Cliente no interesado / Recursos suspendidos / Duplicado..."
              rows={3}
              data-testid="dash-close-reason-input"
            />
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={dashClosing}>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              disabled={dashClosing || !dashCloseReason.trim()}
              onClick={async () => {
                setDashClosing(true);
                try {
                  await api.post(`/initial-contacts/${dashCloseContact.contact_id}/close`, { reason: dashCloseReason.trim() });
                  toast.success('Gestión cerrada');
                  setDashCloseOpen(false);
                  setDashCloseContact(null);
                  setDashCloseReason('');
                  fetchDashboardData();
                } catch (e) {
                  toast.error(e.response?.data?.detail || 'Error al cerrar gestión');
                } finally { setDashClosing(false); }
              }}
              className="bg-blue-600 hover:bg-blue-700"
              data-testid="dash-close-confirm-btn"
            >
              {dashClosing ? 'Cerrando...' : 'Cerrar Gestión'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Reabrir Gestión desde Dashboard (todos los usuarios) */}
      <AlertDialog open={dashReopenOpen} onOpenChange={setDashReopenOpen}>
        <AlertDialogContent data-testid="dash-reopen-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-emerald-700 flex items-center gap-2">
              <RotateCcw size={18} /> Reabrir Gestión
            </AlertDialogTitle>
            <AlertDialogDescription>
              El contacto <strong>{dashReopenContact?.legal_name}</strong> volverá al estado <span className="font-semibold text-emerald-700">ACTIVO</span>. Se registrará automáticamente en la bitácora.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="space-y-2 my-3">
            <Label className="text-xs">Motivo de reapertura (opcional)</Label>
            <Textarea
              value={dashReopenReason}
              onChange={(e) => setDashReopenReason(e.target.value)}
              placeholder="Ej: Cliente retomó interés / Negociación reactivada..."
              rows={3}
              data-testid="dash-reopen-reason-input"
            />
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={dashReopening}>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              disabled={dashReopening}
              onClick={async () => {
                setDashReopening(true);
                try {
                  await api.post(`/initial-contacts/${dashReopenContact.contact_id}/reopen`, { reason: dashReopenReason.trim() });
                  toast.success('Gestión reabierta');
                  setDashReopenOpen(false);
                  setDashReopenContact(null);
                  setDashReopenReason('');
                  fetchDashboardData();
                } catch (e) {
                  toast.error(e.response?.data?.detail || 'Error al reabrir gestión');
                } finally { setDashReopening(false); }
              }}
              className="bg-emerald-600 hover:bg-emerald-700"
              data-testid="dash-reopen-confirm-btn"
            >
              {dashReopening ? 'Reabriendo...' : 'Reabrir Gestión'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Dashboard: Delete confirmation (admin only) */}
      <AlertDialog open={!!dashDeleteContact} onOpenChange={(o) => !o && setDashDeleteContact(null)}>
        <AlertDialogContent data-testid="dash-delete-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-red-600">¿Eliminar contacto inicial?</AlertDialogTitle>
            <AlertDialogDescription>
              Se eliminará permanentemente el contacto{' '}
              <strong>{dashDeleteContact?.legal_name || ''}</strong>
              {dashDeleteContact?.rif ? <> (RIF {dashDeleteContact.rif})</> : null}.
              <br/>
              <span className="text-amber-600">Esta acción no se puede deshacer.</span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={dashDeleting}>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDashDelete}
              disabled={dashDeleting}
              className="bg-red-600 hover:bg-red-700"
              data-testid="dash-delete-confirm"
            >
              {dashDeleting ? 'Eliminando...' : 'Eliminar'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Notification Dialog */}
      <InitialContactEmailDialog
        open={dashNotifyOpen}
        onClose={() => { setDashNotifyOpen(false); setDashNotifyContact(null); }}
        contact={dashNotifyContact}
        onSent={() => { /* refresh commitments not critical; bitácora modal will re-read on next open */ }}
      />
    </div>
  );
};
