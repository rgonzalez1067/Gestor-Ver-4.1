import { useState, useEffect } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Plus, FileText, Download, Monitor, Globe, Smartphone, Link, Trash2, Building2, CreditCard, CheckCircle2 } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const QUOTE_TYPES = [
  { id: 'VPOS', name: 'Cajas Registradoras (VPOS)', icon: Monitor, description: 'Puntos de venta físicos' },
  { id: 'GATEWAY', name: 'Ecommerce (Payment Gateway)', icon: Globe, description: 'Pasarela de pagos' },
  { id: 'MPOS', name: 'Tablet o Android (MPOS)', icon: Smartphone, description: 'Soluciones móviles' },
  { id: 'LINK', name: 'Link de Pago', icon: Link, description: 'Enlaces de cobro' }
];

const PRICING_MODELS = [
  { id: 'conventional', name: 'Modelo Convencional', description: 'Precios estándar' },
  { id: 'outsourcing', name: 'Modelo Outsourcing', description: 'Precios para tercerización' }
];

// Conceptos EXCLUSIVOS de Setup (Inversión Inicial) - NO aparecen en recurrentes
const SETUP_CONCEPTS = [
  { name: 'Suscripción PDV/Banco', isDefault: true, type: 'setup' },
  { name: 'Configuración dispositivo (Pinpad o POS)', isDefault: true, type: 'setup' },
  { name: 'Configuración PDV en MServer', isDefault: true, type: 'setup' },
  { name: 'Configuración Medio de Pago / Banco en MServer, por PDV', isDefault: true, type: 'setup' }
];

// Conceptos de Costos Recurrentes (Mantenimiento) - Solo aparecen en recurrentes
const RECURRING_CONCEPTS = [
  { name: 'Suscripción Medio de Pago / Banco en MServer por PDV', isDefault: true, type: 'recurring' },
  { name: 'Hospedaje MServer', isDefault: true, type: 'recurring' }
];

