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

export const Quotes = () => {
  const [quotes, setQuotes] = useState([]);
  const [clients, setClients] = useState([]);
  const [banks, setBanks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [wizardOpen, setWizardOpen] = useState(false);
  
  // Estado del formulario de cotización
  const [quoteData, setQuoteData] = useState({
    quote_type: '',
    client_id: '',
    cantidad_cajas: 1,
    medios_pago_items: [],
    notes: ''
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
      const [quotesRes, clientsRes, banksRes] = await Promise.all([
        api.get('/quotes'),
        api.get('/clients'),
        api.get('/banks')
      ]);
      setQuotes(quotesRes.data);
      setClients(clientsRes.data);
      setBanks(banksRes.data);
    } catch (error) {
      console.error('Error fetching data:', error);
      toast.error('Error al cargar datos');
    } finally {
      setLoading(false);
    }
  };

  // Obtener los medios de pago asociados al banco seleccionado
  const handleBankSelect = (bankId) => {
    setSelectedBankId(bankId);
    setSelectedMedioPagoId('');
    
    const bank = banks.find(b => b.bank_id === bankId);
    if (bank && bank.products) {
      // Filtrar productos del banco según el tipo de cotización
      const compatibilityField = getCompatibilityField(quoteData.quote_type);
      const filteredProducts = bank.products.filter(p => p[compatibilityField] !== false);
      setAvailableMediosPago(filteredProducts);
    } else {
      setAvailableMediosPago([]);
    }
  };

  // Mapear tipo de cotización a campo de compatibilidad
  const getCompatibilityField = (quoteType) => {
    switch (quoteType) {
      case 'VPOS': return 'vpos_available';
      case 'GATEWAY': return 'gateway_available';
      case 'MPOS': return 'mpos_available';
      case 'LINK': return 'link_available';
      default: return 'vpos_available';
    }
  };

  const openWizard = () => {
    setWizardOpen(true);
    setQuoteData({
      quote_type: '',
      client_id: '',
      cantidad_cajas: 1,
      medios_pago_items: [],
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
    const exists = quoteData.medios_pago_items.some(
      item => item.bank_id === selectedBankId && item.medio_pago_name === selectedMedioPagoId
    );
    
    if (exists) {
      toast.error('Este medio de pago ya fue agregado para este banco');
      return;
    }

    const newItem = {
      bank_id: selectedBankId,
      bank_name: bank.name,
      medio_pago_name: medioPago.product_name,
      description: medioPago.description || '',
      cantidad: quoteData.cantidad_cajas,
      // Costos por defecto (se pueden ajustar según la lógica de negocio)
      setup_cost: 0,
      monthly_cost: 0
    };

    setQuoteData({
      ...quoteData,
      medios_pago_items: [...quoteData.medios_pago_items, newItem]
    });

    // Limpiar selección
    setSelectedBankId('');
    setSelectedMedioPagoId('');
    setAvailableMediosPago([]);
    
    toast.success('Medio de pago agregado');
  };

  const removeMedioPagoItem = (index) => {
    setQuoteData({
      ...quoteData,
      medios_pago_items: quoteData.medios_pago_items.filter((_, i) => i !== index)
    });
  };

  const updateItemCost = (index, field, value) => {
    const updatedItems = [...quoteData.medios_pago_items];
    updatedItems[index] = {
      ...updatedItems[index],
      [field]: parseFloat(value) || 0
    };
    setQuoteData({ ...quoteData, medios_pago_items: updatedItems });
  };

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
        quantity: item.cantidad,
        unit_price_usd: item.setup_cost + item.monthly_cost,
        total_usd: (item.setup_cost + item.monthly_cost) * item.cantidad
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

  const selectedClient = clients.find(c => c.client_id === quoteData.client_id);
  
  // Calcular totales
  const totalSetup = quoteData.medios_pago_items.reduce(
    (sum, item) => sum + (item.setup_cost * item.cantidad), 0
  );
  const totalRecurrente = quoteData.medios_pago_items.reduce(
    (sum, item) => sum + (item.monthly_cost * item.cantidad), 0
  );
  const grandTotal = totalSetup + totalRecurrente;

  // Validar si el formulario de cabecera está completo
  const isHeaderComplete = quoteData.quote_type && quoteData.client_id && quoteData.cantidad_cajas >= 1;

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

          {/* Tabla de cotizaciones existentes */}
          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase tracking-wider">Número</th>
                  <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase tracking-wider">Tipo</th>
                  <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase tracking-wider">Cliente</th>
                  <th className="px-6 py-4 text-right text-sm font-medium text-slate-700 uppercase tracking-wider">Total USD</th>
                  <th className="px-6 py-4 text-right text-sm font-medium text-slate-700 uppercase tracking-wider">Total Bs</th>
                  <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase tracking-wider">Fecha</th>
                  <th className="px-6 py-4 text-center text-sm font-medium text-slate-700 uppercase tracking-wider">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {quotes.map((quote) => {
                  const client = clients.find(c => c.client_id === quote.client_id);
                  return (
                    <tr key={quote.quote_id} className="hover:bg-slate-50 transition-colors">
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
              </div>
            )}
          </div>

          {/* Dialog de Nueva Cotización */}
          <Dialog open={wizardOpen} onOpenChange={setWizardOpen}>
            <DialogContent className="max-w-5xl max-h-[95vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle className="font-manrope text-2xl">Nueva Cotización</DialogTitle>
              </DialogHeader>

              {/* SECCIÓN 1: Parámetros Iniciales */}
              <div className="bg-slate-50 rounded-lg p-5 border">
                <h3 className="font-semibold text-lg text-slate-800 mb-4 flex items-center gap-2">
                  <span className="w-7 h-7 rounded-full bg-brand-blue-600 text-white flex items-center justify-center text-sm">1</span>
                  Parámetros de la Cotización
                </h3>
                
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {/* Tipo de Cotización */}
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
                          <SelectItem key={type.id} value={type.id}>
                            {type.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Cliente */}
                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 block">
                      Cliente <span className="text-red-500">*</span>
                    </Label>
                    <Select
                      value={quoteData.client_id}
                      onValueChange={(value) => setQuoteData({ ...quoteData, client_id: value })}
                    >
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

                  {/* Cantidad de Cajas */}
                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 block">
                      Cantidad de Cajas <span className="text-red-500">*</span>
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
                </div>

                {/* Indicador de estado */}
                {isHeaderComplete && (
                  <div className="mt-4 p-3 bg-brand-green-50 border border-brand-green-200 rounded-lg flex items-center gap-2">
                    <CheckCircle2 size={18} className="text-brand-green-600" />
                    <span className="text-sm text-brand-green-700 font-medium">
                      {getQuoteTypeName(quoteData.quote_type)} • {selectedClient?.fantasy_name} • {quoteData.cantidad_cajas} cajas
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
                    <p className="text-sm text-slate-600 mb-3">
                      Paso A: Seleccione primero el <strong>Banco</strong>, luego el <strong>Medio de Pago</strong> disponible.
                    </p>
                    
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
                      {/* Selector de Banco */}
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
                                {bank.name} ({bank.country})
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      {/* Selector de Medio de Pago (filtrado por banco) */}
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
                            <SelectValue placeholder={
                              !selectedBankId 
                                ? "Primero seleccione un banco" 
                                : availableMediosPago.length === 0 
                                  ? "No hay medios disponibles" 
                                  : "Seleccione medio..."
                            } />
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

                      {/* Botón Agregar */}
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

                    {selectedBankId && availableMediosPago.length === 0 && (
                      <p className="text-sm text-amber-600 mt-3">
                        Este banco no tiene medios de pago configurados para {getQuoteTypeName(quoteData.quote_type)}.
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* SECCIÓN 3: Matriz de Resumen */}
              {isHeaderComplete && quoteData.medios_pago_items.length > 0 && (
                <div className="bg-white rounded-lg p-5 border mt-4">
                  <h3 className="font-semibold text-lg text-slate-800 mb-4 flex items-center gap-2">
                    <span className="w-7 h-7 rounded-full bg-brand-green-600 text-white flex items-center justify-center text-sm">3</span>
                    Matriz de Resumen
                  </h3>
                  
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse">
                      <thead>
                        <tr className="bg-slate-100">
                          <th className="px-4 py-3 text-left text-sm font-semibold text-slate-700 border">Banco</th>
                          <th className="px-4 py-3 text-left text-sm font-semibold text-slate-700 border">Medio de Pago</th>
                          <th className="px-4 py-3 text-center text-sm font-semibold text-slate-700 border">Cant. Cajas</th>
                          <th className="px-4 py-3 text-right text-sm font-semibold text-brand-blue-600 border">Costo Setup ($)</th>
                          <th className="px-4 py-3 text-right text-sm font-semibold text-brand-green-600 border">Costo Recurrente ($)</th>
                          <th className="px-4 py-3 text-center text-sm font-semibold text-slate-700 border">Acciones</th>
                        </tr>
                      </thead>
                      <tbody>
                        {quoteData.medios_pago_items.map((item, index) => (
                          <tr key={index} className="hover:bg-slate-50">
                            <td className="px-4 py-3 text-sm text-slate-900 border font-medium">{item.bank_name}</td>
                            <td className="px-4 py-3 text-sm text-slate-700 border">
                              <div>
                                <p className="font-medium">{item.medio_pago_name}</p>
                                {item.description && (
                                  <p className="text-xs text-slate-500">{item.description}</p>
                                )}
                              </div>
                            </td>
                            <td className="px-4 py-3 text-sm text-center border">
                              <span className="font-mono font-semibold">{item.cantidad}</span>
                            </td>
                            <td className="px-4 py-3 border">
                              <Input
                                type="number"
                                min="0"
                                step="0.01"
                                value={item.setup_cost}
                                onChange={(e) => updateItemCost(index, 'setup_cost', e.target.value)}
                                className="w-24 h-8 text-right font-mono text-sm"
                              />
                            </td>
                            <td className="px-4 py-3 border">
                              <Input
                                type="number"
                                min="0"
                                step="0.01"
                                value={item.monthly_cost}
                                onChange={(e) => updateItemCost(index, 'monthly_cost', e.target.value)}
                                className="w-24 h-8 text-right font-mono text-sm"
                              />
                            </td>
                            <td className="px-4 py-3 text-center border">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => removeMedioPagoItem(index)}
                                className="text-red-600 hover:text-red-700 hover:border-red-300"
                              >
                                <Trash2 size={14} />
                              </Button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr className="bg-slate-100 font-semibold">
                          <td colSpan={3} className="px-4 py-3 text-right text-sm text-slate-700 border">TOTALES:</td>
                          <td className="px-4 py-3 text-right text-sm text-brand-blue-600 border font-mono">${totalSetup.toFixed(2)}</td>
                          <td className="px-4 py-3 text-right text-sm text-brand-green-600 border font-mono">${totalRecurrente.toFixed(2)}</td>
                          <td className="border"></td>
                        </tr>
                        <tr className="bg-slate-900 text-white">
                          <td colSpan={3} className="px-4 py-3 text-right text-sm font-bold border border-slate-900">TOTAL GENERAL:</td>
                          <td colSpan={2} className="px-4 py-3 text-right text-lg font-bold border border-slate-900 font-mono">${grandTotal.toFixed(2)} USD</td>
                          <td className="border border-slate-900"></td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>

                  {/* Notas */}
                  <div className="mt-4">
                    <Label htmlFor="notes" className="text-sm font-medium text-slate-700">Notas adicionales</Label>
                    <Textarea
                      id="notes"
                      value={quoteData.notes}
                      onChange={(e) => setQuoteData({ ...quoteData, notes: e.target.value })}
                      placeholder="Observaciones o condiciones especiales..."
                      rows={2}
                      className="mt-2"
                    />
                  </div>

                  {/* Botón Finalizar */}
                  <div className="mt-6 flex justify-end">
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
