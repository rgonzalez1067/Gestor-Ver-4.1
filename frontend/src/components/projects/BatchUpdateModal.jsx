import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { Button } from '../ui/button';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Checkbox } from '../ui/checkbox';
import { Layers, Building2, ListChecks } from 'lucide-react';
import { STORE_PHASES } from './projectConstants';

// Avance por tienda (% de fases completadas sobre el total de la matriz de la tienda).
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
  if (!stores || stores.length === 0) return 0;
  const totalBoxes = stores.reduce((s, st) => s + (st.box_count || 0), 0);
  if (totalBoxes === 0) return Math.round(stores.reduce((s, st) => s + calcStoreProgress(st), 0) / stores.length);
  return Math.round(stores.reduce((s, st) => s + calcStoreProgress(st) * (st.box_count || 0), 0) / totalBoxes);
};

const pctChipClass = (pct) =>
  pct === 0 ? 'bg-red-100 text-red-700' : pct < 50 ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700';
const pctBarClass = (pct) =>
  pct === 0 ? 'bg-red-400' : pct < 50 ? 'bg-amber-400' : 'bg-emerald-500';

/**
 * Actualización Masiva (multi-selección): marca al 100% una o varias FASES para
 * uno o varios BANCOS/ENTES (cada uno con su propio catálogo de medios de pago).
 * Disponible para todos los proyectos: en multitienda aplica a las tiendas
 * seleccionadas; en NO multitienda aplica directo a la matriz del proyecto.
 */
