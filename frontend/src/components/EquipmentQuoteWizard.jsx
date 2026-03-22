import { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Label } from './ui/label';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from './ui/alert-dialog';
import { Search, Plus, Trash2, Package, Cpu, FileText, CheckCircle2, Monitor, CreditCard, AlertCircle, Wrench, Calendar, Smartphone, Upload, X, ShieldCheck, ShieldAlert, ChevronRight } from 'lucide-react';
import { toast } from 'sonner';

// Categorías principales - 4 categorías planas
const EQUIPMENT_CATEGORIES = [
  { id: 'Verifone', name: 'Equipos Verifone', description: 'PinPad P200 en Windows/Linux', icon: Cpu },
  { id: 'Morefun', name: 'Equipos Morefun', description: 'Soluciones móviles en Android', icon: Smartphone },
  { id: 'Accesorio', name: 'Accesorios', description: 'Periféricos y complementos (Mouses, cables, teclados)', icon: Package },
  { id: 'Reparacion', name: 'Reparaciones', description: 'Mano de obra técnica y servicios de mantenimiento correctivo', icon: Wrench }
];

// Tipos de hardware que aplican para categorías de equipos (Verifone y Morefun)
const DEVICE_TYPES = ['POS', 'Pinpad'];

// Tipos que se consideran accesorios
const ACCESSORY_TYPES = ['Accesorio', 'Base'];

// Tipos para selección de modelo en reparaciones (POS y Pinpad)
const REPAIR_MODEL_TYPES = ['POS', 'Pinpad'];

