import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import DebouncedInput from '../components/DebouncedInput';
import { Popover, PopoverContent, PopoverTrigger } from '../components/ui/popover';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog';
import { Warehouse, Plus, Trash2, PackagePlus, PackageMinus, ArrowLeftRight, History, Box, Cpu, X, Upload, Building2, Pencil, Search, Eye, ExternalLink, ChevronRight, FileDown, ShieldCheck, AlertTriangle, CheckCircle2, FileText } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';
import { usePermission } from '../hooks/usePermission';
import { MigrationButtons } from '../components/MigrationButtons';

const SERIALIZED_TYPES = ['pos', 'pinpad', 'mpos'];
const isSerializedType = (t) => SERIALIZED_TYPES.includes((t || '').toLowerCase());

const MOV_LABELS = {
  entrada: { label: 'Entrada', color: 'bg-emerald-100 text-emerald-700', icon: '+' },
  salida: { label: 'Salida', color: 'bg-red-100 text-red-700', icon: '-' },
  transferencia_entrada: { label: 'Transf. Recibida', color: 'bg-blue-100 text-blue-700', icon: '+' },
  transferencia_salida: { label: 'Transf. Enviada', color: 'bg-orange-100 text-orange-700', icon: '-' },
};

export default function Inventory() {
  const { canEdit, hasSpecial, user: currentUser } = usePermission('inventarios');
  const canCreateWarehouse = canEdit || hasSpecial('inventarios:create_warehouse');
  const userAlmacen = currentUser?.almacen_asignado || null;
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
  const [entryForm, setEntryForm] = useState({ item_id: '', quantity: 1, unit_cost: 0, notes: '', serials: [], acquisition_date: '', supplier: '', invoice_ref: '' });
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

  // Certificación de precarga
  const [certDialog, setCertDialog] = useState(false);
  const [certMovement, setCertMovement] = useState(null);
  const [certResult, setCertResult] = useState(null);
  const [certLoading, setCertLoading] = useState(false);

  // Precarga toggle en entrada
  const [isPrecarga, setIsPrecarga] = useState(false);

  // ==================== EDICIÓN MANUAL DE MOVIMIENTOS (ADMIN) ====================
  const [editMovOpen, setEditMovOpen] = useState(false);
  const [editMov, setEditMov] = useState(null);  // documento original (snapshot)
  const [editForm, setEditForm] = useState({}); // valores actuales del form
  const [editSaving, setEditSaving] = useState(false);
  const [editAudits, setEditAudits] = useState([]);
  const [editTab, setEditTab] = useState('form'); // form | history

  const openEditMovement = async (m) => {
    setEditMov(m);
    setEditForm({
      item_id: m.item_id || '',
      item_name: m.item_name || '',
      item_type: m.item_type || '',
      movement_type: m.movement_type || '',
      quantity: m.quantity ?? 0,
      unit_cost: m.unit_cost ?? 0,
      warehouse_id: m.warehouse_id || '',
      serials: Array.isArray(m.serials) ? m.serials.join(', ') : (m.serials || ''),
      reference: m.reference || '',
      client_name: m.client_name || '',
      client_id: m.client_id || '',
      quote_id: m.quote_id || '',
      quote_number: m.quote_number || '',
      notes: m.notes || '',
      supplier: m.supplier || '',
      invoice_ref: m.invoice_ref || '',
      acquisition_date: m.acquisition_date || '',
      certification_status: m.certification_status || '',
      transfer_id: m.transfer_id || '',
    });
    setEditTab('form');
    setEditAudits([]);
    setEditMovOpen(true);
    // Carga el historial en paralelo
    try {
      const res = await api.get(`/inventory/movements/${m.movement_id}/audit`);
      setEditAudits(res.data?.audits || []);
    } catch {
      setEditAudits([]);
    }
  };

  const saveEditMovement = async () => {
    if (!editMov) return;
    setEditSaving(true);
    try {
      const payload = { ...editForm };
      // Normalizar números
      if (payload.quantity !== '' && payload.quantity !== null) payload.quantity = Number(payload.quantity);
      if (payload.unit_cost !== '' && payload.unit_cost !== null) payload.unit_cost = Number(payload.unit_cost);
      const res = await api.put(`/inventory/movements/${editMov.movement_id}`, payload);
      if (res.data?.changes_count === 0) {
        toast.info('No se detectaron cambios');
      } else {
        toast.success(`Movimiento actualizado · ${res.data.changes_count} campo(s)`);
      }
      // Refrescar listado y auditoría
      await fetchStock();
      const a = await api.get(`/inventory/movements/${editMov.movement_id}/audit`);
      setEditAudits(a.data?.audits || []);
      // Refrescar snapshot
      if (res.data?.movement) setEditMov(res.data.movement);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al guardar');
    } finally {
      setEditSaving(false);
    }
  };

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
  // Seriales solo para POS/Pinpad con clasificación "Bien" (activos rastreables)
  const entryNeedsSerial = selectedEntryItem && isSerializedType(selectedEntryItem.type) && selectedEntryItem.asset_type === 'Bien';

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
    if (!entryForm.acquisition_date) { toast.error('Seleccione la Fecha de Adquisición'); return; }
    if (entryNeedsSerial && entryForm.serials.length !== entryForm.quantity) {
      toast.error(`Debe registrar exactamente ${entryForm.quantity} serial(es). Tiene ${entryForm.serials.length}`);
      return;
    }
    try {
      await api.post(`/inventory/warehouses/${selectedWh}/entry`, {
        ...entryForm,
        unit_cost: entryForm.unit_cost || selectedEntryItem?.price_bs_usd || selectedEntryItem?.price_usd || 0,
        is_precarga: isPrecarga,
      });
      toast.success(isPrecarga ? 'Precarga registrada (pendiente certificación)' : 'Entrada registrada');
      setEntryDialog(false);
      setEntryForm({ item_id: '', quantity: 1, unit_cost: 0, notes: '', serials: [], acquisition_date: '', supplier: '', invoice_ref: '' });
      setIsPrecarga(false);
      fetchStock();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  // ==================== EXIT ====================
  const selectedExitItem = hardware.find(h => h.hardware_id === exitForm.item_id);
  const exitNeedsSerial = selectedExitItem && isSerializedType(selectedExitItem.type) && selectedExitItem.asset_type === 'Bien';

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

  // Excel upload for exit serials
  const [exitExcelAudit, setExitExcelAudit] = useState(null);
  const handleExitExcel = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !exitForm.item_id) return;
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await api.post(`/inventory/validate-serials-stock/${selectedWh}/${exitForm.item_id}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      if (res.data.has_errors) {
        setExitExcelAudit(res.data);
        const msgs = [];
        if (res.data.internal_duplicates?.length > 0) msgs.push(`${res.data.internal_duplicates.length} duplicado(s) interno(s)`);
        if (res.data.not_found_count > 0) msgs.push(`${res.data.not_found_count} no encontrado(s)`);
        toast.error(msgs.join(' y '));
      } else {
        setExitForm(prev => ({ ...prev, serials: res.data.valid, quantity: res.data.valid_count }));
        setExitExcelAudit(null);
        toast.success(`${res.data.valid_count} seriales cargados correctamente`);
      }
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al validar Excel'); }
    e.target.value = '';
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
  const transferNeedsSerial = selectedTransferItem && isSerializedType(selectedTransferItem.type) && selectedTransferItem.asset_type === 'Bien';

  const openTransferForItem = (item) => {
    setTransferForm({ dest_warehouse_id: '', item_id: item.item_id, quantity: 1, notes: '', serials: [] });
    setTransferSerials(item.serials || []);
    setTransferExcelAudit(null);
    setTransferDialog(true);
  };

  // Excel upload for transfer serials
  const [transferExcelAudit, setTransferExcelAudit] = useState(null);
  const handleTransferExcel = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !transferForm.item_id) return;
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await api.post(`/inventory/validate-serials-stock/${selectedWh}/${transferForm.item_id}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      if (res.data.has_errors) {
        setTransferExcelAudit(res.data);
        const msgs = [];
        if (res.data.internal_duplicates?.length > 0) msgs.push(`${res.data.internal_duplicates.length} duplicado(s) interno(s)`);
        if (res.data.not_found_count > 0) msgs.push(`${res.data.not_found_count} no encontrado(s)`);
        toast.error(msgs.join(' y '));
      } else {
        setTransferForm(prev => ({ ...prev, serials: res.data.valid, quantity: res.data.valid_count }));
        setTransferExcelAudit(null);
        toast.success(`${res.data.valid_count} seriales cargados correctamente`);
      }
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al validar Excel'); }
    e.target.value = '';
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
      const res = await api.post('/inventory/transfer', {
        source_warehouse_id: selectedWh,
        ...transferForm,
      });
      const pdfUrl = res.data.transfer_note_url;
      const trfNum = res.data.transfer_number;
      if (pdfUrl) {
        const backendUrl = process.env.REACT_APP_BACKEND_URL || '';
        toast.success(
          <div className="flex flex-col gap-1">
            <span>Transferencia {trfNum} completada</span>
            <a href={`${backendUrl}/api${pdfUrl}`} target="_blank" rel="noopener noreferrer"
              className="text-blue-600 underline text-xs flex items-center gap-1">
              <FileDown size={12} />Descargar Nota de Entrega PDF
            </a>
          </div>,
          { duration: 10000 }
        );
      } else {
        toast.success('Transferencia completada');
      }
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

  // ==================== CERTIFICACIÓN ====================
  const openCertification = (movement) => {
    setCertMovement(movement);
    setCertResult(null);
    setCertDialog(true);
  };

  const handleCertExcel = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !certMovement) return;
    setCertLoading(true);
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await api.post(`/inventory/validate-certification/${certMovement.movement_id}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setCertResult(res.data);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al validar');
    } finally {
      setCertLoading(false);
    }
    e.target.value = '';
  };

  const executeCertification = async (source) => {
    if (!certMovement) return;
    setCertLoading(true);
    try {
      const body = { source };
      if (source === 'excel' && certResult) {
        body.excel_serials = [...(certResult.matching || []), ...(certResult.only_in_excel || [])];
      }
      await api.post(`/inventory/certify/${certMovement.movement_id}`, body);
      toast.success('Certificación completada. Equipos ahora disponibles.');
      setCertDialog(false);
      setCertMovement(null);
      setCertResult(null);
      fetchStock();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al certificar');
    } finally {
      setCertLoading(false);
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
  // Jurisdicción: si el usuario tiene almacén asignado, solo puede editar ese almacén
  const canEditWarehouse = canEdit && (!userAlmacen || !selectedWh || userAlmacen === selectedWh);

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
              <Button variant="outline" size="sm" onClick={() => navigate('/inventory/accounting-report')}
                data-testid="btn-accounting-report" className="border-blue-300 text-blue-700 hover:bg-blue-50">
                <FileText size={14} className="mr-1.5" />Reporte Contable
              </Button>
              <Button variant="outline" size="sm" onClick={() => { setShowClientSearch(true); setClientSearchResults([]); setClientSearch(''); }}
                data-testid="btn-client-search">
                <Search size={14} className="mr-1.5" />Buscar por Cliente
              </Button>
              {canCreateWarehouse && <Button onClick={() => { setWhForm({ name: '', location: '', notes: '', responsible_user_id: '' }); setWhEditing(null); setWhDialog(true); }}
                data-testid="add-warehouse-btn" className="bg-teal-600 hover:bg-teal-700 text-white">
                <Plus size={16} className="mr-1.5" />Nuevo Almacén
              </Button>}
            </div>
          </div>

          <div className="flex justify-end mb-4">
            <MigrationButtons module="inventory-movements" label="Movimientos de Inventario" onImported={fetchAll} />
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
            {currentWh && canEditWarehouse && (
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
                {canEditWarehouse && <Button size="sm" onClick={() => {
                  const currentWh = warehouses.find(w => w.warehouse_id === selectedWh);
                  const isAux = currentWh && !currentWh.name?.toLowerCase().includes('chaguaramos') && !currentWh.name?.toLowerCase().includes('principal');
                  setEntryForm({ item_id: '', quantity: 1, unit_cost: 0, notes: '', serials: [], acquisition_date: '', supplier: isAux ? 'Almacen Principal (LCH)' : '', invoice_ref: '' });
                  setEntryDialog(true);
                }}
                  data-testid="btn-entry" className="bg-emerald-600 hover:bg-emerald-700 text-white">
                  <PackagePlus size={14} className="mr-1.5" />Entrada
                </Button>}
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
                        <th className="px-4 py-3 text-center font-medium text-slate-600">Costo Pond. (Bs)</th>
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
                            {item.has_precarga && (
                              <span className="ml-1.5 px-1.5 py-0.5 text-[10px] font-medium bg-amber-100 text-amber-700 border border-amber-200 rounded" title="En cuarentena técnica">
                                +{item.precarga_qty} precarga
                              </span>
                            )}
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
                              disabled={!canEditWarehouse}
                              className={`w-16 h-7 text-center text-xs border rounded ${item.below_min ? 'border-red-300 bg-red-50 text-red-700 font-bold' : 'border-slate-200'} ${!canEditWarehouse ? 'opacity-60 cursor-not-allowed' : ''}`}
                              data-testid={`min-stock-${item.item_id}`}
                            />
                          </td>
                          <td className="px-4 py-3 text-center text-slate-600">Bs {item.weighted_cost?.toFixed(2)}</td>
                          <td className="px-4 py-3 text-center">
                            {item.requires_serial ? (
                              <div className="flex flex-col items-center gap-0.5">
                                <span className="text-xs text-purple-600">{item.serials?.length || 0} disponibles</span>
                                {item.preassigned_count > 0 && (
                                  <span className="text-[10px] px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded font-medium">
                                    {item.preassigned_count} preasignado{item.preassigned_count > 1 ? 's' : ''}
                                  </span>
                                )}
                              </div>
                            ) : <span className="text-xs text-slate-400">N/A</span>}
                          </td>
                          <td className="px-4 py-3 text-right" onClick={e => e.stopPropagation()}>
                            <div className="flex flex-col gap-1 items-end">
                              {item.has_precarga && (
                                <div className="flex gap-1">
                                  {item.precarga_movements.map(pm => (
                                    <Button key={pm.movement_id} size="sm" variant="ghost"
                                      className="h-6 text-[10px] text-amber-700 hover:text-amber-900 bg-amber-50 hover:bg-amber-100 border border-amber-200"
                                      onClick={() => openCertification(pm)}
                                      data-testid={`btn-certify-${pm.movement_id}`}>
                                      <ShieldCheck size={11} className="mr-1" />Certificar
                                    </Button>
                                  ))}
                                </div>
                              )}
                              {canEditWarehouse && item.quantity > 0 && (
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
                            </div>
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
                        <th className="px-4 py-3 text-left font-medium text-slate-600">Item</th>
                        <th className="px-4 py-3 text-center font-medium text-slate-600">Cant.</th>
                        <th className="px-4 py-3 text-left font-medium text-slate-600">Proveedor</th>
                        <th className="px-4 py-3 text-left font-medium text-slate-600">Referencia</th>
                        <th className="px-4 py-3 text-left font-medium text-slate-600">Por</th>
                        <th className="px-4 py-3 text-center font-medium text-slate-600">PDF</th>
                        {currentUser?.role === 'admin' && <th className="px-4 py-3 text-center font-medium text-slate-600"></th>}
                      </tr>
                    </thead>
                    <tbody>
                      {movements.length === 0 ? (
                        <tr><td colSpan={currentUser?.role === 'admin' ? 9 : 8} className="px-4 py-8 text-center text-slate-400">Sin movimientos</td></tr>
                      ) : movements.map(m => {
                        const ml = MOV_LABELS[m.movement_type] || { label: m.movement_type, color: 'bg-slate-100 text-slate-600', icon: '?' };
                        const backendUrl = process.env.REACT_APP_BACKEND_URL || '';
                        return (
                          <tr key={m.movement_id} className="border-b hover:bg-slate-50" data-testid={`mov-${m.movement_id}`}>
                            <td className="px-4 py-2.5 text-xs text-slate-500">{(m.created_at || '').slice(0, 16).replace('T', ' ')}</td>
                            <td className="px-4 py-2.5">
                              <span className={`px-2 py-0.5 text-xs font-medium rounded ${ml.color}`}>{ml.icon} {ml.label}</span>
                              {m.certification_status === 'precarga' && (
                                <span className="ml-1 px-1.5 py-0.5 text-[10px] font-medium bg-amber-100 text-amber-700 border border-amber-200 rounded">Precarga</span>
                              )}
                            </td>
                            <td className="px-4 py-2.5 text-slate-900">{m.item_name}</td>
                            <td className="px-4 py-2.5 text-center font-medium">{m.quantity}</td>
                            <td className="px-4 py-2.5 text-xs text-slate-600">{m.supplier || '—'}</td>
                            <td className="px-4 py-2.5 text-xs text-slate-500">{m.invoice_ref || m.reference || m.client_name || '—'}</td>
                            <td className="px-4 py-2.5 text-xs text-slate-400">{m.created_by}</td>
                            <td className="px-4 py-2.5 text-center">
                              {m.transfer_note_url ? (
                                <a href={`${backendUrl}/api${m.transfer_note_url}`} target="_blank" rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 transition-colors"
                                  data-testid={`download-transfer-pdf-${m.movement_id}`}
                                  title="Descargar Nota de Transferencia">
                                  <FileDown size={14} />
                                </a>
                              ) : <span className="text-slate-300">—</span>}
                            </td>
                            {currentUser?.role === 'admin' && (
                              <td className="px-4 py-2.5 text-center">
                                <div className="inline-flex items-center gap-0.5">
                                  <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-slate-300 hover:text-blue-600" title="Editar movimiento (Admin)"
                                    data-testid={`edit-mov-${m.movement_id}`}
                                    onClick={() => openEditMovement(m)}>
                                    <Pencil size={13} />
                                  </Button>
                                  <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-slate-300 hover:text-red-600" title="Eliminar movimiento"
                                    data-testid={`delete-mov-${m.movement_id}`}
                                    onClick={async () => {
                                      if (!window.confirm(`Eliminar este movimiento de ${m.item_name}?`)) return;
                                      try {
                                        await api.delete(`/inventory/movements/${m.movement_id}`);
                                        toast.success('Movimiento eliminado');
                                        fetchStock();
                                      } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
                                    }}>
                                    <Trash2 size={13} />
                                  </Button>
                                </div>
                              </td>
                            )}
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
              <div><Label>Nombre *</Label><DebouncedInput value={whForm.name} onCommit={v => setWhForm(p => ({ ...p, name: v }))} data-testid="wh-name" /></div>
              <div><Label>Ubicación</Label><DebouncedInput value={whForm.location} onCommit={v => setWhForm(p => ({ ...p, location: v }))} data-testid="wh-location" /></div>
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
              <div><Label>Notas</Label><DebouncedInput value={whForm.notes} onCommit={v => setWhForm(p => ({ ...p, notes: v }))} /></div>
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
                  setEntryForm({ ...entryForm, item_id: v, unit_cost: hw?.price_bs_usd || hw?.price_usd || 0, serials: [], acquisition_date: entryForm.acquisition_date });
                }}>
                  <SelectTrigger data-testid="entry-item" className="truncate"><SelectValue placeholder="Seleccione..." /></SelectTrigger>
                  <SelectContent>
                    {hardware.filter(h => h.type !== 'Mantenimiento').map(h => (
                      <SelectItem key={h.hardware_id} value={h.hardware_id}>
                        <span className="flex items-center gap-2 min-w-0">
                          {isSerializedType(h.type) && h.asset_type === 'Bien' ? <Cpu size={12} className="text-purple-500 shrink-0" /> : <Box size={12} className="text-slate-400 shrink-0" />}
                          <span className="truncate">{h.name}</span>
                          <span className="text-xs text-slate-400 shrink-0">({h.type}{h.asset_type === 'Servicio' ? ' — Srv' : ''})</span>
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><Label>Cantidad *</Label><DebouncedInput type="number" min={1} value={entryForm.quantity} onCommit={v => setEntryForm(p => ({ ...p, quantity: parseInt(v) || 1 }))} data-testid="entry-qty" /></div>
                <div><Label>Costo Unitario (Bs)</Label><DebouncedInput type="number" step="0.01" value={entryForm.unit_cost} onCommit={v => setEntryForm(p => ({ ...p, unit_cost: parseFloat(v) || 0 }))} data-testid="entry-cost" /></div>
              </div>
              <div>
                <Label>Fecha de Adquisición *</Label>
                <Input type="date" value={entryForm.acquisition_date} onChange={e => setEntryForm(p => ({ ...p, acquisition_date: e.target.value }))} data-testid="entry-acquisition-date" className="w-full" />
              </div>
              <div><Label>Notas</Label><DebouncedInput value={entryForm.notes} onCommit={v => setEntryForm(p => ({ ...p, notes: v }))} /></div>

              {/* Proveedor y Referencia */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Proveedor</Label>
                  <Input
                    value={entryForm.supplier}
                    onChange={e => setEntryForm(p => ({ ...p, supplier: e.target.value.slice(0, 30) }))}
                    placeholder="Nombre del proveedor"
                    maxLength={30}
                    disabled={entryForm.supplier === 'Almacen Principal (LCH)'}
                    className={entryForm.supplier === 'Almacen Principal (LCH)' ? 'bg-slate-100' : ''}
                    data-testid="entry-supplier"
                  />
                  <p className="text-[10px] text-slate-400 text-right mt-0.5">{(entryForm.supplier || '').length}/30</p>
                </div>
                <div>
                  <Label>Referencia (Factura/NE)</Label>
                  <Input
                    value={entryForm.invoice_ref}
                    onChange={e => setEntryForm(p => ({ ...p, invoice_ref: e.target.value.slice(0, 20) }))}
                    placeholder="Nro. Factura/Nota"
                    maxLength={20}
                    data-testid="entry-invoice-ref"
                  />
                  <p className="text-[10px] text-slate-400 text-right mt-0.5">{(entryForm.invoice_ref || '').length}/20</p>
                </div>
              </div>

              {/* Toggle Precarga */}
              {entryNeedsSerial && (
                <label className="flex items-center gap-2 px-3 py-2 border border-amber-200 rounded-lg bg-amber-50 cursor-pointer select-none"
                  data-testid="precarga-toggle">
                  <input type="checkbox" checked={isPrecarga} onChange={e => setIsPrecarga(e.target.checked)}
                    className="accent-amber-600 w-4 h-4" />
                  <div>
                    <span className="text-sm font-medium text-amber-800">Registrar como Precarga</span>
                    <p className="text-[10px] text-amber-600">Los equipos quedarán en cuarentena técnica hasta ser certificados físicamente.</p>
                  </div>
                </label>
              )}

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
                  disabled={!entryForm.item_id || entryForm.quantity < 1 || !entryForm.acquisition_date || (entryNeedsSerial && entryForm.serials.length !== entryForm.quantity)}>
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
                <div><Label>Cantidad *</Label><DebouncedInput type="number" min={1} value={exitForm.quantity} onCommit={v => setExitForm(p => ({ ...p, quantity: parseInt(v) || 1 }))} data-testid="exit-qty" /></div>
                <div><Label>Referencia</Label><DebouncedInput value={exitForm.reference} onCommit={v => setExitForm(p => ({ ...p, reference: v }))} placeholder="COT-XXXX..." /></div>
              </div>
              <div><Label>Cliente</Label><DebouncedInput value={exitForm.client_name} onCommit={v => setExitForm(p => ({ ...p, client_name: v }))} placeholder="Nombre del cliente..." /></div>
              <div><Label>Notas</Label><DebouncedInput value={exitForm.notes} onCommit={v => setExitForm(p => ({ ...p, notes: v }))} /></div>

              {exitNeedsSerial && availableSerials.length > 0 && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold text-red-700 uppercase">Seleccione seriales ({exitForm.serials.length}/{exitForm.quantity})</p>
                    <label className="cursor-pointer" data-testid="exit-excel-upload">
                      <input type="file" className="hidden" accept=".xlsx,.xls,.csv" onChange={handleExitExcel} />
                      <span className="inline-flex items-center gap-1 px-2 py-1 text-[10px] font-medium bg-white border border-red-300 rounded text-red-700 hover:bg-red-100 cursor-pointer transition-colors">
                        <Upload size={10} />Cargar desde Excel
                      </span>
                    </label>
                  </div>
                  <div className="flex flex-wrap gap-1 max-h-40 overflow-y-auto">
                    {availableSerials.map(s => (
                      <button key={s} onClick={() => toggleExitSerial(s)}
                        className={`px-2 py-1 text-xs rounded border transition-colors ${exitForm.serials.includes(s) ? 'bg-red-600 text-white border-red-600' : 'bg-white text-slate-700 border-slate-300 hover:border-red-400'}`}
                        data-testid={`exit-serial-${s}`}>
                        {s}
                      </button>
                    ))}
                  </div>
                  {/* Excel audit */}
                  {exitExcelAudit && exitExcelAudit.has_errors && (
                    <div className="bg-white border border-red-300 rounded p-2 space-y-1">
                      {exitExcelAudit.internal_duplicates?.length > 0 && (
                        <div>
                          <div className="flex items-center gap-1">
                            <AlertTriangle size={12} className="text-orange-600" />
                            <p className="text-[10px] font-semibold text-orange-700">Seriales duplicados en el Excel:</p>
                          </div>
                          <div className="flex flex-wrap gap-1">
                            {exitExcelAudit.internal_duplicates.map((d, i) => (
                              <span key={i} className="px-1.5 py-0.5 text-[10px] bg-orange-100 text-orange-800 border border-orange-300 rounded">
                                {d.serial} (filas {d.row1} y {d.row2})
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                      {exitExcelAudit.not_found?.length > 0 && (
                        <div>
                          <div className="flex items-center gap-1">
                            <AlertTriangle size={12} className="text-red-600" />
                            <p className="text-[10px] font-semibold text-red-700">Seriales no encontrados en stock:</p>
                          </div>
                          <div className="flex flex-wrap gap-1">
                            {exitExcelAudit.not_found.map(s => (
                              <span key={s} className="px-1.5 py-0.5 text-[10px] bg-red-100 text-red-800 border border-red-300 rounded">{s}</span>
                            ))}
                          </div>
                        </div>
                      )}
                      {exitExcelAudit.valid_count > 0 && (
                        <button onClick={() => { setExitForm(prev => ({ ...prev, serials: exitExcelAudit.valid, quantity: exitExcelAudit.valid_count })); setExitExcelAudit(null); }}
                          className="text-[10px] text-blue-600 hover:underline">
                          Usar solo los {exitExcelAudit.valid_count} seriales validos
                        </button>
                      )}
                    </div>
                  )}
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
              <div><Label>Cantidad *</Label><DebouncedInput type="number" min={1} value={transferForm.quantity} onCommit={v => setTransferForm(p => ({ ...p, quantity: parseInt(v) || 1 }))} data-testid="transfer-qty" /></div>
              <div><Label>Notas</Label><DebouncedInput value={transferForm.notes} onCommit={v => setTransferForm(p => ({ ...p, notes: v }))} /></div>

              {transferNeedsSerial && transferSerials.length > 0 && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold text-blue-700 uppercase">Seleccione seriales ({transferForm.serials.length}/{transferForm.quantity})</p>
                    <label className="cursor-pointer" data-testid="transfer-excel-upload">
                      <input type="file" className="hidden" accept=".xlsx,.xls,.csv" onChange={handleTransferExcel} />
                      <span className="inline-flex items-center gap-1 px-2 py-1 text-[10px] font-medium bg-white border border-blue-300 rounded text-blue-700 hover:bg-blue-100 cursor-pointer transition-colors">
                        <Upload size={10} />Cargar desde Excel
                      </span>
                    </label>
                  </div>
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
                  {/* Excel audit */}
                  {transferExcelAudit && transferExcelAudit.has_errors && (
                    <div className="bg-white border border-blue-300 rounded p-2 space-y-1">
                      {transferExcelAudit.internal_duplicates?.length > 0 && (
                        <div>
                          <div className="flex items-center gap-1">
                            <AlertTriangle size={12} className="text-orange-600" />
                            <p className="text-[10px] font-semibold text-orange-700">Seriales duplicados en el Excel:</p>
                          </div>
                          <div className="flex flex-wrap gap-1">
                            {transferExcelAudit.internal_duplicates.map((d, i) => (
                              <span key={i} className="px-1.5 py-0.5 text-[10px] bg-orange-100 text-orange-800 border border-orange-300 rounded">
                                {d.serial} (filas {d.row1} y {d.row2})
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                      {transferExcelAudit.not_found?.length > 0 && (
                        <div>
                          <div className="flex items-center gap-1">
                            <AlertTriangle size={12} className="text-red-600" />
                            <p className="text-[10px] font-semibold text-red-700">Seriales no encontrados en stock:</p>
                          </div>
                          <div className="flex flex-wrap gap-1">
                            {transferExcelAudit.not_found.map(s => (
                              <span key={s} className="px-1.5 py-0.5 text-[10px] bg-red-100 text-red-800 border border-red-300 rounded">{s}</span>
                            ))}
                          </div>
                        </div>
                      )}
                      {transferExcelAudit.valid_count > 0 && (
                        <button onClick={() => { setTransferForm(prev => ({ ...prev, serials: transferExcelAudit.valid, quantity: transferExcelAudit.valid_count })); setTransferExcelAudit(null); }}
                          className="text-[10px] text-blue-600 hover:underline">
                          Usar solo los {transferExcelAudit.valid_count} seriales validos
                        </button>
                      )}
                    </div>
                  )}
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

        {/* ==================== CERTIFICACIÓN DE PRECARGA ==================== */}
        <Dialog open={certDialog} onOpenChange={(o) => { setCertDialog(o); if (!o) { setCertResult(null); setCertMovement(null); } }}>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="certification-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <ShieldCheck size={20} className="text-amber-600" />
                Certificacion de Precarga
              </DialogTitle>
            </DialogHeader>

            {certMovement && (
              <div className="space-y-4">
                {/* Info de la precarga */}
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 space-y-1">
                  <p className="text-sm text-amber-800"><strong>Seriales precargados:</strong> {certMovement.serials?.length || 0}</p>
                  <p className="text-xs text-amber-600">Fecha: {(certMovement.created_at || '').slice(0, 16).replace('T', ' ')}</p>
                  {certMovement.notes && <p className="text-xs text-amber-600">Notas: {certMovement.notes}</p>}
                  {certMovement.serials?.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2 max-h-24 overflow-y-auto">
                      {certMovement.serials.map(s => (
                        <span key={s} className="px-1.5 py-0.5 text-[10px] bg-white border border-amber-200 rounded text-amber-800">{s}</span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Upload Excel */}
                {!certResult && (
                  <div className="space-y-2">
                    <p className="text-sm text-slate-700">Cargue el archivo Excel con los seriales verificados fisicamente:</p>
                    <label className="flex items-center justify-center gap-2 px-4 py-6 border-2 border-dashed border-amber-300 rounded-lg bg-amber-50/50 cursor-pointer hover:bg-amber-100/50 transition-colors"
                      data-testid="cert-excel-upload">
                      <input type="file" className="hidden" accept=".xlsx,.xls,.csv" onChange={handleCertExcel} disabled={certLoading} />
                      {certLoading ? (
                        <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-amber-600" />
                      ) : (
                        <>
                          <Upload size={20} className="text-amber-600" />
                          <span className="text-sm font-medium text-amber-700">Seleccionar archivo Excel de certificacion</span>
                        </>
                      )}
                    </label>
                  </div>
                )}

                {/* Mismatch Report */}
                {certResult && (
                  <div className="space-y-3">
                    <div className="grid grid-cols-3 gap-2 text-center">
                      <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-2">
                        <p className="text-lg font-bold text-emerald-700">{certResult.matching_count}</p>
                        <p className="text-[10px] text-emerald-600 uppercase">Coincidentes</p>
                      </div>
                      <div className={`border rounded-lg p-2 ${certResult.only_in_precarga.length > 0 ? 'bg-red-50 border-red-200' : 'bg-slate-50 border-slate-200'}`}>
                        <p className={`text-lg font-bold ${certResult.only_in_precarga.length > 0 ? 'text-red-700' : 'text-slate-400'}`}>{certResult.only_in_precarga.length}</p>
                        <p className="text-[10px] text-slate-600 uppercase">Solo en Precarga</p>
                      </div>
                      <div className={`border rounded-lg p-2 ${certResult.only_in_excel.length > 0 ? 'bg-blue-50 border-blue-200' : 'bg-slate-50 border-slate-200'}`}>
                        <p className={`text-lg font-bold ${certResult.only_in_excel.length > 0 ? 'text-blue-700' : 'text-slate-400'}`}>{certResult.only_in_excel.length}</p>
                        <p className="text-[10px] text-slate-600 uppercase">Solo en Excel</p>
                      </div>
                    </div>

                    {certResult.has_mismatch && (
                      <div className="bg-red-50 border border-red-200 rounded-lg p-3 space-y-2">
                        <div className="flex items-center gap-2">
                          <AlertTriangle size={16} className="text-red-600" />
                          <p className="text-sm font-semibold text-red-700">Inconsistencias detectadas</p>
                        </div>
                        {certResult.only_in_precarga.length > 0 && (
                          <div>
                            <p className="text-xs text-red-600 font-medium mb-1">Seriales en Precarga que NO estan en Excel:</p>
                            <div className="flex flex-wrap gap-1">
                              {certResult.only_in_precarga.map(s => (
                                <span key={s} className="px-1.5 py-0.5 text-[10px] bg-red-100 text-red-800 border border-red-300 rounded">{s}</span>
                              ))}
                            </div>
                          </div>
                        )}
                        {certResult.only_in_excel.length > 0 && (
                          <div>
                            <p className="text-xs text-blue-600 font-medium mb-1">Seriales en Excel que NO estaban en Precarga:</p>
                            <div className="flex flex-wrap gap-1">
                              {certResult.only_in_excel.map(s => (
                                <span key={s} className="px-1.5 py-0.5 text-[10px] bg-blue-100 text-blue-800 border border-blue-300 rounded">{s}</span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {!certResult.has_mismatch && (
                      <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 flex items-center gap-2">
                        <CheckCircle2 size={16} className="text-emerald-600" />
                        <p className="text-sm text-emerald-700 font-medium">Todos los seriales coinciden perfectamente.</p>
                      </div>
                    )}

                    {/* Action buttons */}
                    <div className="flex flex-col gap-2 pt-2 border-t">
                      <p className="text-xs text-slate-500 font-medium">Seleccione la fuente de datos definitiva:</p>
                      <div className="flex gap-2">
                        <Button onClick={() => executeCertification('excel')} disabled={certLoading}
                          className="flex-1 bg-blue-600 hover:bg-blue-700 text-white" data-testid="cert-use-excel">
                          <Upload size={14} className="mr-1.5" />
                          Actualizar con Excel ({certResult.excel_count} seriales)
                        </Button>
                        <Button onClick={() => executeCertification('original')} disabled={certLoading}
                          variant="outline" className="flex-1" data-testid="cert-use-original">
                          <ShieldCheck size={14} className="mr-1.5" />
                          Mantener Original ({certResult.precarga_count} seriales)
                        </Button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Close without certifying */}
                {!certResult && (
                  <div className="flex justify-end gap-2 pt-2">
                    <Button variant="outline" onClick={() => setCertDialog(false)}>Cancelar</Button>
                    <Button onClick={() => executeCertification('original')} disabled={certLoading}
                      className="bg-amber-600 hover:bg-amber-700 text-white" data-testid="cert-direct">
                      <ShieldCheck size={14} className="mr-1.5" />Certificar sin Excel (usar datos originales)
                    </Button>
                  </div>
                )}
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* ==================== EDIT MOVEMENT DIALOG (Admin-only) ==================== */}
        <Dialog open={editMovOpen} onOpenChange={setEditMovOpen}>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-hidden flex flex-col" data-testid="edit-mov-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Pencil size={18} className="text-blue-600" />
                Editar Movimiento de Inventario
                <span className="text-[11px] font-mono text-slate-400 ml-2">{editMov?.movement_id}</span>
              </DialogTitle>
              <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1.5 mt-2">
                <AlertTriangle size={12} className="inline mr-1" />
                <strong>Edición libre absoluta (uso de arranque/corrección).</strong> Todos los cambios quedan registrados en la pestaña <em>Historial</em>.
              </p>
            </DialogHeader>

            {/* Tabs */}
            <div className="flex gap-1 border-b border-slate-200 -mx-6 px-6">
              <button
                onClick={() => setEditTab('form')}
                className={`px-3 py-2 text-sm font-medium border-b-2 transition ${
                  editTab === 'form' ? 'border-blue-600 text-blue-700' : 'border-transparent text-slate-500 hover:text-slate-700'
                }`}
                data-testid="edit-mov-tab-form"
              >
                Datos
              </button>
              <button
                onClick={() => setEditTab('history')}
                className={`px-3 py-2 text-sm font-medium border-b-2 transition flex items-center gap-1.5 ${
                  editTab === 'history' ? 'border-blue-600 text-blue-700' : 'border-transparent text-slate-500 hover:text-slate-700'
                }`}
                data-testid="edit-mov-tab-history"
              >
                <History size={13} />
                Historial
                {editAudits.length > 0 && (
                  <span className="text-[10px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded-full">{editAudits.length}</span>
                )}
              </button>
            </div>

            <div className="flex-1 overflow-y-auto py-4">
              {editTab === 'form' ? (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-xs">Tipo de movimiento</Label>
                    <Select value={editForm.movement_type} onValueChange={(v) => setEditForm(p => ({ ...p, movement_type: v }))}>
                      <SelectTrigger className="h-9" data-testid="edit-mov-type"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="entrada">Entrada</SelectItem>
                        <SelectItem value="salida">Salida</SelectItem>
                        <SelectItem value="transferencia_entrada">Transferencia recibida</SelectItem>
                        <SelectItem value="transferencia_salida">Transferencia enviada</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-xs">Almacén</Label>
                    <Select value={editForm.warehouse_id} onValueChange={(v) => setEditForm(p => ({ ...p, warehouse_id: v }))}>
                      <SelectTrigger className="h-9" data-testid="edit-mov-warehouse"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {warehouses.map(w => (
                          <SelectItem key={w.warehouse_id} value={w.warehouse_id}>{w.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <Label className="text-xs">Ítem ID (hardware_id)</Label>
                    <Input value={editForm.item_id} onChange={(e) => setEditForm(p => ({ ...p, item_id: e.target.value }))} className="h-9 font-mono text-xs" data-testid="edit-mov-item-id" />
                  </div>
                  <div>
                    <Label className="text-xs">Nombre del ítem</Label>
                    <Input value={editForm.item_name} onChange={(e) => setEditForm(p => ({ ...p, item_name: e.target.value }))} className="h-9" data-testid="edit-mov-item-name" />
                  </div>

                  <div>
                    <Label className="text-xs">Tipo de ítem</Label>
                    <Input value={editForm.item_type} onChange={(e) => setEditForm(p => ({ ...p, item_type: e.target.value }))} className="h-9" data-testid="edit-mov-item-type" />
                  </div>
                  <div>
                    <Label className="text-xs">Cantidad</Label>
                    <Input type="number" min="0" value={editForm.quantity} onChange={(e) => setEditForm(p => ({ ...p, quantity: e.target.value }))} className="h-9" data-testid="edit-mov-quantity" />
                  </div>

                  <div>
                    <Label className="text-xs">Costo unitario (USD)</Label>
                    <Input type="number" step="0.01" min="0" value={editForm.unit_cost} onChange={(e) => setEditForm(p => ({ ...p, unit_cost: e.target.value }))} className="h-9" data-testid="edit-mov-unit-cost" />
                  </div>
                  <div>
                    <Label className="text-xs">Fecha de adquisición</Label>
                    <Input type="date" value={editForm.acquisition_date || ''} onChange={(e) => setEditForm(p => ({ ...p, acquisition_date: e.target.value }))} className="h-9" data-testid="edit-mov-acq-date" />
                  </div>

                  <div>
                    <Label className="text-xs">Proveedor</Label>
                    <Input value={editForm.supplier} onChange={(e) => setEditForm(p => ({ ...p, supplier: e.target.value }))} className="h-9" data-testid="edit-mov-supplier" />
                  </div>
                  <div>
                    <Label className="text-xs">Nº Factura / Doc.</Label>
                    <Input value={editForm.invoice_ref} onChange={(e) => setEditForm(p => ({ ...p, invoice_ref: e.target.value }))} className="h-9" data-testid="edit-mov-invoice-ref" />
                  </div>

                  <div>
                    <Label className="text-xs">Cliente (nombre)</Label>
                    <Input value={editForm.client_name} onChange={(e) => setEditForm(p => ({ ...p, client_name: e.target.value }))} className="h-9" data-testid="edit-mov-client-name" />
                  </div>
                  <div>
                    <Label className="text-xs">Cliente ID</Label>
                    <Input value={editForm.client_id} onChange={(e) => setEditForm(p => ({ ...p, client_id: e.target.value }))} className="h-9 font-mono text-xs" data-testid="edit-mov-client-id" />
                  </div>

                  <div>
                    <Label className="text-xs">Cotización ID</Label>
                    <Input value={editForm.quote_id} onChange={(e) => setEditForm(p => ({ ...p, quote_id: e.target.value }))} className="h-9 font-mono text-xs" data-testid="edit-mov-quote-id" />
                  </div>
                  <div>
                    <Label className="text-xs">Nº Cotización</Label>
                    <Input value={editForm.quote_number} onChange={(e) => setEditForm(p => ({ ...p, quote_number: e.target.value }))} className="h-9" data-testid="edit-mov-quote-number" />
                  </div>

                  <div className="col-span-2">
                    <Label className="text-xs">Referencia</Label>
                    <Input value={editForm.reference} onChange={(e) => setEditForm(p => ({ ...p, reference: e.target.value }))} className="h-9" data-testid="edit-mov-reference" />
                  </div>

                  <div className="col-span-2">
                    <Label className="text-xs">Seriales (separados por coma, solo POS/Pinpad)</Label>
                    <Textarea value={editForm.serials} onChange={(e) => setEditForm(p => ({ ...p, serials: e.target.value }))} rows={2} className="font-mono text-xs" data-testid="edit-mov-serials" />
                  </div>

                  <div className="col-span-2">
                    <Label className="text-xs">Notas / Descripción</Label>
                    <Textarea value={editForm.notes} onChange={(e) => setEditForm(p => ({ ...p, notes: e.target.value }))} rows={3} data-testid="edit-mov-notes" />
                  </div>

                  <div>
                    <Label className="text-xs">Estado certificación</Label>
                    <Select value={editForm.certification_status || '__none__'} onValueChange={(v) => setEditForm(p => ({ ...p, certification_status: v === '__none__' ? '' : v }))}>
                      <SelectTrigger className="h-9" data-testid="edit-mov-cert-status"><SelectValue placeholder="Sin estado" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none__">— Sin estado —</SelectItem>
                        <SelectItem value="precarga">Precarga</SelectItem>
                        <SelectItem value="certificado">Certificado</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-xs">Transfer ID (par transferencia)</Label>
                    <Input value={editForm.transfer_id} onChange={(e) => setEditForm(p => ({ ...p, transfer_id: e.target.value }))} className="h-9 font-mono text-xs" data-testid="edit-mov-transfer-id" />
                  </div>
                </div>
              ) : (
                <div className="space-y-2" data-testid="edit-mov-history-list">
                  {editAudits.length === 0 ? (
                    <p className="text-sm text-slate-400 text-center py-8">Aún no hay ediciones registradas para este movimiento.</p>
                  ) : editAudits.map((a) => (
                    <div key={a.audit_id} className="border border-slate-200 rounded p-3 bg-slate-50" data-testid={`audit-${a.audit_id}`}>
                      <div className="flex items-center justify-between mb-2">
                        <div className="text-xs">
                          <span className="font-semibold text-slate-800">{a.edited_by_name || a.edited_by_email || a.edited_by}</span>
                          <span className="text-slate-400 ml-2">{(a.edited_at || '').slice(0, 19).replace('T', ' ')}</span>
                        </div>
                        <span className="text-[10px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">
                          {Object.keys(a.changes || {}).length} campo(s)
                        </span>
                      </div>
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="text-[10px] uppercase text-slate-400 border-b border-slate-200">
                            <th className="text-left py-1">Campo</th>
                            <th className="text-left py-1">Antes</th>
                            <th className="text-left py-1">Después</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(a.changes || {}).map(([field, vals]) => (
                            <tr key={field} className="border-b border-slate-100">
                              <td className="py-1 font-mono text-[11px] text-slate-700">{field}</td>
                              <td className="py-1 text-red-600 truncate max-w-[200px]" title={String(vals.old ?? '')}>
                                {vals.old === null || vals.old === undefined || vals.old === '' ? <em className="text-slate-400">vacío</em> : String(Array.isArray(vals.old) ? vals.old.join(', ') : vals.old)}
                              </td>
                              <td className="py-1 text-emerald-700 truncate max-w-[200px]" title={String(vals.new ?? '')}>
                                {vals.new === null || vals.new === undefined || vals.new === '' ? <em className="text-slate-400">vacío</em> : String(Array.isArray(vals.new) ? vals.new.join(', ') : vals.new)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-200">
              <Button variant="outline" onClick={() => setEditMovOpen(false)} disabled={editSaving} data-testid="edit-mov-cancel">
                Cerrar
              </Button>
              {editTab === 'form' && (
                <Button onClick={saveEditMovement} disabled={editSaving} className="bg-blue-600 hover:bg-blue-700" data-testid="edit-mov-save">
                  {editSaving ? 'Guardando...' : 'Guardar cambios'}
                </Button>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
}
