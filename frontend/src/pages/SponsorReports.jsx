import { useState, useEffect, useCallback } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Card } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Landmark, Building2, Cpu, Download, RefreshCw, Filter, FolderKanban, DollarSign, ChevronDown, ChevronRight, Lock } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const fmtUSD = (n) => `$${(n || 0).toLocaleString('es-VE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const STATUS_CLR = {
  'Pendiente por Asignar': 'bg-amber-100 text-amber-800',
  'Asignado / En Proceso': 'bg-blue-100 text-blue-800',
  'En proceso/reasignado': 'bg-purple-100 text-purple-800',
  'Suspendido por Cliente': 'bg-rose-100 text-rose-800',
  'Suspendido por Banco': 'bg-rose-100 text-rose-800',
  'Finalizado / Producción': 'bg-emerald-100 text-emerald-800',
  'Finalizado': 'bg-emerald-100 text-emerald-800',
  'Cancelado': 'bg-slate-200 text-slate-700',
};

const SponsorReports = () => {
  const [loading, setLoading] = useState(true);
  const [denied, setDenied] = useState(false);
  const [data, setData] = useState({ groups: [], totals: { sponsors: 0, projects: 0, total_usd: 0 }, sponsors_available: [] });
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [sponsor, setSponsor] = useState('all');
  const [expanded, setExpanded] = useState({});
  const [exporting, setExporting] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      if (sponsor && sponsor !== 'all') params.sponsor = sponsor;
      const res = await api.get('/reports/sponsors', { params });
      setData(res.data);
      setDenied(false);
    } catch (err) {
      if (err.response?.status === 403) {
        setDenied(true);
      } else {
        toast.error(err.response?.data?.detail || 'Error al cargar el reporte');
      }
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, sponsor]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const params = {};
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      if (sponsor && sponsor !== 'all') params.sponsor = sponsor;
      const res = await api.get('/reports/sponsors/csv', { params, responseType: 'blob' });
      const url = URL.createObjectURL(new Blob([res.data], { type: 'text/csv' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = 'cartera_por_patrocinador.csv';
      a.click();
      URL.revokeObjectURL(url);
      toast.success('CSV exportado');
    } catch {
      toast.error('No se pudo exportar el CSV');
    } finally {
      setExporting(false);
    }
  };

  const toggle = (k) => setExpanded((p) => ({ ...p, [k]: !p[k] }));

  if (denied) {
    return (
      <div className="flex min-h-screen bg-white">
        <Sidebar />
        <main className="flex-1 flex items-center justify-center" data-testid="sponsor-reports-denied">
          <div className="text-center">
            <Lock size={48} className="mx-auto text-slate-300 mb-4" />
            <p className="text-lg font-semibold text-slate-600">Acceso restringido</p>
            <p className="text-sm text-slate-400">No tiene permiso para ver Reportes por Patrocinador.</p>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 p-8" data-testid="sponsor-reports-page">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="mb-6 flex items-start justify-between gap-4">
            <div>
              <h1 className="text-4xl font-bold text-slate-900 font-manrope mb-2 flex items-center gap-3">
                <Landmark className="text-indigo-600" size={34} />
                Reportes por Patrocinador
              </h1>
              <p className="text-slate-600">Cartera de proyectos agrupada por Banco patrocinante o llave Procesador — Banco</p>
            </div>
            <Button
              onClick={handleExport}
              disabled={exporting || loading}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
              data-testid="sponsor-export-csv"
            >
              <Download size={16} className="mr-2" />
              {exporting ? 'Exportando…' : 'Exportar CSV'}
            </Button>
          </div>

          {/* Filtros */}
          <Card className="p-4 mb-6">
            <div className="flex flex-wrap items-end gap-4">
              <div>
                <label className="text-xs font-medium text-slate-500 block mb-1">Desde</label>
                <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="w-[160px]" data-testid="sponsor-date-from" />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-500 block mb-1">Hasta</label>
                <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="w-[160px]" data-testid="sponsor-date-to" />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-500 block mb-1">Patrocinador</label>
                <Select value={sponsor} onValueChange={setSponsor}>
                  <SelectTrigger className="w-[260px]" data-testid="sponsor-filter-select">
                    <SelectValue placeholder="Todos los patrocinadores" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todos los patrocinadores</SelectItem>
                    {data.sponsors_available.map((s) => (
                      <SelectItem key={s} value={s}>{s}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button variant="outline" onClick={fetchData} disabled={loading} data-testid="sponsor-refresh">
                <RefreshCw size={15} className={`mr-2 ${loading ? 'animate-spin' : ''}`} />
                Actualizar
              </Button>
            </div>
          </Card>

          {/* KPIs */}
          <div className="grid grid-cols-3 gap-4 mb-6">
            <Card className="p-5 border-l-4 border-indigo-500" data-testid="sponsor-kpi-sponsors">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-500">Patrocinadores</p>
                  <p className="text-3xl font-bold text-slate-900">{data.totals.sponsors}</p>
                </div>
                <Landmark className="text-indigo-300" size={32} />
              </div>
            </Card>
            <Card className="p-5 border-l-4 border-blue-500" data-testid="sponsor-kpi-projects">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-500">Proyectos Patrocinados</p>
                  <p className="text-3xl font-bold text-slate-900">{data.totals.projects}</p>
                </div>
                <FolderKanban className="text-blue-300" size={32} />
              </div>
            </Card>
            <Card className="p-5 border-l-4 border-emerald-500" data-testid="sponsor-kpi-total">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-500">Monto Total (USD)</p>
                  <p className="text-3xl font-bold text-slate-900">{fmtUSD(data.totals.total_usd)}</p>
                </div>
                <DollarSign className="text-emerald-300" size={32} />
              </div>
            </Card>
          </div>

          {/* Grupos por patrocinador */}
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600" />
            </div>
          ) : data.groups.length === 0 ? (
            <Card className="p-16 text-center" data-testid="sponsor-empty">
              <Landmark size={48} className="mx-auto text-slate-300 mb-4" />
              <p className="text-lg font-medium text-slate-500">Sin proyectos patrocinados</p>
              <p className="text-sm text-slate-400">No hay proyectos con patrocinio en el rango seleccionado.</p>
            </Card>
          ) : (
            <div className="space-y-4">
              {data.groups.map((g) => (
                <Card key={g.patrocinador} className="overflow-hidden" data-testid={`sponsor-group-${g.patrocinador}`}>
                  <button
                    type="button"
                    onClick={() => toggle(g.patrocinador)}
                    className="w-full flex items-center justify-between p-4 hover:bg-slate-50 transition-colors text-left"
                    data-testid={`sponsor-group-toggle-${g.patrocinador}`}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      {expanded[g.patrocinador] ? <ChevronDown size={18} className="text-slate-400 shrink-0" /> : <ChevronRight size={18} className="text-slate-400 shrink-0" />}
                      <Landmark size={18} className="text-indigo-500 shrink-0" />
                      <div className="min-w-0">
                        <p className="font-semibold text-slate-800 truncate">{g.patrocinador}</p>
                        <div className="flex items-center gap-2 mt-0.5">
                          {g.is_composite && (
                            <Badge className="bg-indigo-100 text-indigo-700 text-[10px] gap-1"><Cpu size={10} />{g.processor_name}</Badge>
                          )}
                          <Badge className="bg-blue-100 text-blue-700 text-[10px] gap-1"><Building2 size={10} />{g.bank_name}</Badge>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-5 shrink-0">
                      {Object.entries(g.status_breakdown).map(([st, n]) => (
                        <Badge key={st} className={`text-[10px] ${STATUS_CLR[st] || 'bg-slate-100 text-slate-700'}`}>{st}: {n}</Badge>
                      ))}
                      <div className="text-right">
                        <p className="text-xs text-slate-400">{g.project_count} proyecto(s)</p>
                        <p className="text-sm font-bold text-emerald-700">{fmtUSD(g.total_usd)}</p>
                      </div>
                    </div>
                  </button>

                  {expanded[g.patrocinador] && (
                    <div className="border-t border-slate-100 overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead className="bg-slate-50 text-slate-500">
                          <tr>
                            <th className="px-4 py-2 text-left text-xs uppercase font-medium">N° Proyecto</th>
                            <th className="px-4 py-2 text-left text-xs uppercase font-medium">Cliente</th>
                            <th className="px-4 py-2 text-left text-xs uppercase font-medium">Segmento</th>
                            <th className="px-4 py-2 text-left text-xs uppercase font-medium">Tipo</th>
                            <th className="px-4 py-2 text-left text-xs uppercase font-medium">Estado</th>
                            <th className="px-4 py-2 text-left text-xs uppercase font-medium">Generador</th>
                            <th className="px-4 py-2 text-right text-xs uppercase font-medium">Monto USD</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {g.projects.map((pr) => (
                            <tr key={pr.project_id} className="hover:bg-slate-50" data-testid={`sponsor-project-${pr.project_id}`}>
                              <td className="px-4 py-2 font-mono text-xs text-slate-700">{pr.project_number}</td>
                              <td className="px-4 py-2 text-slate-700">{pr.client_name}</td>
                              <td className="px-4 py-2 text-slate-600">{pr.segment}</td>
                              <td className="px-4 py-2 text-slate-600">{pr.type}</td>
                              <td className="px-4 py-2">
                                <Badge className={`text-[10px] ${STATUS_CLR[pr.status] || 'bg-slate-100 text-slate-700'}`}>{pr.status}</Badge>
                              </td>
                              <td className="px-4 py-2 text-slate-600">{pr.generador}</td>
                              <td className="px-4 py-2 text-right font-medium text-slate-700">{fmtUSD(pr.total_usd)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </Card>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default SponsorReports;
