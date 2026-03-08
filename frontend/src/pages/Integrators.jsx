import { useState, useEffect, useRef, Fragment } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { ImportResultPanel } from '../components/ImportResultPanel';
import { Plus, Pencil, Trash2, Upload, FileSpreadsheet, FileText, Search, Filter, Users, CheckCircle, Clock, XCircle, ChevronDown, ChevronUp, Award, Download, AlertCircle, RefreshCw, FileDown } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const INTEGRATOR_TYPES = ['Integrador', 'Comercio'];
const INTEGRATION_TYPE_OPTIONS = [
  { id: 'CR', label: 'CR — Caja Registradora' },
  { id: 'LP', label: 'LP — Link de Pago' },
  { id: 'PG', label: 'PG — Payment Gateway' },
  { id: 'MP', label: 'MP — Android (Mobile POS)' },
  { id: 'TK', label: 'TK — Tokenizador' }
];
const INTEGRATION_MODALITIES = ['Bridge PG', 'MPOS', 'PG Universal', 'PG No universal', 'REST', 'Stand Alone'];
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
  const [integrators, setIntegrators] = useState([]);
  const [users, setUsers] = useState([]);
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
  const [formData, setFormData] = useState({
    name: '', integrator_type: '', integration_type: '', app_name: '',
    integration_modality: '', integrator_status: 'En proceso', gestor: '', categoria: '', certifications: {}
  });
  const fileInputRef = useRef(null);
  const [importResult, setImportResult] = useState(null);
  const [showImportResult, setShowImportResult] = useState(false);
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [importStep, setImportStep] = useState(1);
  const [importMode, setImportMode] = useState('upsert');
  const [importFile, setImportFile] = useState(null);
  const [importLoading, setImportLoading] = useState(false);
  const dropRef = useRef(null);

  useEffect(() => { fetchData(); }, [filterStatus, filterType]);

  const fetchData = async () => {
    try {
      const params = new URLSearchParams();
      if (filterStatus && filterStatus !== 'all') params.append('integrator_status', filterStatus);
      if (filterType && filterType !== 'all') params.append('integrator_type', filterType);
      const url = params.toString() ? `/integrators?${params}` : '/integrators';

      const [intRes, usersRes, servicesRes] = await Promise.all([
        api.get(url), api.get('/auth/users'), api.get('/services')
      ]);
      setIntegrators(intRes.data);
      setUsers(usersRes.data || []);
      const prods = (servicesRes.data || []).filter(s =>
        (s.application_type === 'setup' || s.application_type === 'both') && s.service_type === 'Producto'
      );
      setCertProducts(prods);
    } catch { toast.error('Error al cargar datos'); }
    finally { setLoading(false); }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.name || !formData.integrator_type || !formData.app_name || !formData.integration_modality) {
      toast.error('Complete los campos obligatorios'); return;
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
      } else {
        await api.post('/integrators', payload);
        toast.success('Integrador creado');
      }
      setDialogOpen(false); resetForm(); fetchData();
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

  const openEditDialog = (intg) => {
    setEditingIntegrator(intg);
    setFormData({
      name: intg.name, integrator_type: intg.integrator_type,
      integration_type: intg.integration_type || '', app_name: intg.app_name,
      integration_modality: intg.integration_modality, integrator_status: intg.integrator_status,
      gestor: intg.gestor || '', categoria: intg.categoria || '',
      certifications: intg.certifications || {}
    });
    setDialogOpen(true);
  };

  const resetForm = () => {
    setFormData({ name: '', integrator_type: '', integration_type: '', app_name: '', integration_modality: '', integrator_status: 'En proceso', gestor: '', categoria: '', certifications: {} });
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
        certifications: certs
      };
      await api.put(`/integrators/${integratorId}`, payload);
      setIntegrators(prev => prev.map(i => i.integrator_id === integratorId ? { ...i, certifications: certs } : i));
    } catch { toast.error('Error al actualizar certificación'); }
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
    } catch { toast.error('Error al importar archivo'); }
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

  const filteredIntegrators = integrators.filter(intg => {
    if (!searchTerm) return true;
    const s = searchTerm.toLowerCase();
    return intg.name?.toLowerCase().includes(s) || intg.app_name?.toLowerCase().includes(s) || intg.integration_modality?.toLowerCase().includes(s);
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
              <p className="text-slate-500 mt-1">Aliados técnicos, certificación de productos y gestores asignados</p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setImportDialogOpen(true)} data-testid="import-integrators-btn"><Upload size={16} className="mr-1" />Importar</Button>
              <Button variant="outline" onClick={handleExportExcel} data-testid="export-excel-btn"><FileSpreadsheet size={16} className="mr-1" />Excel</Button>
              <Button variant="outline" onClick={handleExportPDF} data-testid="export-pdf-btn"><FileText size={16} className="mr-1" />PDF</Button>
              <Dialog open={dialogOpen} onOpenChange={(o) => { setDialogOpen(o); if (!o) resetForm(); }}>
                <DialogTrigger asChild>
                  <Button className="bg-brand-green-600 hover:bg-brand-green-700" data-testid="create-integrator-btn"><Plus size={16} className="mr-1" />Nuevo</Button>
                </DialogTrigger>
                <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                  <DialogHeader><DialogTitle className="font-manrope text-xl">{editingIntegrator ? 'Editar Integrador' : 'Nuevo Integrador'}</DialogTitle></DialogHeader>
                  <form onSubmit={handleSubmit} className="space-y-4 mt-2">
                    <div className="grid grid-cols-2 gap-3">
                      <div className="col-span-2">
                        <Label>Nombre del Integrador *</Label>
                        <Input value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} placeholder="Ej: TechPay Solutions" required data-testid="integrator-name-input" />
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
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <Label>Nombre del Aplicativo *</Label>
                        <Input value={formData.app_name} onChange={(e) => setFormData({ ...formData, app_name: e.target.value })} placeholder="Ej: PaymentHub" required data-testid="app-name-input" />
                      </div>
                      <div>
                        <Label>Modalidad de Integración *</Label>
                        <Select value={formData.integration_modality} onValueChange={(v) => setFormData({ ...formData, integration_modality: v })}>
                          <SelectTrigger data-testid="modality-select"><SelectValue placeholder="Seleccione..." /></SelectTrigger>
                          <SelectContent>{INTEGRATION_MODALITIES.map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}</SelectContent>
                        </Select>
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-3">
                      <div>
                        <Label>Gestor Asignado</Label>
                        <Select value={formData.gestor} onValueChange={(v) => setFormData({ ...formData, gestor: v })}>
                          <SelectTrigger data-testid="gestor-select"><SelectValue placeholder="Seleccione..." /></SelectTrigger>
                          <SelectContent>{users.map(u => <SelectItem key={u.user_id} value={u.full_name || u.email}>{u.full_name || u.email}</SelectItem>)}</SelectContent>
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
                        <Label>Estatus *</Label>
                        <Select value={formData.integrator_status} onValueChange={(v) => setFormData({ ...formData, integrator_status: v })}>
                          <SelectTrigger data-testid="status-select"><SelectValue /></SelectTrigger>
                          <SelectContent>{INTEGRATOR_STATUSES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                        </Select>
                      </div>
                    </div>
                    <div className="flex justify-end gap-3 pt-2">
                      <Button type="button" variant="outline" onClick={() => { setDialogOpen(false); resetForm(); }}>Cancelar</Button>
                      <Button type="submit" className="bg-brand-green-600 hover:bg-brand-green-700" data-testid="submit-integrator-btn">{editingIntegrator ? 'Actualizar' : 'Crear'}</Button>
                    </div>
                  </form>
                </DialogContent>
              </Dialog>
            </div>
          </div>

          {/* Filters */}
          <div className="bg-white rounded-lg border border-slate-200 p-3 mb-4">
            <div className="flex flex-wrap gap-3 items-center">
              <div className="flex-1 min-w-[200px] relative">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input placeholder="Buscar..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} className="pl-9" data-testid="search-input" />
              </div>
              <Filter size={14} className="text-slate-400" />
              <Select value={filterStatus} onValueChange={setFilterStatus}>
                <SelectTrigger className="w-[140px]" data-testid="filter-status"><SelectValue placeholder="Estatus" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  {INTEGRATOR_STATUSES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={filterType} onValueChange={setFilterType}>
                <SelectTrigger className="w-[140px]" data-testid="filter-type"><SelectValue placeholder="Tipo" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  {INTEGRATOR_TYPES.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                </SelectContent>
              </Select>
              {(filterStatus || filterType || searchTerm) && (
                <Button variant="ghost" size="sm" onClick={() => { setFilterStatus('all'); setFilterType('all'); setSearchTerm(''); }}>Limpiar</Button>
              )}
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-4 gap-3 mb-4">
            <div className="bg-white rounded-lg border p-3"><div className="text-xs text-slate-500">Total</div><div className="text-xl font-bold text-slate-900">{integrators.length}</div></div>
            <div className="bg-white rounded-lg border border-green-200 p-3"><div className="text-xs text-green-600">Certificados</div><div className="text-xl font-bold text-green-700">{integrators.filter(i => i.integrator_status === 'Certificado').length}</div></div>
            <div className="bg-white rounded-lg border border-amber-200 p-3"><div className="text-xs text-amber-600">En proceso</div><div className="text-xl font-bold text-amber-700">{integrators.filter(i => i.integrator_status === 'En proceso').length}</div></div>
            <div className="bg-white rounded-lg border border-red-200 p-3"><div className="text-xs text-red-600">Suspendidos</div><div className="text-xl font-bold text-red-700">{integrators.filter(i => i.integrator_status === 'Suspendido').length}</div></div>
          </div>

          {showImportResult && importResult && <ImportResultPanel result={importResult} onClose={() => { setShowImportResult(false); setImportResult(null); }} />}

          {/* Table */}
          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden" data-testid="integrators-table">
            <div className="overflow-x-auto">
              <table className="w-full" style={{ tableLayout: 'fixed', minWidth: '1050px' }}>
                <colgroup>
                  <col style={{ width: '20%' }} />
                  <col style={{ width: '7%' }} />
                  <col style={{ width: '8%' }} />
                  <col style={{ width: '14%' }} />
                  <col style={{ width: '11%' }} />
                  <col style={{ width: '11%' }} />
                  <col style={{ width: '12%' }} />
                  <col style={{ width: '9%' }} />
                  <col style={{ width: '8%' }} />
                </colgroup>
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-600 uppercase">Nombre</th>
                    <th className="px-3 py-2.5 text-center text-xs font-semibold text-slate-600 uppercase">Tipo Int.</th>
                    <th className="px-3 py-2.5 text-center text-xs font-semibold text-slate-600 uppercase">Tipo</th>
                    <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-600 uppercase">Aplicativo</th>
                    <th className="px-3 py-2.5 text-center text-xs font-semibold text-slate-600 uppercase">Modalidad</th>
                    <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-600 uppercase">Gestor</th>
                    <th className="px-3 py-2.5 text-center text-xs font-semibold text-slate-600 uppercase">Categoría</th>
                    <th className="px-3 py-2.5 text-center text-xs font-semibold text-slate-600 uppercase">Estatus</th>
                    <th className="px-3 py-2.5 text-center text-xs font-semibold text-slate-600 uppercase">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredIntegrators.length === 0 ? (
                    <tr><td colSpan={9} className="px-4 py-8 text-center text-slate-500">No se encontraron integradores</td></tr>
                  ) : filteredIntegrators.map((intg) => (
                    <Fragment key={intg.integrator_id}>
                      <tr className="hover:bg-slate-50 transition-colors" data-testid={`integrator-row-${intg.integrator_id}`}>
                        <td className="px-3 py-2.5">
                          <p className="font-medium text-slate-900 text-sm truncate" title={intg.name}>{intg.name}</p>
                        </td>
                        <td className="px-3 py-2.5 text-center">
                          {intg.integration_type ? <span className="px-2 py-0.5 rounded text-xs font-bold bg-indigo-100 text-indigo-700">{intg.integration_type}</span> : <span className="text-slate-300">—</span>}
                        </td>
                        <td className="px-3 py-2.5 text-center">
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${intg.integrator_type === 'Integrador' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'}`}>{intg.integrator_type}</span>
                        </td>
                        <td className="px-3 py-2.5">
                          <p className="text-sm text-slate-700 truncate" title={intg.app_name}>{intg.app_name}</p>
                        </td>
                        <td className="px-3 py-2.5 text-center">
                          <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-xs">{intg.integration_modality}</span>
                        </td>
                        <td className="px-3 py-2.5">
                          <p className="text-xs text-slate-600 truncate" title={intg.gestor || ''}>{intg.gestor || '—'}</p>
                        </td>
                        <td className="px-3 py-2.5 text-center">
                          <span className="text-[10px] text-slate-500 truncate block" title={intg.categoria || ''}>{intg.categoria ? intg.categoria.replace('Cliente/Integrador ', '') : '—'}</span>
                        </td>
                        <td className="px-3 py-2.5 text-center">{getStatusBadge(intg.integrator_status)}</td>
                        <td className="px-3 py-2.5 text-center">
                          <div className="flex items-center justify-center gap-0.5">
                            <Button size="sm" variant="ghost" onClick={() => setExpandedRow(expandedRow === intg.integrator_id ? null : intg.integrator_id)}
                              className="text-purple-600 hover:bg-purple-50 h-7 px-1.5" data-testid={`detail-${intg.integrator_id}`}>
                              <Award size={13} />{expandedRow === intg.integrator_id ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => openEditDialog(intg)} className="text-brand-blue-600 hover:bg-blue-50 h-7 w-7 p-0" data-testid={`edit-${intg.integrator_id}`}><Pencil size={13} /></Button>
                            <Button size="sm" variant="ghost" onClick={() => handleDelete(intg.integrator_id)} className="text-red-500 hover:bg-red-50 h-7 w-7 p-0" data-testid={`delete-${intg.integrator_id}`}><Trash2 size={13} /></Button>
                          </div>
                        </td>
                      </tr>
                      {/* Expanded certification matrix */}
                      {expandedRow === intg.integrator_id && (
                        <tr>
                          <td colSpan={9} className="p-0">
                            <div className="bg-slate-50 border-t border-slate-200 p-4" data-testid={`cert-matrix-${intg.integrator_id}`}>
                              <h4 className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-3 flex items-center gap-1.5">
                                <Award size={14} className="text-purple-600" />Matriz de Certificación — {intg.name}
                              </h4>
                              {certProducts.length > 0 ? (
                                <div className="overflow-x-auto">
                                  <div className="flex items-start gap-0" style={{ minWidth: certProducts.length * 90 + 160 }}>
                                    <div className="sticky left-0 z-10 bg-slate-50 pr-2 min-w-[160px]">
                                      <div className="h-16 flex items-end pb-1"><span className="text-xs font-semibold text-slate-700">Producto</span></div>
                                      <div className="h-10 flex items-center"><span className="text-xs font-medium text-slate-500">Estado</span></div>
                                    </div>
                                    {certProducts.map((prod) => {
                                      const val = (intg.certifications || {})[prod.service_id] || 'N/A';
                                      const cfg = CERT_STATES[val] || CERT_STATES['N/A'];
                                      return (
                                        <div key={prod.service_id} className="min-w-[85px] text-center px-1">
                                          <div className="h-16 flex items-end pb-1 justify-center">
                                            <span className="text-[10px] text-slate-600 leading-tight line-clamp-3" title={prod.name}>{prod.name}</span>
                                          </div>
                                          <div className="h-10 flex items-center justify-center">
                                            <button
                                              onClick={() => toggleCert(intg.integrator_id, prod.service_id, val)}
                                              className={`px-3 py-1 rounded border text-xs font-bold transition-colors cursor-pointer ${cfg.color}`}
                                              data-testid={`cert-${intg.integrator_id}-${prod.service_id}`}
                                              title="Click para cambiar: P / C / N/A"
                                            >{cfg.label}</button>
                                          </div>
                                        </div>
                                      );
                                    })}
                                  </div>
                                </div>
                              ) : (
                                <p className="text-xs text-slate-400 italic">No hay productos tipo "Producto" con aplicación "Setup" o "Both" en el catálogo</p>
                              )}
                              <div className="flex gap-4 mt-3 text-[10px] text-slate-500">
                                <span><span className="inline-block w-5 text-center px-1 py-0.5 rounded bg-amber-100 text-amber-700 font-bold mr-1">P</span>Pendiente</span>
                                <span><span className="inline-block w-5 text-center px-1 py-0.5 rounded bg-emerald-100 text-emerald-700 font-bold mr-1">C</span>Certificado</span>
                                <span><span className="inline-block w-5 text-center px-1 py-0.5 rounded bg-[#E3F2FD] text-[#0D47A1] font-bold mr-1">N/A</span>No aplica</span>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
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
                <ImportResultPanel result={importResult} />
                <div className="flex justify-end mt-4">
                  <Button variant="outline" onClick={closeImportDialog}>Cerrar</Button>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
};

export default Integrators;
