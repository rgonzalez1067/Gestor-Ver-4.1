import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Plus, Trash2, Save, Package, Wrench, MessageSquare, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';
import api from '../utils/api';

const formatCurrency = (num) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(num || 0);

export const EditEquipRepairDialog = ({ open, onClose, quote, onSaved }) => {
  const [items, setItems] = useState([]);
  const [notes, setNotes] = useState('');
  const [repairDescription, setRepairDescription] = useState('');
  const [equipmentSerialNumber, setEquipmentSerialNumber] = useState('');
  const [showJustifyModal, setShowJustifyModal] = useState(false);
  const [justification, setJustification] = useState('');
  const [saving, setSaving] = useState(false);

  const isRepair = quote?.quote_category === 'repair';

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
    }
  }, [open, quote]);

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
  };

  const totalInversion = items.reduce((sum, item) => sum + (item.total_usd || 0), 0);

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
      // 1. Duplicar la cotización original (crea nueva versión)
      const dupRes = await api.post(`/quotes/${quote.quote_id}/duplicate`);
      const newQuoteId = dupRes.data.new_quote_id;
      const newQuoteNumber = dupRes.data.new_quote_number;
      const newVersion = dupRes.data.version;

      // 2. Preparar items limpios
      const cleanItems = items.map(item => ({
        hardware_id: item.hardware_id || '',
        name: item.name,
        hardware_type: item.hardware_type || 'Equipo',
        quantity: parseInt(item.quantity) || 1,
        unit_price_usd: parseFloat(item.unit_price_usd) || 0,
        total_usd: (parseInt(item.quantity) || 1) * (parseFloat(item.unit_price_usd) || 0)
      }));

      const newTotal = cleanItems.reduce((sum, i) => sum + i.total_usd, 0);

      // 3. Actualizar la nueva cotización con los datos editados
      const updateData = {
        equipment_items: cleanItems,
        total_usd: newTotal,
        subtotal_usd: newTotal,
        notes: notes,
        repair_description: isRepair ? repairDescription : undefined,
        equipment_serial_number: isRepair ? equipmentSerialNumber : undefined,
      };

      await api.put(`/quotes/${newQuoteId}`, updateData);

      // 4. Regenerar PDF y guardarlo en anexos
      try {
        await api.post(`/quotes/${newQuoteId}/regenerate-equipment-pdf`, {
          justification: justification
        });
      } catch (pdfErr) {
        console.error('Error regenerando PDF:', pdfErr);
      }

      // 5. Registrar en bitácora del cliente
      try {
        await api.post(`/clients/${quote.client_id}/logs`, {
          client_id: quote.client_id,
          detail: `Modificación ${isRepair ? 'Reparación' : 'Equipos'} — ${newQuoteNumber} (v${newVersion}): ${justification}`,
          action: 'Modificación de Cotización'
        });
      } catch (logErr) {
        console.error('Error registrando bitácora:', logErr);
      }

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
                  <Input
                    value={repairDescription}
                    onChange={(e) => setRepairDescription(e.target.value)}
                    placeholder="Ej: Falla de pantalla"
                    data-testid="repair-description"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-500 mb-1 block">Serial del Equipo</label>
                  <Input
                    value={equipmentSerialNumber}
                    onChange={(e) => setEquipmentSerialNumber(e.target.value)}
                    placeholder="Ej: SN-12345"
                    data-testid="repair-serial"
                  />
                </div>
              </div>
            )}

            {/* Tabla de items */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-semibold text-slate-700">Items de la Cotización</h4>
                <Button variant="outline" size="sm" onClick={handleAddItem} data-testid="add-item-btn">
                  <Plus className="w-3.5 h-3.5 mr-1" /> Agregar
                </Button>
              </div>

              <div className="space-y-2">
                {items.map((item, idx) => (
                  <div key={item._key} className="flex gap-2 items-end bg-white border rounded-lg p-3" data-testid={`item-row-${idx}`}>
                    <div className="flex-1">
                      <label className="text-[10px] font-semibold text-slate-400 uppercase">Descripción</label>
                      <Input
                        value={item.name}
                        onChange={(e) => handleUpdateItem(idx, 'name', e.target.value)}
                        placeholder="Nombre del item..."
                        className="text-sm"
                      />
                    </div>
                    <div className="w-20">
                      <label className="text-[10px] font-semibold text-slate-400 uppercase">Cant.</label>
                      <Input
                        type="number"
                        min={1}
                        value={item.quantity}
                        onChange={(e) => handleUpdateItem(idx, 'quantity', parseInt(e.target.value) || 1)}
                        className="text-sm text-center"
                      />
                    </div>
                    <div className="w-28">
                      <label className="text-[10px] font-semibold text-slate-400 uppercase">Precio USD</label>
                      <Input
                        type="number"
                        step="0.01"
                        min={0}
                        value={item.unit_price_usd}
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

            {/* Total */}
            <div className="bg-slate-800 text-white rounded-lg p-4 flex justify-between items-center">
              <div>
                <p className="text-xs text-slate-400 uppercase font-semibold">Nueva Inversión Total</p>
                <p className="text-2xl font-bold">{formatCurrency(totalInversion)}</p>
                <p className="text-[10px] text-blue-300 mt-1">La cotización original v{quote.version || 1} permanece intacta</p>
              </div>
              <Button onClick={handleInitSave} className="bg-blue-600 hover:bg-blue-700" data-testid="save-version-btn">
                <Save className="w-4 h-4 mr-2" /> Generar Nueva Versión
              </Button>
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
              value={justification}
              onChange={(e) => setJustification(e.target.value)}
              maxLength={300}
              rows={4}
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
