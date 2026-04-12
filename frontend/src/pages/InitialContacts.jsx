import { useState, useEffect } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Plus, Phone, Mail, Building2, User, Search, MessageSquare, UserPlus, ArrowRightLeft, Rocket, Clock, ChevronDown, ChevronUp, Filter } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

export const InitialContacts = () => {
  const [contacts, setContacts] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [currentUser, setCurrentUser] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterSede, setFilterSede] = useState('all');

  // Create modal
  const [createOpen, setCreateOpen] = useState(false);
  const [formData, setFormData] = useState({ contact_name: '', phone: '', email: '', legal_name: '' });

  // Action modals
  const [documentOpen, setDocumentOpen] = useState(false);
  const [documentContact, setDocumentContact] = useState(null);
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

  // Bitacora viewer
  const [bitacoraOpen, setBitacoraOpen] = useState(false);
  const [bitacoraContact, setBitacoraContact] = useState(null);

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
    if (!formData.contact_name || !formData.phone || !formData.email || !formData.legal_name) {
      toast.error('Todos los campos son obligatorios'); return;
    }
    try {
      await api.post('/initial-contacts', formData);
      toast.success('Contacto inicial creado');
      setCreateOpen(false);
      setFormData({ contact_name: '', phone: '', email: '', legal_name: '' });
      fetchData();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al crear contacto'); }
  };

  const handleDocument = async () => {
    if (!documentComment.trim()) { toast.error('Escriba un comentario'); return; }
    try {
      await api.post(`/initial-contacts/${documentContact.contact_id}/document`, { comment: documentComment });
      toast.success('Gestion documentada');
      setDocumentOpen(false);
      setDocumentComment('');
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

  const canAssign = currentUser?.role === 'admin' || ['Director', 'Gerente', 'Coordinador'].includes(currentUser?.cargo);
  const canTransfer = currentUser?.role === 'admin' || ['Director', 'Gerente'].includes(currentUser?.cargo);

  // Filter users for assignment based on hierarchy
  const assignableUsers = users.filter(u => {
    if (!currentUser) return false;
    if (currentUser.role === 'admin') return u.user_id !== currentUser.user_id;
    const allowed = { Director: ['Gerente'], Gerente: ['Coordinador', 'Ejecutivo'], Coordinador: ['Ejecutivo'] };
    return (allowed[currentUser.cargo] || []).includes(u.cargo) && u.is_active !== false;
  });

  // Filter users for transfer (only Gerentes from other sede)
  const transferableUsers = users.filter(u => {
    if (!currentUser) return false;
    return u.cargo === 'Gerente' && u.user_id !== currentUser.user_id && u.is_active !== false;
  });

  const filtered = contacts.filter(c => {
    const q = searchTerm.toLowerCase();
    const matchSearch = !q || c.contact_name?.toLowerCase().includes(q) || c.legal_name?.toLowerCase().includes(q) || c.email?.toLowerCase().includes(q) || c.phone?.includes(q);
    const matchSede = filterSede === 'all' || c.sede === filterSede;
    return matchSearch && matchSede;
  });

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
          <div className="bg-slate-100 px-3 py-1.5 rounded-md text-sm text-slate-600">
            <span className="font-semibold">{filtered.length}</span> contacto(s)
          </div>
        </div>

        {/* Table */}
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full" data-testid="contacts-table">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Contacto</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Razon Social</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Telefono / Email</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Asignado a</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Sede</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Fecha</th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-slate-600 uppercase">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loading ? (
                  <tr><td colSpan={7} className="px-4 py-12 text-center text-slate-400">Cargando...</td></tr>
                ) : filtered.length === 0 ? (
                  <tr><td colSpan={7} className="px-4 py-12 text-center text-slate-400">No hay contactos iniciales</td></tr>
                ) : filtered.map((c) => (
                  <tr key={c.contact_id} className="hover:bg-slate-50 group" data-testid={`contact-row-${c.contact_id}`}>
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
                      <div className="text-xs text-slate-600">{c.phone}</div>
                      <div className="text-xs text-slate-400">{c.email}</div>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-700">{c.assigned_to_name || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 text-xs font-medium rounded ${c.sede === 'CORP' ? 'bg-blue-100 text-blue-700' : 'bg-emerald-100 text-emerald-700'}`}>
                        {c.sede}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">{formatDate(c.created_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-1">
                        <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-slate-500 hover:text-blue-600" title="Documentar" data-testid={`doc-btn-${c.contact_id}`}
                          onClick={() => { setDocumentContact(c); setDocumentComment(''); setDocumentOpen(true); }}>
                          <MessageSquare size={14} />
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
                        <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-slate-500 hover:text-green-600" title="Convertir a Prospecto" data-testid={`convert-btn-${c.contact_id}`}
                          onClick={() => { setConvertContact(c); setConvertConfirmOpen(true); }}>
                          <Rocket size={14} />
                        </Button>
                        <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-slate-400 hover:text-slate-600" title="Ver Bitacora"
                          onClick={() => { setBitacoraContact(c); setBitacoraOpen(true); }}>
                          <Clock size={14} />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Create Modal */}
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogContent className="max-w-md" data-testid="create-contact-modal">
            <DialogHeader><DialogTitle className="flex items-center gap-2"><Phone size={20} className="text-green-600" /> Nuevo Contacto Inicial</DialogTitle></DialogHeader>
            <form onSubmit={handleCreate} className="space-y-4 pt-2">
              <div>
                <Label>Nombre del Contacto *</Label>
                <Input value={formData.contact_name} onChange={(e) => setFormData({ ...formData, contact_name: e.target.value })} placeholder="Persona que atiende" required data-testid="input-contact-name" />
              </div>
              <div>
                <Label>Telefono *</Label>
                <Input value={formData.phone} onChange={(e) => setFormData({ ...formData, phone: e.target.value })} placeholder="+58 412 1234567" required data-testid="input-phone" />
              </div>
              <div>
                <Label>Email *</Label>
                <Input type="email" value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })} placeholder="correo@empresa.com" required data-testid="input-email" />
              </div>
              <div>
                <Label>Nombre Juridico (Razon Social) *</Label>
                <Input value={formData.legal_name} onChange={(e) => setFormData({ ...formData, legal_name: e.target.value })} placeholder="Razon social tentativa" required data-testid="input-legal-name" />
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

        {/* Bitacora Modal */}
        <Dialog open={bitacoraOpen} onOpenChange={setBitacoraOpen}>
          <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
            <DialogHeader><DialogTitle className="flex items-center gap-2"><Clock size={20} className="text-slate-600" /> Bitacora: {bitacoraContact?.legal_name}</DialogTitle></DialogHeader>
            <div className="space-y-3">
              {(bitacoraContact?.bitacora || []).slice().reverse().map((entry) => (
                <div key={entry.entry_id} className="flex gap-3 p-3 bg-slate-50 rounded-lg border border-slate-100">
                  <div className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${
                    entry.action === 'created' ? 'bg-green-500' :
                    entry.action === 'assigned' ? 'bg-amber-500' :
                    entry.action === 'transferred' ? 'bg-purple-500' :
                    entry.action === 'converted' ? 'bg-blue-500' : 'bg-slate-400'
                  }`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-slate-700">{entry.description}</p>
                    <p className="text-xs text-slate-400 mt-1">{formatDate(entry.timestamp)} - {entry.user_name}</p>
                  </div>
                </div>
              ))}
              {(!bitacoraContact?.bitacora || bitacoraContact.bitacora.length === 0) && (
                <p className="text-sm text-slate-400 text-center py-4">Sin registros en bitacora</p>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
};

export default InitialContacts;
