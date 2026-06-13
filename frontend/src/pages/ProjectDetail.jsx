import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import api from '../utils/api';
import { formatRif } from '../utils/rifFormatter';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogFooter, AlertDialogTitle, AlertDialogDescription, AlertDialogAction, AlertDialogCancel } from '../components/ui/alert-dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Checkbox } from '../components/ui/checkbox';
import { toast } from 'sonner';
import {
  ArrowLeft, CreditCard, Building2, CheckCircle2, Circle, Clock,
  FileText, Send, Calendar, User, Store, Bell, BellRing, Lock, BarChart3, Mail,
  Plus, X, Paperclip, Image, Ticket, ChevronDown, Eye, Megaphone, ClipboardList,
  Hash, Trash2, AlertCircle, Shield, Edit3, Copy, ImagePlus, Server, Network, Edit2, Layers, FileBarChart, Flag, Landmark, FileDown
} from 'lucide-react';

import { SingleBankSection } from '../components/projects/SingleBankSection';
import { MultistoreBankSection } from '../components/projects/MultistoreBankSection';
import { StoreBankSection } from '../components/projects/StoreBankSection';
import { MultiRifTree } from '../components/projects/MultiRifTree';
import { InternalEmailInput } from '../components/InternalEmailInput';
import { PHASES, STORE_PHASES, PHASE_COLORS, ALL_TOKENS } from '../components/projects/projectConstants';
import { TemplateBodyEditor } from '../components/projects/TemplateBodyEditor';
import { ProjectProgressReportDialog } from '../components/ProjectProgressReportDialog';
import { BatchUpdateModal } from '../components/projects/BatchUpdateModal';
import { EmailDetailViewer } from '../components/projects/EmailDetailViewer';
import { TemplatesAdminDialog } from '../components/projects/TemplatesAdminDialog';
import { RichTextEditor } from '../components/RichTextEditor';
import { EmailPreviewDialog } from '../components/projects/EmailPreviewDialog';
import { CommitmentModal } from '../components/CommitmentModal';
import { ImplementerAlertsModal } from '../components/ImplementerAlertsModal';

