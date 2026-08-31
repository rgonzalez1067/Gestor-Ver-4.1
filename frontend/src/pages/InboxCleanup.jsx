import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, RefreshCw, Trash2, FolderCog, Database, Calculator, AlertTriangle } from 'lucide-react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import api from '../utils/api';

function formatBytes(bytes) {
  const b = Number(bytes) || 0;
  if (b < 1024) return `${b} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let val = b / 1024;
  let i = 0;
  while (val >= 1024 && i < units.length - 1) { val /= 1024; i++; }
  return `${val.toFixed(val >= 100 ? 0 : 1)} ${units[i]}`;
}

function fmtDate(iso) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString('es-VE'); } catch { return iso; }
}

function monthLabel(ym) {
  const [y, m] = (ym || '').split('-');
  const names = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
  const idx = parseInt(m, 10) - 1;
  return idx >= 0 && idx < 12 ? `${names[idx]} ${y}` : ym;
}

export default function InboxCleanup() {
  const navigate = useNavigate();
  const [collections, setCollections] = useState([]);
  const [selected, setSelected] = useState('');
  const [stats, setStats] = useState(null);
  const [loadingCols, setLoadingCols] = useState(true);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [preview, setPreview] = useState(null);
  const [calculating, setCalculating] = useState(false);
  const [purging, setPurging] = useState(false);

  const selectedLabel = collections.find((c) => c.collection === selected)?.label || selected;

  const loadCollections = useCallback(async () => {
    try {
      const { data } = await api.get('/admin/records/cleanup/collections');
      setCollections(data.collections || []);
      if ((data.collections || []).length > 0) {
        setSelected((prev) => prev || data.collections[0].collection);
      }
    } catch (err) {
      const status = err?.response?.status;
      if (status === 403) {
        toast.error('Solo administradores pueden depurar archivos');
        navigate('/settings');
      } else {
        toast.error(err?.response?.data?.detail || 'No se pudo cargar el catálogo de colecciones');
      }
    } finally {
      setLoadingCols(false);
    }
  }, [navigate]);

  const loadStats = useCallback(async (col) => {
    if (!col) return;
    setLoading(true);
    try {
      const { data } = await api.get(`/admin/records/cleanup/${col}/stats`);
      setStats(data);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'No se pudieron cargar las estadísticas');
      setStats(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { loadCollections(); }, [loadCollections]);
  useEffect(() => { if (selected) { setPreview(null); setStartDate(''); setEndDate(''); loadStats(selected); } }, [selected, loadStats]);

  const handleRefresh = () => { setRefreshing(true); setPreview(null); loadCollections(); loadStats(selected); };

  const selectMonth = (ym) => {
    const [y, m] = ym.split('-');
    const start = `${y}-${m}-01`;
    const last = new Date(parseInt(y, 10), parseInt(m, 10), 0).getDate();
    const end = `${y}-${m}-${String(last).padStart(2, '0')}`;
    setStartDate(start);
    setEndDate(end);
    setPreview(null);
  };

  const handleCalculate = async () => {
    if (!startDate || !endDate) { toast.error('Seleccione fecha de inicio y fin'); return; }
    setCalculating(true);
    setPreview(null);
    try {
      const { data } = await api.post(`/admin/records/cleanup/${selected}/preview`, { start_date: startDate, end_date: endDate });
      setPreview(data);
      if (data.count === 0) toast.info('No hay registros en el periodo seleccionado');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error al calcular el periodo');
    } finally {
      setCalculating(false);
    }
  };

  const handlePurge = async () => {
    if (!preview || preview.count === 0) return;
    const ok = window.confirm(
      `Se eliminarán PERMANENTEMENTE ${preview.count} registro(s) de "${selectedLabel}" ` +
      `(${formatBytes(preview.size_bytes)}) del periodo ${startDate} a ${endDate}.\n\n` +
      `Esta acción NO se puede deshacer. ¿Continuar?`
    );
    if (!ok) return;
    setPurging(true);
    try {
      const { data } = await api.post(`/admin/records/cleanup/${selected}/purge`, { start_date: startDate, end_date: endDate });
      toast.success(`Depuración completada: ${data.deleted_count} registro(s) eliminado(s)`);
      setPreview(null);
      handleRefresh();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error al depurar los registros');
    } finally {
      setPurging(false);
    }
  };

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 p-8" data-testid="records-cleanup-page">
        <div className="max-w-4xl mx-auto">
          <Button variant="ghost" size="sm" onClick={() => navigate('/settings')} className="mb-4 -ml-3" data-testid="back-to-settings">
            <ArrowLeft size={16} className="mr-2" /> Volver a Configuración
          </Button>

          <div className="flex items-start justify-between gap-4 mb-6">
            <div className="flex items-start gap-3">
              <div className="w-12 h-12 rounded-xl bg-rose-100 text-rose-600 flex items-center justify-center flex-shrink-0">
                <FolderCog size={26} />
              </div>
              <div>
                <h1 className="text-3xl font-bold text-slate-900 font-manrope">Depuración de Archivos</h1>
                <p className="text-slate-600 text-sm mt-1 max-w-2xl">
                  Seleccione una colección, calcule cuántos registros existen en un periodo y
                  depúrelos para reducir el peso de la base de datos. La eliminación es permanente.
                </p>
              </div>
            </div>
            <Button variant="outline" size="sm" onClick={handleRefresh} disabled={refreshing} data-testid="refresh-stats-btn">
              <RefreshCw size={14} className={`mr-1.5 ${refreshing ? 'animate-spin' : ''}`} /> Actualizar
            </Button>
          </div>

          {/* Selector de colección */}
          <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6" data-testid="collection-selector">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500 mb-3">Colección a depurar</p>
            {loadingCols ? (
              <div className="flex items-center text-slate-400 text-sm py-2">
                <RefreshCw size={16} className="animate-spin mr-2" /> Cargando colecciones...
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {collections.map((c) => {
                  const active = c.collection === selected;
                  return (
                    <button
                      key={c.collection}
                      type="button"
                      onClick={() => setSelected(c.collection)}
                      className={`px-3.5 py-2 rounded-lg border-2 text-sm transition-all flex items-center gap-2 ${active ? 'border-rose-500 bg-rose-50 text-rose-800 font-semibold' : 'border-slate-200 hover:border-rose-300 hover:bg-rose-50/50 text-slate-700'}`}
                      data-testid={`collection-tab-${c.collection}`}
                    >
                      <span>{c.label}</span>
                      <span className={`text-xs px-1.5 py-0.5 rounded-full ${active ? 'bg-rose-200 text-rose-800' : 'bg-slate-100 text-slate-500'}`}>
                        {(c.total_count ?? 0).toLocaleString('es-VE')}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-16 text-slate-400">
              <RefreshCw size={20} className="animate-spin mr-2" /> Cargando estadísticas...
            </div>
          ) : stats && (
            <>
              {/* Panorama general */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6" data-testid="records-stats-cards">
                <div className="bg-white rounded-xl border border-slate-200 p-5">
                  <div className="flex items-center gap-2 text-slate-500 text-xs font-medium uppercase tracking-wide">
                    <Database size={14} /> Total de registros
                  </div>
                  <p className="text-3xl font-bold text-slate-900 mt-2" data-testid="stat-total-count">
                    {(stats?.total_count ?? 0).toLocaleString('es-VE')}
                  </p>
                </div>
                <div className="bg-white rounded-xl border border-slate-200 p-5">
                  <div className="flex items-center gap-2 text-slate-500 text-xs font-medium uppercase tracking-wide">
                    <Database size={14} /> Peso total
                  </div>
                  <p className="text-3xl font-bold text-slate-900 mt-2" data-testid="stat-total-size">
                    {formatBytes(stats?.total_size_bytes)}
                  </p>
                </div>
                <div className="bg-white rounded-xl border border-slate-200 p-5">
                  <div className="flex items-center gap-2 text-slate-500 text-xs font-medium uppercase tracking-wide">
                    Rango de fechas
                  </div>
                  <p className="text-xs text-slate-600 mt-2">
                    <span className="font-medium">Más antiguo:</span> {fmtDate(stats?.oldest)}
                  </p>
                  <p className="text-xs text-slate-600 mt-1">
                    <span className="font-medium">Más reciente:</span> {fmtDate(stats?.newest)}
                  </p>
                </div>
              </div>

              {/* Selección de periodo */}
              <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6" data-testid="period-selector">
                <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
                  <Calculator size={20} className="text-slate-600" /> Depurar {selectedLabel} por periodo
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="start-date" className="text-sm text-slate-700">Fecha inicio</Label>
                    <Input id="start-date" type="date" value={startDate}
                      onChange={(e) => { setStartDate(e.target.value); setPreview(null); }}
                      className="mt-1" data-testid="start-date-input" />
                  </div>
                  <div>
                    <Label htmlFor="end-date" className="text-sm text-slate-700">Fecha fin (inclusive)</Label>
                    <Input id="end-date" type="date" value={endDate}
                      onChange={(e) => { setEndDate(e.target.value); setPreview(null); }}
                      className="mt-1" data-testid="end-date-input" />
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3 mt-4">
                  <Button onClick={handleCalculate} disabled={calculating || !startDate || !endDate}
                    className="bg-slate-800 hover:bg-slate-900 text-white" data-testid="calculate-btn">
                    <Calculator size={16} className="mr-2" />
                    {calculating ? 'Calculando...' : 'Calcular registros'}
                  </Button>

                  {preview && (
                    <div className="flex items-center gap-3 text-sm" data-testid="preview-result">
                      <Badge className="bg-slate-100 text-slate-700 border-slate-200">
                        {preview.count.toLocaleString('es-VE')} registro(s)
                      </Badge>
                      <Badge className="bg-slate-100 text-slate-700 border-slate-200">
                        {formatBytes(preview.size_bytes)}
                      </Badge>
                    </div>
                  )}
                </div>

                {preview && preview.count > 0 && (
                  <div className="mt-5 pt-5 border-t border-slate-100 bg-rose-50 -mx-6 -mb-6 px-6 py-4 rounded-b-xl">
                    <div className="flex items-start gap-3">
                      <AlertTriangle size={20} className="text-rose-600 flex-shrink-0 mt-0.5" />
                      <div className="flex-1">
                        <p className="text-sm text-rose-800 font-medium">
                          Está por eliminar {preview.count.toLocaleString('es-VE')} registro(s) permanentemente.
                        </p>
                        <p className="text-xs text-rose-600 mt-0.5">Esta acción no se puede deshacer.</p>
                      </div>
                      <Button onClick={handlePurge} disabled={purging}
                        className="bg-rose-600 hover:bg-rose-700 text-white flex-shrink-0" data-testid="purge-btn">
                        <Trash2 size={16} className="mr-2" />
                        {purging ? 'Depurando...' : 'Depurar ahora'}
                      </Button>
                    </div>
                  </div>
                )}
              </div>

              {/* Desglose por mes */}
              <div className="bg-white rounded-xl border border-slate-200 p-6" data-testid="monthly-breakdown">
                <h2 className="text-lg font-semibold text-slate-900 mb-1">Desglose por mes</h2>
                <p className="text-sm text-slate-500 mb-4">Haga clic en un mes para cargarlo como periodo.</p>
                {(!stats?.by_month || stats.by_month.length === 0) ? (
                  <p className="text-sm text-slate-400 py-4">No hay registros en esta colección.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm" data-testid="monthly-table">
                      <thead className="bg-slate-50 border-b border-slate-200">
                        <tr>
                          <th className="px-4 py-2.5 text-left font-medium text-slate-600">Mes</th>
                          <th className="px-4 py-2.5 text-right font-medium text-slate-600">Registros</th>
                          <th className="px-4 py-2.5 text-right font-medium text-slate-600">Peso</th>
                          <th className="px-4 py-2.5 text-right font-medium text-slate-600"></th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {stats.by_month.map((row) => (
                          <tr key={row.month} className="hover:bg-slate-50" data-testid={`month-row-${row.month}`}>
                            <td className="px-4 py-2.5 text-slate-800 font-medium">{monthLabel(row.month)}</td>
                            <td className="px-4 py-2.5 text-right text-slate-700">{row.count.toLocaleString('es-VE')}</td>
                            <td className="px-4 py-2.5 text-right text-slate-600">{formatBytes(row.size_bytes)}</td>
                            <td className="px-4 py-2.5 text-right">
                              <Button variant="outline" size="sm" onClick={() => selectMonth(row.month)}
                                data-testid={`select-month-${row.month}`}>
                                Seleccionar
                              </Button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
