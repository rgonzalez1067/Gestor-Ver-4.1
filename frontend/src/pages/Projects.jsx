import { useState, useEffect, useCallback } from 'react';
import { Sidebar } from '../components/Sidebar';
import api from '../utils/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../components/ui/select';
import { toast } from 'sonner';
import {
  FolderKanban, Search, UserCheck, Calendar, Clock, AlertTriangle,
  CheckCircle2, Pause, ChevronDown, ChevronUp, FileText, Send,
  ArrowRight, MessageSquarePlus, Filter, Building2
} from 'lucide-react';

const STATUS_CONFIG = {
  'Pendiente por Asignar': { color: 'bg-amber-100 text-amber-800 border-amber-200', icon: Clock },
  'Asignado / En Proceso': { color: 'bg-blue-100 text-blue-800 border-blue-200', icon: UserCheck },
  'Detenido por Cliente/Banco': { color: 'bg-red-100 text-red-800 border-red-200', icon: Pause },
  'Finalizado / Producción': { color: 'bg-emerald-100 text-emerald-800 border-emerald-200', icon: CheckCircle2 },
};

const PRIORITY_CONFIG = {
  'Baja': 'text-slate-500',
  'Normal': 'text-blue-600',
  'Alta': 'text-orange-600 font-semibold',
  'Urgente': 'text-red-600 font-bold',
};

