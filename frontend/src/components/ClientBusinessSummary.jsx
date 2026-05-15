/**
 * ClientBusinessSummary — Vista 360 del cliente con resumen de cotizaciones
 * activas y proyectos. Se muestra dentro del modal de edición de cliente.
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../utils/api';
import { FileText, Briefcase, ExternalLink, Loader2 } from 'lucide-react';

const fmtUSD = (n) => `$${(Number(n) || 0).toLocaleString('es-VE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const STATUS_COLORS = {
  'Borrador': 'bg-slate-100 text-slate-700',
  'Enviada': 'bg-blue-100 text-blue-700',
  'Emitida': 'bg-blue-100 text-blue-700',
  'Aprobada': 'bg-green-100 text-green-700',
  'Reparada': 'bg-cyan-100 text-cyan-700',
  'Configurada': 'bg-indigo-100 text-indigo-700',
  'Facturada': 'bg-purple-100 text-purple-700',
  'Pagada': 'bg-emerald-100 text-emerald-700',
  'Entregada': 'bg-teal-100 text-teal-700',
  'Enviada a Imple': 'bg-amber-100 text-amber-700',
  'En Implementación': 'bg-amber-100 text-amber-700',
  'Completada': 'bg-emerald-100 text-emerald-700',
};

const TYPE_LABELS = {
  VPOS: 'VPOS', MPOS: 'MPOS', FAST_TRACK: 'MPOS Imple+POS',
  GATEWAY: 'Payment Gateway', LINK_PAGO: 'Link de Pago',
};

const isActiveQuote = (q) => {
  const status = (q.quote_status || '').toLowerCase();
  if (q.archived) return false;
  return !['entregada', 'completada'].includes(status);
};

export function ClientBusinessSummary({ clientId }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [quotes, setQuotes] = useState([]);
  const [projects, setProjects] = useState([]);

  useEffect(() => {
    if (!clientId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const [qRes, pRes] = await Promise.all([
          api.get(`/quotes`, { params: { client_id: clientId } }).catch(() => ({ data: [] })),
          api.get(`/projects`, { params: { client_id: clientId } }).catch(() => ({ data: [] })),
        ]);
        if (cancelled) return;
        const qList = Array.isArray(qRes.data) ? qRes.data : (qRes.data?.quotes || qRes.data?.items || []);
        const pList = Array.isArray(pRes.data) ? pRes.data : (pRes.data?.projects || pRes.data?.items || []);
        setQuotes(qList.filter(q => q.client_id === clientId));
        setProjects(pList.filter(p => p.client_id === clientId));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [clientId]);

  if (loading) {
    return (
      <div className="py-10 flex items-center justify-center text-slate-400">
        <Loader2 size={20} className="animate-spin mr-2" /> Cargando resumen...
      </div>
    );
  }

  const activeQuotes = quotes.filter(isActiveQuote);

  return (
    <div className="space-y-5" data-testid="client-business-summary">
      {/* Métricas rápidas */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3" data-testid="summary-kpi-active-quotes">
          <p className="text-xs text-blue-700 uppercase tracking-wide">Cotizaciones Activas</p>
          <p className="text-2xl font-bold text-blue-900">{activeQuotes.length}</p>
        </div>
        <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3" data-testid="summary-kpi-total-quotes">
          <p className="text-xs text-emerald-700 uppercase tracking-wide">Total Cotizaciones</p>
          <p className="text-2xl font-bold text-emerald-900">{quotes.length}</p>
        </div>
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3" data-testid="summary-kpi-projects">
          <p className="text-xs text-amber-700 uppercase tracking-wide">Proyectos</p>
          <p className="text-2xl font-bold text-amber-900">{projects.length}</p>
        </div>
      </div>

      {/* Cotizaciones Activas */}
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden" data-testid="summary-active-quotes-section">
        <div className="flex items-center justify-between px-4 py-2.5 bg-slate-50 border-b border-slate-200">
          <div className="flex items-center gap-2">
            <FileText size={16} className="text-blue-600" />
            <h4 className="text-sm font-semibold text-slate-800">Cotizaciones Activas ({activeQuotes.length})</h4>
          </div>
        </div>
        {activeQuotes.length === 0 ? (
          <p className="text-xs text-slate-400 text-center py-6">Sin cotizaciones activas</p>
        ) : (
          <div className="max-h-[260px] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-100 text-[10px] uppercase text-slate-600 sticky top-0">
                <tr>
                  <th className="px-3 py-1.5 text-left">Número</th>
                  <th className="px-3 py-1.5 text-left">Tipo</th>
                  <th className="px-3 py-1.5 text-right">Monto USD</th>
                  <th className="px-3 py-1.5 text-left">Estado</th>
                  <th className="px-3 py-1.5 text-center w-10"></th>
                </tr>
              </thead>
              <tbody>
                {activeQuotes.map((q) => (
                  <tr key={q.quote_id} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`summary-quote-row-${q.quote_id}`}>
                    <td className="px-3 py-1.5 font-mono text-xs">{q.quote_number}</td>
                    <td className="px-3 py-1.5 text-xs">{TYPE_LABELS[q.quote_type] || q.quote_type}</td>
                    <td className="px-3 py-1.5 text-right font-mono text-xs">{fmtUSD(q.total_usd)}</td>
                    <td className="px-3 py-1.5">
                      <span className={`px-2 py-0.5 text-[10px] rounded ${STATUS_COLORS[q.quote_status] || 'bg-slate-100 text-slate-600'}`}>
                        {q.quote_status || 'N/A'}
                      </span>
                    </td>
                    <td className="px-3 py-1.5 text-center">
                      <button
                        type="button"
                        onClick={() => window.open(`/quotes?focus=${q.quote_id}`, '_blank')}
                        className="text-blue-600 hover:text-blue-800"
                        title="Abrir cotización en nueva pestaña"
                        data-testid={`summary-quote-open-${q.quote_id}`}
                      >
                        <ExternalLink size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Proyectos */}
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden" data-testid="summary-projects-section">
        <div className="flex items-center justify-between px-4 py-2.5 bg-slate-50 border-b border-slate-200">
          <div className="flex items-center gap-2">
            <Briefcase size={16} className="text-amber-600" />
            <h4 className="text-sm font-semibold text-slate-800">Proyectos ({projects.length})</h4>
          </div>
        </div>
        {projects.length === 0 ? (
          <p className="text-xs text-slate-400 text-center py-6">Sin proyectos registrados</p>
        ) : (
          <div className="max-h-[260px] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-100 text-[10px] uppercase text-slate-600 sticky top-0">
                <tr>
                  <th className="px-3 py-1.5 text-left">Código</th>
                  <th className="px-3 py-1.5 text-left">Fase actual</th>
                  <th className="px-3 py-1.5 text-left">Implementador</th>
                  <th className="px-3 py-1.5 text-left">Estado</th>
                  <th className="px-3 py-1.5 text-center w-10"></th>
                </tr>
              </thead>
              <tbody>
                {projects.map((p) => (
                  <tr key={p.project_id} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`summary-project-row-${p.project_id}`}>
                    <td className="px-3 py-1.5 font-mono text-xs">{p.project_code || p.project_number || p.project_id?.slice(-8)}</td>
                    <td className="px-3 py-1.5 text-xs">{p.current_phase || p.phase || 'N/A'}</td>
                    <td className="px-3 py-1.5 text-xs">{p.implementer_name || p.assigned_to_name || 'Sin asignar'}</td>
                    <td className="px-3 py-1.5 text-xs">
                      <span className={`px-2 py-0.5 text-[10px] rounded ${STATUS_COLORS[p.project_status] || 'bg-slate-100 text-slate-600'}`}>
                        {p.project_status || 'N/A'}
                      </span>
                    </td>
                    <td className="px-3 py-1.5 text-center">
                      <button
                        type="button"
                        onClick={() => navigate(`/projects?focus=${p.project_id}`)}
                        className="text-blue-600 hover:text-blue-800"
                        title="Abrir proyecto"
                        data-testid={`summary-project-open-${p.project_id}`}
                      >
                        <ExternalLink size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
