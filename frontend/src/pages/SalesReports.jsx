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
  LineChart, Line, ComposedChart,
} from 'recharts';
import { TrendingUp, Filter, Clock, BarChart3, RefreshCw, Download } from 'lucide-react';
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

      const [fr, ar, mr] = await Promise.all([
        api.get('/reports/sales/funnel', { params: fp }),
        api.get('/reports/sales/aging', { params }),
        api.get('/reports/sales/monthly', { params: { ...params, year } }),
      ]);
      setFunnelData(fr.data);
      setAgingData(ar.data);
      setMonthlyData(mr.data);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al cargar reportes');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); /* eslint-disable-next-line */ }, [segment, category, year, dateFrom, dateTo]);

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
            <TabsList>
              <TabsTrigger value="funnel" data-testid="tab-funnel"><BarChart3 size={14} className="mr-1" /> Embudo</TabsTrigger>
              <TabsTrigger value="aging" data-testid="tab-aging"><Clock size={14} className="mr-1" /> Aging</TabsTrigger>
              <TabsTrigger value="monthly" data-testid="tab-monthly"><TrendingUp size={14} className="mr-1" /> Mensual</TabsTrigger>
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
          </Tabs>
        </div>
      </main>
    </div>
  );
};

export default SalesReports;
