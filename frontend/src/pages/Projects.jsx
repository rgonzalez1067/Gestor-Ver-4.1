import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import api from '../utils/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../components/ui/select';
import { toast } from 'sonner';
import {
  FolderKanban, Search, UserCheck, Clock, CheckCircle2, Pause,
  FileText, Filter, Paperclip, Eye, RefreshCw, X, UserPlus, AlertTriangle, Store
} from 'lucide-react';

const STATUS_CONFIG = {
  'Pendiente por Asignar': { color: 'bg-amber-100 text-amber-800 border-amber-200', icon: Clock },
  'Asignado / En Proceso': { color: 'bg-blue-100 text-blue-800 border-blue-200', icon: UserCheck },
  'Detenido por Cliente/Banco': { color: 'bg-red-100 text-red-800 border-red-200', icon: Pause },
  'Finalizado / Producción': { color: 'bg-emerald-100 text-emerald-800 border-emerald-200', icon: CheckCircle2 },
};

const STATUS_TRANSITIONS = [
  { id: 'Asignado / En Proceso', label: 'Asignado / En Proceso', icon: UserCheck, iconColor: 'text-blue-600' },
  { id: 'Detenido por Cliente/Banco', label: 'Detenido por Cliente/Banco', icon: Pause, iconColor: 'text-red-600' },
  { id: 'Finalizado / Producción', label: 'Finalizado / Producción', icon: CheckCircle2, iconColor: 'text-emerald-600' },
];

const PRIORITY_OPTIONS = ['Alta', 'Media', 'Normal'];
const PRIORITY_COLORS = { 'Alta': 'text-red-600 font-semibold', 'Media': 'text-orange-600', 'Normal': 'text-blue-600' };

