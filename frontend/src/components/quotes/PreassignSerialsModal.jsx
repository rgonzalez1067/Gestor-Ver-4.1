import { useState, useEffect, useMemo } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { toast } from 'sonner';
import { Search, Package, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

export const PreassignSerialsModal = ({ open, onClose, quote, token, onSuccess }) => {
  const [warehouses, setWarehouses] = useState([]);
  const [selectedWarehouse, setSelectedWarehouse] = useState('');
  const [availableSerials, setAvailableSerials] = useState([]);
  const [selectedSerials, setSelectedSerials] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [existingAssignments, setExistingAssignments] = useState([]);

  // Get equipment info from quote
  const ftItems = quote?.ft_equipment_items || [];
  const requiredQty = ftItems.reduce((sum, i) => sum + (i.quantity || 0), 0);
  const modelName = ftItems.map(i => i.name).join(', ') || 'N/A';
  const itemId = ftItems[0]?.hardware_id || '';

  // Load warehouses and existing assignments
  useEffect(() => {
    if (!open || !quote) return;
    const load = async () => {
      try {
        const [whRes, assignRes] = await Promise.all([
          fetch(`${API}/api/inventory/warehouses`, { headers: { Authorization: `Bearer ${token}` } }),
          fetch(`${API}/api/quotes/${quote.quote_id}/preassigned-serials`, { headers: { Authorization: `Bearer ${token}` } }),
        ]);
        const whData = await whRes.json();
        const assignData = await assignRes.json();
        setWarehouses(Array.isArray(whData) ? whData : []);
        setExistingAssignments(assignData.assignments || []);
        if (assignData.assignments?.length > 0) {
          setSelectedSerials(assignData.assignments.map(a => a.serial));
          setSelectedWarehouse(assignData.assignments[0]?.warehouse_id || '');
        }
      } catch (e) {
        console.error(e);
      }
    };
    load();
  }, [open, quote, token]);

  // Load available serials when warehouse changes
  useEffect(() => {
    if (!selectedWarehouse || !itemId) return;
    const load = async () => {
      setLoading(true);
      try {
        const res = await fetch(
          `${API}/api/inventory/${selectedWarehouse}/available-serials/${itemId}`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        const data = await res.json();
        setAvailableSerials(data.available || []);
      } catch (e) {
        console.error(e);
        setAvailableSerials([]);
      }
      setLoading(false);
    };
    load();
  }, [selectedWarehouse, itemId, token]);

  const filteredSerials = useMemo(() => {
    if (!search.trim()) return availableSerials;
    const q = search.toLowerCase();
    return availableSerials.filter(s => s.serial.toLowerCase().includes(q));
  }, [availableSerials, search]);

  const toggleSerial = (serial) => {
    setSelectedSerials(prev =>
      prev.includes(serial) ? prev.filter(s => s !== serial) : [...prev, serial]
    );
  };

  const handleConfirm = async () => {
    if (selectedSerials.length !== requiredQty) return;
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/api/quotes/${quote.quote_id}/preassign-serials`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          serials: selectedSerials,
          warehouse_id: selectedWarehouse,
          item_id: itemId,
          item_name: modelName,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Error');
      // Toast principal: éxito de la preasignación (siempre que la BD se haya actualizado)
      toast.success(data.message);
      // Toast secundario: estado del correo. Si no se envió, mostrar warning
      // con detalle accionable (configuración faltante, fallo SMTP, etc.).
      if (data.email_sent === false) {
        toast.warning(
          data.email_error
            ? `Correo no enviado: ${data.email_error}`
            : 'Correo de notificación no enviado. Revise Configuración › Sede › Operaciones.'
        );
      } else if (data.email_sent === true && (data.email_recipients || []).length) {
        toast.info(`Correo enviado a ${data.email_recipients.join(', ')}`);
      }
      onSuccess?.();
      onClose();
    } catch (e) {
      toast.error(e.message);
    }
    setSubmitting(false);
  };

  const isReady = selectedSerials.length === requiredQty && selectedWarehouse;
  const hasExisting = existingAssignments.length > 0 && existingAssignments[0]?.status === 'preasignado';

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="preassign-serials-modal">
        <DialogHeader>
          <DialogTitle className="text-lg font-bold text-slate-800">
            Prerregistro de Seriales
          </DialogTitle>
        </DialogHeader>

        {/* Quote Info */}
        <div className="bg-slate-50 rounded-lg p-4 border border-slate-200 space-y-1" data-testid="preassign-quote-info">
          <p className="text-sm text-slate-600"><strong>Cotización:</strong> {quote?.quote_number}</p>
          <p className="text-sm text-slate-600"><strong>Modelo:</strong> {modelName}</p>
          <p className="text-sm text-slate-600"><strong>Cantidad requerida:</strong> {requiredQty} unidades</p>
        </div>

        {hasExisting && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-center gap-2">
            <AlertCircle size={16} className="text-amber-600" />
            <p className="text-sm text-amber-700">
              Ya existen {existingAssignments.length} seriales preasignados. Confirmar reemplazará la selección anterior.
            </p>
          </div>
        )}

        {/* Warehouse Selector */}
        <div>
          <label className="text-sm font-medium text-slate-700 mb-1 block">Almacén de Origen</label>
          <select
            value={selectedWarehouse}
            onChange={e => { setSelectedWarehouse(e.target.value); setSelectedSerials([]); }}
            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
            data-testid="preassign-warehouse-select"
          >
            <option value="">Seleccione un almacén...</option>
            {warehouses.map(w => (
              <option key={w.warehouse_id} value={w.warehouse_id}>{w.name}</option>
            ))}
          </select>
        </div>

        {/* Serials List */}
        {selectedWarehouse && (
          <>
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <Input
                placeholder="Buscar serial..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="pl-9"
                data-testid="preassign-search"
              />
            </div>

            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-500">
                {availableSerials.length} disponibles | {filteredSerials.length} mostrados
              </span>
              <span className={`font-semibold ${selectedSerials.length === requiredQty ? 'text-emerald-600' : 'text-slate-700'}`}>
                {selectedSerials.length} / {requiredQty} seleccionados
              </span>
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="animate-spin text-slate-400" size={24} />
              </div>
            ) : filteredSerials.length === 0 ? (
              <div className="text-center py-8 text-slate-400">
                <Package size={32} className="mx-auto mb-2" />
                <p className="text-sm">No hay seriales disponibles para este modelo en el almacén seleccionado</p>
              </div>
            ) : (
              <div className="max-h-[280px] overflow-y-auto border border-slate-200 rounded-lg divide-y divide-slate-100" data-testid="preassign-serial-list">
                {filteredSerials.map(item => {
                  const isSelected = selectedSerials.includes(item.serial);
                  const isDisabled = !isSelected && selectedSerials.length >= requiredQty;
                  return (
                    <button
                      key={item.serial}
                      onClick={() => !isDisabled && toggleSerial(item.serial)}
                      disabled={isDisabled}
                      className={`w-full flex items-center justify-between px-4 py-2.5 text-left transition-colors
                        ${isSelected ? 'bg-indigo-50 border-l-4 border-l-indigo-500' : 'hover:bg-slate-50 border-l-4 border-l-transparent'}
                        ${isDisabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
                      data-testid={`preassign-serial-${item.serial}`}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors
                          ${isSelected ? 'bg-indigo-600 border-indigo-600' : 'border-slate-300'}`}>
                          {isSelected && <CheckCircle size={14} className="text-white" />}
                        </div>
                        <span className="font-mono text-sm font-medium text-slate-800">{item.serial}</span>
                      </div>
                      {item.acquisition_date && (
                        <span className="text-xs text-slate-400">Adq: {item.acquisition_date}</span>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-2 border-t border-slate-100">
          <Button variant="outline" onClick={onClose} data-testid="preassign-cancel">Cancelar</Button>
          <Button
            onClick={handleConfirm}
            disabled={!isReady || submitting}
            className="bg-indigo-600 hover:bg-indigo-700 text-white"
            data-testid="preassign-confirm"
          >
            {submitting ? <Loader2 className="animate-spin mr-2" size={16} /> : null}
            Confirmar Prerregistro ({selectedSerials.length}/{requiredQty})
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
