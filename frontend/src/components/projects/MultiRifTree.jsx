import { useState } from 'react';
import { ChevronRight, ChevronDown, Building2, Store, Landmark, CheckCircle2 } from 'lucide-react';
import { StoreBankSection } from './StoreBankSection';
import { STORE_PHASES, PHASE_COLORS } from './projectConstants';

const calcStoreProgress = (store) => {
  const sm = store.implementation_matrix || {};
  let completed = 0, total = 0;
  Object.values(sm).forEach(products => {
    Object.values(products).forEach(phases => {
      STORE_PHASES.forEach(p => { total++; if (phases[p]?.completed) completed++; });
    });
  });
  return total > 0 ? Math.round((completed / total) * 100) : 0;
};

const weightedProgress = (stores) => {
  const totalBoxes = stores.reduce((s, st) => s + (st.box_count || 0), 0);
  if (stores.length === 0) return 0;
  if (totalBoxes === 0) return Math.round(stores.reduce((s, st) => s + calcStoreProgress(st), 0) / stores.length);
  return Math.round(stores.reduce((s, st) => s + calcStoreProgress(st) * (st.box_count || 0), 0) / totalBoxes);
};

// Chip de avance con colores semáforo: 0% rojo · <50% amarillo · ≥50% verde.
const pctChipClass = (pct) =>
  pct === 0 ? 'bg-red-100 text-red-700' : pct < 50 ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700';

const ProgressBar = ({ pct, size = 'md' }) => {
  const color = pct >= 100 ? 'bg-emerald-500' : pct > 0 ? 'bg-blue-500' : 'bg-slate-300';
  return (
    <div className="flex items-center gap-2 min-w-[130px]">
      <div className={`flex-1 ${size === 'sm' ? 'h-1.5' : 'h-2'} bg-slate-200 rounded-full overflow-hidden`}>
        <div className={`h-full rounded-full transition-all duration-300 ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-xs font-semibold tabular-nums ${pct >= 100 ? 'text-emerald-700' : 'text-slate-600'}`}>{pct}%</span>
    </div>
  );
};

