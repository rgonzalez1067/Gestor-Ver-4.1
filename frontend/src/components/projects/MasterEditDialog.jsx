import React, { useState, useEffect, useMemo, useCallback } from 'react';
import api from '../../utils/api';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Checkbox } from '../ui/checkbox';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../ui/select';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../ui/tabs';
import { toast } from 'sonner';
import { Pencil, Plus, Trash2, Landmark, Cpu, Store, AlertTriangle } from 'lucide-react';

// Catálogo oficial de estados (sincronizado con backend models.PROJECT_STATUSES).
const PROJECT_STATUSES = ['Por asignar', 'Asignado', 'En Gestión', 'Suspendido', 'Implementado parcial', 'Culminado', 'Anulado'];
const QUOTE_TYPES = [
  { value: 'VPOS', label: 'VPOS', flag: 'vpos_available' },
  { value: 'MPOS', label: 'MPOS', flag: 'mpos_available' },
  { value: 'GATEWAY', label: 'Payment Gateway', flag: 'gateway_available' },
  { value: 'LINK', label: 'Link de Pago', flag: 'link_available' },
];

const flagForType = (qt) => (QUOTE_TYPES.find(t => t.value === (qt || '').toUpperCase())?.flag) || 'vpos_available';

// Productos compatibles con el tipo de proyecto para un banco del catálogo.
const productsForBank = (banksCatalog, bankName, quoteType) => {
  const bank = banksCatalog.find(b => b.name === bankName);
  if (!bank) return [];
  const flag = flagForType(quoteType);
  return (bank.products || []).filter(p => p[flag]).map(p => p.product_name);
};

