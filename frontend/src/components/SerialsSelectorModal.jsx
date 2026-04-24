import { useState, useMemo, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Checkbox } from './ui/checkbox';
import { Search, ListChecks, AlertTriangle } from 'lucide-react';

/**
 * Selector múltiple de seriales para un concepto de reparación.
 *
 * Props:
 * - open, onClose
 * - pool: [{ serial, model_name, model_id }]  (seriales disponibles en la cotización)
 * - initialSelected: string[]  (seriales actualmente asociados al item)
 * - requiredQty: number  (debe coincidir con item.quantity)
 * - itemName: string (para el header del modal)
 * - onSave: (serials: string[]) => void
 */
export const SerialsSelectorModal = ({
  open, onClose, pool, initialSelected = [], requiredQty, itemName, onSave,
}) => {
  const [selected, setSelected] = useState(new Set(initialSelected));
  const [query, setQuery] = useState('');

  useEffect(() => {
    if (open) {
      setSelected(new Set(initialSelected));
      setQuery('');
    }
  }, [open, initialSelected]);

  const filtered = useMemo(() => {
    const q = (query || '').trim().toLowerCase();
    if (!q) return pool;
    return pool.filter(p =>
      (p.serial || '').toLowerCase().includes(q) ||
      (p.model_name || '').toLowerCase().includes(q)
    );
  }, [pool, query]);

  // Agrupar por modelo para mejor lectura.
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
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(serial)) {
        next.delete(serial);
      } else {
        if (prev.size >= requiredQty) {
          // Bloqueo duro
          return prev;
        }
        next.add(serial);
      }
      return next;
    });
  };

  const handleSave = () => {
    onSave(Array.from(selected));
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col" data-testid="serials-selector-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ListChecks size={18} className="text-orange-600" />
            Seriales asociados: <span className="font-normal text-slate-600">{itemName}</span>
          </DialogTitle>
        </DialogHeader>

        {/* Counter + search */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className={`text-xs px-2.5 py-1 rounded-full font-medium ${
            isValid ? 'bg-emerald-100 text-emerald-700'
            : (selCount > requiredQty ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700')
          }`} data-testid="serials-counter">
            {selCount} / {requiredQty} seriales
          </div>
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <Input
              placeholder="Buscar serial o modelo..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-9 h-9 text-sm"
              data-testid="serials-search"
            />
          </div>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto border border-slate-200 rounded-md" data-testid="serials-pool-list">
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
            disabled={!isValid}
            className="bg-orange-600 hover:bg-orange-700"
            data-testid="serials-save"
          >
            {isValid ? 'Guardar selección' : `Faltan ${Math.max(0, requiredQty - selCount)} serial(es)`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default SerialsSelectorModal;
