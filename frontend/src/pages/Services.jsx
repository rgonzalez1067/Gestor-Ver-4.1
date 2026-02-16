import { useState, useEffect } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Textarea } from '../components/ui/textarea';
import { Plus, Pencil, Trash2 } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const SERVICE_CATEGORIES = [
  'Suscripciones y Configuración',
  'Tarjetas y Liquidación',
  'Pagos Inmediatos y Biometría',
  'Cripto y Alternativos',
  'Servicios Especializados'
];

export const Services = () => {
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingService, setEditingService] = useState(null);
  const [formData, setFormData] = useState({
    category: SERVICE_CATEGORIES[0],
    name: '',
    setup_cost_conventional: '',
    monthly_cost_conventional: '',
    setup_cost_outsourcing: '',
    monthly_cost_outsourcing: '',
    description: ''
  });

  useEffect(() => {
    fetchServices();
  }, []);

  const fetchServices = async () => {
    try {
      const response = await api.get('/services');
      setServices(response.data);
    } catch (error) {
      console.error('Error fetching services:', error);
      toast.error('Error al cargar servicios');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        ...formData,
        setup_cost_conventional: parseFloat(formData.setup_cost_conventional),
        monthly_cost_conventional: parseFloat(formData.monthly_cost_conventional),
        setup_cost_outsourcing: parseFloat(formData.setup_cost_outsourcing),
        monthly_cost_outsourcing: parseFloat(formData.monthly_cost_outsourcing)
      };

      if (editingService) {
        await api.put(`/services/${editingService.service_id}`, payload);
        toast.success('Servicio actualizado exitosamente');
      } else {
        await api.post('/services', payload);
        toast.success('Servicio creado exitosamente');
      }
      setDialogOpen(false);
      resetForm();
      fetchServices();
    } catch (error) {
      console.error('Error saving service:', error);
      toast.error('Error al guardar servicio');
    }
  };

  const handleDelete = async (serviceId) => {
    if (!window.confirm('¿Está seguro de eliminar este servicio?')) return;
    
    try {
      await api.delete(`/services/${serviceId}`);
      toast.success('Servicio eliminado exitosamente');
      fetchServices();
    } catch (error) {
      console.error('Error deleting service:', error);
      toast.error('Error al eliminar servicio');
    }
  };

  const openEditDialog = (service) => {
    setEditingService(service);
    setFormData({
      category: service.category,
      name: service.name,
      setup_cost_conventional: service.setup_cost_conventional?.toString() || '0',
      monthly_cost_conventional: service.monthly_cost_conventional?.toString() || '0',
      setup_cost_outsourcing: service.setup_cost_outsourcing?.toString() || '0',
      monthly_cost_outsourcing: service.monthly_cost_outsourcing?.toString() || '0',
      description: service.description || ''
    });
    setDialogOpen(true);
  };

  const resetForm = () => {
    setFormData({
      category: SERVICE_CATEGORIES[0],
      name: '',
      setup_cost_conventional: '',
      monthly_cost_conventional: '',
      setup_cost_outsourcing: '',
      monthly_cost_outsourcing: '',
      description: ''
    });
    setEditingService(null);
  };

  const handleDialogClose = (open) => {
    setDialogOpen(open);
    if (!open) resetForm();
  };

  const groupedServices = services.reduce((acc, service) => {
    if (!acc[service.category]) {
      acc[service.category] = [];
    }
    acc[service.category].push(service);
    return acc;
  }, {});

  if (loading) {
    return (
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center bg-white">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-slate-900 mx-auto"></div>
            <p className="mt-4 text-slate-900">Cargando servicios...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-white">
      <Sidebar />
      
      <main className="flex-1 p-8" data-testid="services-page">
        <div className="max-w-7xl mx-auto">
          <div className="flex justify-between items-center mb-8">
            <div>
              <h1 className="text-4xl font-bold text-slate-900 font-manrope mb-2">
                Servicios
              </h1>
              <p className="text-slate-600">Catálogo de servicios y conceptos facturables</p>
            </div>
            
            <Dialog open={dialogOpen} onOpenChange={handleDialogClose}>
              <DialogTrigger asChild>
                <Button
                  data-testid="add-service-button"
                  className="bg-sky-600 hover:bg-sky-700 text-white"
                >
                  <Plus size={20} className="mr-2" />
                  Nuevo Servicio
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-xl">
                <DialogHeader>
                  <DialogTitle className="font-manrope text-2xl">
                    {editingService ? 'Editar Servicio' : 'Nuevo Servicio'}
                  </DialogTitle>
                </DialogHeader>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <Label htmlFor="category">Categoría</Label>
                    <Select
                      value={formData.category}
                      onValueChange={(value) => setFormData({ ...formData, category: value })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {SERVICE_CATEGORIES.map((cat) => (
                          <SelectItem key={cat} value={cat}>{cat}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <Label htmlFor="name">Nombre del Servicio</Label>
                    <Input
                      id="name"
                      data-testid="service-name-input"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      required
                    />
                  </div>

                  <div className="border-t pt-4">
                    <h3 className="font-semibold text-sm text-slate-700 mb-3">Modelo Convencional</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label htmlFor="setup_cost_conventional">Costo Setup (USD)</Label>
                        <Input
                          id="setup_cost_conventional"
                          type="number"
                          step="0.01"
                          min="0"
                          value={formData.setup_cost_conventional}
                          onChange={(e) => setFormData({ ...formData, setup_cost_conventional: e.target.value })}
                          required
                        />
                      </div>
                      <div>
                        <Label htmlFor="monthly_cost_conventional">Costo Mensual (USD)</Label>
                        <Input
                          id="monthly_cost_conventional"
                          type="number"
                          step="0.01"
                          min="0"
                          value={formData.monthly_cost_conventional}
                          onChange={(e) => setFormData({ ...formData, monthly_cost_conventional: e.target.value })}
                          required
                        />
                      </div>
                    </div>
                  </div>

                  <div className="border-t pt-4">
                    <h3 className="font-semibold text-sm text-slate-700 mb-3">Modelo Outsourcing</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label htmlFor="setup_cost_outsourcing">Costo Setup (USD)</Label>
                        <Input
                          id="setup_cost_outsourcing"
                          type="number"
                          step="0.01"
                          min="0"
                          value={formData.setup_cost_outsourcing}
                          onChange={(e) => setFormData({ ...formData, setup_cost_outsourcing: e.target.value })}
                          required
                        />
                      </div>
                      <div>
                        <Label htmlFor="monthly_cost_outsourcing">Costo Mensual (USD)</Label>
                        <Input
                          id="monthly_cost_outsourcing"
                          type="number"
                          step="0.01"
                          min="0"
                          value={formData.monthly_cost_outsourcing}
                          onChange={(e) => setFormData({ ...formData, monthly_cost_outsourcing: e.target.value })}
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
                      data-testid="save-service-button"
                      className="bg-sky-600 hover:bg-sky-700 text-white"
                    >
                      {editingService ? 'Actualizar' : 'Guardar'}
                    </Button>
                  </div>
                </form>
              </DialogContent>
            </Dialog>
          </div>

          <div className="space-y-6">
            {SERVICE_CATEGORIES.map((category) => {
              const categoryServices = groupedServices[category] || [];
              if (categoryServices.length === 0) return null;

              return (
                <div key={category} className="bg-white rounded-lg border border-slate-200 overflow-hidden">
                  <div className="px-6 py-4 bg-slate-50 border-b border-slate-200">
                    <h2 className="text-lg font-semibold text-slate-900 font-manrope">
                      {category}
                    </h2>
                  </div>
                  <table className="w-full">
                    <thead className="bg-slate-50 border-b border-slate-200">
                      <tr>
                        <th className="px-6 py-3 text-left text-sm font-medium text-slate-700 uppercase tracking-wider">
                          Servicio
                        </th>
                        <th className="px-6 py-3 text-center text-sm font-medium text-slate-700 uppercase tracking-wider" colSpan={2}>
                          Convencional
                        </th>
                        <th className="px-6 py-3 text-center text-sm font-medium text-slate-700 uppercase tracking-wider" colSpan={2}>
                          Outsourcing
                        </th>
                        <th className="px-6 py-3 text-center text-sm font-medium text-slate-700 uppercase tracking-wider">
                          Acciones
                        </th>
                      </tr>
                      <tr className="bg-slate-50 border-b border-slate-200">
                        <th></th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-slate-600">Setup</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-slate-600">Mensual</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-slate-600">Setup</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-slate-600">Mensual</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {categoryServices.map((service) => (
                        <tr key={service.service_id} className="hover:bg-slate-50 transition-colors">
                          <td className="px-6 py-4">
                            <p className="font-medium text-slate-900">{service.name}</p>
                            {service.description && (
                              <p className="text-sm text-slate-500 mt-1">{service.description}</p>
                            )}
                          </td>
                          <td className="px-3 py-4 text-right font-mono text-slate-700 text-sm">
                            ${(service.setup_cost_conventional || 0).toFixed(2)}
                          </td>
                          <td className="px-3 py-4 text-right font-mono text-slate-700 text-sm">
                            ${(service.monthly_cost_conventional || 0).toFixed(2)}
                          </td>
                          <td className="px-3 py-4 text-right font-mono text-emerald-700 text-sm">
                            ${(service.setup_cost_outsourcing || 0).toFixed(2)}
                          </td>
                          <td className="px-3 py-4 text-right font-mono text-emerald-700 text-sm">
                            ${(service.monthly_cost_outsourcing || 0).toFixed(2)}
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex items-center justify-center gap-2">
                              <Button
                                size="sm"
                                variant="outline"
                                data-testid={`edit-service-${service.service_id}`}
                                onClick={() => openEditDialog(service)}
                              >
                                <Pencil size={16} />
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                data-testid={`delete-service-${service.service_id}`}
                                onClick={() => handleDelete(service.service_id)}
                                className="text-red-600 hover:text-red-700 hover:border-red-300"
                              >
                                <Trash2 size={16} />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              );
            })}
          </div>

          {services.length === 0 && (
            <div className="bg-white rounded-lg border border-slate-200 p-12 text-center text-slate-500">
              <p>No hay servicios registrados</p>
              <p className="text-sm mt-1">Agregue su primer servicio usando el botón superior</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default Services;
