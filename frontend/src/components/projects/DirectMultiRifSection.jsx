import { useMemo, useState } from 'react';
import { Building2, Layers, Plus, Trash2, AlertCircle, CheckCircle2 } from 'lucide-react';
import { Button } from '../ui/button';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import { Checkbox } from '../ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { toast } from 'sonner';
import { MultiRifDistributionPanel } from '../quotes/MultiRifDistributionPanel';

const AVAIL_BY_TYPE = {
  VPOS: 'vpos_available',
  MPOS: 'mpos_available',
  GATEWAY: 'gateway_available',
  LINK_PAGO: 'link_available',
};

/**
 * Constructor de matriz Banco→Producto para UN RIF (cuando NO se comparte la
 * matriz entre tiendas). Permite elegir un banco y marcar productos para
 * agregarlos a `rif.boxes_grid`.
 */
function RifMatrixBuilder({ rif, banks, quoteType, onChange }) {
  const [bank, setBank] = useState('');
  const [checked, setChecked] = useState({});

  const availField = AVAIL_BY_TYPE[quoteType] || 'vpos_available';
  const products = useMemo(() => {
    if (!bank) return [];
    const b = banks.find((x) => x.name === bank);
    if (!b || !Array.isArray(b.products)) return [];
    const seen = new Set();
    return b.products.filter((p) => {
      if (!p[availField]) return false;
      const k = (p.product_name || '').trim().toLowerCase();
      if (!k || seen.has(k)) return false;
      seen.add(k);
      return true;
    });
  }, [bank, banks, availField]);

  const grid = rif.boxes_grid || [];

  const addSelected = () => {
    const chosen = products.filter((p) => checked[p.product_name]);
    if (!bank) { toast.error('Selecciona un banco'); return; }
    if (chosen.length === 0) { toast.error('Marca al menos un producto'); return; }
    const existing = new Set(grid.map((g) => `${g.bank_name}||${g.product_name}`));
    const rows = chosen
      .filter((p) => !existing.has(`${bank}||${p.product_name}`))
      .map((p) => ({ quantity: 1, bank_name: bank, product_name: p.product_name }));
    onChange([...grid, ...rows]);
    setChecked({});
    toast.success(`${rows.length} producto(s) agregado(s) a ${rif.client_name || 'RIF'}`);
  };

  const removeRow = (idx) => onChange(grid.filter((_, i) => i !== idx));

  return (
    <div className="rounded-md border border-indigo-100 bg-white p-3 space-y-3" data-testid={`dp-rif-matrix-${rif.client_id || 'new'}`}>
      <div className="flex items-center gap-2 text-sm font-medium text-indigo-800">
        <Building2 size={14} /> {rif.client_name || 'RIF sin cliente'} <span className="text-slate-400 font-normal">— {rif.rif || 's/RIF'}</span>
        <Badge variant="secondary" className="ml-auto text-[10px]">{grid.length} producto(s)</Badge>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-[220px_1fr] gap-3 items-start">
        <div>
          <Label className="text-xs text-slate-600">Banco</Label>
          <Select value={bank} onValueChange={(v) => { setBank(v); setChecked({}); }}>
            <SelectTrigger className="h-9 mt-1" data-testid={`dp-rif-bank-${rif.client_id || 'new'}`}><SelectValue placeholder="Selecciona banco..." /></SelectTrigger>
            <SelectContent>
              {banks.map((bk) => <SelectItem key={bk.bank_id} value={bk.name}>{bk.name}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-xs text-slate-600">Productos disponibles {bank && <span className="text-indigo-500">· {products.length}</span>}</Label>
          {!bank ? (
            <p className="text-xs text-slate-400 italic mt-2">Elige un banco para ver sus productos.</p>
          ) : products.length === 0 ? (
            <p className="text-xs text-slate-400 italic mt-2">Este banco no tiene productos para el tipo de proyecto.</p>
          ) : (
            <div className="mt-1 grid grid-cols-1 sm:grid-cols-2 gap-1.5 max-h-44 overflow-y-auto pr-1">
              {products.map((p) => (
                <label key={p.product_name} className="flex items-center gap-2 bg-white border border-slate-200 rounded-md px-2.5 py-1.5 cursor-pointer hover:bg-indigo-50">
                  <Checkbox checked={!!checked[p.product_name]} onCheckedChange={() => setChecked((c) => ({ ...c, [p.product_name]: !c[p.product_name] }))} data-testid={`dp-rif-check-${rif.client_id || 'new'}-${p.product_name}`} />
                  <span className="text-xs text-slate-700">{p.product_name}</span>
                </label>
              ))}
            </div>
          )}
          <div className="flex justify-end mt-2">
            <Button type="button" size="sm" onClick={addSelected} disabled={!bank} className="bg-indigo-600 hover:bg-indigo-700 text-white" data-testid={`dp-rif-add-${rif.client_id || 'new'}`}>
              <Plus size={13} className="mr-1" /> Agregar a este RIF
            </Button>
          </div>
        </div>
      </div>

      {grid.length > 0 && (
        <div className="border border-slate-200 rounded-md overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-2 py-1.5 text-left font-medium text-slate-600">Banco</th>
                <th className="px-2 py-1.5 text-left font-medium text-slate-600">Producto</th>
                <th className="px-2 py-1.5 w-10"></th>
              </tr>
            </thead>
            <tbody>
              {grid.map((g, i) => (
                <tr key={i} className="border-b border-slate-100">
                  <td className="px-2 py-1 text-slate-700">{g.bank_name}</td>
                  <td className="px-2 py-1 text-slate-700">{g.product_name}</td>
                  <td className="px-2 py-1"><Button type="button" size="sm" variant="ghost" onClick={() => removeRow(i)} className="text-red-600 h-6 w-6 p-0"><Trash2 size={12} /></Button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/**
 * Sección Multi-RIF para Proyectos Directos. Reutiliza el panel de distribución
 * jerárquica (Global → RIF → Tienda) y, cuando la matriz NO es compartida,
 * expone un constructor de matriz Banco→Producto por cada RIF.
 */
export function DirectMultiRifSection({ clients, banks, quoteType, sharedMatrix, distribution, onChange, cantidadCajas }) {
  // Validación de cuadre estricto de sucursales (Σ sucursales == cajas del RIF).
  const storeIssues = useMemo(() => {
    return (distribution || []).map((r) => {
      const ss = (r.stores || []).reduce((s, st) => s + (parseInt(st.boxes) || 0), 0);
      return ss !== (parseInt(r.boxes) || 0);
    });
  }, [distribution]);

  const setRifGrid = (rifIdx, newGrid) => {
    onChange((distribution || []).map((r, i) => i === rifIdx ? { ...r, boxes_grid: newGrid } : r));
  };

  return (
    <div className="space-y-4" data-testid="dp-multirif-section">
      <MultiRifDistributionPanel
        value={distribution}
        onChange={onChange}
        globalBoxes={cantidadCajas}
        clients={clients}
      />

      {/* Aviso de cuadre estricto de sucursales por RIF (Proyectos Directos exige
          que la Σ de cajas de las sucursales sea EXACTAMENTE igual a la del RIF). */}
      {(distribution || []).some((_, i) => storeIssues[i]) && (
        <div className="flex items-start gap-2 text-[12px] text-amber-800 bg-amber-50 border border-amber-200 rounded px-3 py-2" data-testid="dp-multirif-store-warning">
          <AlertCircle size={14} className="mt-0.5 shrink-0" />
          <span>Algún RIF tiene sucursales cuya suma de cajas <strong>no es igual</strong> a las cajas asignadas al RIF. El cuadre debe ser exacto para poder enviar a Implementación.</span>
        </div>
      )}

      {/* Matriz por RIF (solo cuando NO se comparte la configuración). */}
      {!sharedMatrix && (distribution || []).length > 0 && (
        <div className="rounded-lg border border-indigo-200 bg-indigo-50/30 p-4 space-y-3" data-testid="dp-multirif-matrix-block">
          <div className="flex items-center gap-2">
            <Layers size={16} className="text-indigo-600" />
            <h4 className="font-semibold text-sm text-indigo-800">Matriz de Implementación por RIF</h4>
            <span className="text-[11px] text-slate-500">Cada RIF maneja sus propios bancos y productos.</span>
          </div>
          {distribution.map((rif, i) => (
            <RifMatrixBuilder
              key={rif.client_id || i}
              rif={rif}
              banks={banks}
              quoteType={quoteType}
              onChange={(g) => setRifGrid(i, g)}
            />
          ))}
        </div>
      )}

      {sharedMatrix && (
        <div className="flex items-start gap-2 text-[12px] text-emerald-800 bg-emerald-50 border border-emerald-200 rounded px-3 py-2" data-testid="dp-multirif-shared-note">
          <CheckCircle2 size={14} className="mt-0.5 shrink-0" />
          <span>Matriz <strong>compartida</strong>: todas las tiendas usarán la configuración de Bancos/Productos definida en el <strong>Reel de Distribución</strong> de abajo.</span>
        </div>
      )}
    </div>
  );
}

export default DirectMultiRifSection;
