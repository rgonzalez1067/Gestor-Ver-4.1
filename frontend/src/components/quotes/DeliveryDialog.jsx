import { useState, useEffect, useCallback } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Button } from '../ui/button';
import { Label } from '../ui/label';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';
import { Truck, Warehouse, Package, Check, AlertTriangle } from 'lucide-react';
import api from '../../utils/api';
import { toast } from 'sonner';

export function DeliveryDialog({ open, onOpenChange, quoteId, exceptionInfo, onDelivered }) {
  const [loading, setLoading] = useState(false);
  const [prepData, setPrepData] = useState(null);
  const [warehouseId, setWarehouseId] = useState('');
  const [deliveryItems, setDeliveryItems] = useState([]);
  const [notes, setNotes] = useState('');
  const [transportista, setTransportista] = useState('');
  const [guiaPlaca, setGuiaPlaca] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchPrep = useCallback(async (whId) => {
    if (!quoteId) return;
    setLoading(true);
    try {
      const url = whId
        ? `/quotes/${quoteId}/delivery-prep?warehouse_id=${whId}`
        : `/quotes/${quoteId}/delivery-prep`;
      const res = await api.get(url);
      setPrepData(res.data);
      setDeliveryItems(
        res.data.items.map(item => ({
          hardware_id: item.hardware_id,
          name: item.name,
          hardware_type: item.hardware_type,
          quantity: Math.min(item.quantity_quoted, item.stock_available),
          quantity_quoted: item.quantity_quoted,
          stock_available: item.stock_available,
          serials_available: item.serials_available || [],
          requires_serial: item.requires_serial,
          serials: [],
        }))
      );
    } catch {
      toast.error('Error al obtener datos de preparación');
    } finally {
      setLoading(false);
    }
  }, [quoteId]);

  useEffect(() => {
    if (open && quoteId) {
      setWarehouseId('');
      setDeliveryItems([]);
      setNotes('');
      setTransportista('');
      setGuiaPlaca('');
      setPrepData(null);
      fetchPrep(null);
    }
  }, [open, quoteId, fetchPrep]);

  const handleWarehouseChange = (val) => {
    setWarehouseId(val);
    fetchPrep(val);
  };

  const toggleSerial = (itemIdx, serial) => {
    setDeliveryItems(prev => prev.map((item, i) => {
      if (i !== itemIdx) return item;
      const has = item.serials.includes(serial);
      return {
        ...item,
        serials: has ? item.serials.filter(s => s !== serial) : [...item.serials, serial],
      };
    }));
  };

  const updateQty = (itemIdx, qty) => {
    setDeliveryItems(prev => prev.map((item, i) => {
      if (i !== itemIdx) return item;
      const maxQty = Math.min(item.quantity_quoted, item.stock_available);
      return { ...item, quantity: Math.max(0, Math.min(qty, maxQty)) };
    }));
  };

  const isValid = warehouseId &&
    deliveryItems.some(it => it.quantity > 0) &&
    deliveryItems.every(it =>
      it.quantity === 0 || !it.requires_serial || it.serials.length === it.quantity
    );

  const handleSubmit = async () => {
    if (!isValid) return;
    setSubmitting(true);
    try {
      const headers = {};
      if (exceptionInfo) {
        headers['x-exception-reason'] = exceptionInfo.reason;
        headers['x-regularization-date'] = exceptionInfo.regularization_date;
      }
      const payload = {
        warehouse_id: warehouseId,
        delivery_items: deliveryItems
          .filter(it => it.quantity > 0)
          .map(it => ({
            hardware_id: it.hardware_id,
            quantity: it.quantity,
            serials: it.requires_serial ? it.serials : [],
          })),
        notes,
        transportista,
        guia_placa: guiaPlaca,
      };
      const res = await api.post(`/quotes/${quoteId}/deliver`, payload, { headers });
      toast.success('Entrega registrada exitosamente');
      if (res.data.hoja_ruta_url) {
        toast.success('Nota de Entrega PDF generada');
      }
      onOpenChange(false);
      if (onDelivered) onDelivered(res.data);
    } catch (error) {
      const detail = error.response?.data?.detail || '';
      if (detail.startsWith('IRREGULAR:')) {
        toast.error(detail.replace('IRREGULAR:', ''));
      } else {
        toast.error(detail || 'Error al procesar la entrega');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="delivery-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            <Truck size={22} className="text-teal-600" />
            Nota de Entrega
          </DialogTitle>
          {prepData && (
            <p className="text-sm text-slate-500 mt-1">
              Cotización: <strong>{prepData.quote_number}</strong> — {prepData.client_name}
            </p>
          )}
        </DialogHeader>

        {loading && !prepData ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-600" />
          </div>
        ) : (
          <div className="space-y-4">
            {/* Warehouse selector */}
            <div>
              <Label className="flex items-center gap-1.5 mb-1">
                <Warehouse size={14} className="text-teal-600" /> Almacén de Origen *
              </Label>
              <Select value={warehouseId} onValueChange={handleWarehouseChange}>
                <SelectTrigger data-testid="delivery-warehouse">
                  <SelectValue placeholder="Seleccione almacén..." />
                </SelectTrigger>
                <SelectContent>
                  {(prepData?.warehouses || []).map(w => (
                    <SelectItem key={w.warehouse_id} value={w.warehouse_id}>
                      {w.name} {w.location && `— ${w.location}`}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Items */}
            {warehouseId && deliveryItems.length > 0 && (
              <div className="space-y-3">
                <Label className="flex items-center gap-1.5">
                  <Package size={14} className="text-teal-600" /> Equipos a Entregar
                </Label>
                {deliveryItems.map((item, idx) => (
                  <div key={item.hardware_id} className="bg-slate-50 border rounded-lg p-3 space-y-2" data-testid={`delivery-item-${item.hardware_id}`}>
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium text-sm text-slate-900">{item.name}</p>
                        <p className="text-xs text-slate-500">{item.hardware_type} — Cotizado: {item.quantity_quoted} | Stock: {item.stock_available}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Label className="text-xs text-slate-500">Cant:</Label>
                        <input
                          type="number"
                          min={0}
                          max={Math.min(item.quantity_quoted, item.stock_available)}
                          value={item.quantity}
                          onChange={e => updateQty(idx, parseInt(e.target.value) || 0)}
                          className="w-16 h-8 text-center text-sm border rounded"
                          data-testid={`delivery-qty-${item.hardware_id}`}
                        />
                      </div>
                    </div>

                    {item.stock_available < item.quantity_quoted && (
                      <div className="flex items-center gap-1.5 text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded">
                        <AlertTriangle size={12} /> Stock insuficiente. Disponible: {item.stock_available} de {item.quantity_quoted} cotizado(s)
                      </div>
                    )}

                    {item.requires_serial && item.quantity > 0 && item.serials_available.length > 0 && (
                      <div className="bg-white border border-teal-200 rounded p-2 space-y-1.5">
                        <p className="text-xs font-semibold text-teal-700 uppercase">
                          Seleccione seriales ({item.serials.length}/{item.quantity})
                        </p>
                        <div className="flex flex-wrap gap-1 max-h-32 overflow-y-auto">
                          {item.serials_available.map(s => (
                            <button
                              key={s}
                              type="button"
                              onClick={() => toggleSerial(idx, s)}
                              disabled={!item.serials.includes(s) && item.serials.length >= item.quantity}
                              className={`px-2 py-1 text-xs rounded border transition-colors ${
                                item.serials.includes(s)
                                  ? 'bg-teal-600 text-white border-teal-600'
                                  : 'bg-white text-slate-700 border-slate-300 hover:border-teal-400 disabled:opacity-40'
                              }`}
                              data-testid={`delivery-serial-${s}`}
                            >
                              {s} {item.serials.includes(s) && <Check size={10} className="inline ml-0.5" />}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {item.requires_serial && item.quantity > 0 && item.serials_available.length === 0 && (
                      <p className="text-xs text-red-500">No hay seriales disponibles en este almacén</p>
                    )}
                  </div>
                ))}
              </div>
            )}

            {warehouseId && deliveryItems.length === 0 && !loading && (
              <p className="text-sm text-slate-500 text-center py-4">No hay equipos en esta cotización</p>
            )}

            {/* Logistics */}
            <div className="bg-slate-50 rounded-lg border p-3 space-y-3">
              <Label className="text-xs font-semibold text-slate-700 uppercase">Control Logístico y Transporte</Label>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs text-slate-500">Transportado por</Label>
                  <Input
                    value={transportista}
                    onChange={e => setTransportista(e.target.value)}
                    placeholder="Nombre del mensajero / empresa..."
                    data-testid="delivery-transportista"
                  />
                </div>
                <div>
                  <Label className="text-xs text-slate-500">Nro. de Guía / Placa</Label>
                  <Input
                    value={guiaPlaca}
                    onChange={e => setGuiaPlaca(e.target.value)}
                    placeholder="Guía o placa del vehículo..."
                    data-testid="delivery-guia-placa"
                  />
                </div>
              </div>
            </div>

            {/* Notes */}
            <div>
              <Label>Observaciones</Label>
              <Textarea
                value={notes}
                onChange={e => setNotes(e.target.value)}
                placeholder="Notas adicionales para la Nota de Entrega..."
                rows={2}
                data-testid="delivery-notes"
              />
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-2 pt-2 border-t">
              <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
              <Button
                onClick={handleSubmit}
                disabled={!isValid || submitting}
                className="bg-teal-600 hover:bg-teal-700 text-white"
                data-testid="delivery-submit"
              >
                {submitting ? 'Procesando...' : 'Confirmar Entrega y Generar Nota'}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
