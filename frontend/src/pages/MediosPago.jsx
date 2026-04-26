import { useState, useEffect, useRef } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Checkbox } from '../components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { ImportResultPanel } from '../components/ImportResultPanel';
import { MigrationButtons } from '../components/MigrationButtons';
import { Plus, Pencil, Trash2, Upload, FileSpreadsheet, FileText, Settings2, RefreshCw, Layers, Monitor, Globe, Smartphone, Link, LinkIcon, Box, Wrench, Search, Building2, FileBarChart } from 'lucide-react';

const SERVICE_TYPES = [
  { id: 'Producto', name: 'Producto', icon: Box, description: 'Tangible, requiere despacho (Pinpads, Cables, etc.)' },
  { id: 'Servicio', name: 'Servicio', icon: Wrench, description: 'Intangible o configuración (Mantenimiento, Licencia, etc.)' }
];
import api from '../utils/api';
import { toast } from 'sonner';
import { usePermission } from '../hooks/usePermission';

const APPLICATION_TYPES = [
  { id: 'setup', name: 'Solo Setup', icon: Settings2, description: 'Solo gastos de implementación inicial' },
  { id: 'recurring', name: 'Solo Costos Recurrentes', icon: RefreshCw, description: 'Solo cargos mensuales/periódicos' },
  { id: 'both', name: 'Ambos', icon: Layers, description: 'Aplica a Setup y Costos Recurrentes' }
];

const PRODUCT_TYPES = [
  { id: 'vpos_enabled', name: 'VPOS', icon: Monitor, description: 'Cajas Registradoras' },
  { id: 'gateway_enabled', name: 'Payment Gateway', icon: Globe, description: 'Ecommerce' },
  { id: 'mpos_enabled', name: 'MPOS', icon: Smartphone, description: 'Tablet/Android' },
  { id: 'link_enabled', name: 'Link de Pago', icon: Link, description: 'Links de cobro' }
];

const TIPO_CORP_OPTIONS = [
  { id: 'Derecho de Uso', label: 'Derecho de Uso', description: 'Licencias o modelos de usufructo del software/hardware' },
  { id: 'Apoyo Técnico', label: 'Apoyo Técnico', description: 'Asistencia durante implementación o preventa' },
  { id: 'Soporte y Monitoreo', label: 'Soporte y Monitoreo', description: 'Mantenimiento continuo y vigilancia operativa' },
];

