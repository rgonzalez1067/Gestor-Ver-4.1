import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
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
import { OperationalBoard } from '../components/projects/OperationalBoard';
import { ImplementerWorkloadHover } from '../components/projects/ImplementerWorkloadHover';
import {
  FolderKanban, Search, UserCheck, Clock, CheckCircle2, Pause,
  FileText, Filter, Paperclip, Eye, RefreshCw, X, UserPlus, AlertTriangle, Store, BarChart3, Ticket, Trash2, UserCog, Flag, Zap, Landmark, ChevronDown, CreditCard, ClipboardList, Pencil, Gauge, Calendar, CalendarClock, FileSpreadsheet, DollarSign, Snowflake
} from 'lucide-react';

const STATUS_CONFIG = {
  'Por asignar': { color: 'bg-amber-100 text-amber-800 border-amber-200', icon: Clock },
  'Asignado': { color: 'bg-blue-100 text-blue-800 border-blue-200', icon: UserCheck },
  'En Gestión': { color: 'bg-indigo-100 text-indigo-800 border-indigo-200', icon: UserCog },
  'Configurado en espera del Cliente': { color: 'bg-cyan-100 text-cyan-800 border-cyan-200', icon: Pause },
  'Congelado': { color: 'bg-blue-100 text-blue-800 border-blue-200', icon: Snowflake },
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
  { id: 'Congelado', label: 'Congelar Proyecto', icon: Snowflake, iconColor: 'text-blue-600', freezeOnly: true },
  { id: 'Configurado en espera del Cliente', label: 'Configurado en espera del Cliente', icon: Pause, iconColor: 'text-cyan-600' },
  { id: 'Suspendido', label: 'Suspendido', icon: Pause, iconColor: 'text-red-600' },
  { id: 'Implementado parcial', label: 'Implementado parcial', icon: CheckCircle2, iconColor: 'text-orange-600' },
  { id: 'Culminado', label: 'Culminado', icon: CheckCircle2, iconColor: 'text-emerald-600' },
  { id: 'Anulado', label: 'Anulado', icon: X, iconColor: 'text-slate-600' },
];

// Cuerpo del modal de cambio de estado con ESTADO LOCAL propio: al escribir la
// justificación NO se re-renderiza la grilla completa (evita el lag por carácter).
function StatusDialogBody({ project, loading, onCancel, onConfirm }) {
  const [form, setForm] = useState({ new_status: '', note: '', change_date: new Date().toISOString().slice(0, 10) });
  const [file, setFile] = useState(null);

  useEffect(() => {
    setForm({ new_status: '', note: '', change_date: new Date().toISOString().slice(0, 10) });
    setFile(null);
  }, [project?.project_id]);

  return (
    <div className="space-y-4">
      <div className="bg-slate-50 border rounded-lg p-3">
        <p className="font-semibold text-sm">{project.project_number}</p>
        <p className="text-xs text-slate-500">{project.client_name}</p>
        <div className="mt-2">
          <span className="text-[10px] text-slate-500 uppercase">Estado actual:</span>
          <span className={`ml-2 inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full border ${STATUS_CONFIG[project.status]?.color || ''}`}>
            {project.status}
          </span>
        </div>
      </div>

      {/* Status options */}
      <div>
        <Label className="text-sm">Nuevo Estado</Label>
        <div className="space-y-1.5 mt-1.5">
          {STATUS_TRANSITIONS.filter(t => {
            if (t.id === project.status) return false;
            if (t.freezeOnly) return project.status === 'En Gestión';
            if (t.reactivation) return HIDDEN_DEFAULT_STATES.includes(project.status) || project.status === 'Congelado';
            if (project.status === 'Congelado') return false;
            return true;
          }).map(t => {
            const TIcon = t.icon;
            const selected = form.new_status === t.id;
            const dynLabel = (t.reactivation && project.status === 'Congelado')
              ? 'Descongelar (volver a En Gestión)' : t.label;
            return (
              <button key={t.id} onClick={() => setForm(p => ({ ...p, new_status: t.id }))}
                className={`w-full flex items-center gap-3 p-3 rounded-lg border-2 text-left transition-all ${selected ? 'border-slate-800 bg-slate-50 shadow-sm' : 'border-slate-200 hover:border-slate-300'}`}
                data-testid={`status-option-${t.id.replace(/[\s\/]/g, '-').toLowerCase()}`}>
                <TIcon size={18} className={t.iconColor} />
                <span className="text-sm font-medium text-slate-800">{dynLabel}</span>
                {selected && <CheckCircle2 size={16} className="ml-auto text-slate-800" />}
              </button>
            );
          })}
        </div>
      </div>

      {/* Date + Comment (justificación obligatoria) */}
      {form.new_status && (
        <div className="space-y-3 pt-2 border-t border-slate-200 animate-in fade-in-0 slide-in-from-top-1">
          {TICKET_REMINDER_STATES.includes(form.new_status) && (
            <div className="flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 p-2.5 text-amber-800" data-testid="status-ticket-reminder">
              <AlertTriangle size={15} className="mt-0.5 shrink-0" />
              <span className="text-xs">Recuerde <strong>cerrar el Ticket</strong> en el portal al confirmar este estado.</span>
            </div>
          )}
          <div>
            <Label className="text-sm">Fecha del Cambio</Label>
            <Input type="date" value={form.change_date}
              onChange={e => setForm(p => ({ ...p, change_date: e.target.value }))}
              className="mt-1" data-testid="status-change-date" />
          </div>
          <div>
            <Label className="text-sm">Comentario de Justificación <span className="text-red-500">*</span></Label>
            <Textarea value={form.note}
              onChange={e => setForm(p => ({ ...p, note: e.target.value }))}
              placeholder="Motivo o detalle del cambio de estado (obligatorio)..."
              className="mt-1 min-h-[60px] text-sm" data-testid="status-change-comment" />
          </div>
          <div>
            <Label className="text-sm">Anexo (opcional)</Label>
            <Input type="file" onChange={e => setFile(e.target.files?.[0] || null)}
              className="mt-1 text-sm" data-testid="status-change-file" />
            {file && (
              <p className="mt-1 flex items-center gap-1 text-xs text-slate-500">
                <Paperclip size={11} />{file.name}
              </p>
            )}
          </div>
        </div>
      )}

      <div className="flex justify-end gap-3 pt-2 border-t">
        <Button variant="outline" onClick={onCancel}>Cancelar</Button>
        <Button onClick={() => onConfirm(form, file)}
          disabled={loading || !form.new_status || !form.note.trim()}
          className="bg-orange-600 hover:bg-orange-700 text-white"
          data-testid="status-change-confirm-btn">
          {loading ? 'Actualizando...' : 'Confirmar Cambio'}
        </Button>
      </div>
    </div>
  );
}

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

