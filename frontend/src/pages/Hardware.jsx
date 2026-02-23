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

// Categorías principales
const CATEGORIES = [
  { id: 'dispositivos', name: 'Dispositivos', description: 'Hardware y equipos' },
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
    price_usd: '',
    price_bs_usd: '',
    description: ''
  });
  const fileInputRef = useRef(null);

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
      price_usd: '',
      price_bs_usd: '',
      description: ''
    });
    setEditingHardware(null);
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
                Dispositivos y Accesorios
              </h1>
              <p className="text-slate-600">Catálogo de dispositivos de pago y accesorios</p>
            </div>
            
            <div className="flex gap-3">
              <Dialog open={dialogOpen} onOpenChange={handleDialogClose}>
                <DialogTrigger asChild>
                  <Button
                    data-testid="add-hardware-button"
                    className="bg-brand-green-600 hover:bg-brand-green-700 text-white"
                  >
                    <Plus size={20} className="mr-2" />
                    Nuevo Dispositivo
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-xl">
                  <DialogHeader>
                    <DialogTitle className="font-manrope text-2xl">
                      {editingHardware ? 'Editar Dispositivo' : 'Nuevo Dispositivo'}
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
              </Dialog>
            </div>
          </div>

          {/* Tabla de Dispositivos - Estilo MediosPago */}
          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Dispositivo / Accesorio
                  </th>
                  <th className="px-3 py-3 text-center text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Tipo
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
                {hardwareList.map((hardware) => (
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
                        <Button
                          size="sm"
                          variant="outline"
                          data-testid={`edit-hardware-${hardware.hardware_id}`}
                          onClick={() => openEditDialog(hardware)}
                        >
                          <Pencil size={14} />
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          data-testid={`delete-hardware-${hardware.hardware_id}`}
                          onClick={() => handleDelete(hardware.hardware_id)}
                          className="text-red-600 hover:text-red-700 hover:border-red-300"
                        >
                          <Trash2 size={14} />
                        </Button>
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
              <AlertDialogTitle>¿Eliminar Dispositivo?</AlertDialogTitle>
              <AlertDialogDescription>
                ¿Está seguro de que desea eliminar el dispositivo <strong>"{deleteHardwareData.name}"</strong>?
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
      </main>
    </div>
  );
};

export default Hardware;
