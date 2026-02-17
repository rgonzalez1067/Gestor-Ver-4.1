import { useState, useEffect } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Plus, FileText, Download, ChevronRight, ChevronLeft, Monitor, Globe, Smartphone, Link, Trash2 } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const QUOTE_TYPES = [
  { id: 'VPOS', name: 'Cajas Registradoras (VPOS)', icon: Monitor, description: 'Puntos de venta físicos y cajas registradoras' },
  { id: 'GATEWAY', name: 'Ecommerce (Payment Gateway)', icon: Globe, description: 'Pasarela de pagos para comercio electrónico' },
  { id: 'MPOS', name: 'Tablet o Teléfonos Android (MPOS)', icon: Smartphone, description: 'Soluciones móviles de pago' },
  { id: 'LINK', name: 'Link de Pago', icon: Link, description: 'Enlaces de pago para cobros rápidos' }
];

export const Quotes = () => {
  const [quotes, setQuotes] = useState([]);
  const [clients, setClients] = useState([]);
  const [mediosPago, setMediosPago] = useState([]);
  const [banks, setBanks] = useState([]);
  const [hardware, setHardware] = useState([]);
  const [loading, setLoading] = useState(true);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [quoteData, setQuoteData] = useState({
    quote_type: '',
    client_id: '',
    cantidad_cajas: 1,
    medios_pago_items: [],
    hardware: [],
    notes: ''
  });
  const [selectedHardware, setSelectedHardware] = useState({});
  const [newMedioPago, setNewMedioPago] = useState({
    medio_pago_id: '',
    bank_id: '',
    cantidad: 1
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [quotesRes, clientsRes, banksRes, hardwareRes] = await Promise.all([
        api.get('/quotes'),
        api.get('/clients'),
        api.get('/banks'),
        api.get('/hardware')
      ]);
      setQuotes(quotesRes.data);
      setClients(clientsRes.data);
      setBanks(banksRes.data);
      setHardware(hardwareRes.data);
    } catch (error) {
      console.error('Error fetching data:', error);
      toast.error('Error al cargar datos');
    } finally {
      setLoading(false);
    }
  };

  const fetchMediosPagoByCompatibility = async (quoteType) => {
    try {
      const response = await api.get(`/services?compatibility=${quoteType}`);
      setMediosPago(response.data);
    } catch (error) {
      console.error('Error fetching medios de pago:', error);
      setMediosPago([]);
    }
  };

  const getWizardSteps = () => {
    if (quoteData.quote_type === 'VPOS') {
      return ['Tipo', 'Cantidad Cajas', 'Cliente', 'Medios de Pago', 'Revisión'];
    }
    return ['Tipo', 'Cliente', 'Medios de Pago', 'Hardware', 'Revisión'];
  };

  const openWizard = () => {
    setWizardOpen(true);
    setCurrentStep(0);
    setQuoteData({
      quote_type: '',
      client_id: '',
      cantidad_cajas: 1,
      medios_pago_items: [],
      hardware: [],
      notes: ''
    });
    setSelectedHardware({});
    setNewMedioPago({ medio_pago_id: '', bank_id: '', cantidad: 1 });
  };

  const nextStep = () => {
    const steps = getWizardSteps();
    
    if (currentStep === 0 && !quoteData.quote_type) {
      toast.error('Seleccione un tipo de cotización');
      return;
    }
    
    if (quoteData.quote_type === 'VPOS') {
      if (currentStep === 1 && quoteData.cantidad_cajas < 1) {
        toast.error('Ingrese la cantidad de cajas');
        return;
      }
      if (currentStep === 2 && !quoteData.client_id) {
        toast.error('Seleccione un cliente');
        return;
      }
    } else {
      if (currentStep === 1 && !quoteData.client_id) {
        toast.error('Seleccione un cliente');
        return;
      }
    }
    
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
    }
  };

  const prevStep = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const addMedioPagoItem = () => {
    if (!newMedioPago.medio_pago_id || !newMedioPago.bank_id) {
      toast.error('Seleccione un medio de pago y un banco');
      return;
    }
    
    const medioPago = mediosPago.find(m => m.service_id === newMedioPago.medio_pago_id);
    const bank = banks.find(b => b.bank_id === newMedioPago.bank_id);
    
    setQuoteData({
      ...quoteData,
      medios_pago_items: [
        ...quoteData.medios_pago_items,
        {
          ...newMedioPago,
          medio_pago_name: medioPago?.name,
          bank_name: bank?.name,
          precio: (medioPago?.setup_cost_conventional || 0) + (medioPago?.monthly_cost_conventional || 0)
        }
      ]
    });
    
    setNewMedioPago({
      medio_pago_id: '',
      bank_id: '',
      cantidad: quoteData.cantidad_cajas
    });
  };

  const removeMedioPagoItem = (index) => {
    setQuoteData({
      ...quoteData,
      medios_pago_items: quoteData.medios_pago_items.filter((_, i) => i !== index)
    });
  };

  const toggleHardware = (hw) => {
    const key = hw.hardware_id;
    if (selectedHardware[key]) {
      const { [key]: removed, ...rest } = selectedHardware;
      setSelectedHardware(rest);
    } else {
      setSelectedHardware({
        ...selectedHardware,
        [key]: { ...hw, quantity: 1 }
      });
    }
  };

  const updateHardwareQuantity = (id, quantity) => {
    setSelectedHardware({
      ...selectedHardware,
      [id]: { ...selectedHardware[id], quantity: parseInt(quantity) || 1 }
    });
  };

  const handleSubmitQuote = async () => {
    try {
      const serviceItems = quoteData.medios_pago_items.map((item) => {
        const medioPago = mediosPago.find(m => m.service_id === item.medio_pago_id);
        return {
          item_type: 'service',
          item_id: item.medio_pago_id,
          item_name: `${item.medio_pago_name} - ${item.bank_name}`,
          quantity: item.cantidad,
          unit_price_usd: (medioPago?.setup_cost_conventional || 0) + (medioPago?.monthly_cost_conventional || 0),
          total_usd: ((medioPago?.setup_cost_conventional || 0) + (medioPago?.monthly_cost_conventional || 0)) * item.cantidad
        };
      });

      const hardwareItems = Object.values(selectedHardware).map((h) => ({
        item_type: 'hardware',
        item_id: h.hardware_id,
        item_name: h.name,
        quantity: h.quantity,
        unit_price_usd: h.price_usd,
        total_usd: h.price_usd * h.quantity
      }));

      const payload = {
        client_id: quoteData.client_id,
        quote_type: quoteData.quote_type,
        services: serviceItems,
        hardware: hardwareItems,
        notes: quoteData.notes
      };

      await api.post('/quotes', payload);
      toast.success('Cotización creada exitosamente');
      setWizardOpen(false);
      fetchData();
    } catch (error) {
      console.error('Error creating quote:', error);
      toast.error('Error al crear cotización');
    }
  };

  const downloadPDF = async (quoteId) => {
    try {
      const response = await api.get(`/quotes/${quoteId}/pdf`, {
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `cotizacion_${quoteId}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      toast.success('PDF descargado exitosamente');
    } catch (error) {
      console.error('Error downloading PDF:', error);
      toast.error('Error al descargar PDF');
    }
  };

  const getQuoteTypeName = (typeId) => {
    const type = QUOTE_TYPES.find(t => t.id === typeId);
    return type ? type.name : typeId;
  };

  if (loading) {
    return (
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center bg-white">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-green-600 mx-auto"></div>
            <p className="mt-4 text-slate-900">Cargando cotizaciones...</p>
          </div>
        </div>
      </div>
    );
  }

  const selectedClient = clients.find(c => c.client_id === quoteData.client_id);
  const totalMediosPagoUSD = quoteData.medios_pago_items.reduce(
    (sum, item) => sum + (item.precio || 0) * item.cantidad, 0
  );
  const totalHardwareUSD = Object.values(selectedHardware).reduce(
    (sum, h) => sum + h.price_usd * h.quantity, 0
  );
  const grandTotal = totalMediosPagoUSD + totalHardwareUSD;

  const WIZARD_STEPS = getWizardSteps();

  const renderVPOSCantidadCajas = () => (
    <div>
      <Label className="text-lg font-semibold mb-4 block">¿Cuántas cajas registradoras necesita?</Label>
      <div className="max-w-xs mt-4">
        <Input
          type="number"
          min="1"
          value={quoteData.cantidad_cajas}
          onChange={(e) => {
            const cantidad = parseInt(e.target.value) || 1;
            setQuoteData({ ...quoteData, cantidad_cajas: cantidad });
            setNewMedioPago({ ...newMedioPago, cantidad: cantidad });
          }}
          className="text-2xl text-center h-16"
          data-testid="cantidad-cajas-input"
        />
        <p className="text-sm text-slate-500 mt-2 text-center">
          Esta cantidad se usará por defecto en cada medio de pago
        </p>
      </div>
    </div>
  );

  const renderMediosPagoVPOS = () => (
    <div>
      <Label className="text-lg font-semibold mb-4 block">Configurar Medios de Pago</Label>
      
      {quoteData.medios_pago_items.length > 0 && (
        <div className="mb-6 space-y-2">
          <p className="text-sm font-medium text-slate-600 mb-2">Medios de pago agregados:</p>
          {quoteData.medios_pago_items.map((item, index) => (
            <div key={index} className="flex items-center justify-between p-3 bg-brand-green-50 border border-brand-green-200 rounded-lg">
              <div>
                <p className="font-medium text-slate-900">{item.medio_pago_name}</p>
                <p className="text-sm text-slate-600">{item.bank_name} • {item.cantidad} cajas</p>
              </div>
              <div className="flex items-center gap-3">
                <span className="font-mono text-brand-green-600 font-semibold">
                  ${((item.precio || 0) * item.cantidad).toFixed(2)}
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => removeMedioPagoItem(index)}
                  className="text-red-600"
                >
                  <Trash2 size={16} />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
      
      <div className="bg-slate-50 rounded-lg p-4 border">
        <p className="text-sm font-medium text-slate-700 mb-3">Agregar medio de pago</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <Label>Medio de Pago</Label>
            <Select
              value={newMedioPago.medio_pago_id}
              onValueChange={(value) => setNewMedioPago({ ...newMedioPago, medio_pago_id: value })}
            >
              <SelectTrigger data-testid="select-medio-pago">
                <SelectValue placeholder="Seleccione..." />
              </SelectTrigger>
              <SelectContent>
                {mediosPago.map((mp) => (
                  <SelectItem key={mp.service_id} value={mp.service_id}>
                    {mp.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Banco</Label>
            <Select
              value={newMedioPago.bank_id}
              onValueChange={(value) => setNewMedioPago({ ...newMedioPago, bank_id: value })}
            >
              <SelectTrigger data-testid="select-banco">
                <SelectValue placeholder="Seleccione..." />
              </SelectTrigger>
              <SelectContent>
                {banks.map((bank) => (
                  <SelectItem key={bank.bank_id} value={bank.bank_id}>
                    {bank.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Cantidad de Cajas</Label>
            <Input
              type="number"
              min="1"
              value={newMedioPago.cantidad}
              onChange={(e) => setNewMedioPago({ ...newMedioPago, cantidad: parseInt(e.target.value) || 1 })}
            />
          </div>
        </div>
        <Button
          onClick={addMedioPagoItem}
          className="mt-4 bg-brand-blue-600 hover:bg-brand-blue-700 text-white"
          data-testid="add-medio-pago-button"
        >
          <Plus size={16} className="mr-2" />
          Nuevo Medio de Pago
        </Button>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen bg-white">
      <Sidebar />
      
      <main className="flex-1 p-8" data-testid="quotes-page">
        <div className="max-w-7xl mx-auto">
          <div className="flex justify-between items-center mb-8">
            <div>
              <h1 className="text-4xl font-bold text-slate-900 font-manrope mb-2">
                Cotizaciones
              </h1>
              <p className="text-slate-600">Genere cotizaciones profesionales para sus clientes</p>
            </div>
            
            <Button
              onClick={openWizard}
              data-testid="create-quote-button"
              className="bg-brand-green-600 hover:bg-brand-green-700 text-white"
            >
              <Plus size={20} className="mr-2" />
              Nueva Cotización
            </Button>
          </div>

          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Número
                  </th>
                  <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Tipo
                  </th>
                  <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Cliente
                  </th>
                  <th className="px-6 py-4 text-right text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Total USD
                  </th>
                  <th className="px-6 py-4 text-right text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Total Bs
                  </th>
                  <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Fecha
                  </th>
                  <th className="px-6 py-4 text-center text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Acciones
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {quotes.map((quote) => {
                  const client = clients.find(c => c.client_id === quote.client_id);
                  return (
                    <tr key={quote.quote_id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-6 py-4 text-sm font-mono font-medium text-slate-900">
                        {quote.quote_number}
                      </td>
                      <td className="px-6 py-4 text-sm">
                        <span className="px-2 py-1 text-xs font-medium bg-brand-blue-50 text-brand-blue-600 rounded">
                          {getQuoteTypeName(quote.quote_type)}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-900">
                        {client?.fantasy_name || 'N/A'}
                      </td>
                      <td className="px-6 py-4 text-sm font-mono text-right text-brand-green-600 font-semibold">
                        ${quote.total_usd.toFixed(2)}
                      </td>
                      <td className="px-6 py-4 text-sm font-mono text-right text-slate-700">
                        {quote.total_bs.toFixed(2)} Bs
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-600">
                        {new Date(quote.created_at).toLocaleDateString('es-VE')}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center justify-center">
                          <Button
                            size="sm"
                            variant="outline"
                            data-testid={`download-quote-${quote.quote_id}`}
                            onClick={() => downloadPDF(quote.quote_id)}
                            className="text-brand-blue-600 hover:text-brand-blue-700"
                          >
                            <Download size={16} className="mr-1" />
                            PDF
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {quotes.length === 0 && (
              <div className="text-center py-12 text-slate-500">
                <FileText size={48} className="mx-auto mb-4 text-slate-300" />
                <p>No hay cotizaciones</p>
                <p className="text-sm mt-1">Cree su primera cotización usando el botón superior</p>
              </div>
            )}
          </div>

          <Dialog open={wizardOpen} onOpenChange={setWizardOpen}>
            <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle className="font-manrope text-2xl">
                  Nueva Cotización
                </DialogTitle>
              </DialogHeader>

              <div className="mb-6">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  {WIZARD_STEPS.map((step, index) => (
                    <div key={step} className="flex items-center">
                      <div className={`flex items-center justify-center w-8 h-8 rounded-full border-2 font-semibold text-sm ${
                        index === currentStep
                          ? 'border-brand-blue-600 bg-brand-blue-600 text-white'
                          : index < currentStep
                          ? 'border-brand-green-600 bg-brand-green-600 text-white'
                          : 'border-slate-300 text-slate-400'
                      }`}>
                        {index + 1}
                      </div>
                      <span className={`ml-2 font-medium text-sm ${
                        index === currentStep ? 'text-brand-blue-600' : index < currentStep ? 'text-brand-green-600' : 'text-slate-400'
                      }`}>
                        {step}
                      </span>
                      {index < WIZARD_STEPS.length - 1 && (
                        <ChevronRight className="mx-2 text-slate-300" size={16} />
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div className="min-h-[400px]">
                {/* Step 0: Tipo de Cotización */}
                {currentStep === 0 && (
                  <div>
                    <Label className="text-lg font-semibold mb-4 block">¿Qué tipo de cotización desea crear?</Label>
                    <div className="grid grid-cols-2 gap-4 mt-4">
                      {QUOTE_TYPES.map((type) => {
                        const Icon = type.icon;
                        const isSelected = quoteData.quote_type === type.id;
                        return (
                          <div
                            key={type.id}
                            onClick={() => setQuoteData({ ...quoteData, quote_type: type.id })}
                            className={`p-6 rounded-lg border-2 cursor-pointer transition-all ${
                              isSelected
                                ? 'border-brand-green-600 bg-brand-green-50'
                                : 'border-slate-200 hover:border-brand-blue-300 hover:bg-slate-50'
                            }`}
                            data-testid={`quote-type-${type.id}`}
                          >
                            <div className="flex items-center gap-4">
                              <div className={`p-3 rounded-lg ${isSelected ? 'bg-brand-green-600 text-white' : 'bg-slate-100 text-slate-600'}`}>
                                <Icon size={28} />
                              </div>
                              <div>
                                <h3 className="font-semibold text-slate-900">{type.name}</h3>
                                <p className="text-sm text-slate-500 mt-1">{type.description}</p>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* VPOS: Step 1 - Cantidad de Cajas */}
                {quoteData.quote_type === 'VPOS' && currentStep === 1 && renderVPOSCantidadCajas()}

                {/* VPOS: Step 2 - Cliente / Others: Step 1 - Cliente */}
                {((quoteData.quote_type === 'VPOS' && currentStep === 2) || 
                  (quoteData.quote_type !== 'VPOS' && currentStep === 1)) && (
                  <div>
                    <div className="mb-4 p-4 bg-brand-blue-50 rounded-lg">
                      <p className="text-brand-blue-700 font-medium">
                        Tipo: {getQuoteTypeName(quoteData.quote_type)}
                        {quoteData.quote_type === 'VPOS' && ` • ${quoteData.cantidad_cajas} cajas`}
                      </p>
                    </div>
                    <Label htmlFor="client" className="text-lg font-semibold">Seleccione el Cliente</Label>
                    <Select
                      value={quoteData.client_id}
                      onValueChange={(value) => setQuoteData({ ...quoteData, client_id: value })}
                    >
                      <SelectTrigger data-testid="select-client" className="mt-3">
                        <SelectValue placeholder="Seleccione un cliente" />
                      </SelectTrigger>
                      <SelectContent>
                        {clients.map((client) => (
                          <SelectItem key={client.client_id} value={client.client_id}>
                            {client.fantasy_name} ({client.rif})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}

                {/* VPOS: Step 3 - Medios de Pago / Others: Step 2 - Medios de Pago */}
                {((quoteData.quote_type === 'VPOS' && currentStep === 3) || 
                  (quoteData.quote_type !== 'VPOS' && currentStep === 2)) && renderMediosPagoVPOS()}

                {/* Others: Step 3 - Hardware (no VPOS) */}
                {quoteData.quote_type !== 'VPOS' && currentStep === 3 && (
                  <div>
                    <Label className="text-lg font-semibold mb-4 block">Seleccione el Hardware</Label>
                    <div className="space-y-3 mt-4 max-h-[350px] overflow-y-auto">
                      {hardware.map((hw) => {
                        const isSelected = !!selectedHardware[hw.hardware_id];
                        return (
                          <div
                            key={hw.hardware_id}
                            onClick={() => toggleHardware(hw)}
                            className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
                              isSelected
                                ? 'border-brand-green-600 bg-brand-green-50'
                                : 'border-slate-200 hover:border-slate-300'
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <div>
                                <p className="font-medium text-slate-900">{hw.name}</p>
                                <p className="text-sm text-slate-500">{hw.type}</p>
                              </div>
                              <div className="text-right">
                                <p className="font-semibold text-brand-green-600">${hw.price_usd.toFixed(2)}</p>
                              </div>
                            </div>
                            {isSelected && (
                              <div className="mt-3 pt-3 border-t">
                                <Label className="text-xs">Cantidad</Label>
                                <Input
                                  type="number"
                                  min="1"
                                  value={selectedHardware[hw.hardware_id].quantity}
                                  onChange={(e) => updateHardwareQuantity(hw.hardware_id, e.target.value)}
                                  onClick={(e) => e.stopPropagation()}
                                  className="mt-1 w-24"
                                />
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Revisión Final */}
                {((quoteData.quote_type === 'VPOS' && currentStep === 4) || 
                  (quoteData.quote_type !== 'VPOS' && currentStep === 4)) && (
                  <div>
                    <Label className="text-lg font-semibold mb-4 block">Resumen de la Cotización</Label>
                    
                    <div className="bg-slate-50 rounded-lg p-4 mb-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <p className="text-sm text-slate-500">Tipo</p>
                          <p className="font-medium">{getQuoteTypeName(quoteData.quote_type)}</p>
                        </div>
                        <div>
                          <p className="text-sm text-slate-500">Cliente</p>
                          <p className="font-medium">{selectedClient?.fantasy_name}</p>
                        </div>
                        {quoteData.quote_type === 'VPOS' && (
                          <div>
                            <p className="text-sm text-slate-500">Cantidad de Cajas</p>
                            <p className="font-medium">{quoteData.cantidad_cajas}</p>
                          </div>
                        )}
                      </div>
                    </div>

                    {quoteData.medios_pago_items.length > 0 && (
                      <div className="mb-4">
                        <h4 className="font-semibold text-brand-blue-600 mb-2">Medios de Pago</h4>
                        {quoteData.medios_pago_items.map((item, index) => (
                          <div key={index} className="flex justify-between py-2 border-b">
                            <span>{item.medio_pago_name} - {item.bank_name} x{item.cantidad}</span>
                            <span className="font-mono">${((item.precio || 0) * item.cantidad).toFixed(2)}</span>
                          </div>
                        ))}
                        <div className="flex justify-between py-2 font-semibold">
                          <span>Subtotal Medios de Pago</span>
                          <span className="text-brand-blue-600">${totalMediosPagoUSD.toFixed(2)}</span>
                        </div>
                      </div>
                    )}

                    {Object.keys(selectedHardware).length > 0 && (
                      <div className="mb-4">
                        <h4 className="font-semibold text-brand-green-600 mb-2">Hardware</h4>
                        {Object.values(selectedHardware).map((h) => (
                          <div key={h.hardware_id} className="flex justify-between py-2 border-b">
                            <span>{h.name} x{h.quantity}</span>
                            <span className="font-mono">${(h.price_usd * h.quantity).toFixed(2)}</span>
                          </div>
                        ))}
                        <div className="flex justify-between py-2 font-semibold">
                          <span>Subtotal Hardware</span>
                          <span className="text-brand-green-600">${totalHardwareUSD.toFixed(2)}</span>
                        </div>
                      </div>
                    )}

                    <div className="bg-slate-900 text-white rounded-lg p-4 mt-4">
                      <div className="flex justify-between text-xl font-bold">
                        <span>TOTAL</span>
                        <span>${grandTotal.toFixed(2)} USD</span>
                      </div>
                    </div>

                    <div className="mt-4">
                      <Label htmlFor="notes">Notas adicionales</Label>
                      <Textarea
                        id="notes"
                        value={quoteData.notes}
                        onChange={(e) => setQuoteData({ ...quoteData, notes: e.target.value })}
                        placeholder="Observaciones o notas para la cotización..."
                        rows={3}
                        className="mt-2"
                      />
                    </div>
                  </div>
                )}
              </div>

              <div className="flex justify-between pt-4 border-t">
                <Button
                  variant="outline"
                  onClick={prevStep}
                  disabled={currentStep === 0}
                >
                  <ChevronLeft size={16} className="mr-1" />
                  Anterior
                </Button>

                {currentStep < WIZARD_STEPS.length - 1 ? (
                  <Button onClick={nextStep} className="bg-brand-blue-600 hover:bg-brand-blue-700 text-white">
                    Siguiente
                    <ChevronRight size={16} className="ml-1" />
                  </Button>
                ) : (
                  <Button
                    onClick={handleSubmitQuote}
                    className="bg-brand-green-600 hover:bg-brand-green-700 text-white"
                    data-testid="submit-quote-button"
                  >
                    Finalizar Cotización
                  </Button>
                )}
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </main>
    </div>
  );
};

export default Quotes;
