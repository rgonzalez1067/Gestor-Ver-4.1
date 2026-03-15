import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Popover, PopoverContent, PopoverTrigger } from '../components/ui/popover';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog';
import { Warehouse, Plus, Trash2, PackagePlus, PackageMinus, ArrowLeftRight, History, Box, Cpu, X, Upload, Building2, Pencil, Search, Eye, ExternalLink, ChevronRight } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const SERIALIZED_TYPES = ['pos', 'pinpad', 'mpos'];
const isSerializedType = (t) => SERIALIZED_TYPES.includes((t || '').toLowerCase());

const MOV_LABELS = {
  entrada: { label: 'Entrada', color: 'bg-emerald-100 text-emerald-700', icon: '+' },
  salida: { label: 'Salida', color: 'bg-red-100 text-red-700', icon: '-' },
  transferencia_entrada: { label: 'Transf. Recibida', color: 'bg-blue-100 text-blue-700', icon: '+' },
  transferencia_salida: { label: 'Transf. Enviada', color: 'bg-orange-100 text-orange-700', icon: '-' },
};

export default function Inventory() {
  const [warehouses, setWarehouses] = useState([]);
  const [hardware, setHardware] = useState([]);
  const [selectedWh, setSelectedWh] = useState(null);
  const [stock, setStock] = useState([]);
  const [movements, setMovements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('stock'); // stock | movements

  // Dialogs
  const [whDialog, setWhDialog] = useState(false);
  const [whForm, setWhForm] = useState({ name: '', location: '', notes: '', responsible_user_id: '' });
  const [whEditing, setWhEditing] = useState(null);
  const [users, setUsers] = useState([]);
  const [entryDialog, setEntryDialog] = useState(false);
  const [exitDialog, setExitDialog] = useState(false);
  const [transferDialog, setTransferDialog] = useState(false);
  const [deleteWh, setDeleteWh] = useState({ open: false, id: null, name: '' });

  // Entry form
  const [entryForm, setEntryForm] = useState({ item_id: '', quantity: 1, unit_cost: 0, notes: '', serials: [] });
  const [serialInput, setSerialInput] = useState('');

  // Exit form
  const [exitForm, setExitForm] = useState({ item_id: '', quantity: 1, reference: '', client_name: '', notes: '', serials: [] });
  const [availableSerials, setAvailableSerials] = useState([]);

  // Transfer form
  const [transferForm, setTransferForm] = useState({ dest_warehouse_id: '', item_id: '', quantity: 1, notes: '', serials: [] });
  const [transferSerials, setTransferSerials] = useState([]);

  // Kardex (drill-down)
  const [kardexOpen, setKardexOpen] = useState(false);
  const [kardexData, setKardexData] = useState(null);
  const [kardexLoading, setKardexLoading] = useState(false);

  // Buscador inverso por cliente
  const [clientSearch, setClientSearch] = useState('');
  const [clientSearchResults, setClientSearchResults] = useState([]);
  const [clientSearchLoading, setClientSearchLoading] = useState(false);
  const [showClientSearch, setShowClientSearch] = useState(false);

  const navigate = useNavigate();
  const fetchAll = useCallback(async () => {
    try {
      const [whRes, hwRes, usersRes] = await Promise.all([
        api.get('/inventory/warehouses'),
        api.get('/hardware'),
        api.get('/auth/users'),
      ]);
      setWarehouses(whRes.data);
      setHardware(hwRes.data);
      setUsers(usersRes.data);
      if (!selectedWh && whRes.data.length > 0) {
        setSelectedWh(whRes.data[0].warehouse_id);
      }
    } catch { toast.error('Error al cargar datos'); }
    finally { setLoading(false); }
  }, [selectedWh]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const fetchStock = useCallback(async () => {
    if (!selectedWh) return;
    try {
      const [stockRes, movRes] = await Promise.all([
        api.get(`/inventory/warehouses/${selectedWh}/stock`),
        api.get(`/inventory/warehouses/${selectedWh}/movements`)
      ]);
      setStock(stockRes.data);
      setMovements(movRes.data);
    } catch { /* silent */ }
  }, [selectedWh]);

  useEffect(() => { fetchStock(); }, [fetchStock]);

  // ==================== WAREHOUSE CRUD ====================
  const saveWarehouse = async () => {
    if (!whForm.name.trim()) { toast.error('Nombre obligatorio'); return; }
    const payload = { ...whForm, responsible_user_id: whForm.responsible_user_id === 'none' ? '' : whForm.responsible_user_id };
    try {
      if (whEditing) {
        await api.put(`/inventory/warehouses/${whEditing}`, payload);
        toast.success('Almacén actualizado');
      } else {
        const res = await api.post('/inventory/warehouses', payload);
        if (!selectedWh) setSelectedWh(res.data.warehouse_id);
        toast.success('Almacén creado');
      }
      setWhDialog(false);
      setWhEditing(null);
      setWhForm({ name: '', location: '', notes: '', responsible_user_id: '' });
      fetchAll();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  const handleDeleteWh = async () => {
    try {
      await api.delete(`/inventory/warehouses/${deleteWh.id}`);
      toast.success('Almacén eliminado');
      setDeleteWh({ open: false, id: null, name: '' });
      if (selectedWh === deleteWh.id) setSelectedWh(null);
      fetchAll();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  // ==================== MIN STOCK CONFIG ====================
  const saveMinStock = async (itemId, value) => {
    const val = parseInt(value) || 0;
    if (val < 0) { toast.error('Stock mínimo no puede ser negativo'); return; }
    try {
      await api.put(`/inventory/warehouses/${selectedWh}/min-stock/${itemId}`, { min_stock: val });
      toast.success('Stock mínimo actualizado');
      fetchStock();
    } catch { toast.error('Error al guardar'); }
  };

  // ==================== ENTRY ====================
  const selectedEntryItem = hardware.find(h => h.hardware_id === entryForm.item_id);
  const entryNeedsSerial = selectedEntryItem && isSerializedType(selectedEntryItem.type);

  const addSerial = () => {
    const s = serialInput.trim();
    if (!s) return;
    if (entryForm.serials.includes(s)) { toast.error('Serial duplicado'); return; }
    setEntryForm({ ...entryForm, serials: [...entryForm.serials, s] });
    setSerialInput('');
  };

  const handleEntryExcel = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await api.post('/inventory/parse-serials', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      setEntryForm(prev => ({ ...prev, serials: [...prev.serials, ...res.data.serials] }));
      toast.success(`${res.data.count} seriales cargados`);
    } catch { toast.error('Error al leer archivo'); }
    e.target.value = '';
  };

  const submitEntry = async () => {
    if (!entryForm.item_id || entryForm.quantity < 1) { toast.error('Complete los campos'); return; }
    if (entryNeedsSerial && entryForm.serials.length !== entryForm.quantity) {
      toast.error(`Debe registrar exactamente ${entryForm.quantity} serial(es). Tiene ${entryForm.serials.length}`);
      return;
    }
    try {
      await api.post(`/inventory/warehouses/${selectedWh}/entry`, {
        ...entryForm,
        unit_cost: entryForm.unit_cost || selectedEntryItem?.price_usd || 0,
      });
      toast.success('Entrada registrada');
      setEntryDialog(false);
      setEntryForm({ item_id: '', quantity: 1, unit_cost: 0, notes: '', serials: [] });
      fetchStock();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  // ==================== EXIT ====================
  const selectedExitItem = hardware.find(h => h.hardware_id === exitForm.item_id);
  const exitNeedsSerial = selectedExitItem && isSerializedType(selectedExitItem.type);

  const openExitForItem = (item) => {
    setExitForm({ item_id: item.item_id, quantity: 1, reference: '', client_name: '', notes: '', serials: [] });
    setAvailableSerials(item.serials || []);
    setExitDialog(true);
  };

  const toggleExitSerial = (s) => {
    setExitForm(prev => ({
      ...prev,
      serials: prev.serials.includes(s)
        ? prev.serials.filter(x => x !== s)
        : [...prev.serials, s]
    }));
  };

  const submitExit = async () => {
    if (!exitForm.item_id || exitForm.quantity < 1) { toast.error('Complete los campos'); return; }
    if (exitNeedsSerial && exitForm.serials.length !== exitForm.quantity) {
      toast.error(`Seleccione exactamente ${exitForm.quantity} serial(es)`);
      return;
    }
    try {
      await api.post(`/inventory/warehouses/${selectedWh}/exit`, exitForm);
      toast.success('Salida registrada');
      setExitDialog(false);
      fetchStock();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  // ==================== TRANSFER ====================
  const selectedTransferItem = hardware.find(h => h.hardware_id === transferForm.item_id);
  const transferNeedsSerial = selectedTransferItem && isSerializedType(selectedTransferItem.type);

  const openTransferForItem = (item) => {
    setTransferForm({ dest_warehouse_id: '', item_id: item.item_id, quantity: 1, notes: '', serials: [] });
    setTransferSerials(item.serials || []);
    setTransferDialog(true);
  };

  const submitTransfer = async () => {
    if (!transferForm.dest_warehouse_id || !transferForm.item_id || transferForm.quantity < 1) {
      toast.error('Complete todos los campos');
      return;
    }
    if (transferNeedsSerial && transferForm.serials.length !== transferForm.quantity) {
      toast.error(`Seleccione exactamente ${transferForm.quantity} serial(es)`);
      return;
    }
    try {
      await api.post('/inventory/transfer', {
        source_warehouse_id: selectedWh,
        ...transferForm,
      });
      toast.success('Transferencia completada');
      setTransferDialog(false);
      fetchStock();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  // ==================== KARDEX (DRILL-DOWN) ====================
  const openKardex = async (item) => {
    setKardexLoading(true);
    setKardexOpen(true);
    setKardexData(null);
    try {
      const res = await api.get(`/inventory/warehouses/${selectedWh}/kardex/${item.item_id}`);
      setKardexData(res.data);
    } catch {
      toast.error('Error al cargar el Kardex');
      setKardexOpen(false);
    } finally {
      setKardexLoading(false);
    }
  };

  // ==================== BUSCADOR INVERSO POR CLIENTE ====================
  const searchByClient = async () => {
    if (!clientSearch || clientSearch.length < 2) {
      toast.error('Ingrese al menos 2 caracteres');
      return;
    }
    setClientSearchLoading(true);
    try {
      const res = await api.get(`/inventory/movements/search?client_name=${encodeURIComponent(clientSearch)}`);
      setClientSearchResults(res.data);
    } catch {
      toast.error('Error en búsqueda');
    } finally {
      setClientSearchLoading(false);
    }
  };

  // ==================== COMPONENTE POPOVER DESTINATARIO ====================
  const DestinationPopover = ({ movementId, clientName, clientId }) => {
    const [destData, setDestData] = useState(null);
    const [destLoading, setDestLoading] = useState(false);
    const [destOpen, setDestOpen] = useState(false);

    const fetchDestination = async () => {
      if (destData) return;
      setDestLoading(true);
      try {
        const res = await api.get(`/inventory/movements/${movementId}/destination`);
        setDestData(res.data);
      } catch { toast.error('Error al obtener destino'); }
      finally { setDestLoading(false); }
    };

    return (
      <Popover open={destOpen} onOpenChange={(o) => { setDestOpen(o); if (o) fetchDestination(); }}>
        <PopoverTrigger asChild>
          <button className="inline-flex items-center gap-1 px-2 py-1 text-xs text-teal-700 bg-teal-50 hover:bg-teal-100 border border-teal-200 rounded transition-colors"
            data-testid={`btn-destination-${movementId}`}>
            <Eye size={12} /> Ver Destinatario
          </button>
        </PopoverTrigger>
        <PopoverContent className="w-80 p-0" align="end" data-testid={`dest-popover-${movementId}`}>
          {destLoading ? (
            <div className="flex items-center justify-center py-6">
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-teal-600" />
            </div>
          ) : destData ? (
            <div className="p-4 space-y-3">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs text-slate-500 uppercase font-semibold">Cliente / Razón Social</p>
                  {destData.client_id ? (
                    <button onClick={() => navigate('/clients')} className="text-sm font-bold text-teal-700 hover:underline flex items-center gap-1"
                      data-testid={`dest-client-link-${movementId}`}>
                      {destData.client_name} <ExternalLink size={11} />
                    </button>
                  ) : (
                    <p className="text-sm font-bold text-slate-900">{destData.client_name || '—'}</p>
                  )}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-slate-500">RIF:</span>
                  <p className="font-medium text-slate-800">{destData.client_rif || '—'}</p>
                </div>
                <div>
                  <span className="text-slate-500">Cotización:</span>
                  <p className="font-medium text-slate-800">{destData.quote_number || '—'}</p>
                </div>
              </div>
              {destData.serials?.length > 0 && (
                <div>
                  <p className="text-xs text-slate-500 mb-1">Seriales Despachados:</p>
                  <div className="flex flex-wrap gap-1">
                    {destData.serials.map(s => (
                      <span key={s} className="px-2 py-0.5 text-xs bg-purple-50 text-purple-700 border border-purple-200 rounded">{s}</span>
                    ))}
                  </div>
                </div>
              )}
              <div className="text-xs text-slate-400 pt-1 border-t">
                {destData.item_name} — Cant: {destData.quantity} — {(destData.date || '').slice(0, 10)}
              </div>
            </div>
          ) : null}
        </PopoverContent>
      </Popover>
    );
  };

  const currentWh = warehouses.find(w => w.warehouse_id === selectedWh);

  if (loading) {
    return (
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center"><div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-600" /></div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 p-8" data-testid="inventory-page">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-3xl font-bold text-slate-900 font-manrope flex items-center gap-3">
                <Warehouse size={28} className="text-teal-600" />
                Inventarios
              </h1>
              <p className="text-sm text-slate-500 mt-1">Control multialmacén con trazabilidad por serial</p>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => { setShowClientSearch(true); setClientSearchResults([]); setClientSearch(''); }}
                data-testid="btn-client-search">
                <Search size={14} className="mr-1.5" />Buscar por Cliente
              </Button>
              <Button onClick={() => { setWhForm({ name: '', location: '', notes: '', responsible_user_id: '' }); setWhEditing(null); setWhDialog(true); }}
                data-testid="add-warehouse-btn" className="bg-teal-600 hover:bg-teal-700 text-white">
                <Plus size={16} className="mr-1.5" />Nuevo Almacén
              </Button>
            </div>
          </div>

          {/* Warehouse selector */}
          <div className="flex items-center gap-3 mb-6">
            <div className="flex-1">
              <Select value={selectedWh || ''} onValueChange={setSelectedWh}>
                <SelectTrigger data-testid="select-warehouse" className="bg-white">
                  <SelectValue placeholder="Seleccione almacén..." />
                </SelectTrigger>
                <SelectContent>
                  {warehouses.map(w => (
                    <SelectItem key={w.warehouse_id} value={w.warehouse_id}>
                      <span className="flex items-center gap-2">
                        <Building2 size={14} className="text-teal-600" />
                        {w.name} {w.location && <span className="text-xs text-slate-400">— {w.location}</span>}
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {currentWh && (
              <>
                <Button size="sm" variant="outline" onClick={() => { setWhForm({ name: currentWh.name, location: currentWh.location || '', notes: currentWh.notes || '', responsible_user_id: currentWh.responsible_user_id || '' }); setWhEditing(currentWh.warehouse_id); setWhDialog(true); }}>
                  <Pencil size={14} className="mr-1" />Editar
                </Button>
                <Button size="sm" variant="outline" className="text-red-500 hover:text-red-700"
                  onClick={() => setDeleteWh({ open: true, id: currentWh.warehouse_id, name: currentWh.name })}>
                  <Trash2 size={14} />
                </Button>
              </>
            )}
          </div>
          {currentWh?.responsible_name && (
            <p className="text-xs text-slate-500 -mt-4 mb-4 ml-1">
              Responsable: <strong>{currentWh.responsible_name}</strong> ({currentWh.responsible_email})
            </p>
          )}

          {!selectedWh ? (
            <div className="bg-white rounded-lg border border-slate-200 p-12 text-center">
              <Warehouse size={48} className="mx-auto text-slate-300 mb-3" />
              <p className="text-slate-500">Cree o seleccione un almacén para comenzar</p>
            </div>
          ) : (
            <>
              {/* Action buttons */}
              <div className="flex gap-2 mb-4">
                <Button size="sm" onClick={() => { setEntryForm({ item_id: '', quantity: 1, unit_cost: 0, notes: '', serials: [] }); setEntryDialog(true); }}
                  data-testid="btn-entry" className="bg-emerald-600 hover:bg-emerald-700 text-white">
                  <PackagePlus size={14} className="mr-1.5" />Entrada
                </Button>
                <Button size="sm" variant="outline" onClick={() => setTab(tab === 'stock' ? 'movements' : 'stock')} data-testid="btn-toggle-tab">
                  {tab === 'stock' ? <><History size={14} className="mr-1.5" />Movimientos</> : <><Box size={14} className="mr-1.5" />Stock</>}
                </Button>
              </div>

              {/* Stock Tab */}
              {tab === 'stock' && (
                <div className="bg-white rounded-lg border border-slate-200 overflow-hidden" data-testid="stock-table">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 border-b">
                      <tr>
                        <th className="px-4 py-3 text-left font-medium text-slate-600">Ítem</th>
                        <th className="px-4 py-3 text-center font-medium text-slate-600">Tipo</th>
                        <th className="px-4 py-3 text-center font-medium text-slate-600">Saldo</th>
                        <th className="px-4 py-3 text-center font-medium text-slate-600">Stock Mín.</th>
                        <th className="px-4 py-3 text-center font-medium text-slate-600">Costo Prom.</th>
                        <th className="px-4 py-3 text-center font-medium text-slate-600">Seriales</th>
                        <th className="px-4 py-3 text-right font-medium text-slate-600">Acciones</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stock.length === 0 ? (
                        <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Sin stock en este almacén</td></tr>
                      ) : stock.map(item => (
                        <tr key={item.item_id}
                          className={`border-b cursor-pointer transition-colors group ${item.below_min ? 'bg-red-50 hover:bg-red-100/70' : 'hover:bg-teal-50/50'}`}
                          onClick={() => openKardex(item)}
                          data-testid={`stock-row-${item.item_id}`}>
                          <td className="px-4 py-3 font-medium text-slate-900">
                            <span className="flex items-center gap-2">
                              {item.below_min && <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />}
                              {item.item_name}
                              <ChevronRight size={14} className="text-slate-300 group-hover:text-teal-500 transition-colors" />
                            </span>
                          </td>
                          <td className="px-4 py-3 text-center">
                            <span className={`px-2 py-0.5 text-xs rounded ${item.requires_serial ? 'bg-purple-100 text-purple-700' : 'bg-slate-100 text-slate-600'}`}>
                              {item.item_type}
                            </span>
                          </td>
                          <td className={`px-4 py-3 text-center font-bold ${item.below_min ? 'text-red-600' : 'text-slate-900'}`}
                            data-testid={`stock-qty-${item.item_id}`}>
                            {item.quantity}
                          </td>
                          <td className="px-4 py-3 text-center" onClick={e => e.stopPropagation()}>
                            <input
                              type="number"
                              min={0}
                              defaultValue={item.min_stock || 0}
                              onBlur={e => {
                                const v = parseInt(e.target.value) || 0;
                                if (v !== (item.min_stock || 0)) saveMinStock(item.item_id, v);
                              }}
                              onKeyDown={e => { if (e.key === 'Enter') e.target.blur(); }}
                              className={`w-16 h-7 text-center text-xs border rounded ${item.below_min ? 'border-red-300 bg-red-50 text-red-700 font-bold' : 'border-slate-200'}`}
                              data-testid={`min-stock-${item.item_id}`}
                            />
                          </td>
                          <td className="px-4 py-3 text-center text-slate-600">${item.avg_cost?.toFixed(2)}</td>
                          <td className="px-4 py-3 text-center">
                            {item.requires_serial ? (
                              <span className="text-xs text-purple-600">{item.serials?.length || 0} registrados</span>
                            ) : <span className="text-xs text-slate-400">N/A</span>}
                          </td>
                          <td className="px-4 py-3 text-right" onClick={e => e.stopPropagation()}>
                            {item.quantity > 0 && (
                              <div className="flex justify-end gap-1">
                                <Button size="sm" variant="ghost" className="h-7 text-xs text-red-600 hover:text-red-800"
                                  onClick={() => openExitForItem(item)} data-testid={`btn-exit-${item.item_id}`}>
                                  <PackageMinus size={12} className="mr-1" />Salida
                                </Button>
                                {warehouses.length > 1 && (
                                  <Button size="sm" variant="ghost" className="h-7 text-xs text-blue-600 hover:text-blue-800"
                                    onClick={() => openTransferForItem(item)} data-testid={`btn-transfer-${item.item_id}`}>
                                    <ArrowLeftRight size={12} className="mr-1" />Transferir
                                  </Button>
                                )}
                              </div>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Movements Tab */}
              {tab === 'movements' && (
                <div className="bg-white rounded-lg border border-slate-200 overflow-hidden" data-testid="movements-table">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 border-b">
                      <tr>
                        <th className="px-4 py-3 text-left font-medium text-slate-600">Fecha</th>
                        <th className="px-4 py-3 text-left font-medium text-slate-600">Tipo</th>
                        <th className="px-4 py-3 text-left font-medium text-slate-600">Ítem</th>
                        <th className="px-4 py-3 text-center font-medium text-slate-600">Cant.</th>
                        <th className="px-4 py-3 text-left font-medium text-slate-600">Referencia</th>
                        <th className="px-4 py-3 text-left font-medium text-slate-600">Por</th>
                      </tr>
                    </thead>
                    <tbody>
                      {movements.length === 0 ? (
                        <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Sin movimientos</td></tr>
                      ) : movements.map(m => {
                        const ml = MOV_LABELS[m.movement_type] || { label: m.movement_type, color: 'bg-slate-100 text-slate-600', icon: '?' };
                        return (
                          <tr key={m.movement_id} className="border-b hover:bg-slate-50" data-testid={`mov-${m.movement_id}`}>
                            <td className="px-4 py-2.5 text-xs text-slate-500">{(m.created_at || '').slice(0, 16).replace('T', ' ')}</td>
                            <td className="px-4 py-2.5">
                              <span className={`px-2 py-0.5 text-xs font-medium rounded ${ml.color}`}>{ml.icon} {ml.label}</span>
                            </td>
                            <td className="px-4 py-2.5 text-slate-900">{m.item_name}</td>
                            <td className="px-4 py-2.5 text-center font-medium">{m.quantity}</td>
                            <td className="px-4 py-2.5 text-xs text-slate-500">{m.reference || m.client_name || m.notes || '—'}</td>
                            <td className="px-4 py-2.5 text-xs text-slate-400">{m.created_by}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>

        {/* ==================== WAREHOUSE DIALOG ==================== */}
        <Dialog open={whDialog} onOpenChange={setWhDialog}>
          <DialogContent className="max-w-sm" data-testid="warehouse-dialog">
            <DialogHeader><DialogTitle>{whEditing ? 'Editar' : 'Nuevo'} Almacén</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div><Label>Nombre *</Label><Input value={whForm.name} onChange={e => setWhForm({ ...whForm, name: e.target.value })} data-testid="wh-name" /></div>
              <div><Label>Ubicación</Label><Input value={whForm.location} onChange={e => setWhForm({ ...whForm, location: e.target.value })} data-testid="wh-location" /></div>
              <div>
                <Label>Responsable de Almacén</Label>
                <Select value={whForm.responsible_user_id} onValueChange={v => setWhForm({ ...whForm, responsible_user_id: v })}>
                  <SelectTrigger data-testid="wh-responsible">
                    <SelectValue placeholder="Seleccione responsable..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">— Sin responsable —</SelectItem>
                    {users.map(u => (
                      <SelectItem key={u.user_id} value={u.user_id}>
                        {u.full_name} <span className="text-xs text-slate-400">({u.email})</span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div><Label>Notas</Label><Input value={whForm.notes} onChange={e => setWhForm({ ...whForm, notes: e.target.value })} /></div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setWhDialog(false)}>Cancelar</Button>
                <Button onClick={saveWarehouse} data-testid="wh-save" className="bg-teal-600 hover:bg-teal-700 text-white">{whEditing ? 'Actualizar' : 'Crear'}</Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* ==================== ENTRY DIALOG ==================== */}
        <Dialog open={entryDialog} onOpenChange={setEntryDialog}>
          <DialogContent className="max-w-lg" data-testid="entry-dialog">
            <DialogHeader><DialogTitle className="flex items-center gap-2"><PackagePlus size={20} className="text-emerald-600" />Entrada de Inventario</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div>
                <Label>Bien / Servicio *</Label>
                <Select value={entryForm.item_id} onValueChange={v => {
                  const hw = hardware.find(h => h.hardware_id === v);
                  setEntryForm({ ...entryForm, item_id: v, unit_cost: hw?.price_usd || 0, serials: [] });
                }}>
                  <SelectTrigger data-testid="entry-item"><SelectValue placeholder="Seleccione..." /></SelectTrigger>
                  <SelectContent>
                    {hardware.map(h => (
                      <SelectItem key={h.hardware_id} value={h.hardware_id}>
                        <span className="flex items-center gap-2">
                          {isSerializedType(h.type) ? <Cpu size={12} className="text-purple-500" /> : <Box size={12} className="text-slate-400" />}
                          {h.name} <span className="text-xs text-slate-400">({h.type})</span>
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><Label>Cantidad *</Label><Input type="number" min={1} value={entryForm.quantity} onChange={e => setEntryForm({ ...entryForm, quantity: parseInt(e.target.value) || 1 })} data-testid="entry-qty" /></div>
                <div><Label>Costo Unitario ($)</Label><Input type="number" step="0.01" value={entryForm.unit_cost} onChange={e => setEntryForm({ ...entryForm, unit_cost: parseFloat(e.target.value) || 0 })} data-testid="entry-cost" /></div>
              </div>
              <div><Label>Notas</Label><Input value={entryForm.notes} onChange={e => setEntryForm({ ...entryForm, notes: e.target.value })} /></div>

              {/* Seriales (solo hardware crítico) */}
              {entryNeedsSerial && (
                <div className="bg-purple-50 border border-purple-200 rounded-lg p-3 space-y-2">
                  <p className="text-xs font-semibold text-purple-700 uppercase">Seriales obligatorios ({entryForm.serials.length}/{entryForm.quantity})</p>
                  <div className="flex gap-2">
                    <Input value={serialInput} onChange={e => setSerialInput(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addSerial(); } }}
                      placeholder="Escriba serial y Enter..." className="flex-1 text-sm" data-testid="serial-input" />
                    <Button size="sm" variant="outline" onClick={addSerial}>+</Button>
                    <label className="cursor-pointer">
                      <input type="file" className="hidden" accept=".xlsx,.xls,.csv" onChange={handleEntryExcel} />
                      <Button size="sm" variant="outline" className="pointer-events-none"><Upload size={12} className="mr-1" />Excel</Button>
                    </label>
                  </div>
                  {entryForm.serials.length > 0 && (
                    <div className="flex flex-wrap gap-1 max-h-32 overflow-y-auto">
                      {entryForm.serials.map((s, i) => (
                        <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-white border border-purple-200 rounded">
                          {s}
                          <button onClick={() => setEntryForm(prev => ({ ...prev, serials: prev.serials.filter((_, j) => j !== i) }))} className="text-red-400 hover:text-red-600"><X size={10} /></button>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={() => setEntryDialog(false)}>Cancelar</Button>
                <Button onClick={submitEntry} data-testid="entry-submit" className="bg-emerald-600 hover:bg-emerald-700 text-white"
                  disabled={!entryForm.item_id || entryForm.quantity < 1 || (entryNeedsSerial && entryForm.serials.length !== entryForm.quantity)}>
                  Registrar Entrada
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* ==================== EXIT DIALOG ==================== */}
        <Dialog open={exitDialog} onOpenChange={setExitDialog}>
          <DialogContent className="max-w-lg" data-testid="exit-dialog">
            <DialogHeader><DialogTitle className="flex items-center gap-2"><PackageMinus size={20} className="text-red-600" />Salida de Inventario</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <p className="text-sm text-slate-700">Ítem: <strong>{hardware.find(h => h.hardware_id === exitForm.item_id)?.name}</strong></p>
              <div className="grid grid-cols-2 gap-3">
                <div><Label>Cantidad *</Label><Input type="number" min={1} value={exitForm.quantity} onChange={e => setExitForm({ ...exitForm, quantity: parseInt(e.target.value) || 1 })} data-testid="exit-qty" /></div>
                <div><Label>Referencia</Label><Input value={exitForm.reference} onChange={e => setExitForm({ ...exitForm, reference: e.target.value })} placeholder="COT-XXXX..." /></div>
              </div>
              <div><Label>Cliente</Label><Input value={exitForm.client_name} onChange={e => setExitForm({ ...exitForm, client_name: e.target.value })} placeholder="Nombre del cliente..." /></div>
              <div><Label>Notas</Label><Input value={exitForm.notes} onChange={e => setExitForm({ ...exitForm, notes: e.target.value })} /></div>

              {exitNeedsSerial && availableSerials.length > 0 && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-3 space-y-2">
                  <p className="text-xs font-semibold text-red-700 uppercase">Seleccione seriales ({exitForm.serials.length}/{exitForm.quantity})</p>
                  <div className="flex flex-wrap gap-1 max-h-40 overflow-y-auto">
                    {availableSerials.map(s => (
                      <button key={s} onClick={() => toggleExitSerial(s)}
                        className={`px-2 py-1 text-xs rounded border transition-colors ${exitForm.serials.includes(s) ? 'bg-red-600 text-white border-red-600' : 'bg-white text-slate-700 border-slate-300 hover:border-red-400'}`}
                        data-testid={`exit-serial-${s}`}>
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={() => setExitDialog(false)}>Cancelar</Button>
                <Button onClick={submitExit} data-testid="exit-submit" className="bg-red-600 hover:bg-red-700 text-white"
                  disabled={exitForm.quantity < 1 || (exitNeedsSerial && exitForm.serials.length !== exitForm.quantity)}>
                  Registrar Salida
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* ==================== TRANSFER DIALOG ==================== */}
        <Dialog open={transferDialog} onOpenChange={setTransferDialog}>
          <DialogContent className="max-w-lg" data-testid="transfer-dialog">
            <DialogHeader><DialogTitle className="flex items-center gap-2"><ArrowLeftRight size={20} className="text-blue-600" />Transferencia entre Almacenes</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <p className="text-sm text-slate-700">Origen: <strong>{currentWh?.name}</strong> | Ítem: <strong>{hardware.find(h => h.hardware_id === transferForm.item_id)?.name}</strong></p>
              <div>
                <Label>Almacén Destino *</Label>
                <Select value={transferForm.dest_warehouse_id} onValueChange={v => setTransferForm({ ...transferForm, dest_warehouse_id: v })}>
                  <SelectTrigger data-testid="transfer-dest"><SelectValue placeholder="Seleccione destino..." /></SelectTrigger>
                  <SelectContent>
                    {warehouses.filter(w => w.warehouse_id !== selectedWh).map(w => (
                      <SelectItem key={w.warehouse_id} value={w.warehouse_id}>{w.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div><Label>Cantidad *</Label><Input type="number" min={1} value={transferForm.quantity} onChange={e => setTransferForm({ ...transferForm, quantity: parseInt(e.target.value) || 1 })} data-testid="transfer-qty" /></div>
              <div><Label>Notas</Label><Input value={transferForm.notes} onChange={e => setTransferForm({ ...transferForm, notes: e.target.value })} /></div>

              {transferNeedsSerial && transferSerials.length > 0 && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 space-y-2">
                  <p className="text-xs font-semibold text-blue-700 uppercase">Seleccione seriales ({transferForm.serials.length}/{transferForm.quantity})</p>
                  <div className="flex flex-wrap gap-1 max-h-40 overflow-y-auto">
                    {transferSerials.map(s => (
                      <button key={s} onClick={() => setTransferForm(prev => ({
                        ...prev,
                        serials: prev.serials.includes(s) ? prev.serials.filter(x => x !== s) : [...prev.serials, s]
                      }))}
                        className={`px-2 py-1 text-xs rounded border transition-colors ${transferForm.serials.includes(s) ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-slate-700 border-slate-300 hover:border-blue-400'}`}>
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={() => setTransferDialog(false)}>Cancelar</Button>
                <Button onClick={submitTransfer} data-testid="transfer-submit" className="bg-blue-600 hover:bg-blue-700 text-white"
                  disabled={!transferForm.dest_warehouse_id || transferForm.quantity < 1 || (transferNeedsSerial && transferForm.serials.length !== transferForm.quantity)}>
                  Transferir
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* Delete WH Confirm */}
        <AlertDialog open={deleteWh.open} onOpenChange={o => setDeleteWh({ ...deleteWh, open: o })}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Eliminar Almacén</AlertDialogTitle>
              <AlertDialogDescription>¿Eliminar "<strong>{deleteWh.name}</strong>"? Solo se puede eliminar si no tiene movimientos.</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancelar</AlertDialogCancel>
              <AlertDialogAction onClick={handleDeleteWh} className="bg-red-600 hover:bg-red-700 text-white" data-testid="confirm-delete-wh">Eliminar</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* ==================== KARDEX DEL PRODUCTO ==================== */}
        <Dialog open={kardexOpen} onOpenChange={setKardexOpen}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto" data-testid="kardex-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-lg">
                <History size={20} className="text-teal-600" />
                Kardex del Producto
              </DialogTitle>
              {kardexData && (
                <p className="text-sm text-slate-500">
                  <strong>{kardexData.item_name}</strong> ({kardexData.item_type}) — {currentWh?.name || ''}
                </p>
              )}
            </DialogHeader>

            {kardexLoading ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-600" />
              </div>
            ) : kardexData ? (
              <div>
                <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
                  <table className="w-full text-sm" data-testid="kardex-table">
                    <thead className="bg-slate-50 border-b">
                      <tr>
                        <th className="px-3 py-2.5 text-left text-xs font-medium text-slate-600">Fecha</th>
                        <th className="px-3 py-2.5 text-left text-xs font-medium text-slate-600">Tipo</th>
                        <th className="px-3 py-2.5 text-center text-xs font-medium text-slate-600">Cantidad</th>
                        <th className="px-3 py-2.5 text-center text-xs font-medium text-slate-600 bg-teal-50 text-teal-700">Saldo</th>
                        <th className="px-3 py-2.5 text-left text-xs font-medium text-slate-600">Seriales</th>
                        <th className="px-3 py-2.5 text-left text-xs font-medium text-slate-600">Referencia</th>
                        <th className="px-3 py-2.5 text-left text-xs font-medium text-slate-600">Por</th>
                        <th className="px-3 py-2.5 text-center text-xs font-medium text-slate-600">Destino</th>
                      </tr>
                    </thead>
                    <tbody>
                      {kardexData.movements.length === 0 ? (
                        <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-400">Sin movimientos</td></tr>
                      ) : kardexData.movements.map(m => {
                        const ml = MOV_LABELS[m.movement_type] || { label: m.movement_type, color: 'bg-slate-100 text-slate-600', icon: '?' };
                        const isSalida = m.movement_type === 'salida';
                        return (
                          <tr key={m.movement_id} className={`border-b hover:bg-slate-50 ${isSalida ? 'bg-red-50/30' : ''}`} data-testid={`kardex-row-${m.movement_id}`}>
                            <td className="px-3 py-2 text-xs text-slate-500">{(m.date || '').slice(0, 16).replace('T', ' ')}</td>
                            <td className="px-3 py-2">
                              <span className={`px-2 py-0.5 text-xs font-medium rounded ${ml.color}`}>{ml.icon} {ml.label}</span>
                            </td>
                            <td className={`px-3 py-2 text-center font-semibold ${m.signed_qty > 0 ? 'text-emerald-700' : 'text-red-700'}`}>
                              {m.signed_qty > 0 ? '+' : ''}{m.signed_qty}
                            </td>
                            <td className="px-3 py-2 text-center font-bold text-teal-700 bg-teal-50/50">{m.saldo}</td>
                            <td className="px-3 py-2 text-xs text-slate-500 max-w-[150px] truncate" title={m.serials?.join(', ')}>
                              {m.serials?.length > 0 ? m.serials.join(', ') : '—'}
                            </td>
                            <td className="px-3 py-2 text-xs text-slate-500">{m.reference || m.notes || '—'}</td>
                            <td className="px-3 py-2 text-xs text-slate-400">{m.created_by || '—'}</td>
                            <td className="px-3 py-2 text-center">
                              {isSalida && (m.client_name || m.client_id) ? (
                                <DestinationPopover movementId={m.movement_id} clientName={m.client_name} clientId={m.client_id} />
                              ) : (
                                <span className="text-xs text-slate-300">—</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                {/* Saldo final */}
                <div className="mt-3 flex items-center justify-end gap-4 px-1">
                  <span className="text-sm text-slate-500">Saldo Final:</span>
                  <span className="text-xl font-bold text-teal-700" data-testid="kardex-saldo-final">{kardexData.saldo_final}</span>
                </div>
              </div>
            ) : null}
          </DialogContent>
        </Dialog>

        {/* ==================== BUSCADOR INVERSO POR CLIENTE ==================== */}
        <Dialog open={showClientSearch} onOpenChange={setShowClientSearch}>
          <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto" data-testid="client-search-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Search size={20} className="text-teal-600" />
                Buscar Entregas por Cliente
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="flex gap-2">
                <Input
                  value={clientSearch}
                  onChange={e => setClientSearch(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') searchByClient(); }}
                  placeholder="Nombre del cliente..."
                  data-testid="client-search-input"
                />
                <Button onClick={searchByClient} disabled={clientSearchLoading} className="bg-teal-600 hover:bg-teal-700 text-white" data-testid="client-search-btn">
                  {clientSearchLoading ? 'Buscando...' : 'Buscar'}
                </Button>
              </div>

              {clientSearchResults.length > 0 && (
                <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
                  <table className="w-full text-sm" data-testid="client-search-results">
                    <thead className="bg-slate-50 border-b">
                      <tr>
                        <th className="px-3 py-2.5 text-left text-xs font-medium text-slate-600">Fecha</th>
                        <th className="px-3 py-2.5 text-left text-xs font-medium text-slate-600">Producto</th>
                        <th className="px-3 py-2.5 text-center text-xs font-medium text-slate-600">Cant.</th>
                        <th className="px-3 py-2.5 text-left text-xs font-medium text-slate-600">Seriales</th>
                        <th className="px-3 py-2.5 text-left text-xs font-medium text-slate-600">Cliente</th>
                        <th className="px-3 py-2.5 text-left text-xs font-medium text-slate-600">Referencia</th>
                      </tr>
                    </thead>
                    <tbody>
                      {clientSearchResults.map(m => (
                        <tr key={m.movement_id} className="border-b hover:bg-slate-50">
                          <td className="px-3 py-2 text-xs text-slate-500">{(m.created_at || '').slice(0, 16).replace('T', ' ')}</td>
                          <td className="px-3 py-2 text-slate-900">{m.item_name}</td>
                          <td className="px-3 py-2 text-center font-medium">{m.quantity}</td>
                          <td className="px-3 py-2 text-xs text-slate-500">{m.serials?.length > 0 ? m.serials.join(', ') : 'N/A'}</td>
                          <td className="px-3 py-2">
                            {m.client_id ? (
                              <button onClick={() => { setShowClientSearch(false); navigate(`/clients`); }}
                                className="text-teal-600 hover:underline text-sm font-medium flex items-center gap-1">
                                {m.client_name} <ExternalLink size={10} />
                              </button>
                            ) : (
                              <span className="text-sm">{m.client_name || '—'}</span>
                            )}
                          </td>
                          <td className="px-3 py-2 text-xs text-slate-500">{m.reference || m.quote_number || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="px-4 py-2 text-xs text-slate-400 bg-slate-50 border-t">
                    {clientSearchResults.length} resultado(s) encontrado(s)
                  </div>
                </div>
              )}

              {clientSearchResults.length === 0 && clientSearch && !clientSearchLoading && (
                <p className="text-sm text-slate-400 text-center py-6">Sin resultados para "{clientSearch}"</p>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
}
