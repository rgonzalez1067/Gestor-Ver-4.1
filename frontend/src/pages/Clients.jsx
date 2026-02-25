import { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Textarea } from '../components/ui/textarea';
import { ImportResultPanel } from '../components/ImportResultPanel';
import { Plus, Pencil, Trash2, Upload, FileSpreadsheet, FileText, BookOpen, UserPlus, X, CheckCircle, Circle, Search, FileDown, AlertCircle, CheckCircle2 } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const SEGMENT_OPTIONS = ['Pymes', 'Corporativo', 'Mixto'];
const CONTACT_ROLES = ['Administrativo', 'Financiero', 'Técnico', 'Cuentas por Pagar', 'Operativo'];

const emptyContact = () => ({
  contact_id: '',
  first_name: '',
  last_name: '',
  phone: '',
  email: '',
  role: 'Administrativo'
});

export const Clients = () => {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingClient, setEditingClient] = useState(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deleteClientData, setDeleteClientData] = useState({ id: null, name: null });
  const [searchTerm, setSearchTerm] = useState('');

  // Bitácora
  const [logModalOpen, setLogModalOpen] = useState(false);
  const [logClientId, setLogClientId] = useState(null);
  const [logClientName, setLogClientName] = useState('');
  const [logs, setLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [newLog, setNewLog] = useState({ detail: '', action: '', follow_up_date: '' });

  // Import dialog
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [importFile, setImportFile] = useState(null);
  const [importLoading, setImportLoading] = useState(false);
  const [importResult, setImportResult] = useState(null);

  const [formData, setFormData] = useState({
    rif: '',
    legal_name: '',
    fantasy_name: '',
    segment: 'Pymes',
    address: '',
    sucursal: 'Principal',
    contacts: [emptyContact()]
  });

  const fileInputRef = useRef(null);
  const [importResult, setImportResult] = useState(null);
  const [showImportResult, setShowImportResult] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => { fetchClients(); }, []);

  // Handle deep-link from Dashboard alerts
  useEffect(() => {
    const bitacoraClientId = searchParams.get('bitacora');
    if (bitacoraClientId && clients.length > 0) {
      const client = clients.find(c => c.client_id === bitacoraClientId);
      if (client) {
        openBitacora(client);
        setSearchParams({});
      }
    }
  }, [clients, searchParams]);

  const fetchClients = async () => {
    try {
      const response = await api.get('/clients');
      setClients(response.data);
    } catch (error) {
      toast.error('Error al cargar clientes');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    // Migrate legacy contact1/contact2 to contacts array if needed
    const payload = { ...formData };
    // Ensure legacy fields for backwards compat
    if (payload.contacts?.length >= 1) {
      const c = payload.contacts[0];
      payload.contact1 = { name: `${c.first_name} ${c.last_name}`.trim(), phone: c.phone, email: c.email || 'n/a@n.com' };
    } else {
      payload.contact1 = { name: 'N/A', phone: 'N/A', email: 'na@na.com' };
    }
    if (payload.contacts?.length >= 2) {
      const c = payload.contacts[1];
      payload.contact2 = { name: `${c.first_name} ${c.last_name}`.trim(), phone: c.phone, email: c.email || 'n/a@n.com' };
    } else {
      payload.contact2 = { name: 'N/A', phone: 'N/A', email: 'na@na.com' };
    }

    try {
      if (editingClient) {
        await api.put(`/clients/${editingClient.client_id}`, payload);
        toast.success('Cliente actualizado exitosamente');
      } else {
        await api.post('/clients', payload);
        toast.success('Cliente creado exitosamente');
      }
      setDialogOpen(false);
      resetForm();
      fetchClients();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al guardar cliente');
    }
  };

  const handleDelete = async (clientId) => {
    const client = clients.find(c => c.client_id === clientId);
    setDeleteClientData({ id: clientId, name: client?.fantasy_name || client?.legal_name || 'este cliente' });
    setDeleteConfirmOpen(true);
  };

  const executeDelete = async () => {
    const clientId = deleteClientData.id;
    setDeleteConfirmOpen(false);
    if (!clientId) return;
    try {
      await api.delete(`/clients/${clientId}`);
      toast.success('Cliente eliminado exitosamente');
      fetchClients();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al eliminar cliente');
    } finally {
      setDeleteClientData({ id: null, name: null });
    }
  };

  const openEditDialog = (client) => {
    setEditingClient(client);
    // Migrate legacy contacts to new format
    let contacts = client.contacts || [];
    if (contacts.length === 0 && (client.contact1 || client.contact2)) {
      if (client.contact1?.name && client.contact1.name !== 'N/A') {
        const parts = client.contact1.name.split(' ');
        contacts.push({
          contact_id: '',
          first_name: parts[0] || '',
          last_name: parts.slice(1).join(' ') || '',
          phone: client.contact1.phone || '',
          email: client.contact1.email || '',
          role: 'Administrativo'
        });
      }
      if (client.contact2?.name && client.contact2.name !== 'N/A') {
        const parts = client.contact2.name.split(' ');
        contacts.push({
          contact_id: '',
          first_name: parts[0] || '',
          last_name: parts.slice(1).join(' ') || '',
          phone: client.contact2.phone || '',
          email: client.contact2.email || '',
          role: 'Financiero'
        });
      }
    }
    if (contacts.length === 0) contacts = [emptyContact()];

    setFormData({
      rif: client.rif,
      legal_name: client.legal_name,
      fantasy_name: client.fantasy_name,
      segment: client.segment || 'Pymes',
      address: client.address || '',
      sucursal: client.sucursal || 'Principal',
      contacts
    });
    setDialogOpen(true);
  };

  const resetForm = () => {
    setFormData({
      rif: '', legal_name: '', fantasy_name: '', segment: 'Pymes',
      address: '', sucursal: 'Principal', contacts: [emptyContact()]
    });
    setEditingClient(null);
  };

  const handleDialogClose = (open) => {
    setDialogOpen(open);
    if (!open) resetForm();
  };

  // --- Contacts array management ---
  const addContact = () => setFormData(prev => ({ ...prev, contacts: [...prev.contacts, emptyContact()] }));
  const removeContact = (idx) => setFormData(prev => ({ ...prev, contacts: prev.contacts.filter((_, i) => i !== idx) }));
  const updateContact = (idx, field, value) => {
    setFormData(prev => {
      const contacts = [...prev.contacts];
      contacts[idx] = { ...contacts[idx], [field]: value };
      return { ...prev, contacts };
    });
  };

  // --- Bitácora ---
  const openBitacora = async (client) => {
    setLogClientId(client.client_id);
    setLogClientName(client.fantasy_name || client.legal_name);
    setLogModalOpen(true);
    setLogsLoading(true);
    try {
      const res = await api.get(`/clients/${client.client_id}/logs`);
      setLogs(res.data);
    } catch { setLogs([]); }
    finally { setLogsLoading(false); }
  };

  const handleAddLog = async () => {
    if (!newLog.detail.trim()) { toast.error('El detalle es obligatorio'); return; }
    try {
      const res = await api.post(`/clients/${logClientId}/logs`, {
        client_id: logClientId,
        detail: newLog.detail,
        action: newLog.action,
        follow_up_date: newLog.follow_up_date || null
      });
      setLogs(prev => [res.data, ...prev]);
      setNewLog({ detail: '', action: '', follow_up_date: '' });
      toast.success('Entrada de bitácora registrada');
    } catch { toast.error('Error al registrar la entrada'); }
  };

  const toggleLogComplete = async (logId) => {
    try {
      const res = await api.patch(`/clients/logs/${logId}/complete`);
      setLogs(prev => prev.map(l => l.log_id === logId ? { ...l, is_completed: res.data.is_completed } : l));
    } catch { toast.error('Error al actualizar'); }
  };

  // --- Import/Export ---
  const downloadTemplate = async () => {
    try {
      const token = localStorage.getItem('session_token');
      const backendUrl = process.env.REACT_APP_BACKEND_URL;
      const response = await fetch(`${backendUrl}/api/clients/template`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!response.ok) throw new Error('Error al descargar plantilla');
      const blob = await response.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'plantilla_clientes.xlsx';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(a.href);
      toast.success('Plantilla descargada');
    } catch { toast.error('Error al descargar plantilla'); }
  };

  const handleImportFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) { setImportFile(file); setImportResult(null); }
  };

  const executeImport = async () => {
    if (!importFile) { toast.error('Seleccione un archivo'); return; }
    setImportLoading(true);
    setImportResult(null);
    try {
      const fd = new FormData();
      fd.append('file', importFile);
      const response = await api.post('/clients/import', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      setImportResult(response.data);
      if (response.data.status === 'success') { toast.success(response.data.message); fetchClients(); }
      else if (response.data.status === 'partial') { toast.warning(response.data.message); fetchClients(); }
      else toast.error(response.data.message);
    } catch (err) {
      toast.error('Error al importar archivo');
      setImportResult({ status: 'error', message: err.response?.data?.detail || 'Error desconocido', errors: [] });
    } finally { setImportLoading(false); }
  };

  const closeImportDialog = () => { setImportDialogOpen(false); setImportFile(null); setImportResult(null); };

  const handleFileImport = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    try {
      toast.loading('Procesando archivo...', { id: 'import-loading' });
      const response = await api.post('/clients/import', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      toast.dismiss('import-loading');
      if (response.data.status === 'success') toast.success(`${response.data.success_count} clientes importados`);
      else if (response.data.status === 'partial') toast.warning(`Parcial: ${response.data.success_count} OK, ${response.data.error_count} errores`);
      else toast.error(response.data.message || 'Error en la importación');
      fetchClients();
    } catch { toast.dismiss('import-loading'); toast.error('Error al importar'); }
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const exportToCSV = () => {
    const headers = ['RIF', 'Sucursal', 'Nombre Jurídico', 'Nombre Fantasía', 'Segmento'];
    const csvContent = [headers.join(','), ...clients.map(c => [
      `"${c.rif}"`, `"${c.sucursal || 'Principal'}"`, `"${c.legal_name}"`, `"${c.fantasy_name}"`, `"${c.segment || ''}"`
    ].join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = 'clientes.csv'; link.click();
    toast.success('CSV descargado');
  };

  const exportToPDF = async () => {
    try {
      const response = await api.get('/clients/export/pdf', { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a'); link.href = url; link.download = 'clientes.pdf'; link.click();
      toast.success('PDF descargado');
    } catch { toast.error('Error al exportar a PDF'); }
  };

  // Filtered clients
  const filtered = clients.filter(c => {
    if (!searchTerm) return true;
    const s = searchTerm.toLowerCase();
    return c.rif?.toLowerCase().includes(s) || c.legal_name?.toLowerCase().includes(s) ||
      c.fantasy_name?.toLowerCase().includes(s) || (c.sucursal || '').toLowerCase().includes(s);
  });

  if (loading) {
    return (
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center bg-white">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-green-600 mx-auto"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-white">
      <Sidebar />
      <main className="flex-1 p-8" data-testid="clients-page">
        <div className="max-w-7xl mx-auto">
          <div className="flex justify-between items-center mb-8">
            <div>
              <h1 className="text-4xl font-bold text-slate-900 font-manrope mb-2">Clientes</h1>
              <p className="text-slate-600">Gestione la información y seguimiento de sus clientes</p>
            </div>
            <div className="flex gap-2">
              <input type="file" ref={fileInputRef} onChange={handleFileImport} accept=".csv,.xlsx,.xls" className="hidden" />
              <Button variant="outline" onClick={() => setImportDialogOpen(true)} className="border-brand-blue-600 text-brand-blue-600" data-testid="import-clients-btn">
                <Upload size={18} className="mr-2" />Importar
              </Button>
              <Button variant="outline" onClick={exportToCSV} className="border-brand-green-600 text-brand-green-600">
                <FileSpreadsheet size={18} className="mr-2" />CSV
              </Button>
              <Button variant="outline" onClick={exportToPDF} className="border-brand-blue-600 text-brand-blue-600">
                <FileText size={18} className="mr-2" />PDF
              </Button>
              <Dialog open={dialogOpen} onOpenChange={handleDialogClose}>
                <DialogTrigger asChild>
                  <Button data-testid="add-client-button" className="bg-brand-green-600 hover:bg-brand-green-700 text-white">
                    <Plus size={20} className="mr-2" />Nuevo Cliente
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
                  <DialogHeader>
                    <DialogTitle className="font-manrope text-2xl">{editingClient ? 'Editar Cliente' : 'Nuevo Cliente'}</DialogTitle>
                  </DialogHeader>
                  <form onSubmit={handleSubmit} className="space-y-6">
                    {/* Datos del cliente */}
                    <div className="grid grid-cols-3 gap-4">
                      <div>
                        <Label htmlFor="rif">RIF</Label>
                        <Input id="rif" data-testid="client-rif-input" value={formData.rif}
                          onChange={(e) => setFormData({ ...formData, rif: e.target.value })} required />
                      </div>
                      <div>
                        <Label htmlFor="sucursal">Sucursal</Label>
                        <Input id="sucursal" data-testid="client-sucursal-input" value={formData.sucursal}
                          onChange={(e) => setFormData({ ...formData, sucursal: e.target.value })}
                          placeholder="Principal, Sede Norte, etc." required />
                      </div>
                      <div>
                        <Label htmlFor="segment">Segmento</Label>
                        <Select value={formData.segment} onValueChange={(value) => setFormData({ ...formData, segment: value })}>
                          <SelectTrigger data-testid="client-segment-select"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            {SEGMENT_OPTIONS.map((seg) => <SelectItem key={seg} value={seg}>{seg}</SelectItem>)}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label htmlFor="legal_name">Nombre Jurídico</Label>
                        <Input id="legal_name" data-testid="client-legal-name-input" value={formData.legal_name}
                          onChange={(e) => setFormData({ ...formData, legal_name: e.target.value })} required />
                      </div>
                      <div>
                        <Label htmlFor="fantasy_name">Nombre de Fantasía</Label>
                        <Input id="fantasy_name" data-testid="client-fantasy-name-input" value={formData.fantasy_name}
                          onChange={(e) => setFormData({ ...formData, fantasy_name: e.target.value })} required />
                      </div>
                    </div>
                    <div>
                      <Label htmlFor="address">Dirección Fiscal</Label>
                      <Input id="address" data-testid="client-address-input" value={formData.address}
                        onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                        placeholder="Av. Principal, Edificio X, Caracas" />
                    </div>

                    {/* Matriz de Contactos Dinámica */}
                    <div className="border-t pt-4">
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="font-semibold text-lg">Contactos</h3>
                        <Button type="button" size="sm" variant="outline" onClick={addContact} data-testid="add-contact-btn">
                          <UserPlus size={14} className="mr-1" />Agregar Contacto
                        </Button>
                      </div>
                      {formData.contacts.map((contact, idx) => (
                        <div key={idx} className="grid grid-cols-12 gap-2 mb-3 items-end p-3 bg-slate-50 rounded-lg border" data-testid={`contact-row-${idx}`}>
                          <div className="col-span-2">
                            <Label className="text-xs">Nombre</Label>
                            <Input value={contact.first_name} onChange={(e) => updateContact(idx, 'first_name', e.target.value)}
                              placeholder="Nombre" className="h-9 text-sm" required />
                          </div>
                          <div className="col-span-2">
                            <Label className="text-xs">Apellido</Label>
                            <Input value={contact.last_name} onChange={(e) => updateContact(idx, 'last_name', e.target.value)}
                              placeholder="Apellido" className="h-9 text-sm" />
                          </div>
                          <div className="col-span-2">
                            <Label className="text-xs">Teléfono</Label>
                            <Input value={contact.phone} onChange={(e) => updateContact(idx, 'phone', e.target.value)}
                              placeholder="0412..." className="h-9 text-sm" />
                          </div>
                          <div className="col-span-2">
                            <Label className="text-xs">Email</Label>
                            <Input value={contact.email} onChange={(e) => updateContact(idx, 'email', e.target.value)}
                              placeholder="email@..." className="h-9 text-sm" type="email" />
                          </div>
                          <div className="col-span-3">
                            <Label className="text-xs">Rol</Label>
                            <Select value={contact.role} onValueChange={(v) => updateContact(idx, 'role', v)}>
                              <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
                              <SelectContent>
                                {CONTACT_ROLES.map(r => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="col-span-1 flex justify-center">
                            {formData.contacts.length > 1 && (
                              <Button type="button" size="sm" variant="ghost" onClick={() => removeContact(idx)}
                                className="h-9 w-9 p-0 text-red-500 hover:text-red-700" data-testid={`remove-contact-${idx}`}>
                                <X size={16} />
                              </Button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className="flex justify-end gap-3">
                      <Button type="button" variant="outline" onClick={() => handleDialogClose(false)}>Cancelar</Button>
                      <Button type="submit" data-testid="save-client-button" className="bg-brand-green-600 hover:bg-brand-green-700 text-white">
                        {editingClient ? 'Actualizar' : 'Guardar'}
                      </Button>
                    </div>
                  </form>
                </DialogContent>
              </Dialog>
            </div>
          </div>

          {/* Search */}
          <div className="mb-4 max-w-sm relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <Input placeholder="Buscar por RIF, nombre o sucursal..." value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)} className="pl-9" data-testid="client-search" />
          </div>


          {/* Table */}
          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">RIF</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Sucursal</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Nombre Jurídico</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Nombre Fantasía</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Segmento</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Contacto Principal</th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-slate-600 uppercase">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.map((client) => {
                  const mainContact = client.contacts?.[0] || null;
                  const legacyContact = client.contact1;
                  return (
                    <tr key={client.client_id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-4 py-3 text-sm font-mono text-slate-700">{client.rif}</td>
                      <td className="px-4 py-3 text-sm text-slate-600">{client.sucursal || 'Principal'}</td>
                      <td className="px-4 py-3 text-sm font-medium text-slate-900">{client.legal_name}</td>
                      <td className="px-4 py-3 text-sm text-slate-600">{client.fantasy_name}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-block px-2 py-0.5 text-xs font-medium rounded ${
                          client.segment === 'Corporativo' ? 'bg-purple-100 text-purple-700' :
                          client.segment === 'Pymes' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                        }`}>{client.segment || 'N/A'}</span>
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-600">
                        {mainContact ? (
                          <div>
                            <p className="font-medium">{mainContact.first_name} {mainContact.last_name}</p>
                            <p className="text-xs text-slate-400">{mainContact.role} · {mainContact.phone}</p>
                          </div>
                        ) : legacyContact ? (
                          <div>
                            <p className="font-medium">{legacyContact.name}</p>
                            <p className="text-xs text-slate-400">{legacyContact.email}</p>
                          </div>
                        ) : <span className="text-slate-400">—</span>}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-center gap-1">
                          <Button size="sm" variant="outline" onClick={() => openBitacora(client)}
                            data-testid={`bitacora-client-${client.client_id}`} className="text-blue-600 h-8 px-2">
                            <BookOpen size={14} className="mr-1" />Bitácora
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => openEditDialog(client)}
                            data-testid={`edit-client-${client.client_id}`} className="h-8 w-8 p-0">
                            <Pencil size={14} />
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => handleDelete(client.client_id)}
                            data-testid={`delete-client-${client.client_id}`} className="h-8 w-8 p-0 text-red-600 hover:text-red-700 hover:border-red-300">
                            <Trash2 size={14} />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {filtered.length === 0 && (
              <div className="text-center py-12 text-slate-500">
                <p>{searchTerm ? 'No se encontraron clientes con ese criterio' : 'No hay clientes registrados'}</p>
              </div>
            )}
          </div>
        </div>

        {/* Delete confirmation */}
        <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>¿Eliminar Cliente?</AlertDialogTitle>
              <AlertDialogDescription>
                ¿Está seguro de que desea eliminar el cliente <strong>"{deleteClientData.name}"</strong>?
                <br /><br />
                <span className="text-red-600 font-medium">Esta acción es irreversible.</span>
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancelar</AlertDialogCancel>
              <AlertDialogAction onClick={executeDelete} className="bg-red-600 hover:bg-red-700 text-white">Eliminar</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Bitácora Modal */}
        <Dialog open={logModalOpen} onOpenChange={(v) => { if (!v) { setLogModalOpen(false); setLogClientId(null); } }}>
          <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="bitacora-modal">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-lg">
                <BookOpen size={20} className="text-blue-600" />
                Bitácora — {logClientName}
              </DialogTitle>
            </DialogHeader>

            {/* New log entry form */}
            <div className="bg-slate-50 rounded-lg border p-4 space-y-3">
              <h4 className="text-sm font-semibold text-slate-700">Nueva entrada</h4>
              <div>
                <Label className="text-xs">Detalle del contacto *</Label>
                <Textarea value={newLog.detail} onChange={(e) => setNewLog(p => ({ ...p, detail: e.target.value }))}
                  placeholder="Resumen de la interacción con el cliente..." rows={2} data-testid="log-detail-input" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs">Acción resultante</Label>
                  <Input value={newLog.action} onChange={(e) => setNewLog(p => ({ ...p, action: e.target.value }))}
                    placeholder="Ej: Llamar para confirmar recepción" data-testid="log-action-input" />
                </div>
                <div>
                  <Label className="text-xs">Fecha de seguimiento</Label>
                  <Input type="date" value={newLog.follow_up_date} onChange={(e) => setNewLog(p => ({ ...p, follow_up_date: e.target.value }))}
                    data-testid="log-followup-input" />
                </div>
              </div>
              <Button size="sm" onClick={handleAddLog} className="bg-blue-600 hover:bg-blue-700" data-testid="log-submit-btn">
                <Plus size={14} className="mr-1" />Registrar
              </Button>
            </div>

            {/* Log entries */}
            <div className="mt-4 space-y-2">
              {logsLoading ? (
                <div className="text-center py-8 text-slate-400">Cargando bitácora...</div>
              ) : logs.length === 0 ? (
                <div className="text-center py-8 text-slate-400">No hay entradas en la bitácora</div>
              ) : (
                logs.map(log => {
                  const isOverdue = log.follow_up_date && !log.is_completed && log.follow_up_date < new Date().toISOString().split('T')[0];
                  return (
                    <div key={log.log_id} className={`p-3 rounded-lg border ${log.is_completed ? 'bg-green-50/50 border-green-200' : isOverdue ? 'bg-red-50/50 border-red-200' : 'bg-white border-slate-200'}`}
                      data-testid={`log-entry-${log.log_id}`}>
                      <div className="flex items-start gap-2">
                        <button onClick={() => toggleLogComplete(log.log_id)} className="mt-0.5 shrink-0"
                          data-testid={`log-toggle-${log.log_id}`}>
                          {log.is_completed
                            ? <CheckCircle size={16} className="text-green-600" />
                            : <Circle size={16} className={isOverdue ? 'text-red-400' : 'text-slate-300'} />}
                        </button>
                        <div className="flex-1 min-w-0">
                          <p className={`text-sm ${log.is_completed ? 'line-through text-slate-400' : 'text-slate-800'}`}>{log.detail}</p>
                          {log.action && (
                            <p className="text-xs text-blue-600 mt-1 font-medium">Acción: {log.action}</p>
                          )}
                          <div className="flex items-center gap-3 mt-1.5 text-xs text-slate-400">
                            <span>Contacto: {log.contact_date}</span>
                            {log.follow_up_date && (
                              <span className={`px-1.5 py-0.5 rounded ${isOverdue && !log.is_completed ? 'bg-red-100 text-red-600 font-medium' : 'bg-slate-100'}`}>
                                Seguimiento: {log.follow_up_date}
                              </span>
                            )}
                            <span>Por: {log.created_by_name || log.created_by}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
};
