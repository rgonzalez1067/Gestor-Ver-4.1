import React, { memo } from 'react';
import { Check } from 'lucide-react';

const REPAIR_STEPS = [
  { key: 'Borrador', label: 'Borrador' },
  { key: 'Enviada', label: 'Enviada' },
  { key: 'Aprobada', label: 'Aprobada' },
  { key: 'Reparada', label: 'Reparada' },
  { key: 'Facturada', label: 'Factura' },
  { key: 'Pagada', label: 'Pagada' },
  { key: 'Entregada', label: 'Entregada' },
];

const STATUS_ORDER = REPAIR_STEPS.map(s => s.key);

function getStepState(stepKey, currentStatus) {
  const currentIdx = STATUS_ORDER.indexOf(currentStatus);
  const stepIdx = STATUS_ORDER.indexOf(stepKey);
  if (currentIdx < 0 || stepIdx < 0) return 'pending';
  if (stepIdx < currentIdx) return 'completed';
  if (stepIdx === currentIdx) return 'current';
  return 'pending';
}

const RepairStatusPipeline = memo(function RepairStatusPipeline({ currentStatus }) {
  return (
    <div className="flex items-center gap-0.5" data-testid="repair-status-pipeline">
      {REPAIR_STEPS.map((step, idx) => {
        const state = getStepState(step.key, currentStatus);
        return (
          <div key={step.key} className="flex items-center">
            {idx > 0 && (
              <div className={`w-3 h-px mx-0.5 ${
                state === 'pending' ? 'bg-slate-200' : 'bg-cyan-400'
              }`} />
            )}
            <div className="flex flex-col items-center" title={step.label}>
              <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[8px] font-bold transition-all ${
                state === 'completed'
                  ? 'bg-cyan-500 text-white'
                  : state === 'current'
                    ? 'bg-cyan-100 border-2 border-cyan-500 text-cyan-700'
                    : 'bg-slate-100 border border-slate-300 text-slate-400'
              }`}>
                {state === 'completed' ? <Check size={10} strokeWidth={3} /> : (idx + 1)}
              </div>
              <span className={`text-[7px] mt-0.5 leading-none whitespace-nowrap ${
                state === 'completed'
                  ? 'text-cyan-600 font-semibold'
                  : state === 'current'
                    ? 'text-cyan-700 font-bold'
                    : 'text-slate-400'
              }`}>
                {step.label}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
});

export default RepairStatusPipeline;
