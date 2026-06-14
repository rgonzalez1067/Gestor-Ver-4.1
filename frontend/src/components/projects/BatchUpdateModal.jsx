import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Checkbox } from '../ui/checkbox';
import { Layers } from 'lucide-react';
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

// Avance ponderado por cantidad de cajas (igual criterio que el backend / árbol Multi-RIF).
const weightedProgress = (stores) => {
  if (!stores || stores.length === 0) return 0;
  const totalBoxes = stores.reduce((s, st) => s + (st.box_count || 0), 0);
  if (totalBoxes === 0) return Math.round(stores.reduce((s, st) => s + calcStoreProgress(st), 0) / stores.length);
  return Math.round(stores.reduce((s, st) => s + calcStoreProgress(st) * (st.box_count || 0), 0) / totalBoxes);
};

// Colores semáforo: 0% rojo · <50% amarillo · ≥50% verde.
const pctChipClass = (pct) =>
  pct === 0 ? 'bg-red-100 text-red-700' : pct < 50 ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700';
const pctBarClass = (pct) =>
  pct === 0 ? 'bg-red-400' : pct < 50 ? 'bg-amber-400' : 'bg-emerald-500';

/**
 * Modal de Actualización Masiva: marca al 100% una fase + producto + banco
 * para varias tiendas a la vez en un proyecto multi-tienda.
 *
 * Acepta el estado controlado por el padre (project, listas de tiendas) para
 * evitar duplicar la lógica de carga de datos.
 */
