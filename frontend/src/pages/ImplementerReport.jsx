import { useState, useEffect } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { UsersRound, Filter, Download, RefreshCw, CheckCircle2, FileText, Rocket, Mail, Package } from 'lucide-react';
import api from '../utils/api';

const PROJECT_METRICS = [
  { key: 'asignados', label: 'Proyectos Asignados' },
  { key: 'con_ticket', label: 'Proyectos con Ticket Asignado' },
  { key: 'en_gestion', label: 'Proyectos en Gestión' },
  { key: 'culminados', label: 'Proyectos Culminados' },
  { key: 'cajas_culminados', label: 'Cajas en Culminados' },
  { key: 'parcial', label: 'Implementación Parcial' },
  { key: 'suspendidos', label: 'Proyectos Suspendidos' },
];
const PVV_METRICS = [
  { key: 'pvv_recibidos', label: 'PVV Recibidos' },
  { key: 'pvv_configurados', label: 'PVV Configurados' },
  { key: 'pvv_probados', label: 'PVV Probados' },
  { key: 'pvv_produccion', label: 'PVV en Producción' },
];
const NOTIF_METRICS = [
  { key: 'notif_clientes', label: 'Notificaciones a Clientes' },
  { key: 'notif_bancos', label: 'Notificaciones a Bancos' },
];

const fmtDate = (s) => {
  try { return new Date(s).toLocaleDateString('es-VE', { day: '2-digit', month: '2-digit', year: 'numeric' }); }
  catch { return s; }
};

const MetricGroup = ({ title, icon: Icon, metrics, data, accent }) => (
  <div className="mb-4">
    <div className={`flex items-center gap-2 mb-2 text-sm font-semibold ${accent}`}>
      <Icon size={16} /> {title}
    </div>
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {metrics.map(m => (
        <div key={m.key} className="rounded-lg border border-slate-200 bg-white px-3 py-2.5" data-testid={`metric-${m.key}`}>
          <p className="text-[11px] text-slate-500 leading-tight">{m.label}</p>
          <p className="text-xl font-bold text-slate-900 mt-0.5">{data?.[m.key] ?? 0}</p>
        </div>
      ))}
    </div>
  </div>
);