export const MediosPago = () => {
  const { canEdit } = usePermission('medios_pago');
  const [mediosPago, setMediosPago] = useState([]);
  const [recurringServices, setRecurringServices] = useState([]); // Servicios recurrentes para vinculación
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingMedioPago, setEditingMedioPago] = useState(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deleteMedioPagoData, setDeleteMedioPagoData] = useState({ id: null, name: null });
  const [formData, setFormData] = useState({
    name: '',
    service_type: '',
    tipo_corp: '',
    application_type: '',
    vpos_enabled: true,
    gateway_enabled: true,
    mpos_enabled: true,
    link_enabled: true,
    setup_cost_conventional: '',
    monthly_cost_conventional: '',
    setup_cost_outsourcing: '',
    monthly_cost_outsourcing: '',
    description: '',
    linked_recurring_service_id: ''
  });
  const fileInputRef = useRef(null);
  const [importResult, setImportResult] = useState(null);
  const [showImportResult, setShowImportResult] = useState(false);
  // Modal "Bancos asociados al producto"
  const [banksModal, setBanksModal] = useState({ open: false, loading: false, service: null, banks: [] });
  const [reportLoading, setReportLoading] = useState(false);
  const [filterServiceType, setFilterServiceType] = useState('all');
  const [filterComponent, setFilterComponent] = useState('all');
  const [filterAppType, setFilterAppType] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    fetchMediosPago();
    fetchRecurringServices();
  }, []);

  const fetchMediosPago = async () => {
    try {
      const response = await api.get('/services');
      setMediosPago(response.data);
    } catch (error) {
      console.error('Error fetching medios de pago:', error);
      toast.error('Error al cargar medios de pago');
    } finally {
      setLoading(false);
    }
  };

  // Cargar servicios recurrentes disponibles para vinculación
  const fetchRecurringServices = async () => {
    try {
      const response = await api.get('/services?application_type=recurring_available');
      setRecurringServices(response.data);
    } catch (error) {
      console.error('Error fetching recurring services:', error);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.service_type) {
      toast.error('Seleccione el tipo: Producto o Servicio');
      return;
    }

    if (!formData.application_type) {
      toast.error('Seleccione el tipo de aplicación');
      return;
    }

    if (!formData.tipo_corp) {
      toast.error('Seleccione el Tipo Corporativo');
      return;
    }

    if (!formData.vpos_enabled && !formData.gateway_enabled && !formData.mpos_enabled && !formData.link_enabled) {
      toast.error('Seleccione al menos un tipo de producto');
      return;
    }
    
    try {
      const payload = {
        ...formData,
        category: 'General',
        service_type: formData.service_type,
        setup_cost_conventional: formData.application_type !== 'recurring' ? (parseFloat(formData.setup_cost_conventional) || 0) : 0,
        monthly_cost_conventional: formData.application_type !== 'setup' ? (parseFloat(formData.monthly_cost_conventional) || 0) : 0,
        setup_cost_outsourcing: formData.application_type !== 'recurring' ? (parseFloat(formData.setup_cost_outsourcing) || 0) : 0,
        monthly_cost_outsourcing: formData.application_type !== 'setup' ? (parseFloat(formData.monthly_cost_outsourcing) || 0) : 0,
        // Solo guardar vinculación si es tipo setup o both
        linked_recurring_service_id: (formData.application_type === 'setup' || formData.application_type === 'both') 
          ? (formData.linked_recurring_service_id || null) 
          : null
      };

      if (editingMedioPago) {
        await api.put(`/services/${editingMedioPago.service_id}`, payload);
        toast.success('Medio de pago actualizado exitosamente');
      } else {
        await api.post('/services', payload);
        toast.success('Medio de pago creado exitosamente');
      }
      setDialogOpen(false);
      resetForm();
      fetchMediosPago();
    } catch (error) {
      console.error('Error saving medio de pago:', error);
      toast.error('Error al guardar medio de pago');
    }
  };

  const handleDelete = async (serviceId) => {
    const medioPago = mediosPago.find(m => m.service_id === serviceId);
    setDeleteMedioPagoData({ id: serviceId, name: medioPago?.name || 'este medio de pago' });
    setDeleteConfirmOpen(true);
  };

  const executeDelete = async () => {
    const serviceId = deleteMedioPagoData.id;
    setDeleteConfirmOpen(false);
    
    if (!serviceId) return;
    
    try {
      await api.delete(`/services/${serviceId}`);
      toast.success('Medio de pago eliminado exitosamente');
      fetchMediosPago();
    } catch (error) {
      console.error('Error deleting medio de pago:', error);
      if (error.response?.data?.detail) {
        toast.error(error.response.data.detail);
      } else {
        toast.error('Error al eliminar medio de pago');
      }
    } finally {
      setDeleteMedioPagoData({ id: null, name: null });
    }
  };

  const openEditDialog = (medioPago) => {
    setEditingMedioPago(medioPago);
    setFormData({
      name: medioPago.name,
      service_type: medioPago.service_type || 'Servicio',
      tipo_corp: medioPago.tipo_corp || '',
      application_type: medioPago.application_type || 'both',
      vpos_enabled: medioPago.vpos_enabled !== false,
      gateway_enabled: medioPago.gateway_enabled !== false,
      mpos_enabled: medioPago.mpos_enabled !== false,
      link_enabled: medioPago.link_enabled !== false,
      setup_cost_conventional: medioPago.setup_cost_conventional?.toString() || '0',
      monthly_cost_conventional: medioPago.monthly_cost_conventional?.toString() || '0',
      setup_cost_outsourcing: medioPago.setup_cost_outsourcing?.toString() || '0',
      monthly_cost_outsourcing: medioPago.monthly_cost_outsourcing?.toString() || '0',
      description: medioPago.description || '',
      linked_recurring_service_id: medioPago.linked_recurring_service_id || ''
    });
    setDialogOpen(true);
  };

  const resetForm = () => {
    setFormData({
      name: '',
      service_type: '',
      tipo_corp: '',
      application_type: '',
      vpos_enabled: true,
      gateway_enabled: true,
      mpos_enabled: true,
      link_enabled: true,
      setup_cost_conventional: '',
      monthly_cost_conventional: '',
      setup_cost_outsourcing: '',
      monthly_cost_outsourcing: '',
      description: '',
      linked_recurring_service_id: ''
    });
    setEditingMedioPago(null);
  };

  const handleDialogClose = (open) => {
    setDialogOpen(open);
    if (!open) resetForm();
  };

  const handleFileImport = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      toast.loading('Procesando archivo...', { id: 'import-loading' });
      
      const response = await api.post('/services/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      toast.dismiss('import-loading');
      
      const result = response.data;
      setImportResult(result);
      setShowImportResult(true);
      
      if (result.status === 'success') {
        toast.success(`${result.success_count} medios de pago importados exitosamente`);
      } else if (result.status === 'partial') {
        toast.warning(`Importación parcial: ${result.success_count} exitosos, ${result.error_count} con errores`);
      } else {
        toast.error(result.message || 'Error en la importación');
      }
      
      fetchMediosPago();
    } catch (error) {
      toast.dismiss('import-loading');
      console.error('Error importing medios de pago:', error);
      toast.error('Error al importar. Verifique el formato del archivo.');
    }
    
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const closeImportResult = () => {
    setShowImportResult(false);
    setImportResult(null);
  };

  const exportToCSV = () => {
    const headers = ['Nombre', 'Tipo', 'Tipo Corp', 'Tipo Aplicación', 'VPOS', 'Gateway', 'MPOS', 'Link', 'Setup Conv.', 'Mensual Conv.', 'Setup Outs.', 'Mensual Outs.', 'Descripción'];
    const csvContent = [
      headers.join(','),
      ...mediosPago.map(s => [
        `"${s.name}"`,
        `"${s.service_type || 'Servicio'}"`,
        `"${s.tipo_corp || ''}"`,
        `"${s.application_type || 'both'}"`,
        s.vpos_enabled !== false ? 'Sí' : 'No',
        s.gateway_enabled !== false ? 'Sí' : 'No',
        s.mpos_enabled !== false ? 'Sí' : 'No',
        s.link_enabled !== false ? 'Sí' : 'No',
        s.setup_cost_conventional || 0,
        s.monthly_cost_conventional || 0,
        s.setup_cost_outsourcing || 0,
        s.monthly_cost_outsourcing || 0,
        `"${s.description || ''}"`
      ].join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'medios_de_pago.csv';
    link.click();
    toast.success('Archivo CSV descargado');
  };

  const exportToPDF = async () => {
    try {
      const response = await api.get('/services/export/pdf', { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.download = 'medios_de_pago.pdf';
      link.click();
      toast.success('PDF descargado exitosamente');
    } catch (error) {
      console.error('Error exporting to PDF:', error);
      toast.error('Error al exportar a PDF');
    }
  };

  const openBanksModal = async (service) => {
    setBanksModal({ open: true, loading: true, service, banks: [] });
    try {
      const { data } = await api.get(`/services/${service.service_id}/banks`);
      setBanksModal({ open: true, loading: false, service, banks: data.banks || [] });
    } catch (err) {
      toast.error(`Error: ${err.response?.data?.detail || err.message}`);
      setBanksModal({ open: false, loading: false, service: null, banks: [] });
    }
  };

  const downloadBanksByProductReport = async () => {
    setReportLoading(true);
    try {
      const res = await api.get('/services/report/banks-by-product/pdf', { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url;
      const ts = new Date().toISOString().slice(0, 16).replace(/[-:T]/g, '');
      a.download = `bancos_por_producto_${ts}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Reporte "Bancos por Producto" descargado');
    } catch (err) {
      toast.error(`Error al generar reporte: ${err.response?.data?.detail || err.message}`);
    } finally {
      setReportLoading(false);
    }
  };

  const getApplicationTypeBadge = (type) => {
    switch(type) {
      case 'setup':
        return <span className="px-2 py-0.5 text-xs font-medium bg-purple-100 text-purple-700 rounded">Setup</span>;
      case 'recurring':
        return <span className="px-2 py-0.5 text-xs font-medium bg-amber-100 text-amber-700 rounded">Recurrente</span>;
      default:
        return <span className="px-2 py-0.5 text-xs font-medium bg-brand-green-50 text-brand-green-600 rounded">Ambos</span>;
    }
  };

  const getProductBadges = (medioPago) => {
    const badges = [];
    if (medioPago.vpos_enabled !== false) badges.push({ name: 'VPOS', color: 'bg-blue-100 text-blue-700' });
    if (medioPago.gateway_enabled !== false) badges.push({ name: 'Gateway', color: 'bg-green-100 text-green-700' });
    if (medioPago.mpos_enabled !== false) badges.push({ name: 'MPOS', color: 'bg-purple-100 text-purple-700' });
    if (medioPago.link_enabled !== false) badges.push({ name: 'Link', color: 'bg-amber-100 text-amber-700' });
    return badges;
  };

  const showSetupFields = formData.application_type === 'setup' || formData.application_type === 'both';
  const showRecurringFields = formData.application_type === 'recurring' || formData.application_type === 'both';
  const showLinkedField = formData.application_type === 'setup' || formData.application_type === 'both';

  // Obtener nombre del servicio recurrente vinculado
  const getLinkedServiceName = (serviceId) => {
    if (!serviceId) return null;
    const service = recurringServices.find(s => s.service_id === serviceId);
    return service?.name || null;
  };

  // Filtrar servicios recurrentes para no incluir el mismo servicio que se está editando
  const getAvailableRecurringServices = () => {
    // Filtrar Medios de Pago: Categoría = Servicio, Tipo = Recurrente (recurring o both)
    const filtered = mediosPago.filter(s => 
      s.service_type === 'Servicio' && 
      (s.application_type === 'recurring' || s.application_type === 'both')
    );
    if (!editingMedioPago) return filtered;
    return filtered.filter(s => s.service_id !== editingMedioPago.service_id);
  };

  if (loading) {
    return (
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center bg-white">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-green-600 mx-auto"></div>
            <p className="mt-4 text-slate-900">Cargando medios de pago...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-white">
      <Sidebar />
      
      <main className="flex-1 p-8" data-testid="medios-pago-page">
        <div className="max-w-7xl mx-auto">
          <div className="flex justify-between items-center mb-8">
            <div>
              <h1 className="text-4xl font-bold text-slate-900 font-manrope mb-2">
                Medios de Pago
              </h1>
              <p className="text-slate-600">Catálogo de medios de pago y conceptos facturables</p>
            </div>
            
            <div className="flex gap-2">
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileImport}
                accept=".csv,.xlsx,.xls"
                className="hidden"
              />
              {canEdit && <Button
                variant="outline"
                onClick={() => fileInputRef.current?.click()}
                className="border-brand-blue-600 text-brand-blue-600 hover:bg-brand-blue-50"
              >
                <Upload size={18} className="mr-2" />
                Importar
              </Button>}
              <Button
                variant="outline"
                onClick={exportToCSV}
                className="border-brand-green-600 text-brand-green-600 hover:bg-brand-green-50"
              >
                <FileSpreadsheet size={18} className="mr-2" />
                Excel/CSV
              </Button>
              <Button
                variant="outline"
                onClick={exportToPDF}
                className="border-brand-blue-600 text-brand-blue-600 hover:bg-brand-blue-50"
              >
                <FileText size={18} className="mr-2" />
                PDF
              </Button>
              <Button
                variant="outline"
                onClick={downloadBanksByProductReport}
                disabled={reportLoading}
                data-testid="banks-by-product-report-btn"
                className="border-indigo-600 text-indigo-700 hover:bg-indigo-50"
              >
                <FileBarChart size={18} className="mr-2" />
                {reportLoading ? 'Generando...' : 'Bancos por Producto'}
              </Button>
              {canEdit && <Dialog open={dialogOpen} onOpenChange={handleDialogClose}>
                <DialogTrigger asChild>
                  <Button
                    data-testid="add-medio-pago-button"
                    className="bg-brand-green-600 hover:bg-brand-green-700 text-white"
                  >
                    <Plus size={20} className="mr-2" />
                    Nuevo Medio de Pago
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                  <DialogHeader>
                    <DialogTitle className="font-manrope text-2xl">
                      {editingMedioPago ? 'Editar Medio de Pago / Servicio' : 'Nuevo Medio de Pago / Servicio'}
                    </DialogTitle>
                  </DialogHeader>
                  <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                      <Label htmlFor="name">Nombre del Medio de Pago / Servicio</Label>
                      <Input
                        id="name"
                        data-testid="medio-pago-name-input"
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        placeholder="Ej: Tarjeta de Crédito, Débito Bancario, etc."
                        required
                      />
                    </div>

                    {/* Tipo: Producto o Servicio */}
                    <div>
                      <Label className="text-base font-semibold text-slate-900 mb-2 block">
                        Tipo <span className="text-red-500">*</span>
                      </Label>
                      <div className="grid grid-cols-2 gap-3">
                        {SERVICE_TYPES.map((type) => {
                          const Icon = type.icon;
                          const isSelected = formData.service_type === type.id;
                          return (
                            <div
                              key={type.id}
                              onClick={() => setFormData({ ...formData, service_type: type.id })}
                              className={`p-3 rounded-lg border-2 cursor-pointer transition-all flex items-center gap-3 ${
                                isSelected
                                  ? 'border-slate-800 bg-slate-50'
                                  : 'border-slate-200 hover:border-slate-300'
                              }`}
                              data-testid={`service-type-${type.id.toLowerCase()}`}
                            >
                              <div className={`p-2 rounded-lg ${isSelected ? 'bg-slate-800 text-white' : 'bg-slate-100 text-slate-500'}`}>
                                <Icon size={18} />
                              </div>
                              <div className="flex-1">
                                <p className="font-medium text-slate-900 text-sm">{type.name}</p>
                                <p className="text-xs text-slate-500">{type.description}</p>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* Tipo Corp */}
                    <div>
                      <Label className="text-base font-semibold text-slate-900 mb-2 block">
                        Tipo Corp <span className="text-red-500">*</span>
                      </Label>
                      <Select value={formData.tipo_corp} onValueChange={(v) => setFormData({ ...formData, tipo_corp: v })}>
                        <SelectTrigger data-testid="tipo-corp-select">
                          <SelectValue placeholder="Seleccione tipo corporativo..." />
                        </SelectTrigger>
                        <SelectContent>
                          {TIPO_CORP_OPTIONS.map(o => (
                            <SelectItem key={o.id} value={o.id}>
                              <div>
                                <span className="font-medium">{o.label}</span>
                                <span className="text-xs text-slate-400 ml-2">— {o.description}</span>
                              </div>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    {/* Compatibilidad con Productos */}
                    <div className="border-t pt-4">
                      <Label className="text-base font-semibold text-slate-900 mb-2 block">
                        Compatibilidad con Productos <span className="text-red-500">*</span>
                      </Label>
                      <p className="text-sm text-slate-500 mb-4">
                        Seleccione en qué tipos de cotización estará disponible este concepto
                      </p>
                      <div className="grid grid-cols-2 gap-3">
                        {PRODUCT_TYPES.map((type) => {
                          const Icon = type.icon;
                          const isChecked = formData[type.id];
                          return (
                            <label
                              key={type.id}
                              className={`flex items-center gap-3 p-3 rounded-lg border-2 cursor-pointer transition-all ${
                                isChecked
                                  ? 'border-brand-green-600 bg-brand-green-50'
                                  : 'border-slate-200 hover:border-slate-300'
                              }`}
                            >
                              <Checkbox
                                checked={isChecked}
                                onCheckedChange={(checked) => 
                                  setFormData({ ...formData, [type.id]: checked })
                                }
                              />
                              <Icon size={18} className={isChecked ? 'text-brand-green-600' : 'text-slate-400'} />
                              <div>
                                <p className="text-sm font-medium">{type.name}</p>
                                <p className="text-xs text-slate-500">{type.description}</p>
                              </div>
                            </label>
                          );
                        })}
                      </div>
                    </div>

                    {/* Tipo de Aplicación */}
                    <div className="border-t pt-4">
                      <Label className="text-base font-semibold text-slate-900 mb-2 block">
                        ¿A qué aplica este concepto? <span className="text-red-500">*</span>
                      </Label>
                      <p className="text-sm text-slate-500 mb-4">
                        Seleccione dónde debe aparecer en las cotizaciones
                      </p>
                      <div className="grid grid-cols-1 gap-2">
                        {APPLICATION_TYPES.map((type) => {
                          const Icon = type.icon;
                          const isSelected = formData.application_type === type.id;
                          return (
                            <div
                              key={type.id}
                              onClick={() => setFormData({ ...formData, application_type: type.id })}
                              className={`p-3 rounded-lg border-2 cursor-pointer transition-all flex items-center gap-3 ${
                                isSelected
                                  ? 'border-brand-blue-600 bg-brand-blue-50'
                                  : 'border-slate-200 hover:border-slate-300'
                              }`}
                              data-testid={`application-type-${type.id}`}
                            >
                              <div className={`p-2 rounded-lg ${isSelected ? 'bg-brand-blue-600 text-white' : 'bg-slate-100 text-slate-500'}`}>
                                <Icon size={18} />
                              </div>
                              <div className="flex-1">
                                <p className="font-medium text-slate-900 text-sm">{type.name}</p>
                                <p className="text-xs text-slate-500">{type.description}</p>
                              </div>
                              <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                                isSelected ? 'border-brand-blue-600 bg-brand-blue-600' : 'border-slate-300'
                              }`}>
                                {isSelected && <div className="w-1.5 h-1.5 rounded-full bg-white"></div>}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {formData.application_type && (
                      <>
                        {showSetupFields && (
                          <div className="border-t pt-4">
                            <div className="flex items-center gap-2 mb-3">
                              <Settings2 size={18} className="text-brand-blue-600" />
                              <h3 className="font-semibold text-sm text-brand-blue-600">Costos de Setup (Implementación)</h3>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                              <div>
                                <Label htmlFor="setup_cost_conventional">Modelo Convencional (USD)</Label>
                                <Input
                                  id="setup_cost_conventional"
                                  type="number"
                                  step="0.01"
                                  min="0"
                                  value={formData.setup_cost_conventional}
                                  onChange={(e) => setFormData({ ...formData, setup_cost_conventional: e.target.value })}
                                  placeholder="0.00"
                                />
                              </div>
                              <div>
                                <Label htmlFor="setup_cost_outsourcing">Modelo Outsourcing (USD)</Label>
                                <Input
                                  id="setup_cost_outsourcing"
                                  type="number"
                                  step="0.01"
                                  min="0"
                                  value={formData.setup_cost_outsourcing}
                                  onChange={(e) => setFormData({ ...formData, setup_cost_outsourcing: e.target.value })}
                                  placeholder="0.00"
                                />
                              </div>
                            </div>
                          </div>
                        )}

                        {showRecurringFields && (
                          <div className="border-t pt-4">
                            <div className="flex items-center gap-2 mb-3">
                              <RefreshCw size={18} className="text-brand-green-600" />
                              <h3 className="font-semibold text-sm text-brand-green-600">Costos Recurrentes (Mensuales)</h3>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                              <div>
                                <Label htmlFor="monthly_cost_conventional">Modelo Convencional (USD)</Label>
                                <Input
                                  id="monthly_cost_conventional"
                                  type="number"
                                  step="0.01"
                                  min="0"
                                  value={formData.monthly_cost_conventional}
                                  onChange={(e) => setFormData({ ...formData, monthly_cost_conventional: e.target.value })}
                                  placeholder="0.00"
                                />
                              </div>
                              <div>
                                <Label htmlFor="monthly_cost_outsourcing">Modelo Outsourcing (USD)</Label>
                                <Input
                                  id="monthly_cost_outsourcing"
                                  type="number"
                                  step="0.01"
                                  min="0"
                                  value={formData.monthly_cost_outsourcing}
                                  onChange={(e) => setFormData({ ...formData, monthly_cost_outsourcing: e.target.value })}
                                  placeholder="0.00"
                                />
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Vinculación con Concepto Recurrente - Solo para Setup */}
                        {showLinkedField && (
                          <div className="border-t pt-4">
                            <div className="flex items-center gap-2 mb-3">
                              <LinkIcon size={18} className="text-purple-600" />
                              <h3 className="font-semibold text-sm text-purple-600">Vinculación Automática</h3>
                            </div>
                            <p className="text-sm text-slate-500 mb-3">
                              Seleccione el concepto recurrente que se agregará automáticamente a las cotizaciones cuando se incluya este servicio de Setup.
                            </p>
                            <div>
                              <Label htmlFor="linked_recurring">Concepto Recurrente Asociado (Opcional)</Label>
                              <Select 
                                value={formData.linked_recurring_service_id} 
                                onValueChange={(value) => setFormData({ ...formData, linked_recurring_service_id: value === 'none' ? '' : value })}
                              >
                                <SelectTrigger data-testid="linked-recurring-select">
                                  <SelectValue placeholder="Seleccione un concepto recurrente..." />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="none">Sin vinculación</SelectItem>
                                  {getAvailableRecurringServices().map((service) => (
                                    <SelectItem key={service.service_id} value={service.service_id}>
                                      {service.name} 
                                      {service.monthly_cost_conventional > 0 && ` ($${service.monthly_cost_conventional.toFixed(2)}/mes)`}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                              {formData.linked_recurring_service_id && (
                                <p className="text-xs text-purple-600 mt-2">
                                  Al agregar este servicio a una cotización, se incluirá automáticamente el concepto recurrente seleccionado.
                                </p>
                              )}
                            </div>
                          </div>
                        )}
                      </>
                    )}

                    <div>
                      <Label htmlFor="description">Descripción (Opcional)</Label>
                      <Textarea
                        id="description"
                        value={formData.description}
                        onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                        rows={2}
                        placeholder="Información adicional sobre este medio de pago..."
                      />
                    </div>

                    <div className="flex justify-end gap-3 pt-2 border-t">
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => handleDialogClose(false)}
                      >
                        Cancelar
                      </Button>
                      <Button
                        type="submit"
                        data-testid="save-medio-pago-button"
                        className="bg-brand-green-600 hover:bg-brand-green-700 text-white"
                        disabled={!formData.application_type || !formData.service_type || !formData.tipo_corp}
                      >
                        {editingMedioPago ? 'Actualizar' : 'Guardar'}
                      </Button>
                    </div>
                  </form>
                </DialogContent>
              </Dialog>}
            </div>
          </div>

          {/* Import Result Panel */}
          {showImportResult && importResult && (
            <ImportResultPanel result={importResult} onClose={closeImportResult} />
          )}

          <div className="flex justify-end mb-4">
            <MigrationButtons module="payment-methods" label="Medios de Pago" onImported={fetchMediosPago} />
          </div>

          {/* Filter Bar */}
          <div className="bg-white rounded-lg border border-slate-200 p-3 mb-4">
            <div className="flex flex-wrap gap-3 items-center">
              <div className="flex-1 min-w-[180px] relative">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input placeholder="Buscar por nombre..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} className="pl-9 h-9 text-sm" data-testid="search-medios" />
              </div>
              {/* Filtro Categoría */}
              <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-0.5" data-testid="filter-categoria">
                {['all', 'Producto', 'Servicio'].map(t => (
                  <button key={t} onClick={() => setFilterServiceType(t)}
                    className={`px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors ${filterServiceType === t ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                    data-testid={`filter-cat-${t}`}>
                    {t === 'all' ? 'Categoría' : t === 'Producto' ? 'Productos' : 'Servicios'}
                  </button>
                ))}
              </div>
              {/* Filtro Componente */}
              <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-0.5" data-testid="filter-componente">
                {['all', 'vpos', 'gateway', 'mpos', 'link'].map(t => (
                  <button key={t} onClick={() => setFilterComponent(t)}
                    className={`px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors ${filterComponent === t ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                    data-testid={`filter-comp-${t}`}>
                    {t === 'all' ? 'Componente' : t === 'vpos' ? 'VPOS' : t === 'gateway' ? 'Gateway' : t === 'mpos' ? 'MPOS' : 'Link'}
                  </button>
                ))}
              </div>
              {/* Filtro Tipo */}
              <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-0.5" data-testid="filter-tipo">
                {['all', 'setup', 'recurring', 'both'].map(t => (
                  <button key={t} onClick={() => setFilterAppType(t)}
                    className={`px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors ${filterAppType === t ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                    data-testid={`filter-tipo-${t}`}>
                    {t === 'all' ? 'Tipo' : t === 'setup' ? 'Setup' : t === 'recurring' ? 'Recurrente' : 'Ambos'}
                  </button>
                ))}
              </div>
              {(searchTerm || filterServiceType !== 'all' || filterComponent !== 'all' || filterAppType !== 'all') && (
                <Button variant="ghost" size="sm" className="h-9 text-xs" onClick={() => { setSearchTerm(''); setFilterServiceType('all'); setFilterComponent('all'); setFilterAppType('all'); }}>Limpiar</Button>
              )}
            </div>
          </div>

          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Medio de Pago / Servicio
                  </th>
                  <th className="px-3 py-3 text-center text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Categoría
                  </th>
                  <th className="px-3 py-3 text-center text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Tipo Corp
                  </th>
                  <th className="px-3 py-3 text-center text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Componente
                  </th>
                  <th className="px-3 py-3 text-center text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Tipo
                  </th>
                  <th className="px-3 py-3 text-center text-sm font-medium text-brand-blue-600 uppercase tracking-wider" colSpan={2}>
                    Setup
                  </th>
                  <th className="px-3 py-3 text-center text-sm font-medium text-brand-green-600 uppercase tracking-wider" colSpan={2}>
                    Recurrente
                  </th>
                  <th className="px-3 py-3 text-center text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Acciones
                  </th>
                </tr>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th></th>
                  <th></th>
                  <th></th>
                  <th></th>
                  <th></th>
                  <th className="px-2 py-1 text-right text-xs font-medium text-slate-500">Conv.</th>
                  <th className="px-2 py-1 text-right text-xs font-medium text-slate-500">Outs.</th>
                  <th className="px-2 py-1 text-right text-xs font-medium text-slate-500">Conv.</th>
                  <th className="px-2 py-1 text-right text-xs font-medium text-slate-500">Outs.</th>
                  <th></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {mediosPago
                  .filter(m => {
                    if (filterServiceType !== 'all' && m.service_type !== filterServiceType) return false;
                    if (filterComponent !== 'all') {
                      const key = filterComponent === 'vpos' ? 'vpos_enabled' : filterComponent === 'gateway' ? 'gateway_enabled' : filterComponent === 'mpos' ? 'mpos_enabled' : 'link_enabled';
                      if (m[key] === false) return false;
                    }
                    if (filterAppType !== 'all' && (m.application_type || 'both') !== filterAppType) return false;
                    if (searchTerm && !m.name?.toLowerCase().includes(searchTerm.toLowerCase())) return false;
                    return true;
                  })
                  .map((medioPago) => {
                  const productBadges = getProductBadges(medioPago);
                  const linkedServiceName = getLinkedServiceName(medioPago.linked_recurring_service_id);
                  return (
                    <tr key={medioPago.service_id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-4 py-3">
                        <p className="font-medium text-slate-900">{medioPago.name}</p>
                        {medioPago.description && (
                          <p className="text-xs text-slate-500 mt-1 truncate max-w-xs">{medioPago.description}</p>
                        )}
                        {linkedServiceName && (
                          <div className="flex items-center gap-1 mt-1">
                            <LinkIcon size={12} className="text-purple-500" />
                            <span className="text-xs text-purple-600">{linkedServiceName}</span>
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-3 text-center">
                        {medioPago.service_type === 'Producto' ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium bg-orange-100 text-orange-700 rounded">
                            <Box size={12} />Producto
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium bg-cyan-100 text-cyan-700 rounded">
                            <Wrench size={12} />Servicio
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-3 text-center">
                        {medioPago.tipo_corp ? (
                          <span className="px-2 py-0.5 text-xs font-medium bg-indigo-100 text-indigo-700 rounded" data-testid={`tipo-corp-badge-${medioPago.service_id}`}>
                            {medioPago.tipo_corp}
                          </span>
                        ) : (
                          <span className="text-xs text-slate-300">—</span>
                        )}
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex flex-wrap gap-1 justify-center">
                          {productBadges.map((badge, i) => (
                            <span key={i} className={`px-1.5 py-0.5 text-xs font-medium rounded ${badge.color}`}>
                              {badge.name}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-3 py-3 text-center">
                        {getApplicationTypeBadge(medioPago.application_type)}
                      </td>
                      <td className="px-2 py-3 text-right font-mono text-brand-blue-600 text-sm">
                        {medioPago.application_type !== 'recurring' ? `$${(medioPago.setup_cost_conventional || 0).toFixed(2)}` : '-'}
                      </td>
                      <td className="px-2 py-3 text-right font-mono text-brand-blue-600 text-sm">
                        {medioPago.application_type !== 'recurring' ? `$${(medioPago.setup_cost_outsourcing || 0).toFixed(2)}` : '-'}
                      </td>
                      <td className="px-2 py-3 text-right font-mono text-brand-green-600 text-sm">
                        {medioPago.application_type !== 'setup' ? `$${(medioPago.monthly_cost_conventional || 0).toFixed(2)}` : '-'}
                      </td>
                      <td className="px-2 py-3 text-right font-mono text-brand-green-600 text-sm">
                        {medioPago.application_type !== 'setup' ? `$${(medioPago.monthly_cost_outsourcing || 0).toFixed(2)}` : '-'}
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex items-center justify-center gap-1">
                          <Button
                            size="sm"
                            variant="outline"
                            data-testid={`banks-medio-pago-${medioPago.service_id}`}
                            onClick={() => openBanksModal(medioPago)}
                            className="text-indigo-600 border-indigo-200 hover:bg-indigo-50"
                            title="Ver bancos asociados"
                          >
                            <Building2 size={14} className="mr-1" />Bancos
                          </Button>
                          {canEdit && <Button
                            size="sm"
                            variant="outline"
                            data-testid={`edit-medio-pago-${medioPago.service_id}`}
                            onClick={() => openEditDialog(medioPago)}
                          >
                            <Pencil size={14} />
                          </Button>}
                          {canEdit && <Button
                            size="sm"
                            variant="outline"
                            data-testid={`delete-medio-pago-${medioPago.service_id}`}
                            onClick={() => handleDelete(medioPago.service_id)}
                            className="text-red-600 hover:text-red-700 hover:border-red-300"
                          >
                            <Trash2 size={14} />
                          </Button>}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {mediosPago.length === 0 && (
              <div className="text-center py-12 text-slate-500">
                <p>No hay medios de pago registrados</p>
                <p className="text-sm mt-1">Agregue su primer medio de pago usando el botón superior</p>
              </div>
            )}
          </div>
        </div>
        
        {/* Modal de confirmación para Eliminar */}
        <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>¿Eliminar Medio de Pago?</AlertDialogTitle>
              <AlertDialogDescription>
                ¿Está seguro de que desea eliminar el medio de pago <strong>"{deleteMedioPagoData.name}"</strong>?
                <br /><br />
                <span className="text-red-600 font-medium">Esta acción es irreversible y podría afectar datos vinculados (bancos, cotizaciones).</span>
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancelar</AlertDialogCancel>
              <AlertDialogAction 
                onClick={executeDelete}
                className="bg-red-600 hover:bg-red-700 text-white"
              >
                Eliminar
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Modal: Bancos asociados al producto */}
        <Dialog open={banksModal.open} onOpenChange={(o) => !o && setBanksModal({ open: false, loading: false, service: null, banks: [] })}>
          <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto" data-testid="banks-modal">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 font-manrope">
                <Building2 className="text-indigo-600" size={22} />
                Bancos asociados a: <span className="text-indigo-700">{banksModal.service?.name}</span>
              </DialogTitle>
            </DialogHeader>
            {banksModal.loading ? (
              <div className="text-center py-10 text-slate-500">Cargando...</div>
            ) : banksModal.banks.length === 0 ? (
              <div className="text-center py-10 text-slate-500 italic">
                Este producto no está asociado a ningún banco.
              </div>
            ) : (
              <div className="space-y-2">
                <div className="text-sm text-slate-600 mb-2">
                  <strong>{banksModal.banks.length}</strong> banco(s) tienen este producto configurado.
                </div>
                <div className="border border-slate-200 rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 border-b border-slate-200">
                      <tr>
                        <th className="px-3 py-2 text-left font-semibold text-slate-700 w-10">#</th>
                        <th className="px-3 py-2 text-left font-semibold text-slate-700">Banco</th>
                        <th className="px-3 py-2 text-center font-semibold text-slate-700 w-24">Código</th>
                        <th className="px-3 py-2 text-center font-semibold text-slate-700">Componentes</th>
                      </tr>
                    </thead>
                    <tbody>
                      {banksModal.banks.map((b, idx) => {
                        const comps = [];
                        if (b.vpos_available) comps.push({ name: 'VPOS', icon: Monitor });
                        if (b.gateway_available) comps.push({ name: 'Gateway', icon: Globe });
                        if (b.mpos_available) comps.push({ name: 'mPOS', icon: Smartphone });
                        if (b.link_available) comps.push({ name: 'Link', icon: Link });
                        return (
                          <tr key={b.bank_id} className="border-b border-slate-100 hover:bg-slate-50">
                            <td className="px-3 py-2 text-slate-400 text-xs">{idx + 1}</td>
                            <td className="px-3 py-2">
                              <div className="flex items-center gap-2">
                                {b.bank_logo_url ? (
                                  <img src={b.bank_logo_url} alt={b.bank_name} className="w-6 h-6 object-contain rounded" />
                                ) : (
                                  <Building2 size={16} className="text-slate-400" />
                                )}
                                <span className="font-medium text-slate-800">{b.bank_name}</span>
                              </div>
                            </td>
                            <td className="px-3 py-2 text-center text-slate-500 font-mono text-xs">
                              {b.bank_code || '—'}
                            </td>
                            <td className="px-3 py-2">
                              <div className="flex flex-wrap items-center justify-center gap-1">
                                {comps.length === 0 ? (
                                  <span className="text-xs text-slate-400 italic">—</span>
                                ) : (
                                  comps.map((c) => {
                                    const Icon = c.icon;
                                    return (
                                      <span key={c.name} className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-cyan-50 text-cyan-700 border border-cyan-200 text-xs">
                                        <Icon size={11} />{c.name}
                                      </span>
                                    );
                                  })
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
};

export default MediosPago;
