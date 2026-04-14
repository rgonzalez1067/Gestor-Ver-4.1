import { useState, useEffect, useRef, Fragment } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import DebouncedInput from '../components/DebouncedInput';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Popover, PopoverContent, PopoverTrigger } from '../components/ui/popover';
import { Calendar } from '../components/ui/calendar';
import { ImportResultPanel } from '../components/ImportResultPanel';
import { Plus, Pencil, Trash2, Upload, FileSpreadsheet, FileText, Search, Filter, Users, CheckCircle, Clock, XCircle, ChevronDown, ChevronUp, Award, Download, AlertCircle, RefreshCw, FileDown, CalendarDays, BookOpen, UserPlus, Phone, Mail, X } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';
import { usePermission } from '../hooks/usePermission';

const INTEGRATOR_TYPES = ['Integrador', 'Comercio'];
const INTEGRATION_TYPE_OPTIONS = [
  { id: 'CR', label: 'CR — Caja Registradora' },
  { id: 'LP', label: 'LP — Link de Pago' },
  { id: 'PG', label: 'PG — Payment Gateway' },
  { id: 'MP', label: 'MP — Android (Mobile POS)' },
  { id: 'TK', label: 'TK — Tokenizador' }
];
const INTEGRATION_MODALITIES = ['Bridge PG', 'MPOS', 'PG Universal', 'PG No universal', 'REST', 'Stand Alone', 'TKN No Universal', 'TKN Universal', 'Web Link de Pago Modalidad No Universal', 'Web Link de Pago Modalidad Universal', 'Wrapper'];
const INTEGRATOR_STATUSES = ['Certificado', 'En proceso', 'Suspendido'];
const CATEGORIAS = [
  'Cliente/Integrador actual de PG',
  'Cliente/Integrador actual de VPOS',
  'Cliente/Integrador actual Tokenizador',
  'Cliente/Integrador nuevo Link de Pago',
  'Cliente/Integrador nuevo Mpos',
  'Cliente/Integrador nuevo PG',
  'Cliente/Integrador nuevo VPOS',
  'Cliente/Integrador MobilePOS'
];
const CERT_STATES = { P: { label: 'P', color: 'bg-amber-100 text-amber-700 border-amber-300' }, C: { label: 'C', color: 'bg-emerald-100 text-emerald-700 border-emerald-300' }, 'N/A': { label: 'N/A', color: 'bg-[#E3F2FD] text-[#0D47A1] border-[#90CAF9]' } };
const CERT_CYCLE = ['P', 'C', 'N/A'];

