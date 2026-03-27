import React, { memo } from 'react';
import { Check, AlertTriangle } from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from '../ui/popover';

// Flow definitions per category
const FLOWS = {
  repair: [
    { key: 'Enviada', label: 'Enviada', ts: 'sent_to_client_at' },
    { key: 'Aprobada', label: 'Aprobada', ts: 'approved_at' },
    { key: 'Reparada', label: 'Reparada', ts: 'repaired_at' },
    { key: 'Facturada', label: 'Factura', ts: 'invoiced_at' },
    { key: 'Pagada', label: 'Pagada', ts: 'paid_at' },
    { key: 'Entregada', label: 'Entregada', ts: 'delivered_at' },
  ],
  fast_track: [
    { key: 'Enviada', label: 'Enviada', ts: 'sent_to_client_at' },
    { key: 'Aprobada', label: 'Aprobada', ts: 'approved_at' },
    { key: 'Configurada', label: 'Config.', ts: 'configured_at' },
    { key: 'Facturada', label: 'Factura', ts: 'invoiced_at' },
    { key: 'Pagada', label: 'Pagada', ts: 'paid_at' },
    { key: 'Entregada', label: 'Entregada', ts: 'delivered_at' },
  ],
  equipment: [
    { key: 'Enviada', label: 'Enviada', ts: 'sent_to_client_at' },
    { key: 'Aprobada', label: 'Aprobada', ts: 'approved_at' },
    { key: 'Facturada', label: 'Factura', ts: 'invoiced_at' },
    { key: 'Pagada', label: 'Pagada', ts: 'paid_at' },
    { key: 'Entregada', label: 'Entregada', ts: 'delivered_at' },
  ],
  implementation: [
    { key: 'Enviada', label: 'Enviada', ts: 'sent_to_client_at' },
    { key: 'Aprobada', label: 'Aprobada', ts: 'approved_at' },
    { key: 'Facturada', label: 'Factura', ts: 'invoiced_at' },
    { key: 'Pagada', label: 'Pagada', ts: 'paid_at' },
    { key: 'Enviada a Imple', label: 'Imple.', ts: 'sent_to_implementation_at' },
  ],
};

const ACTION_NAMES = {
  approve: 'Aprobación', invoice: 'Factura / Proforma',
  collect: 'Cobranza', deliver: 'Entrega',
  'send-to-implementation': 'Env. a Imple.',
  'repair-complete': 'Reparación', 'repair-deliver': 'Entrega Rep.',
  configure: 'Configuración',
};

function getStepStates(steps, quote) {
  const currentStatus = quote.quote_status || 'Borrador';
  const isIrregular = quote.is_irregular;
  const statusOrder = steps.map(s => s.key);
  const currentIdx = statusOrder.indexOf(currentStatus);
  const isAtFinalStep = currentIdx === steps.length - 1;

  return steps.map((step, idx) => {
    const hasTimestamp = !!quote[step.ts];
    const isPastCurrent = currentIdx >= 0 && idx <= currentIdx;
    const isCurrent = currentIdx >= 0 && idx === currentIdx;

    // Final step reached: show as completed (solid green + check)
    if (isCurrent && isAtFinalStep) return 'completed';
    if (isCurrent) return 'current';
    if (isPastCurrent && hasTimestamp) return 'completed';
    if (isPastCurrent && !hasTimestamp && isIrregular) return 'bypassed';
    if (isPastCurrent) return 'completed';
    return 'pending';
  });
}

function getBypassedException(step, exceptions) {
  if (!exceptions?.length) return null;
  // Map step keys to the action that would skip them
  const stepToSkipActions = {
    'Enviada': ['approve'],
    'Aprobada': ['invoice', 'collect', 'repair-complete', 'configure'],
    'Reparada': ['invoice', 'collect', 'repair-deliver'],
    'Configurada': ['invoice', 'collect'],
    'Facturada': ['collect', 'deliver', 'repair-deliver', 'send-to-implementation'],
    'Pagada': ['deliver', 'repair-deliver', 'send-to-implementation'],
    'Entregada': ['send-to-implementation'],
  };
  const relevantActions = stepToSkipActions[step.key] || [];
  return exceptions.find(e => relevantActions.includes(e.action));
}

