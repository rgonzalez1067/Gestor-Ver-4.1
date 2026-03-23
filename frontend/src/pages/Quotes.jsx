import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Popover, PopoverContent, PopoverTrigger } from '../components/ui/popover';
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '../components/ui/command';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Plus, FileText, Download, Monitor, Globe, Smartphone, Link, Trash2, Building2, CreditCard, CheckCircle2, Copy, Cpu, Users, Landmark, Pencil, Mail, CheckCircle, Send, Package, Settings2, X, Search, Calendar, Receipt, Banknote, Truck, RefreshCw, Upload, FolderOpen, ChevronsUpDown, Check, Unlock, Eye, AlertTriangle, ChevronDown, Store } from 'lucide-react';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../components/ui/dropdown-menu';
import { EquipmentQuoteWizard } from '../components/EquipmentQuoteWizard';
import { AnexosModal } from '../components/AnexosModal';
import { WorkflowUploadModal } from '../components/WorkflowUploadModal';
import { MultiProductSelector } from '../components/MultiProductSelector';
import { QuoteFilters } from '../components/quotes/QuoteFilters';
import { QuotesTable } from '../components/quotes/QuotesTable';
import { PdfPreviewModal } from '../components/quotes/PdfPreviewModal';
import { DeliveryDialog } from '../components/quotes/DeliveryDialog';
import { RepairDeliveryDialog } from '../components/quotes/RepairDeliveryDialog';
import api from '../utils/api';
import { toast } from 'sonner';

const QUOTE_TYPES = [
  { id: 'VPOS', name: 'VPOS (Cajas)', icon: Monitor, description: 'Puntos de venta físicos' },
  { id: 'MPOS', name: 'MPOS (Tablet/Móvil)', icon: Smartphone, description: 'Terminales móviles POS' },
  { id: 'FAST_TRACK', name: 'POS Stand Alone (Fast Track)', icon: Smartphone, description: 'Equipos autogestionados Pyme' },
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
  'Reparada': 'bg-cyan-100 text-cyan-700',
  'Configurada': 'bg-indigo-100 text-indigo-700',
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
  'Reparada': 'Reparada',
  'Configurada': 'Configurada',
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
  'repair': 'Reparaciones',
  'fast_track': 'Fast Track'
};


