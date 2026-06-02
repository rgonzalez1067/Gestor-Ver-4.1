import { useState, useEffect } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Plus, Phone, Mail, Building2, User, Search, BookOpen, UserPlus, ArrowRightLeft, Rocket, ChevronDown, ChevronUp, Filter, Trash2, Send, XCircle, MessageSquare, RotateCcw } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';
import { InitialContactEmailDialog } from '../components/InitialContactEmailDialog';
import BitacoraModal from '../components/BitacoraModal';
import { TwinScrollTable } from '../components/TwinScrollTable';

export const InitialContacts = () => {
  const [contacts, setContacts] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [currentUser, setCurrentUser] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterSede, setFilterSede] = useState('all');

  // Create modal
  const [createOpen, setCreateOpen] = useState(false);
  const [formData, setFormData] = useState({ contact_name: '', phone: '', email: '', legal_name: '', interest_notes: '', referred_by: '', assigned_to_user_id: '', due_date: '' });

  // Action modals
  const [documentOpen, setDocumentOpen] = useState(false);
  const [documentContact, setDocumentContact] = useState(null);
  const [documentNextDate, setDocumentNextDate] = useState('');
  const [documentComment, setDocumentComment] = useState('');

  const [assignOpen, setAssignOpen] = useState(false);
  const [assignContact, setAssignContact] = useState(null);
  const [assignUserId, setAssignUserId] = useState('');
  const [assignComment, setAssignComment] = useState('');

  const [transferOpen, setTransferOpen] = useState(false);
  const [transferContact, setTransferContact] = useState(null);
  const [transferUserId, setTransferUserId] = useState('');
  const [transferComment, setTransferComment] = useState('');

  const [convertConfirmOpen, setConvertConfirmOpen] = useState(false);
  const [convertContact, setConvertContact] = useState(null);

  // Bitacora viewer (unified)
  const [bitacoraOpen, setBitacoraOpen] = useState(false);
  const [bitacoraContact, setBitacoraContact] = useState(null);

  // Cerrar gestión (disponible para todos los usuarios con acceso)
  const [closeOpen, setCloseOpen] = useState(false);
  const [closeContact, setCloseContact] = useState(null);
  const [closeReason, setCloseReason] = useState('');
  const [closing, setClosing] = useState(false);

  // Reabrir gestión (disponible para todos los usuarios con acceso)
  const [reopenOpen, setReopenOpen] = useState(false);
  const [reopenContact, setReopenContact] = useState(null);
  const [reopenReason, setReopenReason] = useState('');
  const [reopenDueDate, setReopenDueDate] = useState('');
  const [reopening, setReopening] = useState(false);

  // Default fecha límite al reabrir: hoy + 5 días
  const defaultReopenDate = () => {
    const d = new Date();
    d.setDate(d.getDate() + 5);
    return d.toISOString().slice(0, 10);
  };

  // Filtro de status: active | closed | all
  const [filterStatus, setFilterStatus] = useState('active');

  // Notification dialog
  const [notifyOpen, setNotifyOpen] = useState(false);
  const [notifyContact, setNotifyContact] = useState(null);

  // Delete (admin only)
  const [deleteContact, setDeleteContact] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const isAdmin = currentUser?.role === 'admin';

  // Expanded rows
  const [expandedRow, setExpandedRow] = useState(null);

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      const [contactsRes, usersRes, meRes] = await Promise.all([
        api.get('/initial-contacts'),
        api.get('/auth/users'),
        api.get('/auth/me')
      ]);
      setContacts(contactsRes.data);
      setUsers(usersRes.data || []);
      setCurrentUser(meRes.data);
    } catch { toast.error('Error al cargar datos'); }
    finally { setLoading(false); }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!formData.contact_name || !formData.legal_name) {
      toast.error('Nombre del contacto y Razón Social son obligatorios'); return;
    }
    if (!formData.phone && !formData.email) {
      toast.error('Debe indicar al menos Teléfono o Email'); return;
    }
    try {
      await api.post('/initial-contacts', formData);
      toast.success('Contacto inicial creado');
      setCreateOpen(false);
      setFormData({ contact_name: '', phone: '', email: '', legal_name: '', interest_notes: '', referred_by: '', assigned_to_user_id: '', due_date: '' });
      fetchData();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al crear contacto'); }
  };

  const handleDocument = async () => {
    if (!documentComment.trim()) { toast.error('Escriba un comentario'); return; }
    try {
      await api.post(`/initial-contacts/${documentContact.contact_id}/document`, {
        comment: documentComment,
        next_contact_date: documentNextDate || null,
      });
      toast.success('Gestion documentada');
      setDocumentOpen(false);
      setDocumentComment('');
      setDocumentNextDate('');
      fetchData();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al documentar'); }
  };

  const handleAssign = async () => {
    if (!assignUserId) { toast.error('Seleccione un usuario'); return; }
    try {
      await api.post(`/initial-contacts/${assignContact.contact_id}/assign`, {
        assigned_to_user_id: assignUserId, comment: assignComment || undefined
      });
      toast.success('Contacto asignado');
      setAssignOpen(false);
      setAssignUserId('');
      setAssignComment('');
      fetchData();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al asignar'); }
  };

  const handleTransfer = async () => {
    if (!transferUserId) { toast.error('Seleccione un usuario destino'); return; }
    try {
      await api.post(`/initial-contacts/${transferContact.contact_id}/transfer`, {
        target_user_id: transferUserId, comment: transferComment || undefined
      });
      toast.success('Contacto transferido');
      setTransferOpen(false);
      setTransferUserId('');
      setTransferComment('');
      fetchData();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al transferir'); }
  };

  const handleConvert = async () => {
    try {
      const res = await api.post(`/initial-contacts/${convertContact.contact_id}/convert`);
      toast.success(res.data.message);
      setConvertConfirmOpen(false);
      fetchData();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al convertir'); }
  };

  const handleDelete = async () => {
    if (!deleteContact) return;
    setDeleting(true);
    try {
      await api.delete(`/initial-contacts/${deleteContact.contact_id}`);
      toast.success('Contacto eliminado');
      setDeleteContact(null);
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al eliminar');
    } finally {
      setDeleting(false);
    }
  };

  // Botones Asignar / Transferir disponibles para todo usuario con acceso al módulo.
  // El control de visibilidad del módulo ya lo maneja el sistema de permisos vía perfil/special_permissions.
  const canAssign = !!currentUser;
  const canTransfer = !!currentUser;

  // Filter users for assignment based on hierarchy
  const assignableUsers = users.filter(u => {
    if (!currentUser) return false;
    if (u.user_id === currentUser.user_id) return false; // No asignar a sí mismo
    if (currentUser.role === 'admin') return true;
    const allowed = { Director: ['Gerente'], Gerente: ['Coordinador', 'Ejecutivo'], Coordinador: ['Ejecutivo'], Ejecutivo: ['Ejecutivo'] };
    return (allowed[currentUser.cargo] || []).includes(u.cargo) && u.is_active !== false;
  });

  // Filter users for transfer (only Gerentes from other sede)
  const transferableUsers = users.filter(u => {
    if (!currentUser) return false;
    return u.cargo === 'Gerente' && u.user_id !== currentUser.user_id && u.is_active !== false;
  });

  const filtered = contacts.filter(c => {
    const q = searchTerm.toLowerCase();
    const matchSearch = !q || c.contact_name?.toLowerCase().includes(q) || c.legal_name?.toLowerCase().includes(q) || c.email?.toLowerCase().includes(q) || c.phone?.includes(q) || c.referred_by?.toLowerCase().includes(q);
    const matchSede = filterSede === 'all' || c.sede === filterSede;
    const isClosed = c.status === 'closed';
    const matchStatus = filterStatus === 'all' || (filterStatus === 'closed' ? isClosed : !isClosed);
    return matchSearch && matchSede && matchStatus;
  });

  const getSLAStatus = (dueDate) => {
    if (!dueDate) return { color: 'bg-slate-100 text-slate-500', label: 'Sin fecha', dot: 'bg-slate-300' };
    const now = new Date();
    const due = new Date(dueDate + 'T23:59:59');
    const diffMs = due.getTime() - now.getTime();
    const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
    if (diffDays >= 1) return { color: 'bg-green-100 text-green-700', label: 'En Tiempo', dot: 'bg-green-500' };
    if (diffDays >= 0) return { color: 'bg-yellow-100 text-yellow-700', label: 'Alerta', dot: 'bg-yellow-500' };
    return { color: 'bg-red-100 text-red-700', label: 'Vencido', dot: 'bg-red-500' };
  };

  const formatDate = (iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleDateString('es-VE', { day: '2-digit', month: '2-digit', year: 'numeric' }) + ' ' + d.toLocaleTimeString('es-VE', { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 p-8" data-testid="initial-contacts-page">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-bold text-slate-900 font-manrope">Contacto Inicial</h1>
            <p className="text-sm text-slate-500 mt-1">Gestion de leads y prospeccion temprana</p>
          </div>
          <Button onClick={() => setCreateOpen(true)} className="bg-brand-green-600 hover:bg-brand-green-700" data-testid="create-contact-btn">
            <Plus size={16} className="mr-1" /> Nuevo Contacto
          </Button>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3 mb-4">
          <div className="relative flex-1 max-w-sm">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <Input placeholder="Buscar por nombre, razon social, email..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} className="pl-9" data-testid="search-contacts" />
          </div>
          <Select value={filterSede} onValueChange={setFilterSede}>
            <SelectTrigger className="w-[140px]" data-testid="filter-sede">
              <Filter size={14} className="mr-1 text-slate-400" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas</SelectItem>
              <SelectItem value="PYME">Pyme</SelectItem>
              <SelectItem value="CORP">Corp</SelectItem>
            </SelectContent>
          </Select>
          <Select value={filterStatus} onValueChange={setFilterStatus}>
            <SelectTrigger className="w-[140px]" data-testid="filter-status">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="active">Activos</SelectItem>
              <SelectItem value="closed">Cerrados</SelectItem>
              <SelectItem value="all">Todos</SelectItem>
            </SelectContent>
          </Select>
          <div className="bg-slate-100 px-3 py-1.5 rounded-md text-sm text-slate-600">
            <span className="font-semibold">{filtered.length}</span> contacto(s)
          </div>
        </div>

        {/* Iter52: Twin Scrollbar — barras superior + inferior sincronizadas
            mediante refs y un sync de scrollLeft 1:1. Útil cuando la grilla
            tiene muchas columnas (Fecha último/próximo contacto añadidas). */}
        <TwinScrollTable>
            <table className="min-w-[1200px] w-full" data-testid="contacts-table">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase whitespace-nowrap">Contacto</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase whitespace-nowrap">Razon Social</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase whitespace-nowrap">Referido Por</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase whitespace-nowrap">Telefono / Email</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase whitespace-nowrap">Asignado a</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase whitespace-nowrap">Sede</th>
                  {/* Iter53: headers de fechas en 2 líneas + valores abreviados día/mes para compactar la grilla. */}
                  <th className="px-3 py-3 text-left text-[11px] font-medium text-slate-600 uppercase leading-tight"><div className="w-16">Fecha<br />límite</div></th>
                  <th className="px-3 py-3 text-left text-[11px] font-medium text-slate-600 uppercase leading-tight"><div className="w-16">Fecha<br />último<br />contacto</div></th>
                  <th className="px-3 py-3 text-left text-[11px] font-medium text-slate-600 uppercase leading-tight"><div className="w-16">Fecha<br />próximo<br />contacto</div></th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase whitespace-nowrap">Creado</th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-slate-600 uppercase whitespace-nowrap">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loading ? (
                  <tr><td colSpan={11} className="px-4 py-12 text-center text-slate-400">Cargando...</td></tr>
                ) : filtered.length === 0 ? (
                  <tr><td colSpan={11} className="px-4 py-12 text-center text-slate-400">No hay contactos iniciales</td></tr>
                ) : filtered.map((c) => (
                  <tr key={c.contact_id} className={`group ${c.status === 'closed' ? 'bg-blue-50 hover:bg-blue-100' : 'hover:bg-slate-50'}`} data-testid={`contact-row-${c.contact_id}`}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-xs font-bold shrink-0">
                          {(c.contact_name || '??').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()}
                        </div>
                        <span className="text-sm font-medium text-slate-800">{c.contact_name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-700">{c.legal_name}</td>
                    <td className="px-4 py-3">
                      {c.referred_by ? (
                        <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-[10px] font-semibold uppercase">{c.referred_by}</span>
                      ) : (
                        <span className="text-xs text-slate-400">Directo</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-xs text-slate-600">{c.phone}</div>
                      <div className="text-xs text-slate-400">{c.email}</div>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-700">{c.assigned_to_name || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 text-xs font-medium rounded ${c.sede === 'CORP' ? 'bg-blue-100 text-blue-700' : 'bg-emerald-100 text-emerald-700'}`}>
                        {c.sede}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {(() => {
                        const sla = getSLAStatus(c.due_date);
                        return c.due_date ? (
                          <div className="flex items-center gap-1.5">
                            <span className={`w-2.5 h-2.5 rounded-full ${sla.dot}`} />
                            <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${sla.color}`}>{new Date(c.due_date + 'T12:00:00').toLocaleDateString('es-VE', { day: '2-digit', month: '2-digit' })}</span>
                          </div>
                        ) : <span className="text-xs text-slate-400">—</span>;
                      })()}
                    </td>
                    <td className="px-3 py-3 text-xs text-slate-600 whitespace-nowrap" data-testid={`last-contact-${c.contact_id}`}>
                      {c.last_contact_date
                        ? new Date(c.last_contact_date).toLocaleDateString('es-VE', { day: '2-digit', month: '2-digit' })
                        : <span className="text-slate-400">--/--</span>}
                    </td>
                    <td className="px-3 py-3 text-xs text-slate-600 whitespace-nowrap" data-testid={`next-contact-${c.contact_id}`}>
                      {c.next_contact_date
                        ? new Date(c.next_contact_date + (c.next_contact_date.includes('T') ? '' : 'T12:00:00')).toLocaleDateString('es-VE', { day: '2-digit', month: '2-digit' })
                        : <span className="text-slate-400">--/--</span>}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">{formatDate(c.created_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-1">
                        <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-slate-500 hover:text-blue-600" title="Bitácora" data-testid={`bitacora-btn-${c.contact_id}`}
                          onClick={() => { setBitacoraContact(c); setBitacoraOpen(true); }}>
                          <BookOpen size={14} />
                        </Button>
                        {canAssign && (
                          <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-slate-500 hover:text-amber-600" title="Asignar" data-testid={`assign-btn-${c.contact_id}`}
                            onClick={() => { setAssignContact(c); setAssignUserId(''); setAssignComment(''); setAssignOpen(true); }}>
                            <UserPlus size={14} />
                          </Button>
                        )}
                        {canTransfer && (
                          <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-slate-500 hover:text-purple-600" title="Transferir" data-testid={`transfer-btn-${c.contact_id}`}
                            onClick={() => { setTransferContact(c); setTransferUserId(''); setTransferComment(''); setTransferOpen(true); }}>
                            <ArrowRightLeft size={14} />
                          </Button>
                        )}
                        {c.status !== 'closed' && (
                          <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-slate-500 hover:text-green-600" title="Convertir a Prospecto" data-testid={`convert-btn-${c.contact_id}`}
                            onClick={() => { setConvertContact(c); setConvertConfirmOpen(true); }}>
                            <Rocket size={14} />
                          </Button>
                        )}
                        <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-slate-500 hover:text-indigo-600" title="Enviar Notificación" data-testid={`notify-btn-${c.contact_id}`}
                          onClick={() => { setNotifyContact(c); setNotifyOpen(true); }}>
                          <Send size={14} />
                        </Button>
                        {c.status !== 'closed' ? (
                          <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-slate-500 hover:text-blue-700"
                            title="Cerrar Gestión"
                            onClick={() => { setCloseContact(c); setCloseReason(''); setCloseOpen(true); }}
                            data-testid={`close-btn-${c.contact_id}`}>
                            <XCircle size={14} />
                          </Button>
                        ) : (
                          <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-slate-500 hover:text-emerald-600"
                            title="Reabrir Gestión"
                            onClick={() => { setReopenContact(c); setReopenReason(''); setReopenDueDate(defaultReopenDate()); setReopenOpen(true); }}
                            data-testid={`reopen-btn-${c.contact_id}`}>
                            <RotateCcw size={14} />
                          </Button>
                        )}
                        {isAdmin && (
                          <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-slate-400 hover:text-red-600"
                            title="Eliminar (solo Admin)"
                            onClick={() => setDeleteContact(c)}
                            data-testid={`delete-btn-${c.contact_id}`}
                          >
                            <Trash2 size={14} />
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
        </TwinScrollTable>

        {/* Create Modal */}
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogContent className="max-w-md" data-testid="create-contact-modal">
            <DialogHeader><DialogTitle className="flex items-center gap-2"><Phone size={20} className="text-green-600" /> Nuevo Contacto Inicial</DialogTitle></DialogHeader>
            <form onSubmit={handleCreate} className="space-y-4 pt-2">
              <div>
                <Label>Nombre del Contacto *</Label>
                <Input value={formData.contact_name} onChange={(e) => setFormData({ ...formData, contact_name: e.target.value })} placeholder="Persona que atiende" required data-testid="input-contact-name" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Telefono</Label>
                  <Input value={formData.phone} onChange={(e) => setFormData({ ...formData, phone: e.target.value })} placeholder="+58 412 1234567" data-testid="input-phone" />
                </div>
                <div>
                  <Label>Email</Label>
                  <Input type="email" value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })} placeholder="correo@empresa.com" data-testid="input-email" />
                </div>
              </div>
              <p className="text-[11px] text-slate-400 -mt-2">Indique al menos uno: Teléfono o Email</p>
              <div>
                <Label>Nombre Juridico (Razon Social) *</Label>
                <Input value={formData.legal_name} onChange={(e) => setFormData({ ...formData, legal_name: e.target.value })} placeholder="Razon social tentativa" required data-testid="input-legal-name" />
              </div>
              <div>
                <Label className="text-xs font-semibold text-blue-600">Referido Por</Label>
                <Input value={formData.referred_by} onChange={(e) => setFormData({ ...formData, referred_by: e.target.value })} placeholder="Ej: Aliado X, LinkedIn, API Web..." className="border-blue-200 bg-blue-50/50 focus:bg-white" data-testid="input-referred-by" />
              </div>
              <div>
                <Label>Aspectos de Interes para el Contacto</Label>
                <Textarea
                  value={formData.interest_notes}
                  onChange={(e) => setFormData({ ...formData, interest_notes: e.target.value.slice(0, 300) })}
                  placeholder="Escriba los aspectos relevantes del contacto, productos de interes, notas importantes..."
                  rows={4}
                  className="resize-y"
                  data-testid="input-interest-notes"
                />
                <p className="text-xs text-slate-400 mt-1 text-right">{(formData.interest_notes || '').length}/300</p>
              </div>
              <div className="border-t border-slate-200 pt-3">
                <p className="text-xs font-semibold text-blue-600 uppercase tracking-wider mb-2">Asignacion y Compromiso</p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>Asignar a</Label>
                    <Select value={formData.assigned_to_user_id} onValueChange={(v) => setFormData({ ...formData, assigned_to_user_id: v })}>
                      <SelectTrigger data-testid="create-assign-select"><SelectValue placeholder="Yo mismo (por defecto)" /></SelectTrigger>
                      <SelectContent>
                        {assignableUsers.map(u => (
                          <SelectItem key={u.user_id} value={u.user_id}>
                            {u.first_name} {u.last_name} ({u.cargo})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Fecha Maxima de Atencion</Label>
                    <Input type="date" value={formData.due_date} onChange={(e) => setFormData({ ...formData, due_date: e.target.value })} data-testid="input-due-date" />
                  </div>
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>Cancelar</Button>
                <Button type="submit" className="bg-green-600 hover:bg-green-700" data-testid="submit-contact-btn">Crear Contacto</Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>

        {/* Document Modal */}
        <Dialog open={documentOpen} onOpenChange={setDocumentOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader><DialogTitle className="flex items-center gap-2"><MessageSquare size={20} className="text-blue-600" /> Documentar Gestion</DialogTitle></DialogHeader>
            {documentContact && <p className="text-sm text-slate-500">Contacto: <strong>{documentContact.legal_name}</strong></p>}
            <Textarea placeholder="Describa la gestion realizada..." value={documentComment} onChange={(e) => setDocumentComment(e.target.value)} rows={4} data-testid="document-comment" />
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-slate-600">Fecha próximo contacto (opcional)</Label>
              <Input
                type="date"
                value={documentNextDate}
                onChange={(e) => setDocumentNextDate(e.target.value)}
                data-testid="document-next-date"
              />
              <p className="text-[10px] text-slate-400">
                Si la informas, aparecerá en la columna "Fecha próximo contacto" de la grilla.
              </p>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setDocumentOpen(false)}>Cancelar</Button>
              <Button onClick={handleDocument} className="bg-blue-600 hover:bg-blue-700" data-testid="submit-document-btn">Guardar</Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* Assign Modal */}
        <Dialog open={assignOpen} onOpenChange={setAssignOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader><DialogTitle className="flex items-center gap-2"><UserPlus size={20} className="text-amber-600" /> Asignar Contacto</DialogTitle></DialogHeader>
            {assignContact && <p className="text-sm text-slate-500">Contacto: <strong>{assignContact.legal_name}</strong></p>}
            <div>
              <Label>Asignar a</Label>
              <Select value={assignUserId} onValueChange={setAssignUserId}>
                <SelectTrigger data-testid="assign-user-select"><SelectValue placeholder="Seleccione usuario..." /></SelectTrigger>
                <SelectContent>
                  {assignableUsers.map(u => (
                    <SelectItem key={u.user_id} value={u.user_id}>
                      {u.first_name} {u.last_name} ({u.cargo} - {u.sede})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Comentario (opcional)</Label>
              <Input value={assignComment} onChange={(e) => setAssignComment(e.target.value)} placeholder="Nota para el receptor..." data-testid="assign-comment" />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setAssignOpen(false)}>Cancelar</Button>
              <Button onClick={handleAssign} className="bg-amber-500 hover:bg-amber-600" data-testid="submit-assign-btn">Asignar</Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* Transfer Modal */}
        <Dialog open={transferOpen} onOpenChange={setTransferOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader><DialogTitle className="flex items-center gap-2"><ArrowRightLeft size={20} className="text-purple-600" /> Transferir a otra Area</DialogTitle></DialogHeader>
            {transferContact && <p className="text-sm text-slate-500">Contacto: <strong>{transferContact.legal_name}</strong> (Sede actual: {transferContact.sede})</p>}
            <div>
              <Label>Transferir a (Gerente)</Label>
              <Select value={transferUserId} onValueChange={setTransferUserId}>
                <SelectTrigger data-testid="transfer-user-select"><SelectValue placeholder="Seleccione gerente destino..." /></SelectTrigger>
                <SelectContent>
                  {transferableUsers.map(u => (
                    <SelectItem key={u.user_id} value={u.user_id}>
                      {u.first_name} {u.last_name} ({u.departamento} - {u.sede})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Comentario (opcional)</Label>
              <Input value={transferComment} onChange={(e) => setTransferComment(e.target.value)} placeholder="Razon de la transferencia..." data-testid="transfer-comment" />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setTransferOpen(false)}>Cancelar</Button>
              <Button onClick={handleTransfer} className="bg-purple-600 hover:bg-purple-700 text-white" data-testid="submit-transfer-btn">Transferir</Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* Convert Confirm */}
        <AlertDialog open={convertConfirmOpen} onOpenChange={setConvertConfirmOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle className="flex items-center gap-2"><Rocket size={20} className="text-green-600" /> Convertir a Prospecto</AlertDialogTitle>
              <AlertDialogDescription>
                Se creara un nuevo registro en <strong>Clientes</strong> con estatus <strong>Prospecto</strong> usando los datos de este contacto:
                {convertContact && (
                  <span className="block mt-2 p-3 bg-green-50 border border-green-200 rounded-lg">
                    <span className="font-semibold block">{convertContact.legal_name}</span>
                    <span className="text-xs text-slate-500">{convertContact.contact_name} - {convertContact.email}</span>
                  </span>
                )}
                <span className="block mt-2 text-xs text-slate-500">El contacto desaparecera de esta vista y usted sera el Ejecutivo responsable del nuevo prospecto.</span>
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel data-testid="cancel-convert">Cancelar</AlertDialogCancel>
              <AlertDialogAction onClick={handleConvert} className="bg-green-600 hover:bg-green-700" data-testid="confirm-convert">Convertir a Prospecto</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Bitácora Modal (unificado, mismo del módulo Clientes) */}
        <BitacoraModal
          open={bitacoraOpen}
          onOpenChange={setBitacoraOpen}
          entityId={bitacoraContact?.contact_id}
          entityName={bitacoraContact?.legal_name || ''}
          contacts={bitacoraContact ? [{
            id: bitacoraContact.contact_id,
            name: bitacoraContact.contact_name || '',
            role: 'Contacto principal',
          }] : []}
          apiPrefix="initial-contacts"
        />

        {/* Cerrar Gestión (todos los usuarios) */}
        <AlertDialog open={closeOpen} onOpenChange={setCloseOpen}>
          <AlertDialogContent data-testid="close-gestion-dialog">
            <AlertDialogHeader>
              <AlertDialogTitle className="text-blue-700">Cerrar Gestión</AlertDialogTitle>
              <AlertDialogDescription>
                El contacto <strong>{closeContact?.legal_name}</strong> quedará marcado como GESTIONADO (fondo azul) y dejará de aparecer en la bandeja activa. Los datos se conservan para histórico y estadísticas.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="space-y-2 my-3">
              <Label className="text-xs">Motivo del cierre (obligatorio)</Label>
              <Textarea
                value={closeReason}
                onChange={(e) => setCloseReason(e.target.value)}
                placeholder="Ej: Cliente no interesado / Recursos suspendidos / Duplicado..."
                rows={3}
                data-testid="close-reason-input"
              />
            </div>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={closing}>Cancelar</AlertDialogCancel>
              <AlertDialogAction
                disabled={closing || !closeReason.trim()}
                onClick={async () => {
                  setClosing(true);
                  try {
                    await api.post(`/initial-contacts/${closeContact.contact_id}/close`, { reason: closeReason.trim() });
                    toast.success('Gestión cerrada');
                    setCloseOpen(false);
                    setCloseContact(null);
                    setCloseReason('');
                    fetchData();
                  } catch (e) {
                    toast.error(e.response?.data?.detail || 'Error al cerrar gestión');
                  } finally { setClosing(false); }
                }}
                className="bg-blue-600 hover:bg-blue-700"
                data-testid="close-confirm-btn"
              >
                {closing ? 'Cerrando...' : 'Cerrar Gestión'}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Reabrir Gestión (todos los usuarios) */}
        <AlertDialog open={reopenOpen} onOpenChange={setReopenOpen}>
          <AlertDialogContent data-testid="reopen-gestion-dialog">
            <AlertDialogHeader>
              <AlertDialogTitle className="text-emerald-700 flex items-center gap-2">
                <RotateCcw size={18} /> Reabrir Gestión
              </AlertDialogTitle>
              <AlertDialogDescription>
                El contacto <strong>{reopenContact?.legal_name}</strong> volverá al estado <span className="font-semibold text-emerald-700">ACTIVO</span> y aparecerá nuevamente en la bandeja de gestión. Se registrará automáticamente en la bitácora.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="space-y-2 my-3">
              <Label className="text-xs">Nueva fecha límite (SLA reinicia en VERDE)</Label>
              <Input
                type="date"
                value={reopenDueDate}
                onChange={(e) => setReopenDueDate(e.target.value)}
                data-testid="reopen-due-date-input"
              />
              <p className="text-[11px] text-slate-400">Por defecto: hoy + 5 días. Puede ajustarla.</p>
              <Label className="text-xs mt-2">Motivo de reapertura (opcional)</Label>
              <Textarea
                value={reopenReason}
                onChange={(e) => setReopenReason(e.target.value)}
                placeholder="Ej: Cliente retomó interés / Llegó nueva información / Negociación reactivada..."
                rows={3}
                data-testid="reopen-reason-input"
              />
            </div>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={reopening}>Cancelar</AlertDialogCancel>
              <AlertDialogAction
                disabled={reopening}
                onClick={async () => {
                  setReopening(true);
                  try {
                    await api.post(`/initial-contacts/${reopenContact.contact_id}/reopen`, {
                      reason: reopenReason.trim(),
                      new_due_date: reopenDueDate || undefined,
                    });
                    toast.success('Gestión reabierta');
                    setReopenOpen(false);
                    setReopenContact(null);
                    setReopenReason('');
                    setReopenDueDate('');
                    fetchData();
                  } catch (e) {
                    toast.error(e.response?.data?.detail || 'Error al reabrir gestión');
                  } finally { setReopening(false); }
                }}
                className="bg-emerald-600 hover:bg-emerald-700"
                data-testid="reopen-confirm-btn"
              >
                {reopening ? 'Reabriendo...' : 'Reabrir Gestión'}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Delete confirmation (admin only) */}
        <AlertDialog open={!!deleteContact} onOpenChange={(o) => !o && setDeleteContact(null)}>
          <AlertDialogContent data-testid="ic-delete-dialog">
            <AlertDialogHeader>
              <AlertDialogTitle className="text-red-600">¿Eliminar contacto inicial?</AlertDialogTitle>
              <AlertDialogDescription>
                Se eliminará permanentemente el contacto{' '}
                <strong>{deleteContact?.legal_name || ''}</strong>
                {deleteContact?.rif ? <> (RIF {deleteContact.rif})</> : null}.
                <br/>
                <span className="text-amber-600">Esta acción no se puede deshacer.</span>
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={deleting} data-testid="ic-delete-cancel">Cancelar</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleDelete}
                disabled={deleting}
                className="bg-red-600 hover:bg-red-700"
                data-testid="ic-delete-confirm"
              >
                {deleting ? 'Eliminando...' : 'Eliminar'}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Notification Dialog */}
        <InitialContactEmailDialog
          open={notifyOpen}
          onClose={() => { setNotifyOpen(false); setNotifyContact(null); }}
          contact={notifyContact}
          onSent={fetchData}
        />
      </main>
    </div>
  );
};

export default InitialContacts;
