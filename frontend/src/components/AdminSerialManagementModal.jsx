/**
 * Modal admin para gestión avanzada de seriales (POS / PINPADS).
 *
 * Acciones disponibles SOLO para rol Administrador:
 *  - Reemplazo de serial (falla de fábrica)
 *  - Reasignación a otro cliente
 *  - Desasignación + marcar como NO ASIGNABLE (blacklist)
 *  - Ver / liberar lista de seriales en blacklist
 *
 * Endpoints backend: /api/admin/inventory/serials/*
 */
import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from './ui/select';
import { Search, RefreshCw, UserCog, Ban, ListX, ChevronLeft, Loader2, Undo2, Trash2, Plus, Pencil, Warehouse as WarehouseIcon } from 'lucide-react';
import { toast } from 'sonner';
import api from '../utils/api';

export const AdminSerialManagementModal = ({ open, onClose }) => {
  const [tab, setTab] = useState('by-model'); // 'by-model' | 'search' | 'blacklist'
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [blacklist, setBlacklist] = useState([]);
  const [loading, setLoading] = useState(false);
  const [actionState, setActionState] = useState(null); // {type, assignment}
  const [clients, setClients] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [serializableItems, setSerializableItems] = useState([]);
  // Tab "Por Modelo"
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [modelSerials, setModelSerials] = useState([]);
  const [modelCounts, setModelCounts] = useState(null);

  const reset = () => { setActionState(null); setQuery(''); setResults([]); };

  useEffect(() => {
    if (!open) return;
    api.get('/clients').then(r => setClients(r.data || [])).catch(() => {});
    api.get('/admin/inventory/items').then(r => setModels(r.data?.items || [])).catch(() => {});
    api.get('/inventory/warehouses').then(r => setWarehouses(r.data || [])).catch(() => {});
    api.get('/admin/inventory/serializable-items').then(r => setSerializableItems(r.data?.items || [])).catch(() => {});
    if (tab === 'blacklist') loadBlacklist();
  }, [open, tab]);

  // Cargar seriales cuando se selecciona un modelo
  useEffect(() => {
    if (!selectedModel) { setModelSerials([]); setModelCounts(null); return; }
    setLoading(true);
    api.get('/admin/inventory/serials/by-item', { params: { item_id: selectedModel } })
      .then(r => {
        setModelSerials(r.data?.serials || []);
        setModelCounts(r.data?.counts || null);
      })
      .catch(e => toast.error(`Error: ${e.response?.data?.detail || e.message}`))
      .finally(() => setLoading(false));
  }, [selectedModel]);

  const refreshByModel = () => {
    if (!selectedModel) return;
    api.get('/admin/inventory/serials/by-item', { params: { item_id: selectedModel } })
      .then(r => {
        setModelSerials(r.data?.serials || []);
        setModelCounts(r.data?.counts || null);
      });
  };

  const handleSearch = async () => {
    if (query.trim().length < 2) {
      toast.error('Ingresa al menos 2 caracteres del serial');
      return;
    }
    setLoading(true);
    try {
      const res = await api.get('/admin/inventory/serials/search', { params: { q: query.trim() } });
      setResults(res.data.results || []);
      if (!res.data.results?.length) toast.info('No se encontraron asignaciones');
    } catch (e) {
      toast.error(`Error: ${e.response?.data?.detail || e.message}`);
    } finally { setLoading(false); }
  };

  const loadBlacklist = async () => {
    setLoading(true);
    try {
      const res = await api.get('/admin/inventory/serials/blacklist');
      setBlacklist(res.data.items || []);
    } catch (e) {
      toast.error(`Error: ${e.response?.data?.detail || e.message}`);
    } finally { setLoading(false); }
  };

  const refreshSearch = async () => {
    if (query.trim().length >= 2) await handleSearch();
    // Si estamos en tab by-model, refrescar también esa vista
    refreshByModel();
  };

  const releaseFromBlacklist = async (serial) => {
    if (!window.confirm(`¿Liberar el serial ${serial} de la lista de no asignables?`)) return;
    try {
      await api.post(`/admin/inventory/serials/blacklist/${encodeURIComponent(serial)}/release`);
      toast.success(`Serial ${serial} liberado`);
      loadBlacklist();
    } catch (e) {
      toast.error(`Error: ${e.response?.data?.detail || e.message}`);
    }
  };

  // ── Acciones por asignación ───────────────────────────────
  const SubReplace = ({ asg }) => {
    const [newSerial, setNewSerial] = useState('');
    const [reason, setReason] = useState('');
    const [returnOld, setReturnOld] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const submit = async () => {
      if (!newSerial.trim() || !reason.trim()) { toast.error('Completa nuevo serial y motivo'); return; }
      setSubmitting(true);
      try {
        await api.post(`/admin/inventory/serials/${asg.assignment_id}/replace`, {
          new_serial: newSerial.trim(),
          reason: reason.trim(),
          return_old_to_stock: returnOld,
        });
        toast.success(`Serial reemplazado: ${asg.serial} → ${newSerial}`);
        setActionState(null);
        refreshSearch();
      } catch (e) {
        toast.error(`Error: ${e.response?.data?.detail || e.message}`);
      } finally { setSubmitting(false); }
    };
    return (
      <div className="space-y-3 p-4 bg-amber-50 border border-amber-200 rounded">
        <h4 className="text-sm font-semibold text-amber-900">Reemplazar serial (falla de fábrica)</h4>
        <p className="text-xs text-slate-600">Serial actual: <b className="font-mono">{asg.serial}</b> · Cliente: {asg.client_name}</p>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-xs text-slate-600">Nuevo serial *</label>
            <Input value={newSerial} onChange={(e) => setNewSerial(e.target.value)} placeholder="Ej: SN1234" data-testid="replace-new-serial" />
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 text-xs text-slate-700">
              <input type="checkbox" checked={returnOld} onChange={(e) => setReturnOld(e.target.checked)} data-testid="replace-return-old" />
              ¿Devolver el viejo al stock asignable?
            </label>
          </div>
        </div>
        <div>
          <label className="text-xs text-slate-600">Motivo *</label>
          <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Falla de fábrica: pantalla no enciende" data-testid="replace-reason" />
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => setActionState(null)} disabled={submitting}>Cancelar</Button>
          <Button size="sm" onClick={submit} disabled={submitting} className="bg-amber-600 hover:bg-amber-700" data-testid="replace-submit">
            {submitting && <Loader2 size={14} className="animate-spin mr-1" />}Confirmar Reemplazo
          </Button>
        </div>
      </div>
    );
  };

  const SubReassign = ({ asg }) => {
    const [newClientId, setNewClientId] = useState('');
    const [reason, setReason] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const submit = async () => {
      if (!newClientId || !reason.trim()) { toast.error('Selecciona cliente destino y motivo'); return; }
      setSubmitting(true);
      try {
        await api.post(`/admin/inventory/serials/${asg.assignment_id}/reassign-client`, {
          new_client_id: newClientId, reason: reason.trim(),
        });
        toast.success('Serial reasignado');
        setActionState(null);
        refreshSearch();
      } catch (e) {
        toast.error(`Error: ${e.response?.data?.detail || e.message}`);
      } finally { setSubmitting(false); }
    };
    return (
      <div className="space-y-3 p-4 bg-blue-50 border border-blue-200 rounded">
        <h4 className="text-sm font-semibold text-blue-900">Reasignar a otro cliente</h4>
        <p className="text-xs text-slate-600">Serial: <b className="font-mono">{asg.serial}</b> · Cliente actual: {asg.client_name}</p>
        <div>
          <label className="text-xs text-slate-600">Cliente destino *</label>
          <Select value={newClientId} onValueChange={setNewClientId}>
            <SelectTrigger data-testid="reassign-client-select"><SelectValue placeholder="Selecciona cliente" /></SelectTrigger>
            <SelectContent className="max-h-72 overflow-y-auto">
              {clients
                .filter(c => c.client_id !== asg.client_id)
                .sort((a, b) => (a.legal_name || '').localeCompare(b.legal_name || ''))
                .map(c => (
                  <SelectItem key={c.client_id} value={c.client_id}>
                    {c.legal_name || c.fantasy_name}
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-xs text-slate-600">Motivo *</label>
          <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Corrección de asignación errónea" data-testid="reassign-reason" />
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => setActionState(null)} disabled={submitting}>Cancelar</Button>
          <Button size="sm" onClick={submit} disabled={submitting} className="bg-blue-600 hover:bg-blue-700" data-testid="reassign-submit">
            {submitting && <Loader2 size={14} className="animate-spin mr-1" />}Confirmar Reasignación
          </Button>
        </div>
      </div>
    );
  };

  const SubUnassign = ({ asg }) => {
    const [reason, setReason] = useState('');
    const [markBlocked, setMarkBlocked] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const submit = async () => {
      if (!reason.trim()) { toast.error('Motivo requerido'); return; }
      setSubmitting(true);
      try {
        await api.post(`/admin/inventory/serials/${asg.assignment_id}/unassign`, {
          reason: reason.trim(), mark_non_assignable: markBlocked,
        });
        toast.success(`Serial ${asg.serial} desasignado${markBlocked ? ' y bloqueado' : ''}`);
        setActionState(null);
        refreshSearch();
      } catch (e) {
        toast.error(`Error: ${e.response?.data?.detail || e.message}`);
      } finally { setSubmitting(false); }
    };
    return (
      <div className="space-y-3 p-4 bg-rose-50 border border-rose-200 rounded">
        <h4 className="text-sm font-semibold text-rose-900">Desasignar serial</h4>
        <p className="text-xs text-slate-600">Serial: <b className="font-mono">{asg.serial}</b> · Cliente: {asg.client_name}</p>
        <label className="flex items-start gap-2 text-xs text-slate-700">
          <input type="checkbox" checked={markBlocked} onChange={(e) => setMarkBlocked(e.target.checked)} data-testid="unassign-mark-blocked" />
          <span>Marcar como <b>NO asignable</b> (pendiente reemplazo del proveedor). Cuando llegue el reemplazo, podrás liberarlo desde "Lista no asignables".</span>
        </label>
        <div>
          <label className="text-xs text-slate-600">Motivo *</label>
          <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Falla detectada, equipo enviado al proveedor para RMA" data-testid="unassign-reason" />
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => setActionState(null)} disabled={submitting}>Cancelar</Button>
          <Button size="sm" onClick={submit} disabled={submitting} className="bg-rose-600 hover:bg-rose-700" data-testid="unassign-submit">
            {submitting && <Loader2 size={14} className="animate-spin mr-1" />}Confirmar Desasignación
          </Button>
        </div>
      </div>
    );
  };

  // ── Gestión de seriales VENDIDOS (sin assignment_id activo) ──
  const SubReturnSold = ({ asg }) => {
    const [warehouseId, setWarehouseId] = useState(asg.warehouse_id || '');
    const [reason, setReason] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const submit = async () => {
      if (!warehouseId || !reason.trim()) { toast.error('Almacén destino y motivo son requeridos'); return; }
      setSubmitting(true);
      try {
        await api.post(`/admin/inventory/serials/sold/${encodeURIComponent(asg.serial)}/return-to-stock`, {
          warehouse_id: warehouseId, reason: reason.trim(),
        });
        toast.success(`Serial ${asg.serial} devuelto al stock`);
        setActionState(null);
        refreshByModel();
      } catch (e) {
        toast.error(`Error: ${e.response?.data?.detail || e.message}`);
      } finally { setSubmitting(false); }
    };
    return (
      <div className="space-y-3 p-4 bg-emerald-50 border border-emerald-200 rounded">
        <h4 className="text-sm font-semibold text-emerald-900">Devolver al stock asignable</h4>
        <p className="text-xs text-slate-600">Serial: <b className="font-mono">{asg.serial}</b> · Estado actual: <span className="font-semibold">Vendido</span></p>
        <div>
          <label className="text-xs text-slate-600">Almacén destino *</label>
          <Select value={warehouseId} onValueChange={setWarehouseId}>
            <SelectTrigger data-testid="return-sold-warehouse-select"><SelectValue placeholder="Selecciona almacén" /></SelectTrigger>
            <SelectContent>
              {warehouses.map(w => (
                <SelectItem key={w.id || w.warehouse_id} value={w.id || w.warehouse_id}>{w.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-xs text-slate-600">Motivo *</label>
          <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Cliente devolvió el equipo; reingresa a inventario" data-testid="return-sold-reason" />
        </div>
        <p className="text-[10px] text-slate-500 italic">Se generará un movimiento de <b>entrada</b> tipo "Devolución administrativa". La salida original se conserva para trazabilidad histórica.</p>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => setActionState(null)} disabled={submitting}>Cancelar</Button>
          <Button size="sm" onClick={submit} disabled={submitting} className="bg-emerald-600 hover:bg-emerald-700" data-testid="return-sold-submit">
            {submitting && <Loader2 size={14} className="animate-spin mr-1" />}Confirmar Devolución
          </Button>
        </div>
      </div>
    );
  };

  const SubUnassignSold = ({ asg }) => {
    const [reason, setReason] = useState('');
    const [markBlocked, setMarkBlocked] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const submit = async () => {
      if (!reason.trim()) { toast.error('Motivo requerido'); return; }
      setSubmitting(true);
      try {
        await api.post(`/admin/inventory/serials/sold/${encodeURIComponent(asg.serial)}/unassign`, {
          reason: reason.trim(), mark_non_assignable: markBlocked,
        });
        toast.success(`Serial ${asg.serial} desasignado${markBlocked ? ' y bloqueado' : ''}`);
        setActionState(null);
        refreshByModel();
      } catch (e) {
        toast.error(`Error: ${e.response?.data?.detail || e.message}`);
      } finally { setSubmitting(false); }
    };
    return (
      <div className="space-y-3 p-4 bg-rose-50 border border-rose-200 rounded">
        <h4 className="text-sm font-semibold text-rose-900">Desasignar serial vendido</h4>
        <p className="text-xs text-slate-600">Serial: <b className="font-mono">{asg.serial}</b></p>
        <label className="flex items-start gap-2 text-xs text-slate-700">
          <input type="checkbox" checked={markBlocked} onChange={(e) => setMarkBlocked(e.target.checked)} data-testid="unassign-sold-mark-blocked" />
          <span>Adicionalmente marcar como <b>NO asignable</b> (blacklist).</span>
        </label>
        <div>
          <label className="text-xs text-slate-600">Motivo *</label>
          <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Corrección de asignación incorrecta del despacho" data-testid="unassign-sold-reason" />
        </div>
        <p className="text-[10px] text-slate-500 italic">Limpia cualquier rastro de asignación residual sin modificar el histórico de movimientos.</p>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => setActionState(null)} disabled={submitting}>Cancelar</Button>
          <Button size="sm" onClick={submit} disabled={submitting} className="bg-rose-600 hover:bg-rose-700" data-testid="unassign-sold-submit">
            {submitting && <Loader2 size={14} className="animate-spin mr-1" />}Confirmar Desasignación
          </Button>
        </div>
      </div>
    );
  };

  const SubDeleteSold = ({ asg }) => {
    const [reason, setReason] = useState('');
    const [confirmText, setConfirmText] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const submit = async () => {
      if (!reason.trim()) { toast.error('Motivo requerido'); return; }
      if (confirmText !== 'ELIMINAR') { toast.error('Escribe ELIMINAR para confirmar'); return; }
      setSubmitting(true);
      try {
        await api.delete(`/admin/inventory/serials/sold/${encodeURIComponent(asg.serial)}`, {
          headers: { 'x-reason': reason.trim() },
        });
        toast.success(`Serial ${asg.serial} eliminado del sistema`);
        setActionState(null);
        refreshByModel();
      } catch (e) {
        toast.error(`Error: ${e.response?.data?.detail || e.message}`);
      } finally { setSubmitting(false); }
    };
    return (
      <div className="space-y-3 p-4 bg-red-50 border border-red-300 rounded">
        <h4 className="text-sm font-semibold text-red-900">⚠ Eliminar serial vendido (acción destructiva)</h4>
        <p className="text-xs text-slate-700">Serial: <b className="font-mono">{asg.serial}</b></p>
        <div className="bg-red-100 border border-red-300 rounded p-2 text-[11px] text-red-900">
          Esto removerá el serial de TODOS los movimientos de inventario (entradas, salidas y transferencias). Si algún movimiento contiene solo este serial, se borrará por completo. <b>No reversible</b>.
        </div>
        <div>
          <label className="text-xs text-slate-600">Motivo *</label>
          <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Serial cargado por error en la importación inicial" data-testid="delete-sold-reason" />
        </div>
        <div>
          <label className="text-xs text-slate-600">Escribe <b>ELIMINAR</b> para confirmar *</label>
          <Input value={confirmText} onChange={(e) => setConfirmText(e.target.value)} placeholder="ELIMINAR" data-testid="delete-sold-confirm" />
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => setActionState(null)} disabled={submitting}>Cancelar</Button>
          <Button size="sm" onClick={submit} disabled={submitting || confirmText !== 'ELIMINAR'} className="bg-red-700 hover:bg-red-800" data-testid="delete-sold-submit">
            {submitting && <Loader2 size={14} className="animate-spin mr-1" />}Eliminar definitivamente
          </Button>
        </div>
      </div>
    );
  };

  // ── Alta de nuevos seriales (individual o masivo) ──
  const SubCreate = () => {
    const [itemId, setItemId] = useState(selectedModel || '');
    const [warehouseId, setWarehouseId] = useState('');
    const [serialsText, setSerialsText] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const parsed = serialsText
      .split(/[\n,;]+/)
      .map(s => s.trim())
      .filter(Boolean);
    const submit = async () => {
      if (!itemId) { toast.error('Seleccione el Producto'); return; }
      if (!warehouseId) { toast.error('Seleccione el Almacén de adscripción'); return; }
      if (parsed.length === 0) { toast.error('Ingrese al menos un número de serial'); return; }
      setSubmitting(true);
      try {
        const res = await api.post('/admin/inventory/serials/create', {
          item_id: itemId, warehouse_id: warehouseId, serials: parsed,
        });
        toast.success(res.data?.message || 'Seriales creados');
        setActionState(null);
        // Si se creó sobre el modelo en pantalla, refrescar; si no, seleccionarlo.
        if (itemId === selectedModel) refreshByModel();
        else setSelectedModel(itemId);
      } catch (e) {
        toast.error(`Error: ${e.response?.data?.detail || e.message}`);
      } finally { setSubmitting(false); }
    };
    return (
      <div className="space-y-3 p-4 bg-indigo-50 border border-indigo-200 rounded" data-testid="serial-create-form">
        <h4 className="text-sm font-semibold text-indigo-900 flex items-center gap-1.5"><Plus size={15} /> Agregar Serial(es)</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <div>
            <label className="text-xs text-slate-600">Producto *</label>
            <Select value={itemId} onValueChange={setItemId}>
              <SelectTrigger data-testid="serial-create-item-select"><SelectValue placeholder="Selecciona producto" /></SelectTrigger>
              <SelectContent className="max-h-72 overflow-y-auto">
                {serializableItems.map(m => (
                  <SelectItem key={m.item_id} value={m.item_id}>{m.name} {m.type ? `· ${m.type}` : ''}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-xs text-slate-600">Almacén de adscripción *</label>
            <Select value={warehouseId} onValueChange={setWarehouseId}>
              <SelectTrigger data-testid="serial-create-warehouse-select"><SelectValue placeholder="Selecciona almacén" /></SelectTrigger>
              <SelectContent>
                {warehouses.map(w => (
                  <SelectItem key={w.warehouse_id || w.id} value={w.warehouse_id || w.id}>{w.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <div>
          <label className="text-xs text-slate-600">Número(s) de Serial * <span className="text-slate-400">(uno por línea o separados por coma — individual o masivo)</span></label>
          <textarea
            value={serialsText}
            onChange={(e) => setSerialsText(e.target.value)}
            rows={4}
            placeholder={'SN-2026-XYZ\nSN-2026-ABC'}
            className="w-full text-xs font-mono border border-slate-300 rounded p-2 mt-0.5"
            data-testid="serial-create-serials-input"
          />
          <p className="text-[10px] text-slate-500 mt-0.5">{parsed.length} serial(es) a crear · nacen en estado <b>Disponible</b>.</p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => setActionState(null)} disabled={submitting}>Cancelar</Button>
          <Button size="sm" onClick={submit} disabled={submitting} className="bg-indigo-600 hover:bg-indigo-700" data-testid="serial-create-submit">
            {submitting && <Loader2 size={14} className="animate-spin mr-1" />}Crear Serial(es)
          </Button>
        </div>
      </div>
    );
  };

  // ── Modificación de un serial (rename + reubicación de almacén) ──
  const SubEdit = ({ asg }) => {
    const [newSerial, setNewSerial] = useState(asg.serial || '');
    const [warehouseId, setWarehouseId] = useState(asg.warehouse_id || '');
    const [reason, setReason] = useState('');
    const [submitting, setSubmitting] = useState(false);
    // La reubicación de almacén solo aplica a seriales en stock o asignados.
    const canRelocate = ['en_stock', 'asignado', 'preasignado', 'asignado_temporal'].includes(asg.status);
    const submit = async () => {
      const rename = newSerial.trim() && newSerial.trim() !== asg.serial;
      const relocate = canRelocate && warehouseId && warehouseId !== (asg.warehouse_id || '');
      if (!rename && !relocate) { toast.error('Indique un nuevo serial y/o un nuevo almacén'); return; }
      if (!reason.trim()) { toast.error('El motivo es obligatorio (auditoría)'); return; }
      setSubmitting(true);
      try {
        const res = await api.put('/admin/inventory/serials/edit', {
          current_serial: asg.serial,
          new_serial: rename ? newSerial.trim() : '',
          new_warehouse_id: relocate ? warehouseId : '',
          reason: reason.trim(),
        });
        toast.success(res.data?.message || 'Serial actualizado');
        setActionState(null);
        refreshByModel();
      } catch (e) {
        toast.error(`Error: ${e.response?.data?.detail || e.message}`);
      } finally { setSubmitting(false); }
    };
    return (
      <div className="space-y-3 p-4 bg-sky-50 border border-sky-200 rounded" data-testid="serial-edit-form">
        <h4 className="text-sm font-semibold text-sky-900 flex items-center gap-1.5"><Pencil size={15} /> Modificar serial</h4>
        <p className="text-xs text-slate-600">Actual: <b className="font-mono">{asg.serial}</b> · Estado: <span className="font-semibold">{asg.status}</span></p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <div>
            <label className="text-xs text-slate-600">Número de Serial</label>
            <Input value={newSerial} onChange={(e) => setNewSerial(e.target.value)} className="font-mono" data-testid="serial-edit-serial-input" />
          </div>
          <div>
            <label className="text-xs text-slate-600">Almacén de adscripción {canRelocate ? '' : '(no editable en este estado)'}</label>
            <Select value={warehouseId} onValueChange={setWarehouseId} disabled={!canRelocate}>
              <SelectTrigger data-testid="serial-edit-warehouse-select"><SelectValue placeholder="Selecciona almacén" /></SelectTrigger>
              <SelectContent>
                {warehouses.map(w => (
                  <SelectItem key={w.warehouse_id || w.id} value={w.warehouse_id || w.id}>{w.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <div>
          <label className="text-xs text-slate-600">Motivo *</label>
          <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Corrección de tipeo / reubicación física" data-testid="serial-edit-reason" />
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => setActionState(null)} disabled={submitting}>Cancelar</Button>
          <Button size="sm" onClick={submit} disabled={submitting} className="bg-sky-600 hover:bg-sky-700" data-testid="serial-edit-submit">
            {submitting && <Loader2 size={14} className="animate-spin mr-1" />}Guardar cambios
          </Button>
        </div>
      </div>
    );
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) { onClose(); reset(); } }}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto" data-testid="admin-serial-management-modal">
        <DialogHeader>
          <DialogTitle className="text-lg">Gestión Administrativa de Seriales (POS / PINPADS)</DialogTitle>
          <p className="text-xs text-slate-500">Solo Administrador · Reemplazo, reasignación y desasignación con auditoría completa.</p>
        </DialogHeader>

        <div className="flex gap-2 border-b pb-2 flex-wrap">
          <button onClick={() => { setTab('by-model'); reset(); }} className={`px-3 py-1.5 text-sm rounded ${tab==='by-model'?'bg-slate-800 text-white':'text-slate-600 hover:bg-slate-100'}`} data-testid="tab-serial-by-model">Por Modelo</button>
          <button onClick={() => { setTab('search'); reset(); }} className={`px-3 py-1.5 text-sm rounded ${tab==='search'?'bg-slate-800 text-white':'text-slate-600 hover:bg-slate-100'}`} data-testid="tab-serial-search">Buscar Serial</button>
          <button onClick={() => setTab('blacklist')} className={`px-3 py-1.5 text-sm rounded ${tab==='blacklist'?'bg-slate-800 text-white':'text-slate-600 hover:bg-slate-100'}`} data-testid="tab-serial-blacklist">Lista no asignables ({blacklist.length})</button>
        </div>

        {tab === 'by-model' && (
          <div className="space-y-3">
            <div className="flex items-end justify-between gap-2">
              <div className="flex-1">
                <label className="text-xs text-slate-600 mb-1 block">Selecciona modelo de POS / PINPAD</label>
                <Select value={selectedModel} onValueChange={setSelectedModel}>
                  <SelectTrigger data-testid="admin-serial-model-select"><SelectValue placeholder="Elige un modelo..." /></SelectTrigger>
                  <SelectContent className="max-h-72 overflow-y-auto">
                    {models.map(m => (
                      <SelectItem key={m.item_id} value={m.item_id}>{m.name} {m.type ? `· ${m.type}` : ''}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button
                size="sm"
                onClick={() => setActionState({ type: 'create' })}
                className="bg-indigo-600 hover:bg-indigo-700 shrink-0"
                data-testid="serial-add-global-btn"
              >
                <Plus size={14} className="mr-1" /> Agregar Serial
              </Button>
            </div>
            {modelCounts && (
              <div className="grid grid-cols-3 md:grid-cols-6 gap-2 text-[11px]">
                <div className="bg-slate-100 rounded p-2 text-center"><div className="text-slate-500">Total</div><div className="font-bold text-slate-800">{modelCounts.total}</div></div>
                <div className="bg-emerald-50 rounded p-2 text-center"><div className="text-emerald-700">En Stock</div><div className="font-bold text-emerald-800">{modelCounts.en_stock}</div></div>
                <div className="bg-indigo-50 rounded p-2 text-center"><div className="text-indigo-700">Preasignado</div><div className="font-bold text-indigo-800">{modelCounts.preasignado}</div></div>
                <div className="bg-amber-50 rounded p-2 text-center"><div className="text-amber-700">Asignado</div><div className="font-bold text-amber-800">{modelCounts.asignado}</div></div>
                <div className="bg-rose-50 rounded p-2 text-center"><div className="text-rose-700">No asignable</div><div className="font-bold text-rose-800">{modelCounts.blacklist}</div></div>
                <div className="bg-slate-50 rounded p-2 text-center"><div className="text-slate-500">Vendido</div><div className="font-bold text-slate-700">{modelCounts.vendido}</div></div>
              </div>
            )}
            {actionState && actionState.type === 'create' && <SubCreate />}
            {actionState && actionState.type === 'edit' && <SubEdit asg={actionState.asg} />}
            {actionState && actionState.type === 'replace' && <SubReplace asg={actionState.asg} />}
            {actionState && actionState.type === 'reassign' && <SubReassign asg={actionState.asg} />}
            {actionState && actionState.type === 'unassign' && <SubUnassign asg={actionState.asg} />}
            {actionState && actionState.type === 'return-sold' && <SubReturnSold asg={actionState.asg} />}
            {actionState && actionState.type === 'unassign-sold' && <SubUnassignSold asg={actionState.asg} />}
            {actionState && actionState.type === 'delete-sold' && <SubDeleteSold asg={actionState.asg} />}
            {!actionState && modelSerials.length > 0 && (
              <div className="max-h-[50vh] overflow-y-auto border rounded">
                <table className="w-full text-xs">
                  <thead className="bg-slate-100 text-slate-600 sticky top-0">
                    <tr>
                      <th className="px-2 py-1.5 text-left">Serial</th>
                      <th className="px-2 py-1.5 text-left">Estado</th>
                      <th className="px-2 py-1.5 text-left">Almacén</th>
                      <th className="px-2 py-1.5 text-left">Cliente</th>
                      <th className="px-2 py-1.5 text-left">Cotización</th>
                      <th className="px-2 py-1.5 text-right">Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {modelSerials.map(r => {
                      const statusColors = {
                        'en_stock': 'bg-emerald-100 text-emerald-700',
                        'asignado': 'bg-amber-100 text-amber-700',
                        'preasignado': 'bg-indigo-100 text-indigo-700',
                        'asignado_temporal': 'bg-violet-100 text-violet-700',
                        'blacklist': 'bg-rose-100 text-rose-700',
                        'vendido': 'bg-slate-100 text-slate-600',
                      };
                      const canEdit = ['asignado', 'preasignado', 'asignado_temporal'].includes(r.status);
                      return (
                        <tr key={r.serial} className="border-t hover:bg-slate-50">
                          <td className="px-2 py-1.5 font-mono">{r.serial}</td>
                          <td className="px-2 py-1.5"><span className={`px-1.5 py-0.5 rounded text-[10px] ${statusColors[r.status] || 'bg-slate-100'}`}>{r.status}</span></td>
                          <td className="px-2 py-1.5 text-slate-700" data-testid={`serial-warehouse-${r.serial}`}>
                            <span className="inline-flex items-center gap-1">
                              <WarehouseIcon size={11} className="text-slate-400 shrink-0" />
                              {r.warehouse_name || '—'}
                            </span>
                          </td>
                          <td className="px-2 py-1.5 text-slate-700">{r.client_name || '—'}</td>
                          <td className="px-2 py-1.5 text-slate-700">{r.quote_number || '—'}</td>
                          <td className="px-2 py-1.5 text-right">
                            <div className="inline-flex flex-wrap gap-1 justify-end items-center">
                            {canEdit && r.assignment_id && (
                              <div className="inline-flex gap-1">
                                <Button size="sm" variant="outline" className="h-6 text-[10px] px-1.5 text-amber-700 border-amber-300" onClick={() => setActionState({ type: 'replace', asg: { ...r, assignment_id: r.assignment_id, serial: r.serial } })} data-testid={`btn-bm-replace-${r.serial}`}>
                                  <RefreshCw size={10} className="mr-0.5" /> Reemplazar
                                </Button>
                                <Button size="sm" variant="outline" className="h-6 text-[10px] px-1.5 text-blue-700 border-blue-300" onClick={() => setActionState({ type: 'reassign', asg: { ...r, assignment_id: r.assignment_id, serial: r.serial } })} data-testid={`btn-bm-reassign-${r.serial}`}>
                                  <UserCog size={10} className="mr-0.5" /> Reasignar
                                </Button>
                                <Button size="sm" variant="outline" className="h-6 text-[10px] px-1.5 text-rose-700 border-rose-300" onClick={() => setActionState({ type: 'unassign', asg: { ...r, assignment_id: r.assignment_id, serial: r.serial } })} data-testid={`btn-bm-unassign-${r.serial}`}>
                                  <Ban size={10} className="mr-0.5" /> Desasignar
                                </Button>
                              </div>
                            )}
                            {r.status === 'blacklist' && (
                              <Button size="sm" variant="outline" className="h-6 text-[10px] px-1.5" onClick={() => releaseFromBlacklist(r.serial).then(refreshByModel)} data-testid={`btn-bm-release-${r.serial}`}>
                                <ListX size={10} className="mr-0.5" /> Liberar
                              </Button>
                            )}
                            {r.status === 'vendido' && (
                              <div className="inline-flex gap-1">
                                <Button size="sm" variant="outline" className="h-6 text-[10px] px-1.5 text-emerald-700 border-emerald-300" onClick={() => setActionState({ type: 'return-sold', asg: { serial: r.serial, warehouse_id: r.warehouse_id } })} data-testid={`btn-bm-return-sold-${r.serial}`}>
                                  <Undo2 size={10} className="mr-0.5" /> Devolver al Stock
                                </Button>
                                <Button size="sm" variant="outline" className="h-6 text-[10px] px-1.5 text-rose-700 border-rose-300" onClick={() => setActionState({ type: 'unassign-sold', asg: { serial: r.serial } })} data-testid={`btn-bm-unassign-sold-${r.serial}`}>
                                  <Ban size={10} className="mr-0.5" /> Desasignar
                                </Button>
                                <Button size="sm" variant="outline" className="h-6 text-[10px] px-1.5 text-red-700 border-red-400" onClick={() => setActionState({ type: 'delete-sold', asg: { serial: r.serial } })} data-testid={`btn-bm-delete-sold-${r.serial}`}>
                                  <Trash2 size={10} className="mr-0.5" /> Eliminar
                                </Button>
                              </div>
                            )}
                            {/* Modificar — disponible en TODAS las filas (rename + reubicación) */}
                            <Button size="sm" variant="outline" className="h-6 text-[10px] px-1.5 text-sky-700 border-sky-300" onClick={() => setActionState({ type: 'edit', asg: { serial: r.serial, status: r.status, warehouse_id: r.warehouse_id } })} data-testid={`btn-bm-edit-${r.serial}`}>
                              <Pencil size={10} className="mr-0.5" /> Modificar
                            </Button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            {!actionState && selectedModel && modelSerials.length === 0 && !loading && (
              <p className="text-sm text-slate-500 text-center py-8">No hay seriales registrados para este modelo.</p>
            )}
          </div>
        )}

        {tab === 'search' && (
          <div className="space-y-3">
            <div className="flex gap-2">
              <Input value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleSearch()} placeholder="Ingresa serial completo o parcial (mín. 2 caracteres)" data-testid="admin-serial-search-input" />
              <Button onClick={handleSearch} disabled={loading} data-testid="admin-serial-search-btn">
                {loading ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
              </Button>
            </div>
            {actionState && actionState.type === 'replace' && <SubReplace asg={actionState.asg} />}
            {actionState && actionState.type === 'reassign' && <SubReassign asg={actionState.asg} />}
            {actionState && actionState.type === 'unassign' && <SubUnassign asg={actionState.asg} />}
            {!actionState && results.length > 0 && (
              <div className="space-y-2 max-h-[50vh] overflow-y-auto">
                {results.map(asg => (
                  <div key={asg.assignment_id} className="border rounded p-3 bg-white">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                      <div>
                        <span className="text-slate-500">Serial:</span> <span className="font-mono font-bold">{asg.serial}</span>
                        <span className={`ml-2 px-1.5 py-0.5 rounded text-[10px] ${
                          asg.status === 'asignado' ? 'bg-emerald-100 text-emerald-700' :
                          asg.status === 'preasignado' ? 'bg-blue-100 text-blue-700' :
                          'bg-slate-100 text-slate-700'
                        }`}>{asg.status}</span>
                      </div>
                      <div className="text-slate-600">{asg.item_name}</div>
                      <div><span className="text-slate-500">Cliente:</span> <b>{asg.client_name}</b></div>
                      <div><span className="text-slate-500">Cotización:</span> {asg.quote_number || '—'}</div>
                      {asg.previous_serial && <div className="text-amber-700"><span className="text-slate-500">Reemplazó a:</span> <span className="font-mono">{asg.previous_serial}</span> ({asg.replacement_reason})</div>}
                    </div>
                    <div className="flex gap-2 mt-2 pt-2 border-t">
                      <Button size="sm" variant="outline" className="text-amber-700 border-amber-300 hover:bg-amber-50" onClick={() => setActionState({ type: 'replace', asg })} data-testid={`btn-replace-${asg.assignment_id}`}>
                        <RefreshCw size={12} className="mr-1" /> Reemplazar Serial
                      </Button>
                      <Button size="sm" variant="outline" className="text-blue-700 border-blue-300 hover:bg-blue-50" onClick={() => setActionState({ type: 'reassign', asg })} data-testid={`btn-reassign-${asg.assignment_id}`}>
                        <UserCog size={12} className="mr-1" /> Reasignar Cliente
                      </Button>
                      <Button size="sm" variant="outline" className="text-rose-700 border-rose-300 hover:bg-rose-50" onClick={() => setActionState({ type: 'unassign', asg })} data-testid={`btn-unassign-${asg.assignment_id}`}>
                        <Ban size={12} className="mr-1" /> Desasignar
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === 'blacklist' && (
          <div className="space-y-2 max-h-[60vh] overflow-y-auto">
            {blacklist.length === 0 && (
              <p className="text-sm text-slate-500 text-center py-8">No hay seriales en la lista de no asignables.</p>
            )}
            {blacklist.map(b => (
              <div key={b.serial} className="border rounded p-3 bg-rose-50/30 flex items-start justify-between gap-2">
                <div className="text-xs space-y-1">
                  <div><b className="font-mono">{b.serial}</b> <span className="px-1.5 py-0.5 rounded text-[10px] bg-rose-100 text-rose-700">NO ASIGNABLE</span></div>
                  <div className="text-slate-600">Motivo: {b.reason}</div>
                  <div className="text-slate-500 text-[10px]">Bloqueado: {b.blocked_at?.slice(0, 16)} por {b.blocked_by}</div>
                  {b.previous_client && <div className="text-slate-500 text-[10px]">Anterior: {b.previous_client} ({b.previous_quote})</div>}
                </div>
                <Button size="sm" variant="outline" onClick={() => releaseFromBlacklist(b.serial)} data-testid={`btn-release-${b.serial}`}>
                  <ListX size={12} className="mr-1" /> Liberar
                </Button>
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default AdminSerialManagementModal;
