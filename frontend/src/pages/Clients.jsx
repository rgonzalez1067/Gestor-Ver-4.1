import { useState, useEffect, useRef } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { ImportResultPanel } from '../components/ImportResultPanel';
import { Plus, Pencil, Trash2, Upload, FileSpreadsheet, FileText } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const SEGMENT_OPTIONS = ['Pymes', 'Corporativo', 'Mixto'];

export const Clients = () => {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingClient, setEditingClient] = useState(null);
  const [formData, setFormData] = useState({
    rif: '',
    legal_name: '',
    fantasy_name: '',
    segment: 'Pymes',
    contact1: { name: '', phone: '', email: '' },
    contact2: { name: '', phone: '', email: '' }
  });
  const fileInputRef = useRef(null);

  useEffect(() => {
    fetchClients();
  }, []);

  const fetchClients = async () => {
    try {
      const response = await api.get('/clients');
      setClients(response.data);
    } catch (error) {
      console.error('Error fetching clients:', error);
      toast.error('Error al cargar clientes');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editingClient) {
        await api.put(`/clients/${editingClient.client_id}`, formData);
        toast.success('Cliente actualizado exitosamente');
      } else {
        await api.post('/clients', formData);
        toast.success('Cliente creado exitosamente');
      }
      setDialogOpen(false);
      resetForm();
      fetchClients();
    } catch (error) {
      console.error('Error saving client:', error);
      toast.error('Error al guardar cliente');
    }
  };

  const handleDelete = async (clientId) => {
    if (!window.confirm('¿Está seguro de eliminar este cliente?')) return;
    
    try {
      await api.delete(`/clients/${clientId}`);
      toast.success('Cliente eliminado exitosamente');
      fetchClients();
    } catch (error) {
      console.error('Error deleting client:', error);
      toast.error('Error al eliminar cliente');
    }
  };

  const openEditDialog = (client) => {
    setEditingClient(client);
    setFormData({
      rif: client.rif,
      legal_name: client.legal_name,
      fantasy_name: client.fantasy_name,
      segment: client.segment || 'Pymes',
      contact1: client.contact1,
      contact2: client.contact2
    });
    setDialogOpen(true);
  };

  const resetForm = () => {
    setFormData({
      rif: '',
      legal_name: '',
      fantasy_name: '',
      segment: 'Pymes',
      contact1: { name: '', phone: '', email: '' },
      contact2: { name: '', phone: '', email: '' }
    });
    setEditingClient(null);
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
      await api.post('/clients/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      toast.success('Clientes importados exitosamente');
      fetchClients();
    } catch (error) {
      console.error('Error importing clients:', error);
      toast.error('Error al importar. Verifique el formato del archivo.');
    }
    
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const exportToCSV = () => {
    const headers = ['RIF', 'Nombre Jurídico', 'Nombre Fantasía', 'Segmento', 'Contacto1 Nombre', 'Contacto1 Teléfono', 'Contacto1 Email'];
    const csvContent = [
      headers.join(','),
      ...clients.map(c => [
        `"${c.rif}"`,
        `"${c.legal_name}"`,
        `"${c.fantasy_name}"`,
        `"${c.segment || ''}"`,
        `"${c.contact1?.name || ''}"`,
        `"${c.contact1?.phone || ''}"`,
        `"${c.contact1?.email || ''}"`
      ].join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'clientes.csv';
    link.click();
    toast.success('Archivo CSV descargado');
  };

  const exportToPDF = async () => {
    try {
      const response = await api.get('/clients/export/pdf', { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.download = 'clientes.pdf';
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
            <p className="mt-4 text-slate-900">Cargando clientes...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-white">
      <Sidebar />
      
      <main className="flex-1 p-8" data-testid="clients-page">
        <div className="max-w-7xl mx-auto">
          <div className="flex justify-between items-center mb-8">
            <div>
              <h1 className="text-4xl font-bold text-slate-900 font-manrope mb-2">
                Clientes
              </h1>
              <p className="text-slate-600">Gestione la información de sus clientes</p>
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
                className="border-brand-blue-600 text-brand-blue-600 hover:bg-brand-blue-50"
              >
                <Upload size={18} className="mr-2" />
                Importar
              </Button>
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
            <Dialog open={dialogOpen} onOpenChange={handleDialogClose}>
              <DialogTrigger asChild>
                <Button
                  data-testid="add-client-button"
                  className="bg-brand-green-600 hover:bg-brand-green-700 text-white"
                >
                  <Plus size={20} className="mr-2" />
                  Nuevo Cliente
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle className="font-manrope text-2xl">
                    {editingClient ? 'Editar Cliente' : 'Nuevo Cliente'}
                  </DialogTitle>
                </DialogHeader>
                <form onSubmit={handleSubmit} className="space-y-6">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="rif">RIF</Label>
                      <Input
                        id="rif"
                        data-testid="client-rif-input"
                        value={formData.rif}
                        onChange={(e) => setFormData({ ...formData, rif: e.target.value })}
                        required
                      />
                    </div>
                    <div>
                      <Label htmlFor="segment">Segmento</Label>
                      <Select
                        value={formData.segment}
                        onValueChange={(value) => setFormData({ ...formData, segment: value })}
                      >
                        <SelectTrigger data-testid="client-segment-select">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {SEGMENT_OPTIONS.map((seg) => (
                            <SelectItem key={seg} value={seg}>{seg}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label htmlFor="legal_name">Nombre Jurídico</Label>
                      <Input
                        id="legal_name"
                        data-testid="client-legal-name-input"
                        value={formData.legal_name}
                        onChange={(e) => setFormData({ ...formData, legal_name: e.target.value })}
                        required
                      />
                    </div>
                    <div>
                      <Label htmlFor="fantasy_name">Nombre de Fantasía</Label>
                      <Input
                        id="fantasy_name"
                        data-testid="client-fantasy-name-input"
                        value={formData.fantasy_name}
                        onChange={(e) => setFormData({ ...formData, fantasy_name: e.target.value })}
                        required
                      />
                    </div>
                  </div>

                  <div className="border-t pt-4">
                    <h3 className="font-semibold text-lg mb-3">Contacto 1</h3>
                    <div className="grid grid-cols-3 gap-4">
                      <div>
                        <Label htmlFor="contact1_name">Nombre</Label>
                        <Input
                          id="contact1_name"
                          value={formData.contact1.name}
                          onChange={(e) => setFormData({
                            ...formData,
                            contact1: { ...formData.contact1, name: e.target.value }
                          })}
                          required
                        />
                      </div>
                      <div>
                        <Label htmlFor="contact1_phone">Teléfono</Label>
                        <Input
                          id="contact1_phone"
                          value={formData.contact1.phone}
                          onChange={(e) => setFormData({
                            ...formData,
                            contact1: { ...formData.contact1, phone: e.target.value }
                          })}
                          required
                        />
                      </div>
                      <div>
                        <Label htmlFor="contact1_email">Email</Label>
                        <Input
                          id="contact1_email"
                          type="email"
                          value={formData.contact1.email}
                          onChange={(e) => setFormData({
                            ...formData,
                            contact1: { ...formData.contact1, email: e.target.value }
                          })}
                          required
                        />
                      </div>
                    </div>
                  </div>

                  <div className="border-t pt-4">
                    <h3 className="font-semibold text-lg mb-3">Contacto 2</h3>
                    <div className="grid grid-cols-3 gap-4">
                      <div>
                        <Label htmlFor="contact2_name">Nombre</Label>
                        <Input
                          id="contact2_name"
                          value={formData.contact2.name}
                          onChange={(e) => setFormData({
                            ...formData,
                            contact2: { ...formData.contact2, name: e.target.value }
                          })}
                          required
                        />
                      </div>
                      <div>
                        <Label htmlFor="contact2_phone">Teléfono</Label>
                        <Input
                          id="contact2_phone"
                          value={formData.contact2.phone}
                          onChange={(e) => setFormData({
                            ...formData,
                            contact2: { ...formData.contact2, phone: e.target.value }
                          })}
                          required
                        />
                      </div>
                      <div>
                        <Label htmlFor="contact2_email">Email</Label>
                        <Input
                          id="contact2_email"
                          type="email"
                          value={formData.contact2.email}
                          onChange={(e) => setFormData({
                            ...formData,
                            contact2: { ...formData.contact2, email: e.target.value }
                          })}
                          required
                        />
                      </div>
                    </div>
                  </div>

                  <div className="flex justify-end gap-3">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => handleDialogClose(false)}
                    >
                      Cancelar
                    </Button>
                    <Button
                      type="submit"
                      data-testid="save-client-button"
                      className="bg-brand-green-600 hover:bg-brand-green-700 text-white"
                    >
                      {editingClient ? 'Actualizar' : 'Guardar'}
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
                  <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase tracking-wider">
                    RIF
                  </th>
                  <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Nombre Jurídico
                  </th>
                  <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Nombre de Fantasía
                  </th>
                  <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Segmento
                  </th>
                  <th className="px-6 py-4 text-left text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Contacto Principal
                  </th>
                  <th className="px-6 py-4 text-center text-sm font-medium text-slate-700 uppercase tracking-wider">
                    Acciones
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {clients.map((client) => (
                  <tr key={client.client_id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-6 py-4 text-sm font-mono text-slate-700">
                      {client.rif}
                    </td>
                    <td className="px-6 py-4 text-sm font-medium text-slate-900">
                      {client.legal_name}
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-600">
                      {client.fantasy_name}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-block px-2 py-1 text-xs font-medium rounded ${
                        client.segment === 'Corporativo' ? 'bg-purple-100 text-purple-700' :
                        client.segment === 'Pymes' ? 'bg-emerald-100 text-emerald-700' :
                        'bg-amber-100 text-amber-700'
                      }`}>
                        {client.segment || 'N/A'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-600">
                      <div>
                        <p className="font-medium">{client.contact1.name}</p>
                        <p className="text-slate-500">{client.contact1.email}</p>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-center gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          data-testid={`edit-client-${client.client_id}`}
                          onClick={() => openEditDialog(client)}
                        >
                          <Pencil size={16} />
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          data-testid={`delete-client-${client.client_id}`}
                          onClick={() => handleDelete(client.client_id)}
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
            {clients.length === 0 && (
              <div className="text-center py-12 text-slate-500">
                <p>No hay clientes registrados</p>
                <p className="text-sm mt-1">Cree su primer cliente usando el botón superior</p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
};

export default Clients;