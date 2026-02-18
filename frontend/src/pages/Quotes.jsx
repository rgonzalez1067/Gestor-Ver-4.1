import { useState, useEffect } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Plus, FileText, Download, Monitor, Globe, Smartphone, Link, Trash2, Building2, CreditCard, CheckCircle2, Copy, Cpu, Users, Landmark } from 'lucide-react';
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

// Conceptos EXCLUSIVOS de Setup (Inversión Inicial)
// lockBancos: true = campo Bancos bloqueado para edición
// autoBancos: true = auto-calcular basado en medios de pago agregados
const SETUP_CONCEPTS = [
  { name: 'Suscripción PDV/Banco', isDefault: true, type: 'setup', lockBancos: false, autoBancos: false },
  { name: 'Configuración dispositivo (Pinpad o POS)', isDefault: true, type: 'setup', lockBancos: true, autoBancos: false },
  { name: 'Configuración PDV en MServer', isDefault: true, type: 'setup', lockBancos: true, autoBancos: false },
  { name: 'Configuración Medio de Pago / Banco en MServer, por PDV', isDefault: true, type: 'setup', lockBancos: false, autoBancos: true }
];

// Recurrentes Básicos (obligatorios) - incluye conceptos pre-relacionados con Setup
// lockBancos: true = campo Bancos bloqueado en 1 (cobro unitario por PDV)
const RECURRING_BASIC_CONCEPTS = [
  { name: 'Derecho de uso de plataforma MServer por PDV', isDefault: true, type: 'recurring_basic', lockBancos: true },
  { name: 'Derecho de uso de plataforma MServer por PDV / Banco', isDefault: true, type: 'recurring_basic' }
];

// Otros Recurrentes - lockBancos: true para mostrar N/A
const RECURRING_OTHER_CONCEPTS = [
  { name: 'Comunicación Backend (SSL Público o VPN, APN, etc.)', isDefault: true, type: 'recurring_other', lockBancos: true },
  { name: 'Procesamiento (HSM, Server, DC, etc.)', isDefault: true, type: 'recurring_other', lockBancos: true }
];