const QuoteStatusStepper = memo(function QuoteStatusStepper({ quote, onOpenBitacoraFlujo }) {
  const cat = quote.quote_category || 'implementation';
  const steps = FLOWS[cat] || FLOWS.implementation;
  const states = getStepStates(steps, quote);
  const exceptions = quote.irregular_exceptions || [];

  return (
    <div className="flex items-center gap-0" data-testid="quote-status-stepper">
      {steps.map((step, idx) => {
        const state = states[idx];
        const exc = state === 'bypassed' ? getBypassedException(step, exceptions) : null;

        // Colors per state
        const circleClass =
          state === 'completed'
            ? 'bg-emerald-500 text-white'
            : state === 'current'
              ? 'bg-emerald-100 border-2 border-emerald-500 text-emerald-700'
              : state === 'bypassed'
                ? 'bg-red-100 border-2 border-red-400 text-red-600'
                : 'bg-slate-100 border border-slate-300 text-slate-400';
        const lineClass =
          state === 'pending'
            ? 'bg-slate-200'
            : state === 'bypassed'
              ? 'bg-red-300'
              : 'bg-emerald-400';
        const labelClass =
          state === 'completed'
            ? 'text-emerald-600 font-semibold'
            : state === 'current'
              ? 'text-emerald-700 font-bold'
              : state === 'bypassed'
                ? 'text-red-500 font-semibold'
                : 'text-slate-400';

        const circleContent =
          state === 'completed'
            ? <Check size={10} strokeWidth={3} />
            : state === 'bypassed'
              ? <AlertTriangle size={9} strokeWidth={2.5} />
              : (idx + 1);

        const stepNode = (
          <div className="flex items-center" key={step.key}>
            {idx > 0 && <div className={`w-3 h-px mx-0.5 ${lineClass}`} />}
            <div className="flex flex-col items-center" title={step.label}>
              <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[8px] font-bold transition-all ${circleClass}`}>
                {circleContent}
              </div>
              <span className={`text-[7px] mt-0.5 leading-none whitespace-nowrap ${labelClass}`}>
                {step.label}
              </span>
            </div>
          </div>
        );

        // Bypassed step: wrap in popover with justification
        if (state === 'bypassed' && exc) {
          return (
            <Popover key={step.key}>
              <PopoverTrigger asChild>
                <button className="flex items-center cursor-pointer outline-none" data-testid={`bypassed-step-${step.key}`}>
                  {idx > 0 && <div className={`w-3 h-px mx-0.5 ${lineClass}`} />}
                  <div className="flex flex-col items-center" title={`${step.label} (Saltada)`}>
                    <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[8px] font-bold transition-all ${circleClass} ring-1 ring-red-300`}>
                      {circleContent}
                    </div>
                    <span className={`text-[7px] mt-0.5 leading-none whitespace-nowrap ${labelClass}`}>
                      {step.label}
                    </span>
                  </div>
                </button>
              </PopoverTrigger>
              <PopoverContent className="w-64 p-0" align="start">
                <div className="bg-red-50 border-b border-red-200 px-3 py-2">
                  <p className="text-xs font-bold text-red-700">Fase Saltada: {step.label}</p>
                </div>
                <div className="p-3 space-y-1.5">
                  <p className="text-[11px] text-slate-600"><span className="font-semibold">Acción:</span> {ACTION_NAMES[exc.action] || exc.action}</p>
                  <p className="text-[11px] text-slate-600"><span className="font-semibold">Justificación:</span> {exc.reason || 'Sin detalle'}</p>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-slate-400">{exc.created_at?.slice(0, 10)}</span>
                    {exc.regularization_date && (
                      <span className="text-[10px] text-red-500 font-medium">Tope: {exc.regularization_date}</span>
                    )}
                  </div>
                </div>
                {onOpenBitacoraFlujo && (
                  <div className="border-t border-red-200 px-3 py-1.5">
                    <button
                      onClick={() => onOpenBitacoraFlujo(quote.quote_id, quote.quote_number)}
                      className="text-[10px] text-red-600 hover:text-red-800 font-medium w-full text-center"
                    >
                      Ver historial completo
                    </button>
                  </div>
                )}
              </PopoverContent>
            </Popover>
          );
        }

        return stepNode;
      })}
    </div>
  );
});

export default QuoteStatusStepper;
