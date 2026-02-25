import { useState, useEffect } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '../components/ui/dropdown-menu';
// Tabs removidos - ahora usamos panel único de gestión
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Plus, FileText, Download, Monitor, Globe, Smartphone, Link, Trash2, Building2, CreditCard, CheckCircle2, Copy, Cpu, Users, Landmark, MoreHorizontal, Pencil, Mail, CheckCircle, Send, Package, Settings2, Filter, X, Search, Calendar, Receipt, Banknote, Truck, RefreshCw, Upload, FolderOpen } from 'lucide-react';
import { EquipmentQuoteWizard } from '../components/EquipmentQuoteWizard';
import { AnexosModal } from '../components/AnexosModal';
import { WorkflowUploadModal } from '../components/WorkflowUploadModal';
import api from '../utils/api';
import { toast } from 'sonner';

const QUOTE_TYPES = [
  { id: 'VPOS_MPOS', name: 'VPOS/MPOS (Cajas y Tablet)', icon: Monitor, description: 'Puntos de venta físicos y móviles' },
  { id: 'GATEWAY', name: 'Payment Gateway', icon: Globe, description: 'Pasarela de pagos' },
  { id: 'LINK', name: 'Link de Pago', icon: Link, description: 'Enlaces de cobro', disabled: true }
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

// Colores de estado
const STATUS_COLORS = {
  'Borrador': 'bg-slate-100 text-slate-700',
  'draft': 'bg-slate-100 text-slate-700', // Legacy support
  'Enviada': 'bg-blue-100 text-blue-700',
  'Emitida': 'bg-blue-100 text-blue-700', // Legacy support
  'Aprobada': 'bg-green-100 text-green-700',
  'Facturada': 'bg-purple-100 text-purple-700',
  'Pagada': 'bg-emerald-100 text-emerald-700',
  'Entregada': 'bg-teal-100 text-teal-700',
  'Enviada a Imple': 'bg-amber-100 text-amber-700',
  'En Implementación': 'bg-amber-100 text-amber-700', // Legacy support
  'Completada': 'bg-emerald-100 text-emerald-700' // Legacy support
};

// Mapeo de nombres de estado (para mostrar en español)
const STATUS_DISPLAY_NAMES = {
  'draft': 'Borrador',
  'Borrador': 'Borrador',
  'Enviada': 'Enviada',
  'Emitida': 'Emitida', // Legacy
  'Aprobada': 'Aprobada',
  'Facturada': 'Facturada',
  'Pagada': 'Pagada',
  'Entregada': 'Entregada',
  'Enviada a Imple': 'Enviada a Imple',
  'En Implementación': 'En Implementación', // Legacy
  'Completada': 'Completada' // Legacy
};

// Categorías de cotización - Actualizado según anexo
const QUOTE_CATEGORY_LABELS = {
  'implementation': 'Implementación',
  'equipment': 'Equipos',
  'repair': 'Reparaciones'
};

// Categorías para filtro según nueva estructura jerárquica
const QUOTE_FILTER_CATEGORIES = [
  { id: 'implementation', name: 'Implementaciones', description: 'Servicios de instalación, configuración o puesta en marcha' },
  { id: 'equipment', name: 'Equipos', description: 'Venta de hardware principal (Laptops, Servidores, etc.)' },
  { id: 'accessory', name: 'Accesorios', description: 'Periféricos y complementos (Mouses, cables, teclados)' },
  { id: 'repair', name: 'Reparaciones', description: 'Mano de obra técnica y servicios de mantenimiento correctivo' }
];

export const Quotes = () => {
  const [quotes, setQuotes] = useState([]);
  const [clients, setClients] = useState([]);
  const [banks, setBanks] = useState([]);
  const [serviceCatalog, setServiceCatalog] = useState([]); // Catálogo de precios
  const [integrators, setIntegrators] = useState([]); // Lista de integradores
  const [pinpads, setPinpads] = useState([]); // Lista de pinpads (dispositivos tipo Pinpad)
  const [allHardware, setAllHardware] = useState([]); // Todos los dispositivos y accesorios
  const [actionLoading, setActionLoading] = useState(null); // Para indicar carga en acciones
  const [loading, setLoading] = useState(true);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [equipmentWizardOpen, setEquipmentWizardOpen] = useState(false);
  
  
  
  // Estado para usar plantilla PDF
  const [useTemplateForPDF, setUseTemplateForPDF] = useState(true); // Por defecto usa plantilla si está disponible
  const [templateAvailable, setTemplateAvailable] = useState({});
  
  // Estados para filtros rápidos
  const [filterClient, setFilterClient] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');
  
  // Estado para edición de cotización existente
  const [editingQuoteId, setEditingQuoteId] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isLoadingEdit, setIsLoadingEdit] = useState(false);
  
  // Estado para modal de Anexos
  const [anexosOpen, setAnexosOpen] = useState(false);
  const [anexosQuoteId, setAnexosQuoteId] = useState(null);
  const [anexosQuoteNumber, setAnexosQuoteNumber] = useState('');
  
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
  
  // Estado para Payment Gateway
  const [pgSetupItems, setPgSetupItems] = useState([]);
  const [pgTransactionRange, setPgTransactionRange] = useState(null);
  const [pgRecurringCostsTable, setPgRecurringCostsTable] = useState(null);
  const [pgSelectedMedioPago, setPgSelectedMedioPago] = useState('');
  const [pgSelectedBankId, setPgSelectedBankId] = useState('');
  
  // Estados para modales de confirmación
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deleteQuoteData, setDeleteQuoteData] = useState({ id: null, number: null });
  
  // Estados para modales de workflow (carga obligatoria de documentos)
  const [workflowModalOpen, setWorkflowModalOpen] = useState(false);
  const [workflowQuoteId, setWorkflowQuoteId] = useState(null);
  const [workflowConfig, setWorkflowConfig] = useState(null);

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
  // NOTA: Solo propaga cuando el usuario MANUALMENTE cambia el header, NO durante carga inicial
  useEffect(() => {
    // No propagar durante carga inicial de edición
    if (isLoadingEdit) {
      return;
    }
    
    const { cantidad_cajas, cantidad_bancos, setup_items, recurring_basic_items, recurring_other_items, additional_items } = quoteData;
    
    if (setup_items.length === 0 && recurring_basic_items.length === 0 && recurring_other_items.length === 0 && (additional_items || []).length === 0) {
      return; // No hay items para actualizar
    }
    
    let needsUpdate = false;
    const newCajas = cantidad_cajas || 1;
    const newBancos = cantidad_bancos || 1;
    
    // Actualizar Setup items
    // CAJAS: Se propaga a TODOS
    // BANCOS: Solo si NO tiene lockBancos ni autoBancos
    const updatedSetupItems = setup_items.map(item => {
      const shouldUpdateCajas = item.cantidad_cajas !== newCajas;
      const shouldUpdateBancos = !item.lockBancos && !item.autoBancos && item.cantidad_bancos !== newBancos;
      
      if (shouldUpdateCajas || shouldUpdateBancos) {
        needsUpdate = true;
        return { 
          ...item, 
          cantidad_cajas: newCajas,
          cantidad_bancos: (item.lockBancos || item.autoBancos) ? item.cantidad_bancos : newBancos
        };
      }
      return item;
    });
    
    // Actualizar Recurrentes Básicos
    // CAJAS: Se propaga a TODOS (incluyendo isAutoLinked)
    // BANCOS: Solo si NO tiene lockBancos y NO es isAutoLinked
    const updatedRecurringBasic = recurring_basic_items.map(item => {
      const shouldUpdateCajas = item.cantidad_cajas !== newCajas;
      const shouldUpdateBancos = !item.lockBancos && !item.isAutoLinked && item.cantidad_bancos !== newBancos;
      
      if (shouldUpdateCajas || shouldUpdateBancos) {
        needsUpdate = true;
        return { 
          ...item, 
          cantidad_cajas: newCajas,
          cantidad_bancos: (item.lockBancos || item.isAutoLinked) ? item.cantidad_bancos : newBancos
        };
      }
      return item;
    });
    
    // Actualizar Otros Recurrentes
    // CAJAS: Se propaga a TODOS
    // BANCOS: Solo si NO tiene lockBancos
    const updatedRecurringOther = recurring_other_items.map(item => {
      const shouldUpdateCajas = item.cantidad_cajas !== newCajas;
      const shouldUpdateBancos = !item.lockBancos && item.cantidad_bancos !== newBancos;
      
      if (shouldUpdateCajas || shouldUpdateBancos) {
        needsUpdate = true;
        return { 
          ...item, 
          cantidad_cajas: newCajas,
          cantidad_bancos: item.lockBancos ? item.cantidad_bancos : newBancos
        };
      }
      return item;
    });
    
    // Actualizar Items Adicionales (medios de pago)
    // CAJAS: Se propaga a TODOS (incluyendo isFromDB)
    // BANCOS: Solo si NO tiene isFromDB
    const updatedAdditionalItems = (additional_items || []).map(item => {
      const shouldUpdateCajas = item.cantidad_cajas !== newCajas;
      const shouldUpdateBancos = !item.isFromDB && item.cantidad_bancos !== newBancos;
      
      if (shouldUpdateCajas || shouldUpdateBancos) {
        needsUpdate = true;
        return { 
          ...item, 
          cantidad_cajas: newCajas,
          cantidad_bancos: item.isFromDB ? item.cantidad_bancos : newBancos
        };
      }
      return item;
    });
    
    if (needsUpdate) {
      setQuoteData(prev => ({
        ...prev,
        setup_items: updatedSetupItems,
        recurring_basic_items: updatedRecurringBasic,
        recurring_other_items: updatedRecurringOther,
        additional_items: updatedAdditionalItems
      }));
    }
  }, [quoteData.cantidad_cajas, quoteData.cantidad_bancos, isLoadingEdit]);

  const fetchData = async () => {
    try {
      const [quotesRes, clientsRes, banksRes, servicesRes, integratorsRes, hardwareRes, templatesRes, pgCostsRes] = await Promise.all([
        api.get('/quotes'),
        api.get('/clients'),
        api.get('/banks'),
        api.get('/services'), // Cargar catálogo de precios
        api.get('/integrators'), // Cargar integradores
        api.get('/hardware'), // Cargar dispositivos
        api.get('/config/templates').catch(() => ({ data: {} })), // Cargar estado de plantillas
        api.get('/pg-recurring-costs').catch(() => ({ data: null })) // Tabla costos recurrentes PG
      ]);
      setQuotes(quotesRes.data);
      setClients(clientsRes.data);
      setBanks(banksRes.data);
      setServiceCatalog(servicesRes.data);
      setIntegrators(integratorsRes.data);
      // Guardar todos los hardware
      setAllHardware(hardwareRes.data || []);
      // Filtrar solo dispositivos tipo "Pinpad" para cotizaciones de implementación
      const pinpadDevices = (hardwareRes.data || []).filter(hw => 
        hw.type?.toLowerCase() === 'pinpad'
      );
      setPinpads(pinpadDevices);
      // Guardar estado de plantillas disponibles
      setTemplateAvailable(templatesRes.data || {});
      // Tabla de costos recurrentes PG
      if (pgCostsRes.data) setPgRecurringCostsTable(pgCostsRes.data);
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
      case 'VPOS_MPOS': return 'vpos_available';
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
    // Resetear modo edición si estaba activo
    setIsEditing(false);
    setEditingQuoteId(null);
    setIsLoadingEdit(false);
    
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
    // Reset PG state
    setPgSetupItems([]);
    setPgTransactionRange(null);
    setPgSelectedMedioPago('');
    setPgSelectedBankId('');
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

  // Eliminar un concepto de Setup (ahora permite eliminar cualquier item)
  const removeSetupItem = (index) => {
    // Confirmar antes de eliminar
    if (!window.confirm('¿Está seguro de eliminar este concepto? Los totales se recalcularán automáticamente.')) {
      return;
    }
    
    setQuoteData({
      ...quoteData,
      setup_items: quoteData.setup_items.filter((_, i) => i !== index)
    });
    toast.success('Concepto eliminado. Los totales han sido recalculados.');
  };

  // Eliminar un concepto de Recurring Basic
  const removeRecurringBasicItem = (index) => {
    if (!window.confirm('¿Está seguro de eliminar este concepto? Los totales se recalcularán automáticamente.')) {
      return;
    }
    
    setQuoteData({
      ...quoteData,
      recurring_basic_items: quoteData.recurring_basic_items.filter((_, i) => i !== index)
    });
    toast.success('Concepto eliminado. Los totales han sido recalculados.');
  };

  // Eliminar un concepto de Recurring Other
  const removeRecurringOtherItem = (index) => {
    if (!window.confirm('¿Está seguro de eliminar este concepto? Los totales se recalcularán automáticamente.')) {
      return;
    }
    
    setQuoteData({
      ...quoteData,
      recurring_other_items: quoteData.recurring_other_items.filter((_, i) => i !== index)
    });
    toast.success('Concepto eliminado. Los totales han sido recalculados.');
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

  // === PG (Payment Gateway) Functions ===
  const addPgSetupItem = () => {
    if (!pgSelectedMedioPago) {
      toast.error('Seleccione un medio de pago');
      return;
    }
    // Check if already added
    if (pgSetupItems.some(item => item.concepto === pgSelectedMedioPago)) {
      toast.error('Este medio de pago ya fue agregado');
      return;
    }
    setPgSetupItems([...pgSetupItems, {
      concepto: pgSelectedMedioPago,
      costo: 0,
      banco: pgSelectedBankId ? (banks.find(b => b.bank_id === pgSelectedBankId)?.name || 'N/A') : 'N/A',
      observacion: ''
    }]);
    setPgSelectedMedioPago('');
    setPgSelectedBankId('');
    toast.success('Medio de pago agregado al setup');
  };

  const updatePgSetupItem = (index, field, value) => {
    const updated = [...pgSetupItems];
    updated[index] = { ...updated[index], [field]: field === 'costo' ? (parseFloat(value) || 0) : value };
    setPgSetupItems(updated);
  };

  const removePgSetupItem = (index) => {
    setPgSetupItems(pgSetupItems.filter((_, i) => i !== index));
  };

  const pgSetupTotal = pgSetupItems.reduce((sum, item) => sum + (item.costo || 0), 0);

  // Calculate PG recurring cost based on number of products and transaction range
  const getPgRecurringCost = () => {
    if (!pgRecurringCostsTable || pgTransactionRange === null || pgSetupItems.length === 0) return null;
    const numProducts = Math.min(pgSetupItems.length, 11);
    const rangeData = pgRecurringCostsTable.data.find(d => d.rango === pgTransactionRange);
    if (!rangeData) return null;
    const costData = rangeData[String(numProducts)];
    if (!costData) return null;
    const rangeInfo = pgRecurringCostsTable.ranges.find(r => r.rango === pgTransactionRange);
    return { ...costData, rango_label: rangeInfo?.label || '', num_products: numProducts, rango_index: pgTransactionRange };
  };

  const pgRecurringCost = getPgRecurringCost();

  // Get all gateway-available medios de pago from all banks
  const allGatewayMediosPago = (() => {
    const seen = new Set();
    const result = [];
    banks.forEach(bank => {
      (bank.products || []).forEach(product => {
        if (product.gateway_available && !seen.has(product.product_name)) {
          seen.add(product.product_name);
          result.push(product);
        }
      });
    });
    return result;
  })();

  // PG Submit handler
  const handleSubmitPGQuote = async () => {
    if (pgSetupItems.length === 0) {
      toast.error('Agregue al menos un concepto de setup');
      return;
    }
    if (!quoteData.client_id || !quoteData.integrator_id) {
      toast.error('Complete los campos obligatorios: Cliente e Integrador');
      return;
    }

    const toastId = toast.loading('Guardando cotización Payment Gateway...');
    try {
      const client = clients.find(c => c.client_id === quoteData.client_id);
      const integrator = integrators.find(i => i.integrator_id === quoteData.integrator_id);

      const payload = {
        client_id: quoteData.client_id,
        quote_category: 'implementation',
        quote_type: 'GATEWAY',
        pricing_model: 'conventional',
        services: [],
        hardware: [],
        equipment_items: [],
        notes: quoteData.notes,
        integrator_id: quoteData.integrator_id,
        integrator_name: integrator?.name || '',
        integrator_app_name: quoteData.integrator_app_name,
        cantidad_cajas: 1,
        cantidad_bancos: 1,
        pg_setup_items: pgSetupItems,
        pg_recurring_cost: pgRecurringCost ? {
          rango_index: pgRecurringCost.rango_index,
          num_products: pgRecurringCost.num_products,
          base: pgRecurringCost.base,
          tope: pgRecurringCost.tope,
          rango_label: pgRecurringCost.rango_label
        } : null,
        pg_transaction_range: pgTransactionRange,
        pdf_data: null
      };

      await api.post('/quotes/create-with-pdf', payload);
      toast.dismiss(toastId);
      toast.success('Cotización Payment Gateway creada exitosamente');
      setWizardOpen(false);
      resetQuoteForm();
      fetchData();
    } catch (error) {
      toast.dismiss(toastId);
      console.error('Error creating PG quote:', error);
      toast.error('Error al crear cotización Payment Gateway');
    }
  };

  const handleSubmitQuote = async () => {
    // Si estamos editando, usar la función de edición
    if (isEditing && editingQuoteId) {
      await handleSaveEditedQuote();
      return;
    }
    
    if (quoteData.setup_items.length === 0 && quoteData.recurring_basic_items.length === 0) {
      toast.error('No hay items en la cotización');
      return;
    }

    const toastId = toast.loading('Guardando cotización y generando PDF...');

    try {
      const client = clients.find(c => c.client_id === quoteData.client_id);
      const integrator = integrators.find(i => i.integrator_id === quoteData.integrator_id);
      const pinpad = pinpads.find(p => p.hardware_id === quoteData.pinpad_id);
      const sponsorBank = banks.find(b => b.bank_id === quoteData.sponsor_bank_id);

      const allItems = [
        ...quoteData.setup_items.map(item => ({
          item_type: 'setup',
          item_name: item.medio_pago_name || item.name,
          quantity: (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1),
          unit_price_usd: item.tarifa || item.unit_price_usd || 0,
          total_usd: item.total_usd || calcularTotal(item),
          cantidad_cajas: item.cantidad_cajas || 1,
          cantidad_bancos: item.cantidad_bancos || 1
        })),
        ...quoteData.recurring_basic_items.map(item => ({
          item_type: 'recurring_basic',
          item_name: item.medio_pago_name || item.name,
          quantity: (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1),
          unit_price_usd: item.tarifa || item.unit_price_usd || 0,
          total_usd: item.total_usd || calcularTotal(item),
          cantidad_cajas: item.cantidad_cajas || 1,
          cantidad_bancos: item.cantidad_bancos || 1
        })),
        ...quoteData.recurring_other_items.map(item => ({
          item_type: 'recurring_other',
          item_name: item.medio_pago_name || item.name,
          quantity: (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1),
          unit_price_usd: item.tarifa || item.unit_price_usd || 0,
          total_usd: item.total_usd || calcularTotal(item),
          cantidad_cajas: item.cantidad_cajas || 1,
          cantidad_bancos: item.cantidad_bancos || 1
        })),
        ...quoteData.additional_items.map(item => ({
          item_type: 'additional',
          item_name: item.medio_pago_name || item.name,
          quantity: (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1),
          unit_price_usd: (item.tarifa_setup || 0) + (item.tarifa_recurrente || 0) || item.unit_price_usd || 0,
          total_usd: item.total_usd || ((item.tarifa_setup || 0) * (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1) + 
                     (item.tarifa_recurrente || 0) * (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1)),
          cantidad_cajas: item.cantidad_cajas || 1,
          cantidad_bancos: item.cantidad_bancos || 1,
          bank_id: item.bank_id || '',
          bank_name: item.bank_name || '',
          tarifa_setup: item.tarifa_setup || 0,
          tarifa_recurrente: item.tarifa_recurrente || 0
        }))
      ];

      // Preparar datos del PDF (mismos datos que exportCurrentQuoteToPDF)
      const templateTypeMap = {
        'VPOS': 'vpos_pyme',
        'VPOS_MPOS': 'vpos_pyme',
        'GATEWAY': 'payment_gateway',
        'MPOS': 'mpos',
        'LINK': 'vpos_pyme'
      };
      const templateType = templateTypeMap[quoteData.quote_type] || 'vpos_pyme';

      const pdfData = {
        cliente_nombre: client?.legal_name || client?.commercial_name || 'Cliente',
        cliente_rif: client?.rif || '',
        cliente_contacto: client?.contact_name || '',
        cliente_address: client?.address || '',
        quote_type: quoteData.quote_type,
        pricing_model: quoteData.pricing_model,
        cantidad_cajas: quoteData.cantidad_cajas || 1,
        quote_number: '', // Se asignará en el backend
        integrator_name: integrator?.name || '',
        integrator_app_name: quoteData.integrator_app_name || '',
        pinpad_model: pinpad?.name || '',
        sponsor_bank_name: sponsorBank?.name || '',
        template_type: templateType,
        setup_items: [
          ...quoteData.setup_items.map(item => ({
            concepto: item.medio_pago_name,
            cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
            cantidad_bancos: item.lockBancos ? 1 : (parseInt(item.cantidad_bancos) || 1),
            tarifa: parseFloat(item.tarifa) || 0,
            bank_name: item.bank_name || null
          })),
          ...quoteData.additional_items.filter(i => i.tarifa_setup > 0).map(item => ({
            concepto: `${item.medio_pago_name} - ${item.bank_name}`,
            cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
            cantidad_bancos: parseInt(item.cantidad_bancos) || 1,
            tarifa: parseFloat(item.tarifa_setup) || 0,
            bank_name: item.bank_name || null
          }))
        ],
        recurring_basic_items: quoteData.recurring_basic_items.map(item => ({
          concepto: item.medio_pago_name + (item.linkedTo ? ` (vinculado a ${item.linkedTo})` : ''),
          cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
          cantidad_bancos: item.lockBancos ? 1 : (parseInt(item.cantidad_bancos) || 1),
          tarifa: parseFloat(item.tarifa) || 0,
          bank_name: item.bank_name || null
        })),
        recurring_other_items: quoteData.recurring_other_items.map(item => ({
          concepto: item.medio_pago_name,
          cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
          cantidad_bancos: item.lockBancos ? 1 : (parseInt(item.cantidad_bancos) || 1),
          tarifa: parseFloat(item.tarifa) || 0,
          bank_name: item.bank_name || null
        })),
        additional_items: quoteData.additional_items
          .filter(item => item.bank_name)
          .map(item => ({
            concepto: item.medio_pago_name,
            cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
            cantidad_bancos: parseInt(item.cantidad_bancos) || 1,
            tarifa: parseFloat(item.tarifa_setup) || 0,
            bank_name: item.bank_name
          })),
        descuento: quoteData.descuento || 0,
        notes: quoteData.notes || ''
      };

      const payload = {
        client_id: quoteData.client_id,
        quote_type: quoteData.quote_type,
        pricing_model: quoteData.pricing_model,
        services: allItems,
        hardware: [],
        integrator_id: quoteData.integrator_id,
        integrator_name: integrator?.name || '',
        integrator_app_name: quoteData.integrator_app_name,
        pinpad_id: quoteData.pinpad_id === 'none' ? '' : quoteData.pinpad_id,
        pinpad_model: quoteData.pinpad_id && quoteData.pinpad_id !== 'none' ? (pinpad?.name || '') : '',
        sponsor_bank_id: quoteData.sponsor_bank_id === 'none' ? '' : quoteData.sponsor_bank_id,
        sponsor_bank_name: quoteData.sponsor_bank_id && quoteData.sponsor_bank_id !== 'none' ? (sponsorBank?.name || '') : '',
        notes: quoteData.notes,
        cantidad_cajas: quoteData.cantidad_cajas || 1,
        cantidad_bancos: quoteData.cantidad_bancos || 1,
        // Incluir datos del PDF
        pdf_data: pdfData
      };

      const response = await api.post('/quotes/create-with-pdf', payload);
      toast.dismiss(toastId);
      
      if (response.data.pdf_url) {
        toast.success('Cotización creada con PDF generado');
      } else {
        toast.success('Cotización creada exitosamente');
      }
      
      setWizardOpen(false);
      resetQuoteForm();
      fetchData();
    } catch (error) {
      toast.dismiss(toastId);
      console.error('Error creating quote:', error);
      toast.error('Error al crear cotización');
    }
  };

  const downloadPDF = async (quoteId) => {
    const toastId = toast.loading('Generando PDF...');
    
    try {
      // Obtener token de autenticación
      const token = localStorage.getItem('session_token');
      if (!token) {
        toast.dismiss(toastId);
        toast.error('Sesión expirada. Por favor, inicie sesión nuevamente');
        return;
      }
      
      const backendUrl = process.env.REACT_APP_BACKEND_URL;
      const pdfUrl = `${backendUrl}/api/quotes/${quoteId}/pdf`;
      
      console.log('[PDF Download] Iniciando descarga:', pdfUrl);
      
      // Usar fetch nativo para mejor control de la descarga
      const response = await fetch(pdfUrl, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Accept': 'application/pdf'
        }
      });
      
      console.log('[PDF Download] Response status:', response.status);
      
      // Verificar respuesta
      if (!response.ok) {
        toast.dismiss(toastId);
        if (response.status === 404) {
          toast.error('Cotización no encontrada');
        } else if (response.status === 401) {
          toast.error('Sesión expirada. Por favor, inicie sesión nuevamente');
          localStorage.removeItem('session_token');
          window.location.href = '/login';
        } else {
          const errorText = await response.text();
          try {
            const errorData = JSON.parse(errorText);
            toast.error(errorData.detail || 'Error al generar PDF');
          } catch {
            toast.error(`Error del servidor: ${response.status}`);
          }
        }
        return;
      }
      
      // Verificar Content-Type
      const contentType = response.headers.get('content-type');
      console.log('[PDF Download] Content-Type:', contentType);
      
      if (!contentType || !contentType.includes('application/pdf')) {
        toast.dismiss(toastId);
        toast.error('El servidor no devolvió un PDF válido');
        console.error('[PDF Download] Content-Type inválido:', contentType);
        return;
      }
      
      // Obtener el blob
      const blob = await response.blob();
      console.log('[PDF Download] Blob recibido:', { size: blob.size, type: blob.type });
      
      if (blob.size === 0) {
        toast.dismiss(toastId);
        toast.error('El archivo PDF está vacío');
        return;
      }
      
      // Obtener nombre del archivo del header
      const contentDisposition = response.headers.get('content-disposition');
      let filename = `cotizacion_${quoteId}.pdf`;
      if (contentDisposition) {
        const match = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (match && match[1]) {
          filename = match[1].replace(/['"]/g, '');
        }
      }
      
      console.log('[PDF Download] Filename:', filename);
      
      // Crear URL del blob
      const blobUrl = window.URL.createObjectURL(blob);
      
      // Crear elemento de descarga
      const downloadLink = document.createElement('a');
      downloadLink.href = blobUrl;
      downloadLink.download = filename;
      
      // Estilos para ocultar pero mantener funcional
      downloadLink.style.position = 'fixed';
      downloadLink.style.left = '-9999px';
      downloadLink.style.top = '-9999px';
      downloadLink.style.visibility = 'hidden';
      
      // Añadir al DOM
      document.body.appendChild(downloadLink);
      
      // Usar setTimeout para asegurar que el elemento esté en el DOM
      await new Promise(resolve => setTimeout(resolve, 100));
      
      // Disparar el click
      downloadLink.click();
      
      console.log('[PDF Download] Click disparado');
      
      // Esperar un poco antes de limpiar para asegurar que la descarga inicie
      setTimeout(() => {
        if (document.body.contains(downloadLink)) {
          document.body.removeChild(downloadLink);
        }
        window.URL.revokeObjectURL(blobUrl);
        console.log('[PDF Download] Limpieza completada');
      }, 3000);
      
      // Mostrar éxito
      toast.dismiss(toastId);
      toast.success(`PDF "${filename}" descargado`);
      
    } catch (error) {
      toast.dismiss(toastId);
      console.error('[PDF Download] Error:', error);
      toast.error('Error al descargar el PDF. Verifique su conexión.');
    }
  };

  // Exportar cotización actual a PDF (sin guardar en BD)
  const exportCurrentQuoteToPDF = async () => {
    const client = clients.find(c => c.client_id === quoteData.client_id);
    if (!client) {
      toast.error('Seleccione un cliente');
      return;
    }

    // Obtener datos de integración y hardware
    const integrator = integrators.find(i => i.integrator_id === quoteData.integrator_id);
    const pinpad = pinpads.find(p => p.hardware_id === quoteData.pinpad_id);
    const sponsorBank = banks.find(b => b.bank_id === quoteData.sponsor_bank_id);

    // Determinar tipo de plantilla según el tipo de cotización
    const templateTypeMap = {
      'VPOS': 'vpos_pyme',
      'VPOS_MPOS': 'vpos_pyme',
      'GATEWAY': 'payment_gateway',
      'MPOS': 'mpos',
      'LINK': 'vpos_pyme'
    };
    const templateType = templateTypeMap[quoteData.quote_type] || 'vpos_pyme';
    const hasTemplate = templateAvailable[templateType]?.exists;

    // Preparar datos para el PDF
    const pdfData = {
      cliente_nombre: client.legal_name || client.commercial_name || 'Cliente',
      cliente_rif: client.rif || '',
      cliente_contacto: client.contact_name || '',  // Persona de contacto
      cliente_address: client.address || '',  // Dirección fiscal para el resumen
      quote_type: quoteData.quote_type,
      pricing_model: quoteData.pricing_model,
      cantidad_cajas: quoteData.cantidad_cajas || 1,  // Total de cajas para el resumen
      quote_number: editingQuoteId ? quotes.find(q => q.quote_id === editingQuoteId)?.quote_number : '',
      // Nuevos campos de integración y hardware
      integrator_name: integrator?.name || '',
      integrator_app_name: quoteData.integrator_app_name || '',
      pinpad_model: pinpad?.name || '',
      sponsor_bank_name: sponsorBank?.name || '',
      template_type: templateType,
      setup_items: [
        ...quoteData.setup_items.map(item => ({
          concepto: item.medio_pago_name,
          cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
          cantidad_bancos: item.lockBancos ? 1 : (parseInt(item.cantidad_bancos) || 1),
          tarifa: parseFloat(item.tarifa) || 0,
          bank_name: item.bank_name || null
        })),
        ...quoteData.additional_items.filter(i => i.tarifa_setup > 0).map(item => ({
          concepto: `${item.medio_pago_name} - ${item.bank_name}`,
          cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
          cantidad_bancos: parseInt(item.cantidad_bancos) || 1,
          tarifa: parseFloat(item.tarifa_setup) || 0,
          bank_name: item.bank_name || null
        }))
      ],
      recurring_basic_items: quoteData.recurring_basic_items.map(item => ({
        concepto: item.medio_pago_name + (item.linkedTo ? ` (vinculado a ${item.linkedTo})` : ''),
        cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
        cantidad_bancos: item.lockBancos ? 1 : (parseInt(item.cantidad_bancos) || 1),
        tarifa: parseFloat(item.tarifa) || 0,
        bank_name: item.bank_name || null
      })),
      recurring_other_items: quoteData.recurring_other_items.map(item => ({
        concepto: item.medio_pago_name,
        cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
        cantidad_bancos: item.lockBancos ? 1 : (parseInt(item.cantidad_bancos) || 1),
        tarifa: parseFloat(item.tarifa) || 0,
        bank_name: item.bank_name || null
      })),
      // additional_items separado para el Resumen Ejecutivo (solo items con bank_name)
      additional_items: quoteData.additional_items
        .filter(item => item.bank_name)
        .map(item => ({
          concepto: item.medio_pago_name,
          cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
          cantidad_bancos: parseInt(item.cantidad_bancos) || 1,
          tarifa: parseFloat(item.tarifa_setup) || 0,
          bank_name: item.bank_name
        })),
      descuento: quoteData.descuento || 0,
      notes: quoteData.notes || ''
    };

    try {
      const toastId = toast.loading(hasTemplate && useTemplateForPDF 
        ? 'Generando PDF con plantilla...' 
        : 'Generando PDF...');
      
      // Obtener token de autenticación
      const token = localStorage.getItem('session_token');
      if (!token) {
        toast.dismiss(toastId);
        toast.error('Sesión expirada. Por favor, inicie sesión nuevamente');
        return;
      }
      
      const backendUrl = process.env.REACT_APP_BACKEND_URL;
      
      // Decidir qué endpoint usar
      const endpoint = (hasTemplate && useTemplateForPDF) 
        ? '/api/quotes/generate-pdf-with-template'
        : '/api/quotes/generate-pdf';
      
      // Usar fetch nativo para mejor control
      const response = await fetch(`${backendUrl}${endpoint}`, {
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
        toast.dismiss(toastId);
        const errorText = await response.text();
        try {
          const errorData = JSON.parse(errorText);
          toast.error(errorData.detail || 'Error al generar PDF');
        } catch {
          toast.error(`Error del servidor: ${response.status}`);
        }
        return;
      }
      
      // Verificar Content-Type
      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/pdf')) {
        toast.dismiss(toastId);
        toast.error('El servidor no devolvió un PDF válido');
        return;
      }
      
      // Obtener el blob
      const blob = await response.blob();
      
      if (blob.size === 0) {
        toast.dismiss(toastId);
        toast.error('El archivo PDF está vacío');
        return;
      }
      
      // Nombre del archivo
      const filename = `cotizacion_${client.legal_name?.replace(/\s+/g, '_') || 'cliente'}_${new Date().toISOString().split('T')[0]}.pdf`;
      
      // Crear URL del blob y descargar
      const blobUrl = window.URL.createObjectURL(blob);
      
      // Crear elemento de descarga
      const downloadLink = document.createElement('a');
      downloadLink.href = blobUrl;
      downloadLink.download = filename;
      downloadLink.style.display = 'none';
      
      // Añadir al DOM, hacer clic y remover
      document.body.appendChild(downloadLink);
      downloadLink.click();
      
      // Limpiar después de un delay
      setTimeout(() => {
        if (downloadLink.parentNode) {
          document.body.removeChild(downloadLink);
        }
        window.URL.revokeObjectURL(blobUrl);
      }, 250);
      
      toast.dismiss(toastId);
      toast.success(hasTemplate && useTemplateForPDF 
        ? 'PDF con plantilla descargado exitosamente' 
        : 'PDF descargado exitosamente');
    } catch (error) {
      toast.dismiss();
      console.error('Error generating PDF:', error);
      toast.error('Error al generar el PDF. Verifique su conexión.');
    }
  };

  const getQuoteTypeName = (typeId) => {
    if (typeId === 'VPOS' || typeId === 'MPOS' || typeId === 'VPOS_MPOS') return 'VPOS/MPOS (Cajas y Tablet)';
    const type = QUOTE_TYPES.find(t => t.id === typeId);
    return type ? type.name : typeId;
  };

  const getPricingModelName = (modelId) => {
    const model = PRICING_MODELS.find(m => m.id === modelId);
    return model ? model.name : modelId;
  };

  // === FUNCIONES DE ACCIONES DE COTIZACIÓN ===
  
  // Enviar al cliente
  const handleSendToClient = async (quoteId) => {
    setActionLoading(quoteId);
    try {
      const response = await api.post(`/quotes/${quoteId}/send-to-client`);
      
      if (response.data.status === 'simulated') {
        toast.warning(response.data.message);
      } else {
        toast.success(response.data.message);
      }
      
      fetchData(); // Recargar lista
    } catch (error) {
      console.error('Error sending to client:', error);
      toast.error(error.response?.data?.detail || 'Error al enviar al cliente');
    } finally {
      setActionLoading(null);
    }
  };

  // Abrir modal de confirmación para eliminar
  const openDeleteConfirm = (quoteId, quoteNumber) => {
    console.log('ABRIR MODAL ELIMINAR:', quoteId, quoteNumber);
    setDeleteQuoteData({ id: quoteId, number: quoteNumber });
    setDeleteConfirmOpen(true);
  };

  // Ejecutar eliminación después de confirmación
  const executeDeleteQuote = async () => {
    const { id: quoteId, number: quoteNumber } = deleteQuoteData;
    setDeleteConfirmOpen(false);
    
    if (!quoteId) return;
    
    setActionLoading(quoteId);
    
    try {
      const response = await api.delete(`/quotes/${quoteId}`);
      toast.success(response.data.message || `Cotización ${quoteNumber} eliminada exitosamente`);
      await fetchData();
    } catch (error) {
      console.error('Error deleting quote:', error);
      
      let errorMessage = 'Error al eliminar la cotización';
      if (error.response?.status === 401) {
        errorMessage = 'Sesión expirada. Por favor, vuelva a iniciar sesión.';
        toast.error(errorMessage);
      } else if (error.response?.status === 404) {
        errorMessage = 'La cotización ya no existe o fue eliminada.';
        toast.error(errorMessage);
        await fetchData();
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
        toast.error(errorMessage);
      } else {
        toast.error(errorMessage);
      }
    } finally {
      setActionLoading(null);
      setDeleteQuoteData({ id: null, number: null });
    }
  };

  // Abrir modal de confirmación para aprobar
  // Abrir modal de workflow para Aprobar (requiere Orden de Compra)
  const openApproveConfirm = (quoteId) => {
    console.log('ABRIR WORKFLOW APROBAR:', quoteId);
    setWorkflowQuoteId(quoteId);
    setWorkflowConfig({
      title: 'Aprobar Cotización',
      description: 'Para aprobar esta cotización, debe cargar la Orden de Compra del cliente. Este documento es obligatorio para continuar.',
      category: 'Orden de Compra',
      acceptMultiple: false,
      acceptTypes: '.pdf,.doc,.docx,.xlsx,.xls,.png,.jpg,.jpeg',
      actionLabel: 'Aprobar',
      actionColor: 'bg-green-600 hover:bg-green-700',
      actionIcon: <CheckCircle size={20} className="text-green-600" />,
      stateEndpoint: 'approve',
      successMessage: 'Cotización aprobada exitosamente',
    });
    setWorkflowModalOpen(true);
  };

  // Abrir modal de workflow para Cobrar (requiere Comprobante de Pago - múltiple)
  const openCollectConfirm = (quoteId) => {
    console.log('ABRIR WORKFLOW COBRAR:', quoteId);
    setWorkflowQuoteId(quoteId);
    setWorkflowConfig({
      title: 'Registrar Cobro',
      description: 'Para registrar el cobro, debe cargar el/los comprobante(s) de pago. Puede subir múltiples archivos si el cliente pagó con diferentes métodos.',
      category: 'Pagos',
      acceptMultiple: true,
      acceptTypes: '.pdf,.png,.jpg,.jpeg,.doc,.docx',
      actionLabel: 'Confirmar Cobro',
      actionColor: 'bg-emerald-600 hover:bg-emerald-700',
      actionIcon: <Banknote size={20} className="text-emerald-600" />,
      stateEndpoint: 'collect',
      successMessage: 'Cotización marcada como Pagada',
    });
    setWorkflowModalOpen(true);
  };

  const handleWorkflowSuccess = () => {
    setWorkflowModalOpen(false);
    setWorkflowQuoteId(null);
    setWorkflowConfig(null);
    fetchData();
  };

  // Enviar a implementación
  const handleSendToImplementation = async (quoteId) => {
    setActionLoading(quoteId);
    try {
      const response = await api.post(`/quotes/${quoteId}/send-to-implementation`);
      
      if (response.data.status === 'simulated') {
        toast.warning(response.data.message);
      } else {
        toast.success(response.data.message);
      }
      
      fetchData();
    } catch (error) {
      console.error('Error sending to implementation:', error);
      toast.error(error.response?.data?.detail || 'Error al enviar a implementación');
    } finally {
      setActionLoading(null);
    }
  };

  // Modificar cotización (abrir wizard con datos precargados)
  const handleEditQuote = async (quote) => {
    // Solo permitir editar cotizaciones de implementación por ahora
    if (quote.quote_category === 'equipment') {
      toast.info('La edición de cotizaciones de equipos estará disponible próximamente');
      return;
    }
    
    // Función auxiliar para detectar si un concepto debe tener lockBancos
    // SOLO estos 5 conceptos muestran N/A:
    // - Derecho de uso de plataforma MServer por PDV (SIN "/ Banco")
    // - Configuración dispositivo (Pinpad o POS)
    // - Configuración PDV en MServer
    // - Comunicación Backend
    // - Procesamiento
    const shouldLockBancos = (itemName) => {
      const lowerName = itemName.toLowerCase();
      
      // EXCLUIR explícitamente "/ Banco" - este SÍ debe mostrar cantidad de bancos
      if (lowerName.includes('/ banco')) {
        return false;
      }
      
      // Solo estos conceptos tienen lockBancos
      const lockBancosNames = [
        'derecho de uso de plataforma mserver por pdv',
        'configuración dispositivo',
        'configuración pdv en mserver',
        'comunicación backend',
        'procesamiento'
      ];
      
      return lockBancosNames.some(name => lowerName.includes(name));
    };
    
    // Función auxiliar para detectar si un concepto tiene autoBancos
    const hasAutoBancos = (itemName) => {
      return itemName.toLowerCase().includes('medio de pago / banco');
    };
    
    // Obtener los servicios y mapear al formato del wizard
    const services = quote.services || [];
    
    // Mapear servicios al formato esperado por el wizard
    // Preservando lockBancos y autoBancos según el nombre del concepto
    // IMPORTANTE: Para items cargados desde BD durante edición:
    // - isDefault=true solo para conceptos base (los que están en las constantes)
    // - Los items auto-vinculados (isAutoLinked) NO deben tener propagación de header
    const mapService = (s, defaultConcept = null, isAutoLinkedItem = false) => {
      const itemName = s.item_name || s.name || '';
      const isLocked = defaultConcept?.lockBancos || shouldLockBancos(itemName);
      const isAuto = defaultConcept?.autoBancos || hasAutoBancos(itemName);
      
      // Solo es "default" si hay un concepto base que coincida y no es auto-vinculado
      const isBaseDefault = defaultConcept !== null && !isAutoLinkedItem;
      
      return {
        service_id: s.item_id || s.service_id || '',
        medio_pago_name: itemName,
        name: itemName,
        quantity: s.quantity || 1,
        tarifa: s.unit_price_usd || 0,
        unit_price_usd: s.unit_price_usd || 0,
        total_usd: s.total_usd || 0,
        cantidad_cajas: s.cantidad_cajas || s.quantity || 1,
        // Preservar cantidad_bancos original de la BD (excepto si lockBancos)
        cantidad_bancos: isLocked ? 1 : (s.cantidad_bancos || 1),
        isDefault: isBaseDefault,
        isAutoLinked: isAutoLinkedItem || s.isAutoLinked || false,
        lockBancos: isLocked,
        autoBancos: isAuto
      };
    };
    
    // Mapear items adicionales con campos específicos (bank_id, bank_name, tarifa_setup, tarifa_recurrente)
    // Los items adicionales SIEMPRE preservan sus valores originales de cantidad_bancos
    // Marcamos isFromDB=true para evitar que el useEffect los actualice
    const mapAdditionalItem = (s) => ({
      id: s.item_id || `additional_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      service_id: s.item_id || s.service_id || '',
      medio_pago_name: s.item_name || s.name || '',
      name: s.item_name || s.name || '',
      quantity: s.quantity || 1,
      // Campos específicos de items adicionales
      bank_id: s.bank_id || '',
      bank_name: s.bank_name || '',
      tarifa_setup: s.tarifa_setup || 0,
      tarifa_recurrente: s.tarifa_recurrente || 0,
      // Fallback: si no hay tarifa_setup/recurrente, usar unit_price_usd dividido
      unit_price_usd: s.unit_price_usd || 0,
      total_usd: s.total_usd || 0,
      // PRESERVAR valores originales de la BD
      cantidad_cajas: s.cantidad_cajas || s.quantity || 1,
      cantidad_bancos: s.cantidad_bancos || 1,
      isDefault: false,
      isAutoLinked: false,
      isFromDB: true, // Marca que viene de BD para evitar propagación automática
      lockBancos: false // Items adicionales nunca tienen lockBancos
    });
    
    // Filtrar por categoría (puede ser 'category' o 'item_type')
    const getCategory = (s) => s.category || s.item_type || '';
    
    // Mapear setup items preservando lockBancos
    const setupItems = services.filter(s => getCategory(s) === 'setup').map(s => {
      // Buscar concepto por defecto que coincida
      const concept = SETUP_CONCEPTS.find(c => 
        s.item_name?.toLowerCase().includes(c.name.toLowerCase().substring(0, 20)) ||
        c.name.toLowerCase().includes((s.item_name || '').toLowerCase().substring(0, 20))
      );
      return mapService(s, concept, false);
    });
    
    // Mapear recurrentes básicos preservando lockBancos
    // Detectar si es auto-vinculado: si el nombre contiene "Recurrente" pero NO tiene un concepto base exacto
    const recurringBasicItems = services.filter(s => getCategory(s) === 'recurring_basic').map(s => {
      const itemName = s.item_name || '';
      const concept = RECURRING_BASIC_CONCEPTS.find(c => 
        itemName.toLowerCase().includes(c.name.toLowerCase().substring(0, 20)) ||
        c.name.toLowerCase().includes(itemName.toLowerCase().substring(0, 20))
      );
      // Es auto-vinculado si fue agregado automáticamente (generalmente tiene isAutoLinked en BD)
      // o si su nombre contiene patrones típicos de items auto-vinculados
      const isAutoLinked = s.isAutoLinked || 
                          (itemName.includes('Recurrente') && !concept) ||
                          (itemName.includes('Suscripción') && !concept);
      return mapService(s, concept, isAutoLinked);
    });
    
    // Mapear otros recurrentes preservando lockBancos
    const recurringOtherItems = services.filter(s => getCategory(s) === 'recurring_other').map(s => {
      const concept = RECURRING_OTHER_CONCEPTS.find(c => 
        s.item_name?.toLowerCase().includes(c.name.toLowerCase().substring(0, 20)) ||
        c.name.toLowerCase().includes((s.item_name || '').toLowerCase().substring(0, 20))
      );
      return mapService(s, concept, false);
    });
    
    // Usar mapAdditionalItem para items adicionales
    const additionalItems = services.filter(s => getCategory(s) === 'additional').map(mapAdditionalItem);
    
    console.log('Loading quote for edit:', {
      quote_id: quote.quote_id,
      quote_type: quote.quote_type,
      client_id: quote.client_id,
      integrator_id: quote.integrator_id,
      pinpad_id: quote.pinpad_id,
      sponsor_bank_id: quote.sponsor_bank_id,
      cantidad_cajas_quote: quote.cantidad_cajas,
      cantidad_bancos_quote: quote.cantidad_bancos,
      services_count: services.length,
      setup: setupItems.length,
      recurring_basic: recurringBasicItems.length,
      recurring_other: recurringOtherItems.length,
      additional: additionalItems.length,
      // Log de lockBancos para debug
      setup_lockBancos: setupItems.map(i => ({ name: i.name, lockBancos: i.lockBancos, cantidad_bancos: i.cantidad_bancos })),
      recurring_lockBancos: recurringBasicItems.map(i => ({ name: i.name, lockBancos: i.lockBancos, cantidad_bancos: i.cantidad_bancos })),
      additional_bancos: additionalItems.map(i => ({ name: i.name, cantidad_bancos: i.cantidad_bancos }))
    });
    
    // Activar flag de carga para bloquear propagación automática
    setIsLoadingEdit(true);
    
    // Precargar datos de la cotización en el formulario
    // Los items mantienen sus valores originales de cantidad_bancos
    setQuoteData({
      quote_type: quote.quote_type || 'VPOS',
      client_id: quote.client_id || '',
      pricing_model: quote.pricing_model || 'conventional',
      cantidad_cajas: quote.cantidad_cajas || 1,
      cantidad_bancos: quote.cantidad_bancos || 1,
      integrator_id: quote.integrator_id || '',
      integrator_app_name: quote.integrator_app_name || '',
      pinpad_id: quote.pinpad_id || '',
      sponsor_bank_id: quote.sponsor_bank_id || '',
      setup_items: setupItems,
      recurring_basic_items: recurringBasicItems,
      recurring_other_items: recurringOtherItems,
      additional_items: additionalItems,
      descuento: quote.descuento || 0,
      notes: quote.notes || ''
    });
    
    // Desactivar flag después de un momento para permitir edición manual posterior
    setTimeout(() => {
      setIsLoadingEdit(false);
    }, 500);
    
    // Marcar como edición
    setEditingQuoteId(quote.quote_id);
    setIsEditing(true);
    
    // Abrir el wizard
    setWizardOpen(true);
    
    toast.info(`Editando cotización ${quote.quote_number}. Al guardar se creará una nueva versión.`);
  };

  // Función para crear nueva versión al guardar edición
  const handleSaveEditedQuote = async () => {
    if (!isEditing || !editingQuoteId) return;
    
    try {
      // Primero duplicar la cotización original
      const duplicateResponse = await api.post(`/quotes/${editingQuoteId}/duplicate`);
      const newQuoteId = duplicateResponse.data.new_quote_id;
      
      // Luego actualizar la nueva cotización con los datos editados
      const integrator = integrators.find(i => i.integrator_id === quoteData.integrator_id);
      const pinpad = pinpads.find(p => p.hardware_id === quoteData.pinpad_id);
      const sponsorBank = banks.find(b => b.bank_id === quoteData.sponsor_bank_id);
      
      // Combinar todos los servicios con el formato correcto
      // Incluir cantidad_cajas y cantidad_bancos para cada item
      const allServices = [
        ...quoteData.setup_items.map(item => ({ 
          item_type: 'setup',
          item_name: item.medio_pago_name || item.name || '',
          quantity: (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1),
          unit_price_usd: item.tarifa || item.unit_price_usd || 0,
          total_usd: item.total_usd || ((item.tarifa || item.unit_price_usd || 0) * (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1)),
          cantidad_cajas: item.cantidad_cajas || 1,
          cantidad_bancos: item.cantidad_bancos || 1
        })),
        ...quoteData.recurring_basic_items.map(item => ({ 
          item_type: 'recurring_basic',
          item_name: item.medio_pago_name || item.name || '',
          quantity: (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1),
          unit_price_usd: item.tarifa || item.unit_price_usd || 0,
          total_usd: item.total_usd || ((item.tarifa || item.unit_price_usd || 0) * (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1)),
          cantidad_cajas: item.cantidad_cajas || 1,
          cantidad_bancos: item.cantidad_bancos || 1
        })),
        ...quoteData.recurring_other_items.map(item => ({ 
          item_type: 'recurring_other',
          item_name: item.medio_pago_name || item.name || '',
          quantity: (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1),
          unit_price_usd: item.tarifa || item.unit_price_usd || 0,
          total_usd: item.total_usd || ((item.tarifa || item.unit_price_usd || 0) * (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1)),
          cantidad_cajas: item.cantidad_cajas || 1,
          cantidad_bancos: item.cantidad_bancos || 1
        })),
        ...quoteData.additional_items.map(item => ({ 
          item_type: 'additional',
          item_name: item.medio_pago_name || item.name || '',
          quantity: (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1),
          unit_price_usd: item.unit_price_usd || (item.tarifa_setup || 0) + (item.tarifa_recurrente || 0),
          total_usd: item.total_usd || ((item.tarifa_setup || 0) * (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1) + 
                     (item.tarifa_recurrente || 0) * (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1)),
          cantidad_cajas: item.cantidad_cajas || 1,
          cantidad_bancos: item.cantidad_bancos || 1,
          // Campos específicos para items adicionales
          bank_id: item.bank_id || '',
          bank_name: item.bank_name || '',
          tarifa_setup: item.tarifa_setup || 0,
          tarifa_recurrente: item.tarifa_recurrente || 0
        }))
      ];
      
      // Calcular totales
      const subtotal = allServices.reduce((sum, item) => sum + (item.total_usd || 0), 0);
      const total = subtotal - (quoteData.descuento || 0);
      
      // Actualizar la cotización duplicada
      await api.put(`/quotes/${newQuoteId}`, {
        quote_type: quoteData.quote_type,
        client_id: quoteData.client_id,
        pricing_model: quoteData.pricing_model,
        services: allServices,
        integrator_id: quoteData.integrator_id,
        integrator_name: integrator?.name || '',
        integrator_app_name: integrator?.app_name || quoteData.integrator_app_name || '',
        // Campos opcionales - enviar vacío si es "none"
        pinpad_id: quoteData.pinpad_id === 'none' ? '' : quoteData.pinpad_id,
        pinpad_model: quoteData.pinpad_id && quoteData.pinpad_id !== 'none' ? (pinpad?.name || '') : '',
        sponsor_bank_id: quoteData.sponsor_bank_id === 'none' ? '' : quoteData.sponsor_bank_id,
        sponsor_bank_name: quoteData.sponsor_bank_id && quoteData.sponsor_bank_id !== 'none' ? (sponsorBank?.name || '') : '',
        subtotal_usd: subtotal,
        total_usd: total,
        descuento: quoteData.descuento || 0,
        notes: quoteData.notes,
        cantidad_cajas: quoteData.cantidad_cajas || 1,
        cantidad_bancos: quoteData.cantidad_bancos || 1
      });
      
      toast.success(`Nueva versión ${duplicateResponse.data.new_quote_number} creada exitosamente`);
      
      // Limpiar estado de edición
      setIsEditing(false);
      setEditingQuoteId(null);
      setWizardOpen(false);
      resetQuoteForm();
      fetchData();
      
    } catch (error) {
      console.error('Error saving edited quote:', error);
      toast.error(error.response?.data?.detail || 'Error al guardar la cotización');
    }
  };

  // Reset del formulario
  const resetQuoteForm = () => {
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
    setIsEditing(false);
    setEditingQuoteId(null);
    // Reset PG state
    setPgSetupItems([]);
    setPgTransactionRange(null);
    setPgSelectedMedioPago('');
    setPgSelectedBankId('');
  };

  // Abrir modal de factura
  // Abrir modal de workflow para Facturar (requiere Factura)
  const openInvoiceModal = (quoteId) => {
    setWorkflowQuoteId(quoteId);
    setWorkflowConfig({
      title: 'Facturar Cotización',
      description: 'Para facturar esta cotización, debe cargar el documento fiscal (Factura). Este archivo se guardará automáticamente en los anexos.',
      category: 'Factura',
      acceptMultiple: false,
      acceptTypes: '.pdf,.doc,.docx,.xlsx,.xls,.png,.jpg,.jpeg',
      actionLabel: 'Facturar',
      actionColor: 'bg-purple-600 hover:bg-purple-700',
      actionIcon: <Receipt size={20} className="text-purple-600" />,
      stateEndpoint: 'invoice',
      successMessage: 'Cotización facturada exitosamente',
      extraFields: [
        { name: 'invoice_number', label: 'Número de Factura', placeholder: 'Ej: FAC-001234', required: false }
      ],
    });
    setWorkflowModalOpen(true);
  };

  // Entregar cotización (solo equipos)
  const handleDeliverQuote = async (quoteId) => {
    if (!window.confirm('¿Confirma que el pedido ha sido entregado?')) return;
    
    setActionLoading(quoteId);
    try {
      await api.post(`/quotes/${quoteId}/deliver`);
      toast.success('Cotización marcada como Entregada');
      fetchData();
    } catch (error) {
      console.error('Error delivering quote:', error);
      toast.error(error.response?.data?.detail || 'Error al marcar como entregada');
    } finally {
      setActionLoading(null);
    }
  };

  const selectedClient = clients.find(c => c.client_id === quoteData.client_id);
  const selectedIntegrator = integrators.find(i => i.integrator_id === quoteData.integrator_id);
  // Campos opcionales - no buscar si el valor es "none"
  const selectedPinpad = quoteData.pinpad_id && quoteData.pinpad_id !== 'none' 
    ? pinpads.find(p => p.hardware_id === quoteData.pinpad_id) 
    : null;
  const selectedSponsorBank = quoteData.sponsor_bank_id && quoteData.sponsor_bank_id !== 'none'
    ? banks.find(b => b.bank_id === quoteData.sponsor_bank_id)
    : null;
  
  // Detectar si es cotización Payment Gateway
  const isPaymentGateway = quoteData.quote_type === 'GATEWAY';
  
  // Validación completa incluyendo nuevos campos obligatorios
  // En modo edición, los campos de integración son opcionales ya que pueden no haber sido configurados originalmente
  const isHeaderComplete = isPaymentGateway 
    ? (quoteData.quote_type && quoteData.client_id && quoteData.integrator_id)
    : (quoteData.quote_type && 
       quoteData.client_id && 
       quoteData.pricing_model && 
       (quoteData.cantidad_cajas >= 1 || quoteData.cantidad_cajas === '') &&
       (isEditing || quoteData.integrator_id)); // Pinpad y Entidad Patrocinadora ahora son opcionales
  
  // En modo edición, siempre mostrar los items si existen
  const canShowItems = isEditing 
    ? (quoteData.quote_type && quoteData.client_id && quoteData.pricing_model)
    : isHeaderComplete;

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
          <div className="flex justify-between items-center mb-6">
            <div>
              <h1 className="text-4xl font-bold text-slate-900 font-manrope mb-2">Cotizaciones</h1>
              <p className="text-slate-600">Genere cotizaciones profesionales para sus clientes</p>
            </div>
          </div>

          {/* Botones de Nueva Cotización */}
          <div className="flex items-center gap-3 mb-6">
            <Button onClick={openWizard} data-testid="create-quote-button" className="bg-brand-green-600 hover:bg-brand-green-700 text-white">
              <Plus size={20} className="mr-2" />
              Nueva Implementación
            </Button>
            <Button onClick={() => setEquipmentWizardOpen(true)} data-testid="create-equipment-quote-button" className="bg-brand-blue-600 hover:bg-brand-blue-700 text-white">
              <Plus size={20} className="mr-2" />
              Nueva Cotización: Equipos, Accesorios y Reparaciones
            </Button>
          </div>

          {/* Filtros Rápidos */}
          <div className="bg-slate-50 rounded-lg p-4 mb-4 border border-slate-200">
            <div className="flex items-center gap-2 mb-3">
              <Filter size={18} className="text-slate-500" />
              <span className="font-medium text-slate-700">Filtros Rápidos</span>
              {(filterClient || filterStatus || filterCategory || filterDateFrom || filterDateTo) && (
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={() => {
                    setFilterClient('');
                    setFilterStatus('');
                    setFilterCategory('');
                    setFilterDateFrom('');
                    setFilterDateTo('');
                  }}
                  className="text-red-500 hover:text-red-700 ml-auto"
                  data-testid="clear-filters-btn"
                >
                  <X size={14} className="mr-1" />
                  Limpiar filtros
                </Button>
              )}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
              {/* Filtro por Cliente */}
              <div>
                <Label className="text-xs text-slate-500 mb-1 block">Cliente</Label>
                <Select value={filterClient} onValueChange={setFilterClient}>
                  <SelectTrigger className="h-9 bg-white" data-testid="filter-client">
                    <SelectValue placeholder="Todos los clientes" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todos los clientes</SelectItem>
                    {clients.map((client) => (
                      <SelectItem key={client.client_id} value={client.client_id}>
                        {client.fantasy_name || client.legal_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Filtro por Estado */}
              <div>
                <Label className="text-xs text-slate-500 mb-1 block">Estado</Label>
                <Select value={filterStatus} onValueChange={setFilterStatus}>
                  <SelectTrigger className="h-9 bg-white" data-testid="filter-status">
                    <SelectValue placeholder="Todos los estados" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todos los estados</SelectItem>
                    <SelectItem value="Borrador">Borrador</SelectItem>
                    <SelectItem value="Enviada">Enviada</SelectItem>
                    <SelectItem value="Aprobada">Aprobada</SelectItem>
                    <SelectItem value="Facturada">Facturada</SelectItem>
                    <SelectItem value="Pagada">Pagada</SelectItem>
                    <SelectItem value="Entregada">Entregada (Equipos)</SelectItem>
                    <SelectItem value="Enviada a Imple">Enviada a Imple</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Filtro por Categoría - Actualizado según nueva estructura */}
              <div>
                <Label className="text-xs text-slate-500 mb-1 block">Categoría</Label>
                <Select value={filterCategory} onValueChange={setFilterCategory}>
                  <SelectTrigger className="h-9 bg-white" data-testid="filter-category">
                    <SelectValue placeholder="Todas las categorías" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todas las categorías</SelectItem>
                    {QUOTE_FILTER_CATEGORIES.map((cat) => (
                      <SelectItem key={cat.id} value={cat.id}>{cat.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Filtro por Fecha Desde */}
              <div>
                <Label className="text-xs text-slate-500 mb-1 block">Desde</Label>
                <Input
                  type="date"
                  value={filterDateFrom}
                  onChange={(e) => setFilterDateFrom(e.target.value)}
                  className="h-9 bg-white"
                  data-testid="filter-date-from"
                />
              </div>

              {/* Filtro por Fecha Hasta */}
              <div>
                <Label className="text-xs text-slate-500 mb-1 block">Hasta</Label>
                <Input
                  type="date"
                  value={filterDateTo}
                  onChange={(e) => setFilterDateTo(e.target.value)}
                  className="h-9 bg-white"
                  data-testid="filter-date-to"
                />
              </div>
            </div>
          </div>

          {/* Panel de Gestión Único - Todas las Cotizaciones */}
          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <table className="w-full" data-testid="quotes-unified-table">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase">Número</th>
                  <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase">Categoría</th>
                  <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase">Tipo</th>
                  <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase">Cliente</th>
                  <th className="px-6 py-4 text-right text-sm font-medium text-slate-700 uppercase">Total USD</th>
                  <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase">Estado</th>
                  <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase">Fecha</th>
                  <th className="px-6 py-4 text-center text-sm font-medium text-slate-700 uppercase">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {quotes
                  .filter(quote => {
                    // Filtro por cliente
                    if (filterClient && filterClient !== 'all' && quote.client_id !== filterClient) return false;
                    
                    // Filtro por estado
                    if (filterStatus && filterStatus !== 'all' && (quote.quote_status || 'Borrador') !== filterStatus) return false;
                    
                    // Filtro por categoría
                    if (filterCategory && filterCategory !== 'all') {
                      const isEquipment = quote.quote_category === 'equipment';
                      if (filterCategory === 'equipment' && !isEquipment) return false;
                      if (filterCategory === 'implementation' && isEquipment) return false;
                    }
                    
                    // Filtro por fecha desde
                    if (filterDateFrom) {
                      const quoteDate = new Date(quote.created_at);
                      const fromDate = new Date(filterDateFrom);
                      if (quoteDate < fromDate) return false;
                    }
                    
                    // Filtro por fecha hasta
                    if (filterDateTo) {
                      const quoteDate = new Date(quote.created_at);
                      const toDate = new Date(filterDateTo);
                      toDate.setHours(23, 59, 59, 999); // Incluir todo el día
                      if (quoteDate > toDate) return false;
                    }
                    
                    return true;
                  })
                  .map((quote) => {
                  const client = clients.find(c => c.client_id === quote.client_id);
                  const statusColor = STATUS_COLORS[quote.quote_status] || STATUS_COLORS['Borrador'];
                  const isLoading = actionLoading === quote.quote_id;
                  const isEquipment = quote.quote_category === 'equipment';
                  
                  // Determinar el tipo a mostrar
                  const displayType = isEquipment 
                    ? (quote.equipment_type || 'Equipos')
                    : getQuoteTypeName(quote.quote_type);
                  
                  // Color de categoría
                  const categoryColor = isEquipment 
                    ? 'bg-amber-100 text-amber-700' 
                    : 'bg-green-100 text-green-700';
                  
                  // Color de tipo según si es equipo o implementación
                  const typeColor = isEquipment
                    ? (quote.equipment_type === 'POS' || quote.equipment_type === 'Pinpad' ? 'bg-blue-100 text-blue-700' : 'bg-amber-100 text-amber-700')
                    : 'bg-brand-blue-50 text-brand-blue-600';
                  
                  return (
                    <tr key={quote.quote_id} className="hover:bg-slate-50" data-testid={`quote-row-${quote.quote_id}`}>
                      <td className="px-6 py-4 text-sm font-mono font-medium text-slate-900">{quote.quote_number}</td>
                      <td className="px-6 py-4 text-sm">
                        <span className={`px-2 py-1 text-xs font-medium rounded ${categoryColor}`}>
                          {isEquipment ? 'Equipos' : 'Implementación'}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm">
                        <span className={`px-2 py-1 text-xs font-medium rounded ${typeColor}`}>
                          {displayType}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-900">{client?.fantasy_name || 'N/A'}</td>
                      <td className="px-6 py-4 text-sm font-mono text-right text-brand-green-600 font-semibold">${quote.total_usd?.toFixed(2) || '0.00'}</td>
                      <td className="px-6 py-4 text-sm">
                        <span className={`px-2 py-1 text-xs font-medium rounded ${statusColor}`}>
                          {STATUS_DISPLAY_NAMES[quote.quote_status] || 'Borrador'}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-600">{new Date(quote.created_at).toLocaleDateString('es-VE')}</td>
                      <td className="px-6 py-4">
                        <div className="flex items-center justify-center gap-2">
                          <Button 
                            size="sm" 
                            variant="outline" 
                            onClick={() => {
                              setAnexosQuoteId(quote.quote_id);
                              setAnexosQuoteNumber(quote.quote_number);
                              setAnexosOpen(true);
                            }}
                            className="text-brand-blue-600"
                            disabled={isLoading}
                            data-testid={`quote-anexos-btn-${quote.quote_id}`}
                          >
                            <FolderOpen size={16} className="mr-1" />Anexos
                          </Button>
                          
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button 
                                size="sm" 
                                variant="outline" 
                                className="px-2"
                                disabled={isLoading}
                                data-testid={`quote-actions-${quote.quote_id}`}
                              >
                                {isLoading ? (
                                  <div className="animate-spin h-4 w-4 border-2 border-slate-400 border-t-transparent rounded-full" />
                                ) : (
                                  <MoreHorizontal size={16} />
                                )}
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-56">
                              {/* Descargar PDF */}
                              <DropdownMenuItem 
                                onSelect={() => downloadPDF(quote.quote_id)}
                                className="cursor-pointer"
                              >
                                <Download size={16} className="mr-2 text-slate-500" />
                                Descargar PDF
                              </DropdownMenuItem>
                              
                              <DropdownMenuSeparator />
                              
                              {/* Modificar - Crea nueva versión */}
                              <DropdownMenuItem 
                                onSelect={() => handleEditQuote(quote)}
                                className="cursor-pointer"
                              >
                                <RefreshCw size={16} className="mr-2 text-slate-500" />
                                Modificar (Nueva Versión)
                              </DropdownMenuItem>
                              
                              <DropdownMenuSeparator />
                              
                              {/* Enviar al Cliente - Borrador -> Enviada */}
                              <DropdownMenuItem 
                                onSelect={() => handleSendToClient(quote.quote_id)}
                                className="cursor-pointer"
                                disabled={quote.quote_status !== 'Borrador'}
                              >
                                <Mail size={16} className="mr-2 text-blue-500" />
                                Enviar al Cliente
                                {quote.sent_to_client_at && (
                                  <span className="ml-auto text-xs text-slate-400">✓</span>
                                )}
                              </DropdownMenuItem>
                              
                              {/* Aprobar - Enviada -> Aprobada */}
                              <DropdownMenuItem 
                                onSelect={() => {
                                  console.log('SELECT APROBAR - quote_id:', quote.quote_id, 'status:', quote.quote_status);
                                  openApproveConfirm(quote.quote_id);
                                }}
                                className="cursor-pointer"
                                disabled={quote.quote_status !== 'Enviada'}
                              >
                                <CheckCircle size={16} className="mr-2 text-green-500" />
                                Aprobar
                                {quote.quote_status === 'Enviada' && <span className="ml-auto text-xs text-green-500">●</span>}
                              </DropdownMenuItem>
                              
                              {/* Facturar - Aprobada -> Facturada */}
                              <DropdownMenuItem 
                                onSelect={() => openInvoiceModal(quote.quote_id)}
                                className="cursor-pointer"
                                disabled={quote.quote_status !== 'Aprobada'}
                              >
                                <Receipt size={16} className="mr-2 text-purple-500" />
                                Facturar
                              </DropdownMenuItem>
                              
                              {/* Cobrar - Facturada -> Pagada */}
                              <DropdownMenuItem 
                                onSelect={() => {
                                  console.log('SELECT COBRAR - quote_id:', quote.quote_id, 'status:', quote.quote_status);
                                  openCollectConfirm(quote.quote_id);
                                }}
                                className="cursor-pointer"
                                disabled={quote.quote_status !== 'Facturada'}
                              >
                                <Banknote size={16} className="mr-2 text-emerald-500" />
                                Cobrar
                                {quote.quote_status === 'Facturada' && <span className="ml-auto text-xs text-emerald-500">●</span>}
                              </DropdownMenuItem>
                              
                              <DropdownMenuSeparator />
                              
                              {/* Acciones finales según categoría */}
                              {isEquipment ? (
                                <DropdownMenuItem 
                                  onSelect={() => handleDeliverQuote(quote.quote_id)}
                                  className="cursor-pointer"
                                  disabled={quote.quote_status !== 'Pagada'}
                                >
                                  <Truck size={16} className="mr-2 text-teal-500" />
                                  Marcar como Entregada
                                </DropdownMenuItem>
                              ) : (
                                <DropdownMenuItem 
                                  onSelect={() => handleSendToImplementation(quote.quote_id)}
                                  className="cursor-pointer"
                                  disabled={quote.quote_status !== 'Pagada'}
                                >
                                  <Send size={16} className="mr-2 text-amber-500" />
                                  Enviar a Implementación
                                </DropdownMenuItem>
                              )}
                              
                              <DropdownMenuSeparator />
                              
                              {/* Eliminar - Función de mantenimiento, disponible en cualquier estado */}
                              <DropdownMenuItem 
                                onSelect={() => {
                                  console.log('SELECT ELIMINAR - quote_id:', quote.quote_id, 'quote_number:', quote.quote_number);
                                  openDeleteConfirm(quote.quote_id, quote.quote_number);
                                }}
                                className="cursor-pointer text-red-600 hover:text-red-700 hover:bg-red-50"
                              >
                                <Trash2 size={16} className="mr-2" />
                                Eliminar Cotización
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {/* Mensaje cuando no hay cotizaciones o no hay resultados */}
            {(() => {
              const filteredQuotes = quotes.filter(quote => {
                if (filterClient && filterClient !== 'all' && quote.client_id !== filterClient) return false;
                if (filterStatus && filterStatus !== 'all' && (quote.quote_status || 'Borrador') !== filterStatus) return false;
                if (filterCategory && filterCategory !== 'all') {
                  const isEquipment = quote.quote_category === 'equipment';
                  if (filterCategory === 'equipment' && !isEquipment) return false;
                  if (filterCategory === 'implementation' && isEquipment) return false;
                }
                if (filterDateFrom) {
                  const quoteDate = new Date(quote.created_at);
                  const fromDate = new Date(filterDateFrom);
                  if (quoteDate < fromDate) return false;
                }
                if (filterDateTo) {
                  const quoteDate = new Date(quote.created_at);
                  const toDate = new Date(filterDateTo);
                  toDate.setHours(23, 59, 59, 999);
                  if (quoteDate > toDate) return false;
                }
                return true;
              });
              
              if (quotes.length === 0) {
                return (
                  <div className="text-center py-12 text-slate-500">
                    <FileText size={48} className="mx-auto mb-4 text-slate-300" />
                    <p>No hay cotizaciones registradas</p>
                    <p className="text-sm mt-2">Cree una cotización de Implementación o Equipos para comenzar</p>
                  </div>
                );
              } else if (filteredQuotes.length === 0) {
                return (
                  <div className="text-center py-12 text-slate-500">
                    <Search size={48} className="mx-auto mb-4 text-slate-300" />
                    <p>No se encontraron cotizaciones</p>
                    <p className="text-sm mt-2">Intente ajustar los filtros de búsqueda</p>
                    <Button 
                      variant="outline" 
                      className="mt-4"
                      onClick={() => {
                        setFilterClient('');
                        setFilterStatus('');
                        setFilterCategory('');
                        setFilterDateFrom('');
                        setFilterDateTo('');
                      }}
                    >
                      <X size={16} className="mr-2" />
                      Limpiar filtros
                    </Button>
                  </div>
                );
              }
              return null;
            })()}
          </div>

          {/* Dialog de Nueva Cotización */}
          <Dialog open={wizardOpen} onOpenChange={(open) => {
            if (!open) {
              // Al cerrar el dialog, resetear el modo edición
              setIsEditing(false);
              setEditingQuoteId(null);
            }
            setWizardOpen(open);
          }}>
            <DialogContent className="max-w-6xl max-h-[95vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle className="font-manrope text-2xl">
                  {isEditing ? 'Modificar Cotización (Nueva Versión)' : 'Nueva Cotización'}
                </DialogTitle>
                {isEditing && (
                  <p className="text-sm text-amber-600 bg-amber-50 px-3 py-2 rounded-lg mt-2">
                    Está editando una cotización existente. Al guardar se creará una nueva versión con número correlativo diferente.
                  </p>
                )}
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
                        setQuoteData({ ...quoteData, quote_type: value, medios_pago_items: [], pricing_model: value === 'GATEWAY' ? 'conventional' : '' });
                        setSelectedBankId('');
                        setSelectedMedioPagoId('');
                        setAvailableMediosPago([]);
                        // Reset PG state when changing type
                        setPgSetupItems([]);
                        setPgTransactionRange(null);
                      }}
                    >
                      <SelectTrigger data-testid="select-quote-type">
                        <SelectValue placeholder="Seleccione tipo..." />
                      </SelectTrigger>
                      <SelectContent>
                        {QUOTE_TYPES.filter(t => !t.disabled).map((type) => (
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

                  {/* Hide Modelo/Cajas/Bancos for Payment Gateway */}
                  {!isPaymentGateway && (
                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 block">
                      Modelo de Precios <span className="text-red-500">*</span>
                    </Label>
                    <Select 
                      value={quoteData.pricing_model} 
                      onValueChange={(value) => {
                        // Al seleccionar modelo, inicializar conceptos SOLO si no estamos en modo edición
                        // o si no hay items ya cargados
                        const cajas = quoteData.cantidad_cajas || 1;
                        const bancos = quoteData.cantidad_bancos || 1;
                        
                        // Si estamos editando y ya hay items, mantenerlos
                        if (isEditing && (quoteData.setup_items.length > 0 || quoteData.recurring_basic_items.length > 0)) {
                          setQuoteData({ 
                            ...quoteData, 
                            pricing_model: value
                          });
                        } else {
                          // Nueva cotización: inicializar conceptos desde el catálogo
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
                        }
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
                  {/* End conditional for non-PG fields */}
                  )}
                </div>

                {isHeaderComplete && (
                  <div className="mt-4 p-3 bg-brand-green-50 border border-brand-green-200 rounded-lg flex items-center gap-2">
                    <CheckCircle2 size={18} className="text-brand-green-600" />
                    <span className="text-sm text-brand-green-700 font-medium">
                      {getQuoteTypeName(quoteData.quote_type)} • {selectedClient?.fantasy_name}
                      {!isPaymentGateway && <> • {getPricingModelName(quoteData.pricing_model)} • {quoteData.cantidad_cajas} cajas • {quoteData.cantidad_bancos} bancos</>}
                    </span>
                  </div>
                )}
              </div>

              {/* SECCIÓN 1.5: Detalles de Integración y Hardware */}
              <div className="bg-gradient-to-r from-slate-50 to-blue-50 rounded-lg p-5 border border-blue-100 mt-4">
                <h3 className="font-semibold text-lg text-slate-800 mb-4 flex items-center gap-2">
                  <Cpu size={20} className="text-brand-blue-600" />
                  Detalles de Integración y Hardware
                </h3>
                
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  {/* Campo 1: Integrador */}
                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 flex items-center gap-2">
                      <Users size={14} className="text-brand-blue-600" />
                      Integrador <span className="text-red-500">*</span>
                    </Label>
                    <Select 
                      value={quoteData.integrator_id} 
                      onValueChange={handleIntegratorChange}
                    >
                      <SelectTrigger data-testid="select-integrator">
                        <SelectValue placeholder="Seleccione integrador..." />
                      </SelectTrigger>
                      <SelectContent>
                        {integrators.filter(i => i.integrator_status === 'Certificado').map((integrator) => (
                          <SelectItem key={integrator.integrator_id} value={integrator.integrator_id}>
                            {integrator.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Campo Informativo: Aplicativo */}
                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 block">
                      Aplicativo Certificado
                    </Label>
                    <div className="h-10 px-3 py-2 bg-slate-100 border border-slate-200 rounded-md flex items-center">
                      <span className={`text-sm ${quoteData.integrator_app_name ? 'text-slate-900 font-medium' : 'text-slate-400'}`}>
                        {quoteData.integrator_app_name || 'Se completa al seleccionar integrador'}
                      </span>
                    </div>
                  </div>

                  {/* Campo 2: Modelo de Pinpad (Opcional) */}
                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 flex items-center gap-2">
                      <Cpu size={14} className="text-brand-green-600" />
                      Modelo de Pinpad <span className="text-slate-400 text-xs font-normal">(Opcional)</span>
                    </Label>
                    <Select 
                      value={quoteData.pinpad_id} 
                      onValueChange={(value) => setQuoteData({ ...quoteData, pinpad_id: value })}
                    >
                      <SelectTrigger data-testid="select-pinpad">
                        <SelectValue placeholder="Seleccione modelo..." />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">Sin Pinpad</SelectItem>
                        {pinpads.length === 0 ? (
                          <SelectItem value="no-pinpads" disabled>No hay Pinpads disponibles</SelectItem>
                        ) : (
                          pinpads.map((pinpad) => (
                            <SelectItem key={pinpad.hardware_id} value={pinpad.hardware_id}>
                              {pinpad.name} {pinpad.price_usd > 0 && `($${pinpad.price_usd})`}
                            </SelectItem>
                          ))
                        )}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Campo 3: Entidad Patrocinadora (Opcional) */}
                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 flex items-center gap-2">
                      <Landmark size={14} className="text-amber-600" />
                      Entidad Patrocinadora <span className="text-slate-400 text-xs font-normal">(Opcional)</span>
                    </Label>
                    <Select 
                      value={quoteData.sponsor_bank_id} 
                      onValueChange={(value) => setQuoteData({ ...quoteData, sponsor_bank_id: value })}
                    >
                      <SelectTrigger data-testid="select-sponsor-bank">
                        <SelectValue placeholder="Seleccione entidad..." />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">Sin Entidad Patrocinadora</SelectItem>
                        {banks.map((bank) => (
                          <SelectItem key={bank.bank_id} value={bank.bank_id}>
                            {bank.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {/* Indicador de campos completos - Solo requiere Integrador */}
                {quoteData.integrator_id && (
                  <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg flex items-center gap-2">
                    <CheckCircle2 size={18} className="text-brand-blue-600" />
                    <span className="text-sm text-brand-blue-700 font-medium">
                      Integrador: {selectedIntegrator?.name} ({quoteData.integrator_app_name})
                      {selectedPinpad && ` • Pinpad: ${selectedPinpad.name}`}
                      {selectedSponsorBank && ` • Patrocinador: ${selectedSponsorBank.name}`}
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
              {canShowItems && quoteData.setup_items.length > 0 && (
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
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => removeSetupItem(index)}
                                  className="h-7 w-7 p-0 text-red-500 hover:text-red-700 hover:bg-red-50"
                                  title="Eliminar"
                                >
                                  <Trash2 size={14} />
                                </Button>
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
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => removeRecurringBasicItem(index)}
                                className="h-7 w-7 p-0 text-red-500 hover:text-red-700 hover:bg-red-50"
                                title="Eliminar"
                              >
                                <Trash2 size={14} />
                              </Button>
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
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => removeRecurringOtherItem(index)}
                                className="h-7 w-7 p-0 text-red-500 hover:text-red-700 hover:bg-red-50"
                                title="Eliminar"
                              >
                                <Trash2 size={14} />
                              </Button>
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

                  {/* SECCIÓN: Resumen Ejecutivo - Matriz de Distribución */}
                  <div className="mt-6 bg-white rounded-lg border border-slate-200 overflow-hidden" data-testid="executive-summary">
                    <div className="bg-slate-100 px-4 py-3 border-b border-slate-200">
                      <h3 className="font-semibold text-lg text-slate-800">Resumen Ejecutivo</h3>
                    </div>
                    
                    {/* Cabecera del Resumen */}
                    <div className="p-4 space-y-3">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="flex">
                          <span className="bg-amber-400 text-slate-900 px-3 py-2 font-semibold text-sm min-w-[140px]">Cliente</span>
                          <span className="bg-white border border-slate-200 px-3 py-2 flex-1 text-slate-900 font-medium">
                            {selectedClient?.legal_name || selectedClient?.fantasy_name || 'N/A'}
                          </span>
                        </div>
                        <div className="flex">
                          <span className="bg-blue-200 text-slate-900 px-3 py-2 font-semibold text-sm min-w-[140px]">Cantidad de Cajas</span>
                          <span className="bg-white border border-slate-200 px-3 py-2 flex-1 text-slate-900 font-medium">
                            {quoteData.cantidad_cajas}
                          </span>
                        </div>
                      </div>
                      
                      <div className="flex">
                        <span className="bg-green-200 text-slate-900 px-3 py-2 font-semibold text-sm min-w-[140px]">Dirección Fiscal</span>
                        <span className="bg-white border border-slate-200 px-3 py-2 flex-1 text-slate-700">
                          {selectedClient?.address || 'No especificada'}
                        </span>
                      </div>
                    </div>

                    {/* Matriz de Distribución - Bancos/Productos/Cajas */}
                    <div className="px-4 pb-4">
                      <table className="w-full border-collapse">
                        <thead>
                          <tr>
                            <th className="bg-green-200 text-slate-900 px-4 py-2 text-left font-semibold border border-slate-200">Bancos</th>
                            <th className="bg-blue-200 text-slate-900 px-4 py-2 text-left font-semibold border border-slate-200">Productos</th>
                            <th className="bg-amber-400 text-slate-900 px-4 py-2 text-center font-semibold border border-slate-200 w-32">Cantidad de Cajas</th>
                          </tr>
                        </thead>
                        <tbody>
                          {/* Agrupar items por banco - SOLO medios de pago con banco (excluir conceptos base) */}
                          {(() => {
                            // Consolidar solo additional_items que tienen bank_name (medios de pago por banco)
                            const bankProductMap = {};
                            quoteData.additional_items
                              .filter(item => item.bank_name) // Solo items con banco asociado
                              .forEach(item => {
                                const bankName = item.bank_name;
                                const productName = item.medio_pago_name || 'Producto';
                                const key = `${bankName}-${productName}`;
                                
                                if (!bankProductMap[key]) {
                                  bankProductMap[key] = {
                                    bank: bankName,
                                    product: productName,
                                    cajas: 0
                                  };
                                }
                                bankProductMap[key].cajas += item.cantidad_cajas || 1;
                              });
                            
                            const rows = Object.values(bankProductMap);
                            
                            if (rows.length === 0) {
                              return (
                                <tr>
                                  <td colSpan={3} className="px-4 py-3 text-center text-slate-500 italic border border-slate-200">
                                    No hay medios de pago seleccionados
                                  </td>
                                </tr>
                              );
                            }
                            
                            return rows.map((row, idx) => (
                              <tr key={idx} className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                                <td className="px-4 py-2 border border-slate-200 text-slate-900">{row.bank}</td>
                                <td className="px-4 py-2 border border-slate-200 text-slate-700">{row.product}</td>
                                <td className="px-4 py-2 border border-slate-200 text-center font-medium text-slate-900">{row.cajas}</td>
                              </tr>
                            ));
                          })()}
                        </tbody>
                      </table>
                    </div>

                    {/* Total de Terminales Virtuales */}
                    <div className="border-t-2 border-slate-400 px-4 py-3 flex justify-between items-center bg-slate-50">
                      <span className="font-semibold text-slate-800">Total de Terminales Virtuales</span>
                      <span className="font-bold text-xl text-slate-900">
                        {(() => {
                          // Sumar cajas solo de medios de pago con banco (excluir conceptos base)
                          const total = quoteData.additional_items
                            .filter(item => item.bank_name)
                            .reduce((sum, item) => sum + (item.cantidad_cajas || 1), 0);
                          return total || quoteData.cantidad_cajas;
                        })()}
                      </span>
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
              {canShowItems && quoteData.setup_items.length === 0 && (
                <div className="text-center py-8 text-slate-500 bg-slate-50 rounded-lg mt-4 border-2 border-dashed">
                  <CreditCard size={40} className="mx-auto mb-3 text-slate-300" />
                  <p className="font-medium">No hay medios de pago agregados</p>
                  <p className="text-sm mt-1">Seleccione un banco y medio de pago para comenzar</p>
                </div>
              )}
            </DialogContent>
          </Dialog>

          {/* Wizard de Equipos y Accesorios */}
          <EquipmentQuoteWizard
            open={equipmentWizardOpen}
            onClose={() => setEquipmentWizardOpen(false)}
            onQuoteCreated={fetchData}
            clients={clients}
            hardware={allHardware}
          />

          {/* Modal de confirmación para Eliminar */}
          <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>¿Eliminar Cotización?</AlertDialogTitle>
                <AlertDialogDescription>
                  ¿Está seguro de que desea eliminar la Cotización <strong>"{deleteQuoteData.number}"</strong> de forma permanente?
                  <br /><br />
                  <span className="text-red-600 font-medium">Esta acción no se puede deshacer.</span>
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancelar</AlertDialogCancel>
                <AlertDialogAction 
                  onClick={executeDeleteQuote}
                  className="bg-red-600 hover:bg-red-700 text-white"
                >
                  Eliminar
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>

          {/* Modal de Workflow (Aprobar/Facturar/Cobrar con carga de documentos) */}
          <WorkflowUploadModal
            open={workflowModalOpen}
            onClose={() => { setWorkflowModalOpen(false); setWorkflowQuoteId(null); setWorkflowConfig(null); }}
            onSuccess={handleWorkflowSuccess}
            quoteId={workflowQuoteId}
            config={workflowConfig}
          />

          {/* Modal de Anexos */}
          <AnexosModal
            open={anexosOpen}
            onClose={() => { setAnexosOpen(false); setAnexosQuoteId(null); }}
            quoteId={anexosQuoteId}
            quoteNumber={anexosQuoteNumber}
          />
        </div>
      </main>
    </div>
  );
};

export default Quotes;
