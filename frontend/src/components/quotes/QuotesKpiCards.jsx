import { useMemo } from 'react';
import { FileText, CheckCircle2, Clock, DollarSign } from 'lucide-react';

/**
 * QuotesKpiCards — Iter49.
 *
 * Calcula 4 indicadores rápidos a partir del array de cotizaciones visibles
 * para el usuario actual. NO requiere endpoint adicional: el cálculo es 100%
 * client-side a partir de los campos ya disponibles.
 *
 * - Total Cotizaciones: # de cotizaciones filtradas por RBAC.
 * - Aprobadas: cotizaciones con `status_approved == true` o estados terminales
 *   ('paid', 'delivered', 'implemented', 'completed').
 * - Pendientes: lo que no es aprobado ni archivado.
 * - Inversión USD: suma del campo `total_usd` (o `total_inversion`) de las
 *   cotizaciones visibles. Formatea en USD.
 */
/**
 * Cotizaciones consideradas "aprobadas": tienen `approved_at` con timestamp
 * (Quote pasó por el paso de aprobación) o `quote_status` en uno de los
 * estados terminales del flujo (Aprobada → Pagada → Implementada).
 */
const APPROVED_STATUSES = new Set([
  'aprobada',
  'facturada',
  'pagada',
  'entregada',
  'implementada',
  'completada',
  'finalizada',
]);

function formatUSD(amount) {
  const n = Number(amount) || 0;
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(1)}K`;
  return `$${n.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}

function isApproved(q) {
  if (q?.approved_at) return true;
  if (q?.paid_at) return true;
  if (q?.sent_to_implementation_at) return true;
  const s = (q?.quote_status || '').toString().toLowerCase();
  return APPROVED_STATUSES.has(s);
}

export function QuotesKpiCards({ quotes = [] }) {
  const stats = useMemo(() => {
    const active = quotes.filter((q) => !q.archived);
    const total = active.length;
    const approved = active.filter(isApproved).length;
    const pending = total - approved;
    const investment = active.reduce((acc, q) => {
      const v = Number(q.total_usd ?? q.total_inversion ?? q.inversion_inicial ?? q.total ?? 0) || 0;
      return acc + v;
    }, 0);
    return { total, approved, pending, investment };
  }, [quotes]);

  const cards = [
    {
      key: 'total',
      label: 'Total Cotizaciones',
      value: stats.total.toLocaleString('es-VE'),
      Icon: FileText,
      iconBg: 'bg-indigo-50',
      iconColor: 'text-indigo-600',
      accent: 'from-indigo-500 to-indigo-600',
    },
    {
      key: 'approved',
      label: 'Aprobadas',
      value: stats.approved.toLocaleString('es-VE'),
      Icon: CheckCircle2,
      iconBg: 'bg-emerald-50',
      iconColor: 'text-emerald-600',
      accent: 'from-emerald-500 to-emerald-600',
    },
    {
      key: 'pending',
      label: 'Pendientes',
      value: stats.pending.toLocaleString('es-VE'),
      Icon: Clock,
      iconBg: 'bg-amber-50',
      iconColor: 'text-amber-600',
      accent: 'from-amber-500 to-orange-500',
    },
    {
      key: 'investment',
      label: 'Inversión Total',
      value: formatUSD(stats.investment),
      sub: 'USD',
      Icon: DollarSign,
      iconBg: 'bg-fuchsia-50',
      iconColor: 'text-fuchsia-600',
      accent: 'from-fuchsia-500 to-pink-500',
    },
  ];

  return (
    <div
      className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6"
      data-testid="quotes-kpi-cards"
    >
      {cards.map((c) => (
        <div
          key={c.key}
          className="relative bg-white border border-slate-200 rounded-xl p-4 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 overflow-hidden"
          data-testid={`quotes-kpi-${c.key}`}
        >
          {/* Acento lateral con gradiente */}
          <div className={`absolute top-0 left-0 bottom-0 w-1 bg-gradient-to-b ${c.accent}`} />
          <div className="flex items-start justify-between mb-3">
            <div className={`w-9 h-9 rounded-lg ${c.iconBg} ${c.iconColor} flex items-center justify-center`}>
              <c.Icon size={18} />
            </div>
          </div>
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
            {c.label}
          </p>
          <div className="flex items-baseline gap-1.5">
            <p className="text-2xl font-bold text-slate-900 font-manrope tracking-tight">
              {c.value}
            </p>
            {c.sub && (
              <span className="text-[11px] font-semibold text-slate-400 uppercase">{c.sub}</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
