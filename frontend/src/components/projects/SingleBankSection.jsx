import { Building2, Bell, CheckCircle2 } from 'lucide-react';
import { Button } from '../ui/button';
import { MiniPie } from './MiniPie';

const PHASES = ['Recibido', 'Configurado', 'Testeado', 'En Producción'];

// ==================== SINGLE BANK: Quantity-based Matrix ====================
export const SingleBankSection = ({ bankName, products, matrixData, onUpdateQuantity, onUpdateCascade, onFillPhase, bankExecutedLevels, onOpenNotif, readOnly, expectedQty, hideBankNotif }) => {
  return (
    <>
      <tr className="bg-blue-50 border-t-2 border-blue-200">
        <td className="px-4 py-2 text-sm font-bold text-blue-900" colSpan={PHASES.length + 2}><Building2 size={14} className="inline mr-2 text-blue-600" />{bankName}</td>
        {!hideBankNotif && (
          <td className="px-3 py-2 text-center">
            <Button size="sm" variant="outline" onClick={onOpenNotif}
              className={`h-7 text-xs ${bankExecutedLevels.length >= 4 ? 'border-emerald-300 text-emerald-700' : 'border-amber-300 text-amber-700'}`}
              data-testid={`notif-bank-btn-${bankName}`}
              title={bankExecutedLevels.length > 0 ? `${bankExecutedLevels.length}/4 envío(s) realizados` : 'Sin envíos aún'}>
              {bankExecutedLevels.length >= 4 ? <CheckCircle2 size={12} className="mr-1" /> : <Bell size={12} className="mr-1" />}
              Notificaciones
            </Button>
          </td>
        )}
      </tr>
      {products.map(productName => {
        const phases = matrixData[productName] || {};
        return (
          <tr key={productName} className="border-t border-slate-100 hover:bg-slate-50">
            <td className="px-4 py-2.5 text-sm text-slate-700">
              <span className="truncate">{productName}</span>
            </td>
            {PHASES.map((phase) => {
              const pd = phases[phase] || {};
              const expected = pd.expected || expectedQty || 0;
              const processed = pd.processed || 0;
              const pct = expected > 0 ? Math.min(Math.round((processed / expected) * 100), 100) : 0;
              const isComplete = processed >= expected && expected > 0;
              return (
                <td key={phase} className="px-2 py-2 text-center border-l border-slate-100">
                  <div className="flex flex-col items-center gap-1">
                    <div className="flex items-center gap-1">
                      <MiniPie percent={pct} size={28} />
                      {!readOnly && !isComplete && expected > 0 && (
                        <button onClick={() => onFillPhase(bankName, productName, phase, expected)}
                          className="w-5 h-5 rounded bg-slate-100 text-slate-500 hover:bg-emerald-500 hover:text-white text-[9px] font-black flex items-center justify-center shrink-0 transition-colors"
                          title={`Completar "${phase}" (procesado = esperado)`}
                          data-testid={`fill-phase-${bankName}-${productName}-${phase}`}>T</button>
                      )}
                    </div>
                    <div className="flex items-center gap-0.5">
                      {readOnly ? (
                        <span className="text-[10px] font-mono text-slate-600">{processed}/{expected}</span>
                      ) : (
                        <>
                          <input type="number" min={0} value={processed}
                            onChange={e => onUpdateQuantity(bankName, productName, phase, expected, parseInt(e.target.value) || 0)}
                            className="w-8 h-5 text-[10px] text-center border border-slate-200 rounded font-mono"
                            title="Procesados" data-testid={`qty-proc-${bankName}-${productName}-${phase}`} />
                          <span className="text-[10px] text-slate-400">/</span>
                          <input type="number" min={0} value={expected}
                            onChange={e => {
                              const newExp = parseInt(e.target.value) || 0;
                              onUpdateCascade(bankName, productName, newExp, phase, processed);
                            }}
                            className="w-8 h-5 text-[10px] text-center border rounded font-mono border-blue-300 bg-blue-50"
                            title="Cantidad de Terminales (se propaga a todas las fases)"
                            data-testid={`qty-exp-${bankName}-${productName}-${phase}`} />
                        </>
                      )}
                    </div>
                  </div>
                </td>);
            })}
            <td className="px-3 py-2.5 text-center border-l border-slate-100">
              {(() => {
                const completedPhases = PHASES.filter(p => {
                  const pd = phases[p] || {};
                  return (pd.processed || 0) >= (pd.expected || 0) && (pd.expected || 0) > 0;
                }).length;
                return <span className="text-xs font-bold text-slate-500">{completedPhases}/{PHASES.length}</span>;
              })()}
            </td>
          </tr>);
      })}
    </>
  );
};
