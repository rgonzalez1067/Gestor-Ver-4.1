import { useState, useEffect, useRef } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Textarea } from '../components/ui/textarea';
import { Plus, Pencil, Trash2, DollarSign, Upload, Download, Cpu, Cable, Box, Smartphone, Package, Wrench, Settings2, Cog, FileSpreadsheet, FileText, FileDown, AlertCircle, CheckCircle2, X } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';
import { usePermission } from '../hooks/usePermission';
import { MigrationButtons } from '../components/MigrationButtons';

// Categorías principales
const CATEGORIES = [
  { id: 'dispositivos', name: 'Bienes y Servicios', description: 'Hardware y equipos' },
  { id: 'servicios', name: 'Servicios', description: 'Mantenimiento, licencias, consultorías' },
  { id: 'repuestos', name: 'Repuestos', description: 'Componentes y piezas de reemplazo' }
];

// Tipos por categoría
const HARDWARE_TYPES = [
  // Dispositivos
  { id: 'Pinpad', name: 'Pinpad', icon: Cpu, color: 'bg-blue-100 text-blue-700', category: 'dispositivos' },
  { id: 'POS', name: 'Punto de Venta (POS)', icon: Smartphone, color: 'bg-green-100 text-green-700', category: 'dispositivos' },
  { id: 'Cable', name: 'Cable', icon: Cable, color: 'bg-yellow-100 text-yellow-700', category: 'dispositivos' },
  { id: 'Base', name: 'Base', icon: Box, color: 'bg-purple-100 text-purple-700', category: 'dispositivos' },
  { id: 'Accesorio', name: 'Accesorio', icon: Package, color: 'bg-slate-100 text-slate-700', category: 'dispositivos' },
  // Servicios
  { id: 'Mantenimiento', name: 'Mantenimiento', icon: Wrench, color: 'bg-orange-100 text-orange-700', category: 'servicios' },
  { id: 'Licencia', name: 'Licencia', icon: Settings2, color: 'bg-cyan-100 text-cyan-700', category: 'servicios' },
  { id: 'Consultoria', name: 'Consultoría', icon: Settings2, color: 'bg-indigo-100 text-indigo-700', category: 'servicios' },
  // Repuestos
  { id: 'Componente', name: 'Componente', icon: Cog, color: 'bg-rose-100 text-rose-700', category: 'repuestos' },
  { id: 'Pieza', name: 'Pieza Mecánica', icon: Cog, color: 'bg-amber-100 text-amber-700', category: 'repuestos' }
];