export const BatchUpdateModal = ({
  open, onOpenChange,
  project,
  batchPhase, setBatchPhase,
  batchBank, setBatchBank,
  batchRif, setBatchRif,
  batchProducts, toggleBatchProduct,
  batchStoreIds,
  batchReason, setBatchReason,
  batchSubmitting,
  toggleBatchStore,
  toggleAllBatchStores,
  submitBatchUpdate,
}) => {
  const stores = project?.stores || [];
  const banks = Object.keys(project?.implementation_matrix || {});
  const bankProducts = batchBank ? Object.keys((project?.implementation_matrix || {})[batchBank] || {}) : [];

  // Fase 5 VPOS Multi-RIF: filtro en cascada por RIF (solo aplica a proyectos Multi-RIF).
  const rifs = project?.rifs || [];
  const isMultiRif = rifs.length > 0;
  const rifLabel = (r) => `${r.client_name || 'Cliente'} — RIF: ${r.rif || ''}`;
  const storesOfRif = (rifId) => stores.filter(s => s.rif_id === rifId);
  const rifPct = (rifId) => weightedProgress(storesOfRif(rifId));
  const globalPct = weightedProgress(stores);
  const filteredStores = (batchRif && batchRif !== '__ALL__')
    ? stores.filter(s => s.rif_id === batchRif)
    : stores;
  // Avance del alcance actualmente visible (RIF seleccionado o global con "Todos").
  const scopePct = (batchRif && batchRif !== '__ALL__') ? rifPct(batchRif) : globalPct;
  const scopeLabel = (batchRif && batchRif !== '__ALL__')
    ? (rifs.find(r => r.rif_id === batchRif)?.client_name || 'RIF')
    : 'Todos los RIFs';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="batch-update-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-amber-600">
            <Layers size={22} />
            Actualización Masiva de Estatus
          </DialogTitle>
          <p className="text-xs text-slate-500 mt-1">
            Marca al 100% una fase para uno o varios medios de pago de un banco, en varias tiendas a la vez.
            Se registra en la bitácora del proyecto.
          </p>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs font-semibold">Fase</Label>
              <Select value={batchPhase} onValueChange={setBatchPhase}>
                <SelectTrigger className="text-sm" data-testid="batch-phase-select"><SelectValue placeholder="Fase..." /></SelectTrigger>
                <SelectContent>
                  {STORE_PHASES.map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs font-semibold">Banco / Ente</Label>
              <Select value={batchBank} onValueChange={setBatchBank}>
                <SelectTrigger className="text-sm" data-testid="batch-bank-select"><SelectValue placeholder="Banco..." /></SelectTrigger>
                <SelectContent>
                  {banks.map(b => <SelectItem key={b} value={b}>{b}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Medios de pago (productos) del banco — selección múltiple */}
          <div>
            <Label className="text-xs font-semibold">
              Medios de Pago <span className="text-amber-600">({batchProducts.length}/{bankProducts.length})</span>
            </Label>
            <div className="border rounded-lg p-3 mt-1.5 bg-slate-50" data-testid="batch-products-list">
              {!batchBank ? (
                <p className="text-xs text-slate-400 text-center py-2">Seleccione un banco para ver sus medios de pago</p>
              ) : bankProducts.length === 0 ? (
                <p className="text-xs text-slate-400 text-center py-2">Este banco no tiene medios de pago configurados</p>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  {bankProducts.map(prod => (
                    <label key={prod} className="flex items-center gap-2 text-sm p-1.5 rounded hover:bg-white cursor-pointer" data-testid={`batch-product-${prod}`}>
                      <Checkbox
                        checked={batchProducts.includes(prod)}
                        onCheckedChange={() => toggleBatchProduct(prod)}
                        data-testid={`batch-product-checkbox-${prod}`}
                      />
                      <span className="flex-1 min-w-0 font-medium text-slate-700 truncate">{prod}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Fase 5: Filtro en cascada por RIF (solo Multi-RIF) con % de avance por RIF */}
          {isMultiRif && (
            <div>
              <Label className="text-xs font-semibold">RIF (Cliente) <span className="text-slate-400 font-normal">— filtra las tiendas</span></Label>
              <Select value={batchRif} onValueChange={setBatchRif}>
                <SelectTrigger className="text-sm" data-testid="batch-rif-select"><SelectValue placeholder="RIF..." /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__ALL__" data-testid="batch-rif-all">
                    <span className="flex items-center gap-2">
                      <span>Todos los RIFs</span>
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${pctChipClass(globalPct)}`} data-testid="batch-rif-pct-all">{globalPct}%</span>
                    </span>
                  </SelectItem>
                  {rifs.map(r => {
                    const p = rifPct(r.rif_id);
                    return (
                      <SelectItem key={r.rif_id} value={r.rif_id} data-testid={`batch-rif-${r.rif_id}`}>
                        <span className="flex items-center gap-2">
                          <span>{rifLabel(r)}</span>
                          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${pctChipClass(p)}`} data-testid={`batch-rif-pct-${r.rif_id}`}>{p}%</span>
                        </span>
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>

              {/* Mini barra de avance del alcance seleccionado */}
              <div className="flex items-center gap-2 mt-2" data-testid="batch-rif-progress">
                <span className="text-[11px] text-slate-500 shrink-0 truncate max-w-[45%]">{scopeLabel}</span>
                <div className="flex-1 h-2 bg-slate-200 rounded-full overflow-hidden">
                  <div className={`h-full rounded-full transition-all duration-300 ${pctBarClass(scopePct)}`} style={{ width: `${scopePct}%` }} />
                </div>
                <span className={`text-[11px] font-bold tabular-nums shrink-0 ${scopePct === 0 ? 'text-red-600' : scopePct < 50 ? 'text-amber-600' : 'text-emerald-700'}`} data-testid="batch-rif-progress-pct">{scopePct}% completado</span>
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

          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-800">
            <p className="font-semibold mb-1">Resumen:</p>
            <p>
              Se completará <b>{batchPhase || '—'}</b> de <b>{batchProducts.length}</b> medio(s) de pago (banco <b>{batchBank || '—'}</b>)
              {isMultiRif && <> · RIF: <b>{batchRif === '__ALL__' ? 'Todos' : (rifs.find(r => r.rif_id === batchRif)?.rif || '—')}</b></>}
              {' '}en <b>{batchStoreIds.length}</b> tienda(s). Esta acción queda registrada en la bitácora.
            </p>
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-2 border-t">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button
            onClick={submitBatchUpdate}
            disabled={batchSubmitting || batchStoreIds.length === 0 || batchProducts.length === 0}
            className="bg-amber-500 hover:bg-amber-600 text-white"
            data-testid="batch-submit-btn"
          >
            {batchSubmitting ? 'Procesando...' : <><Layers size={14} className="mr-1" /> Aplicar a {batchStoreIds.length} tienda(s)</>}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default BatchUpdateModal;