const Projects = () => {
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  // Assign/Reassign dialog
  const [assignDialogOpen, setAssignDialogOpen] = useState(false);
  const [assignProject, setAssignProject] = useState(null);
  const [implementers, setImplementers] = useState([]);
  const [assignForm, setAssignForm] = useState({ assigned_to_user_id: '', estimated_delivery_date: '', reassignment_comment: '', reassignment_date: '' });
  const [assignLoading, setAssignLoading] = useState(false);

  // Status change dialog
  const [statusDialogOpen, setStatusDialogOpen] = useState(false);
  const [statusProject, setStatusProject] = useState(null);
  const [statusForm, setStatusForm] = useState({ new_status: '', note: '', change_date: new Date().toISOString().slice(0, 10) });
  const [statusLoading, setStatusLoading] = useState(false);

  // Anexos dialog
  const [anexosDialogOpen, setAnexosDialogOpen] = useState(false);
  const [anexosProject, setAnexosProject] = useState(null);

  const fetchProjects = useCallback(async () => {
    try {
      const [projRes, statsRes] = await Promise.all([api.get('/projects'), api.get('/projects/stats')]);
      setProjects(projRes.data);
      setStats(statsRes.data);
    } catch (err) { toast.error('Error cargando proyectos'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchProjects(); }, [fetchProjects]);

  const fetchImplementers = async () => {
    try { const res = await api.get('/projects/implementers/list'); setImplementers(res.data); }
    catch { toast.error('Error cargando implementadores'); }
  };

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
    fetchImplementers();
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
    setStatusDialogOpen(true);
  };

  const handleStatusChange = async () => {
    if (!statusForm.new_status) { toast.error('Seleccione un estado'); return; }
    setStatusLoading(true);
    try {
      await api.put(`/projects/${statusProject.project_id}/status`, statusForm);
      toast.success(`Estado: ${statusForm.new_status}`);
      setStatusDialogOpen(false);
      fetchProjects();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al cambiar estado'); }
    finally { setStatusLoading(false); }
  };

  const handlePriorityChange = async (projectId, priority) => {
    try {
      await api.put(`/projects/${projectId}/priority`, { priority });
      toast.success(`Prioridad: ${priority}`);
      fetchProjects();
    } catch (err) { toast.error('Error al cambiar prioridad'); }
  };

  const filtered = projects.filter(p => {
    const matchSearch = !searchTerm ||
      p.project_number?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.client_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.client_rif?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.assigned_to_name?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchStatus = statusFilter === 'all'
      ? true
      : statusFilter === 'irregular'
        ? p.is_irregular === true
        : p.status === statusFilter;
    return matchSearch && matchStatus;
  });

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
          <div className="mb-8">
            <h1 className="text-4xl font-bold text-slate-900 font-manrope mb-2">Proyectos</h1>
            <p className="text-slate-600">Seguimiento de implementaciones post-venta</p>
          </div>

          {/* Stats Cards */}
          <div className="grid grid-cols-6 gap-4 mb-6">
            {[
              { label: 'Total', value: stats.total || 0, cls: 'bg-slate-50 border-slate-200 text-slate-700', filter: 'all' },
              { label: 'Pendientes', value: stats.pending || 0, cls: 'bg-amber-50 border-amber-200 text-amber-700', filter: 'Pendiente por Asignar' },
              { label: 'En Proceso', value: stats.in_progress || 0, cls: 'bg-blue-50 border-blue-200 text-blue-700', filter: 'Asignado / En Proceso' },
              { label: 'Detenidos', value: stats.blocked || 0, cls: 'bg-red-50 border-red-200 text-red-700', filter: 'Detenido por Cliente/Banco' },
              { label: 'Finalizados', value: stats.completed || 0, cls: 'bg-emerald-50 border-emerald-200 text-emerald-700', filter: 'Finalizado / Producción' },
              { label: 'P. Irregular', value: stats.irregular || 0, cls: 'bg-orange-50 border-orange-300 text-orange-700', filter: 'irregular' },
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
              <Input placeholder="Buscar por proyecto, cliente, RIF o implementador..."
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
                  <SelectItem value="all">Todos los estados</SelectItem>
                  {Object.keys(STATUS_CONFIG).map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                  <SelectItem value="irregular">Proceso Irregular</SelectItem>
                </SelectContent>
              </Select>
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
            <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
              <table className="w-full">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Proyecto</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Cliente</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Sede</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Estado</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Implementador</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Prioridad</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Fecha Est.</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-slate-600 uppercase">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filtered.map(project => {
                    const stCfg = STATUS_CONFIG[project.status] || STATUS_CONFIG['Pendiente por Asignar'];
                    const StIcon = stCfg.icon;
                    const hasAssignee = !!project.assigned_to_name;
                    return (
                      <tr key={project.project_id} className="hover:bg-slate-50 transition-colors"
                        data-testid={`project-row-${project.project_id}`}>
                        <td className="px-4 py-3">
                          <p className="text-sm font-semibold text-slate-900">{project.project_number}</p>
                          <p className="text-xs text-slate-400">Cot: {project.quote_number}</p>
                          <div className="flex gap-1 mt-1 flex-wrap">
                            {project.project_type === 'multistore' && (
                              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-semibold rounded bg-blue-100 text-blue-700 border border-blue-200" data-testid="project-multistore-badge">
                                <Store size={10} />Multitienda ({project.stores?.length || 0})
                              </span>
                            )}
                            {project.is_irregular && (
                              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-semibold rounded bg-orange-100 text-orange-700 border border-orange-200" data-testid="project-irregular-badge">
                                <AlertTriangle size={10} />Irregular
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <p className="text-sm font-medium text-slate-800">{project.client_name}</p>
                          <p className="text-xs font-mono text-slate-400">{project.client_rif}</p>
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-600">{project.client_sede || '—'}</td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-full border ${stCfg.color}`}>
                            <StIcon size={12} />{project.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-600">
                          {project.assigned_to_name || <span className="text-slate-400 italic">Sin asignar</span>}
                        </td>
                        <td className="px-4 py-3">
                          <Select value={project.priority || 'Normal'} onValueChange={v => handlePriorityChange(project.project_id, v)}>
                            <SelectTrigger className={`h-7 w-24 text-xs border-0 bg-transparent ${PRIORITY_COLORS[project.priority] || ''}`}>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {PRIORITY_OPTIONS.map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}
                            </SelectContent>
                          </Select>
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-600">{project.estimated_delivery_date || '—'}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-center gap-1">
                            {/* Cambiar Estado */}
                            <Button size="sm" variant="outline" onClick={() => openStatusDialog(project)}
                              title="Cambiar Estado"
                              className="h-8 px-2 text-orange-600 hover:bg-orange-50"
                              data-testid={`status-btn-${project.project_id}`}>
                              <RefreshCw size={14} />
                            </Button>
                            {/* Asignar / Reasignar */}
                            <Button size="sm" variant="outline" onClick={() => openAssignDialog(project)}
                              title={hasAssignee ? 'Reasignar' : 'Asignar'}
                              className={`h-8 px-2 text-xs gap-1 ${hasAssignee ? 'text-purple-600 hover:bg-purple-50' : 'text-blue-600 hover:bg-blue-50'}`}
                              data-testid={`assign-btn-${project.project_id}`}>
                              {hasAssignee ? <UserPlus size={14} /> : <UserCheck size={14} />}
                              <span className="hidden xl:inline">{hasAssignee ? 'Reasignar' : 'Asignar'}</span>
                            </Button>
                            {/* Anexos */}
                            <Button size="sm" variant="outline" title="Anexos"
                              onClick={() => { setAnexosProject(project); setAnexosDialogOpen(true); }}
                              className="h-8 px-2 text-amber-600" data-testid={`anexos-btn-${project.project_id}`}>
                              <Paperclip size={14} />
                            </Button>
                            {/* Ver Detalle */}
                            <Button size="sm" variant="outline" title="Detalle del Proyecto"
                              onClick={() => navigate(`/projects/${project.project_id}`)}
                              className="h-8 px-2 text-emerald-600" data-testid={`detail-btn-${project.project_id}`}>
                              <Eye size={14} />
                            </Button>
                          </div>
                        </td>
                      </tr>
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
                    {STATUS_TRANSITIONS.filter(t => t.id !== statusProject.status).map(t => {
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

                {/* Date + Comment */}
                {statusForm.new_status && (
                  <div className="space-y-3 pt-2 border-t border-slate-200 animate-in fade-in-0 slide-in-from-top-1">
                    <div>
                      <Label className="text-sm">Fecha del Cambio</Label>
                      <Input type="date" value={statusForm.change_date}
                        onChange={e => setStatusForm(p => ({ ...p, change_date: e.target.value }))}
                        className="mt-1" data-testid="status-change-date" />
                    </div>
                    <div>
                      <Label className="text-sm">Comentario</Label>
                      <Textarea value={statusForm.note}
                        onChange={e => setStatusForm(p => ({ ...p, note: e.target.value }))}
                        placeholder="Motivo o detalle del cambio de estado..."
                        className="mt-1 min-h-[60px] text-sm" data-testid="status-change-comment" />
                    </div>
                  </div>
                )}

                <div className="flex justify-end gap-3 pt-2 border-t">
                  <Button variant="outline" onClick={() => setStatusDialogOpen(false)}>Cancelar</Button>
                  <Button onClick={handleStatusChange}
                    disabled={statusLoading || !statusForm.new_status}
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
                  <p className="text-xs text-slate-500">{assignProject.client_name} — {assignProject.client_rif}</p>
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
                </div>
                <div>
                  <Label className="text-sm">Fecha Estimada de Entrega</Label>
                  <Input type="date" value={assignForm.estimated_delivery_date}
                    onChange={e => setAssignForm({ ...assignForm, estimated_delivery_date: e.target.value })}
                    className="mt-1" data-testid="assign-delivery-date" />
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

        {/* Anexos Dialog */}
        <Dialog open={anexosDialogOpen} onOpenChange={setAnexosDialogOpen}>
          <DialogContent className="max-w-lg" data-testid="anexos-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><Paperclip className="text-amber-500" size={20} />Anexos del Proyecto</DialogTitle>
            </DialogHeader>
            {anexosProject && (
              <div className="space-y-3">
                <p className="text-sm text-slate-500">{anexosProject.project_number} — {anexosProject.client_name}</p>
                {(anexosProject.attachments || []).length === 0 ? (
                  <div className="text-center py-8 bg-slate-50 rounded-lg">
                    <Paperclip size={32} className="mx-auto text-slate-300 mb-2" />
                    <p className="text-sm text-slate-400">No hay anexos en este proyecto</p>
                  </div>
                ) : (
                  <div className="space-y-2 max-h-72 overflow-y-auto">
                    {(anexosProject.attachments || []).map((att, i) => (
                      <div key={att.attachment_id || i} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg border">
                        <div className="flex items-center gap-3">
                          <FileText size={18} className="text-blue-500 shrink-0" />
                          <div>
                            <p className="text-sm font-medium">{att.filename}</p>
                            <p className="text-xs text-slate-400">
                              {att.category} · {att.uploaded_by_name || att.uploaded_by}
                              {att.inherited_from && <span className="ml-1 text-amber-600">(heredado de cotización)</span>}
                            </p>
                          </div>
                        </div>
                        {att.url && (
                          <a href={att.url.startsWith('http') ? att.url : `${process.env.REACT_APP_BACKEND_URL}${att.url}`}
                            target="_blank" rel="noopener noreferrer"
                            className="text-blue-600 hover:underline text-sm shrink-0">Descargar</a>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
};

export default Projects;
