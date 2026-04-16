import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import {
  Wrench, Search, Download, AlertTriangle, Clock,
  Package, CheckCircle, ExternalLink, X, Calendar,
  ChevronLeft, ChevronRight, Trash2
} from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';
import { usePermission } from '../hooks/usePermission';

const PAGE_SIZE = 25;

const ESTATUS_OPTIONS = [
  { value: 'all', label: 'Todos' },
  { value: 'En reparación', label: 'En reparación' },
  { value: 'Entregado', label: 'Entregado' },
];

export default function TallerEquipos() {
  const navigate = useNavigate();
  const { user: currentUser } = usePermission('taller');
  const isAdmin = currentUser?.role === 'admin';
  const [equipos, setEquipos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ total: 0, total_en_reparacion: 0, total_entregados: 0, total_alerta: 0 });

  // Filtros
  const [search, setSearch] = useState('');
  const [estatus, setEstatus] = useState('En reparación');
  const [fechaDesde, setFechaDesde] = useState('');
  const [fechaHasta, setFechaHasta] = useState('');

  // Paginación
  const [page, setPage] = useState(1);

  // Modal historial
  const [historialOpen, setHistorialOpen] = useState(false);
  const [historialData, setHistorialData] = useState(null);
  const [historialLoading, setHistorialLoading] = useState(false);

  // Exportar
  const [exporting, setExporting] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.append('search', search.trim());
      if (estatus !== 'all') params.append('estatus', estatus);
      if (fechaDesde) params.append('fecha_desde', fechaDesde);
      if (fechaHasta) params.append('fecha_hasta', fechaHasta);
      const qs = params.toString();
      const res = await api.get(`/taller-equipos${qs ? '?' + qs : ''}`);
      setEquipos(res.data.equipos || []);
      setStats({
        total: res.data.total || 0,
        total_en_reparacion: res.data.total_en_reparacion || 0,
        total_entregados: res.data.total_entregados || 0,
        total_alerta: res.data.total_alerta || 0,
      });
      setPage(1);
    } catch {
      toast.error('Error al cargar equipos en taller');
    } finally {
      setLoading(false);
    }
  }, [search, estatus, fechaDesde, fechaHasta]);

  useEffect(() => {
    const timer = setTimeout(fetchData, 300);
    return () => clearTimeout(timer);
  }, [fetchData]);

  const totalPages = Math.max(1, Math.ceil(equipos.length / PAGE_SIZE));
  const paginatedEquipos = equipos.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const openHistorial = async (tallerEquipoId) => {
    setHistorialOpen(true);
    setHistorialLoading(true);
    setHistorialData(null);
    try {
      const res = await api.get(`/taller-equipos/${tallerEquipoId}/historial`);
      setHistorialData(res.data);
    } catch {
      toast.error('Error al cargar historial');
      setHistorialOpen(false);
    } finally {
      setHistorialLoading(false);
    }
  };

  const handleDeleteEquipo = async (equipo) => {
    if (!confirm(`¿Eliminar registro de ${equipo.serial} (${equipo.modelo})? Esta acción no se puede deshacer.`)) return;
    try {
      await api.delete(`/taller-equipos/${equipo.taller_equipo_id}`);
      toast.success('Registro eliminado');
      fetchEquipos();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al eliminar');
    }
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.append('search', search.trim());
      if (estatus !== 'all') params.append('estatus', estatus);
      if (fechaDesde) params.append('fecha_desde', fechaDesde);
      if (fechaHasta) params.append('fecha_hasta', fechaHasta);
      const qs = params.toString();
      const res = await api.get(`/taller-equipos/export-excel${qs ? '?' + qs : ''}`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `equipos_taller_${new Date().toISOString().slice(0, 10)}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Excel exportado exitosamente');
    } catch {
      toast.error('Error al exportar Excel');
    } finally {
      setExporting(false);
    }
  };

  const clearFilters = () => {
    setSearch('');
    setEstatus('all');
    setFechaDesde('');
    setFechaHasta('');
  };

  const hasFilters = search || estatus !== 'all' || fechaDesde || fechaHasta;

  const formatDate = (iso) => {
    if (!iso) return '-';
    try {
      return new Date(iso).toLocaleDateString('es-VE', { day: '2-digit', month: '2-digit', year: 'numeric' });
    } catch {
      return iso.slice(0, 10);
    }
  };

  return (
    <div className="flex min-h-screen bg-slate-50" data-testid="taller-equipos-page">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <div className="p-6 max-w-[1400px] mx-auto space-y-5">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
                <Wrench size={24} className="text-cyan-600" />
                Equipos en Reparacion
              </h1>
              <p className="text-sm text-slate-500 mt-1">Control de custodia de equipos de terceros en taller</p>
            </div>
            <Button
              onClick={handleExport}
              disabled={exporting || equipos.length === 0}
              variant="outline"
              className="flex items-center gap-2"
              data-testid="export-excel-btn"
            >
              <Download size={16} />
              {exporting ? 'Exportando...' : 'Exportar Excel'}
            </Button>
          </div>

          {/* Stats Cards */}
          <div className="grid grid-cols-4 gap-3">
            <div className="bg-white border rounded-lg p-3 flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center">
                <Package size={18} className="text-slate-600" />
              </div>
              <div>
                <p className="text-xs text-slate-500">Total</p>
                <p className="text-lg font-bold text-slate-900" data-testid="stat-total">{stats.total}</p>
              </div>
            </div>
            <div className="bg-white border rounded-lg p-3 flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-cyan-50 flex items-center justify-center">
                <Wrench size={18} className="text-cyan-600" />
              </div>
              <div>
                <p className="text-xs text-slate-500">En Reparacion</p>
                <p className="text-lg font-bold text-cyan-700" data-testid="stat-en-reparacion">{stats.total_en_reparacion}</p>
              </div>
            </div>
            <div className="bg-white border rounded-lg p-3 flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-green-50 flex items-center justify-center">
                <CheckCircle size={18} className="text-green-600" />
              </div>
              <div>
                <p className="text-xs text-slate-500">Entregados</p>
                <p className="text-lg font-bold text-green-700" data-testid="stat-entregados">{stats.total_entregados}</p>
              </div>
            </div>
            <div className="bg-white border rounded-lg p-3 flex items-center gap-3">
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${stats.total_alerta > 0 ? 'bg-red-50' : 'bg-slate-100'}`}>
                <AlertTriangle size={18} className={stats.total_alerta > 0 ? 'text-red-500' : 'text-slate-400'} />
              </div>
              <div>
                <p className="text-xs text-slate-500">Alerta (+15 dias)</p>
                <p className={`text-lg font-bold ${stats.total_alerta > 0 ? 'text-red-600' : 'text-slate-400'}`} data-testid="stat-alerta">{stats.total_alerta}</p>
              </div>
            </div>
          </div>

          {/* Filters */}
          <div className="bg-white border rounded-lg p-3">
            <div className="flex items-center gap-3 flex-wrap">
              <div className="relative flex-1 min-w-[200px]">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder="Buscar por serial, cliente, modelo o cotizacion..."
                  className="pl-9 h-9 text-sm"
                  data-testid="filter-search"
                />
              </div>
              <Select value={estatus} onValueChange={setEstatus}>
                <SelectTrigger className="w-[160px] h-9 text-sm" data-testid="filter-estatus">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ESTATUS_OPTIONS.map(o => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <div className="flex items-center gap-1.5">
                <Calendar size={14} className="text-slate-400" />
                <Input
                  type="date"
                  value={fechaDesde}
                  onChange={e => setFechaDesde(e.target.value)}
                  className="h-9 text-sm w-[140px]"
                  data-testid="filter-fecha-desde"
                />
                <span className="text-xs text-slate-400">a</span>
                <Input
                  type="date"
                  value={fechaHasta}
                  onChange={e => setFechaHasta(e.target.value)}
                  className="h-9 text-sm w-[140px]"
                  data-testid="filter-fecha-hasta"
                />
              </div>
              {hasFilters && (
                <Button variant="ghost" size="sm" onClick={clearFilters} className="text-xs text-slate-500 hover:text-slate-700" data-testid="clear-filters-btn">
                  <X size={14} className="mr-1" /> Limpiar
                </Button>
              )}
            </div>
          </div>

          {/* Table */}
          <div className="bg-white border rounded-lg overflow-hidden">
            {loading ? (
              <div className="flex items-center justify-center py-16">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-600" />
              </div>
            ) : equipos.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-slate-400">
                <Package size={40} className="mb-3 opacity-40" />
                <p className="text-sm">No se encontraron equipos en taller</p>
                {hasFilters && (
                  <Button variant="link" size="sm" onClick={clearFilters} className="mt-2 text-xs">Limpiar filtros</Button>
                )}
              </div>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm" data-testid="taller-table">
                    <thead>
                      <tr className="bg-slate-50 border-b">
                        <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-600 uppercase">Serial</th>
                        <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-600 uppercase">Modelo</th>
                        <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-600 uppercase">Cliente</th>
                        <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-600 uppercase">Cotizacion Origen</th>
                        <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-600 uppercase">Estatus</th>
                        <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-600 uppercase">Fecha Ingreso</th>
                        <th className="text-right px-4 py-2.5 text-xs font-semibold text-slate-600 uppercase">Dias en Taller</th>
                        {isAdmin && <th className="text-center px-3 py-2.5 text-xs font-semibold text-slate-600 uppercase"></th>}
                      </tr>
                    </thead>
                    <tbody>
                      {paginatedEquipos.map((eq) => {
                        const isAlert = eq.alerta_retraso;
                        return (
                          <tr
                            key={eq.taller_equipo_id}
                            className={`border-b last:border-b-0 transition-colors ${
                              isAlert ? 'bg-red-50/60 hover:bg-red-50' : 'hover:bg-slate-50'
                            }`}
                            data-testid={`taller-row-${eq.serial}`}
                          >
                            <td className="px-4 py-2.5">
                              <button
                                onClick={() => openHistorial(eq.taller_equipo_id)}
                                className="text-cyan-700 font-medium hover:text-cyan-900 hover:underline flex items-center gap-1"
                                data-testid={`serial-link-${eq.serial}`}
                              >
                                {eq.serial}
                              </button>
                            </td>
                            <td className="px-4 py-2.5 text-slate-700">{eq.modelo}</td>
                            <td className="px-4 py-2.5 text-slate-700 max-w-[180px] truncate" title={eq.client_name}>{eq.client_name}</td>
                            <td className="px-4 py-2.5">
                              <button
                                onClick={() => navigate('/quotes')}
                                className="text-sm text-blue-600 hover:text-blue-800 hover:underline flex items-center gap-1"
                                data-testid={`quote-link-${eq.quote_number}`}
                              >
                                {eq.quote_number}
                                <ExternalLink size={12} />
                              </button>
                            </td>
                            <td className="px-4 py-2.5">
                              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
                                eq.estatus === 'En reparación'
                                  ? 'bg-cyan-100 text-cyan-700'
                                  : 'bg-green-100 text-green-700'
                              }`}>
                                {eq.estatus === 'En reparación' ? <Wrench size={11} /> : <CheckCircle size={11} />}
                                {eq.estatus}
                              </span>
                            </td>
                            <td className="px-4 py-2.5 text-slate-600 text-xs">{formatDate(eq.fecha_ingreso)}</td>
                            <td className="px-4 py-2.5 text-right">
                              <span className={`inline-flex items-center gap-1 text-xs font-semibold ${
                                isAlert ? 'text-red-600' : eq.estatus === 'Entregado' ? 'text-slate-400' : 'text-slate-700'
                              }`}>
                                {isAlert && <AlertTriangle size={12} className="text-red-500" />}
                                <Clock size={12} className={isAlert ? 'text-red-400' : 'text-slate-400'} />
                                {eq.dias_en_taller}d
                              </span>
                            </td>
                            {isAdmin && (
                              <td className="px-3 py-2.5 text-center">
                                <Button variant="ghost" size="sm" onClick={() => handleDeleteEquipo(eq)} className="text-slate-300 hover:text-rose-600 hover:bg-rose-50" data-testid={`delete-taller-${eq.serial}`}>
                                  <Trash2 size={15} />
                                </Button>
                              </td>
                            )}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-between px-4 py-2.5 border-t bg-slate-50">
                    <span className="text-xs text-slate-500">
                      {(page - 1) * PAGE_SIZE + 1}-{Math.min(page * PAGE_SIZE, equipos.length)} de {equipos.length}
                    </span>
                    <div className="flex items-center gap-1">
                      <Button variant="ghost" size="sm" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
                        <ChevronLeft size={16} />
                      </Button>
                      <span className="text-xs text-slate-600 px-2">{page}/{totalPages}</span>
                      <Button variant="ghost" size="sm" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}>
                        <ChevronRight size={16} />
                      </Button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Info de solo lectura */}
          <p className="text-[10px] text-slate-400 text-center">
            Vista de solo lectura. Los cambios de estatus se realizan a traves del flujo de cotizaciones.
          </p>
        </div>
      </main>

      {/* Modal Historial */}
      <Dialog open={historialOpen} onOpenChange={setHistorialOpen}>
        <DialogContent className="max-w-md" data-testid="historial-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base">
              <Clock size={18} className="text-cyan-600" />
              Detalle del Equipo
            </DialogTitle>
          </DialogHeader>

          {historialLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-cyan-600" />
            </div>
          ) : historialData ? (
            <div className="space-y-4">
              {/* Equipo info */}
              <div className="bg-slate-50 rounded-lg p-3 space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <p className="text-[10px] text-slate-500 uppercase">Serial</p>
                    <p className="text-sm font-semibold text-slate-900">{historialData.equipo?.serial}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-slate-500 uppercase">Modelo</p>
                    <p className="text-sm font-medium text-slate-700">{historialData.equipo?.modelo}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-slate-500 uppercase">Cliente</p>
                    <p className="text-sm text-slate-700">{historialData.equipo?.client_name}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-slate-500 uppercase">Estatus</p>
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
                      historialData.equipo?.estatus === 'En reparación' ? 'bg-cyan-100 text-cyan-700' : 'bg-green-100 text-green-700'
                    }`}>
                      {historialData.equipo?.estatus}
                    </span>
                  </div>
                  <div>
                    <p className="text-[10px] text-slate-500 uppercase">Fecha Ingreso</p>
                    <p className="text-sm text-slate-700">{formatDate(historialData.equipo?.fecha_ingreso)}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-slate-500 uppercase">Dias en Taller</p>
                    <p className={`text-sm font-semibold ${historialData.equipo?.dias_en_taller > 15 && historialData.equipo?.estatus === 'En reparación' ? 'text-red-600' : 'text-slate-700'}`}>
                      {historialData.equipo?.dias_en_taller} dias
                    </p>
                  </div>
                </div>
                {historialData.equipo?.fecha_entrega && (
                  <div>
                    <p className="text-[10px] text-slate-500 uppercase">Fecha Entrega</p>
                    <p className="text-sm text-green-700">{formatDate(historialData.equipo?.fecha_entrega)}</p>
                  </div>
                )}
              </div>

              {/* Cotización info */}
              <div className="bg-blue-50 rounded-lg p-3 space-y-1">
                <p className="text-[10px] text-blue-600 uppercase font-semibold">Cotizacion de Origen</p>
                <p className="text-sm font-medium text-blue-800">{historialData.cotizacion?.quote_number}</p>
                <p className="text-xs text-blue-600">Estado actual: {historialData.cotizacion?.quote_status}</p>
                {historialData.cotizacion?.approved_at && (
                  <p className="text-xs text-blue-600">Aprobada: {formatDate(historialData.cotizacion?.approved_at)}</p>
                )}
              </div>

              {/* Recibido por */}
              <div className="bg-amber-50 rounded-lg p-3 space-y-1">
                <p className="text-[10px] text-amber-700 uppercase font-semibold">Recibido / Registrado por</p>
                <p className="text-sm font-medium text-amber-900">{historialData.recibido_por?.nombre || 'Sistema'}</p>
                {historialData.recibido_por?.email && (
                  <p className="text-xs text-amber-700">{historialData.recibido_por?.email}</p>
                )}
              </div>

              {/* Timeline de la cotización */}
              {historialData.cotizacion?.status_history?.length > 0 && (
                <div>
                  <p className="text-[10px] text-slate-500 uppercase font-semibold mb-2">Historial de Estados</p>
                  <div className="space-y-1.5 max-h-40 overflow-y-auto">
                    {historialData.cotizacion.status_history.map((sh, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs">
                        <div className="w-1.5 h-1.5 rounded-full bg-slate-400 flex-shrink-0" />
                        <span className="font-medium text-slate-700 w-24">{sh.status}</span>
                        <span className="text-slate-500">{formatDate(sh.timestamp)}</span>
                        <span className="text-slate-400 truncate">{sh.user}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