const ProjectDetail = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [commitmentsOpen, setCommitmentsOpen] = useState(false);
  const [alertsOpen, setAlertsOpen] = useState(false);
  const [bitacoraText, setBitacoraText] = useState('');
  const [bitacoraDate, setBitacoraDate] = useState(new Date().toISOString().split('T')[0]);
  const [bitacoraSubmitting, setBitacoraSubmitting] = useState(false);
  const [progressReportOpen, setProgressReportOpen] = useState(false);
  const [selectedStoreId, setSelectedStoreId] = useState(null);

  // Notificaciones secuenciales
  const [notifDialogOpen, setNotifDialogOpen] = useState(false);
  const [notifTarget, setNotifTarget] = useState(null); // {type: 'client'|'bank', bankName?}
  const [notifSending, setNotifSending] = useState(null); // level string being sent
  // Plantilla Preferida + editor enriquecido dentro del modal de notificaciones
  const [notifPreferences, setNotifPreferences] = useState({ client: '', bank: '', bank_client: '' });
  const [selectedNotifTemplateId, setSelectedNotifTemplateId] = useState('');
  const [notifBody, setNotifBody] = useState('');
  const [projectMatrixHtml, setProjectMatrixHtml] = useState('');
  const [resolvedRecipients, setResolvedRecipients] = useState([]);

  // Otras Notificaciones (ad-hoc avanzado)
  const [emailDialogOpen, setEmailDialogOpen] = useState(false);
  const [emailForm, setEmailForm] = useState({ recipients: [''], subject: '', message: '', templateId: '' });
  const [adhocManualEmail, setAdhocManualEmail] = useState('');

  // Batch update (actualización masiva multitienda)
  const [batchModalOpen, setBatchModalOpen] = useState(false);
  const [batchPhase, setBatchPhase] = useState('');
  const [batchBank, setBatchBank] = useState('');
  const [batchProducts, setBatchProducts] = useState([]);
  const [batchStoreIds, setBatchStoreIds] = useState([]);
  const [batchReason, setBatchReason] = useState('Recepción de información masiva por parte del Banco/Cliente');
  const [batchSubmitting, setBatchSubmitting] = useState(false);
  // Fase 5 VPOS Multi-RIF: filtro en cascada por RIF. '__ALL__' = Todos los RIFs.
  const [batchRif, setBatchRif] = useState('__ALL__');
  const [fichaDownloading, setFichaDownloading] = useState(false);

  // Tiendas visibles en el modal según el filtro de RIF en cascada.
  const getBatchFilteredStores = () => {
    const stores = project?.stores || [];
    if (!batchRif || batchRif === '__ALL__') return stores;
    return stores.filter(s => s.rif_id === batchRif);
  };

  const openBatchModal = () => {
    setBatchPhase(STORE_PHASES[0]);
    const firstBank = Object.keys(project?.implementation_matrix || {})[0] || '';
    setBatchBank(firstBank);
    const prods = firstBank ? Object.keys((project?.implementation_matrix || {})[firstBank] || {}) : [];
    setBatchProducts(prods);
    setBatchStoreIds([]);
    setBatchRif('__ALL__');
    setBatchReason('Recepción de información masiva por parte del Banco/Cliente');
    setBatchModalOpen(true);
  };

  const toggleBatchStore = (storeId) => {
    setBatchStoreIds(prev => prev.includes(storeId) ? prev.filter(s => s !== storeId) : [...prev, storeId]);
  };

  const toggleBatchProduct = (prod) => {
    setBatchProducts(prev => prev.includes(prod) ? prev.filter(p => p !== prod) : [...prev, prod]);
  };

  // Al cambiar de banco en el modal, preseleccionar todos sus medios de pago.
  const handleBatchBankChange = (bank) => {
    setBatchBank(bank);
    setBatchProducts(Object.keys((project?.implementation_matrix || {})[bank] || {}));
  };

  // Al cambiar el RIF, se reinicia la selección de tiendas (cambia el universo visible).
  const handleBatchRifChange = (rif) => {
    setBatchRif(rif);
    setBatchStoreIds([]);
  };

  const toggleAllBatchStores = () => {
    const all = getBatchFilteredStores().map(s => s.store_id);
    setBatchStoreIds(prev => (all.length > 0 && prev.length === all.length) ? [] : all);
  };

  const submitBatchUpdate = async () => {
    if (!batchPhase || !batchBank || batchProducts.length === 0) {
      toast.error('Seleccione fase, banco y al menos un producto'); return;
    }
    if (batchStoreIds.length === 0) {
      toast.error('Seleccione al menos una tienda'); return;
    }
    const confirmMsg = `Se actualizará la fase "${batchPhase}" de ${batchProducts.length} producto(s) (banco ${batchBank}) en ${batchStoreIds.length} tienda(s). ¿Continuar?`;
    if (!window.confirm(confirmMsg)) return;
    setBatchSubmitting(true);
    try {
      const res = await api.post(`/projects/${projectId}/matrix/batch-update`, {
        phase: batchPhase,
        bank_name: batchBank,
        product_names: batchProducts,
        store_ids: batchStoreIds,
        reason: batchReason,
      });
      toast.success(res.data.message || 'Actualización masiva aplicada');
      setBatchModalOpen(false);
      fetchProject();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error en actualización masiva');
    } finally {
      setBatchSubmitting(false);
    }
  };

  useEffect(() => {
    api.get('/cc-groups').then(r => setCcGroups(r.data || [])).catch(() => {});
  }, []);
  const [emailFiles, setEmailFiles] = useState([]);
  const [emailSending, setEmailSending] = useState(false);
  const [suggestedContacts, setSuggestedContacts] = useState([]);
  const [emailTemplates, setEmailTemplates] = useState([]);
  const [attachMatrix, setAttachMatrix] = useState(false);
  const fileInputRef = useRef(null);
  // Adjuntos para Notificaciones a Bancos/Clientes (Cargar Archivos/Imágenes + Matriz)
  const [notifFiles, setNotifFiles] = useState([]);
  const [notifAttachMatrix, setNotifAttachMatrix] = useState(false);
  const notifFileInputRef = useRef(null);

  // Bitácora email detail viewer
  const [emailDetailOpen, setEmailDetailOpen] = useState(false);
  const [emailDetailData, setEmailDetailData] = useState(null);

  // Preview de email (ahora editable)
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  // Destinatarios principales (TO) seleccionados manualmente para la notificación secuencial
  const [mainRecipients, setMainRecipients] = useState([]);
  const [previewSubject, setPreviewSubject] = useState('');
  const [previewSending, setPreviewSending] = useState(false);
  const [previewContext, setPreviewContext] = useState(null); // {type: 'sequential'|'adhoc', target, bankName}
  const editorRef = useRef(null);

  // Admin: template management
  const [templatesDialogOpen, setTemplatesDialogOpen] = useState(false);
  const [templateForm, setTemplateForm] = useState({ name: '', subject: '', body: '' });
  const [editingTemplateId, setEditingTemplateId] = useState(null);
  const [templateSaving, setTemplateSaving] = useState(false);

  // Security Lock: ticket number
  const [ticketInput, setTicketInput] = useState('');
  const [ticketSaving, setTicketSaving] = useState(false);
  const [ticketDupWarning, setTicketDupWarning] = useState(null);

  // VTID Generator
  const [vtidPrefix, setVtidPrefix] = useState('');
  const [vtidStartNumber, setVtidStartNumber] = useState(1);
  const [vtidGenerating, setVtidGenerating] = useState(false);
  const [vtidDeleting, setVtidDeleting] = useState(false);
  const [vtidCollapsed, setVtidCollapsed] = useState(true); // colapsado por defecto

  // Seriales de Implementación
  const [serialInput, setSerialInput] = useState('');
  const [serialUploading, setSerialUploading] = useState(false);
  const serialFileRef = useRef(null);

  // Integrador / Aplicativo editable inline
  const [editingIntegrator, setEditingIntegrator] = useState(false);
  const [integratorName, setIntegratorName] = useState('');
  const [applicationName, setApplicationName] = useState('');
  const [integratorsList, setIntegratorsList] = useState([]);
  const [boxCount, setBoxCount] = useState(0);

  const fetchProject = useCallback(async () => {
    try {
      const res = await api.get(`/projects/${projectId}`);
      setProject(res.data);
    } catch { toast.error('Error al cargar proyecto'); }
    finally { setLoading(false); }
  }, [projectId]);

  useEffect(() => { fetchProject(); }, [fetchProject]);

  // Sync integrator/application from project
  useEffect(() => {
    if (project) {
      setIntegratorName(project.integrator_name || '');
      setApplicationName(project.integrator_app_name || project.application_name || '');
      setBoxCount(project.box_count || project.cantidad_cajas || 0);
    }
  }, [project]);

  // Cargar lista de integradores para el selector
  useEffect(() => {
    api.get('/integrators').then(r => setIntegratorsList(r.data || [])).catch(() => {});
  }, []);

  // Permisos: determinar si el usuario actual puede editar
  const currentUser = JSON.parse(localStorage.getItem('user') || '{}');
  // Edición de la Matriz: Admin, el implementador asignado, o cualquier usuario con
  // PERFIL DE IMPLEMENTACIÓN (cargo Implementador / Coordinador / Gerente de
  // Implementación / Técnico de Infraestructura, o departamento "Implementación").
  // Nota: el acceso al proyecto ya está restringido por la regla de visibilidad
  // (un Implementador solo ve los suyos), por lo que ampliar aquí es seguro.
  const _cargoLc = (currentUser.cargo || '').toLowerCase();
  const _deptoLc = (currentUser.departamento || '').toLowerCase();
  const isImplementationProfile =
    _deptoLc.includes('implement') || _cargoLc.includes('implement') || _cargoLc.includes('infraestructura');
  const canEditMatrix = currentUser.role === 'admin' ||
    (!!project?.assigned_to_user_id && currentUser.user_id === project.assigned_to_user_id) ||
    isImplementationProfile;

  // Seriales de implementación
  const addSerials = async (serialsList) => {
    if (!serialsList.length) return;
    setSerialUploading(true);
    try {
      await api.post(`/projects/${projectId}/implementation-serials`, { serials: serialsList });
      toast.success(`${serialsList.length} serial(es) agregados`);
      fetchProject();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al agregar seriales'); }
    finally { setSerialUploading(false); }
  };

  const handleSerialManualAdd = () => {
    if (!serialInput.trim()) return;
    const serials = serialInput.split(/[\n,;]+/).map(s => s.trim()).filter(Boolean);
    addSerials(serials);
    setSerialInput('');
  };

  const handleSerialFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setSerialUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await api.post(`/projects/${projectId}/implementation-serials/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      toast.success(res.data.message);
      fetchProject();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al cargar archivo de seriales');
    } finally {
      setSerialUploading(false);
    }
    if (serialFileRef.current) serialFileRef.current.value = '';
  };

  const removeSerial = async (serial) => {
    try {
      await api.delete(`/projects/${projectId}/implementation-serials/${encodeURIComponent(serial)}`);
      fetchProject();
    } catch { toast.error('Error al eliminar serial'); }
  };

  // Guardar integrador/aplicativo
  const saveIntegratorFields = async () => {
    try {
      await api.put(`/projects/${projectId}/implementation-fields`, {
        integrator_name: integratorName,
        integrator_app_name: applicationName,
        box_count: boxCount,
      });
      toast.success('Campos actualizados');
      setEditingIntegrator(false);
      fetchProject();
    } catch { toast.error('Error al guardar'); }
  };

  // Matrix update con cantidades
  const updateMatrixQuantity = async (bankName, productName, phase, expected, processed) => {
    try {
      await api.put(`/projects/${projectId}/matrix/phase`, {
        bank_name: bankName, product_name: productName, phase,
        completed: processed >= expected && expected > 0,
        expected, processed
      });
      fetchProject();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al actualizar fase');
    }
  };

  // Parche LOCAL (optimista) del estado del proyecto: actualiza celdas de la matriz
  // de una tienda y el rollup, evitando recargar todo el proyecto (latencia Multi-RIF).
  const patchStoreMatrixLocal = useCallback((storeId, cellUpdates, rollup) => {
    setProject(prev => {
      if (!prev) return prev;
      const stores = (prev.stores || []).map(s => {
        if (s.store_id !== storeId) return s;
        const matrix = { ...(s.implementation_matrix || {}) };
        cellUpdates.forEach(({ bank, product, phase, expected, processed, completed }) => {
          const bankObj = { ...(matrix[bank] || {}) };
          const prodObj = { ...(bankObj[product] || {}) };
          prodObj[phase] = { ...(prodObj[phase] || {}), expected, processed, completed };
          bankObj[product] = prodObj;
          matrix[bank] = bankObj;
        });
        return { ...s, implementation_matrix: matrix };
      });
      return { ...prev, stores, ...(rollup ? { rollup_progress: rollup } : {}) };
    });
  }, []);

  // Matrix update para stores (multitienda)
  const updateStoreMatrixQuantity = async (storeId, bankName, productName, phase, expected, processed) => {
    try {
      const { data } = await api.put(`/projects/${projectId}/stores/${storeId}/matrix/phase`, {
        bank_name: bankName, product_name: productName, phase,
        completed: processed >= expected && expected > 0,
        expected, processed
      });
      patchStoreMatrixLocal(storeId, [{
        bank: bankName, product: productName, phase,
        expected: data.expected, processed: data.processed, completed: data.completed,
      }], data.rollup_progress);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al actualizar fase de tienda');
      fetchProject();
    }
  };

  // Cascade (Single): el campo derecho "Cantidad de Terminales" se propaga a TODAS
  // las fases del producto-Banco. Se preserva el avance (processed) de cada fase;
  // solo la fase editada conserva su processed en vivo.
  const updateMatrixCascade = async (bankName, productName, newExpected, editedPhase, editedProcessed) => {
    try {
      const matrixData = (project?.implementation_matrix?.[bankName]?.[productName]) || {};
      // Secuencial (no Promise.all): evita race read-modify-write que perdería una fase.
      for (const phase of PHASES) {
        const pd = matrixData[phase] || {};
        const processed = phase === editedPhase ? editedProcessed : (pd.processed || 0);
        // eslint-disable-next-line no-await-in-loop
        await api.put(`/projects/${projectId}/matrix/phase`, {
          bank_name: bankName, product_name: productName, phase,
          completed: processed >= newExpected && newExpected > 0,
          expected: newExpected, processed,
        });
      }
      fetchProject();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al actualizar matriz en cascada');
    }
  };

  // Fill-single-phase (T): iguala processed=expected en UNA fase específica del producto (Single)
  const fillPhaseToExpected = async (bankName, productName, phase, expected) => {
    try {
      if (!expected || expected <= 0) {
        toast.error('Defina primero la cantidad Esperada');
        return;
      }
      await api.put(`/projects/${projectId}/matrix/phase`, {
        bank_name: bankName, product_name: productName, phase,
        completed: true, expected, processed: expected,
      });
      fetchProject();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al completar fase');
    }
  };

  // Store: cascade + fill-all (Multitienda)
  const updateStoreMatrixCascade = async (storeId, bankName, productName, newExpected, editedPhase, editedProcessed) => {
    try {
      const store = project?.stores?.find(s => s.store_id === storeId);
      const matrixData = (store?.implementation_matrix?.[bankName]?.[productName]) || {};
      // Secuencial (no Promise.all): cada fase escribe el documento completo; en
      // paralelo se pisarían entre sí (race read-modify-write) y se perdería una fase.
      const cellUpdates = [];
      let lastRollup = null;
      for (const phase of STORE_PHASES) {
        const pd = matrixData[phase] || {};
        const processed = phase === editedPhase ? editedProcessed : (pd.processed || 0);
        // eslint-disable-next-line no-await-in-loop
        const { data } = await api.put(`/projects/${projectId}/stores/${storeId}/matrix/phase`, {
          bank_name: bankName, product_name: productName, phase,
          completed: processed >= newExpected && newExpected > 0,
          expected: newExpected, processed,
        });
        lastRollup = data.rollup_progress || lastRollup;
        cellUpdates.push({ bank: bankName, product: productName, phase, expected: data.expected, processed: data.processed, completed: data.completed });
      }
      patchStoreMatrixLocal(storeId, cellUpdates, lastRollup);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al actualizar matriz en cascada');
      fetchProject();
    }
  };

  const fillStorePhaseToExpected = async (storeId, bankName, productName, phase, expected) => {
    try {
      if (!expected || expected <= 0) {
        toast.error('Defina primero la cantidad Esperada');
        return;
      }
      const { data } = await api.put(`/projects/${projectId}/stores/${storeId}/matrix/phase`, {
        bank_name: bankName, product_name: productName, phase,
        completed: true, expected, processed: expected,
      });
      patchStoreMatrixLocal(storeId, [{
        bank: bankName, product: productName, phase,
        expected: data.expected, processed: data.processed, completed: data.completed,
      }], data.rollup_progress);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al completar fase');
      fetchProject();
    }
  };

  const fetchTemplates = async () => {
    try {
      const res = await api.get('/email-templates?context=IMPLEMENTACION');
      setEmailTemplates(res.data || []);
    } catch (err) {
      console.error('Error cargando plantillas:', err);
      toast.error('Error al cargar las plantillas de correo');
      setEmailTemplates([]);
    }
  };

  const fetchSuggestedContacts = async () => {
    try {
      const res = await api.get(`/projects/${projectId}/suggested-contacts`);
      setSuggestedContacts(res.data || []);
    } catch (err) {
      console.error('Error cargando contactos:', err);
      toast.error('Error al cargar los contactos del proyecto');
      setSuggestedContacts([]);
    }
  };

  // ==================== MATRIX PHASE TOGGLES ====================
  const togglePhase = async (bankName, productName, phase, completed) => {
    try {
      await api.put(`/projects/${projectId}/matrix/phase`, { bank_name: bankName, product_name: productName, phase, completed: !completed });
      fetchProject();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error actualizando fase'); }
  };

  const toggleStorePhase = async (storeId, bankName, productName, phase, completed) => {
    try {
      const { data } = await api.put(`/projects/${projectId}/stores/${storeId}/matrix/phase`, { bank_name: bankName, product_name: productName, phase, completed: !completed });
      patchStoreMatrixLocal(storeId, [{
        bank: bankName, product: productName, phase,
        expected: data.expected, processed: data.processed, completed: data.completed,
      }], data.rollup_progress);
    } catch (err) { toast.error(err.response?.data?.detail || 'Error actualizando fase de tienda'); fetchProject(); }
  };

  // ==================== SEQUENTIAL NOTIFICATIONS ====================
  // Sustituye el token {Matriz_Bancos_Productos} por la tabla real para que sea
  // editable dentro del editor enriquecido (edición de celdas + eliminar fila).
  const injectMatrix = (html, matrixHtml) => {
    const m = matrixHtml !== undefined ? matrixHtml : projectMatrixHtml;
    if (!html || !m) return html || '';
    return String(html).replace(/\{\s*Matriz_Bancos_Productos\s*\}/g, m);
  };

  const openNotifDialog = async (type, bankName) => {
    setNotifTarget({ type, bankName });
    setAdditionalRecipientsList([]);
    setCcNewEmail('');
    setToNewEmail('');
    setMainRecipients([]);
    setResolvedRecipients([]);
    setNotifFiles([]);
    setNotifAttachMatrix(false);
    fetchSuggestedContacts();
    // Cargar Plantillas de Proyecto (Texto Enriquecido) + preferencias + matriz y precargar la preferida
    try {
      const [tplRes, prefRes, varsRes] = await Promise.all([
        api.get('/email-templates?context=IMPLEMENTACION'),
        api.get('/project-notification-preferences'),
        api.get(`/projects/${projectId}/template-variables`),
      ]);
      const tpls = tplRes.data || [];
      const prefs = prefRes.data || {};
      const matrixHtml = varsRes.data?.matrix_html || '';
      setEmailTemplates(tpls);
      setNotifPreferences(prefs);
      setProjectMatrixHtml(matrixHtml);
      const preferredId = prefs[type];
      const preferred = tpls.find(t => t.template_id === preferredId) || tpls[0] || null;
      setSelectedNotifTemplateId(preferred?.template_id || '');
      setNotifBody(injectMatrix(preferred?.body_html || '', matrixHtml));
    } catch (err) {
      console.error('Error cargando plantillas/preferencias:', err);
      setEmailTemplates([]);
      setSelectedNotifTemplateId('');
      setNotifBody('');
      setProjectMatrixHtml('');
    }
    setNotifDialogOpen(true);
  };

  // Cambiar la plantilla seleccionada en el modal → recarga el cuerpo (con matriz inyectada) en el editor
  const handleNotifTemplateChange = (templateId) => {
    setSelectedNotifTemplateId(templateId);
    const tpl = emailTemplates.find(t => t.template_id === templateId);
    setNotifBody(injectMatrix(tpl?.body_html || ''));
  };

  // Marcar la plantilla seleccionada como Preferida para el destino actual
  const markNotifTemplatePreferred = async () => {
    if (!selectedNotifTemplateId || !notifTarget) return;
    try {
      await api.put('/project-notification-preferences', {
        destination: notifTarget.type,
        template_id: selectedNotifTemplateId,
      });
      setNotifPreferences(prev => ({ ...prev, [notifTarget.type]: selectedNotifTemplateId }));
      toast.success('Plantilla marcada como preferida para este destino');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'No se pudo marcar como preferida');
    }
  };

  const getEntityHistory = (target) => {
    if (!project) return [];
    const nh = project.notification_history || {};
    const key = target.type === 'client' ? 'client' : `bank_${target.bankName}`;
    // Para bank_client usamos el historial del banco (donde se registran los envíos combinados)
    return nh[key] || [];
  };

  const NOTIFICATION_PREFIXES = ['Primer Envío', 'Primer Recordatorio', 'Segundo Recordatorio', 'Tercer Recordatorio'];
  const [additionalRecipientsList, setAdditionalRecipientsList] = useState([]);
  const [ccNewEmail, setCcNewEmail] = useState('');
  const [toNewEmail, setToNewEmail] = useState('');
  // Grupos de destinatarios CC reutilizables
  const [ccGroups, setCcGroups] = useState([]);
  const [ccGroupName, setCcGroupName] = useState('');
  const [showSaveGroup, setShowSaveGroup] = useState(false);

  const applyCcGroup = (g) => {
    const merged = [...additionalRecipientsList];
    (g.emails || []).forEach(e => {
      if (e && !merged.map(x => x.toLowerCase()).includes(e.toLowerCase())) merged.push(e);
    });
    setAdditionalRecipientsList(merged);
    toast.success(`Grupo "${g.name}" aplicado (${(g.emails || []).length} correos)`);
  };
  const saveCcGroup = async () => {
    const name = (ccGroupName || '').trim();
    if (!name) return;
    if (additionalRecipientsList.length === 0) { toast.error('Agregue al menos un correo CC antes de guardar el grupo'); return; }
    try {
      await api.post('/cc-groups', { name, emails: additionalRecipientsList });
      toast.success(`Grupo "${name}" guardado`);
      setCcGroupName('');
      setShowSaveGroup(false);
      const r = await api.get('/cc-groups');
      setCcGroups(r.data || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo guardar el grupo');
    }
  };
  const deleteCcGroup = async (id) => {
    try {
      await api.delete(`/cc-groups/${id}`);
      setCcGroups(ccGroups.filter(g => g.group_id !== id));
      toast.success('Grupo eliminado');
    } catch (e) {
      toast.error('No se pudo eliminar el grupo');
    }
  };

  // Agregar/quitar destinatarios CC como tokens (homologado con el cotizador).
  const addCcRecipient = () => {
    const e = (ccNewEmail || '').trim();
    if (!e || !e.includes('@')) { toast.error('Ingrese un correo válido'); return; }
    if (additionalRecipientsList.map(x => x.toLowerCase()).includes(e.toLowerCase())) { setCcNewEmail(''); return; }
    setAdditionalRecipientsList([...additionalRecipientsList, e]);
    setCcNewEmail('');
  };
  const removeCcRecipient = (email) => setAdditionalRecipientsList(additionalRecipientsList.filter(x => x !== email));
  // Agregar/corregir el correo principal (TO) en caliente como token.
  const addToRecipient = () => {
    const e = (toNewEmail || '').trim();
    if (!e || !e.includes('@')) { toast.error('Ingrese un correo válido'); return; }
    if (mainRecipients.map(x => x.toLowerCase()).includes(e.toLowerCase())) { setToNewEmail(''); return; }
    setMainRecipients([...mainRecipients, e]);
    setToNewEmail('');
  };

  const sendNotification = async () => {
    // Validar al menos un destinatario principal
    if (!mainRecipients || mainRecipients.length === 0) {
      toast.error('Agregue al menos un destinatario principal (TO) desde el panel "Contactos del Proyecto"');
      return;
    }
    setNotifSending('sending');
    try {
      const ccList = additionalRecipientsList.filter(e => e && e.includes('@'));

      const formData = new FormData();
      formData.append('target', notifTarget.type);
      if (notifTarget.bankName) formData.append('bank_name', notifTarget.bankName);
      formData.append('to_override', JSON.stringify(mainRecipients));
      formData.append('additional_recipients', JSON.stringify(ccList));
      if (selectedNotifTemplateId) formData.append('template_id', selectedNotifTemplateId);
      if (notifBody) formData.append('custom_html', notifBody);
      formData.append('attach_matrix', notifAttachMatrix ? 'true' : 'false');
      notifFiles.forEach(f => formData.append('files', f));

      const res = await api.post(`/projects/${projectId}/send-notification`, formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      toast.success(res.data.message);
      setAdditionalRecipientsList([]);
      setCcNewEmail('');
      setToNewEmail('');
      setMainRecipients([]);
      setNotifFiles([]);
      setNotifAttachMatrix(false);
      fetchProject();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al enviar notificación');
    } finally { setNotifSending(null); }
  };

  const handleNotifFileSelect = (e) => { setNotifFiles(prev => [...prev, ...Array.from(e.target.files || [])]); };
  const removeNotifFile = (idx) => setNotifFiles(prev => prev.filter((_, i) => i !== idx));

  // ==================== OTRAS NOTIFICACIONES (AD-HOC) ====================
  const openEmailDialog = () => {
    setEmailForm({ recipients: [], subject: '', message: '', templateId: '' });
    setAdhocManualEmail('');
    setEmailFiles([]);
    setAttachMatrix(false);
    // Reset estado CC (compartido con el modal de Notificaciones)
    setAdditionalRecipientsList([]);
    setCcNewEmail('');
    setShowSaveGroup(false);
    setCcGroupName('');
    fetchSuggestedContacts();
    fetchTemplates();
    setEmailDialogOpen(true);
  };

  const addRecipient = () => setEmailForm(prev => ({ ...prev, recipients: [...prev.recipients, ''] }));
  const removeRecipient = (idx) => setEmailForm(prev => ({ ...prev, recipients: prev.recipients.filter((_, i) => i !== idx) }));
  const updateRecipient = (idx, val) => setEmailForm(prev => { const r = [...prev.recipients]; r[idx] = val; return { ...prev, recipients: r }; });

  const addSuggestedContact = (email) => {
    if (!emailForm.recipients.includes(email)) {
      setEmailForm(prev => ({ ...prev, recipients: [...prev.recipients.filter(r => r.trim()), email] }));
    }
  };

  // Homologación con Notificaciones a Bancos/Clientes: alternar destinatario por checkbox.
  const toggleAdhocRecipient = (email) => {
    if (!email) return;
    const lower = email.toLowerCase();
    setEmailForm(prev => {
      const cleaned = prev.recipients.filter(r => r.trim());
      const exists = cleaned.some(r => r.toLowerCase() === lower);
      return { ...prev, recipients: exists ? cleaned.filter(r => r.toLowerCase() !== lower) : [...cleaned, email] };
    });
  };

  const addAdhocManualRecipient = () => {
    const emails = (adhocManualEmail || '').split(/[,;]/).map(e => e.trim()).filter(e => e && e.includes('@'));
    if (emails.length === 0) { toast.error('Ingrese un correo válido'); return; }
    setEmailForm(prev => {
      const cleaned = prev.recipients.filter(r => r.trim());
      const existing = cleaned.map(r => r.toLowerCase());
      const toAdd = emails.filter(e => !existing.includes(e.toLowerCase()));
      return { ...prev, recipients: [...cleaned, ...toAdd] };
    });
    setAdhocManualEmail('');
  };

  const handleTemplateSelect = (templateId) => {
    if (templateId === 'blank') {
      setEmailForm(prev => ({ ...prev, templateId: '', subject: '', message: '' }));
      return;
    }
    const tpl = emailTemplates.find(t => t.template_id === templateId);
    if (tpl) {
      // Las plantillas de proyecto almacenan el contenido enriquecido en body_html.
      const messageBody = tpl.body_html || tpl.body || '';
      setEmailForm(prev => ({ ...prev, templateId: templateId, subject: tpl.subject || '', message: messageBody }));
    }
  };

  const handleFileSelect = (e) => { setEmailFiles(prev => [...prev, ...Array.from(e.target.files || [])]); };
  const removeFile = (idx) => setEmailFiles(prev => prev.filter((_, i) => i !== idx));

  const generateMatrixHTML = () => {
    if (!project) return '';
    const matrix = project.implementation_matrix || {};
    const isMs = project.project_type === 'multistore';
    let html = `<div style="font-family:Arial,sans-serif;"><h3>Matriz de Seguimiento — ${project.ticket_number || project.project_number}</h3>`;
    html += `<p>Cliente: ${project.client_name} | Avance: ${project.rollup_progress?.global_progress || 0}%</p>`;
    html += '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-size:12px;width:100%;">';
    const phases = isMs ? STORE_PHASES : PHASES;
    html += `<tr style="background:#2563eb;color:white;"><th>Banco / Producto</th>${phases.map(p => `<th>${p}</th>`).join('')}</tr>`;
    for (const [bank, products] of Object.entries(matrix)) {
      html += `<tr style="background:#dbeafe;"><td colspan="${phases.length + 1}"><strong>${bank}</strong></td></tr>`;
      for (const [prod, phaseData] of Object.entries(products)) {
        html += `<tr><td style="padding-left:20px;">${prod}</td>`;
        phases.forEach(p => {
          const done = phaseData[p]?.completed;
          html += `<td style="text-align:center;background:${done ? '#d1fae5' : '#f1f5f9'};">${done ? '✓' : '—'}</td>`;
        });
        html += '</tr>';
      }
    }
    html += '</table>';
    if (isMs && project.stores) {
      project.stores.forEach(store => {
        const sm = store.implementation_matrix || {};
        const progress = calcStoreProgress(store);
        html += `<h4 style="margin-top:16px;">Tienda: ${store.name} (${store.box_count} cajas) — ${progress}%</h4>`;
        html += '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-size:12px;width:100%;">';
        html += `<tr style="background:#2563eb;color:white;"><th>Banco / Producto</th>${STORE_PHASES.map(p => `<th>${p}</th>`).join('')}</tr>`;
        for (const [bank, products] of Object.entries(sm)) {
          html += `<tr style="background:#dbeafe;"><td colspan="${STORE_PHASES.length + 1}"><strong>${bank}</strong></td></tr>`;
          for (const [prod, phaseData] of Object.entries(products)) {
            html += `<tr><td style="padding-left:20px;">${prod}</td>`;
            STORE_PHASES.forEach(p => {
              const done = phaseData[p]?.completed;
              html += `<td style="text-align:center;background:${done ? '#d1fae5' : '#f1f5f9'};">${done ? '✓' : '—'}</td>`;
            });
            html += '</tr>';
          }
        }
        html += '</table>';
      });
    }
    html += '</div>';
    return html;
  };

  const handleSendAdhocEmail = async () => {
    const validRecipients = emailForm.recipients.filter(r => r.trim());
    if (!validRecipients.length) { toast.error('Agregue al menos un destinatario'); return; }
    if (!emailForm.subject.trim()) { toast.error('El asunto es obligatorio'); return; }
    if (!emailForm.message.trim()) { toast.error('El mensaje es obligatorio'); return; }

    setEmailSending(true);
    try {
      const formData = new FormData();
      formData.append('recipients', JSON.stringify(validRecipients));
      const ccList = additionalRecipientsList.filter(e => e && e.includes('@'));
      formData.append('additional_recipients', JSON.stringify(ccList));
      formData.append('subject', emailForm.subject);
      formData.append('message', emailForm.message);
      // Matrix HTML se envía separada, no cuenta para el límite de caracteres
      if (attachMatrix) {
        formData.append('matrix_html', generateMatrixHTML());
      }
      emailFiles.forEach(f => formData.append('files', f));
      const res = await api.post(`/projects/${projectId}/send-adhoc-email`, formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      toast.success(res.data.message);
      setEmailDialogOpen(false);
      fetchProject();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al enviar correo'); }
    finally { setEmailSending(false); }
  };

  // ==================== PREVIEW DE EMAIL (EDITABLE) ====================
  const previewNotification = async (target, bankName) => {
    if (!mainRecipients || mainRecipients.length === 0) {
      toast.error('Agregue al menos un destinatario principal antes de generar la vista previa');
      return;
    }
    setPreviewLoading(true);
    try {
      const res = await api.post(`/projects/${projectId}/preview-notification`, {
        target: target || 'client',
        bank_name: bankName || null,
        to_override: mainRecipients,
        template_id: selectedNotifTemplateId || null,
        custom_html: notifBody || null,
      });
      setPreviewData(res.data);
      setPreviewSubject(res.data.subject || '');
      setPreviewContext({ type: 'sequential', target, bankName });
      setPreviewOpen(true);
    } catch (err) { toast.error(err.response?.data?.detail || 'Error generando vista previa'); }
    finally { setPreviewLoading(false); }
  };

  const previewAdhocEmail = async () => {
    if (!emailForm.subject.trim() || !emailForm.message.trim()) {
      toast.error('Escriba asunto y mensaje para la vista previa');
      return;
    }
    setPreviewLoading(true);
    try {
      const res = await api.post(`/projects/${projectId}/preview-adhoc-email`, {
        subject: emailForm.subject,
        message: emailForm.message,
        include_matrix: attachMatrix,
      });
      setPreviewData(res.data);
      setPreviewSubject(res.data.subject || '');
      setPreviewContext({ type: 'adhoc' });
      setPreviewOpen(true);
    } catch (err) { toast.error(err.response?.data?.detail || 'Error generando vista previa'); }
    finally { setPreviewLoading(false); }
  };

  const handleEditorPaste = async (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        e.preventDefault();
        const file = item.getAsFile();
        if (!file) return;
        await uploadAndInsertImage(file);
        return;
      }
    }
  };

  const handleEditorDrop = async (e) => {
    const files = e.dataTransfer?.files;
    if (!files || files.length === 0) return;
    for (const file of files) {
      if (file.type.startsWith('image/')) {
        e.preventDefault();
        await uploadAndInsertImage(file);
        return;
      }
    }
  };

  const uploadAndInsertImage = async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    try {
      toast.info('Subiendo imagen...');
      const res = await api.post('/projects/upload-image', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const url = res.data.url;
      if (editorRef.current) {
        editorRef.current.focus();
        document.execCommand('insertImage', false, url);
      }
      toast.success('Imagen insertada');
    } catch (err) {
      toast.error('Error al subir imagen. Verifique el formato (JPG/PNG) y tamaño (<10MB)');
      // Fallback: insert as base64 (will be converted on send)
      const reader = new FileReader();
      reader.onload = (ev) => {
        if (editorRef.current) {
          editorRef.current.focus();
          document.execCommand('insertImage', false, ev.target.result);
        }
      };
      reader.readAsDataURL(file);
    }
  };

  const handleInsertImage = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/jpeg,image/png,image/gif,image/webp';
    input.onchange = async (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      await uploadAndInsertImage(file);
    };
    input.click();
  };

  const insertVariableInEditor = (variable) => {
    if (!editorRef.current) return;
    editorRef.current.focus();
    document.execCommand('insertText', false, variable);
  };

  const sendFromPreview = async () => {
    if (!editorRef.current) return;
    const editedHtml = editorRef.current.innerHTML;
    const editedSubject = previewSubject;
    setPreviewSending(true);

    try {
      if (previewContext?.type === 'sequential') {
        const ccList = additionalRecipientsList.filter(e => e && e.includes('@'));

        const formData = new FormData();
        formData.append('target', previewContext.target);
        if (previewContext.bankName) formData.append('bank_name', previewContext.bankName);
        if (mainRecipients && mainRecipients.length > 0) formData.append('to_override', JSON.stringify(mainRecipients));
        formData.append('additional_recipients', JSON.stringify(ccList));
        if (selectedNotifTemplateId) formData.append('template_id', selectedNotifTemplateId);
        formData.append('custom_html', editedHtml);
        formData.append('custom_subject', editedSubject);
        formData.append('attach_matrix', notifAttachMatrix ? 'true' : 'false');
        notifFiles.forEach(f => formData.append('files', f));

        const res = await api.post(`/projects/${projectId}/send-notification`, formData, { headers: { 'Content-Type': 'multipart/form-data' } });
        toast.success(res.data.message);
        setPreviewOpen(false);
        setNotifDialogOpen(false);
        setAdditionalRecipientsList([]);
        setCcNewEmail('');
        setToNewEmail('');
        setNotifFiles([]);
        setNotifAttachMatrix(false);
        fetchProject();
      } else if (previewContext?.type === 'adhoc') {
        const validRecipients = emailForm.recipients.filter(r => r.trim());
        const ccList = additionalRecipientsList.filter(e => e && e.includes('@'));
        const formData = new FormData();
        formData.append('recipients', JSON.stringify(validRecipients));
        formData.append('additional_recipients', JSON.stringify(ccList));
        formData.append('subject', editedSubject);
        formData.append('message', editedHtml);
        if (attachMatrix) formData.append('matrix_html', generateMatrixHTML());
        emailFiles.forEach(f => formData.append('files', f));
        const res = await api.post(`/projects/${projectId}/send-adhoc-email`, formData, { headers: { 'Content-Type': 'multipart/form-data' } });
        toast.success(res.data.message);
        setPreviewOpen(false);
        setEmailDialogOpen(false);
        fetchProject();
      }
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al enviar'); }
    finally { setPreviewSending(false); }
  };

  // ==================== BITÁCORA ====================
  const handleAddBitacora = async () => {
    setBitacoraSubmitting(true);
    try {
      await api.post(`/projects/${projectId}/bitacora`, { text: bitacoraText, execution_date: bitacoraDate });
      toast.success('Entrada registrada');
      setBitacoraText('');
      fetchProject();
    } catch { toast.error('Error al registrar entrada'); }
    finally { setBitacoraSubmitting(false); }
  };

  // ==================== TEMPLATE ADMIN ====================
  const openTemplatesAdmin = () => {
    fetchTemplates();
    setTemplateForm({ name: '', subject: '', body: '' });
    setEditingTemplateId(null);
    setTemplatesDialogOpen(true);
  };

  // ==================== FICHA TÉCNICA (PDF on-the-fly) ====================
  const downloadFichaTecnica = async () => {
    setFichaDownloading(true);
    try {
      const res = await api.get(`/projects/${projectId}/ficha-tecnica`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `ficha_tecnica_${project?.project_number || projectId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Ficha Técnica descargada');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al descargar la Ficha Técnica');
    } finally {
      setFichaDownloading(false);
    }
  };

  // ==================== SECURITY LOCK: TICKET NUMBER ====================
  const handleSaveTicket = async (confirmDuplicate = false) => {
    if (!ticketInput.trim()) { toast.error('Ingrese el Número de Ticket'); return; }
    setTicketSaving(true);
    try {
      await api.put(`/projects/${projectId}/ticket`, { ticket_number: ticketInput.trim(), confirm_duplicate: confirmDuplicate });
      toast.success('Ticket registrado exitosamente');
      setTicketInput('');
      setTicketDupWarning(null);
      fetchProject();
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (err.response?.status === 409 && detail && typeof detail === 'object' && detail.code === 'ticket_duplicate') {
        // Ticket ya asociado a otro proyecto → pedir confirmación al usuario.
        setTicketDupWarning(detail);
      } else {
        toast.error((typeof detail === 'string' ? detail : detail?.message) || 'Error al registrar ticket');
      }
    }
    finally { setTicketSaving(false); }
  };

  // ==================== VTID GENERATOR (PER-STORE) ====================
  const handleGenerateVTIDs = async (storeId) => {
    if (!vtidPrefix.trim()) { toast.error('Ingrese un prefijo'); return; }
    setVtidGenerating(true);
    try {
      const res = await api.post(`/projects/${projectId}/vtids/generate`, {
        prefix: vtidPrefix.trim(),
        start_number: vtidStartNumber,
        store_id: storeId || null,
      });
      toast.success(res.data.message);
      fetchProject();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al generar VTIDs'); }
    finally { setVtidGenerating(false); }
  };

  const handleDeleteVTIDs = async (storeId) => {
    setVtidDeleting(true);
    try {
      const url = storeId
        ? `/projects/${projectId}/vtids?store_id=${storeId}`
        : `/projects/${projectId}/vtids`;
      await api.delete(url);
      toast.success('VTIDs eliminados');
      fetchProject();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al eliminar VTIDs'); }
    finally { setVtidDeleting(false); }
  };

  const handleSaveTemplate = async () => {
    if (!templateForm.name.trim() || !templateForm.subject.trim()) { toast.error('Nombre y asunto son obligatorios'); return; }
    setTemplateSaving(true);
    try {
      const tid = editingTemplateId || `tpl_${Date.now()}`;
      const payload = {
        template_id: tid,
        name: templateForm.name,
        subject: templateForm.subject,
        body_html: templateForm.body,
        context: 'IMPLEMENTACION',
      };
      if (editingTemplateId) {
        await api.put(`/email-templates/${editingTemplateId}`, payload);
        toast.success('Plantilla actualizada');
      } else {
        await api.post('/email-templates', payload);
        toast.success('Plantilla creada');
      }
      setTemplateForm({ name: '', subject: '', body: '' });
      setEditingTemplateId(null);
      fetchTemplates();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error guardando plantilla'); }
    finally { setTemplateSaving(false); }
  };

  const handleDeleteTemplate = async (tid) => {
    if (!window.confirm('¿Está seguro de eliminar esta plantilla? Esta acción no se puede deshacer.')) return;
    try {
      await api.delete(`/email-templates/${tid}`);
      toast.success('Plantilla eliminada');
      if (editingTemplateId === tid) { setEditingTemplateId(null); setTemplateForm({ name: '', subject: '', body: '' }); }
      fetchTemplates();
    } catch { toast.error('Error eliminando plantilla'); }
  };

  // ==================== HELPERS ====================
  if (loading || !project) {
    return (<div className="flex min-h-screen bg-white"><Sidebar /><div className="flex-1 flex items-center justify-center"><div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-green-600" /></div></div>);
  }

  const isMultistore = project.project_type === 'multistore';
  const isMultiRif = project.project_type === 'multirif';
  const isLocked = !!project.assigned_to_name && !project.ticket_number;
  const clientNotified = project.client_notified === true;
  const bankNotifications = project.bank_notifications || {};
  const matrix = project.implementation_matrix || {};
  const bankNames = Object.keys(matrix);
  const rollup = project.rollup_progress || {};

  const calcStoreProgress = (store) => {
    const sm = store.implementation_matrix || {};
    let completed = 0, total = 0;
    Object.values(sm).forEach(products => {
      Object.values(products).forEach(phases => {
        STORE_PHASES.forEach(p => { total++; if (phases[p]?.completed) completed++; });
      });
    });
    return total > 0 ? Math.round((completed / total) * 100) : 0;
  };

  const clientHistory = (project.notification_history || {}).client || [];
  const clientExecutedLevels = clientHistory.map(h => h.level);

  return (
    <div className="flex min-h-screen bg-white">
      <Sidebar />
      <main className="flex-1 p-8" data-testid="project-detail-page">
        <div className="max-w-7xl mx-auto">
          <Button variant="ghost" onClick={() => navigate('/projects')} className="mb-4 text-slate-600">
            <ArrowLeft size={16} className="mr-2" />Volver a Proyectos
          </Button>

          {/* Header */}
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-6 mb-6">
            {/* Fila superior: Título + Estado + Acciones */}
            <div className="flex items-start justify-between mb-5 gap-4">
              <h1 className="text-2xl font-bold text-slate-900" data-testid="project-title">Detalle para Implementación del Proyecto</h1>
              <div className="flex flex-col items-end gap-2 shrink-0">
                <span className={`inline-block px-3 py-1 rounded-full text-sm font-medium border ${
                  project.status === 'Por asignar' ? 'bg-amber-100 text-amber-800 border-amber-200' :
                  project.status === 'Asignado' ? 'bg-blue-100 text-blue-800 border-blue-200' :
                  project.status === 'En Gestión' ? 'bg-indigo-100 text-indigo-800 border-indigo-200' :
                  project.status === 'Suspendido' ? 'bg-red-100 text-red-800 border-red-200' :
                  project.status === 'Implementado parcial' ? 'bg-orange-100 text-orange-800 border-orange-200' :
                  'bg-emerald-100 text-emerald-800 border-emerald-200'
                }`} data-testid="project-status">{project.status}</span>
                {isMultistore && (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-full bg-blue-100 text-blue-700 border border-blue-200">
                    <Store size={12} />Multitienda ({project.stores?.length || 0})
                  </span>
                )}
                {rollup.global_progress !== undefined && (
                  <div className="flex items-center gap-2 w-40">
                    <div className="flex-1 bg-slate-100 rounded-full h-2 overflow-hidden">
                      <div className={`h-full rounded-full transition-all duration-500 ${rollup.global_progress >= 100 ? 'bg-emerald-500' : rollup.global_progress >= 50 ? 'bg-blue-500' : 'bg-amber-400'}`} style={{ width: `${Math.min(rollup.global_progress, 100)}%` }} />
                    </div>
                    <span className="text-xs font-bold text-slate-700" data-testid="header-progress">{rollup.global_progress}%</span>
                  </div>
                )}
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => setProgressReportOpen(true)} className="text-xs gap-1 border-sky-200 text-sky-700 hover:bg-sky-50 h-7 px-2" data-testid="open-progress-report-btn">
                    <FileBarChart size={12} />Reporte de Avance
                  </Button>
                  <Button variant="outline" size="sm" onClick={openEmailDialog} className="text-xs gap-1 border-indigo-200 text-indigo-600 hover:bg-indigo-50 h-7 px-2" data-testid="adhoc-email-btn">
                    <Megaphone size={12} />Otras Notificaciones
                  </Button>
                  {(() => {
                    const isAssignedImpl = currentUser.user_id && currentUser.user_id === project.assigned_to_user_id;
                    const cargo = (currentUser.cargo || '').toLowerCase();
                    const isCoordAdmin = (currentUser.role || '').toLowerCase() === 'admin' || cargo === 'coordinador' || cargo === 'gerente';
                    if (!(isAssignedImpl || isCoordAdmin)) return null;
                    const activeAlerts = (project.implementer_alerts || []).filter(a => !a.completed).length;
                    return (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setAlertsOpen(true)}
                        className="text-xs gap-1 border-amber-300 text-amber-700 hover:bg-amber-50 h-7 px-2 relative"
                        data-testid="open-implementer-alerts-btn"
                        title={isAssignedImpl ? 'Gestionar mis recordatorios personales' : 'Supervisión de alertas del implementador (solo lectura)'}
                      >
                        <BellRing size={12} />Mis Alertas
                        {activeAlerts > 0 && (
                          <span className="ml-1 inline-flex items-center justify-center rounded-full bg-amber-600 text-white text-[10px] font-bold px-1.5 min-w-[16px] h-[16px]" data-testid="implementer-alerts-badge">
                            {activeAlerts}
                          </span>
                        )}
                      </Button>
                    );
                  })()}
                  <Button variant="outline" size="sm" onClick={downloadFichaTecnica} disabled={fichaDownloading} className="text-xs gap-1 border-emerald-200 text-emerald-700 hover:bg-emerald-50 h-7 px-2" data-testid="download-ficha-tecnica-btn">
                    <FileDown size={12} />{fichaDownloading ? 'Generando...' : 'Ficha Técnica'}
                  </Button>
                  <Button variant="outline" size="sm" onClick={openTemplatesAdmin} className="text-xs gap-1 border-slate-200 text-slate-600 hover:bg-slate-50 h-7 px-2" data-testid="manage-templates-btn">
                    <ClipboardList size={12} />Plantillas
                  </Button>
                </div>
              </div>
            </div>

            {/* Compromisos Gerenciales — banner sticky si hay activos */}
            {(() => {
              const active = (project.commitments || []).filter(c => !c.completed);
              if (active.length === 0) return null;
              return (
                <div
                  className="sticky top-0 z-10 bg-gradient-to-r from-red-600 to-red-500 text-white rounded-lg p-4 mb-4 shadow-lg border-2 border-red-700 animate-pulse-slow"
                  data-testid="commitments-banner"
                >
                  <div className="flex items-start gap-3">
                    <Flag size={22} className="shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <p className="font-bold text-sm uppercase tracking-wide">
                        Compromiso gerencial pendiente ({active.length})
                      </p>
                      {active.slice(0, 2).map((c) => {
                        const overdue = c.deadline && new Date(c.deadline) < new Date();
                        return (
                          <p key={c.commitment_id} className="text-sm mt-1" data-testid={`commitment-banner-${c.commitment_id}`}>
                            <b>{c.created_by_name}</b> ({c.created_by_role}): {c.message}
                            {c.deadline && (
                              <span className={`ml-2 text-xs ${overdue ? 'bg-yellow-400 text-red-900 font-bold' : 'bg-white/20'} px-2 py-0.5 rounded`}>
                                {overdue ? 'VENCIDO: ' : 'Límite: '}{new Date(c.deadline).toLocaleDateString('es-VE')}
                              </span>
                            )}
                          </p>
                        );
                      })}
                      {active.length > 2 && (
                        <p className="text-xs opacity-80 mt-1">+ {active.length - 2} compromiso(s) más...</p>
                      )}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCommitmentsOpen(true)}
                      className="bg-white hover:bg-red-50 text-red-700 border-white font-semibold whitespace-nowrap"
                      data-testid="commitments-banner-open-btn"
                    >
                      Ver / Gestionar
                    </Button>
                  </div>
                </div>
              );
            })()}

            {/* Bloques de información en grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              {/* Bloque 1: Datos del Proyecto */}
              <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-3">
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Datos del Proyecto</p>
                {(project.quote_type || project.project_type_impl) && (
                  <div>
                    <p className="text-xs text-slate-500">Tipo de Proyecto</p>
                    <p className="text-sm font-semibold text-slate-700" data-testid="project-type-impl">
                      {(() => {
                        // Heredado obligatoriamente del "Tipo de Cotización" origen.
                        const qt = (project.quote_type || '').toUpperCase();
                        if (qt === 'VPOS') return 'VPOS';
                        if (qt === 'MPOS' || qt === 'FAST_TRACK') return 'MPOS';
                        if (qt === 'GATEWAY') return 'Payment Gateway';
                        if (qt === 'LINK_PAGO' || qt === 'LINK') return 'Link de Pago';
                        // Fallback legacy al project_type_impl si no hay quote_type mapeable.
                        return project.project_type_impl === 'pos_fast_track' ? 'MPOS' :
                               project.project_type_impl === 'vpos_mpos' ? 'VPOS' :
                               project.project_type_impl === 'payment_gateway' ? 'Payment Gateway' : (project.project_type_impl || qt || '—');
                      })()}
                    </p>
                  </div>
                )}
                <div>
                  <p className="text-xs text-slate-500">Ticket</p>
                  {project.ticket_number ? (
                    <p className="text-base font-bold text-indigo-700 flex items-center gap-1.5" data-testid="project-ticket">
                      <Ticket size={15} className="text-indigo-500" />{project.ticket_number}
                    </p>
                  ) : <p className="text-sm font-semibold text-slate-600">Sin asignar</p>}
                </div>
                <div>
                  <p className="text-xs text-slate-500">N. Proyecto</p>
                  <p className="text-sm font-semibold text-slate-700">{project.project_number}</p>
                </div>
                {project.quote_number && (
                  <div>
                    <p className="text-xs text-slate-500">Cotización Origen</p>
                    <p className="text-sm font-mono font-semibold text-blue-700" data-testid="project-quote-number-ref">
                      {project.quote_number}
                    </p>
                  </div>
                )}
                <div>
                  <p className="text-xs text-slate-500">Cliente</p>
                  <p className="text-sm font-semibold text-slate-700">{project.client_name}</p>
                  <p className="text-xs text-slate-400">{formatRif(project.client_rif)} — {project.client_sede}</p>
                </div>
                {/* Datos Comerciales: Grupo Económico + Nombre de Fantasía */}
                <div className="pt-2 mt-2 border-t border-slate-100 space-y-2">
                  <div>
                    <p className="text-xs text-slate-500">Grupo Económico</p>
                    <p className="text-sm font-semibold text-slate-700" data-testid="economic-group">{project.economic_group || 'Sin Grupo Económico'}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Nombre de Fantasía</p>
                    <p className="text-sm font-semibold text-slate-700" data-testid="fantasy-name">{project.fantasy_name || project.client_name || '—'}</p>
                  </div>
                </div>
              </div>

              {/* Bloque 2: Implementación (incluye servidor + integrador/aplicativo) */}
              <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-3">
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Implementación</p>
                {/* Integrador y Aplicativo (movidos desde el header) */}
                {editingIntegrator ? (
                  <div className="space-y-2 pb-2 border-b border-slate-100">
                    <div>
                      <p className="text-xs text-slate-500 mb-1">Integrador</p>
                      <Select value={integratorName} onValueChange={(v) => {
                        if (v === 'Stand Alone') {
                          setIntegratorName('Stand Alone');
                          setApplicationName('');
                        } else {
                          const integ = integratorsList.find(i => i.integrator_id === v);
                          if (integ) {
                            setIntegratorName(integ.name);
                            setApplicationName(integ.app_name || '');
                          }
                        }
                      }}>
                        <SelectTrigger className="h-7 text-xs" data-testid="integrator-select">
                          <SelectValue placeholder="Seleccione integrador..." />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="Stand Alone">Stand Alone</SelectItem>
                          {integratorsList.map(integ => (
                            <SelectItem key={integ.integrator_id} value={integ.integrator_id}>
                              {integ.name}{integ.app_name ? ` — ${integ.app_name}` : ''}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500 mb-1">Aplicativo</p>
                      <Input value={applicationName} onChange={e => setApplicationName(e.target.value)}
                        placeholder="Se autocompleta del integrador" className="h-7 text-xs" data-testid="application-input" />
                    </div>
                    <div>
                      <p className="text-xs text-slate-500 mb-1">Cantidad de Cajas/Terminales</p>
                      <Input type="number" min={0} value={boxCount} onChange={e => setBoxCount(parseInt(e.target.value) || 0)}
                        placeholder="Ej: 5" className="h-7 text-xs w-24" data-testid="box-count-input" />
                    </div>
                    <div className="flex gap-1">
                      <Button size="sm" className="h-6 text-[10px]" onClick={saveIntegratorFields}>Guardar</Button>
                      <Button size="sm" variant="ghost" className="h-6 text-[10px]" onClick={() => setEditingIntegrator(false)}>Cancelar</Button>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-2 pb-2 border-b border-slate-100">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-xs text-slate-500">Integrador</p>
                        <p className="text-sm font-semibold text-slate-700" data-testid="integrator-name">{project.integrator_name || 'Stand Alone'}</p>
                      </div>
                      {canEditMatrix && (
                        <button onClick={() => setEditingIntegrator(true)} className="text-slate-400 hover:text-blue-500" data-testid="edit-integrator-btn">
                          <Edit2 size={12} />
                        </button>
                      )}
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Aplicativo</p>
                      <p className="text-sm font-semibold text-slate-700" data-testid="application-name">{project.integrator_app_name || project.application_name || '—'}</p>
                    </div>
                    {/* Iter39: Nro de Cajas + Nro de PVV — informativos read-only.
                        PVV es el mismo valor del Resumen Ejecutivo bajo "Total de Terminales Virtuales". */}
                    <div className="grid grid-cols-2 gap-3 pt-1">
                      <div>
                        <p className="text-xs text-slate-500">Nro de Cajas</p>
                        <p className="text-sm font-semibold text-slate-700" data-testid="project-nro-cajas">
                          {project.cantidad_cajas || project.box_count || 0}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">Nro de PVV <span className="text-[10px] text-slate-400">(Cajas × Bancos × Productos)</span></p>
                        <p className="text-sm font-bold text-indigo-700" data-testid="project-nro-pvv">
                          {project.pvv_count ?? 0}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
                <div className="flex items-center gap-3">
                  <CreditCard size={18} className="text-emerald-600 shrink-0" />
                  <div>
                    <p className="text-xs text-slate-500">Modelo de Pinpad</p>
                    <p className="text-sm font-semibold text-slate-700" data-testid="pinpad-model">{project.pinpad_model || '—'}</p>
                  </div>
                </div>
                {/* Patrocinador de Pinpads (entidad que patrocina/asocia los terminales) */}
                <div className="flex items-center gap-3">
                  <Building2 size={18} className="text-blue-600 shrink-0" />
                  <div>
                    <p className="text-xs text-slate-500">Patrocinador de Pinpads</p>
                    <p className="text-sm font-semibold text-slate-700" data-testid="sponsor-bank">
                      {project.sponsor_processor_name && project.sponsor_bank_name
                        ? `${project.sponsor_processor_name} — ${project.sponsor_bank_name}`
                        : (project.sponsor_bank_name || project.sponsor_processor_name || '—')}
                    </p>
                  </div>
                </div>
                {/* Patrocinador de la Implementación (Implementación Patrocinada): Banco directo o Procesador — Banco */}
                <div className="flex items-center gap-3">
                  <Landmark size={18} className="text-indigo-600 shrink-0" />
                  <div>
                    <p className="text-xs text-slate-500">Patrocinador de la Implementación</p>
                    <p className="text-sm font-semibold text-slate-700" data-testid="project-detail-patrocinador">
                      {project.patrocinador_label
                        || (project.sponsored_implementation && project.sponsoring_bank_name
                              ? (project.sponsoring_processor_name
                                    ? `${project.sponsoring_processor_name} — ${project.sponsoring_bank_name}`
                                    : project.sponsoring_bank_name)
                              : '—')}
                    </p>
                  </div>
                </div>
                {project.assigned_to_name && (
                  <div className="flex items-center gap-3 pt-1 mt-1 border-t border-slate-100">
                    <User size={18} className="text-violet-600 shrink-0" />
                    <div>
                      <p className="text-xs text-slate-500">Implementador</p>
                      <p className="text-sm font-semibold text-slate-700">{project.assigned_to_name}</p>
                      {(project.fecha_asignacion || project.assigned_at) && (
                        <p className="text-[10px] text-slate-400">Asignado el: {new Date(project.fecha_asignacion || project.assigned_at).toLocaleDateString('es-VE')}</p>
                      )}
                    </div>
                  </div>
                )}
                {(project.server_name || project.communication_type) && (
                  <div className="flex items-center gap-6 pt-1 mt-1 border-t border-slate-100" data-testid="server-comm-row">
                    {project.server_name && (
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <Server size={18} className="text-blue-600 shrink-0" />
                        <div className="min-w-0">
                          <p className="text-xs text-slate-500">Servidor de Instalación</p>
                          <p className="text-sm font-semibold text-blue-700 truncate" data-testid="server-name">{project.server_name}</p>
                        </div>
                      </div>
                    )}
                    {project.communication_type && (
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <Network size={18} className="text-cyan-600 shrink-0" />
                        <div className="min-w-0">
                          <p className="text-xs text-slate-500">Tipo de Comunicación</p>
                          <p className="text-sm font-semibold text-cyan-700" data-testid="communication-type">{project.communication_type}</p>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Bloque 2.5: Equipos Vinculados — Grid Horizontal con scroll cap (6 filas). */}
              {project.equipments && project.equipments.length > 0 && (
                <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-2" data-testid="equipment-section">
                  <div className="flex items-center justify-between">
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Modelo y Seriales de Equipos</p>
                    <span className="text-[10px] font-bold text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded">
                      {project.equipments.length}
                    </span>
                  </div>
                  <div
                    className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-[336px] overflow-y-auto pr-1"
                    data-testid="equipment-grid"
                  >
                    {project.equipments.map((eq, idx) => (
                      <div key={idx} className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2" data-testid={`equipment-row-${idx}`}>
                        <p className="text-[10px] text-slate-500 truncate">{eq.modelo}</p>
                        <p className="text-xs font-mono font-bold text-slate-800">S/N: {eq.serial}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Provisión de seriales por un tercero (Infraestructura/Cliente/Banco) */}
              {project.serials_provider_note && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-start gap-3" data-testid="serials-provider-note-section">
                  <Landmark size={18} className="text-blue-600 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-[10px] font-bold text-blue-500 uppercase tracking-wider">Provisión de Seriales</p>
                    <p className="text-sm font-semibold text-blue-800 mt-0.5" data-testid="serials-provider-note">{project.serials_provider_note}</p>
                  </div>
                </div>
              )}

              {/* Bloque 2.7: Pinpads desde Inventario (PYME) — Grid Horizontal con scroll cap (6 filas).
                  Iter40: limitado a max ~6 filas con barra de scroll para evitar que listas largas
                  empujen el resto del detalle hacia abajo. */}
              {project.pinpad_serials && project.pinpad_serials.length > 0 && (
                <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-2" data-testid="pinpad-serials-section">
                  <div className="flex items-center justify-between">
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">POS / Pinpad (Inventario)</p>
                    <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded" data-testid="pinpad-serials-count">
                      {project.pinpad_serials.length}
                    </span>
                  </div>
                  <div
                    className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-[336px] overflow-y-auto pr-1"
                    data-testid="pinpad-serials-grid"
                  >
                    {project.pinpad_serials.map((pp, idx) => (
                      <div key={idx} className="bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2" data-testid={`pinpad-serial-row-${idx}`}>
                        <p className="text-[10px] text-emerald-600 truncate">{pp.modelo}</p>
                        <p className="text-xs font-mono font-bold text-emerald-800">S/N: {pp.serial}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Bloque: Seriales de Implementación (esquina superior derecha).
                  Iter41: se oculta cuando los seriales ya vienen precargados desde
                  "POS/Pinpad (Inventario)" o "Modelo y Seriales de Equipos" para evitar
                  redundancia visual y confusión del implementador. */}
              {((project.pinpad_serials || []).length === 0 && (project.equipments || []).length === 0) && (
                <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-2" data-testid="impl-serials-section">
                  <div className="flex items-center justify-between">
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Seriales (Implementacion)</p>
                    <span className="text-[10px] font-bold text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">{(project.implementation_serials || []).length}</span>
                  </div>
                  {(project.implementation_serials || []).length > 0 && (
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-1 max-h-28 overflow-y-auto">
                      {(project.implementation_serials || []).map((s, idx) => (
                        <div key={idx} className="bg-slate-50 border rounded px-2 py-1 flex items-center justify-between gap-1">
                          <span className="text-[10px] font-mono font-bold text-slate-700 truncate">{s}</span>
                          {canEditMatrix && <button onClick={() => removeSerial(s)} className="text-slate-300 hover:text-red-500 shrink-0"><X size={10} /></button>}
                        </div>
                      ))}
                    </div>
                  )}
                  {canEditMatrix && (
                    <div className="flex gap-1 mt-1">
                      <Input value={serialInput} onChange={e => setSerialInput(e.target.value)}
                        placeholder="Serial(es) separados por coma" className="h-7 text-[10px] flex-1"
                        onKeyDown={e => e.key === 'Enter' && handleSerialManualAdd()} data-testid="serial-input" />
                      <Button size="sm" className="h-7 text-[10px] px-2" onClick={handleSerialManualAdd} disabled={serialUploading} data-testid="serial-add-btn">+</Button>
                      <input ref={serialFileRef} type="file" accept=".csv,.xlsx,.xls,.txt" className="hidden" onChange={handleSerialFileUpload} />
                      <Button size="sm" variant="outline" className="h-7 text-[10px] px-2" onClick={() => serialFileRef.current?.click()} disabled={serialUploading} data-testid="serial-excel-btn">Excel</Button>
                    </div>
                  )}
                </div>
              )}

            </div>
          </div>

          {/* ============ SECURITY LOCK: TICKET REQUIRED ============ */}
          {project.assigned_to_name && !project.ticket_number && (
            <div className="mb-6 bg-amber-50 border-2 border-amber-300 rounded-xl p-5" data-testid="security-lock-banner">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-full bg-amber-100 flex items-center justify-center shrink-0">
                  <Shield size={24} className="text-amber-600" />
                </div>
                <div className="flex-1">
                  <h3 className="text-base font-bold text-amber-900">Proyecto Bloqueado — Ticket Requerido</h3>
                  <p className="text-sm text-amber-700 mt-1">Para desbloquear las funciones de ejecución, registre el Número de Ticket proporcionado por el sistema de gestión.</p>
                  <div className="flex items-end gap-3 mt-3">
                    <div className="flex-1 max-w-sm">
                      <Label className="text-xs font-medium text-amber-800">Número de Ticket</Label>
                      <Input
                        placeholder="Ej: TK-2026-0001"
                        value={ticketInput}
                        onChange={e => setTicketInput(e.target.value)}
                        className="mt-1 h-9 border-amber-300 focus:ring-amber-400"
                        data-testid="security-lock-ticket-input"
                      />
                    </div>
                    <Button
                      onClick={() => handleSaveTicket()}
                      disabled={ticketSaving || !ticketInput.trim()}
                      className="h-9 bg-amber-600 hover:bg-amber-700 text-white gap-1.5"
                      data-testid="security-lock-save-btn"
                    >
                      <Lock size={14} />{ticketSaving ? 'Guardando...' : 'Desbloquear'}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Confirmación: Ticket ya asociado a otro proyecto (carga flexible) */}
          <AlertDialog open={!!ticketDupWarning} onOpenChange={(o) => { if (!o) setTicketDupWarning(null); }}>
            <AlertDialogContent data-testid="ticket-duplicate-dialog">
              <AlertDialogHeader>
                <AlertDialogTitle>Ticket ya asociado a otro proyecto</AlertDialogTitle>
                <AlertDialogDescription data-testid="ticket-duplicate-message">
                  {ticketDupWarning?.message}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel data-testid="ticket-duplicate-cancel">Cancelar</AlertDialogCancel>
                <AlertDialogAction
                  onClick={() => handleSaveTicket(true)}
                  className="bg-amber-600 hover:bg-amber-700"
                  data-testid="ticket-duplicate-confirm"
                >
                  Sí, asignar de todos modos
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>

          {/* ============ NOTIFICATION SECTION ============ */}
          <div className="mb-6">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-bold text-slate-900">Matriz de Implementación</h2>
              <div className="flex items-center gap-2">
                {/* Actualización Masiva — proyectos multitienda y Multi-RIF */}
                {(isMultistore || isMultiRif) && canEditMatrix && clientNotified && (
                  <Button
                    onClick={openBatchModal}
                    className="gap-2 bg-amber-500 hover:bg-amber-600 text-white"
                    data-testid="batch-update-btn"
                  >
                    <Layers size={16} />
                    Actualización Masiva
                  </Button>
                )}
                {/* Notificación Única para proyectos Single con un solo banco */}
                {!isMultistore && bankNames.length === 1 && (
                  <Button
                    onClick={() => openNotifDialog('bank_client', bankNames[0])}
                    disabled={isLocked}
                    className={`gap-2 ${isLocked ? 'bg-slate-300 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-700'} text-white`}
                    data-testid="notif-bank-client-btn"
                  >
                    <BellRing size={16} />
                    Notificación Única (Cliente y Banco)
                  </Button>
                )}
                {/* Botón Notificaciones general — se oculta en Single con 1 banco (usa Notificación Única) */}
                {!(!isMultistore && bankNames.length === 1) && (
                  <Button onClick={() => openNotifDialog('client')} disabled={isLocked} className={`gap-2 ${isLocked ? 'bg-slate-300 cursor-not-allowed' : clientNotified ? 'bg-emerald-500 hover:bg-emerald-600' : 'bg-amber-500 hover:bg-amber-600'} text-white`} data-testid="notifications-btn">
                    {clientNotified ? <BellRing size={16} /> : <Bell size={16} />}
                    Notificaciones a Cliente
                  </Button>
                )}
              </div>
            </div>

            {/* Hard Stop */}
            {!clientNotified && (
              <div className="bg-slate-50 border-2 border-dashed border-slate-300 rounded-xl p-10 text-center" data-testid="matrix-locked">
                <Lock size={40} className="mx-auto text-slate-300 mb-3" />
                <p className="text-sm font-semibold text-slate-500">Matriz Bloqueada</p>
                <p className="text-xs text-slate-400 mt-1">Ejecute la "Primera Comunicación" al cliente para desbloquear</p>
              </div>
            )}

            {/* Main Matrix */}
            {clientNotified && (
              <>
                {isMultistore ? (
                  <div className="mb-3 bg-blue-50 border border-blue-200 rounded-lg p-3">
                    <div className="flex items-center justify-between">
                      <p className="text-sm text-blue-800 font-medium flex items-center gap-2"><Store size={16} className="text-blue-600" />Multitienda — Solo lectura (avance automático)</p>
                      {rollup.global_progress !== undefined && <span className="text-sm font-bold text-blue-900" data-testid="rollup-global-progress"><BarChart3 size={14} className="inline mr-1" />Avance Global: {rollup.global_progress}%</span>}
                    </div>
                  </div>
                ) : (rollup.global_progress > 0 && (
                  <div className="mb-3 bg-emerald-50 border border-emerald-200 rounded-lg p-3">
                    <div className="flex items-center justify-between">
                      <p className="text-sm text-emerald-800 font-medium flex items-center gap-2"><BarChart3 size={16} className="text-emerald-600" />Avance de Implementación</p>
                      <span className="text-sm font-bold text-emerald-900" data-testid="single-progress">{rollup.global_progress}%</span>
                    </div>
                  </div>
                ))}

                {bankNames.length === 0 ? (
                  <div className="text-center py-10 bg-slate-50 rounded-lg border"><p className="text-slate-400">No hay datos en la matriz</p></div>
                ) : (
                  <div className="overflow-x-auto rounded-lg border border-slate-200">
                    <table className="w-full" data-testid="implementation-matrix">
                      <thead>
                        <tr>
                          <th className="bg-blue-600 text-white px-4 py-3 text-left text-sm font-semibold min-w-[200px]">Bancos / Productos</th>
                          {isMultistore ? (
                            <th className="bg-blue-600 text-white px-4 py-3 text-center text-sm font-semibold min-w-[300px]">Avance (Roll-up)</th>
                          ) : PHASES.map(phase => (
                            <th key={phase} className={`px-3 py-3 text-center text-xs font-semibold border-l border-slate-200 min-w-[100px] ${PHASE_COLORS[phase]}`}>{phase}</th>
                          ))}
                          <th className="bg-blue-600 text-white px-3 py-3 text-center text-xs font-semibold border-l border-slate-200 min-w-[130px]">Notificaciones</th>
                        </tr>
                      </thead>
                      <tbody>
                        {bankNames.map(bankName => {
                          const products = Object.keys(matrix[bankName]);
                          const bankHistory = (project.notification_history || {})[`bank_${bankName}`] || [];
                          const bankExecutedLevels = bankHistory.map(h => h.level);
                          return (isMultistore || isMultiRif) ? (
                            <MultistoreBankSection key={bankName} bankName={bankName} products={products}
                              rollupBankData={rollup.bank_progress?.[bankName] || {}}
                              bankExecutedLevels={bankExecutedLevels} onOpenNotif={() => openNotifDialog('bank', bankName)} />
                          ) : (
                            <SingleBankSection key={bankName} bankName={bankName} products={products}
                              matrixData={matrix[bankName]} onUpdateQuantity={updateMatrixQuantity}
                              onUpdateCascade={updateMatrixCascade} onFillPhase={fillPhaseToExpected}
                              bankExecutedLevels={bankExecutedLevels} onOpenNotif={() => openNotifDialog('bank', bankName)}
                              readOnly={!canEditMatrix} expectedQty={project.box_count || project.cantidad_cajas || 0}
                              hideBankNotif={bankNames.length === 1} />
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </div>

          {/* ============ MULTI-RIF TREE (3 niveles) ============ */}
          {isMultiRif && clientNotified && (project.rifs?.length > 0 || project.stores?.length > 0) && (
            <MultiRifTree
              project={project}
              canEditMatrix={canEditMatrix}
              onUpdateStoreQuantity={updateStoreMatrixQuantity}
              onUpdateStoreCascade={updateStoreMatrixCascade}
              onFillStorePhase={fillStorePhaseToExpected}
            />
          )}

          {/* ============ MULTISTORE STORES ============ */}
          {isMultistore && clientNotified && project.stores?.length > 0 && (
            <div className="mb-6" data-testid="multistore-section">
              <h2 className="text-lg font-bold text-slate-900 mb-3 flex items-center gap-2"><Store size={20} className="text-blue-600" />Seguimiento por Tienda ({project.stores.length})</h2>
              <div className="flex gap-2 mb-4 flex-wrap">
                {project.stores.map((store) => {
                  const progress = calcStoreProgress(store);
                  const isActive = selectedStoreId === store.store_id;
                  return (
                    <button key={store.store_id} onClick={() => setSelectedStoreId(isActive ? null : store.store_id)}
                      className={`px-4 py-2.5 rounded-lg border text-sm font-medium transition-all ${isActive ? 'bg-blue-600 text-white border-blue-600 shadow-sm' : 'bg-white text-slate-700 border-slate-200 hover:border-blue-300 hover:bg-blue-50'}`}
                      data-testid={`store-tab-${store.store_id}`}>
                      <span className="font-semibold">{store.name}</span>
                      <span className={`ml-2 text-xs ${isActive ? 'text-blue-200' : 'text-slate-400'}`}>{store.box_count} caja{store.box_count !== 1 ? 's' : ''} · {progress}%</span>
                    </button>
                  );
                })}
              </div>
              {selectedStoreId && (() => {
                const store = project.stores.find(s => s.store_id === selectedStoreId);
                if (!store) return null;
                const storeMatrix = store.implementation_matrix || {};
                const storeBankNames = Object.keys(storeMatrix);
                return (
                  <div className="bg-white rounded-lg border border-blue-200 p-4" data-testid={`store-matrix-${store.store_id}`}>
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <h3 className="text-base font-bold text-slate-900 flex items-center gap-2"><Store size={16} className="text-blue-600" />{store.name}</h3>
                        <p className="text-xs text-slate-500">{store.box_count} caja{store.box_count !== 1 ? 's' : ''} · Avance: {calcStoreProgress(store)}%</p>
                      </div>
                    </div>
                    {storeBankNames.length === 0 ? (
                      <p className="text-sm text-slate-400 text-center py-6">Sin datos en la matriz</p>
                    ) : (
                      <div className="overflow-x-auto rounded-lg border border-slate-200">
                        <table className="w-full">
                          <thead><tr>
                            <th className="bg-blue-600 text-white px-4 py-2.5 text-left text-xs font-semibold min-w-[200px]">Bancos / Productos</th>
                            {STORE_PHASES.map(p => <th key={p} className={`px-3 py-2.5 text-center text-xs font-semibold border-l border-slate-200 min-w-[100px] ${PHASE_COLORS[p]}`}>{p}</th>)}
                            <th className="bg-blue-600 text-white px-3 py-2.5 text-center text-xs font-semibold border-l border-slate-200">Avance</th>
                          </tr></thead>
                          <tbody>
                            {storeBankNames.map(bk => (
                              <StoreBankSection key={bk} bankName={bk} products={Object.keys(storeMatrix[bk])}
                                matrixData={storeMatrix[bk]} storeId={store.store_id}
                                onUpdateStoreQuantity={updateStoreMatrixQuantity}
                                onUpdateStoreCascade={updateStoreMatrixCascade}
                                onFillStorePhase={fillStorePhaseToExpected}
                                phases={STORE_PHASES} readOnly={!canEditMatrix} expectedQty={store.box_count || 0} />
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                );
              })()}
            </div>
          )}

          {/* ============ VTID GENERATOR (COLAPSABLE) ============ */}
          {project.ticket_number && (
            <div className="mb-6" data-testid="vtid-section">
              <button
                type="button"
                onClick={() => setVtidCollapsed(prev => !prev)}
                className="w-full flex items-center justify-between px-4 py-3 bg-white border border-slate-200 rounded-xl hover:bg-slate-50 transition-colors mb-3"
                data-testid="vtid-toggle-btn"
              >
                <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                  <Hash size={20} className="text-indigo-600" />
                  Terminales Virtuales (VTID)
                  <span className="text-xs font-normal text-slate-400 ml-2">
                    ({isMultistore
                      ? `${(project.stores || []).filter(s => (s.vtids || []).length > 0).length}/${(project.stores || []).length} con VTIDs`
                      : `${(project.vtids || []).length} VTID(s)`})
                  </span>
                </h2>
                <ChevronDown
                  size={18}
                  className={`text-slate-400 transition-transform ${vtidCollapsed ? '' : 'rotate-180'}`}
                />
              </button>

              {!vtidCollapsed && (<>
              {isMultistore ? (
                /* MULTITIENDA: VTIDs por sucursal */
                <div className="space-y-4">
                  {(project.stores || []).map(store => {
                    const storeVtids = store.vtids || [];
                    const hasVtids = storeVtids.length > 0;
                    return (
                      <div key={store.store_id} className="bg-white border border-slate-200 rounded-xl overflow-hidden" data-testid={`vtid-store-${store.store_id}`}>
                        <div className={`px-4 py-3 border-b flex items-center justify-between ${hasVtids ? 'bg-indigo-50 border-indigo-200' : 'bg-slate-50 border-slate-200'}`}>
                          <div>
                            <p className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                              <Store size={14} className="text-blue-600" />{store.name}
                              <span className="text-xs font-normal text-slate-500">({store.box_count} caja{store.box_count !== 1 ? 's' : ''})</span>
                            </p>
                            {hasVtids && (
                              <p className="text-[10px] text-indigo-500 mt-0.5">
                                Prefijo: <span className="font-bold">{store.vtid_prefix}</span>
                                {store.vtid_generated_by && <> · {store.vtid_generated_by}</>}
                                {store.vtid_generated_at && <> · {new Date(store.vtid_generated_at).toLocaleDateString('es-VE')}</>}
                              </p>
                            )}
                          </div>
                          {hasVtids ? (
                            <Button variant="outline" size="sm" onClick={() => handleDeleteVTIDs(store.store_id)}
                              disabled={vtidDeleting} className="h-7 text-xs text-red-500 border-red-200 hover:bg-red-50 gap-1"
                              data-testid={`vtid-delete-${store.store_id}`}>
                              <Trash2 size={12} />{vtidDeleting ? '...' : 'Eliminar'}
                            </Button>
                          ) : (
                            <div className="flex items-end gap-2">
                              <Input placeholder="Prefijo" value={vtidPrefix} onChange={e => setVtidPrefix(e.target.value.toUpperCase())}
                                className="h-8 w-24 text-xs border-indigo-300 uppercase" maxLength={10} data-testid={`vtid-prefix-${store.store_id}`} />
                              <Input type="number" min={1} value={vtidStartNumber} onChange={e => setVtidStartNumber(parseInt(e.target.value) || 1)}
                                className="h-8 w-16 text-xs border-indigo-300" data-testid={`vtid-start-${store.store_id}`} />
                              <Button size="sm" onClick={() => handleGenerateVTIDs(store.store_id)}
                                disabled={vtidGenerating || !vtidPrefix.trim()}
                                className="h-8 text-xs bg-indigo-600 hover:bg-indigo-700 text-white gap-1"
                                data-testid={`vtid-generate-${store.store_id}`}>
                                <Hash size={12} />{vtidGenerating ? '...' : 'Generar'}
                              </Button>
                            </div>
                          )}
                        </div>
                        {hasVtids && (
                          <div className="p-3">
                            <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-8 gap-1.5">
                              {storeVtids.map((vtid, idx) => (
                                <div key={vtid.vtid_id || idx}
                                  className="px-2 py-1.5 rounded bg-slate-50 border border-slate-200 text-center"
                                  data-testid={`vtid-${store.store_id}-${idx}`}>
                                  <p className="text-xs font-bold font-mono text-indigo-700">{vtid.code}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                /* TIENDA ÚNICA: VTIDs a nivel de proyecto */
                (!project.vtids || project.vtids.length === 0) ? (
                  <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-5">
                    <p className="text-sm text-indigo-700 mb-3">Genere los IDs de terminales virtuales. Se creará uno por cada caja registrada.</p>
                    <div className="flex items-end gap-3 flex-wrap">
                      <div>
                        <Label className="text-xs font-medium text-indigo-800">Prefijo</Label>
                        <Input placeholder="Ej: MS, VT" value={vtidPrefix} onChange={e => setVtidPrefix(e.target.value.toUpperCase())}
                          className="mt-1 h-9 w-32 border-indigo-300 uppercase" maxLength={10} data-testid="vtid-prefix-input" />
                      </div>
                      <div>
                        <Label className="text-xs font-medium text-indigo-800">Inicio</Label>
                        <Input type="number" min={1} value={vtidStartNumber} onChange={e => setVtidStartNumber(parseInt(e.target.value) || 1)}
                          className="mt-1 h-9 w-20 border-indigo-300" data-testid="vtid-start-input" />
                      </div>
                      <Button onClick={() => handleGenerateVTIDs(null)} disabled={vtidGenerating || !vtidPrefix.trim()}
                        className="h-9 bg-indigo-600 hover:bg-indigo-700 text-white gap-1.5" data-testid="vtid-generate-btn">
                        <Hash size={14} />{vtidGenerating ? 'Generando...' : 'Generar VTIDs'}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
                    <div className="bg-indigo-50 px-4 py-3 border-b border-indigo-200 flex items-center justify-between">
                      <div>
                        <p className="text-sm font-semibold text-indigo-900">{project.vtids.length} Terminal{project.vtids.length !== 1 ? 'es' : ''}</p>
                        <p className="text-[10px] text-indigo-500">
                          Prefijo: <span className="font-bold">{project.vtid_prefix}</span>
                          {project.vtid_generated_by && <> · {project.vtid_generated_by}</>}
                        </p>
                      </div>
                      <Button variant="outline" size="sm" onClick={() => handleDeleteVTIDs(null)}
                        disabled={vtidDeleting} className="h-7 text-xs text-red-500 border-red-200 hover:bg-red-50 gap-1" data-testid="vtid-delete-btn">
                        <Trash2 size={12} />{vtidDeleting ? '...' : 'Eliminar'}
                      </Button>
                    </div>
                    <div className="p-4">
                      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
                        {project.vtids.map((vtid, idx) => (
                          <div key={vtid.vtid_id || idx} className="px-3 py-2 rounded-lg bg-slate-50 border border-slate-200 text-center" data-testid={`vtid-item-${idx}`}>
                            <p className="text-sm font-bold font-mono text-indigo-700">{vtid.code}</p>
                            <p className="text-[10px] text-slate-400">#{vtid.sequence}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )
              )}
              </>)}
            </div>
          )}

          {/* ============ BITÁCORA ============ */}
          <div className="mb-6">
            <h2 className="text-lg font-bold text-slate-900 mb-3">Bitácora de Seguimiento</h2>
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 mb-4">
              <div className="grid grid-cols-12 gap-3 items-end">
                <div className="col-span-2">
                  <label className="text-xs font-medium text-slate-600">Fecha de Ejecución</label>
                  <Input type="date" value={bitacoraDate} onChange={e => setBitacoraDate(e.target.value)} data-testid="bitacora-date" className="h-9" />
                </div>
                <div className="col-span-8">
                  <label className="text-xs font-medium text-slate-600">Observación</label>
                  <Input value={bitacoraText} onChange={e => setBitacoraText(e.target.value)} placeholder="Registrar observación o avance..." data-testid="bitacora-text" className="h-9" />
                </div>
                <div className="col-span-2">
                  <Button onClick={handleAddBitacora} disabled={!bitacoraText.trim() || bitacoraSubmitting}
                    className="w-full h-9 bg-brand-green-600 hover:bg-brand-green-700 text-white text-sm" data-testid="bitacora-submit">
                    <Send size={14} className="mr-1" />Registrar
                  </Button>
                </div>
              </div>
            </div>
            <div className="space-y-2" data-testid="bitacora-list">
              {(project.bitacora || []).length === 0 ? (
                <p className="text-sm text-slate-400 text-center py-6">Sin entradas en la bitácora</p>
              ) : (
                [...(project.bitacora || [])].reverse().map(entry => (
                  <div key={entry.entry_id} className="flex items-start gap-4 p-3 bg-white border border-slate-100 rounded-lg">
                    <div className="shrink-0 flex items-center gap-2 text-xs bg-slate-100 rounded px-2 py-1">
                      <Calendar size={12} className="text-slate-500" />
                      <span className="font-mono font-medium">{entry.execution_date}</span>
                    </div>
                    <div className="flex-1">
                      <p className="text-sm text-slate-800">{entry.text}</p>
                      <p className="text-xs text-slate-400 mt-1">
                        <User size={10} className="inline mr-1" />{entry.created_by_name} · {new Date(entry.created_at).toLocaleString('es-VE')}
                      </p>
                    </div>
                    {entry.email_detail && (
                      <Button variant="ghost" size="sm" className="text-xs text-indigo-500 hover:text-indigo-700 shrink-0"
                        onClick={() => { setEmailDetailData(entry.email_detail); setEmailDetailOpen(true); }}
                        data-testid={`view-email-${entry.entry_id}`}>
                        <Eye size={14} className="mr-1" />Ver Correo
                      </Button>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* ==================== NOTIFICATION DIALOG ==================== */}
        <Dialog open={notifDialogOpen} onOpenChange={setNotifDialogOpen}>
          <DialogContent
            className={`${notifTarget?.type === 'bank_client' ? 'max-w-5xl' : 'max-w-3xl'} max-h-[90vh] overflow-y-auto`}
            data-testid="notif-dialog"
          >
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><Bell size={20} className="text-amber-500" />Notificaciones — {notifTarget?.type === 'client' ? 'Cliente' : notifTarget?.type === 'bank_client' ? `Cliente + ${notifTarget?.bankName}` : notifTarget?.bankName}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-2">
              {/* ============ DESTINATARIOS: Selección directa por checkbox ============
                  Cada contacto se muestra como una fila con casilla, Nombre, Email y Rol.
                  Al tildar la casilla el correo se añade automáticamente a mainRecipients
                  (TO). Esta es la fuente única de verdad antes del despacho SMTP.
                  Cuando el target es "bank_client" (banco único + cliente conjunto), se
                  renderizan DOS secciones lado a lado para aprovechar el ancho. */}
              <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                <div className="flex items-center justify-between mb-3">
                  <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Destinatarios del Proyecto</p>
                  {(() => {
                    const tType = notifTarget?.type;
                    const tBank = notifTarget?.bankName;
                    const filtered = suggestedContacts.filter(c => {
                      if (tType === 'client') return c.source === 'client';
                      if (tType === 'bank') return c.source === 'bank' && (!tBank || c.bank_name === tBank);
                      if (tType === 'bank_client') return c.source === 'client' || (c.source === 'bank' && (!tBank || c.bank_name === tBank));
                      return true;
                    });
                    if (filtered.length === 0) return null;
                    const allEmails = filtered.map(c => (c.email || '').toLowerCase());
                    const allSelected = allEmails.every(e => mainRecipients.map(x => x.toLowerCase()).includes(e));
                    return (
                      <Button type="button" size="sm" variant="outline" className="h-7 text-xs"
                        data-testid="toggle-all-contacts-btn"
                        onClick={() => {
                          if (allSelected) {
                            // Deseleccionar todos los del scope actual
                            setMainRecipients(mainRecipients.filter(e => !allEmails.includes(e.toLowerCase())));
                            toast.info('Selección limpiada');
                          } else {
                            const existing = mainRecipients.map(x => x.toLowerCase());
                            const toAdd = filtered.map(c => c.email).filter(e => e && !existing.includes(e.toLowerCase()));
                            setMainRecipients([...mainRecipients, ...toAdd]);
                            toast.success(`${toAdd.length} contacto(s) seleccionado(s)`);
                          }
                        }}
                      >
                        {allSelected ? <><X size={12} className="mr-1" />Limpiar</> : <><CheckCircle2 size={12} className="mr-1" />Seleccionar todos</>}
                      </Button>
                    );
                  })()}
                </div>
                {(() => {
                  const tType = notifTarget?.type;
                  const tBank = notifTarget?.bankName;
                  const clientContacts = suggestedContacts.filter(c => c.source === 'client');
                  const bankContacts = suggestedContacts.filter(c => c.source === 'bank' && (!tBank || c.bank_name === tBank));
                  const showClient = tType === 'client' || tType === 'bank_client';
                  const showBank = tType === 'bank' || tType === 'bank_client';
                  const hasAny = (showClient && clientContacts.length > 0) || (showBank && bankContacts.length > 0);
                  if (!hasAny) {
                    return <p className="text-xs text-slate-400">No hay contactos registrados para este proyecto</p>;
                  }
                  const toggleContact = (email) => {
                    const lower = (email || '').toLowerCase();
                    if (!lower) return;
                    const idx = mainRecipients.map(x => x.toLowerCase()).indexOf(lower);
                    if (idx >= 0) {
                      setMainRecipients(mainRecipients.filter((_, j) => j !== idx));
                    } else {
                      setMainRecipients([...mainRecipients, email]);
                    }
                  };
                  const renderContactsTable = (rows, prefix, accent) => (
                    <div className="bg-white rounded-md border border-slate-200 overflow-hidden">
                      <table className="w-full text-sm" data-testid={`contacts-table-${prefix}`}>
                        <thead className={`${accent} text-[10px] uppercase tracking-wide`}>
                          <tr>
                            <th className="px-3 py-2 text-left w-10"></th>
                            <th className="px-3 py-2 text-left font-semibold">Nombre y Apellido</th>
                            <th className="px-3 py-2 text-left font-semibold">Email</th>
                            <th className="px-3 py-2 text-left font-semibold">Rol / Cargo</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rows.map((c, i) => {
                            const checked = mainRecipients.map(x => x.toLowerCase()).includes((c.email || '').toLowerCase());
                            return (
                              <tr
                                key={`${prefix}-${i}`}
                                className={`border-t border-slate-100 hover:bg-slate-50 cursor-pointer transition-colors ${checked ? 'bg-emerald-50/40' : ''}`}
                                data-testid={`contact-row-${prefix}-${i}`}
                                onClick={() => toggleContact(c.email)}
                              >
                                <td className="px-3 py-2.5 align-middle">
                                  <Checkbox
                                    checked={checked}
                                    onCheckedChange={() => toggleContact(c.email)}
                                    onClick={(e) => e.stopPropagation()}
                                    data-testid={`contact-checkbox-${prefix}-${i}`}
                                  />
                                </td>
                                <td className="px-3 py-2.5 align-middle text-slate-800 font-medium whitespace-normal break-words">
                                  {c.name || c.label || '—'}
                                </td>
                                <td className="px-3 py-2.5 align-middle text-slate-600 font-mono text-xs whitespace-normal break-all">
                                  {c.email}
                                </td>
                                <td className="px-3 py-2.5 align-middle text-slate-500 whitespace-normal break-words">
                                  {c.contact_type || '—'}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  );
                  const sectionWrap = (label, color, content) => (
                    <div>
                      <p className={`text-[10px] font-semibold ${color} uppercase mb-1.5 tracking-wide`}>{label}</p>
                      {content}
                    </div>
                  );
                  // Layout: bank_client → grid 2 cols full-width. Otros → stacked.
                  if (tType === 'bank_client') {
                    return (
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        {clientContacts.length > 0
                          ? sectionWrap('Contactos del Cliente', 'text-indigo-700', renderContactsTable(clientContacts, 'client', 'bg-indigo-50 text-indigo-700'))
                          : <div><p className="text-[10px] font-semibold text-indigo-700 uppercase mb-1.5">Contactos del Cliente</p><p className="text-xs text-slate-400 p-3 bg-white rounded-md border border-slate-200">Sin contactos registrados</p></div>}
                        {bankContacts.length > 0
                          ? sectionWrap(`Contactos del Banco: ${tBank}`, 'text-blue-700', renderContactsTable(bankContacts, 'bank', 'bg-blue-50 text-blue-700'))
                          : <div><p className="text-[10px] font-semibold text-blue-700 uppercase mb-1.5">Contactos del Banco: {tBank}</p><p className="text-xs text-slate-400 p-3 bg-white rounded-md border border-slate-200">Sin contactos registrados</p></div>}
                      </div>
                    );
                  }
                  return (
                    <div className="space-y-3">
                      {showClient && clientContacts.length > 0 && sectionWrap('Contactos del Cliente', 'text-indigo-700', renderContactsTable(clientContacts, 'client', 'bg-indigo-50 text-indigo-700'))}
                      {showBank && bankContacts.length > 0 && sectionWrap(tBank ? `Contactos del Banco: ${tBank}` : 'Contactos del Banco', 'text-blue-700', renderContactsTable(bankContacts, 'bank', 'bg-blue-50 text-blue-700'))}
                    </div>
                  );
                })()}
              </div>

              {/* Historial de envíos y próximo envío */}
              {(() => {
                const history = notifTarget ? getEntityHistory(notifTarget) : [];
                const sendCount = history.length;
                const prefixIdx = Math.min(sendCount, NOTIFICATION_PREFIXES.length - 1);
                const nextPrefix = NOTIFICATION_PREFIXES[prefixIdx];

                return (
                  <div className="space-y-3">
                    {/* Historial de envíos anteriores */}
                    {history.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-[10px] font-semibold text-slate-500 uppercase">Historial de Envíos ({history.length})</p>
                        {history.map((entry, idx) => (
                          <div key={idx} className="flex items-center justify-between p-2.5 rounded-lg bg-emerald-50 border border-emerald-200" data-testid={`notif-history-${idx}`}>
                            <div className="flex items-center gap-2.5">
                              <div className="w-7 h-7 rounded-full bg-emerald-500 text-white flex items-center justify-center text-xs font-bold">{idx + 1}</div>
                              <div>
                                <p className="text-sm font-medium text-emerald-700">[{entry.level}]</p>
                                <p className="text-[10px] text-emerald-500">{entry.sent_by} · {new Date(entry.sent_at).toLocaleString('es-VE')}</p>
                              </div>
                            </div>
                            <CheckCircle2 size={18} className="text-emerald-500" />
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Próximo envío — Estilo VISUAL UNIFICADO para Primer Envío y
                        Recordatorios (homologación visual: el modal de la primera
                        notificación y el de los recordatorios son idénticos
                        excepto por el badge textual "[Primer Envío]" vs
                        "[Primer Recordatorio]" / "[Segundo Recordatorio]" etc.). */}
                    <div className="p-4 rounded-lg border-2 bg-blue-50 border-blue-200 transition-all" data-testid="next-send-block">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold bg-blue-500 text-white">
                            {sendCount + 1}
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-slate-800">Próximo envío: [{nextPrefix}]</p>
                            <p className="text-xs text-slate-500">
                              Plantilla: <span className="font-medium">{emailTemplates.find(t => t.template_id === selectedNotifTemplateId)?.name || '—'}</span>
                              {selectedNotifTemplateId && notifPreferences[notifTarget?.type] === selectedNotifTemplateId && (
                                <span className="ml-2 inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-100 text-amber-700 border border-amber-200" data-testid="preferred-badge">★ Preferida</span>
                              )}
                            </p>
                          </div>
                        </div>
                      </div>

                      {/* Destinatarios resueltos */}
                      <div className="mb-3 space-y-2">
                        <div className="bg-white rounded-lg p-2.5 border border-slate-200">
                          <p className="text-[10px] font-semibold text-slate-400 uppercase mb-1">Destinatarios Principales (TO)</p>
                          <div className="flex flex-wrap gap-1.5 min-h-[28px]" data-testid="main-recipients-chips">
                            {mainRecipients.length === 0 ? (
                              <span className="text-xs text-amber-600 italic">Aún no hay destinatarios. Selecciónelos arriba o agregue/corrija uno abajo.</span>
                            ) : (
                              mainRecipients.map((email, i) => (
                                <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-emerald-50 border border-emerald-200 rounded text-emerald-700 font-mono" data-testid={`main-recipient-${i}`}>
                                  {email}
                                  <button
                                    type="button"
                                    className="ml-1 text-emerald-500 hover:text-rose-600"
                                    title="Quitar"
                                    data-testid={`remove-main-recipient-${i}`}
                                    onClick={() => setMainRecipients(mainRecipients.filter((_, j) => j !== i))}
                                  >×</button>
                                </span>
                              ))
                            )}
                          </div>
                          {/* Agregar/Corregir correo principal en caliente */}
                          <div className="flex gap-2 mt-2 items-start">
                            <div className="flex-1">
                              <InternalEmailInput
                                value={toNewEmail}
                                onChange={setToNewEmail}
                                onEnter={addToRecipient}
                                profile="strategic"
                                placeholder="Agregar/corregir correo principal — o busque usuario interno"
                                testId="notif-to-input"
                              />
                            </div>
                            <Button type="button" variant="outline" size="sm" onClick={addToRecipient}
                              disabled={!toNewEmail.trim() || !toNewEmail.includes('@')}
                              data-testid="notif-add-to-btn" className="mt-0">
                              <Plus size={14} />
                            </Button>
                          </div>
                          <p className="text-[10px] text-slate-400 mt-1">Si el correo precargado del Cliente/Banco es incorrecto, escriba aquí el correcto (solo afecta este envío).</p>
                        </div>

                        {/* Destinatarios adicionales (CC) — componente de tokens homologado */}
                        <div className="bg-white rounded-lg p-2.5 border border-slate-200">
                          <label className="text-[10px] font-semibold text-slate-400 uppercase block mb-1">
                            Destinatarios Adicionales (CC)
                          </label>
                          <div className="flex gap-2 items-start">
                            <div className="flex-1">
                              <InternalEmailInput
                                value={ccNewEmail}
                                onChange={setCcNewEmail}
                                onEnter={addCcRecipient}
                                profile="strategic"
                                placeholder="correo@ejemplo.com — o busque usuario interno"
                                testId="notif-cc-input"
                              />
                            </div>
                            <Button type="button" variant="outline" size="sm" onClick={addCcRecipient}
                              disabled={!ccNewEmail.trim() || !ccNewEmail.includes('@')}
                              data-testid="notif-add-cc-btn" className="mt-0">
                              <Plus size={14} />
                            </Button>
                          </div>
                          {additionalRecipientsList.length > 0 && (
                            <div className="flex flex-wrap gap-1.5 mt-2" data-testid="cc-recipients-chips">
                              {additionalRecipientsList.map((email, idx) => (
                                <span key={idx} className="inline-flex items-center gap-1 text-xs bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded-full" data-testid={`cc-recipient-${idx}`}>
                                  {email}
                                  <button type="button" onClick={() => removeCcRecipient(email)} className="hover:text-red-500 ml-0.5" data-testid={`remove-cc-recipient-${idx}`}>
                                    <X size={12} />
                                  </button>
                                </span>
                              ))}
                            </div>
                          )}
                          <p className="text-[10px] text-slate-400 mt-1">
                            Estos correos recibirán copia (CC). Haga clic en un usuario interno o agregue uno externo con el botón +.
                          </p>

                          {/* Grupos de destinatarios CC reutilizables */}
                          <div className="mt-2 pt-2 border-t border-slate-100">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-[10px] font-semibold text-slate-400 uppercase">Grupos guardados</span>
                              {additionalRecipientsList.length > 0 && (
                                <button
                                  type="button"
                                  onClick={() => setShowSaveGroup(s => !s)}
                                  data-testid="cc-save-group-toggle"
                                  className="text-[11px] text-blue-600 hover:underline"
                                >
                                  + Guardar selección como grupo
                                </button>
                              )}
                            </div>
                            {showSaveGroup && (
                              <div className="flex gap-2 mb-2">
                                <Input
                                  value={ccGroupName}
                                  onChange={(e) => setCcGroupName(e.target.value)}
                                  placeholder="Nombre del grupo (ej: Equipo Implementación Banesco)"
                                  className="h-8 text-xs"
                                  data-testid="cc-group-name-input"
                                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); saveCcGroup(); } }}
                                />
                                <Button size="sm" variant="outline" onClick={saveCcGroup} disabled={!ccGroupName.trim()} data-testid="cc-save-group-btn" className="shrink-0">
                                  Guardar
                                </Button>
                              </div>
                            )}
                            {ccGroups.length === 0 ? (
                              <p className="text-[11px] text-slate-400 italic">Aún no hay grupos. Agregue correos arriba y guárdelos para reutilizarlos con un clic.</p>
                            ) : (
                              <div className="flex flex-wrap gap-1.5" data-testid="cc-groups-list">
                                {ccGroups.map(g => (
                                  <span key={g.group_id} className="inline-flex items-center gap-1 text-[11px] bg-slate-100 border border-slate-200 rounded-full pl-2 pr-1 py-0.5" data-testid={`cc-group-${g.group_id}`}>
                                    <button
                                      type="button"
                                      onClick={() => applyCcGroup(g)}
                                      className="hover:text-blue-700 font-medium"
                                      title={`Aplicar grupo (${(g.emails || []).length} correos)`}
                                      data-testid={`apply-cc-group-${g.group_id}`}
                                    >
                                      {g.name} <span className="text-slate-400">({(g.emails || []).length})</span>
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => deleteCcGroup(g.group_id)}
                                      className="text-slate-400 hover:text-red-500"
                                      title="Eliminar grupo"
                                      data-testid={`delete-cc-group-${g.group_id}`}
                                    >
                                      <X size={11} />
                                    </button>
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* ===== Plantilla de Proyecto (Texto Enriquecido) — precargada con la Preferida ===== */}
                      <div className="bg-white rounded-lg p-3 border border-slate-200 mb-3 space-y-2" data-testid="notif-template-panel">
                        <div className="flex items-end gap-2">
                          <div className="flex-1">
                            <label className="text-[10px] font-semibold text-slate-400 uppercase block mb-1">Plantilla</label>
                            <Select value={selectedNotifTemplateId || ''} onValueChange={handleNotifTemplateChange}>
                              <SelectTrigger className="h-9 text-sm" data-testid="notif-template-select">
                                <SelectValue placeholder="Seleccionar plantilla..." />
                              </SelectTrigger>
                              <SelectContent>
                                {emailTemplates.map(t => (
                                  <SelectItem key={t.template_id} value={t.template_id} data-testid={`notif-template-option-${t.template_id}`}>
                                    {t.name}{notifPreferences[notifTarget?.type] === t.template_id ? ' ★' : ''}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                          <Button
                            type="button" size="sm" variant="outline"
                            className={`h-9 text-xs gap-1 ${notifPreferences[notifTarget?.type] === selectedNotifTemplateId ? 'border-amber-300 text-amber-600 bg-amber-50' : 'border-slate-200 text-slate-600'}`}
                            disabled={!selectedNotifTemplateId || notifPreferences[notifTarget?.type] === selectedNotifTemplateId}
                            onClick={markNotifTemplatePreferred}
                            data-testid="mark-preferred-btn"
                            title="Marcar esta plantilla como preferida para este destino"
                          >
                            ★ {notifPreferences[notifTarget?.type] === selectedNotifTemplateId ? 'Preferida' : 'Marcar preferida'}
                          </Button>
                        </div>
                        <div>
                          <label className="text-[10px] font-semibold text-slate-400 uppercase block mb-1">Contenido del mensaje</label>
                          <RichTextEditor
                            key={`notif-editor-${selectedNotifTemplateId}`}
                            value={notifBody}
                            onChange={(html) => setNotifBody(html)}
                            maxChars={20000}
                            hardLimit={false}
                            placeholder="Contenido del correo. Puede editarlo antes de enviar."
                            testid="notif-body-editor"
                            minHeight={180}
                            maxHeight={340}
                            tableRowActions={true}
                          />
                        </div>
                      </div>

                      {/* Panel de Variables Disponibles */}
                      <details className="bg-indigo-50 rounded-lg border border-indigo-200 mb-3">
                        <summary className="px-3 py-2 text-[10px] font-semibold text-indigo-700 cursor-pointer select-none flex items-center gap-1">
                          <ClipboardList size={12} />Variables disponibles para la plantilla
                        </summary>
                        <div className="px-3 pb-2 flex flex-wrap gap-1">
                          {ALL_TOKENS.map(t => `{${t}}`).map(v => (
                            <span key={v} onClick={() => { navigator.clipboard.writeText(v); toast.success(`${v} copiado`); }}
                              className="text-[10px] px-1.5 py-0.5 rounded bg-white border border-indigo-200 text-indigo-600 hover:bg-indigo-100 cursor-pointer transition-all"
                              title={`Clic para copiar ${v}`}>{v}</span>
                          ))}
                        </div>
                      </details>

                      {/* Adjuntos y Matriz (homologado con Otras Notificaciones) */}
                      <div className="bg-white rounded-lg p-3 border border-slate-200 mb-3" data-testid="notif-attachments-panel">
                        <p className="text-[10px] font-semibold text-slate-400 uppercase mb-1.5">Adjuntos y Matriz de Distribución</p>
                        <div className="flex items-center gap-2 flex-wrap">
                          <input ref={notifFileInputRef} type="file" multiple accept=".jpg,.jpeg,.png,.pdf,.doc,.docx,.xls,.xlsx,.txt" className="hidden" onChange={handleNotifFileSelect} />
                          <Button variant="outline" size="sm" onClick={() => notifFileInputRef.current?.click()} className="text-xs gap-1.5" data-testid="notif-attach-files-btn"><Paperclip size={14} />Cargar Archivos</Button>
                          <Button variant="outline" size="sm" onClick={() => { const i = document.createElement('input'); i.type = 'file'; i.accept = 'image/jpeg,image/png'; i.multiple = true; i.onchange = (ev) => setNotifFiles(prev => [...prev, ...Array.from(ev.target.files || [])]); i.click(); }}
                            className="text-xs gap-1.5" data-testid="notif-attach-images-btn"><Image size={14} />Cargar Imágenes</Button>
                          <Button variant={notifAttachMatrix ? 'default' : 'outline'} size="sm"
                            onClick={() => setNotifAttachMatrix(!notifAttachMatrix)}
                            className={`text-xs gap-1.5 ${notifAttachMatrix ? 'bg-indigo-600 hover:bg-indigo-700 text-white' : ''}`}
                            data-testid="notif-attach-matrix-btn">
                            <BarChart3 size={14} />Adjuntar Matriz
                          </Button>
                        </div>
                        {notifFiles.length > 0 && (
                          <div className="mt-2 space-y-1">
                            {notifFiles.map((f, idx) => (
                              <div key={idx} className="flex items-center justify-between bg-slate-50 rounded px-2.5 py-1.5 text-xs" data-testid={`notif-file-${idx}`}>
                                <span className="truncate text-slate-700 flex-1">{f.name}</span>
                                <button onClick={() => removeNotifFile(idx)} className="ml-2 text-red-400 hover:text-red-600 shrink-0"><X size={14} /></button>
                              </div>
                            ))}
                          </div>
                        )}
                        {notifAttachMatrix && <p className="text-[10px] text-indigo-500 mt-1">Se adjuntará al cuerpo una tabla con el estatus actual de la matriz de seguimiento (con sus avances).</p>}
                      </div>

                      {/* Botones de acción */}
                      <div className="flex items-center justify-end gap-2">
                        <Button size="sm" variant="outline" className="h-8 text-xs border-blue-200 text-blue-600 hover:bg-blue-50"
                          disabled={previewLoading} onClick={() => previewNotification(notifTarget?.type, notifTarget?.bankName)}
                          data-testid="preview-next-notif">
                          <Eye size={12} className="mr-1" />{previewLoading ? '...' : 'Vista Previa'}
                        </Button>
                        <Button size="sm" className="h-8 text-xs text-white bg-blue-500 hover:bg-blue-600"
                          disabled={!!notifSending} onClick={sendNotification}
                          data-testid="send-next-notif">
                          <Send size={12} className="mr-1" />{notifSending ? 'Enviando...' : 'Enviar'}
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })()}
            </div>
          </DialogContent>
        </Dialog>

        {/* ==================== OTRAS NOTIFICACIONES DIALOG (homologado) ==================== */}
        <Dialog open={emailDialogOpen} onOpenChange={(o) => { if (!emailSending) setEmailDialogOpen(o); }}>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="adhoc-email-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><Megaphone size={20} className="text-indigo-500" />Otras Notificaciones</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-2">
              {/* ============ DESTINATARIOS DEL PROYECTO (tabla con checkboxes) ============ */}
              <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                <div className="flex items-center justify-between mb-3">
                  <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Destinatarios del Proyecto</p>
                  {suggestedContacts.length > 0 && (() => {
                    const allEmails = suggestedContacts.map(c => (c.email || '').toLowerCase());
                    const current = emailForm.recipients.map(x => x.trim().toLowerCase());
                    const allSelected = allEmails.every(e => current.includes(e));
                    return (
                      <Button type="button" size="sm" variant="outline" className="h-7 text-xs" data-testid="adhoc-toggle-all-contacts"
                        onClick={() => {
                          setEmailForm(prev => {
                            const cleaned = prev.recipients.filter(r => r.trim());
                            if (allSelected) {
                              return { ...prev, recipients: cleaned.filter(r => !allEmails.includes(r.toLowerCase())) };
                            }
                            const existing = cleaned.map(r => r.toLowerCase());
                            const toAdd = suggestedContacts.map(c => c.email).filter(e => e && !existing.includes(e.toLowerCase()));
                            return { ...prev, recipients: [...cleaned, ...toAdd] };
                          });
                        }}>
                        {allSelected ? <><X size={12} className="mr-1" />Limpiar</> : <><CheckCircle2 size={12} className="mr-1" />Seleccionar todos</>}
                      </Button>
                    );
                  })()}
                </div>
                {suggestedContacts.length === 0 ? (
                  <p className="text-xs text-slate-400">No hay contactos registrados para este proyecto</p>
                ) : (
                  <div className="bg-white rounded-md border border-slate-200 overflow-hidden">
                    <table className="w-full text-sm" data-testid="adhoc-contacts-table">
                      <thead className="bg-indigo-50 text-indigo-700 text-[10px] uppercase tracking-wide">
                        <tr>
                          <th className="px-3 py-2 text-left w-10"></th>
                          <th className="px-3 py-2 text-left font-semibold">Nombre y Apellido</th>
                          <th className="px-3 py-2 text-left font-semibold">Email</th>
                          <th className="px-3 py-2 text-left font-semibold">Rol / Cargo</th>
                        </tr>
                      </thead>
                      <tbody>
                        {suggestedContacts.map((c, i) => {
                          const checked = emailForm.recipients.map(x => x.trim().toLowerCase()).includes((c.email || '').toLowerCase());
                          return (
                            <tr key={i} className={`border-t border-slate-100 hover:bg-slate-50 cursor-pointer transition-colors ${checked ? 'bg-emerald-50/40' : ''}`}
                              data-testid={`adhoc-contact-row-${i}`} onClick={() => toggleAdhocRecipient(c.email)}>
                              <td className="px-3 py-2.5 align-middle">
                                <Checkbox checked={checked} onCheckedChange={() => toggleAdhocRecipient(c.email)} onClick={(e) => e.stopPropagation()} data-testid={`adhoc-contact-checkbox-${i}`} />
                              </td>
                              <td className="px-3 py-2.5 align-middle text-slate-800 font-medium whitespace-normal break-words">{c.name || c.label || '—'}</td>
                              <td className="px-3 py-2.5 align-middle text-slate-600 font-mono text-xs whitespace-normal break-all">{c.email}</td>
                              <td className="px-3 py-2.5 align-middle text-slate-500 whitespace-normal break-words">{c.contact_type || '—'}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* ============ TARJETA DE COMPOSICIÓN (estilo unificado) ============ */}
              <div className="p-4 rounded-lg border-2 bg-blue-50 border-blue-200" data-testid="adhoc-compose-card">
                {/* Destinatarios (TO) */}
                <div className="bg-white rounded-lg p-2.5 border border-slate-200 mb-3">
                  <p className="text-[10px] font-semibold text-slate-400 uppercase mb-1">Destinatarios (TO) <span className="text-red-500">*</span></p>
                  <div className="flex flex-wrap gap-1.5 min-h-[28px]" data-testid="adhoc-recipients-chips">
                    {emailForm.recipients.filter(r => r.trim()).length === 0 ? (
                      <span className="text-xs text-amber-600 italic">Seleccione contactos arriba o agregue un correo manual abajo.</span>
                    ) : emailForm.recipients.filter(r => r.trim()).map((email, i) => (
                      <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-emerald-50 border border-emerald-200 rounded text-emerald-700 font-mono" data-testid={`adhoc-recipient-${i}`}>
                        {email}
                        <button type="button" className="ml-1 text-emerald-500 hover:text-rose-600" title="Quitar" onClick={() => toggleAdhocRecipient(email)}>×</button>
                      </span>
                    ))}
                  </div>
                  <div className="flex gap-2 mt-2 items-start">
                    <div className="flex-1">
                      <InternalEmailInput
                        value={adhocManualEmail}
                        onChange={setAdhocManualEmail}
                        onEnter={addAdhocManualRecipient}
                        profile="strategic"
                        placeholder="Agregar correo — o busque un usuario interno"
                        testId="adhoc-manual-email-input"
                      />
                    </div>
                    <Button type="button" size="sm" variant="outline" onClick={addAdhocManualRecipient}
                      disabled={!adhocManualEmail.trim() || !adhocManualEmail.includes('@')}
                      className="text-xs mt-0" data-testid="adhoc-add-recipient-btn"><Plus size={14} /></Button>
                  </div>
                  <p className="text-[10px] text-slate-400 mt-1">Seleccione contactos arriba, busque un usuario interno o escriba un correo externo.</p>
                </div>

                {/* Destinatarios Adicionales (CC) — homologado con Notificaciones */}
                <div className="bg-white rounded-lg p-2.5 border border-slate-200 mb-3">
                  <label className="text-[10px] font-semibold text-slate-400 uppercase block mb-1">
                    Destinatarios Adicionales (CC)
                  </label>
                  <div className="flex gap-2 items-start">
                    <div className="flex-1">
                      <InternalEmailInput
                        value={ccNewEmail}
                        onChange={setCcNewEmail}
                        onEnter={addCcRecipient}
                        profile="strategic"
                        placeholder="correo@ejemplo.com — o busque usuario interno"
                        testId="adhoc-cc-input"
                      />
                    </div>
                    <Button type="button" variant="outline" size="sm" onClick={addCcRecipient}
                      disabled={!ccNewEmail.trim() || !ccNewEmail.includes('@')}
                      data-testid="adhoc-add-cc-btn" className="mt-0">
                      <Plus size={14} />
                    </Button>
                  </div>
                  {additionalRecipientsList.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2" data-testid="adhoc-cc-recipients-chips">
                      {additionalRecipientsList.map((email, idx) => (
                        <span key={idx} className="inline-flex items-center gap-1 text-xs bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded-full" data-testid={`adhoc-cc-recipient-${idx}`}>
                          {email}
                          <button type="button" onClick={() => removeCcRecipient(email)} className="hover:text-red-500 ml-0.5" data-testid={`adhoc-remove-cc-recipient-${idx}`}>
                            <X size={12} />
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                  <p className="text-[10px] text-slate-400 mt-1">
                    Estos correos recibirán copia (CC). Haga clic en un usuario interno o agregue uno externo con el botón +.
                  </p>

                  {/* Grupos de destinatarios CC reutilizables (compartidos) */}
                  <div className="mt-2 pt-2 border-t border-slate-100">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] font-semibold text-slate-400 uppercase">Grupos guardados</span>
                      {additionalRecipientsList.length > 0 && (
                        <button
                          type="button"
                          onClick={() => setShowSaveGroup(s => !s)}
                          data-testid="adhoc-cc-save-group-toggle"
                          className="text-[11px] text-blue-600 hover:underline"
                        >
                          + Guardar selección como grupo
                        </button>
                      )}
                    </div>
                    {showSaveGroup && (
                      <div className="flex gap-2 mb-2">
                        <Input
                          value={ccGroupName}
                          onChange={(e) => setCcGroupName(e.target.value)}
                          placeholder="Nombre del grupo (ej: Equipo Implementación Banesco)"
                          className="h-8 text-xs"
                          data-testid="adhoc-cc-group-name-input"
                          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); saveCcGroup(); } }}
                        />
                        <Button size="sm" variant="outline" onClick={saveCcGroup} disabled={!ccGroupName.trim()} data-testid="adhoc-cc-save-group-btn" className="shrink-0">
                          Guardar
                        </Button>
                      </div>
                    )}
                    {ccGroups.length === 0 ? (
                      <p className="text-[11px] text-slate-400 italic">Aún no hay grupos. Agregue correos arriba y guárdelos para reutilizarlos con un clic.</p>
                    ) : (
                      <div className="flex flex-wrap gap-1.5" data-testid="adhoc-cc-groups-list">
                        {ccGroups.map(g => (
                          <span key={g.group_id} className="inline-flex items-center gap-1 text-[11px] bg-slate-100 border border-slate-200 rounded-full pl-2 pr-1 py-0.5" data-testid={`adhoc-cc-group-${g.group_id}`}>
                            <button
                              type="button"
                              onClick={() => applyCcGroup(g)}
                              className="hover:text-blue-700 font-medium"
                              title={`Aplicar grupo (${(g.emails || []).length} correos)`}
                              data-testid={`adhoc-apply-cc-group-${g.group_id}`}
                            >
                              {g.name} <span className="text-slate-400">({(g.emails || []).length})</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => deleteCcGroup(g.group_id)}
                              className="text-slate-400 hover:text-red-500"
                              title="Eliminar grupo"
                              data-testid={`adhoc-delete-cc-group-${g.group_id}`}
                            >
                              <X size={11} />
                            </button>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Plantilla + Asunto + Editor */}
                <div className="bg-white rounded-lg p-3 border border-slate-200 mb-3 space-y-2">
                  <div>
                    <label className="text-[10px] font-semibold text-slate-400 uppercase block mb-1">Plantilla</label>
                    <Select value={emailForm.templateId || 'blank'} onValueChange={handleTemplateSelect}>
                      <SelectTrigger className="h-9 text-sm" data-testid="template-select"><SelectValue placeholder="Seleccionar plantilla..." /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="blank">Hoja en blanco</SelectItem>
                        {emailTemplates.map(t => <SelectItem key={t.template_id} value={t.template_id}>{t.name}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <label className="text-[10px] font-semibold text-slate-400 uppercase block mb-1">Asunto <span className="text-red-500">*</span></label>
                    <Input placeholder="Asunto del correo..." value={emailForm.subject}
                      onChange={e => setEmailForm(prev => ({ ...prev, subject: e.target.value }))}
                      className="h-9 text-sm" data-testid="email-subject" />
                  </div>
                  <div>
                    <label className="text-[10px] font-semibold text-slate-400 uppercase block mb-1">Contenido del mensaje <span className="text-red-500">*</span></label>
                    <RichTextEditor
                      value={emailForm.message}
                      onChange={(html) => setEmailForm(prev => ({ ...prev, message: html }))}
                      maxChars={20000}
                      hardLimit={false}
                      placeholder="Escriba su mensaje aquí. Al elegir una plantilla se cargará con su formato."
                      testid="email-message"
                      showPreview
                      minHeight={180}
                      maxHeight={340}
                      tableRowActions={true}
                    />
                  </div>
                </div>

                {/* Variables disponibles (colapsable homologado) */}
                <details className="bg-indigo-50 rounded-lg border border-indigo-200 mb-3">
                  <summary className="px-3 py-2 text-[10px] font-semibold text-indigo-700 cursor-pointer select-none flex items-center gap-1">
                    <ClipboardList size={12} />Variables disponibles (clic para insertar en el mensaje)
                  </summary>
                  <div className="px-3 pb-2 flex flex-wrap gap-1">
                    {ALL_TOKENS.map(t => `{${t}}`).map(v => (
                      <button key={v} type="button" onClick={() => setEmailForm(prev => ({ ...prev, message: prev.message + ` ${v}` }))}
                        className="text-[10px] px-1.5 py-0.5 rounded bg-white border border-indigo-200 text-indigo-600 hover:bg-indigo-100 cursor-pointer transition-all"
                        title={`Insertar ${v}`}>{v}</button>
                    ))}
                  </div>
                </details>

                {/* Adjuntos y Matriz (capacidades potentes conservadas) */}
                <div className="bg-white rounded-lg p-3 border border-slate-200 mb-3">
                  <p className="text-[10px] font-semibold text-slate-400 uppercase mb-1.5">Adjuntos y Matriz de Distribución</p>
                  <div className="flex items-center gap-2 flex-wrap">
                    <input ref={fileInputRef} type="file" multiple accept=".jpg,.jpeg,.png,.pdf,.doc,.docx,.xls,.xlsx,.txt" className="hidden" onChange={handleFileSelect} />
                    <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()} className="text-xs gap-1.5" data-testid="attach-files-btn"><Paperclip size={14} />Cargar Archivos</Button>
                    <Button variant="outline" size="sm" onClick={() => { const i = document.createElement('input'); i.type = 'file'; i.accept = 'image/jpeg,image/png'; i.multiple = true; i.onchange = (ev) => setEmailFiles(prev => [...prev, ...Array.from(ev.target.files || [])]); i.click(); }}
                      className="text-xs gap-1.5" data-testid="attach-images-btn"><Image size={14} />Cargar Imágenes</Button>
                    <Button variant={attachMatrix ? 'default' : 'outline'} size="sm"
                      onClick={() => setAttachMatrix(!attachMatrix)}
                      className={`text-xs gap-1.5 ${attachMatrix ? 'bg-indigo-600 hover:bg-indigo-700 text-white' : ''}`}
                      data-testid="attach-matrix-btn">
                      <BarChart3 size={14} />Adjuntar Matriz
                    </Button>
                  </div>
                  {emailFiles.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {emailFiles.map((f, idx) => (
                        <div key={idx} className="flex items-center justify-between bg-slate-50 rounded px-2.5 py-1.5 text-xs">
                          <span className="truncate text-slate-700 flex-1">{f.name}</span>
                          <button onClick={() => removeFile(idx)} className="ml-2 text-red-400 hover:text-red-600 shrink-0"><X size={14} /></button>
                        </div>
                      ))}
                    </div>
                  )}
                  {attachMatrix && <p className="text-[10px] text-indigo-500 mt-1">Se adjuntará una tabla HTML con el estatus actual de la matriz de seguimiento (con sus avances).</p>}
                </div>

                {/* Acciones */}
                <div className="flex items-center justify-end gap-2">
                  <Button size="sm" variant="outline" onClick={() => setEmailDialogOpen(false)} disabled={emailSending} className="h-8 text-xs">Cancelar</Button>
                  <Button size="sm" variant="outline" onClick={previewAdhocEmail}
                    disabled={previewLoading || !emailForm.subject.trim() || !emailForm.message.trim()}
                    className="h-8 text-xs border-blue-200 text-blue-600 hover:bg-blue-50 gap-1.5" data-testid="preview-adhoc-email-btn">
                    <Eye size={14} />{previewLoading ? 'Cargando...' : 'Vista Previa'}
                  </Button>
                  <Button size="sm" onClick={handleSendAdhocEmail}
                    disabled={emailSending || !emailForm.subject.trim() || !emailForm.message.trim() || !emailForm.recipients.some(r => r.trim())}
                    className="h-8 text-xs bg-blue-500 hover:bg-blue-600 text-white gap-1.5" data-testid="send-adhoc-email-btn">
                    <Send size={14} />{emailSending ? 'Enviando...' : 'Enviar Correo'}
                  </Button>
                </div>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* ==================== EMAIL DETAIL VIEWER ==================== */}
        <EmailDetailViewer
          open={emailDetailOpen}
          onOpenChange={setEmailDetailOpen}
          data={emailDetailData}
        />

        {/* ==================== TEMPLATES ADMIN DIALOG ==================== */}
        <TemplatesAdminDialog
          open={templatesDialogOpen}
          onOpenChange={setTemplatesDialogOpen}
          emailTemplates={emailTemplates}
          editingTemplateId={editingTemplateId}
          setEditingTemplateId={setEditingTemplateId}
          templateForm={templateForm}
          setTemplateForm={setTemplateForm}
          templateSaving={templateSaving}
          handleSaveTemplate={handleSaveTemplate}
          handleDeleteTemplate={handleDeleteTemplate}
        />

        {/* ==================== EMAIL PREVIEW / EDITOR DIALOG ==================== */}
        <EmailPreviewDialog
          open={previewOpen}
          onOpenChange={setPreviewOpen}
          previewData={previewData}
          previewSubject={previewSubject}
          setPreviewSubject={setPreviewSubject}
          previewSending={previewSending}
          sendFromPreview={sendFromPreview}
          editorRef={editorRef}
          handleEditorPaste={handleEditorPaste}
          handleEditorDrop={handleEditorDrop}
          handleInsertImage={handleInsertImage}
          insertVariableInEditor={insertVariableInEditor}
        />

        {/* ================= Actualización Masiva (Batch Update) ================= */}
        <BatchUpdateModal
          open={batchModalOpen}
          onOpenChange={setBatchModalOpen}
          project={project}
          batchPhase={batchPhase}
          setBatchPhase={setBatchPhase}
          batchBank={batchBank}
          setBatchBank={handleBatchBankChange}
          batchRif={batchRif}
          setBatchRif={handleBatchRifChange}
          batchProducts={batchProducts}
          toggleBatchProduct={toggleBatchProduct}
          batchStoreIds={batchStoreIds}
          batchReason={batchReason}
          setBatchReason={setBatchReason}
          batchSubmitting={batchSubmitting}
          toggleBatchStore={toggleBatchStore}
          toggleAllBatchStores={toggleAllBatchStores}
          submitBatchUpdate={submitBatchUpdate}
        />

        <ProjectProgressReportDialog
          open={progressReportOpen}
          onOpenChange={setProgressReportOpen}
          projectId={project?.project_id}
        />

        {commitmentsOpen && project && (() => {
          const cargo = (currentUser.cargo || '').toLowerCase();
          const canManage = (currentUser.role || '').toLowerCase() === 'admin' || cargo === 'coordinador' || cargo === 'gerente';
          return (
            <CommitmentModal
              open={commitmentsOpen}
              onClose={() => setCommitmentsOpen(false)}
              projectId={project.project_id}
              projectNumber={project.project_number}
              clientName={project.client_name}
              canManage={canManage}
              onChange={() => fetchProject()}
            />
          );
        })()}

        {alertsOpen && project && (() => {
          const isAssignedImpl = currentUser.user_id && currentUser.user_id === project.assigned_to_user_id;
          const cargo = (currentUser.cargo || '').toLowerCase();
          const isCoordAdmin = (currentUser.role || '').toLowerCase() === 'admin' || cargo === 'coordinador' || cargo === 'gerente';
          return (
            <ImplementerAlertsModal
              open={alertsOpen}
              onClose={() => setAlertsOpen(false)}
              projectId={project.project_id}
              projectNumber={project.project_number}
              clientName={project.client_name}
              canManage={isAssignedImpl}
              readOnly={!isAssignedImpl && isCoordAdmin}
              onChange={() => fetchProject()}
            />
          );
        })()}
      </main>
    </div>
  );
};


export default ProjectDetail;
