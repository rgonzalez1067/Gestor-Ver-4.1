import { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Label } from './ui/label';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from './ui/alert-dialog';
import { Search, Plus, Trash2, Package, Cpu, FileText, CheckCircle2, Monitor, CreditCard, AlertCircle, Wrench, Calendar } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

// Categorías principales - ACTUALIZADO según nueva estructura jerárquica
const EQUIPMENT_CATEGORIES = [
  { id: 'Dispositivo', name: 'Equipos', description: 'Venta de hardware principal (Laptops, Servidores, etc.)', icon: Cpu },
  { id: 'Accesorio', name: 'Accesorios', description: 'Periféricos y complementos (Mouses, cables, teclados)', icon: Package },
  { id: 'Reparacion', name: 'Reparaciones', description: 'Mano de obra técnica y servicios de mantenimiento correctivo', icon: Wrench }
];

// Subtipos para Dispositivos
const DEVICE_SUBTYPES = [
  { id: 'POS', name: 'POS', description: 'Terminales de punto de venta' },
  { id: 'Pinpad', name: 'Pinpad', description: 'Dispositivos Pinpad' }
];

// Tipos que se consideran accesorios
const ACCESSORY_TYPES = ['Accesorio', 'Base'];

export const EquipmentQuoteWizard = ({ open, onClose, onQuoteCreated, clients, hardware }) => {
  const [step, setStep] = useState(1);
  const [selectedClient, setSelectedClient] = useState(null);
  const [equipmentCategory, setEquipmentCategory] = useState(''); // "Dispositivo", "Accesorio" o "Reparacion"
  const [deviceSubtype, setDeviceSubtype] = useState(''); // "POS" o "Pinpad" (solo para Dispositivos)
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedItems, setSelectedItems] = useState([]);
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  
  // Campos específicos para REPARACIONES
  const [repairDescription, setRepairDescription] = useState('');
  const [equipmentSerialNumber, setEquipmentSerialNumber] = useState('');
  const [estimatedDeliveryDate, setEstimatedDeliveryDate] = useState('');

  // Reset cuando cambia la categoría
  useEffect(() => {
    if (equipmentCategory !== 'Dispositivo') {
      setDeviceSubtype('');
    }
    setSearchQuery('');
  }, [equipmentCategory]);

  // Determinar si el selector de ítems debe estar habilitado
  const isItemSelectionEnabled = () => {
    if (equipmentCategory === 'Dispositivo') {
      return !!deviceSubtype; // Debe tener subtipo seleccionado
    }
    return !!equipmentCategory; // Solo necesita la categoría
  };

  // Filtrar hardware según la categoría y subtipo seleccionados
  const filteredHardware = hardware.filter(item => {
    // Si no hay selección, no mostrar nada
    if (!isItemSelectionEnabled()) return false;

    let matchesCategory = false;

    if (equipmentCategory === 'Dispositivo') {
      // Filtrar por subtipo específico (POS o Pinpad)
      matchesCategory = item.type === deviceSubtype;
    } else if (equipmentCategory === 'Accesorio') {
      // Filtrar por tipos que son accesorios
      matchesCategory = ACCESSORY_TYPES.includes(item.type);
    }

    const matchesSearch = searchQuery 
      ? item.name.toLowerCase().includes(searchQuery.toLowerCase())
      : true;
    
    return matchesCategory && matchesSearch;
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
    setEquipmentCategory('');
    setDeviceSubtype('');
    setSearchQuery('');
    setSelectedItems([]);
    setNotes('');
    setShowConfirmDialog(false);
  };

  // Mostrar modal de confirmación
  const handleConfirmGenerate = () => {
    if (!selectedClient || selectedItems.length === 0) {
      toast.error('Complete todos los campos requeridos');
      return;
    }
    setShowConfirmDialog(true);
  };

  // Generar PDF y cerrar
  const handleGeneratePDF = async () => {
    setShowConfirmDialog(false);
    setLoading(true);
    
    try {
      // Determinar el tipo de equipo para el PDF
      const equipmentTypeForPdf = equipmentCategory === 'Dispositivo' 
        ? (deviceSubtype === 'POS' ? 'POS' : 'Pinpad')
        : 'Accesorio';

      const pdfData = {
        cliente_nombre: selectedClient.legal_name || selectedClient.fantasy_name,
        cliente_rif: selectedClient.rif || '',
        cliente_address: selectedClient.address || '',
        equipment_type: equipmentTypeForPdf,
        items: selectedItems,
        notes: notes
      };

      // Obtener token de autenticación
      const token = localStorage.getItem('session_token');
      if (!token) {
        toast.error('Sesión expirada. Por favor, inicie sesión nuevamente');
        setLoading(false);
        return;
      }
      
      const backendUrl = process.env.REACT_APP_BACKEND_URL;
      
      // Usar fetch nativo para mejor control de la descarga
      const response = await fetch(`${backendUrl}/api/quotes/generate-equipment-pdf`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
          'Accept': 'application/pdf'
        },
        body: JSON.stringify(pdfData)
      });
      
      // Verificar respuesta
      if (!response.ok) {
        const errorText = await response.text();
        try {
          const errorData = JSON.parse(errorText);
          toast.error(errorData.detail || 'Error al generar PDF');
        } catch {
          toast.error(`Error del servidor: ${response.status}`);
        }
        setLoading(false);
        return;
      }
      
      // Obtener el blob
      const blob = await response.blob();
      
      if (blob.size === 0) {
        toast.error('El archivo PDF está vacío');
        setLoading(false);
        return;
      }
      
      // Crear URL del blob y descargar
      const blobUrl = window.URL.createObjectURL(blob);
      const filename = `cotizacion_${equipmentTypeForPdf.toLowerCase()}_${selectedClient.rif || 'cliente'}.pdf`;
      
      const downloadLink = document.createElement('a');
      downloadLink.href = blobUrl;
      downloadLink.download = filename;
      downloadLink.style.display = 'none';
      
      document.body.appendChild(downloadLink);
      downloadLink.click();
      
      setTimeout(() => {
        if (downloadLink.parentNode) {
          document.body.removeChild(downloadLink);
        }
        window.URL.revokeObjectURL(blobUrl);
      }, 250);

      toast.success('PDF generado exitosamente');
      
      // Guardar cotización en BD
      await api.post('/quotes', {
        client_id: selectedClient.client_id,
        quote_category: 'equipment',
        equipment_type: equipmentTypeForPdf,
        equipment_items: selectedItems,
        notes: notes
      });

      onQuoteCreated && onQuoteCreated();
      resetWizard();
      onClose();
    } catch (error) {
      console.error('Error generando PDF:', error);
      toast.error('Error al generar la cotización. Verifique su conexión.');
    } finally {
      setLoading(false);
    }
  };

  // Obtener etiqueta del tipo de cotización
  const getEquipmentTypeLabel = () => {
    if (equipmentCategory === 'Dispositivo') {
      return deviceSubtype ? `Dispositivo (${deviceSubtype})` : 'Dispositivo';
    }
    return equipmentCategory || 'No seleccionado';
  };

  return (
    <>
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
                  data-testid="equipment-step1-next"
                >
                  Siguiente
                </Button>
              </div>
            </div>
          )}

          {/* Paso 2: Tipo de Cotización con Selección Dinámica */}
          {step === 2 && (
            <div className="space-y-4">
              <h3 className="font-semibold text-lg text-slate-800">Paso 2: Tipo de Cotización</h3>
              <p className="text-slate-600 text-sm">Seleccione la categoría de ítems a cotizar.</p>
              
              {/* Selección de Categoría Principal */}
              <div className="grid grid-cols-2 gap-4">
                {EQUIPMENT_CATEGORIES.map((cat) => {
                  const IconComponent = cat.icon;
                  return (
                    <button
                      key={cat.id}
                      onClick={() => {
                        setEquipmentCategory(cat.id);
                        setDeviceSubtype('');
                      }}
                      className={`p-4 rounded-lg border-2 text-left transition-all ${
                        equipmentCategory === cat.id 
                          ? 'border-brand-blue-600 bg-brand-blue-50' 
                          : 'border-slate-200 hover:border-slate-300'
                      }`}
                      data-testid={`equipment-category-${cat.id.toLowerCase()}`}
                    >
                      <div className="flex items-center gap-3">
                        <IconComponent size={24} className={equipmentCategory === cat.id ? 'text-brand-blue-600' : 'text-slate-400'} />
                        <div>
                          <p className="font-semibold text-slate-900">{cat.name}</p>
                          <p className="text-sm text-slate-500">{cat.description}</p>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Dropdown secundario para Dispositivos */}
              {equipmentCategory === 'Dispositivo' && (
                <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                  <Label className="text-blue-800 font-medium mb-2 block">
                    <Monitor size={16} className="inline mr-2" />
                    Tipo de Dispositivo *
                  </Label>
                  <Select 
                    value={deviceSubtype} 
                    onValueChange={setDeviceSubtype}
                  >
                    <SelectTrigger data-testid="equipment-device-subtype" className="bg-white">
                      <SelectValue placeholder="Seleccione tipo de dispositivo..." />
                    </SelectTrigger>
                    <SelectContent>
                      {DEVICE_SUBTYPES.map((subtype) => (
                        <SelectItem key={subtype.id} value={subtype.id}>
                          {subtype.name} - {subtype.description}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {/* Indicador de selección */}
              {(equipmentCategory === 'Accesorio' || (equipmentCategory === 'Dispositivo' && deviceSubtype)) && (
                <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-lg flex items-center gap-2">
                  <CheckCircle2 size={18} className="text-green-600" />
                  <span className="text-sm text-green-700 font-medium">
                    Seleccionado: {getEquipmentTypeLabel()}
                  </span>
                </div>
              )}

              <div className="flex justify-between pt-4">
                <Button variant="outline" onClick={() => setStep(1)}>
                  Anterior
                </Button>
                <Button 
                  onClick={() => setStep(3)} 
                  disabled={!equipmentCategory || (equipmentCategory === 'Dispositivo' && !deviceSubtype)}
                  className="bg-brand-blue-600 hover:bg-brand-blue-700"
                  data-testid="equipment-step2-next"
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
              <p className="text-slate-600 text-sm">
                {equipmentCategory === 'Accesorio' 
                  ? 'Agregue los accesorios y complementos a cotizar.'
                  : `Agregue los ${deviceSubtype === 'POS' ? 'terminales POS' : 'Pinpads'} a cotizar.`
                }
              </p>
              
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
                  <div className="p-4 text-center">
                    <AlertCircle className="mx-auto mb-2 text-amber-500" size={24} />
                    <p className="text-slate-500">No se encontraron productos</p>
                    <p className="text-sm text-slate-400 mt-1">
                      Verifique que existan productos de tipo "{equipmentCategory === 'Dispositivo' ? deviceSubtype : 'Accesorio'}" en Dispositivos y Accesorios
                    </p>
                  </div>
                ) : (
                  filteredHardware.map((item) => (
                    <div 
                      key={item.hardware_id} 
                      className="flex items-center justify-between p-3 hover:bg-slate-50 border-b last:border-b-0"
                      data-testid={`equipment-item-${item.hardware_id}`}
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
                        data-testid={`equipment-add-${item.hardware_id}`}
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
                              data-testid={`equipment-quantity-${index}`}
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
                              data-testid={`equipment-price-${index}`}
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
                              data-testid={`equipment-remove-${index}`}
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
                        <td className="px-3 py-3 text-right font-bold text-lg" data-testid="equipment-total">${totalUSD.toFixed(2)}</td>
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
                  data-testid="equipment-notes"
                />
              </div>

              <div className="flex justify-between pt-4">
                <Button variant="outline" onClick={() => setStep(2)}>
                  Anterior
                </Button>
                <Button 
                  onClick={handleConfirmGenerate} 
                  disabled={selectedItems.length === 0 || loading}
                  className="bg-brand-green-600 hover:bg-brand-green-700"
                  data-testid="equipment-confirm-btn"
                >
                  <FileText size={16} className="mr-2" />
                  {loading ? 'Generando...' : 'Confirmar y Generar PDF'}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Modal de Confirmación */}
      <AlertDialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirmar Cotización</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3">
                <p>¿Está seguro de generar la cotización para:</p>
                <div className="bg-slate-50 p-3 rounded-lg">
                  <p className="font-medium text-slate-900">{selectedClient?.legal_name || selectedClient?.fantasy_name}</p>
                  <p className="text-sm text-slate-600">RIF: {selectedClient?.rif}</p>
                  <p className="text-sm text-slate-600">Tipo: {getEquipmentTypeLabel()}</p>
                  <p className="text-sm text-slate-600">Items: {selectedItems.length}</p>
                  <p className="text-sm font-medium text-brand-green-600">Total: ${totalUSD.toFixed(2)}</p>
                </div>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="equipment-confirm-cancel">Cancelar</AlertDialogCancel>
            <AlertDialogAction 
              onClick={handleGeneratePDF} 
              className="bg-brand-green-600 hover:bg-brand-green-700"
              data-testid="equipment-confirm-generate"
            >
              Generar Cotización
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};

export default EquipmentQuoteWizard;
