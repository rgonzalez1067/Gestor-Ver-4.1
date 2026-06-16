import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import api from '../utils/api';
import { formatRif } from '../utils/rifFormatter';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../components/ui/select';
import { Popover, PopoverContent, PopoverTrigger } from '../components/ui/popover';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../components/ui/tooltip';
import { toast } from 'sonner';
import { usePermission } from '../hooks/usePermission';
import { ProjectTypeBadge } from '../components/projects/ProjectTypeBadge';
import { BulkReassignModal } from '../components/BulkReassignModal';
import { CommitmentModal } from '../components/CommitmentModal';
import { WorkloadReportFiltersModal } from '../components/WorkloadReportFiltersModal';
import { TemplatesAdminDialog } from '../components/projects/TemplatesAdminDialog';
import { MasterEditDialog } from '../components/projects/MasterEditDialog';
import {
  FolderKanban, Search, UserCheck, Clock, CheckCircle2, Pause,
  FileText, Filter, Paperclip, Eye, RefreshCw, X, UserPlus, AlertTriangle, Store, BarChart3, Ticket, Trash2, UserCog, Flag, Zap, Landmark, ChevronDown, CreditCard, ClipboardList, Pencil
} from 'lucide-react';

const STATUS_CONFIG = {
  'Por asignar': { color: 'bg-amber-100 text-amber-800 border-amber-200', icon: Clock },
  'Asignado': { color: 'bg-blue-100 text-blue-800 border-blue-200', icon: UserCheck },
  'En Gestión': { color: 'bg-indigo-100 text-indigo-800 border-indigo-200', icon: UserCog },
  'Suspendido': { color: 'bg-red-100 text-red-800 border-red-200', icon: Pause },
  'Implementado parcial': { color: 'bg-orange-100 text-orange-800 border-orange-200', icon: CheckCircle2 },
  'Culminado': { color: 'bg-emerald-100 text-emerald-800 border-emerald-200', icon: CheckCircle2 },
  'Anulado': { color: 'bg-slate-200 text-slate-700 border-slate-300', icon: X },
};

// Estados que se ocultan por defecto en la bandeja (cerrados / pausados).
const HIDDEN_DEFAULT_STATES = ['Suspendido', 'Implementado parcial', 'Culminado', 'Anulado'];
// Estados que disparan recordatorio de cierre de ticket en el portal
// (proyecto cerrado / suspendido / anulado).
const TICKET_REMINDER_STATES = ['Culminado', 'Suspendido', 'Anulado'];

// Toast ROJO prominente (esquina superior derecha) para recordar el cierre del
// Ticket cuando un proyecto pasa a un estado terminal/pausado.
const showTicketReminderToast = (status) => {
  toast.custom((t) => (
    <div
      className="w-[380px] bg-red-600 text-white rounded-xl shadow-2xl ring-2 ring-red-300/70 overflow-hidden"
      data-testid="ticket-reminder-toast"
      data-status={status}
    >
      <div className="flex items-start gap-3 p-4">
        <div className="shrink-0 mt-0.5 bg-white/20 rounded-lg p-2">
          <AlertTriangle size={22} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-bold text-sm leading-snug flex items-center gap-1.5">
            <Ticket size={15} /> Recuerde cerrar el Ticket
          </p>
          <p className="text-xs text-white/90 mt-1 break-words">
            El proyecto pasó a <strong>{status}</strong>. Cierre el Ticket en el portal al confirmar este estado.
          </p>
        </div>
        <button
          onClick={() => toast.dismiss(t)}
          className="shrink-0 p-1 rounded-lg hover:bg-white/15 transition-colors"
          aria-label="Cerrar"
          data-testid="ticket-reminder-close-btn"
        >
          <X size={16} />
        </button>
      </div>
    </div>
  ), { duration: 10000 });
};

// Estados asignables MANUALMENTE por el usuario vía "Cambiar estado".
// Los estados automáticos (Por asignar, Asignado, En Gestión) responden a triggers.
const STATUS_TRANSITIONS = [
  { id: 'En Gestión', label: 'En Gestión (Reactivar)', icon: UserCog, iconColor: 'text-indigo-600', reactivation: true },
  { id: 'Suspendido', label: 'Suspendido', icon: Pause, iconColor: 'text-red-600' },
  { id: 'Implementado parcial', label: 'Implementado parcial', icon: CheckCircle2, iconColor: 'text-orange-600' },
  { id: 'Culminado', label: 'Culminado', icon: CheckCircle2, iconColor: 'text-emerald-600' },
  { id: 'Anulado', label: 'Anulado', icon: X, iconColor: 'text-slate-600' },
];

/**
 * Patrocinador del proyecto (Implementación Patrocinada).
 *  - Escenario A (Directo): "Banco X".
 *  - Escenario B (Compuesto): "Procesador Y — Banco X".
 * Usa la etiqueta persistida si existe; si no, la calcula (proyectos legacy).
 */
const getPatrocinadorLabel = (p) => {
  if (p?.patrocinador_label) return p.patrocinador_label;
  if (!p?.sponsored_implementation || !p?.sponsoring_bank_name) return null;
  const proc = (p.sponsoring_processor_name || '').trim();
  return proc ? `${proc} — ${p.sponsoring_bank_name}` : p.sponsoring_bank_name;
};

// Normaliza el quote_type heredado a las 4 categorías canónicas para el filtro.
const normalizeProjectType = (qt) => {
  const t = (qt || '').toUpperCase();
  if (t === 'LINK_PAGO' || t === 'LINK') return 'LINK';
  if (t === 'FAST_TRACK') return 'MPOS';
  return t; // VPOS | MPOS | GATEWAY
};

// Opciones del filtro "Tipo de Proyecto" (label legible → valor canónico).
const PROJECT_TYPE_FILTERS = [
  { value: 'VPOS', label: 'VPOS' },
  { value: 'MPOS', label: 'MPOS' },
  { value: 'GATEWAY', label: 'Payment Gateway' },
  { value: 'LINK', label: 'Link de Pago' },
];

