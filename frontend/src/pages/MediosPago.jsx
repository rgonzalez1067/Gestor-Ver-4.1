import { useState, useEffect, useRef } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Plus, Pencil, Trash2, Upload, Download, FileSpreadsheet, FileText } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

export const MediosPago = () => {
  const [mediosPago, setMediosPago] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingMedioPago, setEditingMedioPago] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    setup_cost_conventional: '',
    monthly_cost_conventional: '',
    setup_cost_outsourcing: '',
    monthly_cost_outsourcing: '',
    description: ''
  });
  const fileInputRef = useRef(null);

  useEffect(() => {
    fetchMediosPago();
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

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        ...formData,
        category: 'General',
        setup_cost_conventional: parseFloat(formData.setup_cost_conventional) || 0,
        monthly_cost_conventional: parseFloat(formData.monthly_cost_conventional) || 0,
        setup_cost_outsourcing: parseFloat(formData.setup_cost_outsourcing) || 0,
        monthly_cost_outsourcing: parseFloat(formData.monthly_cost_outsourcing) || 0
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
    if (!window.confirm('¿Está seguro de eliminar este medio de pago?')) return;
    
    try {
      await api.delete(`/services/${serviceId}`);
      toast.success('Medio de pago eliminado exitosamente');
      fetchMediosPago();
    } catch (error) {
      console.error('Error deleting medio de pago:', error);
      toast.error('Error al eliminar medio de pago');
    }
  };

  const openEditDialog = (medioPago) => {
    setEditingMedioPago(medioPago);
    setFormData({
      name: medioPago.name,
      setup_cost_conventional: medioPago.setup_cost_conventional?.toString() || '0',
      monthly_cost_conventional: medioPago.monthly_cost_conventional?.toString() || '0',
      setup_cost_outsourcing: medioPago.setup_cost_outsourcing?.toString() || '0',
      monthly_cost_outsourcing: medioPago.monthly_cost_outsourcing?.toString() || '0',
      description: medioPago.description || ''
    });
    setDialogOpen(true);
  };

  const resetForm = () => {
    setFormData({
      name: '',
      setup_cost_conventional: '',
      monthly_cost_conventional: '',
      setup_cost_outsourcing: '',
      monthly_cost_outsourcing: '',
      description: ''
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
      await api.post('/services/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      toast.success('Medios de pago importados exitosamente');
      fetchMediosPago();
    } catch (error) {
      console.error('Error importing medios de pago:', error);
      toast.error('Error al importar. Verifique el formato del archivo.');
    }
    
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const exportToCSV = () => {
    const headers = ['Nombre', 'Setup Convencional', 'Mensual Convencional', 'Setup Outsourcing', 'Mensual Outsourcing', 'Descripción'];
    const csvContent = [
      headers.join(','),
      ...mediosPago.map(s => [
        `"${s.name}"`,
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
              <Button
                variant="outline"
                onClick={() => fileInputRef.current?.click()}
                data-testid="import-services-button"
                className="border-brand-blue-600 text-brand-blue-600 hover:bg-brand-blue-50"
              >
                <Upload size={18} className="mr-2" />
                Importar
              </Button>
              <Button
                variant="outline"
                onClick={exportToCSV}
                data-testid="export-csv-button"
                className="border-brand-green-600 text-brand-green-600 hover:bg-brand-green-50"
              >
                <FileSpreadsheet size={18} className="mr-2" />
                Excel/CSV
              </Button>
              <Button
                variant="outline"
                onClick={exportToPDF}
                data-testid="export-pdf-button"
                className="border-brand-blue-600 text-brand-blue-600 hover:bg-brand-blue-50"
              >
                <FileText size={18} className="mr-2" />
                PDF
              </Button>
              <Dialog open={dialogOpen} onOpenChange={handleDialogClose}>
                <DialogTrigger asChild>
                  <Button
                    data-testid="add-service-button"
                    className="bg-brand-green-600 hover:bg-brand-green-700 text-white"
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
                      <h3 className="font-semibold text-sm text-brand-blue-600 mb-3">Modelo Convencional</h3>
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
                      <h3 className="font-semibold text-sm text-brand-green-600 mb-3">Modelo Outsourcing</h3>
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
                        className="bg-brand-green-600 hover:bg-brand-green-700 text-white"
                      >
                        {editingService ? 'Actualizar' : 'Guardar'}
                      </Button>
                    </div>
                  </form>
                </DialogContent>
              </Dialog>
            </div>
          </div>

          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-6 py-3 text-left text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Servicio
                  </th>
                  <th className="px-6 py-3 text-center text-sm font-medium text-brand-blue-600 uppercase tracking-wider" colSpan={2}>
                    Convencional
                  </th>
                  <th className="px-6 py-3 text-center text-sm font-medium text-brand-green-600 uppercase tracking-wider" colSpan={2}>
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
                {services.map((service) => (
                  <tr key={service.service_id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-6 py-4">
                      <p className="font-medium text-slate-900">{service.name}</p>
                      {service.description && (
                        <p className="text-sm text-slate-500 mt-1">{service.description}</p>
                      )}
                    </td>
                    <td className="px-3 py-4 text-right font-mono text-brand-blue-600 text-sm">
                      ${(service.setup_cost_conventional || 0).toFixed(2)}
                    </td>
                    <td className="px-3 py-4 text-right font-mono text-brand-blue-600 text-sm">
                      ${(service.monthly_cost_conventional || 0).toFixed(2)}
                    </td>
                    <td className="px-3 py-4 text-right font-mono text-brand-green-600 text-sm">
                      ${(service.setup_cost_outsourcing || 0).toFixed(2)}
                    </td>
                    <td className="px-3 py-4 text-right font-mono text-brand-green-600 text-sm">
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
            {services.length === 0 && (
              <div className="text-center py-12 text-slate-500">
                <p>No hay servicios registrados</p>
                <p className="text-sm mt-1">Agregue su primer servicio usando el botón superior</p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
};

export default Services;
