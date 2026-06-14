import { useState, useEffect, useCallback } from 'react';
import { Card } from '../ui/card';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Send, CheckCircle2, FileText, DollarSign, Rocket, Target, Download, Filter, Loader2, Users } from 'lucide-react';
import api from '../../utils/api';
import { toast } from 'sonner';

const fmtUSD = (n) => `$${(n || 0).toLocaleString('es-VE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const FUNNEL_META = {
  enviada: { icon: Send, color: 'bg-sky-500', soft: 'bg-sky-50 text-sky-700 border-sky-200' },
  aprobada: { icon: CheckCircle2, color: 'bg-green-500', soft: 'bg-green-50 text-green-700 border-green-200' },
  facturada: { icon: FileText, color: 'bg-yellow-500', soft: 'bg-yellow-50 text-yellow-700 border-yellow-200' },
  pagada: { icon: DollarSign, color: 'bg-violet-500', soft: 'bg-violet-50 text-violet-700 border-violet-200' },
  entregada: { icon: Rocket, color: 'bg-emerald-600', soft: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
};

// Etiquetas de las estaciones del flujo para los tags de progreso
const STATION_COLOR = (label) => {
  const l = (label || '').toLowerCase();
  if (l.includes('imple') || l.includes('entreg')) return 'bg-emerald-100 text-emerald-800 border-emerald-300';
  if (l.includes('pag')) return 'bg-violet-100 text-violet-800 border-violet-300';
  if (l.includes('factur')) return 'bg-yellow-100 text-yellow-800 border-yellow-300';
  if (l.includes('aprob')) return 'bg-green-100 text-green-800 border-green-300';
  if (l.includes('enviada')) return 'bg-sky-100 text-sky-800 border-sky-300';
  return 'bg-slate-100 text-slate-700 border-slate-300';
};

export const AdvancedSalesTab = () => {
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [selTypes, setSelTypes] = useState([]);
  const [origin, setOrigin] = useState('all');
  const [filterCatalog, setFilterCatalog] = useState({ quote_types: [], origins: [] });
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    api.get('/reports/sales/advanced/filters')
      .then((r) => setFilterCatalog(r.data))
      .catch(() => {});
  }, []);

  const buildParams = useCallback(() => {
    const p = {};
    if (dateFrom) p.date_from = dateFrom;
    if (dateTo) p.date_to = dateTo;
    if (selTypes.length) p.quote_types = selTypes.join(',');
    if (origin !== 'all') p.origins = origin;
    return p;
  }, [dateFrom, dateTo, selTypes, origin]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/reports/sales/advanced', { params: buildParams() });
      setData(res.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error al cargar la consulta avanzada');
    } finally {
      setLoading(false);
    }
  }, [buildParams]);

  useEffect(() => { fetchData(); /* eslint-disable-next-line */ }, []);

  const toggleType = (t) =>
    setSelTypes((prev) => (prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]));

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await api.get('/reports/sales/advanced/export', { params: buildParams(), responseType: 'blob' });
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }));
      const a = document.createElement('a');
      const ts = new Date().toISOString().slice(0, 16).replace(/[:T-]/g, '');
      a.href = url; a.download = `consulta_ventas_avanzada_${ts}.xlsx`; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast.success('Excel descargado');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error al exportar a Excel');
    } finally {
      setExporting(false);
    }
  };

  const funnel = data?.funnel || [];
  const rows = data?.rows || [];

  return (
    <div className="space-y-4" data-testid="advanced-sales-tab">
      {/* ===== FILTROS ===== */}
      <Card className="p-4">
        <div className="flex items-center gap-2 mb-3 text-slate-700">
          <Filter size={16} /> <span className="font-semibold text-sm">Filtros acumulativos</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div>
            <label className="text-xs font-medium text-slate-500">Desde (fecha de creación)</label>
            <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="h-9 mt-1" data-testid="adv-date-from" />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-500">Hasta</label>
            <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="h-9 mt-1" data-testid="adv-date-to" />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-500">Origen de la Cotización</label>
            <Select value={origin} onValueChange={setOrigin}>
              <SelectTrigger className="h-9 mt-1" data-testid="adv-origin"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos los orígenes</SelectItem>
                {filterCatalog.origins.map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-end gap-2">
            <Button onClick={fetchData} disabled={loading} className="h-9 bg-blue-600 hover:bg-blue-700 flex-1" data-testid="adv-apply-btn">
              {loading ? <Loader2 size={15} className="animate-spin mr-1" /> : <Filter size={15} className="mr-1" />}Filtrar
            </Button>
            <Button onClick={handleExport} disabled={exporting || !rows.length} variant="outline" className="h-9 border-emerald-300 text-emerald-700 hover:bg-emerald-50" data-testid="adv-export-excel-btn">
              {exporting ? <Loader2 size={15} className="animate-spin mr-1" /> : <Download size={15} className="mr-1" />}Exportar a Excel
            </Button>
          </div>
        </div>
        <div className="mt-3">
          <label className="text-xs font-medium text-slate-500">Tipo de Cotización (selección múltiple)</label>
          <div className="flex flex-wrap gap-1.5 mt-1.5">
            {filterCatalog.quote_types.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => toggleType(t)}
                data-testid={`adv-type-${t}`}
                className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                  selTypes.includes(t) ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-slate-600 border-slate-300 hover:bg-slate-50'
                }`}
              >
                {t}
              </button>
            ))}
            {selTypes.length > 0 && (
              <button type="button" onClick={() => setSelTypes([])} className="px-3 py-1 rounded-full text-xs text-red-600 hover:bg-red-50 border border-transparent" data-testid="adv-type-clear">
                Limpiar ({selTypes.length})
              </button>
            )}
          </div>
        </div>
      </Card>

      {/* ===== FUNNEL CARDS + CRM ===== */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {funnel.map((f) => {
          const meta = FUNNEL_META[f.key] || FUNNEL_META.enviada;
          const Icon = meta.icon;
          return (
            <Card key={f.key} className={`p-3 border ${meta.soft}`} data-testid={`adv-funnel-${f.key}`}>
              <div className="flex items-center justify-between">
                <Icon size={18} />
                <span className="text-2xl font-bold" data-testid={`adv-funnel-count-${f.key}`}>{f.count}</span>
              </div>
              <p className="text-[11px] leading-tight mt-1 font-medium">{f.label}</p>
              <p className="text-[11px] mt-1 font-semibold opacity-80">{fmtUSD(f.total_usd)}</p>
            </Card>
          );
        })}
        <Card className="p-3 border bg-indigo-50 text-indigo-700 border-indigo-200" data-testid="adv-crm-kpi">
          <div className="flex items-center justify-between">
            <Target size={18} />
            <span className="text-2xl font-bold" data-testid="adv-crm-count">{data?.crm_conversion?.count ?? 0}</span>
          </div>
          <p className="text-[11px] leading-tight mt-1 font-medium">Conversión de Leads: Contacto a Prospecto</p>
        </Card>
      </div>

      {/* ===== GRILLA DETALLADA ===== */}
      <Card className="p-0 overflow-hidden">
        <div className="px-4 py-3 border-b bg-slate-50 flex items-center justify-between">
          <div className="flex items-center gap-2 text-slate-700">
            <Users size={16} /><span className="font-semibold text-sm">Detalle de Cotizaciones — Trazabilidad Administrativa</span>
          </div>
          <Badge variant="secondary" className="bg-slate-200 text-slate-700">{data?.total_rows ?? 0} registros</Badge>
        </div>
        <div className="overflow-x-auto max-h-[560px] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-100 sticky top-0 z-10">
              <tr>
                <th className="px-3 py-2 text-left text-xs font-semibold text-slate-600 uppercase">ID Cotización</th>
                <th className="px-3 py-2 text-left text-xs font-semibold text-slate-600 uppercase">Cliente / Empresa</th>
                <th className="px-3 py-2 text-left text-xs font-semibold text-slate-600 uppercase">Generador</th>
                <th className="px-3 py-2 text-left text-xs font-semibold text-slate-600 uppercase">Fecha Emisión</th>
                <th className="px-3 py-2 text-right text-xs font-semibold text-slate-600 uppercase">Monto USD</th>
                <th className="px-3 py-2 text-left text-xs font-semibold text-slate-600 uppercase">Tipo</th>
                <th className="px-3 py-2 text-left text-xs font-semibold text-slate-600 uppercase">Origen</th>
                <th className="px-3 py-2 text-center text-xs font-semibold text-slate-600 uppercase" title="Cajas en cotizaciones de Implementación">Cajas</th>
                <th className="px-3 py-2 text-center text-xs font-semibold text-slate-600 uppercase" title="Equipos en cotizaciones de Reparación">Equipos Rep.</th>
                <th className="px-3 py-2 text-center text-xs font-semibold text-slate-600 uppercase" title="Equipos vendidos">Equipos Vend.</th>
                <th className="px-3 py-2 text-left text-xs font-semibold text-slate-600 uppercase">Progreso Administrativo</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={11} className="px-3 py-8 text-center text-slate-400"><Loader2 size={20} className="animate-spin inline" /></td></tr>
              ) : rows.length === 0 ? (
                <tr><td colSpan={11} className="px-3 py-8 text-center text-slate-400 italic">Sin cotizaciones para los filtros aplicados.</td></tr>
              ) : (
                rows.map((r) => (
                  <tr key={r.quote_id} className="border-b border-slate-100 hover:bg-slate-50" data-testid={`adv-row-${r.quote_id}`}>
                    <td className="px-3 py-2 font-medium text-slate-800 whitespace-nowrap">{r.quote_number}</td>
                    <td className="px-3 py-2 text-slate-700">{r.client_name}</td>
                    <td className="px-3 py-2 text-slate-700 whitespace-nowrap" data-testid={`adv-row-creator-${r.quote_id}`}>{r.creator}</td>
                    <td className="px-3 py-2 text-slate-500 whitespace-nowrap">{r.created_at}</td>
                    <td className="px-3 py-2 text-right font-semibold text-slate-700 whitespace-nowrap">{fmtUSD(r.total_usd)}</td>
                    <td className="px-3 py-2"><Badge variant="secondary" className="bg-slate-100 text-slate-700 text-xs">{r.quote_type}</Badge></td>
                    <td className="px-3 py-2 text-xs text-slate-600 whitespace-nowrap">{r.origin}</td>
                    <td className="px-3 py-2 text-center text-slate-700" data-testid={`adv-row-boxes-${r.quote_id}`}>{r.boxes != null ? <span className="font-semibold text-blue-700">{r.boxes}</span> : <span className="text-slate-300">—</span>}</td>
                    <td className="px-3 py-2 text-center text-slate-700" data-testid={`adv-row-repair-${r.quote_id}`}>{r.repair_units != null ? <span className="font-semibold text-amber-700">{r.repair_units}</span> : <span className="text-slate-300">—</span>}</td>
                    <td className="px-3 py-2 text-center text-slate-700" data-testid={`adv-row-sold-${r.quote_id}`}>{r.sold_units != null ? <span className="font-semibold text-emerald-700">{r.sold_units}</span> : <span className="text-slate-300">—</span>}</td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap items-center gap-1">
                        {(r.progress || []).length === 0 ? (
                          <span className="text-xs text-slate-400 italic">Borrador</span>
                        ) : (
                          r.progress.map((st, i) => (
                            <span key={i} className="flex items-center">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${STATION_COLOR(st)}`}>{st}</span>
                              {i < r.progress.length - 1 && <span className="text-slate-300 mx-0.5">→</span>}
                            </span>
                          ))
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};
