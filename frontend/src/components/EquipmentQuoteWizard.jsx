import { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Label } from './ui/label';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Search, Plus, Trash2, Package, Cpu, FileText, CheckCircle2 } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const EQUIPMENT_TYPES = [
  { id: 'Dispositivo', name: 'Dispositivos', description: 'Equipos de pago (Pinpads, Terminales, etc.)' },
  { id: 'Accesorio', name: 'Accesorios', description: 'Complementos y consumibles' }
];

export const EquipmentQuoteWizard = ({ open, onClose, onQuoteCreated, clients, hardware }) => {
  const [step, setStep] = useState(1);
  const [selectedClient, setSelectedClient] = useState(null);
  const [equipmentType, setEquipmentType] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedItems, setSelectedItems] = useState([]);
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);

  // Filtrar hardware por tipo y búsqueda
  const filteredHardware = hardware.filter(item => {
    const matchesType = equipmentType ? item.type === equipmentType : true;
    const matchesSearch = searchQuery 
      ? item.name.toLowerCase().includes(searchQuery.toLowerCase())
      : true;
    return matchesType && matchesSearch;
  });

  // Agregar item a la cotización
  const addItem = (item) => {
    const existingIndex = selectedItems.findIndex(i => i.hardware_id === item.hardware_id);
    
    if (existingIndex >= 0) {
      // Incrementar cantidad si ya existe
      const updated = [...selectedItems];
      updated[existingIndex].quantity += 1;
      updated[existingIndex].total_usd = updated[existingIndex].quantity * updated[existingIndex].unit_price_usd;
      setSelectedItems(updated);
    } else {
      // Agregar nuevo item
      setSelectedItems([...selectedItems, {
        hardware_id: item.hardware_id,
        name: item.name,
        hardware_type: item.type,
        quantity: 1,
        unit_price_usd: item.price_usd || 0,
        total_usd: item.price_usd || 0
      }]);
    }
    toast.success(`${item.name} agregado`);
  };

  // Actualizar cantidad de un item
  const updateItemQuantity = (index, quantity) => {
    const updated = [...selectedItems];
    updated[index].quantity = Math.max(1, parseInt(quantity) || 1);
    updated[index].total_usd = updated[index].quantity * updated[index].unit_price_usd;
    setSelectedItems(updated);
  };

  // Actualizar precio de un item
  const updateItemPrice = (index, price) => {
    const updated = [...selectedItems];
    updated[index].unit_price_usd = parseFloat(price) || 0;
    updated[index].total_usd = updated[index].quantity * updated[index].unit_price_usd;
    setSelectedItems(updated);
  };

  // Eliminar item
  const removeItem = (index) => {
    setSelectedItems(selectedItems.filter((_, i) => i !== index));
  };

  // Calcular total
  const totalUSD = selectedItems.reduce((sum, item) => sum + item.total_usd, 0);

  // Reset wizard
  const resetWizard = () => {
    setStep(1);
    setSelectedClient(null);
    setEquipmentType('');
    setSearchQuery('');
    setSelectedItems([]);
    setNotes('');
  };

  // Generar PDF y cerrar
  const handleGeneratePDF = async () => {
    if (!selectedClient || selectedItems.length === 0) {
      toast.error('Complete todos los campos requeridos');
      return;
    }

    setLoading(true);
    try {
      const pdfData = {
        cliente_nombre: selectedClient.legal_name || selectedClient.fantasy_name,
        cliente_rif: selectedClient.rif || '',
        cliente_address: selectedClient.address || '',
        equipment_type: equipmentType,
        items: selectedItems,
        notes: notes
      };

      const response = await api.post('/quotes/generate-equipment-pdf', pdfData, {
        responseType: 'blob'
      });

      // Descargar PDF
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `cotizacion_${equipmentType.toLowerCase()}_${selectedClient.rif || 'cliente'}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      toast.success('PDF generado exitosamente');
      
      // Guardar cotización en BD
      await api.post('/quotes', {
        client_id: selectedClient.client_id,
        quote_category: 'equipment',
        equipment_type: equipmentType,
        equipment_items: selectedItems,
        notes: notes
      });

      onQuoteCreated && onQuoteCreated();
      resetWizard();
      onClose();
    } catch (error) {
      console.error('Error generando PDF:', error);
      toast.error('Error al generar la cotización');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl">
            <Package className="text-brand-blue-600" />
            Nueva Cotización de Equipos y Accesorios
          </DialogTitle>
        </DialogHeader>

        {/* Indicador de pasos */}
        <div className="flex items-center justify-center gap-2 mb-6">
          {[1, 2, 3].map((s) => (
            <div key={s} className="flex items-center">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                step >= s ? 'bg-brand-blue-600 text-white' : 'bg-slate-200 text-slate-500'
              }`}>
                {step > s ? <CheckCircle2 size={16} /> : s}
              </div>
              {s < 3 && (
                <div className={`w-16 h-1 mx-1 ${step > s ? 'bg-brand-blue-600' : 'bg-slate-200'}`} />
              )}
            </div>
          ))}
        </div>

        {/* Paso 1: Selección de Cliente */}
        {step === 1 && (
          <div className="space-y-4">
            <h3 className="font-semibold text-lg text-slate-800">Paso 1: Identificación del Cliente</h3>
            <p className="text-slate-600 text-sm">Busque y seleccione el cliente para esta cotización.</p>
            
            <div>
              <Label>Cliente *</Label>
              <Select 
                value={selectedClient?.client_id || ''} 
                onValueChange={(value) => {
                  const client = clients.find(c => c.client_id === value);
                  setSelectedClient(client);
                }}
              >
                <SelectTrigger data-testid="equipment-select-client">
                  <SelectValue placeholder="Buscar por RIF o Nombre..." />
                </SelectTrigger>
                <SelectContent>
                  {clients.map((client) => (
                    <SelectItem key={client.client_id} value={client.client_id}>
                      {client.rif} - {client.fantasy_name || client.legal_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {selectedClient && (
              <div className="bg-slate-50 rounded-lg p-4 space-y-2">
                <p className="font-medium text-slate-900">{selectedClient.legal_name}</p>
                <p className="text-sm text-slate-600">RIF: {selectedClient.rif}</p>
                {selectedClient.address && (
                  <p className="text-sm text-slate-600">Dirección: {selectedClient.address}</p>
                )}
              </div>
            )}

            <div className="flex justify-end pt-4">
              <Button 
                onClick={() => setStep(2)} 
                disabled={!selectedClient}
                className="bg-brand-blue-600 hover:bg-brand-blue-700"
              >
                Siguiente
              </Button>
            </div>
          </div>
        )}

        {/* Paso 2: Tipo de Cotización */}
        {step === 2 && (
          <div className="space-y-4">
            <h3 className="font-semibold text-lg text-slate-800">Paso 2: Tipo de Cotización</h3>
            <p className="text-slate-600 text-sm">Seleccione el tipo de ítems a cotizar. Esto determinará el formato del PDF.</p>
            
            <div className="grid grid-cols-2 gap-4">
              {EQUIPMENT_TYPES.map((type) => (
                <button
                  key={type.id}
                  onClick={() => setEquipmentType(type.id)}
                  className={`p-4 rounded-lg border-2 text-left transition-all ${
                    equipmentType === type.id 
                      ? 'border-brand-blue-600 bg-brand-blue-50' 
                      : 'border-slate-200 hover:border-slate-300'
                  }`}
                  data-testid={`equipment-type-${type.id.toLowerCase()}`}
                >
                  <div className="flex items-center gap-3">
                    {type.id === 'Dispositivo' ? <Cpu size={24} className="text-brand-blue-600" /> : <Package size={24} className="text-amber-600" />}
                    <div>
                      <p className="font-semibold text-slate-900">{type.name}</p>
                      <p className="text-sm text-slate-500">{type.description}</p>
                    </div>
                  </div>
                </button>
              ))}
            </div>

            <div className="flex justify-between pt-4">
              <Button variant="outline" onClick={() => setStep(1)}>
                Anterior
              </Button>
              <Button 
                onClick={() => setStep(3)} 
                disabled={!equipmentType}
                className="bg-brand-blue-600 hover:bg-brand-blue-700"
              >
                Siguiente
              </Button>
            </div>
          </div>
        )}

        {/* Paso 3: Selección de Items */}
        {step === 3 && (
          <div className="space-y-4">
            <h3 className="font-semibold text-lg text-slate-800">Paso 3: Selección de Productos</h3>
            <p className="text-slate-600 text-sm">Busque y agregue los productos a cotizar.</p>
            
            {/* Buscador */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" size={18} />
              <Input
                placeholder="Buscar producto..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
                data-testid="equipment-search-input"
              />
            </div>

            {/* Lista de productos disponibles */}
            <div className="border rounded-lg max-h-48 overflow-y-auto">
              {filteredHardware.length === 0 ? (
                <p className="p-4 text-center text-slate-500">No se encontraron productos</p>
              ) : (
                filteredHardware.map((item) => (
                  <div 
                    key={item.hardware_id} 
                    className="flex items-center justify-between p-3 hover:bg-slate-50 border-b last:border-b-0"
                  >
                    <div>
                      <p className="font-medium text-slate-900">{item.name}</p>
                      <p className="text-sm text-slate-500">{item.type} • ${item.price_usd?.toFixed(2) || '0.00'}</p>
                    </div>
                    <Button 
                      size="sm" 
                      variant="outline" 
                      onClick={() => addItem(item)}
                      className="text-brand-green-600 border-brand-green-600"
                    >
                      <Plus size={16} className="mr-1" /> Agregar
                    </Button>
                  </div>
                ))
              )}
            </div>

            {/* Items seleccionados */}
            {selectedItems.length > 0 && (
              <div className="mt-4">
                <h4 className="font-medium text-slate-800 mb-2">Productos Seleccionados ({selectedItems.length})</h4>
                <table className="w-full border rounded-lg overflow-hidden">
                  <thead className="bg-slate-100">
                    <tr>
                      <th className="px-3 py-2 text-left text-sm font-medium text-slate-700">Producto</th>
                      <th className="px-3 py-2 text-center text-sm font-medium text-slate-700 w-24">Cantidad</th>
                      <th className="px-3 py-2 text-right text-sm font-medium text-slate-700 w-28">Precio Unit.</th>
                      <th className="px-3 py-2 text-right text-sm font-medium text-slate-700 w-28">Total</th>
                      <th className="px-3 py-2 w-12"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedItems.map((item, index) => (
                      <tr key={index} className="border-t">
                        <td className="px-3 py-2 text-slate-900">{item.name}</td>
                        <td className="px-3 py-2">
                          <Input
                            type="number"
                            min="1"
                            value={item.quantity}
                            onChange={(e) => updateItemQuantity(index, e.target.value)}
                            className="w-20 text-center"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <Input
                            type="number"
                            step="0.01"
                            min="0"
                            value={item.unit_price_usd}
                            onChange={(e) => updateItemPrice(index, e.target.value)}
                            className="w-24 text-right"
                          />
                        </td>
                        <td className="px-3 py-2 text-right font-medium text-brand-green-600">
                          ${item.total_usd.toFixed(2)}
                        </td>
                        <td className="px-3 py-2">
                          <Button 
                            size="sm" 
                            variant="ghost" 
                            onClick={() => removeItem(index)}
                            className="text-red-500 hover:text-red-700"
                          >
                            <Trash2 size={16} />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="bg-slate-900 text-white">
                    <tr>
                      <td colSpan="3" className="px-3 py-3 text-right font-semibold">TOTAL:</td>
                      <td className="px-3 py-3 text-right font-bold text-lg">${totalUSD.toFixed(2)}</td>
                      <td></td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}

            {/* Notas */}
            <div>
              <Label>Observaciones (opcional)</Label>
              <Textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Notas adicionales para la cotización..."
                rows={2}
              />
            </div>

            <div className="flex justify-between pt-4">
              <Button variant="outline" onClick={() => setStep(2)}>
                Anterior
              </Button>
              <Button 
                onClick={handleGeneratePDF} 
                disabled={selectedItems.length === 0 || loading}
                className="bg-brand-green-600 hover:bg-brand-green-700"
                data-testid="equipment-generate-pdf"
              >
                <FileText size={16} className="mr-2" />
                {loading ? 'Generando...' : 'Confirmar y Generar PDF'}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default EquipmentQuoteWizard;
