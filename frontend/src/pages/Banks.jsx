import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { ImportResultPanel } from '../components/ImportResultPanel';
import { Plus, Pencil, Trash2, Package, Upload, FileSpreadsheet, FileText, Monitor, Globe, Smartphone, Link, ImagePlus, User, Phone, Mail, Building2, Hash, Eye, Rocket } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';
import { usePermission } from '../hooks/usePermission';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const COMPONENT_TYPES = [
  { id: 'vpos_available', name: 'VPOS', icon: Monitor, description: 'Cajas Registradoras' },
  { id: 'gateway_available', name: 'Gateway', icon: Globe, description: 'Ecommerce' },
  { id: 'mpos_available', name: 'MPOS', icon: Smartphone, description: 'Tablet/Android' },
  { id: 'link_available', name: 'Link', icon: Link, description: 'Links de cobro' }
];

const LogoUpload = ({ logoUrl, onUpload, onRemove }) => {
  const [dragging, setDragging] = useState(false);
  const [hovering, setHovering] = useState(false);
  const inputRef = useRef(null);

  const handleFile = useCallback(async (file) => {
    if (!file || !file.type.startsWith('image/')) {
      toast.error('Solo se permiten imágenes (PNG, JPG, WEBP)');
      return;
    }
    const fd = new FormData();
    fd.append('file', file);
    try {
      const res = await api.post('/banks/upload-logo', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      onUpload(res.data.logo_url);
      toast.success('Logo subido');
    } catch {
      toast.error('Error al subir logo');
    }
  }, [onUpload]);

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }, [handleFile]);

  return (
    <div
      className={`relative rounded-xl border-2 border-dashed flex items-center justify-center cursor-pointer transition-all ${dragging ? 'border-sky-500 bg-sky-50' : 'border-slate-300 bg-slate-50 hover:border-slate-400'}`}
      style={{ width: 150, height: 150 }}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
      data-testid="logo-upload-area"
    >
      <input ref={inputRef} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])} />
      {logoUrl ? (
        <>
          <img src={`${API_URL}${logoUrl}`} alt="Logo" className="w-[130px] h-[130px] object-contain rounded-lg bg-white" onError={(e) => { e.target.onerror = null; e.target.style.display = 'none'; }} />
          {hovering && (
            <div className="absolute inset-0 bg-black/50 rounded-xl flex flex-col items-center justify-center gap-2">
              <button type="button" onClick={() => inputRef.current?.click()} className="px-3 py-1.5 text-xs font-medium bg-white text-slate-800 rounded-md hover:bg-slate-100 transition-colors">
                Cambiar
              </button>
              {onRemove && (
                <button type="button" onClick={onRemove} className="px-3 py-1.5 text-xs font-medium bg-red-500 text-white rounded-md hover:bg-red-600 transition-colors">
                  Eliminar
                </button>
              )}
            </div>
          )}
        </>
      ) : (
        <div className="text-center" onClick={() => inputRef.current?.click()}>
          <ImagePlus size={32} className="mx-auto text-slate-400" />
          <p className="text-xs text-slate-400 mt-2">Subir Logo</p>
          <p className="text-[10px] text-slate-300 mt-0.5">PNG o JPG</p>
        </div>
      )}
    </div>
  );
};