export default function ImplementerReport() {
  const today = new Date().toISOString().slice(0, 10);
  const firstOfMonth = today.slice(0, 8) + '01';
  const [dateFrom, setDateFrom] = useState(firstOfMonth);
  const [dateTo, setDateTo] = useState(today);
  const [implementers, setImplementers] = useState([]);
  const [mode, setMode] = useState('all'); // all | single | multi
  const [selectedIds, setSelectedIds] = useState([]);
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(null);

  useEffect(() => {
    api.get('/reports/implementers/list')
      .then(r => setImplementers(r.data?.implementers || []))
      .catch(() => toast.error('No se pudo cargar la lista de implementadores'));
  }, []);

  const toggleId = (id) => setSelectedIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);

  const generate = async () => {
    if (!dateFrom || !dateTo) { toast.error('Selecciona el rango de fechas'); return; }
    let ids = [];
    if (mode === 'all') ids = ['all'];
    else if (mode === 'single') { if (!selectedIds[0]) { toast.error('Selecciona un implementador'); return; } ids = [selectedIds[0]]; }
    else { if (selectedIds.length === 0) { toast.error('Selecciona al menos un implementador'); return; } ids = selectedIds; }
    setLoading(true);
    try {
      const res = await api.post('/reports/implementers/generate', { date_from: dateFrom, date_to: dateTo, implementer_ids: ids });
      setReport(res.data);
      if ((res.data?.results || []).length === 0) toast.info('Sin datos para el criterio seleccionado');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error al generar el reporte');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 p-6 lg:p-8 overflow-x-hidden">
        {/* Estilos de impresión: salto de página por implementador */}
        <style>{`
          @media print {
            body { background: #fff; }
            .no-print { display: none !important; }
            .impl-report-block { page-break-before: always; break-before: page; }
            .impl-report-block:first-of-type { page-break-before: avoid; break-before: avoid; }
            .print-area { padding: 0 !important; }
          }
        `}</style>

        <div className="no-print">
          <div className="flex items-center gap-3 mb-1">
            <div className="w-11 h-11 rounded-xl bg-indigo-100 text-indigo-600 flex items-center justify-center">
              <UsersRound size={24} />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900 font-manrope">Reporte de Gestión de Implementadores</h1>
              <p className="text-sm text-slate-500">Métricas de rendimiento acotadas al periodo seleccionado</p>
            </div>
          </div>

          {/* Filtros */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 mt-5 mb-6">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-700 mb-4"><Filter size={16} /> Criterios de búsqueda</div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div>
                <Label className="text-xs">Desde *</Label>
                <Input type="date" value={dateFrom} max={dateTo} onChange={e => setDateFrom(e.target.value)} className="mt-1" data-testid="report-date-from" />
              </div>
              <div>
                <Label className="text-xs">Hasta *</Label>
                <Input type="date" value={dateTo} min={dateFrom} onChange={e => setDateTo(e.target.value)} className="mt-1" data-testid="report-date-to" />
              </div>
              <div>
                <Label className="text-xs">Alcance</Label>
                <div className="flex gap-1.5 mt-1">
                  {[['all', 'Todos'], ['single', 'Uno'], ['multi', 'Varios']].map(([v, lbl]) => (
                    <button key={v} type="button" onClick={() => { setMode(v); setSelectedIds([]); }}
                      className={`flex-1 px-2 py-2 rounded-lg text-xs font-medium border transition-colors ${mode === v ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-slate-600 border-slate-200 hover:border-indigo-300'}`}
                      data-testid={`report-mode-${v}`}>{lbl}</button>
                  ))}
                </div>
              </div>
            </div>

            {mode === 'single' && (
              <select className="w-full md:w-1/2 border border-slate-200 rounded-lg px-3 py-2 text-sm" value={selectedIds[0] || ''}
                onChange={e => setSelectedIds(e.target.value ? [e.target.value] : [])} data-testid="report-single-select">
                <option value="">Seleccione un implementador...</option>
                {implementers.map(i => <option key={i.user_id} value={i.user_id}>{i.name}</option>)}
              </select>
            )}
            {mode === 'multi' && (
              <div className="max-h-44 overflow-y-auto border rounded-lg p-2 grid grid-cols-1 md:grid-cols-2 gap-1" data-testid="report-multi-list">
                {implementers.map(i => (
                  <label key={i.user_id} className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-slate-50 cursor-pointer text-sm">
                    <input type="checkbox" checked={selectedIds.includes(i.user_id)} onChange={() => toggleId(i.user_id)} data-testid={`report-check-${i.user_id}`} />
                    {i.name}
                  </label>
                ))}
              </div>
            )}

            <div className="flex gap-2 mt-4">
              <Button onClick={generate} disabled={loading} className="bg-indigo-600 hover:bg-indigo-700" data-testid="report-generate-btn">
                {loading ? <RefreshCw size={16} className="mr-1.5 animate-spin" /> : <Filter size={16} className="mr-1.5" />}
                {loading ? 'Generando...' : 'Generar Reporte'}
              </Button>
              {report && (
                <Button variant="outline" onClick={() => window.print()} data-testid="report-pdf-btn">
                  <Download size={16} className="mr-1.5" /> Descargar PDF
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Resultados */}
        {report && (
          <div className="print-area">
            {report.results.length === 0 ? (
              <div className="text-center text-slate-400 py-12 no-print">Sin resultados para el periodo.</div>
            ) : report.results.map((r) => (
              <div key={r.implementer_id} className="impl-report-block bg-white rounded-xl border border-slate-200 p-6 mb-6" data-testid={`impl-block-${r.implementer_id}`}>
                <div className="border-b border-slate-200 pb-3 mb-4">
                  <h2 className="text-xl font-bold text-slate-900" data-testid="impl-name">{r.implementer_name}</h2>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Periodo: Desde {fmtDate(report.date_from)} Hasta {fmtDate(report.date_to)}
                    {'  ·  '}Generado: {new Date(report.generated_at).toLocaleString('es-VE')}
                  </p>
                </div>
                <MetricGroup title="A. Gestión de Proyectos de Integración" icon={FileText} metrics={PROJECT_METRICS} data={r.metrics} accent="text-indigo-700" />
                <MetricGroup title="B. Puntos de Venta Virtuales (PVV)" icon={Rocket} metrics={PVV_METRICS} data={r.metrics} accent="text-emerald-700" />
                <MetricGroup title="C. Notificaciones y Comunicaciones" icon={Mail} metrics={NOTIF_METRICS} data={r.metrics} accent="text-amber-700" />
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
