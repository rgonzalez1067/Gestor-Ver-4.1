import { Building2 } from 'lucide-react';
import { MiniPie } from './MiniPie';

// ==================== STORE: Bank Section ====================
export const StoreBankSection = ({ bankName, products, matrixData, storeId, onUpdateStoreQuantity, onUpdateStoreCascade, onFillAllStore, phases, readOnly, expectedQty }) => {
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
              <div className="flex items-center gap-1.5">
                {!readOnly && onFillAllStore && (
                  <button onClick={() => onFillAllStore(storeId, bankName, productName)}
                    className="w-5 h-5 rounded bg-slate-100 text-slate-500 hover:bg-emerald-500 hover:text-white text-[9px] font-black flex items-center justify-center shrink-0 transition-colors"
                    title="Completar todas las fases (T)" data-testid={`store-fill-all-${storeId}-${bankName}-${productName}`}>T</button>
                )}
                <span className="truncate">{productName}</span>
              </div>
            </td>
            {phases.map((phase, phaseIdx) => {
              const d = pd[phase] || {};
              const expected = d.expected || expectedQty || 0;
              const processed = d.processed || 0;
              const pct = expected > 0 ? Math.min(Math.round((processed / expected) * 100), 100) : 0;
              const isRecibido = phaseIdx === 0;
              return (
                <td key={phase} className="px-2 py-2 text-center border-l border-slate-100">
                  <div className="flex flex-col items-center gap-1">
                    <MiniPie percent={pct} size={26} />
                    <div className="flex items-center gap-0.5">
                      {readOnly ? (
                        <span className="text-[10px] font-mono text-slate-600">{processed}/{expected}</span>
                      ) : (
                        <>
                          <input type="number" min={0} value={processed}
                            onChange={e => onUpdateStoreQuantity(storeId, bankName, productName, phase, expected, parseInt(e.target.value) || 0)}
                            className="w-8 h-5 text-[10px] text-center border border-slate-200 rounded font-mono"
                            data-testid={`store-qty-proc-${storeId}-${bankName}-${productName}-${phase}`} />
                          <span className="text-[10px] text-slate-400">/</span>
                          <input type="number" min={0} value={expected}
                            onChange={e => {
                              const newExp = parseInt(e.target.value) || 0;
                              if (isRecibido && onUpdateStoreCascade) {
                                onUpdateStoreCascade(storeId, bankName, productName, newExp, processed);
                              } else {
                                onUpdateStoreQuantity(storeId, bankName, productName, phase, newExp, processed);
                              }
                            }}
                            className={`w-8 h-5 text-[10px] text-center border rounded font-mono ${isRecibido ? 'border-blue-300 bg-blue-50' : 'border-slate-200'}`}
                            title={isRecibido ? "Esperados (se propaga a todas las fases)" : "Esperados"}
                            data-testid={`store-qty-exp-${storeId}-${bankName}-${productName}-${phase}`} />
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
