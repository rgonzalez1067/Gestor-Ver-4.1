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
import { Plus, Pencil, Trash2, Upload, FileSpreadsheet, FileText, BookOpen, UserPlus, X, CheckCircle, Circle, Search, FileDown, AlertCircle, CheckCircle2, ScanLine, FileUp, Download, ArrowRight, RefreshCw } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const SEGMENT_OPTIONS = ['Pymes', 'Corporativo', 'Mixto'];
const CONTACT_ROLES = ['Administrativo', 'Financiero', 'Técnico', 'Cuentas por Pagar', 'Operativo'];
const CATEGORIAS_COMERCIALES = [
  'Supermercados', 'Abastos', 'Restaurantes', 'Panaderías', 'Bares', 'Discotecas',
  'Comida Rápida', 'Cafeterías', 'Tiendas de Ropa', 'Boutique', 'Salón de Belleza',
  'Barbería', 'Spa/Salud', 'Gimnasios', 'Cosmética', 'Tiendas de Calzados',
  'Mueblerías', 'Ferretería', 'Tiendas de Electrodomésticos', 'Jardinería',
  'Joyerías', 'Tienda de Electrónica', 'Venta de Software', 'Jugueterías',
  'Librerías', 'Tiendas por Departamento', 'Colegios', 'Universidades',
  'Inmobiliarias', 'Clínicas',
];

