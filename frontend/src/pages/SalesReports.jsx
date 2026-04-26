import { useState, useEffect, useMemo } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Card } from '../components/ui/card';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid,
  Line, ComposedChart, PieChart, Pie, Cell,
} from 'recharts';
import { TrendingUp, Filter, Clock, BarChart3, RefreshCw, Download, DollarSign, Users, Wrench, Package, Target, ArrowUp, ArrowDown, Minus, FileText, AlertTriangle, Rocket } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const fmtUSD = (n) => `$${(n || 0).toLocaleString('es-VE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const MONTH_NAMES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

const FUNNEL_COLORS = {
  Enviada: '#0ea5e9',
  Aprobada: '#22c55e',
  Facturada: '#f59e0b',
  Pagada: '#8b5cf6',
  Entregada: '#10b981',
};

const BUCKET_COLORS = { '0-7': '#22c55e', '8-15': '#f59e0b', '16-30': '#f97316', '>30': '#ef4444' };

const exportCSV = (rows, filename) => {
  if (!rows.length) return;
  const headers = Object.keys(rows[0]);
  const csv = [headers.join(','), ...rows.map(r => headers.map(h => {
    const v = r[h];
    if (v == null) return '';
    const s = String(v).replace(/"/g, '""');
    return /[",\n]/.test(s) ? `"${s}"` : s;
  }).join(','))].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
};

const SalesReports = () => {
  const [tab, setTab] = useState('funnel');

  // RBAC: Resumen Ejecutivo PDF requiere flag especial o admin
  const currentUser = useMemo(() => {
    try { return JSON.parse(localStorage.getItem('user') || 'null'); } catch { return null; }
  }, []);
  const canExportExecutive = currentUser?.role === 'admin' ||
    (currentUser?.special_permissions || []).includes('reportes_ventas:executive_summary');

  // Filtros compartidos
  const today = new Date();
  const yyyy = today.getFullYear();
  const [year, setYear] = useState(String(yyyy));
  const [segment, setSegment] = useState('all');
  const [category, setCategory] = useState('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const [funnelData, setFunnelData] = useState(null);
  const [agingData, setAgingData] = useState(null);
  const [monthlyData, setMonthlyData] = useState(null);
  const [receivablesData, setReceivablesData] = useState(null);
  const [rankingData, setRankingData] = useState(null);
  const [productivityData, setProductivityData] = useState(null);
  const [stockData, setStockData] = useState(null);
  const [leadsData, setLeadsData] = useState(null);
  const [irregularData, setIrregularData] = useState(null);
  const [irregularLoading, setIrregularLoading] = useState(false);
  const [loading, setLoading] = useState(false);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const params = {};
      if (segment !== 'all') params.segment = segment;
      if (category !== 'all') params.category = category;

      const fp = { ...params };
      if (dateFrom) fp.date_from = dateFrom;
      if (dateTo) fp.date_to = dateTo;

      const [fr, ar, mr, rec, rk, prod, stk, lds, irr] = await Promise.all([
        api.get('/reports/sales/funnel', { params: fp }),
        api.get('/reports/sales/aging', { params }),
        api.get('/reports/sales/monthly', { params: { ...params, year } }),
        api.get('/reports/sales/receivables', { params }),
        api.get('/reports/sales/clients-ranking', { params: { ...params, year, top_n: 20 } }),
        api.get('/reports/sales/repair-productivity', { params: dateFrom || dateTo ? { date_from: dateFrom, date_to: dateTo } : {} }),
        api.get('/reports/sales/stock-vs-demand', { params: { months_back: 6 } }),
        api.get('/reports/sales/leads-funnel', { params: dateFrom || dateTo ? { date_from: dateFrom, date_to: dateTo } : {} }),
        api.get('/reports/sales/irregular-quotes', { params: fp }),
      ]);
      setFunnelData(fr.data);
      setAgingData(ar.data);
      setMonthlyData(mr.data);
      setReceivablesData(rec.data);
      setRankingData(rk.data);
      setProductivityData(prod.data);
      setStockData(stk.data);
      setLeadsData(lds.data);
      setIrregularData(irr.data);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al cargar reportes');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); /* eslint-disable-next-line */ }, [segment, category, year, dateFrom, dateTo]);

  const downloadExecutiveSummary = async () => {
    try {
      const params = { year };
      if (segment !== 'all') params.segment = segment;
      if (category !== 'all') params.category = category;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const res = await api.get('/reports/sales/executive-summary', { params, responseType: 'blob' });
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const a = document.createElement('a');
      const ts = new Date().toISOString().slice(0, 16).replace(/[:T-]/g, '');
      a.href = url;
      a.download = `resumen_ejecutivo_${ts}.pdf`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast.success('Resumen ejecutivo descargado');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al generar PDF');
    }
  };

  const downloadIrregularPdf = async () => {
    setIrregularLoading(true);
    try {
      const params = {};
      if (segment !== 'all') params.segment = segment;
      if (category !== 'all') params.category = category;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const res = await api.get('/reports/sales/irregular-quotes/pdf', { params, responseType: 'blob' });
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const a = document.createElement('a');
      const ts = new Date().toISOString().slice(0, 16).replace(/[:T-]/g, '');
      a.href = url;
      a.download = `cotizaciones_irregulares_${ts}.pdf`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast.success('Reporte descargado');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al generar PDF');
    } finally {
      setIrregularLoading(false);
    }
  };

  const funnelChart = useMemo(() => {
    if (!funnelData) return [];
    return funnelData.stages.map(s => ({ stage: s.stage, count: s.count, monto: s.amount_usd, fill: FUNNEL_COLORS[s.stage] }));
  }, [funnelData]);

  const monthlyChart = useMemo(() => {
    if (!monthlyData) return [];
    return monthlyData.months.map(m => ({
      mes: MONTH_NAMES[m.month - 1],
      Cotizado: m.cotizado, Facturado: m.facturado, Cobrado: m.cobrado,
    }));
  }, [monthlyData]);

  const yearOptions = useMemo(() => {
    const arr = [];
    for (let y = yyyy; y >= yyyy - 5; y--) arr.push(String(y));
    return arr;
  }, [yyyy]);

  return (
    <div className="flex min-h-screen bg-white">
      <Sidebar />
      <main className="flex-1 p-8" data-testid="sales-reports-page">
        <div className="max-w-7xl mx-auto">
          <div className="flex justify-between items-start mb-6">
            <div>
              <h1 className="text-4xl font-bold text-slate-900 font-manrope mb-2">Reportes de Ventas</h1>
              <p className="text-slate-600">Embudo, aging y evolución mensual de cotizaciones</p>
            </div>
            <Button variant="outline" onClick={fetchAll} disabled={loading} data-testid="refresh-reports">
              <RefreshCw size={16} className={`mr-2 ${loading ? 'animate-spin' : ''}`} /> Actualizar
            </Button>
            {canExportExecutive && (
              <Button onClick={downloadExecutiveSummary} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="download-executive-summary">
                <FileText size={16} className="mr-2" /> Resumen Ejecutivo PDF
              </Button>
            )}
          </div>

          {/* Filtros compartidos */}
          <Card className="p-4 mb-6 border-slate-200">
            <div className="flex items-center gap-2 mb-3">
              <Filter size={14} className="text-slate-500" />
              <span className="text-sm font-semibold text-slate-700">Filtros</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <div>
                <label className="text-[10px] uppercase text-slate-500 font-semibold">Segmento</label>
                <Select value={segment} onValueChange={setSegment}>
                  <SelectTrigger data-testid="filter-segment" className="h-9 text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todos</SelectItem>
                    <SelectItem value="PYME">PYME</SelectItem>
                    <SelectItem value="CORP">CORP</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-[10px] uppercase text-slate-500 font-semibold">Categoría</label>
                <Select value={category} onValueChange={setCategory}>
                  <SelectTrigger data-testid="filter-category" className="h-9 text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todas</SelectItem>
                    <SelectItem value="implementation">Implementación</SelectItem>
                    <SelectItem value="fast_track">Fast Track</SelectItem>
                    <SelectItem value="equipment">Equipos</SelectItem>
                    <SelectItem value="repair">Reparaciones</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-[10px] uppercase text-slate-500 font-semibold">Desde (Funnel)</label>
                <Input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="h-9 text-sm" data-testid="filter-date-from" />
              </div>
              <div>
                <label className="text-[10px] uppercase text-slate-500 font-semibold">Hasta (Funnel)</label>
                <Input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className="h-9 text-sm" data-testid="filter-date-to" />
              </div>
              <div>
                <label className="text-[10px] uppercase text-slate-500 font-semibold">Año (Mensual)</label>
                <Select value={year} onValueChange={setYear}>
                  <SelectTrigger data-testid="filter-year" className="h-9 text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {yearOptions.map(y => <SelectItem key={y} value={y}>{y}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </Card>

          <Tabs value={tab} onValueChange={setTab}>
            <TabsList className="flex-wrap h-auto">
              <TabsTrigger value="funnel" data-testid="tab-funnel"><BarChart3 size={14} className="mr-1" /> Embudo</TabsTrigger>
              <TabsTrigger value="aging" data-testid="tab-aging"><Clock size={14} className="mr-1" /> Aging</TabsTrigger>
              <TabsTrigger value="monthly" data-testid="tab-monthly"><TrendingUp size={14} className="mr-1" /> Mensual</TabsTrigger>
              <TabsTrigger value="receivables" data-testid="tab-receivables"><DollarSign size={14} className="mr-1" /> Por Cobrar</TabsTrigger>
              <TabsTrigger value="ranking" data-testid="tab-ranking"><Users size={14} className="mr-1" /> Clientes Top</TabsTrigger>
              <TabsTrigger value="productivity" data-testid="tab-productivity"><Wrench size={14} className="mr-1" /> Productividad</TabsTrigger>
              <TabsTrigger value="stock" data-testid="tab-stock"><Package size={14} className="mr-1" /> Stock</TabsTrigger>
              <TabsTrigger value="leads" data-testid="tab-leads"><Target size={14} className="mr-1" /> Leads</TabsTrigger>
              <TabsTrigger value="irregular" data-testid="tab-irregular"><AlertTriangle size={14} className="mr-1" /> Irregulares</TabsTrigger>
            </TabsList>

            {/* === FUNNEL === */}
            <TabsContent value="funnel" className="mt-4">
              {!funnelData ? (
                <Card className="p-8 text-center text-slate-400">Cargando...</Card>
              ) : (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
                    <Card className="p-4 border-slate-200" data-testid="kpi-quotes-total">
                      <p className="text-xs text-slate-500">Cotizaciones</p>
                      <p className="text-2xl font-bold text-slate-900">{funnelData.totals.quotes_total}</p>
                    </Card>
                    <Card className="p-4 border-slate-200" data-testid="kpi-amount-total">
                      <p className="text-xs text-slate-500">Monto total cotizado</p>
                      <p className="text-2xl font-bold text-slate-900">{fmtUSD(funnelData.totals.amount_total_usd)}</p>
                    </Card>
                    <Card className="p-4 border-emerald-200 bg-emerald-50" data-testid="kpi-conv-paid">
                      <p className="text-xs text-emerald-700">Conversión Enviada → Pagada</p>
                      <p className="text-2xl font-bold text-emerald-800">{funnelData.totals.conversion_sent_to_paid}%</p>
                    </Card>
                    <Card className="p-4 border-blue-200 bg-blue-50" data-testid="kpi-conv-delivered">
                      <p className="text-xs text-blue-700">Conversión Enviada → Entregada</p>
                      <p className="text-2xl font-bold text-blue-800">{funnelData.totals.conversion_sent_to_delivered}%</p>
                    </Card>
                  </div>

                  <Card className="p-5 border-slate-200 mb-4">
                    <p className="text-sm font-semibold text-slate-800 mb-3">Cotizaciones por etapa del flujo</p>
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart data={funnelChart} layout="vertical" margin={{ left: 30 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                        <XAxis type="number" stroke="#64748b" />
                        <YAxis type="category" dataKey="stage" stroke="#64748b" width={90} />
                        <Tooltip
                          formatter={(val, name) => name === 'count' ? [val, '# Cotizaciones'] : [fmtUSD(val), 'Monto USD']}
                          contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8 }}
                        />
                        <Legend />
                        <Bar dataKey="count" name="# Cotizaciones" radius={[0, 4, 4, 0]} fill="#0ea5e9" />
                      </BarChart>
                    </ResponsiveContainer>
                  </Card>

                  <Card className="p-5 border-slate-200">
                    <p className="text-sm font-semibold text-slate-800 mb-3">Detalle por etapa</p>
                    <table className="w-full text-sm">
                      <thead className="text-left text-[11px] uppercase text-slate-500 border-b">
                        <tr><th className="py-2">Etapa</th><th className="py-2 text-right">Cotizaciones</th><th className="py-2 text-right">Monto USD</th></tr>
                      </thead>
                      <tbody>
                        {funnelData.stages.map(s => (
                          <tr key={s.stage} className="border-b last:border-b-0 hover:bg-slate-50">
                            <td className="py-2 font-medium" style={{ color: FUNNEL_COLORS[s.stage] }}>{s.stage}</td>
                            <td className="py-2 text-right">{s.count}</td>
                            <td className="py-2 text-right font-mono">{fmtUSD(s.amount_usd)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </Card>
                </>
              )}
            </TabsContent>

            {/* === AGING === */}
            <TabsContent value="aging" className="mt-4">
              {!agingData ? (
                <Card className="p-8 text-center text-slate-400">Cargando...</Card>
              ) : (
                <>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                    {agingData.buckets.map(b => (
                      <Card key={b.bucket} className="p-4" style={{ borderColor: BUCKET_COLORS[b.bucket] + '55' }} data-testid={`bucket-${b.bucket}`}>
                        <p className="text-xs uppercase font-semibold" style={{ color: BUCKET_COLORS[b.bucket] }}>{b.bucket} días</p>
                        <p className="text-xl font-bold text-slate-900">{b.count}</p>
                        <p className="text-xs text-slate-500 font-mono">{fmtUSD(b.amount_usd)}</p>
                      </Card>
                    ))}
                  </div>
                  <Card className="p-5 border-slate-200">
                    <div className="flex items-center justify-between mb-3">
                      <p className="text-sm font-semibold text-slate-800">Cotizaciones pendientes ({agingData.rows.length})</p>
                      <Button size="sm" variant="outline" onClick={() => exportCSV(agingData.rows, 'aging_cotizaciones.csv')} disabled={!agingData.rows.length} data-testid="export-aging-csv">
                        <Download size={14} className="mr-1" /> CSV
                      </Button>
                    </div>
                    {agingData.rows.length === 0 ? (
                      <p className="text-center text-slate-400 py-6">No hay cotizaciones pendientes — todo está al día. 🎉</p>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead className="text-left text-[11px] uppercase text-slate-500 border-b">
                            <tr>
                              <th className="py-2">Número</th>
                              <th className="py-2">Cliente</th>
                              <th className="py-2">Estado</th>
                              <th className="py-2">Gestor</th>
                              <th className="py-2 text-right">USD</th>
                              <th className="py-2 text-right">Días</th>
                            </tr>
                          </thead>
                          <tbody>
                            {agingData.rows.map(r => (
                              <tr key={r.quote_id} className="border-b last:border-b-0 hover:bg-slate-50" data-testid={`aging-row-${r.quote_number}`}>
                                <td className="py-2 font-mono text-xs">{r.quote_number}</td>
                                <td className="py-2">{r.client_name}</td>
                                <td className="py-2"><Badge variant="outline">{r.quote_status}</Badge></td>
                                <td className="py-2 text-xs text-slate-600">{r.gestor || '—'}</td>
                                <td className="py-2 text-right font-mono">{fmtUSD(r.total_usd)}</td>
                                <td className="py-2 text-right">
                                  <span className="px-2 py-0.5 rounded-full text-xs font-bold" style={{ backgroundColor: BUCKET_COLORS[r.bucket] + '22', color: BUCKET_COLORS[r.bucket] }}>
                                    {r.days_in_state}d
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </Card>
                </>
              )}
            </TabsContent>

            {/* === MONTHLY === */}
            <TabsContent value="monthly" className="mt-4">
              {!monthlyData ? (
                <Card className="p-8 text-center text-slate-400">Cargando...</Card>
              ) : (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
                    <Card className="p-4 border-blue-200 bg-blue-50" data-testid="kpi-cotizado">
                      <p className="text-xs text-blue-700">Cotizado {year}</p>
                      <p className="text-2xl font-bold text-blue-900">{fmtUSD(monthlyData.totals.cotizado)}</p>
                    </Card>
                    <Card className="p-4 border-amber-200 bg-amber-50" data-testid="kpi-facturado">
                      <p className="text-xs text-amber-700">Facturado {year}</p>
                      <p className="text-2xl font-bold text-amber-900">{fmtUSD(monthlyData.totals.facturado)}</p>
                    </Card>
                    <Card className="p-4 border-emerald-200 bg-emerald-50" data-testid="kpi-cobrado">
                      <p className="text-xs text-emerald-700">Cobrado {year}</p>
                      <p className="text-2xl font-bold text-emerald-900">{fmtUSD(monthlyData.totals.cobrado)}</p>
                    </Card>
                  </div>

                  <Card className="p-5 border-slate-200 mb-4">
                    <p className="text-sm font-semibold text-slate-800 mb-3">Evolución mensual {year}</p>
                    <ResponsiveContainer width="100%" height={320}>
                      <ComposedChart data={monthlyChart}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                        <XAxis dataKey="mes" stroke="#64748b" />
                        <YAxis stroke="#64748b" tickFormatter={(v) => `$${v.toLocaleString()}`} />
                        <Tooltip formatter={(v) => fmtUSD(v)} contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8 }} />
                        <Legend />
                        <Bar dataKey="Cotizado" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="Facturado" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                        <Line type="monotone" dataKey="Cobrado" stroke="#10b981" strokeWidth={3} dot={{ r: 4 }} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </Card>

                  <Card className="p-5 border-slate-200">
                    <div className="flex items-center justify-between mb-3">
                      <p className="text-sm font-semibold text-slate-800">Detalle mensual</p>
                      <Button size="sm" variant="outline" onClick={() => exportCSV(monthlyData.months.map(m => ({ mes: MONTH_NAMES[m.month-1], ...m })), `ventas_${year}.csv`)} data-testid="export-monthly-csv">
                        <Download size={14} className="mr-1" /> CSV
                      </Button>
                    </div>
                    <table className="w-full text-sm">
                      <thead className="text-left text-[11px] uppercase text-slate-500 border-b">
                        <tr>
                          <th className="py-2">Mes</th>
                          <th className="py-2 text-right">Cotizado USD</th>
                          <th className="py-2 text-right">Facturado USD</th>
                          <th className="py-2 text-right">Cobrado USD</th>
                          <th className="py-2 text-right text-xs">Gap Fact-Cob</th>
                        </tr>
                      </thead>
                      <tbody>
                        {monthlyData.months.map(m => {
                          const gap = m.facturado - m.cobrado;
                          return (
                            <tr key={m.month} className="border-b last:border-b-0 hover:bg-slate-50">
                              <td className="py-2 font-medium">{MONTH_NAMES[m.month - 1]}</td>
                              <td className="py-2 text-right font-mono text-blue-700">{fmtUSD(m.cotizado)}</td>
                              <td className="py-2 text-right font-mono text-amber-700">{fmtUSD(m.facturado)}</td>
                              <td className="py-2 text-right font-mono text-emerald-700">{fmtUSD(m.cobrado)}</td>
                              <td className="py-2 text-right font-mono text-xs text-slate-500">{gap > 0 ? fmtUSD(gap) : '—'}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </Card>
                </>
              )}
            </TabsContent>

            {/* === RECEIVABLES === */}
            <TabsContent value="receivables" className="mt-4">
              {!receivablesData ? (
                <Card className="p-8 text-center text-slate-400">Cargando...</Card>
              ) : (
                <>
                  <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-4">
                    <Card className="p-4 col-span-2 border-rose-200 bg-rose-50" data-testid="kpi-pending-total">
                      <p className="text-xs text-rose-700">Total por cobrar</p>
                      <p className="text-2xl font-bold text-rose-900">{fmtUSD(receivablesData.total_pending_usd)}</p>
                      <p className="text-[11px] text-rose-600">{receivablesData.total_pending_count} factura(s)</p>
                    </Card>
                    {receivablesData.buckets.map(b => (
                      <Card key={b.bucket} className="p-4" style={{ borderColor: BUCKET_COLORS[b.bucket] + '55' }} data-testid={`rec-bucket-${b.bucket}`}>
                        <p className="text-xs uppercase font-semibold" style={{ color: BUCKET_COLORS[b.bucket] }}>{b.bucket} días</p>
                        <p className="text-xl font-bold text-slate-900">{b.count}</p>
                        <p className="text-xs text-slate-500 font-mono">{fmtUSD(b.amount_usd)}</p>
                      </Card>
                    ))}
                  </div>

                  {receivablesData.top_debtors.length > 0 && (
                    <Card className="p-5 border-slate-200 mb-4">
                      <p className="text-sm font-semibold text-slate-800 mb-3">Top deudores</p>
                      <table className="w-full text-sm">
                        <thead className="text-left text-[11px] uppercase text-slate-500 border-b">
                          <tr><th className="py-2">Cliente</th><th className="py-2 text-right">Facturas</th><th className="py-2 text-right">Monto USD</th><th className="py-2 text-right">Máx. días</th></tr>
                        </thead>
                        <tbody>
                          {receivablesData.top_debtors.map(d => (
                            <tr key={d.client_id} className="border-b last:border-b-0 hover:bg-slate-50">
                              <td className="py-2 font-medium">{d.client_name} <Badge variant="outline" className="ml-2 text-[10px]">{d.client_segment}</Badge></td>
                              <td className="py-2 text-right">{d.invoices}</td>
                              <td className="py-2 text-right font-mono text-rose-700 font-bold">{fmtUSD(d.amount_usd)}</td>
                              <td className="py-2 text-right text-xs text-slate-500">{d.max_days}d</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </Card>
                  )}

                  <Card className="p-5 border-slate-200">
                    <div className="flex items-center justify-between mb-3">
                      <p className="text-sm font-semibold text-slate-800">Detalle de facturas pendientes ({receivablesData.rows.length})</p>
                      <Button size="sm" variant="outline" onClick={() => exportCSV(receivablesData.rows, 'cuentas_por_cobrar.csv')} disabled={!receivablesData.rows.length} data-testid="export-receivables-csv">
                        <Download size={14} className="mr-1" /> CSV
                      </Button>
                    </div>
                    {receivablesData.rows.length === 0 ? (
                      <p className="text-center text-emerald-600 py-6">Sin cuentas por cobrar pendientes 🎉</p>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead className="text-left text-[11px] uppercase text-slate-500 border-b">
                            <tr>
                              <th className="py-2">Cotización</th><th className="py-2">Factura</th><th className="py-2">Cliente</th>
                              <th className="py-2">Gestor</th><th className="py-2 text-right">USD</th><th className="py-2 text-right">Días</th>
                            </tr>
                          </thead>
                          <tbody>
                            {receivablesData.rows.map(r => (
                              <tr key={r.quote_id} className="border-b last:border-b-0 hover:bg-slate-50">
                                <td className="py-2 font-mono text-xs">{r.quote_number}</td>
                                <td className="py-2 text-xs">{r.invoice_number || '—'}</td>
                                <td className="py-2">{r.client_name}</td>
                                <td className="py-2 text-xs text-slate-600">{r.gestor || '—'}</td>
                                <td className="py-2 text-right font-mono">{fmtUSD(r.total_usd)}</td>
                                <td className="py-2 text-right">
                                  <span className="px-2 py-0.5 rounded-full text-xs font-bold" style={{ backgroundColor: BUCKET_COLORS[r.bucket] + '22', color: BUCKET_COLORS[r.bucket] }}>{r.days_since_invoice}d</span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </Card>
                </>
              )}
            </TabsContent>

            {/* === RANKING === */}
            <TabsContent value="ranking" className="mt-4">
              {!rankingData ? (
                <Card className="p-8 text-center text-slate-400">Cargando...</Card>
              ) : (
                <Card className="p-5 border-slate-200">
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-sm font-semibold text-slate-800">Top {rankingData.ranking.length} clientes — Total {fmtUSD(rankingData.total_amount)} en {year}</p>
                    <Button size="sm" variant="outline" onClick={() => exportCSV(rankingData.ranking, `ranking_clientes_${year}.csv`)} disabled={!rankingData.ranking.length} data-testid="export-ranking-csv">
                      <Download size={14} className="mr-1" /> CSV
                    </Button>
                  </div>
                  {rankingData.ranking.length === 0 ? (
                    <p className="text-center text-slate-400 py-6">Sin datos para el año seleccionado</p>
                  ) : (
                    <table className="w-full text-sm">
                      <thead className="text-left text-[11px] uppercase text-slate-500 border-b">
                        <tr>
                          <th className="py-2">#</th><th className="py-2">Cliente</th>
                          <th className="py-2 text-right">Cotizaciones</th>
                          <th className="py-2 text-right">Total Cotizado</th>
                          <th className="py-2 text-right">Pagado</th>
                          <th className="py-2 text-right">Tend. Trim.</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rankingData.ranking.map((r, idx) => (
                          <tr key={r.client_id} className="border-b last:border-b-0 hover:bg-slate-50" data-testid={`ranking-row-${idx}`}>
                            <td className="py-2 font-bold text-slate-400">{idx + 1}</td>
                            <td className="py-2 font-medium">{r.client_name} <Badge variant="outline" className="ml-2 text-[10px]">{r.client_segment}</Badge></td>
                            <td className="py-2 text-right">{r.quotes_count}</td>
                            <td className="py-2 text-right font-mono font-bold">{fmtUSD(r.total_usd)}</td>
                            <td className="py-2 text-right font-mono text-emerald-700">{fmtUSD(r.paid_usd)}</td>
                            <td className="py-2 text-right">
                              {r.trend_pct === null ? (
                                <span className="text-xs text-blue-600 font-semibold">NUEVO</span>
                              ) : r.trend_pct > 0 ? (
                                <span className="inline-flex items-center text-emerald-700 text-xs font-bold"><ArrowUp size={12} />{r.trend_pct}%</span>
                              ) : r.trend_pct < 0 ? (
                                <span className="inline-flex items-center text-rose-700 text-xs font-bold"><ArrowDown size={12} />{r.trend_pct}%</span>
                              ) : (
                                <span className="inline-flex items-center text-slate-400 text-xs"><Minus size={12} />0%</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </Card>
              )}
            </TabsContent>

            {/* === PRODUCTIVITY === */}
            <TabsContent value="productivity" className="mt-4">
              {!productivityData ? (
                <Card className="p-8 text-center text-slate-400">Cargando...</Card>
              ) : (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
                    <Card className="p-4 border-slate-200" data-testid="kpi-prod-total">
                      <p className="text-xs text-slate-500">Reparaciones evaluadas</p>
                      <p className="text-2xl font-bold text-slate-900">{productivityData.sla_total}</p>
                    </Card>
                    <Card className="p-4 border-rose-200 bg-rose-50" data-testid="kpi-prod-breach">
                      <p className="text-xs text-rose-700">Excedieron SLA (&gt;7 días)</p>
                      <p className="text-2xl font-bold text-rose-900">{productivityData.sla_breach}</p>
                    </Card>
                    <Card className="p-4 border-amber-200 bg-amber-50" data-testid="kpi-prod-pct">
                      <p className="text-xs text-amber-700">% Breach</p>
                      <p className="text-2xl font-bold text-amber-900">{productivityData.sla_pct}%</p>
                    </Card>
                  </div>

                  <Card className="p-5 border-slate-200 mb-4">
                    <p className="text-sm font-semibold text-slate-800 mb-3">Por implementador / gestor</p>
                    <table className="w-full text-sm">
                      <thead className="text-left text-[11px] uppercase text-slate-500 border-b">
                        <tr>
                          <th className="py-2">Gestor</th><th className="py-2 text-right">Reparaciones</th>
                          <th className="py-2 text-right">Avg Reparación (h)</th>
                          <th className="py-2 text-right">Avg Entrega (h)</th>
                          <th className="py-2 text-right">Avg Total (días)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {productivityData.by_implementor.map(i => (
                          <tr key={i.gestor} className="border-b last:border-b-0 hover:bg-slate-50">
                            <td className="py-2 font-medium">{i.gestor}</td>
                            <td className="py-2 text-right">{i.count}</td>
                            <td className="py-2 text-right font-mono">{i.avg_repair_hours ?? '—'}h</td>
                            <td className="py-2 text-right font-mono">{i.avg_deliver_hours ?? '—'}h</td>
                            <td className="py-2 text-right font-mono font-bold">{i.avg_total_days ?? '—'}d</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </Card>

                  <Card className="p-5 border-slate-200">
                    <div className="flex items-center justify-between mb-3">
                      <p className="text-sm font-semibold text-slate-800">Detalle por reparación</p>
                      <Button size="sm" variant="outline" onClick={() => exportCSV(productivityData.rows, 'productividad_reparaciones.csv')} disabled={!productivityData.rows.length} data-testid="export-prod-csv">
                        <Download size={14} className="mr-1" /> CSV
                      </Button>
                    </div>
                    <div className="overflow-x-auto max-h-96 overflow-y-auto">
                      <table className="w-full text-sm">
                        <thead className="text-left text-[11px] uppercase text-slate-500 border-b sticky top-0 bg-white">
                          <tr>
                            <th className="py-2">Cotización</th><th className="py-2">Cliente</th>
                            <th className="py-2">Gestor</th><th className="py-2 text-right">Reparación (h)</th>
                            <th className="py-2 text-right">Entrega (h)</th><th className="py-2 text-right">Total (días)</th>
                          </tr>
                        </thead>
                        <tbody>
                          {productivityData.rows.map(r => (
                            <tr key={r.quote_id} className="border-b last:border-b-0 hover:bg-slate-50">
                              <td className="py-2 font-mono text-xs">{r.quote_number}</td>
                              <td className="py-2">{r.client_name}</td>
                              <td className="py-2 text-xs text-slate-600">{r.gestor}</td>
                              <td className="py-2 text-right font-mono">{r.repair_lead_h ?? '—'}</td>
                              <td className="py-2 text-right font-mono">{r.deliver_lead_h ?? '—'}</td>
                              <td className="py-2 text-right font-mono font-bold">{r.total_lead_days ?? '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </Card>
                </>
              )}
            </TabsContent>

            {/* === STOCK === */}
            <TabsContent value="stock" className="mt-4">
              {!stockData ? (
                <Card className="p-8 text-center text-slate-400">Cargando...</Card>
              ) : (
                <>
                  <div className="grid grid-cols-3 gap-3 mb-4">
                    <Card className="p-4 border-rose-200 bg-rose-50" data-testid="kpi-stock-critical">
                      <p className="text-xs text-rose-700 uppercase font-semibold">Crítico</p>
                      <p className="text-2xl font-bold text-rose-900">{stockData.summary.critical}</p>
                      <p className="text-[11px] text-rose-600">&lt;1 mes de cobertura</p>
                    </Card>
                    <Card className="p-4 border-amber-200 bg-amber-50" data-testid="kpi-stock-warning">
                      <p className="text-xs text-amber-700 uppercase font-semibold">Alerta</p>
                      <p className="text-2xl font-bold text-amber-900">{stockData.summary.warning}</p>
                      <p className="text-[11px] text-amber-600">1-2 meses de cobertura</p>
                    </Card>
                    <Card className="p-4 border-emerald-200 bg-emerald-50" data-testid="kpi-stock-ok">
                      <p className="text-xs text-emerald-700 uppercase font-semibold">OK</p>
                      <p className="text-2xl font-bold text-emerald-900">{stockData.summary.ok}</p>
                      <p className="text-[11px] text-emerald-600">&gt;2 meses de cobertura</p>
                    </Card>
                  </div>

                  <Card className="p-5 border-slate-200">
                    <div className="flex items-center justify-between mb-3">
                      <p className="text-sm font-semibold text-slate-800">Top {stockData.items.length} ítems por demanda (últimos {stockData.months_back} meses)</p>
                      <Button size="sm" variant="outline" onClick={() => exportCSV(stockData.items, 'stock_vs_demanda.csv')} disabled={!stockData.items.length} data-testid="export-stock-csv">
                        <Download size={14} className="mr-1" /> CSV
                      </Button>
                    </div>
                    <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
                      <table className="w-full text-sm">
                        <thead className="text-left text-[11px] uppercase text-slate-500 border-b sticky top-0 bg-white">
                          <tr>
                            <th className="py-2">Ítem</th><th className="py-2">Tipo</th>
                            <th className="py-2 text-right">Stock</th>
                            <th className="py-2 text-right">Demanda</th>
                            <th className="py-2 text-right">Demanda/mes</th>
                            <th className="py-2 text-right">Cobertura</th>
                            <th className="py-2 text-center">Estado</th>
                          </tr>
                        </thead>
                        <tbody>
                          {stockData.items.map(it => {
                            const sColors = { critical: 'bg-rose-100 text-rose-700', warning: 'bg-amber-100 text-amber-700', ok: 'bg-emerald-100 text-emerald-700', no_demand: 'bg-slate-100 text-slate-500' };
                            const sLabel = { critical: 'CRÍTICO', warning: 'ALERTA', ok: 'OK', no_demand: 'SIN DEMANDA' };
                            return (
                              <tr key={it.item_id} className="border-b last:border-b-0 hover:bg-slate-50">
                                <td className="py-2 font-medium">{it.item_name}</td>
                                <td className="py-2 text-xs text-slate-500">{it.item_type}</td>
                                <td className="py-2 text-right font-mono">{it.stock}</td>
                                <td className="py-2 text-right font-mono font-bold">{it.demand}</td>
                                <td className="py-2 text-right font-mono text-xs">{it.monthly_demand}</td>
                                <td className="py-2 text-right font-mono text-xs">{it.coverage_months ?? '∞'}</td>
                                <td className="py-2 text-center">
                                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${sColors[it.status]}`}>{sLabel[it.status]}</span>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </Card>
                </>
              )}
            </TabsContent>

            {/* === LEADS === */}
            <TabsContent value="leads" className="mt-4">
              {!leadsData ? (
                <Card className="p-8 text-center text-slate-400">Cargando...</Card>
              ) : (
                <>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                    <Card className="p-4 border-slate-200" data-testid="kpi-leads-total">
                      <p className="text-xs text-slate-500">Total Leads</p>
                      <p className="text-2xl font-bold text-slate-900">{leadsData.total_leads}</p>
                    </Card>
                    <Card className="p-4 border-emerald-200 bg-emerald-50" data-testid="kpi-leads-converted">
                      <p className="text-xs text-emerald-700">Convertidos</p>
                      <p className="text-2xl font-bold text-emerald-900">{leadsData.converted}</p>
                    </Card>
                    <Card className="p-4 border-blue-200 bg-blue-50" data-testid="kpi-leads-rate">
                      <p className="text-xs text-blue-700">Tasa Conversión</p>
                      <p className="text-2xl font-bold text-blue-900">{leadsData.conversion_pct}%</p>
                    </Card>
                    <Card className="p-4 border-purple-200 bg-purple-50" data-testid="kpi-leads-avg-days">
                      <p className="text-xs text-purple-700">Días Promedio</p>
                      <p className="text-2xl font-bold text-purple-900">{leadsData.avg_convert_days ?? '—'}</p>
                    </Card>
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <Card className="p-5 border-slate-200">
                      <p className="text-sm font-semibold text-slate-800 mb-3">Distribución por origen</p>
                      <ResponsiveContainer width="100%" height={250}>
                        <PieChart>
                          <Pie data={leadsData.by_origin} dataKey="total" nameKey="origin" outerRadius={90} label={(e) => `${e.origin}: ${e.total}`}>
                            {leadsData.by_origin.map((_, idx) => (
                              <Cell key={idx} fill={['#3b82f6','#22c55e','#f59e0b','#8b5cf6','#ef4444','#10b981'][idx % 6]} />
                            ))}
                          </Pie>
                          <Tooltip />
                        </PieChart>
                      </ResponsiveContainer>
                    </Card>

                    <Card className="p-5 border-slate-200">
                      <p className="text-sm font-semibold text-slate-800 mb-3">Conversión por origen</p>
                      <table className="w-full text-sm">
                        <thead className="text-left text-[11px] uppercase text-slate-500 border-b">
                          <tr><th className="py-2">Origen</th><th className="py-2 text-right">Leads</th><th className="py-2 text-right">Convertidos</th><th className="py-2 text-right">%</th></tr>
                        </thead>
                        <tbody>
                          {leadsData.by_origin.map(o => (
                            <tr key={o.origin} className="border-b last:border-b-0 hover:bg-slate-50">
                              <td className="py-2 font-medium">{o.origin}</td>
                              <td className="py-2 text-right">{o.total}</td>
                              <td className="py-2 text-right text-emerald-700">{o.converted}</td>
                              <td className="py-2 text-right font-bold">{o.conversion_pct}%</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </Card>
                  </div>
                </>
              )}
            </TabsContent>

            {/* === IRREGULARES === */}
            <TabsContent value="irregular" className="mt-4">
              {!irregularData ? (
                <Card className="p-8 text-center text-slate-400">Cargando...</Card>
              ) : (
                <>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                    <Card className="p-4 border-rose-200 bg-rose-50" data-testid="kpi-irregular-total">
                      <p className="text-xs text-rose-700">Cotizaciones irregulares</p>
                      <p className="text-2xl font-bold text-rose-800">{irregularData.total_irregular}</p>
                    </Card>
                    <Card className="p-4 border-violet-200 bg-violet-50" data-testid="kpi-irregular-projects">
                      <p className="text-xs text-violet-700">Pasadas a Proyecto</p>
                      <p className="text-2xl font-bold text-violet-800">{irregularData.passed_to_project}</p>
                    </Card>
                    <Card className="p-4 border-slate-200" data-testid="kpi-irregular-amount">
                      <p className="text-xs text-slate-500">Monto total (USD)</p>
                      <p className="text-2xl font-bold text-slate-900">{fmtUSD(irregularData.total_usd)}</p>
                    </Card>
                    <Card className="p-4 border-amber-200 bg-amber-50">
                      <p className="text-xs text-amber-700 mb-1">Tipos de irregularidad</p>
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(irregularData.by_issue || {}).map(([k, n]) => (
                          <Badge key={k} variant="outline" className="bg-white text-amber-800 border-amber-300 text-[10px]">
                            {n} × {k}
                          </Badge>
                        ))}
                      </div>
                    </Card>
                  </div>

                  <div className="flex justify-end mb-3">
                    <Button
                      onClick={downloadIrregularPdf}
                      disabled={irregularLoading}
                      data-testid="download-irregular-pdf"
                      className="bg-rose-600 hover:bg-rose-700 text-white"
                    >
                      <FileText size={16} className="mr-2" />
                      {irregularLoading ? 'Generando...' : 'Descargar PDF'}
                    </Button>
                  </div>

                  {irregularData.items.length === 0 ? (
                    <Card className="p-10 text-center">
                      <p className="text-emerald-700 text-lg font-semibold">✅ No hay cotizaciones irregulares con los filtros aplicados.</p>
                    </Card>
                  ) : (
                    <div className="space-y-3" data-testid="irregular-list">
                      {irregularData.items.map((it) => (
                        <Card key={it.quote_id} className="p-4 border-slate-200">
                          <div className="flex items-start justify-between gap-2 flex-wrap">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-mono text-sm font-bold text-sky-800">{it.quote_number || '—'}</span>
                                <span className="text-slate-300">·</span>
                                <span className="font-semibold text-slate-800">{it.client_name || '—'}</span>
                                {it.passed_to_project && (
                                  <Badge className="bg-gradient-to-r from-violet-500 to-purple-600 text-white text-[10px] border-0">
                                    <Rocket size={10} className="mr-1" /> Pasó a Proyecto
                                  </Badge>
                                )}
                              </div>
                              <div className="flex gap-3 mt-1 text-xs text-slate-500 flex-wrap">
                                <span>Categoría: <b className="text-slate-700">{(it.quote_category || '—')}</b></span>
                                <span>Segmento: <b className="text-slate-700">{(it.client_segment || '—').toUpperCase()}</b></span>
                                <span>Estado actual: <b className="text-slate-700">{it.current_status}</b></span>
                                <span>Monto: <b className="text-slate-700">{fmtUSD(it.total_usd)}</b></span>
                              </div>
                            </div>
                          </div>

                          {/* Timeline */}
                          <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-1.5">
                            {it.phases.map((ph) => (
                              <div
                                key={ph.field}
                                className={`px-2 py-1.5 rounded border text-center ${
                                  ph.present
                                    ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                                    : 'bg-rose-50 border-rose-200 text-rose-800'
                                }`}
                                data-testid={`phase-${ph.field}`}
                              >
                                <div className="text-[10px] font-semibold">{ph.label}</div>
                                <div className="text-[10px] font-mono mt-0.5">
                                  {ph.timestamp ? new Date(ph.timestamp).toLocaleDateString('es-VE') : '—'}
                                </div>
                              </div>
                            ))}
                          </div>

                          {/* Issues */}
                          <div className="mt-2 flex flex-wrap gap-1">
                            {it.issues.map((iss) => (
                              <Badge key={iss} className="bg-amber-100 text-amber-800 border border-amber-300 text-[10px]">
                                ⚠ {iss}
                              </Badge>
                            ))}
                          </div>
                        </Card>
                      ))}
                    </div>
                  )}
                </>
              )}
            </TabsContent>
          </Tabs>
        </div>
      </main>
    </div>
  );
};

export default SalesReports;
