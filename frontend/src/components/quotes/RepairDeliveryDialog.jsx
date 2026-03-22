import { useState, useEffect, useCallback } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Button } from '../ui/button';
import { Label } from '../ui/label';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';
import { Checkbox } from '../ui/checkbox';
import { Wrench, User, Building, Package, Check, Search } from 'lucide-react';
import api from '../../utils/api';
import { toast } from 'sonner';

const COURIERS = ['ZOOM (Oficina)', 'ZOOM (Casillero)', 'MRW', 'Tealca', 'Domesa'];

export function RepairDeliveryDialog({ open, onOpenChange, quoteId, exceptionInfo, onDelivered }) {
  const [loading, setLoading] = useState(false);
  const [prepData, setPrepData] = useState(null);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [searchTerm, setSearchTerm] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [notes, setNotes] = useState('');

  // Logistics
  const [deliveryMethod, setDeliveryMethod] = useState('');
  const [receiverName, setReceiverName] = useState('');
  const [receiverCedula, setReceiverCedula] = useState('');
  const [receiverPhone, setReceiverPhone] = useState('');
  const [courierName, setCourierName] = useState('');
  const [courierOffice, setCourierOffice] = useState('');

  const fetchPrep = useCallback(async () => {
    if (!quoteId) return;
    setLoading(true);
    try {
      const res = await api.get(`/quotes/${quoteId}/repair-delivery-prep`);
      setPrepData(res.data);
      // Pre-seleccionar todos los equipos de esta cotización
      const allIds = new Set();
      (res.data.modelos || []).forEach(m => {
        (m.serials || []).forEach(s => {
          if (s.quote_number === res.data.quote_number) {
            allIds.add(s.taller_equipo_id);
          }
        });
      });
      setSelectedIds(allIds);
    } catch {
      toast.error('Error al obtener datos de equipos en taller');
    } finally {
      setLoading(false);
    }
  }, [quoteId]);

  useEffect(() => {
    if (open && quoteId) {
      setSelectedIds(new Set());
      setSearchTerm('');
      setNotes('');
      setDeliveryMethod('');
      setReceiverName('');
      setReceiverCedula('');
      setReceiverPhone('');
      setCourierName('');
      setCourierOffice('');
      setPrepData(null);
      fetchPrep();
    }
  }, [open, quoteId, fetchPrep]);

  const toggleSerial = (id) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAllInModel = (serials, checked) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      serials.forEach(s => {
        if (checked) next.add(s.taller_equipo_id);
        else next.delete(s.taller_equipo_id);
      });
      return next;
    });
  };

  const filterSerials = (serials) => {
    if (!searchTerm.trim()) return serials;
    const term = searchTerm.toLowerCase();
    return serials.filter(s =>
      s.serial.toLowerCase().includes(term) ||
      s.quote_number.toLowerCase().includes(term)
    );
  };

  const isValid = deliveryMethod &&
    receiverName.trim() &&
    selectedIds.size > 0 &&
    (deliveryMethod !== 'courier' || (courierName && courierOffice));

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
        selected_serials: Array.from(selectedIds),
        delivery_method: deliveryMethod,
        receiver_name: receiverName,
        receiver_cedula: receiverCedula,
        receiver_phone: receiverPhone,
        courier_name: deliveryMethod === 'courier' ? courierName : '',
        courier_office: deliveryMethod === 'courier' ? courierOffice : '',
        notes,
      };
      const res = await api.post(`/quotes/${quoteId}/repair-deliver`, payload, { headers });
      toast.success(res.data.message || 'Entrega registrada exitosamente');
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
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="repair-delivery-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            <Wrench size={22} className="text-cyan-600" />
            Entrega de Equipos Reparados
          </DialogTitle>
          {prepData && (
            <p className="text-sm text-slate-500 mt-1">
              Cotización: <strong>{prepData.quote_number}</strong> — {prepData.client_name}
            </p>
          )}
        </DialogHeader>

        {loading && !prepData ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-600" />
          </div>
        ) : (
          <div className="space-y-4">
            {/* Resumen */}
            {prepData && (
              <div className="bg-cyan-50 border border-cyan-200 rounded-lg p-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Package size={16} className="text-cyan-600" />
                  <span className="text-sm font-medium text-cyan-800">
                    {prepData.total_equipos} equipo(s) en taller para este cliente
                  </span>
                </div>
                <span className="text-xs bg-cyan-100 text-cyan-700 px-2 py-1 rounded font-medium">
                  {selectedIds.size} seleccionado(s)
                </span>
              </div>
            )}

            {/* Buscador */}
            {prepData && prepData.total_equipos > 5 && (
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  value={searchTerm}
                  onChange={e => setSearchTerm(e.target.value)}
                  placeholder="Buscar serial o cotización..."
                  className="pl-9 h-8 text-sm"
                  data-testid="repair-delivery-search"
                />
              </div>
            )}

            {/* Listado por modelo */}
            {prepData && prepData.modelos.map((modelo, mIdx) => {
              const filteredSerials = filterSerials(modelo.serials);
              if (filteredSerials.length === 0) return null;
              const allChecked = filteredSerials.every(s => selectedIds.has(s.taller_equipo_id));
              const someChecked = filteredSerials.some(s => selectedIds.has(s.taller_equipo_id));

              return (
                <div key={mIdx} className="bg-slate-50 border rounded-lg p-3 space-y-2" data-testid={`repair-model-group-${mIdx}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Checkbox
                        checked={allChecked}
                        className={someChecked && !allChecked ? 'opacity-60' : ''}
                        onCheckedChange={(checked) => toggleAllInModel(filteredSerials, checked)}
                        data-testid={`repair-model-toggle-all-${mIdx}`}
                      />
                      <p className="font-medium text-sm text-slate-900">{modelo.modelo}</p>
                    </div>
                    <span className="text-xs text-slate-500">
                      {filteredSerials.filter(s => selectedIds.has(s.taller_equipo_id)).length}/{filteredSerials.length} serial(es)
                    </span>
                  </div>

                  <div className="flex flex-wrap gap-1.5 max-h-40 overflow-y-auto">
                    {filteredSerials.map((s) => {
                      const isSelected = selectedIds.has(s.taller_equipo_id);
                      const isFromThisQuote = prepData && s.quote_number === prepData.quote_number;
                      return (
                        <button
                          key={s.taller_equipo_id}
                          type="button"
                          onClick={() => toggleSerial(s.taller_equipo_id)}
                          className={`px-2 py-1 text-xs rounded border transition-colors flex items-center gap-1 ${
                            isSelected
                              ? 'bg-cyan-600 text-white border-cyan-600'
                              : isFromThisQuote
                                ? 'bg-cyan-50 text-cyan-800 border-cyan-300 hover:bg-cyan-100'
                                : 'bg-white text-slate-700 border-slate-300 hover:border-cyan-400'
                          }`}
                          data-testid={`repair-serial-${s.serial}`}
                        >
                          {s.serial}
                          {isSelected && <Check size={10} />}
                          {!isSelected && isFromThisQuote && <span className="text-[8px] ml-0.5 opacity-70">COT</span>}
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}

            {prepData && prepData.total_equipos === 0 && (
              <div className="text-center py-8 text-slate-500 text-sm">
                No hay equipos en reparación para este cliente
              </div>
            )}

            {/* Metodo de Envio */}
            <div className="bg-slate-50 rounded-lg border p-3 space-y-3">
              <Label className="text-xs font-semibold text-slate-700 uppercase">Metodo de Envio *</Label>
              <div className="grid grid-cols-2 gap-2">
                <button type="button" onClick={() => setDeliveryMethod('personalizada')}
                  className={`flex items-center gap-2 p-3 rounded-lg border-2 transition-all text-left ${
                    deliveryMethod === 'personalizada' ? 'border-cyan-500 bg-cyan-50' : 'border-slate-200 hover:border-cyan-300'
                  }`} data-testid="repair-delivery-method-personal">
                  <User size={18} className={deliveryMethod === 'personalizada' ? 'text-cyan-600' : 'text-slate-400'} />
                  <div>
                    <p className="text-sm font-medium text-slate-800">Entrega Personalizada</p>
                    <p className="text-[10px] text-slate-500">Receptor directo en destino</p>
                  </div>
                </button>
                <button type="button" onClick={() => setDeliveryMethod('courier')}
                  className={`flex items-center gap-2 p-3 rounded-lg border-2 transition-all text-left ${
                    deliveryMethod === 'courier' ? 'border-blue-500 bg-blue-50' : 'border-slate-200 hover:border-blue-300'
                  }`} data-testid="repair-delivery-method-courier">
                  <Building size={18} className={deliveryMethod === 'courier' ? 'text-blue-600' : 'text-slate-400'} />
                  <div>
                    <p className="text-sm font-medium text-slate-800">Courier</p>
                    <p className="text-[10px] text-slate-500">Envio por empresa de encomiendas</p>
                  </div>
                </button>
              </div>

              {deliveryMethod && (
                <div className="space-y-2 pt-2 border-t">
                  <p className="text-xs font-medium text-slate-600">
                    {deliveryMethod === 'personalizada' ? 'Datos del Receptor' : 'Datos del Contacto de Recepcion'}
                  </p>
                  <div className="grid grid-cols-3 gap-2">
                    <div>
                      <Label className="text-[10px] text-slate-500">Nombre *</Label>
                      <Input value={receiverName} onChange={e => setReceiverName(e.target.value)}
                        placeholder="Nombre completo..." data-testid="repair-delivery-receiver-name" className="h-8 text-sm" />
                    </div>
                    <div>
                      <Label className="text-[10px] text-slate-500">Cedula</Label>
                      <Input value={receiverCedula} onChange={e => setReceiverCedula(e.target.value)}
                        placeholder="V-XXXXXXXX" data-testid="repair-delivery-receiver-cedula" className="h-8 text-sm" />
                    </div>
                    <div>
                      <Label className="text-[10px] text-slate-500">Telefono</Label>
                      <Input value={receiverPhone} onChange={e => setReceiverPhone(e.target.value)}
                        placeholder="0414-..." data-testid="repair-delivery-receiver-phone" className="h-8 text-sm" />
                    </div>
                  </div>
                </div>
              )}

              {deliveryMethod === 'courier' && (
                <div className="space-y-2 pt-2 border-t">
                  <p className="text-xs font-medium text-slate-600">Datos del Courier</p>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <Label className="text-[10px] text-slate-500">Courier *</Label>
                      <Select value={courierName} onValueChange={setCourierName}>
                        <SelectTrigger data-testid="repair-delivery-courier-name" className="h-8 text-sm">
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
                        placeholder="Nombre de oficina..." data-testid="repair-delivery-courier-office" className="h-8 text-sm" />
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Notas */}
            <div>
              <Label>Observaciones</Label>
              <Textarea
                value={notes}
                onChange={e => setNotes(e.target.value)}
                placeholder="Notas adicionales para la Nota de Entrega..."
                rows={2}
                data-testid="repair-delivery-notes"
              />
            </div>

            {/* Acciones */}
            <div className="flex justify-end gap-2 pt-2 border-t">
              <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
              <Button
                onClick={handleSubmit}
                disabled={!isValid || submitting}
                className="bg-cyan-600 hover:bg-cyan-700 text-white"
                data-testid="repair-delivery-submit"
              >
                {submitting ? 'Procesando...' : `Confirmar Entrega (${selectedIds.size} equipo${selectedIds.size !== 1 ? 's' : ''})`}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