export const Integrators = () => {
  const { canEdit, canCreate } = usePermission('integradores');
  const [integrators, setIntegrators] = useState([]);
  const [users, setUsers] = useState([]);
  const [implementadores, setImplementadores] = useState([]);
  const [certProducts, setCertProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingIntegrator, setEditingIntegrator] = useState(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deleteIntegratorData, setDeleteIntegratorData] = useState({ id: null, name: null });
  const [expandedRow, setExpandedRow] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterType, setFilterType] = useState('');
  const [filterIntType, setFilterIntType] = useState('');
  const [filterModality, setFilterModality] = useState('');
  const [filterGestor, setFilterGestor] = useState('');
  const [formData, setFormData] = useState({
    name: '', integrator_type: '', integration_type: '', app_name: '',
    integration_modality: '', integrator_status: 'En proceso', gestor: '', categoria: '', certifications: {}, last_contact_date: '', email: '',
    contacts: []
  });
  // Confirmación de asignación de implementador
  const [assignConfirmOpen, setAssignConfirmOpen] = useState(false);
  const [pendingAssign, setPendingAssign] = useState({ integratorId: null, integratorName: '', userId: null, userName: '' });
  const fileInputRef = useRef(null);
  const [importResult, setImportResult] = useState(null);
  const [showImportResult, setShowImportResult] = useState(false);
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [importStep, setImportStep] = useState(1);
  const [importMode, setImportMode] = useState('upsert');
  const [importFile, setImportFile] = useState(null);
  const [importLoading, setImportLoading] = useState(false);
  const dropRef = useRef(null);
  const [certFilters, setCertFilters] = useState({});
  // Bitácora
  const [bitacoraOpen, setBitacoraOpen] = useState(false);
  const [bitacoraIntegrator, setBitacoraIntegrator] = useState(null);
  const [bitacoraEntries, setBitacoraEntries] = useState([]);
  const [bitacoraLoading, setBitacoraLoading] = useState(false);
  const [bitacoraForm, setBitacoraForm] = useState({ description: '', contact_id: '', contact_name: '', date: new Date().toISOString().slice(0, 10), commitment: '', commitment_deadline: '' });
  // Timeline Viewer (replaces evolution)
  const [timelineOpen, setTimelineOpen] = useState(false);
  const [timelineIntegrator, setTimelineIntegrator] = useState(null);
  const [timelineEntries, setTimelineEntries] = useState([]);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [timelineSearch, setTimelineSearch] = useState('');
  const [timelineExpanded, setTimelineExpanded] = useState({});
  // Summary
  const [summaryOpen, setSummaryOpen] = useState(false);
  const [summaryData, setSummaryData] = useState(null);
  const [summaryGroupBy, setSummaryGroupBy] = useState('phase');
  const [summaryLoading, setSummaryLoading] = useState(false);

  // Email notification modal
  const [emailNotifyOpen, setEmailNotifyOpen] = useState(false);
  const [emailNotifyIntegrator, setEmailNotifyIntegrator] = useState(null);
  const [emailCustomMessage, setEmailCustomMessage] = useState('');
  const [emailNewRecipient, setEmailNewRecipient] = useState('');
  const [emailRecipientsList, setEmailRecipientsList] = useState([]);
  const [emailSending, setEmailSending] = useState(false);

  useEffect(() => { fetchData(); }, [filterStatus, filterType]);

  const fetchData = async () => {
    try {
      const params = new URLSearchParams();
      if (filterStatus && filterStatus !== 'all') params.append('integrator_status', filterStatus);
      if (filterType && filterType !== 'all') params.append('integrator_type', filterType);
      const url = params.toString() ? `/integrators?${params}` : '/integrators';

      const [intRes, usersRes, servicesRes, implRes] = await Promise.all([
        api.get(url), api.get('/auth/users'), api.get('/services'), api.get('/auth/implementadores')
      ]);
      setIntegrators(intRes.data);
      setUsers(usersRes.data || []);
      setImplementadores(implRes.data || []);
      const prods = (servicesRes.data || []).filter(s =>
        (s.application_type === 'setup' || s.application_type === 'both') && s.service_type === 'Producto'
      );
      setCertProducts(prods);
    } catch { toast.error('Error al cargar datos'); }
    finally { setLoading(false); }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const isCreate = !editingIntegrator;
    if (isCreate) {
      if (!formData.name || !formData.integrator_type || !formData.app_name) {
        toast.error('Complete los campos obligatorios: Nombre, Tipo Integrador y Aplicativo'); return;
      }
    } else {
      if (!formData.name || !formData.integrator_type || !formData.app_name) {
        toast.error('Complete los campos obligatorios'); return;
      }
    }
    try {
      const payload = { ...formData };
      // Auto-initialize all certifications to N/A on create
      if (!editingIntegrator) {
        const initCerts = {};
        certProducts.forEach(p => { initCerts[p.service_id] = 'N/A'; });
        payload.certifications = initCerts;
      }
      if (editingIntegrator) {
        await api.put(`/integrators/${editingIntegrator.integrator_id}`, payload);
        toast.success('Integrador actualizado');
        setDialogOpen(false); resetForm(); fetchData();
      } else {
        const res = await api.post('/integrators', payload);
        toast.success('Integrador creado');
        setDialogOpen(false); resetForm(); fetchData();
        // Abrir modal de notificación al Gerente de Implementación
        const newIntegrator = res.data;
        setEmailNotifyIntegrator({ ...payload, integrator_id: newIntegrator?.integrator_id || '' });
        setEmailCustomMessage('');
        setEmailNewRecipient('');
        setEmailRecipientsList([]);
        setEmailNotifyOpen(true);
      }
    } catch { toast.error('Error al guardar integrador'); }
  };

  const handleDelete = (id) => {
    const intg = integrators.find(i => i.integrator_id === id);
    setDeleteIntegratorData({ id, name: intg?.name || '' });
    setDeleteConfirmOpen(true);
  };

  const executeDelete = async () => {
    setDeleteConfirmOpen(false);
    if (!deleteIntegratorData.id) return;
    try {
      await api.delete(`/integrators/${deleteIntegratorData.id}`);
      toast.success('Integrador eliminado'); fetchData();
    } catch (error) { toast.error(error.response?.data?.detail || 'Error al eliminar'); }
    finally { setDeleteIntegratorData({ id: null, name: null }); }
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

  const sendNewProjectNotification = async () => {
    if (!emailNotifyIntegrator?.integrator_id) {
      toast.error('No se pudo identificar el integrador');
      setEmailNotifyOpen(false);
      return;
    }
    setEmailSending(true);
    try {
      const headers = {};
      if (emailCustomMessage.trim()) headers['x-custom-message'] = emailCustomMessage.trim();
      if (emailRecipientsList.length > 0) headers['x-additional-recipients'] = emailRecipientsList.join(',');
      const res = await api.post(`/integrators/${emailNotifyIntegrator.integrator_id}/notify-new-project`, {}, { headers });
      toast.success(res.data.message || 'Notificacion enviada');
      setEmailNotifyOpen(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al enviar notificacion');
    } finally {
      setEmailSending(false);
    }
  };

  const openEditDialog = (intg) => {
    setEditingIntegrator(intg);
    setFormData({
      name: intg.name, integrator_type: intg.integrator_type,
      integration_type: intg.integration_type || '', app_name: intg.app_name,
      integration_modality: intg.integration_modality, integrator_status: intg.integrator_status,
      gestor: intg.gestor || '', categoria: intg.categoria || '',
      certifications: intg.certifications || {},
      last_contact_date: intg.last_contact_date || '',
      email: intg.email || '',
      contacts: intg.contacts || []
    });
    setDialogOpen(true);
  };

  const resetForm = () => {
    setFormData({ name: '', integrator_type: '', integration_type: '', app_name: '', integration_modality: '', integrator_status: 'En proceso', gestor: '', categoria: '', certifications: {}, last_contact_date: '', email: '', contacts: [] });
    setEditingIntegrator(null);
  };

  const toggleCert = async (integratorId, serviceId, currentVal) => {
    const idx = CERT_CYCLE.indexOf(currentVal || 'N/A');
    const next = CERT_CYCLE[(idx + 1) % CERT_CYCLE.length];
    const intg = integrators.find(i => i.integrator_id === integratorId);
    if (!intg) return;
    const certs = { ...(intg.certifications || {}), [serviceId]: next };
    try {
      const payload = {
        name: intg.name,
        integrator_type: intg.integrator_type,
        integration_type: intg.integration_type || null,
        app_name: intg.app_name,
        integration_modality: intg.integration_modality,
        integrator_status: intg.integrator_status,
        gestor: intg.gestor || null,
        categoria: intg.categoria || null,
        last_contact_date: intg.last_contact_date || null,
        certifications: certs
      };
      await api.put(`/integrators/${integratorId}`, payload);
      setIntegrators(prev => prev.map(i => i.integrator_id === integratorId ? { ...i, certifications: certs } : i));
    } catch { toast.error('Error al actualizar certificación'); }
  };

  const updateContactDate = async (integratorId, date) => {
    const dateStr = date ? date.toISOString().split('T')[0] : null;
    try {
      await api.patch(`/integrators/${integratorId}/contact-date`, { last_contact_date: dateStr });
      setIntegrators(prev => prev.map(i => i.integrator_id === integratorId ? { ...i, last_contact_date: dateStr } : i));
      toast.success('Fecha actualizada');
    } catch { toast.error('Error al actualizar fecha'); }
  };

  const handleExportExcel = async () => {
    try {
      const res = await api.get('/integrators/export/excel', { responseType: 'blob' });
      const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([res.data]));
      link.download = 'integradores.xlsx'; link.click(); toast.success('Excel exportado');
    } catch { toast.error('Error al exportar'); }
  };

  const handleExportPDF = async () => {
    try {
      const res = await api.get('/integrators/export/pdf', { responseType: 'blob' });
      const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([res.data]));
      link.download = 'integradores.pdf'; link.click(); toast.success('PDF exportado');
    } catch { toast.error('Error al exportar'); }
  };

  const handleDownloadTemplate = async () => {
    try {
      const res = await api.get('/integrators/import/template', { responseType: 'blob' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(new Blob([res.data]));
      link.download = 'plantilla_integradores.xlsx'; link.click();
      toast.success('Plantilla descargada');
    } catch { toast.error('Error al descargar plantilla'); }
  };

  const handleImportFileDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer?.files?.[0] || e.target?.files?.[0];
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['xlsx', 'xls', 'csv'].includes(ext)) {
      toast.error('Solo archivos .xlsx, .xls o .csv'); return;
    }
    setImportFile(file);
    setImportStep(3);
  };

  const handleImportExecute = async () => {
    if (!importFile) return;
    setImportLoading(true);
    const fd = new FormData();
    fd.append('file', importFile);
    fd.append('mode', importMode);
    try {
      const res = await api.post('/integrators/import', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      setImportResult(res.data); setShowImportResult(true);
      if (res.data.status === 'success') toast.success(res.data.message);
      else if (res.data.status === 'partial') toast.warning(res.data.message);
      else toast.error(res.data.message);
      fetchData();
    } catch (err) {
      const errData = err?.response?.data;
      if (errData && errData.errors) {
        // Backend returned an ImportResult with errors
        setImportResult(errData); setShowImportResult(true);
        toast.error(errData.message || 'Error en la importación');
      } else if (errData?.detail) {
        // Pydantic validation or HTTPException
        const detail = typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail);
        setImportResult({
          status: 'error', total_processed: 0, success_count: 0, updated_count: 0,
          cert_updates_count: 0, error_count: 1, skipped_count: 0,
          errors: [{ row: 0, column: 'Sistema', value: null, error_type: 'format',
            message: `Error del servidor: ${detail}`,
            suggested_action: 'Verifique el formato del archivo y que contenga las columnas requeridas. Descargue la plantilla modelo como referencia.' }],
          message: `Error técnico: ${detail}`
        });
        setShowImportResult(true);
        toast.error(`Error: ${detail}`);
      } else {
        const msg = err?.message || 'Error desconocido al importar archivo';
        setImportResult({
          status: 'error', total_processed: 0, success_count: 0, updated_count: 0,
          cert_updates_count: 0, error_count: 1, skipped_count: 0,
          errors: [{ row: 0, column: 'Conexión', value: null, error_type: 'format',
            message: `Error de conexión: ${msg}`,
            suggested_action: 'Verifique su conexión a internet e intente nuevamente. Si el problema persiste, descargue la plantilla y verifique el formato.' }],
          message: `Error de conexión: ${msg}`
        });
        setShowImportResult(true);
        toast.error(msg);
      }
    }
    finally { setImportLoading(false); }
  };

  const closeImportDialog = () => {
    setImportDialogOpen(false);
    setImportStep(1);
    setImportFile(null);
    setImportResult(null);
    setShowImportResult(false);
    setImportMode('upsert');
  };

  const getStatusBadge = (s) => {
    const map = { 'Certificado': 'bg-green-100 text-green-700', 'En proceso': 'bg-amber-100 text-amber-700', 'Suspendido': 'bg-red-100 text-red-700' };
    const icons = { 'Certificado': CheckCircle, 'En proceso': Clock, 'Suspendido': XCircle };
    const Icon = icons[s] || Clock;
    return <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${map[s] || 'bg-slate-100 text-slate-600'}`}><Icon size={12} />{s}</span>;
  };

  const toggleCertFilter = (integratorId, status) => {
    setCertFilters(prev => {
      const current = prev[integratorId] || new Set();
      const next = new Set(current);
      if (next.has(status)) {
        next.delete(status);
      } else {
        next.add(status);
      }
      return { ...prev, [integratorId]: next };
    });
  };

  const clearCertFilter = (integratorId) => {
    setCertFilters(prev => {
      const copy = { ...prev };
      delete copy[integratorId];
      return copy;
    });
  };

  // Contact management helpers
  const addContact = () => {
    setFormData(prev => ({ ...prev, contacts: [...(prev.contacts || []), { contact_id: `ctc_${Date.now().toString(36)}`, name: '', email: '', phone: '' }] }));
  };
  const removeContact = (idx) => {
    setFormData(prev => ({ ...prev, contacts: prev.contacts.filter((_, i) => i !== idx) }));
  };
  const updateContact = (idx, field, value) => {
    setFormData(prev => {
      const contacts = [...prev.contacts];
      contacts[idx] = { ...contacts[idx], [field]: value };
      return { ...prev, contacts };
    });
  };

  // Bitácora functions
  const openBitacora = async (intg) => {
    setBitacoraIntegrator(intg);
    setBitacoraOpen(true);
    setBitacoraLoading(true);
    setBitacoraForm({ description: '', contact_id: '', contact_name: '', date: new Date().toISOString().slice(0, 10), commitment: '', commitment_deadline: '' });
    try {
      const res = await api.get(`/integrators/${intg.integrator_id}/bitacora`);
      setBitacoraEntries(res.data);
    } catch { toast.error('Error al cargar bitácora'); }
    finally { setBitacoraLoading(false); }
  };

  const saveBitacoraEntry = async () => {
    if (!bitacoraForm.description.trim()) { toast.error('Describa la gestión realizada'); return; }
    try {
      await api.post(`/integrators/${bitacoraIntegrator.integrator_id}/bitacora`, bitacoraForm);
      toast.success('Gestión registrada');
      setBitacoraForm({ description: '', contact_id: '', contact_name: '', date: new Date().toISOString().slice(0, 10), commitment: '', commitment_deadline: '' });
      // Clear uncontrolled inputs
      document.querySelectorAll('[data-testid="bitacora-description"], [data-testid="bitacora-contact-input"], [data-testid="bitacora-commitment"]').forEach(el => { el.value = ''; el._init = false; });
      const res = await api.get(`/integrators/${bitacoraIntegrator.integrator_id}/bitacora`);
      setBitacoraEntries(res.data);
      fetchData();
    } catch { toast.error('Error al guardar'); }
  };

  const toggleCommitmentComplete = async (entry) => {
    try {
      await api.patch(`/integrators/${bitacoraIntegrator.integrator_id}/bitacora/${entry.entry_id}`, { commitment_completed: !entry.commitment_completed });
      const res = await api.get(`/integrators/${bitacoraIntegrator.integrator_id}/bitacora`);
      setBitacoraEntries(res.data);
      fetchData();
    } catch { toast.error('Error al actualizar'); }
  };

  const deleteBitacoraEntry = async (entryId) => {
    try {
      await api.delete(`/integrators/${bitacoraIntegrator.integrator_id}/bitacora/${entryId}`);
      setBitacoraEntries(prev => prev.filter(e => e.entry_id !== entryId));
      toast.success('Entrada eliminada');
    } catch { toast.error('Error al eliminar'); }
  };

  // Timeline viewer functions
  const openTimeline = async (intg) => {
    setTimelineIntegrator(intg);
    setTimelineOpen(true);
    setTimelineLoading(true);
    setTimelineSearch('');
    setTimelineExpanded({});
    try {
      const res = await api.get(`/integrators/${intg.integrator_id}/bitacora`);
      setTimelineEntries(res.data);
    } catch { toast.error('Error al cargar historial'); }
    finally { setTimelineLoading(false); }
  };

  const formatTimelineDate = (dateStr) => {
    const today = new Date().toISOString().slice(0, 10);
    if (dateStr === today) {
      const d = new Date(dateStr + 'T12:00:00');
      return `Hoy (${d.toLocaleDateString('es-VE', { day: '2-digit', month: '2-digit', year: 'numeric' })})`;
    }
    const d = new Date(dateStr + 'T12:00:00');
    return d.toLocaleDateString('es-VE', { day: '2-digit', month: '2-digit', year: 'numeric' });
  };

  const toggleTimelineExpand = (entryId) => {
    setTimelineExpanded(prev => ({ ...prev, [entryId]: !prev[entryId] }));
  };

  // Summary functions
  const openSummary = async (groupBy = 'phase') => {
    setSummaryOpen(true);
    setSummaryGroupBy(groupBy);
    setSummaryLoading(true);
    try {
      const res = await api.get(`/integrators/summary?group_by=${groupBy}`);
      setSummaryData(res.data);
    } catch { toast.error('Error al cargar resumen'); }
    finally { setSummaryLoading(false); }
  };

  const changeSummaryGroup = async (groupBy) => {
    setSummaryGroupBy(groupBy);
    setSummaryLoading(true);
    try {
      const res = await api.get(`/integrators/summary?group_by=${groupBy}`);
      setSummaryData(res.data);
    } catch { toast.error('Error al cargar resumen'); }
    finally { setSummaryLoading(false); }
  };

  // Assignment handler for Gestor (inline)
  const handleAssignGestor = async (integratorId, userId) => {
    try {
      const res = await api.put(`/integrators/${integratorId}/assign`, { user_id: userId });
      toast.success(res.data.message || 'Gestor asignado');
      if (res.data.email?.simulated) {
        toast.info('Notificación por email simulada');
      }
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al asignar gestor');
    }
  };

  // Implementador assignment with confirmation step
  const requestAssignImplementador = (integratorId, userId) => {
    const intg = integrators.find(i => i.integrator_id === integratorId);
    const impl = implementadores.find(u => u.user_id === userId);
    setPendingAssign({
      integratorId,
      integratorName: intg?.name || '',
      userId,
      userName: impl?.full_name || impl?.email || ''
    });
    setAssignConfirmOpen(true);
  };

  const executeAssignImplementador = async () => {
    setAssignConfirmOpen(false);
    if (!pendingAssign.integratorId || !pendingAssign.userId) return;
    try {
      const res = await api.put(`/integrators/${pendingAssign.integratorId}/assign-implementador`, { user_id: pendingAssign.userId });
      toast.success(res.data.message || 'Implementador asignado');
      if (res.data.email?.simulated) {
        toast.info('Notificación por email simulada');
      }
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al asignar implementador');
    } finally {
      setPendingAssign({ integratorId: null, integratorName: '', userId: null, userName: '' });
    }
  };

  const filteredIntegrators = integrators.filter(intg => {
    if (filterIntType && filterIntType !== 'all' && intg.integration_type !== filterIntType) return false;
    if (filterModality && filterModality !== 'all' && intg.integration_modality !== filterModality) return false;
    if (filterGestor && filterGestor !== 'all' && intg.gestor !== filterGestor) return false;
    if (!searchTerm) return true;
    const s = searchTerm.toLowerCase();
    return intg.name?.toLowerCase().includes(s) || intg.app_name?.toLowerCase().includes(s) || intg.integration_modality?.toLowerCase().includes(s) || intg.gestor?.toLowerCase().includes(s);
  });

  if (loading) return (
    <div className="flex min-h-screen"><Sidebar /><div className="flex-1 flex items-center justify-center"><div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-blue-600" /></div></div>
  );

  return (
    <div className="flex min-h-screen bg-white">
      <Sidebar />
      <main className="flex-1 p-8" data-testid="integrators-page">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="flex justify-between items-center mb-6">
            <div>
              <h1 className="text-3xl font-bold text-slate-900 font-manrope flex items-center gap-3">
                <Users className="text-brand-blue-600" size={28} />Gestión de Integradores
              </h1>
              <p className="text-slate-500 mt-1">Tablero de asignación de proyectos, certificación y seguimiento de implementadores</p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => openSummary()} data-testid="summary-btn" className="border-purple-200 text-purple-700 hover:bg-purple-50"><Filter size={16} className="mr-1" />Resumen</Button>
              {canEdit && <Button variant="outline" onClick={() => setImportDialogOpen(true)} data-testid="import-integrators-btn"><Upload size={16} className="mr-1" />Importar</Button>}
              <Button variant="outline" onClick={handleExportExcel} data-testid="export-excel-btn"><FileSpreadsheet size={16} className="mr-1" />Excel</Button>
              <Button variant="outline" onClick={handleExportPDF} data-testid="export-pdf-btn"><FileText size={16} className="mr-1" />PDF</Button>
              {canCreate && <Dialog open={dialogOpen} onOpenChange={(o) => { setDialogOpen(o); if (!o) resetForm(); }}>
                <DialogTrigger asChild>
                  <Button className="bg-brand-green-600 hover:bg-brand-green-700" data-testid="create-integrator-btn"><Plus size={16} className="mr-1" />Nuevo Proyecto de Integración</Button>
                </DialogTrigger>
                <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                  <DialogHeader><DialogTitle className="font-manrope text-xl">{editingIntegrator ? 'Editar Proyecto de Integración' : 'Nuevo Proyecto de Integración'}</DialogTitle></DialogHeader>
                  <form onSubmit={handleSubmit} className="space-y-4 mt-2">
                    {/* === FASE 1: Datos Técnicos de Origen (siempre visibles) === */}
                    <div className="space-y-1">
                      {!editingIntegrator && <p className="text-xs font-semibold text-brand-blue-600 uppercase tracking-wider">Datos del Integrador</p>}
                      <div className="grid grid-cols-2 gap-3">
                        <div className="col-span-2">
                          <Label>Nombre del Integrador *</Label>
                          <DebouncedInput value={formData.name} onCommit={(v) => setFormData(prev => ({ ...prev, name: v }))} placeholder="Ej: TechPay Solutions" required data-testid="integrator-name-input" />
                        </div>
                        <div>
                          <Label>Tipo de Integración *</Label>
                          <Select value={formData.integration_type} onValueChange={(v) => setFormData({ ...formData, integration_type: v })}>
                            <SelectTrigger data-testid="integration-type-select"><SelectValue placeholder="Seleccione..." /></SelectTrigger>
                            <SelectContent>{INTEGRATION_TYPE_OPTIONS.map(o => <SelectItem key={o.id} value={o.id}>{o.label}</SelectItem>)}</SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label>Tipo de Integrador *</Label>
                          <Select value={formData.integrator_type} onValueChange={(v) => setFormData({ ...formData, integrator_type: v })}>
                            <SelectTrigger data-testid="integrator-type-select"><SelectValue placeholder="Seleccione..." /></SelectTrigger>
                            <SelectContent>{INTEGRATOR_TYPES.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
                          </Select>
                        </div>
                        <div className="col-span-2">
                          <Label>Nombre del Aplicativo *</Label>
                          <DebouncedInput value={formData.app_name} onCommit={(v) => setFormData(prev => ({ ...prev, app_name: v }))} placeholder="Ej: PaymentHub v3" required data-testid="app-name-input" />
                        </div>
                      </div>
                    </div>

                    {/* === FASE 2: Control Gerencial (solo en edición) === */}
                    {editingIntegrator && (
                      <div className="border-t border-slate-200 pt-3 space-y-1">
                        <p className="text-xs font-semibold text-teal-600 uppercase tracking-wider">Gestión de Implementación</p>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <Label>Modalidad de Integración</Label>
                            <Select value={formData.integration_modality || ''} onValueChange={(v) => setFormData({ ...formData, integration_modality: v })}>
                              <SelectTrigger data-testid="modality-select"><SelectValue placeholder="Seleccione..." /></SelectTrigger>
                              <SelectContent>{INTEGRATION_MODALITIES.map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}</SelectContent>
                            </Select>
                          </div>
                          <div>
                            <Label>Categoría</Label>
                            <Select value={formData.categoria} onValueChange={(v) => setFormData({ ...formData, categoria: v })}>
                              <SelectTrigger data-testid="categoria-select"><SelectValue placeholder="Seleccione..." /></SelectTrigger>
                              <SelectContent>{CATEGORIAS.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
                            </Select>
                          </div>
                          <div>
                            <Label>Gestor Asignado</Label>
                            <Select value={formData.gestor} onValueChange={(v) => setFormData({ ...formData, gestor: v })}>
                              <SelectTrigger data-testid="gestor-select"><SelectValue placeholder="Seleccione..." /></SelectTrigger>
                              <SelectContent>{users.map(u => <SelectItem key={u.user_id} value={u.full_name || u.email}>{u.full_name || u.email}</SelectItem>)}</SelectContent>
                            </Select>
                          </div>
                          <div>
                            <Label>Estatus</Label>
                            <Select value={formData.integrator_status} onValueChange={(v) => setFormData({ ...formData, integrator_status: v })}>
                              <SelectTrigger data-testid="status-select"><SelectValue /></SelectTrigger>
                              <SelectContent>{INTEGRATOR_STATUSES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                            </Select>
                          </div>
                        </div>
                      </div>
                    )}
                    {/* Correo del integrador */}
                    <div>
                      <Label>Correo de Contacto</Label>
                      <Input
                        value={formData.email || ''}
                        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                        placeholder="correo@empresa.com"
                        type="email"
                        data-testid="integrator-email-input"
                      />
                    </div>
                    {/* Contactos Técnicos */}
                    <div className="border-t border-slate-200 pt-3 mt-1">
                      <div className="flex items-center justify-between mb-2">
                        <Label className="text-sm font-semibold text-slate-700">Responsables Técnicos</Label>
                        <Button type="button" variant="outline" size="sm" className="h-7 text-xs" onClick={addContact} data-testid="add-contact-btn">
                          <UserPlus size={13} className="mr-1" /> Agregar responsable
                        </Button>
                      </div>
                      {(formData.contacts || []).length === 0 && (
                        <p className="text-xs text-slate-400 italic mb-2">Sin responsables técnicos asignados</p>
                      )}
                      {(formData.contacts || []).map((c, idx) => (
                        <div key={c.contact_id || idx} className="flex items-center gap-2 mb-2 bg-slate-50 rounded-lg p-2" data-testid={`contact-row-${idx}`}>
                          <DebouncedInput value={c.name} onCommit={(v) => updateContact(idx, 'name', v)} placeholder="Nombre completo" className="h-8 text-xs flex-1" />
                          <div className="relative flex-1">
                            <Mail size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-400" />
                            <DebouncedInput value={c.email} onCommit={(v) => updateContact(idx, 'email', v)} placeholder="correo@empresa.com" className="h-8 text-xs pl-7" type="email" />
                          </div>
                          <div className="relative w-[140px]">
                            <Phone size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-400" />
                            <DebouncedInput value={c.phone} onCommit={(v) => updateContact(idx, 'phone', v)} placeholder="+58 412..." className="h-8 text-xs pl-7" />
                          </div>
                          <Button type="button" variant="ghost" size="sm" className="h-8 w-8 p-0 text-red-400 hover:text-red-600 hover:bg-red-50" onClick={() => removeContact(idx)}>
                            <X size={14} />
                          </Button>
                        </div>
                      ))}
                    </div>
                    <div className="flex justify-end gap-3 pt-2">
                      <Button type="button" variant="outline" onClick={() => { setDialogOpen(false); resetForm(); }}>Cancelar</Button>
                      <Button type="submit" className="bg-brand-green-600 hover:bg-brand-green-700" data-testid="submit-integrator-btn">{editingIntegrator ? 'Actualizar' : 'Crear'}</Button>
                    </div>
                  </form>
                </DialogContent>
              </Dialog>}
            </div>
          </div>

          {/* Filters */}
          <div className="bg-white rounded-lg border border-slate-200 p-3 mb-4">
            <div className="flex flex-wrap gap-2 items-center">
              <div className="flex-1 min-w-[180px] relative">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <DebouncedInput placeholder="Buscar nombre, aplicativo, gestor..." value={searchTerm} onCommit={(v) => setSearchTerm(v)} debounceMs={400} className="pl-9 h-9 text-sm" data-testid="search-input" />
              </div>
              <Select value={filterIntType} onValueChange={setFilterIntType}>
                <SelectTrigger className="w-[110px] h-9 text-xs" data-testid="filter-int-type"><SelectValue placeholder="Tipo Int." /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  {INTEGRATION_TYPE_OPTIONS.map(o => <SelectItem key={o.id} value={o.id}>{o.id}</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={filterStatus} onValueChange={setFilterStatus}>
                <SelectTrigger className="w-[120px] h-9 text-xs" data-testid="filter-status"><SelectValue placeholder="Estatus" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  {INTEGRATOR_STATUSES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={filterType} onValueChange={setFilterType}>
                <SelectTrigger className="w-[115px] h-9 text-xs" data-testid="filter-type"><SelectValue placeholder="Tipo" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  {INTEGRATOR_TYPES.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={filterModality} onValueChange={setFilterModality}>
                <SelectTrigger className="w-[120px] h-9 text-xs" data-testid="filter-modality"><SelectValue placeholder="Modalidad" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todas</SelectItem>
                  {INTEGRATION_MODALITIES.map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={filterGestor} onValueChange={setFilterGestor}>
                <SelectTrigger className="w-[120px] h-9 text-xs" data-testid="filter-gestor"><SelectValue placeholder="Gestor" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  {users.map(u => <SelectItem key={u.user_id} value={u.full_name || u.email}>{u.full_name || u.email}</SelectItem>)}
                </SelectContent>
              </Select>
              {(filterStatus || filterType || filterIntType || filterModality || filterGestor || searchTerm) && (
                <Button variant="ghost" size="sm" className="h-9 text-xs" onClick={() => { setFilterStatus('all'); setFilterType('all'); setFilterIntType('all'); setFilterModality('all'); setFilterGestor('all'); setSearchTerm(''); }} data-testid="clear-filters-btn">Limpiar</Button>
              )}
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-5 gap-3 mb-4">
            <div className="bg-white rounded-lg border p-3"><div className="text-xs text-slate-500">Total</div><div className="text-xl font-bold text-slate-900">{integrators.length}</div></div>
            <div className="bg-white rounded-lg border border-green-200 p-3"><div className="text-xs text-green-600">Certificados</div><div className="text-xl font-bold text-green-700">{integrators.filter(i => i.integrator_status === 'Certificado').length}</div></div>
            <div className="bg-white rounded-lg border border-blue-200 p-3"><div className="text-xs text-blue-600">En Ejecución</div><div className="text-xl font-bold text-blue-700">{integrators.filter(i => i.implementador && i.integrator_status === 'En proceso').length}</div></div>
            <div className="bg-white rounded-lg border border-amber-200 p-3"><div className="text-xs text-amber-600">Sin Implementador</div><div className="text-xl font-bold text-amber-700">{integrators.filter(i => !i.implementador).length}</div></div>
            <div className="bg-white rounded-lg border border-red-200 p-3"><div className="text-xs text-red-600">Suspendidos</div><div className="text-xl font-bold text-red-700">{integrators.filter(i => i.integrator_status === 'Suspendido').length}</div></div>
          </div>

          {/* Table */}
          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden" data-testid="integrators-table">
            <div className="overflow-x-auto">
              <table className="w-full" style={{ tableLayout: 'fixed', minWidth: '1150px' }}>
                <colgroup>
                  <col style={{ width: '17%' }} />
                  <col style={{ width: '5%' }} />
                  <col style={{ width: '6%' }} />
                  <col style={{ width: '12%' }} />
                  <col style={{ width: '9%' }} />
                  <col style={{ width: '10%' }} />
                  <col style={{ width: '10%' }} />
                  <col style={{ width: '9%' }} />
                  <col style={{ width: '9%' }} />
                  <col style={{ width: '13%' }} />
                </colgroup>
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-600 uppercase">Nombre</th>
                    <th className="px-2 py-2.5 text-center text-xs font-semibold text-slate-600 uppercase">T.Int</th>
                    <th className="px-2 py-2.5 text-center text-xs font-semibold text-slate-600 uppercase">Tipo</th>
                    <th className="px-2 py-2.5 text-left text-xs font-semibold text-slate-600 uppercase">Aplicativo</th>
                    <th className="px-2 py-2.5 text-center text-xs font-semibold text-slate-600 uppercase">Modalidad</th>
                    <th className="px-2 py-2.5 text-left text-xs font-semibold text-slate-600 uppercase">Gestor</th>
                    <th className="px-2 py-2.5 text-left text-xs font-semibold text-slate-600 uppercase">Implementador</th>
                    <th className="px-2 py-2.5 text-center text-xs font-semibold text-slate-600 uppercase">Categoría</th>
                    <th className="px-2 py-2.5 text-center text-xs font-semibold text-slate-600 uppercase">Últ. Contacto</th>
                    <th className="px-2 py-2.5 text-center text-xs font-semibold text-slate-600 uppercase">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredIntegrators.length === 0 ? (
                    <tr><td colSpan={10} className="px-4 py-8 text-center text-slate-500">No se encontraron integradores</td></tr>
                  ) : filteredIntegrators.map((intg) => (
                    <Fragment key={intg.integrator_id}>
                      <tr className={`transition-colors ${
                        !intg.implementador
                          ? 'bg-amber-50/60 hover:bg-amber-100/60'
                          : intg.integrator_status === 'En proceso'
                            ? 'bg-blue-50/40 hover:bg-blue-100/40'
                            : 'hover:bg-slate-50'
                      }`} data-testid={`integrator-row-${intg.integrator_id}`}>
                        <td className="px-3 py-2">
                          <p className="font-medium text-slate-900 text-sm truncate" title={intg.name}>{intg.name}</p>
                        </td>
                        <td className="px-2 py-2 text-center">
                          {intg.integration_type ? <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-indigo-100 text-indigo-700">{intg.integration_type}</span> : <span className="text-slate-300">—</span>}
                        </td>
                        <td className="px-2 py-2 text-center">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${intg.integrator_type === 'Integrador' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'}`}>{intg.integrator_type === 'Integrador' ? 'Int.' : 'Com.'}</span>
                        </td>
                        <td className="px-2 py-2">
                          <p className="text-xs text-slate-700 truncate" title={intg.app_name}>{intg.app_name}</p>
                        </td>
                        <td className="px-2 py-2 text-center">
                          <span className="text-[10px] text-slate-600 truncate block" title={intg.integration_modality}>{intg.integration_modality}</span>
                        </td>
                        <td className="px-2 py-2">
                          {intg.gestor ? (
                            <p className="text-[10px] text-slate-600 truncate" title={intg.gestor}>{intg.gestor}</p>
                          ) : (
                            <Select onValueChange={(userId) => handleAssignGestor(intg.integrator_id, userId)}>
                              <SelectTrigger className="h-7 text-[10px] border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100 w-full" data-testid={`assign-gestor-${intg.integrator_id}`}>
                                <SelectValue placeholder="Asignar..." />
                              </SelectTrigger>
                              <SelectContent>
                                {users.map(u => (
                                  <SelectItem key={u.user_id} value={u.user_id} className="text-xs">
                                    {u.full_name || u.email}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          )}
                        </td>
                        <td className="px-2 py-2">
                          {intg.implementador ? (
                            <p className="text-[10px] text-teal-700 font-medium truncate" title={intg.implementador}>{intg.implementador}</p>
                          ) : implementadores.length > 0 ? (
                            <Select onValueChange={(userId) => requestAssignImplementador(intg.integrator_id, userId)}>
                              <SelectTrigger className="h-7 text-[10px] border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100 w-full" data-testid={`assign-impl-${intg.integrator_id}`}>
                                <SelectValue placeholder="Asignar..." />
                              </SelectTrigger>
                              <SelectContent>
                                {implementadores.map(u => (
                                  <SelectItem key={u.user_id} value={u.user_id} className="text-xs">
                                    {u.full_name || u.email}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          ) : (
                            <span className="text-[10px] text-slate-400 italic">Sin implementadores</span>
                          )}
                        </td>
                        <td className="px-2 py-2 text-center">
                          <span className="text-[10px] text-slate-500 truncate block" title={intg.categoria || ''}>{intg.categoria ? intg.categoria.replace('Cliente/Integrador ', '') : '—'}</span>
                        </td>
                        <td className="px-2 py-2 text-center">
                          <Popover>
                            <PopoverTrigger asChild>
                              <button className="inline-flex items-center gap-1 text-[10px] text-slate-600 hover:text-brand-blue-600 cursor-pointer hover:bg-slate-100 px-1.5 py-0.5 rounded transition-colors" data-testid={`date-${intg.integrator_id}`}>
                                <CalendarDays size={11} />
                                {intg.last_contact_date ? new Date(intg.last_contact_date + 'T12:00:00').toLocaleDateString('es-VE', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '—'}
                              </button>
                            </PopoverTrigger>
                            <PopoverContent className="w-auto p-0" align="center">
                              <Calendar
                                mode="single"
                                selected={intg.last_contact_date ? new Date(intg.last_contact_date + 'T12:00:00') : undefined}
                                onSelect={(date) => updateContactDate(intg.integrator_id, date)}
                                disabled={(date) => date > new Date()}
                                initialFocus
                              />
                            </PopoverContent>
                          </Popover>
                        </td>
                        <td className="px-2 py-2" style={{ minWidth: '160px' }}>
                          <div className="flex items-center justify-center gap-1">
                            <Button size="sm" variant="ghost" onClick={() => setExpandedRow(expandedRow === intg.integrator_id ? null : intg.integrator_id)}
                              className="text-purple-600 hover:bg-purple-50 h-7 px-1.5" data-testid={`detail-${intg.integrator_id}`}>
                              <Award size={13} />{expandedRow === intg.integrator_id ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => openTimeline(intg)}
                              className="text-purple-500 hover:bg-purple-50 h-7 w-7 p-0"
                              data-testid={`timeline-${intg.integrator_id}`} title="Reporte Histórico">
                              <FileText size={13} />
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => openBitacora(intg)}
                              className={`h-7 w-7 p-0 ${intg.has_overdue_commitments ? 'text-amber-500 hover:bg-amber-50 animate-pulse' : 'text-slate-500 hover:bg-slate-100'}`}
                              data-testid={`bitacora-${intg.integrator_id}`} title="Bitácora de gestión">
                              <BookOpen size={13} />
                            </Button>
                            {canEdit && <Button size="sm" variant="ghost" onClick={() => openEditDialog(intg)} className="text-brand-blue-600 hover:bg-blue-50 h-7 w-7 p-0" data-testid={`edit-${intg.integrator_id}`}><Pencil size={13} /></Button>}
                            {canEdit && <Button size="sm" variant="ghost" onClick={() => handleDelete(intg.integrator_id)} className="text-red-500 hover:bg-red-50 h-7 w-7 p-0" data-testid={`delete-${intg.integrator_id}`}><Trash2 size={13} /></Button>}
                          </div>
                        </td>
                      </tr>
                      {/* Expanded certification matrix */}
                      {expandedRow === intg.integrator_id && (() => {
                        const certs = intg.certifications || {};
                        const counts = { C: 0, P: 0, 'N/A': 0 };
                        certProducts.forEach(p => { counts[certs[p.service_id] || 'N/A']++; });
                        const af = certFilters[intg.integrator_id];
                        const hasFilter = af && af.size > 0;
                        const visible = hasFilter ? certProducts.filter(p => af.has(certs[p.service_id] || 'N/A')) : certProducts;
                        const pills = [
                          { key: 'C', label: 'Certificados', count: counts.C, idle: 'bg-emerald-100 text-emerald-700 border-emerald-300', on: 'bg-emerald-500 text-white border-emerald-600 shadow-[0_0_8px_rgba(16,185,129,0.5)]' },
                          { key: 'P', label: 'Pendientes', count: counts.P, idle: 'bg-amber-100 text-amber-700 border-amber-300', on: 'bg-amber-500 text-white border-amber-600 shadow-[0_0_8px_rgba(245,158,11,0.5)]' },
                          { key: 'N/A', label: 'No Aplica', count: counts['N/A'], idle: 'bg-[#E3F2FD] text-[#0D47A1] border-[#90CAF9]', on: 'bg-[#1565C0] text-white border-[#0D47A1] shadow-[0_0_8px_rgba(21,101,192,0.5)]' },
                        ];
                        return (
                        <tr>
                          <td colSpan={11} className="p-0">
                            <div className="bg-slate-50 border-t border-slate-200 p-4" data-testid={`cert-matrix-${intg.integrator_id}`}>
                              <h4 className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-3 flex items-center gap-1.5">
                                <Award size={14} className="text-purple-600" />Matriz de Servicios y Productos — {intg.name}
                              </h4>
                              {certProducts.length > 0 ? (
                                <>
                                  <div className="flex items-center flex-wrap gap-2 mb-3" data-testid={`cert-filter-${intg.integrator_id}`}>
                                    {pills.map(f => {
                                      const active = hasFilter && af.has(f.key);
                                      return (
                                        <button key={f.key} onClick={() => toggleCertFilter(intg.integrator_id, f.key)}
                                          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-semibold transition-all cursor-pointer hover:scale-105 ${active ? f.on : f.idle}`}
                                          data-testid={`cert-filter-${intg.integrator_id}-${f.key}`}>
                                          {f.key} <span className="font-normal">{f.label}</span>
                                          <span className={`ml-0.5 px-1.5 rounded-full text-[10px] font-bold ${active ? 'bg-white/30' : 'bg-black/10'}`}>{f.count}</span>
                                        </button>
                                      );
                                    })}
                                    {hasFilter && (
                                      <button onClick={() => clearCertFilter(intg.integrator_id)}
                                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full border border-slate-300 text-[11px] font-medium text-slate-600 bg-white hover:bg-slate-100 transition-all cursor-pointer"
                                        data-testid={`cert-filter-${intg.integrator_id}-clear`}>
                                        Ver Todos
                                      </button>
                                    )}
                                    {hasFilter && <span className="text-[10px] text-slate-400 ml-1">Mostrando {visible.length} de {certProducts.length}</span>}
                                  </div>
                                  <div className="overflow-x-auto">
                                    <div className="flex items-start gap-0" style={{ minWidth: visible.length * 90 + 160 }}>
                                      <div className="sticky left-0 z-10 bg-slate-50 pr-2 min-w-[160px]">
                                        <div className="h-16 flex items-end pb-1"><span className="text-xs font-semibold text-slate-700">Producto</span></div>
                                        <div className="h-10 flex items-center"><span className="text-xs font-medium text-slate-500">Estado</span></div>
                                      </div>
                                      {visible.map((prod) => {
                                        const val = certs[prod.service_id] || 'N/A';
                                        const cfg = CERT_STATES[val] || CERT_STATES['N/A'];
                                        return (
                                          <div key={prod.service_id} className="min-w-[85px] text-center px-1">
                                            <div className="h-16 flex items-end pb-1 justify-center">
                                              <span className="text-[10px] text-slate-600 leading-tight line-clamp-3" title={prod.name}>{prod.name}</span>
                                            </div>
                                            <div className="h-10 flex items-center justify-center">
                                              <button onClick={() => toggleCert(intg.integrator_id, prod.service_id, val)}
                                                className={`px-3 py-1 rounded border text-xs font-bold transition-colors cursor-pointer ${cfg.color}`}
                                                data-testid={`cert-${intg.integrator_id}-${prod.service_id}`}
                                                title="Click para cambiar: P / C / N/A">{cfg.label}</button>
                                            </div>
                                          </div>
                                        );
                                      })}
                                    </div>
                                  </div>
                                </>
                              ) : (
                                <p className="text-xs text-slate-400 italic">No hay productos tipo "Producto" con aplicación "Setup" o "Both" en el catálogo</p>
                              )}
                            </div>
                          </td>
                        </tr>
                        );
                      })()}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Eliminar Integrador</AlertDialogTitle>
              <AlertDialogDescription>
                Eliminar <strong>"{deleteIntegratorData.name}"</strong>?<br />
                <span className="text-red-600 font-medium">Esta acción es irreversible.</span>
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancelar</AlertDialogCancel>
              <AlertDialogAction onClick={executeDelete} className="bg-red-600 hover:bg-red-700 text-white">Eliminar</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Confirmación de asignación de Implementador */}
        <AlertDialog open={assignConfirmOpen} onOpenChange={setAssignConfirmOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Confirmar Asignación de Implementador</AlertDialogTitle>
              <AlertDialogDescription>
                ¿Está seguro que desea asignar a <strong className="text-slate-900">{pendingAssign.userName}</strong> como implementador del proyecto <strong className="text-slate-900">{pendingAssign.integratorName}</strong>?
                <br /><br />
                <span className="text-xs text-slate-500">Se enviará una notificación por correo electrónico al implementador con los datos del proyecto y los contactos técnicos del integrador.</span>
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel onClick={() => setPendingAssign({ integratorId: null, integratorName: '', userId: null, userName: '' })}>Cancelar</AlertDialogCancel>
              <AlertDialogAction onClick={executeAssignImplementador} className="bg-teal-600 hover:bg-teal-700 text-white" data-testid="confirm-assign-impl-btn">Confirmar Asignación</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Import Wizard Dialog */}
        <Dialog open={importDialogOpen} onOpenChange={(o) => { if (!o) closeImportDialog(); else setImportDialogOpen(true); }}>
          <DialogContent className="max-w-xl" data-testid="import-wizard-dialog">
            <DialogHeader>
              <DialogTitle className="font-manrope text-xl flex items-center gap-2">
                <Upload size={20} className="text-brand-blue-600" />Asistente de Importación
              </DialogTitle>
            </DialogHeader>

            {/* Step Indicator */}
            {!showImportResult && (
              <div className="flex items-center gap-2 mb-4">
                {[1, 2, 3].map(s => (
                  <div key={s} className="flex items-center gap-2">
                    <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${importStep >= s ? 'bg-brand-blue-600 text-white' : 'bg-slate-200 text-slate-500'}`}>{s}</div>
                    <span className={`text-xs font-medium ${importStep >= s ? 'text-slate-700' : 'text-slate-400'}`}>
                      {s === 1 ? 'Plantilla' : s === 2 ? 'Archivo' : 'Procesar'}
                    </span>
                    {s < 3 && <div className={`w-8 h-0.5 ${importStep > s ? 'bg-brand-blue-600' : 'bg-slate-200'}`} />}
                  </div>
                ))}
              </div>
            )}

            {/* Step 1: Download Template */}
            {!showImportResult && importStep === 1 && (
              <div className="space-y-4" data-testid="import-step-1">
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-blue-800 mb-2 flex items-center gap-1.5">
                    <FileDown size={16} />Descargar Plantilla Modelo
                  </h3>
                  <p className="text-xs text-blue-700 mb-3">
                    Descargue la plantilla Excel con las columnas correctas, ejemplos de datos y valores válidos.
                    Esto evita errores de formato y acelera la carga masiva.
                  </p>
                  <Button onClick={handleDownloadTemplate} variant="outline" className="border-blue-300 text-blue-700 hover:bg-blue-100" data-testid="download-template-btn">
                    <Download size={14} className="mr-1.5" />Descargar Plantilla (.xlsx)
                  </Button>
                </div>
                <div className="flex justify-end">
                  <Button onClick={() => setImportStep(2)} data-testid="import-next-step-2">
                    Siguiente <ChevronDown size={14} className="ml-1 rotate-[-90deg]" />
                  </Button>
                </div>
              </div>
            )}

            {/* Step 2: File Upload (Drag & Drop) */}
            {!showImportResult && importStep === 2 && (
              <div className="space-y-4" data-testid="import-step-2">
                <div
                  ref={dropRef}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={handleImportFileDrop}
                  className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer ${importFile ? 'border-green-400 bg-green-50' : 'border-slate-300 hover:border-brand-blue-400 hover:bg-slate-50'}`}
                  onClick={() => fileInputRef.current?.click()}
                  data-testid="import-drop-zone"
                >
                  <input type="file" ref={fileInputRef} onChange={handleImportFileDrop} accept=".xlsx,.xls,.csv" className="hidden" />
                  {importFile ? (
                    <div className="space-y-2">
                      <CheckCircle size={32} className="mx-auto text-green-600" />
                      <p className="text-sm font-medium text-green-700">{importFile.name}</p>
                      <p className="text-xs text-green-600">{(importFile.size / 1024).toFixed(1)} KB</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <Upload size={32} className="mx-auto text-slate-400" />
                      <p className="text-sm font-medium text-slate-600">Arrastre y suelte su archivo aquí</p>
                      <p className="text-xs text-slate-400">o haga clic para buscar — .xlsx, .xls, .csv</p>
                    </div>
                  )}
                </div>
                <div className="flex justify-between">
                  <Button variant="ghost" onClick={() => setImportStep(1)}>Atrás</Button>
                  <Button onClick={() => setImportStep(3)} disabled={!importFile} data-testid="import-next-step-3">
                    Siguiente <ChevronDown size={14} className="ml-1 rotate-[-90deg]" />
                  </Button>
                </div>
              </div>
            )}

            {/* Step 3: Processing Options */}
            {!showImportResult && importStep === 3 && (
              <div className="space-y-4" data-testid="import-step-3">
                <div>
                  <Label className="text-sm font-semibold mb-2 block">Modo de Procesamiento</Label>
                  <div className="space-y-2">
                    <label className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${importMode === 'upsert' ? 'border-brand-blue-400 bg-blue-50' : 'border-slate-200 hover:border-slate-300'}`} data-testid="import-mode-upsert">
                      <input type="radio" name="importMode" value="upsert" checked={importMode === 'upsert'} onChange={() => setImportMode('upsert')} className="mt-0.5" />
                      <div>
                        <p className="text-sm font-medium text-slate-800 flex items-center gap-1.5">
                          <RefreshCw size={13} className="text-blue-600" />Actualizar existentes y cargar nuevos
                          <span className="text-[10px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded font-semibold">RECOMENDADO</span>
                        </p>
                        <p className="text-xs text-slate-500 mt-0.5">Si un integrador ya existe (mismo nombre + tipo), se actualizan sus datos preservando la Matriz de Certificación.</p>
                      </div>
                    </label>
                    <label className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${importMode === 'insert_only' ? 'border-brand-blue-400 bg-blue-50' : 'border-slate-200 hover:border-slate-300'}`} data-testid="import-mode-insert-only">
                      <input type="radio" name="importMode" value="insert_only" checked={importMode === 'insert_only'} onChange={() => setImportMode('insert_only')} className="mt-0.5" />
                      <div>
                        <p className="text-sm font-medium text-slate-800 flex items-center gap-1.5">
                          <AlertCircle size={13} className="text-amber-600" />Solo insertar nuevos
                        </p>
                        <p className="text-xs text-slate-500 mt-0.5">Omite los registros que ya existen. No modifica datos existentes.</p>
                      </div>
                    </label>
                  </div>
                </div>
                {importFile && (
                  <div className="bg-slate-50 rounded-lg p-3 flex items-center gap-3 border border-slate-200">
                    <FileSpreadsheet size={20} className="text-green-600 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-700 truncate">{importFile.name}</p>
                      <p className="text-xs text-slate-500">{(importFile.size / 1024).toFixed(1)} KB</p>
                    </div>
                  </div>
                )}
                <div className="flex justify-between">
                  <Button variant="ghost" onClick={() => setImportStep(2)}>Atrás</Button>
                  <Button onClick={handleImportExecute} disabled={importLoading} className="bg-brand-green-600 hover:bg-brand-green-700" data-testid="import-execute-btn">
                    {importLoading ? <><div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />Procesando...</> : <>Procesar Importación</>}
                  </Button>
                </div>
              </div>
            )}

            {/* Import Results */}
            {showImportResult && importResult && (
              <div data-testid="import-results-panel">
                <ImportResultPanel result={importResult} onClose={closeImportDialog} />
                <div className="flex justify-end mt-4">
                  <Button variant="outline" onClick={closeImportDialog}>Cerrar</Button>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </main>

      {/* Bitácora Modal */}
      <Dialog open={bitacoraOpen} onOpenChange={(o) => { if (!o) setBitacoraOpen(false); }}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="bitacora-modal">
          <DialogHeader>
            <DialogTitle className="font-manrope text-xl flex items-center gap-2">
              <BookOpen size={20} className="text-slate-600" />
              Bitácora — {bitacoraIntegrator?.name}
            </DialogTitle>
          </DialogHeader>

          {/* New Entry Form — solo si canCreate (edit o override integradores:create) */}
          {canCreate && <div className="bg-slate-50 rounded-lg border border-slate-200 p-3 space-y-2">
            <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Nueva Gestión</p>
            <textarea
              ref={el => { if (el && !el._init) { el._init = true; el.value = bitacoraForm.description; } }}
              onChange={(e) => {
                const val = e.target.value;
                if (window._bitDescTimer) clearTimeout(window._bitDescTimer);
                window._bitDescTimer = setTimeout(() => setBitacoraForm(p => ({ ...p, description: val })), 300);
              }}
              placeholder="Describa la gestión realizada (llamada, reunión, correo de seguimiento...)"
              className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 min-h-[60px]"
              data-testid="bitacora-description"
            />
            <div className="grid grid-cols-3 gap-2">
              <div>
                <Label className="text-[10px] text-slate-500">Persona contactada</Label>
                <div className="relative">
                  <input
                    ref={el => { if (el && !el._init) { el._init = true; el.value = bitacoraForm.contact_name; } }}
                    onChange={(e) => {
                      const val = e.target.value;
                      if (window._bitContactTimer) clearTimeout(window._bitContactTimer);
                      window._bitContactTimer = setTimeout(() => setBitacoraForm(p => ({ ...p, contact_name: val, contact_id: '' })), 300);
                    }}
                    list={`bitacora-contacts-${bitacoraIntegrator?.integrator_id}`}
                    placeholder="Escriba o seleccione..."
                    className="flex h-8 w-full rounded-md border border-input bg-background px-3 py-2 text-xs ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                    data-testid="bitacora-contact-input"
                  />
                  <datalist id={`bitacora-contacts-${bitacoraIntegrator?.integrator_id}`}>
                    {(bitacoraIntegrator?.contacts || []).map(c => (
                      <option key={c.contact_id} value={c.name} />
                    ))}
                  </datalist>
                </div>
              </div>
              <div>
                <Label className="text-[10px] text-slate-500">Fecha de gestión</Label>
                <Input type="date" value={bitacoraForm.date} onChange={(e) => setBitacoraForm(p => ({ ...p, date: e.target.value }))} className="h-8 text-xs" />
              </div>
              <div>
                <Label className="text-[10px] text-slate-500">Fecha límite compromiso</Label>
                <Input type="date" value={bitacoraForm.commitment_deadline} onChange={(e) => setBitacoraForm(p => ({ ...p, commitment_deadline: e.target.value }))} className="h-8 text-xs" />
              </div>
            </div>
            <div>
              <Label className="text-[10px] text-slate-500">Compromiso establecido</Label>
              <input
                ref={el => { if (el && !el._init) { el._init = true; el.value = bitacoraForm.commitment; } }}
                onChange={(e) => {
                  const val = e.target.value;
                  if (window._bitCommitTimer) clearTimeout(window._bitCommitTimer);
                  window._bitCommitTimer = setTimeout(() => setBitacoraForm(p => ({ ...p, commitment: val })), 300);
                }}
                placeholder="Ej: Enviar credenciales de prueba"
                className="flex h-8 w-full rounded-md border border-input bg-background px-3 py-2 text-xs ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                data-testid="bitacora-commitment"
              />
            </div>
            <div className="flex justify-end">
              <Button size="sm" className="h-8 text-xs bg-brand-green-600 hover:bg-brand-green-700" onClick={saveBitacoraEntry} data-testid="bitacora-save-btn">
                <Plus size={13} className="mr-1" /> Registrar Gestión
              </Button>
            </div>
          </div>}

          {/* Entries Timeline */}
          <div className="mt-2">
            <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">Historial ({bitacoraEntries.length})</p>
            {bitacoraLoading ? (
              <p className="text-sm text-slate-400 text-center py-4">Cargando...</p>
            ) : bitacoraEntries.length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-4 italic">Sin gestiones registradas</p>
            ) : (
              <div className="space-y-2 max-h-[350px] overflow-y-auto">
                {bitacoraEntries.map(entry => {
                  const isOverdue = entry.commitment_deadline && !entry.commitment_completed && entry.commitment_deadline < new Date().toISOString().slice(0, 10);
                  return (
                    <div key={entry.entry_id} className={`border rounded-lg p-3 transition-all ${isOverdue ? 'border-amber-300 bg-amber-50' : entry.commitment_completed ? 'border-green-200 bg-green-50/50' : 'border-slate-200 bg-white'}`} data-testid={`bitacora-entry-${entry.entry_id}`}>
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-slate-800">{entry.description}</p>
                          <div className="flex flex-wrap items-center gap-2 mt-1.5 text-[10px] text-slate-500">
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-slate-100 rounded"><CalendarDays size={10} />{entry.date}</span>
                            {entry.contact_name && <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded"><Users size={10} />{entry.contact_name}</span>}
                          </div>
                          {entry.commitment && (
                            <div className={`mt-2 flex items-start gap-2 p-2 rounded text-xs ${isOverdue ? 'bg-amber-100/70' : entry.commitment_completed ? 'bg-green-100/70' : 'bg-slate-50'}`}>
                              <button onClick={() => toggleCommitmentComplete(entry)} className="mt-0.5 flex-shrink-0" disabled={!canEdit} data-testid={`toggle-commitment-${entry.entry_id}`}>
                                {entry.commitment_completed
                                  ? <CheckCircle size={14} className="text-green-600" />
                                  : <Clock size={14} className={isOverdue ? 'text-amber-600' : 'text-slate-400'} />}
                              </button>
                              <div className="min-w-0">
                                <p className={`font-medium ${entry.commitment_completed ? 'line-through text-slate-400' : 'text-slate-700'}`}>{entry.commitment}</p>
                                {entry.commitment_deadline && (
                                  <p className={`text-[10px] mt-0.5 ${isOverdue ? 'text-amber-700 font-semibold' : 'text-slate-400'}`}>
                                    {isOverdue ? 'Vencido: ' : 'Fecha límite: '}{entry.commitment_deadline}
                                  </p>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                        {canEdit && <Button size="sm" variant="ghost" className="h-6 w-6 p-0 text-slate-300 hover:text-red-500" onClick={() => deleteBitacoraEntry(entry.entry_id)}>
                          <Trash2 size={12} />
                        </Button>}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Timeline Viewer Modal (Reporte Histórico) */}
      <Dialog open={timelineOpen} onOpenChange={(o) => { if (!o) setTimelineOpen(false); }}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-hidden flex flex-col" data-testid="timeline-modal">
          <DialogHeader className="shrink-0">
            <DialogTitle className="font-manrope text-xl flex items-center gap-2">
              <FileText size={20} className="text-purple-600" />
              Reporte Histórico — {timelineIntegrator?.name}
            </DialogTitle>
          </DialogHeader>

          {/* Search */}
          <div className="shrink-0 relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <Input
              value={timelineSearch}
              onChange={(e) => setTimelineSearch(e.target.value)}
              placeholder="Buscar en gestiones (ej: contrato, credenciales...)"
              className="pl-9 h-9 text-sm"
              data-testid="timeline-search"
            />
          </div>

          {/* Timeline Content */}
          <div className="flex-1 overflow-y-auto mt-2 min-h-0">
            {timelineLoading ? (
              <p className="text-sm text-slate-400 text-center py-8">Cargando historial...</p>
            ) : (() => {
              const filtered = timelineEntries.filter(e => {
                if (!timelineSearch) return true;
                const s = timelineSearch.toLowerCase();
                return (e.description || '').toLowerCase().includes(s) ||
                  (e.contact_name || '').toLowerCase().includes(s) ||
                  (e.commitment || '').toLowerCase().includes(s);
              });
              if (filtered.length === 0) {
                return (
                  <div className="text-center py-8">
                    <BookOpen size={28} className="mx-auto text-slate-300 mb-2" />
                    <p className="text-sm text-slate-400 italic">
                      {timelineSearch ? `Sin resultados para "${timelineSearch}"` : 'Sin gestiones registradas para este integrador'}
                    </p>
                  </div>
                );
              }
              return (
                <div className="space-y-0">
                  {/* Header row */}
                  <div className="grid grid-cols-[140px_1fr] gap-4 pb-2 mb-2 border-b border-slate-200">
                    <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Hito Temporal</span>
                    <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Detalle de la Gestión</span>
                  </div>
                  {filtered.map((entry) => {
                    const isOverdue = entry.commitment_deadline && !entry.commitment_completed && entry.commitment_deadline < new Date().toISOString().slice(0, 10);
                    const isCompleted = entry.commitment_completed;
                    const isExpanded = timelineExpanded[entry.entry_id];
                    const descriptionLong = (entry.description || '').length > 120;
                    const borderColor = isOverdue ? 'border-l-red-500' : isCompleted ? 'border-l-emerald-500' : 'border-l-slate-200';

                    return (
                      <div
                        key={entry.entry_id}
                        data-testid={`timeline-entry-${entry.entry_id}`}
                        className={`grid grid-cols-[140px_1fr] gap-4 border-l-[3px] ${borderColor} bg-white hover:bg-slate-50/50 transition-colors cursor-pointer py-4 px-2`}
                        onClick={() => descriptionLong && toggleTimelineExpand(entry.entry_id)}
                      >
                        {/* Date column */}
                        <div className="text-right pr-2">
                          <p className="text-sm font-semibold text-slate-800 leading-snug">{formatTimelineDate(entry.date)}</p>
                        </div>

                        {/* Detail column */}
                        <div className="space-y-2">
                          {entry.contact_name && (
                            <p className="text-sm">
                              <span className="font-bold text-slate-700">Interlocutor: </span>
                              <span className="text-slate-600">{entry.contact_name}</span>
                            </p>
                          )}
                          <div className="text-sm">
                            <span className="font-bold text-slate-700">Acción: </span>
                            <span className="text-slate-600">
                              {!isExpanded && descriptionLong
                                ? entry.description.slice(0, 120) + '...'
                                : entry.description}
                            </span>
                            {descriptionLong && (
                              <button
                                onClick={(e) => { e.stopPropagation(); toggleTimelineExpand(entry.entry_id); }}
                                className="ml-1 text-[10px] text-purple-600 hover:text-purple-800 font-medium"
                                data-testid={`timeline-expand-${entry.entry_id}`}
                              >
                                {isExpanded ? 'ver menos' : 'ver más'}
                              </button>
                            )}
                          </div>
                          {entry.commitment && (
                            <p className="text-sm">
                              <span className={`font-bold ${isOverdue ? 'text-red-600' : isCompleted ? 'text-emerald-600' : 'text-slate-700'}`}>Compromiso: </span>
                              <span className={`${isCompleted ? 'line-through text-slate-400' : isOverdue ? 'text-red-700' : 'text-slate-600'}`}>
                                {entry.commitment}
                                {entry.commitment_deadline && (
                                  <span className={`ml-1 ${isOverdue ? 'font-semibold' : ''}`}>
                                    (Límite: {formatTimelineDate(entry.commitment_deadline)})
                                  </span>
                                )}
                              </span>
                              {isOverdue && <span className="ml-1.5 text-[9px] font-bold text-red-500 uppercase">Vencido</span>}
                              {isCompleted && <span className="ml-1.5 text-[9px] font-bold text-emerald-500 uppercase">Cumplido</span>}
                            </p>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              );
            })()}
          </div>

          {/* Footer */}
          <div className="shrink-0 flex items-center justify-between pt-2 border-t border-slate-200 mt-2">
            <span className="text-[10px] text-slate-400">{timelineEntries.length} gestiones registradas</span>
            {timelineSearch && <span className="text-[10px] text-purple-500">{timelineEntries.filter(e => { const s = timelineSearch.toLowerCase(); return (e.description || '').toLowerCase().includes(s) || (e.contact_name || '').toLowerCase().includes(s) || (e.commitment || '').toLowerCase().includes(s); }).length} coincidencias</span>}
          </div>
        </DialogContent>
      </Dialog>

      {/* Summary Modal */}
      <Dialog open={summaryOpen} onOpenChange={(o) => { if (!o) setSummaryOpen(false); }}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto" data-testid="summary-modal">
          <DialogHeader>
            <DialogTitle className="font-manrope text-xl">Resumen de Integraciones</DialogTitle>
          </DialogHeader>
          <div className="flex items-center gap-2 mb-4">
            <span className="text-xs text-slate-500 font-medium">Agrupar por:</span>
            <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-0.5">
              {[
                { key: 'phase', label: 'Fase' },
                { key: 'product', label: 'Producto' },
                { key: 'modality', label: 'Modalidad' },
              ].map(g => (
                <button key={g.key} onClick={() => changeSummaryGroup(g.key)}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${summaryGroupBy === g.key ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                  data-testid={`summary-group-${g.key}`}>{g.label}</button>
              ))}
            </div>
            {summaryData && <span className="text-xs text-slate-400 ml-auto">Total: {summaryData.total} integraciones</span>}
          </div>
          {summaryLoading ? (
            <p className="text-sm text-slate-400 text-center py-8">Cargando resumen...</p>
          ) : summaryData ? (
            <div className="space-y-3">
              {Object.values(summaryData.groups).sort((a, b) => b.count - a.count).map(group => (
                <div key={group.label} className="border border-slate-200 rounded-lg overflow-hidden">
                  <div className="bg-slate-50 px-4 py-2.5 flex items-center justify-between border-b border-slate-200">
                    <h3 className="font-semibold text-sm text-slate-800">{group.label}</h3>
                    <div className="flex items-center gap-3 text-xs">
                      <span className="font-bold text-slate-700">{group.count}</span>
                      {group.certified !== undefined && (
                        <>
                          <span className="text-emerald-600">C: {group.certified}</span>
                          <span className="text-amber-600">P: {group.pending}</span>
                        </>
                      )}
                    </div>
                  </div>
                  <table className="w-full text-sm">
                    <tbody className="divide-y divide-slate-100">
                      {group.items.slice(0, 15).map((item, i) => (
                        <tr key={i} className="hover:bg-slate-50">
                          <td className="px-4 py-1.5 font-medium text-slate-800 text-xs">{item.name}</td>
                          {item.app_name !== undefined && <td className="px-3 py-1.5 text-xs text-slate-500">{item.app_name}</td>}
                          {item.status !== undefined && (
                            <td className="px-3 py-1.5 text-center">
                              <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${item.status === 'C' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>{item.status}</span>
                            </td>
                          )}
                          {item.integration_phase && (
                            <td className="px-3 py-1.5 text-center">
                              <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium border ${PHASE_COLORS[item.integration_phase] || 'bg-slate-100'}`}>{item.integration_phase}</span>
                            </td>
                          )}
                          {item.integration_modality && <td className="px-3 py-1.5 text-xs text-slate-500 text-right">{item.integration_modality}</td>}
                        </tr>
                      ))}
                      {group.items.length > 15 && (
                        <tr><td colSpan={5} className="px-4 py-1.5 text-xs text-slate-400 text-center">...y {group.items.length - 15} más</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              ))}
              {Object.keys(summaryData.groups).length === 0 && (
                <p className="text-sm text-slate-400 text-center py-8 italic">Sin datos para agrupar</p>
              )}
            </div>
          ) : null}
        </DialogContent>
      </Dialog>

      {/* Modal de Notificación — Nuevo Proyecto de Integración */}
      <Dialog open={emailNotifyOpen} onOpenChange={setEmailNotifyOpen}>
        <DialogContent className="max-w-lg" data-testid="email-notify-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-lg">
              <Mail size={20} className="text-blue-600" />
              Notificar Nuevo Proyecto
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="bg-blue-50 rounded-lg p-3 border border-blue-200">
              <p className="text-sm text-blue-800">
                Se enviara la notificacion al <strong>Gerente de Implementacion</strong> configurado en Correos de Notificacion.
              </p>
              {emailNotifyIntegrator && (
                <div className="mt-2 text-xs text-blue-700 space-y-0.5">
                  <p><strong>Integrador:</strong> {emailNotifyIntegrator.name}</p>
                  <p><strong>Aplicativo:</strong> {emailNotifyIntegrator.app_name}</p>
                </div>
              )}
            </div>
            <div>
              <Label className="text-sm font-medium">Comentarios adicionales (opcional)</Label>
              <Textarea
                placeholder="Agregue informacion adicional para el Gerente de Implementacion..."
                value={emailCustomMessage}
                onChange={(e) => setEmailCustomMessage(e.target.value)}
                rows={3}
                className="mt-1"
                data-testid="email-custom-message"
              />
            </div>
            <div>
              <Label className="text-sm font-medium">Enviar copia a (CC)</Label>
              <div className="flex gap-2 mt-1">
                <Input
                  type="email"
                  placeholder="correo@empresa.com"
                  value={emailNewRecipient}
                  onChange={(e) => setEmailNewRecipient(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addEmailRecipient(); } }}
                  className="flex-1"
                  data-testid="email-add-recipient-input"
                />
                <Button type="button" variant="outline" size="sm" onClick={addEmailRecipient} data-testid="email-add-recipient-btn">
                  <Plus size={14} />
                </Button>
              </div>
              {emailRecipientsList.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {emailRecipientsList.map((email) => (
                    <span key={email} className="inline-flex items-center gap-1 bg-slate-100 text-slate-700 px-2 py-0.5 rounded-full text-xs">
                      {email}
                      <button onClick={() => removeEmailRecipient(email)} className="hover:text-red-500">
                        <X size={12} />
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setEmailNotifyOpen(false)} data-testid="email-skip-btn">
                Omitir
              </Button>
              <Button
                onClick={sendNewProjectNotification}
                disabled={emailSending}
                className="bg-blue-600 hover:bg-blue-700 text-white"
                data-testid="email-send-btn"
              >
                <Mail size={14} className="mr-1" />
                {emailSending ? 'Enviando...' : 'Enviar Notificacion'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Integrators;
