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
  Plus, X, Paperclip, Image, Ticket, ChevronDown, Eye, Megaphone, ClipboardList
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

const NOTIFICATION_LEVELS = [
  'Primera Comunicación',
  'Primer Recordatorio',
  'Segundo Recordatorio',
  'Tercer Recordatorio',
];

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

  // Admin: template management
  const [templatesDialogOpen, setTemplatesDialogOpen] = useState(false);
  const [templateForm, setTemplateForm] = useState({ name: '', subject: '', body: '' });
  const [editingTemplateId, setEditingTemplateId] = useState(null);
  const [templateSaving, setTemplateSaving] = useState(false);

  const fetchProject = useCallback(async () => {
    try {
      const res = await api.get(`/projects/${projectId}`);
      setProject(res.data);
    } catch { toast.error('Error al cargar proyecto'); }
    finally { setLoading(false); }
  }, [projectId]);

  useEffect(() => { fetchProject(); }, [fetchProject]);

  const fetchTemplates = async () => {
    try {
      const res = await api.get('/email-templates');
      setEmailTemplates(res.data);
    } catch { /* ignore */ }
  };

  const fetchSuggestedContacts = async () => {
    try {
      const res = await api.get(`/projects/${projectId}/suggested-contacts`);
      setSuggestedContacts(res.data);
    } catch { /* ignore */ }
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
  const openNotifDialog = (type, bankName) => {
    setNotifTarget({ type, bankName });
    setNotifDialogOpen(true);
  };

  const getEntityHistory = (target) => {
    if (!project) return [];
    const nh = project.notification_history || {};
    const key = target.type === 'client' ? 'client' : `bank_${target.bankName}`;
    return nh[key] || [];
  };

  const sendNotification = async (level) => {
    setNotifSending(level);
    try {
      const res = await api.post(`/projects/${projectId}/send-notification`, {
        target: notifTarget.type,
        bank_name: notifTarget.bankName || null,
        level,
      });
      toast.success(res.data.message);
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
      setEmailForm(prev => ({ ...prev, templateId: templateId, subject: tpl.subject, message: tpl.body }));
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
      let fullMessage = emailForm.message;
      if (attachMatrix) {
        fullMessage += '\n\n---MATRIZ DE SEGUIMIENTO---\n' + generateMatrixHTML();
      }
      const formData = new FormData();
      formData.append('recipients', JSON.stringify(validRecipients));
      formData.append('subject', emailForm.subject);
      formData.append('message', fullMessage);
      emailFiles.forEach(f => formData.append('files', f));
      const res = await api.post(`/projects/${projectId}/send-adhoc-email`, formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      toast.success(res.data.message);
      setEmailDialogOpen(false);
      fetchProject();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al enviar correo'); }
    finally { setEmailSending(false); }
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

  const handleSaveTemplate = async () => {
    if (!templateForm.name.trim() || !templateForm.subject.trim()) { toast.error('Nombre y asunto son obligatorios'); return; }
    setTemplateSaving(true);
    try {
      const fd = new FormData();
      fd.append('name', templateForm.name);
      fd.append('subject', templateForm.subject);
      fd.append('body_content', templateForm.body);
      if (editingTemplateId) {
        await api.put(`/email-templates/${editingTemplateId}`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
        toast.success('Plantilla actualizada');
      } else {
        await api.post('/email-templates', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
        toast.success('Plantilla creada');
      }
      setTemplateForm({ name: '', subject: '', body: '' });
      setEditingTemplateId(null);
      fetchTemplates();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error guardando plantilla'); }
    finally { setTemplateSaving(false); }
  };

  const handleDeleteTemplate = async (tid) => {
    try {
      await api.delete(`/email-templates/${tid}`);
      toast.success('Plantilla eliminada');
      fetchTemplates();
    } catch { toast.error('Error eliminando plantilla'); }
  };

  // ==================== HELPERS ====================
  if (loading || !project) {
    return (<div className="flex min-h-screen bg-white"><Sidebar /><div className="flex-1 flex items-center justify-center"><div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-green-600" /></div></div>);
  }

  const isMultistore = project.project_type === 'multistore';
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
            <div className="flex items-start justify-between">
              <div>
                <h1 className="text-2xl font-bold text-slate-900 mb-1" data-testid="project-title">Detalle para Implementación del Proyecto</h1>
                <div className="flex items-center gap-3">
                  {project.ticket_number ? (
                    <p className="text-lg font-semibold text-indigo-700 flex items-center gap-2" data-testid="project-ticket">
                      <Ticket size={18} className="text-indigo-500" />{project.ticket_number}
                      <span className="text-sm text-slate-400 font-normal">({project.project_number})</span>
                    </p>
                  ) : (<p className="text-lg font-semibold text-slate-700">{project.project_number}</p>)}
                </div>
                <p className="text-sm text-slate-500">{project.client_name} — {project.client_rif} — {project.client_sede}</p>
              </div>
              <div className="text-right space-y-1">
                <span className={`inline-block px-3 py-1 rounded-full text-sm font-medium border ${
                  project.status === 'Pendiente por Asignar' ? 'bg-amber-100 text-amber-800 border-amber-200' :
                  project.status === 'Asignado / En Proceso' ? 'bg-blue-100 text-blue-800 border-blue-200' :
                  project.status === 'Detenido por Cliente/Banco' ? 'bg-red-100 text-red-800 border-red-200' :
                  'bg-emerald-100 text-emerald-800 border-emerald-200'
                }`}>{project.status}</span>
                {project.assigned_to_name && <p className="text-sm text-slate-500">Implementador: <strong>{project.assigned_to_name}</strong></p>}
                {isMultistore && <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-semibold rounded bg-blue-100 text-blue-700 border border-blue-200"><Store size={12} />Multitienda ({project.stores?.length || 0})</span>}
                {rollup.global_progress !== undefined && (
                  <div className="flex items-center gap-2 justify-end mt-1">
                    <div className="w-24 bg-slate-100 rounded-full h-2 overflow-hidden">
                      <div className={`h-full rounded-full ${rollup.global_progress >= 100 ? 'bg-emerald-500' : rollup.global_progress >= 50 ? 'bg-blue-500' : 'bg-amber-400'}`} style={{ width: `${Math.min(rollup.global_progress, 100)}%` }} />
                    </div>
                    <span className="text-xs font-bold text-slate-600" data-testid="header-progress">{rollup.global_progress}%</span>
                  </div>
                )}
                <div className="flex gap-2 justify-end mt-2">
                  <Button variant="outline" size="sm" onClick={openEmailDialog} className="text-xs gap-1.5 border-indigo-200 text-indigo-600 hover:bg-indigo-50" data-testid="adhoc-email-btn">
                    <Megaphone size={14} />Otras Notificaciones
                  </Button>
                  <Button variant="outline" size="sm" onClick={openTemplatesAdmin} className="text-xs gap-1.5 border-slate-200 text-slate-600 hover:bg-slate-50" data-testid="manage-templates-btn">
                    <ClipboardList size={14} />Plantillas
                  </Button>
                </div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4 mt-4 pt-4 border-t border-slate-200">
              <div className="flex items-center gap-3 bg-white rounded-lg p-3 border border-slate-200">
                <CreditCard size={20} className="text-emerald-600" />
                <div><p className="text-xs text-slate-500 uppercase font-medium">Modelo de Pinpad</p><p className="text-sm font-semibold text-slate-800" data-testid="pinpad-model">{project.pinpad_model || '—'}</p></div>
              </div>
              <div className="flex items-center gap-3 bg-white rounded-lg p-3 border border-slate-200">
                <Building2 size={20} className="text-blue-600" />
                <div><p className="text-xs text-slate-500 uppercase font-medium">Banco Patrocinador</p><p className="text-sm font-semibold text-slate-800" data-testid="sponsor-bank">{project.sponsor_bank_name || '—'}</p></div>
              </div>
            </div>
          </div>

          {/* ============ NOTIFICATION SECTION ============ */}
          <div className="mb-6">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-bold text-slate-900">Matriz de Implementación</h2>
              <Button onClick={() => openNotifDialog('client')} className={`gap-2 ${clientNotified ? 'bg-emerald-500 hover:bg-emerald-600' : 'bg-amber-500 hover:bg-amber-600'} text-white`} data-testid="notifications-btn">
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
                              matrixData={matrix[bankName]} onTogglePhase={togglePhase}
                              bankExecutedLevels={bankExecutedLevels} onOpenNotif={() => openNotifDialog('bank', bankName)} />
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
                                matrixData={storeMatrix[bk]} storeId={store.store_id} onTogglePhase={toggleStorePhase} phases={STORE_PHASES} />
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
          <DialogContent className="max-w-md" data-testid="notif-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><Bell size={20} className="text-amber-500" />Notificaciones — {notifTarget?.type === 'client' ? 'Cliente' : notifTarget?.bankName}</DialogTitle>
            </DialogHeader>
            <div className="space-y-3 py-2">
              {NOTIFICATION_LEVELS.map((level, idx) => {
                const history = notifTarget ? getEntityHistory(notifTarget) : [];
                const executedLevels = history.map(h => h.level);
                const isExecuted = executedLevels.includes(level);
                const prevExecuted = idx === 0 || executedLevels.includes(NOTIFICATION_LEVELS[idx - 1]);
                const isEnabled = !isExecuted && prevExecuted;
                const executedEntry = history.find(h => h.level === level);

                return (
                  <div key={level} className={`flex items-center justify-between p-3 rounded-lg border transition-all ${
                    isExecuted ? 'bg-emerald-50 border-emerald-200' : isEnabled ? 'bg-white border-amber-200 hover:border-amber-300' : 'bg-slate-50 border-slate-200 opacity-50'
                  }`} data-testid={`notif-level-${idx}`}>
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                        isExecuted ? 'bg-emerald-500 text-white' : isEnabled ? 'bg-amber-100 text-amber-700 border border-amber-300' : 'bg-slate-200 text-slate-400'
                      }`}>{idx + 1}</div>
                      <div>
                        <p className={`text-sm font-medium ${isExecuted ? 'text-emerald-700' : 'text-slate-700'}`}>{level}</p>
                        {isExecuted && executedEntry && (
                          <p className="text-[10px] text-emerald-500">{executedEntry.sent_by} · {new Date(executedEntry.sent_at).toLocaleString('es-VE')}</p>
                        )}
                      </div>
                    </div>
                    {isExecuted ? (
                      <CheckCircle2 size={20} className="text-emerald-500" />
                    ) : isEnabled ? (
                      <Button size="sm" className="bg-amber-500 hover:bg-amber-600 text-white h-8 text-xs"
                        disabled={notifSending === level} onClick={() => sendNotification(level)}
                        data-testid={`send-notif-${idx}`}>
                        <Send size={12} className="mr-1" />{notifSending === level ? 'Enviando...' : 'Enviar'}
                      </Button>
                    ) : (
                      <Lock size={16} className="text-slate-300" />
                    )}
                  </div>
                );
              })}
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
                  <span className={`text-[10px] ${emailForm.message.length > 1000 ? 'text-red-500 font-semibold' : 'text-slate-400'}`}>{emailForm.message.length}/1000</span>
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

              {/* Actions */}
              <div className="flex justify-end gap-3 pt-3 border-t">
                <Button variant="outline" onClick={() => setEmailDialogOpen(false)} disabled={emailSending}>Cancelar</Button>
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
          <DialogContent className="max-w-xl max-h-[80vh] overflow-y-auto" data-testid="templates-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><ClipboardList size={20} className="text-slate-600" />Gestionar Plantillas de Correo</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              {/* Template form */}
              <div className="bg-slate-50 border rounded-lg p-4 space-y-3">
                <p className="text-sm font-semibold text-slate-700">{editingTemplateId ? 'Editar Plantilla' : 'Nueva Plantilla'}</p>
                <Input placeholder="Nombre de la plantilla" value={templateForm.name} onChange={e => setTemplateForm(p => ({ ...p, name: e.target.value }))}
                  className="h-9 text-sm" data-testid="template-name" />
                <Input placeholder="Asunto predeterminado" value={templateForm.subject} onChange={e => setTemplateForm(p => ({ ...p, subject: e.target.value }))}
                  className="h-9 text-sm" data-testid="template-subject" />
                <Textarea placeholder="Cuerpo del mensaje..." value={templateForm.body} onChange={e => setTemplateForm(p => ({ ...p, body: e.target.value }))}
                  className="text-sm min-h-[80px]" data-testid="template-body" />
                <div className="flex gap-2">
                  <Button size="sm" onClick={handleSaveTemplate} disabled={templateSaving} className="bg-blue-600 hover:bg-blue-700 text-white text-xs" data-testid="save-template-btn">
                    {templateSaving ? 'Guardando...' : editingTemplateId ? 'Actualizar' : 'Crear'}
                  </Button>
                  {editingTemplateId && (
                    <Button size="sm" variant="outline" onClick={() => { setEditingTemplateId(null); setTemplateForm({ name: '', subject: '', body: '' }); }} className="text-xs">Cancelar</Button>
                  )}
                </div>
              </div>

              {/* Template list */}
              <div className="space-y-2">
                {emailTemplates.length === 0 ? (
                  <p className="text-sm text-slate-400 text-center py-4">No hay plantillas registradas</p>
                ) : emailTemplates.map(t => (
                  <div key={t.template_id} className="flex items-center justify-between p-3 bg-white border rounded-lg" data-testid={`template-item-${t.template_id}`}>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-slate-800 truncate">{t.name}</p>
                      <p className="text-xs text-slate-500 truncate">Asunto: {t.subject}</p>
                    </div>
                    <div className="flex gap-1 shrink-0 ml-2">
                      <Button variant="ghost" size="sm" className="text-xs h-7" onClick={() => { setEditingTemplateId(t.template_id); setTemplateForm({ name: t.name, subject: t.subject, body: t.body || '' }); }}>Editar</Button>
                      <Button variant="ghost" size="sm" className="text-xs h-7 text-red-500 hover:text-red-700" onClick={() => handleDeleteTemplate(t.template_id)}>Eliminar</Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
};


// ==================== SINGLE: Bank Section ====================
const SingleBankSection = ({ bankName, products, matrixData, onTogglePhase, bankExecutedLevels, onOpenNotif }) => {
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
              const pd = phases[phase]; const done = pd?.completed || false;
              return (
                <td key={phase} className="px-3 py-2.5 text-center border-l border-slate-100">
                  <button onClick={() => onTogglePhase(bankName, productName, phase, done)}
                    className={`inline-flex items-center justify-center w-7 h-7 rounded-md transition-all ${done ? 'bg-emerald-500 text-white shadow-sm hover:bg-emerald-600' : 'bg-slate-100 text-slate-400 hover:bg-slate-200'}`}
                    title={done ? `${phase}: ${pd?.updated_by || ''}` : `Marcar ${phase}`}
                    data-testid={`phase-${bankName}-${productName}-${phase}`}>
                    {done ? <CheckCircle2 size={16} /> : <Circle size={16} />}
                  </button>
                </td>);
            })}
            <td className="px-3 py-2.5 text-center border-l border-slate-100 text-xs text-slate-400">{Object.values(phases).filter(p => p?.completed).length}/{PHASES.length}</td>
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
const StoreBankSection = ({ bankName, products, matrixData, storeId, onTogglePhase, phases }) => {
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
              const d = pd[phase]; const done = d?.completed || false;
              return (
                <td key={phase} className="px-3 py-2.5 text-center border-l border-slate-100">
                  <button onClick={() => onTogglePhase(storeId, bankName, productName, phase, done)}
                    className={`inline-flex items-center justify-center w-7 h-7 rounded-md transition-all ${done ? 'bg-emerald-500 text-white shadow-sm hover:bg-emerald-600' : 'bg-slate-100 text-slate-400 hover:bg-slate-200'}`}
                    title={done ? `${phase}: ${d?.updated_by || ''}` : `Marcar ${phase}`}
                    data-testid={`store-phase-${storeId}-${bankName}-${productName}-${phase}`}>
                    {done ? <CheckCircle2 size={16} /> : <Circle size={16} />}
                  </button>
                </td>);
            })}
            <td className="px-3 py-2.5 text-center border-l border-slate-100 text-xs text-slate-400">{Object.values(pd).filter(p => p?.completed).length}/{phases.length}</td>
          </tr>);
      })}
    </>
  );
};

export default ProjectDetail;
