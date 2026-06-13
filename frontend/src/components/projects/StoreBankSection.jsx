import { useState, useEffect, useRef } from 'react';
import { Building2 } from 'lucide-react';
import { MiniPie } from './MiniPie';

// Input numérico con estado LOCAL: el usuario escribe sin latencia y el valor se
// PERSISTE solo al salir del campo (blur) o al presionar Enter. Evita disparar una
// petición + recálculo por cada tecla (clave para la "transcripción" en Multi-RIF).
const QtyInput = ({ value, onCommit, className, testid, title }) => {
  const [val, setVal] = useState(String(value ?? 0));
  const focusedRef = useRef(false);
  // Sincroniza con la prop cuando cambia externamente y el input no está enfocado.
  useEffect(() => { if (!focusedRef.current) setVal(String(value ?? 0)); }, [value]);
  const commit = () => {
    const n = parseInt(val, 10) || 0;
    if (n !== (value ?? 0)) onCommit(n);
    else setVal(String(value ?? 0));
  };
  return (
    <input
      type="number" min={0} value={val}
      onFocus={() => { focusedRef.current = true; }}
      onChange={e => setVal(e.target.value)}
      onBlur={() => { focusedRef.current = false; commit(); }}
      onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); e.currentTarget.blur(); } }}
      className={className} title={title} data-testid={testid}
    />
  );
};

// ==================== STORE: Bank Section ====================
export const StoreBankSection = ({ bankName, products, matrixData, storeId, onUpdateStoreQuantity, onUpdateStoreCascade, onFillStorePhase, phases, readOnly, expectedQty }) => {
  return (
    <>
      <tr className="bg-blue-50 border-t-2 border-blue-200">
        <td className="px-4 py-2 text-sm font-bold text-blue-900" colSpan={phases.length + 2}><Building2 size={14} className="inline mr-2 text-blue-600" />{bankName}</td>
      </tr>
      {products.map(productName => {
        const pd = matrixData[productName] || {};
        return (
          <tr key={productName} className="border-t border-slate-100 hover:bg-slate-50">
            <td className="px-6 py-2.5 text-sm text-slate-700">
              <span className="truncate">{productName}</span>
            </td>
            {phases.map((phase) => {
              const d = pd[phase] || {};
              const expected = d.expected || expectedQty || 0;
              const processed = d.processed || 0;
              const pct = expected > 0 ? Math.min(Math.round((processed / expected) * 100), 100) : 0;
              const isComplete = processed >= expected && expected > 0;
              return (
                <td key={phase} className="px-2 py-2 text-center border-l border-slate-100">
                  <div className="flex flex-col items-center gap-1">
                    <div className="flex items-center gap-1">
                      <MiniPie percent={pct} size={26} />
                      {!readOnly && !isComplete && expected > 0 && onFillStorePhase && (
                        <button onClick={() => onFillStorePhase(storeId, bankName, productName, phase, expected)}
                          className="w-5 h-5 rounded bg-slate-100 text-slate-500 hover:bg-emerald-500 hover:text-white text-[9px] font-black flex items-center justify-center shrink-0 transition-colors"
                          title={`Completar "${phase}" (procesado = esperado)`}
                          data-testid={`store-fill-phase-${storeId}-${bankName}-${productName}-${phase}`}>T</button>
                      )}
                    </div>
                    <div className="flex items-center gap-0.5">
                      {readOnly ? (
                        <span className="text-[10px] font-mono text-slate-600">{processed}/{expected}</span>
                      ) : (
                        <>
                          <QtyInput
                            value={processed}
                            onCommit={(n) => onUpdateStoreQuantity(storeId, bankName, productName, phase, expected, n)}
                            className="w-8 h-5 text-[10px] text-center border border-slate-200 rounded font-mono"
                            testid={`store-qty-proc-${storeId}-${bankName}-${productName}-${phase}`} />
                          <span className="text-[10px] text-slate-400">/</span>
                          <QtyInput
                            value={expected}
                            onCommit={(newExp) => {
                              if (onUpdateStoreCascade) {
                                onUpdateStoreCascade(storeId, bankName, productName, newExp, phase, processed);
                              } else {
                                onUpdateStoreQuantity(storeId, bankName, productName, phase, newExp, processed);
                              }
                            }}
                            className="w-8 h-5 text-[10px] text-center border rounded font-mono border-blue-300 bg-blue-50"
                            title="Cantidad de Terminales (se propaga a todas las fases)"
                            testid={`store-qty-exp-${storeId}-${bankName}-${productName}-${phase}`} />
                        </>
                      )}
                    </div>
                  </div>
                </td>);
            })}
            <td className="px-3 py-2.5 text-center border-l border-slate-100">
              {(() => {
                const completedPhases = phases.filter(p => {
                  const d = pd[p] || {};
                  return (d.processed || 0) >= (d.expected || 0) && (d.expected || 0) > 0;
                }).length;
                return <span className="text-xs font-bold text-slate-500">{completedPhases}/{phases.length}</span>;
              })()}
            </td>
          </tr>);
      })}
    </>
  );
};
