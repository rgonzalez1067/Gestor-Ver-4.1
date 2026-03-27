import { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '../components/ui/dropdown-menu';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Textarea } from '../components/ui/textarea';
import DebouncedInput from '../components/DebouncedInput';
import { Plus, Pencil, Trash2, Upload, FileSpreadsheet, FileText, BookOpen, UserPlus, X, CheckCircle, Circle, Search, FileDown, AlertCircle, CheckCircle2, ScanLine, FileUp, Download, ArrowRight, RefreshCw, MoreHorizontal } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';
import { usePermission } from '../hooks/usePermission';

const SEGMENT_OPTIONS = ['Pymes', 'Corporativo', 'Emprendedor', 'Mixto'];
const CONDICION_OPTIONS = ['Prospecto', 'Cliente'];
const REFERIDOR_OPTIONS = [
  'Correo de Ventas', 'Integrador', 'Directores', 'Corporativo',
  'Jose Dolande', 'Melissa Garcia', 'Katherine Quailey', 'Rafael Gonzalez', 'Otro Cliente'
];
const CONTACT_ROLES = ['Administrativo', 'Financiero', 'Técnico', 'Cuentas por Pagar', 'Operativo', 'Propietario', 'Director'];
const CATEGORIAS_COMERCIALES = [
  'Retail', 'Farmacia', 'Restaurante', 'Supermercado', 'Abasto', 'Panadería',
  'Bar / Discoteca', 'Comida Rápida', 'Cafetería', 'Tienda de Ropa', 'Boutique',
  'Salón de Belleza', 'Barbería', 'Spa / Salud', 'Gimnasio', 'Cosmética',
  'Calzados', 'Mueblería', 'Ferretería', 'Electrodomésticos', 'Joyería',
  'Electrónica', 'Software', 'Juguetería', 'Librería', 'Tienda por Departamento',
  'Educación', 'Inmobiliaria', 'Clínica', 'Alimentos', 'Tecnología', 'Servicios',
];
const TIPOS_SERVICIO = ['VPOS', 'MPOS', 'Payment Gateway', 'Link de Pago'];

const emptyContact = () => ({
  contact_id: '',
  full_name: '',
  phone: '',
  email: '',
  role: 'Administrativo'
});

