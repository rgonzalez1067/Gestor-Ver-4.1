// Badge reutilizable para identificar el tipo de negocio del proyecto/cotización.
// Lee el `quote_type` heredado de la cotización origen y lo mapea a un color
// consistente entre todas las vistas (Grilla de Proyectos, Histórico, Reporte
// de Irregularidades, Detalle).
import { CreditCard, Smartphone, Globe, Link as LinkIcon } from 'lucide-react';

const TYPE_CONFIG = {
  VPOS: {
    label: 'VPOS',
    icon: CreditCard,
    className: 'bg-blue-100 text-blue-800 border-blue-200',
  },
  MPOS: {
    label: 'MPOS',
    icon: Smartphone,
    className: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  },
  GATEWAY: {
    label: 'Payment Gateway',
    icon: Globe,
    className: 'bg-purple-100 text-purple-800 border-purple-200',
  },
  LINK: {
    label: 'Link de Pago',
    icon: LinkIcon,
    className: 'bg-slate-100 text-slate-700 border-slate-200',
  },
};

// Normaliza variantes del backend a las claves canónicas del catálogo.
const TYPE_ALIASES = { LINK_PAGO: 'LINK', LINK: 'LINK', FAST_TRACK: 'MPOS' };

const FALLBACK = {
  label: '—',
  icon: null,
  className: 'bg-slate-50 text-slate-500 border-slate-200',
};

/**
 * Badge para tipo de proyecto/cotización.
 * @param {string} quoteType  Uno de: 'VPOS' | 'MPOS' | 'GATEWAY' | 'LINK'
 * @param {string} size       'sm' (default) | 'xs'
 * @param {boolean} compact   true → solo texto, sin icono
 */
export function ProjectTypeBadge({ quoteType, size = 'sm', compact = false }) {
  const key = (quoteType || '').toUpperCase();
  const cfg = TYPE_CONFIG[TYPE_ALIASES[key] || key] || FALLBACK;
  const Icon = cfg.icon;
  const sizeClasses = size === 'xs'
    ? 'px-1.5 py-0.5 text-[10px]'
    : 'px-2 py-0.5 text-xs';
  return (
    <span
      className={`inline-flex items-center gap-1 ${sizeClasses} font-medium rounded-md border ${cfg.className}`}
      data-testid={`project-type-badge-${(quoteType || 'unknown').toLowerCase()}`}
    >
      {Icon && !compact && <Icon size={size === 'xs' ? 10 : 11} />}
      {cfg.label}
    </span>
  );
}

export default ProjectTypeBadge;
