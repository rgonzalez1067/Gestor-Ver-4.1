import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
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
import { Plus, FileText, Download, Monitor, Globe, Smartphone, Link, Trash2, Building2, CreditCard, CheckCircle2, Copy, Cpu, Users, Landmark, Pencil, Mail, CheckCircle, Send, Package, Settings2, X, Search, Calendar, Receipt, Banknote, Truck, RefreshCw, Upload, FolderOpen, ChevronsUpDown, Check, Unlock, Eye, AlertTriangle, ChevronDown, Store, Database } from 'lucide-react';
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
import { ModifyQuoteChoiceDialog } from '../components/ModifyQuoteChoiceDialog';
import { QuotesTable } from '../components/quotes/QuotesTable';
import { NewQuoteButtons } from '../components/quotes/NewQuoteButtons';
import { QuotesKpiCards } from '../components/quotes/QuotesKpiCards';
import { IrregularQuotesBanner } from '../components/quotes/IrregularQuotesBanner';
import { PdfPreviewModal } from '../components/quotes/PdfPreviewModal';
import { DeliveryDialog } from '../components/quotes/DeliveryDialog';
import { RepairDeliveryDialog } from '../components/quotes/RepairDeliveryDialog';
import { RepairCompleteModal } from '../components/quotes/RepairCompleteModal';
import { PreassignSerialsModal } from '../components/quotes/PreassignSerialsModal';
import { QuoteWizardDialog } from '../components/quotes/QuoteWizardDialog';
import { validateMultiRif } from '../components/quotes/MultiRifDistributionPanel';
import { QuoteModals } from '../components/quotes/QuoteModals';
import { QuotesBundleMigrationModal } from '../components/quotes/QuotesBundleMigrationModal';
import { QUOTE_TYPES, PRICING_MODELS, SETUP_CONCEPTS, RECURRING_BASIC_CONCEPTS, RECURRING_OTHER_CONCEPTS, STATUS_COLORS, STATUS_DISPLAY_NAMES, QUOTE_CATEGORY_LABELS, ACTION_LABELS } from '../components/quotes/constants';
import api from '../utils/api';
import { toast } from 'sonner';
import { usePermission } from '../hooks/usePermission';
import { useQuoteFilters } from '../hooks/useQuoteFilters';
import { useQuoteRbac } from '../hooks/useQuoteRbac';



