import { useState, useEffect, useCallback } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Button } from '../ui/button';
import { Label } from '../ui/label';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';
import { Truck, Warehouse, Package, Check, AlertTriangle, Upload, User, Building, FileText } from 'lucide-react';
import api from '../../utils/api';
import { toast } from 'sonner';

const COURIERS = ['ZOOM (Oficina)', 'ZOOM (Casillero)', 'MRW', 'Tealca', 'Domesa'];

export function DeliveryDialog({ open, onOpenChange, quoteId, exceptionInfo, onDelivered, emailHeaders = null }) {
  const [loading, setLoading] = useState(false);
  const [prepData, setPrepData] = useState(null);
  const [warehouseId, setWarehouseId] = useState('');
  const [deliveryItems, setDeliveryItems] = useState([]);
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Logistics: delivery method
  const [deliveryMethod, setDeliveryMethod] = useState('');  // 'personalizada' | 'courier'
  const [receiverName, setReceiverName] = useState('');
  const [receiverCedula, setReceiverCedula] = useState('');
  const [receiverPhone, setReceiverPhone] = useState('');
  const [courierName, setCourierName] = useState('');
  const [courierOffice, setCourierOffice] = useState('');
  const [invoiceNumber, setInvoiceNumber] = useState('');

  // Excel upload audit per item
  const [excelAudit, setExcelAudit] = useState({});

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
      setDeliveryMethod('');
      setReceiverName('');
      setReceiverCedula('');
      setReceiverPhone('');
      setCourierName('');
      setCourierOffice('');
      setInvoiceNumber('');
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

  // Excel upload for delivery serials with anti-duplicate validation
  const handleDeliveryExcel = async (e, itemIdx) => {
    const file = e.target.files?.[0];
    if (!file || !warehouseId) return;
    const item = deliveryItems[itemIdx];
    if (!item) return;
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await api.post(`/inventory/validate-serials-stock/${warehouseId}/${item.hardware_id}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      // Check for internal duplicates in Excel
      const parseRes = await api.post('/inventory/parse-serials', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const allSerials = parseRes.data.serials || [];
      const seen = {};
      const duplicates = [];
      allSerials.forEach((s, row) => {
        if (seen[s] !== undefined) {
          duplicates.push({ serial: s, row1: seen[s] + 1, row2: row + 1 });
        } else {
          seen[s] = row;
        }
      });

      if (duplicates.length > 0) {
        setExcelAudit(prev => ({ ...prev, [itemIdx]: { duplicates, not_found: res.data.not_found, valid: res.data.valid } }));
        toast.error(`${duplicates.length} serial(es) duplicados en el Excel`);
      } else if (res.data.has_errors) {
        setExcelAudit(prev => ({ ...prev, [itemIdx]: { duplicates: [], not_found: res.data.not_found, valid: res.data.valid } }));
        toast.error(`${res.data.not_found_count} serial(es) no encontrados en stock`);
      } else {
        setDeliveryItems(prev => prev.map((it, i) => {
          if (i !== itemIdx) return it;
          return { ...it, serials: res.data.valid, quantity: res.data.valid_count };
        }));
        setExcelAudit(prev => { const n = { ...prev }; delete n[itemIdx]; return n; });
        toast.success(`${res.data.valid_count} seriales cargados correctamente`);
      }
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al validar Excel'); }
    e.target.value = '';
  };

  const isValid = warehouseId &&
    deliveryMethod &&
    receiverName.trim() &&
    invoiceNumber.trim() &&
    deliveryItems.some(it => it.quantity > 0) &&
    deliveryItems.every(it =>
      it.quantity === 0 || !it.requires_serial || it.serials.length === it.quantity
    ) &&
    (deliveryMethod !== 'courier' || (courierName && courierOffice));

  const handleSubmit = async () => {
    if (!isValid) return;
    setSubmitting(true);
    try {
      const headers = { ...(emailHeaders || {}) };
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
        delivery_method: deliveryMethod,
        receiver_name: receiverName,
        receiver_cedula: receiverCedula,
        receiver_phone: receiverPhone,
        courier_name: deliveryMethod === 'courier' ? courierName : '',
        courier_office: deliveryMethod === 'courier' ? courierOffice : '',
        invoice_number: invoiceNumber,
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
                        <div className="flex items-center justify-between">
                          <p className="text-xs font-semibold text-teal-700 uppercase">
                            Seleccione seriales ({item.serials.length}/{item.quantity})
                          </p>
                          <label className="cursor-pointer" data-testid={`delivery-excel-upload-${idx}`}>
                            <input type="file" className="hidden" accept=".xlsx,.xls,.csv" onChange={e => handleDeliveryExcel(e, idx)} />
                            <span className="inline-flex items-center gap-1 px-2 py-1 text-[10px] font-medium bg-teal-50 border border-teal-300 rounded text-teal-700 hover:bg-teal-100 cursor-pointer transition-colors">
                              <Upload size={10} />Cargar desde Excel
                            </span>
                          </label>
                        </div>
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
                        {/* Excel audit report */}
                        {excelAudit[idx] && (
                          <div className="bg-red-50 border border-red-200 rounded p-2 space-y-1.5">
                            {excelAudit[idx].duplicates?.length > 0 && (
                              <div>
                                <div className="flex items-center gap-1">
                                  <AlertTriangle size={12} className="text-red-600" />
                                  <p className="text-[10px] font-semibold text-red-700">Seriales duplicados en el Excel:</p>
                                </div>
                                <div className="flex flex-wrap gap-1 mt-1">
                                  {excelAudit[idx].duplicates.map((d, di) => (
                                    <span key={di} className="px-1.5 py-0.5 text-[10px] bg-red-100 text-red-800 border border-red-300 rounded">
                                      {d.serial} (filas {d.row1} y {d.row2})
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}
                            {excelAudit[idx].not_found?.length > 0 && (
                              <div>
                                <p className="text-[10px] font-semibold text-red-700">No encontrados en stock:</p>
                                <div className="flex flex-wrap gap-1 mt-1">
                                  {excelAudit[idx].not_found.map(s => (
                                    <span key={s} className="px-1.5 py-0.5 text-[10px] bg-red-100 text-red-800 border border-red-300 rounded">{s}</span>
                                  ))}
                                </div>
                              </div>
                            )}
                            {excelAudit[idx].valid?.length > 0 && (
                              <button onClick={() => {
                                setDeliveryItems(prev => prev.map((it, i) => i !== idx ? it : { ...it, serials: excelAudit[idx].valid, quantity: excelAudit[idx].valid.length }));
                                setExcelAudit(prev => { const n = { ...prev }; delete n[idx]; return n; });
                              }} className="text-[10px] text-blue-600 hover:underline">
                                Usar solo los {excelAudit[idx].valid.length} seriales validos
                              </button>
                            )}
                          </div>
                        )}
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

            {/* Logistics — Delivery Method */}
            <div className="bg-slate-50 rounded-lg border p-3 space-y-3">
              <Label className="text-xs font-semibold text-slate-700 uppercase">Metodo de Envio *</Label>
              <div className="grid grid-cols-2 gap-2">
                <button type="button" onClick={() => setDeliveryMethod('personalizada')}
                  className={`flex items-center gap-2 p-3 rounded-lg border-2 transition-all text-left ${
                    deliveryMethod === 'personalizada' ? 'border-teal-500 bg-teal-50' : 'border-slate-200 hover:border-teal-300'
                  }`} data-testid="delivery-method-personal">
                  <User size={18} className={deliveryMethod === 'personalizada' ? 'text-teal-600' : 'text-slate-400'} />
                  <div>
                    <p className="text-sm font-medium text-slate-800">Entrega Personalizada</p>
                    <p className="text-[10px] text-slate-500">Receptor directo en destino</p>
                  </div>
                </button>
                <button type="button" onClick={() => setDeliveryMethod('courier')}
                  className={`flex items-center gap-2 p-3 rounded-lg border-2 transition-all text-left ${
                    deliveryMethod === 'courier' ? 'border-blue-500 bg-blue-50' : 'border-slate-200 hover:border-blue-300'
                  }`} data-testid="delivery-method-courier">
                  <Building size={18} className={deliveryMethod === 'courier' ? 'text-blue-600' : 'text-slate-400'} />
                  <div>
                    <p className="text-sm font-medium text-slate-800">Courier</p>
                    <p className="text-[10px] text-slate-500">Envio por empresa de encomiendas</p>
                  </div>
                </button>
              </div>

              {/* Common receiver fields */}
              {deliveryMethod && (
                <div className="space-y-2 pt-2 border-t">
                  <p className="text-xs font-medium text-slate-600">
                    {deliveryMethod === 'personalizada' ? 'Datos del Receptor' : 'Datos del Contacto de Recepcion'}
                  </p>
                  <div className="grid grid-cols-3 gap-2">
                    <div>
                      <Label className="text-[10px] text-slate-500">Nombre *</Label>
                      <Input value={receiverName} onChange={e => setReceiverName(e.target.value)}
                        placeholder="Nombre completo..." data-testid="delivery-receiver-name" className="h-8 text-sm" />
                    </div>
                    <div>
                      <Label className="text-[10px] text-slate-500">Cedula</Label>
                      <Input value={receiverCedula} onChange={e => setReceiverCedula(e.target.value)}
                        placeholder="V-XXXXXXXX" data-testid="delivery-receiver-cedula" className="h-8 text-sm" />
                    </div>
                    <div>
                      <Label className="text-[10px] text-slate-500">Telefono</Label>
                      <Input value={receiverPhone} onChange={e => setReceiverPhone(e.target.value)}
                        placeholder="0414-..." data-testid="delivery-receiver-phone" className="h-8 text-sm" />
                    </div>
                  </div>
                </div>
              )}

              {/* Courier-specific fields */}
              {deliveryMethod === 'courier' && (
                <div className="space-y-2 pt-2 border-t">
                  <p className="text-xs font-medium text-slate-600">Datos del Courier</p>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <Label className="text-[10px] text-slate-500">Courier *</Label>
                      <Select value={courierName} onValueChange={setCourierName}>
                        <SelectTrigger data-testid="delivery-courier-name" className="h-8 text-sm">
                          <SelectValue placeholder="Seleccione courier..." />
                        </SelectTrigger>
                        <SelectContent>
                          {COURIERS.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label className="text-[10px] text-slate-500">Oficina de Destino *</Label>
                      <Input value={courierOffice} onChange={e => setCourierOffice(e.target.value)}
                        placeholder="Nombre de oficina..." data-testid="delivery-courier-office" className="h-8 text-sm" />
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Nro. de Factura */}
            <div className="bg-amber-50 rounded-lg border border-amber-200 p-3 space-y-2">
              <Label className="text-xs font-semibold text-amber-800 uppercase flex items-center gap-1">
                <FileText size={14} /> Nro. de Factura *
              </Label>
              <Input
                value={invoiceNumber}
                onChange={e => setInvoiceNumber(e.target.value)}
                placeholder="Ej: F-12345"
                className="h-8 text-sm"
                data-testid="delivery-invoice-number"
              />
              <p className="text-[10px] text-amber-600">El nro. de factura se registra como referencia de salida en el inventario.</p>
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