export const EquipmentQuoteWizard = ({ open, onClose, onQuoteCreated, clients, hardware }) => {
  const [step, setStep] = useState(1);
  const [selectedClient, setSelectedClient] = useState(null);
  const [equipmentCategory, setEquipmentCategory] = useState(''); // "Verifone", "Morefun", "Accesorio" o "Reparacion"
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedItems, setSelectedItems] = useState([]);
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  
  // Campos específicos para REPARACIONES
  const [repairDescription, setRepairDescription] = useState('');
  const [equipmentSerialNumber, setEquipmentSerialNumber] = useState('');
  const [estimatedDeliveryDate, setEstimatedDeliveryDate] = useState('');

  // Carga masiva de seriales (legacy - mantener para compatibilidad)
  const [bulkUploadLoading, setBulkUploadLoading] = useState(false);
  const [bulkValidationResult, setBulkValidationResult] = useState(null);
  const [acceptUnknownSerials, setAcceptUnknownSerials] = useState(false);
  const [confirmedSerials, setConfirmedSerials] = useState([]);

  // Flujo cíclico multi-modelo para reparaciones
  const [repairModels, setRepairModels] = useState([]); // Array de { model_id, model_name, quantity, serials }
  const [currentModel, setCurrentModel] = useState(null); // Hardware item seleccionado
  const [currentModelQty, setCurrentModelQty] = useState('');
  const [currentModelSerials, setCurrentModelSerials] = useState([]); // Seriales ingresados para modelo actual
  const [serialInput, setSerialInput] = useState(''); // Input para ingreso manual de serial
  const [modelSearchQuery, setModelSearchQuery] = useState(''); // Buscador de modelos

  // Hardware POS/Pinpad disponible para selección de modelo (solo Bienes físicos)
  const availableModels = hardware.filter(item =>
    REPAIR_MODEL_TYPES.includes(item.type) &&
    (item.asset_type || 'Bien') === 'Bien' &&
    (modelSearchQuery ? item.name.toLowerCase().includes(modelSearchQuery.toLowerCase()) : true) &&
    !repairModels.some(rm => rm.model_id === item.hardware_id)
  );

  // Reset cuando cambia la categoría
  useEffect(() => {
    if (equipmentCategory !== 'Reparacion') {
      setRepairDescription('');
      setEquipmentSerialNumber('');
      setEstimatedDeliveryDate('');
      setBulkValidationResult(null);
      setAcceptUnknownSerials(false);
      setConfirmedSerials([]);
      setRepairModels([]);
      setCurrentModel(null);
      setCurrentModelQty('');
      setCurrentModelSerials([]);
      setSerialInput('');
      setModelSearchQuery('');
    }
    setSearchQuery('');
  }, [equipmentCategory]);

  // Filtrar hardware según la categoría seleccionada
  const filteredHardware = hardware.filter(item => {
    if (!equipmentCategory) return false;

    let matchesCategory = false;

    if (equipmentCategory === 'Verifone' || equipmentCategory === 'Morefun') {
      matchesCategory = DEVICE_TYPES.includes(item.type) && (item.asset_type || 'Bien') === 'Bien';
    } else if (equipmentCategory === 'Accesorio') {
      matchesCategory = ACCESSORY_TYPES.includes(item.type);
    } else if (equipmentCategory === 'Reparacion') {
      const repairTypes = ['Mantenimiento', 'Consultoria', 'Componente', 'Pieza'];
      matchesCategory = repairTypes.includes(item.type);
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
    setSearchQuery('');
    setSelectedItems([]);
    setNotes('');
    setShowConfirmDialog(false);
    setRepairDescription('');
    setEquipmentSerialNumber('');
    setEstimatedDeliveryDate('');
    setBulkUploadLoading(false);
    setBulkValidationResult(null);
    setAcceptUnknownSerials(false);
    setConfirmedSerials([]);
    setRepairModels([]);
    setCurrentModel(null);
    setCurrentModelQty('');
    setCurrentModelSerials([]);
    setSerialInput('');
    setModelSearchQuery('');
  };

  // ==================== FLUJO CÍCLICO MULTI-MODELO ====================
  const addSerialManual = () => {
    const val = serialInput.trim();
    if (!val) return;
    if (currentModelSerials.includes(val)) {
      toast.error('Este serial ya fue ingresado');
      return;
    }
    const qty = parseInt(currentModelQty, 10) || 0;
    if (currentModelSerials.length >= qty) {
      toast.error(`Ya se alcanzó la cantidad declarada (${qty})`);
      return;
    }
    setCurrentModelSerials(prev => [...prev, val]);
    setSerialInput('');
  };

  const removeSerial = (idx) => {
    setCurrentModelSerials(prev => prev.filter((_, i) => i !== idx));
  };

  const confirmCurrentModel = () => {
    const qty = parseInt(currentModelQty, 10) || 0;
    if (currentModelSerials.length !== qty) {
      toast.error(`La cantidad de seriales (${currentModelSerials.length}) no coincide con la cantidad declarada (${qty})`);
      return;
    }
    setRepairModels(prev => [...prev, {
      model_id: currentModel.hardware_id,
      model_name: currentModel.name,
      quantity: qty,
      serials: [...currentModelSerials]
    }]);
    // Reset para nuevo modelo
    setCurrentModel(null);
    setCurrentModelQty('');
    setCurrentModelSerials([]);
    setSerialInput('');
    setModelSearchQuery('');
    setBulkValidationResult(null);
    setAcceptUnknownSerials(false);
    toast.success('Modelo confirmado. Puede agregar otro modelo o continuar.');
  };

  const removeRepairModel = (idx) => {
    setRepairModels(prev => prev.filter((_, i) => i !== idx));
  };

  // ==================== CARGA MASIVA DE SERIALES (POR MODELO) ====================
  const handleBulkUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = '';
    if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
      toast.error('El archivo debe ser formato Excel (.xlsx)');
      return;
    }
    setBulkUploadLoading(true);
    setBulkValidationResult(null);
    setAcceptUnknownSerials(false);
    try {
      const token = localStorage.getItem('session_token');
      const fd = new FormData();
      fd.append('file', file);
      fd.append('client_id', selectedClient?.client_id || '');
      const backendUrl = process.env.REACT_APP_BACKEND_URL;
      const res = await fetch(`${backendUrl}/api/quotes/validate-repair-serials`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: fd
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Error al procesar el archivo');
      }
      const result = await res.json();
      setBulkValidationResult(result);
      if (result.not_found_count === 0) {
        toast.success(`${result.found_count} serial(es) validados exitosamente`);
      } else {
        toast.info(`${result.found_count} encontrados, ${result.not_found_count} no registrados en inventario`);
      }
    } catch (err) {
      toast.error(err.message || 'Error al cargar el archivo');
      setBulkValidationResult(null);
    } finally {
      setBulkUploadLoading(false);
    }
  };

  const handleConfirmBulkSerials = () => {
    if (!bulkValidationResult) return;
    const qty = parseInt(currentModelQty, 10) || 0;
    const allBulk = [
      ...bulkValidationResult.found.map(s => s.serial),
      ...(acceptUnknownSerials ? bulkValidationResult.not_found.map(s => s.serial) : [])
    ];
    // Combinar con los manuales ya ingresados (sin duplicados)
    const merged = [...currentModelSerials];
    for (const s of allBulk) {
      if (!merged.includes(s)) merged.push(s);
    }
    if (merged.length > qty && qty > 0) {
      toast.error(`Los seriales (${merged.length}) superan la cantidad declarada (${qty}). Ajuste la cantidad o reduzca los seriales.`);
      return;
    }
    setCurrentModelSerials(merged);
    setBulkValidationResult(null);
    setAcceptUnknownSerials(false);
    toast.success(`${allBulk.length} serial(es) agregados del archivo`);
  };

  const clearBulkUpload = () => {
    setBulkValidationResult(null);
    setAcceptUnknownSerials(false);
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
      // Mapear categoría al tipo para el PDF
      const equipmentTypeForPdf = equipmentCategory === 'Reparacion' ? 'Reparación' : equipmentCategory;

      const pdfData = {
        client_id: selectedClient.client_id,
        cliente_nombre: selectedClient.legal_name || selectedClient.fantasy_name,
        cliente_rif: selectedClient.rif || '',
        cliente_address: selectedClient.address || '',
        equipment_type: equipmentTypeForPdf,
        items: selectedItems,
        notes: notes,
        repair_description: repairDescription,
        equipment_serial_number: equipmentSerialNumber,
        estimated_delivery_date: estimatedDeliveryDate,
        bulk_serials: confirmedSerials,
        repair_models: repairModels.map(m => ({
          model_name: m.model_name,
          model_id: m.model_id,
          quantity: m.quantity,
          serials: m.serials
        }))
      };

      const token = localStorage.getItem('session_token');
      if (!token) {
        toast.error('Sesión expirada. Por favor, inicie sesión nuevamente');
        return;
      }
      
      const backendUrl = process.env.REACT_APP_BACKEND_URL;
      
      const response = await fetch(`${backendUrl}/api/quotes/generate-equipment-pdf`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
          'Accept': 'application/pdf'
        },
        body: JSON.stringify(pdfData)
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        try {
          const errorData = JSON.parse(errorText);
          toast.error(errorData.detail || 'Error al generar PDF');
        } catch {
          toast.error(`Error del servidor: ${response.status}`);
        }
        return;
      }
      
      const blob = await response.blob();
      
      if (blob.size === 0) {
        toast.error('El archivo PDF está vacío');
        return;
      }
      
      // Descargar PDF
      const blobUrl = window.URL.createObjectURL(blob);
      const filename = `cotizacion_${equipmentTypeForPdf.toLowerCase()}_${selectedClient.rif || 'cliente'}.pdf`;
      
      const downloadLink = document.createElement('a');
      downloadLink.href = blobUrl;
      downloadLink.download = filename;
      downloadLink.style.display = 'none';
      document.body.appendChild(downloadLink);
      downloadLink.click();
      
      setTimeout(() => {
        if (downloadLink.parentNode) document.body.removeChild(downloadLink);
        window.URL.revokeObjectURL(blobUrl);
      }, 250);

      toast.success('Cotización creada y PDF generado exitosamente');
      onQuoteCreated && onQuoteCreated();
    } catch (error) {
      console.error('Error generando PDF:', error);
      toast.error('Error al generar la cotización. Verifique su conexión.');
    } finally {
      setLoading(false);
      resetWizard();
      onClose();
    }
  };

  // Obtener etiqueta del tipo de cotización
  const getEquipmentTypeLabel = () => {
    const cat = EQUIPMENT_CATEGORIES.find(c => c.id === equipmentCategory);
    return cat ? cat.name : 'No seleccionado';
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onClose}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-xl">
              <Package className="text-brand-blue-600" />
              Nueva Cotización: Equipos, Accesorios y Reparaciones
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
              
              {/* Selección de Categoría Principal - 4 categorías */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {EQUIPMENT_CATEGORIES.map((cat) => {
                  const IconComponent = cat.icon;
                  return (
                    <button
                      key={cat.id}
                      onClick={() => setEquipmentCategory(cat.id)}
                      className={`p-4 rounded-lg border-2 text-left transition-all ${
                        equipmentCategory === cat.id 
                          ? 'border-brand-blue-600 bg-brand-blue-50' 
                          : 'border-slate-200 hover:border-slate-300'
                      }`}
                      data-testid={`equipment-category-${cat.id.toLowerCase()}`}
                    >
                      <div className="flex flex-col items-center text-center gap-2">
                        <IconComponent size={28} className={equipmentCategory === cat.id ? 'text-brand-blue-600' : 'text-slate-400'} />
                        <div>
                          <p className="font-semibold text-slate-900 text-sm">{cat.name}</p>
                          <p className="text-xs text-slate-500 mt-1">{cat.description}</p>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Campos específicos para REPARACIONES - Flujo cíclico multi-modelo */}
              {equipmentCategory === 'Reparacion' && (
                <div className="mt-4 p-4 bg-orange-50 border border-orange-200 rounded-lg space-y-4">
                  <div className="flex items-center gap-2 text-orange-800 font-medium">
                    <Wrench size={18} />
                    Información de la Reparación
                  </div>
                  
                  <div>
                    <Label className="text-orange-800">Descripción de la falla *</Label>
                    <Textarea
                      value={repairDescription}
                      onChange={(e) => setRepairDescription(e.target.value)}
                      placeholder="Describa el problema o falla de los equipos..."
                      className="bg-white mt-1"
                      rows={2}
                      data-testid="repair-description"
                    />
                  </div>
                  
                  <div className="w-1/2">
                    <Label className="text-orange-800">Fecha estimada de entrega</Label>
                    <div className="relative mt-1">
                      <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                      <Input type="date" value={estimatedDeliveryDate} onChange={(e) => setEstimatedDeliveryDate(e.target.value)} className="bg-white pl-10" data-testid="repair-delivery-date" />
                    </div>
                  </div>

                  {/* Modelos confirmados */}
                  {repairModels.length > 0 && (
                    <div className="space-y-2">
                      <Label className="text-orange-800 font-medium">Modelos registrados</Label>
                      {repairModels.map((rm, idx) => (
                        <div key={idx} className="flex items-center justify-between bg-white rounded-lg border border-orange-200 p-3">
                          <div className="flex items-center gap-3">
                            <CheckCircle2 size={18} className="text-green-500" />
                            <div>
                              <p className="text-sm font-semibold text-slate-800">{rm.model_name}</p>
                              <p className="text-xs text-slate-500">{rm.quantity} equipo(s) — {rm.serials.length} serial(es)</p>
                            </div>
                          </div>
                          <Button variant="ghost" size="sm" onClick={() => removeRepairModel(idx)} className="text-red-400 hover:text-red-600 h-7" data-testid={`remove-model-${idx}`}>
                            <Trash2 size={14} />
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Ciclo de ingreso de modelo */}
                  <div className="border-t border-orange-200 pt-4 space-y-3">
                    <Label className="text-orange-800 font-medium flex items-center gap-1.5">
                      <Plus size={15} />
                      {repairModels.length > 0 ? 'Agregar otro modelo a la orden' : 'Seleccionar modelo de equipo'}
                    </Label>

                    {/* Paso A: Selección de modelo */}
                    {!currentModel ? (
                      <div className="space-y-2">
                        <div className="relative">
                          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                          <Input
                            placeholder="Buscar modelo POS o Pinpad..."
                            value={modelSearchQuery}
                            onChange={(e) => setModelSearchQuery(e.target.value)}
                            className="pl-10 bg-white"
                            data-testid="repair-model-search"
                          />
                        </div>
                        <div className="max-h-36 overflow-y-auto border rounded-lg bg-white">
                          {availableModels.length === 0 ? (
                            <p className="p-3 text-center text-xs text-slate-400">No hay modelos disponibles</p>
                          ) : (
                            availableModels.map(item => (
                              <button
                                key={item.hardware_id}
                                onClick={() => { setCurrentModel(item); setModelSearchQuery(''); }}
                                className="w-full text-left px-3 py-2.5 hover:bg-orange-50 border-b last:border-b-0 flex items-center justify-between"
                                data-testid={`repair-select-model-${item.hardware_id}`}
                              >
                                <div>
                                  <p className="text-sm font-medium text-slate-800">{item.name}</p>
                                  <p className="text-xs text-slate-400">{item.type} • ${item.price_usd?.toFixed(2) || '0.00'}</p>
                                </div>
                                <ChevronRight size={16} className="text-slate-300" />
                              </button>
                            ))
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-3 bg-white border border-orange-200 rounded-lg p-4">
                        {/* Header del modelo seleccionado */}
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Cpu size={18} className="text-orange-600" />
                            <span className="font-semibold text-slate-800">{currentModel.name}</span>
                          </div>
                          <Button variant="ghost" size="sm" onClick={() => { setCurrentModel(null); setCurrentModelQty(''); setCurrentModelSerials([]); setSerialInput(''); setBulkValidationResult(null); }} className="text-xs text-slate-500 h-7">
                            Cambiar modelo
                          </Button>
                        </div>

                        {/* Paso B: Cantidad */}
                        <div>
                          <Label className="text-sm text-slate-600">Cantidad de equipos *</Label>
                          <Input
                            type="number" min="1"
                            value={currentModelQty}
                            onChange={(e) => setCurrentModelQty(e.target.value)}
                            placeholder="Ej: 5"
                            className="w-32 mt-1"
                            data-testid="repair-model-qty"
                          />
                        </div>

                        {/* Paso C: Captura de seriales */}
                        {parseInt(currentModelQty, 10) > 0 && (
                          <div className="space-y-2">
                            <div className="flex items-center justify-between">
                              <Label className="text-sm text-slate-600">
                                Seriales ({currentModelSerials.length} / {currentModelQty})
                              </Label>
                              {currentModelSerials.length < parseInt(currentModelQty, 10) && (
                                <label className="cursor-pointer">
                                  <input type="file" accept=".xlsx,.xls" onChange={handleBulkUpload} className="hidden" data-testid="repair-bulk-file" />
                                  <span className="text-xs text-orange-600 hover:text-orange-800 flex items-center gap-1 font-medium">
                                    <Upload size={13} />{bulkUploadLoading ? 'Procesando...' : 'Carga desde Excel'}
                                  </span>
                                </label>
                              )}
                            </div>

                            {/* Input manual */}
                            {currentModelSerials.length < parseInt(currentModelQty, 10) && !bulkValidationResult && (
                              <div className="flex gap-2">
                                <Input
                                  value={serialInput}
                                  onChange={(e) => setSerialInput(e.target.value)}
                                  onKeyDown={(e) => e.key === 'Enter' && addSerialManual()}
                                  placeholder="Escribir serial y Enter..."
                                  className="flex-1"
                                  data-testid="repair-serial-input"
                                />
                                <Button size="sm" variant="outline" onClick={addSerialManual} className="shrink-0" data-testid="repair-add-serial-btn">
                                  <Plus size={14} />
                                </Button>
                              </div>
                            )}

                            {/* Resultados de validación masiva */}
                            {bulkValidationResult && (
                              <div className="space-y-2 border border-slate-200 rounded-lg p-3 bg-slate-50">
                                {bulkValidationResult.found.length > 0 && (
                                  <div>
                                    <p className="text-[10px] font-semibold text-green-700 flex items-center gap-1 mb-1"><ShieldCheck size={12} />En inventario ({bulkValidationResult.found_count})</p>
                                    <div className="flex flex-wrap gap-1 max-h-16 overflow-y-auto">
                                      {bulkValidationResult.found.map((s, i) => (
                                        <span key={i} className="px-1.5 py-0.5 bg-green-100 text-green-800 text-[10px] font-mono rounded">{s.serial}</span>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {bulkValidationResult.not_found.length > 0 && (
                                  <div>
                                    <p className="text-[10px] font-semibold text-amber-700 flex items-center gap-1 mb-1"><ShieldAlert size={12} />No registrados ({bulkValidationResult.not_found_count})</p>
                                    <div className="flex flex-wrap gap-1 max-h-16 overflow-y-auto">
                                      {bulkValidationResult.not_found.map((s, i) => (
                                        <span key={i} className="px-1.5 py-0.5 bg-amber-100 text-amber-800 text-[10px] font-mono rounded">{s.serial}</span>
                                      ))}
                                    </div>
                                    <label className="flex items-center gap-2 mt-2 cursor-pointer">
                                      <input type="checkbox" checked={acceptUnknownSerials} onChange={(e) => setAcceptUnknownSerials(e.target.checked)} className="rounded border-amber-400" data-testid="bulk-accept-unknown" />
                                      <span className="text-[11px] text-amber-800 font-medium">Aceptar equipos no registrados</span>
                                    </label>
                                  </div>
                                )}
                                <div className="flex gap-2">
                                  <Button size="sm" onClick={handleConfirmBulkSerials} disabled={bulkValidationResult.found_count === 0 && !acceptUnknownSerials} className="flex-1 bg-orange-600 hover:bg-orange-700 text-white text-xs h-8" data-testid="bulk-confirm-btn">
                                    Agregar seriales
                                  </Button>
                                  <Button size="sm" variant="ghost" onClick={clearBulkUpload} className="text-xs text-slate-500 h-8">Cancelar</Button>
                                </div>
                              </div>
                            )}

                            {/* Seriales ingresados */}
                            {currentModelSerials.length > 0 && (
                              <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
                                {currentModelSerials.map((s, i) => (
                                  <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 bg-slate-100 text-slate-700 text-[11px] font-mono rounded-full border">
                                    {s}
                                    <button onClick={() => removeSerial(i)} className="text-red-400 hover:text-red-600"><X size={10} /></button>
                                  </span>
                                ))}
                              </div>
                            )}

                            {/* Paso D: Validación de cuota y confirmación */}
                            {currentModelSerials.length === parseInt(currentModelQty, 10) && (
                              <Button size="sm" onClick={confirmCurrentModel} className="w-full bg-green-600 hover:bg-green-700 text-white" data-testid="repair-confirm-model-btn">
                                <CheckCircle2 size={14} className="mr-1.5" />
                                Confirmar {currentModel.name} ({currentModelSerials.length} serial{currentModelSerials.length > 1 ? 'es' : ''})
                              </Button>
                            )}
                            {currentModelSerials.length > 0 && currentModelSerials.length !== parseInt(currentModelQty, 10) && (
                              <p className="text-xs text-amber-600 flex items-center gap-1">
                                <AlertCircle size={12} />
                                Faltan {parseInt(currentModelQty, 10) - currentModelSerials.length} serial(es) para completar la cuota
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Indicador de selección */}
              {equipmentCategory && (equipmentCategory !== 'Reparacion' || repairDescription) && (
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
                  disabled={!equipmentCategory || (equipmentCategory === 'Reparacion' && !repairDescription)}
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
                  : equipmentCategory === 'Reparacion'
                    ? 'Agregue los servicios de reparación a cotizar.'
                    : `Agregue los equipos ${equipmentCategory} a cotizar.`
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
                      Verifique que existan productos de tipo "{getEquipmentTypeLabel()}" en Dispositivos y Accesorios
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
                  {repairModels.length > 0 && (
                    <div className="mt-1">
                      <p className="text-sm text-slate-600 font-medium">Modelos de equipo:</p>
                      {repairModels.map((rm, i) => (
                        <p key={i} className="text-xs text-slate-500 ml-2">• {rm.model_name}: {rm.quantity} equipo(s), {rm.serials.length} serial(es)</p>
                      ))}
                    </div>
                  )}
                  {confirmedSerials.length > 0 && repairModels.length === 0 && (
                    <p className="text-sm text-slate-600">Seriales: {confirmedSerials.length}</p>
                  )}
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