export const BatchUpdateModal = ({
  open, onOpenChange,
  project,
  isMultistore,
  batchPhases, toggleBatchPhase,
  batchBanks, toggleBatchBank,
  batchBankProducts, toggleBatchBankProduct,
  batchRif, setBatchRif,
  batchStoreIds,
  batchReason, setBatchReason,
  batchSubmitting,
  toggleBatchStore,
  toggleAllBatchStores,
  submitBatchUpdate,
}) => {
  const stores = project?.stores || [];
  const matrix = project?.implementation_matrix || {};
  const banks = Object.keys(matrix);
  const productsOfBank = (bank) => Object.keys(matrix[bank] || {});

  const rifs = project?.rifs || [];
  const isMultiRif = rifs.length > 0;
  const rifLabel = (r) => `${r.client_name || 'Cliente'} — RIF: ${r.rif || ''}`;
  const storesOfRif = (rifId) => stores.filter(s => s.rif_id === rifId);
  const rifPct = (rifId) => weightedProgress(storesOfRif(rifId));
  const globalPct = weightedProgress(stores);
  const filteredStores = (batchRif && batchRif !== '__ALL__')
    ? stores.filter(s => s.rif_id === batchRif)
    : stores;
  const scopePct = (batchRif && batchRif !== '__ALL__') ? rifPct(batchRif) : globalPct;
  const scopeLabel = (batchRif && batchRif !== '__ALL__')
    ? (rifs.find(r => r.rif_id === batchRif)?.client_name || 'RIF')
    : 'Todos los RIFs';

  const banksWithProducts = batchBanks.filter(b => (batchBankProducts[b] || []).length > 0);
  const totalProducts = banksWithProducts.reduce((n, b) => n + (batchBankProducts[b] || []).length, 0);
  const canSubmit =
    batchPhases.length > 0 &&
    banksWithProducts.length > 0 &&
    (!isMultistore || batchStoreIds.length > 0);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="batch-update-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-amber-600">
            <Layers size={22} />
            Actualización Masiva de Estatus
          </DialogTitle>
          <p className="text-xs text-slate-500 mt-1">
            Marca al 100% una o varias fases para varios medios de pago de uno o varios bancos/entes.
            {isMultistore ? ' Se aplica a las tiendas seleccionadas.' : ' Se aplica a la matriz del proyecto.'}
            {' '}Queda registrado en la bitácora.
          </p>
          <DialogDescription className="sr-only">Asistente de actualización masiva de estatus de proyecto</DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* ===== FASES (multi-selección) ===== */}
          <div>
            <Label className="text-xs font-semibold flex items-center gap-1">
              <ListChecks size={13} /> Fases <span className="text-amber-600">({batchPhases.length})</span>
            </Label>
            <div className="border rounded-lg p-2.5 mt-1.5 bg-slate-50 grid grid-cols-2 sm:grid-cols-4 gap-2" data-testid="batch-phases-list">
              {STORE_PHASES.map(p => (
                <label key={p} className="flex items-center gap-2 text-sm p-1.5 rounded hover:bg-white cursor-pointer" data-testid={`batch-phase-${p}`}>
                  <Checkbox
                    checked={batchPhases.includes(p)}
                    onCheckedChange={() => toggleBatchPhase(p)}
                    data-testid={`batch-phase-checkbox-${p}`}
                  />
                  <span className="flex-1 min-w-0 font-medium text-slate-700 truncate text-xs">{p}</span>
                </label>
              ))}
            </div>
          </div>

          {/* ===== BANCOS / ENTES (multi-selección) ===== */}
          <div>
            <Label className="text-xs font-semibold flex items-center gap-1">
              <Building2 size={13} /> Banco / Ente <span className="text-amber-600">({batchBanks.length}/{banks.length})</span>
            </Label>
            <div className="border rounded-lg p-2.5 mt-1.5 bg-slate-50 grid grid-cols-2 gap-2" data-testid="batch-banks-list">
              {banks.length === 0 ? (
                <p className="text-xs text-slate-400 text-center py-2 col-span-2">Este proyecto no tiene bancos/entes en la matriz</p>
              ) : banks.map(b => (
                <label key={b} className="flex items-center gap-2 text-sm p-1.5 rounded hover:bg-white cursor-pointer" data-testid={`batch-bank-${b}`}>
                  <Checkbox
                    checked={batchBanks.includes(b)}
                    onCheckedChange={() => toggleBatchBank(b)}
                    data-testid={`batch-bank-checkbox-${b}`}
                  />
                  <span className="flex-1 min-w-0 font-medium text-slate-700 truncate">{b}</span>
                </label>
              ))}
            </div>
          </div>

          {/* ===== MEDIOS DE PAGO por cada banco seleccionado (bloques dinámicos) ===== */}
          {batchBanks.length > 0 && (
            <div className="space-y-2" data-testid="batch-payment-methods">
              <Label className="text-xs font-semibold">Medios de Pago por Banco/Ente</Label>
              {batchBanks.map(bank => {
                const prods = productsOfBank(bank);
                const selected = batchBankProducts[bank] || [];
                return (
                  <div key={bank} className="border rounded-lg overflow-hidden" data-testid={`batch-bank-block-${bank}`}>
                    <div className="flex items-center justify-between px-3 py-2 bg-indigo-50 border-b border-indigo-100">
                      <span className="text-sm font-semibold text-indigo-800 flex items-center gap-1.5 truncate">
                        <Building2 size={13} /> {bank}
                      </span>
                      <span className="text-[11px] font-bold text-indigo-600 shrink-0">{selected.length}/{prods.length}</span>
                    </div>
                    <div className="p-2.5 bg-white">
                      {prods.length === 0 ? (
                        <p className="text-xs text-slate-400 text-center py-2">Este banco no tiene medios de pago configurados</p>
                      ) : (
                        <div className="grid grid-cols-2 gap-2">
                          {prods.map(prod => (
                            <label key={prod} className="flex items-center gap-2 text-sm p-1.5 rounded hover:bg-slate-50 cursor-pointer" data-testid={`batch-product-${bank}-${prod}`}>
                              <Checkbox
                                checked={selected.includes(prod)}
                                onCheckedChange={() => toggleBatchBankProduct(bank, prod)}
                                data-testid={`batch-product-checkbox-${bank}-${prod}`}
                              />
                              <span className="flex-1 min-w-0 font-medium text-slate-700 truncate">{prod}</span>
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* ===== TIENDAS (solo multitienda / Multi-RIF) ===== */}
          {isMultistore && (
            <>
              {isMultiRif && (
                <div>
                  <Label className="text-xs font-semibold">RIF (Cliente) <span className="text-slate-400 font-normal">— filtra las tiendas</span></Label>
                  <Select value={batchRif} onValueChange={setBatchRif}>
                    <SelectTrigger className="text-sm" data-testid="batch-rif-select"><SelectValue placeholder="RIF..." /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__ALL__" data-testid="batch-rif-all">
                        <span className="flex items-center gap-2">
                          <span>Todos los RIFs</span>
                          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${pctChipClass(globalPct)}`}>{globalPct}%</span>
                        </span>
                      </SelectItem>
                      {rifs.map(r => {
                        const p = rifPct(r.rif_id);
                        return (
                          <SelectItem key={r.rif_id} value={r.rif_id} data-testid={`batch-rif-${r.rif_id}`}>
                            <span className="flex items-center gap-2">
                              <span>{rifLabel(r)}</span>
                              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${pctChipClass(p)}`}>{p}%</span>
                            </span>
                          </SelectItem>
                        );
                      })}
                    </SelectContent>
                  </Select>
                  <div className="flex items-center gap-2 mt-2" data-testid="batch-rif-progress">
                    <span className="text-[11px] text-slate-500 shrink-0 truncate max-w-[45%]">{scopeLabel}</span>
                    <div className="flex-1 h-2 bg-slate-200 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full transition-all duration-300 ${pctBarClass(scopePct)}`} style={{ width: `${scopePct}%` }} />
                    </div>
                    <span className={`text-[11px] font-bold tabular-nums shrink-0 ${scopePct === 0 ? 'text-red-600' : scopePct < 50 ? 'text-amber-600' : 'text-emerald-700'}`}>{scopePct}% completado</span>
                  </div>
                </div>
              )}

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <Label className="text-xs font-semibold">Tiendas a procesar <span className="text-amber-600">({batchStoreIds.length}/{filteredStores.length})</span></Label>
                  <Button variant="ghost" size="sm" onClick={toggleAllBatchStores} className="text-xs text-amber-600" data-testid="batch-select-all">
                    {filteredStores.length > 0 && batchStoreIds.length === filteredStores.length ? 'Deseleccionar todas' : 'Seleccionar todas'}
                  </Button>
                </div>
                <div className="border rounded-lg p-3 max-h-60 overflow-y-auto bg-slate-50">
                  {filteredStores.length === 0 ? (
                    <p className="text-xs text-slate-400 text-center py-3">
                      {isMultiRif && batchRif !== '__ALL__' ? 'Este RIF no tiene tiendas' : 'Este proyecto no tiene tiendas'}
                    </p>
                  ) : (
                    <div className="grid grid-cols-2 gap-2">
                      {filteredStores.map(s => {
                        const sp = calcStoreProgress(s);
                        return (
                          <label key={s.store_id} className="flex items-center gap-2 text-sm p-1.5 rounded hover:bg-white cursor-pointer" data-testid={`batch-store-${s.store_id}`}>
                            <Checkbox
                              checked={batchStoreIds.includes(s.store_id)}
                              onCheckedChange={() => toggleBatchStore(s.store_id)}
                            />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-1.5">
                                <span className="font-medium text-slate-700 truncate">{s.name}</span>
                                <span className={`text-[9px] font-bold px-1 py-0.5 rounded-full shrink-0 ${pctChipClass(sp)}`}>{sp}%</span>
                              </div>
                              <div className="text-[10px] text-slate-400">{s.code || ''} · {s.box_count || 0} PDV</div>
                            </div>
                          </label>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            </>
          )}

          <div>
            <Label className="text-xs font-semibold">Motivo / Justificación</Label>
            <Textarea
              value={batchReason}
              onChange={(e) => setBatchReason(e.target.value)}
              placeholder="Ej: Recepción de información masiva por parte del Banco/Cliente..."
              rows={2} className="text-sm"
              data-testid="batch-reason"
            />
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-800" data-testid="batch-summary">
            <p className="font-semibold mb-1">Resumen:</p>
            <p>
              Se completará(n) <b>{batchPhases.length}</b> fase(s) [{batchPhases.join(', ') || '—'}] para <b>{totalProducts}</b> medio(s) de pago
              distribuidos en <b>{banksWithProducts.length}</b> banco(s)/ente(s)
              {isMultistore ? <> en <b>{batchStoreIds.length}</b> tienda(s)</> : <> sobre <b>la matriz del proyecto</b></>}.
              {' '}Esta acción queda registrada en la bitácora.
            </p>
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-2 border-t">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button
            onClick={submitBatchUpdate}
            disabled={batchSubmitting || !canSubmit}
            className="bg-amber-500 hover:bg-amber-600 text-white"
            data-testid="batch-submit-btn"
          >
            {batchSubmitting ? 'Procesando...' : <><Layers size={14} className="mr-1" /> Aplicar cambios</>}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default BatchUpdateModal;
