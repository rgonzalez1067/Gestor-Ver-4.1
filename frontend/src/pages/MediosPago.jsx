import { useState, useEffect, useRef } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Plus, Pencil, Trash2, Upload, FileSpreadsheet, FileText, Settings2, RefreshCw, Layers } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const APPLICATION_TYPES = [
  { id: 'setup', name: 'Solo Setup', icon: Settings2, description: 'Solo gastos de implementación inicial' },
  { id: 'recurring', name: 'Solo Costos Recurrentes', icon: RefreshCw, description: 'Solo cargos mensuales/periódicos' },
  { id: 'both', name: 'Ambos', icon: Layers, description: 'Aplica a Setup y Costos Recurrentes' }
];

export const MediosPago = () => {
  const [mediosPago, setMediosPago] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingMedioPago, setEditingMedioPago] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    application_type: '',
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
    
    if (!formData.application_type) {
      toast.error('Seleccione el tipo de aplicación');
      return;
    }
    
    try {
      const payload = {
        ...formData,
        category: 'General',
        setup_cost_conventional: formData.application_type !== 'recurring' ? (parseFloat(formData.setup_cost_conventional) || 0) : 0,
        monthly_cost_conventional: formData.application_type !== 'setup' ? (parseFloat(formData.monthly_cost_conventional) || 0) : 0,
        setup_cost_outsourcing: formData.application_type !== 'recurring' ? (parseFloat(formData.setup_cost_outsourcing) || 0) : 0,
        monthly_cost_outsourcing: formData.application_type !== 'setup' ? (parseFloat(formData.monthly_cost_outsourcing) || 0) : 0
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
      application_type: medioPago.application_type || 'both',
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
      application_type: '',
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
    const headers = ['Nombre', 'Tipo Aplicación', 'Setup Convencional', 'Mensual Convencional', 'Setup Outsourcing', 'Mensual Outsourcing', 'Descripción'];
    const csvContent = [
      headers.join(','),
      ...mediosPago.map(s => [
        `"${s.name}"`,
        `"${s.application_type || 'both'}"`,
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

  const getApplicationTypeBadge = (type) => {
    switch(type) {
      case 'setup':
        return <span className="px-2 py-1 text-xs font-medium bg-purple-100 text-purple-700 rounded">Solo Setup</span>;
      case 'recurring':
        return <span className="px-2 py-1 text-xs font-medium bg-amber-100 text-amber-700 rounded">Solo Recurrente</span>;
      default:
        return <span className="px-2 py-1 text-xs font-medium bg-brand-green-50 text-brand-green-600 rounded">Ambos</span>;
    }
  };

  const showSetupFields = formData.application_type === 'setup' || formData.application_type === 'both';
  const showRecurringFields = formData.application_type === 'recurring' || formData.application_type === 'both';

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
                data-testid="import-medios-pago-button"
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
                    data-testid="add-medio-pago-button"
                    className="bg-brand-green-600 hover:bg-brand-green-700 text-white"
                  >
                    <Plus size={20} className="mr-2" />
                    Nuevo Medio de Pago
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
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

                    <div className="border-t pt-4">
                      <Label className="text-base font-semibold text-slate-900 mb-3 block">
                        ¿A qué aplica este concepto? <span className="text-red-500">*</span>
                      </Label>
                      <p className="text-sm text-slate-500 mb-4">
                        Seleccione dónde debe aparecer este concepto en las cotizaciones
                      </p>
                      <div className="grid grid-cols-1 gap-3">
                        {APPLICATION_TYPES.map((type) => {
                          const Icon = type.icon;
                          const isSelected = formData.application_type === type.id;
                          return (
                            <div
                              key={type.id}
                              onClick={() => setFormData({ ...formData, application_type: type.id })}
                              className={`p-4 rounded-lg border-2 cursor-pointer transition-all flex items-center gap-4 ${
                                isSelected
                                  ? 'border-brand-green-600 bg-brand-green-50'
                                  : 'border-slate-200 hover:border-slate-300'
                              }`}
                              data-testid={`application-type-${type.id}`}
                            >
                              <div className={`p-2 rounded-lg ${isSelected ? 'bg-brand-green-600 text-white' : 'bg-slate-100 text-slate-500'}`}>
                                <Icon size={20} />
                              </div>
                              <div className="flex-1">
                                <p className="font-medium text-slate-900">{type.name}</p>
                                <p className="text-sm text-slate-500">{type.description}</p>
                              </div>
                              <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                                isSelected ? 'border-brand-green-600 bg-brand-green-600' : 'border-slate-300'
                              }`}>
                                {isSelected && <div className="w-2 h-2 rounded-full bg-white"></div>}
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
                      </>
                    )}

                    <div>
                      <Label htmlFor="description">Descripción (Opcional)</Label>
                      <Textarea
                        id="description"
                        value={formData.description}
                        onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                        rows={3}
                        placeholder="Información adicional sobre este medio de pago..."
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
                        data-testid="save-medio-pago-button"
                        className="bg-brand-green-600 hover:bg-brand-green-700 text-white"
                        disabled={!formData.application_type}
                      >
                        {editingMedioPago ? 'Actualizar' : 'Guardar'}
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
                    Medio de Pago / Servicio
                  </th>
                  <th className="px-4 py-3 text-center text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Aplica a
                  </th>
                  <th className="px-4 py-3 text-center text-sm font-medium text-brand-blue-600 uppercase tracking-wider" colSpan={2}>
                    Setup
                  </th>
                  <th className="px-4 py-3 text-center text-sm font-medium text-brand-green-600 uppercase tracking-wider" colSpan={2}>
                    Recurrente
                  </th>
                  <th className="px-4 py-3 text-center text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Acciones
                  </th>
                </tr>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th></th>
                  <th></th>
                  <th className="px-2 py-2 text-right text-xs font-medium text-slate-600">Conv.</th>
                  <th className="px-2 py-2 text-right text-xs font-medium text-slate-600">Outs.</th>
                  <th className="px-2 py-2 text-right text-xs font-medium text-slate-600">Conv.</th>
                  <th className="px-2 py-2 text-right text-xs font-medium text-slate-600">Outs.</th>
                  <th></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {mediosPago.map((medioPago) => (
                  <tr key={medioPago.service_id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-6 py-4">
                      <p className="font-medium text-slate-900">{medioPago.name}</p>
                      {medioPago.description && (
                        <p className="text-sm text-slate-500 mt-1">{medioPago.description}</p>
                      )}
                    </td>
                    <td className="px-4 py-4 text-center">
                      {getApplicationTypeBadge(medioPago.application_type)}
                    </td>
                    <td className="px-2 py-4 text-right font-mono text-brand-blue-600 text-sm">
                      {medioPago.application_type !== 'recurring' ? `$${(medioPago.setup_cost_conventional || 0).toFixed(2)}` : '-'}
                    </td>
                    <td className="px-2 py-4 text-right font-mono text-brand-blue-600 text-sm">
                      {medioPago.application_type !== 'recurring' ? `$${(medioPago.setup_cost_outsourcing || 0).toFixed(2)}` : '-'}
                    </td>
                    <td className="px-2 py-4 text-right font-mono text-brand-green-600 text-sm">
                      {medioPago.application_type !== 'setup' ? `$${(medioPago.monthly_cost_conventional || 0).toFixed(2)}` : '-'}
                    </td>
                    <td className="px-2 py-4 text-right font-mono text-brand-green-600 text-sm">
                      {medioPago.application_type !== 'setup' ? `$${(medioPago.monthly_cost_outsourcing || 0).toFixed(2)}` : '-'}
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center justify-center gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          data-testid={`edit-medio-pago-${medioPago.service_id}`}
                          onClick={() => openEditDialog(medioPago)}
                        >
                          <Pencil size={16} />
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          data-testid={`delete-medio-pago-${medioPago.service_id}`}
                          onClick={() => handleDelete(medioPago.service_id)}
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
            {mediosPago.length === 0 && (
              <div className="text-center py-12 text-slate-500">
                <p>No hay medios de pago registrados</p>
                <p className="text-sm mt-1">Agregue su primer medio de pago usando el botón superior</p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
};

export default MediosPago;
