import { useMemo } from 'react';
import { FileText, FilePenLine, Send, CheckCircle2, Receipt, Banknote } from 'lucide-react';
import { getEffectiveStatus, quoteMatchesFilters } from './quoteStatus';

/**
 * QuotesKpiCards — Panel de 6 KPIs dinámicos y reactivos.
 *
 * Se recalcula en tiempo real según los filtros de la grilla (período/fechas,
 * categoría, segmento, cliente). El universo base OMITE el filtro de ESTADO,
 * de modo que cada tarjeta cuenta las cotizaciones de ese estatus dentro del
 * universo filtrado y coincide EXACTAMENTE con las filas de la grilla al
 * aplicar el filtro de ese estado. Cálculo 100% client-side (instantáneo).
 *
 * Métricas: Totales · Borrador · Enviadas · Aprobadas · Facturadas · Pagadas.
 */
export function QuotesKpiCards({ quotes = [], filters = {} }) {
  const stats = useMemo(() => {
    // Universo base: RBAC-visibles, no archivadas, filtradas por todo EXCEPTO estado.
    const base = quotes.filter(
      (q) => !q.archived && quoteMatchesFilters(q, filters, { includeStatus: false }),
    );
    const counts = { Borrador: 0, Enviada: 0, Aprobada: 0, Facturada: 0, Pagada: 0 };
    for (const q of base) {
      const s = getEffectiveStatus(q);
      if (counts[s] !== undefined) counts[s] += 1;
    }
    return {
      total: base.length,
      borrador: counts.Borrador,
      enviada: counts.Enviada,
      aprobada: counts.Aprobada,
      facturada: counts.Facturada,
      pagada: counts.Pagada,
    };
  }, [quotes, filters]);

  const cards = [
    { key: 'total', label: 'Cotizaciones Totales', value: stats.total, Icon: FileText, iconBg: 'bg-indigo-50', iconColor: 'text-indigo-600', accent: 'from-indigo-500 to-indigo-600' },
    { key: 'borrador', label: 'En Borrador', value: stats.borrador, Icon: FilePenLine, iconBg: 'bg-slate-100', iconColor: 'text-slate-600', accent: 'from-slate-400 to-slate-500' },
    { key: 'enviada', label: 'Enviadas', value: stats.enviada, Icon: Send, iconBg: 'bg-blue-50', iconColor: 'text-blue-600', accent: 'from-blue-500 to-blue-600' },
    { key: 'aprobada', label: 'Aprobadas', value: stats.aprobada, Icon: CheckCircle2, iconBg: 'bg-emerald-50', iconColor: 'text-emerald-600', accent: 'from-emerald-500 to-emerald-600' },
    { key: 'facturada', label: 'Facturadas', value: stats.facturada, Icon: Receipt, iconBg: 'bg-purple-50', iconColor: 'text-purple-600', accent: 'from-purple-500 to-purple-600' },
    { key: 'pagada', label: 'Pagadas', value: stats.pagada, Icon: Banknote, iconBg: 'bg-teal-50', iconColor: 'text-teal-600', accent: 'from-teal-500 to-emerald-600' },
  ];

  return (
    <div
      className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6"
      data-testid="quotes-kpi-cards"
    >
      {cards.map((c) => (
        <div
          key={c.key}
          className="relative bg-white border border-slate-200 rounded-xl p-4 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 overflow-hidden"
          data-testid={`quotes-kpi-${c.key}`}
        >
          <div className={`absolute top-0 left-0 bottom-0 w-1 bg-gradient-to-b ${c.accent}`} />
          <div className="flex items-start justify-between mb-3">
            <div className={`w-9 h-9 rounded-lg ${c.iconBg} ${c.iconColor} flex items-center justify-center`}>
              <c.Icon size={18} />
            </div>
          </div>
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1 leading-tight">
            {c.label}
          </p>
          <p
            className="text-2xl font-bold text-slate-900 font-manrope tracking-tight"
            data-testid={`quotes-kpi-${c.key}-value`}
          >
            {Number(c.value).toLocaleString('es-VE')}
          </p>
        </div>
      ))}
    </div>
  );
}
