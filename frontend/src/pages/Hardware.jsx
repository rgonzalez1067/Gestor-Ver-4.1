import { useState, useEffect } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Textarea } from '../components/ui/textarea';
import { Plus, Pencil, Trash2, DollarSign } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

export const Hardware = () => {
  const [hardwareList, setHardwareList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingHardware, setEditingHardware] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    type: 'Pinpad',
    price_usd: '',
    price_bs_usd: '',
    description: ''
  });

  useEffect(() => {
    fetchHardware();
  }, []);

  const fetchHardware = async () => {
    try {
      const response = await api.get('/hardware');
      setHardwareList(response.data);
    } catch (error) {
      console.error('Error fetching hardware:', error);
      toast.error('Error al cargar hardware');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        ...formData,
        price_usd: parseFloat(formData.price_usd),
        price_bs_usd: parseFloat(formData.price_bs_usd)
      };

      if (editingHardware) {
        await api.put(`/hardware/${editingHardware.hardware_id}`, payload);
        toast.success('Dispositivo actualizado exitosamente');
      } else {
        await api.post('/hardware', payload);
        toast.success('Dispositivo creado exitosamente');
      }
      setDialogOpen(false);
      resetForm();
      fetchHardware();
    } catch (error) {
      console.error('Error saving hardware:', error);
      toast.error('Error al guardar hardware');
    }
  };

  const handleDelete = async (hardwareId) => {
    if (!window.confirm('¿Está seguro de eliminar este hardware?')) return;
    
    try {
      await api.delete(`/hardware/${hardwareId}`);
      toast.success('Hardware eliminado exitosamente');
      fetchHardware();
    } catch (error) {
      console.error('Error deleting hardware:', error);
      toast.error('Error al eliminar hardware');
    }
  };

  const openEditDialog = (hardware) => {
    setEditingHardware(hardware);
    setFormData({
      name: hardware.name,
      type: hardware.type,
      price_usd: hardware.price_usd.toString(),
      price_bs_usd: hardware.price_bs_usd.toString(),
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
              <p className="text-slate-600">Catálogo de dispositivos y accesorios</p>
            </div>
            
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
                      required
                    />
                  </div>

                  <div>
                    <Label htmlFor="type">Tipo</Label>
                    <Select
                      value={formData.type}
                      onValueChange={(value) => setFormData({ ...formData, type: value })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Pinpad">Pinpad</SelectItem>
                        <SelectItem value="POS">Punto de Venta (POS)</SelectItem>
                        <SelectItem value="Cable">Cable</SelectItem>
                        <SelectItem value="Base">Base</SelectItem>
                        <SelectItem value="Accesorio">Accesorio</SelectItem>
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
                          required
                        />
                      </div>
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
                          required
                        />
                      </div>
                    </div>
                  </div>

                  <div>
                    <Label htmlFor="description">Descripción (Opcional)</Label>
                    <Textarea
                      id="description"
                      value={formData.description}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      rows={3}
                    />
                  </div>

                  <div className="flex justify-end gap-3 pt-2">
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

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {hardwareList.map((hardware) => (
              <div
                key={hardware.hardware_id}
                className="bg-white rounded-lg border border-slate-200 p-6 card-hover"
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <h3 className="text-xl font-semibold text-slate-900 font-manrope mb-1">
                      {hardware.name}
                    </h3>
                    <span className="inline-block px-2 py-1 text-xs font-medium bg-slate-100 text-slate-700 rounded">
                      {hardware.type}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      data-testid={`edit-hardware-${hardware.hardware_id}`}
                      onClick={() => openEditDialog(hardware)}
                    >
                      <Pencil size={16} />
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      data-testid={`delete-hardware-${hardware.hardware_id}`}
                      onClick={() => handleDelete(hardware.hardware_id)}
                      className="text-red-600 hover:text-red-700 hover:border-red-300"
                    >
                      <Trash2 size={16} />
                    </Button>
                  </div>
                </div>

                {hardware.description && (
                  <p className="text-sm text-slate-600 mb-4">
                    {hardware.description}
                  </p>
                )}

                <div className="border-t pt-4 space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-slate-600">Efectivo $:</span>
                    <span className="text-lg font-semibold text-emerald-600">
                      ${hardware.price_usd.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-slate-600">Bs/USD:</span>
                    <span className="text-lg font-semibold text-brand-blue-600">
                      ${hardware.price_bs_usd.toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {hardwareList.length === 0 && (
            <div className="bg-white rounded-lg border border-slate-200 p-12 text-center text-slate-500">
              <p>No hay hardware registrado</p>
              <p className="text-sm mt-1">Agregue su primer dispositivo usando el botón superior</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default Hardware;