export const Quotes = () => {
  const { canEdit, user: currentUser } = usePermission('cotizaciones');
  const [searchParams, setSearchParams] = useSearchParams();
  const [highlightedQuote, setHighlightedQuote] = useState(null);
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
  const [actionOverrides, setActionOverrides] = useState({}); // Fase B: overrides por config_key
  const [customActions, setCustomActions] = useState([]);     // Fase A: acciones custom
  const [wizardOpen, setWizardOpen] = useState(false);
  const [equipmentWizardOpen, setEquipmentWizardOpen] = useState(false);
  const [equipmentWizardMode, setEquipmentWizardMode] = useState(''); // 'equipment' o 'repair'
  const [equipmentWizardSegment, setEquipmentWizardSegment] = useState('PYME'); // Iter50: PYME | CORP
  
  
  
  // Estado para usar plantilla PDF
  const [useTemplateForPDF, setUseTemplateForPDF] = useState(true); // Por defecto usa plantilla si está disponible
  const [templateAvailable, setTemplateAvailable] = useState({});
  
  // Estados para filtros rápidos
  const {
    filterClient, setFilterClient,
    filterStatus, setFilterStatus,
    filterCategory, setFilterCategory,
    filterSegment, setFilterSegment,
    filterDateFrom, setFilterDateFrom,
    filterDateTo, setFilterDateTo,
    clearFilters,
  } = useQuoteFilters();

  // RBAC: Permisos especiales de cotizaciones + listado filtrado
  const { rbac, rbacFilteredQuotes } = useQuoteRbac({ currentUser, canEdit, quotes });

  // Subset de clientes con cotizaciones activas/visibles para el usuario actual.
  // Se usa SOLO en el dropdown de Filtros Rápidos para que no muestre todo el catálogo
  // de clientes (que dificulta la búsqueda). Se considera "activa" toda cotización que
  // no esté archivada y que el usuario pueda ver por RBAC. La tabla y otros consumidores
  // siguen recibiendo el catálogo completo para resolver legal_name en cualquier fila.
  const clientsWithActiveQuotes = useMemo(() => {
    const ids = new Set(
      (rbacFilteredQuotes || [])
        .filter((q) => !q.archived)
        .map((q) => q.client_id)
        .filter(Boolean),
    );
    return (clients || []).filter((c) => ids.has(c.client_id));
  }, [rbacFilteredQuotes, clients]);

  // Migración de BD (solo admin)
  const isAdmin = (currentUser?.role || '').toLowerCase() === 'admin';
  const [bundleModalOpen, setBundleModalOpen] = useState(false);
  
  // Estado para edición de cotización existente
  const [editingQuoteId, setEditingQuoteId] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isLoadingEdit, setIsLoadingEdit] = useState(false);
  // Estado para edición de Equipos/Reparaciones
  const [editEquipRepairOpen, setEditEquipRepairOpen] = useState(false);
  const [editEquipRepairQuote, setEditEquipRepairQuote] = useState(null);
  // Estado para modal de elección "Modificar Cotización"
  const [modifyChoiceOpen, setModifyChoiceOpen] = useState(false);
  const [modifyChoiceQuote, setModifyChoiceQuote] = useState(null);
  const [editMode, setEditMode] = useState('new_version'); // 'new_version' | 'in_place'
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
    integrator_name: '',
    integrator_app_name: '', // Campo informativo auto-completado
    pinpad_id: '',
    sponsor_bank_id: '', // Entidad patrocinadora/vendedora
    requires_pinpad_config: true,  // ¿Requiere Configuración de PinPads?
    requires_vpn: false,           // ¿Requiere VPN? (default No)
    communication_type: 'NO_APLICA', // Tipo de Comunicación: VPN | SSL | NO_APLICA
    setup_items: [],              // Items exclusivos de Setup
    recurring_basic_items: [],    // Recurrentes Básicos (incluye complementos de adicionales)
    recurring_other_items: [],    // Otros Recurrentes
    additional_items: [],         // Items adicionales (medios de pago de bancos)
    descuento: 0,
    descuento_setup: 0,
    descuento_recurrente: 0,
    notes: '',
    include_recurring: true,
    // Implementación Patrocinada (radio Sí/No + dropdown banco condicional)
    sponsored_implementation: false,
    sponsoring_bank_id: '',
    sponsoring_processor_id: '',
    sponsoring_processor_name: '',
    // Cliente exento de IVA (radio Sí/No)
    iva_exempt: false,
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
  // Regularización masiva (admin)
  const [regularizeBatchOpen, setRegularizeBatchOpen] = useState(false);
  const [regularizeRunning, setRegularizeRunning] = useState(false);
  const [regularizeResult, setRegularizeResult] = useState(null);
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
  // "Enviar al Cliente" — Paso 1: selección de contactos de la ficha del cliente.
  const [contactSelectOpen, setContactSelectOpen] = useState(false);
  const [contactSelectQuoteId, setContactSelectQuoteId] = useState(null);
  const [contactList, setContactList] = useState([]);
  const [contactSelectedEmails, setContactSelectedEmails] = useState([]);
  const [contactSelectLoading, setContactSelectLoading] = useState(false);
  // "Cotización Equipos Infra" — interceptación post-personalización para clientes Corp.
  const [equiposInfraOpen, setEquiposInfraOpen] = useState(false);
  const [equiposInfraQuoteId, setEquiposInfraQuoteId] = useState(null);
  const [equiposInfraSending, setEquiposInfraSending] = useState(false);
  // Adjuntos manuales del modal de Personalizar Comunicación.
  // Cada item: { attachment_id, filename, size, content_type }
  const [emailManualAttachments, setEmailManualAttachments] = useState([]);
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
  // Headers de personalización de correo (mensaje, CCs, anexos manuales) que
  // se capturan al confirmar el modal de envío y se propagan al diálogo de
  // delivery para que el POST /deliver los incluya. Antes los anexos manuales
  // se perdían entre el cierre del modal de correo y el envío real.
  const [deliveryEmailHeaders, setDeliveryEmailHeaders] = useState(null);

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
  const [economicGroup, setEconomicGroup] = useState('');
  const [fantasyName, setFantasyName] = useState('');
  const [pymeNeedsPinpads, setPymeNeedsPinpads] = useState(null); // null | true | false
  const [pymePinpadModels, setPymePinpadModels] = useState([]); // [{hardware_id, name, type}]
  const [pymePinpadSelectedModel, setPymePinpadSelectedModel] = useState(''); // hardware_id
  const [pymePinpadSerials, setPymePinpadSerials] = useState([]); // [{serial, modelo, movement_id, ...}]
  const [pymePinpadSerialsSelected, setPymePinpadSerialsSelected] = useState({}); // Map serial -> boolean
  const [pymePinpadLoading, setPymePinpadLoading] = useState(false);
  // Sub-flujo "Sí, pero no dispongo de seriales — los suministra un tercero".
  const [serialsByOther, setSerialsByOther] = useState(false); // muestra sub-opciones
  const [serialsProviderNote, setSerialsProviderNote] = useState(''); // texto inyectado en Ficha Técnica
  const [serialsBankModal, setSerialsBankModal] = useState({ open: false, processor: null });
  // Fase Impresora Fiscal (Feb 2026): se solicita después de pinpad y antes
  // de consolidated_data, para imprimir en la Ficha Técnica de la Implementación.
  const [fiscalPrinterFromClient, setFiscalPrinterFromClient] = useState(''); // valor pre-existente en cliente
  const [fiscalPrinterModel, setFiscalPrinterModel] = useState(''); // valor capturado en el modal
  // Modal 2 — Confirmación de Implementador (heredado desde ficha de cliente)
  const [confirmImplementerInfo, setConfirmImplementerInfo] = useState({ loading: false, name: '', user_id: '' });
  // Instrucciones adicionales para el Implementador (HTML rich-text, máx 500 chars)
  const [implInstructions, setImplInstructions] = useState('');
  const [implInstructionsLen, setImplInstructionsLen] = useState(0);

  useEffect(() => {
    fetchData();
    // Cargar overrides + custom actions del Motor de Notificaciones
    (async () => {
      try {
        const [ovRes, caRes] = await Promise.all([
          api.get('/quote-action-overrides'),
          api.get('/quote-custom-actions'),
        ]);
        const ovMap = {};
        for (const o of ovRes.data?.items || []) ovMap[o.config_key] = o;
        setActionOverrides(ovMap);
        setCustomActions(caRes.data?.items || []);
      } catch {
        // Si los endpoints no existen aún (deploy parcial), usar valores por defecto
      }
    })();
  }, []);

  // Auto-highlight cuando se llega con ?highlight=COT-NUMBER (desde Reportes de Irregulares)
  useEffect(() => {
    const target = searchParams.get('highlight');
    if (!target || quotes.length === 0) return;
    const match = quotes.find(q => q.quote_number === target);
    if (match) {
      setHighlightedQuote(target);
      // Scroll a la fila tras un breve delay para esperar el render
      setTimeout(() => {
        const row = document.querySelector(`[data-quote-row="${target}"]`);
        if (row) row.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 200);
      // Quitar highlight a los 6s
      setTimeout(() => setHighlightedQuote(null), 6000);
    }
    // Limpiar el query param
    const next = new URLSearchParams(searchParams);
    next.delete('highlight');
    setSearchParams(next, { replace: true });
    // eslint-disable-next-line
  }, [quotes]);

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

  // Productos CORE (Tarjetas) — disparan tarifa plana (techo) en items con autoTariff
  // Soporta variantes TDC/TDD ↔ TDD/TDC, con/sin acentos y cualquier número de espacios.
  const CORE_PRODUCTS_LOWER = [
    'tarjeta de crédito y débito',
    'tarjeta de credito y debito',
    'tarjeta de crédito/débito',
    'tarjeta de credito/debito',
    'tarjetas de crédito y débito',
    'tarjetas de credito y debito',
    // Liquidación en divisas — orden TDC/TDD
    'tdc/tdd liquidación en divisas',
    'tdc/tdd liquidacion en divisas',
    'tdc / tdd liquidación en divisas',
    'tdc / tdd liquidacion en divisas',
    // Liquidación en divisas — orden TDD/TDC (catálogo real BD)
    'tdd/tdc liquidación en divisas',
    'tdd/tdc liquidacion en divisas',
    'tdd / tdc liquidación en divisas',
    'tdd / tdc liquidacion en divisas',
  ];

  /** Normaliza nombre: lowercase, trim, colapsa espacios múltiples. */
  const normalizeProductName = (name) => (name || '').toLowerCase().replace(/\s+/g, ' ').trim();

  /** Determina si un nombre de producto es CORE (Tarjeta o TDC/TDD divisas). */
  const isCoreProductName = (name) => {
    const n = normalizeProductName(name);
    if (!n) return false;
    return CORE_PRODUCTS_LOWER.some(c => n === c || n.startsWith(c) || n.includes(c));
  };

  /**
   * Calcula la tarifa automática según las reglas de negocio:
   * - Si hay al menos un producto CORE en `additional_items` → retorna `ceiling`.
   * - Si NO hay CORE → suma `perUnit` por cada combinación digital/banco con techo `ceiling`.
   * Cada item en `additional_items` ya representa una combinación (producto, banco).
   */
  const calculateAutoTariff = (additionalItems, ceiling, perUnit) => {
    const items = additionalItems || [];
    const hasCore = items.some(it => isCoreProductName(it.medio_pago_name || it.name));
    if (hasCore) return ceiling;
    const digitalCount = items.filter(it => !isCoreProductName(it.medio_pago_name || it.name)).length;
    return Math.min(digitalCount * perUnit, ceiling);
  };

  // ============================================================================
  // REGLA DE NEGOCIO: TDD/TDC Liquidación en Divisas en Setup
  // ----------------------------------------------------------------------------
  // Cuando el usuario incluye en "Set Up - Puesta en Marcha" un item llamado
  // "TDD/TDC Liquidación en Divisas" (con cantidad > 0), las tarifas de los
  // recurrentes con autoTariff se cargan a su techo ($8 / $6) como DEFAULT
  // editable. El usuario puede modificarlas manualmente; no se sobrescriben
  // mientras la regla esté activa. Si quita el concepto, las tarifas vuelven al
  // cálculo automático normal.
  //
  // Aplica solo a tipos VPOS, MPOS, FAST_TRACK (no GATEWAY ni LINK).
  // El item puede aparecer en `setup_items` (concepto base) o en
  // `additional_items` (medio de pago × banco — caso real de uso).
  // ============================================================================
  const TDD_TDC_DIVISAS_PATTERNS = [
    // Orden TDD/TDC (catálogo real)
    'tdd/tdc liquidación en divisas',
    'tdd/tdc liquidacion en divisas',
    'tdd / tdc liquidación en divisas',
    'tdd / tdc liquidacion en divisas',
    // Orden TDC/TDD (variante)
    'tdc/tdd liquidación en divisas',
    'tdc/tdd liquidacion en divisas',
    'tdc / tdd liquidación en divisas',
    'tdc / tdd liquidacion en divisas',
  ];
  const TDD_TDC_ELIGIBLE_TYPES = ['VPOS', 'MPOS', 'FAST_TRACK'];

  const matchesTddTdcDivisas = (rawName) => {
    const n = normalizeProductName(rawName);
    if (!n) return false;
    return TDD_TDC_DIVISAS_PATTERNS.some(p => n === p || n.startsWith(p) || n.includes(p));
  };

  const isTddTdcDivisasActive = useMemo(() => {
    if (!TDD_TDC_ELIGIBLE_TYPES.includes(quoteData.quote_type)) return false;
    // Buscar tanto en setup_items como en additional_items (la sección "Set Up"
    // de la UI muestra ambos juntos).
    const setupItems = quoteData.setup_items || [];
    const additionals = quoteData.additional_items || [];
    const checkList = (items) => items.some(it => {
      const rawName = it.medio_pago_name || it.name || '';
      const qty = Number(it.cantidad_cajas ?? it.cantidad ?? it.quantity ?? 0);
      if (qty <= 0) return false;
      return matchesTddTdcDivisas(rawName);
    });
    return checkList(setupItems) || checkList(additionals);
  }, [quoteData.setup_items, quoteData.additional_items, quoteData.quote_type]);

  // Reactividad: recalcular tarifas en items con autoTariff cuando cambien los additional_items
  useEffect(() => {
    if (isLoadingEdit) return;
    // Si la regla TDD/TDC Liquidación en Divisas está activa, NO recalcular
    // automáticamente (preservar valores default $8/$6 o ediciones manuales).
    if (isTddTdcDivisasActive) return;
    const additionals = quoteData.additional_items || [];

    let changed = false;

    const updatedBasic = (quoteData.recurring_basic_items || []).map(item => {
      if (!item.autoTariff || item.tarifaManual) return item;
      const newT = calculateAutoTariff(additionals, item.autoTariff.ceiling, item.autoTariff.perUnit);
      if (Number(item.tarifa) !== newT) {
        changed = true;
        return { ...item, tarifa: newT };
      }
      return item;
    });

    const updatedOther = (quoteData.recurring_other_items || []).map(item => {
      if (!item.autoTariff) return item;
      const newT = calculateAutoTariff(additionals, item.autoTariff.ceiling, item.autoTariff.perUnit);
      if (Number(item.tarifa) !== newT) {
        changed = true;
        return { ...item, tarifa: newT };
      }
      return item;
    });

    if (changed) {
      setQuoteData(prev => ({
        ...prev,
        recurring_basic_items: updatedBasic,
        recurring_other_items: updatedOther,
      }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [quoteData.additional_items, isLoadingEdit, isTddTdcDivisasActive]);

  // Detecta transición de la regla TDD/TDC Liquidación en Divisas (activar/desactivar)
  // - Activar: setea tarifas de items con autoTariff a su `ceiling` ($8 / $6).
  // - Desactivar: revierte al cálculo automático.
  const prevTddTdcActiveRef = useRef(false);
  useEffect(() => {
    if (isLoadingEdit) {
      prevTddTdcActiveRef.current = isTddTdcDivisasActive;
      return;
    }
    const wasActive = prevTddTdcActiveRef.current;
    if (isTddTdcDivisasActive && !wasActive) {
      // Activación → cargar tarifa ceiling como default editable
      setQuoteData(prev => ({
        ...prev,
        recurring_basic_items: (prev.recurring_basic_items || []).map(it =>
          it.autoTariff && !it.tarifaManual ? { ...it, tarifa: it.autoTariff.ceiling } : it
        ),
        recurring_other_items: (prev.recurring_other_items || []).map(it =>
          it.autoTariff ? { ...it, tarifa: it.autoTariff.ceiling } : it
        ),
      }));
    } else if (!isTddTdcDivisasActive && wasActive) {
      // Desactivación → recalcular tarifa según additional_items
      const additionals = quoteData.additional_items || [];
      setQuoteData(prev => ({
        ...prev,
        recurring_basic_items: (prev.recurring_basic_items || []).map(it =>
          it.autoTariff && !it.tarifaManual ? { ...it, tarifa: calculateAutoTariff(additionals, it.autoTariff.ceiling, it.autoTariff.perUnit) } : it
        ),
        recurring_other_items: (prev.recurring_other_items || []).map(it =>
          it.autoTariff ? { ...it, tarifa: calculateAutoTariff(additionals, it.autoTariff.ceiling, it.autoTariff.perUnit) } : it
        ),
      }));
    }
    prevTddTdcActiveRef.current = isTddTdcDivisasActive;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isTddTdcDivisasActive, isLoadingEdit]);

  // Sincronizar valores de Cajas de la cabecera con los conceptos base
  // REGLA DE ORO: Solo propaga cajas cuando el USUARIO cambia manualmente el header
  // BANCOS: Solo se propaga a items con `inheritBancos: true` (ej. "Suscripción PDV/Banco").
  //         Para el resto cada fila tiene su valor estático e independiente.
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

    const cajasChanged = prevCajasRef.current !== cajas;
    const bancosChanged = prevBancosRef.current !== bancos;

    // Si nada cambió, salir
    if (!cajasChanged && !bancosChanged) {
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

    // Actualizar Setup items — CAJAS siempre; BANCOS solo si inheritBancos
    const updatedSetupItems = setup_items.map(item => {
      let updated = item;
      if (cajasChanged && item.cantidad_cajas !== newCajas) {
        updated = { ...updated, cantidad_cajas: newCajas };
        needsUpdate = true;
      }
      if (bancosChanged && item.inheritBancos && !item.bancosManual && item.cantidad_bancos !== newBancos) {
        updated = { ...updated, cantidad_bancos: newBancos };
        needsUpdate = true;
      }
      return updated;
    });

    // Actualizar Recurrentes Básicos — SOLO CAJAS
    // Actualizar Recurrentes Básicos — CAJAS siempre; BANCOS solo si inheritBancos
    const updatedRecurringBasic = recurring_basic_items.map(item => {
      let updated = item;
      if (cajasChanged && item.cantidad_cajas !== newCajas) {
        updated = { ...updated, cantidad_cajas: newCajas };
        needsUpdate = true;
      }
      if (bancosChanged && item.inheritBancos && !item.bancosManual && item.cantidad_bancos !== newBancos) {
        updated = { ...updated, cantidad_bancos: newBancos };
        needsUpdate = true;
      }
      return updated;
    });

    // Actualizar Otros Recurrentes — SOLO CAJAS
    const updatedRecurringOther = recurring_other_items.map(item => {
      if (cajasChanged && item.cantidad_cajas !== newCajas) {
        needsUpdate = true;
        return { ...item, cantidad_cajas: newCajas };
      }
      return item;
    });

    // Actualizar Items Adicionales — SOLO CAJAS
    const updatedAdditionalItems = (additional_items || []).map(item => {
      if (cajasChanged && item.cantidad_cajas !== newCajas) {
        needsUpdate = true;
        return { ...item, cantidad_cajas: newCajas };
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
      // Ordenar clientes alfabéticamente por legal_name (Razón Social) con
      // fallback a fantasy_name para mejorar la búsqueda en el filtro.
      const sortedClients = [...(clientsRes.data || [])].sort((a, b) => {
        const an = (a.legal_name || a.fantasy_name || '').toLowerCase();
        const bn = (b.legal_name || b.fantasy_name || '').toLowerCase();
        return an.localeCompare(bn, 'es', { sensitivity: 'base' });
      });
      setClients(sortedClients);
      setBanks(banksRes.data);
      setServiceCatalog(servicesRes.data);
      setIntegrators(integratorsRes.data);
      // Irregular count
      try { const ic = await api.get('/quotes/irregular/count'); setIrregularCount(ic.data.count || 0); } catch {}
      // Guardar todos los hardware
      setAllHardware(hardwareRes.data || []);
      // Filtrar solo dispositivos tipo "Pinpad" y clasificación "Bien" para cotizaciones de implementación
      const pinpadDevices = (hardwareRes.data || []).filter(hw => 
        hw.type?.toLowerCase() === 'pinpad'
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
      // Excluir productos en "Fase Previa a Producción" (no disponibles para este banco).
      const filteredProducts = bank.products.filter(p => p[compatibilityField] !== false && !p.pre_production);
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
      // Por defecto cantidad_bancos=1 e independiente del selector global
      // Excepción: conceptos con inheritBancos heredan el valor del header
      return {
        id: `setup_${concept.name}`,
        medio_pago_name: concept.name,
        cantidad_cajas: cantidadCajas,
        cantidad_bancos: concept.inheritBancos ? (cantidadBancos || 1) : 1,
        tarifa: prices.setup_cost,
        isDefault: true,
        type: 'setup',
        lockBancos: concept.lockBancos || false,
        autoBancos: concept.autoBancos || false,
        inheritBancos: concept.inheritBancos || false
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
        // Por defecto 1 (independiente del selector global). Si el concepto tiene
        // inheritBancos, hereda el valor del header.
        cantidad_bancos: concept.inheritBancos ? (cantidadBancos || 1) : 1,
        tarifa: prices.monthly_cost,
        isDefault: true,
        type: 'recurring_basic',
        lockBancos: concept.lockBancos || false,
        inheritBancos: concept.inheritBancos || false,
        autoTariff: concept.autoTariff || null
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
        cantidad_bancos: 1, // Default 1 - independiente del selector global
        tarifa,
        isDefault: true,
        type: 'recurring_other',
        lockBancos: concept.lockBancos || false,
        autoTariff: concept.autoTariff || null
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
      integrator_name: '',
      integrator_app_name: '',
      pinpad_id: '',
      sponsor_bank_id: '',
      requires_pinpad_config: true,
      requires_vpn: false,
      communication_type: 'NO_APLICA',
      setup_items: [],
      recurring_basic_items: [],
      recurring_other_items: [],
      additional_items: [],
      descuento: 0,
      notes: '',
      include_recurring: true,
      sponsored_implementation: false,
      sponsoring_bank_id: '',
      sponsoring_processor_id: '',
      sponsoring_processor_name: '',
      iva_exempt: false,
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
  // Regla de negocio: "Sin Integrador" → Aplicativo Certificado = "Stand Alone" (obligatorio).
  const handleIntegratorChange = (integratorId) => {
    const integrator = integrators.find(i => i.integrator_id === integratorId);
    const isSinIntegrador = integratorId === 'sin_integrador';
    setQuoteData({
      ...quoteData,
      integrator_id: integratorId,
      integrator_app_name: isSinIntegrador ? 'Stand Alone' : (integrator?.app_name || ''),
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
  // === Sincronización reactiva Set Up → Costos Recurrentes Básicos ===
  // Cuando cambia el "Número de Cajas" de un ítem de Set Up (concepto base o
  // medio de pago adicional), se propaga automáticamente el mismo valor al ítem
  // gemelo de Recurrentes Básicos identificado por su vínculo 1:1 (sourceServiceId
  // / linkedTo / mismo nombre de producto). El flujo es UNIDIRECCIONAL.
  const propagateBoxesToRecurring = (recurringItems, sourceItem, newCajas) => {
    if (!Array.isArray(recurringItems) || !sourceItem) return recurringItems;
    const srcName = sourceItem.medio_pago_name;
    const srcId = sourceItem.id;
    let changed = false;
    const next = recurringItems.map(r => {
      // Prioridad 1: vínculo explícito por ID de origen o por producto vinculado.
      const linkedById = srcId && (r.sourceServiceId === srcId || r.sourceSetupId === srcId || r.linkedSetupId === srcId);
      const linkedByName = srcName && r.linkedTo === srcName;
      // Prioridad 2 (fallback): mismo nombre, SOLO para recurrentes sin vínculo
      // explícito (conceptos base), para no sobre-propagar a gemelos de otros productos.
      const sameNameUnlinked = srcName && r.medio_pago_name === srcName && !r.linkedTo && !r.sourceServiceId;
      const isTwin = linkedById || linkedByName || sameNameUnlinked;
      if (isTwin && r.cantidad_cajas !== newCajas) {
        changed = true;
        // Limpiamos totalOverride para que el subtotal se recalcule con las nuevas cajas.
        return { ...r, cantidad_cajas: newCajas, totalOverride: undefined };
      }
      return r;
    });
    return changed ? next : recurringItems;
  };

  const updateSetupItem = (index, field, value) => {
    const updatedItems = [...quoteData.setup_items];
    const parsed = field === 'cantidad_cajas' || field === 'cantidad_bancos' || field === 'tarifa'
      ? (value === '' ? '' : parseFloat(value))
      : value;
    updatedItems[index] = { ...updatedItems[index], [field]: parsed };
    const patch = { ...quoteData, setup_items: updatedItems };
    if (field === 'cantidad_cajas' && parsed !== '' && Number.isFinite(parsed) && parsed > 0) {
      patch.recurring_basic_items = propagateBoxesToRecurring(quoteData.recurring_basic_items, updatedItems[index], parsed);
    }
    setQuoteData(patch);
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

  // Duplicar cualquier concepto de Recurring Basic (manual o auto-vinculado).
  // La copia se desliga 100% del Setup que la generó (isAutoLinked=false,
  // inheritBancos=false, autoTariff=null) para que sea editable libremente y
  // no se elimine al recalcular las dependencias del Setup.
  const duplicateRecurringBasicItem = (index) => {
    const itemToDuplicate = quoteData.recurring_basic_items[index];
    if (!itemToDuplicate) return;
    const newItem = {
      ...itemToDuplicate,
      id: `recurring_basic_copy_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      isDefault: false,
      isCopy: true,
      // La copia es una fila manual editable: rompemos todos los vínculos auto.
      isAutoLinked: false,
      linkedSetupId: undefined,
      sourceSetupId: undefined,
      inheritBancos: false,
      lockBancos: false,
      autoTariff: null,
    };
    const updated = [
      ...quoteData.recurring_basic_items.slice(0, index + 1),
      newItem,
      ...quoteData.recurring_basic_items.slice(index + 1),
    ];
    setQuoteData({ ...quoteData, recurring_basic_items: updated });
    toast.success('Concepto duplicado');
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
    const next = {
      ...updatedItems[index],
      [field]: field === 'cantidad_cajas' || field === 'cantidad_bancos' || field === 'tarifa'
        ? (value === '' ? '' : parseFloat(value))
        : value
    };
    // Edición manual de la tarifa en items con cálculo automático (autoTariff,
    // p.ej. "Derecho de uso de plataforma MServer por PDV"): al escribir un
    // valor se marca `tarifaManual` para que el motor automático NO lo
    // sobrescriba. Si el campo se vacía, se revierte al cálculo automático.
    if (field === 'tarifa' && updatedItems[index]?.autoTariff) {
      next.tarifaManual = value !== '';
    }
    updatedItems[index] = next;
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
    const parsed = parseFloat(value) || 0;
    updatedItems[index] = {
      ...updatedItems[index],
      [field]: parsed
    };
    const patch = { ...quoteData, additional_items: updatedItems };
    // Sincronización Set Up → Recurrentes: propagar Número de Cajas al ítem gemelo.
    if (field === 'cantidad_cajas' && parsed > 0) {
      patch.recurring_basic_items = propagateBoxesToRecurring(quoteData.recurring_basic_items, updatedItems[index], parsed);
    }
    setQuoteData(patch);
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
      // Filtrar por gateway_available y excluir "Fase Previa a Producción".
      const filtered = (bank.products || []).filter(p => p.gateway_available && !p.pre_production);
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
  // Builder ÚNICO del payload de PDF (TemplateQuotePDFRequest) usado por
  // Guardar (create-with-pdf vía pdf_data), Previsualizar y Exportar, para
  // garantizar que las TRES generen EXACTAMENTE el mismo PDF (misma versión).
  const buildTemplatePdfData = (quoteNumber = '') => {
    const client = clients.find(c => c.client_id === quoteData.client_id) || selectedClient || {};
    const integrator = integrators.find(i => i.integrator_id === quoteData.integrator_id);
    const pinpad = (quoteData.quote_type === 'FAST_TRACK')
      ? [...posDevices, ...pinpads].find(p => p.hardware_id === quoteData.pinpad_id)
      : pinpads.find(p => p.hardware_id === quoteData.pinpad_id);
    const sponsorBank = banks.find(b => b.bank_id === quoteData.sponsor_bank_id);
    const templateTypeMap = {
      'VPOS': 'vpos_pyme', 'VPOS_MPOS': 'vpos_pyme', 'GATEWAY': 'payment_gateway',
      'LINK_PAGO': 'payment_gateway', 'MPOS': 'mpos', 'LINK': 'vpos_pyme'
    };
    const templateType = templateTypeMap[quoteData.quote_type] || 'vpos_pyme';
    const _isMultiRif = quoteData.quote_type === 'VPOS_MULTIRIF';
    return {
      cliente_nombre: _isMultiRif ? (quoteData.sponsoring_bank_name || 'Banco') : (client.legal_name || client.commercial_name || client.fantasy_name || 'Cliente'),
      cliente_rif: _isMultiRif ? '' : (client.rif || ''),
      cliente_contacto: _isMultiRif ? '' : (client.contact_name || ''),
      cliente_address: _isMultiRif ? '' : (client.address || ''),
      is_multirif: _isMultiRif,
      multirif_distribution: _isMultiRif ? (quoteData.multirif_distribution || []) : [],
      sponsoring_bank_id: quoteData.sponsoring_bank_id || null,
      sponsoring_bank_name: quoteData.sponsoring_bank_name || '',
      // IDs para hidratación server-side (aislamiento de RBAC): el backend resuelve
      // los nombres autoritativos desde Mongo → Previsualizar/Exportar/Guardar idénticos.
      client_id: quoteData.client_id || null,
      integrator_id: quoteData.integrator_id || null,
      pinpad_id: quoteData.pinpad_id || null,
      sponsor_bank_id: quoteData.sponsor_bank_id || null,
      sponsor_processor_id: quoteData.sponsor_processor_id || null,
      quote_type: quoteData.quote_type,
      link_pago_variant: quoteData.link_pago_variant || 'link_pago',
      pricing_model: quoteData.pricing_model,
      cantidad_cajas: quoteData.cantidad_cajas || 1,
      quote_number: quoteNumber || '',
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
      communication_type: quoteData.communication_type || (quoteData.requires_vpn ? 'VPN' : 'NO_APLICA'),
      notes: quoteData.notes || '',
      is_production_client: isProductionClient,
      pg_setup_items: pgSetupItems.map(item => ({
        concepto: item.concepto, costo: item.costo || 0, banco: item.banco || '', observacion: item.observacion || ''
      })),
      production_items: productionItems.map(item => ({
        concepto: item.medio_pago_name,
        cantidad_cajas: parseInt(item.cantidad_cajas) || 1,
        cantidad_bancos: parseInt(item.cantidad_bancos) || 1,
        tarifa: parseFloat(item.tarifa) || 0,
        tipo_corp: findServiceTipoCorp(item.medio_pago_name)
      })),
      pg_recurring_cost: pgShowRecurringTable && pgMediosPagoCount > 0 ? {
        num_products: Math.min(pgMediosPagoCount, 11),
        rangos: getPgFullRecurringTable().map(r => ({
          rango_label: r.label,
          costo_base_total: r.base,
          precio_tope: r.tope
        }))
      } : null,
      branch_details: branchDetails.filter(b => b.store_name && b.quantity > 0),
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
  };

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
        quote_type: quoteData.quote_type || 'GATEWAY',
        client_segment: quoteData.client_segment || 'PYME',
        link_pago_variant: quoteData.link_pago_variant || 'link_pago',
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
        // Mismo payload de PDF que Previsualizar/Exportar → PDF idéntico (incluye
        // tabla de recurrentes, setup por medio de pago/banco, resumen, etc.)
        pdf_data: buildTemplatePdfData('')
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
      if (!error?.response) {
        // Sin respuesta del servidor = la petición se interrumpió/canceló
        // (p.ej. sesión expirada durante el envío). El backend pudo haberla creado.
        toast.warning('La conexión se interrumpió durante el envío. Verifique el listado: la cotización pudo haberse creado. Si no aparece, intente de nuevo.', { duration: 8000 });
        fetchData();
      } else {
        const detail = error.response?.data?.detail || error.message || 'Error desconocido';
        toast.error(`Error al crear cotización Payment Gateway: ${detail}`);
      }
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

    // Validar consistencia de sucursales: si hay branches definidas, la suma debe ser exacta
    if (branchDetails.length > 0) {
      const totalBranchBoxes = branchDetails.reduce((sum, b) => sum + (parseInt(b.quantity) || 0), 0);
      const totalEquipment = parseInt(quoteData.cantidad_cajas) || 0;
      if (totalBranchBoxes !== totalEquipment) {
        toast.error(`La suma de cajas en sucursales (${totalBranchBoxes}) no coincide con el total de equipos (${totalEquipment}). Ajuste las cantidades antes de guardar.`);
        return;
      }
    }

    // VPOS Multi-RIF: el lote global debe estar distribuido al 100% (Reel de saldos).
    if (isMultiRif) {
      const v = validateMultiRif(quoteData.multirif_distribution, quoteData.cantidad_cajas);
      if (!v.valid) {
        toast.error(v.errors[0] || `Distribución Multi-RIF incompleta (${v.assigned}/${v.total} cajas). Distribuya el 100% antes de guardar.`);
        return;
      }
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
        'MPOS': 'mpos_pyme',
        'FAST_TRACK': 'mpos_pyme',
        'GATEWAY': 'payment_gateway',
        'LINK_PAGO': 'payment_gateway',
        'LINK': 'vpos_pyme'
      };
      const templateType = templateTypeMap[quoteData.quote_type] || 'vpos_pyme';

      const pdfData = {
        cliente_nombre: isMultiRif ? (quoteData.sponsoring_bank_name || 'Banco') : (client?.legal_name || client?.commercial_name || 'Cliente'),
        cliente_rif: isMultiRif ? '' : (client?.rif || ''),
        cliente_contacto: isMultiRif ? '' : (client?.contact_name || ''),
        cliente_address: isMultiRif ? '' : (client?.address || ''),
        is_multirif: !!isMultiRif,
        multirif_distribution: isMultiRif ? (quoteData.multirif_distribution || []) : [],
        sponsoring_bank_id: quoteData.sponsoring_bank_id || null,
        sponsoring_bank_name: quoteData.sponsoring_bank_name || '',
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
        communication_type: quoteData.communication_type || (quoteData.requires_vpn ? 'VPN' : 'NO_APLICA'),
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
        client_id: quoteData.client_id || (isMultiRif ? null : quoteData.client_id),
        is_multirif: !!isMultiRif,
        multirif_distribution: isMultiRif ? (quoteData.multirif_distribution || []) : null,
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
        communication_type: quoteData.communication_type || (quoteData.requires_vpn ? 'VPN' : 'NO_APLICA'),
        production_items: productionItems.map(item => ({
          item_name: item.medio_pago_name,
          cantidad_cajas: item.cantidad_cajas || 1,
          cantidad_bancos: item.cantidad_bancos || 1,
          tarifa: item.tarifa || 0,
          total: (item.tarifa || 0) * (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1)
        })),
        // Detalle de sucursales (opcional)
        branch_details: branchDetails.filter(b => b.store_name && b.quantity > 0),
        // Implementación Patrocinada
        sponsored_implementation: !!quoteData.sponsored_implementation,
        sponsoring_bank_id: quoteData.sponsored_implementation ? (quoteData.sponsoring_bank_id || '') : '',
        sponsoring_bank_name: (quoteData.sponsored_implementation && quoteData.sponsoring_bank_id)
          ? (banks.find(b => b.bank_id === quoteData.sponsoring_bank_id)?.name || '')
          : '',
        sponsoring_processor_id: quoteData.sponsored_implementation ? (quoteData.sponsoring_processor_id || '') : '',
        sponsoring_processor_name: quoteData.sponsored_implementation ? (quoteData.sponsoring_processor_name || '') : '',
        // Cliente exento de IVA
        iva_exempt: !!quoteData.iva_exempt,
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

  // Nota iter 182: la descarga de PDF desde el menú de acciones fue eliminada
  // por descargar una versión desactualizada. El PDF oficial se obtiene ahora
  // exclusivamente desde el botón "Anexos".


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
      'LINK_PAGO': 'payment_gateway',
      'MPOS': 'mpos',
      'LINK': 'vpos_pyme'
    };
    const templateType = templateTypeMap[quoteData.quote_type] || 'vpos_pyme';
    const hasTemplate = templateAvailable[templateType]?.exists;

    // Preparar datos para el PDF (builder compartido → idéntico a Guardar/Previsualizar)
    const pdfData = buildTemplatePdfData(
      editingQuoteId ? (quotes.find(q => q.quote_id === editingQuoteId)?.quote_number || '') : ''
    );

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
      
      // Homogeneidad (Fallo 1): Exportar usa SIEMPRE el mismo motor de plantilla
      // que Previsualizar (preview-pdf-with-template) y Guardar (create-with-pdf),
      // para que las 3 salidas sean idénticas. Nunca caer al endpoint legacy.
      const endpoint = '/api/quotes/generate-pdf-with-template';
      
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
      // Builder compartido → PDF idéntico a Guardar y Exportar
      const pdfData = buildTemplatePdfData('');
      
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
  const openEmailModal = (action, quoteId, initialRecipients = []) => {
    const q = quotes.find(q => q.quote_id === quoteId);
    setEmailModalConfig({ action, quoteId, quoteName: q?.quote_number || '' });
    setEmailCustomMessage('');
    setEmailNewRecipient('');
    // Permite precargar destinatarios (ej. contactos seleccionados de la ficha del cliente).
    setEmailRecipientsList(Array.isArray(initialRecipients) ? initialRecipients : []);
    setEmailManualAttachments([]);
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
    if (emailManualAttachments.length > 0) {
      headers['x-manual-attachment-ids'] = emailManualAttachments.map(a => a.attachment_id).join(',');
    }
    return headers;
  };

  const confirmEmailAndProceed = () => {
    const { action, quoteId } = emailModalConfig;
    setEmailModalOpen(false);
    
    if (action === 'send-to-client') {
      proceedSendToClient(quoteId);
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
      // Productos digitales (Payment Gateway / Link de Pago-Tokenizador): se OMITEN
      // los modales de Multitienda, Pinpads e Impresora Fiscal, pero SÍ se conservan
      // "Datos Técnicos e Instrucciones" y "Asignación del Implementador".
      const _q = quotes.find(q => q.quote_id === quoteId);
      const _qt = (_q?.quote_type || '').toUpperCase();
      if (_qt === 'GATEWAY' || _qt === 'LINK_PAGO') {
        openDigitalImplementationWizard(quoteId, pendingAction?.exceptionHeaders || null);
      } else {
        openMultistoreDialog(quoteId, pendingAction?.exceptionHeaders || null);
      }
    } else if (action === 'deliver') {
      // Capturar los headers ANTES de cerrar el modal de email para no perder
      // los anexos manuales ni el mensaje personalizado.
      handleDeliverQuote(quoteId, pendingAction?.exceptionHeaders || null, getEmailHeaders());
    } else if (action && action.startsWith('custom:')) {
      // Custom action (override de catálogo): action="custom:<action_id>"
      const actionId = action.slice('custom:'.length);
      executeCustomAction(quoteId, actionId, emailModalConfig.actionLabel || actionId);
    }
  };

  // Ejecuta una custom action con mensaje personalizado + CCs + adjuntos del modal
  const executeCustomAction = async (quoteId, actionId, label) => {
    try {
      setActionLoading(quoteId);
      const payload = {
        custom_message: emailCustomMessage?.trim() || null,
        cc_emails: emailRecipientsList || [],
      };
      const headers = {};
      if (emailManualAttachments.length > 0) {
        headers['x-manual-attachment-ids'] = emailManualAttachments.map(a => a.attachment_id).join(',');
      }
      const res = await api.post(`/quotes/${quoteId}/custom-action/${actionId}`, payload, { headers });
      // Limpiar adjuntos: ya fueron consumidos en el backend.
      setEmailManualAttachments([]);
      toast.success(res.data?.message || `${label} ejecutada`);
    } catch (e) {
      toast.error(e.response?.data?.detail || `Error ejecutando ${label}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Enviar al cliente — Paso 1: selección de contactos de la ficha del cliente.
  // Intercepta el flujo: antes de "Personalizar Comunicación" se eligen los
  // destinatarios desde el maestro de contactos del cliente.
  const handleSendToClient = async (quoteId) => {
    const quote = quotes.find(q => q.quote_id === quoteId);
    setContactSelectQuoteId(quoteId);
    setContactSelectedEmails([]);
    setContactList([]);
    setContactSelectOpen(true);
    setContactSelectLoading(true);
    try {
      if (quote?.client_id) {
        const res = await api.get(`/clients/${quote.client_id}/consolidated-contacts`);
        const contacts = (res.data?.contacts || []).filter(c => (c.email || '').includes('@'));
        setContactList(contacts);
      }
    } catch {
      // Si la ficha no se puede leer, el modal queda vacío: el operador puede
      // continuar y capturar destinatarios manualmente en el paso siguiente.
    } finally {
      setContactSelectLoading(false);
    }
  };

  const toggleContactEmail = (email) => {
    setContactSelectedEmails((prev) =>
      prev.includes(email) ? prev.filter((e) => e !== email) : [...prev, email],
    );
  };

  // Paso 2: cerrar selección y abrir "Personalizar Comunicación" con los
  // correos seleccionados precargados en el campo de destinatarios (TO).
  const handleContactSelectContinue = () => {
    const quoteId = contactSelectQuoteId;
    setContactSelectOpen(false);
    openEmailModal('send-to-client', quoteId, contactSelectedEmails);
  };

  // Intercepta "Enviar al Cliente": para cotizaciones de tipo VPOS / MPOS /
  // VPOS_MULTIRIF generadas por el segmento/área Corporativo, si la acción
  // "Cotización Equipos Infra" está configurada y activa, muestra primero el
  // modal de Equipos de Infraestructura. Pyme/otros tipos o acción desactivada →
  // despacho directo (comportamiento estándar).
  //
  // FIX (jun 2026): antes solo se disparaba con `client_segment === 'CORP'`, por
  // lo que las cotizaciones generadas por usuarios de Corporativo cuyo cliente
  // no quedaba marcado como CORP no activaban el modal. Ahora se considera
  // Corporativo si el segmento del cliente es CORP O el creador pertenece al
  // departamento de Ventas Corporativas (origen inmutable `creator_departamento`).
  const proceedSendToClient = async (quoteId) => {
    const quote = quotes.find(q => q.quote_id === quoteId);
    const qt = (quote?.quote_type || '').toUpperCase();
    const isEligibleType = ['VPOS', 'MPOS', 'VPOS_MULTIRIF'].includes(qt);
    const seg = (quote?.client_segment || '').toUpperCase();
    const creatorDept = (quote?.creator_departamento || '').toLowerCase();
    const isCorp = seg === 'CORP' || creatorDept.includes('corporativ');
    if (isEligibleType && isCorp) {
      try {
        const res = await api.get('/other-actions/configs/cotizacion_equipos_infra');
        const cfg = res.data || {};
        const hasRecipients = (cfg.recipients || []).length > 0;
        if (cfg.exists !== false && cfg.enabled !== false && hasRecipients) {
          setEquiposInfraQuoteId(quoteId);
          setEquiposInfraOpen(true);
          return;
        }
      } catch {
        // Si la consulta falla, continúa con el envío directo (cero regresión).
      }
    }
    executeSendToClient(quoteId);
  };

  // Respuesta del modal de Equipos Infra. En ambos casos se despacha la
  // cotización; sólo si responde "Sí" se dispara la acción de infraestructura.
  const handleEquiposInfraAnswer = async (includesInfra) => {
    const quoteId = equiposInfraQuoteId;
    setEquiposInfraOpen(false);
    if (includesInfra) {
      setEquiposInfraSending(true);
      try {
        await api.post(`/quotes/${quoteId}/equipos-infra`);
      } catch (e) {
        console.error('equipos-infra dispatch error', e);
      } finally {
        setEquiposInfraSending(false);
      }
    }
    executeSendToClient(quoteId);
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
      // VPOS Multi-RIF: declarar la condición multitienda (jerarquía de 3 niveles)
      // en el payload aunque no se envíen `stores` (el backend la deriva de
      // multirif_distribution). NO se envían `stores` para no enrutarlo al
      // multistore plano y conservar project_type="multirif".
      const _sendingQuote = quotes.find(q => q.quote_id === quoteId);
      if ((_sendingQuote?.quote_type || '').toUpperCase() === 'VPOS_MULTIRIF') {
        body.is_multirif = true;
        body.is_multistore = true;
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
      // Grupo Económico y Nombre de Fantasía (campos siempre incluidos para que backend aplique defaults)
      body.economic_group = (economicGroup || '').trim();
      body.fantasy_name = (fantasyName || '').trim();
      // Instrucciones adicionales para el Implementador (HTML rich-text)
      if (implInstructions && implInstructions.trim()) {
        body.implementation_instructions = implInstructions;
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
      // Modelo de impresora fiscal (editable): la fuente de verdad es el valor del campo.
      const finalFiscalModel = (fiscalPrinterModel || fiscalPrinterFromClient || '').trim();
      if (finalFiscalModel) {
        body.fiscal_printer_model = finalFiscalModel;
      }
      // Nota de provisión de seriales por un tercero (Infraestructura/Cliente/Banco).
      // Se envía tal cual (puede contener espacios/guiones de formato intencionales).
      if (serialsProviderNote && serialsProviderNote.trim()) {
        body.serials_provider_note = serialsProviderNote;
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
    const _q = quotes.find(q => q.quote_id === quoteId);
    const _isMultiRif = (_q?.quote_type || '').toUpperCase() === 'VPOS_MULTIRIF';

    // ── Reset común del wizard de implementación ──
    setMultistoreQuoteId(quoteId);
    setMultistoreExceptionInfo(exceptionInfo);
    setMultistoreNewStore({ name: '', box_count: '' });
    setMultistoreSending(false);
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
    // Reset sub-flujo seriales por tercero
    setSerialsByOther(false);
    setSerialsProviderNote('');
    setSerialsBankModal({ open: false, processor: null });
    // Reset instrucciones y grupo/fantasía
    setImplInstructions('');
    setImplInstructionsLen(0);
    setMultistoreDialogOpen(true);

    if (_isMultiRif) {
      // VPOS Multi-RIF: la condición multitienda es intrínseca (jerarquía
      // Global→RIF→Sucursal que el backend construye desde multirif_distribution).
      // Se OMITE ÚNICAMENTE el modal "¿Es Multitienda?" (asignando TRUE por debajo),
      // pero se MANTIENEN obligatorios los pasos siguientes del wizard:
      // Pinpads → Impresora Fiscal → Servi → Confirmación.
      setProjectTypeImpl('vpos_mpos');
      setIsMultistore(true);
      setMultistoreStores([]);
      setMultistorePhase('pinpad_question');
      return;
    }

    // ── Flujo estándar (no Multi-RIF) ──
    setIsMultistore(null);
    setProjectTypeImpl(null);
    // Auto-inferir project_type desde la cotización (elimina paso manual).
    // VPOS → vpos_mpos (búsqueda por RIF);  GATEWAY → payment_gateway;  MPOS/FAST_TRACK → pos_fast_track
    const qt = (_q?.quote_type || '').toUpperCase();
    let inferred = 'pos_fast_track';
    if (qt === 'VPOS') inferred = 'vpos_mpos';
    else if (qt === 'GATEWAY' || qt === 'LINK') inferred = 'payment_gateway';
    else if (qt === 'MPOS' || qt === 'FAST_TRACK') inferred = 'pos_fast_track';
    // Ejecutamos la selección a continuación. Pasamos `quoteId` EXPLÍCITO para
    // evitar el stale closure de `multistoreQuoteId` (setState asíncrono no
    // está committed cuando dispara el setTimeout). Fix iter37.
    setTimeout(() => { handleProjectTypeSelect(inferred, quoteId); }, 0);
  };

  // ── Flujo optimizado para productos DIGITALES (Payment Gateway / Link de Pago-Tokenizador) ──
  // Omite Multitienda, Pinpads e Impresora Fiscal (no aplican a e-commerce/enlaces),
  // pero CONSERVA "Datos Técnicos e Instrucciones" (consolidated_data) y
  // "Asignación del Implementador" (confirm_implementer). Salta directo a esos pasos.
  const openDigitalImplementationWizard = async (quoteId, exceptionInfo) => {
    const _q = quotes.find(q => q.quote_id === quoteId);
    // Reset del wizard (idéntico a openMultistoreDialog).
    setMultistoreQuoteId(quoteId);
    setMultistoreExceptionInfo(exceptionInfo);
    setMultistoreNewStore({ name: '', box_count: '' });
    setMultistoreSending(false);
    setEquipmentList([]);
    setEquipmentAvailable({ quote_equipment: [], rif_equipment: [] });
    setEquipmentSelected({});
    setPymeServerName('');
    setPymeServerCustom('');
    setPymeNeedsPinpads(null);
    setPymePinpadModels([]);
    setPymePinpadSelectedModel('');
    setPymePinpadSerials([]);
    setPymePinpadSerialsSelected({});
    setSerialsByOther(false);
    setSerialsProviderNote('');
    setSerialsBankModal({ open: false, processor: null });
    setImplInstructions('');
    setImplInstructionsLen(0);
    // Producto digital: sin hardware ni multitienda.
    setProjectTypeImpl('payment_gateway');
    setIsMultistore(false);
    setMultistoreStores([]);
    // Precargar Grupo Económico y Nombre de Fantasía desde la ficha del cliente
    // (editables en el modal "Datos Técnicos e Instrucciones").
    try {
      if (_q?.client_id) {
        const res = await api.get(`/clients/${_q.client_id}`);
        const c = res.data || {};
        setEconomicGroup((c.grupo_economico || '').toString());
        setFantasyName((c.fantasy_name || '').toString());
      } else {
        setEconomicGroup('');
        setFantasyName('');
      }
    } catch {
      setEconomicGroup('');
      setFantasyName('');
    }
    // Abrir el wizard directamente en "Datos Técnicos e Instrucciones".
    setMultistorePhase('consolidated_data');
    setMultistoreDialogOpen(true);
  };

  const handleProjectTypeSelect = async (type, overrideQuoteId) => {
    // FIX iter37: el `overrideQuoteId` toma precedencia para evitar leer
    // `multistoreQuoteId` del closure stale (puede ser null durante el primer
    // ciclo si openMultistoreDialog acaba de disparar el setTimeout).
    const effectiveQuoteId = overrideQuoteId || multistoreQuoteId;
    setProjectTypeImpl(type);

    // ── PRIMER MODAL: Multitienda ──
    // Independientemente de PYME/no-PYME, el flujo arranca SIEMPRE con la
    // validación de Multitienda. El usuario debe ratificar (o cambiar) la
    // condición de multi-sucursal antes de continuar a Pinpads/Fiscal.
    if (type === 'payment_gateway') {
      // Payment Gateway no requiere precarga de equipos pero también pasa por multistore.
      await advanceToMultistorePhase(effectiveQuoteId);
    } else {
      // POS o VPOS/MPOS: auto-cargar equipos en background y mostrar multistore.
      setEquipmentLoading(true);
      try {
        const res = await api.get(`/quotes/${effectiveQuoteId}/equipment-for-implementation?project_type=${type}`);
        setEquipmentAvailable(res.data);
        const sel = {};
        (res.data.quote_equipment || []).forEach(eq => { sel[eq.equipo_id] = true; });
        setEquipmentSelected(sel);
        setEquipmentList(res.data.quote_equipment || []);
      } catch (err) {
        // Pre-carga en background: la fase "Equipos" del wizard fue eliminada
        // (Feb 2026). Si el endpoint falla, seguimos el flujo con listas vacías;
        // no debemos emitir un toast que confunda al usuario.
        console.warn('[send-to-impl] precarga de equipos falló (no crítico):', err);
        setEquipmentAvailable({ quote_equipment: [], rif_equipment: [] });
      } finally {
        setEquipmentLoading(false);
      }
      await advanceToMultistorePhase(effectiveQuoteId);
    }
  };

  // ── Impresora Fiscal: posicionada después de Pinpad y antes del consolidated/multistore ──
  const goToFiscalPrinterPhase = async () => {
    // Reset explícito de los states para evitar arrastrar valores del wizard anterior.
    setFiscalPrinterFromClient('');
    setFiscalPrinterModel('');
    try {
      const quote = quotes.find(q => q.quote_id === multistoreQuoteId);
      if (quote?.client_id) {
        const c = await api.get(`/clients/${quote.client_id}`);
        // Forzar lectura del campo del cliente. Si está registrado, precargarlo
        // como informativo; si está vacío, el modal exigirá input al usuario.
        const existing = (c.data?.modelo_impresora_fiscal || '').toString().trim();
        if (existing) {
          setFiscalPrinterFromClient(existing);
          setFiscalPrinterModel(existing);
        }
      }
    } catch {
      // Mantiene strings vacíos → modal solicitará input.
    }
    setMultistorePhase('fiscal_printer');
  };

  const handleFiscalPrinterContinue = async () => {
    // El campo es EDITABLE y se precarga con el valor de la ficha. La fuente de
    // verdad es lo que quedó en `fiscalPrinterModel` (editado o precargado).
    const finalModel = (fiscalPrinterModel || '').trim();
    if (!finalModel) {
      toast.error('Indique el modelo de impresora fiscal');
      return;
    }
    // Si el modelo cambió respecto al registrado en la ficha (o no existía), persistirlo.
    if (finalModel !== (fiscalPrinterFromClient || '').trim()) {
      try {
        const quote = quotes.find(q => q.quote_id === multistoreQuoteId);
        if (quote?.client_id) {
          await api.patch(`/clients/${quote.client_id}`, { modelo_impresora_fiscal: finalModel });
        }
      } catch {
        // No bloquea el flujo si la actualización del cliente falla
      }
    }
    // Avanzar al siguiente paso del wizard. HOMOLOGACIÓN (V2): la secuencia es
    // IDÉNTICA para PYME y Corp — sin diferenciación por segmento. Tras la
    // secuencia física (Multitienda/Pinpad/Fiscal) SIEMPRE se muestran
    // "Datos Técnicos e Instrucciones" (consolidated_data) y luego "Implementador"
    // (confirm_implementer), independientemente del segmento del creador.
    const quote = quotes.find(q => q.quote_id === multistoreQuoteId);
    // Precargar Grupo Económico y Nombre de Fantasía desde la ficha del cliente
    // (editables en el modal consolidated_data antes de enviar la ficha técnica).
    try {
      if (quote?.client_id) {
        const res = await api.get(`/clients/${quote.client_id}`);
        const c = res.data || {};
        setEconomicGroup((c.grupo_economico || '').toString());
        setFantasyName((c.fantasy_name || '').toString());
      } else {
        setEconomicGroup('');
        setFantasyName('');
      }
    } catch {
      // No bloquea el flujo si la ficha no se puede leer
    }
    setMultistorePhase('consolidated_data');
  };

  const advanceToMultistorePhase = async (overrideQuoteId) => {
    // FIX iter37: aceptar `overrideQuoteId` explícito para evitar leer el state
    // `multistoreQuoteId` que puede no estar committed durante el primer ciclo.
    const effectiveQuoteId = overrideQuoteId || multistoreQuoteId;
    // Build final equipment list from selections
    const allEquip = [...(equipmentAvailable.quote_equipment || []), ...(equipmentAvailable.rif_equipment || [])];
    const selected = allEquip.filter(eq => equipmentSelected[eq.equipo_id]);
    setEquipmentList(selected);

    // PRIMER MODAL OBLIGATORIO (Multitienda) — válido para PYME y no-PYME.
    // Antes el flujo PYME saltaba este paso; ahora también pasa por aquí
    // para que el operador pueda ratificar o cambiar la condición Multitienda
    // antes de continuar a Pinpads y Fiscal.

    // FIX Iter37 (feb 2026): para detectar la distribución previa de forma
    // SÍNCRONA y reactiva, hacemos un GET fresco de la cotización en vez de
    // leer del state `quotes` (que podía estar desactualizado y forzaba al
    // usuario a pulsar "Volver" para refrescar). Esto garantiza que la
    // grilla heredada se cargue al primer intento.
    let quote = quotes.find(q => q.quote_id === effectiveQuoteId);
    try {
      const fresh = await api.get(`/quotes/${effectiveQuoteId}`);
      if (fresh?.data) quote = fresh.data;
    } catch (err) {
      console.warn('[multistore] no se pudo refrescar cotización, usando caché:', err);
    }

    // Pre-check branch data → si hay distribución guardada, fase 'inherited';
    // si no, fase 'ask' (pregunta directa Sí/No).
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

  const handlePymeServerContinue = async () => {
    const server = pymeServerName === 'Otro' ? pymeServerCustom.trim() : pymeServerName;
    if (!server) {
      toast.error('Seleccione o ingrese el servidor de instalación');
      return;
    }
    // Precargar Grupo Económico y Nombre de Fantasía desde la ficha del cliente.
    // Ambos quedan EDITABLES en el modal (el operador puede corregirlos antes de continuar).
    try {
      const quote = quotes.find(q => q.quote_id === multistoreQuoteId);
      if (quote?.client_id) {
        const res = await api.get(`/clients/${quote.client_id}`);
        const c = res.data || {};
        setEconomicGroup((c.grupo_economico || '').toString());
        setFantasyName((c.fantasy_name || '').toString());
      }
    } catch {
      // No bloquea el flujo si la ficha no se puede leer
    }
    setMultistorePhase('economic_data');
  };

  const handleEconomicDataContinue = async () => {
    // Avanzar a Modal 2: Confirmación de Implementador heredado de la ficha de cliente
    setMultistorePhase('confirm_implementer');
    const quote = quotes.find(q => q.quote_id === multistoreQuoteId);
    if (!quote?.client_id) {
      setConfirmImplementerInfo({ loading: false, name: '', user_id: '' });
      return;
    }
    setConfirmImplementerInfo({ loading: true, name: '', user_id: '' });
    try {
      const res = await api.get(`/clients/${quote.client_id}`);
      const c = res.data || {};
      setConfirmImplementerInfo({
        loading: false,
        name: c.implementer_name || '',
        user_id: c.implementer_user_id || '',
      });
    } catch {
      setConfirmImplementerInfo({ loading: false, name: '', user_id: '' });
    }
  };

  const handleConfirmImplementerAdvance = () => {
    // Paso 3 (final): confirmar asignación y enviar a implementación
    const pinpadSerials = pymePinpadSerials.filter(s => pymePinpadSerialsSelected[s.serial]);
    const stores = isMultistore ? multistoreStores : null;
    setMultistoreDialogOpen(false);
    handleSendToImplementation(multistoreQuoteId, multistoreExceptionInfo, stores);
  };

  const handlePymePinpadAnswer = async (needsPinpads) => {
    // Salir del sub-flujo "suministrado por otro" al elegir Sí/No explícitos.
    setSerialsByOther(false);
    setSerialsProviderNote('');
    setSerialsBankModal({ open: false, processor: null });
    setPymeNeedsPinpads(needsPinpads);
    if (!needsPinpads) {
      // No pinpads → avanzar a Impresora Fiscal (luego sigue al modal consolidado)
      goToFiscalPrinterPhase();
    } else {
      // Sí pinpads: cargar modelos disponibles
      setMultistorePhase('pinpad_selection');
      setPymePinpadLoading(true);
      try {
        const res = await api.get(`/quotes/${multistoreQuoteId}/pinpad-models`);
        setPymePinpadModels(res.data.models || []);
        // ── Precarga automática de seriales PREASIGNADOS ──
        // Si la cotización tiene seriales preasignados en una fase previa,
        // auto-seleccionamos el modelo correspondiente (item_id) para que
        // el usuario vea de inmediato los seriales reservados al cliente,
        // sin tener que recorrer todo el catálogo manualmente.
        try {
          const pre = await api.get(`/quotes/${multistoreQuoteId}/preassigned-serials`);
          const preassignedItemId = pre.data?.assignments?.[0]?.item_id;
          if (preassignedItemId) {
            await handlePymePinpadModelSelect(preassignedItemId);
          }
        } catch {
          // Si no hay preasignación o falla, el usuario selecciona modelo manualmente.
        }
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
    // Tras confirmar pinpads → Impresora Fiscal → modal consolidado
    goToFiscalPrinterPhase();
  };

  // ── Sub-flujo: Seriales suministrados por un tercero ──
  // Avanza el flujo sin seriales físicos, guardando la nota descriptiva que
  // se inyectará en la Ficha Técnica del proyecto.
  const proceedSerialsByOther = (note) => {
    setSerialsProviderNote(note);
    setPymeNeedsPinpads(false);
    // Limpiar cualquier serial seleccionado previamente.
    setPymePinpadSerials([]);
    setPymePinpadSerialsSelected({});
    setSerialsBankModal({ open: false, processor: null });
    goToFiscalPrinterPhase();
  };

  const handleSerialsProvider = (kind) => {
    if (kind === 'infra') {
      proceedSerialsByOther('Los Seriales de los Equipos serán suplidos por Infraestructura');
    } else if (kind === 'client') {
      proceedSerialsByOther('Los Seriales de los Equipos serán suplidos por el Cliente');
    } else if (kind === 'bank') {
      setSerialsBankModal({ open: true, processor: null });
    }
  };

  // Selección de banco (nivel 1). Si es Procesador → abre nivel 2 (bancos vinculados).
  const handleSerialsBankSelect = (bank) => {
    if (bank.type === 'Procesador') {
      setSerialsBankModal({ open: true, processor: bank });
    } else {
      proceedSerialsByOther(`Los Seriales de los Equipos serán suplidos por ${bank.name}`);
    }
  };

  // Selección del banco final vinculado a un Procesador (nivel 2).
  const handleSerialsLinkedBankSelect = (proc, bank) => {
    proceedSerialsByOther(`Los Seriales de los Equipos serán suplidos por ${proc.name} - ${bank.name} - `);
  };

  // Avanzar desde consolidado: cargar implementer heredado del cliente → fase confirm
  const handleConsolidatedContinue = async () => {
    const effectiveServer = pymeServerName === 'Otro' ? pymeServerCustom.trim() : pymeServerName;
    if (!effectiveServer) {
      toast.error('Seleccione o ingrese el servidor de instalación');
      return;
    }
    // Avanzar a Modal 3: Confirmación de Implementador heredado de la ficha de cliente
    setMultistorePhase('confirm_implementer');
    const quote = quotes.find(q => q.quote_id === multistoreQuoteId);
    if (!quote?.client_id) {
      setConfirmImplementerInfo({ loading: false, name: '', user_id: '' });
      return;
    }
    setConfirmImplementerInfo({ loading: true, name: '', user_id: '' });
    try {
      const res = await api.get(`/clients/${quote.client_id}`);
      const c = res.data || {};
      setConfirmImplementerInfo({
        loading: false,
        name: c.implementer_name || '',
        user_id: c.implementer_user_id || '',
      });
    } catch {
      setConfirmImplementerInfo({ loading: false, name: '', user_id: '' });
    }
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
      // Escenario C: No es multitienda — avanzar al Paso 1 (pinpad question)
      setIsMultistore(false);
      setMultistorePhase('pinpad_question');
    }
  };

  // Confirmar herencia de datos previos (Escenario A - Sí)
  const confirmInheritedStores = async () => {
    // Bloqueo estricto de balance: la sumatoria por sucursal debe coincidir
    // exactamente con la cantidad inicial del proyecto antes de avanzar.
    const totalCajas = getMultistoreTotalCajas();
    if (multistoreAssignedBoxes !== totalCajas) {
      toast.error(`No se puede continuar: La cantidad de cajas distribuidas (${multistoreAssignedBoxes}) no coincide con la cantidad inicial asignada al proyecto (${totalCajas}). Por favor, ajuste el balance de hardware antes de enviar a implementación.`);
      return;
    }
    setIsMultistore(true);
    setMultistorePhase('pinpad_question');
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
      toast.error(`No se puede continuar: La cantidad de cajas distribuidas (${multistoreAssignedBoxes}) no coincide con la cantidad inicial asignada al proyecto (${totalCajas}). Por favor, ajuste el balance de hardware antes de enviar a implementación.`);
      return;
    }
    // Avanzar al Paso 1 (Pinpad question), no enviar aún.
    setMultistorePhase('pinpad_question');
  };

  // Modificar cotización: PRIMERO pregunta el modo (nueva versión vs. mantener original)
  const handleEditQuote = (quote) => {
    setModifyChoiceQuote(quote);
    setModifyChoiceOpen(true);
  };

  // Tras elegir el modo en el ModifyQuoteChoiceDialog, abre el editor real.
  const handleEditModeChosen = async (mode) => {
    setEditMode(mode);
    const quote = modifyChoiceQuote;
    setModifyChoiceOpen(false);
    if (!quote) return;
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
      window.__implEditJustification = justification;
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

    // Función auxiliar para detectar si un concepto debe heredar bancos del header
    // (Solo "Suscripción PDV/Banco" - sin la palabra "Configuración" antes)
    const hasInheritBancos = (itemName) => {
      const lower = (itemName || '').toLowerCase();
      // 1) "Suscripción PDV/Banco" base — excluye "Configuración Medio de Pago / Banco..."
      if (lower.startsWith('suscripción pdv/banco') || lower.startsWith('suscripcion pdv/banco')) {
        return true;
      }
      // 2) "Derecho de uso de plataforma MServer por PDV / Banco" (recurrente básico)
      if (lower.startsWith('derecho de uso de plataforma mserver por pdv / banco') ||
          lower.startsWith('derecho de uso de plataforma mserver por pdv/banco')) {
        return true;
      }
      return false;
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
      const isInherit = defaultConcept?.inheritBancos || hasInheritBancos(itemName);
      const autoTariffCfg = defaultConcept?.autoTariff || null;
      
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
        inheritBancos: isInherit,
        autoTariff: autoTariffCfg,
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
      link_pago_variant: quote.link_pago_variant || 'link_pago',
      client_id: quote.client_id || '',
      client_segment: (quote.client_segment || 'PYME').toUpperCase(),
      pricing_model: quote.pricing_model || 'conventional',
      cantidad_cajas: quote.cantidad_cajas || 1,
      cantidad_bancos: quote.cantidad_bancos || 1,
      integrator_id: quote.integrator_id || '',
      integrator_name: quote.integrator_id === 'sin_integrador'
        ? 'sin_integrador'
        : (integrators.find(i => i.integrator_id === quote.integrator_id)?.name || ''),
      integrator_app_name: quote.integrator_app_name || '',
      pinpad_id: quote.pinpad_id || '',
      sponsor_bank_id: quote.sponsor_bank_id || '',
      requires_pinpad_config: quote.requires_pinpad_config !== false,
      requires_vpn: quote.requires_vpn !== false,
      communication_type: quote.communication_type || (quote.requires_vpn ? 'VPN' : 'NO_APLICA'),
      setup_items: setupItems,
      recurring_basic_items: recurringBasicItems,
      recurring_other_items: recurringOtherItems,
      additional_items: additionalItems,
      descuento: quote.descuento || 0,
      descuento_setup: quote.descuento_setup || 0,
      descuento_recurrente: quote.descuento_recurrente || 0,
      notes: quote.notes || '',
      sponsored_implementation: !!quote.sponsored_implementation,
      sponsoring_bank_id: quote.sponsoring_bank_id || '',
      sponsoring_bank_name: quote.sponsoring_bank_name || '',
      sponsoring_processor_id: quote.sponsoring_processor_id || '',
      sponsoring_processor_name: quote.sponsoring_processor_name || '',
      iva_exempt: !!quote.iva_exempt,
    });
    
    // Load PG data if it's a Payment Gateway / Link de Pago quote
    if (quote.quote_type === 'GATEWAY' || quote.quote_type === 'LINK_PAGO') {
      // Re-etiquetar el concepto base (Persona Jurídica / "Costo Base") como fixed.
      // El flag `fixed` se descarta al guardar; sin restaurarlo, al modificar se
      // contaría como un medio de pago extra e inflaría la tabla de recurrentes (+1 producto).
      const restoredSetup = (quote.pg_setup_items || []).map(item => {
        const isBase = item.observacion === 'Costo Base' ||
          (item.concepto || '').toLowerCase().includes('persona jur');
        return isBase ? { ...item, fixed: true } : item;
      });
      setPgSetupItems(restoredSetup);
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
      // Primero duplicar la cotización original (modo elegido por el usuario)
      const duplicateResponse = await api.post(
        `/quotes/${editingQuoteId}/duplicate`,
        null,
        { params: { mode: editMode } },
      );
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
        client_segment: quoteData.client_segment,
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
        communication_type: quoteData.communication_type || (quoteData.requires_vpn ? 'VPN' : 'NO_APLICA'),
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
        })),
        // Implementación Patrocinada
        sponsored_implementation: !!quoteData.sponsored_implementation,
        sponsoring_bank_id: quoteData.sponsored_implementation ? (quoteData.sponsoring_bank_id || '') : '',
        sponsoring_bank_name: (quoteData.sponsored_implementation && quoteData.sponsoring_bank_id)
          ? (banks.find(b => b.bank_id === quoteData.sponsoring_bank_id)?.name || '')
          : '',
        sponsoring_processor_id: quoteData.sponsored_implementation ? (quoteData.sponsoring_processor_id || '') : '',
        sponsoring_processor_name: quoteData.sponsored_implementation ? (quoteData.sponsoring_processor_name || '') : '',
        // Cliente exento de IVA
        iva_exempt: !!quoteData.iva_exempt,
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
      integrator_name: '',
      integrator_app_name: '',
      pinpad_id: '',
      sponsor_bank_id: '',
      requires_pinpad_config: true,
      requires_vpn: false,
      communication_type: 'NO_APLICA',
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
      description: 'Para registrar la facturación, debe cargar el documento fiscal (Factura o Proforma). Puede adjuntar MÁS DE UN archivo si el caso requiere fraccionamiento o soporte documental extenso. Todos se guardarán como anexos independientes.',
      category: 'Factura',
      acceptMultiple: true,
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

  // Entregar cotización — abre dialog correspondiente según categoría.
  // emailHeaders: contiene x-manual-attachment-ids, x-custom-message y x-additional-recipients.
  const handleDeliverQuote = async (quoteId, exceptionInfo, emailHeaders = null) => {
    const quote = quotes.find(q => q.quote_id === quoteId);
    const isRepairQuote = quote?.quote_category === 'repair';
    setDeliveryQuoteId(quoteId);
    setDeliveryExceptionInfo(exceptionInfo || null);
    setDeliveryEmailHeaders(emailHeaders || null);
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
  
  // Detectar si es cotización Payment Gateway (incluye Link de Pago) o MPOS
  const isPaymentGateway = quoteData.quote_type === 'GATEWAY' || quoteData.quote_type === 'LINK_PAGO';
  const isMultiRif = quoteData.quote_type === 'VPOS_MULTIRIF';
  const isVPOS = quoteData.quote_type === 'VPOS' || isMultiRif;
  const isMPOS = quoteData.quote_type === 'MPOS' || quoteData.quote_type === 'FAST_TRACK';
  const isFastTrackType = quoteData.quote_type === 'FAST_TRACK';
  const isMegaSoftSponsor = selectedSponsorBank?.name?.toLowerCase().includes('mega soft') || selectedSponsorBank?.name?.toLowerCase().includes('megasoft');
  
  // Validación completa incluyendo nuevos campos obligatorios
  // En modo edición, los campos de integración son opcionales ya que pueden no haber sido configurados originalmente
  const isHeaderCompleteBase = isMultiRif
    ? (quoteData.quote_type &&
       quoteData.sponsoring_bank_id &&  // Multi-RIF: el banco (adquirencia) reemplaza al cliente
       quoteData.pricing_model &&
       (quoteData.cantidad_cajas >= 1 || quoteData.cantidad_cajas === '') &&
       (isEditing || quoteData.integrator_id))
    : isPaymentGateway 
    ? (quoteData.quote_type && quoteData.client_id && quoteData.integrator_id)
    : (quoteData.quote_type && 
       quoteData.client_id && 
       quoteData.pricing_model && 
       (quoteData.cantidad_cajas >= 1 || quoteData.cantidad_cajas === '') &&
       (isEditing || quoteData.integrator_id));
  // Si Implementación Patrocinada = Sí, el banco es obligatorio para considerar el header completo.
  const isSponsorshipValid = !quoteData.sponsored_implementation || !!quoteData.sponsoring_bank_id;
  const isHeaderComplete = isHeaderCompleteBase && isSponsorshipValid;
  
  // En modo edición, siempre mostrar los items si existen
  const canShowItems = isEditing 
    ? (quoteData.quote_type && (quoteData.client_id || isMultiRif) && quoteData.pricing_model)
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
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />

      <main className="flex-1 relative" data-testid="quotes-page">
        {/* Iter49: accent gradient bar — continuidad visual con el Centro de Mensajes */}
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-indigo-600 via-violet-600 to-fuchsia-600 z-10" />

        <div className="max-w-7xl mx-auto p-8">
          <div className="flex justify-between items-start mb-6">
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-slate-900 font-manrope">Cotizaciones</h1>
              <p className="text-sm text-slate-500 mt-1">Genere cotizaciones profesionales para sus clientes</p>
            </div>
            {isAdmin && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setBundleModalOpen(true)}
                data-testid="quotes-bundle-migration-btn"
                className="border-slate-200 text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                title="Exportar / Importar cotizaciones, histórico y proyectos (solo administradores)"
              >
                <Database size={14} className="mr-1.5" />
                Migración BD
              </Button>
            )}
          </div>

          {/* Iter49: KPI cards — computados del array de cotizaciones, no requiere backend */}
          <QuotesKpiCards
            quotes={rbacFilteredQuotes}
            filters={{ filterClient, filterStatus, filterCategory, filterSegment, filterDateFrom, filterDateTo }}
          />

          {/* Botones de Nueva Cotización — Visibilidad por Permisos Especiales */}
          <NewQuoteButtons
            rbac={rbac}
            onOpenImpl={(segment) => openWizard(segment)}
            onOpenEquipment={(segment) => { setEquipmentWizardMode('equipment'); setEquipmentWizardSegment(segment || 'PYME'); setEquipmentWizardOpen(true); }}
            onOpenRepair={() => { setEquipmentWizardMode('repair'); setEquipmentWizardSegment('PYME'); setEquipmentWizardOpen(true); }}
          />

          {/* Filtros Rápidos */}
          <QuoteFilters
            clients={clientsWithActiveQuotes}
            filterClient={filterClient} setFilterClient={setFilterClient}
            filterStatus={filterStatus} setFilterStatus={setFilterStatus}
            filterCategory={filterCategory} setFilterCategory={setFilterCategory}
            filterSegment={filterSegment} setFilterSegment={setFilterSegment}
            filterDateFrom={filterDateFrom} setFilterDateFrom={setFilterDateFrom}
            filterDateTo={filterDateTo} setFilterDateTo={setFilterDateTo}
          />

          {/* Widget de Cotizaciones Irregulares */}
          {irregularCount > 0 && (
            <div className="mb-6 flex items-center gap-4 bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-xl px-5 py-4 shadow-sm"
              data-testid="irregular-widget">
              <div className="relative shrink-0">
                <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 text-white flex items-center justify-center font-bold text-lg shadow-md">
                  {irregularCount}
                </div>
                <span className="absolute -top-0.5 -right-0.5 w-3 h-3 rounded-full bg-rose-500 ring-2 ring-white animate-pulse" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-bold text-amber-900">Cotizaciones en Estado Irregular</p>
                <p className="text-xs text-amber-700">Tienen pasos saltados pendientes de regularización</p>
              </div>
              {currentUser?.role === 'admin' && (
                <Button
                  size="sm"
                  className="bg-amber-500 hover:bg-amber-600 text-white shadow-sm font-semibold"
                  onClick={() => setRegularizeBatchOpen(true)}
                  data-testid="regularize-batch-btn"
                >
                  Regularizar masivo
                </Button>
              )}
            </div>
          )}

          {/* Panel de Gestión Único - Todas las Cotizaciones (filtradas por RBAC) */}
          <QuotesTable
            quotes={rbacFilteredQuotes}
            clients={clients}
            actionOverrides={actionOverrides}
            customActions={customActions}
            currentUserId={currentUser?.user_id || ''}
            currentUserEmail={currentUser?.email || ''}
            currentUserCargo={currentUser?.cargo || ''}
            currentUserRole={currentUser?.role || ''}
            onCustomAction={(quoteId, actionId, label) => {
              // Pasa por modal de Personalización (estándar) en lugar de window.confirm
              const q = quotes.find((qq) => qq.quote_id === quoteId);
              setEmailModalConfig({
                action: `custom:${actionId}`,
                actionLabel: label,
                quoteId,
                quoteName: q?.quote_number || '',
              });
              setEmailCustomMessage('');
              setEmailNewRecipient('');
              setEmailRecipientsList([]);
              setEmailModalOpen(true);
            }}
            filterClient={filterClient}
            filterStatus={filterStatus}
            filterCategory={filterCategory}
            filterSegment={filterSegment}
            filterDateFrom={filterDateFrom}
            filterDateTo={filterDateTo}
            actionLoading={actionLoading}
            canEdit={canEdit || rbac.isOpsReadonly}
            opsReadonly={rbac.isOpsReadonly}
            highlightedQuoteNumber={highlightedQuote}
            onOpenAnexos={(quote) => {
              setAnexosQuoteId(quote.quote_id);
              setAnexosQuoteNumber(quote.quote_number);
              setAnexosOpen(true);
            }}
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
            clearFilters={clearFilters}
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
            isPaymentGateway, isVPOS, isMPOS, isFastTrackType, isMegaSoftSponsor, isMultiRif,
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
            duplicateRecurringBasicItem,
            getQuoteTypeName, initPgSetup,
            pgFullRecurringTable, updateSetupItem, updateRecurringBasicItem,
            updateRecurringOtherItem, updateAdditionalItem, updatePgSetupItem,
            isLoadingEdit, editingQuoteId, currentUser,
          }} />

          {/* Modales secundarios (componente extraído) */}
          <QuoteModals ctx={{
            pdfPreviewOpen, setPdfPreviewOpen, pdfPreviewUrl, setPdfPreviewUrl, pdfPreviewLoading,
            equipmentWizardOpen, setEquipmentWizardOpen, equipmentWizardMode, setEquipmentWizardMode, equipmentWizardSegment,
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
            emailManualAttachments, setEmailManualAttachments,
            addEmailRecipient, removeEmailRecipient, confirmEmailAndProceed,
            contactSelectOpen, setContactSelectOpen, contactList, contactSelectLoading,
            contactSelectedEmails, toggleContactEmail, handleContactSelectContinue,
            bitacoraFlujoOpen, setBitacoraFlujoOpen, bitacoraFlujoQuoteNumber,
            bitacoraFlujoEntries, bitacoraFlujoLoading,
            deliveryDialogOpen, setDeliveryDialogOpen, deliveryQuoteId, deliveryExceptionInfo, deliveryEmailHeaders,
            repairDeliveryDialogOpen, setRepairDeliveryDialogOpen,
            preassignModal, setPreassignModal,
            multistoreDialogOpen, setMultistoreDialogOpen, multistoreSending,
            multistorePhase, setMultistorePhase, multistoreStores, setMultistoreStores,
            multistoreNewStore, setMultistoreNewStore, isMultistore, setIsMultistore,
            multistoreAssignedBoxes, confirmMultistore, addMultistoreStore, removeMultistoreStore,
            getMultistoreTotalCajas, getMultistoreQuote, confirmInheritedStores,
            handleProjectTypeSelect, advanceToMultistorePhase, modifyInheritedStores, handleMultistoreAnswer,
            pymeServerName, setPymeServerName, pymeServerCustom, setPymeServerCustom,
            economicGroup, setEconomicGroup, fantasyName, setFantasyName, handleEconomicDataContinue,
            confirmImplementerInfo, handleConfirmImplementerAdvance,
            implInstructions, setImplInstructions, implInstructionsLen, setImplInstructionsLen, handleConsolidatedContinue,
            pymeNeedsPinpads, setPymeNeedsPinpads,
            pymePinpadModels, pymePinpadSelectedModel,
            pymePinpadSerials, pymePinpadSerialsSelected, setPymePinpadSerialsSelected,
            pymePinpadLoading, handlePymeServerContinue, handlePymePinpadAnswer,
            handlePymePinpadModelSelect, handlePymePinpadConfirm,
            // Sub-flujo: seriales suministrados por un tercero
            banks,
            serialsByOther, setSerialsByOther, serialsProviderNote,
            serialsBankModal, setSerialsBankModal,
            handleSerialsProvider, handleSerialsBankSelect, handleSerialsLinkedBankSelect,
            // Fiscal Printer phase
            fiscalPrinterFromClient, fiscalPrinterModel, setFiscalPrinterModel, handleFiscalPrinterContinue,
            projectTypeImpl, equipmentList, equipmentAvailable, equipmentLoading,
            equipmentSelected, setEquipmentSelected,
          }} />

          {/* Modal interceptor: Equipos de Infraestructura (solo clientes Corp) */}
          <AlertDialog open={equiposInfraOpen} onOpenChange={(v) => { if (!v) setEquiposInfraOpen(false); }}>
            <AlertDialogContent data-testid="equipos-infra-modal">
              <AlertDialogHeader>
                <AlertDialogTitle>Equipos de Infraestructura</AlertDialogTitle>
                <AlertDialogDescription>
                  ¿Esta cotización incluye <strong>Equipos de Infraestructura</strong>?
                  <br />
                  Al confirmar, se enviará la cotización al cliente. Si respondes "Sí", además se
                  notificará al área de infraestructura según la configuración.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel
                  onClick={() => handleEquiposInfraAnswer(false)}
                  disabled={equiposInfraSending}
                  data-testid="equipos-infra-no"
                >
                  No, enviar normal
                </AlertDialogCancel>
                <AlertDialogAction
                  onClick={() => handleEquiposInfraAnswer(true)}
                  disabled={equiposInfraSending}
                  className="bg-blue-600 hover:bg-blue-700"
                  data-testid="equipos-infra-yes"
                >
                  Sí, incluye Equipos Infra
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>


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
            editMode={editMode}
            onSaved={fetchData}
          />

          {/* Modal de elección al ejecutar Modificar Cotización */}
          <ModifyQuoteChoiceDialog
            open={modifyChoiceOpen}
            onClose={() => { setModifyChoiceOpen(false); setModifyChoiceQuote(null); }}
            quote={modifyChoiceQuote}
            onChoose={handleEditModeChosen}
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

          {/* Migración de Cotizaciones (Admin) */}
          {bundleModalOpen && (
            <QuotesBundleMigrationModal
              open={bundleModalOpen}
              onClose={() => setBundleModalOpen(false)}
            />
          )}

          {/* Regularización Masiva Retroactiva (Admin-only) */}
          <Dialog open={regularizeBatchOpen} onOpenChange={(o) => { setRegularizeBatchOpen(o); if (!o) setRegularizeResult(null); }}>
            <DialogContent className="max-w-2xl max-h-[85vh] overflow-hidden flex flex-col" data-testid="regularize-batch-dialog">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2 text-orange-700">
                  Regularización Masiva Retroactiva
                </DialogTitle>
                <p className="text-xs text-slate-500 mt-1">
                  Completa el <code>status_history</code> faltante con timestamps reales y aplica la auto-regularización para cotizaciones que ya alcanzaron el estado-resultado de sus excepciones.
                </p>
              </DialogHeader>

              {!regularizeResult ? (
                <div className="space-y-3 py-2">
                  <div className="text-sm text-slate-700 bg-amber-50 border border-amber-200 rounded p-3">
                    <strong>{irregularCount}</strong> cotización(es) irregular(es) en este momento. Recomendado: primero <em>previsualizar</em> (dry-run) y luego aplicar.
                  </div>
                  <div className="flex gap-2 justify-end">
                    <Button
                      variant="outline"
                      disabled={regularizeRunning}
                      onClick={async () => {
                        setRegularizeRunning(true);
                        try {
                          const res = await api.post('/admin/quotes/regularize-batch', { dry_run: true });
                          setRegularizeResult({ ...res.data, _was_dry_run: true });
                        } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
                        finally { setRegularizeRunning(false); }
                      }}
                      data-testid="regularize-dry-run-btn"
                    >
                      {regularizeRunning ? 'Procesando...' : 'Previsualizar (dry-run)'}
                    </Button>
                    <Button
                      className="bg-orange-600 hover:bg-orange-700 text-white"
                      disabled={regularizeRunning}
                      onClick={async () => {
                        if (!window.confirm(`Aplicar regularización masiva sobre ${irregularCount} cotización(es)? Esta operación modifica registros.`)) return;
                        setRegularizeRunning(true);
                        try {
                          const res = await api.post('/admin/quotes/regularize-batch', { dry_run: false });
                          setRegularizeResult({ ...res.data, _was_dry_run: false });
                          // refrescar conteo
                          try { const ic = await api.get('/quotes/irregular/count'); setIrregularCount(ic.data.count || 0); } catch {}
                          fetchData();
                        } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
                        finally { setRegularizeRunning(false); }
                      }}
                      data-testid="regularize-apply-btn"
                    >
                      {regularizeRunning ? 'Aplicando...' : 'Aplicar regularización'}
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex-1 overflow-y-auto space-y-3 py-2" data-testid="regularize-result">
                  <div className={`rounded-lg border p-3 ${regularizeResult._was_dry_run ? 'bg-blue-50 border-blue-200' : 'bg-emerald-50 border-emerald-200'}`}>
                    <p className="text-sm font-semibold mb-2">
                      {regularizeResult._was_dry_run ? '🔍 Previsualización (no se aplicaron cambios)' : '✅ Regularización aplicada'}
                    </p>
                    <ul className="text-xs space-y-0.5">
                      <li>· Irregulares antes: <strong>{regularizeResult.total_irregular_before}</strong></li>
                      <li>· Regularizadas: <strong>{regularizeResult.regularized_count}</strong></li>
                      <li>· Backfill aplicado a: <strong>{regularizeResult.backfilled_count}</strong> cotización(es)</li>
                      <li>· No regularizables (criterio insuficiente): <strong>{regularizeResult.cannot_regularize_count}</strong></li>
                      {!regularizeResult._was_dry_run && (
                        <li>· Irregulares después: <strong>{regularizeResult.total_irregular_after}</strong></li>
                      )}
                    </ul>
                  </div>

                  {regularizeResult.details?.regularized?.length > 0 && (
                    <details open className="text-xs border border-emerald-100 rounded">
                      <summary className="cursor-pointer p-2 font-semibold bg-emerald-50 text-emerald-800">
                        Regularizadas ({regularizeResult.details.regularized.length})
                      </summary>
                      <ul className="p-2 space-y-0.5 max-h-40 overflow-y-auto">
                        {regularizeResult.details.regularized.map((q, i) => (
                          <li key={i}>· <span className="font-mono">{q.quote_number}</span> <span className="text-slate-500">({q.status})</span></li>
                        ))}
                      </ul>
                    </details>
                  )}

                  {regularizeResult.details?.backfilled?.length > 0 && (
                    <details className="text-xs border border-slate-200 rounded">
                      <summary className="cursor-pointer p-2 font-semibold bg-slate-50">
                        Backfill aplicado ({regularizeResult.details.backfilled.length})
                      </summary>
                      <ul className="p-2 space-y-1 max-h-40 overflow-y-auto">
                        {regularizeResult.details.backfilled.map((q, i) => (
                          <li key={i}>· <span className="font-mono">{q.quote_number}</span> ({q.status}) ← <span className="text-slate-500">{q.added_steps.join(', ')}</span></li>
                        ))}
                      </ul>
                    </details>
                  )}

                  {regularizeResult.details?.cannot_regularize?.length > 0 && (
                    <details className="text-xs border border-amber-200 rounded">
                      <summary className="cursor-pointer p-2 font-semibold bg-amber-50 text-amber-800">
                        No regularizables ({regularizeResult.details.cannot_regularize.length})
                      </summary>
                      <ul className="p-2 space-y-1 max-h-40 overflow-y-auto">
                        {regularizeResult.details.cannot_regularize.map((q, i) => (
                          <li key={i}>
                            · <span className="font-mono">{q.quote_number}</span> ({q.status}) — {q.reason}
                            {q.unmet && q.unmet.length > 0 && (
                              <span className="text-amber-700"> · requiere: {q.unmet.map(u => `${u.action} → ${u.needs}`).join(', ')}</span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}

                  <div className="flex gap-2 justify-end pt-2 border-t border-slate-200">
                    {regularizeResult._was_dry_run && (
                      <Button
                        className="bg-orange-600 hover:bg-orange-700 text-white"
                        disabled={regularizeRunning}
                        onClick={async () => {
                          if (!window.confirm(`Aplicar regularización masiva real? Se modificarán ${regularizeResult.regularized_count} cotización(es).`)) return;
                          setRegularizeRunning(true);
                          try {
                            const res = await api.post('/admin/quotes/regularize-batch', { dry_run: false });
                            setRegularizeResult({ ...res.data, _was_dry_run: false });
                            try { const ic = await api.get('/quotes/irregular/count'); setIrregularCount(ic.data.count || 0); } catch {}
                            fetchData();
                          } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
                          finally { setRegularizeRunning(false); }
                        }}
                      >
                        Aplicar ahora
                      </Button>
                    )}
                    <Button variant="outline" onClick={() => { setRegularizeBatchOpen(false); setRegularizeResult(null); }}>
                      Cerrar
                    </Button>
                  </div>
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