// Editor relacional: lista de bancos, cada uno con multi-selección de productos.
const BankProductsEditor = ({ value, onChange, banksCatalog, quoteType, testidPrefix }) => {
  const bankNames = banksCatalog.map(b => b.name);

  const updateBank = (idx, patch) => {
    const next = value.map((row, i) => (i === idx ? { ...row, ...patch } : row));
    onChange(next);
  };
  const removeBank = (idx) => onChange(value.filter((_, i) => i !== idx));
  const addBank = () => onChange([...value, { bank_name: '', products: [] }]);

  const toggleProduct = (idx, prod) => {
    const row = value[idx];
    const has = row.products.includes(prod);
    updateBank(idx, { products: has ? row.products.filter(p => p !== prod) : [...row.products, prod] });
  };

  return (
    <div className="space-y-3" data-testid={`${testidPrefix}-editor`}>
      {value.length === 0 && (
        <p className="text-xs text-slate-400 italic">Sin bancos de implementación. Agrega uno.</p>
      )}
      {value.map((row, idx) => {
        const opts = productsForBank(banksCatalog, row.bank_name, quoteType);
        // Conserva productos previos aunque ya no estén en el catálogo filtrado (override permisivo).
        const allOpts = Array.from(new Set([...opts, ...row.products]));
        return (
          <div key={idx} className="rounded-lg border border-slate-200 p-3 bg-slate-50/60" data-testid={`${testidPrefix}-row-${idx}`}>
            <div className="flex items-center gap-2 mb-2">
              <Landmark size={15} className="text-indigo-500 shrink-0" />
              <Select value={row.bank_name || undefined} onValueChange={(v) => updateBank(idx, { bank_name: v })}>
                <SelectTrigger className="flex-1 h-8 text-sm bg-white" data-testid={`${testidPrefix}-bank-select-${idx}`}>
                  <SelectValue placeholder="Seleccione un banco..." />
                </SelectTrigger>
                <SelectContent>
                  {bankNames.map(bn => <SelectItem key={bn} value={bn}>{bn}</SelectItem>)}
                </SelectContent>
              </Select>
              <Button type="button" size="sm" variant="ghost" onClick={() => removeBank(idx)}
                className="h-8 px-2 text-rose-500 hover:bg-rose-50" data-testid={`${testidPrefix}-remove-bank-${idx}`}>
                <Trash2 size={14} />
              </Button>
            </div>
            {row.bank_name && (
              <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 pl-1">
                {allOpts.length === 0 && (
                  <p className="col-span-2 text-xs text-amber-600">Este banco no tiene productos compatibles con el tipo seleccionado.</p>
                )}
                {allOpts.map(prod => (
                  <label key={prod} className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
                    <Checkbox checked={row.products.includes(prod)} onCheckedChange={() => toggleProduct(idx, prod)}
                      data-testid={`${testidPrefix}-product-${idx}-${prod.trim().replace(/\s+/g, '-').toLowerCase()}`} />
                    <span>{prod}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        );
      })}
      <Button type="button" size="sm" variant="outline" onClick={addBank}
        className="text-indigo-600 border-indigo-200 hover:bg-indigo-50" data-testid={`${testidPrefix}-add-bank`}>
        <Plus size={14} className="mr-1" />Agregar Banco
      </Button>
    </div>
  );
};

export const MasterEditDialog = ({ open, onOpenChange, project, onSaved }) => {
  const [banksCatalog, setBanksCatalog] = useState([]);
  const [hardwareCatalog, setHardwareCatalog] = useState([]);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(null);

  const isMultistore = project?.project_type === 'multistore';

  const matrixToRows = (matrix) =>
    Object.entries(matrix || {}).map(([bank_name, prods]) => ({ bank_name, products: Object.keys(prods || {}) }));

  const initForm = useCallback((p) => ({
    project_number: p.project_number || '',
    client_name: p.client_name || '',
    client_rif: p.client_rif || '',
    client_sede: p.client_sede || '',
    total_usd: p.total_usd ?? '',
    total_bs: p.total_bs ?? '',
    integrator_name: p.integrator_name || '',
    integrator_app_name: p.integrator_app_name || '',
    pinpad_model: p.pinpad_model || '',
    server_name: p.server_name || '',
    ticket_number: p.ticket_number || '',
    status: p.status || 'Por asignar',
    quote_type: (p.quote_type || 'VPOS').toUpperCase(),
    sponsoring_bank_name: p.sponsoring_bank_name || '',
    sponsoring_bank_id: p.sponsoring_bank_id || '',
    banks_products: matrixToRows(p.implementation_matrix),
    stores_products: (p.stores || []).map(s => ({
      store_id: s.store_id,
      name: s.name || s.store_id,
      banks_products: matrixToRows(s.implementation_matrix),
    })),
    hardware: (p.hardware || []).map(h => ({ hardware_id: h.hardware_id, name: h.name, type: h.type })),
  }), []);

  useEffect(() => {
    if (!open || !project) return;
    setForm(initForm(project));
    (async () => {
      try {
        const [b, h] = await Promise.all([
          api.get('/banks').catch(() => ({ data: [] })),
          api.get('/hardware').catch(() => ({ data: [] })),
        ]);
        setBanksCatalog(b.data || []);
        setHardwareCatalog(h.data || []);
      } catch { /* noop */ }
    })();
  }, [open, project, initForm]);

  const statusOptions = useMemo(() => {
    const cur = form?.status;
    return cur && !PROJECT_STATUSES.includes(cur) ? [cur, ...PROJECT_STATUSES] : PROJECT_STATUSES;
  }, [form?.status]);

  const set = (patch) => setForm(prev => ({ ...prev, ...patch }));

  const toggleHardware = (hw) => {
    const has = form.hardware.some(x => x.hardware_id === hw.hardware_id);
    set({ hardware: has ? form.hardware.filter(x => x.hardware_id !== hw.hardware_id) : [...form.hardware, { hardware_id: hw.hardware_id, name: hw.name, type: hw.type }] });
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = {
        project_number: form.project_number,
        client_name: form.client_name,
        client_rif: form.client_rif,
        client_sede: form.client_sede,
        total_usd: form.total_usd === '' ? null : Number(form.total_usd),
        total_bs: form.total_bs === '' ? null : Number(form.total_bs),
        integrator_name: form.integrator_name,
        integrator_app_name: form.integrator_app_name,
        pinpad_model: form.pinpad_model,
        server_name: form.server_name,
        ticket_number: form.ticket_number,
        status: form.status,
        quote_type: form.quote_type,
        sponsoring_bank_name: form.sponsoring_bank_name,
        sponsoring_bank_id: form.sponsoring_bank_id,
        hardware: form.hardware,
      };
      if (isMultistore) {
        payload.stores_products = form.stores_products.map(s => ({ store_id: s.store_id, banks_products: s.banks_products }));
      } else {
        payload.banks_products = form.banks_products;
      }
      await api.put(`/projects/${project.project_id}/master-override`, payload);
      toast.success('Proyecto actualizado (Edición Maestra)');
      onOpenChange(false);
      onSaved?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al guardar la edición maestra');
    } finally {
      setSaving(false);
    }
  };

  if (!form) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="master-edit-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Pencil size={18} className="text-slate-700" />
            Edición Maestra <span className="text-xs font-normal text-rose-600 bg-rose-50 px-2 py-0.5 rounded-full border border-rose-200">Super-Admin</span>
          </DialogTitle>
          <DialogDescription>
            Sobrescritura directa y sin restricciones de los datos del proyecto {project.project_number}. Los cambios reconstruyen las estructuras relacionales (bancos, productos y matriz).
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-2">
          {/* Datos Generales */}
          <section>
            <h3 className="text-sm font-semibold text-slate-800 mb-2">Datos Generales</h3>
            <div className="grid grid-cols-2 gap-3">
              {[
                ['project_number', 'Nro de Proyecto'],
                ['ticket_number', 'Nro de Ticket'],
                ['client_name', 'Cliente (Razón Social)'],
                ['client_rif', 'RIF'],
                ['client_sede', 'Sede'],
                ['server_name', 'Servidor'],
                ['integrator_name', 'Integrador'],
                ['integrator_app_name', 'App del Integrador'],
                ['pinpad_model', 'Modelo Pinpad'],
              ].map(([key, label]) => (
                <div key={key}>
                  <Label className="text-xs">{label}</Label>
                  <Input value={form[key]} onChange={e => set({ [key]: e.target.value })}
                    className="mt-1 h-8 text-sm" data-testid={`master-field-${key}`} />
                </div>
              ))}
              <div>
                <Label className="text-xs">Total USD</Label>
                <Input type="number" value={form.total_usd} onChange={e => set({ total_usd: e.target.value })}
                  className="mt-1 h-8 text-sm" data-testid="master-field-total_usd" />
              </div>
              <div>
                <Label className="text-xs">Total Bs</Label>
                <Input type="number" value={form.total_bs} onChange={e => set({ total_bs: e.target.value })}
                  className="mt-1 h-8 text-sm" data-testid="master-field-total_bs" />
              </div>
            </div>
          </section>

          {/* Clasificación (dropdowns) */}
          <section>
            <h3 className="text-sm font-semibold text-slate-800 mb-2">Clasificación</h3>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label className="text-xs">Estado del Proyecto</Label>
                <Select value={form.status} onValueChange={v => set({ status: v })}>
                  <SelectTrigger className="mt-1 h-8 text-sm" data-testid="master-status-select"><SelectValue /></SelectTrigger>
                  <SelectContent>{statusOptions.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs">Tipo de Proyecto</Label>
                <Select value={form.quote_type} onValueChange={v => set({ quote_type: v })}>
                  <SelectTrigger className="mt-1 h-8 text-sm" data-testid="master-type-select"><SelectValue /></SelectTrigger>
                  <SelectContent>{QUOTE_TYPES.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs">Banco Patrocinador</Label>
                <Select value={form.sponsoring_bank_name || '__none__'}
                  onValueChange={v => {
                    if (v === '__none__') { set({ sponsoring_bank_name: '', sponsoring_bank_id: '' }); return; }
                    const bk = banksCatalog.find(b => b.name === v);
                    set({ sponsoring_bank_name: v, sponsoring_bank_id: bk?.bank_id || '' });
                  }}>
                  <SelectTrigger className="mt-1 h-8 text-sm" data-testid="master-sponsor-select"><SelectValue placeholder="Ninguno" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">— Ninguno —</SelectItem>
                    {banksCatalog.map(b => <SelectItem key={b.bank_id} value={b.name}>{b.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </section>

          {/* Banco(s) ↔ Productos */}
          <section>
            <h3 className="text-sm font-semibold text-slate-800 mb-1 flex items-center gap-2">
              Banco(s) de Implementación y Productos
              {isMultistore && <span className="inline-flex items-center gap-1 text-[10px] font-medium text-blue-700 bg-blue-50 border border-blue-200 px-1.5 py-0.5 rounded"><Store size={10} />Multitienda</span>}
            </h3>
            <p className="text-xs text-slate-400 mb-2">Los productos se filtran por el Tipo de Proyecto seleccionado.</p>
            {isMultistore ? (
              form.stores_products.length === 0 ? (
                <p className="text-xs text-slate-400 italic">Este proyecto multitienda no tiene tiendas registradas.</p>
              ) : (
                <Tabs defaultValue={form.stores_products[0].store_id} className="w-full">
                  <TabsList className="flex-wrap h-auto">
                    {form.stores_products.map(s => (
                      <TabsTrigger key={s.store_id} value={s.store_id} className="text-xs" data-testid={`master-store-tab-${s.store_id}`}>{s.name}</TabsTrigger>
                    ))}
                  </TabsList>
                  {form.stores_products.map((s, sIdx) => (
                    <TabsContent key={s.store_id} value={s.store_id} className="mt-3">
                      <BankProductsEditor
                        value={s.banks_products}
                        onChange={(next) => {
                          const stores = form.stores_products.map((x, i) => i === sIdx ? { ...x, banks_products: next } : x);
                          set({ stores_products: stores });
                        }}
                        banksCatalog={banksCatalog}
                        quoteType={form.quote_type}
                        testidPrefix={`master-store-${sIdx}`}
                      />
                    </TabsContent>
                  ))}
                </Tabs>
              )
            ) : (
              <BankProductsEditor
                value={form.banks_products}
                onChange={(next) => set({ banks_products: next })}
                banksCatalog={banksCatalog}
                quoteType={form.quote_type}
                testidPrefix="master-single"
              />
            )}
          </section>

          {/* Hardware */}
          <section>
            <h3 className="text-sm font-semibold text-slate-800 mb-2 flex items-center gap-2"><Cpu size={15} className="text-slate-500" />Hardware (Dispositivos)</h3>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 max-h-44 overflow-y-auto rounded-lg border border-slate-200 p-3" data-testid="master-hardware-list">
              {hardwareCatalog.length === 0 && <p className="text-xs text-slate-400 italic col-span-2">Sin hardware en el catálogo.</p>}
              {hardwareCatalog.map(hw => (
                <label key={hw.hardware_id} className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
                  <Checkbox checked={form.hardware.some(x => x.hardware_id === hw.hardware_id)} onCheckedChange={() => toggleHardware(hw)}
                    data-testid={`master-hardware-${hw.hardware_id}`} />
                  <span>{hw.name} <span className="text-slate-400">({hw.type})</span></span>
                </label>
              ))}
            </div>
          </section>

          <div className="flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 p-2.5 text-amber-800">
            <AlertTriangle size={15} className="mt-0.5 shrink-0" />
            <span className="text-xs">Esta acción sobrescribe directamente los datos del proyecto y reconstruye sus relaciones. Verifica antes de guardar.</span>
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-2 border-t">
          <Button variant="outline" onClick={() => onOpenChange(false)} data-testid="master-cancel-btn">Cancelar</Button>
          <Button onClick={handleSave} disabled={saving} className="bg-slate-800 hover:bg-slate-900 text-white" data-testid="master-save-btn">
            {saving ? 'Guardando...' : 'Guardar Override'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