// Normaliza texto para búsqueda insensible a mayúsculas y acentos.
const norm = (s) => (s || '').toString().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');


// Opciones del filtro "Tipo de Proyecto" (label legible → valor canónico).
const PROJECT_TYPE_FILTERS = [
  { value: 'VPOS', label: 'VPOS' },
  { value: 'MPOS', label: 'MPOS' },
  { value: 'GATEWAY', label: 'Payment Gateway' },
  { value: 'LINK', label: 'Link de Pago (todas)' },
  { value: 'LINK:link_pago', label: '› Solo Link de Pago', sub: true },
  { value: 'LINK:tokenizador', label: '› Solo Tokenizador', sub: true },
  { value: 'LINK:ambos', label: '› Solo Link/Tokenizador', sub: true },
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
  // Equipo comercial del usuario según su departamento (para el indicador $ de Cobro Recurrente)
  const userSalesTeam = (() => {
    const dept = (currentUser?.departamento || '').toLowerCase();
    if (dept.includes('ventas corporativ')) return 'CORP';
    if (dept.includes('ventas pyme')) return 'PYME';
    return null;
  })();
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [slaConfig, setSlaConfig] = useState(null); // matriz de días por etapa
  const [clientMap, setClientMap] = useState({}); // client_id → {fantasy_name, legal_name}
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const searchBoxRef = useRef(null);
  const [statusFilter, setStatusFilter] = useState('active');
  const [typeFilter, setTypeFilter] = useState('all'); // 'all' | 'VPOS' | 'MPOS' | 'GATEWAY' | 'LINK'
  const [sponsorFilter, setSponsorFilter] = useState('all');
  const [sponsorPickerOpen, setSponsorPickerOpen] = useState(false);
  const [sponsorSearch, setSponsorSearch] = useState('');
  const [integratorFilter, setIntegratorFilter] = useState('all');
  const [cobroFilter, setCobroFilter] = useState('all'); // 'all' | 'cobrado' | 'pendiente'
  const [avanceFilter, setAvanceFilter] = useState('all'); // 'all' | 'al_dia' | 'medio' | 'critico'
  const [integratorPickerOpen, setIntegratorPickerOpen] = useState(false);
  const [integratorSearch, setIntegratorSearch] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

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
  const [statusLoading, setStatusLoading] = useState(false);

  // Edición Maestra (Super-Admin Override)
  const [masterEditOpen, setMasterEditOpen] = useState(false);
  const [masterEditProject, setMasterEditProject] = useState(null);
  const [fichaLoadingId, setFichaLoadingId] = useState(null);

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
        api.get('/projects/stats').catch(() => ({ data: {} })),
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
            economic_group: c.grupo_economico || c.economic_group || '',
            rif: c.rif || '',
          };
        }
      });
      setClientMap(map);
    } catch (err) { toast.error('Error cargando proyectos'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchProjects(); }, [fetchProjects]);

  // ==================== COBRO RECURRENTE ($) ====================
  const [cobroSavingId, setCobroSavingId] = useState(null);
  const canToggleCobro = (project) => {
    if (isAdmin) return true;
    const team = (project.client_segment || 'PYME').toUpperCase();
    return !!userSalesTeam && userSalesTeam === team;
  };
  const toggleCobroRecurrente = async (project) => {
    if (!canToggleCobro(project)) return;
    setCobroSavingId(project.project_id);
    const next = !project.cobro_recurrente_status;
    try {
      const res = await api.put(`/projects/${project.project_id}/cobro-recurrente`, { status: next });
      setProjects((prev) => prev.map((p) => p.project_id === project.project_id
        ? { ...p, cobro_recurrente_status: res.data.cobro_recurrente_status,
            cobro_recurrente_by_name: res.data.cobro_recurrente_by_name,
            cobro_recurrente_at: res.data.cobro_recurrente_at }
        : p));
      toast.success(next ? 'Cobro recurrente marcado como cobrado' : 'Cobro recurrente desmarcado');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'No se pudo actualizar el cobro recurrente');
    } finally { setCobroSavingId(null); }
  };

  // Cierra el typeahead de Cliente al hacer clic fuera del campo.
  useEffect(() => {
    const onClickOutside = (e) => {
      if (searchBoxRef.current && !searchBoxRef.current.contains(e.target)) setShowSuggestions(false);
    };
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, []);

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
    setStatusDialogOpen(true);
  };

  const handleStatusChange = async (form, file) => {
    if (!form.new_status) { toast.error('Seleccione un estado'); return; }
    if (!form.note.trim()) { toast.error('El comentario de justificación es obligatorio'); return; }
    setStatusLoading(true);
    try {
      const fd = new FormData();
      fd.append('new_status', form.new_status);
      fd.append('note', form.note);
      fd.append('change_date', form.change_date || '');
      if (file) fd.append('file', file);
      await api.put(`/projects/${statusProject.project_id}/status`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      toast.success(`Estado: ${form.new_status}`);
      if (TICKET_REMINDER_STATES.includes(form.new_status)) {
        showTicketReminderToast(form.new_status);
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

  // Acceso rápido a la Ficha Técnica desde la grilla: descarga el PDF con la
  // sesión activa y lo abre en una pestaña nueva (no se puede abrir por URL
  // directa porque el endpoint exige el token de autorización).
  const viewFichaTecnica = async (project) => {
    setFichaLoadingId(project.project_id);
    try {
      const res = await api.get(`/projects/${project.project_id}/ficha-tecnica`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      window.open(url, '_blank', 'noopener,noreferrer');
      setTimeout(() => window.URL.revokeObjectURL(url), 60000);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al abrir la Ficha Técnica');
    } finally {
      setFichaLoadingId(null);
    }
  };

  // Predicado de filtros que NO dependen del estado (búsqueda, tipo, patrocinador,
  // integrador, rango de fechas). Sirve de base tanto para las tarjetas de estado
  // como para el set final mostrado en la grilla.
  // === Nivel de AVANCE (criticidad temporal) por proyecto ===
  // Reutiliza los MISMOS umbrales del semáforo SLA por etapa (backend calcula
  // `business_days_in_state` con el Calendario Laboral).
  const _stageKeyOf = (p) => {
    if (!p.assigned_to_name) return 'por_asignar';
    if (!p.ticket_number) return 'asignado';
    return 'en_gestion';
  };
  const _avanceLevel = (p) => {
    // Estados terminales/cerrados no tienen criticidad temporal pendiente: se
    // contabilizan como "Al día" (evita mostrar 'Crítico' en proyectos cerrados).
    const FINISHED = ['Culminado', 'Implementado parcial', 'Anulado', 'Cancelado', 'Finalizado'];
    if (FINISHED.includes(p.status)) return 'al_dia';
    const c = (slaConfig && slaConfig[_stageKeyOf(p)]) || {};
    const w = Number(c.warning_days ?? 2);
    const d = Number(c.delay_days ?? 4);
    const days = Number(p.business_days_in_state ?? 0);
    if (days >= d) return 'critico';
    if (days >= w) return 'medio';
    return 'al_dia';
  };

  const matchesNonStatus = (p) => {
    const sponsorLabel = getPatrocinadorLabel(p);
    // Filtro "Cliente": busca por Nº proyecto/ticket, Nombre de Fantasía, RIF,
    // Nombre Jurídico (Razón Social) y Grupo Económico (insensible a acentos).
    const fantasy = clientMap[p.client_id]?.fantasy_name || p.fantasy_name || '';
    const q = norm(searchTerm);
    const matchSearch = !searchTerm || [
      p.project_number, p.ticket_number, fantasy, p.client_rif,
      p.client_legal_name, p.client_economic_group,
      p.assigned_to_name, p.created_by_name, p.integrator_name, sponsorLabel,
    ].some(v => norm(v).includes(q));
    const matchSponsor = sponsorFilter === 'all'
      ? true
      : sponsorFilter === '__none__'
        ? !sponsorLabel
        : sponsorLabel === sponsorFilter;
    const matchType = typeFilter === 'all'
      ? true
      : typeFilter.startsWith('LINK:')
        ? (normalizeProjectType(p.quote_type) === 'LINK'
           && String(p.link_pago_variant || 'link_pago').toLowerCase() === typeFilter.split(':')[1])
        : normalizeProjectType(p.quote_type) === typeFilter;
    const matchIntegrator = integratorFilter === 'all'
      ? true
      : integratorFilter === '__none__'
        ? !(p.integrator_name || '').trim()
        : p.integrator_name === integratorFilter;
    const matchDate = (() => {
      if (!dateFrom && !dateTo) return true;
      const raw = p.sent_to_implementation_at || p.created_at || '';
      const d = raw ? String(raw).slice(0, 10) : '';
      if (!d) return false;
      if (dateFrom && d < dateFrom) return false;
      if (dateTo && d > dateTo) return false;
      return true;
    })();
    const matchCobro = cobroFilter === 'all'
      ? true
      : cobroFilter === 'cobrado'
        ? !!p.cobro_recurrente_status
        : !p.cobro_recurrente_status;
    const matchAvance = avanceFilter === 'all' ? true
      : avanceFilter === 'congelado' ? p.status === 'Congelado'
      : _avanceLevel(p) === avanceFilter;
    return matchSearch && matchSponsor && matchType && matchIntegrator && matchDate && matchCobro && matchAvance;
  };

  const matchesStatus = (p) => statusFilter === 'all'
    ? true
    : statusFilter === 'active'
      ? !HIDDEN_DEFAULT_STATES.includes(p.status)
      : statusFilter === 'suspended'
        ? p.status === 'Suspendido'
        : statusFilter === 'in_progress'
          ? ['Asignado', 'En Gestión', 'Implementado parcial'].includes(p.status)
          : p.status === statusFilter;

  // Typeahead de "Cliente": sugiere clientes (con proyectos) por RIF/Razón
  // Social/Fantasía y Grupos Económicos. Insensible a acentos y mayúsculas.
  const clientsWithProjects = useMemo(() => {
    const m = new Map();
    projects.forEach((p) => {
      if (p.client_id && !m.has(p.client_id)) {
        m.set(p.client_id, {
          client_id: p.client_id,
          rif: p.client_rif || clientMap[p.client_id]?.rif || '',
          legal_name: p.client_legal_name || clientMap[p.client_id]?.legal_name || p.client_name || '',
          fantasy_name: clientMap[p.client_id]?.fantasy_name || p.fantasy_name || '',
          economic_group: p.client_economic_group || clientMap[p.client_id]?.economic_group || '',
        });
      }
    });
    return [...m.values()];
  }, [projects, clientMap]);

  const clientSuggestions = useMemo(() => {
    const q = norm(searchTerm);
    if (q.length < 3) return { clients: [], groups: [] };
    const clients = clientsWithProjects.filter((c) =>
      norm(c.rif).includes(q) || norm(c.legal_name).includes(q) ||
      norm(c.fantasy_name).includes(q) || norm(c.economic_group).includes(q)
    ).slice(0, 8);
    const gmap = new Map();
    clientsWithProjects.forEach((c) => {
      const g = (c.economic_group || '').trim();
      if (g && norm(g).includes(q)) gmap.set(norm(g), g);
    });
    return { clients, groups: [...gmap.values()].slice(0, 5) };
  }, [searchTerm, clientsWithProjects]);

  const pickSuggestion = (term) => { setSearchTerm(term); setShowSuggestions(false); };


  // Base: todos los filtros menos el estado. Final: + filtro de estado (lo que se muestra).
  const baseFiltered = projects.filter(matchesNonStatus);
  const filtered = baseFiltered.filter(matchesStatus);

  // KPIs dinámicos (Regla de Oro): "Total" refleja el set filtrado completo (incluye
  // estado); las tarjetas de estado cuentan su estado dentro de los demás filtros.
  const countStatus = (st) => baseFiltered.filter(p => p.status === st).length;
  const kpi = {
    total: filtered.length,
    por_asignar: countStatus('Por asignar'),
    asignado: countStatus('Asignado'),
    en_gestion: countStatus('En Gestión'),
    congelado: countStatus('Congelado'),
    suspendido: countStatus('Suspendido'),
    parcial: countStatus('Implementado parcial'),
    culminado: countStatus('Culminado'),
  };

  // === Desglose de AVANCE (criticidad temporal) para tooltips de KPIs ===
  // Reutiliza `_avanceLevel`; cada tarjeta se desglosa sobre su MISMO subconjunto,
  // por lo que la suma de los 3 niveles == total.
  const avanceBreakdown = (subset) => {
    const bd = { al_dia: 0, medio: 0, critico: 0 };
    for (const p of (subset || [])) bd[_avanceLevel(p)]++;
    return bd;
  };

  // Indicador de Avance Global: promedio del % de avance (rollup_progress.global_progress)
  // sobre el MISMO set filtrado que la grilla. Proyectos sin avance cuentan como 0%.
  const globalProgress = filtered.length
    ? Math.round(filtered.reduce((acc, p) => acc + (p.rollup_progress?.global_progress || 0), 0) / filtered.length)
    : 0;

  // Mini Tablero de Avance Operativo: agrega las 4 métricas (físico + PVV).
  // Por defecto (statusFilter 'active' o 'all') suma sobre TODOS los estados del
  // set filtrado por fecha/tipo/integrador/cliente → coincide con el consolidado
  // del Reporte de Carga. Reacciona a un estado SOLO si el usuario lo selecciona
  // explícitamente (click en una tarjeta KPI de estado específico).
  const boardSource = (statusFilter === 'active' || statusFilter === 'all') ? baseFiltered : filtered;
  const boardMetrics = boardSource.reduce((acc, p) => {
    const om = p.operational_metrics || {};
    acc.cajasAsig += om.cajas_asignadas || 0;
    acc.cajasConf += om.cajas_configuradas || 0;
    acc.pvvAsig += om.pvv_asignados || 0;
    acc.pvvConf += om.pvv_configurados || 0;
    return acc;
  }, { cajasAsig: 0, cajasConf: 0, pvvAsig: 0, pvvConf: 0 });

  // === Alertas Críticas de Compromisos (Mis Alertas del Implementador) ===
  // Fuente: implementer_alerts no completados. Toast y marcas solo para el
  // Implementador en sesión, sobre SUS proyectos asignados (decisión 1b/3b).
  const isImplementer = (currentUser?.cargo || '').toLowerCase() === 'implementador';
  const formatDMY = (s) => {
    if (!s) return '';
    const m = String(s).slice(0, 10).match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (m) return `${m[3]}/${m[2]}/${m[1]}`;
    const d = new Date(s);
    return isNaN(d.getTime()) ? String(s) : `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`;
  };
  const activeAlertsOf = (p) => isImplementer
    ? (p.implementer_alerts || []).filter(a => !a.completed)
    : [];
  const hasCommitmentAlerts = isImplementer && projects.some(
    p => p.assigned_to_user_id === currentUser?.user_id && (p.implementer_alerts || []).some(a => !a.completed)
  );

  // Lista de patrocinadores distintos (para el dropdown del filtro).
  const sponsorOptions = Array.from(
    new Set(projects.map(getPatrocinadorLabel).filter(Boolean))
  ).sort((a, b) => a.localeCompare(b));
  const sponsorOptionsFiltered = sponsorOptions.filter(
    s => !sponsorSearch || s.toLowerCase().includes(sponsorSearch.toLowerCase())
  );

  // Lista de integradores distintos presentes en los proyectos visibles.
  const integratorOptions = Array.from(
    new Set(projects.map(p => (p.integrator_name || '').trim()).filter(Boolean))
  ).sort((a, b) => a.localeCompare(b, 'es', { sensitivity: 'base' }));
  const integratorOptionsFiltered = integratorOptions.filter(
    s => !integratorSearch || s.toLowerCase().includes(integratorSearch.toLowerCase())
  );

  const hasActiveFilters = searchTerm || statusFilter !== 'active' || typeFilter !== 'all'
    || sponsorFilter !== 'all' || integratorFilter !== 'all' || cobroFilter !== 'all' || avanceFilter !== 'all' || dateFrom || dateTo;
  const resetFilters = () => {
    setSearchTerm(''); setStatusFilter('active'); setTypeFilter('all');
    setSponsorFilter('all'); setIntegratorFilter('all'); setCobroFilter('all'); setAvanceFilter('all'); setDateFrom(''); setDateTo('');
  };

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
              {hasCommitmentAlerts && (
                <div
                  className="mt-3 inline-flex items-center gap-2 rounded-md px-4 py-2 shadow-md"
                  style={{ backgroundColor: '#D32F2F' }}
                  data-testid="commitments-alert-toast"
                  role="alert"
                >
                  <AlertTriangle size={18} className="text-white shrink-0" />
                  <span className="text-white text-sm font-semibold">
                    Atención: Tiene alertas de compromisos programadas/vencidas en sus proyectos.
                  </span>
                </div>
              )}
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

          {/* Mini Tablero de Avance Operativo (físico + PVV) — reactivo al filtro */}
          <OperationalBoard metrics={boardMetrics} count={boardSource.length} />

          {/* Stats Cards */}
          <div className="grid grid-cols-4 lg:grid-cols-8 gap-2 mb-4">
            {[
              { label: 'Total', value: kpi.total, cls: 'bg-slate-50 border-slate-200 text-slate-700', filter: 'all', subset: filtered },
              { label: 'Por Asignar', value: kpi.por_asignar, cls: 'bg-amber-50 border-amber-200 text-amber-700', filter: 'Por asignar', subset: baseFiltered.filter(p => p.status === 'Por asignar') },
              { label: 'Asignado', value: kpi.asignado, cls: 'bg-sky-50 border-sky-200 text-sky-700', filter: 'Asignado', subset: baseFiltered.filter(p => p.status === 'Asignado') },
              { label: 'En Gestión', value: kpi.en_gestion, cls: 'bg-indigo-50 border-indigo-200 text-indigo-700', filter: 'En Gestión', subset: baseFiltered.filter(p => p.status === 'En Gestión') },
              { label: 'Congelados', value: kpi.congelado, cls: 'bg-blue-50 border-blue-200 text-blue-700', filter: 'Congelado', subset: baseFiltered.filter(p => p.status === 'Congelado'), icon: Snowflake },
              { label: 'Suspendido', value: kpi.suspendido, cls: 'bg-red-50 border-red-200 text-red-700', filter: 'Suspendido', subset: baseFiltered.filter(p => p.status === 'Suspendido') },
              { label: 'Implementado Parcial', value: kpi.parcial, cls: 'bg-violet-50 border-violet-200 text-violet-700', filter: 'Implementado parcial', subset: baseFiltered.filter(p => p.status === 'Implementado parcial') },
              { label: 'Culminado', value: kpi.culminado, cls: 'bg-emerald-50 border-emerald-200 text-emerald-700', filter: 'Culminado', subset: baseFiltered.filter(p => p.status === 'Culminado') },
            ].map(s => {
              const key = s.label.toLowerCase().replace(/\s/g, '-');
              const bd = avanceBreakdown(s.subset);
              return (
              <TooltipProvider key={s.label} delayDuration={200}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div
                      className={`p-3 rounded-lg border cursor-pointer transition-all ${s.cls} ${statusFilter === s.filter ? 'ring-2 ring-offset-1 ring-current' : 'hover:shadow-sm'}`}
                      onClick={() => setStatusFilter(s.filter)}
                      data-testid={`stat-${key}`}>
                      <p className="text-xl font-bold leading-none" data-testid={`stat-value-${key}`}>{s.value}</p>
                      <p className="text-xs leading-tight mt-1.5">{s.label}</p>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="bg-slate-900/95 text-white border border-slate-700 shadow-xl px-3 py-2 rounded-lg" data-testid={`kpi-tooltip-${key}`}>
                    <p className="text-[11px] font-semibold mb-1.5 text-slate-100 uppercase tracking-wide">Resumen de Avance</p>
                    <div className="space-y-1 text-xs min-w-[160px]">
                      <div className="flex items-center justify-between gap-4">
                        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-emerald-400 shrink-0" />Al día</span>
                        <span className="font-bold tabular-nums" data-testid={`kpi-tt-aldia-${key}`}>{bd.al_dia}</span>
                      </div>
                      <div className="flex items-center justify-between gap-4">
                        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-amber-400 shrink-0" />Retraso Medio</span>
                        <span className="font-bold tabular-nums" data-testid={`kpi-tt-medio-${key}`}>{bd.medio}</span>
                      </div>
                      <div className="flex items-center justify-between gap-4">
                        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-red-500 shrink-0" />Retraso Crítico</span>
                        <span className="font-bold tabular-nums" data-testid={`kpi-tt-critico-${key}`}>{bd.critico}</span>
                      </div>
                      <div className="flex items-center justify-between gap-4 border-t border-slate-700 mt-1 pt-1 text-slate-300">
                        <span>Total</span>
                        <span className="font-bold tabular-nums" data-testid={`kpi-tt-total-${key}`}>{bd.al_dia + bd.medio + bd.critico}</span>
                      </div>
                    </div>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              );
            })}
          </div>

          {/* Indicador de Avance Global (reactivo al filtro activo) */}
          <div className="mb-6 p-4 rounded-lg border border-violet-200 bg-gradient-to-r from-violet-50 to-indigo-50" data-testid="global-progress-widget">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Gauge size={16} className="text-violet-600" />
                <span className="text-sm font-semibold text-slate-700">Avance Global</span>
                <span className="text-xs text-slate-500">
                  · {filtered.length} proyecto{filtered.length === 1 ? '' : 's'}
                  {(currentUser?.cargo || '').toLowerCase() === 'implementador' ? ' asignado' + (filtered.length === 1 ? '' : 's') : ' en vista'}
                </span>
              </div>
              <span className="text-2xl font-bold text-violet-700 tabular-nums" data-testid="global-progress-value">{globalProgress}%</span>
            </div>
            <div className="h-3 w-full rounded-full bg-violet-100 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-violet-500 to-indigo-500 transition-all duration-500"
                style={{ width: `${globalProgress}%` }}
                data-testid="global-progress-bar"
              />
            </div>
          </div>

          {/* Filters */}
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <div className="relative flex-1 min-w-[240px] max-w-sm" ref={searchBoxRef}>
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 z-10" />
              <Input placeholder="Buscar por cliente, RIF, Razón Social o Grupo Económico…"
                value={searchTerm}
                onChange={e => { setSearchTerm(e.target.value); setShowSuggestions(true); }}
                onFocus={() => setShowSuggestions(true)}
                className="pl-9" data-testid="project-search" autoComplete="off" />
              {searchTerm && (
                <button type="button" onClick={() => { setSearchTerm(''); setShowSuggestions(false); }}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-300 hover:text-slate-500 z-10"
                  data-testid="project-search-clear"><X size={14} /></button>
              )}
              {showSuggestions && norm(searchTerm).length >= 3 && (
                <div className="absolute z-30 mt-1 w-full bg-white border border-slate-200 rounded-md shadow-lg max-h-72 overflow-y-auto"
                  data-testid="project-search-suggestions">
                  {clientSuggestions.groups.map((g) => (
                    <button key={`g-${g}`} type="button" onClick={() => pickSuggestion(g)}
                      className="w-full text-left px-3 py-2 text-xs hover:bg-indigo-50 border-b border-slate-100 flex items-center gap-2"
                      data-testid={`project-search-group-${g}`}>
                      <Landmark size={13} className="text-indigo-500 shrink-0" />
                      <span className="font-medium text-indigo-700">Grupo: {g}</span>
                    </button>
                  ))}
                  {clientSuggestions.clients.map((c) => (
                    <button key={c.client_id} type="button" onClick={() => pickSuggestion(c.rif || c.legal_name)}
                      className="w-full text-left px-3 py-2 text-xs hover:bg-blue-50 border-b border-slate-100 last:border-0"
                      data-testid={`project-search-client-${c.client_id}`}>
                      <span className="font-mono text-slate-500">{c.rif || 'S/RIF'}</span>
                      <span className="text-slate-700"> — {c.legal_name || c.fantasy_name}</span>
                      {c.economic_group && <span className="text-slate-400"> (Grupo: {c.economic_group})</span>}
                    </button>
                  ))}
                  {clientSuggestions.clients.length === 0 && clientSuggestions.groups.length === 0 && (
                    <div className="px-3 py-3 text-xs text-slate-400 text-center" data-testid="project-search-no-results">
                      No se encontraron coincidencias para la búsqueda
                    </div>
                  )}
                </div>
              )}
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
                <SelectTrigger className={`w-[210px] ${typeFilter !== 'all' ? 'border-indigo-400 text-indigo-700' : ''}`} data-testid="project-type-filter">
                  <SelectValue placeholder="Todos los tipos" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all" data-testid="project-type-option-all">Todos los tipos</SelectItem>
                  {PROJECT_TYPE_FILTERS.map(t => (
                    <SelectItem key={t.value} value={t.value} data-testid={`project-type-option-${t.value.toLowerCase()}`} className={t.sub ? 'pl-6 text-slate-500' : ''}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {/* Filtro por Cobro Recurrente ($) */}
            <div className="flex items-center gap-2">
              <DollarSign size={16} className="text-slate-400" />
              <Select value={cobroFilter} onValueChange={setCobroFilter}>
                <SelectTrigger className={`w-[190px] ${cobroFilter !== 'all' ? 'border-emerald-500 text-emerald-700' : ''}`} data-testid="project-cobro-filter">
                  <SelectValue placeholder="Cobro recurrente" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all" data-testid="project-cobro-option-all">Cobro: Todos</SelectItem>
                  <SelectItem value="cobrado" data-testid="project-cobro-option-cobrado">Cobro: Cobrado</SelectItem>
                  <SelectItem value="pendiente" data-testid="project-cobro-option-pendiente">Cobro: Pendiente</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {/* Filtro por Avance (criticidad temporal / semáforo SLA) */}
            <div className="flex items-center gap-2">
              <Gauge size={16} className="text-slate-400" />
              <Select value={avanceFilter} onValueChange={setAvanceFilter}>
                <SelectTrigger className={`w-[200px] ${avanceFilter !== 'all' ? 'border-violet-500 text-violet-700' : ''}`} data-testid="project-avance-filter">
                  <SelectValue placeholder="Avance: Todos" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all" data-testid="project-avance-option-all">Avance: Todos</SelectItem>
                  <SelectItem value="al_dia" data-testid="project-avance-option-al_dia">
                    <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shrink-0" />Al día</span>
                  </SelectItem>
                  <SelectItem value="medio" data-testid="project-avance-option-medio">
                    <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-amber-400 shrink-0" />Retraso Medio</span>
                  </SelectItem>
                  <SelectItem value="critico" data-testid="project-avance-option-critico">
                    <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-red-500 shrink-0" />Retraso Crítico</span>
                  </SelectItem>
                  <SelectItem value="congelado" data-testid="project-avance-option-congelado">
                    <span className="flex items-center gap-2"><Snowflake size={12} className="text-blue-500 shrink-0" />Congelado</span>
                  </SelectItem>
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
            {/* Filtro por Integrador (dropdown + búsqueda interna) */}
            <div className="flex items-center gap-2">
              <UserCog size={16} className="text-slate-400" />
              <Popover open={integratorPickerOpen} onOpenChange={(o) => { setIntegratorPickerOpen(o); if (!o) setIntegratorSearch(''); }}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className={`w-[230px] justify-between font-normal ${integratorFilter !== 'all' ? 'border-indigo-400 text-indigo-700' : 'text-slate-600'}`}
                    data-testid="project-integrator-filter"
                  >
                    <span className="truncate">
                      {integratorFilter === 'all'
                        ? 'Todos los integradores'
                        : integratorFilter === '__none__'
                          ? 'Sin integrador'
                          : integratorFilter}
                    </span>
                    <ChevronDown size={15} className="shrink-0 opacity-60" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[280px] p-0" align="start" data-testid="project-integrator-popover">
                  <div className="p-2 border-b">
                    <Input
                      placeholder="Buscar integrador…"
                      value={integratorSearch}
                      onChange={(e) => setIntegratorSearch(e.target.value)}
                      className="h-8 text-sm"
                      data-testid="project-integrator-search"
                    />
                  </div>
                  <div className="max-h-[260px] overflow-y-auto py-1">
                    <button
                      type="button"
                      className={`w-full text-left px-3 py-1.5 text-sm hover:bg-slate-100 ${integratorFilter === 'all' ? 'font-semibold text-indigo-700' : 'text-slate-700'}`}
                      onClick={() => { setIntegratorFilter('all'); setIntegratorPickerOpen(false); setIntegratorSearch(''); }}
                      data-testid="project-integrator-option-all"
                    >
                      Todos los integradores
                    </button>
                    <button
                      type="button"
                      className={`w-full text-left px-3 py-1.5 text-sm hover:bg-slate-100 ${integratorFilter === '__none__' ? 'font-semibold text-indigo-700' : 'text-slate-500'}`}
                      onClick={() => { setIntegratorFilter('__none__'); setIntegratorPickerOpen(false); setIntegratorSearch(''); }}
                      data-testid="project-integrator-option-none"
                    >
                      Sin integrador
                    </button>
                    {integratorOptionsFiltered.length === 0 && (
                      <p className="px-3 py-2 text-xs text-slate-400">Sin coincidencias</p>
                    )}
                    {integratorOptionsFiltered.map((s) => (
                      <button
                        key={s}
                        type="button"
                        className={`w-full text-left px-3 py-1.5 text-sm hover:bg-slate-100 ${integratorFilter === s ? 'font-semibold text-indigo-700' : 'text-slate-700'}`}
                        onClick={() => { setIntegratorFilter(s); setIntegratorPickerOpen(false); setIntegratorSearch(''); }}
                        data-testid={`project-integrator-option-${s}`}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </PopoverContent>
              </Popover>
            </div>
            {/* Filtro por rango de fechas (fecha de envío a implementación) */}
            <div className="flex items-center gap-1.5">
              <Calendar size={16} className="text-slate-400" />
              <Input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className={`w-[150px] h-9 text-sm ${dateFrom ? 'border-indigo-400 text-indigo-700' : ''}`}
                data-testid="project-date-from"
                title="Desde (fecha de envío a implementación)"
              />
              <span className="text-slate-400 text-sm">–</span>
              <Input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className={`w-[150px] h-9 text-sm ${dateTo ? 'border-indigo-400 text-indigo-700' : ''}`}
                data-testid="project-date-to"
                title="Hasta (fecha de envío a implementación)"
              />
            </div>
            {hasActiveFilters && (
              <Button
                variant="ghost"
                size="sm"
                onClick={resetFilters}
                className="text-slate-500 hover:text-slate-800"
                data-testid="project-clear-filters"
                title="Limpiar todos los filtros"
              >
                <X size={14} className="mr-1" />
                Limpiar
              </Button>
            )}
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
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Envío a Imple / Último Contacto</th>
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
                    const isFrozen = project.status === 'Congelado';
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
                    // Días HÁBILES en el estado actual, calculados por el backend
                    // (excluye fines de semana y festivos del Calendario Laboral).
                    const _bizDays = Number(project.business_days_in_state ?? 0);

                    if (isFrozen) {
                      slaColor = 'bg-blue-400';
                      slaLabel = 'Congelado · SLA en pausa';
                    } else if (isSuspended) {
                      slaColor = 'bg-slate-400';
                      slaLabel = 'Detenido';
                    } else if (isFinished) {
                      slaColor = 'bg-blue-500';
                      slaLabel = project.status;
                    } else if (!project.assigned_to_name) {
                      // Etapa A: Sin asignar
                      slaDays = _bizDays;
                      slaLabel = `Sin asignar · ${slaDays}d háb.`;
                      slaColor = _color(slaDays, 'por_asignar');
                    } else if (!project.ticket_number) {
                      // Etapa B: Asignado sin desbloquear
                      slaDays = _bizDays;
                      slaLabel = `Pendiente desbloqueo · ${slaDays}d háb.`;
                      slaColor = _color(slaDays, 'asignado');
                    } else {
                      // Etapa C: Desbloqueado / En Gestión
                      slaDays = _bizDays;
                      slaLabel = `En gestión · ${slaDays}d háb.`;
                      slaColor = _color(slaDays, 'en_gestion');
                    }
                    
                    return (
                      <React.Fragment key={project.project_id}>
                      <tr className={`hover:bg-slate-50 transition-colors ${project.direct_project ? 'bg-amber-50/70 hover:bg-amber-100/70' : ''}`}
                        data-testid={`project-row-${project.project_id}`}
                        data-direct-project={project.direct_project ? 'true' : 'false'}>
                        <td className="px-4 py-3">
                          {/* Marca roja de Compromiso (implementer_alerts activos) */}
                          {(() => {
                            const activeAlerts = activeAlertsOf(project);
                            if (activeAlerts.length === 0) return null;
                            return (
                              <TooltipProvider delayDuration={0}>
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <span
                                      className="inline-flex items-center gap-1 mb-1.5 px-1.5 py-0.5 rounded bg-red-600 text-white text-[10px] font-bold cursor-help animate-pulse"
                                      data-testid={`project-commitment-badge-${project.project_id}`}
                                    >
                                      <AlertTriangle size={11} />
                                      Compromiso{activeAlerts.length > 1 ? ` (${activeAlerts.length})` : ''}
                                    </span>
                                  </TooltipTrigger>
                                  <TooltipContent side="right" className="bg-red-700 text-white border-red-800 max-w-[320px]" data-testid={`project-commitment-tooltip-${project.project_id}`}>
                                    {activeAlerts.map((a) => {
                                      const overdue = a.deadline && new Date(a.deadline) < new Date();
                                      return (
                                        <div key={a.alert_id} className="mb-2 last:mb-0">
                                          <p className="text-[11px] font-semibold text-red-200">Compromiso</p>
                                          <p className="text-xs">{a.message}</p>
                                          {a.deadline && (
                                            <p className="text-[11px] mt-0.5">
                                              <span className="text-red-200">Fecha Límite: </span>
                                              <span className={overdue ? 'font-bold text-yellow-300' : 'font-medium'}>
                                                {formatDMY(a.deadline)}{overdue ? ' · Vencido' : ''}
                                              </span>
                                            </p>
                                          )}
                                        </div>
                                      );
                                    })}
                                  </TooltipContent>
                                </Tooltip>
                              </TooltipProvider>
                            );
                          })()}
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
                          {project.project_number && (
                            <p className="text-xs font-mono font-semibold text-slate-600 flex items-center gap-1 mt-0.5" data-testid={`project-number-${project.project_id}`} title="Nro de Proyecto">
                              <FolderKanban size={11} className="text-slate-400" />{project.project_number}
                            </p>
                          )}
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
                            <ProjectTypeBadge quoteType={project.quote_type} variant={project.link_pago_variant} />
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
                          <p className="text-slate-700" data-testid={`project-sent-impl-date-${project.project_id}`}>
                            {project.sent_to_implementation_at
                              ? new Date(project.sent_to_implementation_at).toLocaleDateString('es-VE')
                              : <span className="text-slate-400 italic">—</span>}
                          </p>
                          <p className="text-xs italic text-slate-400 mt-0.5" data-testid={`project-last-contact-date-${project.project_id}`}>
                            {project.last_contact_at
                              ? new Date(project.last_contact_at).toLocaleDateString('es-VE')
                              : '--/--/----'}
                          </p>
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-600">
                          {project.assigned_to_name ? (
                            <ImplementerWorkloadHover
                              userId={project.assigned_to_user_id}
                              name={project.assigned_to_name}
                              assignedAt={project.assigned_at}
                              lastFollowupAt={project.last_followup_at}
                              projectId={project.project_id}
                            />
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
                            {/* Cobro Recurrente ($) — toggle exclusivo Ventas del mismo equipo (o Admin) */}
                            {(() => {
                              const on = !!project.cobro_recurrente_status;
                              const allowed = canToggleCobro(project);
                              const saving = cobroSavingId === project.project_id;
                              const tip = !allowed
                                ? 'Acción exclusiva para el equipo comercial asignado al proyecto'
                                : (on
                                    ? `Cobro recurrente COBRADO${project.cobro_recurrente_by_name ? ' · ' + project.cobro_recurrente_by_name : ''} (clic para desmarcar)`
                                    : 'Marcar cobro recurrente como cobrado');
                              return (
                                <Button size="sm" variant="outline"
                                  onClick={() => allowed && !saving && toggleCobroRecurrente(project)}
                                  disabled={!allowed || saving}
                                  title={tip}
                                  className={`h-8 px-2 ${on
                                    ? 'text-white bg-emerald-600 border-emerald-600 hover:bg-emerald-700'
                                    : 'text-white bg-rose-600 border-rose-600 hover:bg-rose-700'} ${!allowed ? 'opacity-60 cursor-not-allowed' : ''}`}
                                  data-testid={`cobro-recurrente-btn-${project.project_id}`}
                                  data-cobro-status={on ? 'on' : 'off'}
                                  data-cobro-allowed={allowed ? 'true' : 'false'}>
                                  <DollarSign size={14} />
                                </Button>
                              );
                            })()}
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
                            {/* Acceso rápido a Ficha Técnica — abre el PDF en pestaña nueva */}
                            <Button
                              size="sm" variant="outline"
                              title="Ver Ficha Técnica"
                              onClick={() => viewFichaTecnica(project)}
                              disabled={fichaLoadingId === project.project_id}
                              className="h-8 px-2 text-cyan-700 hover:bg-cyan-50 border-cyan-200"
                              data-testid={`ficha-tecnica-btn-${project.project_id}`}>
                              {fichaLoadingId === project.project_id
                                ? <Clock size={14} className="animate-spin" />
                                : <FileSpreadsheet size={14} />}
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
                          {/* Aviso de cuenta regresiva de entrada en producción
                              (solo cuando faltan <= 5 días hábiles). Fondo ámbar,
                              nunca rojo (reservado a alertas de compromisos). */}
                          {(() => {
                            const dl = project.production_days_left;
                            if (dl === null || dl === undefined || dl > 5) return null;
                            let msg;
                            if (dl < 0) msg = 'La fecha estimada de entrada en producción del cliente ya transcurrió.';
                            else if (dl === 0) msg = 'Hoy es la fecha estimada de entrada en producción.';
                            else msg = `Quedan ${dl} día${dl === 1 ? '' : 's'} para la entrada en producción prevista por el cliente.`;
                            return (
                              <div
                                className="mb-2 flex items-center gap-2 px-3 py-2 rounded-md bg-orange-400 border-2 border-orange-500 shadow-sm"
                                data-testid={`production-countdown-${project.project_id}`}
                                data-days-left={dl}
                              >
                                <CalendarClock size={17} className="text-black shrink-0" />
                                <span className="text-sm font-extrabold text-black tracking-tight">{msg}</span>
                              </div>
                            );
                          })()}
                          {project.status === 'Congelado' && (() => {
                            const fa = project.frozen_at ? new Date(project.frozen_at) : null;
                            const dias = fa ? Math.max(0, Math.floor((Date.now() - fa.getTime()) / 86400000)) : 0;
                            return (
                              <div
                                className="mb-2 flex items-center gap-2 px-3 py-1.5 rounded-md bg-blue-50 border border-blue-200"
                                data-testid={`frozen-indicator-${project.project_id}`}
                                data-frozen-days={dias}
                                title={project.freeze_reason ? `Motivo: ${project.freeze_reason}` : 'Proyecto congelado'}
                              >
                                <Snowflake size={15} className="text-blue-600 shrink-0" />
                                <span className="text-xs font-bold text-blue-700">Congelado · {dias} día{dias === 1 ? '' : 's'}</span>
                              </div>
                            );
                          })()}
                          <div className="flex items-center gap-3" title={`${slaLabel} — Avance: ${pct}%`}>
                            <div className="flex-1 bg-slate-100 rounded-full h-3 overflow-hidden">
                              <div className={`h-full rounded-full transition-all duration-500 ${(isSuspended || isFrozen) ? 'bg-slate-400 bg-[length:20px_20px] bg-[linear-gradient(45deg,rgba(255,255,255,.15)_25%,transparent_25%,transparent_50%,rgba(255,255,255,.15)_50%,rgba(255,255,255,.15)_75%,transparent_75%,transparent)]' : slaColor}`} style={{ width: `${Math.max(Math.min(pct, 100), 5)}%` }} />
                            </div>
                            <span className={`text-xs font-bold min-w-[36px] text-right ${pct >= 100 ? 'text-emerald-600' : 'text-slate-600'}`}>{pct}%</span>
                            <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full whitespace-nowrap ${
                              isFrozen ? 'bg-blue-50 text-blue-700' :
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
          <DialogContent className="max-w-md max-h-[90vh] overflow-y-auto" data-testid="status-change-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <RefreshCw size={20} className="text-orange-500" />
                Cambiar Estado del Proyecto
              </DialogTitle>
            </DialogHeader>
            {statusProject && (
              <StatusDialogBody
                project={statusProject}
                loading={statusLoading}
                onCancel={() => setStatusDialogOpen(false)}
                onConfirm={handleStatusChange}
              />
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