export const Quotes = () => {
  const [quotes, setQuotes] = useState([]);
  const [clients, setClients] = useState([]);
  const [banks, setBanks] = useState([]);
  const [serviceCatalog, setServiceCatalog] = useState([]); // Catálogo de precios
  const [loading, setLoading] = useState(true);
  const [wizardOpen, setWizardOpen] = useState(false);
  
  // Estado del formulario de cotización
  const [quoteData, setQuoteData] = useState({
    quote_type: '',
    client_id: '',
    pricing_model: '', // 'conventional' o 'outsourcing'
    cantidad_cajas: 1,
    cantidad_bancos: 1,
    setup_items: [],       // Items exclusivos de Setup
    recurring_items: [],   // Items exclusivos de Recurrente
    additional_items: [],  // Items adicionales (medios de pago de bancos)
    descuento: 0,
    notes: ''
  });
  });
  
  // Estado para agregar nuevo medio de pago
  const [selectedBankId, setSelectedBankId] = useState('');
  const [selectedMedioPagoId, setSelectedMedioPagoId] = useState('');
  const [availableMediosPago, setAvailableMediosPago] = useState([]);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [quotesRes, clientsRes, banksRes, servicesRes] = await Promise.all([
        api.get('/quotes'),
        api.get('/clients'),
        api.get('/banks'),
        api.get('/services') // Cargar catálogo de precios
      ]);
      setQuotes(quotesRes.data);
      setClients(clientsRes.data);
      setBanks(banksRes.data);
      setServiceCatalog(servicesRes.data);
    } catch (error) {
      console.error('Error fetching data:', error);
      toast.error('Error al cargar datos');
    } finally {
      setLoading(false);
    }
  };

  // Buscar precio en el catálogo de servicios según modelo seleccionado
  const findServicePrice = (productName) => {
    const service = serviceCatalog.find(s => 
      s.name.toLowerCase() === productName.toLowerCase() ||
      s.name.toLowerCase().includes(productName.toLowerCase()) ||
      productName.toLowerCase().includes(s.name.toLowerCase())
    );
    
    if (service) {
      // Seleccionar precios según el modelo elegido
      const isOutsourcing = quoteData.pricing_model === 'outsourcing';
      return {
        setup_cost: isOutsourcing 
          ? (service.setup_cost_outsourcing || 0) 
          : (service.setup_cost_conventional || 0),
        monthly_cost: isOutsourcing 
          ? (service.monthly_cost_outsourcing || 0) 
          : (service.monthly_cost_conventional || 0),
        application_type: service.application_type || 'both'
      };
    }
    return { setup_cost: 0, monthly_cost: 0, application_type: 'both' };
  };

  // Obtener los medios de pago asociados al banco seleccionado
  const handleBankSelect = (bankId) => {
    setSelectedBankId(bankId);
    setSelectedMedioPagoId('');
    
    const bank = banks.find(b => b.bank_id === bankId);
    if (bank && bank.products) {
      const compatibilityField = getCompatibilityField(quoteData.quote_type);
      const filteredProducts = bank.products.filter(p => p[compatibilityField] !== false);
      setAvailableMediosPago(filteredProducts);
    } else {
      setAvailableMediosPago([]);
    }
  };

  const getCompatibilityField = (quoteType) => {
    switch (quoteType) {
      case 'VPOS': return 'vpos_available';
      case 'GATEWAY': return 'gateway_available';
      case 'MPOS': return 'mpos_available';
      case 'LINK': return 'link_available';
      default: return 'vpos_available';
    }
  };

  // Inicializar conceptos de Setup cuando se completan los parámetros
  const initializeSetupConcepts = (pricingModel, cantidadCajas, cantidadBancos) => {
    return SETUP_CONCEPTS.map((concept) => {
      const prices = findServicePriceWithModel(concept.name, pricingModel);
      return {
        id: `setup_${concept.name}`,
        medio_pago_name: concept.name,
        cantidad_cajas: cantidadCajas,
        cantidad_bancos: cantidadBancos,
        tarifa: prices.setup_cost,
        isDefault: true,
        type: 'setup'
      };
    });
  };

  // Inicializar conceptos de Recurrente cuando se completan los parámetros
  const initializeRecurringConcepts = (pricingModel, cantidadCajas, cantidadBancos) => {
    return RECURRING_CONCEPTS.map((concept) => {
      const prices = findServicePriceWithModel(concept.name, pricingModel);
      return {
        id: `recurring_${concept.name}`,
        medio_pago_name: concept.name,
        cantidad_cajas: cantidadCajas,
        cantidad_bancos: cantidadBancos,
        tarifa: prices.monthly_cost,
        isDefault: true,
        type: 'recurring'
      };
    });
  };

  // Versión de findServicePrice que acepta modelo como parámetro (para inicialización)
  const findServicePriceWithModel = (productName, pricingModel) => {
    const service = serviceCatalog.find(s => 
      s.name.toLowerCase() === productName.toLowerCase() ||
      s.name.toLowerCase().includes(productName.toLowerCase()) ||
      productName.toLowerCase().includes(s.name.toLowerCase())
    );
    
    if (service) {
      const isOutsourcing = pricingModel === 'outsourcing';
      return {
        setup_cost: isOutsourcing 
          ? (service.setup_cost_outsourcing || 0) 
          : (service.setup_cost_conventional || 0),
        monthly_cost: isOutsourcing 
          ? (service.monthly_cost_outsourcing || 0) 
          : (service.monthly_cost_conventional || 0),
        application_type: service.application_type || 'both'
      };
    }
    return { setup_cost: 0, monthly_cost: 0, application_type: 'both' };
  };

  const openWizard = () => {
    setWizardOpen(true);
    setQuoteData({
      quote_type: '',
      client_id: '',
      pricing_model: '',
      cantidad_cajas: 1,
      cantidad_bancos: 1,
      setup_items: [],
      recurring_items: [],
      additional_items: [],
      descuento: 0,
      notes: ''
    });
    setSelectedBankId('');
    setSelectedMedioPagoId('');
    setAvailableMediosPago([]);
  };

  const addMedioPagoItem = () => {
    if (!selectedBankId || !selectedMedioPagoId) {
      toast.error('Seleccione un banco y un medio de pago');
      return;
    }
    
    const bank = banks.find(b => b.bank_id === selectedBankId);
    const medioPago = availableMediosPago.find(m => m.product_name === selectedMedioPagoId);
    
    if (!bank || !medioPago) return;

    // Verificar si ya existe esta combinación
    const exists = quoteData.additional_items.some(
      item => item.bank_id === selectedBankId && item.medio_pago_name === selectedMedioPagoId
    );
    
    if (exists) {
      toast.error('Este medio de pago ya fue agregado para este banco');
      return;
    }

    // Buscar precios en el catálogo
    const prices = findServicePrice(medioPago.product_name);

    const newItem = {
      id: `${selectedBankId}_${selectedMedioPagoId}`,
      bank_id: selectedBankId,
      bank_name: bank.name,
      medio_pago_name: medioPago.product_name,
      description: medioPago.description || '',
      cantidad_cajas: quoteData.cantidad_cajas,
      cantidad_bancos: quoteData.cantidad_bancos,
      tarifa_setup: prices.setup_cost,
      tarifa_recurrente: prices.monthly_cost,
      application_type: prices.application_type,
      isDefault: false
    };

    setQuoteData({
      ...quoteData,
      additional_items: [...quoteData.additional_items, newItem]
    });

    setSelectedBankId('');
    setSelectedMedioPagoId('');
    setAvailableMediosPago([]);
    
    toast.success('Medio de pago agregado');
  };

  const removeAdditionalItem = (index) => {
    setQuoteData({
      ...quoteData,
      additional_items: quoteData.additional_items.filter((_, i) => i !== index)
    });
  };

  // Actualizar campo en setup_items
  const updateSetupItem = (index, field, value) => {
    const updatedItems = [...quoteData.setup_items];
    updatedItems[index] = {
      ...updatedItems[index],
      [field]: parseFloat(value) || 0
    };
    setQuoteData({ ...quoteData, setup_items: updatedItems });
  };

  // Actualizar campo en recurring_items
  const updateRecurringItem = (index, field, value) => {
    const updatedItems = [...quoteData.recurring_items];
    updatedItems[index] = {
      ...updatedItems[index],
      [field]: parseFloat(value) || 0
    };
    setQuoteData({ ...quoteData, recurring_items: updatedItems });
  };

  // Actualizar campo en additional_items
  const updateAdditionalItem = (index, field, value) => {
    const updatedItems = [...quoteData.additional_items];
    updatedItems[index] = {
      ...updatedItems[index],
      [field]: parseFloat(value) || 0
    };
    setQuoteData({ ...quoteData, additional_items: updatedItems });
  };

  // Calcular total por fila: Tarifa * Cajas * Bancos
  const calcularTotal = (item) => {
    const cajas = item.cantidad_cajas || 1;
    const bancos = item.cantidad_bancos || 1;
    const tarifa = item.tarifa || item.tarifa_setup || 0;
    return tarifa * cajas * bancos;
  };

  const calcularTotalRecurrente = (item) => {
    const cajas = item.cantidad_cajas || 1;
    const bancos = item.cantidad_bancos || 1;
    const tarifa = item.tarifa || item.tarifa_recurrente || 0;
    return tarifa * cajas * bancos;
  };
    const bancos = item.cantidad_bancos || 1;
    return item.tarifa_setup * cajas * bancos;
  };

  const calcularTotalRecurrenteFila = (item) => {
    const cajas = item.cantidad_cajas || 1;
    const bancos = item.cantidad_bancos || 1;
    return item.tarifa_recurrente * cajas * bancos;
  };

  // Calcular subtotales
  const subtotalSetup = quoteData.medios_pago_items.reduce(
    (sum, item) => sum + calcularTotalFila(item), 0
  );
  const subtotalRecurrente = quoteData.medios_pago_items.reduce(
    (sum, item) => sum + calcularTotalRecurrenteFila(item), 0
  );

  // Calcular descuento
  const montoDescuentoSetup = subtotalSetup * (quoteData.descuento / 100);
  const montoDescuentoRecurrente = subtotalRecurrente * (quoteData.descuento / 100);

  // Totales netos
  const totalNetoSetup = subtotalSetup - montoDescuentoSetup;
  const totalNetoRecurrente = subtotalRecurrente - montoDescuentoRecurrente;
  const grandTotal = totalNetoSetup + totalNetoRecurrente;

  const handleSubmitQuote = async () => {
    if (quoteData.medios_pago_items.length === 0) {
      toast.error('Agregue al menos un medio de pago');
      return;
    }

    try {
      const serviceItems = quoteData.medios_pago_items.map((item) => ({
        item_type: 'service',
        item_id: `${item.bank_id}_${item.medio_pago_name}`,
        item_name: `${item.medio_pago_name} - ${item.bank_name}`,
        quantity: item.cantidad_cajas * item.cantidad_bancos,
        unit_price_usd: item.tarifa_setup + item.tarifa_recurrente,
        total_usd: calcularTotalFila(item) + calcularTotalRecurrenteFila(item)
      }));

      const payload = {
        client_id: quoteData.client_id,
        quote_type: quoteData.quote_type,
        services: serviceItems,
        hardware: [],
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
      const response = await api.get(`/quotes/${quoteId}/pdf`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `cotizacion_${quoteId}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      toast.success('PDF descargado');
    } catch (error) {
      toast.error('Error al descargar PDF');
    }
  };

  const getQuoteTypeName = (typeId) => {
    const type = QUOTE_TYPES.find(t => t.id === typeId);
    return type ? type.name : typeId;
  };

  const getPricingModelName = (modelId) => {
    const model = PRICING_MODELS.find(m => m.id === modelId);
    return model ? model.name : modelId;
  };

  const selectedClient = clients.find(c => c.client_id === quoteData.client_id);
  const isHeaderComplete = quoteData.quote_type && quoteData.client_id && quoteData.pricing_model && quoteData.cantidad_cajas >= 1;

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

  return (
    <div className="flex min-h-screen bg-white">
      <Sidebar />
      
      <main className="flex-1 p-8" data-testid="quotes-page">
        <div className="max-w-7xl mx-auto">
          <div className="flex justify-between items-center mb-8">
            <div>
              <h1 className="text-4xl font-bold text-slate-900 font-manrope mb-2">Cotizaciones</h1>
              <p className="text-slate-600">Genere cotizaciones profesionales para sus clientes</p>
            </div>
            
            <Button onClick={openWizard} data-testid="create-quote-button" className="bg-brand-green-600 hover:bg-brand-green-700 text-white">
              <Plus size={20} className="mr-2" />
              Nueva Cotización
            </Button>
          </div>

          {/* Tabla de cotizaciones existentes */}
          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase">Número</th>
                  <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase">Tipo</th>
                  <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase">Cliente</th>
                  <th className="px-6 py-4 text-right text-sm font-medium text-slate-700 uppercase">Total USD</th>
                  <th className="px-6 py-4 text-right text-sm font-medium text-slate-700 uppercase">Total Bs</th>
                  <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase">Fecha</th>
                  <th className="px-6 py-4 text-center text-sm font-medium text-slate-700 uppercase">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {quotes.map((quote) => {
                  const client = clients.find(c => c.client_id === quote.client_id);
                  return (
                    <tr key={quote.quote_id} className="hover:bg-slate-50">
                      <td className="px-6 py-4 text-sm font-mono font-medium text-slate-900">{quote.quote_number}</td>
                      <td className="px-6 py-4 text-sm">
                        <span className="px-2 py-1 text-xs font-medium bg-brand-blue-50 text-brand-blue-600 rounded">
                          {getQuoteTypeName(quote.quote_type)}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-900">{client?.fantasy_name || 'N/A'}</td>
                      <td className="px-6 py-4 text-sm font-mono text-right text-brand-green-600 font-semibold">${quote.total_usd.toFixed(2)}</td>
                      <td className="px-6 py-4 text-sm font-mono text-right text-slate-700">{quote.total_bs.toFixed(2)} Bs</td>
                      <td className="px-6 py-4 text-sm text-slate-600">{new Date(quote.created_at).toLocaleDateString('es-VE')}</td>
                      <td className="px-6 py-4">
                        <div className="flex items-center justify-center">
                          <Button size="sm" variant="outline" onClick={() => downloadPDF(quote.quote_id)} className="text-brand-blue-600">
                            <Download size={16} className="mr-1" />PDF
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
              </div>
            )}
          </div>

          {/* Dialog de Nueva Cotización */}
          <Dialog open={wizardOpen} onOpenChange={setWizardOpen}>
            <DialogContent className="max-w-6xl max-h-[95vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle className="font-manrope text-2xl">Nueva Cotización</DialogTitle>
              </DialogHeader>

              {/* SECCIÓN 1: Parámetros Iniciales */}
              <div className="bg-slate-50 rounded-lg p-5 border">
                <h3 className="font-semibold text-lg text-slate-800 mb-4 flex items-center gap-2">
                  <span className="w-7 h-7 rounded-full bg-brand-blue-600 text-white flex items-center justify-center text-sm">1</span>
                  Parámetros de la Cotización
                </h3>
                
                <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 block">
                      Tipo de Cotización <span className="text-red-500">*</span>
                    </Label>
                    <Select
                      value={quoteData.quote_type}
                      onValueChange={(value) => {
                        setQuoteData({ ...quoteData, quote_type: value, medios_pago_items: [] });
                        setSelectedBankId('');
                        setSelectedMedioPagoId('');
                        setAvailableMediosPago([]);
                      }}
                    >
                      <SelectTrigger data-testid="select-quote-type">
                        <SelectValue placeholder="Seleccione tipo..." />
                      </SelectTrigger>
                      <SelectContent>
                        {QUOTE_TYPES.map((type) => (
                          <SelectItem key={type.id} value={type.id}>{type.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 block">
                      Cliente <span className="text-red-500">*</span>
                    </Label>
                    <Select value={quoteData.client_id} onValueChange={(value) => setQuoteData({ ...quoteData, client_id: value })}>
                      <SelectTrigger data-testid="select-client">
                        <SelectValue placeholder="Buscar cliente..." />
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

                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 block">
                      Modelo de Precios <span className="text-red-500">*</span>
                    </Label>
                    <Select 
                      value={quoteData.pricing_model} 
                      onValueChange={(value) => {
                        // Al seleccionar modelo, inicializar con conceptos base
                        const defaultItems = initializeDefaultConcepts(value, quoteData.cantidad_cajas, quoteData.cantidad_bancos);
                        setQuoteData({ ...quoteData, pricing_model: value, medios_pago_items: defaultItems });
                      }}
                    >
                      <SelectTrigger data-testid="select-pricing-model">
                        <SelectValue placeholder="Seleccione modelo..." />
                      </SelectTrigger>
                      <SelectContent>
                        {PRICING_MODELS.map((model) => (
                          <SelectItem key={model.id} value={model.id}>{model.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 block">
                      Cajas (VTID) <span className="text-red-500">*</span>
                    </Label>
                    <Input
                      type="number"
                      min="1"
                      value={quoteData.cantidad_cajas}
                      onChange={(e) => setQuoteData({ ...quoteData, cantidad_cajas: parseInt(e.target.value) || 1 })}
                      data-testid="cantidad-cajas-input"
                      className="h-10"
                    />
                  </div>

                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 block">
                      Bancos/Entes
                    </Label>
                    <Input
                      type="number"
                      min="1"
                      value={quoteData.cantidad_bancos}
                      onChange={(e) => setQuoteData({ ...quoteData, cantidad_bancos: parseInt(e.target.value) || 1 })}
                      data-testid="cantidad-bancos-input"
                      className="h-10"
                    />
                  </div>
                </div>

                {isHeaderComplete && (
                  <div className="mt-4 p-3 bg-brand-green-50 border border-brand-green-200 rounded-lg flex items-center gap-2">
                    <CheckCircle2 size={18} className="text-brand-green-600" />
                    <span className="text-sm text-brand-green-700 font-medium">
                      {getQuoteTypeName(quoteData.quote_type)} • {selectedClient?.fantasy_name} • {getPricingModelName(quoteData.pricing_model)} • {quoteData.cantidad_cajas} cajas • {quoteData.cantidad_bancos} bancos
                    </span>
                  </div>
                )}
              </div>

              {/* SECCIÓN 2: Selección de Medios de Pago */}
              {isHeaderComplete && (
                <div className="bg-white rounded-lg p-5 border mt-4">
                  <h3 className="font-semibold text-lg text-slate-800 mb-4 flex items-center gap-2">
                    <span className="w-7 h-7 rounded-full bg-brand-blue-600 text-white flex items-center justify-center text-sm">2</span>
                    Selección de Medios de Pago
                  </h3>
                  
                  <div className="bg-slate-50 rounded-lg p-4 border mb-4">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
                      <div>
                        <Label className="text-sm font-medium text-slate-700 mb-2 flex items-center gap-2">
                          <Building2 size={16} className="text-brand-blue-600" />
                          Banco
                        </Label>
                        <Select value={selectedBankId} onValueChange={handleBankSelect}>
                          <SelectTrigger data-testid="select-bank">
                            <SelectValue placeholder="Seleccione banco..." />
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
                        <Label className="text-sm font-medium text-slate-700 mb-2 flex items-center gap-2">
                          <CreditCard size={16} className="text-brand-green-600" />
                          Medio de Pago
                        </Label>
                        <Select 
                          value={selectedMedioPagoId} 
                          onValueChange={setSelectedMedioPagoId}
                          disabled={!selectedBankId || availableMediosPago.length === 0}
                        >
                          <SelectTrigger data-testid="select-medio-pago">
                            <SelectValue placeholder={!selectedBankId ? "Primero seleccione banco" : "Seleccione medio..."} />
                          </SelectTrigger>
                          <SelectContent>
                            {availableMediosPago.map((mp) => (
                              <SelectItem key={mp.product_name} value={mp.product_name}>
                                {mp.product_name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      <Button
                        onClick={addMedioPagoItem}
                        disabled={!selectedBankId || !selectedMedioPagoId}
                        className="bg-brand-blue-600 hover:bg-brand-blue-700 text-white h-10"
                        data-testid="add-medio-pago-btn"
                      >
                        <Plus size={16} className="mr-2" />
                        Agregar
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {/* SECCIÓN 3: Matriz de Resumen - Set Up */}
              {isHeaderComplete && quoteData.medios_pago_items.length > 0 && (
                <div className="bg-white rounded-lg border mt-4 overflow-hidden">
                  {/* Encabezado Set Up */}
                  <div className="bg-gradient-to-r from-cyan-500 to-cyan-600 text-white text-center py-2 font-semibold">
                    Set Up - Puesta en Marcha
                  </div>
                  
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse text-sm">
                      <thead>
                        <tr className="bg-slate-100">
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-16">N°</th>
                          <th className="px-3 py-2 text-left font-semibold text-slate-700 border border-slate-300">Concepto</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-24">(VTID)<br/>Cajas</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-24">Bancos o<br/>Entes</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-28">Tarifa Set-up<br/>(USD/VTID/Banco)</th>
                          <th className="px-3 py-2 text-center font-semibold text-brand-blue-600 border border-slate-300 w-32 bg-blue-50">Total Set-Up USD</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-16">Acc.</th>
                        </tr>
                      </thead>
                      <tbody>
                        {quoteData.medios_pago_items.map((item, index) => (
                          <tr key={index} className={`${index % 2 === 0 ? 'bg-white' : 'bg-slate-50'} ${item.isDefault ? 'border-l-4 border-l-cyan-500' : ''}`}>
                            <td className="px-3 py-2 text-center font-medium border border-slate-300">{index + 1}</td>
                            <td className="px-3 py-2 border border-slate-300">
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-slate-900">{item.medio_pago_name}</span>
                                {item.isDefault && (
                                  <span className="px-1.5 py-0.5 text-xs font-medium bg-cyan-100 text-cyan-700 rounded">Base</span>
                                )}
                              </div>
                              {item.bank_name !== '-' && <div className="text-xs text-slate-500">{item.bank_name}</div>}
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Input
                                type="number"
                                min="1"
                                value={item.cantidad_cajas}
                                onChange={(e) => updateItemField(index, 'cantidad_cajas', e.target.value)}
                                className="w-16 h-7 text-center text-sm mx-auto"
                              />
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Input
                                type="number"
                                min="1"
                                value={item.cantidad_bancos}
                                onChange={(e) => updateItemField(index, 'cantidad_bancos', e.target.value)}
                                className="w-16 h-7 text-center text-sm mx-auto"
                              />
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Input
                                type="number"
                                min="0"
                                step="0.01"
                                value={item.tarifa_setup}
                                onChange={(e) => updateItemField(index, 'tarifa_setup', e.target.value)}
                                className="w-20 h-7 text-right text-sm mx-auto font-mono"
                              />
                            </td>
                            <td className="px-3 py-2 text-right border border-slate-300 bg-blue-50 font-mono font-semibold text-brand-blue-600">
                              ${calcularTotalFila(item).toFixed(2)}
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              {!item.isDefault && (
                                <Button size="sm" variant="outline" onClick={() => removeMedioPagoItem(index)} className="text-red-600 h-7 w-7 p-0">
                                  <Trash2 size={14} />
                                </Button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr className="bg-slate-100">
                          <td colSpan={5} className="px-3 py-2 text-right font-semibold border border-slate-300">Subtotal:</td>
                          <td className="px-3 py-2 text-right font-mono font-bold text-brand-blue-600 border border-slate-300 bg-blue-50">${subtotalSetup.toFixed(2)}</td>
                          <td className="border border-slate-300"></td>
                        </tr>
                        <tr className="bg-amber-50">
                          <td colSpan={4} className="px-3 py-2 text-right font-semibold border border-slate-300">Descuento:</td>
                          <td className="px-3 py-2 text-center border border-slate-300">
                            <div className="flex items-center justify-center gap-1">
                              <Input
                                type="number"
                                min="0"
                                max="100"
                                step="0.01"
                                value={quoteData.descuento}
                                onChange={(e) => setQuoteData({ ...quoteData, descuento: parseFloat(e.target.value) || 0 })}
                                className="w-16 h-7 text-right text-sm font-mono"
                              />
                              <span className="text-sm">%</span>
                            </div>
                          </td>
                          <td className="px-3 py-2 text-right font-mono font-bold text-amber-600 border border-slate-300">-${montoDescuentoSetup.toFixed(2)}</td>
                          <td className="border border-slate-300"></td>
                        </tr>
                        <tr className="bg-green-100">
                          <td colSpan={5} className="px-3 py-2 text-right font-bold border border-slate-300">Total Costos de Arranque (VTID) Neto:</td>
                          <td className="px-3 py-2 text-right font-mono font-bold text-brand-green-700 border border-slate-300 text-lg">${totalNetoSetup.toFixed(2)}</td>
                          <td className="border border-slate-300"></td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>

                  {/* Encabezado Costos Recurrentes */}
                  <div className="bg-gradient-to-r from-green-500 to-green-600 text-white text-center py-2 font-semibold mt-4">
                    Costos Recurrentes - Mensuales
                  </div>
                  
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse text-sm">
                      <thead>
                        <tr className="bg-slate-100">
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-16">N°</th>
                          <th className="px-3 py-2 text-left font-semibold text-slate-700 border border-slate-300">Concepto</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-24">(VTID)<br/>Cajas</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-24">Bancos o<br/>Entes</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-28">Tarifa Mensual<br/>(USD/VTID/Banco)</th>
                          <th className="px-3 py-2 text-center font-semibold text-brand-green-600 border border-slate-300 w-32 bg-green-50">Total Mensual USD</th>
                        </tr>
                      </thead>
                      <tbody>
                        {quoteData.medios_pago_items.map((item, index) => (
                          <tr key={index} className={`${index % 2 === 0 ? 'bg-white' : 'bg-slate-50'} ${item.isDefault ? 'border-l-4 border-l-green-500' : ''}`}>
                            <td className="px-3 py-2 text-center font-medium border border-slate-300">{index + 1}</td>
                            <td className="px-3 py-2 border border-slate-300">
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-slate-900">{item.medio_pago_name}</span>
                                {item.isDefault && (
                                  <span className="px-1.5 py-0.5 text-xs font-medium bg-green-100 text-green-700 rounded">Base</span>
                                )}
                              </div>
                              {item.bank_name !== '-' && <div className="text-xs text-slate-500">{item.bank_name}</div>}
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300 font-mono">{item.cantidad_cajas}</td>
                            <td className="px-3 py-2 text-center border border-slate-300 font-mono">{item.cantidad_bancos}</td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Input
                                type="number"
                                min="0"
                                step="0.01"
                                value={item.tarifa_recurrente}
                                onChange={(e) => updateItemField(index, 'tarifa_recurrente', e.target.value)}
                                className="w-20 h-7 text-right text-sm mx-auto font-mono"
                              />
                            </td>
                            <td className="px-3 py-2 text-right border border-slate-300 bg-green-50 font-mono font-semibold text-brand-green-600">
                              ${calcularTotalRecurrenteFila(item).toFixed(2)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr className="bg-slate-100">
                          <td colSpan={5} className="px-3 py-2 text-right font-semibold border border-slate-300">Subtotal Mensual:</td>
                          <td className="px-3 py-2 text-right font-mono font-bold text-brand-green-600 border border-slate-300 bg-green-50">${subtotalRecurrente.toFixed(2)}</td>
                        </tr>
                        <tr className="bg-amber-50">
                          <td colSpan={5} className="px-3 py-2 text-right font-semibold border border-slate-300">Descuento ({quoteData.descuento}%):</td>
                          <td className="px-3 py-2 text-right font-mono font-bold text-amber-600 border border-slate-300">-${montoDescuentoRecurrente.toFixed(2)}</td>
                        </tr>
                        <tr className="bg-green-100">
                          <td colSpan={5} className="px-3 py-2 text-right font-bold border border-slate-300">Total Costos Recurrentes Neto:</td>
                          <td className="px-3 py-2 text-right font-mono font-bold text-brand-green-700 border border-slate-300 text-lg">${totalNetoRecurrente.toFixed(2)}</td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>

                  {/* Resumen General */}
                  <div className="bg-slate-900 text-white p-4 mt-4 rounded-b-lg">
                    <div className="flex justify-between items-center">
                      <span className="text-lg font-semibold">TOTAL GENERAL (Setup + Recurrente)</span>
                      <span className="text-2xl font-bold font-mono">${grandTotal.toFixed(2)} USD</span>
                    </div>
                  </div>

                  {/* Notas y Botón Finalizar */}
                  <div className="p-4">
                    <Label htmlFor="notes" className="text-sm font-medium text-slate-700">Notas adicionales</Label>
                    <Textarea
                      id="notes"
                      value={quoteData.notes}
                      onChange={(e) => setQuoteData({ ...quoteData, notes: e.target.value })}
                      placeholder="Observaciones o condiciones especiales..."
                      rows={2}
                      className="mt-2"
                    />

                    <div className="mt-4 flex justify-end">
                      <Button
                        onClick={handleSubmitQuote}
                        className="bg-brand-green-600 hover:bg-brand-green-700 text-white px-8 py-3 text-lg"
                        data-testid="submit-quote-button"
                      >
                        <CheckCircle2 size={20} className="mr-2" />
                        Finalizar Cotización
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {/* Mensaje cuando no hay items */}
              {isHeaderComplete && quoteData.medios_pago_items.length === 0 && (
                <div className="text-center py-8 text-slate-500 bg-slate-50 rounded-lg mt-4 border-2 border-dashed">
                  <CreditCard size={40} className="mx-auto mb-3 text-slate-300" />
                  <p className="font-medium">No hay medios de pago agregados</p>
                  <p className="text-sm mt-1">Seleccione un banco y medio de pago para comenzar</p>
                </div>
              )}
            </DialogContent>
          </Dialog>
        </div>
      </main>
    </div>
  );
};

export default Quotes;
