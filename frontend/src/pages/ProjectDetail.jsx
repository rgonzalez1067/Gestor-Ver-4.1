import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import api from '../utils/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';
import {
  ArrowLeft, CreditCard, Building2, CheckCircle2, Circle, Clock,
  FileText, Send, Calendar, User, Store, Bell, BellRing, Lock, BarChart3, Mail,
  Plus, X, Paperclip, Image, Ticket, ChevronDown, Eye, Megaphone, ClipboardList,
  Hash, Trash2, AlertCircle, Shield, Edit3, Copy, ImagePlus, Server, Edit2
} from 'lucide-react';

const PHASES = ['Notificado', 'Recibido', 'Configurado', 'Testeado', 'En Producción'];
const STORE_PHASES = ['Recibido', 'Configurado', 'Testeado', 'En Producción'];
const PHASE_COLORS = {
  'Notificado': 'bg-lime-100 text-lime-800',
  'Recibido': 'bg-sky-100 text-sky-800',
  'Configurado': 'bg-violet-100 text-violet-800',
  'Testeado': 'bg-cyan-100 text-cyan-800',
  'En Producción': 'bg-emerald-100 text-emerald-800',
};

// ==================== TEMPLATE BODY EDITOR CON RESALTADO Y AUTOCOMPLETE ====================
const ALL_TOKENS = [
  'Nombre_Cliente','Rif_Cliente','Contacto_Principal','Datos_Contacto','Telefono_Contacto','Email_Contacto',
  'Nro_Proyecto','Ticket_Nro','Tipo_Proyecto','Fecha_Asignacion','Nombre_Sucursal','Cantidad_Cajas',
  'Servidor_Instalacion','Nombre_Implementador','Correo_Implementador','Integrador','Aplicativo_Integracion',
  'Modelo_Seriales_POS','Modelo_Seriales_Equipos','Lista_VTID','Matriz_Bancos_Productos',
];

