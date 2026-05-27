import { useState, useEffect, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Plus, Trash2, Save, Upload, FileSpreadsheet, Building2, Boxes, Loader2, FileDown, Search, X, CheckCircle2, AlertCircle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Switch } from '../components/ui/switch';
import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { toast } from 'sonner';
import api from '../utils/api';
import { usePermission } from '../hooks/usePermission';

const QUOTE_TYPES = [
  { id: 'VPOS', label: 'VPOS', avail: 'vpos_available' },
  { id: 'MPOS', label: 'MPOS', avail: 'mpos_available' },
  { id: 'GATEWAY', label: 'Payment Gateway', avail: 'gateway_available' },
  { id: 'LINK_PAGO', label: 'Link de Pago', avail: 'link_available' },
];
const REQUIRES_HW = (qt) => qt === 'VPOS' || qt === 'MPOS';
const AVAIL_FIELD = (qt) => (QUOTE_TYPES.find((x) => x.id === qt) || {}).avail || 'vpos_available';

/* ------------------------------------------------------------------ */
/* Combobox de clientes con búsqueda                                  */
/* ------------------------------------------------------------------ */
function ClientCombobox({ clients, value, onChange }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, [open]);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return clients.slice(0, 50);
    return clients.filter((c) =>
      (c.fantasy_name || '').toLowerCase().includes(s) ||
      (c.legal_name || '').toLowerCase().includes(s) ||
      (c.rif || '').toLowerCase().includes(s)
    ).slice(0, 50);
  }, [clients, q]);

  const selected = clients.find((c) => c.client_id === value);

  return (
    <div className="relative" ref={ref} data-testid="dp-client-combobox">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full h-10 px-3 border border-slate-200 rounded-md bg-white text-left text-sm hover:border-slate-300 focus:border-blue-500 focus:outline-none flex items-center justify-between"
      >
        <span className={selected ? 'text-slate-900 truncate' : 'text-slate-400'}>
          {selected ? (selected.legal_name || selected.fantasy_name) : 'Seleccionar cliente...'}
        </span>
        <Search size={16} className="text-slate-400 flex-shrink-0" />
      </button>
      {open && (
        <div className="absolute z-50 mt-1 w-full max-h-72 bg-white border border-slate-200 rounded-md shadow-xl flex flex-col">
          <div className="p-2 border-b border-slate-100">
            <Input
              autoFocus
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Buscar por nombre, fantasy o RIF..."
              className="h-9"
              data-testid="dp-client-search"
            />
          </div>
          <div className="overflow-y-auto flex-1 py-1">
            {filtered.length === 0 ? (
              <div className="px-3 py-4 text-xs text-slate-400 text-center">Sin resultados</div>
            ) : filtered.map((c) => (
              <button
                key={c.client_id}
                type="button"
                onClick={() => { onChange(c.client_id); setOpen(false); setQ(''); }}
                className="w-full text-left px-3 py-2 hover:bg-blue-50 text-sm border-b border-slate-50 last:border-b-0"
                data-testid={`dp-client-opt-${c.client_id}`}
              >
                <div className="font-medium text-slate-800 truncate">{c.legal_name || c.fantasy_name}</div>
                <div className="text-xs text-slate-500 truncate">{c.fantasy_name || ''} · {c.rif || 'sin RIF'}</div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Excel uploader (descarga plantilla + upload + entrega items)       */
/* ------------------------------------------------------------------ */
function ExcelUploader({ kind, onParsed, testIdPrefix }) {
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);

  const downloadTemplate = async () => {
    try {
      const res = await api.get(`/direct-projects/excel-templates/${kind}`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = kind === 'serials' ? 'plantilla_seriales.xlsx' : 'plantilla_sucursales.xlsx';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      toast.error(`Error descargando plantilla: ${e.response?.data?.detail || e.message}`);
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await api.post(`/direct-projects/excel-parse/${kind}`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const items = res.data?.items || [];
      const errors = res.data?.errors || [];
      if (items.length === 0 && errors.length) {
        toast.error(`Excel sin filas válidas. ${errors[0]}`);
      } else if (errors.length) {
        toast.warning(`Cargadas ${items.length} fila(s) con ${errors.length} aviso(s)`);
      } else {
        toast.success(`${items.length} fila(s) cargada(s) desde Excel`);
      }
      onParsed(items, errors);
    } catch (err) {
      toast.error(`Error al parsear Excel: ${err.response?.data?.detail || err.message}`);
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  return (
    <div className="flex items-center gap-2">
      <Button variant="outline" size="sm" onClick={downloadTemplate} data-testid={`${testIdPrefix}-download-tpl`}>
        <FileDown size={14} className="mr-1" /> Plantilla
      </Button>
      <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} disabled={busy} data-testid={`${testIdPrefix}-upload`}>
        {busy ? <Loader2 size={14} className="mr-1 animate-spin" /> : <Upload size={14} className="mr-1" />}
        Cargar Excel
      </Button>
      <input ref={fileRef} type="file" accept=".xlsx" onChange={handleUpload} className="hidden" data-testid={`${testIdPrefix}-file-input`} />
    </div>
  );
}

/* ================================================================== */
/* Página principal                                                   */
/* ================================================================== */
export default function DirectProjectCreation() {
  const navigate = useNavigate();
  const { canEdit, isAdmin } = usePermission('proyectos_directos');

  const [clients, setClients] = useState([]);
  const [banks, setBanks] = useState([]);
  const [integrators, setIntegrators] = useState([]);  // array plano de docs
  const [hardware, setHardware] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  /* Form state */
  const [form, setForm] = useState({
    client_id: '',
    economic_group: '',
    fantasy_name: '',
    quote_type: 'VPOS',
    sede: 'PYME',
    cantidad_cajas: 1,
    sponsor_bank_id: '',
    sponsor_bank_name: '',
    integrator_name: '',          // primer dropdown (nombre del integrador)
    integrator_id: '',            // se llena al elegir la app específica (cascada)
    integrator_app_name: '',      // segundo dropdown (app del integrador)
    pinpad_model: '',
    pinpad_bank: '',
    fiscal_printer_model: '',
    pinpad_serials: [],
    is_multistore: false,
    stores: [],
    // Reel: cada fila es { quantity, bank_name, product_name, store_name? }
    boxes_grid: [{ quantity: 1, bank_name: '', product_name: '', store_name: '' }],
    implementation_instructions: '',
  });

  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  /* Carga inicial */
  useEffect(() => {
    const fetchAll = async () => {
      setLoading(true);
      try {
        const [cRes, bRes, iRes, hRes] = await Promise.all([
          api.get('/clients'),
          api.get('/banks'),
          api.get('/integrators'),
          api.get('/hardware'),
        ]);
        const sortedClients = [...(cRes.data || [])].sort((a, b) =>
          (a.fantasy_name || a.legal_name || '').localeCompare(b.fantasy_name || b.legal_name || '', 'es', { sensitivity: 'base' })
        );
        setClients(sortedClients);
        setBanks(bRes.data || []);
        setIntegrators(iRes.data || []);
        setHardware(hRes.data || []);
      } catch (e) {
        toast.error(`Error cargando datos: ${e.response?.data?.detail || e.message}`);
      } finally { setLoading(false); }
    };
    fetchAll();
  }, []);

  /* Auto-completar cliente */
  useEffect(() => {
    if (!form.client_id) return;
    const c = clients.find((x) => x.client_id === form.client_id);
    if (!c) return;
    set({
      economic_group: c.economic_group || c.grupo_economico || '',
      fantasy_name: c.fantasy_name || '',
      sede: (c.client_segment || c.sede || 'PYME').toUpperCase(),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.client_id]);

  /* Helpers grilla (reel) */
  const updateBox = (idx, patch) => {
    setForm((f) => {
      const next = [...f.boxes_grid];
      // Al cambiar el banco, limpiar el producto seleccionado (puede no existir en el nuevo banco)
      if (patch.bank_name !== undefined && patch.bank_name !== next[idx].bank_name) {
        next[idx] = { ...next[idx], ...patch, product_name: '' };
      } else {
        next[idx] = { ...next[idx], ...patch };
      }
      return { ...f, boxes_grid: next };
    });
  };
  const addBoxRow = () => set({ boxes_grid: [...form.boxes_grid, { quantity: 1, bank_name: '', product_name: '', store_name: '' }] });
  const removeBoxRow = (idx) => set({ boxes_grid: form.boxes_grid.filter((_, i) => i !== idx) });

  const totalBoxesInGrid = useMemo(
    () => form.boxes_grid.reduce((acc, b) => acc + (parseInt(b.quantity) || 0), 0),
    [form.boxes_grid]
  );

  /* Productos disponibles para una fila según banco seleccionado + tipo de proyecto */
  const productsForBank = (bankName) => {
    if (!bankName) return [];
    const bank = banks.find((b) => b.name === bankName);
    if (!bank || !Array.isArray(bank.products)) return [];
    const availField = AVAIL_FIELD(form.quote_type);
    return bank.products.filter((p) => !!p[availField]);
  };

  /* Multitienda */
  const addStore = () => set({ stores: [...form.stores, { name: '', box_count: 1 }] });
  const removeStore = (idx) => set({ stores: form.stores.filter((_, i) => i !== idx) });
  const updateStore = (idx, patch) => {
    const next = [...form.stores];
    next[idx] = { ...next[idx], ...patch };
    set({ stores: next });
  };
  const totalStoreBoxes = useMemo(() => form.stores.reduce((acc, s) => acc + (parseInt(s.box_count) || 0), 0), [form.stores]);

  /* Seriales Pinpad */
  const addSerial = () => set({ pinpad_serials: [...form.pinpad_serials, { modelo: form.pinpad_model || '', serial: '' }] });
  const removeSerial = (idx) => set({ pinpad_serials: form.pinpad_serials.filter((_, i) => i !== idx) });
  const updateSerial = (idx, patch) => {
    const next = [...form.pinpad_serials];
    next[idx] = { ...next[idx], ...patch };
    set({ pinpad_serials: next });
  };
  const clearSerials = () => set({ pinpad_serials: [] });

  /* Cascada Integrador → Apps */
  const integratorNames = useMemo(() => {
    const names = Array.from(new Set(integrators.map((i) => i.name).filter(Boolean)));
    return names.sort((a, b) => a.localeCompare(b, 'es', { sensitivity: 'base' }));
  }, [integrators]);

  const appsForIntegrator = useMemo(() => {
    if (!form.integrator_name) return [];
    return integrators.filter((i) => i.name === form.integrator_name && (i.app_name || '').trim());
  }, [integrators, form.integrator_name]);

  /* Pinpad models — solo Bien + Pinpad/POS */
  const pinpadModels = useMemo(() => {
    return hardware
      .filter((h) => (h.asset_type === 'Bien') && (h.type === 'Pinpad' || h.type === 'POS'))
      .map((h) => ({ value: h.name, label: h.name, type: h.type }))
      .sort((a, b) => a.label.localeCompare(b.label, 'es', { sensitivity: 'base' }));
  }, [hardware]);

  /* Validación pre-envío */
  const errors = useMemo(() => {
    const errs = [];
    if (!form.client_id) errs.push('Debes seleccionar un cliente');
    if (!form.quote_type) errs.push('Debes seleccionar el tipo de proyecto');
    if (!form.cantidad_cajas || form.cantidad_cajas < 1) errs.push('Cantidad de cajas debe ser >= 1');
    if (REQUIRES_HW(form.quote_type) && !form.pinpad_model) errs.push('VPOS/MPOS requiere Modelo de Pinpad');
    if (form.is_multistore) {
      if (form.stores.length === 0) errs.push('Multitienda activado: agrega al menos una sucursal');
      if (totalStoreBoxes !== Number(form.cantidad_cajas)) {
        errs.push(`Suma de cajas por sucursal (${totalStoreBoxes}) ≠ Cantidad de Cajas (${form.cantidad_cajas})`);
      }
    }
    if (form.boxes_grid.length === 0) {
      errs.push('Agrega al menos una fila a la grilla');
    } else {
      if (totalBoxesInGrid !== Number(form.cantidad_cajas)) {
        errs.push(`Suma de cajas en la grilla (${totalBoxesInGrid}) ≠ Cantidad de Cajas (${form.cantidad_cajas})`);
      }
      form.boxes_grid.forEach((b, i) => {
        if (!b.bank_name) errs.push(`Fila #${i + 1}: banco requerido`);
        if (!b.product_name) errs.push(`Fila #${i + 1}: producto requerido`);
        if (!b.quantity || b.quantity < 1) errs.push(`Fila #${i + 1}: cantidad >= 1`);
      });
    }
    return errs;
  }, [form, totalStoreBoxes, totalBoxesInGrid]);

  const handleSubmit = async () => {
    if (errors.length) {
      toast.error(`Hay ${errors.length} error(es) en el formulario. Revisa.`);
      return;
    }
    setSaving(true);
    try {
      const payload = { ...form, cantidad_cajas: Number(form.cantidad_cajas) };
      delete payload.equipment_serials;  // ya no aplica
      if (form.sponsor_bank_id && !form.sponsor_bank_name) {
        const b = banks.find((x) => x.bank_id === form.sponsor_bank_id);
        if (b) payload.sponsor_bank_name = b.name;
      }
      const res = await api.post('/direct-projects', payload);
      const d = res.data;
      toast.success(`Proyecto ${d.project_number} creado ${d.notification?.dispatched ? '· correo enviado' : '· sin notificación configurada'}`);
      navigate(`/projects/${d.project_id}`);
    } catch (e) {
      toast.error(`Error: ${e.response?.data?.detail || e.message}`);
    } finally { setSaving(false); }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64"><Loader2 size={32} className="animate-spin text-blue-600" /></div>;
  }

  if (!canEdit && !isAdmin) {
    return (
      <div className="max-w-2xl mx-auto p-8 text-center">
        <h2 className="text-xl font-semibold text-slate-700">Acceso restringido</h2>
        <p className="text-slate-500 mt-2">No tienes permisos de edición en el módulo Proyectos Directos.</p>
        <Button className="mt-4" onClick={() => navigate('/projects')}>Volver a Proyectos</Button>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto p-4 lg:p-6 space-y-5" data-testid="direct-project-page">
      <div className="flex items-center justify-between gap-3">
        <Button variant="ghost" size="sm" onClick={() => navigate('/projects')} data-testid="dp-back-btn">
          <ArrowLeft size={18} className="mr-1" /> Proyectos
        </Button>
        <div className="text-right">
          <h1 className="text-2xl font-bold text-slate-900">Proyecto Directo</h1>
          <p className="text-xs text-slate-500">Implementación sin cotización previa</p>
        </div>
      </div>

      {/* Card 1: Cliente */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2"><Building2 size={18} /> Datos del Cliente</CardTitle>
          <CardDescription className="text-xs">Selecciona el cliente; Grupo Económico y Nombre de Fantasía se auto-completan y son editables.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="md:col-span-1">
              <Label className="text-xs">Cliente *</Label>
              <ClientCombobox clients={clients} value={form.client_id} onChange={(v) => set({ client_id: v })} />
            </div>
            <div>
              <Label className="text-xs">Grupo Económico</Label>
              <Input value={form.economic_group} onChange={(e) => set({ economic_group: e.target.value })} data-testid="dp-economic-group" placeholder="Editable" />
            </div>
            <div>
              <Label className="text-xs">Nombre de Fantasía</Label>
              <Input value={form.fantasy_name} onChange={(e) => set({ fantasy_name: e.target.value })} data-testid="dp-fantasy-name" placeholder="Editable" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Card 2: Definición comercial */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Definición Comercial</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div>
              <Label className="text-xs">Tipo de Proyecto *</Label>
              <Select value={form.quote_type} onValueChange={(v) => set({ quote_type: v, boxes_grid: form.boxes_grid.map((b) => ({ ...b, product_name: '' })) })}>
                <SelectTrigger className="h-10" data-testid="dp-quote-type"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {QUOTE_TYPES.map((qt) => <SelectItem key={qt.id} value={qt.id}>{qt.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Sede</Label>
              <Select value={form.sede} onValueChange={(v) => set({ sede: v })}>
                <SelectTrigger className="h-10" data-testid="dp-sede"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="PYME">PYME</SelectItem>
                  <SelectItem value="CORP">CORP</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Cantidad de Cajas *</Label>
              <Input type="number" min="1" value={form.cantidad_cajas}
                     onChange={(e) => set({ cantidad_cajas: e.target.value === '' ? '' : Math.max(1, parseInt(e.target.value) || 1) })}
                     data-testid="dp-cantidad-cajas" />
            </div>
            <div>
              <Label className="text-xs">Banco Patrocinante</Label>
              <Select value={form.sponsor_bank_id || ''} onValueChange={(v) => {
                const b = banks.find((x) => x.bank_id === v);
                set({ sponsor_bank_id: v, sponsor_bank_name: b?.name || '' });
              }}>
                <SelectTrigger className="h-10" data-testid="dp-sponsor-bank"><SelectValue placeholder="Sin banco" /></SelectTrigger>
                <SelectContent>
                  {banks.map((b) => <SelectItem key={b.bank_id} value={b.bank_id}>{b.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            {/* Cascada Integrador → App */}
            <div>
              <Label className="text-xs">Integrador</Label>
              <Select value={form.integrator_name || ''} onValueChange={(v) => set({ integrator_name: v, integrator_app_name: '', integrator_id: '' })}>
                <SelectTrigger className="h-10" data-testid="dp-integrator"><SelectValue placeholder="Sin integrador" /></SelectTrigger>
                <SelectContent>
                  {integratorNames.map((n) => <SelectItem key={n} value={n}>{n}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Aplicación {form.integrator_name && <span className="text-amber-600">({appsForIntegrator.length})</span>}</Label>
              <Select
                value={form.integrator_id || ''}
                onValueChange={(integratorId) => {
                  const apt = integrators.find((i) => i.integrator_id === integratorId);
                  set({ integrator_id: integratorId, integrator_app_name: apt?.app_name || '' });
                }}
                disabled={!form.integrator_name || appsForIntegrator.length === 0}
              >
                <SelectTrigger className="h-10" data-testid="dp-integrator-app">
                  <SelectValue placeholder={!form.integrator_name ? 'Elige integrador primero' : (appsForIntegrator.length === 0 ? 'Sin apps registradas' : 'Seleccionar app...')} />
                </SelectTrigger>
                <SelectContent>
                  {appsForIntegrator.map((i) => <SelectItem key={i.integrator_id} value={i.integrator_id}>{i.app_name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Card 3: HW (solo VPOS/MPOS) */}
      {REQUIRES_HW(form.quote_type) && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Hardware <span className="text-xs font-normal text-slate-500">(solo VPOS/MPOS)</span></CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <Label className="text-xs">Modelo Pinpad *</Label>
                <Select value={form.pinpad_model} onValueChange={(v) => set({ pinpad_model: v })}>
                  <SelectTrigger className="h-10" data-testid="dp-pinpad-model">
                    <SelectValue placeholder="Seleccionar pinpad..." />
                  </SelectTrigger>
                  <SelectContent className="max-h-72">
                    {pinpadModels.length === 0 ? (
                      <div className="px-3 py-2 text-xs text-slate-400 italic">Sin modelos de Pinpad/POS marcados como Bien en el catálogo</div>
                    ) : pinpadModels.map((m) => (
                      <SelectItem key={m.value} value={m.value}>
                        {m.label} <span className="text-xs text-slate-400 ml-1">[{m.type}]</span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs">Banco del Pinpad</Label>
                <Select value={form.pinpad_bank || ''} onValueChange={(v) => set({ pinpad_bank: v })}>
                  <SelectTrigger className="h-10" data-testid="dp-pinpad-bank"><SelectValue placeholder="Seleccionar" /></SelectTrigger>
                  <SelectContent>
                    {banks.map((b) => <SelectItem key={b.bank_id} value={b.name}>{b.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs">Modelo Impresora Fiscal</Label>
                <Input value={form.fiscal_printer_model} onChange={(e) => set({ fiscal_printer_model: e.target.value })} data-testid="dp-fiscal-printer" />
              </div>
            </div>

            {/* Seriales Pinpad (carga interactiva) */}
            <div className="border border-slate-200 rounded-md p-3 bg-slate-50/40">
              <div className="flex items-center justify-between mb-2">
                <div className="font-medium text-sm text-slate-700 flex items-center gap-2">
                  <Boxes size={14} /> Seriales Pinpad
                  {form.pinpad_serials.length > 0 && <Badge variant="secondary" className="bg-emerald-100 text-emerald-700 text-[10px]">{form.pinpad_serials.length}</Badge>}
                </div>
                <div className="flex items-center gap-2">
                  <ExcelUploader kind="serials" testIdPrefix="dp-pp" onParsed={(items) => set({ pinpad_serials: [...form.pinpad_serials, ...items] })} />
                  <Button size="sm" variant="outline" onClick={addSerial} data-testid="dp-add-pinpad-serial"><Plus size={14} className="mr-1" /> Manual</Button>
                  {form.pinpad_serials.length > 0 && (
                    <Button size="sm" variant="ghost" onClick={clearSerials} className="text-red-600 hover:bg-red-50" data-testid="dp-clear-serials">
                      <Trash2 size={14} className="mr-1" /> Vaciar
                    </Button>
                  )}
                </div>
              </div>
              <p className="text-[11px] text-slate-500 mb-2">Tras cargar el Excel se listan aquí — puedes auditar y eliminar registros erróneos antes de enviar.</p>
              <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1">
                {form.pinpad_serials.length === 0 ? (
                  <p className="text-xs text-slate-400 italic">Sin seriales cargados</p>
                ) : form.pinpad_serials.map((s, i) => (
                  <div key={i} className="flex gap-2 items-center" data-testid={`dp-pinpad-serial-row-${i}`}>
                    <span className="text-xs text-slate-400 font-mono w-7 text-right">{i + 1}.</span>
                    <Input value={s.modelo} onChange={(e) => updateSerial(i, { modelo: e.target.value })} placeholder="Modelo" className="h-8 text-sm" />
                    <Input value={s.serial} onChange={(e) => updateSerial(i, { serial: e.target.value })} placeholder="Serial" className="h-8 text-sm" />
                    <Button size="sm" variant="ghost" onClick={() => removeSerial(i)} className="text-red-600" data-testid={`dp-remove-serial-${i}`}><Trash2 size={14} /></Button>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Card 4: Multitienda */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Control Multitienda</CardTitle>
            <div className="flex items-center gap-2">
              <Label htmlFor="multistore-toggle" className="text-xs">{form.is_multistore ? 'Activado' : 'Desactivado'}</Label>
              <Switch id="multistore-toggle" checked={form.is_multistore} onCheckedChange={(v) => set({ is_multistore: v, stores: v ? form.stores : [] })} data-testid="dp-multistore-toggle" />
            </div>
          </div>
        </CardHeader>
        {form.is_multistore && (
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <p className="text-xs text-slate-500 flex items-center gap-2">
                {totalStoreBoxes === Number(form.cantidad_cajas) ? <CheckCircle2 size={14} className="text-emerald-600" /> : <AlertCircle size={14} className="text-red-500" />}
                Suma de cajas: <strong className={totalStoreBoxes === Number(form.cantidad_cajas) ? 'text-emerald-600' : 'text-red-600'}>{totalStoreBoxes}</strong> / {form.cantidad_cajas}
              </p>
              <div className="flex gap-2">
                <ExcelUploader kind="branches" testIdPrefix="dp-stores" onParsed={(items) => set({ stores: [...form.stores, ...items] })} />
                <Button size="sm" variant="outline" onClick={addStore} data-testid="dp-add-store"><Plus size={14} className="mr-1" /> Sucursal</Button>
              </div>
            </div>

            {form.stores.length > 0 ? (
              <div className="border border-slate-200 rounded-md overflow-hidden bg-white" data-testid="dp-stores-grid">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium text-slate-600 w-12">#</th>
                      <th className="px-3 py-2 text-left font-medium text-slate-600">Sucursal</th>
                      <th className="px-3 py-2 text-left font-medium text-slate-600 w-32">Cantidad Cajas</th>
                      <th className="px-3 py-2 w-12"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {form.stores.map((s, i) => (
                      <tr key={i} className="border-b border-slate-100" data-testid={`dp-store-row-${i}`}>
                        <td className="px-3 py-1.5 text-slate-400 font-mono">{i + 1}</td>
                        <td className="px-3 py-1.5">
                          <Input value={s.name} onChange={(e) => updateStore(i, { name: e.target.value })} placeholder="Nombre Sucursal" className="h-8 text-sm" />
                        </td>
                        <td className="px-3 py-1.5">
                          <Input type="number" min="1" value={s.box_count} onChange={(e) => updateStore(i, { box_count: Math.max(1, parseInt(e.target.value) || 1) })} className="h-8 text-sm w-24" />
                        </td>
                        <td className="px-3 py-1.5">
                          <Button size="sm" variant="ghost" onClick={() => removeStore(i)} className="text-red-600"><Trash2 size={14} /></Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-xs text-slate-400 italic">Sin sucursales cargadas. Agrega manualmente o vía Excel.</p>
            )}
          </CardContent>
        )}
      </Card>

      {/* Card 5: Reel de distribución de cajas */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">Reel de Distribución de Cajas</CardTitle>
              <CardDescription className="text-xs">
                Cada fila: <strong>Cantidad</strong> + <strong>Banco</strong> + <strong>Producto</strong>.
                El catálogo de productos se filtra por banco + tipo de proyecto (<strong>{(QUOTE_TYPES.find((q) => q.id === form.quote_type) || {}).label}</strong>).
              </CardDescription>
            </div>
            <p className="text-xs text-slate-500 flex items-center gap-2">
              {totalBoxesInGrid === Number(form.cantidad_cajas) ? <CheckCircle2 size={14} className="text-emerald-600" /> : <AlertCircle size={14} className="text-red-500" />}
              <strong className={totalBoxesInGrid === Number(form.cantidad_cajas) ? 'text-emerald-600' : 'text-red-600'}>{totalBoxesInGrid}</strong>/{form.cantidad_cajas}
            </p>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="border border-slate-200 rounded-md overflow-hidden bg-white">
            <table className="w-full text-sm" data-testid="dp-boxes-grid">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-3 py-2 text-left font-medium text-slate-600 w-12">#</th>
                  <th className="px-3 py-2 text-left font-medium text-slate-600 w-24">Cantidad</th>
                  <th className="px-3 py-2 text-left font-medium text-slate-600">Banco</th>
                  <th className="px-3 py-2 text-left font-medium text-slate-600">Producto</th>
                  {form.is_multistore && <th className="px-3 py-2 text-left font-medium text-slate-600">Sucursal</th>}
                  <th className="px-3 py-2 w-12"></th>
                </tr>
              </thead>
              <tbody>
                {form.boxes_grid.map((b, i) => {
                  const products = productsForBank(b.bank_name);
                  return (
                    <tr key={i} className="border-b border-slate-100" data-testid={`dp-box-row-${i}`}>
                      <td className="px-3 py-1.5 text-slate-400 font-mono">{i + 1}</td>
                      <td className="px-3 py-1.5">
                        <Input
                          type="number" min="1"
                          value={b.quantity}
                          onChange={(e) => updateBox(i, { quantity: Math.max(1, parseInt(e.target.value) || 1) })}
                          className="h-8 text-sm w-20"
                          data-testid={`dp-box-${i}-quantity`}
                        />
                      </td>
                      <td className="px-3 py-1.5">
                        <Select value={b.bank_name} onValueChange={(v) => updateBox(i, { bank_name: v })}>
                          <SelectTrigger className="h-8 text-sm" data-testid={`dp-box-${i}-bank`}><SelectValue placeholder="Banco..." /></SelectTrigger>
                          <SelectContent>
                            {banks.map((bk) => <SelectItem key={bk.bank_id} value={bk.name}>{bk.name}</SelectItem>)}
                          </SelectContent>
                        </Select>
                      </td>
                      <td className="px-3 py-1.5">
                        <Select
                          value={b.product_name}
                          onValueChange={(v) => updateBox(i, { product_name: v })}
                          disabled={!b.bank_name || products.length === 0}
                        >
                          <SelectTrigger className="h-8 text-sm" data-testid={`dp-box-${i}-product`}>
                            <SelectValue placeholder={!b.bank_name ? 'Elige banco primero' : (products.length === 0 ? 'Sin productos disponibles' : 'Producto...')} />
                          </SelectTrigger>
                          <SelectContent className="max-h-60">
                            {products.map((p) => (
                              <SelectItem key={p.product_name} value={p.product_name}>{p.product_name}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </td>
                      {form.is_multistore && (
                        <td className="px-3 py-1.5">
                          <Select value={b.store_name || ''} onValueChange={(v) => updateBox(i, { store_name: v })}>
                            <SelectTrigger className="h-8 text-sm"><SelectValue placeholder="(opcional)" /></SelectTrigger>
                            <SelectContent>
                              {form.stores.map((s, si) => <SelectItem key={si} value={s.name}>{s.name}</SelectItem>)}
                            </SelectContent>
                          </Select>
                        </td>
                      )}
                      <td className="px-3 py-1.5">
                        <Button size="sm" variant="ghost" onClick={() => removeBoxRow(i)} className="text-red-600" disabled={form.boxes_grid.length === 1} data-testid={`dp-box-${i}-remove`}><Trash2 size={14} /></Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <Button variant="outline" size="sm" onClick={addBoxRow} data-testid="dp-add-box-row"><Plus size={14} className="mr-1" /> Agregar fila</Button>
        </CardContent>
      </Card>

      {/* Card 6: Instrucciones */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Instrucciones para el Implementador <span className="text-xs font-normal text-slate-500">(opcional)</span></CardTitle>
        </CardHeader>
        <CardContent>
          <Textarea
            value={form.implementation_instructions}
            onChange={(e) => set({ implementation_instructions: e.target.value })}
            placeholder="Notas internas para el equipo de implementación (máx 500 caracteres)"
            rows={4}
            maxLength={500}
            data-testid="dp-instructions"
          />
          <div className="text-xs text-slate-400 text-right mt-1">{(form.implementation_instructions || '').length}/500</div>
        </CardContent>
      </Card>

      {/* Errores + Submit */}
      {errors.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-md p-3 text-sm text-red-800" data-testid="dp-errors">
          <strong>Hay errores que debes corregir:</strong>
          <ul className="list-disc list-inside mt-1 space-y-0.5">
            {errors.slice(0, 6).map((e, i) => <li key={i}>{e}</li>)}
            {errors.length > 6 && <li>... y {errors.length - 6} más</li>}
          </ul>
        </div>
      )}

      <div className="flex items-center justify-end gap-3 sticky bottom-0 bg-white border-t border-slate-200 -mx-4 lg:-mx-6 px-4 lg:px-6 py-3">
        <Button variant="outline" onClick={() => navigate('/projects')} disabled={saving} data-testid="dp-cancel-btn">
          <X size={14} className="mr-1" /> Cancelar
        </Button>
        <Button onClick={handleSubmit} disabled={saving || errors.length > 0} className="bg-emerald-600 hover:bg-emerald-700" data-testid="dp-submit-btn">
          {saving ? <Loader2 size={14} className="animate-spin mr-1" /> : <Save size={14} className="mr-1" />}
          Enviar a Implementación
        </Button>
      </div>
    </div>
  );
}
