import { useState, useMemo, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Checkbox } from './ui/checkbox';
import { Switch } from './ui/switch';
import { Search, ListChecks, AlertTriangle, CheckSquare, Square, Package } from 'lucide-react';
import { toast } from 'sonner';

/**
 * Selector múltiple de seriales para un concepto de reparación.
 *
 * Props:
 * - open, onClose
 * - pool: [{ serial, model_name, model_id }]  (seriales disponibles en la cotización)
 * - initialSelected: string[]
 * - initialNoSerial: bool — si el concepto está marcado como administrativo/logístico
 * - requiredQty: number  (debe coincidir con item.quantity)
 * - itemName: string
 * - onSave: (serials: string[], noSerial: bool) => void
 */
export const SerialsSelectorModal = ({
  open, onClose, pool, initialSelected = [], initialNoSerial = false, requiredQty, itemName, onSave,
}) => {
  const [selected, setSelected] = useState(new Set(initialSelected));
  const [noSerial, setNoSerial] = useState(!!initialNoSerial);
  const [query, setQuery] = useState('');

  useEffect(() => {
    if (open) {
      setSelected(new Set(initialSelected));
      setNoSerial(!!initialNoSerial);
      setQuery('');
    }
  }, [open, initialSelected, initialNoSerial]);

  const filtered = useMemo(() => {
    const q = (query || '').trim().toLowerCase();
    if (!q) return pool;
    return pool.filter(p =>
      (p.serial || '').toLowerCase().includes(q) ||
      (p.model_name || '').toLowerCase().includes(q)
    );
  }, [pool, query]);

  const groups = useMemo(() => {
    const map = {};
    for (const p of filtered) {
      const key = p.model_name || 'Sin modelo';
      if (!map[key]) map[key] = [];
      map[key].push(p);
    }
    return map;
  }, [filtered]);

  const selCount = selected.size;
  const atLimit = selCount >= requiredQty;
  const isValid = selCount === requiredQty;

  const toggle = (serial) => {
    if (noSerial) return; // Bloqueado en modo "Sin Serial"
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(serial)) {
        next.delete(serial);
      } else {
        if (prev.size >= requiredQty) return prev;
        next.add(serial);
      }
      return next;
    });
  };

  // Selecciona todos los seriales visibles (filtrados) hasta llegar a requiredQty.
  const handleSelectAll = () => {
    if (noSerial) return;
    if (filtered.length === 0) {
      toast.info('No hay seriales en la lista para seleccionar.');
      return;
    }
    if (filtered.length > requiredQty) {
      toast.warning(`La cantidad del concepto es ${requiredQty}. Se marcarán los primeros ${requiredQty} seriales visibles; los demás quedan disponibles.`);
    }
    const next = new Set();
    for (const p of filtered) {
      if (next.size >= requiredQty) break;
      next.add(p.serial);
    }
    setSelected(next);
  };

  const handleClearAll = () => {
    if (noSerial) return;
    setSelected(new Set());
  };

  const handleToggleNoSerial = (val) => {
    setNoSerial(val);
    if (val) {
      // Al activar "Sin Serial" limpia la selección
      setSelected(new Set());
    }
  };

  const handleSave = () => {
    if (noSerial) {
      onSave([], true);
      onClose();
      return;
    }
    onSave(Array.from(selected), false);
    onClose();
  };

  // El botón Guardar acepta: noSerial=true OR selección exacta.
  const canSave = noSerial || isValid;
  const allFilteredSelected = !noSerial && filtered.length > 0 && filtered.every(p => selected.has(p.serial));

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col" data-testid="serials-selector-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ListChecks size={18} className="text-orange-600" />
            Seriales asociados: <span className="font-normal text-slate-600">{itemName}</span>
          </DialogTitle>
        </DialogHeader>

        {/* === Toolbar superior: Sin Serial + Seleccionar todos === */}
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-2.5">
          {/* Sin Serial switch */}
          <div className={`flex items-center justify-between gap-3 px-2 py-1.5 rounded-md border ${
            noSerial ? 'bg-emerald-50 border-emerald-300' : 'bg-white border-slate-200'
          }`}>
            <div className="flex items-center gap-2">
              <Package size={15} className={noSerial ? 'text-emerald-700' : 'text-slate-500'} />
              <div>
                <div className={`text-sm font-medium ${noSerial ? 'text-emerald-800' : 'text-slate-800'}`}>
                  Sin Serial — concepto administrativo/logístico
                </div>
                <div className="text-[10px] text-slate-500">
                  Para Casillero, Envío, Seguros, Gastos, etc. No requiere vincular hardware.
                </div>
              </div>
            </div>
            <Switch
              checked={noSerial}
              onCheckedChange={handleToggleNoSerial}
              data-testid="serials-no-serial-switch"
            />
          </div>

          {/* Seleccionar todos / Limpiar */}
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={handleSelectAll}
                disabled={noSerial || filtered.length === 0}
                className="h-8 text-xs border-orange-200 text-orange-700 hover:bg-orange-50 disabled:opacity-50"
                data-testid="serials-select-all-btn"
              >
                {allFilteredSelected ? <CheckSquare size={14} className="mr-1" /> : <Square size={14} className="mr-1" />}
                Seleccionar todos ({Math.min(filtered.length, requiredQty)})
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={handleClearAll}
                disabled={noSerial || selected.size === 0}
                className="h-8 text-xs text-slate-500 hover:text-slate-700"
                data-testid="serials-clear-btn"
              >
                Limpiar
              </Button>
            </div>
            <div className={`text-xs px-2.5 py-1 rounded-full font-medium ${
              noSerial ? 'bg-emerald-100 text-emerald-700'
              : isValid ? 'bg-emerald-100 text-emerald-700'
              : (selCount > requiredQty ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700')
            }`} data-testid="serials-counter">
              {noSerial ? 'Sin serial' : `${selCount} / ${requiredQty} seriales`}
            </div>
          </div>

          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <Input
              placeholder="Buscar serial o modelo..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-9 h-9 text-sm"
              disabled={noSerial}
              data-testid="serials-search"
            />
          </div>
        </div>

        {/* List */}
        <div className={`flex-1 overflow-y-auto border border-slate-200 rounded-md ${noSerial ? 'opacity-50 pointer-events-none' : ''}`} data-testid="serials-pool-list">
          {Object.keys(groups).length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-sm">
              <AlertTriangle size={28} className="mx-auto mb-2 text-amber-400" />
              {pool.length === 0
                ? 'No hay seriales precargados en esta cotización. Agregue modelos con seriales en el paso anterior.'
                : 'No hay coincidencias con la búsqueda.'}
            </div>
          ) : Object.entries(groups).map(([model, serials]) => (
            <div key={model} className="border-b border-slate-100 last:border-b-0">
              <div className="bg-slate-50 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500 sticky top-0 z-10">
                {model} · {serials.length}
              </div>
              <ul className="divide-y divide-slate-100">
                {serials.map(p => {
                  const checked = selected.has(p.serial);
                  const disabled = !checked && atLimit;
                  return (
                    <li key={p.serial}
                        className={`flex items-center gap-3 px-3 py-2 text-sm transition ${
                          checked ? 'bg-emerald-50' : (disabled ? 'bg-slate-50/50' : 'hover:bg-slate-50')
                        }`}>
                      <Checkbox
                        checked={checked}
                        disabled={disabled}
                        onCheckedChange={() => toggle(p.serial)}
                        className="h-4 w-4"
                        data-testid={`serial-chk-${p.serial}`}
                      />
                      <span className={`font-mono text-xs flex-1 ${checked ? 'text-emerald-700 font-medium' : (disabled ? 'text-slate-400' : 'text-slate-700')}`}>
                        {p.serial}
                      </span>
                      {disabled && <span className="text-[10px] text-slate-400 italic">límite alcanzado</span>}
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose} data-testid="serials-cancel">Cancelar</Button>
          <Button
            onClick={handleSave}
            disabled={!canSave}
            className={noSerial ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-orange-600 hover:bg-orange-700'}
            data-testid="serials-save"
          >
            {noSerial
              ? 'Guardar sin serial'
              : isValid
                ? 'Guardar selección'
                : `Faltan ${Math.max(0, requiredQty - selCount)} serial(es)`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default SerialsSelectorModal;