export const Quotes = () => {
  const [quotes, setQuotes] = useState([]);
  const [clients, setClients] = useState([]);
  const [banks, setBanks] = useState([]);
  const [serviceCatalog, setServiceCatalog] = useState([]); // Catálogo de precios
  const [integrators, setIntegrators] = useState([]); // Lista de integradores
  const [pinpads, setPinpads] = useState([]); // Lista de pinpads (dispositivos tipo Pinpad)
  const [loading, setLoading] = useState(true);
  const [wizardOpen, setWizardOpen] = useState(false);
  
  // Estado del formulario de cotización
  const [quoteData, setQuoteData] = useState({
    quote_type: '',
    client_id: '',
    pricing_model: '', // 'conventional' o 'outsourcing'
    cantidad_cajas: 1,
    cantidad_bancos: 1,
    // Nuevos campos de integración y hardware
    integrator_id: '',
    integrator_app_name: '', // Campo informativo auto-completado
    pinpad_id: '',
    sponsor_bank_id: '', // Entidad patrocinadora/vendedora
    setup_items: [],              // Items exclusivos de Setup
    recurring_basic_items: [],    // Recurrentes Básicos (incluye complementos de adicionales)
    recurring_other_items: [],    // Otros Recurrentes
    additional_items: [],         // Items adicionales (medios de pago de bancos)
    descuento: 0,
    notes: ''
  });
  
  // Estado para agregar nuevo medio de pago
  const [selectedBankId, setSelectedBankId] = useState('');
  const [selectedMedioPagoId, setSelectedMedioPagoId] = useState('');
  const [availableMediosPago, setAvailableMediosPago] = useState([]);

  useEffect(() => {
    fetchData();
  }, []);

  // Auto-calcular campo "Bancos" para conceptos con autoBancos: true
  useEffect(() => {
    if (quoteData.setup_items.length > 0) {
      const totalMediosPago = quoteData.additional_items.length;
      
      const updatedSetupItems = quoteData.setup_items.map(item => {
        if (item.autoBancos) {
          return { ...item, cantidad_bancos: Math.max(1, totalMediosPago) };
        }
        return item;
      });
      
      // Solo actualizar si hay cambios
      const hasChanges = updatedSetupItems.some((item, idx) => 
        item.cantidad_bancos !== quoteData.setup_items[idx].cantidad_bancos
      );
      
      if (hasChanges) {
        setQuoteData(prev => ({ ...prev, setup_items: updatedSetupItems }));
      }
    }
  }, [quoteData.additional_items.length]);

  // Sincronizar valores de Cajas y Bancos de la cabecera con los conceptos base
  useEffect(() => {
    const { cantidad_cajas, cantidad_bancos, setup_items, recurring_basic_items, recurring_other_items } = quoteData;
    
    if (setup_items.length === 0 && recurring_basic_items.length === 0 && recurring_other_items.length === 0) {
      return; // No hay items para actualizar
    }
    
    let needsUpdate = false;
    
    // Actualizar Setup items (excepto lockBancos y autoBancos)
    const updatedSetupItems = setup_items.map(item => {
      if (item.isDefault) {
        const newCajas = cantidad_cajas || 1;
        const newBancos = (item.lockBancos || item.autoBancos) ? item.cantidad_bancos : (cantidad_bancos || 1);
        
        if (item.cantidad_cajas !== newCajas || (!item.lockBancos && !item.autoBancos && item.cantidad_bancos !== newBancos)) {
          needsUpdate = true;
          return { ...item, cantidad_cajas: newCajas, cantidad_bancos: newBancos };
        }
      }
      return item;
    });
    
    // Actualizar Recurrentes Básicos (solo los base, no los auto-vinculados)
    const updatedRecurringBasic = recurring_basic_items.map(item => {
      if (item.isDefault && !item.isAutoLinked) {
        const newCajas = cantidad_cajas || 1;
        const newBancos = cantidad_bancos || 1;
        
        if (item.cantidad_cajas !== newCajas || item.cantidad_bancos !== newBancos) {
          needsUpdate = true;
          return { ...item, cantidad_cajas: newCajas, cantidad_bancos: newBancos };
        }
      }
      return item;
    });
    
    // Actualizar Otros Recurrentes
    const updatedRecurringOther = recurring_other_items.map(item => {
      if (item.isDefault) {
        const newCajas = cantidad_cajas || 1;
        const newBancos = cantidad_bancos || 1;
        
        if (item.cantidad_cajas !== newCajas || item.cantidad_bancos !== newBancos) {
          needsUpdate = true;
          return { ...item, cantidad_cajas: newCajas, cantidad_bancos: newBancos };
        }
      }
      return item;
    });
    
    if (needsUpdate) {
      setQuoteData(prev => ({
        ...prev,
        setup_items: updatedSetupItems,
        recurring_basic_items: updatedRecurringBasic,
        recurring_other_items: updatedRecurringOther
      }));
    }
  }, [quoteData.cantidad_cajas, quoteData.cantidad_bancos]);

  const fetchData = async () => {
    try {
      const [quotesRes, clientsRes, banksRes, servicesRes, integratorsRes, hardwareRes] = await Promise.all([
        api.get('/quotes'),
        api.get('/clients'),
        api.get('/banks'),
        api.get('/services'), // Cargar catálogo de precios
        api.get('/integrators'), // Cargar integradores
        api.get('/hardware') // Cargar dispositivos
      ]);
      setQuotes(quotesRes.data);
      setClients(clientsRes.data);
      setBanks(banksRes.data);
      setServiceCatalog(servicesRes.data);
      setIntegrators(integratorsRes.data);
      // Filtrar solo dispositivos tipo "Pinpad"
      const pinpadDevices = (hardwareRes.data || []).filter(hw => 
        hw.type?.toLowerCase() === 'pinpad'
      );
      setPinpads(pinpadDevices);
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
        application_type: service.application_type || 'both',
        linked_recurring_service_id: service.linked_recurring_service_id || null
      };
    }
    return { setup_cost: 0, monthly_cost: 0, application_type: 'both', linked_recurring_service_id: null };
  };

  // Obtener servicio por ID
  const getServiceById = (serviceId) => {
    return serviceCatalog.find(s => s.service_id === serviceId);
  };

  // Función para consolidar recurrentes (de-duplicar y acumular)
  const consolidateRecurringItems = (items) => {
    const consolidated = {};
    
    items.forEach(item => {
      const key = item.medio_pago_name;
      if (consolidated[key]) {
        // Acumular en cantidad_bancos
        consolidated[key].cantidad_bancos += item.cantidad_bancos || 1;
      } else {
        consolidated[key] = { ...item };
      }
    });
    
    return Object.values(consolidated);
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
      // Si lockBancos es true, el campo Bancos vale 1 y está bloqueado
      // Si autoBancos es true, el campo Bancos se calculará dinámicamente
      const bancosValue = concept.lockBancos ? 1 : cantidadBancos;
      return {
        id: `setup_${concept.name}`,
        medio_pago_name: concept.name,
        cantidad_cajas: cantidadCajas,
        cantidad_bancos: bancosValue,
        tarifa: prices.setup_cost,
        isDefault: true,
        type: 'setup',
        lockBancos: concept.lockBancos || false,
        autoBancos: concept.autoBancos || false
      };
    });
  };

  // BLOQUE 1: Inicializar Recurrentes Básicos
  const initializeRecurringBasicConcepts = (pricingModel, cantidadCajas, cantidadBancos) => {
    return RECURRING_BASIC_CONCEPTS.map((concept) => {
      const prices = findServicePriceWithModel(concept.name, pricingModel);
      return {
        id: `recurring_basic_${concept.name}`,
        medio_pago_name: concept.name,
        cantidad_cajas: cantidadCajas,
        cantidad_bancos: concept.lockBancos ? 1 : cantidadBancos, // lockBancos usa 1 fijo
        tarifa: prices.monthly_cost,
        isDefault: true,
        type: 'recurring_basic',
        lockBancos: concept.lockBancos || false
      };
    });
  };

  // Inicializar Otros Recurrentes
  const initializeRecurringOtherConcepts = (pricingModel, cantidadCajas, cantidadBancos) => {
    return RECURRING_OTHER_CONCEPTS.map((concept) => {
      const prices = findServicePriceWithModel(concept.name, pricingModel);
      return {
        id: `recurring_other_${concept.name}`,
        medio_pago_name: concept.name,
        cantidad_cajas: cantidadCajas,
        cantidad_bancos: concept.lockBancos ? 1 : cantidadBancos, // N/A usa 1 internamente
        tarifa: prices.monthly_cost,
        isDefault: true,
        type: 'recurring_other',
        lockBancos: concept.lockBancos || false
      };
    });
  };

  // Función para agregar complementos recurrentes de items ADICIONALES (no de conceptos base)
  // Solo aplica a los medios de pago que el usuario agregó manualmente
  const addRecurringComplementsFromAdditional = () => {
    const cajas = quoteData.cantidad_cajas || 1;
    const bancos = quoteData.cantidad_bancos || 1;
    
    // Solo crear complementos para los items adicionales (los que el usuario agregó)
    const newComplements = quoteData.additional_items.map((item) => {
      const prices = findServicePriceWithModel(`Mantenimiento ${item.medio_pago_name}`, quoteData.pricing_model);
      return {
        id: `recurring_from_additional_${item.id}`,
        medio_pago_name: `Mantenimiento ${item.medio_pago_name}`,
        linkedTo: item.medio_pago_name,
        bank_name: item.bank_name,
        cantidad_cajas: cajas,
        cantidad_bancos: bancos,
        tarifa: prices.monthly_cost || item.tarifa_recurrente || 0,
        isDefault: false,
        isComplement: true,
        type: 'recurring_basic'
      };
    });

    // Agregar a recurring_basic_items sin duplicar
    const existingIds = quoteData.recurring_basic_items.map(i => i.id);
    const uniqueComplements = newComplements.filter(c => !existingIds.includes(c.id));

    setQuoteData({
      ...quoteData,
      recurring_basic_items: [...quoteData.recurring_basic_items, ...uniqueComplements]
    });
  };

  // Versión de findServicePrice que acepta modelo como parámetro (para inicialización)
  const findServicePriceWithModel = (productName, pricingModel) => {
    // Primero intentar coincidencia exacta (case-insensitive)
    let service = serviceCatalog.find(s => 
      s.name.toLowerCase() === productName.toLowerCase()
    );
    
    // Si no hay coincidencia exacta, buscar por inclusión pero priorizando el nombre más largo
    if (!service) {
      const candidates = serviceCatalog.filter(s => 
        s.name.toLowerCase().includes(productName.toLowerCase()) ||
        productName.toLowerCase().includes(s.name.toLowerCase())
      );
      
      // Ordenar por longitud de nombre descendente para evitar que nombres cortos coincidan antes
      if (candidates.length > 0) {
        candidates.sort((a, b) => b.name.length - a.name.length);
        // Buscar el que mejor coincida con la longitud del productName
        service = candidates.find(c => 
          c.name.toLowerCase() === productName.toLowerCase() ||
          Math.abs(c.name.length - productName.length) < 10
        ) || candidates[0];
      }
    }
    
    if (service) {
      const isOutsourcing = pricingModel === 'outsourcing';
      return {
        setup_cost: isOutsourcing 
          ? (service.setup_cost_outsourcing || 0) 
          : (service.setup_cost_conventional || 0),
        monthly_cost: isOutsourcing 
          ? (service.monthly_cost_outsourcing || 0) 
          : (service.monthly_cost_conventional || 0),
        application_type: service.application_type || 'both',
        service_id: service.service_id,
        service_name: service.name
      };
    }
    return { setup_cost: 0, monthly_cost: 0, application_type: 'both', service_id: null, service_name: null };
  };

  const openWizard = () => {
    setWizardOpen(true);
    setQuoteData({
      quote_type: '',
      client_id: '',
      pricing_model: '',
      cantidad_cajas: 1,
      cantidad_bancos: 1,
      integrator_id: '',
      integrator_app_name: '',
      pinpad_id: '',
      sponsor_bank_id: '',
      setup_items: [],
      recurring_basic_items: [],
      recurring_other_items: [],
      additional_items: [],
      descuento: 0,
      notes: ''
    });
    setSelectedBankId('');
    setSelectedMedioPagoId('');
    setAvailableMediosPago([]);
  };

  // Handler para selección de integrador
  const handleIntegratorChange = (integratorId) => {
    const integrator = integrators.find(i => i.integrator_id === integratorId);
    setQuoteData({
      ...quoteData,
      integrator_id: integratorId,
      integrator_app_name: integrator?.app_name || ''
    });
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

    // REGLA: Nuevos Medios de Pago siempre inician con Bancos = 1
    const newItem = {
      id: `${selectedBankId}_${selectedMedioPagoId}`,
      bank_id: selectedBankId,
      bank_name: bank.name,
      medio_pago_name: medioPago.product_name,
      description: medioPago.description || '',
      cantidad_cajas: quoteData.cantidad_cajas,
      cantidad_bancos: 1, // Siempre inicia en 1, configuración granular
      tarifa_setup: prices.setup_cost,
      tarifa_recurrente: prices.monthly_cost,
      application_type: prices.application_type,
      isDefault: false,
      linked_recurring_service_id: prices.linked_recurring_service_id
    };

    // Preparar nuevo estado
    let newAdditionalItems = [...quoteData.additional_items, newItem];
    let newRecurringBasicItems = [...quoteData.recurring_basic_items];

    // CARGA AUTOMÁTICA: Si el servicio tiene un recurrente vinculado, agregarlo
    if (prices.linked_recurring_service_id) {
      const linkedService = getServiceById(prices.linked_recurring_service_id);
      if (linkedService) {
        const isOutsourcing = quoteData.pricing_model === 'outsourcing';
        const linkedMonthlyPrice = isOutsourcing 
          ? (linkedService.monthly_cost_outsourcing || 0) 
          : (linkedService.monthly_cost_conventional || 0);

        // Crear item recurrente vinculado
        const linkedRecurringItem = {
          id: `auto_linked_${newItem.id}_${linkedService.service_id}`,
          medio_pago_name: linkedService.name,
          linkedTo: medioPago.product_name,
          bank_name: bank.name,
          cantidad_cajas: quoteData.cantidad_cajas,
          cantidad_bancos: 1, // Cada vinculación cuenta como 1 banco para acumulación
          tarifa: linkedMonthlyPrice,
          isDefault: false,
          isAutoLinked: true,
          sourceServiceId: newItem.id,
          type: 'recurring_basic'
        };

        newRecurringBasicItems.push(linkedRecurringItem);
        
        toast.success(`Agregado: ${medioPago.product_name} + Recurrente vinculado: ${linkedService.name}`);
      } else {
        toast.success('Medio de pago agregado');
      }
    } else {
      toast.success('Medio de pago agregado');
    }

    // Consolidar recurrentes (de-duplicar y acumular cantidades)
    const consolidatedRecurring = consolidateRecurringItems(newRecurringBasicItems);

    setQuoteData({
      ...quoteData,
      additional_items: newAdditionalItems,
      recurring_basic_items: consolidatedRecurring
    });

    setSelectedBankId('');
    setSelectedMedioPagoId('');
    setAvailableMediosPago([]);
  };

  const removeAdditionalItem = (index) => {
    const itemToRemove = quoteData.additional_items[index];
    
    // Remover también los recurrentes vinculados a este item
    const filteredRecurringBasic = quoteData.recurring_basic_items.filter(
      r => r.sourceServiceId !== itemToRemove.id
    );
    
    // Re-consolidar recurrentes después de eliminar
    const consolidatedRecurring = consolidateRecurringItems(filteredRecurringBasic);

    setQuoteData({
      ...quoteData,
      additional_items: quoteData.additional_items.filter((_, i) => i !== index),
      recurring_basic_items: consolidatedRecurring
    });
  };

  // Eliminar item de recurrentes básicos (solo auto-vinculados)
  const removeRecurringBasicItem = (index) => {
    const item = quoteData.recurring_basic_items[index];
    if (!item.isAutoLinked) {
      toast.error('Los conceptos base no se pueden eliminar');
      return;
    }
    setQuoteData({
      ...quoteData,
      recurring_basic_items: quoteData.recurring_basic_items.filter((_, i) => i !== index)
    });
  };

  // Actualizar campo en setup_items
  const updateSetupItem = (index, field, value) => {
    const updatedItems = [...quoteData.setup_items];
    updatedItems[index] = {
      ...updatedItems[index],
      [field]: field === 'cantidad_cajas' || field === 'cantidad_bancos' || field === 'tarifa' 
        ? (value === '' ? '' : parseFloat(value)) 
        : value
    };
    setQuoteData({ ...quoteData, setup_items: updatedItems });
  };

  // Duplicar un concepto de Setup
  const duplicateSetupItem = (index) => {
    const itemToDuplicate = quoteData.setup_items[index];
    const newItem = {
      ...itemToDuplicate,
      id: `setup_copy_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      isDefault: false, // La copia no es concepto base
      isCopy: true
    };
    
    // Insertar la copia justo después del original
    const newSetupItems = [
      ...quoteData.setup_items.slice(0, index + 1),
      newItem,
      ...quoteData.setup_items.slice(index + 1)
    ];
    
    setQuoteData({ ...quoteData, setup_items: newSetupItems });
    toast.success('Concepto duplicado');
  };

  // Eliminar un concepto de Setup (solo copias, no los base)
  const removeSetupItem = (index) => {
    const item = quoteData.setup_items[index];
    if (item.isDefault && !item.isCopy) {
      toast.error('Los conceptos base no se pueden eliminar');
      return;
    }
    setQuoteData({
      ...quoteData,
      setup_items: quoteData.setup_items.filter((_, i) => i !== index)
    });
  };

  // Actualizar campo en recurring_basic_items
  const updateRecurringBasicItem = (index, field, value) => {
    const updatedItems = [...quoteData.recurring_basic_items];
    updatedItems[index] = {
      ...updatedItems[index],
      [field]: field === 'cantidad_cajas' || field === 'cantidad_bancos' || field === 'tarifa' 
        ? (value === '' ? '' : parseFloat(value)) 
        : value
    };
    setQuoteData({ ...quoteData, recurring_basic_items: updatedItems });
  };

  // Actualizar campo en recurring_other_items
  const updateRecurringOtherItem = (index, field, value) => {
    const updatedItems = [...quoteData.recurring_other_items];
    updatedItems[index] = {
      ...updatedItems[index],
      [field]: field === 'cantidad_cajas' || field === 'cantidad_bancos' || field === 'tarifa' 
        ? (value === '' ? '' : parseFloat(value)) 
        : value
    };
    setQuoteData({ ...quoteData, recurring_other_items: updatedItems });
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
    // Si lockBancos es true, el cálculo usa 1 (N/A en UI)
    const bancos = item.lockBancos ? 1 : (item.cantidad_bancos || 1);
    const tarifa = item.tarifa || item.tarifa_setup || 0;
    return tarifa * cajas * bancos;
  };

  const calcularTotalRecurrente = (item) => {
    const cajas = item.cantidad_cajas || 1;
    const bancos = item.cantidad_bancos || 1;
    const tarifa = item.tarifa || item.tarifa_recurrente || 0;
    return tarifa * cajas * bancos;
  };

  // Calcular subtotales SETUP (conceptos base + adicionales con tarifa_setup)
  const subtotalSetup = 
    (quoteData.setup_items || []).reduce((sum, item) => sum + calcularTotal(item), 0) +
    (quoteData.additional_items || []).reduce((sum, item) => sum + ((item.tarifa_setup || 0) * (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1)), 0);

  // Calcular subtotales RECURRENTES (2 bloques + adicionales)
  const subtotalRecurringBasic = (quoteData.recurring_basic_items || []).reduce((sum, item) => sum + calcularTotal(item), 0);
  const subtotalRecurringOther = (quoteData.recurring_other_items || []).reduce((sum, item) => sum + calcularTotal(item), 0);
  const subtotalRecurringAdditional = (quoteData.additional_items || []).reduce((sum, item) => sum + ((item.tarifa_recurrente || 0) * (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1)), 0);
  
  const subtotalRecurrente = subtotalRecurringBasic + subtotalRecurringOther + subtotalRecurringAdditional;

  // Calcular descuento
  const montoDescuentoSetup = subtotalSetup * (quoteData.descuento / 100);
  const montoDescuentoRecurrente = subtotalRecurrente * (quoteData.descuento / 100);

  // Totales netos
  const totalNetoSetup = subtotalSetup - montoDescuentoSetup;
  const totalNetoRecurrente = subtotalRecurrente - montoDescuentoRecurrente;
  const grandTotal = totalNetoSetup + totalNetoRecurrente;

  const handleSubmitQuote = async () => {
    if (quoteData.setup_items.length === 0 && quoteData.recurring_basic_items.length === 0) {
      toast.error('No hay items en la cotización');
      return;
    }

    try {
      const allItems = [
        ...quoteData.setup_items.map(item => ({
          item_type: 'setup',
          item_name: item.medio_pago_name,
          quantity: item.cantidad_cajas * item.cantidad_bancos,
          unit_price_usd: item.tarifa,
          total_usd: calcularTotal(item)
        })),
        ...quoteData.recurring_basic_items.map(item => ({
          item_type: 'recurring_basic',
          item_name: item.medio_pago_name,
          quantity: item.cantidad_cajas * item.cantidad_bancos,
          unit_price_usd: item.tarifa,
          total_usd: calcularTotal(item)
        })),
        ...quoteData.recurring_other_items.map(item => ({
          item_type: 'recurring_other',
          item_name: item.medio_pago_name,
          quantity: item.cantidad_cajas * item.cantidad_bancos,
          unit_price_usd: item.tarifa,
          total_usd: calcularTotal(item)
        })),
        ...quoteData.additional_items.map(item => ({
          item_type: 'additional',
          item_name: `${item.medio_pago_name} - ${item.bank_name}`,
          quantity: item.cantidad_cajas * item.cantidad_bancos,
          unit_price_usd: (item.tarifa_setup || 0) + (item.tarifa_recurrente || 0),
          total_usd: (item.tarifa_setup || 0) * item.cantidad_cajas * item.cantidad_bancos + 
                     (item.tarifa_recurrente || 0) * item.cantidad_cajas * item.cantidad_bancos
        }))
      ];

      const payload = {
        client_id: quoteData.client_id,
        quote_type: quoteData.quote_type,
        services: allItems,
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

  // Exportar cotización actual a PDF (sin guardar en BD)
  const exportCurrentQuoteToPDF = async () => {
    const client = clients.find(c => c.client_id === quoteData.client_id);
    if (!client) {
      toast.error('Seleccione un cliente');
      return;
    }

    // Preparar datos para el PDF
    const pdfData = {
      cliente_nombre: client.legal_name || client.commercial_name || 'Cliente',
      cliente_rif: client.rif || '',
      quote_type: quoteData.quote_type,
      pricing_model: quoteData.pricing_model,
      setup_items: [
        ...quoteData.setup_items.map(item => ({
          concepto: item.medio_pago_name,
          cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
          cantidad_bancos: item.lockBancos ? 1 : (parseInt(item.cantidad_bancos) || 1),
          tarifa: parseFloat(item.tarifa) || 0
        })),
        ...quoteData.additional_items.filter(i => i.tarifa_setup > 0).map(item => ({
          concepto: `${item.medio_pago_name} - ${item.bank_name}`,
          cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
          cantidad_bancos: parseInt(item.cantidad_bancos) || 1,
          tarifa: parseFloat(item.tarifa_setup) || 0
        }))
      ],
      recurring_basic_items: quoteData.recurring_basic_items.map(item => ({
        concepto: item.medio_pago_name + (item.linkedTo ? ` (vinculado a ${item.linkedTo})` : ''),
        cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
        cantidad_bancos: item.lockBancos ? 1 : (parseInt(item.cantidad_bancos) || 1),
        tarifa: parseFloat(item.tarifa) || 0
      })),
      recurring_other_items: quoteData.recurring_other_items.map(item => ({
        concepto: item.medio_pago_name,
        cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
        cantidad_bancos: item.lockBancos ? 1 : (parseInt(item.cantidad_bancos) || 1),
        tarifa: parseFloat(item.tarifa) || 0
      })),
      descuento: quoteData.descuento || 0,
      notes: quoteData.notes || ''
    };

    try {
      toast.loading('Generando PDF...');
      
      const response = await api.post('/quotes/generate-pdf', pdfData, { 
        responseType: 'blob',
        headers: {
          'Accept': 'application/pdf'
        }
      });
      
      // Verificar que la respuesta sea válida
      if (!response.data || response.data.size === 0) {
        toast.dismiss();
        toast.error('Error: Respuesta vacía del servidor');
        return;
      }
      
      // Verificar el tipo de contenido
      const contentType = response.headers['content-type'];
      if (contentType && contentType.includes('application/json')) {
        // Es un error JSON, no un PDF
        const text = await response.data.text();
        const errorData = JSON.parse(text);
        toast.dismiss();
        toast.error(errorData.detail || 'Error al generar PDF');
        return;
      }
      
      // Crear blob con tipo correcto
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      
      // Nombre del archivo
      const filename = `cotizacion_${client.legal_name?.replace(/\s+/g, '_') || 'cliente'}_${new Date().toISOString().split('T')[0]}.pdf`;
      
      // Crear elemento de descarga
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      link.target = '_blank';
      
      // Añadir al DOM, hacer clic y remover
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      // Limpiar URL después de un delay
      setTimeout(() => {
        window.URL.revokeObjectURL(url);
      }, 1000);
      
      toast.dismiss();
      toast.success('PDF descargado exitosamente');
    } catch (error) {
      toast.dismiss();
      console.error('Error generating PDF:', error);
      
      // Intentar obtener mensaje de error específico
      let errorMessage = 'Error al generar PDF';
      if (error.response?.data) {
        try {
          const text = await error.response.data.text?.();
          if (text) {
            const errorData = JSON.parse(text);
            errorMessage = errorData.detail || errorMessage;
          }
        } catch (e) {
          // Ignorar errores de parsing
        }
      }
      
      toast.error(errorMessage);
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
  const selectedIntegrator = integrators.find(i => i.integrator_id === quoteData.integrator_id);
  const selectedPinpad = pinpads.find(p => p.hardware_id === quoteData.pinpad_id);
  const selectedSponsorBank = banks.find(b => b.bank_id === quoteData.sponsor_bank_id);
  
  // Validación completa incluyendo nuevos campos obligatorios
  const isHeaderComplete = quoteData.quote_type && 
    quoteData.client_id && 
    quoteData.pricing_model && 
    (quoteData.cantidad_cajas >= 1 || quoteData.cantidad_cajas === '') &&
    quoteData.integrator_id &&
    quoteData.pinpad_id &&
    quoteData.sponsor_bank_id;

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
                        // Al seleccionar modelo, inicializar todos los conceptos
                        const cajas = quoteData.cantidad_cajas || 1;
                        const bancos = quoteData.cantidad_bancos || 1;
                        const setupItems = initializeSetupConcepts(value, cajas, bancos);
                        const recurringBasicItems = initializeRecurringBasicConcepts(value, cajas, bancos);
                        const recurringOtherItems = initializeRecurringOtherConcepts(value, cajas, bancos);
                        setQuoteData({ 
                          ...quoteData, 
                          pricing_model: value, 
                          cantidad_cajas: cajas,
                          cantidad_bancos: bancos,
                          setup_items: setupItems,
                          recurring_basic_items: recurringBasicItems,
                          recurring_other_items: recurringOtherItems,
                          additional_items: []
                        });
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
                      onChange={(e) => setQuoteData({ ...quoteData, cantidad_cajas: e.target.value === '' ? '' : parseInt(e.target.value) })}
                      onBlur={(e) => {
                        if (e.target.value === '' || parseInt(e.target.value) < 1) {
                          setQuoteData({ ...quoteData, cantidad_cajas: 1 });
                        }
                      }}
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
                      onChange={(e) => setQuoteData({ ...quoteData, cantidad_bancos: e.target.value === '' ? '' : parseInt(e.target.value) })}
                      onBlur={(e) => {
                        if (e.target.value === '' || parseInt(e.target.value) < 1) {
                          setQuoteData({ ...quoteData, cantidad_bancos: 1 });
                        }
                      }}
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

              {/* SECCIÓN 3: Matriz de Resumen - Set Up (EXCLUSIVO) */}
              {isHeaderComplete && quoteData.setup_items.length > 0 && (
                <div className="bg-white rounded-lg border mt-4 overflow-hidden">
                  {/* Encabezado Set Up */}
                  <div className="bg-gradient-to-r from-cyan-500 to-cyan-600 text-white text-center py-2 font-semibold">
                    Set Up - Puesta en Marcha (Inversión Inicial)
                  </div>
                  
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse text-sm">
                      <thead>
                        <tr className="bg-slate-100">
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-16">N°</th>
                          <th className="px-3 py-2 text-left font-semibold text-slate-700 border border-slate-300">Concepto</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-24">(VTID)<br/>Cajas</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-24">Bancos o<br/>Entes</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-28">Tarifa Set-up<br/>(USD)</th>
                          <th className="px-3 py-2 text-center font-semibold text-brand-blue-600 border border-slate-300 w-32 bg-blue-50">Total USD</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-16"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {/* Conceptos base de Setup */}
                        {quoteData.setup_items.map((item, index) => (
                          <tr key={`setup-${index}`} className={`${index % 2 === 0 ? 'bg-white' : 'bg-slate-50'} border-l-4 ${item.isCopy ? 'border-l-amber-500' : 'border-l-cyan-500'}`}>
                            <td className="px-3 py-2 text-center font-medium border border-slate-300">{index + 1}</td>
                            <td className="px-3 py-2 border border-slate-300">
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-slate-900">{item.medio_pago_name}</span>
                                {item.isCopy ? (
                                  <span className="px-1.5 py-0.5 text-xs font-medium bg-amber-100 text-amber-700 rounded">Copia</span>
                                ) : (
                                  <span className="px-1.5 py-0.5 text-xs font-medium bg-cyan-100 text-cyan-700 rounded">Base</span>
                                )}
                                {item.lockBancos && <span className="px-1.5 py-0.5 text-xs font-medium bg-slate-200 text-slate-600 rounded">N/A</span>}
                                {item.autoBancos && <span className="px-1.5 py-0.5 text-xs font-medium bg-purple-100 text-purple-700 rounded">Auto</span>}
                              </div>
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Input
                                type="number"
                                min="1"
                                value={item.cantidad_cajas}
                                onChange={(e) => updateSetupItem(index, 'cantidad_cajas', e.target.value)}
                                className="w-16 h-7 text-center text-sm mx-auto"
                              />
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              {item.lockBancos ? (
                                <div className="w-16 h-7 flex items-center justify-center text-sm mx-auto font-medium text-slate-400 bg-slate-100 rounded">
                                  N/A
                                </div>
                              ) : item.autoBancos ? (
                                <div className="w-16 h-7 flex items-center justify-center text-sm mx-auto font-medium text-purple-600 bg-purple-50 rounded">
                                  {item.cantidad_bancos}
                                </div>
                              ) : (
                                <Input
                                  type="number"
                                  min="1"
                                  value={item.cantidad_bancos}
                                  onChange={(e) => updateSetupItem(index, 'cantidad_bancos', e.target.value)}
                                  className="w-16 h-7 text-center text-sm mx-auto"
                                />
                              )}
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Input
                                type="number"
                                min="0"
                                step="0.01"
                                value={item.tarifa}
                                onChange={(e) => updateSetupItem(index, 'tarifa', e.target.value)}
                                className="w-20 h-7 text-right text-sm mx-auto font-mono"
                              />
                            </td>
                            <td className="px-3 py-2 text-right border border-slate-300 bg-blue-50 font-mono font-semibold text-brand-blue-600">
                              ${calcularTotal(item).toFixed(2)}
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <div className="flex items-center justify-center gap-1">
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => duplicateSetupItem(index)}
                                  className="h-7 w-7 p-0 text-brand-blue-500 hover:text-brand-blue-700 hover:bg-blue-50"
                                  title="Duplicar"
                                >
                                  <Copy size={14} />
                                </Button>
                                {item.isCopy && (
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => removeSetupItem(index)}
                                    className="h-7 w-7 p-0 text-red-500 hover:text-red-700 hover:bg-red-50"
                                    title="Eliminar"
                                  >
                                    <Trash2 size={14} />
                                  </Button>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))}
                        {/* Items adicionales con Setup */}
                        {quoteData.additional_items.filter(i => i.tarifa_setup > 0).map((item, index) => {
                          const realIndex = quoteData.additional_items.indexOf(item);
                          return (
                          <tr key={`add-setup-${index}`} className="bg-white border-l-4 border-l-amber-500">
                            <td className="px-3 py-2 text-center font-medium border border-slate-300">{quoteData.setup_items.length + index + 1}</td>
                            <td className="px-3 py-2 border border-slate-300">
                              <div className="font-medium text-slate-900">{item.medio_pago_name}</div>
                              <div className="text-xs text-slate-500">{item.bank_name}</div>
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Input
                                type="number"
                                min="1"
                                value={item.cantidad_cajas}
                                onChange={(e) => updateAdditionalItem(realIndex, 'cantidad_cajas', e.target.value)}
                                className="w-16 h-7 text-center text-sm mx-auto"
                              />
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Input
                                type="number"
                                min="1"
                                value={item.cantidad_bancos}
                                onChange={(e) => updateAdditionalItem(realIndex, 'cantidad_bancos', e.target.value)}
                                className="w-16 h-7 text-center text-sm mx-auto"
                              />
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Input
                                type="number"
                                min="0"
                                step="0.01"
                                value={item.tarifa_setup}
                                onChange={(e) => updateAdditionalItem(realIndex, 'tarifa_setup', e.target.value)}
                                className="w-20 h-7 text-right text-sm mx-auto font-mono"
                              />
                            </td>
                            <td className="px-3 py-2 text-right border border-slate-300 bg-blue-50 font-mono font-semibold text-brand-blue-600">
                              ${((item.tarifa_setup || 0) * (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1)).toFixed(2)}
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => removeAdditionalItem(realIndex)}
                                className="h-7 w-7 p-0 text-red-500 hover:text-red-700 hover:bg-red-50"
                                title="Eliminar"
                              >
                                <Trash2 size={14} />
                              </Button>
                            </td>
                          </tr>
                        )})}
                      </tbody>
                      <tfoot>
                        <tr className="bg-slate-100">
                          <td colSpan={6} className="px-3 py-2 text-right font-semibold border border-slate-300">Subtotal Setup:</td>
                          <td className="px-3 py-2 text-right font-mono font-bold text-brand-blue-600 border border-slate-300 bg-blue-50">${subtotalSetup.toFixed(2)}</td>
                        </tr>
                        <tr className="bg-amber-50">
                          <td colSpan={5} className="px-3 py-2 text-right font-semibold border border-slate-300">Descuento:</td>
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
                          <td></td>
                        </tr>
                        <tr className="bg-cyan-100">
                          <td colSpan={6} className="px-3 py-2 text-right font-bold border border-slate-300">Total Setup Neto:</td>
                          <td className="px-3 py-2 text-right font-mono font-bold text-cyan-700 border border-slate-300 text-lg">${totalNetoSetup.toFixed(2)}</td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>

                  {/* BLOQUE 1: Recurrentes Básicos */}
                  <div className="bg-gradient-to-r from-green-500 to-green-600 text-white text-center py-2 font-semibold mt-4">
                    Costos Recurrentes - Básicos
                  </div>
                  
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse text-sm">
                      <thead>
                        <tr className="bg-slate-100">
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-16">N°</th>
                          <th className="px-3 py-2 text-left font-semibold text-slate-700 border border-slate-300">Concepto</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-24">(VTID)<br/>Cajas</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-24">Bancos o<br/>Entes</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-28">Tarifa Mensual<br/>(USD)</th>
                          <th className="px-3 py-2 text-center font-semibold text-brand-green-600 border border-slate-300 w-32 bg-green-50">Total USD</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-16"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {(quoteData.recurring_basic_items || []).map((item, index) => (
                          <tr key={`rec-basic-${index}`} className={`${index % 2 === 0 ? 'bg-white' : 'bg-slate-50'} border-l-4 ${item.isAutoLinked ? 'border-l-purple-500' : 'border-l-green-500'}`}>
                            <td className="px-3 py-2 text-center font-medium border border-slate-300">{index + 1}</td>
                            <td className="px-3 py-2 border border-slate-300">
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-slate-900">{item.medio_pago_name}</span>
                                {item.isAutoLinked ? (
                                  <span className="px-1.5 py-0.5 text-xs font-medium bg-purple-100 text-purple-700 rounded">Auto</span>
                                ) : (
                                  <span className="px-1.5 py-0.5 text-xs font-medium bg-green-100 text-green-700 rounded">Básico</span>
                                )}
                                {item.lockBancos && <span className="px-1.5 py-0.5 text-xs font-medium bg-slate-200 text-slate-600 rounded">N/A</span>}
                              </div>
                              {item.linkedTo && (
                                <div className="text-xs text-slate-500 mt-1">Vinculado a: {item.linkedTo}</div>
                              )}
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Input
                                type="number"
                                min="1"
                                value={item.cantidad_cajas}
                                onChange={(e) => updateRecurringBasicItem(index, 'cantidad_cajas', e.target.value)}
                                className="w-16 h-7 text-center text-sm mx-auto"
                              />
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              {item.lockBancos ? (
                                <div className="w-16 h-7 flex items-center justify-center text-sm mx-auto font-medium text-slate-400 bg-slate-100 rounded">
                                  N/A
                                </div>
                              ) : (
                                <Input
                                  type="number"
                                  min="1"
                                  value={item.cantidad_bancos}
                                  onChange={(e) => updateRecurringBasicItem(index, 'cantidad_bancos', e.target.value)}
                                  className="w-16 h-7 text-center text-sm mx-auto"
                                />
                              )}
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Input
                                type="number"
                                min="0"
                                step="0.01"
                                value={item.tarifa}
                                onChange={(e) => updateRecurringBasicItem(index, 'tarifa', e.target.value)}
                                className="w-20 h-7 text-right text-sm mx-auto font-mono"
                              />
                            </td>
                            <td className="px-3 py-2 text-right border border-slate-300 bg-green-50 font-mono font-semibold text-brand-green-600">
                              ${calcularTotal(item).toFixed(2)}
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              {item.isAutoLinked && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => removeRecurringBasicItem(index)}
                                  className="h-7 w-7 p-0 text-red-500 hover:text-red-700 hover:bg-red-50"
                                  title="Eliminar"
                                >
                                  <Trash2 size={14} />
                                </Button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr className="bg-green-50">
                          <td colSpan={6} className="px-3 py-2 text-right font-semibold border border-slate-300">Subtotal Básicos:</td>
                          <td className="px-3 py-2 text-right font-mono font-bold text-brand-green-600 border border-slate-300">${subtotalRecurringBasic.toFixed(2)}</td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>

                  {/* BLOQUE 2: Otros Recurrentes */}
                  <div className="bg-gradient-to-r from-teal-500 to-teal-600 text-white text-center py-2 font-semibold mt-4">
                    Otros Recurrentes
                  </div>
                  
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse text-sm">
                      <thead>
                        <tr className="bg-slate-100">
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-16">N°</th>
                          <th className="px-3 py-2 text-left font-semibold text-slate-700 border border-slate-300">Concepto</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-24">(VTID)<br/>Cajas</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-24">Bancos o<br/>Entes</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-28">Tarifa Mensual<br/>(USD)</th>
                          <th className="px-3 py-2 text-center font-semibold text-teal-600 border border-slate-300 w-32 bg-teal-50">Total USD</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-16"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {(quoteData.recurring_other_items || []).map((item, index) => (
                          <tr key={`rec-other-${index}`} className={`${index % 2 === 0 ? 'bg-white' : 'bg-slate-50'} border-l-4 border-l-teal-500`}>
                            <td className="px-3 py-2 text-center font-medium border border-slate-300">{index + 1}</td>
                            <td className="px-3 py-2 border border-slate-300">
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-slate-900">{item.medio_pago_name}</span>
                                <span className="px-1.5 py-0.5 text-xs font-medium bg-teal-100 text-teal-700 rounded">Otro</span>
                                {item.lockBancos && <span className="px-1.5 py-0.5 text-xs font-medium bg-slate-200 text-slate-600 rounded">N/A</span>}
                              </div>
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Input
                                type="number"
                                min="1"
                                value={item.cantidad_cajas}
                                onChange={(e) => updateRecurringOtherItem(index, 'cantidad_cajas', e.target.value)}
                                className="w-16 h-7 text-center text-sm mx-auto"
                              />
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              {item.lockBancos ? (
                                <div className="w-16 h-7 flex items-center justify-center text-sm mx-auto font-medium text-slate-400 bg-slate-100 rounded">
                                  N/A
                                </div>
                              ) : (
                                <Input
                                  type="number"
                                  min="1"
                                  value={item.cantidad_bancos}
                                  onChange={(e) => updateRecurringOtherItem(index, 'cantidad_bancos', e.target.value)}
                                  className="w-16 h-7 text-center text-sm mx-auto"
                                />
                              )}
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Input
                                type="number"
                                min="0"
                                step="0.01"
                                value={item.tarifa}
                                onChange={(e) => updateRecurringOtherItem(index, 'tarifa', e.target.value)}
                                className={`w-20 h-7 text-right text-sm mx-auto font-mono ${(!item.tarifa || item.tarifa === 0) ? 'border-amber-400 bg-amber-50' : ''}`}
                                placeholder="0.00"
                              />
                              {(!item.tarifa || item.tarifa === 0) && (
                                <p className="text-xs text-amber-600 mt-1">Configurar</p>
                              )}
                            </td>
                            <td className="px-3 py-2 text-right border border-slate-300 bg-teal-50 font-mono font-semibold text-teal-600">
                              ${calcularTotal(item).toFixed(2)}
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              {/* Los conceptos base no se pueden eliminar */}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr className="bg-teal-50">
                          <td colSpan={6} className="px-3 py-2 text-right font-semibold border border-slate-300">Subtotal Otros:</td>
                          <td className="px-3 py-2 text-right font-mono font-bold text-teal-600 border border-slate-300">${subtotalRecurringOther.toFixed(2)}</td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>

                  {/* Resumen Total Recurrentes */}
                  <div className="overflow-x-auto mt-4">
                    <table className="w-full border-collapse text-sm">
                      <tfoot>
                        <tr className="bg-slate-100">
                          <td colSpan={6} className="px-3 py-2 text-right font-semibold border border-slate-300">SUBTOTAL RECURRENTES:</td>
                          <td className="px-3 py-2 text-right font-mono font-bold text-brand-green-600 border border-slate-300 bg-green-50 w-32">${subtotalRecurrente.toFixed(2)}</td>
                        </tr>
                        <tr className="bg-amber-50">
                          <td colSpan={6} className="px-3 py-2 text-right font-semibold border border-slate-300">Descuento ({quoteData.descuento}%):</td>
                          <td className="px-3 py-2 text-right font-mono font-bold text-amber-600 border border-slate-300 w-32">-${montoDescuentoRecurrente.toFixed(2)}</td>
                        </tr>
                        <tr className="bg-green-100">
                          <td colSpan={6} className="px-3 py-2 text-right font-bold border border-slate-300">TOTAL RECURRENTE NETO:</td>
                          <td className="px-3 py-2 text-right font-mono font-bold text-brand-green-700 border border-slate-300 text-lg w-32">${totalNetoRecurrente.toFixed(2)}</td>
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

                    <div className="mt-4 flex justify-end gap-3">
                      <Button
                        onClick={exportCurrentQuoteToPDF}
                        variant="outline"
                        className="border-brand-blue-600 text-brand-blue-600 hover:bg-brand-blue-50 px-6 py-3 text-lg"
                        data-testid="export-pdf-button"
                      >
                        <Download size={20} className="mr-2" />
                        Exportar PDF
                      </Button>
                      <Button
                        onClick={handleSubmitQuote}
                        className="bg-brand-green-600 hover:bg-brand-green-700 text-white px-8 py-3 text-lg"
                        data-testid="submit-quote-button"
                      >
                        <CheckCircle2 size={20} className="mr-2" />
                        Guardar Cotización
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {/* Mensaje cuando no hay items */}
              {isHeaderComplete && quoteData.setup_items.length === 0 && (
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
