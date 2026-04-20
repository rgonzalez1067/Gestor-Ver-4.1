import { Building2, Bell, CheckCircle2, Lock } from 'lucide-react';
import { Button } from '../ui/button';

// ==================== MULTISTORE: Bank Section (Read-Only) ====================
export const MultistoreBankSection = ({ bankName, products, rollupBankData, bankExecutedLevels, onOpenNotif }) => {
  return (
    <>
      <tr className="bg-blue-50 border-t-2 border-blue-200">
        <td className="px-4 py-2 text-sm font-bold text-blue-900"><Building2 size={14} className="inline mr-2 text-blue-600" />{bankName}</td>
        <td className="px-4 py-2 text-center text-xs text-blue-600 font-medium">
          {(() => { const pcts = products.map(p => rollupBankData[p] || 0); return `Promedio: ${pcts.length > 0 ? Math.round(pcts.reduce((a, b) => a + b, 0) / pcts.length) : 0}%`; })()}
        </td>
        <td className="px-3 py-2 text-center">
          <Button size="sm" variant="outline" onClick={onOpenNotif}
            className={`h-7 text-xs ${bankExecutedLevels.length >= 4 ? 'border-emerald-300 text-emerald-700' : bankExecutedLevels.length > 0 ? 'border-blue-300 text-blue-700' : 'border-amber-300 text-amber-700'}`}
            data-testid={`notif-bank-btn-${bankName}`}>
            {bankExecutedLevels.length >= 4 ? <CheckCircle2 size={12} className="mr-1" /> : <Bell size={12} className="mr-1" />}
            {bankExecutedLevels.length > 0 ? `${bankExecutedLevels.length}/4` : 'Notificaciones'}
          </Button>
        </td>
      </tr>
      {products.map(productName => {
        const pct = rollupBankData[productName] || 0;
        return (
          <tr key={productName} className="border-t border-slate-100 hover:bg-slate-50">
            <td className="px-6 py-2.5 text-sm text-slate-700">{productName}</td>
            <td className="px-4 py-2.5 border-l border-slate-100">
              <div className="flex items-center gap-3">
                <div className="flex-1 bg-slate-100 rounded-full h-3 overflow-hidden">
                  <div className={`h-full rounded-full transition-all duration-500 ${pct >= 100 ? 'bg-emerald-500' : pct >= 50 ? 'bg-blue-500' : pct > 0 ? 'bg-amber-400' : 'bg-slate-200'}`}
                    style={{ width: `${Math.min(pct, 100)}%` }} data-testid={`rollup-bar-${bankName}-${productName}`} />
                </div>
                <span className={`text-sm font-bold min-w-[45px] text-right ${pct >= 100 ? 'text-emerald-600' : 'text-slate-600'}`}>{pct}%</span>
              </div>
            </td>
            <td className="px-3 py-2.5 text-center border-l border-slate-100 text-xs text-slate-400"><Lock size={12} className="inline text-slate-300" /></td>
          </tr>);
      })}
    </>
  );
};