const Projects = () => {
  const { canEdit, hasSpecial, isAdmin: isAdminPerm, user: currentUser } = usePermission('proyectos');
  const canManageTemplates = isAdminPerm || hasSpecial('proyectos:manage_email_templates');
  // Coord/Gerente/Admin → acciones gerenciales (reasignación masiva + compromisos)
  const canManage = (() => {
    const role = (currentUser?.role || '').toLowerCase();
    const cargo = (currentUser?.cargo || '').toLowerCase();
    return role === 'admin' || cargo === 'coordinador' || cargo === 'gerente';
  })();
  const isAdmin = currentUser?.role === 'admin';
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [slaConfig, setSlaConfig] = useState(null); // matriz de días por etapa
  const [clientMap, setClientMap] = useState({}); // client_id → {fantasy_name, legal_name}
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('active');
  const [typeFilter, setTypeFilter] = useState('all'); // 'all' | 'VPOS' | 'MPOS' | 'GATEWAY' | 'LINK'
  const [sponsorFilter, setSponsorFilter] = useState('all');
  const [sponsorPickerOpen, setSponsorPickerOpen] = useState(false);
  const [sponsorSearch, setSponsorSearch] = useState('');

  // Assign/Reassign dialog
  const [assignDialogOpen, setAssignDialogOpen] = useState(false);
  const [assignProject, setAssignProject] = useState(null);
  const [implementers, setImplementers] = useState([]);
  // Fase B — Reasignación masiva + Compromisos (Coordinador/Gerente/Admin)
  const [bulkReassignOpen, setBulkReassignOpen] = useState(false);
  const [commitmentsOpen, setCommitmentsOpen] = useState(false);
  const [commitmentsTarget, setCommitmentsTarget] = useState(null);
  const [workloadFiltersOpen, setWorkloadFiltersOpen] = useState(false);
  const [assignForm, setAssignForm] = useState({ assigned_to_user_id: '', estimated_delivery_date: '', reassignment_comment: '', reassignment_date: '' });
  const [assignLoading, setAssignLoading] = useState(false);

  // Status change dialog
  const [statusDialogOpen, setStatusDialogOpen] = useState(false);
  const [statusProject, setStatusProject] = useState(null);
  const [statusForm, setStatusForm] = useState({ new_status: '', note: '', change_date: new Date().toISOString().slice(0, 10) });
  const [statusFile, setStatusFile] = useState(null);
  const [statusLoading, setStatusLoading] = useState(false);

  // Edición Maestra (Super-Admin Override)
  const [masterEditOpen, setMasterEditOpen] = useState(false);
  const [masterEditProject, setMasterEditProject] = useState(null);

  // Gestor global de Plantillas de Correo (acceso desde el maestro de Proyectos)
  const [emailTemplates, setEmailTemplates] = useState([]);
  const [templatesDialogOpen, setTemplatesDialogOpen] = useState(false);
  const [editingTemplateId, setEditingTemplateId] = useState(null);
  const [templateForm, setTemplateForm] = useState({ name: '', subject: '', body: '' });
  const [templateSaving, setTemplateSaving] = useState(false);

  const fetchTemplates = async () => {
    try {
      const res = await api.get('/email-templates?context=IMPLEMENTACION');
      setEmailTemplates(res.data || []);
    } catch (err) {
      toast.error('Error al cargar las plantillas de correo');
      setEmailTemplates([]);
    }
  };

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

  const fetchProjects = useCallback(async () => {
    try {
      const [projRes, statsRes, clientsRes, implRes] = await Promise.all([
        api.get('/projects'),
        api.get('/projects/stats'),
        api.get('/clients').catch(() => ({ data: [] })),
        api.get('/projects/implementers/list').catch(() => ({ data: [] })),
      ]);
      setProjects(projRes.data);
      setStats(statsRes.data);
      setImplementers(implRes.data || []);
      // Construir mapa cliente_id → {fantasy_name, legal_name} para tooltip
      const map = {};
      (clientsRes.data || []).forEach((c) => {
        if (c.client_id) {
          map[c.client_id] = {
            fantasy_name: c.fantasy_name || '',
            legal_name: c.legal_name || '',
          };
        }
      });
      setClientMap(map);
    } catch (err) { toast.error('Error cargando proyectos'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchProjects(); }, [fetchProjects]);

  // Mantenimiento (Admin): backfill del "Generador" (created_by_name) para
  // proyectos antiguos que lo tengan vacío (idempotente / no destructivo).
  const [backfillLoading, setBackfillLoading] = useState(false);
  const handleBackfillGenerator = async () => {
    if (!window.confirm('¿Cargar el nombre del "Generador" en los proyectos que lo tengan vacío?\n\nToma el dato de la cotización origen (o del usuario que la creó). Es seguro y solo afecta a los proyectos sin Generador.')) return;
    setBackfillLoading(true);
    try {
      const { data } = await api.post('/projects/backfill-generator');
      if (data.updated > 0) {
        toast.success(`Generador cargado: ${data.updated} proyecto(s). Sin Generador restantes: ${data.remaining_missing}.`);
      } else {
        toast.info('Todos los proyectos ya tienen Generador asignado. No hubo cambios.');
      }
      fetchProjects();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'No se pudo ejecutar la carga del Generador.');
    } finally {
      setBackfillLoading(false);
    }
  };

  useEffect(() => {
    api.get('/project-sla/config')
      .then((r) => setSlaConfig(r.data.config?.stages || null))
      .catch(() => setSlaConfig(null));
  }, []);

  // ==================== ASSIGN / REASSIGN ====================
  const openAssignDialog = (project) => {
    setAssignProject(project);
    const isReassign = !!project.assigned_to_name;
    setAssignForm({
      assigned_to_user_id: '',
      estimated_delivery_date: project.estimated_delivery_date || '',
      reassignment_comment: '',
      reassignment_date: isReassign ? new Date().toISOString().slice(0, 10) : ''
    });
    setAssignDialogOpen(true);
  };

  const handleAssign = async () => {
    if (!assignForm.assigned_to_user_id) { toast.error('Seleccione un implementador'); return; }
    const isReassign = !!assignProject.assigned_to_name;
    if (isReassign && !assignForm.reassignment_comment.trim()) { toast.error('Ingrese un comentario para la reasignación'); return; }
    setAssignLoading(true);
    try {
      await api.put(`/projects/${assignProject.project_id}/assign`, assignForm);
      toast.success(isReassign ? 'Proyecto reasignado exitosamente' : 'Proyecto asignado exitosamente');
      setAssignDialogOpen(false);
      fetchProjects();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al asignar'); }
    finally { setAssignLoading(false); }
  };

  // ==================== STATUS CHANGE ====================
  const openStatusDialog = (project) => {
    setStatusProject(project);
    setStatusForm({ new_status: '', note: '', change_date: new Date().toISOString().slice(0, 10) });
    setStatusFile(null);
    setStatusDialogOpen(true);
  };

  const handleStatusChange = async () => {
    if (!statusForm.new_status) { toast.error('Seleccione un estado'); return; }
    if (!statusForm.note.trim()) { toast.error('El comentario de justificación es obligatorio'); return; }
    setStatusLoading(true);
    try {
      const fd = new FormData();
      fd.append('new_status', statusForm.new_status);
      fd.append('note', statusForm.note);
      fd.append('change_date', statusForm.change_date || '');
      if (statusFile) fd.append('file', statusFile);
      await api.put(`/projects/${statusProject.project_id}/status`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      toast.success(`Estado: ${statusForm.new_status}`);
      if (TICKET_REMINDER_STATES.includes(statusForm.new_status)) {
        showTicketReminderToast(statusForm.new_status);
      }
      setStatusDialogOpen(false);
      fetchProjects();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al cambiar estado'); }
    finally { setStatusLoading(false); }
  };

  const handleDeleteProject = async (project) => {
    if (!confirm(`¿Eliminar proyecto ${project.project_number} (${project.client_name})? Esta acción no se puede deshacer.`)) return;
    try {
      await api.delete(`/projects/${project.project_id}`);
      toast.success('Proyecto eliminado');
      fetchProjects();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al eliminar');
    }
  };

  const filtered = projects.filter(p => {
    const sponsorLabel = getPatrocinadorLabel(p);
    // Filtro "Cliente": consulta estrictamente sobre el Nombre de Fantasía.
    const fantasy = clientMap[p.client_id]?.fantasy_name || p.fantasy_name || '';
    const matchSearch = !searchTerm ||
      p.project_number?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.ticket_number?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      fantasy.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.client_rif?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.assigned_to_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.created_by_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      sponsorLabel?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchStatus = statusFilter === 'all'
      ? true
      : statusFilter === 'active'
        ? !HIDDEN_DEFAULT_STATES.includes(p.status)
        : statusFilter === 'suspended'
          ? p.status === 'Suspendido'
          : statusFilter === 'in_progress'
            ? ['Asignado', 'En Gestión', 'Implementado parcial'].includes(p.status)
            : p.status === statusFilter;
    const matchSponsor = sponsorFilter === 'all'
      ? true
      : sponsorFilter === '__none__'
        ? !sponsorLabel
        : sponsorLabel === sponsorFilter;
    const matchType = typeFilter === 'all' ? true : normalizeProjectType(p.quote_type) === typeFilter;
    return matchSearch && matchStatus && matchSponsor && matchType;
  });

  // Lista de patrocinadores distintos (para el dropdown del filtro).
  const sponsorOptions = Array.from(
    new Set(projects.map(getPatrocinadorLabel).filter(Boolean))
  ).sort((a, b) => a.localeCompare(b));
  const sponsorOptionsFiltered = sponsorOptions.filter(
    s => !sponsorSearch || s.toLowerCase().includes(sponsorSearch.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex min-h-screen bg-white">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-green-600" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-white">
      <Sidebar />
      <main className="flex-1 p-8" data-testid="projects-page">
        <div className="max-w-7xl mx-auto">
          <div className="mb-8 flex items-start justify-between gap-4">
            <div>
              <h1 className="text-4xl font-bold text-slate-900 font-manrope mb-2">Proyectos</h1>
              <p className="text-slate-600">Seguimiento de implementaciones post-venta</p>
            </div>
            <div className="flex items-center gap-2">
              {canManageTemplates && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={openTemplatesAdmin}
                  data-testid="projects-templates-btn"
                  className="border-slate-300 text-slate-700 hover:bg-slate-50"
                  title="Gestionar plantillas de correo de implementación (función especial autorizada por perfil)"
                >
                  <ClipboardList size={14} className="mr-1.5" />
                  Plantillas
                </Button>
              )}
              {canManage && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => { setBulkReassignOpen(true); }}
                  data-testid="bulk-reassign-open-btn"
                  className="border-purple-300 text-purple-700 hover:bg-purple-50"
                  title="Reasignar múltiples proyectos entre implementadores"
                >
                  <UserCog size={14} className="mr-1.5" />
                  Reasignación Masiva
                </Button>
              )}
              {isAdmin && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleBackfillGenerator}
                  disabled={backfillLoading}
                  data-testid="backfill-generator-btn"
                  className="border-amber-300 text-amber-700 hover:bg-amber-50"
                  title="Cargar el nombre del 'Generador' en proyectos antiguos que lo tengan vacío (idempotente, solo Admin)"
                >
                  <RefreshCw size={14} className={`mr-1.5 ${backfillLoading ? 'animate-spin' : ''}`} />
                  {backfillLoading ? 'Cargando…' : 'Cargar Generador'}
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setWorkloadFiltersOpen(true)}
                data-testid="projects-workload-pdf-btn"
                className="border-indigo-300 text-indigo-700 hover:bg-indigo-50"
                title="Abrir filtros y generar PDF de carga/estatus agrupado por implementador"
              >
                <FileText size={14} className="mr-1.5" />
                Reporte Carga (PDF)
              </Button>
            </div>
          </div>

          {/* Stats Cards */}
          <div className="grid grid-cols-5 gap-4 mb-6">
            {[
              { label: 'Total', value: stats.total || 0, cls: 'bg-slate-50 border-slate-200 text-slate-700', filter: 'all' },
              { label: 'Pendientes', value: stats.pending || 0, cls: 'bg-amber-50 border-amber-200 text-amber-700', filter: 'Por asignar' },
              { label: 'En Proceso', value: stats.in_progress || 0, cls: 'bg-blue-50 border-blue-200 text-blue-700', filter: 'in_progress' },
              { label: 'Suspendidos', value: stats.blocked || 0, cls: 'bg-red-50 border-red-200 text-red-700', filter: 'suspended' },
              { label: 'Finalizados', value: stats.completed || 0, cls: 'bg-emerald-50 border-emerald-200 text-emerald-700', filter: 'Culminado' },
            ].map(s => (
              <div key={s.label}
                className={`p-4 rounded-lg border cursor-pointer transition-all ${s.cls} ${statusFilter === s.filter ? 'ring-2 ring-offset-1 ring-current' : 'hover:shadow-sm'}`}
                onClick={() => setStatusFilter(s.filter)}
                data-testid={`stat-${s.label.toLowerCase().replace(/\s/g, '-')}`}>
                <p className="text-2xl font-bold">{s.value}</p>
                <p className="text-sm">{s.label}</p>
              </div>
            ))}
          </div>

          {/* Filters */}
          <div className="flex gap-3 mb-4">
            <div className="relative flex-1 max-w-sm">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <Input placeholder="Buscar por ticket, proyecto, cliente, RIF, implementador o generador..."
                value={searchTerm} onChange={e => setSearchTerm(e.target.value)}
                className="pl-9" data-testid="project-search" />
            </div>
            <div className="flex items-center gap-2">
              <Filter size={16} className="text-slate-400" />
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-[220px]" data-testid="project-status-filter">
                  <SelectValue placeholder="Todos los estados" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Activos (ocultar cerrados)</SelectItem>
                  <SelectItem value="all">Todos los estados</SelectItem>
                  {Object.keys(STATUS_CONFIG).map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            {/* Filtro por Tipo de Proyecto (heredado del Tipo de Cotización origen) */}
            <div className="flex items-center gap-2">
              <CreditCard size={16} className="text-slate-400" />
              <Select value={typeFilter} onValueChange={setTypeFilter}>
                <SelectTrigger className={`w-[190px] ${typeFilter !== 'all' ? 'border-indigo-400 text-indigo-700' : ''}`} data-testid="project-type-filter">
                  <SelectValue placeholder="Todos los tipos" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all" data-testid="project-type-option-all">Todos los tipos</SelectItem>
                  {PROJECT_TYPE_FILTERS.map(t => (
                    <SelectItem key={t.value} value={t.value} data-testid={`project-type-option-${t.value.toLowerCase()}`}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {/* Filtro por Patrocinador (dropdown + búsqueda interna) */}
            <div className="flex items-center gap-2">
              <Landmark size={16} className="text-slate-400" />
              <Popover open={sponsorPickerOpen} onOpenChange={(o) => { setSponsorPickerOpen(o); if (!o) setSponsorSearch(''); }}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className={`w-[240px] justify-between font-normal ${sponsorFilter !== 'all' ? 'border-indigo-400 text-indigo-700' : 'text-slate-600'}`}
                    data-testid="project-sponsor-filter"
                  >
                    <span className="truncate">
                      {sponsorFilter === 'all'
                        ? 'Todos los patrocinadores'
                        : sponsorFilter === '__none__'
                          ? 'Sin patrocinador'
                          : sponsorFilter}
                    </span>
                    <ChevronDown size={15} className="shrink-0 opacity-60" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[280px] p-0" align="start" data-testid="project-sponsor-popover">
                  <div className="p-2 border-b">
                    <Input
                      placeholder="Buscar patrocinador…"
                      value={sponsorSearch}
                      onChange={(e) => setSponsorSearch(e.target.value)}
                      className="h-8 text-sm"
                      data-testid="project-sponsor-search"
                    />
                  </div>
                  <div className="max-h-[260px] overflow-y-auto py-1">
                    <button
                      type="button"
                      className={`w-full text-left px-3 py-1.5 text-sm hover:bg-slate-100 ${sponsorFilter === 'all' ? 'font-semibold text-indigo-700' : 'text-slate-700'}`}
                      onClick={() => { setSponsorFilter('all'); setSponsorPickerOpen(false); setSponsorSearch(''); }}
                      data-testid="project-sponsor-option-all"
                    >
                      Todos los patrocinadores
                    </button>
                    <button
                      type="button"
                      className={`w-full text-left px-3 py-1.5 text-sm hover:bg-slate-100 ${sponsorFilter === '__none__' ? 'font-semibold text-indigo-700' : 'text-slate-500'}`}
                      onClick={() => { setSponsorFilter('__none__'); setSponsorPickerOpen(false); setSponsorSearch(''); }}
                      data-testid="project-sponsor-option-none"
                    >
                      Sin patrocinador
                    </button>
                    {sponsorOptionsFiltered.length === 0 && (
                      <p className="px-3 py-2 text-xs text-slate-400">Sin coincidencias</p>
                    )}
                    {sponsorOptionsFiltered.map((s) => (
                      <button
                        key={s}
                        type="button"
                        className={`w-full text-left px-3 py-1.5 text-sm hover:bg-slate-100 ${sponsorFilter === s ? 'font-semibold text-indigo-700' : 'text-slate-700'}`}
                        onClick={() => { setSponsorFilter(s); setSponsorPickerOpen(false); setSponsorSearch(''); }}
                        data-testid={`project-sponsor-option-${s}`}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </PopoverContent>
              </Popover>
            </div>
          </div>

          {/* Projects Table */}
          {filtered.length === 0 ? (
            <div className="text-center py-16 bg-slate-50 rounded-lg border border-slate-200" data-testid="no-projects">
              <FolderKanban size={48} className="mx-auto text-slate-300 mb-4" />
              <p className="text-lg font-medium text-slate-500">No hay proyectos</p>
              <p className="text-sm text-slate-400">Los proyectos se crean automáticamente al enviar una cotización a Implementación</p>
            </div>
          ) : (
            <div className="bg-white rounded-lg border border-slate-200 overflow-x-auto">
              <table className="w-full min-w-[1100px]">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Cliente / Ticket</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Tipo</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Sede</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Estado</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Envío a Imple</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Implementador</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Generador</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Patrocinador</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-slate-600 uppercase">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filtered.map(project => {
                    const stCfg = STATUS_CONFIG[project.status] || STATUS_CONFIG['Por asignar'];
                    const StIcon = stCfg.icon;
                    const hasAssignee = !!project.assigned_to_name;
                    
                    // === SLA SEMÁFORO ===
                    const now = new Date();
                    const isSuspended = project.status?.includes('Detenido') || project.status?.includes('Suspendido');
                    const isFinished = project.status === 'Finalizado' || project.status === 'Cancelado';
                    const pct = project.rollup_progress?.global_progress || 0;
                    
                    let slaDays = 0;
                    let slaLabel = '';
                    let slaColor = 'bg-emerald-500';

                    // Umbrales configurables por etapa (matriz SLA). Fallback 2/4.
                    const _th = (stageKey) => {
                      const c = (slaConfig && slaConfig[stageKey]) || {};
                      return { w: Number(c.warning_days ?? 2), d: Number(c.delay_days ?? 4) };
                    };
                    const _color = (days, stageKey) => {
                      const { w, d } = _th(stageKey);
                      return days >= d ? 'bg-red-500' : days >= w ? 'bg-yellow-500' : 'bg-emerald-500';
                    };
                    const _enteredDays = (...candidates) => {
                      const ref = candidates.find(Boolean);
                      const refDate = ref ? new Date(ref) : now;
                      return Math.floor((now - refDate) / (1000 * 60 * 60 * 24));
                    };

                    if (isSuspended) {
                      slaColor = 'bg-slate-400';
                      slaLabel = 'Detenido';
                    } else if (isFinished) {
                      slaColor = 'bg-blue-500';
                      slaLabel = project.status;
                    } else if (!project.assigned_to_name) {
                      // Etapa A: Sin asignar — desde que entró al estado actual
                      slaDays = _enteredDays(project.status_changed_at, project.sent_to_implementation_at, project.created_at);
                      slaLabel = `Sin asignar · ${slaDays}d`;
                      slaColor = _color(slaDays, 'por_asignar');
                    } else if (!project.ticket_number) {
                      // Etapa B: Asignado sin desbloquear
                      slaDays = _enteredDays(project.status_changed_at, project.assigned_at, project.created_at);
                      slaLabel = `Pendiente desbloqueo · ${slaDays}d`;
                      slaColor = _color(slaDays, 'asignado');
                    } else {
                      // Etapa C: Desbloqueado / En Gestión — desde que entró al estado actual
                      slaDays = _enteredDays(project.status_changed_at, project.unblocked_at, project.assigned_at, project.created_at);
                      slaLabel = `En gestión · ${slaDays}d`;
                      slaColor = _color(slaDays, 'en_gestion');
                    }
                    
                    return (
                      <React.Fragment key={project.project_id}>
                      <tr className={`hover:bg-slate-50 transition-colors ${project.direct_project ? 'bg-amber-50/70 hover:bg-amber-100/70' : ''}`}
                        data-testid={`project-row-${project.project_id}`}
                        data-direct-project={project.direct_project ? 'true' : 'false'}>
                        <td className="px-4 py-3">
                          {/* Cliente como info principal — Nombre de Fantasía nativo; hover → Razón Social */}
                          {(() => {
                            const c = clientMap[project.client_id] || {};
                            const fantasy = c.fantasy_name || project.fantasy_name || '';
                            const legal = c.legal_name || project.client_name || '';
                            // Mostramos Nombre de Fantasía como principal; hover → Razón Social.
                            const mainName = fantasy || legal;
                            if (!fantasy || fantasy === legal) {
                              return (
                                <p className="text-sm font-semibold text-slate-900" data-testid={`project-client-${project.project_id}`}>
                                  {mainName}
                                </p>
                              );
                            }
                            return (
                              <TooltipProvider delayDuration={200}>
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <p
                                      className="text-sm font-semibold text-slate-900 cursor-help underline decoration-dotted decoration-slate-300 underline-offset-2 hover:decoration-slate-500 inline-block"
                                      data-testid={`project-client-${project.project_id}`}
                                    >
                                      {fantasy}
                                    </p>
                                  </TooltipTrigger>
                                  <TooltipContent side="top" className="bg-slate-900 text-white text-xs max-w-[280px] border-slate-700">
                                    <p className="font-semibold mb-0.5 text-slate-300">Razón Social</p>
                                    <p className="font-normal">{legal}</p>
                                  </TooltipContent>
                                </Tooltip>
                              </TooltipProvider>
                            );
                          })()}
                          <p className="text-xs font-mono text-slate-400">{formatRif(project.client_rif)}</p>
                          {project.ticket_number && (
                            <p className="text-xs text-indigo-600 flex items-center gap-1 mt-0.5" data-testid={`ticket-${project.project_id}`}>
                              <Ticket size={11} />{project.ticket_number}
                            </p>
                          )}
                          <div className="flex gap-1 mt-1 flex-wrap">
                            {project.project_type === 'multistore' && (
                              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-semibold rounded bg-blue-100 text-blue-700 border border-blue-200" data-testid="project-multistore-badge">
                                <Store size={10} />Multitienda ({project.stores?.length || 0})
                              </span>
                            )}
                            {project.direct_project && (
                              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-semibold rounded bg-amber-100 text-amber-700 border border-amber-300" data-testid="project-direct-badge" title="Proyecto creado desde el flujo Proyecto Directo">
                                <Zap size={10} />Directo
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <button
                            type="button"
                            onClick={() => setTypeFilter(prev => prev === normalizeProjectType(project.quote_type) ? 'all' : normalizeProjectType(project.quote_type))}
                            title="Filtrar por este tipo de proyecto"
                            className="cursor-pointer hover:opacity-80 transition-opacity"
                            data-testid={`project-type-chip-${project.project_id}`}
                          >
                            <ProjectTypeBadge quoteType={project.quote_type} />
                          </button>
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-600">{project.client_sede || '—'}</td>
                        <td className="px-4 py-3">
                          {/* Badge de estado: color de fondo SINCRONIZADO con la
                              barra de avance/SLA (slaColor) y texto blanco
                              forzado para máximo contraste. Feb 2026. */}
                          <span className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-full ${slaColor} text-white shadow-sm`}>
                            <StIcon size={12} className="text-white" />{project.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-600" data-testid={`project-sent-impl-${project.project_id}`}>
                          {project.sent_to_implementation_at
                            ? new Date(project.sent_to_implementation_at).toLocaleDateString('es-VE')
                            : <span className="text-slate-400 italic">—</span>}
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-600">
                          {project.assigned_to_name ? (
                            <div>
                              <span>{project.assigned_to_name}</span>
                              {project.assigned_at && (
                                <p className="text-[10px] text-slate-400 mt-0.5">Asignado: {new Date(project.assigned_at).toLocaleDateString('es-VE')}</p>
                              )}
                              {project.last_contact_at && (
                                <p className="text-[10px] text-emerald-600 mt-0.5" data-testid={`last-contact-${project.project_id}`}>
                                  Último contacto: {new Date(project.last_contact_at).toLocaleDateString('es-VE')}
                                </p>
                              )}
                            </div>
                          ) : <span className="text-slate-400 italic">Sin asignar</span>}
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-600" data-testid={`project-generator-${project.project_id}`}>
                          {project.created_by_name && project.created_by_name !== '—'
                            ? <span>{project.created_by_name}</span>
                            : <span className="text-slate-400 italic">—</span>}
                        </td>
                        <td className="px-4 py-3 text-sm" data-testid={`project-sponsor-${project.project_id}`}>
                          {getPatrocinadorLabel(project)
                            ? <span className="inline-flex items-center gap-1 text-slate-700">
                                <Landmark size={13} className="text-indigo-500 shrink-0" />
                                <span className="font-medium">{getPatrocinadorLabel(project)}</span>
                              </span>
                            : <span className="text-slate-400 italic">—</span>}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-center gap-1">
                            {/* Cambiar Estado */}
                            <Button size="sm" variant="outline" onClick={() => openStatusDialog(project)}
                              title="Cambiar Estado"
                              className="h-8 px-2 text-orange-600 hover:bg-orange-50"
                              data-testid={`status-btn-${project.project_id}`}>
                              <RefreshCw size={14} />
                            </Button>
                            {/* Asignar / Reasignar — solo icono para no desbordar la columna */}
                            {canEdit && <Button size="sm" variant="outline" onClick={() => openAssignDialog(project)}
                              title={hasAssignee ? 'Reasignar' : 'Asignar'}
                              className={`h-8 px-2 ${hasAssignee ? 'text-purple-600 hover:bg-purple-50' : 'text-blue-600 hover:bg-blue-50'}`}
                              data-testid={`assign-btn-${project.project_id}`}>
                              {hasAssignee ? <UserPlus size={14} /> : <UserCheck size={14} />}
                            </Button>}
                            {/* Ver Detalle — Iter39: deshabilitado si no hay implementador asignado. */}
                            <Button
                              size="sm" variant="outline"
                              title={hasAssignee ? 'Detalle del Proyecto' : 'Detalle no disponible: el proyecto debe tener un implementador asignado'}
                              onClick={() => hasAssignee && navigate(`/projects/${project.project_id}`)}
                              disabled={!hasAssignee}
                              className={`h-8 px-2 ${hasAssignee ? 'text-emerald-600' : 'text-slate-300 cursor-not-allowed opacity-60'}`}
                              data-testid={`detail-btn-${project.project_id}`}
                              data-detail-enabled={hasAssignee ? 'true' : 'false'}>
                              <Eye size={14} />
                            </Button>
                            {/* Compromiso (Coord/Gerente/Admin crea/gestiona; todos leen) */}
                            {(() => {
                              const active = (project.commitments || []).filter(c => !c.completed);
                              const hasActive = active.length > 0;
                              return (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  title={hasActive ? `${active.length} compromiso(s) activo(s)` : 'Gestionar compromisos gerenciales'}
                                  onClick={() => { setCommitmentsTarget(project); setCommitmentsOpen(true); }}
                                  className={`h-8 px-2 relative ${hasActive ? 'text-red-600 border-red-300 hover:bg-red-50 animate-pulse' : 'text-slate-500 hover:text-red-600'}`}
                                  data-testid={`commitment-btn-${project.project_id}`}
                                >
                                  <Flag size={14} />
                                  {hasActive && (
                                    <span className="absolute -top-1 -right-1 bg-red-600 text-white text-[9px] font-bold rounded-full w-4 h-4 flex items-center justify-center">
                                      {active.length}
                                    </span>
                                  )}
                                </Button>
                              );
                            })()}
                            {isAdmin && (
                              <Button size="sm" variant="outline" title="Edición Maestra (Admin)"
                                onClick={() => { setMasterEditProject(project); setMasterEditOpen(true); }}
                                className="h-8 px-2 text-slate-500 hover:text-slate-800 hover:border-slate-400" data-testid={`master-edit-btn-${project.project_id}`}>
                                <Pencil size={14} />
                              </Button>
                            )}
                            {isAdmin && (
                              <Button size="sm" variant="outline" title="Eliminar Proyecto"
                                onClick={() => handleDeleteProject(project)}
                                className="h-8 px-2 text-slate-300 hover:text-rose-600 hover:border-rose-300" data-testid={`delete-btn-${project.project_id}`}>
                                <Trash2 size={14} />
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                      {/* Fila SLA Semáforo */}
                      <tr className="border-b border-slate-200" data-testid={`sla-row-${project.project_id}`}>
                        <td colSpan={8} className="px-4 py-1.5">
                          <div className="flex items-center gap-3" title={`${slaLabel} — Avance: ${pct}%`}>
                            <div className="flex-1 bg-slate-100 rounded-full h-3 overflow-hidden">
                              <div className={`h-full rounded-full transition-all duration-500 ${isSuspended ? 'bg-slate-400 bg-[length:20px_20px] bg-[linear-gradient(45deg,rgba(255,255,255,.15)_25%,transparent_25%,transparent_50%,rgba(255,255,255,.15)_50%,rgba(255,255,255,.15)_75%,transparent_75%,transparent)]' : slaColor}`} style={{ width: `${Math.max(Math.min(pct, 100), 5)}%` }} />
                            </div>
                            <span className={`text-xs font-bold min-w-[36px] text-right ${pct >= 100 ? 'text-emerald-600' : 'text-slate-600'}`}>{pct}%</span>
                            <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full whitespace-nowrap ${
                              isSuspended ? 'bg-slate-100 text-slate-500' :
                              isFinished ? 'bg-blue-50 text-blue-600' :
                              slaColor === 'bg-emerald-500' ? 'bg-emerald-50 text-emerald-700' :
                              slaColor === 'bg-yellow-500' ? 'bg-yellow-50 text-yellow-700' :
                              'bg-red-50 text-red-700'
                            }`} data-testid={`sla-badge-${project.project_id}`}>
                              {slaLabel}
                            </span>
                          </div>
                        </td>
                      </tr>
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* ==================== STATUS CHANGE DIALOG ==================== */}
        <Dialog open={statusDialogOpen} onOpenChange={setStatusDialogOpen}>
          <DialogContent className="max-w-md" data-testid="status-change-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <RefreshCw size={20} className="text-orange-500" />
                Cambiar Estado del Proyecto
              </DialogTitle>
            </DialogHeader>
            {statusProject && (
              <div className="space-y-4">
                <div className="bg-slate-50 border rounded-lg p-3">
                  <p className="font-semibold text-sm">{statusProject.project_number}</p>
                  <p className="text-xs text-slate-500">{statusProject.client_name}</p>
                  <div className="mt-2">
                    <span className="text-[10px] text-slate-500 uppercase">Estado actual:</span>
                    <span className={`ml-2 inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full border ${STATUS_CONFIG[statusProject.status]?.color || ''}`}>
                      {statusProject.status}
                    </span>
                  </div>
                </div>

                {/* Status options */}
                <div>
                  <Label className="text-sm">Nuevo Estado</Label>
                  <div className="space-y-1.5 mt-1.5">
                    {STATUS_TRANSITIONS.filter(t => {
                      if (t.id === statusProject.status) return false;
                      // La opción de reactivar solo aplica a proyectos cerrados/pausados.
                      if (t.reactivation) return HIDDEN_DEFAULT_STATES.includes(statusProject.status);
                      return true;
                    }).map(t => {
                      const TIcon = t.icon;
                      const selected = statusForm.new_status === t.id;
                      return (
                        <button key={t.id} onClick={() => setStatusForm(p => ({ ...p, new_status: t.id }))}
                          className={`w-full flex items-center gap-3 p-3 rounded-lg border-2 text-left transition-all ${selected ? 'border-slate-800 bg-slate-50 shadow-sm' : 'border-slate-200 hover:border-slate-300'}`}
                          data-testid={`status-option-${t.id.replace(/[\s\/]/g, '-').toLowerCase()}`}>
                          <TIcon size={18} className={t.iconColor} />
                          <span className="text-sm font-medium text-slate-800">{t.label}</span>
                          {selected && <CheckCircle2 size={16} className="ml-auto text-slate-800" />}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Date + Comment (justificación obligatoria) */}
                {statusForm.new_status && (
                  <div className="space-y-3 pt-2 border-t border-slate-200 animate-in fade-in-0 slide-in-from-top-1">
                    {TICKET_REMINDER_STATES.includes(statusForm.new_status) && (
                      <div className="flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 p-2.5 text-amber-800" data-testid="status-ticket-reminder">
                        <AlertTriangle size={15} className="mt-0.5 shrink-0" />
                        <span className="text-xs">Recuerde <strong>cerrar el Ticket</strong> en el portal al confirmar este estado.</span>
                      </div>
                    )}
                    <div>
                      <Label className="text-sm">Fecha del Cambio</Label>
                      <Input type="date" value={statusForm.change_date}
                        onChange={e => setStatusForm(p => ({ ...p, change_date: e.target.value }))}
                        className="mt-1" data-testid="status-change-date" />
                    </div>
                    <div>
                      <Label className="text-sm">Comentario de Justificación <span className="text-red-500">*</span></Label>
                      <Textarea value={statusForm.note}
                        onChange={e => setStatusForm(p => ({ ...p, note: e.target.value }))}
                        placeholder="Motivo o detalle del cambio de estado (obligatorio)..."
                        className="mt-1 min-h-[60px] text-sm" data-testid="status-change-comment" />
                    </div>
                    <div>
                      <Label className="text-sm">Anexo (opcional)</Label>
                      <Input type="file" onChange={e => setStatusFile(e.target.files?.[0] || null)}
                        className="mt-1 text-sm" data-testid="status-change-file" />
                      {statusFile && (
                        <p className="mt-1 flex items-center gap-1 text-xs text-slate-500">
                          <Paperclip size={11} />{statusFile.name}
                        </p>
                      )}
                    </div>
                  </div>
                )}

                <div className="flex justify-end gap-3 pt-2 border-t">
                  <Button variant="outline" onClick={() => setStatusDialogOpen(false)}>Cancelar</Button>
                  <Button onClick={handleStatusChange}
                    disabled={statusLoading || !statusForm.new_status || !statusForm.note.trim()}
                    className="bg-orange-600 hover:bg-orange-700 text-white"
                    data-testid="status-change-confirm-btn">
                    {statusLoading ? 'Actualizando...' : 'Confirmar Cambio'}
                  </Button>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* ==================== ASSIGN / REASSIGN DIALOG ==================== */}
        <Dialog open={assignDialogOpen} onOpenChange={setAssignDialogOpen}>
          <DialogContent className="max-w-md" data-testid="assign-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                {assignProject?.assigned_to_name
                  ? <><UserPlus className="text-purple-500" size={20} />Reasignar Proyecto</>
                  : <><UserCheck className="text-blue-500" size={20} />Asignar Proyecto</>
                }
              </DialogTitle>
            </DialogHeader>
            {assignProject && (
              <div className="space-y-4">
                <div className="bg-slate-50 border rounded-lg p-3">
                  <p className="font-semibold text-sm">{assignProject.project_number}</p>
                  <p className="text-xs text-slate-500">{assignProject.client_name} — {formatRif(assignProject.client_rif)}</p>
                </div>

                {/* Current assignee (only for reassignment) */}
                {assignProject.assigned_to_name && (
                  <div className="bg-purple-50 border border-purple-200 rounded-lg p-3" data-testid="current-assignee-info">
                    <p className="text-[10px] text-purple-600 uppercase font-semibold mb-1">Responsable Actual</p>
                    <p className="text-sm font-medium text-purple-900">{assignProject.assigned_to_name}</p>
                    {assignProject.assigned_at && (
                      <p className="text-xs text-purple-500">Asignado: {new Date(assignProject.assigned_at).toLocaleDateString('es-VE')}</p>
                    )}
                  </div>
                )}

                <div>
                  <Label className="text-sm">Nuevo Implementador</Label>
                  <Select value={assignForm.assigned_to_user_id} onValueChange={v => setAssignForm({ ...assignForm, assigned_to_user_id: v })}>
                    <SelectTrigger className="mt-1" data-testid="select-implementer"><SelectValue placeholder="Seleccionar implementador..." /></SelectTrigger>
                    <SelectContent>
                      {implementers.map(u => (
                        <SelectItem key={u.user_id} value={u.user_id}>
                          {u.first_name} {u.last_name} {u.cargo ? `(${u.cargo})` : ''}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {assignForm.assigned_to_user_id && (
                    <p className="text-[10px] text-slate-400 mt-1">
                      Fecha de asignación: <span className="font-medium text-slate-600">{new Date().toLocaleDateString('es-VE')}</span> (se registra automáticamente)
                    </p>
                  )}
                </div>

                {/* Reassignment fields */}
                {assignProject.assigned_to_name && (
                  <div className="space-y-3 pt-2 border-t border-purple-200 animate-in fade-in-0">
                    <div>
                      <Label className="text-sm">Fecha de Reasignación <span className="text-red-500">*</span></Label>
                      <Input type="date" value={assignForm.reassignment_date}
                        onChange={e => setAssignForm({ ...assignForm, reassignment_date: e.target.value })}
                        className="mt-1" data-testid="reassign-date" />
                    </div>
                    <div>
                      <Label className="text-sm">Motivo de la Reasignación <span className="text-red-500">*</span></Label>
                      <Textarea value={assignForm.reassignment_comment}
                        onChange={e => setAssignForm({ ...assignForm, reassignment_comment: e.target.value })}
                        placeholder="Explique el motivo de la reasignación..."
                        className="mt-1 min-h-[60px] text-sm" data-testid="reassign-comment" />
                    </div>
                  </div>
                )}

                <div className="flex justify-end gap-3 pt-2 border-t">
                  <Button variant="outline" onClick={() => setAssignDialogOpen(false)}>Cancelar</Button>
                  <Button onClick={handleAssign}
                    disabled={assignLoading || !assignForm.assigned_to_user_id || (assignProject.assigned_to_name && !assignForm.reassignment_comment.trim())}
                    className={`text-white ${assignProject.assigned_to_name ? 'bg-purple-600 hover:bg-purple-700' : 'bg-blue-600 hover:bg-blue-700'}`}
                    data-testid="assign-confirm-btn">
                    {assignLoading ? 'Procesando...' : assignProject.assigned_to_name ? 'Reasignar Proyecto' : 'Asignar Proyecto'}
                  </Button>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* Fase B — Modales gerenciales */}
        {bulkReassignOpen && (
          <BulkReassignModal
            open={bulkReassignOpen}
            onClose={() => setBulkReassignOpen(false)}
            onSuccess={() => { fetchProjects(); }}
            implementadores={implementers.map(u => ({ user_id: u.user_id, full_name: u.full_name || `${u.first_name||''} ${u.last_name||''}`.trim() }))}
            projects={projects}
          />
        )}
        {commitmentsOpen && commitmentsTarget && (
          <CommitmentModal
            open={commitmentsOpen}
            onClose={() => { setCommitmentsOpen(false); setCommitmentsTarget(null); }}
            projectId={commitmentsTarget.project_id}
            projectNumber={commitmentsTarget.project_number || commitmentsTarget.client_name}
            clientName={commitmentsTarget.client_name}
            canManage={canManage}
            onChange={fetchProjects}
          />
        )}
        {workloadFiltersOpen && (
          <WorkloadReportFiltersModal
            open={workloadFiltersOpen}
            onClose={() => setWorkloadFiltersOpen(false)}
          />
        )}

        {/* ==================== TEMPLATES ADMIN DIALOG (acceso global) ==================== */}
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

        {masterEditProject && (
          <MasterEditDialog
            open={masterEditOpen}
            onOpenChange={(o) => { setMasterEditOpen(o); if (!o) setMasterEditProject(null); }}
            project={masterEditProject}
            onSaved={fetchProjects}
          />
        )}
      </main>
    </div>
  );
};

export default Projects;
