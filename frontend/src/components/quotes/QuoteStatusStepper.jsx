import React, { memo } from 'react';
import { Check, AlertTriangle } from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from '../ui/popover';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip';

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
    { key: 'Preasignada', label: 'Preasign.', ts: 'preassigned_at' },
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

    // Regla principal: si el step tiene su timestamp, la acción ya se ejecutó.
    // Siempre se marca como completed (check verde sólido), aunque sea el
    // step "current" del quote_status. Esto evita el caso donde la cotización
    // sigue en estado "Aprobada" pero ya pasó por Preasignación: visualmente
    // ambos pasos quedan como completed.
    if (hasTimestamp) return 'completed';

    // Final step alcanzado sin timestamp (caso borde): completed
    if (isCurrent && isAtFinalStep) return 'completed';
    // Step actual sin timestamp todavía: en progreso
    if (isCurrent) return 'current';
    // Step pasado sin timestamp: bypassed (si la cotización es irregular) o completed legacy
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

function formatStepDate(isoDate) {
  if (!isoDate) return null;
  try {
    const d = new Date(isoDate);
    return d.toLocaleDateString('es-VE', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return null; }
}

const QuoteStatusStepper = memo(function QuoteStatusStepper({ quote, onOpenBitacoraFlujo, customActions = [] }) {
  const cat = quote.quote_category || 'implementation';
  const baseSteps = FLOWS[cat] || FLOWS.implementation;
  const exec = quote.custom_actions_executed || {};

  // Inyectar custom actions del catálogo como pasos extra.
  // - Si la custom action tiene `position_after`, intentar insertarla justo después de ese step.
  // - Si no tiene `position_after` (o no encontramos el ancla), va al final.
  // Cada custom action se trata como un paso virtual con timestamp en `exec[action_id]`.
  const steps = (() => {
    const result = [...baseSteps];
    const noAnchor = [];
    for (const ca of customActions) {
      const stepObj = {
        key: `custom:${ca.action_id}`,
        label: (ca.label || ca.action_id).slice(0, 12),
        ts: null,                              // timestamp se resuelve via exec map
        custom_action_id: ca.action_id,
        custom: true,
      };
      const anchor = ca.position_after;
      if (anchor) {
        const idx = result.findIndex((s) => {
          const map = {
            send_to_client: 'Enviada', approve: 'Aprobada', invoice: 'Facturada',
            collect: 'Pagada', deliver: 'Entregada', configure: 'Configurada',
            repair_complete: 'Reparada', send_to_implementation: 'Enviada a Imple',
          };
          return s.key === (map[anchor] || anchor);
        });
        if (idx >= 0) {
          result.splice(idx + 1, 0, stepObj);
          continue;
        }
      }
      noAnchor.push(stepObj);
    }
    result.push(...noAnchor);
    return result;
  })();

  // Helper para resolver timestamp incluso de custom steps
  const getStepTimestamp = (step) => step.custom ? exec[step.custom_action_id] : quote[step.ts];
  const states = steps.map((step, idx) => {
    if (getStepTimestamp(step)) return 'completed';
    // Para steps base usamos la lógica existente; para custom sin timestamp, pending
    if (step.custom) return 'pending';
    // Reusar getStepStates solo sobre los baseSteps para el resto
    return null;
  });
  // Calcular estados base con la función original sobre baseSteps y mapear por key
  const baseStates = getStepStates(baseSteps, quote);
  const baseStateByKey = {};
  baseSteps.forEach((s, i) => { baseStateByKey[s.key] = baseStates[i]; });
  for (let i = 0; i < steps.length; i++) {
    if (states[i] === null) states[i] = baseStateByKey[steps[i].key] || 'pending';
  }

  const exceptions = quote.irregular_exceptions || [];

  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex items-center gap-0" data-testid="quote-status-stepper">
        {steps.map((step, idx) => {
          const state = states[idx];
          const exc = state === 'bypassed' ? getBypassedException(step, exceptions) : null;
          const tsValue = getStepTimestamp(step);
          const dateStr = formatStepDate(tsValue);

          // Colors per state
          const circleClass =
            state === 'completed'
              ? (step.custom ? 'bg-violet-500 text-white' : 'bg-emerald-500 text-white')
              : state === 'current'
                ? 'bg-emerald-100 border-2 border-emerald-500 text-emerald-700'
                : state === 'bypassed'
                  ? 'bg-red-100 border-2 border-red-400 text-red-600'
                  : (step.custom ? 'bg-violet-50 border border-violet-300 text-violet-400' : 'bg-slate-100 border border-slate-300 text-slate-400');
          const lineClass =
            state === 'pending'
              ? 'bg-slate-200'
              : state === 'bypassed'
                ? 'bg-red-300'
                : (step.custom ? 'bg-violet-400' : 'bg-emerald-400');
          const labelClass =
            state === 'completed'
              ? (step.custom ? 'text-violet-600 font-semibold' : 'text-emerald-600 font-semibold')
              : state === 'current'
                ? 'text-emerald-700 font-bold'
                : state === 'bypassed'
                  ? 'text-red-500 font-semibold'
                  : (step.custom ? 'text-violet-400' : 'text-slate-400');

          const circleContent =
            state === 'completed'
              ? <Check size={10} strokeWidth={3} />
              : state === 'bypassed'
                ? <AlertTriangle size={9} strokeWidth={2.5} />
                : (idx + 1);

          const stepInner = (
            <>
              {idx > 0 && <div className={`w-3 h-px mx-0.5 ${lineClass}`} />}
              <div className="flex flex-col items-center">
                <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[8px] font-bold transition-all ${circleClass}`}>
                  {circleContent}
                </div>
                <span className={`text-[7px] mt-0.5 leading-none whitespace-nowrap ${labelClass}`}>
                  {step.label}
                </span>
              </div>
            </>
          );

          // Bypassed step: popover with justification
          if (state === 'bypassed' && exc) {
            return (
              <Popover key={step.key}>
                <PopoverTrigger asChild>
                  <button className="flex items-center cursor-pointer outline-none" data-testid={`bypassed-step-${step.key}`}>
                    {idx > 0 && <div className={`w-3 h-px mx-0.5 ${lineClass}`} />}
                    <div className="flex flex-col items-center">
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

          // Completed/Current with timestamp: tooltip with date
          if ((state === 'completed' || state === 'current') && dateStr) {
            return (
              <Tooltip key={step.key}>
                <TooltipTrigger asChild>
                  <div className="flex items-center cursor-default" data-testid={`step-${step.key}`}>
                    {stepInner}
                  </div>
                </TooltipTrigger>
                <TooltipContent side="top" className="text-[10px] px-2 py-1">
                  <p className="font-semibold">{step.label}</p>
                  <p className="text-slate-300">{dateStr}</p>
                </TooltipContent>
              </Tooltip>
            );
          }

          // Pending or no date
          return (
            <div className="flex items-center" key={step.key} data-testid={`step-${step.key}`}>
              {stepInner}
            </div>
          );
        })}
      </div>
    </TooltipProvider>
  );
});

export default QuoteStatusStepper;