export const Quotes = () => {
  const [quotes, setQuotes] = useState([]);
  const [clients, setClients] = useState([]);
  const [banks, setBanks] = useState([]);
  const [serviceCatalog, setServiceCatalog] = useState([]); // Catálogo de precios
  const [integrators, setIntegrators] = useState([]); // Lista de integradores
  const [pinpads, setPinpads] = useState([]); // Lista de pinpads (dispositivos tipo Pinpad)
  const [posDevices, setPosDevices] = useState([]); // Lista de POS (dispositivos tipo POS) para MPOS
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
  const [filterSegment, setFilterSegment] = useState('');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');
  
  // Estado para edición de cotización existente
  const [editingQuoteId, setEditingQuoteId] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isLoadingEdit, setIsLoadingEdit] = useState(false);
  // Refs para evitar propagación automática al cargar edición
  const prevCajasRef = useRef(null);
  const prevBancosRef = useRef(null);
  
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
    requires_pinpad_config: true,  // ¿Requiere Configuración de PinPads?
    requires_vpn: true,            // ¿Requiere VPN?
    setup_items: [],              // Items exclusivos de Setup
    recurring_basic_items: [],    // Recurrentes Básicos (incluye complementos de adicionales)
    recurring_other_items: [],    // Otros Recurrentes
    additional_items: [],         // Items adicionales (medios de pago de bancos)
    descuento: 0,
    descuento_setup: 0,
    descuento_recurrente: 0,
    notes: ''
  });
  
  // Estado para agregar nuevo medio de pago
  const [selectedBankId, setSelectedBankId] = useState('');
  const [selectedMedioPagoId, setSelectedMedioPagoId] = useState('');
  const [availableMediosPago, setAvailableMediosPago] = useState([]);
  // Estado para búsqueda de clientes
  const [clientSearchOpen, setClientSearchOpen] = useState(false);
  const [clientSearchQuery, setClientSearchQuery] = useState('');
  const [clientSearchResults, setClientSearchResults] = useState([]);
  const [isSearchingClients, setIsSearchingClients] = useState(false);
  const clientSearchTimer = useRef(null);
  
  // Estado para Payment Gateway
  const [pgSetupItems, setPgSetupItems] = useState([]);
  const [pgTransactionRange, setPgTransactionRange] = useState(null);
  const [pgRecurringCostsTable, setPgRecurringCostsTable] = useState(null);
  const [pgSelectedMedioPago, setPgSelectedMedioPago] = useState('');
  const [pgSelectedBankId, setPgSelectedBankId] = useState('');
  const [pgDefaults, setPgDefaults] = useState(null);
  const [pgShowRecurringTable, setPgShowRecurringTable] = useState(false);
  const [pgFilteredProducts, setPgFilteredProducts] = useState([]);
  
  // Estados para modales de confirmación
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deleteQuoteData, setDeleteQuoteData] = useState({ id: null, number: null });
  
  // Estados para modales de workflow (carga obligatoria de documentos)
  const [workflowModalOpen, setWorkflowModalOpen] = useState(false);
  const [workflowQuoteId, setWorkflowQuoteId] = useState(null);
  const [workflowConfig, setWorkflowConfig] = useState(null);
  
  // Estado para "Cliente en Producción"
  const [isProductionClient, setIsProductionClient] = useState(false);
  const [productionItems, setProductionItems] = useState([]);
  const [productionSelectedServiceId, setProductionSelectedServiceId] = useState('');
  
  // Estado para previsualización de PDF
  const [pdfPreviewOpen, setPdfPreviewOpen] = useState(false);
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState(null);
  const [pdfPreviewLoading, setPdfPreviewLoading] = useState(false);

  // Estado para flujo irregular (Protocolo de Excepción)
  const [irregularCount, setIrregularCount] = useState(0);
  const [exceptionModalOpen, setExceptionModalOpen] = useState(false);
  const [exceptionData, setExceptionData] = useState({ reason: '', regularization_date: '' });
  const [pendingAction, setPendingAction] = useState(null); // { quoteId, action, quote }
  // Bitácora de Flujo (Historial de Excepciones)
  const [bitacoraFlujoOpen, setBitacoraFlujoOpen] = useState(false);
  const [bitacoraFlujoQuoteId, setBitacoraFlujoQuoteId] = useState(null);
  
  // Modal de envío con mensaje personalizado y CC
  const [emailModalOpen, setEmailModalOpen] = useState(false);
  const [emailModalConfig, setEmailModalConfig] = useState({ action: '', quoteId: '', quoteName: '' });
  const [emailCustomMessage, setEmailCustomMessage] = useState('');
  const [emailAdditionalRecipients, setEmailAdditionalRecipients] = useState('');
  const [emailNewRecipient, setEmailNewRecipient] = useState('');
  const [emailRecipientsList, setEmailRecipientsList] = useState([]);
  const [bitacoraFlujoQuoteNumber, setBitacoraFlujoQuoteNumber] = useState('');
  const [bitacoraFlujoEntries, setBitacoraFlujoEntries] = useState([]);
  const [bitacoraFlujoLoading, setBitacoraFlujoLoading] = useState(false);

  // Estado para DeliveryDialog (Hoja de Ruta)
  const [deliveryDialogOpen, setDeliveryDialogOpen] = useState(false);
  // Estado para RepairDeliveryDialog
  const [repairDeliveryDialogOpen, setRepairDeliveryDialogOpen] = useState(false);
  const [deliveryQuoteId, setDeliveryQuoteId] = useState(null);
  const [deliveryExceptionInfo, setDeliveryExceptionInfo] = useState(null);

  // Estado para flujo Multitienda
  const [multistoreDialogOpen, setMultistoreDialogOpen] = useState(false);
  const [multistoreQuoteId, setMultistoreQuoteId] = useState(null);
  const [multistoreExceptionInfo, setMultistoreExceptionInfo] = useState(null);
  const [isMultistore, setIsMultistore] = useState(null); // null = no decidido, true/false
  const [multistoreStores, setMultistoreStores] = useState([]);
  const [multistoreNewStore, setMultistoreNewStore] = useState({ name: '', box_count: '' });
  const [multistorePhase, setMultistorePhase] = useState('ask'); // 'ask' | 'collect' | 'confirm'
  const [multistoreSending, setMultistoreSending] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  // Búsqueda server-side de clientes con debounce
  useEffect(() => {
    if (!clientSearchQuery || clientSearchQuery.length < 2) {
      setClientSearchResults(clients);
      return;
    }
    setIsSearchingClients(true);
    if (clientSearchTimer.current) clearTimeout(clientSearchTimer.current);
    clientSearchTimer.current = setTimeout(async () => {
      try {
        const res = await api.get(`/clients/search?q=${encodeURIComponent(clientSearchQuery)}`);
        setClientSearchResults(res.data);
      } catch {
        // Fallback: filtrar localmente
        const q = clientSearchQuery.toLowerCase();
        setClientSearchResults(clients.filter(c =>
          (c.fantasy_name || '').toLowerCase().includes(q) ||
          (c.legal_name || '').toLowerCase().includes(q) ||
          (c.rif || '').toLowerCase().includes(q)
        ));
      } finally {
        setIsSearchingClients(false);
      }
    }, 300);
    return () => { if (clientSearchTimer.current) clearTimeout(clientSearchTimer.current); };
  }, [clientSearchQuery, clients]);

  // Auto-calcular campo "Bancos" para conceptos con autoBancos: true
  useEffect(() => {
    // No auto-calcular durante carga de edición (prioridad absoluta a datos de BD)
    if (isLoadingEdit) return;
    
    if (quoteData.setup_items.length > 0) {
      const totalMediosPago = quoteData.additional_items.length;
      
      const updatedSetupItems = quoteData.setup_items.map(item => {
        // Solo auto-calcular si autoBancos está activo Y no hay override manual
        if (item.autoBancos && (item.bancosOverride === undefined || item.bancosOverride === null)) {
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
  // REGLA DE ORO: Solo propaga cuando el USUARIO cambia manualmente el header
  // NO durante carga de edición (los datos guardados tienen prioridad absoluta)
  useEffect(() => {
    const cajas = quoteData.cantidad_cajas;
    const bancos = quoteData.cantidad_bancos;
    
    // Durante carga de edición: solo actualizar refs, no propagar
    if (isLoadingEdit) {
      prevCajasRef.current = cajas;
      prevBancosRef.current = bancos;
      return;
    }
    
    // Si los valores no cambiaron respecto al ref anterior, no propagar
    // Esto evita la propagación cuando isLoadingEdit pasa de true a false
    if (prevCajasRef.current === cajas && prevBancosRef.current === bancos) {
      return;
    }
    
    // Actualizar refs con los nuevos valores del usuario
    prevCajasRef.current = cajas;
    prevBancosRef.current = bancos;
    
    const { setup_items, recurring_basic_items, recurring_other_items, additional_items } = quoteData;
    
    if (setup_items.length === 0 && recurring_basic_items.length === 0 && recurring_other_items.length === 0 && (additional_items || []).length === 0) {
      return; // No hay items para actualizar
    }
    
    let needsUpdate = false;
    const newCajas = cajas || 1;
    const newBancos = bancos || 1;
    
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
      const [quotesRes, clientsRes, banksRes, servicesRes, integratorsRes, hardwareRes, templatesRes, pgCostsRes, pgDefaultsRes] = await Promise.all([
        api.get('/quotes'),
        api.get('/clients'),
        api.get('/banks'),
        api.get('/services'), // Cargar catálogo de precios
        api.get('/integrators'), // Cargar integradores
        api.get('/hardware'), // Cargar dispositivos
        api.get('/config/templates').catch(() => ({ data: {} })), // Cargar estado de plantillas
        api.get('/pg-recurring-costs').catch(() => ({ data: null })), // Tabla costos recurrentes PG
        api.get('/pg-defaults').catch(() => ({ data: null })) // Defaults PG (Persona Jurídica)
      ]);
      setQuotes(quotesRes.data);
      setClients(clientsRes.data);
      setBanks(banksRes.data);
      setServiceCatalog(servicesRes.data);
      setIntegrators(integratorsRes.data);
      // Irregular count
      try { const ic = await api.get('/quotes/irregular/count'); setIrregularCount(ic.data.count || 0); } catch {}
      // Guardar todos los hardware
      setAllHardware(hardwareRes.data || []);
      // Filtrar solo dispositivos tipo "Pinpad" y clasificación "Bien" para cotizaciones de implementación
      const pinpadDevices = (hardwareRes.data || []).filter(hw => 
        hw.type?.toLowerCase() === 'pinpad' && (hw.asset_type || 'Bien') === 'Bien'
      );
      setPinpads(pinpadDevices);
      const posHardware = (hardwareRes.data || []).filter(hw => 
        hw.type?.toLowerCase() === 'pos' && (hw.asset_type || 'Bien') === 'Bien'
      );
      setPosDevices(posHardware);
      // Guardar estado de plantillas disponibles
      setTemplateAvailable(templatesRes.data || {});
      // Tabla de costos recurrentes PG
      if (pgCostsRes.data) setPgRecurringCostsTable(pgCostsRes.data);
      // Defaults PG
      if (pgDefaultsRes.data) setPgDefaults(pgDefaultsRes.data);
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
      case 'VPOS':
      case 'MPOS': return 'vpos_available';
      case 'GATEWAY': return 'gateway_available';
      case 'MPOS': return 'mpos_available';
      case 'LINK': return 'link_available';
      default: return 'vpos_available';
    }
  };

  // Inicializar conceptos de Setup cuando se completan los parámetros
  const initializeSetupConcepts = (pricingModel, cantidadCajas, cantidadBancos, requiresPinpadConfig = true) => {
    const concepts = requiresPinpadConfig
      ? SETUP_CONCEPTS
      : SETUP_CONCEPTS.filter(c => c.name !== 'Configuración dispositivo (Pinpad o POS)');
    return concepts.map((concept) => {
      const prices = findServicePriceWithModel(concept.name, pricingModel);
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
  const initializeRecurringOtherConcepts = (pricingModel, cantidadCajas, cantidadBancos, requiresVpn = true) => {
    return RECURRING_OTHER_CONCEPTS.map((concept) => {
      const isVpnItem = concept.name.includes('Comunicación Backend');
      let tarifa;
      if (isVpnItem) {
        // Para el ítem de Comunicación Backend, el costo depende del flag VPN
        const service = serviceCatalog.find(s =>
          s.name.toLowerCase().includes('comunicación backend') ||
          s.name.toLowerCase().includes('comunicacion backend') ||
          concept.name.toLowerCase().includes(s.name.toLowerCase())
        );
        if (service) {
          tarifa = requiresVpn
            ? (service.monthly_cost_conventional || 0)
            : (service.monthly_cost_outsourcing || 0);
        } else {
          const prices = findServicePriceWithModel(concept.name, pricingModel);
          tarifa = prices.monthly_cost;
        }
      } else {
        const prices = findServicePriceWithModel(concept.name, pricingModel);
        tarifa = prices.monthly_cost;
      }
      return {
        id: `recurring_other_${concept.name}`,
        medio_pago_name: concept.name,
        cantidad_cajas: cantidadCajas,
        cantidad_bancos: concept.lockBancos ? 1 : cantidadBancos,
        tarifa,
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

  const openWizard = (segment = 'PYME') => {
    // Resetear modo edición si estaba activo
    setIsEditing(false);
    setEditingQuoteId(null);
    setIsLoadingEdit(false);
    
    setWizardOpen(true);
    setQuoteData({
      quote_type: '',
      client_id: '',
      client_segment: segment,
      pricing_model: '',
      cantidad_cajas: 1,
      cantidad_bancos: 1,
      integrator_id: '',
      integrator_app_name: '',
      pinpad_id: '',
      sponsor_bank_id: '',
      requires_pinpad_config: true,
      requires_vpn: true,
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
    setPgShowRecurringTable(false);
    setPgFilteredProducts([]);
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

  // Agregar múltiples medios de pago de una vez (VPOS)
  const addMultipleMediosPago = (selectedProducts) => {
    if (!selectedBankId || selectedProducts.length === 0) return;
    const bank = banks.find(b => b.bank_id === selectedBankId);
    if (!bank) return;

    let newAdditionalItems = [...quoteData.additional_items];
    let newRecurringBasicItems = [...quoteData.recurring_basic_items];
    let addedCount = 0;

    for (const medioPago of selectedProducts) {
      const exists = newAdditionalItems.some(
        item => item.bank_id === selectedBankId && item.medio_pago_name === medioPago.product_name
      );
      if (exists) continue;

      const prices = findServicePrice(medioPago.product_name);
      const newItem = {
        id: `${selectedBankId}_${medioPago.product_name}`,
        bank_id: selectedBankId,
        bank_name: bank.name,
        medio_pago_name: medioPago.product_name,
        description: medioPago.description || '',
        cantidad_cajas: quoteData.cantidad_cajas,
        cantidad_bancos: 1,
        tarifa_setup: prices.setup_cost,
        tarifa_recurrente: prices.monthly_cost,
        application_type: prices.application_type,
        isDefault: false,
        linked_recurring_service_id: prices.linked_recurring_service_id
      };
      newAdditionalItems.push(newItem);
      addedCount++;

      if (prices.linked_recurring_service_id) {
        const linkedService = getServiceById(prices.linked_recurring_service_id);
        if (linkedService) {
          const isOutsourcing = quoteData.pricing_model === 'outsourcing';
          const linkedMonthlyPrice = isOutsourcing
            ? (linkedService.monthly_cost_outsourcing || 0)
            : (linkedService.monthly_cost_conventional || 0);
          newRecurringBasicItems.push({
            id: `auto_linked_${newItem.id}_${linkedService.service_id}`,
            medio_pago_name: linkedService.name,
            linkedTo: medioPago.product_name,
            bank_name: bank.name,
            cantidad_cajas: quoteData.cantidad_cajas,
            cantidad_bancos: 1,
            tarifa: linkedMonthlyPrice,
            isDefault: false,
            isAutoLinked: true,
            sourceServiceId: newItem.id,
            type: 'recurring_basic'
          });
        }
      }
    }

    if (addedCount > 0) {
      const consolidatedRecurring = consolidateRecurringItems(newRecurringBasicItems);
      setQuoteData({
        ...quoteData,
        additional_items: newAdditionalItems,
        recurring_basic_items: consolidatedRecurring
      });
      toast.success(`${addedCount} medio(s) de pago agregado(s)`);
    }
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
    // If there's a manual override, use that
    if (item.totalOverride !== undefined && item.totalOverride !== null) {
      return item.totalOverride;
    }
    const cajas = item.cantidad_cajas || 1;
    // Si lockBancos es true, el cálculo usa 1 (N/A en UI)
    const bancos = item.lockBancos ? 1 : (item.cantidad_bancos || 1);
    const tarifa = item.tarifa || item.tarifa_setup || 0;
    return tarifa * cajas * bancos;
  };

  // Calculate the standard (non-overridden) total for comparison
  const calcularTotalEstandar = (item) => {
    const cajas = item.cantidad_cajas || 1;
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

  // Calcular subtotal "Cliente en Producción" (conceptos recurrentes adicionales)
  const subtotalProduction = productionItems.reduce((sum, item) => sum + ((item.tarifa || 0) * (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1)), 0);

  // Calcular descuentos independientes (Setup vs Recurrente)
  const montoDescuentoSetup = subtotalSetup * ((quoteData.descuento_setup || 0) / 100);
  const montoDescuentoRecurrente = (subtotalRecurrente + subtotalProduction) * ((quoteData.descuento_recurrente || 0) / 100);

  // Totales netos
  const totalNetoSetup = subtotalSetup - montoDescuentoSetup;
  const totalNetoRecurrente = (subtotalRecurrente + subtotalProduction) - montoDescuentoRecurrente;
  const grandTotal = totalNetoSetup + totalNetoRecurrente;

  // === PG (Payment Gateway) Functions ===
  
  // Auto-load "Persona Jurídica" when PG is selected and header becomes complete
  const initPgSetup = () => {
    // Find Persona Jurídica price from services catalog (outsourcing model)
    const pjService = serviceCatalog.find(s => s.gateway_enabled && s.name?.toLowerCase().includes('persona jur'));
    const pjCost = pjService?.setup_cost_outsourcing || pgDefaults?.costo || 240;
    if (pgSetupItems.length === 0) {
      setPgSetupItems([{
        concepto: 'Persona Jurídica',
        costo: pjCost,
        banco: 'N/A',
        observacion: 'Costo Base',
        fixed: true
      }]);
    }
  };

  // Handle bank selection → filter products by gateway_available for that bank
  const handlePgBankChange = (bankId) => {
    setPgSelectedBankId(bankId);
    setPgSelectedMedioPago('');
    if (!bankId) {
      setPgFilteredProducts([]);
      return;
    }
    const bank = banks.find(b => b.bank_id === bankId);
    if (bank) {
      // Solo filtrar por gateway_available, las duplicaciones las maneja MultiProductSelector
      const filtered = (bank.products || []).filter(p => p.gateway_available);
      setPgFilteredProducts(filtered);
    }
  };

  // Lookup outsourcing price from services catalog for a given product name
  const getPgOutsourcingPrice = (productName) => {
    const match = serviceCatalog.find(s => 
      s.gateway_enabled && s.application_type === 'setup' && s.name === productName
    );
    return match?.setup_cost_outsourcing || 0;
  };

  const addPgSetupItem = () => {
    if (!pgSelectedBankId) {
      toast.error('Seleccione un banco primero');
      return;
    }
    if (!pgSelectedMedioPago) {
      toast.error('Seleccione un medio de pago');
      return;
    }
    const bank = banks.find(b => b.bank_id === pgSelectedBankId);
    
    if (pgSetupItems.some(item => item.concepto === pgSelectedMedioPago && item.banco === (bank?.name || 'N/A'))) {
      toast.error('Este medio de pago de este banco ya fue agregado');
      return;
    }
    // Auto-fill cost from Outsourcing pricing in services catalog
    const outsourcingCost = getPgOutsourcingPrice(pgSelectedMedioPago);
    setPgSetupItems([...pgSetupItems, {
      concepto: pgSelectedMedioPago,
      costo: outsourcingCost,
      banco: bank?.name || 'N/A',
      observacion: ''
    }]);
    setPgSelectedMedioPago('');
    setPgSelectedBankId('');
    setPgFilteredProducts([]);
    setPgShowRecurringTable(false);
    toast.success('Medio de pago agregado al setup');
  };

  // Agregar múltiples medios de pago de una vez (PG)
  const addMultiplePgSetupItems = (selectedProducts) => {
    if (!pgSelectedBankId || selectedProducts.length === 0) return;
    const bank = banks.find(b => b.bank_id === pgSelectedBankId);
    if (!bank) return;

    let newItems = [...pgSetupItems];
    let addedCount = 0;

    for (const product of selectedProducts) {
      const exists = newItems.some(item => item.concepto === product.product_name && item.banco === bank.name);
      if (exists) continue;

      const outsourcingCost = getPgOutsourcingPrice(product.product_name);
      newItems.push({
        concepto: product.product_name,
        costo: outsourcingCost,
        banco: bank.name,
        observacion: ''
      });
      addedCount++;
    }

    if (addedCount > 0) {
      setPgSetupItems(newItems);
      setPgShowRecurringTable(false);
      toast.success(`${addedCount} medio(s) de pago agregado(s) al setup`);
    }
    setPgSelectedBankId('');
    setPgFilteredProducts([]);
  };

  const updatePgSetupItem = (index, field, value) => {
    const updated = [...pgSetupItems];
    updated[index] = { ...updated[index], [field]: field === 'costo' ? (parseFloat(value) || 0) : value };
    setPgSetupItems(updated);
  };

  const removePgSetupItem = (index) => {
    // Don't allow removing fixed items (Persona Jurídica)
    if (pgSetupItems[index]?.fixed) {
      toast.error('Este concepto es fijo y no puede ser eliminado');
      return;
    }
    setPgSetupItems(pgSetupItems.filter((_, i) => i !== index));
    setPgShowRecurringTable(false); // Reset recurring table when items change
  };

  const pgSetupTotal = pgSetupItems.reduce((sum, item) => sum + (item.costo || 0), 0);

  // Count only medios de pago (exclude Persona Jurídica which is fixed)
  const pgMediosPagoCount = pgSetupItems.filter(item => !item.fixed).length;

  // Generate full recurring costs table for N products
  const generatePgRecurringTable = () => {
    if (!pgRecurringCostsTable || pgMediosPagoCount === 0) {
      toast.error('Agregue al menos un medio de pago para generar la tabla de recurrentes');
      return;
    }
    setPgShowRecurringTable(true);
  };

  const getPgFullRecurringTable = () => {
    if (!pgRecurringCostsTable || pgMediosPagoCount === 0) return [];
    const numProducts = Math.min(pgMediosPagoCount, 11);
    return pgRecurringCostsTable.data.map(rangeRow => {
      const rangeInfo = pgRecurringCostsTable.ranges.find(r => r.rango === rangeRow.rango);
      const costData = rangeRow[String(numProducts)];
      return {
        rango: rangeRow.rango,
        label: rangeInfo?.label || '',
        min: rangeInfo?.min || 0,
        max: rangeInfo?.max || 0,
        base: costData?.base,
        tope: costData?.tope
      };
    });
  };

  const pgFullRecurringTable = pgShowRecurringTable ? getPgFullRecurringTable() : [];

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
      const integrator = integrators.find(i => i.integrator_id === quoteData.integrator_id);

      // Build recurring cost data (full table for N products)
      const recurringData = pgShowRecurringTable && pgMediosPagoCount > 0 ? {
        num_products: Math.min(pgMediosPagoCount, 11),
        table: getPgFullRecurringTable()
      } : null;

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
        pg_setup_items: pgSetupItems.map(({ fixed, ...item }) => item), // Remove fixed flag
        pg_recurring_cost: recurringData,
        pg_transaction_range: pgMediosPagoCount,
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
      const pinpad = (quoteData.quote_type === 'MPOS' ? posDevices : pinpads).find(p => p.hardware_id === quoteData.pinpad_id);
      const sponsorBank = banks.find(b => b.bank_id === quoteData.sponsor_bank_id);

      const allItems = [
        ...quoteData.setup_items.map(item => ({
          item_type: 'setup',
          item_name: item.medio_pago_name || item.name,
          quantity: (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1),
          unit_price_usd: item.tarifa || item.unit_price_usd || 0,
          total_usd: item.totalOverride || calcularTotal(item),
          cantidad_cajas: item.cantidad_cajas || 1,
          cantidad_bancos: item.cantidad_bancos || 1,
          // Metadatos para restaurar correctamente al editar
          lockBancos: item.lockBancos || false,
          autoBancos: item.autoBancos || false,
          bancosOverride: item.bancosOverride || null,
          totalOverride: item.totalOverride || null
        })),
        ...quoteData.recurring_basic_items.map(item => ({
          item_type: 'recurring_basic',
          item_name: item.medio_pago_name || item.name,
          quantity: (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1),
          unit_price_usd: item.tarifa || item.unit_price_usd || 0,
          total_usd: calcularTotal(item),
          cantidad_cajas: item.cantidad_cajas || 1,
          cantidad_bancos: item.cantidad_bancos || 1,
          lockBancos: item.lockBancos || false,
          isAutoLinked: item.isAutoLinked || false
        })),
        ...quoteData.recurring_other_items.map(item => ({
          item_type: 'recurring_other',
          item_name: item.medio_pago_name || item.name,
          quantity: (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1),
          unit_price_usd: item.tarifa || item.unit_price_usd || 0,
          total_usd: calcularTotal(item),
          cantidad_cajas: item.cantidad_cajas || 1,
          cantidad_bancos: item.cantidad_bancos || 1,
          lockBancos: item.lockBancos || false
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
        })),
        // Items de cliente en producción
        ...productionItems.map(item => ({
          item_type: 'production_recurring',
          item_name: item.medio_pago_name || item.name,
          quantity: (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1),
          unit_price_usd: item.tarifa || 0,
          total_usd: (item.tarifa || 0) * (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1),
          cantidad_cajas: item.cantidad_cajas || 1,
          cantidad_bancos: item.cantidad_bancos || 1
        }))
      ];

      // Preparar datos del PDF (mismos datos que exportCurrentQuoteToPDF)
      const templateTypeMap = {
        'VPOS': 'vpos_pyme',
        'VPOS': 'vpos_pyme',
        'MPOS': 'mpos_pyme',
        'FAST_TRACK': 'mpos_pyme',
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
        integrator_name: integrator?.name || (quoteData.integrator_id === 'sin_integrador' ? 'Sin integrador por el momento' : ''),
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
        descuento_setup: quoteData.descuento_setup || 0,
        descuento_recurrente: quoteData.descuento_recurrente || 0,
        requires_pinpad_config: quoteData.requires_pinpad_config !== false,
        requires_vpn: quoteData.requires_vpn !== false,
        notes: quoteData.notes || '',
        is_production_client: isProductionClient,
        pg_setup_items: pgSetupItems.map(item => ({
          concepto: item.concepto,
          costo: item.costo || 0,
          banco: item.banco || '',
          observacion: item.observacion || ''
        })),
        production_items: productionItems.map(item => ({
          concepto: item.medio_pago_name,
          cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
          cantidad_bancos: parseInt(item.cantidad_bancos) || 1,
          tarifa: parseFloat(item.tarifa) || 0
        }))
      };

      const payload = {
        client_id: quoteData.client_id,
        client_segment: quoteData.client_segment || 'PYME',
        quote_category: isFastTrackType ? 'fast_track' : 'implementation',
        quote_type: quoteData.quote_type,
        pricing_model: quoteData.pricing_model,
        services: allItems,
        hardware: [],
        integrator_id: quoteData.integrator_id,
        integrator_name: integrator?.name || (quoteData.integrator_id === 'sin_integrador' ? 'Sin integrador por el momento' : ''),
        integrator_app_name: quoteData.integrator_app_name,
        pinpad_id: quoteData.pinpad_id === 'none' ? '' : quoteData.pinpad_id,
        pinpad_model: quoteData.pinpad_id && quoteData.pinpad_id !== 'none' ? (pinpad?.name || '') : '',
        sponsor_bank_id: quoteData.sponsor_bank_id === 'none' ? '' : quoteData.sponsor_bank_id,
        sponsor_bank_name: quoteData.sponsor_bank_id && quoteData.sponsor_bank_id !== 'none' ? (sponsorBank?.name || '') : '',
        notes: quoteData.notes,
        cantidad_cajas: quoteData.cantidad_cajas || 1,
        cantidad_bancos: quoteData.cantidad_bancos || 1,
        is_production_client: isProductionClient,
        requires_pinpad_config: quoteData.requires_pinpad_config !== false,
        requires_vpn: quoteData.requires_vpn !== false,
        production_items: productionItems.map(item => ({
          item_name: item.medio_pago_name,
          cantidad_cajas: item.cantidad_cajas || 1,
          cantidad_bancos: item.cantidad_bancos || 1,
          tarifa: item.tarifa || 0,
          total: (item.tarifa || 0) * (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1)
        })),
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
      descuento_setup: quoteData.descuento_setup || 0,
      descuento_recurrente: quoteData.descuento_recurrente || 0,
      requires_pinpad_config: quoteData.requires_pinpad_config !== false,
      requires_vpn: quoteData.requires_vpn !== false,
      notes: quoteData.notes || '',
      is_production_client: isProductionClient,
      // PG setup items para el PDF de Payment Gateway
      pg_setup_items: pgSetupItems.map(item => ({
        concepto: item.concepto,
        costo: item.costo || 0,
        banco: item.banco || '',
        observacion: item.observacion || ''
      })),
      production_items: productionItems.map(item => ({
        concepto: item.medio_pago_name,
        cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
        cantidad_bancos: parseInt(item.cantidad_bancos) || 1,
        tarifa: parseFloat(item.tarifa) || 0
      })),
      // PG Recurring costs (tabla de rangos)
      pg_recurring_cost: pgShowRecurringTable && pgMediosPagoCount > 0 ? {
        num_products: Math.min(pgMediosPagoCount, 11),
        rangos: getPgFullRecurringTable().map(r => ({
          rango_label: r.label,
          costo_base_total: r.base,
          precio_tope: r.tope
        }))
      } : null
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

  // Previsualizar PDF en modal
  const previewCurrentQuotePDF = async () => {
    const client = selectedClient;
    if (!client) {
      toast.error('Seleccione un cliente primero');
      return;
    }
    
    setPdfPreviewLoading(true);
    
    try {
      const pdfData = {
        cliente_nombre: client.legal_name || client.fantasy_name || '',
        cliente_rif: client.rif || '',
        cliente_contacto: client.contact_name || '',
        cliente_address: client.address || '',
        quote_type: quoteData.quote_type,
        pricing_model: quoteData.pricing_model,
        cantidad_cajas: quoteData.cantidad_cajas || 1,
        quote_number: '',
        template_type: isPaymentGateway ? 'payment_gateway' : 'vpos_pyme',
        integrator_name: integrators.find(i => i.integrator_id === quoteData.integrator_id)?.name || (quoteData.integrator_id === 'sin_integrador' ? 'Sin integrador por el momento' : ''),
        integrator_app_name: quoteData.integrator_app_name || '',
        pinpad_model: '',
        sponsor_bank_name: '',
        setup_items: quoteData.setup_items.map(item => ({
          concepto: item.medio_pago_name, cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
          cantidad_bancos: item.lockBancos ? 1 : (parseInt(item.cantidad_bancos) || 1),
          tarifa: parseFloat(item.tarifa) || 0, bank_name: item.bank_name || null
        })),
        recurring_basic_items: quoteData.recurring_basic_items.map(item => ({
          concepto: item.medio_pago_name, cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
          cantidad_bancos: item.lockBancos ? 1 : (parseInt(item.cantidad_bancos) || 1),
          tarifa: parseFloat(item.tarifa) || 0
        })),
        recurring_other_items: quoteData.recurring_other_items.map(item => ({
          concepto: item.medio_pago_name, cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
          cantidad_bancos: item.lockBancos ? 1 : (parseInt(item.cantidad_bancos) || 1),
          tarifa: parseFloat(item.tarifa) || 0
        })),
        additional_items: [],
        pg_setup_items: pgSetupItems.map(item => ({
          concepto: item.concepto, costo: item.costo || 0, banco: item.banco || '', observacion: item.observacion || ''
        })),
        production_items: productionItems.map(item => ({
          concepto: item.medio_pago_name, cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
          cantidad_bancos: parseInt(item.cantidad_bancos) || 1, tarifa: parseFloat(item.tarifa) || 0
        })),
        descuento: quoteData.descuento || 0,
        descuento_setup: quoteData.descuento_setup || 0,
        descuento_recurrente: quoteData.descuento_recurrente || 0,
        requires_pinpad_config: quoteData.requires_pinpad_config !== false,
        requires_vpn: quoteData.requires_vpn !== false,
        notes: quoteData.notes || '',
        is_production_client: isProductionClient,
        pg_recurring_cost: pgShowRecurringTable && pgMediosPagoCount > 0 ? {
          num_products: Math.min(pgMediosPagoCount, 11),
          rangos: getPgFullRecurringTable().map(r => ({
            rango_label: r.label,
            costo_base_total: r.base,
            precio_tope: r.tope
          }))
        } : null
      };
      
      const token = localStorage.getItem('session_token');
      const backendUrl = process.env.REACT_APP_BACKEND_URL;
      
      const response = await fetch(`${backendUrl}/api/quotes/preview-pdf-with-template`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json', 'Accept': 'application/pdf' },
        body: JSON.stringify(pdfData)
      });
      
      if (!response.ok) {
        const errText = await response.text();
        try { toast.error(JSON.parse(errText).detail || 'Error al previsualizar'); } catch { toast.error('Error al generar previsualización'); }
        return;
      }
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      setPdfPreviewUrl(url);
      setPdfPreviewOpen(true);
    } catch (error) {
      console.error('Error previewing PDF:', error);
      toast.error('Error al previsualizar el PDF');
    } finally {
      setPdfPreviewLoading(false);
    }
  };

  const getQuoteTypeName = (typeId) => {
    if (typeId === 'VPOS') return 'VPOS (Cajas)';
    if (typeId === 'MPOS') return 'MPOS (Tablet/Móvil)';
    if (typeId === 'FAST_TRACK') return 'POS Stand Alone (Fast Track)';
    if (typeId === 'VPOS_MPOS') return 'VPOS/MPOS';
    const type = QUOTE_TYPES.find(t => t.id === typeId);
    return type ? type.name : typeId;
  };

  const getPricingModelName = (modelId) => {
    const model = PRICING_MODELS.find(m => m.id === modelId);
    return model ? model.name : modelId;
  };

  // === FUNCIONES DE ACCIONES DE COTIZACIÓN ===
  
  // === Modal de Envío: helpers ===
  const openEmailModal = (action, quoteId) => {
    const q = quotes.find(q => q.quote_id === quoteId);
    setEmailModalConfig({ action, quoteId, quoteName: q?.quote_number || '' });
    setEmailCustomMessage('');
    setEmailNewRecipient('');
    setEmailRecipientsList([]);
    setEmailModalOpen(true);
  };

  const addEmailRecipient = () => {
    const email = emailNewRecipient.trim();
    if (email && email.includes('@') && !emailRecipientsList.includes(email)) {
      setEmailRecipientsList([...emailRecipientsList, email]);
      setEmailNewRecipient('');
    }
  };

  const removeEmailRecipient = (email) => {
    setEmailRecipientsList(emailRecipientsList.filter(e => e !== email));
  };

  const getEmailHeaders = () => {
    const headers = {};
    if (emailCustomMessage.trim()) headers['x-custom-message'] = emailCustomMessage.trim().slice(0, 200);
    if (emailRecipientsList.length > 0) headers['x-additional-recipients'] = emailRecipientsList.join(',');
    return headers;
  };

  const confirmEmailAndProceed = () => {
    const { action, quoteId } = emailModalConfig;
    setEmailModalOpen(false);
    
    if (action === 'send-to-client') {
      executeSendToClient(quoteId);
    } else if (action === 'approve') {
      openApproveConfirm(quoteId, pendingAction?.exceptionHeaders || null);
    } else if (action === 'repair-complete') {
      handleRepairComplete(quoteId);
    } else if (action === 'configure') {
      handleConfigure(quoteId);
    } else if (action === 'invoice') {
      _openInvoiceModalDirect(quoteId, pendingAction?.exceptionHeaders || null);
    } else if (action === 'collect') {
      openCollectConfirm(quoteId, pendingAction?.exceptionHeaders || null);
    } else if (action === 'send-to-implementation') {
      openMultistoreDialog(quoteId, pendingAction?.exceptionHeaders || null);
    } else if (action === 'deliver') {
      handleDeliverQuote(quoteId, pendingAction?.exceptionHeaders || null);
    }
  };

  // Enviar al cliente (con modal previo)
  const handleSendToClient = (quoteId) => {
    openEmailModal('send-to-client', quoteId);
  };

  const executeSendToClient = async (quoteId) => {
    setActionLoading(quoteId);
    try {
      const response = await api.post(`/quotes/${quoteId}/send-to-client`, {}, { headers: getEmailHeaders() });
      
      if (response.data.status === 'simulated') {
        toast.warning(response.data.message);
      } else {
        toast.success(response.data.message);
      }
      
      fetchData();
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

  // ==================== FLUJO IRREGULAR (Protocolo de Excepción) ====================
  const REGULAR_FLOW_MAP = {
    'approve': 'Enviada',
    'repair-complete': 'Aprobada',
    'configure': 'Aprobada',
    'invoice': 'Aprobada',
    'collect': 'Facturada',
    'deliver': 'Pagada',
    'send-to-implementation': 'Pagada',
  };
  const ACTION_LABELS = {
    'approve': 'Aprobación',
    'repair-complete': 'Marcar como Reparada',
    'configure': 'Marcar como Configurada',
    'invoice': 'Factura / Proforma',
    'collect': 'Cobranza',
    'deliver': 'Entregar',
    'send-to-client': 'Enviar al Cliente',
    'send-to-implementation': 'Enviar a Implementación',
  };

  const openBitacoraFlujo = async (quoteId, quoteNumber) => {
    setBitacoraFlujoQuoteId(quoteId);
    setBitacoraFlujoQuoteNumber(quoteNumber);
    setBitacoraFlujoOpen(true);
    setBitacoraFlujoLoading(true);
    try {
      const res = await api.get(`/quotes/${quoteId}/audit-log`);
      setBitacoraFlujoEntries(res.data);
    } catch { toast.error('Error al cargar historial de excepciones'); }
    finally { setBitacoraFlujoLoading(false); }
  };

  const checkIrregularAndProceed = (quoteId, action, proceedFn) => {
    const quote = quotes.find(q => q.quote_id === quoteId);
    const currentStatus = quote?.quote_status || 'Borrador';
    const expectedStatus = REGULAR_FLOW_MAP[action];
    if (expectedStatus && currentStatus !== expectedStatus) {
      // Flujo irregular — abrir modal de excepción
      setPendingAction({ quoteId, action, proceedFn, currentStatus, expectedStatus });
      setExceptionData({ reason: '', regularization_date: '' });
      setExceptionModalOpen(true);
      return;
    }
    // Flujo regular — abrir email modal antes de proceder
    openEmailModal(action, quoteId);
    setPendingAction({ quoteId, action, proceedFn, exceptionHeaders: null });
  };

  const confirmException = () => {
    if (!exceptionData.reason.trim()) { toast.error('Debe ingresar el motivo de la excepción'); return; }
    setExceptionModalOpen(false);
    // Abrir email modal con la excepción pendiente
    openEmailModal(pendingAction.action, pendingAction.quoteId);
    setPendingAction({ ...pendingAction, exceptionHeaders: exceptionData });
  };

  // Abrir modal de workflow para Aprobar (requiere Orden de Compra)
  const openApproveConfirm = (quoteId, exceptionInfo) => {
    setWorkflowQuoteId(quoteId);
    setWorkflowConfig({
      title: 'Aprobación de Cotización',
      description: 'Para registrar la aprobación, debe cargar la Orden de Compra del cliente. Este documento es obligatorio para continuar.',
      category: 'Orden de Compra',
      acceptMultiple: false,
      acceptTypes: '.pdf,.doc,.docx,.xlsx,.xls,.png,.jpg,.jpeg',
      actionLabel: 'Confirmar Aprobación',
      actionColor: 'bg-green-600 hover:bg-green-700',
      actionIcon: <CheckCircle size={20} className="text-green-600" />,
      stateEndpoint: 'approve',
      successMessage: 'Aprobación registrada exitosamente',
      exceptionHeaders: exceptionInfo || null,
      emailHeaders: getEmailHeaders(),
    });
    setWorkflowModalOpen(true);
  };

  // Abrir modal de workflow para Cobrar (requiere Comprobante de Pago - múltiple)
  const openCollectConfirm = (quoteId, exceptionInfo) => {
    setWorkflowQuoteId(quoteId);
    setWorkflowConfig({
      title: 'Registrar Cobranza',
      description: 'Para registrar la cobranza, debe cargar el/los comprobante(s) de pago. Puede subir múltiples archivos si el cliente pagó con diferentes métodos.',
      category: 'Pagos',
      acceptMultiple: true,
      acceptTypes: '.pdf,.png,.jpg,.jpeg,.doc,.docx',
      actionLabel: 'Confirmar Cobranza',
      actionColor: 'bg-emerald-600 hover:bg-emerald-700',
      actionIcon: <Banknote size={20} className="text-emerald-600" />,
      stateEndpoint: 'collect',
      successMessage: 'Cobranza registrada exitosamente',
      exceptionHeaders: exceptionInfo || null,
      emailHeaders: getEmailHeaders(),
    });
    setWorkflowModalOpen(true);
  };

  const handleWorkflowSuccess = () => {
    setWorkflowModalOpen(false);
    setWorkflowQuoteId(null);
    setWorkflowConfig(null);
    fetchData();
  };

  // Enviar a implementación (con soporte multitienda)
  const handleSendToImplementation = async (quoteId, exceptionInfo, storesData = null) => {
    setActionLoading(quoteId);
    try {
      const headers = {};
      if (exceptionInfo) {
        headers['x-exception-reason'] = exceptionInfo.reason;
        headers['x-regularization-date'] = exceptionInfo.regularization_date;
      }
      const body = {};
      if (storesData && storesData.length > 0) {
        body.is_multistore = true;
        body.stores = storesData;
      }
      const response = await api.post(`/quotes/${quoteId}/send-to-implementation`, body, { headers });
      
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

  // ==================== FLUJO MULTITIENDA ====================
  const openMultistoreDialog = (quoteId, exceptionInfo) => {
    setMultistoreQuoteId(quoteId);
    setMultistoreExceptionInfo(exceptionInfo);
    setIsMultistore(null);
    setMultistoreStores([]);
    setMultistoreNewStore({ name: '', box_count: '' });
    setMultistorePhase('ask');
    setMultistoreSending(false);
    setMultistoreDialogOpen(true);
  };

  const getMultistoreQuote = () => quotes.find(q => q.quote_id === multistoreQuoteId);

  const getMultistoreTotalCajas = () => {
    const q = getMultistoreQuote();
    return q?.cantidad_cajas || q?.services?.reduce((sum, s) => Math.max(sum, s.cantidad_cajas || 0), 0) || 1;
  };

  const multistoreAssignedBoxes = multistoreStores.reduce((sum, s) => sum + (s.box_count || 0), 0);

  const handleMultistoreAnswer = (answer) => {
    if (answer) {
      setIsMultistore(true);
      setMultistorePhase('collect');
    } else {
      // No es multitienda — ejecutar directamente
      setMultistoreDialogOpen(false);
      handleSendToImplementation(multistoreQuoteId, multistoreExceptionInfo, null);
    }
  };

  const addMultistoreStore = () => {
    const name = multistoreNewStore.name.trim();
    const boxCount = parseInt(multistoreNewStore.box_count) || 0;
    if (!name) { toast.error('Ingrese el nombre de la tienda'); return; }
    if (boxCount <= 0) { toast.error('La cantidad de cajas debe ser mayor a 0'); return; }
    const totalCajas = getMultistoreTotalCajas();
    const remaining = totalCajas - multistoreAssignedBoxes;
    if (boxCount > remaining) { toast.error(`Solo quedan ${remaining} caja(s) por asignar`); return; }
    setMultistoreStores([...multistoreStores, { name, box_count: boxCount }]);
    setMultistoreNewStore({ name: '', box_count: '' });
  };

  const removeMultistoreStore = (index) => {
    setMultistoreStores(multistoreStores.filter((_, i) => i !== index));
  };

  const confirmMultistore = async () => {
    const totalCajas = getMultistoreTotalCajas();
    if (multistoreAssignedBoxes !== totalCajas) {
      toast.error(`Debe asignar exactamente ${totalCajas} caja(s). Asignadas: ${multistoreAssignedBoxes}`);
      return;
    }
    setMultistoreSending(true);
    setMultistoreDialogOpen(false);
    await handleSendToImplementation(multistoreQuoteId, multistoreExceptionInfo, multistoreStores);
    setMultistoreSending(false);
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
        autoBancos: isAuto,
        // Restaurar overrides guardados
        bancosOverride: s.bancosOverride || null,
        totalOverride: s.totalOverride || null
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
      // Buscar concepto por defecto - matching más preciso
      const concept = SETUP_CONCEPTS.find(c => {
        const itemLower = (s.item_name || '').toLowerCase();
        const conceptLower = c.name.toLowerCase();
        return itemLower === conceptLower || 
               itemLower.includes(conceptLower) || 
               conceptLower.includes(itemLower);
      });
      return mapService(s, concept, false);
    });
    
    // Mapear recurrentes básicos preservando lockBancos
    // Matching más preciso: primero intentar coincidencia exacta, luego parcial
    const recurringBasicItems = services.filter(s => getCategory(s) === 'recurring_basic').map(s => {
      const itemName = s.item_name || '';
      const itemLower = itemName.toLowerCase();
      // Primero buscar coincidencia exacta
      let concept = RECURRING_BASIC_CONCEPTS.find(c => c.name.toLowerCase() === itemLower);
      // Si no hay coincidencia exacta, buscar la coincidencia más larga (más específica)
      if (!concept) {
        const matches = RECURRING_BASIC_CONCEPTS.filter(c => 
          itemLower.includes(c.name.toLowerCase()) || c.name.toLowerCase().includes(itemLower)
        );
        // Elegir la coincidencia más larga (más específica)
        if (matches.length > 0) {
          concept = matches.reduce((a, b) => a.name.length > b.name.length ? a : b);
        }
      }
      // Es auto-vinculado si fue agregado automáticamente (generalmente tiene isAutoLinked en BD)
      // o si su nombre contiene patrones típicos de items auto-vinculados
      const isAutoLinked = s.isAutoLinked || 
                          (itemName.includes('Recurrente') && !concept) ||
                          (itemName.includes('Suscripción') && !concept);
      return mapService(s, concept, isAutoLinked);
    });
    
    // Mapear otros recurrentes preservando lockBancos
    const recurringOtherItems = services.filter(s => getCategory(s) === 'recurring_other').map(s => {
      const itemLower = (s.item_name || '').toLowerCase();
      let concept = RECURRING_OTHER_CONCEPTS.find(c => c.name.toLowerCase() === itemLower);
      if (!concept) {
        const matches = RECURRING_OTHER_CONCEPTS.filter(c => 
          itemLower.includes(c.name.toLowerCase()) || c.name.toLowerCase().includes(itemLower)
        );
        if (matches.length > 0) {
          concept = matches.reduce((a, b) => a.name.length > b.name.length ? a : b);
        }
      }
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
      requires_pinpad_config: quote.requires_pinpad_config !== false,
      requires_vpn: quote.requires_vpn !== false,
      setup_items: setupItems,
      recurring_basic_items: recurringBasicItems,
      recurring_other_items: recurringOtherItems,
      additional_items: additionalItems,
      descuento: quote.descuento || 0,
      descuento_setup: quote.descuento_setup || 0,
      descuento_recurrente: quote.descuento_recurrente || 0,
      notes: quote.notes || ''
    });
    
    // Load PG data if it's a Payment Gateway quote
    if (quote.quote_type === 'GATEWAY') {
      setPgSetupItems(quote.pg_setup_items || []);
      setPgTransactionRange(quote.pg_transaction_range || null);
    }
    
    // Restaurar estado de "Cliente en Producción"
    setIsProductionClient(quote.is_production_client || false);
    if (quote.production_items && quote.production_items.length > 0) {
      setProductionItems(quote.production_items.map(item => ({
        id: `prod_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        service_id: item.service_id || '',
        medio_pago_name: item.item_name || item.medio_pago_name || item.concepto || '',
        cantidad_cajas: item.cantidad_cajas || 1,
        cantidad_bancos: item.cantidad_bancos || 1,
        tarifa: item.tarifa || item.unit_price_usd || 0,
        type: 'production_recurring'
      })));
    } else {
      setProductionItems([]);
    }
    
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
          total_usd: item.totalOverride || ((item.tarifa || item.unit_price_usd || 0) * (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1)),
          cantidad_cajas: item.cantidad_cajas || 1,
          cantidad_bancos: item.cantidad_bancos || 1,
          lockBancos: item.lockBancos || false,
          autoBancos: item.autoBancos || false,
          bancosOverride: item.bancosOverride || null,
          totalOverride: item.totalOverride || null
        })),
        ...quoteData.recurring_basic_items.map(item => ({ 
          item_type: 'recurring_basic',
          item_name: item.medio_pago_name || item.name || '',
          quantity: (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1),
          unit_price_usd: item.tarifa || item.unit_price_usd || 0,
          total_usd: (item.tarifa || item.unit_price_usd || 0) * (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1),
          cantidad_cajas: item.cantidad_cajas || 1,
          cantidad_bancos: item.cantidad_bancos || 1,
          lockBancos: item.lockBancos || false,
          isAutoLinked: item.isAutoLinked || false
        })),
        ...quoteData.recurring_other_items.map(item => ({ 
          item_type: 'recurring_other',
          item_name: item.medio_pago_name || item.name || '',
          quantity: (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1),
          unit_price_usd: item.tarifa || item.unit_price_usd || 0,
          total_usd: (item.tarifa || item.unit_price_usd || 0) * (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1),
          cantidad_cajas: item.cantidad_cajas || 1,
          cantidad_bancos: item.cantidad_bancos || 1,
          lockBancos: item.lockBancos || false
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
        })),
        // Items de cliente en producción
        ...productionItems.map(item => ({
          item_type: 'production_recurring',
          item_name: item.medio_pago_name || item.name || '',
          quantity: (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1),
          unit_price_usd: item.tarifa || 0,
          total_usd: (item.tarifa || 0) * (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1),
          cantidad_cajas: item.cantidad_cajas || 1,
          cantidad_bancos: item.cantidad_bancos || 1
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
        descuento_setup: quoteData.descuento_setup || 0,
        descuento_recurrente: quoteData.descuento_recurrente || 0,
        requires_pinpad_config: quoteData.requires_pinpad_config !== false,
        requires_vpn: quoteData.requires_vpn !== false,
        notes: quoteData.notes,
        cantidad_cajas: quoteData.cantidad_cajas || 1,
        cantidad_bancos: quoteData.cantidad_bancos || 1,
        is_production_client: isProductionClient,
        production_items: productionItems.map(item => ({
          item_name: item.medio_pago_name,
          cantidad_cajas: item.cantidad_cajas || 1,
          cantidad_bancos: item.cantidad_bancos || 1,
          tarifa: item.tarifa || 0,
          total: (item.tarifa || 0) * (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1)
        }))
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
      requires_pinpad_config: true,
      requires_vpn: true,
      setup_items: [],
      recurring_basic_items: [],
      recurring_other_items: [],
      additional_items: [],
      descuento: 0,
      descuento_setup: 0,
      descuento_recurrente: 0,
      notes: ''
    });
    setIsEditing(false);
    setEditingQuoteId(null);
    // Reset PG state
    setPgSetupItems([]);
    setPgTransactionRange(null);
    setPgSelectedMedioPago('');
    setPgSelectedBankId('');
    setPgShowRecurringTable(false);
    setPgFilteredProducts([]);
    // Reset production client
    setIsProductionClient(false);
    setProductionItems([]);
    setProductionSelectedServiceId('');
  };

  // Marcar reparación como completada
  const handleRepairComplete = async (quoteId) => {
    setActionLoading(quoteId);
    try {
      const headers = getEmailHeaders();
      const response = await api.post(`/quotes/${quoteId}/repair-complete`, {}, { headers });
      if (response.data.status === 'simulated') {
        toast.warning(response.data.message);
      } else {
        toast.success(response.data.message);
      }
      fetchData();
    } catch (error) {
      console.error('Error marking repair complete:', error);
      toast.error(error.response?.data?.detail || 'Error al marcar reparación como completada');
    } finally {
      setActionLoading(null);
    }
  };

  // Marcar Fast Track como Configurada
  const handleConfigure = async (quoteId) => {
    setActionLoading(quoteId);
    try {
      const headers = getEmailHeaders();
      const response = await api.post(`/quotes/${quoteId}/configure`, {}, { headers });
      if (response.data.status === 'simulated') {
        toast.warning(response.data.message);
      } else {
        toast.success(response.data.message);
      }
      fetchData();
    } catch (error) {
      console.error('Error marking as configured:', error);
      toast.error(error.response?.data?.detail || 'Error al marcar como configurada');
    } finally {
      setActionLoading(null);
    }
  };

  // Abrir modal de factura
  // Abrir modal de workflow para Facturar (requiere Factura)
  const openInvoiceModal = (quoteId) => {
    const quote = quotes.find(q => q.quote_id === quoteId);
    const currentStatus = quote?.quote_status || 'Borrador';
    const isRepairQuote = quote?.quote_category === 'repair';
    const isFastTrack = quote?.quote_category === 'fast_track';
    const expectedStatus = isRepairQuote ? 'Reparada' : isFastTrack ? 'Configurada' : 'Aprobada';
    const isIrregular = currentStatus !== expectedStatus;
    if (isIrregular) {
      setPendingAction({ quoteId, action: 'invoice', proceedFn: _openInvoiceModalDirect, currentStatus, expectedStatus });
      setExceptionData({ reason: '', regularization_date: '' });
      setExceptionModalOpen(true);
      return;
    }
    // Flujo regular — abrir email modal
    openEmailModal('invoice', quoteId);
    setPendingAction({ quoteId, action: 'invoice', proceedFn: _openInvoiceModalDirect, exceptionHeaders: null });
  };

  const _openInvoiceModalDirect = (quoteId, exceptionInfo) => {
    setWorkflowQuoteId(quoteId);
    setWorkflowConfig({
      title: 'Factura / Proforma',
      description: 'Para registrar la facturación, debe cargar el documento fiscal (Factura o Proforma). Este archivo se guardará automáticamente en los anexos.',
      category: 'Factura',
      acceptMultiple: false,
      acceptTypes: '.pdf,.doc,.docx,.xlsx,.xls,.png,.jpg,.jpeg',
      actionLabel: 'Confirmar Factura / Proforma',
      actionColor: 'bg-purple-600 hover:bg-purple-700',
      actionIcon: <Receipt size={20} className="text-purple-600" />,
      stateEndpoint: 'invoice',
      successMessage: 'Factura / Proforma registrada exitosamente',
      extraFields: [
        { name: 'invoice_number', label: 'Número de Factura', placeholder: 'Ej: FAC-001234', required: false }
      ],
      exceptionHeaders: exceptionInfo || null,
      emailHeaders: getEmailHeaders(),
    });
    setWorkflowModalOpen(true);
  };

  // Entregar cotización — abre dialog correspondiente según categoría
  const handleDeliverQuote = async (quoteId, exceptionInfo) => {
    const quote = quotes.find(q => q.quote_id === quoteId);
    const isRepairQuote = quote?.quote_category === 'repair';
    setDeliveryQuoteId(quoteId);
    setDeliveryExceptionInfo(exceptionInfo || null);
    if (isRepairQuote) {
      setRepairDeliveryDialogOpen(true);
    } else {
      setDeliveryDialogOpen(true);
    }
  };

  const selectedClient = clients.find(c => c.client_id === quoteData.client_id) || 
    clientSearchResults.find(c => c.client_id === quoteData.client_id);
  const selectedIntegrator = integrators.find(i => i.integrator_id === quoteData.integrator_id);
  // Campos opcionales - no buscar si el valor es "none"
  const selectedPinpad = quoteData.pinpad_id && quoteData.pinpad_id !== 'none' 
    ? pinpads.find(p => p.hardware_id === quoteData.pinpad_id) 
    : null;
  const selectedSponsorBank = quoteData.sponsor_bank_id && quoteData.sponsor_bank_id !== 'none'
    ? banks.find(b => b.bank_id === quoteData.sponsor_bank_id)
    : null;
  
  // Detectar si es cotización Payment Gateway o MPOS
  const isPaymentGateway = quoteData.quote_type === 'GATEWAY';
  const isMPOS = quoteData.quote_type === 'MPOS' || quoteData.quote_type === 'FAST_TRACK';
  const isFastTrackType = quoteData.quote_type === 'FAST_TRACK';
  
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
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button data-testid="create-quote-button" className="bg-brand-green-600 hover:bg-brand-green-700 text-white">
                  <Plus size={20} className="mr-2" />
                  Nueva Implementación
                  <ChevronDown size={16} className="ml-2" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-72">
                <DropdownMenuItem onClick={() => openWizard('PYME')} className="py-3 cursor-pointer" data-testid="new-impl-pyme">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-emerald-100 flex items-center justify-center">
                      <Users size={16} className="text-emerald-700" />
                    </div>
                    <div>
                      <p className="font-medium text-sm">Clientes Pymes</p>
                      <p className="text-xs text-slate-500">Flujos estandarizados y ágiles</p>
                    </div>
                  </div>
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => openWizard('CORP')} className="py-3 cursor-pointer" data-testid="new-impl-corp">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center">
                      <Building2 size={16} className="text-blue-700" />
                    </div>
                    <div>
                      <p className="font-medium text-sm">Clientes Corporativos</p>
                      <p className="text-xs text-slate-500">Proyectos de gran envergadura</p>
                    </div>
                  </div>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <Button onClick={() => setEquipmentWizardOpen(true)} data-testid="create-equipment-quote-button" className="bg-brand-blue-600 hover:bg-brand-blue-700 text-white">
              <Plus size={20} className="mr-2" />
              Nueva Cotización: Equipos, Accesorios y Reparaciones
            </Button>
          </div>

          {/* Filtros Rápidos */}
          <QuoteFilters
            clients={clients}
            filterClient={filterClient} setFilterClient={setFilterClient}
            filterStatus={filterStatus} setFilterStatus={setFilterStatus}
            filterCategory={filterCategory} setFilterCategory={setFilterCategory}
            filterSegment={filterSegment} setFilterSegment={setFilterSegment}
            filterDateFrom={filterDateFrom} setFilterDateFrom={setFilterDateFrom}
            filterDateTo={filterDateTo} setFilterDateTo={setFilterDateTo}
          />

          {/* Widget de Cotizaciones Irregulares */}
          {irregularCount > 0 && (
            <div className="mb-4 flex items-center gap-3 bg-orange-50 border border-orange-200 rounded-lg px-4 py-3 cursor-pointer hover:bg-orange-100 transition-colors"
              onClick={() => { setFilterStatus('all'); /* Future: filter irregular only */ }}
              data-testid="irregular-widget">
              <div className="w-10 h-10 rounded-full bg-orange-500 text-white flex items-center justify-center font-bold text-lg shrink-0">{irregularCount}</div>
              <div>
                <p className="text-sm font-semibold text-orange-800">Cotizaciones en Estado Irregular</p>
                <p className="text-xs text-orange-600">Tienen pasos saltados pendientes de regularización</p>
              </div>
            </div>
          )}

          {/* Panel de Gestión Único - Todas las Cotizaciones */}
          <QuotesTable
            quotes={quotes}
            clients={clients}
            filterClient={filterClient}
            filterStatus={filterStatus}
            filterCategory={filterCategory}
            filterSegment={filterSegment}
            filterDateFrom={filterDateFrom}
            filterDateTo={filterDateTo}
            actionLoading={actionLoading}
            onOpenAnexos={(quote) => {
              setAnexosQuoteId(quote.quote_id);
              setAnexosQuoteNumber(quote.quote_number);
              setAnexosOpen(true);
            }}
            onDownloadPDF={downloadPDF}
            onEditQuote={handleEditQuote}
            onSendToClient={handleSendToClient}
            onApprove={(id) => checkIrregularAndProceed(id, 'approve', openApproveConfirm)}
            onInvoice={openInvoiceModal}
            onCollect={(id) => checkIrregularAndProceed(id, 'collect', openCollectConfirm)}
            onDeliver={(id) => checkIrregularAndProceed(id, 'deliver', handleDeliverQuote)}
            onSendToImplementation={(id) => checkIrregularAndProceed(id, 'send-to-implementation', handleSendToImplementation)}
            onRepairComplete={(id) => {
              openEmailModal('repair-complete', id);
              setPendingAction({ quoteId: id, action: 'repair-complete', proceedFn: handleRepairComplete, exceptionHeaders: null });
            }}
            onConfigure={(id) => {
              openEmailModal('configure', id);
              setPendingAction({ quoteId: id, action: 'configure', proceedFn: handleConfigure, exceptionHeaders: null });
            }}
            onOpenBitacoraFlujo={openBitacoraFlujo}
            onDelete={openDeleteConfirm}
            clearFilters={() => {
              setFilterClient('');
              setFilterStatus('');
              setFilterCategory('');
              setFilterSegment('');
              setFilterDateFrom('');
              setFilterDateTo('');
            }}
          />

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
                <DialogTitle className="font-manrope text-2xl flex items-center gap-3">
                  {isEditing ? 'Modificar Cotización (Nueva Versión)' : 'Nueva Implementación'}
                  {!isEditing && quoteData.client_segment && (
                    <span className={`px-3 py-1 text-xs font-semibold rounded-full ${
                      quoteData.client_segment === 'CORP'
                        ? 'bg-blue-100 text-blue-700 border border-blue-300'
                        : 'bg-emerald-100 text-emerald-700 border border-emerald-300'
                    }`} data-testid="segment-badge">
                      {quoteData.client_segment === 'CORP' ? 'Corporativo' : 'Pyme'}
                    </span>
                  )}
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
                        const isMposSelected = value === 'MPOS';
                        const isFastTrack = value === 'FAST_TRACK';
                        const isMposLike = isMposSelected || isFastTrack;
                        
                        // Buscar banco "Mega Soft" para default de Fast Track
                        const megaSoftBank = isFastTrack ? banks.find(b => b.name?.toLowerCase().includes('mega soft') || b.name?.toLowerCase().includes('megasoft')) : null;
                        
                        setQuoteData({ 
                          ...quoteData, 
                          quote_type: value, 
                          medios_pago_items: [], 
                          pricing_model: value === 'GATEWAY' ? 'conventional' : (isMposLike ? 'outsourcing' : ''),
                          requires_vpn: isFastTrack ? false : true,
                          requires_pinpad_config: true,
                          // Defaults para Fast Track
                          integrator_id: isFastTrack ? (quoteData.integrator_id || 'sin_integrador') : (isMposSelected ? quoteData.integrator_id : ''),
                          sponsor_bank_id: isFastTrack ? (megaSoftBank?.bank_id || quoteData.sponsor_bank_id || '') : quoteData.sponsor_bank_id,
                        });
                        setSelectedBankId('');
                        setSelectedMedioPagoId('');
                        setAvailableMediosPago([]);
                        setPgSetupItems([]);
                        setPgTransactionRange(null);
                        setPgShowRecurringTable(false);
                        setPgFilteredProducts([]);
                        if (value === 'GATEWAY') {
                          const pjService = serviceCatalog.find(s => s.gateway_enabled && s.name?.toLowerCase().includes('persona jur'));
                          const pjCost = pjService?.setup_cost_outsourcing || pgDefaults?.costo || 240;
                          setPgSetupItems([{
                            concepto: 'Persona Jurídica',
                            costo: pjCost,
                            banco: 'N/A',
                            observacion: 'Costo Base',
                            fixed: true
                          }]);
                        }
                        // MPOS/Fast Track: auto-inicializar items con outsourcing
                        if (isMposLike) {
                          const cajas = quoteData.cantidad_cajas || 1;
                          const bancos = quoteData.cantidad_bancos || 1;
                          const setupItems = initializeSetupConcepts('outsourcing', cajas, bancos, quoteData.requires_pinpad_config);
                          const recurringBasicItems = initializeRecurringBasicConcepts('outsourcing', cajas, bancos);
                          const recurringOtherItems = initializeRecurringOtherConcepts('outsourcing', cajas, bancos, true);
                          setQuoteData(prev => ({
                            ...prev,
                            quote_type: value,
                            pricing_model: 'outsourcing',
                            setup_items: setupItems,
                            recurring_basic_items: recurringBasicItems,
                            recurring_other_items: recurringOtherItems,
                            additional_items: [],
                          }));
                        }
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
                    <Popover open={clientSearchOpen} onOpenChange={setClientSearchOpen}>
                      <PopoverTrigger asChild>
                        <Button
                          variant="outline"
                          role="combobox"
                          aria-expanded={clientSearchOpen}
                          className="w-full justify-between h-10 font-normal"
                          data-testid="select-client"
                        >
                          {quoteData.client_id ? (
                            <span className="truncate">
                              {selectedClient?.fantasy_name || selectedClient?.legal_name} - {selectedClient?.rif}
                            </span>
                          ) : (
                            <span className="text-muted-foreground">Buscar por nombre o RIF...</span>
                          )}
                          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-[400px] p-0" align="start">
                        <Command shouldFilter={false}>
                          <CommandInput
                            placeholder="Buscar cliente..."
                            value={clientSearchQuery}
                            onValueChange={setClientSearchQuery}
                            data-testid="client-search-input"
                          />
                          <CommandList>
                            <CommandEmpty>{isSearchingClients ? 'Buscando...' : 'No se encontraron clientes.'}</CommandEmpty>
                            <CommandGroup>
                              {clientSearchResults
                                .map((client) => (
                                  <CommandItem
                                    key={client.client_id}
                                    value={`${client.fantasy_name} ${client.rif}`}
                                    onSelect={() => {
                                      setQuoteData(prev => ({ ...prev, client_id: client.client_id }));
                                      setClientSearchOpen(false);
                                      setClientSearchQuery('');
                                    }}
                                    data-testid={`client-option-${client.client_id}`}
                                  >
                                    <Check className={`mr-2 h-4 w-4 ${quoteData.client_id === client.client_id ? 'opacity-100' : 'opacity-0'}`} />
                                    <div className="flex flex-col">
                                      <span className="font-medium">{client.fantasy_name || client.legal_name}</span>
                                      <span className="text-xs text-muted-foreground">{client.rif}</span>
                                    </div>
                                  </CommandItem>
                                ))}
                            </CommandGroup>
                          </CommandList>
                        </Command>
                      </PopoverContent>
                    </Popover>
                  </div>

                  {/* Hide Modelo/Cajas/Bancos for Payment Gateway */}
                  {!isPaymentGateway && (<>
                  {/* Modelo de Precios: oculto para MPOS (forzado a Outsourcing) */}
                  {!isMPOS ? (
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
                          const setupItems = initializeSetupConcepts(value, cajas, bancos, quoteData.requires_pinpad_config);
                          const recurringBasicItems = initializeRecurringBasicConcepts(value, cajas, bancos);
                          const recurringOtherItems = initializeRecurringOtherConcepts(value, cajas, bancos, quoteData.requires_vpn);
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
                  ) : (
                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 block">
                      Modelo de Precios
                    </Label>
                    <div className="h-10 px-3 py-2 bg-slate-100 border border-slate-200 rounded-md flex items-center">
                      <span className="text-sm text-slate-700 font-medium">Outsourcing (fijo MPOS)</span>
                    </div>
                  </div>
                  )}

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
                  </>)}
                </div>

                {/* Parámetros dinámicos VPOS: PinPads y VPN */}
                {!isPaymentGateway && quoteData.pricing_model && (
                  <div className={`grid grid-cols-1 ${isMPOS ? 'md:grid-cols-1' : 'md:grid-cols-2'} gap-4 mt-4 pt-4 border-t border-slate-200`}>
                    <div>
                      <Label className="text-sm font-medium text-slate-700 mb-2 block">
                        ¿Requiere Configuración de {isMPOS ? 'POS' : 'PinPads'}?
                      </Label>
                      <Select
                        value={quoteData.requires_pinpad_config ? 'si' : 'no'}
                        onValueChange={(v) => {
                          const newVal = v === 'si';
                          const cajas = quoteData.cantidad_cajas || 1;
                          const bancos = quoteData.cantidad_bancos || 1;
                          if (newVal && !quoteData.requires_pinpad_config) {
                            // Agregar ítem de vuelta
                            const pinpadConcept = SETUP_CONCEPTS.find(c => c.name === 'Configuración dispositivo (Pinpad o POS)');
                            if (pinpadConcept) {
                              const prices = findServicePriceWithModel(pinpadConcept.name, quoteData.pricing_model);
                              const pinpadItem = {
                                id: `setup_${pinpadConcept.name}`,
                                medio_pago_name: pinpadConcept.name,
                                cantidad_cajas: cajas,
                                cantidad_bancos: 1,
                                tarifa: prices.setup_cost,
                                isDefault: true,
                                type: 'setup',
                                lockBancos: true,
                                autoBancos: false
                              };
                              // Insertar en posición 1 (después del primer concepto)
                              const newSetup = [...quoteData.setup_items];
                              newSetup.splice(1, 0, pinpadItem);
                              setQuoteData({ ...quoteData, requires_pinpad_config: true, setup_items: newSetup });
                            }
                          } else if (!newVal && quoteData.requires_pinpad_config) {
                            // Eliminar ítem de Configuración dispositivo
                            const newSetup = quoteData.setup_items.filter(
                              i => i.medio_pago_name !== 'Configuración dispositivo (Pinpad o POS)'
                            );
                            setQuoteData({ ...quoteData, requires_pinpad_config: false, setup_items: newSetup });
                          }
                        }}
                      >
                        <SelectTrigger data-testid="select-requires-pinpad">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="si">Sí</SelectItem>
                          <SelectItem value="no">No</SelectItem>
                        </SelectContent>
                      </Select>
                      <p className="text-[10px] text-slate-400 mt-1">
                        {quoteData.requires_pinpad_config
                          ? `Incluye "Configuración dispositivo (${isMPOS ? 'POS' : 'Pinpad o POS'})" en Setup`
                          : 'Excluido del Setup — total recalculado'}
                      </p>
                    </div>

                    {/* VPN toggle: solo VPOS, MPOS asume conectividad estándar */}
                    {!isMPOS && (
                      <div>
                        <Label className="text-sm font-medium text-slate-700 mb-2 block">
                          ¿Requiere VPN?
                        </Label>
                        <Select
                          value={quoteData.requires_vpn ? 'si' : 'no'}
                          onValueChange={(v) => {
                            const newVal = v === 'si';
                            // Actualizar tarifa de "Comunicación Backend" en recurring_other_items
                            const updatedOther = quoteData.recurring_other_items.map(item => {
                              if (item.medio_pago_name.includes('Comunicación Backend')) {
                                const service = serviceCatalog.find(s =>
                                  s.name.toLowerCase().includes('comunicación backend') ||
                                  s.name.toLowerCase().includes('comunicacion backend') ||
                                  item.medio_pago_name.toLowerCase().includes(s.name.toLowerCase())
                                );
                                if (service) {
                                  return {
                                    ...item,
                                    tarifa: newVal
                                      ? (service.monthly_cost_conventional || 0)
                                      : (service.monthly_cost_outsourcing || 0)
                                  };
                                }
                              }
                              return item;
                            });
                            setQuoteData({ ...quoteData, requires_vpn: newVal, recurring_other_items: updatedOther });
                          }}
                        >
                          <SelectTrigger data-testid="select-requires-vpn">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="si">Sí — Costo Conv.</SelectItem>
                            <SelectItem value="no">No — Costo Outs.</SelectItem>
                          </SelectContent>
                        </Select>
                        <p className="text-[10px] text-slate-400 mt-1">
                          {quoteData.requires_vpn
                            ? 'Comunicación Backend usa tarifa Convencional'
                            : 'Comunicación Backend usa tarifa Outsourcing'}
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {isHeaderComplete && (
                  <div className="mt-4 p-3 bg-brand-green-50 border border-brand-green-200 rounded-lg flex items-center gap-2">
                    <CheckCircle2 size={18} className="text-brand-green-600" />
                    <span className="text-sm text-brand-green-700 font-medium">
                      {getQuoteTypeName(quoteData.quote_type)} • {selectedClient?.fantasy_name || selectedClient?.legal_name} - {selectedClient?.rif}
                      {!isPaymentGateway && <> • {getPricingModelName(quoteData.pricing_model)} • {quoteData.cantidad_cajas} cajas • {quoteData.cantidad_bancos} bancos</>}
                    </span>
                  </div>
                )}
              </div>

              {/* SECCIÓN 1.5: Detalles de Integración y Hardware */}
              <div className="bg-gradient-to-r from-slate-50 to-blue-50 rounded-lg p-5 border border-blue-100 mt-4">
                <h3 className="font-semibold text-lg text-slate-800 mb-4 flex items-center gap-2">
                  <Cpu size={20} className="text-brand-blue-600" />
                  {isPaymentGateway ? 'Integrador' : 'Detalles de Integración y Hardware'}
                </h3>
                
                <div className={`grid grid-cols-1 ${isPaymentGateway ? 'md:grid-cols-2' : 'md:grid-cols-4'} gap-4`}>
                  {/* Campo 1: Integrador */}
                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 flex items-center gap-2">
                      <Users size={14} className="text-brand-blue-600" />
                      Integrador {!isMPOS && <span className="text-red-500">*</span>}
                      {isMPOS && <span className="text-slate-400 text-xs font-normal">(Opcional)</span>}
                    </Label>
                    <Select 
                      value={quoteData.integrator_id} 
                      onValueChange={handleIntegratorChange}
                    >
                      <SelectTrigger data-testid="select-integrator">
                        <SelectValue placeholder="Seleccione integrador..." />
                      </SelectTrigger>
                      <SelectContent>
                        {(isMPOS || isPaymentGateway) && (
                          <SelectItem value="sin_integrador">Sin integrador</SelectItem>
                        )}
                        {integrators
                          .filter(i => {
                            if (i.integrator_status !== 'Certificado') return false;
                            if (isPaymentGateway) {
                              return i.integration_modality === 'PG Universal' || i.integration_modality === 'PG No universal';
                            }
                            return true;
                          })
                          .map((integrator) => (
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

                  {/* Campo 2: Modelo de Pinpad/POS - Solo para VPOS/MPOS */}
                  {!isPaymentGateway && (
                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 flex items-center gap-2">
                      <Cpu size={14} className="text-brand-green-600" />
                      {isMPOS ? 'Modelo de POS' : 'Modelo de Pinpad'} <span className="text-slate-400 text-xs font-normal">(Opcional)</span>
                    </Label>
                    <Select 
                      value={quoteData.pinpad_id} 
                      onValueChange={(value) => setQuoteData({ ...quoteData, pinpad_id: value })}
                    >
                      <SelectTrigger data-testid="select-pinpad">
                        <SelectValue placeholder={`Seleccione ${isMPOS ? 'POS' : 'modelo'}...`} />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">Sin {isMPOS ? 'POS' : 'Pinpad'}</SelectItem>
                        {(isMPOS ? posDevices : pinpads).length === 0 ? (
                          <SelectItem value="no-devices" disabled>No hay {isMPOS ? 'POS' : 'Pinpads'} disponibles</SelectItem>
                        ) : (
                          (isMPOS ? posDevices : pinpads).map((device) => (
                            <SelectItem key={device.hardware_id} value={device.hardware_id}>
                              {device.name} {device.price_usd > 0 && `($${device.price_usd})`}
                            </SelectItem>
                          ))
                        )}
                      </SelectContent>
                    </Select>
                  </div>
                  )}

                  {/* Campo 3: Entidad Patrocinadora (Opcional) - Solo para VPOS/MPOS */}
                  {!isPaymentGateway && (
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
                  )}
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

              {/* ====== SECCIÓN PG: Setup de Payment Gateway ====== */}
              {isPaymentGateway && isHeaderComplete && (
                <div className="bg-white rounded-lg p-5 border mt-4">
                  <h3 className="font-semibold text-lg text-slate-800 mb-4 flex items-center gap-2">
                    <span className="w-7 h-7 rounded-full bg-emerald-600 text-white flex items-center justify-center text-sm">2</span>
                    Payment Gateway - Inversión en Setup / Arranque
                  </h3>
                  
                  {/* Auto-load Persona Jurídica */}
                  {pgSetupItems.length === 0 && pgDefaults && (
                    <div className="mb-4">
                      <Button onClick={initPgSetup} className="bg-amber-600 hover:bg-amber-700 text-white" data-testid="pg-init-setup-btn">
                        Cargar concepto base (Persona Jurídica)
                      </Button>
                    </div>
                  )}

                  {/* Agregar medio de pago: BANCO primero, luego selector múltiple */}
                  <div className="bg-slate-50 rounded-lg p-4 border mb-4">
                    <p className="text-xs text-slate-500 mb-3 font-medium uppercase tracking-wide">Agregar Medio de Pago</p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-end">
                      <div>
                        <Label className="text-sm font-medium text-slate-700 mb-2 block">1. Banco</Label>
                        <Select value={pgSelectedBankId} onValueChange={handlePgBankChange}>
                          <SelectTrigger data-testid="pg-select-bank">
                            <SelectValue placeholder="Seleccione banco..." />
                          </SelectTrigger>
                          <SelectContent>
                            {banks.map((bank) => (
                              <SelectItem key={bank.bank_id} value={bank.bank_id}>{bank.name}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <Label className="text-sm font-medium text-slate-700 mb-2 block">2. Concepto(s) (Medio de Pago)</Label>
                        <MultiProductSelector
                          products={pgFilteredProducts}
                          existingItems={pgSetupItems}
                          bankName={banks.find(b => b.bank_id === pgSelectedBankId)?.name || ''}
                          onAdd={addMultiplePgSetupItems}
                          disabled={!pgSelectedBankId}
                          duplicateKey="product_name"
                          existingKey="concepto"
                          existingBankKey="banco"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Tabla de setup items */}
                  {pgSetupItems.length > 0 && (
                    <div className="overflow-x-auto">
                      <table className="w-full border-collapse">
                        <thead>
                          <tr className="bg-slate-100">
                            <th className="border p-2 text-left text-sm font-medium text-slate-700">Concepto</th>
                            <th className="border p-2 text-left text-sm font-medium text-slate-700 w-36">Costo ($)</th>
                            <th className="border p-2 text-left text-sm font-medium text-slate-700">Banco</th>
                            <th className="border p-2 text-left text-sm font-medium text-slate-700">Observación</th>
                            <th className="border p-2 text-center text-sm font-medium text-slate-700 w-16"></th>
                          </tr>
                        </thead>
                        <tbody>
                          {pgSetupItems.map((item, index) => (
                            <tr key={index} className={`hover:bg-slate-50 ${item.fixed ? 'bg-amber-50' : ''}`}>
                              <td className="border p-2 text-sm font-medium">
                                {item.concepto}
                                {item.fixed && <span className="ml-2 text-xs bg-amber-200 text-amber-800 px-1.5 py-0.5 rounded">Fijo</span>}
                              </td>
                              <td className="border p-2">
                                <Input
                                  type="number"
                                  step="0.01"
                                  value={item.costo}
                                  onChange={(e) => updatePgSetupItem(index, 'costo', e.target.value)}
                                  data-testid={`pg-setup-cost-${index}`}
                                  className="h-8 text-sm"
                                />
                              </td>
                              <td className="border p-2 text-sm">{item.banco}</td>
                              <td className="border p-2">
                                <Input
                                  value={item.observacion}
                                  onChange={(e) => updatePgSetupItem(index, 'observacion', e.target.value)}
                                  data-testid={`pg-setup-obs-${index}`}
                                  className="h-8 text-sm"
                                  placeholder="Observación..."
                                />
                              </td>
                              <td className="border p-2 text-center">
                                {!item.fixed && (
                                  <Button variant="ghost" size="sm" onClick={() => removePgSetupItem(index)} data-testid={`pg-remove-item-${index}`} className="text-red-500 hover:text-red-700 h-7 w-7 p-0">
                                    <Trash2 size={14} />
                                  </Button>
                                )}
                              </td>
                            </tr>
                          ))}
                          <tr className="bg-emerald-50 font-semibold">
                            <td className="border p-2 text-sm text-right" colSpan={1}>Total Setup:</td>
                            <td className="border p-2 text-sm text-emerald-700">${pgSetupTotal.toFixed(2)}</td>
                            <td className="border p-2" colSpan={3}></td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  )}

                  {pgSetupItems.length === 0 && !pgDefaults && (
                    <div className="text-center py-8 text-slate-400">
                      Cargando configuración...
                    </div>
                  )}
                </div>
              )}

              {/* ====== SECCIÓN PG: Costos Recurrentes ====== */}
              {isPaymentGateway && isHeaderComplete && pgSetupItems.length > 0 && pgRecurringCostsTable && (
                <div className="bg-white rounded-lg p-5 border mt-4">
                  <h3 className="font-semibold text-lg text-slate-800 mb-4 flex items-center gap-2">
                    <span className="w-7 h-7 rounded-full bg-blue-600 text-white flex items-center justify-center text-sm">3</span>
                    Costos Recurrentes Mensuales
                  </h3>
                  
                  <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                    <p className="text-sm text-blue-700">
                      Medios de Pago seleccionados: <strong>{pgMediosPagoCount}</strong>
                      {pgMediosPagoCount === 0 && <span className="text-amber-600 ml-2">(Agregue al menos un medio de pago para calcular recurrentes)</span>}
                    </p>
                  </div>

                  {!pgShowRecurringTable ? (
                    <div className="text-center py-4">
                      <Button 
                        onClick={generatePgRecurringTable} 
                        className="bg-blue-600 hover:bg-blue-700 text-white px-6"
                        disabled={pgMediosPagoCount === 0}
                        data-testid="pg-generate-recurring-btn"
                      >
                        <RefreshCw size={16} className="mr-2" />
                        Generar Tabla de Recurrentes
                      </Button>
                    </div>
                  ) : (
                    <>
                      <div className="mb-3 flex items-center justify-between">
                        <p className="text-sm text-slate-600">
                          Tabla calculada para <strong>{Math.min(pgMediosPagoCount, 11)}</strong> medio(s) de pago
                        </p>
                        <Button 
                          variant="outline" size="sm"
                          onClick={generatePgRecurringTable}
                          data-testid="pg-refresh-recurring-btn"
                        >
                          <RefreshCw size={14} className="mr-1" /> Recalcular
                        </Button>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full border-collapse text-sm">
                          <thead>
                            <tr className="bg-blue-100">
                              <th className="border p-2 text-left font-medium text-blue-800">Rango</th>
                              <th className="border p-2 text-left font-medium text-blue-800">Transacciones</th>
                              <th className="border p-2 text-right font-medium text-blue-800">Total $ Base</th>
                              <th className="border p-2 text-right font-medium text-blue-800">Precio Tope por Rango</th>
                            </tr>
                          </thead>
                          <tbody>
                            {pgFullRecurringTable.map((row, idx) => (
                              <tr key={row.rango} className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                                <td className="border p-2 font-medium">{row.rango}</td>
                                <td className="border p-2">{row.label}</td>
                                <td className="border p-2 text-right font-semibold text-emerald-700">
                                  {row.base !== null && row.base !== undefined ? `$${row.base.toFixed(2)}` : 'Negociable'}
                                </td>
                                <td className="border p-2 text-right">
                                  {row.tope !== null && row.tope !== undefined ? `$${row.tope.toFixed(6)}` : 'N/A'}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </div>
              )}

              {/* SECCIÓN 2: Selección de Medios de Pago - Solo para VPOS/MPOS */}
              {!isPaymentGateway && isHeaderComplete && (
                <div className="bg-white rounded-lg p-5 border mt-4">
                  <h3 className="font-semibold text-lg text-slate-800 mb-4 flex items-center gap-2">
                    <span className="w-7 h-7 rounded-full bg-brand-blue-600 text-white flex items-center justify-center text-sm">2</span>
                    Selección de Medios de Pago
                  </h3>
                  
                  <div className="bg-slate-50 rounded-lg p-4 border mb-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-end">
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
                          Medios de Pago
                        </Label>
                        <MultiProductSelector
                          products={availableMediosPago}
                          existingItems={quoteData.additional_items}
                          bankName={banks.find(b => b.bank_id === selectedBankId)?.name || ''}
                          onAdd={addMultipleMediosPago}
                          disabled={!selectedBankId}
                          duplicateKey="product_name"
                          existingKey="medio_pago_name"
                          existingBankKey="bank_name"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* SECCIÓN 3: Matriz de Resumen - Set Up (EXCLUSIVO) - Solo para VPOS/MPOS */}
              {!isPaymentGateway && canShowItems && quoteData.setup_items.length > 0 && (
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
                                {item.autoBancos && !item.bancosOverride && <span className="px-1.5 py-0.5 text-xs font-medium bg-purple-100 text-purple-700 rounded">Auto</span>}
                                {item.autoBancos && item.bancosOverride && <span className="px-1.5 py-0.5 text-xs font-medium bg-amber-100 text-amber-700 rounded">Manual</span>}
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
                                <div className="flex items-center justify-center gap-1">
                                  {(item.bancosOverride !== undefined && item.bancosOverride !== null) && (
                                    <Unlock size={12} className="text-amber-500" title="Valor editado manualmente (auto-cálculo desactivado)" />
                                  )}
                                  <Input
                                    type="number"
                                    min="1"
                                    value={item.cantidad_bancos}
                                    onChange={(e) => {
                                      const val = parseInt(e.target.value) || 1;
                                      const autoVal = Math.max(1, quoteData.additional_items.length);
                                      if (val === autoVal || e.target.value === '') {
                                        // Si el valor coincide con el auto-cálculo, quitar override
                                        const updatedItems = [...quoteData.setup_items];
                                        updatedItems[index] = { ...updatedItems[index], cantidad_bancos: autoVal, bancosOverride: undefined, totalOverride: undefined };
                                        setQuoteData({ ...quoteData, setup_items: updatedItems });
                                      } else {
                                        const updatedItems = [...quoteData.setup_items];
                                        updatedItems[index] = { ...updatedItems[index], cantidad_bancos: val, bancosOverride: val, totalOverride: undefined };
                                        setQuoteData({ ...quoteData, setup_items: updatedItems });
                                      }
                                    }}
                                    className={`w-16 h-7 text-center text-sm mx-auto ${(item.bancosOverride !== undefined && item.bancosOverride !== null) ? 'border-amber-400 bg-amber-50' : 'border-purple-300 bg-purple-50'}`}
                                    data-testid={`setup-bancos-${index}`}
                                  />
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
                              {item.autoBancos ? (
                                <div className="flex items-center justify-end gap-1">
                                  {item.totalOverride !== undefined && item.totalOverride !== null && (
                                    <Unlock size={12} className="text-amber-500" title="Monto editado manualmente" />
                                  )}
                                  <Input
                                    type="number"
                                    min="0"
                                    step="0.01"
                                    value={item.totalOverride !== undefined && item.totalOverride !== null ? item.totalOverride : calcularTotalEstandar(item)}
                                    onChange={(e) => {
                                      const val = parseFloat(e.target.value);
                                      const stdTotal = calcularTotalEstandar(item);
                                      // If value matches standard calc, remove override
                                      if (val === stdTotal || e.target.value === '') {
                                        updateSetupItem(index, 'totalOverride', undefined);
                                      } else {
                                        updateSetupItem(index, 'totalOverride', val || 0);
                                      }
                                    }}
                                    className={`w-24 h-7 text-right text-sm font-mono ${item.totalOverride !== undefined && item.totalOverride !== null ? 'border-amber-400 bg-amber-50' : ''}`}
                                    data-testid={`setup-total-${index}`}
                                  />
                                </div>
                              ) : (
                                <span>${calcularTotal(item).toFixed(2)}</span>
                              )}
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
                          <td colSpan={5} className="px-3 py-2 text-right font-semibold border border-slate-300">Descuento Setup:</td>
                          <td className="px-3 py-2 text-center border border-slate-300">
                            <div className="flex items-center justify-center gap-1">
                              <Input
                                type="number"
                                min="0"
                                max="100"
                                step="0.01"
                                value={quoteData.descuento_setup}
                                onChange={(e) => setQuoteData({ ...quoteData, descuento_setup: parseFloat(e.target.value) || 0 })}
                                className="w-16 h-7 text-right text-sm font-mono"
                                data-testid="descuento-setup-input"
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
                          <td colSpan={5} className="px-3 py-2 text-right font-semibold border border-slate-300">Descuento Recurrente:</td>
                          <td className="px-3 py-2 text-center border border-slate-300">
                            <div className="flex items-center justify-center gap-1">
                              <Input
                                type="number"
                                min="0"
                                max="100"
                                step="0.01"
                                value={quoteData.descuento_recurrente}
                                onChange={(e) => setQuoteData({ ...quoteData, descuento_recurrente: parseFloat(e.target.value) || 0 })}
                                className="w-16 h-7 text-right text-sm font-mono"
                                data-testid="descuento-recurrente-input"
                              />
                              <span className="text-sm">%</span>
                            </div>
                          </td>
                          <td className="px-3 py-2 text-right font-mono font-bold text-amber-600 border border-slate-300 w-32">-${montoDescuentoRecurrente.toFixed(2)}</td>
                        </tr>
                        <tr className="bg-green-100">
                          <td colSpan={6} className="px-3 py-2 text-right font-bold border border-slate-300">TOTAL RECURRENTE NETO:</td>
                          <td className="px-3 py-2 text-right font-mono font-bold text-brand-green-700 border border-slate-300 text-lg w-32">${totalNetoRecurrente.toFixed(2)}</td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>

                  {/* SECCIÓN: Cliente en Producción */}
                  <div className="mt-4 bg-white rounded-lg border border-orange-200 overflow-hidden" data-testid="production-client-section">
                    <div className="bg-gradient-to-r from-orange-500 to-orange-600 text-white px-4 py-2.5 flex items-center justify-between">
                      <span className="font-semibold">Cliente en Producción</span>
                    </div>
                    <div className="p-4">
                      <div className="flex items-center gap-4 mb-3">
                        <span className="text-sm font-medium text-slate-700">¿Este cliente ya se encuentra en producción?</span>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant={isProductionClient ? 'default' : 'outline'}
                            onClick={() => setIsProductionClient(true)}
                            className={`h-8 px-4 ${isProductionClient ? 'bg-orange-600 hover:bg-orange-700' : ''}`}
                            data-testid="production-client-yes"
                          >
                            Sí
                          </Button>
                          <Button
                            size="sm"
                            variant={!isProductionClient ? 'default' : 'outline'}
                            onClick={() => { setIsProductionClient(false); setProductionItems([]); }}
                            className={`h-8 px-4 ${!isProductionClient ? 'bg-slate-600 hover:bg-slate-700' : ''}`}
                            data-testid="production-client-no"
                          >
                            No
                          </Button>
                        </div>
                      </div>

                      {isProductionClient && (
                        <div className="space-y-3 mt-3 pt-3 border-t border-orange-100">
                          <p className="text-xs text-slate-500">Seleccione conceptos recurrentes adicionales que apliquen para este cliente en producción.</p>
                          
                          {/* Selector de servicio recurrente */}
                          <div className="flex items-end gap-2">
                            <div className="flex-1">
                              <Label className="text-xs font-medium text-slate-600 mb-1 block">Concepto Recurrente</Label>
                              <Select value={productionSelectedServiceId} onValueChange={setProductionSelectedServiceId}>
                                <SelectTrigger className="h-9" data-testid="production-service-select">
                                  <SelectValue placeholder="Seleccionar concepto..." />
                                </SelectTrigger>
                                <SelectContent>
                                  {serviceCatalog
                                    .filter(s => s.application_type === 'recurring' || s.application_type === 'both')
                                    .filter(s => !productionItems.find(pi => pi.service_id === s.service_id))
                                    .map(s => (
                                      <SelectItem key={s.service_id} value={s.service_id}>
                                        {s.name}
                                      </SelectItem>
                                    ))
                                  }
                                </SelectContent>
                              </Select>
                            </div>
                            <Button
                              size="sm"
                              className="h-9 bg-orange-600 hover:bg-orange-700"
                              disabled={!productionSelectedServiceId}
                              data-testid="production-add-btn"
                              onClick={() => {
                                const service = serviceCatalog.find(s => s.service_id === productionSelectedServiceId);
                                if (!service) return;
                                const isOutsourcing = quoteData.pricing_model === 'outsourcing';
                                const tarifa = isOutsourcing ? (service.monthly_cost_outsourcing || 0) : (service.monthly_cost_conventional || 0);
                                setProductionItems([...productionItems, {
                                  id: `prod_${Date.now()}`,
                                  service_id: service.service_id,
                                  medio_pago_name: service.name,
                                  cantidad_cajas: quoteData.cantidad_cajas || 1,
                                  cantidad_bancos: quoteData.cantidad_bancos || 1,
                                  tarifa: tarifa,
                                  type: 'production_recurring'
                                }]);
                                setProductionSelectedServiceId('');
                              }}
                            >
                              <Plus size={14} className="mr-1" /> Agregar
                            </Button>
                          </div>

                          {/* Tabla de items de producción */}
                          {productionItems.length > 0 && (
                            <div className="overflow-x-auto">
                              <table className="w-full border-collapse text-sm">
                                <thead>
                                  <tr className="bg-orange-50">
                                    <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-16">N°</th>
                                    <th className="px-3 py-2 text-left font-semibold text-slate-700 border border-slate-300">Concepto</th>
                                    <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-24">Cajas</th>
                                    <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-24">Bancos</th>
                                    <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-28">Tarifa (USD)</th>
                                    <th className="px-3 py-2 text-center font-semibold text-orange-600 border border-slate-300 w-32 bg-orange-50">Total USD</th>
                                    <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-12"></th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {productionItems.map((item, idx) => (
                                    <tr key={item.id} className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                                      <td className="px-3 py-2 text-center font-medium border border-slate-300">{idx + 1}</td>
                                      <td className="px-3 py-2 border border-slate-300 font-medium text-slate-900">{item.medio_pago_name}</td>
                                      <td className="px-3 py-2 text-center border border-slate-300">
                                        <Input
                                          type="number" min="1" value={item.cantidad_cajas}
                                          onChange={(e) => {
                                            const updated = [...productionItems];
                                            updated[idx] = { ...updated[idx], cantidad_cajas: parseInt(e.target.value) || 1 };
                                            setProductionItems(updated);
                                          }}
                                          className="w-16 h-7 text-center text-sm mx-auto"
                                          data-testid={`production-cajas-${idx}`}
                                        />
                                      </td>
                                      <td className="px-3 py-2 text-center border border-slate-300">
                                        <Input
                                          type="number" min="1" value={item.cantidad_bancos}
                                          onChange={(e) => {
                                            const updated = [...productionItems];
                                            updated[idx] = { ...updated[idx], cantidad_bancos: parseInt(e.target.value) || 1 };
                                            setProductionItems(updated);
                                          }}
                                          className="w-16 h-7 text-center text-sm mx-auto"
                                          data-testid={`production-bancos-${idx}`}
                                        />
                                      </td>
                                      <td className="px-3 py-2 text-center border border-slate-300">
                                        <Input
                                          type="number" min="0" step="0.01" value={item.tarifa}
                                          onChange={(e) => {
                                            const updated = [...productionItems];
                                            updated[idx] = { ...updated[idx], tarifa: parseFloat(e.target.value) || 0 };
                                            setProductionItems(updated);
                                          }}
                                          className="w-20 h-7 text-right text-sm mx-auto font-mono"
                                          data-testid={`production-tarifa-${idx}`}
                                        />
                                      </td>
                                      <td className="px-3 py-2 text-right border border-slate-300 bg-orange-50 font-mono font-semibold text-orange-600">
                                        ${((item.tarifa || 0) * (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1)).toFixed(2)}
                                      </td>
                                      <td className="px-3 py-2 text-center border border-slate-300">
                                        <Button
                                          size="sm" variant="ghost"
                                          onClick={() => setProductionItems(productionItems.filter((_, i) => i !== idx))}
                                          className="h-7 w-7 p-0 text-red-500 hover:text-red-700 hover:bg-red-50"
                                          data-testid={`production-remove-${idx}`}
                                        >
                                          <Trash2 size={14} />
                                        </Button>
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                                <tfoot>
                                  <tr className="bg-orange-50">
                                    <td colSpan={5} className="px-3 py-2 text-right font-semibold border border-slate-300">Subtotal Producción:</td>
                                    <td className="px-3 py-2 text-right font-mono font-bold text-orange-600 border border-slate-300">${subtotalProduction.toFixed(2)}</td>
                                    <td className="border border-slate-300"></td>
                                  </tr>
                                </tfoot>
                              </table>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
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
                        onClick={previewCurrentQuotePDF}
                        variant="outline"
                        disabled={pdfPreviewLoading}
                        className="border-slate-400 text-slate-600 hover:bg-slate-50 px-5 py-3 text-base"
                        data-testid="preview-pdf-button"
                      >
                        <Eye size={18} className="mr-2" />
                        {pdfPreviewLoading ? 'Generando...' : 'Previsualizar PDF'}
                      </Button>
                      <Button
                        onClick={exportCurrentQuoteToPDF}
                        variant="outline"
                        className="border-brand-blue-600 text-brand-blue-600 hover:bg-brand-blue-50 px-5 py-3 text-base"
                        data-testid="export-pdf-button"
                      >
                        <Download size={18} className="mr-2" />
                        Exportar PDF
                      </Button>
                      <Button
                        onClick={handleSubmitQuote}
                        className="bg-brand-green-600 hover:bg-brand-green-700 text-white px-6 py-3 text-base"
                        data-testid="submit-quote-button"
                      >
                        <CheckCircle2 size={18} className="mr-2" />
                        Guardar Cotización
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {/* Botones de acción para Payment Gateway */}
              {isPaymentGateway && isHeaderComplete && pgSetupItems.length > 0 && (
                <div className="bg-white rounded-lg p-5 border mt-4">
                  <Label htmlFor="pg-notes" className="text-sm font-medium text-slate-700">Notas adicionales</Label>
                  <Textarea
                    id="pg-notes"
                    value={quoteData.notes}
                    onChange={(e) => setQuoteData({ ...quoteData, notes: e.target.value })}
                    placeholder="Observaciones o condiciones especiales..."
                    rows={2}
                    className="mt-2"
                    data-testid="pg-notes-input"
                  />
                  <div className="mt-4 flex justify-end gap-3">
                    <Button
                      onClick={previewCurrentQuotePDF}
                      variant="outline"
                      disabled={pdfPreviewLoading}
                      className="border-slate-400 text-slate-600 hover:bg-slate-50 px-5 py-3 text-base"
                      data-testid="pg-preview-pdf-button"
                    >
                      <Eye size={18} className="mr-2" />
                      {pdfPreviewLoading ? 'Generando...' : 'Previsualizar PDF'}
                    </Button>
                    <Button
                      onClick={exportCurrentQuoteToPDF}
                      variant="outline"
                      className="border-brand-blue-600 text-brand-blue-600 hover:bg-brand-blue-50 px-5 py-3 text-base"
                      data-testid="pg-export-pdf-button"
                    >
                      <Download size={18} className="mr-2" />
                      Exportar PDF
                    </Button>
                    <Button
                      onClick={handleSubmitPGQuote}
                      className="bg-emerald-600 hover:bg-emerald-700 text-white px-6 py-3 text-base"
                      data-testid="pg-submit-quote-button"
                    >
                      <CheckCircle2 size={18} className="mr-2" />
                      Guardar Cotización PG
                    </Button>
                  </div>
                </div>
              )}

              {/* Mensaje cuando no hay items - Solo para VPOS/MPOS */}
              {!isPaymentGateway && canShowItems && quoteData.setup_items.length === 0 && (
                <div className="text-center py-8 text-slate-500 bg-slate-50 rounded-lg mt-4 border-2 border-dashed">
                  <CreditCard size={40} className="mx-auto mb-3 text-slate-300" />
                  <p className="font-medium">No hay medios de pago agregados</p>
                  <p className="text-sm mt-1">Seleccione un banco y medio de pago para comenzar</p>
                </div>
              )}
            </DialogContent>
          </Dialog>

          {/* Modal de Previsualización PDF */}
          <PdfPreviewModal
            open={pdfPreviewOpen}
            onOpenChange={(open) => {
              if (!open && pdfPreviewUrl) { window.URL.revokeObjectURL(pdfPreviewUrl); setPdfPreviewUrl(null); }
              setPdfPreviewOpen(open);
            }}
            pdfUrl={pdfPreviewUrl}
            loading={pdfPreviewLoading}
          />

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

          {/* Modal de Protocolo de Excepción (Flujo Irregular) */}
          <Dialog open={exceptionModalOpen} onOpenChange={setExceptionModalOpen}>
            <DialogContent className="max-w-md" data-testid="exception-modal">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2 text-orange-700">
                  <AlertTriangle size={22} className="text-orange-500" />
                  Alerta de Flujo Irregular
                </DialogTitle>
              </DialogHeader>
              {pendingAction && (
                <div className="space-y-4">
                  <div className="bg-orange-50 border border-orange-200 rounded-lg p-3 text-sm">
                    <p className="text-orange-800">
                      Detectamos que está intentando <strong>{ACTION_LABELS[pendingAction.action]}</strong> sin haber completado el paso anterior.
                    </p>
                    <p className="text-orange-600 mt-1 text-xs">
                      Estado esperado: <strong>{pendingAction.expectedStatus}</strong> — Estado actual: <strong>{pendingAction.currentStatus}</strong>
                    </p>
                  </div>
                  <div>
                    <Label className="text-sm font-medium">Motivo de la Excepción <span className="text-red-500">*</span></Label>
                    <Textarea value={exceptionData.reason}
                      onChange={e => setExceptionData(p => ({ ...p, reason: e.target.value }))}
                      placeholder="Explique por qué se realiza esta acción fuera del flujo regular..."
                      className="mt-1 min-h-[70px] text-sm" data-testid="exception-reason" />
                  </div>
                  <div>
                    <Label className="text-sm font-medium">Compromiso de Regularización</Label>
                    <Input type="date" value={exceptionData.regularization_date}
                      onChange={e => setExceptionData(p => ({ ...p, regularization_date: e.target.value }))}
                      className="mt-1" data-testid="exception-regularization-date" />
                    <p className="text-[10px] text-slate-400 mt-1">Fecha máxima para completar el paso faltante</p>
                  </div>
                  <div className="flex justify-end gap-3 pt-2 border-t">
                    <Button variant="outline" onClick={() => { setExceptionModalOpen(false); setPendingAction(null); }}>Cancelar</Button>
                    <Button onClick={confirmException}
                      disabled={!exceptionData.reason.trim()}
                      className="bg-orange-600 hover:bg-orange-700 text-white"
                      data-testid="exception-confirm-btn">
                      Confirmar Acción
                    </Button>
                  </div>
                </div>
              )}
            </DialogContent>
          </Dialog>

          {/* Modal de Personalización de Envío */}
          <Dialog open={emailModalOpen} onOpenChange={(open) => { if (!open) { setEmailModalOpen(false); setPendingAction(null); } }}>
            <DialogContent className="max-w-md" data-testid="email-modal">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2 text-blue-700">
                  <Mail size={20} className="text-blue-500" />
                  Personalizar Comunicación
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800">
                  <p>Acción: <strong>{ACTION_LABELS[emailModalConfig.action] || emailModalConfig.action}</strong></p>
                  {emailModalConfig.quoteName && <p className="text-xs text-blue-600 mt-0.5">Cotización: {emailModalConfig.quoteName}</p>}
                </div>
                <div>
                  <Label className="text-sm font-medium">Mensaje personalizado <span className="text-xs text-slate-400">(opcional, máx 200 caracteres)</span></Label>
                  <Textarea
                    value={emailCustomMessage}
                    onChange={e => setEmailCustomMessage(e.target.value.slice(0, 200))}
                    placeholder="Ej: Estimado cliente, adjuntamos la documentación solicitada..."
                    className="mt-1 min-h-[70px] text-sm"
                    maxLength={200}
                    data-testid="email-custom-message" />
                  <p className="text-[10px] text-slate-400 mt-1 text-right">{emailCustomMessage.length}/200</p>
                </div>
                <div>
                  <Label className="text-sm font-medium">Destinatarios adicionales (CC)</Label>
                  <div className="flex gap-2 mt-1">
                    <Input
                      type="email"
                      value={emailNewRecipient}
                      onChange={e => setEmailNewRecipient(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addEmailRecipient(); } }}
                      placeholder="correo@ejemplo.com"
                      className="flex-1 text-sm"
                      data-testid="email-cc-input" />
                    <Button type="button" variant="outline" size="sm" onClick={addEmailRecipient}
                      disabled={!emailNewRecipient.trim() || !emailNewRecipient.includes('@')}
                      data-testid="email-add-cc-btn">
                      <Plus size={14} />
                    </Button>
                  </div>
                  {emailRecipientsList.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {emailRecipientsList.map((email, idx) => (
                        <span key={idx} className="inline-flex items-center gap-1 text-xs bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded-full">
                          {email}
                          <button onClick={() => removeEmailRecipient(email)} className="hover:text-red-500 ml-0.5">
                            <X size={12} />
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex justify-end gap-3 pt-3 border-t">
                  <Button variant="outline" onClick={() => { setEmailModalOpen(false); setPendingAction(null); }} data-testid="email-cancel-btn">Cancelar</Button>
                  <Button onClick={confirmEmailAndProceed}
                    className="bg-blue-600 hover:bg-blue-700 text-white"
                    data-testid="email-confirm-btn">
                    <Send size={14} className="mr-1.5" />
                    Continuar
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>

          {/* Modal de Bitácora de Flujo (Historial de Excepciones) */}
          <Dialog open={bitacoraFlujoOpen} onOpenChange={setBitacoraFlujoOpen}>
            <DialogContent className="max-w-2xl max-h-[85vh] overflow-hidden flex flex-col" data-testid="bitacora-flujo-modal">
              <DialogHeader className="shrink-0">
                <DialogTitle className="flex items-center gap-2">
                  <AlertTriangle size={20} className="text-orange-500" />
                  Bitácora de Flujo — {bitacoraFlujoQuoteNumber}
                </DialogTitle>
              </DialogHeader>
              <div className="flex-1 overflow-y-auto min-h-0 mt-2">
                {bitacoraFlujoLoading ? (
                  <p className="text-sm text-slate-400 text-center py-8">Cargando historial...</p>
                ) : bitacoraFlujoEntries.length === 0 ? (
                  <div className="text-center py-8">
                    <CheckCircle size={32} className="mx-auto text-emerald-300 mb-2" />
                    <p className="text-sm text-slate-400">No hay excepciones registradas para esta cotización</p>
                  </div>
                ) : (
                  <div className="relative pl-8 space-y-0">
                    <div className="absolute left-[12px] top-3 bottom-3 w-0.5 bg-orange-200" />
                    {bitacoraFlujoEntries.map((entry) => {
                      const isOverdue = entry.regularization_date && entry.regularization_date < new Date().toISOString().slice(0, 10);
                      return (
                        <div key={entry.audit_id} className="relative pb-5" data-testid={`flujo-entry-${entry.audit_id}`}>
                          <div className={`absolute left-[-22px] top-1.5 w-4 h-4 rounded-full border-2 ${isOverdue ? 'bg-red-500 border-red-300' : 'bg-orange-500 border-orange-300'}`} />
                          <div className={`bg-white border rounded-lg p-4 ml-1 ${isOverdue ? 'border-red-200' : 'border-slate-200'}`}>
                            <div className="flex items-center justify-between mb-2">
                              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-bold rounded-full bg-orange-100 text-orange-700 border border-orange-200">
                                {ACTION_LABELS[entry.action] || entry.action}
                              </span>
                              <span className="text-[10px] text-slate-400">{entry.created_at?.slice(0, 10)}</span>
                            </div>
                            <p className="text-sm text-slate-800 mb-2">
                              El usuario <strong className="text-slate-900">{entry.user_name}</strong> ejecutó <strong>{ACTION_LABELS[entry.action]}</strong> sin haber completado el paso <strong>"{entry.expected_status}"</strong>.
                              <span className="text-slate-500"> Estado en el momento: "{entry.actual_status}".</span>
                            </p>
                            <div className="bg-slate-50 rounded p-2.5 space-y-1.5">
                              <p className="text-xs"><span className="font-semibold text-slate-700">Motivo:</span> <span className="text-slate-600">{entry.exception_reason}</span></p>
                              {entry.regularization_date && (
                                <p className="text-xs">
                                  <span className="font-semibold text-slate-700">Compromiso de regularización:</span>{' '}
                                  <span className={`font-medium ${isOverdue ? 'text-red-600' : 'text-slate-600'}`}>
                                    {entry.regularization_date}
                                    {isOverdue && <span className="ml-1.5 text-[9px] font-bold text-red-500 uppercase">Vencido</span>}
                                  </span>
                                </p>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
              <div className="shrink-0 flex items-center justify-between pt-2 border-t border-slate-200 mt-2">
                <span className="text-[10px] text-slate-400">{bitacoraFlujoEntries.length} excepciones registradas</span>
                <Button variant="outline" size="sm" onClick={() => setBitacoraFlujoOpen(false)}>Cerrar</Button>
              </div>
            </DialogContent>
          </Dialog>

          {/* Delivery Dialog (Hoja de Ruta) */}
          <DeliveryDialog
            open={deliveryDialogOpen}
            onOpenChange={setDeliveryDialogOpen}
            quoteId={deliveryQuoteId}
            exceptionInfo={deliveryExceptionInfo}
            onDelivered={() => fetchData()}
          />

          {/* Repair Delivery Dialog (Entrega de Reparaciones) */}
          <RepairDeliveryDialog
            open={repairDeliveryDialogOpen}
            onOpenChange={setRepairDeliveryDialogOpen}
            quoteId={deliveryQuoteId}
            exceptionInfo={deliveryExceptionInfo}
            onDelivered={() => fetchData()}
          />

          {/* Diálogo Multitienda */}
          <Dialog open={multistoreDialogOpen} onOpenChange={(open) => { if (!open && !multistoreSending) { setMultistoreDialogOpen(false); } }}>
            <DialogContent className="max-w-lg" data-testid="multistore-dialog">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <Store size={20} className="text-blue-600" />
                  Enviar a Implementación
                </DialogTitle>
              </DialogHeader>

              {/* Fase 1: Pregunta Multitienda */}
              {multistorePhase === 'ask' && (
                <div className="space-y-4 py-2" data-testid="multistore-ask-phase">
                  <p className="text-sm text-slate-600">¿Esta implementación es <strong>Multitienda</strong>?</p>
                  <p className="text-xs text-slate-400">Si el proyecto incluye múltiples sucursales o tiendas, seleccione "Sí" para registrar los datos de cada una.</p>
                  <div className="flex gap-3 justify-end pt-2">
                    <Button variant="outline" onClick={() => handleMultistoreAnswer(false)} data-testid="multistore-no-btn">
                      No, tienda única
                    </Button>
                    <Button className="bg-blue-600 hover:bg-blue-700 text-white" onClick={() => handleMultistoreAnswer(true)} data-testid="multistore-yes-btn">
                      <Store size={14} className="mr-1.5" />
                      Sí, Multitienda
                    </Button>
                  </div>
                </div>
              )}

              {/* Fase 2: Recolectar tiendas */}
              {multistorePhase === 'collect' && (
                <div className="space-y-4 py-2" data-testid="multistore-collect-phase">
                  {(() => {
                    const totalCajas = getMultistoreTotalCajas();
                    const remaining = totalCajas - multistoreAssignedBoxes;
                    return (
                      <>
                        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-medium text-blue-800">Total de cajas en cotización:</span>
                            <span className="text-lg font-bold text-blue-900">{totalCajas}</span>
                          </div>
                          <div className="flex items-center justify-between mt-1">
                            <span className="text-sm text-blue-700">Cajas asignadas:</span>
                            <span className={`text-sm font-semibold ${multistoreAssignedBoxes === totalCajas ? 'text-emerald-600' : 'text-blue-700'}`}>{multistoreAssignedBoxes} / {totalCajas}</span>
                          </div>
                          {remaining > 0 && (
                            <div className="mt-1 text-xs text-blue-600">Faltan {remaining} caja(s) por asignar</div>
                          )}
                          {remaining === 0 && (
                            <div className="mt-1 text-xs text-emerald-600 font-medium">Todas las cajas han sido asignadas</div>
                          )}
                        </div>

                        {/* Lista de tiendas registradas */}
                        {multistoreStores.length > 0 && (
                          <div className="border rounded-lg overflow-hidden">
                            <table className="w-full text-sm">
                              <thead>
                                <tr className="bg-slate-50 border-b">
                                  <th className="text-left px-3 py-2 text-xs font-semibold text-slate-600">#</th>
                                  <th className="text-left px-3 py-2 text-xs font-semibold text-slate-600">Tienda</th>
                                  <th className="text-center px-3 py-2 text-xs font-semibold text-slate-600">Cajas</th>
                                  <th className="text-center px-3 py-2 text-xs font-semibold text-slate-600 w-10"></th>
                                </tr>
                              </thead>
                              <tbody>
                                {multistoreStores.map((store, idx) => (
                                  <tr key={idx} className="border-b last:border-0 hover:bg-slate-50" data-testid={`multistore-row-${idx}`}>
                                    <td className="px-3 py-2 text-slate-500">{idx + 1}</td>
                                    <td className="px-3 py-2 font-medium text-slate-800">{store.name}</td>
                                    <td className="px-3 py-2 text-center text-slate-700">{store.box_count}</td>
                                    <td className="px-3 py-2 text-center">
                                      <button onClick={() => removeMultistoreStore(idx)} className="text-red-400 hover:text-red-600 transition-colors" data-testid={`multistore-remove-${idx}`}>
                                        <Trash2 size={14} />
                                      </button>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}

                        {/* Formulario para agregar tienda */}
                        {remaining > 0 && (
                          <div className="flex items-end gap-2">
                            <div className="flex-1">
                              <Label className="text-xs text-slate-500">Nombre de tienda</Label>
                              <Input
                                placeholder="Ej: Tienda Centro, Sucursal Norte..."
                                value={multistoreNewStore.name}
                                onChange={(e) => setMultistoreNewStore({ ...multistoreNewStore, name: e.target.value })}
                                data-testid="multistore-store-name"
                                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addMultistoreStore(); } }}
                              />
                            </div>
                            <div className="w-24">
                              <Label className="text-xs text-slate-500">Cajas</Label>
                              <Input
                                type="number"
                                min="1"
                                max={remaining}
                                placeholder="Cant."
                                value={multistoreNewStore.box_count}
                                onChange={(e) => setMultistoreNewStore({ ...multistoreNewStore, box_count: e.target.value })}
                                data-testid="multistore-store-boxes"
                                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addMultistoreStore(); } }}
                              />
                            </div>
                            <Button variant="outline" size="sm" onClick={addMultistoreStore} data-testid="multistore-add-store-btn" className="shrink-0">
                              <Plus size={14} className="mr-1" /> Agregar
                            </Button>
                          </div>
                        )}

                        {/* Botones de acción */}
                        <div className="flex justify-between items-center pt-3 border-t">
                          <Button variant="ghost" size="sm" onClick={() => { setMultistorePhase('ask'); setMultistoreStores([]); }} data-testid="multistore-back-btn">
                            Volver
                          </Button>
                          <Button
                            className="bg-blue-600 hover:bg-blue-700 text-white"
                            disabled={multistoreAssignedBoxes !== totalCajas || multistoreStores.length === 0}
                            onClick={confirmMultistore}
                            data-testid="multistore-confirm-btn"
                          >
                            <Send size={14} className="mr-1.5" />
                            Confirmar y Enviar ({multistoreStores.length} tienda{multistoreStores.length !== 1 ? 's' : ''})
                          </Button>
                        </div>
                      </>
                    );
                  })()}
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
