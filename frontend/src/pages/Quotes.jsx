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
import { BranchDetailPanel } from '../components/BranchDetailPanel';
import { AnexosModal } from '../components/AnexosModal';
import { WorkflowUploadModal } from '../components/WorkflowUploadModal';
import { ApprovalBillingModal } from '../components/ApprovalBillingModal';
import { MultiProductSelector } from '../components/MultiProductSelector';
import { EditEquipRepairDialog } from '../components/EditEquipRepairDialog';
import { JustificationModal } from '../components/JustificationModal';
import { QuoteFilters } from '../components/quotes/QuoteFilters';
import { QuotesTable } from '../components/quotes/QuotesTable';
import { PdfPreviewModal } from '../components/quotes/PdfPreviewModal';
import { DeliveryDialog } from '../components/quotes/DeliveryDialog';
import { RepairDeliveryDialog } from '../components/quotes/RepairDeliveryDialog';
import { RepairCompleteModal } from '../components/quotes/RepairCompleteModal';
import { PreassignSerialsModal } from '../components/quotes/PreassignSerialsModal';
import { QuoteWizardDialog } from '../components/quotes/QuoteWizardDialog';
import { QuoteModals } from '../components/quotes/QuoteModals';
import { QUOTE_TYPES, PRICING_MODELS, SETUP_CONCEPTS, RECURRING_BASIC_CONCEPTS, RECURRING_OTHER_CONCEPTS, STATUS_COLORS, STATUS_DISPLAY_NAMES, QUOTE_CATEGORY_LABELS, ACTION_LABELS } from '../components/quotes/constants';
import api from '../utils/api';
import { toast } from 'sonner';
import { usePermission } from '../hooks/usePermission';