export const Clients = () => {
  const { canEdit } = usePermission('clientes');
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
    rif: '', legal_name: '', fantasy_name: '', segment: 'Pymes', condicion: 'Prospecto', referidor: '',
    address: '', branch_address: '', categoria_comercial: '', sucursal: 'Principal',
    grupo_economico: '', ejecutivo_propietario: '', ejecutivo_user_id: '',
    cantidad_tiendas: '', cantidad_cajas: '',
    fecha_primer_contacto: '', tipo_contacto: '', tipo_servicio: [],
    integrador_id: '', integrador_name: '', aplicativo: '',
    modelo_impresora_fiscal: '',
    contacts: [emptyContact()]
  });

  const [integrators, setIntegrators] = useState([]);
  const [ejecutivos, setEjecutivos] = useState([]);
  const [bitacoraInicioOpen, setBitacoraInicioOpen] = useState(false);
  const [bitacoraInicioText, setBitacoraInicioText] = useState('');
  const [fiscalPrinters, setFiscalPrinters] = useState([]);
  const [customPrinterName, setCustomPrinterName] = useState('');
  const [showCustomPrinterInput, setShowCustomPrinterInput] = useState(false);

  const fileInputRef = useRef(null);
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => { fetchClients(); fetchIntegrators(); fetchEjecutivos(); fetchFiscalPrinters(); }, []);

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

  const fetchIntegrators = async () => {
    try {
      const resp = await api.get('/integrators/dropdown');
      setIntegrators(resp.data);
    } catch { /* silently ignore */ }
  };

  const fetchEjecutivos = async () => {
    try {
      const resp = await api.get('/auth/ejecutivos');
      setEjecutivos(resp.data);
    } catch { /* silently ignore */ }
  };

  const fetchFiscalPrinters = async () => {
    try {
      const resp = await api.get('/fiscal-printers');
      setFiscalPrinters(resp.data);
    } catch { /* silently ignore */ }
  };

  const handlePrinterSelect = (value) => {
    if (value === '__otra__') {
      setShowCustomPrinterInput(true);
      setCustomPrinterName('');
    } else {
      setFormData(prev => ({ ...prev, modelo_impresora_fiscal: value === '_none_' ? '' : value }));
      setShowCustomPrinterInput(false);
    }
  };

  const handleAddCustomPrinter = async () => {
    const name = customPrinterName.trim();
    if (!name) return;
    // Usar inmediatamente como valor del campo
    setFormData(prev => ({ ...prev, modelo_impresora_fiscal: name }));
    setShowCustomPrinterInput(false);
    // Preguntar si desea registrar en la tabla maestra
    if (window.confirm(`¿Desea registrar "${name}" como opción precargada para futuros clientes?`)) {
      try {
        await api.post('/fiscal-printers', { name });
        await fetchFiscalPrinters();
        toast.success(`Modelo "${name}" registrado en la tabla maestra`);
      } catch (err) {
        toast.error(err.response?.data?.detail || 'Error al registrar modelo');
      }
    }
  };

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
    // Convertir strings vacíos a null para campos numéricos opcionales
    if (payload.cantidad_tiendas === '' || payload.cantidad_tiendas === null) payload.cantidad_tiendas = null;
    else payload.cantidad_tiendas = parseInt(payload.cantidad_tiendas, 10) || null;
    if (payload.cantidad_cajas === '' || payload.cantidad_cajas === null) payload.cantidad_cajas = null;
    else payload.cantidad_cajas = parseInt(payload.cantidad_cajas, 10) || null;
    // Convertir strings vacíos a null para campos opcionales
    for (const key of ['referidor', 'address', 'branch_address', 'categoria_comercial', 'grupo_economico', 'ejecutivo_propietario', 'ejecutivo_user_id', 'fecha_primer_contacto', 'tipo_contacto', 'integrador_id', 'integrador_name', 'aplicativo', 'modelo_impresora_fiscal']) {
      if (payload[key] === '') payload[key] = null;
    }
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
      const detail = error.response?.data?.detail;
      if (Array.isArray(detail)) {
        const fields = detail.map(d => d.loc?.slice(-1)?.[0] || 'campo').join(', ');
        toast.error(`Error de validación en: ${fields}`);
      } else {
        toast.error(detail || 'Error al guardar cliente');
      }
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
      condicion: client.condicion || 'Prospecto',
      referidor: client.referidor || '',
      address: client.address || '',
      branch_address: client.branch_address || '',
      categoria_comercial: client.categoria_comercial || '',
      sucursal: client.sucursal || 'Principal',
      grupo_economico: client.grupo_economico || '',
      ejecutivo_propietario: client.ejecutivo_propietario || '',
      ejecutivo_user_id: client.ejecutivo_user_id || '',
      cantidad_tiendas: client.cantidad_tiendas ?? '',
      cantidad_cajas: client.cantidad_cajas ?? '',
      fecha_primer_contacto: client.fecha_primer_contacto || '',
      tipo_contacto: client.tipo_contacto || '',
      tipo_servicio: client.tipo_servicio || [],
      integrador_id: client.integrador_id || '',
      integrador_name: client.integrador_name || '',
      aplicativo: client.aplicativo || '',
      modelo_impresora_fiscal: client.modelo_impresora_fiscal || '',
      contacts
    });
    setDialogOpen(true);
  };

  const resetForm = () => {
    setFormData({
      rif: '', legal_name: '', fantasy_name: '', segment: 'Pymes', condicion: 'Prospecto',
      address: '', branch_address: '', categoria_comercial: '', sucursal: 'Principal',
      grupo_economico: '', ejecutivo_propietario: '', ejecutivo_user_id: '',
      cantidad_tiendas: '', cantidad_cajas: '',
      fecha_primer_contacto: '', tipo_contacto: '', tipo_servicio: [],
      integrador_id: '', integrador_name: '', aplicativo: '',
      modelo_impresora_fiscal: '',
      contacts: [emptyContact()]
    });
    setEditingClient(null);
    setBitacoraInicioText('');
  };

  // Manejar cambio de ejecutivo
  const handleEjecutivoChange = (userId) => {
    if (userId === '_none_') {
      setFormData(prev => ({ ...prev, ejecutivo_user_id: '', ejecutivo_propietario: '' }));
      return;
    }
    const ej = ejecutivos.find(e => e.user_id === userId);
    setFormData(prev => ({
      ...prev,
      ejecutivo_user_id: userId,
      ejecutivo_propietario: ej?.full_name || ''
    }));
  };

  // Manejar cambio de integrador
  const handleIntegradorChange = (integradorId) => {
    const intg = integrators.find(i => i.integrator_id === integradorId);
    setFormData(prev => ({
      ...prev,
      integrador_id: integradorId,
      integrador_name: intg?.name || '',
      aplicativo: '' // Reset aplicativo al cambiar integrador
    }));
  };

  // Obtener aplicativos filtrados por integrador seleccionado
  const getAplicativos = () => {
    if (!formData.integrador_id) return [];
    const intg = integrators.find(i => i.integrator_id === formData.integrador_id);
    return intg?.app_name ? [intg.app_name] : [];
  };

  // Toggle tipo de servicio (multi-select)
  const toggleTipoServicio = (tipo) => {
    setFormData(prev => ({
      ...prev,
      tipo_servicio: (prev.tipo_servicio || []).includes(tipo)
        ? prev.tipo_servicio.filter(t => t !== tipo)
        : [...(prev.tipo_servicio || []), tipo]
    }));
  };

  // Bitácora de Inicio - registrar primer contacto
  const handleBitacoraInicio = async () => {
    if (!bitacoraInicioText.trim()) { toast.error('Ingrese el resultado del contacto'); return; }
    const clientId = editingClient?.client_id;
    if (!clientId) { toast.error('Guarde el cliente primero'); return; }
    try {
      await api.post(`/clients/${clientId}/log`, {
        client_id: clientId,
        detail: bitacoraInicioText,
        action: 'Primer Contacto',
        contact_date: new Date().toISOString().split('T')[0]
      });
      toast.success('Bitácora de inicio registrada');
      setBitacoraInicioOpen(false);
      setBitacoraInicioText('');
    } catch (err) {
      toast.error('Error al registrar bitácora');
    }
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

  const downloadErrorReport = () => {
    if (!importResult?.errors?.length) return;
    // Build CSV content
    const headers = ['Fila', 'Columna', 'Valor Recibido', 'Tipo Error', 'Descripción del Error', 'Acción Sugerida'];
    const rows = importResult.errors.map(err => [
      err.row || '',
      err.column || '',
      (err.value || '').replace(/"/g, '""'),
      err.error_type === 'missing' ? 'Campo Obligatorio Vacío' :
        err.error_type === 'invalid' ? 'Valor Inválido' :
        err.error_type === 'duplicate' ? 'Registro Duplicado' :
        err.error_type === 'format' ? 'Error de Formato' : err.error_type,
      (err.message || '').replace(/"/g, '""'),
      (err.suggested_action || '').replace(/"/g, '""'),
    ]);
    const csvContent = '\uFEFF' + [headers, ...rows].map(r => r.map(c => `"${c}"`).join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `errores_importacion_clientes_${new Date().toISOString().slice(0,10)}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(a.href);
    toast.success('Reporte de errores descargado');
  };

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

    // Partir del estado limpio para no perder campos obligatorios
    const newData = {
      rif: rifResult.rif || '',
      legal_name: rifResult.legal_name || '',
      fantasy_name: rifResult.legal_name || '',
      segment: 'Pymes',
      condicion: 'Prospecto',
      referidor: '',
      address: rifResult.address || '',
      branch_address: '',
      categoria_comercial: '',
      sucursal: addBranch ? '' : 'Principal',
      grupo_economico: '',
      ejecutivo_propietario: '',
      ejecutivo_user_id: '',
      cantidad_tiendas: '',
      cantidad_cajas: '',
      fecha_primer_contacto: '',
      tipo_contacto: '',
      tipo_servicio: [],
      integrador_id: '',
      integrador_name: '',
      aplicativo: '',
      modelo_impresora_fiscal: '',
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
      toast.success('Datos del RIF recuperados. Verifique y complete los campos faltantes antes de guardar.');
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
              {canEdit && <Button variant="outline" onClick={() => setRifDialogOpen(true)} className="border-amber-500 text-amber-600 hover:bg-amber-50" data-testid="load-rif-btn">
                <ScanLine size={18} className="mr-2" />Cargar desde RIF Digital
              </Button>}
              {canEdit && <Button variant="outline" onClick={() => setImportDialogOpen(true)} className="border-brand-blue-600 text-brand-blue-600" data-testid="import-clients-btn">
                <Upload size={18} className="mr-2" />Importar
              </Button>}
              <Button variant="outline" onClick={exportToCSV} className="border-brand-green-600 text-brand-green-600">
                <FileSpreadsheet size={18} className="mr-2" />CSV
              </Button>
              <Button variant="outline" onClick={exportToPDF} className="border-brand-blue-600 text-brand-blue-600">
                <FileText size={18} className="mr-2" />PDF
              </Button>
              {canEdit && <Dialog open={dialogOpen} onOpenChange={handleDialogClose}>
                <DialogTrigger asChild>
                  <Button data-testid="add-client-button" className="bg-brand-green-600 hover:bg-brand-green-700 text-white">
                    <Plus size={20} className="mr-2" />Nuevo Cliente
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-5xl max-h-[92vh] overflow-y-auto">
                  <DialogHeader>
                    <div className="flex items-center justify-between">
                      <DialogTitle className="font-manrope text-2xl">{editingClient ? 'Editar Cliente' : 'Nuevo Cliente'}</DialogTitle>
                      <Button type="button" size="sm" variant="outline"
                        onClick={() => editingClient ? setBitacoraInicioOpen(true) : toast.info('Guarde el cliente primero para registrar la bitácora')}
                        data-testid="bitacora-inicio-btn" className="text-blue-600 border-blue-200 hover:bg-blue-50">
                        <BookOpen size={14} className="mr-1.5" />Bitácora de Inicio
                      </Button>
                    </div>
                  </DialogHeader>
                  <form onSubmit={handleSubmitWithHighlight} className="space-y-5">
                    {/* Banner de campos auto-completados */}
                    {rifHighlightFields.size > 0 && (
                      <div className="flex items-center gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg" data-testid="rif-auto-fill-banner">
                        <ScanLine size={18} className="text-amber-600 shrink-0" />
                        <p className="text-sm text-amber-800">
                          Los campos resaltados en <span className="font-semibold text-amber-700">amarillo</span> fueron extraídos automáticamente del RIF Digital.
                        </p>
                      </div>
                    )}

                    {/* === 4 CUADRANTES === */}
                    <div className="grid grid-cols-2 gap-5">

                      {/* CUADRANTE 1: Estatus y Definición Legal */}
                      <div className="space-y-3 p-4 rounded-lg border border-slate-200" style={{ backgroundColor: formData.condicion === 'Cliente' ? '#f0fdf4' : '#fefce8' }}>
                        <h3 className="text-xs font-semibold uppercase tracking-wider border-b pb-2" style={{ color: formData.condicion === 'Cliente' ? '#15803d' : '#a16207', borderColor: formData.condicion === 'Cliente' ? '#bbf7d0' : '#fde68a' }}>
                          Estatus y Definición Legal
                        </h3>
                        <div>
                          <Label className="text-xs">Condición</Label>
                          <Select value={formData.condicion} onValueChange={(v) => setFormData(prev => ({ ...prev, condicion: v }))}>
                            <SelectTrigger data-testid="client-condicion-select" className="h-9 font-medium">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {CONDICION_OPTIONS.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label className="text-xs">RIF</Label>
                          <DebouncedInput data-testid="client-rif-input" value={formData.rif}
                            onCommit={(v) => { setFormData(prev => ({ ...prev, rif: v })); setRifHighlightFields(prev => { const n = new Set(prev); n.delete('rif'); return n; }); }}
                            className={`h-9 font-mono ${rifHighlightFields.has('rif') ? 'bg-amber-50 border-amber-300 ring-1 ring-amber-200' : ''}`}
                            placeholder="J000000000" required />
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <Label className="text-xs">Nombre Jurídico</Label>
                            <DebouncedInput data-testid="client-legal-name-input" value={formData.legal_name}
                              onCommit={(v) => { setFormData(prev => ({ ...prev, legal_name: v })); setRifHighlightFields(prev => { const n = new Set(prev); n.delete('legal_name'); return n; }); }}
                              className={`h-9 ${rifHighlightFields.has('legal_name') ? 'bg-amber-50 border-amber-300 ring-1 ring-amber-200' : ''}`} required />
                          </div>
                          <div>
                            <Label className="text-xs">Nombre de Fantasía</Label>
                            <DebouncedInput data-testid="client-fantasy-name-input" value={formData.fantasy_name}
                              onCommit={(v) => { setFormData(prev => ({ ...prev, fantasy_name: v })); setRifHighlightFields(prev => { const n = new Set(prev); n.delete('fantasy_name'); return n; }); }}
                              className={`h-9 ${rifHighlightFields.has('fantasy_name') ? 'bg-amber-50 border-amber-300 ring-1 ring-amber-200' : ''}`} required />
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <Label className="text-xs">Grupo Económico</Label>
                            <DebouncedInput data-testid="client-grupo-economico-input" value={formData.grupo_economico}
                              onCommit={(v) => setFormData(prev => ({ ...prev, grupo_economico: v }))}
                              className="h-9" placeholder="Ej: Grupo Polar" />
                          </div>
                          <div>
                            <Label className="text-xs">Segmento</Label>
                            <Select value={formData.segment} onValueChange={(v) => setFormData(prev => ({ ...prev, segment: v }))}>
                              <SelectTrigger data-testid="client-segment-select" className="h-9"><SelectValue /></SelectTrigger>
                              <SelectContent>
                                {SEGMENT_OPTIONS.map(seg => <SelectItem key={seg} value={seg}>{seg}</SelectItem>)}
                              </SelectContent>
                            </Select>
                          </div>
                        </div>
                        <div>
                          <Label className="text-xs">Referidor</Label>
                          <Select value={formData.referidor || '_none_'} onValueChange={(v) => setFormData(prev => ({ ...prev, referidor: v === '_none_' ? '' : v }))}>
                            <SelectTrigger data-testid="client-referidor-select" className="h-9"><SelectValue placeholder="Seleccionar..." /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="_none_">Seleccionar...</SelectItem>
                              {REFERIDOR_OPTIONS.map(r => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                            </SelectContent>
                          </Select>
                        </div>
                      </div>

                      {/* CUADRANTE 2: Capacidad Operativa */}
                      <div className="space-y-3 p-4 bg-slate-50 rounded-lg border border-slate-200">
                        <h3 className="text-xs font-semibold text-slate-700 uppercase tracking-wider border-b border-slate-300 pb-2">Capacidad Operativa</h3>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <Label className="text-xs">Cantidad de Tiendas</Label>
                            <DebouncedInput type="number" min="0" data-testid="client-cantidad-tiendas-input"
                              value={formData.cantidad_tiendas}
                              onCommit={(v) => setFormData(prev => ({ ...prev, cantidad_tiendas: v }))}
                              className="h-9" placeholder="0" />
                          </div>
                          <div>
                            <Label className="text-xs">Cantidad de Cajas</Label>
                            <DebouncedInput type="number" min="0" data-testid="client-cantidad-cajas-input"
                              value={formData.cantidad_cajas}
                              onCommit={(v) => setFormData(prev => ({ ...prev, cantidad_cajas: v }))}
                              className="h-9" placeholder="0" />
                          </div>
                        </div>
                        <div>
                          <Label className="text-xs">Categoría Comercial</Label>
                          <Select value={formData.categoria_comercial || '_none_'} onValueChange={(v) => setFormData(prev => ({ ...prev, categoria_comercial: v === '_none_' ? '' : v }))}>
                            <SelectTrigger data-testid="client-categoria-select" className="h-9"><SelectValue placeholder="Seleccionar..." /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="_none_">Seleccionar...</SelectItem>
                              {CATEGORIAS_COMERCIALES.map(cat => <SelectItem key={cat} value={cat}>{cat}</SelectItem>)}
                            </SelectContent>
                          </Select>
                        </div>
                      </div>

                      {/* CUADRANTE 3: Ubicación y Sedes */}
                      <div className="space-y-3 p-4 bg-slate-50 rounded-lg border border-slate-200">
                        <h3 className="text-xs font-semibold text-slate-700 uppercase tracking-wider border-b border-slate-300 pb-2">Ubicación y Sedes</h3>
                        <div>
                          <Label className="text-xs">Dirección Fiscal</Label>
                          <DebouncedInput as="textarea" data-testid="client-address-input" value={formData.address}
                            onCommit={(v) => { setFormData(prev => ({ ...prev, address: v })); setRifHighlightFields(prev => { const n = new Set(prev); n.delete('address'); return n; }); }}
                            className={`flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring min-h-[56px] resize-none ${rifHighlightFields.has('address') ? 'bg-amber-50 border-amber-300 ring-1 ring-amber-200' : ''}`}
                            placeholder="Av. Principal, Edificio..." />
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <Label className="text-xs">Nombre de Sucursal</Label>
                            <DebouncedInput data-testid="client-sucursal-input" value={formData.sucursal}
                              onCommit={(v) => setFormData(prev => ({ ...prev, sucursal: v }))}
                              className="h-9" placeholder="Sede Principal" required />
                          </div>
                          <div>
                            <Label className="text-xs">Dirección de Sucursal</Label>
                            <DebouncedInput data-testid="client-branch-address-input" value={formData.branch_address}
                              onCommit={(v) => setFormData(prev => ({ ...prev, branch_address: v }))}
                              className="h-9" placeholder="Ubicación física" />
                          </div>
                        </div>
                      </div>

                      {/* CUADRANTE 4: Gestión y Soluciones Técnicas */}
                      <div className="space-y-3 p-4 bg-slate-50 rounded-lg border border-slate-200">
                        <h3 className="text-xs font-semibold text-slate-700 uppercase tracking-wider border-b border-slate-300 pb-2">Gestión y Soluciones</h3>
                        <div>
                          <Label className="text-xs">Ejecutivo Propietario</Label>
                          <Select value={formData.ejecutivo_user_id || '_none_'} onValueChange={handleEjecutivoChange}>
                            <SelectTrigger data-testid="client-ejecutivo-select" className="h-9"><SelectValue placeholder="Seleccionar ejecutivo..." /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="_none_">Sin asignar</SelectItem>
                              {ejecutivos.map(ej => (
                                <SelectItem key={ej.user_id} value={ej.user_id}>
                                  {ej.full_name} <span className="text-slate-400 text-xs ml-1">({ej.cargo})</span>
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <Label className="text-xs">Integrador</Label>
                            <Select value={formData.integrador_id || '_none_'} onValueChange={(v) => v === '_none_' ? setFormData(prev => ({ ...prev, integrador_id: '', integrador_name: '', aplicativo: '' })) : handleIntegradorChange(v)}>
                              <SelectTrigger data-testid="client-integrador-select" className="h-9"><SelectValue placeholder="Seleccionar..." /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="_none_">Sin integrador</SelectItem>
                                {integrators.map(i => <SelectItem key={i.integrator_id} value={i.integrator_id}>{i.name}</SelectItem>)}
                              </SelectContent>
                            </Select>
                          </div>
                          <div>
                            <Label className="text-xs">Aplicativo</Label>
                            {getAplicativos().length > 0 ? (
                              <Select value={formData.aplicativo || '_none_'} onValueChange={(v) => setFormData(prev => ({ ...prev, aplicativo: v === '_none_' ? '' : v }))}>
                                <SelectTrigger data-testid="client-aplicativo-select" className="h-9"><SelectValue placeholder="Seleccionar..." /></SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="_none_">Seleccionar...</SelectItem>
                                  {getAplicativos().map(a => <SelectItem key={a} value={a}>{a}</SelectItem>)}
                                </SelectContent>
                              </Select>
                            ) : (
                              <DebouncedInput data-testid="client-aplicativo-input" value={formData.aplicativo}
                                onCommit={(v) => setFormData(prev => ({ ...prev, aplicativo: v }))}
                                className="h-9" placeholder={formData.integrador_id ? 'Escriba el aplicativo' : 'Seleccione integrador'}
                                disabled={!formData.integrador_id} />
                            )}
                          </div>
                        </div>
                        <div>
                          <Label className="text-xs">Tipo de Servicio</Label>
                          <div className="flex flex-wrap gap-2 mt-1">
                            {TIPOS_SERVICIO.map(ts => (
                              <button key={ts} type="button" onClick={() => toggleTipoServicio(ts)}
                                data-testid={`tipo-servicio-${ts.toLowerCase().replace(/\s/g, '-')}`}
                                className={`px-2.5 py-1 text-xs font-medium rounded-full border transition-colors ${
                                  (formData.tipo_servicio || []).includes(ts)
                                    ? 'bg-blue-100 border-blue-300 text-blue-700'
                                    : 'bg-white border-slate-200 text-slate-500 hover:border-blue-200'
                                }`}>
                                {ts}
                              </button>
                            ))}
                          </div>
                        </div>
                        <div>
                          <Label className="text-xs">Modelo de Impresora Fiscal</Label>
                          {!showCustomPrinterInput ? (
                            <Select value={formData.modelo_impresora_fiscal || '_none_'} onValueChange={handlePrinterSelect}>
                              <SelectTrigger data-testid="client-printer-select" className="h-9"><SelectValue placeholder="Seleccionar modelo..." /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="_none_">Sin especificar</SelectItem>
                                {fiscalPrinters.map(p => <SelectItem key={p.model_id} value={p.name}>{p.name}</SelectItem>)}
                                <SelectItem value="__otra__">Otra...</SelectItem>
                              </SelectContent>
                            </Select>
                          ) : (
                            <div className="flex gap-2 mt-0.5">
                              <Input
                                data-testid="client-printer-custom-input"
                                value={customPrinterName}
                                onChange={e => setCustomPrinterName(e.target.value)}
                                onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), handleAddCustomPrinter())}
                                className="h-9 flex-1" placeholder="Nombre del modelo..."
                                autoFocus
                              />
                              <Button type="button" size="sm" className="h-9 bg-emerald-600 hover:bg-emerald-700 text-white px-3"
                                onClick={handleAddCustomPrinter} data-testid="client-printer-custom-confirm">
                                <CheckCircle size={14} />
                              </Button>
                              <Button type="button" size="sm" variant="ghost" className="h-9 px-2"
                                onClick={() => setShowCustomPrinterInput(false)} data-testid="client-printer-custom-cancel">
                                <X size={14} />
                              </Button>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* === CONTACTOS === */}
                    <div className="border-t pt-4">
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="font-semibold text-sm uppercase tracking-wider text-slate-700">Contactos</h3>
                        <Button type="button" size="sm" variant="outline" onClick={addContact} data-testid="add-contact-btn">
                          <UserPlus size={14} className="mr-1" />Agregar
                        </Button>
                      </div>
                      {formData.contacts.map((contact, idx) => (
                        <div key={idx} className="grid grid-cols-12 gap-2 mb-2 items-end p-2.5 bg-slate-50 rounded-lg border" data-testid={`contact-row-${idx}`}>
                          <div className="col-span-3">
                            <Label className="text-xs">Nombre</Label>
                            <DebouncedInput value={contact.full_name} onCommit={(v) => updateContact(idx, 'full_name', v)}
                              placeholder="Nombre completo" className="h-8 text-sm" data-testid={`contact-full-name-${idx}`} required />
                          </div>
                          <div className="col-span-2">
                            <Label className="text-xs">Teléfono</Label>
                            <DebouncedInput value={contact.phone} onCommit={(v) => updateContact(idx, 'phone', v)}
                              placeholder="0412..." className="h-8 text-sm" />
                          </div>
                          <div className="col-span-3">
                            <Label className="text-xs">Email</Label>
                            <DebouncedInput value={contact.email} onCommit={(v) => updateContact(idx, 'email', v)}
                              placeholder="email@..." className="h-8 text-sm" type="email" />
                          </div>
                          <div className="col-span-3">
                            <Label className="text-xs">Rol</Label>
                            <Select value={contact.role} onValueChange={(v) => updateContact(idx, 'role', v)}>
                              <SelectTrigger className="h-8 text-sm"><SelectValue /></SelectTrigger>
                              <SelectContent>
                                {CONTACT_ROLES.map(r => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="col-span-1 flex justify-center">
                            {formData.contacts.length > 1 && (
                              <Button type="button" size="sm" variant="ghost" onClick={() => removeContact(idx)}
                                className="h-8 w-8 p-0 text-red-500 hover:text-red-700" data-testid={`remove-contact-${idx}`}>
                                <X size={16} />
                              </Button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className="flex justify-end gap-3 pt-2">
                      <Button type="button" variant="outline" onClick={() => handleDialogClose(false)}>Cancelar</Button>
                      <Button type="submit" data-testid="save-client-button" className="bg-brand-green-600 hover:bg-brand-green-700 text-white">
                        {editingClient ? 'Actualizar' : 'Guardar'}
                      </Button>
                    </div>
                  </form>
                </DialogContent>
              </Dialog>}
            </div>
          </div>

          {/* Search */}
          <div className="mb-4 max-w-sm relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <DebouncedInput placeholder="Buscar por RIF, nombre o sucursal..." value={searchTerm}
              onCommit={(v) => setSearchTerm(v)} debounceMs={400} className="pl-9" data-testid="client-search" />
          </div>


          {/* Table */}
          <div className="bg-white rounded-lg border border-slate-200 overflow-x-auto">
            <table className="w-full min-w-[900px]">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase w-[130px]">RIF</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase w-[90px]">Sucursal</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Nombre Jurídico</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Nombre Fantasía</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase w-[100px]">Segmento</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase w-[120px]">Categoría</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase">Contacto Principal</th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-slate-600 uppercase w-[120px]">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.map((client) => {
                  const mainContact = client.contacts?.[0] || null;
                  const legacyContact = client.contact1;
                  return (
                    <tr key={client.client_id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-4 py-3 text-sm font-mono text-slate-700 whitespace-nowrap">
                          {client.rif}
                          {client.condicion && (
                            <span className={`ml-2 inline-block px-1.5 py-0.5 text-[10px] font-semibold rounded ${
                              client.condicion === 'Cliente' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                            }`}>{client.condicion}</span>
                          )}
                        </td>
                      <td className="px-4 py-3 text-sm text-slate-600">{client.sucursal || 'Principal'}</td>
                      <td className="px-4 py-3 text-sm font-medium text-slate-900 max-w-[200px] truncate" title={client.legal_name}>{client.legal_name}</td>
                      <td className="px-4 py-3 text-sm text-slate-600 max-w-[180px] truncate" title={client.fantasy_name}>{client.fantasy_name}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-block px-2 py-0.5 text-xs font-medium rounded ${
                          client.segment === 'Corporativo' ? 'bg-purple-100 text-purple-700' :
                          client.segment === 'Pymes' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                        }`}>{client.segment || 'N/A'}</span>
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-600 truncate max-w-[120px]" title={client.categoria_comercial}>{client.categoria_comercial || '—'}</td>
                      <td className="px-4 py-3 text-sm text-slate-600">
                        {mainContact ? (
                          <div>
                            <p className="font-medium truncate max-w-[160px]">{mainContact.full_name || `${mainContact.first_name || ''} ${mainContact.last_name || ''}`.trim() || '—'}</p>
                            <p className="text-xs text-slate-400 truncate max-w-[160px]">{mainContact.role} · {mainContact.phone}</p>
                          </div>
                        ) : legacyContact ? (
                          <div>
                            <p className="font-medium truncate max-w-[160px]">{legacyContact.name}</p>
                            <p className="text-xs text-slate-400 truncate max-w-[160px]">{legacyContact.email}</p>
                          </div>
                        ) : <span className="text-slate-400">—</span>}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-center gap-1">
                          <Button size="sm" variant="outline" onClick={() => openBitacora(client)}
                            data-testid={`bitacora-client-${client.client_id}`} className="text-blue-600 h-8 px-2">
                            <BookOpen size={14} />
                          </Button>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button size="sm" variant="outline" className="h-8 w-8 p-0" data-testid={`client-actions-${client.client_id}`}>
                                <MoreHorizontal size={16} />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-48">
                              <DropdownMenuItem onSelect={() => openUpdateRifDialog(client)} className="cursor-pointer">
                                <ScanLine size={14} className="mr-2 text-amber-600" /> Escanear RIF
                              </DropdownMenuItem>
                              {client.rif_document_url && (
                                <DropdownMenuItem onSelect={() => downloadRifDocument(client)} className="cursor-pointer">
                                  <Download size={14} className="mr-2 text-green-600" /> Descargar RIF
                                </DropdownMenuItem>
                              )}
                              <DropdownMenuSeparator />
                              {canEdit && <DropdownMenuItem onSelect={() => openEditDialog(client)} className="cursor-pointer">
                                <Pencil size={14} className="mr-2 text-slate-500" /> Editar
                              </DropdownMenuItem>}
                              {canEdit && <><DropdownMenuSeparator />
                              <DropdownMenuItem onSelect={() => handleDelete(client.client_id)}
                                className="cursor-pointer text-red-600 hover:text-red-700 hover:bg-red-50">
                                <Trash2 size={14} className="mr-2" /> Eliminar
                              </DropdownMenuItem></>}
                            </DropdownMenuContent>
                          </DropdownMenu>
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
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="import-clients-dialog">
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
                  <li>Descargue la plantilla con todas las columnas y valores válidos</li>
                  <li>Complete los datos respetando los formatos indicados en las hojas "Instrucciones" y "Valores Válidos"</li>
                  <li>La llave única es <strong>RIF + Sucursal</strong> (se permite duplicar RIF si la sucursal es distinta)</li>
                  <li>Campos obligatorios: <strong>RIF</strong> y <strong>Nombre Jurídico</strong></li>
                  <li>Cargue el archivo completado (.xlsx, .xls o .csv)</li>
                </ol>
                <Button variant="outline" size="sm" onClick={downloadTemplate}
                  className="mt-3 text-blue-700 border-blue-300 hover:bg-blue-100" data-testid="download-client-template-btn">
                  <FileDown size={16} className="mr-2" />Descargar Plantilla Actualizada
                </Button>
              </div>
              <div>
                <Label>Archivo a importar (Excel o CSV)</Label>
                <div className="mt-2 flex items-center gap-3">
                  <Input type="file" accept=".xlsx,.xls,.csv" onChange={handleImportFileChange}
                    className="flex-1" data-testid="import-client-file-input" />
                </div>
                {importFile && (
                  <p className="text-sm text-slate-600 mt-2">Archivo seleccionado: <strong>{importFile.name}</strong> ({(importFile.size / 1024).toFixed(1)} KB)</p>
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
                  {/* Stats summary */}
                  {importResult.total_processed > 0 && (
                    <div className="flex flex-wrap gap-3 my-2 text-xs">
                      <span className="px-2 py-1 bg-slate-100 rounded font-medium">Procesados: {importResult.total_processed}</span>
                      {importResult.success_count > 0 && <span className="px-2 py-1 bg-green-100 text-green-700 rounded font-medium">Importados: {importResult.success_count}</span>}
                      {importResult.skipped_count > 0 && <span className="px-2 py-1 bg-red-100 text-red-700 rounded font-medium">Omitidos: {importResult.skipped_count}</span>}
                      {importResult.error_count > 0 && <span className="px-2 py-1 bg-amber-100 text-amber-700 rounded font-medium">Errores: {importResult.error_count}</span>}
                    </div>
                  )}
                  {importResult.errors?.length > 0 && (
                    <div className="mt-3">
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-sm font-medium text-slate-700">Detalle de errores ({importResult.errors.length}):</p>
                        <Button variant="outline" size="sm" onClick={downloadErrorReport}
                          className="h-7 text-xs border-slate-300" data-testid="download-errors-btn">
                          <Download size={13} className="mr-1" />Descargar Reporte
                        </Button>
                      </div>
                      <div className="max-h-48 overflow-y-auto space-y-1.5">
                        {importResult.errors.slice(0, 20).map((err, idx) => (
                          <div key={idx} className={`text-xs p-2 rounded border ${
                            err.error_type === 'missing' ? 'bg-red-50 border-red-200' :
                            err.error_type === 'duplicate' ? 'bg-orange-50 border-orange-200' :
                            err.error_type === 'invalid' ? 'bg-amber-50 border-amber-200' :
                            'bg-slate-50 border-slate-200'
                          }`}>
                            <p className="font-medium text-slate-800">{err.message}</p>
                            {err.suggested_action && (
                              <p className="text-slate-500 mt-0.5 italic">{err.suggested_action}</p>
                            )}
                          </div>
                        ))}
                        {importResult.errors.length > 20 && (
                          <p className="text-xs text-slate-500 italic text-center py-1">
                            ... y {importResult.errors.length - 20} errores más. Descargue el reporte completo para verlos todos.
                          </p>
                        )}
                      </div>
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
                <DebouncedInput as="textarea" value={newLog.detail} onCommit={(v) => setNewLog(p => ({ ...p, detail: v }))}
                  placeholder="Resumen de la interacción con el cliente..." rows={2} data-testid="log-detail-input" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs">Acción resultante / Compromiso adquirido</Label>
                  <DebouncedInput value={newLog.action} onCommit={(v) => setNewLog(p => ({ ...p, action: v }))}
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
                            <p className="text-xs text-blue-600 mt-1 font-medium">Acción/Compromiso: {log.action}</p>
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

        {/* Modal Bitácora de Inicio */}
        <Dialog open={bitacoraInicioOpen} onOpenChange={setBitacoraInicioOpen}>
          <DialogContent className="max-w-md" data-testid="bitacora-inicio-modal">
            <DialogHeader>
              <DialogTitle>Bitácora de Inicio</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <p className="text-sm text-slate-500">Registre el resultado del primer contacto con este cliente.</p>
              <textarea value={bitacoraInicioText} onChange={(e) => setBitacoraInicioText(e.target.value)}
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring min-h-[100px] resize-none"
                placeholder="Describa el resultado del contacto..." data-testid="bitacora-inicio-text" />
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => setBitacoraInicioOpen(false)}>Cancelar</Button>
                <Button type="button" size="sm" onClick={handleBitacoraInicio} data-testid="bitacora-inicio-save"
                  className="bg-blue-600 hover:bg-blue-700 text-white">Guardar</Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

      </main>
    </div>
  );
};