const Projects = () => {
  const [projects, setProjects] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [expandedProject, setExpandedProject] = useState(null);

  // Assign dialog
  const [assignDialogOpen, setAssignDialogOpen] = useState(false);
  const [assignProject, setAssignProject] = useState(null);
  const [implementers, setImplementers] = useState([]);
  const [assignForm, setAssignForm] = useState({ assigned_to_user_id: '', estimated_delivery_date: '' });
  const [assignLoading, setAssignLoading] = useState(false);

  // Status change dialog
  const [statusDialogOpen, setStatusDialogOpen] = useState(false);
  const [statusProject, setStatusProject] = useState(null);
  const [newStatus, setNewStatus] = useState('');
  const [statusNote, setStatusNote] = useState('');

  // Note dialog
  const [noteDialogOpen, setNoteDialogOpen] = useState(false);
  const [noteProject, setNoteProject] = useState(null);
  const [noteText, setNoteText] = useState('');

  const fetchProjects = useCallback(async () => {
    try {
      const [projRes, statsRes] = await Promise.all([
        api.get('/projects'),
        api.get('/projects/stats')
      ]);
      setProjects(projRes.data);
      setStats(statsRes.data);
    } catch (err) {
      toast.error('Error cargando proyectos');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchProjects(); }, [fetchProjects]);

  const fetchImplementers = async () => {
    try {
      const res = await api.get('/projects/implementers/list');
      setImplementers(res.data);
    } catch (err) {
      toast.error('Error cargando implementadores');
    }
  };

  const openAssignDialog = (project) => {
    setAssignProject(project);
    setAssignForm({ assigned_to_user_id: project.assigned_to_user_id || '', estimated_delivery_date: project.estimated_delivery_date || '' });
    fetchImplementers();
    setAssignDialogOpen(true);
  };

  const handleAssign = async () => {
    if (!assignForm.assigned_to_user_id) { toast.error('Seleccione un implementador'); return; }
    setAssignLoading(true);
    try {
      await api.put(`/projects/${assignProject.project_id}/assign`, assignForm);
      toast.success('Proyecto asignado exitosamente');
      setAssignDialogOpen(false);
      fetchProjects();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al asignar');
    } finally {
      setAssignLoading(false);
    }
  };

  const openStatusDialog = (project) => {
    setStatusProject(project);
    setNewStatus('');
    setStatusNote('');
    setStatusDialogOpen(true);
  };

  const handleStatusChange = async () => {
    if (!newStatus) return;
    try {
      await api.put(`/projects/${statusProject.project_id}/status`, { new_status: newStatus, note: statusNote || null });
      toast.success(`Estado cambiado a "${newStatus}"`);
      setStatusDialogOpen(false);
      fetchProjects();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al cambiar estado');
    }
  };

  const openNoteDialog = (project) => {
    setNoteProject(project);
    setNoteText('');
    setNoteDialogOpen(true);
  };

  const handleAddNote = async () => {
    if (!noteText.trim()) return;
    try {
      await api.post(`/projects/${noteProject.project_id}/notes`, { text: noteText });
      toast.success('Nota agregada');
      setNoteDialogOpen(false);
      fetchProjects();
    } catch (err) {
      toast.error('Error al agregar nota');
    }
  };

  const filtered = projects.filter(p => {
    const matchSearch = !searchTerm ||
      p.project_number?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.client_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.client_rif?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.assigned_to_name?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchStatus = statusFilter === 'all' || p.status === statusFilter;
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
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-4xl font-bold text-slate-900 font-manrope mb-2">Proyectos</h1>
            <p className="text-slate-600">Seguimiento de implementaciones post-venta</p>
          </div>

          {/* Stats Cards */}
          <div className="grid grid-cols-5 gap-4 mb-6">
            {[
              { label: 'Total', value: stats.total || 0, cls: 'bg-slate-50 border-slate-200 text-slate-700' },
              { label: 'Pendientes', value: stats.pending || 0, cls: 'bg-amber-50 border-amber-200 text-amber-700' },
              { label: 'En Proceso', value: stats.in_progress || 0, cls: 'bg-blue-50 border-blue-200 text-blue-700' },
              { label: 'Detenidos', value: stats.blocked || 0, cls: 'bg-red-50 border-red-200 text-red-700' },
              { label: 'Finalizados', value: stats.completed || 0, cls: 'bg-emerald-50 border-emerald-200 text-emerald-700' },
            ].map(s => (
              <div key={s.label} className={`p-4 rounded-lg border ${s.cls}`} data-testid={`stat-${s.label.toLowerCase()}`}>
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
                    const isExpanded = expandedProject === project.project_id;
                    return (
                      <ProjectRow key={project.project_id} project={project} stCfg={stCfg} StIcon={StIcon}
                        isExpanded={isExpanded}
                        onToggleExpand={() => setExpandedProject(isExpanded ? null : project.project_id)}
                        onAssign={() => openAssignDialog(project)}
                        onStatusChange={() => openStatusDialog(project)}
                        onAddNote={() => openNoteDialog(project)}
                      />
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Assign Dialog */}
        <Dialog open={assignDialogOpen} onOpenChange={setAssignDialogOpen}>
          <DialogContent className="max-w-md" data-testid="assign-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><UserCheck className="text-blue-500" size={20} />Asignar Proyecto</DialogTitle>
            </DialogHeader>
            {assignProject && (
              <div className="space-y-4">
                <div className="bg-slate-50 border rounded-lg p-3">
                  <p className="font-semibold">{assignProject.project_number}</p>
                  <p className="text-sm text-slate-500">{assignProject.client_name} — {assignProject.client_rif}</p>
                </div>
                <div>
                  <Label>Implementador</Label>
                  <Select value={assignForm.assigned_to_user_id} onValueChange={v => setAssignForm({ ...assignForm, assigned_to_user_id: v })}>
                    <SelectTrigger data-testid="select-implementer"><SelectValue placeholder="Seleccionar implementador..." /></SelectTrigger>
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
                  <Label>Fecha Estimada de Entrega</Label>
                  <Input type="date" value={assignForm.estimated_delivery_date}
                    onChange={e => setAssignForm({ ...assignForm, estimated_delivery_date: e.target.value })}
                    data-testid="assign-delivery-date" />
                </div>
                <div className="flex justify-end gap-3 pt-2 border-t">
                  <Button variant="outline" onClick={() => setAssignDialogOpen(false)}>Cancelar</Button>
                  <Button onClick={handleAssign} disabled={assignLoading || !assignForm.assigned_to_user_id}
                    className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="assign-confirm-btn">
                    {assignLoading ? 'Asignando...' : 'Asignar Proyecto'}
                  </Button>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* Status Change Dialog */}
        <Dialog open={statusDialogOpen} onOpenChange={setStatusDialogOpen}>
          <DialogContent className="max-w-md" data-testid="status-dialog">
            <DialogHeader>
              <DialogTitle>Cambiar Estado del Proyecto</DialogTitle>
            </DialogHeader>
            {statusProject && (
              <div className="space-y-4">
                <div className="bg-slate-50 border rounded-lg p-3">
                  <p className="font-semibold">{statusProject.project_number}</p>
                  <p className="text-sm text-slate-500">Estado actual: <span className="font-medium">{statusProject.status}</span></p>
                </div>
                <div>
                  <Label>Nuevo Estado</Label>
                  <Select value={newStatus} onValueChange={setNewStatus}>
                    <SelectTrigger data-testid="select-new-status"><SelectValue placeholder="Seleccionar estado..." /></SelectTrigger>
                    <SelectContent>
                      {Object.keys(STATUS_CONFIG).filter(s => s !== statusProject.status).map(s => (
                        <SelectItem key={s} value={s}>{s}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Nota (opcional)</Label>
                  <Input value={statusNote} onChange={e => setStatusNote(e.target.value)}
                    placeholder="Motivo del cambio..." data-testid="status-note-input" />
                </div>
                <div className="flex justify-end gap-3 pt-2 border-t">
                  <Button variant="outline" onClick={() => setStatusDialogOpen(false)}>Cancelar</Button>
                  <Button onClick={handleStatusChange} disabled={!newStatus}
                    className="bg-brand-green-600 hover:bg-brand-green-700 text-white" data-testid="status-confirm-btn">
                    Actualizar Estado
                  </Button>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* Add Note Dialog */}
        <Dialog open={noteDialogOpen} onOpenChange={setNoteDialogOpen}>
          <DialogContent className="max-w-md" data-testid="note-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><MessageSquarePlus size={18} />Agregar Nota</DialogTitle>
            </DialogHeader>
            {noteProject && (
              <div className="space-y-4">
                <div className="bg-slate-50 border rounded-lg p-3">
                  <p className="font-semibold">{noteProject.project_number} — {noteProject.client_name}</p>
                </div>
                <div>
                  <Label>Nota</Label>
                  <textarea value={noteText} onChange={e => setNoteText(e.target.value)}
                    placeholder="Escriba una nota o avance..." rows={3}
                    className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm" data-testid="note-text-input" />
                </div>
                <div className="flex justify-end gap-3 pt-2 border-t">
                  <Button variant="outline" onClick={() => setNoteDialogOpen(false)}>Cancelar</Button>
                  <Button onClick={handleAddNote} disabled={!noteText.trim()}
                    className="bg-brand-green-600 hover:bg-brand-green-700 text-white" data-testid="note-confirm-btn">
                    Agregar Nota
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

// Sub-component: Project Row with expandable detail
const ProjectRow = ({ project, stCfg, StIcon, isExpanded, onToggleExpand, onAssign, onStatusChange, onAddNote }) => {
  return (
    <>
      <tr className="hover:bg-slate-50 transition-colors cursor-pointer" onClick={onToggleExpand}
        data-testid={`project-row-${project.project_id}`}>
        <td className="px-4 py-3">
          <div>
            <p className="text-sm font-semibold text-slate-900">{project.project_number}</p>
            <p className="text-xs text-slate-400">Cot: {project.quote_number}</p>
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
        <td className="px-4 py-3 text-sm text-slate-600">{project.assigned_to_name || <span className="text-slate-400 italic">Sin asignar</span>}</td>
        <td className="px-4 py-3">
          <span className={`text-sm ${PRIORITY_CONFIG[project.priority] || ''}`}>{project.priority}</span>
        </td>
        <td className="px-4 py-3 text-sm text-slate-600">{project.estimated_delivery_date || '—'}</td>
        <td className="px-4 py-3">
          <div className="flex items-center justify-center gap-1" onClick={e => e.stopPropagation()}>
            <Button size="sm" variant="outline" onClick={onAssign} title="Asignar"
              className="h-8 px-2 text-blue-600" data-testid={`assign-btn-${project.project_id}`}>
              <UserCheck size={14} />
            </Button>
            <Button size="sm" variant="outline" onClick={onStatusChange} title="Cambiar Estado"
              className="h-8 px-2 text-amber-600" data-testid={`status-btn-${project.project_id}`}>
              <ArrowRight size={14} />
            </Button>
            <Button size="sm" variant="outline" onClick={onAddNote} title="Agregar Nota"
              className="h-8 px-2 text-slate-600" data-testid={`note-btn-${project.project_id}`}>
              <MessageSquarePlus size={14} />
            </Button>
            {isExpanded ? <ChevronUp size={16} className="text-slate-400 ml-1" /> : <ChevronDown size={16} className="text-slate-400 ml-1" />}
          </div>
        </td>
      </tr>
      {isExpanded && (
        <tr data-testid={`project-detail-${project.project_id}`}>
          <td colSpan={8} className="bg-slate-50 px-6 py-4 border-t border-slate-100">
            <div className="grid grid-cols-3 gap-6">
              {/* Left: Quote info */}
              <div>
                <h4 className="text-xs font-semibold uppercase text-slate-500 mb-2">Datos de Cotización</h4>
                <div className="space-y-1 text-sm">
                  <p><span className="text-slate-500">Tipo:</span> {project.quote_type} ({project.quote_category})</p>
                  <p><span className="text-slate-500">Total USD:</span> ${project.total_usd?.toLocaleString('es-VE', { minimumFractionDigits: 2 })}</p>
                  {project.integrator_name && <p><span className="text-slate-500">Integrador:</span> {project.integrator_name}</p>}
                  {project.pinpad_model && <p><span className="text-slate-500">Pinpad:</span> {project.pinpad_model}</p>}
                  {project.sponsor_bank_name && <p><span className="text-slate-500">Banco:</span> {project.sponsor_bank_name}</p>}
                  {project.quote_pdf_url && (
                    <a href={project.quote_pdf_url} target="_blank" rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-blue-600 hover:underline mt-1">
                      <FileText size={14} />Ver PDF Cotización
                    </a>
                  )}
                </div>
              </div>
              {/* Center: Products/Services */}
              <div>
                <h4 className="text-xs font-semibold uppercase text-slate-500 mb-2">Productos / Servicios</h4>
                <div className="space-y-1 text-sm max-h-32 overflow-y-auto">
                  {(project.services || []).map((s, i) => (
                    <p key={i} className="text-slate-700">{s.concepto || s.name || `Servicio ${i + 1}`}</p>
                  ))}
                  {(project.hardware || []).map((h, i) => (
                    <p key={`hw-${i}`} className="text-slate-700">{h.concepto || h.name || `Hardware ${i + 1}`}</p>
                  ))}
                  {(project.banks || []).length > 0 && (
                    <div className="mt-2">
                      <p className="text-xs text-slate-400 font-medium">Bancos:</p>
                      {project.banks.map((b, i) => <p key={i} className="text-slate-600 flex items-center gap-1"><Building2 size={12} />{b.bank_name}</p>)}
                    </div>
                  )}
                </div>
              </div>
              {/* Right: Notes */}
              <div>
                <h4 className="text-xs font-semibold uppercase text-slate-500 mb-2">Historial / Notas ({(project.notes || []).length})</h4>
                <div className="space-y-2 max-h-40 overflow-y-auto">
                  {(project.notes || []).slice().reverse().map(note => (
                    <div key={note.note_id} className="text-sm bg-white border border-slate-100 rounded p-2">
                      <p className="text-slate-800">{note.text}</p>
                      <p className="text-xs text-slate-400 mt-1">{note.created_by_name} · {new Date(note.created_at).toLocaleString('es-VE')}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
};

export default Projects;