export const Banks = () => {
  const { canEdit } = usePermission('bancos');
  const navigate = useNavigate();
  const [banks, setBanks] = useState([]);
  const [mediosPago, setMediosPago] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingBank, setEditingBank] = useState(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deleteBankData, setDeleteBankData] = useState({ id: null, name: null });
  const [formData, setFormData] = useState({
    name: '', type: 'Banco', country: 'Venezuela',
    rif: '', bank_code: '',
    contact_name: '', contact_phone: '', contact_email: '',
    bank_logo_url: '', products: []
  });
  const [newProduct, setNewProduct] = useState({
    product_name: '', description: '', service_id: '',
    vpos_available: false, gateway_available: false, mpos_available: false, link_available: false
  });
  const fileInputRef = useRef(null);
  const [importResult, setImportResult] = useState(null);
  const [showImportResult, setShowImportResult] = useState(false);

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      const [banksRes, mediosPagoRes] = await Promise.all([api.get('/banks'), api.get('/services')]);
      setBanks(banksRes.data);
      setMediosPago(mediosPagoRes.data);
    } catch { toast.error('Error al cargar datos'); }
    finally { setLoading(false); }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editingBank) {
        await api.put(`/banks/${editingBank.bank_id}`, formData);
        toast.success('Banco actualizado');
      } else {
        await api.post('/banks', formData);
        toast.success('Banco creado');
      }
      setDialogOpen(false);
      resetForm();
      fetchData();
    } catch { toast.error('Error al guardar banco'); }
  };

  const handleDelete = (bankId) => {
    const bank = banks.find(b => b.bank_id === bankId);
    setDeleteBankData({ id: bankId, name: bank?.name || 'este banco' });
    setDeleteConfirmOpen(true);
  };

  const executeDelete = async () => {
    const bankId = deleteBankData.id;
    setDeleteConfirmOpen(false);
    if (!bankId) return;
    try {
      await api.delete(`/banks/${bankId}`);
      toast.success('Banco eliminado');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al eliminar banco');
    } finally { setDeleteBankData({ id: null, name: null }); }
  };

  const handleMedioPagoSelect = (serviceId) => {
    const sel = mediosPago.find(m => m.service_id === serviceId);
    if (sel) {
      setNewProduct({
        ...newProduct, service_id: serviceId, product_name: sel.name,
        description: sel.description || '',
        vpos_available: sel.vpos_enabled !== false, gateway_available: sel.gateway_enabled !== false,
        mpos_available: sel.mpos_enabled !== false, link_available: sel.link_enabled !== false
      });
    }
  };

  const addProduct = () => {
    if (!newProduct.product_name) { toast.error('Seleccione un medio de pago'); return; }
    setFormData({ ...formData, products: [...formData.products, { ...newProduct }] });
    setNewProduct({ product_name: '', description: '', service_id: '', vpos_available: false, gateway_available: false, mpos_available: false, link_available: false });
  };

  const toggleProductComponent = (index, field) => {
    const updated = [...formData.products];
    updated[index] = { ...updated[index], [field]: !updated[index][field] };
    setFormData({ ...formData, products: updated });
  };

  const removeProduct = (index) => {
    setFormData({ ...formData, products: formData.products.filter((_, i) => i !== index) });
  };

  const openEditDialog = (bank) => {
    setEditingBank(bank);
    setFormData({
      name: bank.name, type: bank.type, country: bank.country,
      rif: bank.rif || '', bank_code: bank.bank_code || '',
      contact_name: bank.contact_name || '', contact_phone: bank.contact_phone || '',
      contact_email: bank.contact_email || '', bank_logo_url: bank.bank_logo_url || '',
      products: bank.products || []
    });
    setDialogOpen(true);
  };

  const resetForm = () => {
    setFormData({
      name: '', type: 'Banco', country: 'Venezuela',
      rif: '', bank_code: '',
      contact_name: '', contact_phone: '', contact_email: '',
      bank_logo_url: '', products: []
    });
    setNewProduct({ product_name: '', description: '', service_id: '', vpos_available: false, gateway_available: false, mpos_available: false, link_available: false });
    setEditingBank(null);
  };

  const handleDialogClose = (open) => { setDialogOpen(open); if (!open) resetForm(); };

  const handleFileImport = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    try {
      toast.loading('Procesando archivo...', { id: 'import-loading' });
      const response = await api.post('/banks/import', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      toast.dismiss('import-loading');
      const result = response.data;
      setImportResult(result); setShowImportResult(true);
      if (result.status === 'success') toast.success(`${result.success_count} bancos importados`);
      else if (result.status === 'partial') toast.warning(`Parcial: ${result.success_count} exitosos, ${result.error_count} errores`);
      else toast.error(result.message || 'Error en importación');
      fetchData();
    } catch { toast.dismiss('import-loading'); toast.error('Error al importar bancos'); }
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const exportToCSV = () => {
    const headers = ['Nombre', 'Tipo', 'País', 'RIF', 'Código', 'Contacto', 'Teléfono', 'Email', 'Productos'];
    const csvContent = [
      headers.join(','),
      ...banks.map(b => [
        `"${b.name}"`, `"${b.type}"`, `"${b.country}"`, `"${b.rif || ''}"`, `"${b.bank_code || ''}"`,
        `"${b.contact_name || ''}"`, `"${b.contact_phone || ''}"`, `"${b.contact_email || ''}"`,
        `"${(b.products || []).map(p => p.product_name).join('; ')}"`
      ].join(','))
    ].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'bancos.csv';
    link.click();
    toast.success('CSV descargado');
  };

  const exportToPDF = async () => {
    try {
      const response = await api.get('/banks/export/pdf', { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.download = 'bancos.pdf';
      link.click();
      toast.success('PDF descargado');
    } catch { toast.error('Error al exportar PDF'); }
  };

  const getProductChips = (products) => {
    if (!products || products.length === 0) return [];
    const unique = new Map();
    products.forEach(p => {
      if (!unique.has(p.product_name)) unique.set(p.product_name, p);
    });
    return Array.from(unique.values());
  };

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
      <main className="flex-1 p-8" data-testid="banks-page">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="flex justify-between items-center mb-8">
            <div>
              <h1 className="text-4xl font-bold text-slate-900 font-manrope mb-2">Bancos y Entidades</h1>
              <p className="text-slate-600">Gestione bancos, medios de pago y contactos institucionales</p>
            </div>
            <div className="flex gap-2">
              <input type="file" ref={fileInputRef} onChange={handleFileImport} accept=".csv,.xlsx,.xls" className="hidden" />
              {canEdit && <Button variant="outline" onClick={() => fileInputRef.current?.click()} className="border-brand-blue-600 text-brand-blue-600 hover:bg-brand-blue-50">
                <Upload size={18} className="mr-2" />Importar
              </Button>}
              <Button variant="outline" onClick={exportToCSV} className="border-brand-green-600 text-brand-green-600 hover:bg-brand-green-50">
                <FileSpreadsheet size={18} className="mr-2" />CSV
              </Button>
              <Button variant="outline" onClick={exportToPDF} className="border-brand-blue-600 text-brand-blue-600 hover:bg-brand-blue-50">
                <FileText size={18} className="mr-2" />PDF
              </Button>
              {canEdit && <Dialog open={dialogOpen} onOpenChange={handleDialogClose}>
                <DialogTrigger asChild>
                  <Button data-testid="add-bank-button" className="bg-brand-green-600 hover:bg-brand-green-700 text-white">
                    <Plus size={20} className="mr-2" />Nuevo Banco
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                  <DialogHeader>
                    <DialogTitle className="font-manrope text-2xl">{editingBank ? 'Editar Banco' : 'Nuevo Banco'}</DialogTitle>
                  </DialogHeader>
                  <form onSubmit={handleSubmit} className="space-y-6">
                    {/* Logo + Basic Info */}
                    <div className="flex gap-5 items-start">
                      <LogoUpload
                        logoUrl={formData.bank_logo_url}
                        onUpload={(url) => setFormData({ ...formData, bank_logo_url: url })}
                        onRemove={() => setFormData({ ...formData, bank_logo_url: '' })}
                      />
                      <div className="flex-1 grid grid-cols-2 gap-3">
                        <div className="col-span-2">
                          <Label htmlFor="name">Nombre de la Entidad</Label>
                          <Input id="name" data-testid="bank-name-input" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} required />
                        </div>
                        <div>
                          <Label htmlFor="type">Tipo</Label>
                          <Select value={formData.type} onValueChange={(v) => setFormData({ ...formData, type: v })}>
                            <SelectTrigger><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="Banco">Banco</SelectItem>
                              <SelectItem value="Fintech">Fintech</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label htmlFor="country">País</Label>
                          <Select value={formData.country} onValueChange={(v) => setFormData({ ...formData, country: v })}>
                            <SelectTrigger><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="Venezuela">Venezuela</SelectItem>
                              <SelectItem value="Estados Unidos">Estados Unidos</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                    </div>

                    {/* Fiscal Info */}
                    <div className="border-t pt-4">
                      <h3 className="font-semibold text-sm text-slate-500 uppercase tracking-wide mb-3 flex items-center gap-2">
                        <Building2 size={16} />Información Fiscal
                      </h3>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <Label htmlFor="rif">RIF</Label>
                          <Input id="rif" data-testid="bank-rif-input" placeholder="J-00000000-0" value={formData.rif} onChange={(e) => setFormData({ ...formData, rif: e.target.value })} />
                        </div>
                        <div>
                          <Label htmlFor="bank_code">Código Bancario</Label>
                          <Input id="bank_code" data-testid="bank-code-input" placeholder="0102" value={formData.bank_code} onChange={(e) => setFormData({ ...formData, bank_code: e.target.value })} />
                        </div>
                      </div>
                    </div>

                    {/* Contact Info */}
                    <div className="border-t pt-4">
                      <h3 className="font-semibold text-sm text-slate-500 uppercase tracking-wide mb-3 flex items-center gap-2">
                        <User size={16} />Contacto Institucional
                      </h3>
                      <div className="grid grid-cols-1 gap-3">
                        <div>
                          <Label htmlFor="contact_name">Nombre del Contacto</Label>
                          <Input id="contact_name" data-testid="bank-contact-name" placeholder="Juan Pérez - Gerente de Canales" value={formData.contact_name} onChange={(e) => setFormData({ ...formData, contact_name: e.target.value })} />
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <Label htmlFor="contact_phone">Teléfono</Label>
                            <Input id="contact_phone" data-testid="bank-contact-phone" placeholder="+58 412-0000000" value={formData.contact_phone} onChange={(e) => setFormData({ ...formData, contact_phone: e.target.value })} />
                          </div>
                          <div>
                            <Label htmlFor="contact_email">Correo Electrónico</Label>
                            <Input id="contact_email" data-testid="bank-contact-email" placeholder="jperez@banco.com" value={formData.contact_email} onChange={(e) => setFormData({ ...formData, contact_email: e.target.value })} />
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Medios de Pago */}
                    <div className="border-t pt-4">
                      <h3 className="font-semibold text-sm text-slate-500 uppercase tracking-wide mb-3 flex items-center gap-2">
                        <Package size={16} />Medios de Pago Asociados
                      </h3>
                      <div className="space-y-2 mb-4">
                        {formData.products.map((product, index) => (
                          <div key={index} className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg border">
                            <span className="text-sm font-medium text-slate-800 truncate min-w-0 flex-shrink mr-3">{product.product_name}</span>
                            <div className="flex items-center gap-1.5 shrink-0">
                              <button type="button" onClick={() => toggleProductComponent(index, 'vpos_available')}
                                className={`px-2 py-1 text-[10px] font-bold rounded transition-colors ${product.vpos_available ? 'bg-blue-500 text-white' : 'bg-slate-200 text-slate-400 line-through'}`}
                                data-testid={`toggle-vpos-${index}`}>VPOS</button>
                              <button type="button" onClick={() => toggleProductComponent(index, 'mpos_available')}
                                className={`px-2 py-1 text-[10px] font-bold rounded transition-colors ${product.mpos_available ? 'bg-purple-500 text-white' : 'bg-slate-200 text-slate-400 line-through'}`}
                                data-testid={`toggle-mpos-${index}`}>MPOS</button>
                              <button type="button" onClick={() => toggleProductComponent(index, 'gateway_available')}
                                className={`px-2 py-1 text-[10px] font-bold rounded transition-colors ${product.gateway_available ? 'bg-green-500 text-white' : 'bg-slate-200 text-slate-400 line-through'}`}
                                data-testid={`toggle-gw-${index}`}>PG</button>
                              <button type="button" onClick={() => toggleProductComponent(index, 'link_available')}
                                className={`px-2 py-1 text-[10px] font-bold rounded transition-colors ${product.link_available ? 'bg-amber-500 text-white' : 'bg-slate-200 text-slate-400 line-through'}`}
                                data-testid={`toggle-link-${index}`}>Link</button>
                              <Button type="button" size="sm" variant="ghost" onClick={() => removeProduct(index)} className="text-red-500 h-7 w-7 p-0 ml-1">
                                <Trash2 size={14} />
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                      <div className="bg-sky-50 rounded-lg p-4 border border-sky-200">
                        <p className="text-sm font-medium text-sky-700 mb-2">Agregar Medio de Pago</p>
                        <div className="flex gap-2">
                          <Select value={newProduct.service_id} onValueChange={handleMedioPagoSelect}>
                            <SelectTrigger data-testid="select-medio-pago-bank" className="flex-1">
                              <SelectValue placeholder="Seleccione..." />
                            </SelectTrigger>
                            <SelectContent>
                              {mediosPago.map((m) => (<SelectItem key={m.service_id} value={m.service_id}>{m.name}</SelectItem>))}
                            </SelectContent>
                          </Select>
                          <Button type="button" onClick={addProduct} disabled={!newProduct.service_id} className="bg-sky-600 hover:bg-sky-700 text-white">
                            <Plus size={16} />
                          </Button>
                        </div>
                        {newProduct.service_id && (
                          <div className="mt-3 grid grid-cols-4 gap-2">
                            {COMPONENT_TYPES.map((c) => {
                              const Icon = c.icon;
                              const on = newProduct[c.id];
                              return (
                                <button type="button" key={c.id}
                                  onClick={() => setNewProduct({ ...newProduct, [c.id]: !on })}
                                  className={`flex items-center gap-1.5 p-2 rounded border text-xs transition-colors ${on ? 'border-green-400 bg-green-50 text-green-700' : 'border-slate-200 bg-white text-slate-400'}`}
                                  data-testid={`new-toggle-${c.id}`}>
                                  <Icon size={14} />{c.name}
                                </button>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex justify-end gap-3 pt-2">
                      <Button type="button" variant="outline" onClick={() => handleDialogClose(false)}>Cancelar</Button>
                      <Button type="submit" data-testid="save-bank-button" className="bg-brand-green-600 hover:bg-brand-green-700 text-white">
                        {editingBank ? 'Actualizar' : 'Guardar'}
                      </Button>
                    </div>
                  </form>
                </DialogContent>
              </Dialog>}
            </div>
          </div>

          {showImportResult && importResult && (
            <ImportResultPanel result={importResult} onClose={() => { setShowImportResult(false); setImportResult(null); }} />
          )}

          {/* Integration Report Button */}
          <div className="mb-6">
            <Button onClick={() => navigate('/banks/integrations/report')}
              data-testid="integration-report-btn"
              className="bg-purple-600 hover:bg-purple-700 text-white w-full justify-center py-3 text-sm font-semibold">
              <Rocket size={18} className="mr-2" />
              Consulta de Proyectos en Proceso de Integración
            </Button>
          </div>

          {/* Bank Rows - Horizontal Layout */}
          <div className="space-y-3" data-testid="banks-list">
            {banks.map((bank) => {
              const chips = getProductChips(bank.products);
              const integrationsCount = (bank.integrations || []).filter(i => i.status !== 'Masificación').length;
              return (
                <div key={bank.bank_id} data-testid={`bank-row-${bank.bank_id}`}
                  className="bg-white rounded-lg border border-slate-200 p-4 hover:border-slate-300 hover:shadow-sm transition-all flex items-center gap-5">
                  
                  {/* Block 1: Logo */}
                  <div className="shrink-0 w-20 h-20 rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center overflow-hidden cursor-pointer"
                    onClick={() => navigate(`/banks/${bank.bank_id}`)}>
                    {bank.bank_logo_url ? (
                      <img src={`${API_URL}${bank.bank_logo_url}`} alt={bank.name} className="w-[70px] h-[70px] object-contain" onError={(e) => { e.target.onerror = null; e.target.style.display = 'none'; }} />
                    ) : (
                      <Building2 size={28} className="text-slate-400" />
                    )}
                  </div>

                  {/* Block 2: Fiscal Info */}
                  <div className="min-w-[200px] shrink-0">
                    <h3 className="text-base font-semibold text-slate-900 font-manrope leading-tight cursor-pointer hover:text-brand-blue-600 transition-colors"
                      onClick={() => navigate(`/banks/${bank.bank_id}`)}>{bank.name}</h3>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="px-1.5 py-0.5 text-[10px] font-semibold rounded bg-slate-100 text-slate-600">{bank.type}</span>
                      {bank.bank_code && (
                        <span className="text-xs text-slate-500 flex items-center gap-0.5">
                          <Hash size={10} />{bank.bank_code}
                        </span>
                      )}
                    </div>
                    {bank.rif && <p className="text-xs text-slate-500 mt-0.5">{bank.rif}</p>}
                  </div>

                  {/* Block 3: Payment Methods Chips + Counters */}
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap gap-1.5 mb-1.5">
                      {chips.length > 0 ? (
                        chips.slice(0, 5).map((p, i) => (
                          <span key={i} className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-sky-50 text-sky-700 border border-sky-200 whitespace-nowrap">
                            {p.product_name}
                          </span>
                        ))
                      ) : (
                        <span className="text-xs text-slate-400 italic">Sin medios de pago</span>
                      )}
                      {chips.length > 5 && (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-500">
                          +{chips.length - 5} más
                        </span>
                      )}
                    </div>
                    <div className="flex gap-3 text-xs">
                      <span className="text-emerald-600 font-medium">{chips.length} Activos</span>
                      {integrationsCount > 0 && (
                        <span className="text-purple-600 font-medium flex items-center gap-0.5">
                          <Rocket size={10} />{integrationsCount} en Integración
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Block 4: Contact + Actions */}
                  <div className="shrink-0 flex items-center gap-4">
                    {bank.contact_name && (
                      <div className="text-right hidden lg:block min-w-[140px]">
                        <p className="text-xs font-medium text-slate-700 truncate flex items-center justify-end gap-1"><User size={11} />{bank.contact_name}</p>
                        {bank.contact_phone && <p className="text-[11px] text-slate-500 truncate flex items-center justify-end gap-1"><Phone size={10} />{bank.contact_phone}</p>}
                        {bank.contact_email && <p className="text-[11px] text-slate-500 truncate flex items-center justify-end gap-1"><Mail size={10} />{bank.contact_email}</p>}
                      </div>
                    )}
                    <div className="flex gap-1.5">
                      <Button size="sm" variant="outline" data-testid={`view-bank-${bank.bank_id}`} onClick={() => navigate(`/banks/${bank.bank_id}`)} className="h-8 w-8 p-0 text-brand-blue-600 hover:text-brand-blue-700 hover:border-brand-blue-300">
                        <Eye size={14} />
                      </Button>
                      {canEdit && <Button size="sm" variant="outline" data-testid={`edit-bank-${bank.bank_id}`} onClick={() => openEditDialog(bank)} className="h-8 w-8 p-0">
                        <Pencil size={14} />
                      </Button>}
                      {canEdit && <Button size="sm" variant="outline" data-testid={`delete-bank-${bank.bank_id}`} onClick={() => handleDelete(bank.bank_id)} className="h-8 w-8 p-0 text-red-600 hover:text-red-700 hover:border-red-300">
                        <Trash2 size={14} />
                      </Button>}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {banks.length === 0 && (
            <div className="bg-white rounded-lg border border-slate-200 p-12 text-center text-slate-500">
              <Building2 size={40} className="mx-auto text-slate-300 mb-3" />
              <p>No hay bancos registrados</p>
              <p className="text-sm mt-1">Cree su primer banco usando el botón superior</p>
            </div>
          )}
        </div>

        <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Eliminar Banco</AlertDialogTitle>
              <AlertDialogDescription>
                Eliminar <strong>"{deleteBankData.name}"</strong>? <br />
                <span className="text-red-600 font-medium">Esta acción es irreversible.</span>
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancelar</AlertDialogCancel>
              <AlertDialogAction onClick={executeDelete} className="bg-red-600 hover:bg-red-700 text-white">Eliminar</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </main>
    </div>
  );
};

export default Banks;
