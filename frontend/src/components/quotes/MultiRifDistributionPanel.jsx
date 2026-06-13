import { useState, useMemo } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import { Plus, Trash2, Store, Building2, AlertCircle, CheckCircle2, Search, X } from 'lucide-react';

/**
 * Motor de distribución anidada VPOS Multi-RIF: Global → RIF (Cliente) → Tienda/Sucursal.
 * Reglas ("Reel"):
 *  - Σ cajas de Tiendas (N3) ≤ cajas del RIF (N2).
 *  - Σ cajas de RIFs (N2) ≤ Cajas Globales (N1).
 *  - El guardado se bloquea hasta distribuir el 100% de las cajas globales.
 *
 * value: [{ client_id, rif, client_name, boxes, stores: [{ name, boxes }] }]
 */
const sumStores = (rif) => (rif.stores || []).reduce((s, st) => s + (parseInt(st.boxes) || 0), 0);
const sumRifs = (dist) => (dist || []).reduce((s, r) => s + (parseInt(r.boxes) || 0), 0);

export const validateMultiRif = (dist, globalBoxes) => {
  const total = parseInt(globalBoxes) || 0;
  const assigned = sumRifs(dist);
  const errors = [];
  if (!dist || dist.length === 0) errors.push('Debe agregar al menos un Cliente/RIF.');
  (dist || []).forEach((r, i) => {
    if (!r.client_id) errors.push(`RIF #${i + 1}: seleccione un cliente.`);
    const ss = sumStores(r);
    if (ss > (parseInt(r.boxes) || 0)) {
      errors.push(`${r.client_name || 'RIF #' + (i + 1)}: las cajas de sus sucursales (${ss}) superan sus cajas asignadas (${r.boxes || 0}).`);
    }
  });
  if (assigned > total) errors.push(`Las cajas asignadas a los RIFs (${assigned}) superan las Cajas Globales (${total}).`);
  const fullyDistributed = total > 0 && assigned === total;
  return { valid: errors.length === 0 && fullyDistributed, assigned, total, fullyDistributed, errors };
};

const ClientSearch = ({ clients, onPick, onCancel }) => {
  const [q, setQ] = useState('');
  const results = useMemo(() => {
    if (q.trim().length < 2) return [];
    const t = q.toLowerCase();
    return (clients || []).filter(c =>
      (c.legal_name || '').toLowerCase().includes(t) ||
      (c.fantasy_name || '').toLowerCase().includes(t) ||
      (c.rif || '').toLowerCase().includes(t)
    ).slice(0, 8);
  }, [q, clients]);
  return (
    <div className="relative flex-1">
      <div className="flex items-center gap-1">
        <Search size={13} className="text-slate-400 shrink-0" />
        <Input autoFocus value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Buscar cliente por nombre o RIF…" className="h-8 text-xs"
          data-testid="multirif-client-search-input" />
        <Button type="button" size="sm" variant="ghost" onClick={onCancel} className="h-7 w-7 p-0 text-slate-400"><X size={13} /></Button>
      </div>
      {results.length > 0 && (
        <div className="absolute z-20 mt-1 w-full bg-white border border-slate-200 rounded-md shadow-lg max-h-52 overflow-y-auto">
          {results.map(c => (
            <button key={c.client_id} type="button"
              onClick={() => onPick(c)}
              className="w-full text-left px-2.5 py-1.5 text-xs hover:bg-blue-50 border-b border-slate-100 last:border-0"
              data-testid={`multirif-client-option-${c.client_id}`}>
              <span className="font-medium text-slate-700">{c.fantasy_name || c.legal_name}</span>
              <span className="text-slate-400"> — {c.rif}</span>
            </button>
          ))}
        </div>
      )}
      {q.trim().length >= 2 && results.length === 0 && (
        <p className="text-[11px] text-slate-400 mt-1 ml-5">Sin coincidencias.</p>
      )}
    </div>
  );
};

