import { useState, useEffect, useRef } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Plus, Trash2, Save, Package, Wrench, MessageSquare, AlertCircle, ChevronDown, Search } from 'lucide-react';
import { toast } from 'sonner';
import api from '../utils/api';

const formatCurrency = (num) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(num || 0);
const IVA_RATE = 0.16;

export const EditEquipRepairDialog = ({ open, onClose, quote, onSaved }) => {
  const [items, setItems] = useState([]);
  const [notes, setNotes] = useState('');
  const [repairDescription, setRepairDescription] = useState('');
  const [equipmentSerialNumber, setEquipmentSerialNumber] = useState('');
  const [showJustifyModal, setShowJustifyModal] = useState(false);
  const [justification, setJustification] = useState('');
  const [saving, setSaving] = useState(false);
  // Catálogo de hardware
  const [catalog, setCatalog] = useState([]);
  // Dropdown state per item
  const [activeDropdown, setActiveDropdown] = useState(null);
  const [dropdownSearch, setDropdownSearch] = useState('');
  const dropdownRef = useRef(null);

  const isRepair = quote?.quote_category === 'repair';

  // Cargar catálogo de hardware
  useEffect(() => {
    const loadCatalog = async () => {
      try {
        const res = await api.get('/hardware');
        setCatalog(res.data || []);
      } catch { setCatalog([]); }
    };
    if (open) loadCatalog();
  }, [open]);

  useEffect(() => {
    if (open && quote) {
      setItems((quote.equipment_items || []).map((item, idx) => ({
        ...item,
        _key: `item_${idx}_${Date.now()}`
      })));
      setNotes(quote.notes || '');
      setRepairDescription(quote.repair_description || '');
      setEquipmentSerialNumber(quote.equipment_serial_number || '');
      setJustification('');
      setActiveDropdown(null);
    }
  }, [open, quote]);

  // Cerrar dropdown al hacer clic afuera
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setActiveDropdown(null);
        setDropdownSearch('');
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Filtrar catálogo según tipo de cotización
  const getFilteredCatalog = () => {
    const query = dropdownSearch.toLowerCase();
    let filtered;
    if (isRepair) {
      // Reparaciones: solo items de Mantenimiento
      filtered = catalog.filter(h => h.type === 'Mantenimiento');
    } else {
      // Equipos y Accesorios: POS, Pinpad, Base (Bienes)
      filtered = catalog.filter(h => ['POS', 'Pinpad', 'Base'].includes(h.type));
    }
    if (query) {
      filtered = filtered.filter(h => h.name.toLowerCase().includes(query));
    }
    return filtered;
  };

  const handleSelectFromCatalog = (index, catalogItem) => {
    const updated = [...items];
    updated[index] = {
      ...updated[index],
      hardware_id: catalogItem.hardware_id,
      name: catalogItem.name,
      hardware_type: catalogItem.type,
      unit_price_usd: catalogItem.price_usd || 0,
      total_usd: (updated[index].quantity || 1) * (catalogItem.price_usd || 0)
    };
    setItems(updated);
    setActiveDropdown(null);
    setDropdownSearch('');
  };

  const handleAddItem = () => {
    setItems([...items, {
      _key: `new_${Date.now()}`,
      hardware_id: '',
      name: '',
      hardware_type: isRepair ? 'Mantenimiento' : 'Equipo',
      quantity: 1,
      unit_price_usd: 0,
      total_usd: 0
    }]);
  };

  const handleUpdateItem = (index, field, value) => {
    const updated = [...items];
    updated[index] = { ...updated[index], [field]: value };
    if (field === 'quantity' || field === 'unit_price_usd') {
      const qty = field === 'quantity' ? value : updated[index].quantity;
      const price = field === 'unit_price_usd' ? value : updated[index].unit_price_usd;
      updated[index].total_usd = (parseFloat(qty) || 0) * (parseFloat(price) || 0);
    }
    setItems(updated);
  };

  const handleRemoveItem = (index) => {
    setItems(items.filter((_, i) => i !== index));
    if (activeDropdown === index) setActiveDropdown(null);
  };

  const subtotal = items.reduce((sum, item) => sum + (item.total_usd || 0), 0);
  const iva = Math.round(subtotal * IVA_RATE * 100) / 100;
  const totalConIva = Math.round((subtotal + iva) * 100) / 100;

  const handleInitSave = () => {
    if (items.length === 0) {
      toast.error('Debe tener al menos un item');
      return;
    }
    if (items.some(i => !i.name.trim())) {
      toast.error('Todos los items deben tener descripción');
      return;
    }
    setShowJustifyModal(true);
  };

  const handleConfirmSave = async () => {
    if (justification.length < 20) {
      toast.error('La justificación debe tener al menos 20 caracteres');
      return;
    }
    setSaving(true);
    try {
      // 1. Duplicar la cotización original
      const dupRes = await api.post(`/quotes/${quote.quote_id}/duplicate`);
      const newQuoteId = dupRes.data.new_quote_id;
      const newQuoteNumber = dupRes.data.new_quote_number;
      const newVersion = dupRes.data.version;

      // 2. Preparar items limpios con los NUEVOS valores
      const cleanItems = items.map(item => ({
        hardware_id: item.hardware_id || '',
        name: item.name,
        hardware_type: item.hardware_type || 'Equipo',
        quantity: parseInt(item.quantity) || 1,
        unit_price_usd: parseFloat(item.unit_price_usd) || 0,
        total_usd: (parseInt(item.quantity) || 1) * (parseFloat(item.unit_price_usd) || 0)
      }));

      const newSubtotal = cleanItems.reduce((sum, i) => sum + i.total_usd, 0);
      const newIva = Math.round(newSubtotal * IVA_RATE * 100) / 100;
      const newTotal = Math.round((newSubtotal + newIva) * 100) / 100;

      // 3. Actualizar con los datos EDITADOS (nuevos items, nuevos totales)
      const updateData = {
        equipment_items: cleanItems,
        subtotal_usd: newSubtotal,
        total_usd: newTotal,
        notes: notes,
      };
      if (isRepair) {
        updateData.repair_description = repairDescription;
        updateData.equipment_serial_number = equipmentSerialNumber;
      }

      await api.put(`/quotes/${newQuoteId}`, updateData);

      // 4. Regenerar PDF con datos actualizados
      try {
        await api.post(`/quotes/${newQuoteId}/regenerate-equipment-pdf`, {});
      } catch (pdfErr) {
        console.error('Error regenerando PDF:', pdfErr);
      }

      // 5. Bitácora del cliente
      try {
        await api.post(`/clients/${quote.client_id}/logs`, {
          client_id: quote.client_id,
          detail: `Modificación ${isRepair ? 'Reparación' : 'Equipos'} — ${newQuoteNumber} (v${newVersion}): ${justification}`,
          action: 'Modificación de Cotización'
        });
      } catch (logErr) { console.error('Error bitácora:', logErr); }

      toast.success(`Nueva versión ${newQuoteNumber} (v${newVersion}) creada exitosamente`);
      setShowJustifyModal(false);
      setJustification('');
      onSaved && onSaved();
      onClose();
    } catch (error) {
      console.error('Error al modificar:', error);
      toast.error('Error al crear nueva versión: ' + (error.response?.data?.detail || error.message));
    } finally {
      setSaving(false);
    }
  };

  if (!quote) return null;

  const filteredCatalog = getFilteredCatalog();

  return (
    <>
      <Dialog open={open && !showJustifyModal} onOpenChange={(v) => !v && onClose()}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="edit-equip-repair-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-lg">
              {isRepair ? <Wrench className="w-5 h-5 text-amber-500" /> : <Package className="w-5 h-5 text-blue-500" />}
              Modificar {isRepair ? 'Reparación' : 'Equipos y Accesorios'}
            </DialogTitle>
            <DialogDescription>
              Cotización {quote.quote_number} — {quote.client_name}. Al guardar se creará la versión {(quote.version || 1) + 1}.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* Info original */}
            <div className="bg-slate-50 rounded-lg p-3 text-xs text-slate-500 border">
              <span className="font-semibold text-slate-700">Original:</span> {quote.quote_number} v{quote.version || 1} — {quote.equipment_type || (isRepair ? 'Reparación' : 'Equipos')} — Total: {formatCurrency(quote.total_usd)}
            </div>

            {/* Campos de reparación */}
            {isRepair && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-500 mb-1 block">Descripción de Falla</label>
                  <Input value={repairDescription} onChange={(e) => setRepairDescription(e.target.value)} placeholder="Ej: Falla de pantalla" data-testid="repair-description" />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-500 mb-1 block">Serial del Equipo</label>
                  <Input value={equipmentSerialNumber} onChange={(e) => setEquipmentSerialNumber(e.target.value)} placeholder="Ej: SN-12345" data-testid="repair-serial" />
                </div>
              </div>
            )}

            {/* Tabla de items */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-semibold text-slate-700">
                  Items de la Cotización
                  <span className="text-xs font-normal text-slate-400 ml-2">
                    ({isRepair ? 'Catálogo: Mantenimiento' : 'Catálogo: Bienes'})
                  </span>
                </h4>
                <Button variant="outline" size="sm" onClick={handleAddItem} data-testid="add-item-btn">
                  <Plus className="w-3.5 h-3.5 mr-1" /> Agregar
                </Button>
              </div>

              <div className="space-y-2" ref={dropdownRef}>
                {items.map((item, idx) => (
                  <div key={item._key} className="flex gap-2 items-end bg-white border rounded-lg p-3" data-testid={`item-row-${idx}`}>
                    {/* Descripción con dropdown */}
                    <div className="flex-1 relative">
                      <label className="text-[10px] font-semibold text-slate-400 uppercase">Descripción</label>
                      <div
                        className="flex items-center border rounded-md px-3 py-2 cursor-pointer hover:border-blue-400 transition bg-white"
                        onClick={() => { setActiveDropdown(activeDropdown === idx ? null : idx); setDropdownSearch(''); }}
                      >
                        <span className={`flex-1 text-sm ${item.name ? 'text-slate-800' : 'text-slate-400'}`}>
                          {item.name || 'Seleccionar item...'}
                        </span>
                        <ChevronDown className="w-4 h-4 text-slate-400" />
                      </div>
                      {/* Dropdown */}
                      {activeDropdown === idx && (
                        <div className="absolute z-50 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-52 overflow-hidden">
                          <div className="p-2 border-b">
                            <div className="relative">
                              <Search className="absolute left-2 top-2 w-3.5 h-3.5 text-slate-400" />
                              <input
                                type="text"
                                className="w-full pl-7 pr-3 py-1.5 text-sm border rounded focus:outline-none focus:ring-1 focus:ring-blue-400"
                                placeholder="Buscar..."
                                value={dropdownSearch}
                                onChange={(e) => setDropdownSearch(e.target.value)}
                                autoFocus
                                onClick={(e) => e.stopPropagation()}
                              />
                            </div>
                          </div>
                          <div className="overflow-y-auto max-h-40">
                            {filteredCatalog.length === 0 ? (
                              <div className="px-3 py-2 text-xs text-slate-400">No hay items disponibles</div>
                            ) : (
                              filteredCatalog.map(catItem => (
                                <div
                                  key={catItem.hardware_id}
                                  className="flex items-center justify-between px-3 py-2 hover:bg-blue-50 cursor-pointer transition text-sm"
                                  onClick={() => handleSelectFromCatalog(idx, catItem)}
                                >
                                  <div>
                                    <span className="font-medium text-slate-800">{catItem.name}</span>
                                    <span className="ml-2 text-[10px] text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">{catItem.type}</span>
                                  </div>
                                  <span className="text-xs font-mono text-emerald-600">{formatCurrency(catItem.price_usd)}</span>
                                </div>
                              ))
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                    <div className="w-20">
                      <label className="text-[10px] font-semibold text-slate-400 uppercase">Cant.</label>
                      <Input
                        type="number" min={1} value={item.quantity}
                        onChange={(e) => handleUpdateItem(idx, 'quantity', parseInt(e.target.value) || 1)}
                        className="text-sm text-center"
                      />
                    </div>
                    <div className="w-28">
                      <label className="text-[10px] font-semibold text-slate-400 uppercase">Precio USD</label>
                      <Input
                        type="number" step="0.01" min={0} value={item.unit_price_usd}
                        onChange={(e) => handleUpdateItem(idx, 'unit_price_usd', parseFloat(e.target.value) || 0)}
                        className="text-sm text-right"
                      />
                    </div>
                    <div className="w-24 text-right">
                      <label className="text-[10px] font-semibold text-slate-400 uppercase">Total</label>
                      <div className="text-sm font-semibold text-emerald-700 py-2">{formatCurrency(item.total_usd)}</div>
                    </div>
                    <Button variant="ghost" size="sm" onClick={() => handleRemoveItem(idx)} className="text-slate-300 hover:text-rose-600">
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                ))}
                {items.length === 0 && (
                  <div className="text-center py-6 text-slate-400 text-sm">No hay items. Use "Agregar" para comenzar.</div>
                )}
              </div>
            </div>

            {/* Notas */}
            <div>
              <label className="text-xs font-semibold text-slate-500 mb-1 block">Notas / Observaciones</label>
              <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} placeholder="Notas adicionales..." />
            </div>

            {/* Desglose financiero */}
            <div className="bg-slate-800 text-white rounded-lg p-4">
              <div className="flex justify-between items-start">
                <div className="space-y-1">
                  <div className="flex justify-between gap-8 text-sm">
                    <span className="text-slate-400">Subtotal:</span>
                    <span className="font-mono">{formatCurrency(subtotal)}</span>
                  </div>
                  <div className="flex justify-between gap-8 text-sm">
                    <span className="text-slate-400">IVA (16%):</span>
                    <span className="font-mono">{formatCurrency(iva)}</span>
                  </div>
                  <div className="flex justify-between gap-8 text-lg font-bold border-t border-slate-600 pt-1 mt-1">
                    <span>Total:</span>
                    <span className="text-emerald-300">{formatCurrency(totalConIva)}</span>
                  </div>
                  <p className="text-[10px] text-blue-300 mt-2">La cotización original v{quote.version || 1} permanece intacta</p>
                </div>
                <Button onClick={handleInitSave} className="bg-blue-600 hover:bg-blue-700 ml-4" data-testid="save-version-btn">
                  <Save className="w-4 h-4 mr-2" /> Generar Nueva Versión
                </Button>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Modal de Justificación */}
      <Dialog open={showJustifyModal} onOpenChange={(v) => !v && setShowJustifyModal(false)}>
        <DialogContent className="max-w-md" data-testid="justify-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <MessageSquare className="w-5 h-5 text-blue-500" /> Justificación de Cambio
            </DialogTitle>
            <DialogDescription>
              Indique el motivo de la modificación. Se registrará en la Bitácora del cliente.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <Textarea
              value={justification} onChange={(e) => setJustification(e.target.value)}
              maxLength={300} rows={4}
              placeholder="Ej: Cambio en modelo de equipos por solicitud del cliente..."
              data-testid="justification-input"
            />
            <div className="flex justify-between items-center">
              <span className={`text-xs font-semibold ${justification.length < 20 ? 'text-rose-500' : 'text-emerald-500'}`}>
                {justification.length}/300 (mín. 20)
              </span>
              {justification.length < 20 && (
                <span className="text-xs text-rose-400 flex items-center gap-1">
                  <AlertCircle className="w-3 h-3" /> Mínimo 20 caracteres
                </span>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowJustifyModal(false)}>Cancelar</Button>
            <Button
              disabled={justification.length < 20 || saving}
              onClick={handleConfirmSave}
              className="bg-slate-900 hover:bg-slate-800"
              data-testid="confirm-save-btn"
            >
              {saving ? 'Guardando...' : 'Confirmar y Guardar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default EditEquipRepairDialog;
