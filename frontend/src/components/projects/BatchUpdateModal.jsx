import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Checkbox } from '../ui/checkbox';
import { Layers } from 'lucide-react';
import { STORE_PHASES } from './projectConstants';

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
  const filteredStores = (batchRif && batchRif !== '__ALL__')
    ? stores.filter(s => s.rif_id === batchRif)
    : stores;

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

          {/* Fase 5: Filtro en cascada por RIF (solo Multi-RIF) */}
          {isMultiRif && (
            <div>
              <Label className="text-xs font-semibold">RIF (Cliente) <span className="text-slate-400 font-normal">— filtra las tiendas</span></Label>
              <Select value={batchRif} onValueChange={setBatchRif}>
                <SelectTrigger className="text-sm" data-testid="batch-rif-select"><SelectValue placeholder="RIF..." /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__ALL__" data-testid="batch-rif-all">Todos los RIFs</SelectItem>
                  {rifs.map(r => (
                    <SelectItem key={r.rif_id} value={r.rif_id} data-testid={`batch-rif-${r.rif_id}`}>
                      {rifLabel(r)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
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
                  {filteredStores.map(s => (
                    <label key={s.store_id} className="flex items-center gap-2 text-sm p-1.5 rounded hover:bg-white cursor-pointer" data-testid={`batch-store-${s.store_id}`}>
                      <Checkbox
                        checked={batchStoreIds.includes(s.store_id)}
                        onCheckedChange={() => toggleBatchStore(s.store_id)}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-slate-700 truncate">{s.name}</div>
                        <div className="text-[10px] text-slate-400">{s.code || ''} · {s.box_count || 0} PDV</div>
                      </div>
                    </label>
                  ))}
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