export const Hardware = () => {
  const { canEdit } = usePermission('dispositivos');
  const [hardwareList, setHardwareList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingHardware, setEditingHardware] = useState(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deleteHardwareData, setDeleteHardwareData] = useState({ id: null, name: null });
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [formData, setFormData] = useState({
    name: '',
    category: 'dispositivos',
    type: 'Pinpad',
    asset_type: 'Bien',
    price_usd: '',
    price_bs_usd: '',
    description: ''
  });
  const fileInputRef = useRef(null);
  
  // Estados para importación
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [importFile, setImportFile] = useState(null);
  const [importLoading, setImportLoading] = useState(false);
  const [importResult, setImportResult] = useState(null);

  useEffect(() => {
    fetchHardware();
  }, []);

  const fetchHardware = async () => {
    try {
      const response = await api.get('/hardware');
      setHardwareList(response.data);
    } catch (error) {
      console.error('Error fetching hardware:', error);
      toast.error('Error al cargar bienes y servicios');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        ...formData,
        price_usd: parseFloat(formData.price_usd) || 0,
        price_bs_usd: parseFloat(formData.price_bs_usd) || 0
      };

      if (editingHardware) {
        await api.put(`/hardware/${editingHardware.hardware_id}`, payload);
        toast.success('Registro actualizado exitosamente');
      } else {
        await api.post('/hardware', payload);
        toast.success('Registro creado exitosamente');
      }
      setDialogOpen(false);
      resetForm();
      fetchHardware();
    } catch (error) {
      console.error('Error saving hardware:', error);
      toast.error('Error al guardar registro');
    }
  };

  const handleDelete = async (hardwareId) => {
    const hardware = hardwareList.find(h => h.hardware_id === hardwareId);
    setDeleteHardwareData({ id: hardwareId, name: hardware?.name || 'este registro' });
    setDeleteConfirmOpen(true);
  };

  const executeDelete = async () => {
    const hardwareId = deleteHardwareData.id;
    setDeleteConfirmOpen(false);
    
    if (!hardwareId) return;
    
    try {
      await api.delete(`/hardware/${hardwareId}`);
      toast.success('Dispositivo eliminado exitosamente');
      fetchHardware();
    } catch (error) {
      console.error('Error deleting hardware:', error);
      if (error.response?.data?.detail) {
        toast.error(error.response.data.detail);
      } else {
        toast.error('Error al eliminar dispositivo');
      }
    } finally {
      setDeleteHardwareData({ id: null, name: null });
    }
  };

  const openEditDialog = (hardware) => {
    setEditingHardware(hardware);
    setFormData({
      name: hardware.name,
      type: hardware.type,
      asset_type: hardware.asset_type || 'Bien',
      price_usd: hardware.price_usd?.toString() || '0',
      price_bs_usd: hardware.price_bs_usd?.toString() || '0',
      description: hardware.description || ''
    });
    setDialogOpen(true);
  };

  const resetForm = () => {
    setFormData({
      name: '',
      type: 'Pinpad',
      asset_type: 'Bien',
      price_usd: '',
      price_bs_usd: '',
      description: ''
    });
    setEditingHardware(null);
  };

  // ==================== FUNCIONES DE IMPORTACIÓN/EXPORTACIÓN ====================

  // Descargar plantilla de importación
  const downloadTemplate = async () => {
    try {
      const token = localStorage.getItem('session_token');
      const backendUrl = process.env.REACT_APP_BACKEND_URL;
      
      const response = await fetch(`${backendUrl}/api/hardware/template`, {
        method: 'GET',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (!response.ok) throw new Error('Error al descargar plantilla');
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'plantilla_bienes_servicios.xlsx';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      
      toast.success('Plantilla descargada');
    } catch (error) {
      console.error('Error downloading template:', error);
      toast.error('Error al descargar plantilla');
    }
  };

  // Exportar a Excel
  const exportToExcel = async () => {
    const toastId = toast.loading('Exportando a Excel...');
    try {
      const token = localStorage.getItem('session_token');
      const backendUrl = process.env.REACT_APP_BACKEND_URL;
      
      const response = await fetch(`${backendUrl}/api/hardware/export/excel`, {
        method: 'GET',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (!response.ok) throw new Error('Error al exportar');
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `bienes_servicios_${new Date().toISOString().split('T')[0]}.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      
      toast.dismiss(toastId);
      toast.success('Archivo Excel descargado');
    } catch (error) {
      toast.dismiss(toastId);
      console.error('Error exporting to Excel:', error);
      toast.error('Error al exportar a Excel');
    }
  };

  // Exportar a PDF
  const exportToPDF = async () => {
    const toastId = toast.loading('Exportando a PDF...');
    try {
      const token = localStorage.getItem('session_token');
      const backendUrl = process.env.REACT_APP_BACKEND_URL;
      
      const response = await fetch(`${backendUrl}/api/hardware/export/pdf`, {
        method: 'GET',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (!response.ok) throw new Error('Error al exportar');
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `bienes_servicios_${new Date().toISOString().split('T')[0]}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      
      toast.dismiss(toastId);
      toast.success('Archivo PDF descargado');
    } catch (error) {
      toast.dismiss(toastId);
      console.error('Error exporting to PDF:', error);
      toast.error('Error al exportar a PDF');
    }
  };

  // Manejar archivo de importación
  const handleImportFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      setImportFile(file);
      setImportResult(null);
    }
  };

  // Ejecutar importación
  const executeImport = async () => {
    if (!importFile) {
      toast.error('Seleccione un archivo');
      return;
    }
    
    setImportLoading(true);
    setImportResult(null);
    
    try {
      const formData = new FormData();
      formData.append('file', importFile);
      
      const response = await api.post('/hardware/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      setImportResult(response.data);
      
      if (response.data.status === 'success') {
        toast.success(response.data.message);
        fetchHardware();
      } else if (response.data.status === 'partial') {
        toast.warning(response.data.message);
        fetchHardware();
      } else {
        toast.error(response.data.message);
      }
    } catch (error) {
      console.error('Error importing:', error);
      toast.error('Error al importar archivo');
      setImportResult({
        status: 'error',
        message: error.response?.data?.detail || 'Error desconocido',
        errors: []
      });
    } finally {
      setImportLoading(false);
    }
  };

  // Cerrar modal de importación
  const closeImportDialog = () => {
    setImportDialogOpen(false);
    setImportFile(null);
    setImportResult(null);
  };

  const handleDialogClose = (open) => {
    setDialogOpen(open);
    if (!open) resetForm();
  };

  const getTypeBadge = (type) => {
    const typeConfig = HARDWARE_TYPES.find(t => t.id === type) || HARDWARE_TYPES[4];
    const Icon = typeConfig.icon;
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded ${typeConfig.color}`}>
        <Icon size={12} />
        {typeConfig.name}
      </span>
    );
  };

  // Agrupar hardware por tipo
  const groupedByType = HARDWARE_TYPES.reduce((acc, type) => {
    acc[type.id] = hardwareList.filter(h => h.type === type.id);
    return acc;
  }, {});

  if (loading) {
    return (
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center bg-white">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-green-600 mx-auto"></div>
            <p className="mt-4 text-slate-900">Cargando dispositivos...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-white">
      <Sidebar />
      
      <main className="flex-1 p-8" data-testid="hardware-page">
        <div className="max-w-7xl mx-auto">
          <div className="flex justify-between items-center mb-8">
            <div>
              <h1 className="text-4xl font-bold text-slate-900 font-manrope mb-2">
                Bienes y Servicios
              </h1>
              <p className="text-slate-600">Catálogo de bienes y servicios de la empresa</p>
            </div>
            
            <div className="flex gap-2">
              {/* Botón Importar */}
              {canEdit && <Button
                variant="outline"
                onClick={() => setImportDialogOpen(true)}
                data-testid="import-hardware-btn"
                className="text-brand-blue-600 border-brand-blue-600 hover:bg-brand-blue-50"
              >
                <Upload size={18} className="mr-2" />
                Importar
              </Button>}
              
              {/* Dropdown Exportar */}
              <div className="relative group">
                <Button
                  variant="outline"
                  data-testid="export-hardware-btn"
                  className="text-brand-green-600 border-brand-green-600 hover:bg-brand-green-50"
                >
                  <Download size={18} className="mr-2" />
                  Exportar
                </Button>
                <div className="absolute right-0 mt-1 w-48 bg-white border border-slate-200 rounded-lg shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
                  <button
                    onClick={exportToExcel}
                    className="flex items-center gap-2 w-full px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 rounded-t-lg"
                    data-testid="export-excel-btn"
                  >
                    <FileSpreadsheet size={16} className="text-green-600" />
                    Exportar a Excel
                  </button>
                  <button
                    onClick={exportToPDF}
                    className="flex items-center gap-2 w-full px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 rounded-b-lg"
                    data-testid="export-pdf-btn"
                  >
                    <FileText size={16} className="text-red-600" />
                    Exportar a PDF
                  </button>
                </div>
              </div>
              
              {/* Botón Nuevo */}
              {canEdit && <Dialog open={dialogOpen} onOpenChange={handleDialogClose}>
                <DialogTrigger asChild>
                  <Button
                    data-testid="add-hardware-button"
                    className="bg-brand-green-600 hover:bg-brand-green-700 text-white"
                  >
                    <Plus size={20} className="mr-2" />
                    Nuevo Registro
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-xl">
                  <DialogHeader>
                    <DialogTitle className="font-manrope text-2xl">
                      {editingHardware ? 'Editar Registro' : 'Nuevo Registro'}
                    </DialogTitle>
                  </DialogHeader>
                  <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                      <Label htmlFor="name">Nombre</Label>
                      <Input
                        id="name"
                        data-testid="hardware-name-input"
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        placeholder="Ej: Verifone V240m"
                        required
                      />
                    </div>

                    <div>
                      <Label htmlFor="type">Tipo de Dispositivo</Label>
                      <Select
                        value={formData.type}
                        onValueChange={(value) => setFormData({ ...formData, type: value })}
                      >
                        <SelectTrigger data-testid="hardware-type-select">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {HARDWARE_TYPES.map((type) => {
                            const Icon = type.icon;
                            return (
                              <SelectItem key={type.id} value={type.id}>
                                <div className="flex items-center gap-2">
                                  <Icon size={14} />
                                  {type.name}
                                </div>
                              </SelectItem>
                            );
                          })}
                        </SelectContent>
                      </Select>
                    </div>

                    <div>
                      <Label>Clasificación *</Label>
                      <Select
                        value={formData.asset_type}
                        onValueChange={(value) => setFormData({ ...formData, asset_type: value })}
                      >
                        <SelectTrigger data-testid="hardware-asset-type-select">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="Bien">Bien (Activo físico)</SelectItem>
                          <SelectItem value="Servicio">Servicio (Intangible)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label htmlFor="price_usd">Precio Efectivo (USD)</Label>
                        <div className="relative">
                          <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                          <Input
                            id="price_usd"
                            type="number"
                            step="0.01"
                            min="0"
                            className="pl-9"
                            value={formData.price_usd}
                            onChange={(e) => setFormData({ ...formData, price_usd: e.target.value })}
                            placeholder="0.00"
                            required
                          />
                        </div>
                        <p className="text-xs text-slate-500 mt-1">Precio para pago en efectivo</p>
                      </div>
                      <div>
                        <Label htmlFor="price_bs_usd">Precio Bs/USD</Label>
                        <div className="relative">
                          <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                          <Input
                            id="price_bs_usd"
                            type="number"
                            step="0.01"
                            min="0"
                            className="pl-9"
                            value={formData.price_bs_usd}
                            onChange={(e) => setFormData({ ...formData, price_bs_usd: e.target.value })}
                            placeholder="0.00"
                            required
                          />
                        </div>
                        <p className="text-xs text-slate-500 mt-1">Precio para pago en Bs o transferencia</p>
                      </div>
                    </div>

                    <div>
                      <Label htmlFor="description">Descripción (Opcional)</Label>
                      <Textarea
                        id="description"
                        value={formData.description}
                        onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                        rows={2}
                        placeholder="Especificaciones técnicas, modelo, características..."
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
                        data-testid="save-hardware-button"
                        className="bg-brand-green-600 hover:bg-brand-green-700 text-white"
                      >
                        {editingHardware ? 'Actualizar' : 'Guardar'}
                      </Button>
                    </div>
                  </form>
                </DialogContent>
              </Dialog>}            </div>
          </div>

          {/* Filter Bar */}
          <div className="bg-white rounded-lg border border-slate-200 p-3 mb-4">
            <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-0.5" data-testid="filter-hw-category">
              <button onClick={() => setSelectedCategory('all')}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${selectedCategory === 'all' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                data-testid="filter-hw-all">Todas</button>
              {HARDWARE_TYPES.map(t => (
                <button key={t.id} onClick={() => setSelectedCategory(t.id)}
                  className={`px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors ${selectedCategory === t.id ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                  data-testid={`filter-hw-${t.id}`}>{t.name}</button>
              ))}
              {selectedCategory !== 'all' && (
                <button onClick={() => setSelectedCategory('all')}
                  className="ml-1 px-2 py-1.5 text-xs text-slate-400 hover:text-slate-600">Limpiar</button>
              )}
            </div>
          </div>

          {/* Tabla de Dispositivos - Estilo MediosPago */}
          <div className="flex justify-end mb-4">
            <MigrationButtons module="hardware" label="Bienes y Servicios" onImported={fetchHardware} />
          </div>
          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Dispositivo / Accesorio
                  </th>
                  <th className="px-3 py-3 text-center text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Categoría
                  </th>
                  <th className="px-3 py-3 text-center text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Clasificación
                  </th>
                  <th className="px-3 py-3 text-center text-sm font-medium text-emerald-600 uppercase tracking-wider">
                    Precio Efectivo
                  </th>
                  <th className="px-3 py-3 text-center text-sm font-medium text-brand-blue-600 uppercase tracking-wider">
                    Precio Bs/USD
                  </th>
                  <th className="px-3 py-3 text-center text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Acciones
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {hardwareList
                  .filter(h => selectedCategory === 'all' || h.type === selectedCategory)
                  .map((hardware) => (
                  <tr key={hardware.hardware_id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3">
                      <p className="font-medium text-slate-900">{hardware.name}</p>
                      {hardware.description && (
                        <p className="text-xs text-slate-500 mt-1 truncate max-w-xs">{hardware.description}</p>
                      )}
                    </td>
                    <td className="px-3 py-3 text-center">
                      {getTypeBadge(hardware.type)}
                    </td>
                    <td className="px-3 py-3 text-center">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                        hardware.asset_type === 'Servicio'
                          ? 'bg-purple-100 text-purple-700 border border-purple-200'
                          : 'bg-teal-100 text-teal-700 border border-teal-200'
                      }`}>{hardware.asset_type || 'Bien'}</span>
                    </td>
                    <td className="px-3 py-3 text-center">
                      <span className="font-mono text-emerald-600 font-semibold">
                        ${(hardware.price_usd || 0).toFixed(2)}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-center">
                      <span className="font-mono text-brand-blue-600 font-semibold">
                        ${(hardware.price_bs_usd || 0).toFixed(2)}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex items-center justify-center gap-1">
                        {canEdit && <Button
                          size="sm"
                          variant="outline"
                          data-testid={`edit-hardware-${hardware.hardware_id}`}
                          onClick={() => openEditDialog(hardware)}
                        >
                          <Pencil size={14} />
                        </Button>}
                        {canEdit && <Button
                          size="sm"
                          variant="outline"
                          data-testid={`delete-hardware-${hardware.hardware_id}`}
                          onClick={() => handleDelete(hardware.hardware_id)}
                          className="text-red-600 hover:text-red-700 hover:border-red-300"
                        >
                          <Trash2 size={14} />
                        </Button>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {hardwareList.length === 0 && (
              <div className="text-center py-12 text-slate-500">
                <Package size={48} className="mx-auto mb-4 text-slate-300" />
                <p>No hay dispositivos registrados</p>
                <p className="text-sm mt-1">Agregue su primer dispositivo usando el botón superior</p>
              </div>
            )}
          </div>

          {/* Resumen por tipo */}
          {hardwareList.length > 0 && (
            <div className="mt-6 grid grid-cols-2 md:grid-cols-5 gap-4">
              {HARDWARE_TYPES.map((type) => {
                const count = groupedByType[type.id]?.length || 0;
                const Icon = type.icon;
                return (
                  <div key={type.id} className={`p-4 rounded-lg border ${count > 0 ? 'border-slate-200 bg-white' : 'border-slate-100 bg-slate-50'}`}>
                    <div className="flex items-center gap-2 mb-2">
                      <div className={`p-1.5 rounded ${type.color}`}>
                        <Icon size={14} />
                      </div>
                      <span className="text-sm font-medium text-slate-700">{type.name}</span>
                    </div>
                    <p className="text-2xl font-bold text-slate-900">{count}</p>
                    <p className="text-xs text-slate-500">
                      {count === 1 ? 'dispositivo' : 'dispositivos'}
                    </p>
                  </div>
                );
              })}
            </div>
          )}
        </div>
        
        {/* Modal de confirmación para Eliminar */}
        <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>¿Eliminar Registro?</AlertDialogTitle>
              <AlertDialogDescription>
                ¿Está seguro de que desea eliminar <strong>"{deleteHardwareData.name}"</strong>?
                <br /><br />
                <span className="text-red-600 font-medium">Esta acción es irreversible y podría afectar datos vinculados (cotizaciones de equipos).</span>
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
        
        {/* Modal de Importación */}
        <Dialog open={importDialogOpen} onOpenChange={closeImportDialog}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Upload className="text-brand-blue-600" />
                Importar Bienes y Servicios
              </DialogTitle>
            </DialogHeader>
            
            <div className="space-y-4">
              {/* Instrucciones */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-sm text-blue-800 mb-2">
                  <strong>Instrucciones:</strong>
                </p>
                <ol className="text-sm text-blue-700 list-decimal list-inside space-y-1">
                  <li>Descargue la plantilla de ejemplo</li>
                  <li>Complete los datos en el archivo Excel/CSV</li>
                  <li>Cargue el archivo completado</li>
                </ol>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={downloadTemplate}
                  className="mt-3 text-blue-700 border-blue-300 hover:bg-blue-100"
                  data-testid="download-template-btn"
                >
                  <FileDown size={16} className="mr-2" />
                  Descargar Plantilla
                </Button>
              </div>
              
              {/* Selector de archivo */}
              <div>
                <Label>Archivo a importar (Excel o CSV)</Label>
                <div className="mt-2 flex items-center gap-3">
                  <Input
                    type="file"
                    accept=".xlsx,.xls,.csv"
                    onChange={handleImportFileChange}
                    className="flex-1"
                    data-testid="import-file-input"
                  />
                </div>
                {importFile && (
                  <p className="text-sm text-slate-600 mt-2">
                    Archivo seleccionado: <strong>{importFile.name}</strong>
                  </p>
                )}
              </div>
              
              {/* Resultado de importación */}
              {importResult && (
                <div className={`rounded-lg p-4 ${
                  importResult.status === 'success' ? 'bg-green-50 border border-green-200' :
                  importResult.status === 'partial' ? 'bg-amber-50 border border-amber-200' :
                  'bg-red-50 border border-red-200'
                }`}>
                  <div className="flex items-center gap-2 mb-2">
                    {importResult.status === 'success' ? (
                      <CheckCircle2 className="text-green-600" size={20} />
                    ) : importResult.status === 'partial' ? (
                      <AlertCircle className="text-amber-600" size={20} />
                    ) : (
                      <X className="text-red-600" size={20} />
                    )}
                    <span className={`font-medium ${
                      importResult.status === 'success' ? 'text-green-800' :
                      importResult.status === 'partial' ? 'text-amber-800' :
                      'text-red-800'
                    }`}>
                      {importResult.message}
                    </span>
                  </div>
                  
                  {importResult.errors && importResult.errors.length > 0 && (
                    <div className="mt-3 max-h-40 overflow-y-auto">
                      <p className="text-sm font-medium text-slate-700 mb-2">Errores encontrados:</p>
                      <ul className="text-sm space-y-1">
                        {importResult.errors.slice(0, 10).map((err, idx) => (
                          <li key={idx} className="text-red-700">
                            Fila {err.row}: {err.message} ({err.column})
                          </li>
                        ))}
                        {importResult.errors.length > 10 && (
                          <li className="text-slate-500 italic">
                            ... y {importResult.errors.length - 10} errores más
                          </li>
                        )}
                      </ul>
                    </div>
                  )}
                </div>
              )}
              
              {/* Botones */}
              <div className="flex justify-end gap-3 pt-2 border-t">
                <Button variant="outline" onClick={closeImportDialog}>
                  Cerrar
                </Button>
                <Button
                  onClick={executeImport}
                  disabled={!importFile || importLoading}
                  className="bg-brand-blue-600 hover:bg-brand-blue-700 text-white"
                  data-testid="execute-import-btn"
                >
                  {importLoading ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      Importando...
                    </>
                  ) : (
                    <>
                      <Upload size={16} className="mr-2" />
                      Importar
                    </>
                  )}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
};

export default Hardware;
