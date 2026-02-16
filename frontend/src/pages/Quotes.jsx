import { useState, useEffect } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Plus, FileText, Download, ChevronRight, ChevronLeft } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const WIZARD_STEPS = ['Cliente', 'Servicios', 'Hardware', 'Revisión'];

export const Quotes = () => {
  const [quotes, setQuotes] = useState([]);
  const [clients, setClients] = useState([]);
  const [services, setServices] = useState([]);
  const [hardware, setHardware] = useState([]);
  const [loading, setLoading] = useState(true);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [quoteData, setQuoteData] = useState({
    client_id: '',
    services: [],
    hardware: [],
    notes: ''
  });
  const [selectedItems, setSelectedItems] = useState({
    services: {},
    hardware: {}
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [quotesRes, clientsRes, servicesRes, hardwareRes] = await Promise.all([
        api.get('/quotes'),
        api.get('/clients'),
        api.get('/services'),
        api.get('/hardware')
      ]);
      setQuotes(quotesRes.data);
      setClients(clientsRes.data);
      setServices(servicesRes.data);
      setHardware(hardwareRes.data);
    } catch (error) {
      console.error('Error fetching data:', error);
      toast.error('Error al cargar datos');
    } finally {
      setLoading(false);
    }
  };

  const openWizard = () => {
    setWizardOpen(true);
    setCurrentStep(0);
    setQuoteData({
      client_id: '',
      services: [],
      hardware: [],
      notes: ''
    });
    setSelectedItems({ services: {}, hardware: {} });
  };

  const nextStep = () => {
    if (currentStep === 0 && !quoteData.client_id) {
      toast.error('Seleccione un cliente');
      return;
    }
    if (currentStep < WIZARD_STEPS.length - 1) {
      setCurrentStep(currentStep + 1);
    }
  };

  const prevStep = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const toggleService = (service) => {
    const key = service.service_id;
    if (selectedItems.services[key]) {
      const { [key]: removed, ...rest } = selectedItems.services;
      setSelectedItems({ ...selectedItems, services: rest });
    } else {
      setSelectedItems({
        ...selectedItems,
        services: {
          ...selectedItems.services,
          [key]: { ...service, quantity: 1 }
        }
      });
    }
  };

  const toggleHardware = (hw) => {
    const key = hw.hardware_id;
    if (selectedItems.hardware[key]) {
      const { [key]: removed, ...rest } = selectedItems.hardware;
      setSelectedItems({ ...selectedItems, hardware: rest });
    } else {
      setSelectedItems({
        ...selectedItems,
        hardware: {
          ...selectedItems.hardware,
          [key]: { ...hw, quantity: 1 }
        }
      });
    }
  };

  const updateQuantity = (type, id, quantity) => {
    setSelectedItems({
      ...selectedItems,
      [type]: {
        ...selectedItems[type],
        [id]: { ...selectedItems[type][id], quantity: parseInt(quantity) || 1 }
      }
    });
  };

  const handleSubmitQuote = async () => {
    try {
      const serviceItems = Object.values(selectedItems.services).map((s) => ({
        item_type: 'service',
        item_id: s.service_id,
        item_name: s.name,
        quantity: s.quantity,
        unit_price_usd: (s.setup_cost_conventional || 0) + (s.monthly_cost_conventional || 0),
        total_usd: ((s.setup_cost_conventional || 0) + (s.monthly_cost_conventional || 0)) * s.quantity
      }));

      const hardwareItems = Object.values(selectedItems.hardware).map((h) => ({
        item_type: 'hardware',
        item_id: h.hardware_id,
        item_name: h.name,
        quantity: h.quantity,
        unit_price_usd: h.price_usd,
        total_usd: h.price_usd * h.quantity
      }));

      const payload = {
        client_id: quoteData.client_id,
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

  if (loading) {
    return (
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center bg-white">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-slate-900 mx-auto"></div>
            <p className="mt-4 text-slate-900">Cargando cotizaciones...</p>
          </div>
        </div>
      </div>
    );
  }

  const selectedClient = clients.find(c => c.client_id === quoteData.client_id);
  const totalServicesUSD = Object.values(selectedItems.services).reduce(
    (sum, s) => sum + ((s.setup_cost_conventional || 0) + (s.monthly_cost_conventional || 0)) * s.quantity, 0
  );
  const totalHardwareUSD = Object.values(selectedItems.hardware).reduce(
    (sum, h) => sum + h.price_usd * h.quantity, 0
  );
  const grandTotal = totalServicesUSD + totalHardwareUSD;

  return (
    <div className="flex min-h-screen bg-slate-50">
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
              className="bg-sky-600 hover:bg-sky-700 text-white"
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
                      <td className="px-6 py-4 text-sm text-slate-900">
                        {client?.fantasy_name || 'N/A'}
                      </td>
                      <td className="px-6 py-4 text-sm font-mono text-right text-emerald-600 font-semibold">
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
                            className="text-sky-600 hover:text-sky-700"
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
                <div className="flex items-center justify-between">
                  {WIZARD_STEPS.map((step, index) => (
                    <div key={step} className="flex items-center">
                      <div className={`flex items-center justify-center w-10 h-10 rounded-full border-2 font-semibold ${
                        index === currentStep
                          ? 'border-sky-600 bg-sky-600 text-white'
                          : index < currentStep
                          ? 'border-emerald-600 bg-emerald-600 text-white'
                          : 'border-slate-300 text-slate-400'
                      }`}>
                        {index + 1}
                      </div>
                      <span className={`ml-2 font-medium ${
                        index === currentStep ? 'text-sky-600' : index < currentStep ? 'text-emerald-600' : 'text-slate-400'
                      }`}>
                        {step}
                      </span>
                      {index < WIZARD_STEPS.length - 1 && (
                        <ChevronRight className="mx-4 text-slate-300" size={20} />
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div className="min-h-[400px]">
                {currentStep === 0 && (
                  <div>
                    <Label htmlFor="client">Seleccione el Cliente</Label>
                    <Select
                      value={quoteData.client_id}
                      onValueChange={(value) => setQuoteData({ ...quoteData, client_id: value })}
                    >
                      <SelectTrigger data-testid="select-client">
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

                {currentStep === 1 && (
                  <div>
                    <h3 className="text-lg font-semibold mb-4">Seleccione Servicios</h3>
                    <div className="space-y-3 max-h-[500px] overflow-y-auto">
                      {services.map((service) => {
                        const isSelected = !!selectedItems.services[service.service_id];
                        return (
                          <div
                            key={service.service_id}
                            className={`p-4 border rounded-lg cursor-pointer transition-all ${
                              isSelected ? 'border-sky-600 bg-sky-50' : 'border-slate-200 hover:border-sky-300'
                            }`}
                            onClick={() => toggleService(service)}
                          >
                            <div className="flex justify-between items-start">
                              <div className="flex-1">
                                <p className="font-medium text-slate-900">{service.name}</p>
                                <p className="text-sm text-slate-500">{service.category}</p>
                              </div>
                              <div className="text-right">
                                <p className="font-semibold text-slate-900">
                                  ${((service.setup_cost_conventional || 0) + (service.monthly_cost_conventional || 0)).toFixed(2)}
                                </p>
                                <p className="text-xs text-slate-500">
                                  Setup: ${service.setup_cost_conventional || 0} + Mensual: ${service.monthly_cost_conventional || 0}
                                </p>
                              </div>
                            </div>
                            {isSelected && (
                              <div className="mt-3 pt-3 border-t">
                                <Label htmlFor={`qty-${service.service_id}`} className="text-xs">Cantidad</Label>
                                <Input
                                  id={`qty-${service.service_id}`}
                                  type="number"
                                  min="1"
                                  value={selectedItems.services[service.service_id].quantity}
                                  onChange={(e) => updateQuantity('services', service.service_id, e.target.value)}
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

                {currentStep === 2 && (
                  <div>
                    <h3 className="text-lg font-semibold mb-4">Seleccione Hardware</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-h-[500px] overflow-y-auto">
                      {hardware.map((hw) => {
                        const isSelected = !!selectedItems.hardware[hw.hardware_id];
                        return (
                          <div
                            key={hw.hardware_id}
                            className={`p-4 border rounded-lg cursor-pointer transition-all ${
                              isSelected ? 'border-sky-600 bg-sky-50' : 'border-slate-200 hover:border-sky-300'
                            }`}
                            onClick={() => toggleHardware(hw)}
                          >
                            <div className="flex justify-between items-start mb-2">
                              <p className="font-medium text-slate-900">{hw.name}</p>
                              <span className="text-xs px-2 py-1 bg-slate-100 rounded">{hw.type}</span>
                            </div>
                            <p className="text-sm font-semibold text-emerald-600">${hw.price_usd.toFixed(2)}</p>
                            {isSelected && (
                              <div className="mt-3 pt-3 border-t">
                                <Label htmlFor={`qty-hw-${hw.hardware_id}`} className="text-xs">Cantidad</Label>
                                <Input
                                  id={`qty-hw-${hw.hardware_id}`}
                                  type="number"
                                  min="1"
                                  value={selectedItems.hardware[hw.hardware_id].quantity}
                                  onChange={(e) => updateQuantity('hardware', hw.hardware_id, e.target.value)}
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

                {currentStep === 3 && (
                  <div>
                    <h3 className="text-lg font-semibold mb-4">Revisión de Cotización</h3>
                    
                    {selectedClient && (
                      <div className="mb-6 p-4 bg-slate-50 rounded-lg border">
                        <p className="text-sm text-slate-600 mb-1">Cliente:</p>
                        <p className="font-semibold text-slate-900">{selectedClient.fantasy_name}</p>
                        <p className="text-sm text-slate-600">{selectedClient.rif}</p>
                      </div>
                    )}

                    {Object.keys(selectedItems.services).length > 0 && (
                      <div className="mb-4">
                        <h4 className="font-semibold mb-2">Servicios</h4>
                        <div className="space-y-2">
                          {Object.values(selectedItems.services).map((s) => (
                            <div key={s.service_id} className="flex justify-between text-sm p-2 bg-slate-50 rounded">
                              <span>{s.name} x {s.quantity}</span>
                              <span className="font-semibold">${(((s.setup_cost_conventional || 0) + (s.monthly_cost_conventional || 0)) * s.quantity).toFixed(2)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {Object.keys(selectedItems.hardware).length > 0 && (
                      <div className="mb-4">
                        <h4 className="font-semibold mb-2">Hardware</h4>
                        <div className="space-y-2">
                          {Object.values(selectedItems.hardware).map((h) => (
                            <div key={h.hardware_id} className="flex justify-between text-sm p-2 bg-slate-50 rounded">
                              <span>{h.name} x {h.quantity}</span>
                              <span className="font-semibold">${(h.price_usd * h.quantity).toFixed(2)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="border-t pt-4 mb-4">
                      <div className="flex justify-between text-lg font-bold">
                        <span>Total (USD)</span>
                        <span className="text-emerald-600">${grandTotal.toFixed(2)}</span>
                      </div>
                    </div>

                    <div>
                      <Label htmlFor="notes">Notas (Opcional)</Label>
                      <Textarea
                        id="notes"
                        value={quoteData.notes}
                        onChange={(e) => setQuoteData({ ...quoteData, notes: e.target.value })}
                        rows={3}
                        placeholder="Agregue notas adicionales para esta cotización..."
                      />
                    </div>
                  </div>
                )}
              </div>

              <div className="flex justify-between pt-6 border-t">
                <Button
                  variant="outline"
                  onClick={prevStep}
                  disabled={currentStep === 0}
                >
                  <ChevronLeft size={16} className="mr-1" />
                  Anterior
                </Button>
                
                {currentStep < WIZARD_STEPS.length - 1 ? (
                  <Button
                    onClick={nextStep}
                    className="bg-sky-600 hover:bg-sky-700 text-white"
                  >
                    Siguiente
                    <ChevronRight size={16} className="ml-1" />
                  </Button>
                ) : (
                  <Button
                    onClick={handleSubmitQuote}
                    data-testid="submit-quote-button"
                    className="bg-emerald-600 hover:bg-emerald-700 text-white"
                  >
                    Generar Cotización
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