export const MultiRifDistributionPanel = ({ value = [], onChange, globalBoxes = 0, clients = [] }) => {
  const [expanded, setExpanded] = useState(value.length > 0);
  const [searchingIdx, setSearchingIdx] = useState(null); // índice del RIF buscando cliente

  const { assigned, total, fullyDistributed } = validateMultiRif(value, globalBoxes);
  const pct = total > 0 ? Math.min(100, Math.round((assigned / total) * 100)) : 0;
  const over = assigned > total;

  const update = (next) => onChange(next);
  const addRif = () => { update([...value, { client_id: '', rif: '', client_name: '', boxes: 1, stores: [] }]); setSearchingIdx(value.length); };
  const removeRif = (i) => update(value.filter((_, idx) => idx !== i));
  const setRif = (i, patch) => update(value.map((r, idx) => idx === i ? { ...r, ...patch } : r));
  const addStore = (i) => setRif(i, { stores: [...(value[i].stores || []), { name: '', boxes: 1 }] });
  const removeStore = (i, si) => setRif(i, { stores: value[i].stores.filter((_, x) => x !== si) });
  const setStore = (i, si, patch) => setRif(i, { stores: value[i].stores.map((s, x) => x === si ? { ...s, ...patch } : s) });

  if (!expanded) {
    return (
      <div className="mt-4">
        <Button type="button" variant="outline" onClick={() => { setExpanded(true); if (value.length === 0) addRif(); }}
          className="border-dashed border-indigo-300 text-indigo-600 hover:bg-indigo-50" data-testid="btn-expand-multirif">
          <Building2 size={16} className="mr-2" />
          + Detalle de Tiendas/Sucursales (Multi-RIF)
        </Button>
        <p className="text-[10px] text-slate-400 mt-1 ml-1">Distribuya el lote global entre clientes (RIF) y sus sucursales.</p>
      </div>
    );
  }

  return (
    <div className="mt-4 border border-indigo-200 rounded-lg bg-indigo-50/30 p-4" data-testid="multirif-distribution-panel">
      {/* Encabezado + barra de progreso en vivo */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Building2 size={18} className="text-indigo-600" />
          <h4 className="font-semibold text-sm text-indigo-800">Distribución Multi-RIF</h4>
          <Badge variant="outline" className={`text-xs ${fullyDistributed ? 'border-green-400 text-green-700' : over ? 'border-red-400 text-red-700' : 'border-amber-400 text-amber-700'}`} data-testid="multirif-progress-badge">
            {assigned} / {total} cajas
            {fullyDistributed && <CheckCircle2 size={11} className="ml-1" />}
          </Badge>
        </div>
        <div className="flex gap-2">
          <Button type="button" size="sm" variant="outline" onClick={addRif}
            className="h-7 text-xs border-indigo-300 text-indigo-600" data-testid="btn-add-rif">
            <Plus size={12} className="mr-1" />Cliente/RIF
          </Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => { setExpanded(false); onChange([]); }}
            className="h-7 text-xs text-slate-400 hover:text-red-500">Quitar</Button>
        </div>
      </div>

      {/* Barra de progreso */}
      <div className="mb-3" data-testid="multirif-progress-bar">
        <div className="h-2.5 w-full bg-slate-200 rounded-full overflow-hidden">
          <div className={`h-full rounded-full transition-all duration-300 ${over ? 'bg-red-500' : fullyDistributed ? 'bg-emerald-500' : 'bg-blue-500'}`}
            style={{ width: `${over ? 100 : pct}%` }} />
        </div>
        <p className={`text-[11px] mt-1 font-medium ${over ? 'text-red-600' : fullyDistributed ? 'text-emerald-700' : 'text-slate-500'}`}>
          {over ? `Excede el lote global por ${assigned - total} caja(s).` : fullyDistributed ? '¡Lote distribuido al 100%!' : `Faltan ${total - assigned} caja(s) por distribuir.`}
        </p>
      </div>

      {/* Lista de RIFs */}
      <div className="space-y-3 max-h-[360px] overflow-y-auto pr-1">
        {value.map((rif, i) => {
          const ss = sumStores(rif);
          const rifOver = ss > (parseInt(rif.boxes) || 0);
          return (
            <div key={i} className="rounded-lg border border-slate-200 bg-white p-3" data-testid={`multirif-rif-${i}`}>
              <div className="flex items-center gap-2 mb-2">
                {searchingIdx === i || !rif.client_id ? (
                  <ClientSearch clients={clients}
                    onPick={(c) => { setRif(i, { client_id: c.client_id, rif: c.rif, client_name: c.fantasy_name || c.legal_name }); setSearchingIdx(null); }}
                    onCancel={() => setSearchingIdx(null)} />
                ) : (
                  <button type="button" onClick={() => setSearchingIdx(i)}
                    className="flex-1 text-left text-sm font-medium text-slate-700 hover:text-indigo-600" data-testid={`multirif-rif-name-${i}`}>
                    {rif.client_name} <span className="text-slate-400 font-normal">— {rif.rif}</span>
                  </button>
                )}
                <div className="flex items-center gap-1 shrink-0">
                  <Label className="text-[10px] text-slate-500">Cajas RIF</Label>
                  <Input type="number" min={1} value={rif.boxes}
                    onChange={(e) => setRif(i, { boxes: e.target.value === '' ? '' : parseInt(e.target.value) })}
                    className="h-8 w-16 text-xs text-center" data-testid={`multirif-rif-boxes-${i}`} />
                </div>
                <Button type="button" size="sm" variant="ghost" onClick={() => removeRif(i)}
                  className="h-8 w-8 p-0 text-slate-300 hover:text-red-500"><Trash2 size={13} /></Button>
              </div>

              {rifOver && (
                <div className="flex items-center gap-1.5 text-[11px] text-red-600 bg-red-50 border border-red-200 rounded px-2 py-1 mb-2" data-testid={`multirif-rif-error-${i}`}>
                  <AlertCircle size={12} />Sucursales ({ss}) &gt; cajas del RIF ({rif.boxes || 0}).
                </div>
              )}

              {/* Sucursales (N3) */}
              <div className="pl-3 border-l-2 border-indigo-100 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-slate-500 flex items-center gap-1"><Store size={11} />Sucursales ({ss}/{rif.boxes || 0})</span>
                  <Button type="button" size="sm" variant="ghost" onClick={() => addStore(i)}
                    className="h-6 text-[11px] text-indigo-600 hover:bg-indigo-50" data-testid={`btn-add-store-${i}`}>
                    <Plus size={11} className="mr-0.5" />Sucursal
                  </Button>
                </div>
                {(rif.stores || []).map((st, si) => (
                  <div key={si} className="grid grid-cols-[1fr_70px_28px] gap-2 items-center" data-testid={`multirif-store-${i}-${si}`}>
                    <Input value={st.name} onChange={(e) => setStore(i, si, { name: e.target.value })}
                      placeholder={`Sucursal ${si + 1}`} className="h-7 text-xs" data-testid={`multirif-store-name-${i}-${si}`} />
                    <Input type="number" min={1} value={st.boxes}
                      onChange={(e) => setStore(i, si, { boxes: e.target.value === '' ? '' : parseInt(e.target.value) })}
                      className="h-7 text-xs text-center" data-testid={`multirif-store-boxes-${i}-${si}`} />
                    <Button type="button" size="sm" variant="ghost" onClick={() => removeStore(i, si)}
                      className="h-7 w-7 p-0 text-slate-300 hover:text-red-500"><Trash2 size={12} /></Button>
                  </div>
                ))}
                {(rif.stores || []).length === 0 && (
                  <p className="text-[11px] text-slate-400 py-1">Sin sucursales. Agregue al menos una.</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default MultiRifDistributionPanel;
