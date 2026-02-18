import { useState, useEffect, useRef } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Plus, Pencil, Trash2, Upload, FileSpreadsheet, FileText, Download, Search, Filter, Users, CheckCircle, Clock, XCircle } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const INTEGRATOR_TYPES = ['Integrador', 'Comercio'];
const INTEGRATION_MODALITIES = ['Bridge PG', 'MPOS', 'PG Universal', 'PG No universal', 'REST', 'Stand Alone'];
const INTEGRATOR_STATUSES = ['Certificado', 'En proceso', 'Suspendido'];

export const Integrators = () => {
  const [integrators, setIntegrators] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingIntegrator, setEditingIntegrator] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterType, setFilterType] = useState('');
  const [formData, setFormData] = useState({
    name: '',
    integrator_type: '',
    app_name: '',
    integration_modality: '',
    status: 'En proceso'
  });
  const fileInputRef = useRef(null);

  useEffect(() => {
    fetchIntegrators();
  }, [filterStatus, filterType]);

  const fetchIntegrators = async () => {
    try {
      let url = '/integrators';
      const params = new URLSearchParams();
      if (filterStatus) params.append('status', filterStatus);
      if (filterType) params.append('integrator_type', filterType);
      if (params.toString()) url += `?${params.toString()}`;
      
      const response = await api.get(url);
      setIntegrators(response.data);
    } catch (error) {
      console.error('Error fetching integrators:', error);
      toast.error('Error al cargar integradores');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.name || !formData.integrator_type || !formData.app_name || !formData.integration_modality) {
      toast.error('Todos los campos son obligatorios');
      return;
    }

    try {
      if (editingIntegrator) {
        await api.put(`/integrators/${editingIntegrator.integrator_id}`, formData);
        toast.success('Integrador actualizado exitosamente');
      } else {
        await api.post('/integrators', formData);
        toast.success('Integrador creado exitosamente');
      }
      
      setDialogOpen(false);
      resetForm();
      fetchIntegrators();
    } catch (error) {
      console.error('Error saving integrator:', error);
      toast.error('Error al guardar integrador');
    }
  };

  const handleDelete = async (integratorId) => {
    if (!window.confirm('¿Está seguro de eliminar este integrador?')) return;

    try {
      await api.delete(`/integrators/${integratorId}`);
      toast.success('Integrador eliminado exitosamente');
      fetchIntegrators();
    } catch (error) {
      console.error('Error deleting integrator:', error);
      toast.error('Error al eliminar integrador');
    }
  };

  const openEditDialog = (integrator) => {
    setEditingIntegrator(integrator);
    setFormData({
      name: integrator.name,
      integrator_type: integrator.integrator_type,
      app_name: integrator.app_name,
      integration_modality: integrator.integration_modality,
      status: integrator.status
    });
    setDialogOpen(true);
  };

  const resetForm = () => {
    setFormData({
      name: '',
      integrator_type: '',
      app_name: '',
      integration_modality: '',
      status: 'En proceso'
    });
    setEditingIntegrator(null);
  };

  const handleExportExcel = async () => {
    try {
      const response = await api.get('/integrators/export/excel', { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'integradores.xlsx');
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      toast.success('Excel exportado exitosamente');
    } catch (error) {
      toast.error('Error al exportar Excel');
    }
  };

  const handleExportPDF = async () => {
    try {
      const response = await api.get('/integrators/export/pdf', { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'integradores.pdf');
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      toast.success('PDF exportado exitosamente');
    } catch (error) {
      toast.error('Error al exportar PDF');
    }
  };

  const handleImport = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await api.post('/integrators/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      toast.success(response.data.message);
      
      if (response.data.errors && response.data.errors.length > 0) {
        response.data.errors.forEach(err => toast.warning(err));
      }
      
      fetchIntegrators();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al importar archivo');
    } finally {
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'Certificado':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700">
            <CheckCircle size={12} />
            Certificado
          </span>
        );
      case 'En proceso':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-700">
            <Clock size={12} />
            En proceso
          </span>
        );
      case 'Suspendido':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">
            <XCircle size={12} />
            Suspendido
          </span>
        );
      default:
        return status;
    }
  };

  const getTypeBadge = (type) => {
    switch (type) {
      case 'Integrador':
        return <span className="px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700">Integrador</span>;
      case 'Comercio':
        return <span className="px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700">Comercio</span>;
      default:
        return type;
    }
  };

  const filteredIntegrators = integrators.filter(intg => {
    if (searchTerm) {
      const search = searchTerm.toLowerCase();
      return (
        intg.name?.toLowerCase().includes(search) ||
        intg.app_name?.toLowerCase().includes(search) ||
        intg.integration_modality?.toLowerCase().includes(search)
      );
    }
    return true;
  });

  if (loading) {
    return (
      <div className="flex min-h-screen bg-slate-50">
        <Sidebar />
        <main className="flex-1 p-8">
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-blue-600"></div>
            <p className="ml-4 text-slate-600">Cargando integradores...</p>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 p-8">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="flex justify-between items-center mb-6">
            <div>
              <h1 className="text-3xl font-bold text-slate-900 font-manrope flex items-center gap-3">
                <Users className="text-brand-blue-600" size={32} />
                Gestión de Integradores
              </h1>
              <p className="text-slate-500 mt-1">Administre los aliados técnicos y sus estados de certificación</p>
            </div>
            
            <div className="flex gap-2">
              {/* Import */}
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleImport}
                accept=".xlsx,.xls,.csv"
                className="hidden"
              />
              <Button
                variant="outline"
                onClick={() => fileInputRef.current?.click()}
                className="border-slate-300"
                data-testid="import-integrators-btn"
              >
                <Upload size={16} className="mr-2" />
                Importar
              </Button>
              
              {/* Export Dropdown */}
              <div className="flex gap-1">
                <Button
                  variant="outline"
                  onClick={handleExportExcel}
                  className="border-slate-300"
                  data-testid="export-excel-btn"
                >
                  <FileSpreadsheet size={16} className="mr-1" />
                  Excel
                </Button>
                <Button
                  variant="outline"
                  onClick={handleExportPDF}
                  className="border-slate-300"
                  data-testid="export-pdf-btn"
                >
                  <FileText size={16} className="mr-1" />
                  PDF
                </Button>
              </div>
              
              {/* Create Dialog */}
              <Dialog open={dialogOpen} onOpenChange={(open) => { setDialogOpen(open); if (!open) resetForm(); }}>
                <DialogTrigger asChild>
                  <Button className="bg-brand-green-600 hover:bg-brand-green-700" data-testid="create-integrator-btn">
                    <Plus size={16} className="mr-2" />
                    Nuevo Integrador
                  </Button>
                </DialogTrigger>
                <DialogContent className="sm:max-w-lg">
                  <DialogHeader>
                    <DialogTitle className="text-xl font-semibold">
                      {editingIntegrator ? 'Editar Integrador' : 'Nuevo Integrador'}
                    </DialogTitle>
                  </DialogHeader>
                  <form onSubmit={handleSubmit} className="space-y-4 mt-4">
                    <div>
                      <Label htmlFor="name">Nombre del Integrador *</Label>
                      <Input
                        id="name"
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        placeholder="Ej: TechPay Solutions"
                        required
                        data-testid="integrator-name-input"
                      />
                    </div>
                    
                    <div>
                      <Label htmlFor="integrator_type">Tipo de Integrador *</Label>
                      <Select 
                        value={formData.integrator_type} 
                        onValueChange={(value) => setFormData({ ...formData, integrator_type: value })}
                      >
                        <SelectTrigger data-testid="integrator-type-select">
                          <SelectValue placeholder="Seleccione un tipo" />
                        </SelectTrigger>
                        <SelectContent>
                          {INTEGRATOR_TYPES.map(type => (
                            <SelectItem key={type} value={type}>{type}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    
                    <div>
                      <Label htmlFor="app_name">Nombre del Aplicativo *</Label>
                      <Input
                        id="app_name"
                        value={formData.app_name}
                        onChange={(e) => setFormData({ ...formData, app_name: e.target.value })}
                        placeholder="Ej: PaymentHub"
                        required
                        data-testid="app-name-input"
                      />
                    </div>
                    
                    <div>
                      <Label htmlFor="integration_modality">Modalidad de Integración *</Label>
                      <Select 
                        value={formData.integration_modality} 
                        onValueChange={(value) => setFormData({ ...formData, integration_modality: value })}
                      >
                        <SelectTrigger data-testid="modality-select">
                          <SelectValue placeholder="Seleccione una modalidad" />
                        </SelectTrigger>
                        <SelectContent>
                          {INTEGRATION_MODALITIES.map(modality => (
                            <SelectItem key={modality} value={modality}>{modality}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    
                    <div>
                      <Label htmlFor="status">Estatus *</Label>
                      <Select 
                        value={formData.status} 
                        onValueChange={(value) => setFormData({ ...formData, status: value })}
                      >
                        <SelectTrigger data-testid="status-select">
                          <SelectValue placeholder="Seleccione un estatus" />
                        </SelectTrigger>
                        <SelectContent>
                          {INTEGRATOR_STATUSES.map(status => (
                            <SelectItem key={status} value={status}>{status}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    
                    <div className="flex justify-end gap-3 pt-4">
                      <Button type="button" variant="outline" onClick={() => { setDialogOpen(false); resetForm(); }}>
                        Cancelar
                      </Button>
                      <Button type="submit" className="bg-brand-green-600 hover:bg-brand-green-700" data-testid="submit-integrator-btn">
                        {editingIntegrator ? 'Actualizar' : 'Crear'}
                      </Button>
                    </div>
                  </form>
                </DialogContent>
              </Dialog>
            </div>
          </div>

          {/* Filters */}
          <div className="bg-white rounded-lg border border-slate-200 p-4 mb-6">
            <div className="flex flex-wrap gap-4 items-center">
              <div className="flex-1 min-w-[200px]">
                <div className="relative">
                  <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <Input
                    placeholder="Buscar por nombre, aplicativo o modalidad..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="pl-10"
                    data-testid="search-input"
                  />
                </div>
              </div>
              
              <div className="flex items-center gap-2">
                <Filter size={16} className="text-slate-400" />
                <Select value={filterStatus} onValueChange={setFilterStatus}>
                  <SelectTrigger className="w-[150px]" data-testid="filter-status">
                    <SelectValue placeholder="Estatus" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todos</SelectItem>
                    {INTEGRATOR_STATUSES.map(status => (
                      <SelectItem key={status} value={status}>{status}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                
                <Select value={filterType} onValueChange={setFilterType}>
                  <SelectTrigger className="w-[150px]" data-testid="filter-type">
                    <SelectValue placeholder="Tipo" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todos</SelectItem>
                    {INTEGRATOR_TYPES.map(type => (
                      <SelectItem key={type} value={type}>{type}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                
                {(filterStatus || filterType || searchTerm) && (
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={() => { setFilterStatus(''); setFilterType(''); setSearchTerm(''); }}
                    className="text-slate-500"
                  >
                    Limpiar
                  </Button>
                )}
              </div>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            <div className="bg-white rounded-lg border border-slate-200 p-4">
              <div className="text-sm text-slate-500">Total</div>
              <div className="text-2xl font-bold text-slate-900">{integrators.length}</div>
            </div>
            <div className="bg-white rounded-lg border border-green-200 p-4">
              <div className="text-sm text-green-600">Certificados</div>
              <div className="text-2xl font-bold text-green-700">
                {integrators.filter(i => i.status === 'Certificado').length}
              </div>
            </div>
            <div className="bg-white rounded-lg border border-amber-200 p-4">
              <div className="text-sm text-amber-600">En proceso</div>
              <div className="text-2xl font-bold text-amber-700">
                {integrators.filter(i => i.status === 'En proceso').length}
              </div>
            </div>
            <div className="bg-white rounded-lg border border-red-200 p-4">
              <div className="text-sm text-red-600">Suspendidos</div>
              <div className="text-2xl font-bold text-red-700">
                {integrators.filter(i => i.status === 'Suspendido').length}
              </div>
            </div>
          </div>

          {/* Table */}
          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="px-4 py-3 text-left text-sm font-semibold text-slate-700">Nombre</th>
                    <th className="px-4 py-3 text-center text-sm font-semibold text-slate-700">Tipo</th>
                    <th className="px-4 py-3 text-left text-sm font-semibold text-slate-700">Aplicativo</th>
                    <th className="px-4 py-3 text-center text-sm font-semibold text-slate-700">Modalidad</th>
                    <th className="px-4 py-3 text-center text-sm font-semibold text-slate-700">Estatus</th>
                    <th className="px-4 py-3 text-center text-sm font-semibold text-slate-700">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredIntegrators.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                        No se encontraron integradores
                      </td>
                    </tr>
                  ) : (
                    filteredIntegrators.map((integrator) => (
                      <tr key={integrator.integrator_id} className="hover:bg-slate-50 transition-colors" data-testid={`integrator-row-${integrator.integrator_id}`}>
                        <td className="px-4 py-3">
                          <p className="font-medium text-slate-900">{integrator.name}</p>
                        </td>
                        <td className="px-4 py-3 text-center">
                          {getTypeBadge(integrator.integrator_type)}
                        </td>
                        <td className="px-4 py-3">
                          <p className="text-slate-700">{integrator.app_name}</p>
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-sm">
                            {integrator.integration_modality}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-center">
                          {getStatusBadge(integrator.status)}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-center gap-1">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => openEditDialog(integrator)}
                              className="text-brand-blue-600 hover:text-brand-blue-700 hover:bg-blue-50"
                              data-testid={`edit-${integrator.integrator_id}`}
                            >
                              <Pencil size={16} />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleDelete(integrator.integrator_id)}
                              className="text-red-500 hover:text-red-700 hover:bg-red-50"
                              data-testid={`delete-${integrator.integrator_id}`}
                            >
                              <Trash2 size={16} />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Integrators;