export const Quotes = () => {
  const { canEdit, user: currentUser } = usePermission('cotizaciones');
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
  const [equipmentWizardMode, setEquipmentWizardMode] = useState(''); // 'equipment' o 'repair'
  
  
  
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

  // RBAC: Permisos especiales de cotizaciones
  const rbac = useMemo(() => {
    const sp = currentUser?.special_permissions || [];
    const isAdm = currentUser?.role === 'admin';
    const hasImplPyme = isAdm || sp.includes('cotizaciones:impl_pyme');
    const hasImplCorp = isAdm || sp.includes('cotizaciones:impl_corp');
    const hasEquipos = isAdm || sp.includes('cotizaciones:equipos');
    const hasReparaciones = isAdm || sp.includes('cotizaciones:reparaciones');
    const hasAnyImpl = hasImplPyme || hasImplCorp;
    const hasAnyCotPerm = sp.some(p => p.startsWith('cotizaciones:'));
    const showButtons = canEdit && (isAdm || hasAnyImpl || hasEquipos || hasReparaciones);
    return { hasImplPyme, hasImplCorp, hasEquipos, hasReparaciones, hasAnyImpl, hasAnyCotPerm, showButtons, isAdm };
  }, [currentUser, canEdit]);

  // RBAC: Filtrar cotizaciones según permisos
  const rbacFilteredQuotes = useMemo(() => {
    if (rbac.isAdm || !rbac.hasAnyCotPerm) return quotes;
    const allowed = [];
    if (rbac.hasImplPyme || rbac.hasImplCorp) allowed.push('implementation', 'fast_track');
    if (rbac.hasEquipos) allowed.push('equipment');
    if (rbac.hasReparaciones) allowed.push('repair');
    return quotes.filter(q => allowed.includes(q.quote_category));
  }, [quotes, rbac]);
  
  // Estado para edición de cotización existente
  const [editingQuoteId, setEditingQuoteId] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isLoadingEdit, setIsLoadingEdit] = useState(false);
  // Estado para edición de Equipos/Reparaciones
  const [editEquipRepairOpen, setEditEquipRepairOpen] = useState(false);
  const [editEquipRepairQuote, setEditEquipRepairQuote] = useState(null);
  // Estado para modal de justificación en Implementaciones
  const [implJustifyOpen, setImplJustifyOpen] = useState(false);
  const [implJustifyCallback, setImplJustifyCallback] = useState(null);
  const [implJustifyQuoteNum, setImplJustifyQuoteNum] = useState('');
  const [implJustifyVersion, setImplJustifyVersion] = useState(1);
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
    notes: '',
    include_recurring: true
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
  // Fast Track: items de equipos para PDF híbrido
  const [ftEquipmentItems, setFtEquipmentItems] = useState([]);
  const [pgShowRecurringTable, setPgShowRecurringTable] = useState(false);
  const [pgFilteredProducts, setPgFilteredProducts] = useState([]);
  // Detalle de sucursales (opcional para VPOS/MPOS/Fast Track)
  const [branchDetails, setBranchDetails] = useState([]);
  
  // Estados para modales de confirmación
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deleteQuoteData, setDeleteQuoteData] = useState({ id: null, number: null });
  
  // Estados para modales de workflow (carga obligatoria de documentos)
  const [workflowModalOpen, setWorkflowModalOpen] = useState(false);
  const [workflowQuoteId, setWorkflowQuoteId] = useState(null);
  const [workflowConfig, setWorkflowConfig] = useState(null);

  // Estado para modal de Aprobación con Instrucción de Facturación
  const [approvalModalOpen, setApprovalModalOpen] = useState(false);
  const [approvalQuoteId, setApprovalQuoteId] = useState(null);
  const [approvalConfig, setApprovalConfig] = useState(null);
  
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
  const exceptionReasonRef = useRef('');
  const exceptionDebounceRef = useRef(null);
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
  // Estado para RepairCompleteModal
  const [repairCompleteModalOpen, setRepairCompleteModalOpen] = useState(false);
  const [repairCompleteQuoteId, setRepairCompleteQuoteId] = useState(null);
  const [repairCompleteConfig, setRepairCompleteConfig] = useState(null);
  const [preassignModal, setPreassignModal] = useState({ open: false, quote: null });
  const [deliveryQuoteId, setDeliveryQuoteId] = useState(null);
  const [deliveryExceptionInfo, setDeliveryExceptionInfo] = useState(null);

  // Estado para flujo Multitienda
  const [multistoreDialogOpen, setMultistoreDialogOpen] = useState(false);
  const [multistoreQuoteId, setMultistoreQuoteId] = useState(null);
  const [multistoreExceptionInfo, setMultistoreExceptionInfo] = useState(null);
  const [isMultistore, setIsMultistore] = useState(null); // null = no decidido, true/false
  const [multistoreStores, setMultistoreStores] = useState([]);
  const [multistoreNewStore, setMultistoreNewStore] = useState({ name: '', box_count: '' });
  const [multistorePhase, setMultistorePhase] = useState('project_type'); // 'project_type' | 'equipment' | 'ask' | 'inherited' | 'collect' | 'confirm'
  const [multistoreSending, setMultistoreSending] = useState(false);

  // Estado para gestión de plantillas de cotización
  // Template editing removed — centralized in Configuración > Plantillas de Correo

  // fetchQuoteTemplates removed — centralized in Configuración

  // handleSaveQuoteTemplate / handleDeleteQuoteTemplate removed — centralized in Configuración

  // Estado para tipo de proyecto y equipos
  const [projectTypeImpl, setProjectTypeImpl] = useState(null); // 'pos_fast_track' | 'vpos_mpos' | 'payment_gateway'
  const [equipmentList, setEquipmentList] = useState([]); // Equipos seleccionados
  const [equipmentAvailable, setEquipmentAvailable] = useState({ quote_equipment: [], rif_equipment: [] });
  const [equipmentLoading, setEquipmentLoading] = useState(false);
  const [equipmentSelected, setEquipmentSelected] = useState({}); // Map of equipo_id -> boolean

  // Estado para flujo PYME extendido (Servidor + Pinpads)
  const [pymeServerName, setPymeServerName] = useState(''); // 'Multicomercio MSC' | 'Multicomercio MSC2' | custom
  const [pymeServerCustom, setPymeServerCustom] = useState('');
  const [pymeNeedsPinpads, setPymeNeedsPinpads] = useState(null); // null | true | false
  const [pymePinpadModels, setPymePinpadModels] = useState([]); // [{hardware_id, name, type}]
  const [pymePinpadSelectedModel, setPymePinpadSelectedModel] = useState(''); // hardware_id
  const [pymePinpadSerials, setPymePinpadSerials] = useState([]); // [{serial, modelo, movement_id, ...}]
  const [pymePinpadSerialsSelected, setPymePinpadSerialsSelected] = useState({}); // Map serial -> boolean
  const [pymePinpadLoading, setPymePinpadLoading] = useState(false);

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
        api.get('/clients').catch(() => ({ data: [] })),
        api.get('/banks').catch(() => ({ data: [] })),
        api.get('/services').catch(() => ({ data: [] })),
        api.get('/integrators').catch(() => ({ data: [] })),
        api.get('/hardware').catch(() => ({ data: [] })),
        api.get('/config/templates').catch(() => ({ data: {} })),
        api.get('/pg-recurring-costs').catch(() => ({ data: null })),
        api.get('/pg-defaults').catch(() => ({ data: null }))
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
    const normalize = (str) => str.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, ' ').trim();
    const nameNorm = normalize(productName);
    
    const service = serviceCatalog.find(s => {
      const sNorm = normalize(s.name);
      return sNorm === nameNorm ||
        sNorm.includes(nameNorm) ||
        nameNorm.includes(sNorm);
    });
    
    if (service) {
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

  // Buscar tipo_corp de un servicio por nombre (para PDF corporativo)
  // Prioriza servicios que tengan tipo_corp definido (evita duplicados PYME sin tipo_corp)
  const findServiceTipoCorp = (productName) => {
    if (!productName) return '';
    const nameLC = productName.toLowerCase();
    // Primero buscar match exacto con tipo_corp definido
    const exactWithCorp = serviceCatalog.find(s =>
      s.tipo_corp && s.name.toLowerCase() === nameLC
    );
    if (exactWithCorp) return exactWithCorp.tipo_corp;
    // Luego match parcial con tipo_corp definido
    const partialWithCorp = serviceCatalog.find(s =>
      s.tipo_corp && (
        s.name.toLowerCase().includes(nameLC) ||
        nameLC.includes(s.name.toLowerCase())
      )
    );
    if (partialWithCorp) return partialWithCorp.tipo_corp;
    // Fallback: cualquier match
    const anyMatch = serviceCatalog.find(s =>
      s.name.toLowerCase() === nameLC ||
      s.name.toLowerCase().includes(nameLC) ||
      nameLC.includes(s.name.toLowerCase())
    );
    return anyMatch?.tipo_corp || '';
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
    
    // Limpiar búsqueda de clientes
    setClientSearchQuery('');
    setClientSearchResults([]);
    
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
      notes: '',
      include_recurring: true
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

  // Subtotal de hardware Fast Track (espejo del modelo seleccionado en Integración)
  const ftHardwareSubtotal = (() => {
    if (quoteData.quote_type !== 'FAST_TRACK') return 0;
    if (quoteData.pinpad_id && quoteData.pinpad_id !== 'none') {
      const hw = [...posDevices, ...pinpads].find(p => p.hardware_id === quoteData.pinpad_id);
      if (hw) return (parseInt(quoteData.cantidad_cajas) || 1) * (hw.price_bs_usd || hw.price_usd || 0);
    }
    return ftEquipmentItems.reduce((acc, it) => acc + (it.quantity * it.unit_price_usd), 0);
  })();

  const grandTotal = totalNetoSetup + totalNetoRecurrente + ftHardwareSubtotal;

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
      const pinpad = (quoteData.quote_type === 'FAST_TRACK')
        ? [...posDevices, ...pinpads].find(p => p.hardware_id === quoteData.pinpad_id)
        : (quoteData.quote_type === 'MPOS' ? posDevices : pinpads).find(p => p.hardware_id === quoteData.pinpad_id);
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
        client_segment: quoteData.client_segment || 'PYME',
        setup_items: [
          ...quoteData.setup_items.map(item => ({
            concepto: item.medio_pago_name,
            cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
            cantidad_bancos: item.lockBancos ? 1 : (parseInt(item.cantidad_bancos) || 1),
            tarifa: parseFloat(item.tarifa) || 0,
            bank_name: item.bank_name || null,
            tipo_corp: findServiceTipoCorp(item.medio_pago_name)
          })),
          ...quoteData.additional_items.map(item => ({
            concepto: `${item.medio_pago_name} - ${item.bank_name}`,
            cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
            cantidad_bancos: parseInt(item.cantidad_bancos) || 1,
            tarifa: parseFloat(item.tarifa_setup) || 0,
            bank_name: item.bank_name || null,
            tipo_corp: findServiceTipoCorp(item.medio_pago_name)
          }))
        ],
        recurring_basic_items: quoteData.recurring_basic_items.map(item => ({
          concepto: item.medio_pago_name + (item.linkedTo ? ` (vinculado a ${item.linkedTo})` : ''),
          cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
          cantidad_bancos: item.lockBancos ? 1 : (parseInt(item.cantidad_bancos) || 1),
          tarifa: parseFloat(item.tarifa) || 0,
          bank_name: item.bank_name || null,
          tipo_corp: findServiceTipoCorp(item.medio_pago_name)
        })),
        recurring_other_items: quoteData.recurring_other_items.map(item => ({
          concepto: item.medio_pago_name,
          cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
          cantidad_bancos: item.lockBancos ? 1 : (parseInt(item.cantidad_bancos) || 1),
          tarifa: parseFloat(item.tarifa) || 0,
          bank_name: item.bank_name || null,
          tipo_corp: findServiceTipoCorp(item.medio_pago_name)
        })),
        additional_items: quoteData.additional_items
          .filter(item => item.bank_name)
          .map(item => ({
            concepto: item.medio_pago_name,
            cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
            cantidad_bancos: parseInt(item.cantidad_bancos) || 1,
            tarifa: parseFloat(item.tarifa_setup) || 0,
            bank_name: item.bank_name,
            tipo_corp: findServiceTipoCorp(item.medio_pago_name)
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
          tarifa: parseFloat(item.tarifa) || 0,
          tipo_corp: findServiceTipoCorp(item.medio_pago_name)
        })),
        ft_equipment_items: (() => {
          if (quoteData.quote_type !== 'FAST_TRACK') return [];
          if (quoteData.pinpad_id && quoteData.pinpad_id !== 'none') {
            const hw = [...posDevices, ...pinpads].find(p => p.hardware_id === quoteData.pinpad_id);
            if (hw) return [{ name: hw.name, hardware_type: hw.type || 'POS', quantity: parseInt(quoteData.cantidad_cajas) || 1, unit_price_usd: hw.price_bs_usd || hw.price_usd || 0 }];
          }
          if (isMegaSoftSponsor) return ftEquipmentItems.map(item => ({ name: item.name, hardware_type: item.hardware_type, quantity: item.quantity, unit_price_usd: item.unit_price_usd }));
          return [];
        })(),
        branch_details: branchDetails.filter(b => b.store_name && b.quantity > 0),
        include_recurring: quoteData.include_recurring !== false
      };

      const payload = {
        client_id: quoteData.client_id,
        client_segment: quoteData.client_segment || 'PYME',
        quote_category: quoteData.quote_type === 'FAST_TRACK' ? 'fast_track' : 'implementation',
        quote_type: quoteData.quote_type,
        pricing_model: quoteData.pricing_model,
        services: allItems,
        hardware: [],
        ft_equipment_items: (() => {
          if (quoteData.quote_type !== 'FAST_TRACK') return [];
          // Si hay modelo sincronizado desde Integración, usarlo como único item
          if (quoteData.pinpad_id && quoteData.pinpad_id !== 'none') {
            const hw = [...posDevices, ...pinpads].find(p => p.hardware_id === quoteData.pinpad_id);
            if (hw) return [{ hardware_id: hw.hardware_id, name: hw.name, hardware_type: hw.type || 'POS', quantity: parseInt(quoteData.cantidad_cajas) || 1, unit_price_usd: hw.price_bs_usd || hw.price_usd || 0 }];
          }
          // Fallback: items manuales (Mega Soft)
          if (isMegaSoftSponsor) return ftEquipmentItems;
          return [];
        })(),
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
        // Detalle de sucursales (opcional)
        branch_details: branchDetails.filter(b => b.store_name && b.quantity > 0),
        // Total USD = Total Setup Neto + Equipment (calculado por el wizard)
        override_total_usd: totalNetoSetup + ftHardwareSubtotal,
        descuento_setup: quoteData.descuento_setup || 0,
        descuento_recurrente: quoteData.descuento_recurrente || 0,
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
    const pinpad = (quoteData.quote_type === 'FAST_TRACK')
      ? [...posDevices, ...pinpads].find(p => p.hardware_id === quoteData.pinpad_id)
      : pinpads.find(p => p.hardware_id === quoteData.pinpad_id);
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
      client_segment: quoteData.client_segment || 'PYME',
      setup_items: [
        ...quoteData.setup_items.map(item => ({
          concepto: item.medio_pago_name,
          cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
          cantidad_bancos: item.lockBancos ? 1 : (parseInt(item.cantidad_bancos) || 1),
          tarifa: parseFloat(item.tarifa) || 0,
          bank_name: item.bank_name || null,
          tipo_corp: findServiceTipoCorp(item.medio_pago_name)
        })),
        ...quoteData.additional_items.map(item => ({
          concepto: `${item.medio_pago_name} - ${item.bank_name}`,
          cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
          cantidad_bancos: parseInt(item.cantidad_bancos) || 1,
          tarifa: parseFloat(item.tarifa_setup) || 0,
          bank_name: item.bank_name || null,
          tipo_corp: findServiceTipoCorp(item.medio_pago_name)
        }))
      ],
      recurring_basic_items: quoteData.recurring_basic_items.map(item => ({
        concepto: item.medio_pago_name + (item.linkedTo ? ` (vinculado a ${item.linkedTo})` : ''),
        cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
        cantidad_bancos: item.lockBancos ? 1 : (parseInt(item.cantidad_bancos) || 1),
        tarifa: parseFloat(item.tarifa) || 0,
        bank_name: item.bank_name || null,
        tipo_corp: findServiceTipoCorp(item.medio_pago_name)
      })),
      recurring_other_items: quoteData.recurring_other_items.map(item => ({
        concepto: item.medio_pago_name,
        cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
        cantidad_bancos: item.lockBancos ? 1 : (parseInt(item.cantidad_bancos) || 1),
        tarifa: parseFloat(item.tarifa) || 0,
        bank_name: item.bank_name || null,
        tipo_corp: findServiceTipoCorp(item.medio_pago_name)
      })),
      // additional_items separado para el Resumen Ejecutivo (solo items con bank_name)
      additional_items: quoteData.additional_items
        .filter(item => item.bank_name)
        .map(item => ({
          concepto: item.medio_pago_name,
          cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
          cantidad_bancos: parseInt(item.cantidad_bancos) || 1,
          tarifa: parseFloat(item.tarifa_setup) || 0,
          bank_name: item.bank_name,
          tipo_corp: findServiceTipoCorp(item.medio_pago_name)
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
        tarifa: parseFloat(item.tarifa) || 0,
        tipo_corp: findServiceTipoCorp(item.medio_pago_name)
      })),
      // PG Recurring costs (tabla de rangos)
      pg_recurring_cost: pgShowRecurringTable && pgMediosPagoCount > 0 ? {
        num_products: Math.min(pgMediosPagoCount, 11),
        rangos: getPgFullRecurringTable().map(r => ({
          rango_label: r.label,
          costo_base_total: r.base,
          precio_tope: r.tope
        }))
      } : null,
      branch_details: branchDetails.filter(b => b.store_name && b.quantity > 0),
      // Fast Track: equipo sincronizado desde Detalles de Integración
      ft_equipment_items: (() => {
        if (quoteData.quote_type !== 'FAST_TRACK') return [];
        if (quoteData.pinpad_id && quoteData.pinpad_id !== 'none') {
          const hw = [...posDevices, ...pinpads].find(p => p.hardware_id === quoteData.pinpad_id);
          if (hw) return [{ name: hw.name, hardware_type: hw.type || 'POS', quantity: parseInt(quoteData.cantidad_cajas) || 1, unit_price_usd: hw.price_bs_usd || hw.price_usd || 0 }];
        }
        return ftEquipmentItems.map(it => ({ name: it.name, hardware_type: it.hardware_type, quantity: it.quantity, unit_price_usd: it.unit_price_usd }));
      })(),
      include_recurring: quoteData.include_recurring !== false
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
        client_segment: quoteData.client_segment || 'PYME',
        integrator_name: integrators.find(i => i.integrator_id === quoteData.integrator_id)?.name || (quoteData.integrator_id === 'sin_integrador' ? 'Sin integrador por el momento' : ''),
        integrator_app_name: quoteData.integrator_app_name || '',
        pinpad_model: '',
        sponsor_bank_name: '',
        setup_items: quoteData.setup_items.map(item => ({
          concepto: item.medio_pago_name, cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
          cantidad_bancos: item.lockBancos ? 1 : (parseInt(item.cantidad_bancos) || 1),
          tarifa: parseFloat(item.tarifa) || 0, bank_name: item.bank_name || null,
          tipo_corp: findServiceTipoCorp(item.medio_pago_name)
        })),
        recurring_basic_items: quoteData.recurring_basic_items.map(item => ({
          concepto: item.medio_pago_name, cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
          cantidad_bancos: item.lockBancos ? 1 : (parseInt(item.cantidad_bancos) || 1),
          tarifa: parseFloat(item.tarifa) || 0,
          tipo_corp: findServiceTipoCorp(item.medio_pago_name)
        })),
        recurring_other_items: quoteData.recurring_other_items.map(item => ({
          concepto: item.medio_pago_name, cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
          cantidad_bancos: item.lockBancos ? 1 : (parseInt(item.cantidad_bancos) || 1),
          tarifa: parseFloat(item.tarifa) || 0,
          tipo_corp: findServiceTipoCorp(item.medio_pago_name)
        })),
        additional_items: [],
        pg_setup_items: pgSetupItems.map(item => ({
          concepto: item.concepto, costo: item.costo || 0, banco: item.banco || '', observacion: item.observacion || ''
        })),
        production_items: productionItems.map(item => ({
          concepto: item.medio_pago_name, cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
          cantidad_bancos: parseInt(item.cantidad_bancos) || 1, tarifa: parseFloat(item.tarifa) || 0,
          tipo_corp: findServiceTipoCorp(item.medio_pago_name)
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
        } : null,
        ft_equipment_items: (() => {
          if (quoteData.quote_type !== 'FAST_TRACK') return [];
          if (quoteData.pinpad_id && quoteData.pinpad_id !== 'none') {
            const hw = [...posDevices, ...pinpads].find(p => p.hardware_id === quoteData.pinpad_id);
            if (hw) return [{ name: hw.name, hardware_type: hw.type || 'POS', quantity: parseInt(quoteData.cantidad_cajas) || 1, unit_price_usd: hw.price_bs_usd || hw.price_usd || 0 }];
          }
          return ftEquipmentItems.map(it => ({ name: it.name, hardware_type: it.hardware_type, quantity: it.quantity, unit_price_usd: it.unit_price_usd }));
        })(),
        include_recurring: quoteData.include_recurring !== false
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
    if (typeId === 'FAST_TRACK') return 'MPOS (Imple + POS)';
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
      exceptionReasonRef.current = '';
      setExceptionModalOpen(true);
      return;
    }
    // Flujo regular — abrir email modal antes de proceder
    openEmailModal(action, quoteId);
    setPendingAction({ quoteId, action, proceedFn, exceptionHeaders: null });
  };

  const confirmException = () => {
    // Sincronizar ref → state para asegurar el último valor escrito
    const currentReason = exceptionReasonRef.current || exceptionData.reason;
    if (!currentReason.trim()) { toast.error('Debe ingresar el motivo de la excepción'); return; }
    const finalData = { ...exceptionData, reason: currentReason };
    setExceptionModalOpen(false);
    // Abrir email modal con la excepción pendiente
    openEmailModal(pendingAction.action, pendingAction.quoteId);
    setPendingAction({ ...pendingAction, exceptionHeaders: finalData });
  };

  // Abrir modal de workflow para Aprobar (requiere Orden de Compra)
  const openApproveConfirm = (quoteId, exceptionInfo) => {
    setApprovalQuoteId(quoteId);
    setApprovalConfig({
      exceptionHeaders: exceptionInfo || null,
      emailHeaders: getEmailHeaders(),
    });
    setApprovalModalOpen(true);
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
      const headers = { ...getEmailHeaders() };
      if (exceptionInfo) {
        headers['x-exception-reason'] = exceptionInfo.reason;
        headers['x-regularization-date'] = exceptionInfo.regularization_date;
      }
      const body = {};
      if (storesData && storesData.length > 0) {
        body.is_multistore = true;
        body.stores = storesData;
      }
      if (projectTypeImpl) {
        body.project_type_impl = projectTypeImpl;
      }
      if (equipmentList && equipmentList.length > 0) {
        body.equipment_serials = equipmentList.map(eq => ({
          modelo: eq.modelo,
          serial: eq.serial,
          marca: eq.marca || '',
          equipo_id: eq.equipo_id,
          source: eq.source,
        }));
      }
      // PYME extended: server_name
      const effectiveServer = pymeServerName === 'Otro' ? pymeServerCustom : pymeServerName;
      if (effectiveServer) {
        body.server_name = effectiveServer;
      }
      // PYME extended: pinpad_serials
      const selectedPinpadSerials = pymePinpadSerials.filter(s => pymePinpadSerialsSelected[s.serial]);
      if (selectedPinpadSerials.length > 0) {
        body.pinpad_serials = selectedPinpadSerials.map(s => ({
          modelo: s.modelo,
          serial: s.serial,
          movement_id: s.movement_id || '',
        }));
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
    setMultistoreNewStore({ name: '', box_count: '' });
    setMultistoreSending(false);
    setProjectTypeImpl(null);
    setEquipmentList([]);
    setEquipmentAvailable({ quote_equipment: [], rif_equipment: [] });
    setEquipmentSelected({});
    // Reset PYME flow
    setPymeServerName('');
    setPymeServerCustom('');
    setPymeNeedsPinpads(null);
    setPymePinpadModels([]);
    setPymePinpadSelectedModel('');
    setPymePinpadSerials([]);
    setPymePinpadSerialsSelected({});
    setMultistorePhase('project_type');
    setMultistoreDialogOpen(true);
  };

  const handleProjectTypeSelect = async (type) => {
    setProjectTypeImpl(type);

    // Detectar si es PYME para flujo extendido
    const quote = quotes.find(q => q.quote_id === multistoreQuoteId);
    const segment = (quote?.client_segment || '').toLowerCase();
    const isPyme = segment === 'pyme' || segment === 'pymes' || (quote?.quote_number || '').toUpperCase().includes('-PYME');

    if (isPyme) {
      // Flujo PYME: server selection → pinpad question → pinpad selection
      setMultistorePhase('server');
      return;
    }

    if (type === 'payment_gateway') {
      // Payment Gateway: skip equipment, go to multistore question
      advanceToMultistorePhase();
    } else {
      // POS or VPOS/MPOS: load equipment
      setMultistorePhase('equipment');
      setEquipmentLoading(true);
      try {
        const res = await api.get(`/quotes/${multistoreQuoteId}/equipment-for-implementation?project_type=${type}`);
        setEquipmentAvailable(res.data);
        // Auto-select all quote equipment
        const sel = {};
        (res.data.quote_equipment || []).forEach(eq => { sel[eq.equipo_id] = true; });
        if (type === 'pos_fast_track') {
          // POS Fast Track: auto-select ALL quote equipment
          // (already done above)
        }
        setEquipmentSelected(sel);
      } catch (err) {
        toast.error('Error cargando equipos');
        setEquipmentAvailable({ quote_equipment: [], rif_equipment: [] });
      } finally {
        setEquipmentLoading(false);
      }
    }
  };

  const advanceToMultistorePhase = () => {
    // Build final equipment list from selections
    const allEquip = [...(equipmentAvailable.quote_equipment || []), ...(equipmentAvailable.rif_equipment || [])];
    const selected = allEquip.filter(eq => equipmentSelected[eq.equipo_id]);
    setEquipmentList(selected);

    // Check PYME: if PYME, skip multistore — go straight to confirm/send
    const quote = quotes.find(q => q.quote_id === multistoreQuoteId);
    const segment = (quote?.client_segment || '').toLowerCase();
    const isPyme = segment === 'pyme' || segment === 'pymes' || (quote?.quote_number || '').toUpperCase().includes('-PYME');
    if (isPyme) {
      // PYME flow: close dialog and send directly
      setMultistoreDialogOpen(false);
      handleSendToImplementation(multistoreQuoteId, multistoreExceptionInfo, null);
      return;
    }

    // Pre-check branch data for multistore
    const branchData = (quote?.branch_details || []).filter(b => b.store_name && b.quantity > 0);
    if (branchData.length > 0) {
      setMultistoreStores(branchData.map(b => ({ name: b.store_name, box_count: parseInt(b.quantity) || 0 })));
      setMultistorePhase('inherited');
    } else {
      setMultistoreStores([]);
      setMultistorePhase('ask');
    }
  };

  // ==================== FLUJO PYME EXTENDIDO ====================

  const handlePymeServerContinue = () => {
    const server = pymeServerName === 'Otro' ? pymeServerCustom.trim() : pymeServerName;
    if (!server) {
      toast.error('Seleccione o ingrese el servidor de instalación');
      return;
    }
    setMultistorePhase('pinpad_question');
  };

  const handlePymePinpadAnswer = async (needsPinpads) => {
    setPymeNeedsPinpads(needsPinpads);
    if (!needsPinpads) {
      // No necesita pinpads: proceder directamente a conversión
      setMultistoreDialogOpen(false);
      handleSendToImplementation(multistoreQuoteId, multistoreExceptionInfo, null);
    } else {
      // Sí necesita pinpads: cargar modelos disponibles
      setMultistorePhase('pinpad_selection');
      setPymePinpadLoading(true);
      try {
        const res = await api.get(`/quotes/${multistoreQuoteId}/pinpad-models`);
        setPymePinpadModels(res.data.models || []);
      } catch (err) {
        toast.error('Error cargando modelos de POS/Pinpad');
      } finally {
        setPymePinpadLoading(false);
      }
    }
  };

  const handlePymePinpadModelSelect = async (modelId) => {
    setPymePinpadSelectedModel(modelId);
    setPymePinpadSerials([]);
    setPymePinpadSerialsSelected({});
    if (!modelId) return;
    setPymePinpadLoading(true);
    try {
      const res = await api.get(`/quotes/${multistoreQuoteId}/inventory-serials?model_id=${modelId}`);
      const serials = res.data.serials || [];
      setPymePinpadSerials(serials);
      // Auto-select all
      const sel = {};
      serials.forEach(s => { sel[s.serial] = true; });
      setPymePinpadSerialsSelected(sel);
    } catch (err) {
      toast.error('Error buscando seriales en inventario');
    } finally {
      setPymePinpadLoading(false);
    }
  };

  const handlePymePinpadConfirm = () => {
    // Confirm and proceed to send
    setMultistoreDialogOpen(false);
    handleSendToImplementation(multistoreQuoteId, multistoreExceptionInfo, null);
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
      // Escenario B: Multitienda sin datos previos → abrir editor obligatorio
      setMultistoreStores([]);
      setMultistorePhase('collect');
    } else {
      // Escenario C: No es multitienda — ejecutar directamente (monotienda)
      setMultistoreDialogOpen(false);
      handleSendToImplementation(multistoreQuoteId, multistoreExceptionInfo, null);
    }
  };

  // Confirmar herencia de datos previos (Escenario A - Sí)
  const confirmInheritedStores = async () => {
    setMultistoreSending(true);
    setMultistoreDialogOpen(false);
    await handleSendToImplementation(multistoreQuoteId, multistoreExceptionInfo, multistoreStores);
    setMultistoreSending(false);
  };

  // Modificar distribución heredada (Escenario A - No)
  const modifyInheritedStores = () => {
    // Pasar a fase 'collect' con los datos pre-cargados para edición
    setIsMultistore(true);
    setMultistorePhase('collect');
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
    if (isMultistore && multistoreAssignedBoxes !== totalCajas) {
      toast.error(`Debe asignar exactamente ${totalCajas} caja(s). Asignadas: ${multistoreAssignedBoxes}`);
      return;
    }
    setMultistoreSending(true);
    setMultistoreDialogOpen(false);
    await handleSendToImplementation(multistoreQuoteId, multistoreExceptionInfo, isMultistore ? multistoreStores : null);
    setMultistoreSending(false);
  };

  // Modificar cotización (abrir wizard con datos precargados)
  const handleEditQuote = async (quote) => {
    // Equipos y Reparaciones: usar diálogo propio
    if (quote.quote_category === 'equipment' || quote.quote_category === 'repair') {
      setEditEquipRepairQuote(quote);
      setEditEquipRepairOpen(true);
      return;
    }
    
    // Implementaciones: mostrar modal de justificación primero
    setImplJustifyQuoteNum(quote.quote_number);
    setImplJustifyVersion(quote.version || 1);
    setImplJustifyCallback(() => async (justification) => {
      // Guardar justificación para uso al guardar
      window.__implEditJustification = justification;
      // Cargar datos y abrir wizard
      await loadImplementationForEdit(quote);
    });
    setImplJustifyOpen(true);
  };

  // Función separada para cargar datos de implementación en el wizard
  const loadImplementationForEdit = async (quote) => {
    setImplJustifyOpen(false);
    
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
    const mapAdditionalItem = (s) => {
      const name = s.item_name || s.name || '';
      let setup = s.tarifa_setup || 0;
      let recurrente = s.tarifa_recurrente || 0;
      // Recuperar precio del catálogo si viene con 0 (posible fallo de lookup original)
      if (setup === 0 && recurrente === 0 && name) {
        const catalogPrices = findServicePriceWithModel(name, quote.pricing_model || 'conventional');
        if (catalogPrices.setup_cost > 0) setup = catalogPrices.setup_cost;
        if (catalogPrices.monthly_cost > 0) recurrente = catalogPrices.monthly_cost;
      }
      return {
        id: s.item_id || `additional_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        service_id: s.item_id || s.service_id || '',
        medio_pago_name: name,
        name: name,
        quantity: s.quantity || 1,
        bank_id: s.bank_id || '',
        bank_name: s.bank_name || '',
        tarifa_setup: setup,
        tarifa_recurrente: recurrente,
        unit_price_usd: s.unit_price_usd || 0,
        total_usd: s.total_usd || 0,
        cantidad_cajas: s.cantidad_cajas || s.quantity || 1,
        cantidad_bancos: s.cantidad_bancos || 1,
        isDefault: false,
        isAutoLinked: false,
        isFromDB: true,
        lockBancos: false
      };
    };
    
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
      const pinpad = (quoteData.quote_type === 'FAST_TRACK')
        ? [...posDevices, ...pinpads].find(p => p.hardware_id === quoteData.pinpad_id)
        : pinpads.find(p => p.hardware_id === quoteData.pinpad_id);
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
      
      // Usar totalNetoSetup del wizard (ya calculado correctamente en el componente)
      const subtotal = allServices.reduce((sum, item) => sum + (item.total_usd || 0), 0);
      const total = subtotal - (quoteData.descuento || 0);
      
      // Calcular costo de hardware Fast Track
      const ftHwSubtotal = (() => {
        if (quoteData.quote_type !== 'FAST_TRACK') return 0;
        if (quoteData.pinpad_id && quoteData.pinpad_id !== 'none') {
          const hw = [...posDevices, ...pinpads].find(p => p.hardware_id === quoteData.pinpad_id);
          if (hw) return (parseInt(quoteData.cantidad_cajas) || 1) * (hw.price_bs_usd || hw.price_usd || 0);
        }
        return ftEquipmentItems.reduce((acc, it) => acc + (it.quantity * it.unit_price_usd), 0);
      })();

      // Construir ft_equipment_items sincronizado
      const syncedFtItems = (() => {
        if (quoteData.quote_type !== 'FAST_TRACK') return [];
        if (quoteData.pinpad_id && quoteData.pinpad_id !== 'none') {
          const hw = [...posDevices, ...pinpads].find(p => p.hardware_id === quoteData.pinpad_id);
          if (hw) return [{ hardware_id: hw.hardware_id, name: hw.name, hardware_type: hw.type || 'POS', quantity: parseInt(quoteData.cantidad_cajas) || 1, unit_price_usd: hw.price_bs_usd || hw.price_usd || 0 }];
        }
        return ftEquipmentItems;
      })();

      // Actualizar la cotización duplicada
      await api.put(`/quotes/${newQuoteId}`, {
        quote_type: quoteData.quote_type,
        client_id: quoteData.client_id,
        pricing_model: quoteData.pricing_model,
        services: allServices,
        integrator_id: quoteData.integrator_id,
        integrator_name: integrator?.name || '',
        integrator_app_name: integrator?.app_name || quoteData.integrator_app_name || '',
        pinpad_id: quoteData.pinpad_id === 'none' ? '' : quoteData.pinpad_id,
        pinpad_model: quoteData.pinpad_id && quoteData.pinpad_id !== 'none' ? (pinpad?.name || '') : '',
        sponsor_bank_id: quoteData.sponsor_bank_id === 'none' ? '' : quoteData.sponsor_bank_id,
        sponsor_bank_name: quoteData.sponsor_bank_id && quoteData.sponsor_bank_id !== 'none' ? (sponsorBank?.name || '') : '',
        subtotal_usd: subtotal,
        total_usd: totalNetoSetup + ftHwSubtotal,
        recurring_total_usd: totalNetoRecurrente,
        ft_hardware_subtotal: ftHwSubtotal,
        ft_equipment_items: syncedFtItems,
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
      
      // Registrar justificación en bitácora del cliente
      const implJustification = window.__implEditJustification;
      if (implJustification && quoteData.client_id) {
        try {
          await api.post(`/clients/${quoteData.client_id}/logs`, {
            client_id: quoteData.client_id,
            detail: `Modificación Implementación — ${duplicateResponse.data.new_quote_number} (v${duplicateResponse.data.version}): ${implJustification}`,
            action: 'Modificación de Cotización'
          });
        } catch (logErr) { console.error('Error bitácora:', logErr); }
        window.__implEditJustification = null;
      }
      
      // Regenerar PDF para la nueva versión (backend reconstruye desde datos almacenados)
      try {
        await api.post(`/quotes/${newQuoteId}/regenerate-pdf`, {});
        toast.success('PDF generado y registrado en anexos');
      } catch (pdfError) {
        console.error('Error regenerando PDF:', pdfError);
        toast.info('Cotización guardada. Puede generar el PDF manualmente desde Acciones.');
      }
      
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
    // Limpiar búsqueda de clientes
    setClientSearchQuery('');
    setClientSearchResults([]);
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
    // Reset Fast Track equipment
    setFtEquipmentItems([]);
    // Reset branch details
    setBranchDetails([]);
  };

  // Marcar reparación como completada — ahora abre modal con calculadora
  const handleRepairComplete = async (quoteId) => {
    setRepairCompleteQuoteId(quoteId);
    setRepairCompleteConfig({
      exceptionHeaders: pendingAction?.exceptionHeaders || null,
      emailHeaders: getEmailHeaders(),
    });
    setRepairCompleteModalOpen(true);
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
      exceptionReasonRef.current = '';
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
    ? (quoteData.quote_type === 'FAST_TRACK'
        ? [...posDevices, ...pinpads].find(p => p.hardware_id === quoteData.pinpad_id)
        : pinpads.find(p => p.hardware_id === quoteData.pinpad_id))
    : null;
  const selectedSponsorBank = quoteData.sponsor_bank_id && quoteData.sponsor_bank_id !== 'none'
    ? banks.find(b => b.bank_id === quoteData.sponsor_bank_id)
    : null;
  
  // Detectar si es cotización Payment Gateway o MPOS
  const isPaymentGateway = quoteData.quote_type === 'GATEWAY';
  const isVPOS = quoteData.quote_type === 'VPOS';
  const isMPOS = quoteData.quote_type === 'MPOS' || quoteData.quote_type === 'FAST_TRACK';
  const isFastTrackType = quoteData.quote_type === 'FAST_TRACK';
  const isMegaSoftSponsor = selectedSponsorBank?.name?.toLowerCase().includes('mega soft') || selectedSponsorBank?.name?.toLowerCase().includes('megasoft');
  
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

          {/* Botones de Nueva Cotización — Visibilidad por Permisos Especiales */}
          {rbac.showButtons && (
              <div className="flex items-center gap-3 mb-6">
                {/* Botón 1: Implementaciones */}
                {rbac.hasAnyImpl && (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button data-testid="create-quote-button" className="bg-brand-green-600 hover:bg-brand-green-700 text-white">
                        <Plus size={20} className="mr-2" />
                        Implementaciones
                        <ChevronDown size={16} className="ml-2" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="start" className="w-72">
                      {rbac.hasImplPyme && (
                        <DropdownMenuItem onClick={() => openWizard('PYME')} className="py-3 cursor-pointer" data-testid="new-impl-pyme">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-lg bg-emerald-100 flex items-center justify-center">
                              <Users size={16} className="text-emerald-700" />
                            </div>
                            <div>
                              <p className="font-medium text-sm">Clientes Pymes</p>
                              <p className="text-xs text-slate-500">VPOS, MPOS, Gateway, Link de Pago</p>
                            </div>
                          </div>
                        </DropdownMenuItem>
                      )}
                      {rbac.hasImplCorp && (
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
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                )}

                {/* Botón 2: Equipos y Accesorios */}
                {rbac.hasEquipos && (
                  <Button onClick={() => { setEquipmentWizardMode('equipment'); setEquipmentWizardOpen(true); }}
                    data-testid="create-equipment-quote-button"
                    className="bg-brand-blue-600 hover:bg-brand-blue-700 text-white">
                    <Plus size={20} className="mr-2" />
                    Equipos y Accesorios
                  </Button>
                )}

                {/* Botón 3: Reparaciones */}
                {rbac.hasReparaciones && (
                  <Button onClick={() => { setEquipmentWizardMode('repair'); setEquipmentWizardOpen(true); }}
                    data-testid="create-repair-quote-button"
                    className="bg-amber-600 hover:bg-amber-700 text-white">
                    <Plus size={20} className="mr-2" />
                    Reparaciones
                  </Button>
                )}
              </div>
          )}

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

          {/* Panel de Gestión Único - Todas las Cotizaciones (filtradas por RBAC) */}
          <QuotesTable
            quotes={rbacFilteredQuotes}
            clients={clients}
            filterClient={filterClient}
            filterStatus={filterStatus}
            filterCategory={filterCategory}
            filterSegment={filterSegment}
            filterDateFrom={filterDateFrom}
            filterDateTo={filterDateTo}
            actionLoading={actionLoading}
            canEdit={canEdit}
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
            onOpenFtConfig={(quote) => handleEditQuote(quote)}
            onPreassignSerials={(quote) => setPreassignModal({ open: true, quote })}
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


          {/* Wizard de Nueva Cotización (componente extraído) */}
          <QuoteWizardDialog ctx={{
            wizardOpen, setWizardOpen, isEditing, setIsEditing, setEditingQuoteId,
            quoteData, setQuoteData, banks, integrators, pinpads, posDevices, allHardware,
            serviceCatalog, clients, clientSearchQuery, setClientSearchQuery, clientSearchResults,
            selectedBankId, setSelectedBankId, selectedMedioPagoId, setSelectedMedioPagoId,
            availableMediosPago, setAvailableMediosPago,
            pgSetupItems, setPgSetupItems, pgTransactionRange, setPgTransactionRange,
            pgRecurringCostsTable, setPgRecurringCostsTable, pgSelectedMedioPago, setPgSelectedMedioPago,
            pgSelectedBankId, setPgSelectedBankId, pgDefaults,
            pgShowRecurringTable, setPgShowRecurringTable, pgFilteredProducts, setPgFilteredProducts,
            ftEquipmentItems, setFtEquipmentItems,
            branchDetails, setBranchDetails,
            isProductionClient, setIsProductionClient,
            productionItems, setProductionItems,
            productionSelectedServiceId, setProductionSelectedServiceId,
            pdfPreviewLoading,
            selectedClient, selectedIntegrator, selectedPinpad, selectedSponsorBank,
            isPaymentGateway, isVPOS, isMPOS, isFastTrackType, isMegaSoftSponsor,
            isHeaderComplete, canShowItems,
            calcularTotal, calcularTotalEstandar, calcularTotalRecurrente,
            subtotalSetup, subtotalRecurringBasic, subtotalRecurringOther, subtotalRecurringAdditional,
            subtotalRecurrente, subtotalProduction, montoDescuentoSetup, montoDescuentoRecurrente,
            totalNetoSetup, totalNetoRecurrente, ftHardwareSubtotal, grandTotal,
            pgSetupTotal,
            pgMediosPagoCount,
            initializeSetupConcepts, initializeRecurringBasicConcepts, initializeRecurringOtherConcepts,
            findServicePrice, findServicePriceWithModel, handleBankSelect,
            addMedioPagoItem, addMultipleMediosPago, duplicateSetupItem, handleSubmitQuote,
            handleSubmitPGQuote, exportCurrentQuoteToPDF, previewCurrentQuotePDF,
            handlePgBankChange, addPgSetupItem, addMultiplePgSetupItems,
            generatePgRecurringTable, getPgFullRecurringTable,
            getPricingModelName,
            handleIntegratorChange, removeAdditionalItem, removeSetupItem,
            removeRecurringBasicItem, removeRecurringOtherItem, removePgSetupItem,
            getQuoteTypeName, initPgSetup,
            pgFullRecurringTable, updateSetupItem, updateRecurringBasicItem,
            updateRecurringOtherItem, updateAdditionalItem, updatePgSetupItem,
            isLoadingEdit, editingQuoteId, currentUser,
          }} />

          {/* Modales secundarios (componente extraído) */}
          <QuoteModals ctx={{
            pdfPreviewOpen, setPdfPreviewOpen, pdfPreviewUrl, setPdfPreviewUrl, pdfPreviewLoading,
            equipmentWizardOpen, setEquipmentWizardOpen, equipmentWizardMode, setEquipmentWizardMode,
            clients, allHardware, currentUser, fetchData, quotes,
            deleteConfirmOpen, setDeleteConfirmOpen, deleteQuoteData, executeDeleteQuote,
            workflowModalOpen, setWorkflowModalOpen, workflowQuoteId, setWorkflowQuoteId,
            workflowConfig, setWorkflowConfig, handleWorkflowSuccess,
            approvalModalOpen, setApprovalModalOpen, approvalQuoteId, setApprovalQuoteId,
            approvalConfig, setApprovalConfig,
            anexosOpen, setAnexosOpen, anexosQuoteId, setAnexosQuoteId, anexosQuoteNumber,
            exceptionModalOpen, setExceptionModalOpen, exceptionData, setExceptionData,
            exceptionReasonRef, exceptionDebounceRef, pendingAction, setPendingAction,
            confirmException,
            emailModalOpen, setEmailModalOpen, emailModalConfig, emailCustomMessage, setEmailCustomMessage,
            emailNewRecipient, setEmailNewRecipient, emailRecipientsList, setEmailRecipientsList,
            addEmailRecipient, removeEmailRecipient, confirmEmailAndProceed,
            bitacoraFlujoOpen, setBitacoraFlujoOpen, bitacoraFlujoQuoteNumber,
            bitacoraFlujoEntries, bitacoraFlujoLoading,
            deliveryDialogOpen, setDeliveryDialogOpen, deliveryQuoteId, deliveryExceptionInfo,
            repairDeliveryDialogOpen, setRepairDeliveryDialogOpen,
            preassignModal, setPreassignModal,
            multistoreDialogOpen, setMultistoreDialogOpen, multistoreSending,
            multistorePhase, setMultistorePhase, multistoreStores, setMultistoreStores,
            multistoreNewStore, setMultistoreNewStore, isMultistore, setIsMultistore,
            multistoreAssignedBoxes, confirmMultistore, addMultistoreStore, removeMultistoreStore,
            getMultistoreTotalCajas, getMultistoreQuote, confirmInheritedStores,
            handleProjectTypeSelect, advanceToMultistorePhase, modifyInheritedStores, handleMultistoreAnswer,
            pymeServerName, setPymeServerName, pymeServerCustom, setPymeServerCustom,
            pymeNeedsPinpads, setPymeNeedsPinpads,
            pymePinpadModels, pymePinpadSelectedModel,
            pymePinpadSerials, pymePinpadSerialsSelected, setPymePinpadSerialsSelected,
            pymePinpadLoading, handlePymeServerContinue, handlePymePinpadAnswer,
            handlePymePinpadModelSelect, handlePymePinpadConfirm,
            projectTypeImpl, equipmentList, equipmentAvailable, equipmentLoading,
            equipmentSelected, setEquipmentSelected,
          }} />

          {/* Modal Reparacion Completada con Calculadora */}
          <RepairCompleteModal
            open={repairCompleteModalOpen}
            onClose={() => { setRepairCompleteModalOpen(false); setRepairCompleteQuoteId(null); }}
            onSuccess={fetchData}
            quoteId={repairCompleteQuoteId}
            quotes={quotes}
            config={repairCompleteConfig}
          />

          {/* Diálogo de edición de Equipos/Reparaciones */}
          <EditEquipRepairDialog
            open={editEquipRepairOpen}
            onClose={() => { setEditEquipRepairOpen(false); setEditEquipRepairQuote(null); }}
            quote={editEquipRepairQuote}
            onSaved={fetchData}
          />

          {/* Modal de justificación para Implementaciones */}
          <JustificationModal
            open={implJustifyOpen}
            onClose={() => { setImplJustifyOpen(false); setImplJustifyCallback(null); }}
            onConfirm={async (justification) => {
              if (implJustifyCallback) {
                await implJustifyCallback(justification);
              }
            }}
            quoteNumber={implJustifyQuoteNum}
            version={implJustifyVersion}
          />
        </div>

      </main>
    </div>
  );
};

export default Quotes;