export const MultiRifTree = ({ project, canEditMatrix, onUpdateStoreQuantity, onUpdateStoreCascade, onFillStorePhase }) => {
  const [openRifs, setOpenRifs] = useState({});
  const [openStores, setOpenStores] = useState({});

  const rifs = project.rifs || [];
  const allStores = project.stores || [];
  const storesByRif = (rifId) => allStores.filter(s => s.rif_id === rifId);

  const globalPct = weightedProgress(allStores);
  const totalBoxes = rifs.reduce((s, r) => s + (r.box_count || 0), 0);

  const toggleRif = (id) => setOpenRifs(p => ({ ...p, [id]: !p[id] }));
  const toggleStore = (id) => setOpenStores(p => ({ ...p, [id]: !p[id] }));

  return (
    <div className="mb-6" data-testid="multirif-section">
      <h2 className="text-lg font-bold text-slate-900 mb-3 flex items-center gap-2">
        <Building2 size={20} className="text-indigo-600" />
        Seguimiento Multi-RIF · 3 Niveles
      </h2>

      {/* Nivel 1: Global */}
      <div className="rounded-lg border border-indigo-200 bg-indigo-50/40 p-3 mb-3" data-testid="multirif-global-node">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <Landmark size={18} className="text-indigo-700" />
            <span className="font-semibold text-sm text-indigo-900">Proyecto Global</span>
            <span className="text-xs text-slate-500">· {rifs.length} RIF(s) · {allStores.length} sucursal(es) · {totalBoxes} caja(s)</span>
          </div>
          <ProgressBar pct={globalPct} />
        </div>
      </div>

      {/* Nivel 2: RIFs */}
      <div className="space-y-2">
        {rifs.map((rif) => {
          const stores = storesByRif(rif.rif_id);
          const rifPct = weightedProgress(stores);
          const isOpen = !!openRifs[rif.rif_id];
          return (
            <div key={rif.rif_id} className="rounded-lg border border-slate-200 bg-white overflow-hidden" data-testid={`multirif-rif-node-${rif.rif_id}`}>
              <button type="button" onClick={() => toggleRif(rif.rif_id)}
                className="w-full flex items-center justify-between gap-3 px-3 py-2.5 hover:bg-slate-50 text-left"
                data-testid={`multirif-rif-toggle-${rif.rif_id}`}>
                <div className="flex items-center gap-2 min-w-0">
                  {isOpen ? <ChevronDown size={16} className="text-slate-400 shrink-0" /> : <ChevronRight size={16} className="text-slate-400 shrink-0" />}
                  <Building2 size={16} className="text-indigo-500 shrink-0" />
                  <span className="font-semibold text-sm text-slate-800 truncate">{rif.client_name}</span>
                  <span className="text-xs text-slate-400 shrink-0">— {rif.rif} · {stores.length} suc. · {rif.box_count} caja(s)</span>
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full shrink-0 ${pctChipClass(rifPct)}`} data-testid={`multirif-rif-pct-${rif.rif_id}`}>{rifPct}%</span>
                  {rifPct >= 100 && <CheckCircle2 size={14} className="text-emerald-500 shrink-0" />}
                </div>
                <div className="shrink-0"><ProgressBar pct={rifPct} /></div>
              </button>

              {/* Nivel 3: Sucursales */}
              {isOpen && (
                <div className="px-3 pb-3 pt-1 space-y-2 bg-slate-50/50 border-t border-slate-100">
                  {stores.length === 0 && <p className="text-xs text-slate-400 py-2 pl-6">Este RIF no tiene sucursales.</p>}
                  {stores.map((store) => {
                    const stPct = calcStoreProgress(store);
                    const stOpen = !!openStores[store.store_id];
                    const storeMatrix = store.implementation_matrix || {};
                    const storeBankNames = Object.keys(storeMatrix);
                    return (
                      <div key={store.store_id} className="rounded-md border border-slate-200 bg-white" data-testid={`multirif-store-node-${store.store_id}`}>
                        <button type="button" onClick={() => toggleStore(store.store_id)}
                          className="w-full flex items-center justify-between gap-3 px-3 py-2 hover:bg-slate-50 text-left"
                          data-testid={`multirif-store-toggle-${store.store_id}`}>
                          <div className="flex items-center gap-2 min-w-0">
                            {stOpen ? <ChevronDown size={14} className="text-slate-400 shrink-0" /> : <ChevronRight size={14} className="text-slate-400 shrink-0" />}
                            <Store size={14} className="text-blue-500 shrink-0" />
                            <span className="text-sm text-slate-700 truncate">{store.name}</span>
                            <span className="text-xs text-slate-400 shrink-0">· {store.box_count} caja(s)</span>
                          </div>
                          <div className="shrink-0"><ProgressBar pct={stPct} size="sm" /></div>
                        </button>

                        {stOpen && (
                          <div className="px-3 pb-3" data-testid={`multirif-store-matrix-${store.store_id}`}>
                            {storeBankNames.length === 0 ? (
                              <p className="text-xs text-slate-400 text-center py-4">Sin datos en la matriz.</p>
                            ) : (
                              <div className="overflow-x-auto rounded-lg border border-slate-200">
                                <table className="w-full">
                                  <thead><tr>
                                    <th className="bg-blue-600 text-white px-4 py-2 text-left text-xs font-semibold min-w-[200px]">Bancos / Productos</th>
                                    {STORE_PHASES.map(p => <th key={p} className={`px-3 py-2 text-center text-xs font-semibold border-l border-slate-200 min-w-[100px] ${PHASE_COLORS[p]}`}>{p}</th>)}
                                    <th className="bg-blue-600 text-white px-3 py-2 text-center text-xs font-semibold border-l border-slate-200">Avance</th>
                                  </tr></thead>
                                  <tbody>
                                    {storeBankNames.map(bk => (
                                      <StoreBankSection key={bk} bankName={bk} products={Object.keys(storeMatrix[bk])}
                                        matrixData={storeMatrix[bk]} storeId={store.store_id}
                                        onUpdateStoreQuantity={onUpdateStoreQuantity}
                                        onUpdateStoreCascade={onUpdateStoreCascade}
                                        onFillStorePhase={onFillStorePhase}
                                        phases={STORE_PHASES} readOnly={!canEditMatrix} expectedQty={store.box_count || 0} />
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default MultiRifTree;