const emptyContact = () => ({
  contact_id: '',
  full_name: '',
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
  const [logClientContacts, setLogClientContacts] = useState([]);
  const [logs, setLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [newLog, setNewLog] = useState({ detail: '', action: '', follow_up_date: '', contacted_person: '' });

  // Import dialog
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [importFile, setImportFile] = useState(null);
  const [importLoading, setImportLoading] = useState(false);
  const [importResult, setImportResult] = useState(null);

  // RIF Digital parsing
  const [rifDialogOpen, setRifDialogOpen] = useState(false);
  const [rifFile, setRifFile] = useState(null);
  const [rifParsing, setRifParsing] = useState(false);
  const [rifProgress, setRifProgress] = useState(0);
  const [rifResult, setRifResult] = useState(null);
  const [rifHighlightFields, setRifHighlightFields] = useState(new Set());
  const rifFileInputRef = useRef(null);

  // Update RIF for existing client
  const [updateRifDialogOpen, setUpdateRifDialogOpen] = useState(false);
  const [updateRifClient, setUpdateRifClient] = useState(null);
  const [updateRifFile, setUpdateRifFile] = useState(null);
  const [updateRifLoading, setUpdateRifLoading] = useState(false);
  const [updateRifProgress, setUpdateRifProgress] = useState(0);
  const [updateRifResult, setUpdateRifResult] = useState(null);
  const updateRifFileInputRef = useRef(null);

  const [formData, setFormData] = useState({
    rif: '',
    legal_name: '',
    fantasy_name: '',
    segment: 'Pymes',
    address: '',
    branch_address: '',
    categoria_comercial: '',
    sucursal: 'Principal',
    contacts: [emptyContact()]
  });

  const fileInputRef = useRef(null);
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
      payload.contact1 = { name: c.full_name || `${c.first_name || ''} ${c.last_name || ''}`.trim(), phone: c.phone, email: c.email || 'n/a@n.com' };
    } else {
      payload.contact1 = { name: 'N/A', phone: 'N/A', email: 'na@na.com' };
    }
    if (payload.contacts?.length >= 2) {
      const c = payload.contacts[1];
      payload.contact2 = { name: c.full_name || `${c.first_name || ''} ${c.last_name || ''}`.trim(), phone: c.phone, email: c.email || 'n/a@n.com' };
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
        contacts.push({
          contact_id: '',
          full_name: client.contact1.name,
          phone: client.contact1.phone || '',
          email: client.contact1.email || '',
          role: 'Administrativo'
        });
      }
      if (client.contact2?.name && client.contact2.name !== 'N/A') {
        contacts.push({
          contact_id: '',
          full_name: client.contact2.name,
          phone: client.contact2.phone || '',
          email: client.contact2.email || '',
          role: 'Financiero'
        });
      }
    }
    // Migrate old first_name/last_name to full_name
    contacts = contacts.map(c => ({
      ...c,
      full_name: c.full_name || `${c.first_name || ''} ${c.last_name || ''}`.trim() || ''
    }));
    if (contacts.length === 0) contacts = [emptyContact()];

    setFormData({
      rif: client.rif,
      legal_name: client.legal_name,
      fantasy_name: client.fantasy_name,
      segment: client.segment || 'Pymes',
      address: client.address || '',
      branch_address: client.branch_address || '',
      categoria_comercial: client.categoria_comercial || '',
      sucursal: client.sucursal || 'Principal',
      contacts
    });
    setDialogOpen(true);
  };

  const resetForm = () => {
    setFormData({
      rif: '', legal_name: '', fantasy_name: '', segment: 'Pymes',
      address: '', branch_address: '', categoria_comercial: '', sucursal: 'Principal', contacts: [emptyContact()]
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
    const contacts = (client.contacts || []).map(c => {
      const name = c.full_name || `${c.first_name || ''} ${c.last_name || ''}`.trim();
      return { id: c.contact_id, name, role: c.role || '' };
    });
    setLogClientContacts(contacts);
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
        follow_up_date: newLog.follow_up_date || null,
        contacted_person: newLog.contacted_person || null
      });
      setLogs(prev => [res.data, ...prev]);
      setNewLog({ detail: '', action: '', follow_up_date: '', contacted_person: '' });
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

  // --- RIF Digital parsing ---
  const handleRifFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      setRifFile(file);
      setRifResult(null);
    }
  };

  const executeRifParse = async () => {
    if (!rifFile) { toast.error('Seleccione un archivo PDF'); return; }
    setRifParsing(true);
    setRifProgress(0);
    setRifResult(null);

    // Simular barra de progreso
    const progressInterval = setInterval(() => {
      setRifProgress(prev => prev < 85 ? prev + Math.random() * 15 : prev);
    }, 200);

    try {
      const fd = new FormData();
      fd.append('file', rifFile);
      const response = await api.post('/clients/parse-rif', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      clearInterval(progressInterval);
      setRifProgress(100);
      setRifResult(response.data);
    } catch (err) {
      clearInterval(progressInterval);
      setRifProgress(0);
      toast.error(err.response?.data?.detail || 'Error al procesar el RIF Digital');
    } finally {
      setRifParsing(false);
    }
  };

  const applyRifDataToForm = (addBranch = false) => {
    if (!rifResult) return;
    const highlighted = new Set();

    const newData = {
      rif: rifResult.rif || '',
      legal_name: rifResult.legal_name || '',
      fantasy_name: rifResult.legal_name || '',
      segment: 'Pymes',
      address: rifResult.address || '',
      branch_address: '',
      categoria_comercial: '',
      sucursal: addBranch ? '' : 'Principal',
      contacts: [emptyContact()]
    };

    if (newData.rif) highlighted.add('rif');
    if (newData.legal_name) highlighted.add('legal_name');
    if (newData.fantasy_name) highlighted.add('fantasy_name');
    if (newData.address) highlighted.add('address');

    setRifHighlightFields(highlighted);
    setFormData(newData);
    setEditingClient(null);
    setRifDialogOpen(false);
    setRifFile(null);
    setRifResult(null);
    setRifProgress(0);
    setDialogOpen(true);

    if (addBranch) {
      toast.info('Complete el nombre de la sucursal para este cliente existente');
    } else {
      toast.success('Datos extraídos del RIF. Verifique y complete los campos antes de guardar.');
    }
  };

  const closeRifDialog = () => {
    setRifDialogOpen(false);
    setRifFile(null);
    setRifResult(null);
    setRifProgress(0);
    if (rifFileInputRef.current) rifFileInputRef.current.value = '';
  };

  // --- Update RIF for existing client ---
  const openUpdateRifDialog = (client) => {
    setUpdateRifClient(client);
    setUpdateRifFile(null);
    setUpdateRifResult(null);
    setUpdateRifProgress(0);
    setUpdateRifDialogOpen(true);
  };

  const executeUpdateRif = async () => {
    if (!updateRifFile || !updateRifClient) return;
    setUpdateRifLoading(true);
    setUpdateRifProgress(0);
    setUpdateRifResult(null);

    const progressInterval = setInterval(() => {
      setUpdateRifProgress(prev => prev < 85 ? prev + Math.random() * 15 : prev);
    }, 200);

    try {
      const fd = new FormData();
      fd.append('file', updateRifFile);
      const response = await api.post(`/clients/${updateRifClient.client_id}/update-from-rif`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      clearInterval(progressInterval);
      setUpdateRifProgress(100);
      setUpdateRifResult(response.data);
      toast.success('Cliente actualizado exitosamente desde RIF');
      fetchClients();
    } catch (err) {
      clearInterval(progressInterval);
      setUpdateRifProgress(0);
      toast.error(err.response?.data?.detail || 'Error al procesar el RIF');
    } finally {
      setUpdateRifLoading(false);
    }
  };

  const closeUpdateRifDialog = () => {
    setUpdateRifDialogOpen(false);
    setUpdateRifClient(null);
    setUpdateRifFile(null);
    setUpdateRifResult(null);
    setUpdateRifProgress(0);
    if (updateRifFileInputRef.current) updateRifFileInputRef.current.value = '';
  };

  const downloadRifDocument = async (client) => {
    try {
      const token = localStorage.getItem('session_token');
      const backendUrl = process.env.REACT_APP_BACKEND_URL;
      const response = await fetch(`${backendUrl}/api/clients/${client.client_id}/rif-document`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Error al descargar');
      }
      const blob = await response.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = client.rif_document_filename || `RIF_${client.rif}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(a.href);
      toast.success('Documento RIF descargado');
    } catch (err) {
      toast.error(err.message || 'Error al descargar el documento RIF');
    }
  };

  // Limpiar highlight al guardar
  const handleSubmitWithHighlight = async (e) => {
    await handleSubmit(e);
    setRifHighlightFields(new Set());
  };

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
              <Button variant="outline" onClick={() => setRifDialogOpen(true)} className="border-amber-500 text-amber-600 hover:bg-amber-50" data-testid="load-rif-btn">
                <ScanLine size={18} className="mr-2" />Cargar desde RIF Digital
              </Button>
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
                  <form onSubmit={handleSubmitWithHighlight} className="space-y-6">
                    {/* Banner de campos auto-completados */}
                    {rifHighlightFields.size > 0 && (
                      <div className="flex items-center gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg" data-testid="rif-auto-fill-banner">
                        <ScanLine size={18} className="text-amber-600 shrink-0" />
                        <p className="text-sm text-amber-800">
                          Los campos resaltados en <span className="font-semibold text-amber-700">amarillo</span> fueron extraídos automáticamente del RIF Digital. Verifique antes de guardar.
                        </p>
                      </div>
                    )}
                    {/* Datos del cliente */}
                    <div className="grid grid-cols-3 gap-4">
                      <div>
                        <Label htmlFor="rif">RIF</Label>
                        <Input id="rif" data-testid="client-rif-input" value={formData.rif}
                          onChange={(e) => { setFormData({ ...formData, rif: e.target.value }); setRifHighlightFields(prev => { const n = new Set(prev); n.delete('rif'); return n; }); }}
                          className={rifHighlightFields.has('rif') ? 'bg-amber-50 border-amber-300 ring-1 ring-amber-200' : ''} required />
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
                          onChange={(e) => { setFormData({ ...formData, legal_name: e.target.value }); setRifHighlightFields(prev => { const n = new Set(prev); n.delete('legal_name'); return n; }); }}
                          className={rifHighlightFields.has('legal_name') ? 'bg-amber-50 border-amber-300 ring-1 ring-amber-200' : ''} required />
                      </div>
                      <div>
                        <Label htmlFor="fantasy_name">Nombre de Fantasía</Label>
                        <Input id="fantasy_name" data-testid="client-fantasy-name-input" value={formData.fantasy_name}
                          onChange={(e) => { setFormData({ ...formData, fantasy_name: e.target.value }); setRifHighlightFields(prev => { const n = new Set(prev); n.delete('fantasy_name'); return n; }); }}
                          className={rifHighlightFields.has('fantasy_name') ? 'bg-amber-50 border-amber-300 ring-1 ring-amber-200' : ''} required />
                      </div>
                    </div>
                    <div>
                      <Label htmlFor="address">Dirección Fiscal</Label>
                      <Input id="address" data-testid="client-address-input" value={formData.address}
                        onChange={(e) => { setFormData({ ...formData, address: e.target.value }); setRifHighlightFields(prev => { const n = new Set(prev); n.delete('address'); return n; }); }}
                        className={rifHighlightFields.has('address') ? 'bg-amber-50 border-amber-300 ring-1 ring-amber-200' : ''}
                        placeholder="Av. Principal, Edificio X, Caracas" />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label htmlFor="branch_address">Dirección de la Sucursal</Label>
                        <Input id="branch_address" data-testid="client-branch-address-input" value={formData.branch_address}
                          onChange={(e) => setFormData({ ...formData, branch_address: e.target.value })}
                          placeholder="Dirección física de la sucursal" />
                      </div>
                      <div>
                        <Label htmlFor="categoria_comercial">Categoría Comercial</Label>
                        <Select value={formData.categoria_comercial || '_none_'} onValueChange={(v) => setFormData({ ...formData, categoria_comercial: v === '_none_' ? '' : v })}>
                          <SelectTrigger data-testid="client-categoria-select"><SelectValue placeholder="Seleccionar..." /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="_none_">Seleccionar...</SelectItem>
                            {CATEGORIAS_COMERCIALES.map(cat => <SelectItem key={cat} value={cat}>{cat}</SelectItem>)}
                          </SelectContent>
                        </Select>
                      </div>
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
                          <div className="col-span-3">
                            <Label className="text-xs">Nombre y Apellidos</Label>
                            <Input value={contact.full_name} onChange={(e) => updateContact(idx, 'full_name', e.target.value)}
                              placeholder="Nombre completo" className="h-9 text-sm" data-testid={`contact-full-name-${idx}`} required />
                          </div>
                          <div className="col-span-2">
                            <Label className="text-xs">Teléfono</Label>
                            <Input value={contact.phone} onChange={(e) => updateContact(idx, 'phone', e.target.value)}
                              placeholder="0412..." className="h-9 text-sm" />
                          </div>
                          <div className="col-span-3">
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
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Categoría</th>
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
                      <td className="px-4 py-3 text-sm text-slate-600">{client.categoria_comercial || '—'}</td>
                      <td className="px-4 py-3 text-sm text-slate-600">
                        {mainContact ? (
                          <div>
                            <p className="font-medium">{mainContact.full_name || `${mainContact.first_name || ''} ${mainContact.last_name || ''}`.trim() || '—'}</p>
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
                          <Button size="sm" variant="outline" onClick={() => openUpdateRifDialog(client)}
                            data-testid={`update-rif-client-${client.client_id}`} className="text-amber-600 h-8 px-2" title="Escanear RIF">
                            <ScanLine size={14} />
                          </Button>
                          {client.rif_document_url && (
                            <Button size="sm" variant="outline" onClick={() => downloadRifDocument(client)}
                              data-testid={`download-rif-client-${client.client_id}`} className="text-green-600 h-8 px-2" title="Descargar RIF">
                              <Download size={14} />
                            </Button>
                          )}
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

        {/* Import Dialog */}
        <Dialog open={importDialogOpen} onOpenChange={closeImportDialog}>
          <DialogContent className="max-w-2xl" data-testid="import-clients-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Upload className="text-brand-blue-600" size={20} />
                Importar Clientes
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-sm text-blue-800 mb-2"><strong>Instrucciones:</strong></p>
                <ol className="text-sm text-blue-700 list-decimal list-inside space-y-1">
                  <li>Descargue la plantilla de ejemplo con las columnas requeridas</li>
                  <li>Complete los datos en el archivo Excel/CSV</li>
                  <li>La llave única es <strong>RIF + Sucursal</strong> (se permite duplicar RIF si la sucursal es distinta)</li>
                  <li>Cargue el archivo completado</li>
                </ol>
                <Button variant="outline" size="sm" onClick={downloadTemplate}
                  className="mt-3 text-blue-700 border-blue-300 hover:bg-blue-100" data-testid="download-client-template-btn">
                  <FileDown size={16} className="mr-2" />Descargar Plantilla
                </Button>
              </div>
              <div>
                <Label>Archivo a importar (Excel o CSV)</Label>
                <div className="mt-2 flex items-center gap-3">
                  <Input type="file" accept=".xlsx,.xls,.csv" onChange={handleImportFileChange}
                    className="flex-1" data-testid="import-client-file-input" />
                </div>
                {importFile && (
                  <p className="text-sm text-slate-600 mt-2">Archivo seleccionado: <strong>{importFile.name}</strong></p>
                )}
              </div>
              {importResult && (
                <div className={`rounded-lg p-4 ${
                  importResult.status === 'success' ? 'bg-green-50 border border-green-200' :
                  importResult.status === 'partial' ? 'bg-amber-50 border border-amber-200' :
                  'bg-red-50 border border-red-200'
                }`}>
                  <div className="flex items-center gap-2 mb-2">
                    {importResult.status === 'success' ? <CheckCircle2 className="text-green-600" size={20} /> :
                     importResult.status === 'partial' ? <AlertCircle className="text-amber-600" size={20} /> :
                     <X className="text-red-600" size={20} />}
                    <span className={`font-medium ${
                      importResult.status === 'success' ? 'text-green-800' :
                      importResult.status === 'partial' ? 'text-amber-800' : 'text-red-800'
                    }`}>{importResult.message}</span>
                  </div>
                  {importResult.errors?.length > 0 && (
                    <div className="mt-3 max-h-40 overflow-y-auto">
                      <p className="text-sm font-medium text-slate-700 mb-2">Errores encontrados:</p>
                      <ul className="text-sm space-y-1">
                        {importResult.errors.slice(0, 10).map((err, idx) => (
                          <li key={idx} className="text-red-700">Fila {err.row}: {err.message} ({err.column})</li>
                        ))}
                        {importResult.errors.length > 10 && (
                          <li className="text-slate-500 italic">... y {importResult.errors.length - 10} errores más</li>
                        )}
                      </ul>
                    </div>
                  )}
                </div>
              )}
              <div className="flex justify-end gap-3 pt-2 border-t">
                <Button variant="outline" onClick={closeImportDialog}>Cerrar</Button>
                <Button onClick={executeImport} disabled={!importFile || importLoading}
                  className="bg-brand-blue-600 hover:bg-brand-blue-700 text-white" data-testid="execute-client-import-btn">
                  {importLoading ? (
                    <><div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />Importando...</>
                  ) : (
                    <><Upload size={16} className="mr-2" />Importar</>
                  )}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* Delete confirmation */}
        <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>

        {/* RIF Digital Dialog */}
        <Dialog open={rifDialogOpen} onOpenChange={closeRifDialog}>
          <DialogContent className="max-w-lg" data-testid="rif-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <ScanLine className="text-amber-500" size={22} />
                Cargar desde RIF Digital
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                <p className="text-sm text-amber-800 mb-1"><strong>Instrucciones:</strong></p>
                <p className="text-sm text-amber-700">Suba el archivo del RIF Digital emitido por el SENIAT (PDF, JPG o PNG). El sistema extraerá automáticamente el <strong>RIF</strong>, la <strong>Razón Social</strong> y la <strong>Dirección Fiscal</strong>.</p>
              </div>

              <div>
                <Label>Archivo RIF Digital (PDF, JPG, PNG)</Label>
                <div className="mt-2">
                  <Input ref={rifFileInputRef} type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={handleRifFileSelect}
                    data-testid="rif-file-input" />
                </div>
                {rifFile && <p className="text-sm text-slate-600 mt-1">Archivo: <strong>{rifFile.name}</strong></p>}
              </div>

              {/* Barra de progreso */}
              {rifParsing && (
                <div className="space-y-2" data-testid="rif-progress">
                  <div className="flex items-center gap-2">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-amber-600" />
                    <span className="text-sm text-amber-700 font-medium">Escaneando documento...</span>
                  </div>
                  <div className="w-full bg-amber-100 rounded-full h-2.5">
                    <div className="bg-amber-500 h-2.5 rounded-full transition-all duration-300" style={{ width: `${rifProgress}%` }} />
                  </div>
                </div>
              )}

              {/* Resultado */}
              {rifResult && (
                <div className="space-y-3" data-testid="rif-result">
                  <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <CheckCircle2 size={18} className="text-green-600" />
                      <span className="font-medium text-green-800">Datos extraídos exitosamente</span>
                    </div>
                    <div className="space-y-2 text-sm">
                      <div className="flex"><span className="font-medium text-slate-700 w-28">RIF:</span><span className="text-slate-900">{rifResult.rif}</span></div>
                      <div className="flex"><span className="font-medium text-slate-700 w-28">Razón Social:</span><span className="text-slate-900">{rifResult.legal_name}</span></div>
                      <div className="flex flex-col"><span className="font-medium text-slate-700">Dirección Fiscal:</span><span className="text-slate-900 mt-0.5">{rifResult.address}</span></div>
                    </div>
                  </div>

                  {/* Alerta de duplicado */}
                  {rifResult.is_duplicate && (
                    <div className="bg-orange-50 border border-orange-300 rounded-lg p-4" data-testid="rif-duplicate-alert">
                      <div className="flex items-center gap-2 mb-2">
                        <AlertCircle size={18} className="text-orange-600" />
                        <span className="font-semibold text-orange-800">RIF ya registrado</span>
                      </div>
                      <p className="text-sm text-orange-700 mb-3">
                        Este RIF ya existe en la base de datos con las siguientes sucursales:
                      </p>
                      <div className="space-y-1 mb-3">
                        {rifResult.existing_clients.map((ec, i) => (
                          <div key={i} className="text-sm text-orange-900 bg-orange-100 rounded px-2 py-1">
                            <strong>{ec.rif}</strong> — {ec.legal_name || ec.fantasy_name} ({ec.sucursal || 'Principal'})
                          </div>
                        ))}
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" onClick={() => applyRifDataToForm(true)}
                          className="bg-orange-600 hover:bg-orange-700 text-white" data-testid="rif-add-branch-btn">
                          <Plus size={14} className="mr-1" />Agregar Nueva Sucursal
                        </Button>
                      </div>
                    </div>
                  )}

                  {/* Botón para cliente nuevo */}
                  {!rifResult.is_duplicate && (
                    <Button onClick={() => applyRifDataToForm(false)}
                      className="w-full bg-green-600 hover:bg-green-700 text-white" data-testid="rif-create-client-btn">
                      <UserPlus size={16} className="mr-2" />Crear Cliente Nuevo
                    </Button>
                  )}
                </div>
              )}

              <div className="flex justify-end gap-3 pt-2 border-t">
                <Button variant="outline" onClick={closeRifDialog}>Cerrar</Button>
                {!rifResult && (
                  <Button onClick={executeRifParse} disabled={!rifFile || rifParsing}
                    className="bg-amber-500 hover:bg-amber-600 text-white" data-testid="rif-scan-btn">
                    {rifParsing ? (
                      <><div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />Escaneando...</>
                    ) : (
                      <><ScanLine size={16} className="mr-2" />Escanear RIF</>
                    )}
                  </Button>
                )}
              </div>
            </div>
          </DialogContent>
        </Dialog>
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
                  <Label className="text-xs">Persona contactada</Label>
                  <Select value={newLog.contacted_person} onValueChange={(v) => setNewLog(p => ({ ...p, contacted_person: v }))}>
                    <SelectTrigger data-testid="log-contact-select" className="h-9">
                      <SelectValue placeholder="Seleccione contacto..." />
                    </SelectTrigger>
                    <SelectContent>
                      {logClientContacts.map(c => (
                        <SelectItem key={c.id} value={c.name}>
                          {c.name}{c.role ? ` (${c.role})` : ''}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
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
                          {log.contacted_person && (
                            <p className="text-xs text-purple-600 mt-0.5 font-medium">Contacto: {log.contacted_person}</p>
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

        {/* Update RIF Dialog for existing clients */}
        <Dialog open={updateRifDialogOpen} onOpenChange={closeUpdateRifDialog}>
          <DialogContent className="max-w-lg" data-testid="update-rif-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <RefreshCw className="text-amber-500" size={22} />
                Actualizar Cliente desde RIF
              </DialogTitle>
            </DialogHeader>
            {updateRifClient && (
              <div className="space-y-4">
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                  <p className="text-sm text-slate-600">Cliente seleccionado:</p>
                  <p className="font-semibold text-slate-900">{updateRifClient.legal_name || updateRifClient.fantasy_name}</p>
                  <p className="text-sm font-mono text-slate-500">{updateRifClient.rif} — {updateRifClient.sucursal || 'Principal'}</p>
                </div>

                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
                  <p className="text-sm text-amber-800">Suba el archivo del RIF (PDF, JPG o PNG). El sistema extraerá los datos, actualizará la información del cliente y archivará el documento.</p>
                </div>

                <div>
                  <Label>Archivo RIF (PDF, JPG, PNG)</Label>
                  <div className="mt-2">
                    <Input ref={updateRifFileInputRef} type="file" accept=".pdf,.jpg,.jpeg,.png"
                      onChange={(e) => { setUpdateRifFile(e.target.files?.[0] || null); setUpdateRifResult(null); }}
                      data-testid="update-rif-file-input" />
                  </div>
                  {updateRifFile && <p className="text-sm text-slate-600 mt-1">Archivo: <strong>{updateRifFile.name}</strong></p>}
                </div>

                {updateRifLoading && (
                  <div className="space-y-2" data-testid="update-rif-progress">
                    <div className="flex items-center gap-2">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-amber-600" />
                      <span className="text-sm text-amber-700 font-medium">Escaneando y actualizando...</span>
                    </div>
                    <div className="w-full bg-amber-100 rounded-full h-2.5">
                      <div className="bg-amber-500 h-2.5 rounded-full transition-all duration-300" style={{ width: `${updateRifProgress}%` }} />
                    </div>
                  </div>
                )}

                {updateRifResult && (
                  <div className="space-y-3" data-testid="update-rif-result">
                    <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <CheckCircle2 size={18} className="text-green-600" />
                        <span className="font-medium text-green-800">{updateRifResult.message}</span>
                      </div>

                      <p className="text-xs font-semibold text-slate-500 uppercase mb-2">Comparación de datos</p>
                      <div className="space-y-2">
                        {['rif', 'legal_name', 'address'].map(field => {
                          const labels = { rif: 'RIF', legal_name: 'Razón Social', address: 'Dirección Fiscal' };
                          const prev = updateRifResult.previous_data?.[field] || '—';
                          const next = updateRifResult.updated_data?.[field] || '—';
                          const changed = prev !== next;
                          return (
                            <div key={field} className={`text-sm rounded p-2 ${changed ? 'bg-amber-50 border border-amber-200' : 'bg-white border border-slate-100'}`}>
                              <span className="font-medium text-slate-700 block text-xs mb-1">{labels[field]}</span>
                              {changed ? (
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="line-through text-red-400">{prev}</span>
                                  <ArrowRight size={14} className="text-slate-400 shrink-0" />
                                  <span className="text-green-700 font-medium">{next}</span>
                                </div>
                              ) : (
                                <span className="text-slate-600">{prev}</span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                      <p className="text-xs text-slate-400 mt-3">Formato origen: {updateRifResult.source_format}</p>
                    </div>
                  </div>
                )}

                <div className="flex justify-end gap-3 pt-2 border-t">
                  <Button variant="outline" onClick={closeUpdateRifDialog}>
                    {updateRifResult ? 'Cerrar' : 'Cancelar'}
                  </Button>
                  {!updateRifResult && (
                    <Button onClick={executeUpdateRif} disabled={!updateRifFile || updateRifLoading}
                      className="bg-amber-500 hover:bg-amber-600 text-white" data-testid="update-rif-scan-btn">
                      {updateRifLoading ? (
                        <><div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />Procesando...</>
                      ) : (
                        <><ScanLine size={16} className="mr-2" />Escanear y Actualizar</>
                      )}
                    </Button>
                  )}
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
};