const TemplateBodyEditor = ({ value, onChange }) => {
  const textareaRef = useRef(null);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [suggestIdx, setSuggestIdx] = useState(0);
  const [cursorPos, setCursorPos] = useState(0);
  const [braceStart, setBraceStart] = useState(-1);

  const handleChange = (e) => {
    const val = e.target.value;
    const pos = e.target.selectionStart;
    onChange(val);
    setCursorPos(pos);

    // Detect if we're inside a `{...` token being typed
    const before = val.slice(0, pos);
    const lastBrace = before.lastIndexOf('{');
    const lastClose = before.lastIndexOf('}');
    if (lastBrace > lastClose) {
      const partial = before.slice(lastBrace + 1);
      if (!/\s/.test(partial) && partial.length <= 40) {
        const filtered = ALL_TOKENS.filter(t => t.toLowerCase().startsWith(partial.toLowerCase()));
        setSuggestions(filtered);
        setSuggestIdx(0);
        setBraceStart(lastBrace);
        setShowSuggestions(filtered.length > 0);
        return;
      }
    }
    setShowSuggestions(false);
  };

  const insertSuggestion = (token) => {
    const before = value.slice(0, braceStart);
    const after = value.slice(cursorPos);
    const newVal = before + `{${token}}` + after;
    onChange(newVal);
    setShowSuggestions(false);
    setTimeout(() => {
      if (textareaRef.current) {
        const newPos = before.length + token.length + 2;
        textareaRef.current.selectionStart = newPos;
        textareaRef.current.selectionEnd = newPos;
        textareaRef.current.focus();
      }
    }, 0);
  };

  const handleKeyDown = (e) => {
    if (!showSuggestions) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setSuggestIdx(i => Math.min(i + 1, suggestions.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSuggestIdx(i => Math.max(i - 1, 0)); }
    else if (e.key === 'Enter' || e.key === 'Tab') {
      if (suggestions[suggestIdx]) { e.preventDefault(); insertSuggestion(suggestions[suggestIdx]); }
    }
    else if (e.key === 'Escape') { setShowSuggestions(false); }
  };

  // Render highlighted preview (tokens as blue pills, rest invisible)
  const renderHighlighted = () => {
    if (!value) return null;
    const parts = value.split(/(\{[A-Za-z_]+\})/g);
    return parts.map((part, i) =>
      /^\{[A-Za-z_]+\}$/.test(part)
        ? <mark key={i} className="bg-blue-100 text-blue-700 rounded px-0.5 font-mono text-[11px] border border-blue-200" style={{ color: 'transparent', background: 'rgba(219,234,254,0.7)', borderRadius: '3px', padding: '1px 2px' }}>{part}</mark>
        : <span key={i} style={{ color: 'transparent' }}>{part}</span>
    );
  };

  return (
    <div className="relative mt-1" data-testid="template-body-editor">
      {/* Highlighted background layer — only shows colored backgrounds behind tokens */}
      <div className="absolute inset-0 pointer-events-none p-3 text-sm whitespace-pre-wrap break-words overflow-hidden font-sans leading-[1.625] select-none"
        aria-hidden="true" style={{ zIndex: 0 }}>
        {renderHighlighted()}
      </div>
      {/* Actual textarea — text fully visible on top */}
      <textarea ref={textareaRef} value={value} onChange={handleChange} onKeyDown={handleKeyDown}
        placeholder="Contenido de la plantilla... Escribe { para autocompletar variables"
        className="w-full text-sm min-h-[200px] resize-y border border-slate-200 rounded-lg p-3 bg-transparent relative focus:ring-2 focus:ring-blue-300 focus:border-blue-400 outline-none leading-[1.625]"
        style={{ zIndex: 1, color: '#1e293b', caretColor: '#1e293b' }}
        data-testid="template-body" />
      {/* Autocomplete dropdown */}
      {showSuggestions && suggestions.length > 0 && (
        <div className="absolute z-50 bg-white border border-blue-200 rounded-lg shadow-lg max-h-48 overflow-y-auto w-64 left-4"
          style={{ top: '60px' }} data-testid="token-autocomplete">
          {suggestions.map((s, i) => (
            <button key={s} className={`w-full text-left px-3 py-1.5 text-xs font-mono hover:bg-blue-50 transition-colors ${i === suggestIdx ? 'bg-blue-50 text-blue-700' : 'text-slate-700'}`}
              onMouseDown={(e) => { e.preventDefault(); insertSuggestion(s); }}
              data-testid={`suggest-${s}`}>
              <span className="text-blue-400">{'{'}</span>{s}<span className="text-blue-400">{'}'}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};


const ProjectDetail = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [bitacoraText, setBitacoraText] = useState('');
  const [bitacoraDate, setBitacoraDate] = useState(new Date().toISOString().split('T')[0]);
  const [bitacoraSubmitting, setBitacoraSubmitting] = useState(false);
  const [selectedStoreId, setSelectedStoreId] = useState(null);

  // Notificaciones secuenciales
  const [notifDialogOpen, setNotifDialogOpen] = useState(false);
  const [notifTarget, setNotifTarget] = useState(null); // {type: 'client'|'bank', bankName?}
  const [notifSending, setNotifSending] = useState(null); // level string being sent
  const [resolvedRecipients, setResolvedRecipients] = useState([]);

  // Otras Notificaciones (ad-hoc avanzado)
  const [emailDialogOpen, setEmailDialogOpen] = useState(false);
  const [emailForm, setEmailForm] = useState({ recipients: [''], subject: '', message: '', templateId: '' });
  const [emailFiles, setEmailFiles] = useState([]);
  const [emailSending, setEmailSending] = useState(false);
  const [suggestedContacts, setSuggestedContacts] = useState([]);
  const [emailTemplates, setEmailTemplates] = useState([]);
  const [attachMatrix, setAttachMatrix] = useState(false);
  const fileInputRef = useRef(null);

  // Bitácora email detail viewer
  const [emailDetailOpen, setEmailDetailOpen] = useState(false);
  const [emailDetailData, setEmailDetailData] = useState(null);

  // Preview de email (ahora editable)
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
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

  // VTID Generator
  const [vtidPrefix, setVtidPrefix] = useState('');
  const [vtidStartNumber, setVtidStartNumber] = useState(1);
  const [vtidGenerating, setVtidGenerating] = useState(false);
  const [vtidDeleting, setVtidDeleting] = useState(false);

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
  const canEditMatrix = currentUser.role === 'admin' ||
    currentUser.user_id === project?.assigned_to ||
    (project?.assigned_to && currentUser.user_id === (() => {
      // Check if current user is supervisor of the implementer (simplified client-side check)
      return project?.implementer_supervisor_id;
    })());

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

  // Matrix update para stores (multitienda)
  const updateStoreMatrixQuantity = async (storeId, bankName, productName, phase, expected, processed) => {
    try {
      await api.put(`/projects/${projectId}/stores/${storeId}/matrix/phase`, {
        bank_name: bankName, product_name: productName, phase,
        completed: processed >= expected && expected > 0,
        expected, processed
      });
      fetchProject();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al actualizar fase de tienda');
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
      await api.put(`/projects/${projectId}/stores/${storeId}/matrix/phase`, { bank_name: bankName, product_name: productName, phase, completed: !completed });
      fetchProject();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error actualizando fase de tienda'); }
  };

  // ==================== SEQUENTIAL NOTIFICATIONS ====================
  const openNotifDialog = async (type, bankName) => {
    setNotifTarget({ type, bankName });
    setAdditionalRecipients('');
    fetchSuggestedContacts();
    // Resolver destinatarios reales desde el backend
    try {
      const res = await api.post(`/projects/${projectId}/preview-notification`, {
        target: type,
        bank_name: bankName || null,
      });
      setResolvedRecipients(res.data.recipients || []);
    } catch {
      setResolvedRecipients([]);
    }
    setNotifDialogOpen(true);
  };

  const getEntityHistory = (target) => {
    if (!project) return [];
    const nh = project.notification_history || {};
    const key = target.type === 'client' ? 'client' : `bank_${target.bankName}`;
    return nh[key] || [];
  };

  const NOTIFICATION_PREFIXES = ['Primer Envío', 'Primer Recordatorio', 'Segundo Recordatorio', 'Tercer Recordatorio'];
  const [additionalRecipients, setAdditionalRecipients] = useState('');

  const sendNotification = async () => {
    setNotifSending('sending');
    try {
      // Parse additional recipients (comma or semicolon separated)
      const ccList = additionalRecipients
        .split(/[,;]/)
        .map(e => e.trim())
        .filter(e => e && e.includes('@'));

      const res = await api.post(`/projects/${projectId}/send-notification`, {
        target: notifTarget.type,
        bank_name: notifTarget.bankName || null,
        additional_recipients: ccList.length > 0 ? ccList : null,
      });
      toast.success(res.data.message);
      setAdditionalRecipients('');
      fetchProject();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al enviar notificación');
    } finally { setNotifSending(null); }
  };

  // ==================== OTRAS NOTIFICACIONES (AD-HOC) ====================
  const openEmailDialog = () => {
    setEmailForm({ recipients: [''], subject: '', message: '', templateId: '' });
    setEmailFiles([]);
    setAttachMatrix(false);
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

  const handleTemplateSelect = (templateId) => {
    if (templateId === 'blank') {
      setEmailForm(prev => ({ ...prev, templateId: '', subject: '', message: '' }));
      return;
    }
    const tpl = emailTemplates.find(t => t.template_id === templateId);
    if (tpl) {
      // Use body field if available, otherwise use empty string (body_html is for system templates)
      const messageBody = tpl.body || '';
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
    if (emailForm.message.length > 1000) { toast.error('Máximo 1000 caracteres'); return; }

    setEmailSending(true);
    try {
      const formData = new FormData();
      formData.append('recipients', JSON.stringify(validRecipients));
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
    setPreviewLoading(true);
    try {
      const res = await api.post(`/projects/${projectId}/preview-notification`, {
        target: target || 'client',
        bank_name: bankName || null,
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
        const ccList = additionalRecipients
          .split(/[,;]/)
          .map(e => e.trim())
          .filter(e => e && e.includes('@'));

        const res = await api.post(`/projects/${projectId}/send-notification`, {
          target: previewContext.target,
          bank_name: previewContext.bankName || null,
          additional_recipients: ccList.length > 0 ? ccList : null,
          custom_html: editedHtml,
          custom_subject: editedSubject,
        });
        toast.success(res.data.message);
        setPreviewOpen(false);
        setNotifDialogOpen(false);
        setAdditionalRecipients('');
        fetchProject();
      } else if (previewContext?.type === 'adhoc') {
        const validRecipients = emailForm.recipients.filter(r => r.trim());
        const formData = new FormData();
        formData.append('recipients', JSON.stringify(validRecipients));
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

  // ==================== SECURITY LOCK: TICKET NUMBER ====================
  const handleSaveTicket = async () => {
    if (!ticketInput.trim()) { toast.error('Ingrese el Número de Ticket'); return; }
    setTicketSaving(true);
    try {
      await api.put(`/projects/${projectId}/ticket`, { ticket_number: ticketInput.trim() });
      toast.success('Ticket registrado exitosamente');
      setTicketInput('');
      fetchProject();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al registrar ticket'); }
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
                  project.status === 'Pendiente por Asignar' ? 'bg-amber-100 text-amber-800 border-amber-200' :
                  project.status === 'Asignado / En Proceso' ? 'bg-blue-100 text-blue-800 border-blue-200' :
                  project.status === 'Suspendido por Cliente' ? 'bg-red-100 text-red-800 border-red-200' :
                  project.status === 'Suspendido por Banco' ? 'bg-orange-100 text-orange-800 border-orange-200' :
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
                  <Button variant="outline" size="sm" onClick={openEmailDialog} className="text-xs gap-1 border-indigo-200 text-indigo-600 hover:bg-indigo-50 h-7 px-2" data-testid="adhoc-email-btn">
                    <Megaphone size={12} />Notificaciones
                  </Button>
                  <Button variant="outline" size="sm" onClick={openTemplatesAdmin} className="text-xs gap-1 border-slate-200 text-slate-600 hover:bg-slate-50 h-7 px-2" data-testid="manage-templates-btn">
                    <ClipboardList size={12} />Plantillas
                  </Button>
                </div>
              </div>
            </div>

            {/* Bloques de información en grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              {/* Bloque 1: Datos del Proyecto */}
              <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-3">
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Datos del Proyecto</p>
                {project.project_type_impl && (
                  <div>
                    <p className="text-xs text-slate-500">Tipo de Proyecto</p>
                    <p className="text-sm font-semibold text-slate-700" data-testid="project-type-impl">
                      {project.project_type_impl === 'pos_fast_track' ? 'POS Stand Alone / Fast Track' :
                       project.project_type_impl === 'vpos_mpos' ? 'VPOS / MPOS' :
                       project.project_type_impl === 'payment_gateway' ? 'Pasarela de Pago' : project.project_type_impl}
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
                <div>
                  <p className="text-xs text-slate-500">Cliente</p>
                  <p className="text-sm font-semibold text-slate-700">{project.client_name}</p>
                  <p className="text-xs text-slate-400">{project.client_rif} — {project.client_sede}</p>
                </div>
                {/* Integrador y Aplicativo */}
                <div className="pt-2 mt-2 border-t border-slate-100 space-y-2">
                  {editingIntegrator ? (
                    <>
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
                    </>
                  ) : (
                    <>
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
                    </>
                  )}
                </div>
              </div>

              {/* Bloque 2: Implementación (incluye servidor) */}
              <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-3">
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Implementación</p>
                <div className="flex items-center gap-3">
                  <CreditCard size={18} className="text-emerald-600 shrink-0" />
                  <div>
                    <p className="text-xs text-slate-500">Modelo de Pinpad</p>
                    <p className="text-sm font-semibold text-slate-700" data-testid="pinpad-model">{project.pinpad_model || '—'}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Building2 size={18} className="text-blue-600 shrink-0" />
                  <div>
                    <p className="text-xs text-slate-500">Banco Patrocinador</p>
                    <p className="text-sm font-semibold text-slate-700" data-testid="sponsor-bank">{project.sponsor_bank_name || '—'}</p>
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
                {project.server_name && (
                  <div className="flex items-center gap-3 pt-1 mt-1 border-t border-slate-100">
                    <Server size={18} className="text-blue-600 shrink-0" />
                    <div>
                      <p className="text-xs text-slate-500">Servidor de Instalación</p>
                      <p className="text-sm font-semibold text-blue-700" data-testid="server-name">{project.server_name}</p>
                    </div>
                  </div>
                )}
              </div>

              {/* Bloque 2.5: Equipos Vinculados — Grid Horizontal */}
              {project.equipments && project.equipments.length > 0 && (
                <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-2" data-testid="equipment-section">
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Modelo y Seriales de Equipos</p>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {project.equipments.map((eq, idx) => (
                      <div key={idx} className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2" data-testid={`equipment-row-${idx}`}>
                        <p className="text-[10px] text-slate-500 truncate">{eq.modelo}</p>
                        <p className="text-xs font-mono font-bold text-slate-800">S/N: {eq.serial}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Bloque 2.7: Pinpads desde Inventario (PYME) — Grid Horizontal */}
              {project.pinpad_serials && project.pinpad_serials.length > 0 && (
                <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-2" data-testid="pinpad-serials-section">
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">POS / Pinpad (Inventario)</p>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {project.pinpad_serials.map((pp, idx) => (
                      <div key={idx} className="bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2" data-testid={`pinpad-serial-row-${idx}`}>
                        <p className="text-[10px] text-emerald-600 truncate">{pp.modelo}</p>
                        <p className="text-xs font-mono font-bold text-emerald-800">S/N: {pp.serial}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Bloque: Seriales de Implementación (esquina superior derecha) */}
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
                      onClick={handleSaveTicket}
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

          {/* ============ NOTIFICATION SECTION ============ */}
          <div className="mb-6">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-bold text-slate-900">Matriz de Implementación</h2>
              <Button onClick={() => openNotifDialog('client')} disabled={isLocked} className={`gap-2 ${isLocked ? 'bg-slate-300 cursor-not-allowed' : clientNotified ? 'bg-emerald-500 hover:bg-emerald-600' : 'bg-amber-500 hover:bg-amber-600'} text-white`} data-testid="notifications-btn">
                {clientNotified ? <BellRing size={16} /> : <Bell size={16} />}
                Notificaciones
              </Button>
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
                          return isMultistore ? (
                            <MultistoreBankSection key={bankName} bankName={bankName} products={products}
                              rollupBankData={rollup.bank_progress?.[bankName] || {}}
                              bankExecutedLevels={bankExecutedLevels} onOpenNotif={() => openNotifDialog('bank', bankName)} />
                          ) : (
                            <SingleBankSection key={bankName} bankName={bankName} products={products}
                              matrixData={matrix[bankName]} onUpdateQuantity={updateMatrixQuantity}
                              bankExecutedLevels={bankExecutedLevels} onOpenNotif={() => openNotifDialog('bank', bankName)}
                              readOnly={!canEditMatrix} expectedQty={project.box_count || project.cantidad_cajas || 0} />
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </div>

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

          {/* ============ VTID GENERATOR ============ */}
          {project.ticket_number && (
            <div className="mb-6" data-testid="vtid-section">
              <h2 className="text-lg font-bold text-slate-900 mb-3 flex items-center gap-2">
                <Hash size={20} className="text-indigo-600" />Terminales Virtuales (VTID)
              </h2>

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
          <DialogContent className="max-w-lg" data-testid="notif-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><Bell size={20} className="text-amber-500" />Notificaciones — {notifTarget?.type === 'client' ? 'Cliente' : notifTarget?.bankName}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-2">
              {/* Mostrar TODOS los destinatarios del proyecto agrupados */}
              <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">
                <p className="text-xs font-medium text-slate-500 uppercase mb-2">Destinatarios del Proyecto</p>
                {(() => {
                  const clientContacts = suggestedContacts.filter(c => c.source === 'client');
                  const bankContacts = suggestedContacts.filter(c => c.source === 'bank');
                  const hasContacts = suggestedContacts.length > 0;
                  return hasContacts ? (
                    <div className="space-y-3">
                      {clientContacts.length > 0 && (
                        <div>
                          <p className="text-[10px] font-semibold text-indigo-600 uppercase mb-1">Cliente</p>
                          <div className="space-y-1">
                            {clientContacts.map((c, i) => (
                              <div key={`client-${i}`} className="flex items-center gap-2 text-sm">
                                <Mail size={12} className="text-indigo-400 shrink-0" />
                                <span className="text-slate-700">{c.email}</span>
                                <span className="text-[10px] text-slate-400">({c.label})</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {bankContacts.length > 0 && (
                        <div>
                          <p className="text-[10px] font-semibold text-blue-600 uppercase mb-1">Bancos</p>
                          <div className="space-y-1">
                            {bankContacts.map((c, i) => (
                              <div key={`bank-${i}`} className="flex items-center gap-2 text-sm">
                                <Mail size={12} className="text-blue-400 shrink-0" />
                                <span className="text-slate-700">{c.email}</span>
                                <span className="text-[10px] text-slate-400">({c.label})</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <p className="text-xs text-slate-400">No hay contactos registrados para este proyecto</p>
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

                    {/* Próximo envío */}
                    <div className={`p-4 rounded-lg border-2 transition-all ${
                      sendCount === 0 ? 'bg-blue-50 border-blue-200' : 'bg-amber-50 border-amber-200'
                    }`} data-testid="next-send-block">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <div className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold ${
                            sendCount === 0 ? 'bg-blue-500 text-white' : 'bg-amber-500 text-white'
                          }`}>{sendCount + 1}</div>
                          <div>
                            <p className="text-sm font-semibold text-slate-800">Próximo envío: [{nextPrefix}]</p>
                            <p className="text-xs text-slate-500">
                              Plantilla: <span className="font-medium">{notifTarget?.type === 'client' ? 'Notificación de Proyecto — Cliente' : 'Notificación de Proyecto — Banco'}</span>
                            </p>
                          </div>
                        </div>
                      </div>

                      {/* Destinatarios resueltos */}
                      <div className="mb-3 space-y-2">
                        <div className="bg-white rounded-lg p-2.5 border border-slate-200">
                          <p className="text-[10px] font-semibold text-slate-400 uppercase mb-1">Destinatarios Principales (TO) — desde Base de Datos</p>
                          <div className="flex flex-wrap gap-1.5">
                            {resolvedRecipients.length === 0 ? (
                              <span className="text-xs text-red-500 italic">Sin correos registrados en la ficha</span>
                            ) : (
                              resolvedRecipients.map((email, i) => (
                                <span key={i} className="px-2 py-0.5 text-xs bg-emerald-50 border border-emerald-200 rounded text-emerald-700 font-mono" data-testid={`resolved-recipient-${i}`}>
                                  {email}
                                </span>
                              ))
                            )}
                          </div>
                        </div>

                        {/* Campo de destinatarios adicionales (CC) */}
                        <div className="bg-white rounded-lg p-2.5 border border-slate-200">
                          <label className="text-[10px] font-semibold text-slate-400 uppercase block mb-1">
                            Destinatarios Adicionales (CC) — separados por coma
                          </label>
                          <input
                            type="text"
                            value={additionalRecipients}
                            onChange={(e) => setAdditionalRecipients(e.target.value)}
                            placeholder="gerente@empresa.com, compras@empresa.com"
                            className="w-full px-3 py-1.5 text-sm border border-slate-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-400 focus:border-blue-400"
                            data-testid="additional-recipients-input"
                          />
                          <p className="text-[10px] text-slate-400 mt-1">
                            Estos correos recibirán copia (CC) de la notificación
                          </p>
                        </div>
                      </div>

                      {/* Panel de Variables Disponibles */}
                      <details className="bg-indigo-50 rounded-lg border border-indigo-200 mb-3">
                        <summary className="px-3 py-2 text-[10px] font-semibold text-indigo-700 cursor-pointer select-none flex items-center gap-1">
                          <ClipboardList size={12} />Variables disponibles para la plantilla
                        </summary>
                        <div className="px-3 pb-2 flex flex-wrap gap-1">
                          {['{Nombre_Cliente}', '{Contacto_Principal}', '{Datos_Contacto}', '{Nombre_Sucursal}', '{Cantidad_Cajas}', '{Integrador}', '{Aplicativo_Integracion}', '{Nombre_Implementador}', '{Correo_Implementador}', '{Telefono_Implementador}', '{Matriz_Bancos_Productos}', '{Lista_VTID}', '{Modelo_Seriales_Equipos}', '{project_number}', '{ticket_number}', '{quote_number}'].map(v => (
                            <span key={v} onClick={() => { navigator.clipboard.writeText(v); toast.success(`${v} copiado`); }}
                              className="text-[10px] px-1.5 py-0.5 rounded bg-white border border-indigo-200 text-indigo-600 hover:bg-indigo-100 cursor-pointer transition-all"
                              title={`Clic para copiar ${v}`}>{v}</span>
                          ))}
                        </div>
                      </details>

                      {/* Botones de acción */}
                      <div className="flex items-center justify-end gap-2">
                        <Button size="sm" variant="outline" className="h-8 text-xs border-blue-200 text-blue-600 hover:bg-blue-50"
                          disabled={previewLoading} onClick={() => previewNotification(notifTarget?.type, notifTarget?.bankName)}
                          data-testid="preview-next-notif">
                          <Eye size={12} className="mr-1" />{previewLoading ? '...' : 'Vista Previa'}
                        </Button>
                        <Button size="sm" className={`h-8 text-xs text-white ${
                          sendCount === 0 ? 'bg-blue-500 hover:bg-blue-600' : 'bg-amber-500 hover:bg-amber-600'
                        }`}
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

        {/* ==================== OTRAS NOTIFICACIONES DIALOG ==================== */}
        <Dialog open={emailDialogOpen} onOpenChange={(o) => { if (!emailSending) setEmailDialogOpen(o); }}>
          <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="adhoc-email-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><Megaphone size={20} className="text-indigo-500" />Otras Notificaciones</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              {/* Contactos sugeridos */}
              {suggestedContacts.length > 0 && (
                <div>
                  <Label className="text-xs font-medium text-slate-500 uppercase">Contactos del Proyecto</Label>
                  <div className="flex flex-wrap gap-1.5 mt-1.5">
                    {suggestedContacts.map((c, i) => (
                      <button key={i} onClick={() => addSuggestedContact(c.email)}
                        className={`text-xs px-2.5 py-1.5 rounded-full border transition-all ${
                          emailForm.recipients.includes(c.email) ? 'bg-indigo-100 border-indigo-300 text-indigo-700' : 'bg-slate-50 border-slate-200 text-slate-600 hover:border-indigo-200'
                        }`} data-testid={`suggested-contact-${i}`} title={c.label}>
                        {c.label.length > 30 ? c.label.slice(0, 30) + '...' : c.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Destinatarios */}
              <div>
                <Label className="text-sm font-medium">Destinatarios <span className="text-red-500">*</span></Label>
                <div className="space-y-2 mt-1.5">
                  {emailForm.recipients.map((r, idx) => (
                    <div key={idx} className="flex items-center gap-2">
                      <Input type="email" placeholder="correo@ejemplo.com" value={r} onChange={e => updateRecipient(idx, e.target.value)}
                        className="flex-1 h-9 text-sm" data-testid={`email-recipient-${idx}`} />
                      {emailForm.recipients.length > 1 && <button onClick={() => removeRecipient(idx)} className="text-red-400 hover:text-red-600"><X size={16} /></button>}
                    </div>
                  ))}
                  <Button variant="ghost" size="sm" onClick={addRecipient} className="text-xs text-indigo-600" data-testid="add-recipient-btn"><Plus size={14} className="mr-1" />Agregar</Button>
                </div>
              </div>

              {/* Plantilla predefinida / Hoja en blanco */}
              <div>
                <Label className="text-sm font-medium">Plantilla</Label>
                <Select value={emailForm.templateId || 'blank'} onValueChange={handleTemplateSelect}>
                  <SelectTrigger className="mt-1 h-9" data-testid="template-select"><SelectValue placeholder="Seleccionar plantilla..." /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="blank">Hoja en blanco</SelectItem>
                    {emailTemplates.map(t => <SelectItem key={t.template_id} value={t.template_id}>{t.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>

              {/* Asunto */}
              <div>
                <Label className="text-sm font-medium">Asunto <span className="text-red-500">*</span></Label>
                <Input placeholder="Asunto del correo..." value={emailForm.subject}
                  onChange={e => setEmailForm(prev => ({ ...prev, subject: e.target.value }))}
                  className="mt-1 h-9 text-sm" data-testid="email-subject" />
              </div>

              {/* Mensaje */}
              <div>
                <div className="flex items-center justify-between">
                  <Label className="text-sm font-medium">Mensaje <span className="text-red-500">*</span></Label>
                  <span className={`text-[10px] ${(emailForm.message?.length || 0) > 1000 ? 'text-red-500 font-semibold' : 'text-slate-400'}`}>{emailForm.message?.length || 0}/1000</span>
                </div>
                <Textarea placeholder="Escriba su mensaje aquí..." value={emailForm.message}
                  onChange={e => setEmailForm(prev => ({ ...prev, message: e.target.value }))}
                  className="mt-1 text-sm min-h-[180px] resize-y" maxLength={1000} data-testid="email-message" />
              </div>

              {/* Adjuntos + Matriz */}
              <div>
                <Label className="text-sm font-medium">Adjuntos</Label>
                <div className="mt-1.5 flex items-center gap-2 flex-wrap">
                  <input ref={fileInputRef} type="file" multiple accept=".jpg,.jpeg,.png,.pdf,.doc,.docx,.xls,.xlsx,.txt" className="hidden" onChange={handleFileSelect} />
                  <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()} className="text-xs gap-1.5" data-testid="attach-files-btn"><Paperclip size={14} />Archivos</Button>
                  <Button variant="outline" size="sm" onClick={() => { const i = document.createElement('input'); i.type = 'file'; i.accept = 'image/jpeg,image/png'; i.multiple = true; i.onchange = (ev) => setEmailFiles(prev => [...prev, ...Array.from(ev.target.files || [])]); i.click(); }}
                    className="text-xs gap-1.5" data-testid="attach-images-btn"><Image size={14} />Imágenes</Button>
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
                {attachMatrix && <p className="text-[10px] text-indigo-500 mt-1">Se adjuntará una tabla HTML con el estatus actual de la matriz de seguimiento</p>}
              </div>

              {/* Variables disponibles */}
              <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">
                <p className="text-[10px] font-semibold text-slate-500 uppercase mb-1.5">Variables disponibles (escriba en el mensaje para auto-inyectar)</p>
                <div className="flex flex-wrap gap-1">
                  {['{Nombre_Cliente}', '{Contacto_Principal}', '{Datos_Contacto}', '{Nombre_Sucursal}', '{Cantidad_Cajas}', '{Integrador}', '{Aplicativo_Integracion}', '{Nombre_Implementador}', '{Correo_Implementador}', '{Telefono_Implementador}', '{Matriz_Bancos_Productos}', '{Lista_VTID}', '{Modelo_Seriales_Equipos}', '{project_number}', '{ticket_number}', '{quote_number}'].map(v => (
                    <button key={v} type="button" onClick={() => setEmailForm(prev => ({ ...prev, message: prev.message + ` ${v}` }))}
                      className="text-[10px] px-1.5 py-0.5 rounded bg-white border border-slate-300 text-slate-600 hover:bg-indigo-50 hover:border-indigo-300 hover:text-indigo-700 transition-all cursor-pointer"
                      title={`Insertar ${v}`}>{v}</button>
                  ))}
                </div>
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-3 pt-3 border-t">
                <Button variant="outline" onClick={() => setEmailDialogOpen(false)} disabled={emailSending}>Cancelar</Button>
                <Button variant="outline" onClick={previewAdhocEmail}
                  disabled={previewLoading || !emailForm.subject.trim() || !emailForm.message.trim()}
                  className="border-blue-200 text-blue-600 hover:bg-blue-50 gap-1.5" data-testid="preview-adhoc-email-btn">
                  <Eye size={14} />{previewLoading ? 'Cargando...' : 'Vista Previa'}
                </Button>
                <Button onClick={handleSendAdhocEmail}
                  disabled={emailSending || !emailForm.subject.trim() || !emailForm.message.trim() || !emailForm.recipients.some(r => r.trim())}
                  className="bg-indigo-600 hover:bg-indigo-700 text-white gap-1.5" data-testid="send-adhoc-email-btn">
                  <Send size={14} />{emailSending ? 'Enviando...' : 'Enviar Correo'}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* ==================== EMAIL DETAIL VIEWER ==================== */}
        <Dialog open={emailDetailOpen} onOpenChange={setEmailDetailOpen}>
          <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto" data-testid="email-detail-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><Eye size={20} className="text-indigo-500" />Detalle del Correo</DialogTitle>
            </DialogHeader>
            {emailDetailData && (
              <div className="space-y-3">
                <div className="bg-slate-50 rounded-lg p-3 space-y-2 text-sm">
                  <div><span className="font-medium text-slate-600">Asunto:</span> <span className="text-slate-800">{emailDetailData.subject}</span></div>
                  <div><span className="font-medium text-slate-600">Destinatarios:</span> <span className="text-slate-800">{emailDetailData.recipients?.join(', ')}</span></div>
                  {emailDetailData.level && <div><span className="font-medium text-slate-600">Nivel:</span> <span className="text-slate-800">{emailDetailData.level}</span></div>}
                  <div><span className="font-medium text-slate-600">Fecha:</span> <span className="text-slate-800">{emailDetailData.sent_at ? new Date(emailDetailData.sent_at).toLocaleString('es-VE') : '—'}</span></div>
                  {emailDetailData.attachments?.length > 0 && (
                    <div><span className="font-medium text-slate-600">Adjuntos:</span> <span className="text-slate-800">{emailDetailData.attachments.map(a => a.filename).join(', ')}</span></div>
                  )}
                </div>
                <div className="border rounded-lg p-4">
                  <p className="text-xs font-medium text-slate-500 uppercase mb-2">Contenido</p>
                  {emailDetailData.message ? (
                    <div className="text-sm text-slate-800 whitespace-pre-wrap">{emailDetailData.message}</div>
                  ) : emailDetailData.html_content ? (
                    <div className="text-sm text-slate-800 prose prose-sm max-w-none" dangerouslySetInnerHTML={{ __html: emailDetailData.html_content }} />
                  ) : (
                    <p className="text-sm text-slate-400">Sin contenido disponible</p>
                  )}
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* ==================== TEMPLATES ADMIN DIALOG ==================== */}
        <Dialog open={templatesDialogOpen} onOpenChange={setTemplatesDialogOpen}>
          <DialogContent className="max-w-5xl" data-testid="templates-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><ClipboardList size={20} className="text-slate-600" />Gestionar Plantillas de Correo</DialogTitle>
            </DialogHeader>
            <div className="grid grid-cols-12 gap-4 min-h-[400px]">
              {/* Lista de plantillas (col-3) */}
              <div className="col-span-3 border-r border-slate-200 pr-4">
                <p className="text-xs font-semibold text-slate-500 uppercase mb-3">Plantillas Registradas</p>
                <div className="space-y-2 max-h-[450px] overflow-y-auto">
                  {emailTemplates.length === 0 ? (
                    <p className="text-sm text-slate-400 text-center py-8">No hay plantillas registradas</p>
                  ) : emailTemplates.map(t => (
                    <div key={t.template_id}
                      className={`p-3 rounded-lg border cursor-pointer transition-all ${editingTemplateId === t.template_id ? 'bg-blue-50 border-blue-300' : 'bg-white border-slate-200 hover:border-slate-300'}`}
                      data-testid={`template-item-${t.template_id}`}>
                      <p className="text-sm font-semibold text-slate-800">{t.name}</p>
                      <p className="text-xs text-slate-500 mt-0.5 truncate">Asunto: {t.subject}</p>
                      {t.body && <p className="text-xs text-slate-400 mt-1 line-clamp-2">{t.body.slice(0, 100)}{t.body.length > 100 ? '...' : ''}</p>}
                      <div className="flex gap-2 mt-2">
                        <Button variant="outline" size="sm" className="h-7 text-xs gap-1" data-testid={`edit-template-${t.template_id}`}
                          onClick={() => { setEditingTemplateId(t.template_id); setTemplateForm({ name: t.name, subject: t.subject, body: t.body_html || t.body || '' }); }}>
                          Editar
                        </Button>
                        <Button variant="outline" size="sm" className="h-7 text-xs gap-1 text-red-500 hover:text-red-700 border-red-200 hover:border-red-300"
                          data-testid={`delete-template-${t.template_id}`}
                          onClick={() => handleDeleteTemplate(t.template_id)}>
                          Eliminar
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Formulario de edición (col-6) */}
              <div className="col-span-6">
                <p className="text-xs font-semibold text-slate-500 uppercase mb-3">{editingTemplateId ? 'Editar Plantilla' : 'Nueva Plantilla'}</p>
                <div className="space-y-3">
                  <div>
                    <Label className="text-sm">Nombre <span className="text-red-500">*</span></Label>
                    <Input placeholder="Ej: Solicitud de acceso, Confirmación de pruebas..." value={templateForm.name}
                      onChange={e => setTemplateForm(p => ({ ...p, name: e.target.value }))}
                      className="h-9 text-sm mt-1" data-testid="template-name" />
                  </div>
                  <div>
                    <Label className="text-sm">Asunto <span className="text-red-500">*</span></Label>
                    <Input placeholder="Asunto predeterminado del correo" value={templateForm.subject}
                      onChange={e => setTemplateForm(p => ({ ...p, subject: e.target.value }))}
                      className="h-9 text-sm mt-1" data-testid="template-subject" />
                  </div>
                  <div>
                    <Label className="text-sm">Cuerpo del mensaje</Label>
                    <TemplateBodyEditor
                      value={templateForm.body}
                      onChange={val => setTemplateForm(p => ({ ...p, body: val }))}
                    />
                  </div>
                  <div className="flex gap-2 pt-2">
                    <Button onClick={handleSaveTemplate} disabled={templateSaving || !templateForm.name.trim() || !templateForm.subject.trim()}
                      className="bg-blue-600 hover:bg-blue-700 text-white text-sm" data-testid="save-template-btn">
                      {templateSaving ? 'Guardando...' : editingTemplateId ? 'Actualizar Plantilla' : 'Crear Plantilla'}
                    </Button>
                    {editingTemplateId && (
                      <Button variant="outline" onClick={() => { setEditingTemplateId(null); setTemplateForm({ name: '', subject: '', body: '' }); }}
                        className="text-sm">Nueva Plantilla</Button>
                    )}
                  </div>
                </div>
              </div>

              {/* Panel Diccionario de Variables (col-3) */}
              <div className="col-span-3 border-l border-slate-200 pl-4">
                <p className="text-xs font-semibold text-slate-500 uppercase mb-3">Variables Disponibles</p>
                <p className="text-[10px] text-slate-400 mb-3">Haz clic en una variable para copiarla al portapapeles e insertarla en el editor.</p>
                <div className="space-y-3 max-h-[430px] overflow-y-auto pr-1">
                  {[
                    { cat: 'Cliente', icon: <Building2 size={14} className="text-blue-500" />, vars: [
                      { token: 'Nombre_Cliente', desc: 'Razón social del cliente' },
                      { token: 'Rif_Cliente', desc: 'RIF del cliente' },
                      { token: 'Contacto_Principal', desc: 'Nombre del contacto' },
                      { token: 'Datos_Contacto', desc: 'Contacto + Tel + Email' },
                      { token: 'Telefono_Contacto', desc: 'Teléfono del contacto' },
                      { token: 'Email_Contacto', desc: 'Correo del contacto' },
                    ]},
                    { cat: 'Proyecto', icon: <FileText size={14} className="text-violet-500" />, vars: [
                      { token: 'Nro_Proyecto', desc: 'Número del proyecto' },
                      { token: 'Ticket_Nro', desc: 'Número de ticket' },
                      { token: 'Tipo_Proyecto', desc: 'Tipo de implementación' },
                      { token: 'Fecha_Asignacion', desc: 'Fecha de asignación' },
                      { token: 'Nombre_Sucursal', desc: 'Sucursal del cliente' },
                      { token: 'Cantidad_Cajas', desc: 'Cantidad de cajas' },
                    ]},
                    { cat: 'Infraestructura', icon: <Server size={14} className="text-emerald-500" />, vars: [
                      { token: 'Servidor_Instalacion', desc: 'Servidor asignado' },
                      { token: 'Nombre_Implementador', desc: 'Implementador asignado' },
                      { token: 'Correo_Implementador', desc: 'Correo del implementador' },
                      { token: 'Integrador', desc: 'Nombre del integrador' },
                      { token: 'Aplicativo_Integracion', desc: 'App de integración' },
                    ]},
                    { cat: 'Hardware', icon: <CreditCard size={14} className="text-amber-500" />, vars: [
                      { token: 'Modelo_Seriales_POS', desc: 'Tabla de POS/Pinpad' },
                      { token: 'Modelo_Seriales_Equipos', desc: 'Tabla de equipos' },
                      { token: 'Lista_VTID', desc: 'Lista de VTIDs' },
                      { token: 'Matriz_Bancos_Productos', desc: 'Matriz de bancos' },
                    ]},
                  ].map(group => (
                    <div key={group.cat}>
                      <div className="flex items-center gap-1.5 mb-1.5">
                        {group.icon}
                        <span className="text-xs font-bold text-slate-700">{group.cat}</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5 mb-2">
                        {group.vars.map(v => (
                          <button key={v.token} title={v.desc}
                            data-testid={`var-token-${v.token}`}
                            className="inline-flex items-center px-2 py-1 text-[11px] font-mono bg-slate-100 hover:bg-blue-100 hover:text-blue-700 border border-slate-200 hover:border-blue-300 rounded-md cursor-pointer transition-all group"
                            onClick={() => {
                              const tag = `{${v.token}}`;
                              try { navigator.clipboard.writeText(tag).then(() => toast.success(`Copiado: ${tag}`)); } catch(e) { toast.success(`Insertado: ${tag}`); }
                              setTemplateForm(p => ({ ...p, body: p.body + tag }));
                            }}>
                            <span className="text-slate-500 group-hover:text-blue-500">{'{'}</span>
                            <span>{v.token}</span>
                            <span className="text-slate-500 group-hover:text-blue-500">{'}'}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* ==================== EMAIL PREVIEW / EDITOR DIALOG ==================== */}
        <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto" data-testid="email-preview-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><Edit3 size={20} className="text-blue-500" />Editor de Envío Final</DialogTitle>
            </DialogHeader>
            {previewData && (
              <div className="space-y-3">
                {/* Editable subject */}
                <div className="bg-slate-50 rounded-lg p-3 space-y-2 text-sm border border-slate-200">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-500 min-w-[70px] shrink-0">Asunto:</span>
                    <Input
                      value={previewSubject}
                      onChange={e => setPreviewSubject(e.target.value)}
                      className="h-8 text-sm font-medium"
                      data-testid="preview-subject-input"
                    />
                  </div>
                  {previewData.recipients && (
                    <div className="flex items-start gap-2">
                      <span className="font-medium text-slate-500 min-w-[70px]">Para:</span>
                      <span className="text-slate-700 text-xs">{previewData.recipients.join(', ')}</span>
                    </div>
                  )}
                  {previewData.entity_label && (
                    <div className="flex items-start gap-2">
                      <span className="font-medium text-slate-500 min-w-[70px]">Destino:</span>
                      <span className="text-slate-700 text-xs">{previewData.entity_label}</span>
                    </div>
                  )}
                </div>

                {/* Variables resolved (collapsible) */}
                {previewData.variables && Object.keys(previewData.variables).length > 0 && (
                  <details className="bg-blue-50 rounded-lg border border-blue-200">
                    <summary className="px-3 py-2 text-xs font-semibold text-blue-700 cursor-pointer select-none">Variables Resueltas ({Object.keys(previewData.variables).length})</summary>
                    <div className="px-3 pb-3 grid grid-cols-2 gap-x-4 gap-y-1">
                      {Object.entries(previewData.variables).map(([k, v]) => (
                        <div key={k} className="flex items-start gap-1.5 text-[11px]">
                          <code className="text-blue-600 font-mono shrink-0">{`{${k}}`}</code>
                          <span className="text-slate-600 truncate" title={String(v)}>{String(v || '—').slice(0, 60)}</span>
                        </div>
                      ))}
                    </div>
                  </details>
                )}

                {/* EDITABLE HTML content */}
                <div className="border rounded-lg overflow-hidden">
                  <div className="bg-slate-100 px-3 py-2 border-b flex items-center justify-between">
                    <p className="text-xs font-semibold text-slate-500 uppercase">Contenido Editable — Modifique antes de enviar</p>
                    <div className="flex items-center gap-1">
                      <Button variant="ghost" size="sm" onClick={handleInsertImage} className="h-7 px-2 text-xs gap-1 text-slate-600 hover:text-indigo-700" data-testid="preview-insert-image-btn">
                        <ImagePlus size={14} />Imagen
                      </Button>
                    </div>
                  </div>

                  {/* Variables insert panel */}
                  <details className="bg-indigo-50 border-b border-indigo-200">
                    <summary className="px-3 py-1.5 text-[10px] font-semibold text-indigo-700 cursor-pointer select-none flex items-center gap-1">
                      <ClipboardList size={11} />Insertar Variable en el editor
                    </summary>
                    <div className="px-3 pb-2 flex flex-wrap gap-1">
                      {['{Nombre_Cliente}', '{Contacto_Principal}', '{Datos_Contacto}', '{Nombre_Sucursal}', '{Cantidad_Cajas}', '{Integrador}', '{Aplicativo_Integracion}', '{Nombre_Implementador}', '{Correo_Implementador}', '{Telefono_Implementador}', '{Matriz_Bancos_Productos}', '{Lista_VTID}', '{Modelo_Seriales_Equipos}', '{project_number}', '{ticket_number}', '{quote_number}'].map(v => (
                        <button key={v} type="button" onClick={() => insertVariableInEditor(v)}
                          className="text-[10px] px-1.5 py-0.5 rounded bg-white border border-indigo-200 text-indigo-600 hover:bg-indigo-100 cursor-pointer transition-all"
                          title={`Insertar ${v} en la posición del cursor`}>{v}</button>
                      ))}
                    </div>
                    <p className="px-3 pb-1.5 text-[9px] text-indigo-400">Las variables insertadas aquí se procesan automáticamente antes del envío.</p>
                  </details>

                  <div
                    ref={editorRef}
                    contentEditable
                    suppressContentEditableWarning
                    onPaste={handleEditorPaste}
                    onDrop={handleEditorDrop}
                    onDragOver={e => e.preventDefault()}
                    className="p-4 bg-white min-h-[300px] max-h-[50vh] overflow-y-auto prose prose-sm max-w-none focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:ring-inset"
                    dangerouslySetInnerHTML={{ __html: previewData.html }}
                    data-testid="preview-editable-content"
                  />
                  <div className="bg-amber-50 px-3 py-1.5 border-t border-amber-200">
                    <p className="text-[10px] text-amber-700">Los cambios realizados aquí solo afectan este envío. La plantilla base NO se modifica. Puede pegar imágenes directamente (Ctrl+V) o arrastrar archivos JPG/PNG.</p>
                  </div>
                </div>

                {/* Action buttons */}
                <div className="flex justify-between items-center pt-2">
                  <Button variant="outline" onClick={() => setPreviewOpen(false)} data-testid="close-preview-btn">Cancelar</Button>
                  <Button
                    onClick={sendFromPreview}
                    disabled={previewSending}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white gap-2"
                    data-testid="preview-send-btn"
                  >
                    <Send size={16} />{previewSending ? 'Enviando...' : 'Enviar Correo'}
                  </Button>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
};


// ==================== SINGLE: Bank Section ====================
// ==================== Mini Pie Chart SVG ====================
const MiniPie = ({ percent, size = 28 }) => {
  const r = (size - 4) / 2;
  const c = size / 2;
  const circumference = 2 * Math.PI * r;
  const offset = circumference - (percent / 100) * circumference;
  const color = percent >= 100 ? '#10b981' : percent >= 50 ? '#3b82f6' : percent > 0 ? '#f59e0b' : '#e2e8f0';
  return (
    <svg width={size} height={size} className="shrink-0">
      <circle cx={c} cy={c} r={r} fill="none" stroke="#e2e8f0" strokeWidth={3} />
      <circle cx={c} cy={c} r={r} fill="none" stroke={color} strokeWidth={3}
        strokeDasharray={circumference} strokeDashoffset={offset}
        strokeLinecap="round" transform={`rotate(-90 ${c} ${c})`} />
      <text x={c} y={c} textAnchor="middle" dominantBaseline="central" fontSize={8} fontWeight="bold" fill={color}>
        {percent}%
      </text>
    </svg>
  );
};

// ==================== SINGLE BANK: Quantity-based Matrix ====================
const SingleBankSection = ({ bankName, products, matrixData, onUpdateQuantity, bankExecutedLevels, onOpenNotif, readOnly, expectedQty }) => {
  const lastLevel = bankExecutedLevels.length > 0 ? bankExecutedLevels[bankExecutedLevels.length - 1] : null;
  return (
    <>
      <tr className="bg-blue-50 border-t-2 border-blue-200">
        <td className="px-4 py-2 text-sm font-bold text-blue-900" colSpan={PHASES.length + 1}><Building2 size={14} className="inline mr-2 text-blue-600" />{bankName}</td>
        <td className="px-3 py-2 text-center">
          <Button size="sm" variant="outline" onClick={onOpenNotif}
            className={`h-7 text-xs ${bankExecutedLevels.length >= 4 ? 'border-emerald-300 text-emerald-700' : bankExecutedLevels.length > 0 ? 'border-blue-300 text-blue-700' : 'border-amber-300 text-amber-700'}`}
            data-testid={`notif-bank-btn-${bankName}`}>
            {bankExecutedLevels.length >= 4 ? <CheckCircle2 size={12} className="mr-1" /> : <Bell size={12} className="mr-1" />}
            {bankExecutedLevels.length > 0 ? `${bankExecutedLevels.length}/4` : 'Notificaciones'}
          </Button>
        </td>
      </tr>
      {products.map(productName => {
        const phases = matrixData[productName] || {};
        return (
          <tr key={productName} className="border-t border-slate-100 hover:bg-slate-50">
            <td className="px-6 py-2.5 text-sm text-slate-700">{productName}</td>
            {PHASES.map(phase => {
              const pd = phases[phase] || {};
              const expected = pd.expected || expectedQty || 0;
              const processed = pd.processed || 0;
              const pct = expected > 0 ? Math.min(Math.round((processed / expected) * 100), 100) : 0;
              return (
                <td key={phase} className="px-2 py-2 text-center border-l border-slate-100">
                  <div className="flex flex-col items-center gap-1">
                    <MiniPie percent={pct} size={28} />
                    <div className="flex items-center gap-0.5">
                      {readOnly ? (
                        <span className="text-[10px] font-mono text-slate-600">{processed}/{expected}</span>
                      ) : (
                        <>
                          <input type="number" min={0} value={processed}
                            onChange={e => onUpdateQuantity(bankName, productName, phase, expected, parseInt(e.target.value) || 0)}
                            className="w-8 h-5 text-[10px] text-center border border-slate-200 rounded font-mono"
                            title="Procesados" data-testid={`qty-proc-${bankName}-${productName}-${phase}`} />
                          <span className="text-[10px] text-slate-400">/</span>
                          <input type="number" min={0} value={expected}
                            onChange={e => onUpdateQuantity(bankName, productName, phase, parseInt(e.target.value) || 0, processed)}
                            className="w-8 h-5 text-[10px] text-center border border-slate-200 rounded font-mono"
                            title="Esperados" data-testid={`qty-exp-${bankName}-${productName}-${phase}`} />
                        </>
                      )}
                    </div>
                  </div>
                </td>);
            })}
            <td className="px-3 py-2.5 text-center border-l border-slate-100">
              {(() => {
                const totalPhases = PHASES.length;
                const completedPhases = PHASES.filter(p => {
                  const pd = phases[p] || {};
                  return (pd.processed || 0) >= (pd.expected || 0) && (pd.expected || 0) > 0;
                }).length;
                return <span className="text-xs font-bold text-slate-500">{completedPhases}/{totalPhases}</span>;
              })()}
            </td>
          </tr>);
      })}
    </>
  );
};


// ==================== MULTISTORE: Bank Section (Read-Only) ====================
const MultistoreBankSection = ({ bankName, products, rollupBankData, bankExecutedLevels, onOpenNotif }) => {
  return (
    <>
      <tr className="bg-blue-50 border-t-2 border-blue-200">
        <td className="px-4 py-2 text-sm font-bold text-blue-900"><Building2 size={14} className="inline mr-2 text-blue-600" />{bankName}</td>
        <td className="px-4 py-2 text-center text-xs text-blue-600 font-medium">
          {(() => { const pcts = products.map(p => rollupBankData[p] || 0); return `Promedio: ${pcts.length > 0 ? Math.round(pcts.reduce((a, b) => a + b, 0) / pcts.length) : 0}%`; })()}
        </td>
        <td className="px-3 py-2 text-center">
          <Button size="sm" variant="outline" onClick={onOpenNotif}
            className={`h-7 text-xs ${bankExecutedLevels.length >= 4 ? 'border-emerald-300 text-emerald-700' : bankExecutedLevels.length > 0 ? 'border-blue-300 text-blue-700' : 'border-amber-300 text-amber-700'}`}
            data-testid={`notif-bank-btn-${bankName}`}>
            {bankExecutedLevels.length >= 4 ? <CheckCircle2 size={12} className="mr-1" /> : <Bell size={12} className="mr-1" />}
            {bankExecutedLevels.length > 0 ? `${bankExecutedLevels.length}/4` : 'Notificaciones'}
          </Button>
        </td>
      </tr>
      {products.map(productName => {
        const pct = rollupBankData[productName] || 0;
        return (
          <tr key={productName} className="border-t border-slate-100 hover:bg-slate-50">
            <td className="px-6 py-2.5 text-sm text-slate-700">{productName}</td>
            <td className="px-4 py-2.5 border-l border-slate-100">
              <div className="flex items-center gap-3">
                <div className="flex-1 bg-slate-100 rounded-full h-3 overflow-hidden">
                  <div className={`h-full rounded-full transition-all duration-500 ${pct >= 100 ? 'bg-emerald-500' : pct >= 50 ? 'bg-blue-500' : pct > 0 ? 'bg-amber-400' : 'bg-slate-200'}`}
                    style={{ width: `${Math.min(pct, 100)}%` }} data-testid={`rollup-bar-${bankName}-${productName}`} />
                </div>
                <span className={`text-sm font-bold min-w-[45px] text-right ${pct >= 100 ? 'text-emerald-600' : 'text-slate-600'}`}>{pct}%</span>
              </div>
            </td>
            <td className="px-3 py-2.5 text-center border-l border-slate-100 text-xs text-slate-400"><Lock size={12} className="inline text-slate-300" /></td>
          </tr>);
      })}
    </>
  );
};


// ==================== STORE: Bank Section ====================
const StoreBankSection = ({ bankName, products, matrixData, storeId, onUpdateStoreQuantity, phases, readOnly, expectedQty }) => {
  return (
    <>
      <tr className="bg-blue-50 border-t-2 border-blue-200">
        <td className="px-4 py-2 text-sm font-bold text-blue-900" colSpan={phases.length + 2}><Building2 size={14} className="inline mr-2 text-blue-600" />{bankName}</td>
      </tr>
      {products.map(productName => {
        const pd = matrixData[productName] || {};
        return (
          <tr key={productName} className="border-t border-slate-100 hover:bg-slate-50">
            <td className="px-6 py-2.5 text-sm text-slate-700">{productName}</td>
            {phases.map(phase => {
              const d = pd[phase] || {};
              const expected = d.expected || expectedQty || 0;
              const processed = d.processed || 0;
              const pct = expected > 0 ? Math.min(Math.round((processed / expected) * 100), 100) : 0;
              return (
                <td key={phase} className="px-2 py-2 text-center border-l border-slate-100">
                  <div className="flex flex-col items-center gap-1">
                    <MiniPie percent={pct} size={26} />
                    <div className="flex items-center gap-0.5">
                      {readOnly ? (
                        <span className="text-[10px] font-mono text-slate-600">{processed}/{expected}</span>
                      ) : (
                        <>
                          <input type="number" min={0} value={processed}
                            onChange={e => onUpdateStoreQuantity(storeId, bankName, productName, phase, expected, parseInt(e.target.value) || 0)}
                            className="w-8 h-5 text-[10px] text-center border border-slate-200 rounded font-mono"
                            data-testid={`store-qty-proc-${storeId}-${bankName}-${productName}-${phase}`} />
                          <span className="text-[10px] text-slate-400">/</span>
                          <input type="number" min={0} value={expected}
                            onChange={e => onUpdateStoreQuantity(storeId, bankName, productName, phase, parseInt(e.target.value) || 0, processed)}
                            className="w-8 h-5 text-[10px] text-center border border-slate-200 rounded font-mono"
                            data-testid={`store-qty-exp-${storeId}-${bankName}-${productName}-${phase}`} />
                        </>
                      )}
                    </div>
                  </div>
                </td>);
            })}
            <td className="px-3 py-2.5 text-center border-l border-slate-100">
              {(() => {
                const completedPhases = phases.filter(p => {
                  const d = pd[p] || {};
                  return (d.processed || 0) >= (d.expected || 0) && (d.expected || 0) > 0;
                }).length;
                return <span className="text-xs font-bold text-slate-500">{completedPhases}/{phases.length}</span>;
              })()}
            </td>
          </tr>);
      })}
    </>
  );
};

export default ProjectDetail;
