import { useState, useEffect, useRef } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Plus, Pencil, Trash2, Package, Upload, FileSpreadsheet, FileText, Monitor, Globe, Smartphone, Link } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const COMPONENT_TYPES = [
  { id: 'vpos_available', name: 'VPOS', icon: Monitor, description: 'Cajas Registradoras' },
  { id: 'gateway_available', name: 'Payment Gateway', icon: Globe, description: 'Ecommerce' },
  { id: 'mpos_available', name: 'MPOS', icon: Smartphone, description: 'Tablet/Android' },
  { id: 'link_available', name: 'Link de Pago', icon: Link, description: 'Links de cobro' }
];

export const Banks = () => {
  const [banks, setBanks] = useState([]);
  const [mediosPago, setMediosPago] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingBank, setEditingBank] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    type: 'Banco',
    country: 'Venezuela',
    products: []
  });
  const [newProduct, setNewProduct] = useState({ 
    product_name: '', 
    description: '',
    service_id: '',
    vpos_available: false,
    gateway_available: false,
    mpos_available: false,
    link_available: false
  });
  const fileInputRef = useRef(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [banksRes, mediosPagoRes] = await Promise.all([
        api.get('/banks'),
        api.get('/services')
      ]);
      setBanks(banksRes.data);
      setMediosPago(mediosPagoRes.data);
    } catch (error) {
      console.error('Error fetching data:', error);
      toast.error('Error al cargar datos');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editingBank) {
        await api.put(`/banks/${editingBank.bank_id}`, formData);
        toast.success('Banco actualizado exitosamente');
      } else {
        await api.post('/banks', formData);
        toast.success('Banco creado exitosamente');
      }
      setDialogOpen(false);
      resetForm();
      fetchData();
    } catch (error) {
      console.error('Error saving bank:', error);
      toast.error('Error al guardar banco');
    }
  };

  const handleDelete = async (bankId) => {
    if (!window.confirm('¿Está seguro de eliminar este banco?')) return;
    
    try {
      await api.delete(`/banks/${bankId}`);
      toast.success('Banco eliminado exitosamente');
      fetchData();
    } catch (error) {
      console.error('Error deleting bank:', error);
      toast.error('Error al eliminar banco');
    }
  };

  const handleMedioPagoSelect = (serviceId) => {
    const selectedMedio = mediosPago.find(m => m.service_id === serviceId);
    if (selectedMedio) {
      setNewProduct({
        ...newProduct,
        service_id: serviceId,
        product_name: selectedMedio.name,
        description: selectedMedio.description || '',
        vpos_available: selectedMedio.vpos_enabled !== false,
        gateway_available: selectedMedio.gateway_enabled !== false,
        mpos_available: selectedMedio.mpos_enabled !== false,
        link_available: selectedMedio.link_enabled !== false
      });
    }
  };

  const addProduct = () => {
    if (!newProduct.product_name) {
      toast.error('Seleccione un medio de pago');
      return;
    }
    setFormData({
      ...formData,
      products: [...formData.products, { ...newProduct }]
    });
    setNewProduct({ 
      product_name: '', 
      description: '',
      service_id: '',
      vpos_available: false,
      gateway_available: false,
      mpos_available: false,
      link_available: false
    });
  };

  const removeProduct = (index) => {
    setFormData({
      ...formData,
      products: formData.products.filter((_, i) => i !== index)
    });
  };

  const openEditDialog = (bank) => {
    setEditingBank(bank);
    setFormData({
      name: bank.name,
      type: bank.type,
      country: bank.country,
      products: bank.products || []
    });
    setDialogOpen(true);
  };

  const resetForm = () => {
    setFormData({
      name: '',
      type: 'Banco',
      country: 'Venezuela',
      products: []
    });
    setNewProduct({ 
      product_name: '', 
      description: '',
      service_id: '',
      vpos_available: false,
      gateway_available: false,
      mpos_available: false,
      link_available: false
    });
    setEditingBank(null);
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
      await api.post('/banks/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      toast.success('Bancos importados exitosamente');
      fetchBanks();
    } catch (error) {
      console.error('Error importing banks:', error);
      toast.error('Error al importar bancos. Verifique el formato del archivo.');
    }
    
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const exportToCSV = () => {
    const headers = ['Nombre', 'Tipo', 'País', 'Productos'];
    const csvContent = [
      headers.join(','),
      ...banks.map(b => [
        `"${b.name}"`,
        `"${b.type}"`,
        `"${b.country}"`,
        `"${(b.products || []).map(p => p.product_name).join('; ')}"`
      ].join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'bancos.csv';
    link.click();
    toast.success('Archivo CSV descargado');
  };

  const exportToPDF = async () => {
    try {
      const response = await api.get('/banks/export/pdf', { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.download = 'bancos.pdf';
      link.click();
      toast.success('PDF descargado exitosamente');
    } catch (error) {
      console.error('Error exporting to PDF:', error);
      toast.error('Error al exportar a PDF');
    }
  };

  const getComponentBadges = (product) => {
    const badges = [];
    if (product.vpos_available) badges.push({ name: 'VPOS', color: 'bg-blue-100 text-blue-700' });
    if (product.gateway_available) badges.push({ name: 'Gateway', color: 'bg-green-100 text-green-700' });
    if (product.mpos_available) badges.push({ name: 'MPOS', color: 'bg-purple-100 text-purple-700' });
    if (product.link_available) badges.push({ name: 'Link', color: 'bg-amber-100 text-amber-700' });
    return badges;
  };

  if (loading) {
    return (
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center bg-white">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-green-600 mx-auto"></div>
            <p className="mt-4 text-slate-900">Cargando bancos...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-white">
      <Sidebar />
      
      <main className="flex-1 p-8" data-testid="banks-page">
        <div className="max-w-7xl mx-auto">
          <div className="flex justify-between items-center mb-8">
            <div>
              <h1 className="text-4xl font-bold text-slate-900 font-manrope mb-2">
                Bancos y Entidades
              </h1>
              <p className="text-slate-600">Gestione bancos y sus productos asociados</p>
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
                    data-testid="add-bank-button"
                    className="bg-brand-green-600 hover:bg-brand-green-700 text-white"
                  >
                    <Plus size={20} className="mr-2" />
                    Nuevo Banco
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                  <DialogHeader>
                    <DialogTitle className="font-manrope text-2xl">
                      {editingBank ? 'Editar Banco' : 'Nuevo Banco'}
                    </DialogTitle>
                  </DialogHeader>
                  <form onSubmit={handleSubmit} className="space-y-6">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="col-span-2">
                        <Label htmlFor="name">Nombre</Label>
                        <Input
                          id="name"
                          data-testid="bank-name-input"
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
                            <SelectItem value="Banco">Banco</SelectItem>
                            <SelectItem value="Fintech">Fintech</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <Label htmlFor="country">País</Label>
                        <Select
                          value={formData.country}
                          onValueChange={(value) => setFormData({ ...formData, country: value })}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="Venezuela">Venezuela</SelectItem>
                            <SelectItem value="Estados Unidos">Estados Unidos</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    <div className="border-t pt-4">
                      <h3 className="font-semibold text-lg mb-3 flex items-center gap-2">
                        <Package size={20} />
                        Medios de Pago Asociados
                      </h3>
                      
                      <div className="space-y-3 mb-4">
                        {formData.products.map((product, index) => {
                          const badges = getComponentBadges(product);
                          return (
                            <div
                              key={index}
                              className="p-3 bg-slate-50 rounded-lg border"
                            >
                              <div className="flex items-start justify-between">
                                <div className="flex-1">
                                  <p className="font-medium">{product.product_name}</p>
                                  {product.description && (
                                    <p className="text-sm text-slate-500">{product.description}</p>
                                  )}
                                  {badges.length > 0 && (
                                    <div className="flex gap-1 mt-2 flex-wrap">
                                      {badges.map((badge, i) => (
                                        <span key={i} className={`px-2 py-0.5 text-xs font-medium rounded ${badge.color}`}>
                                          {badge.name}
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                </div>
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  onClick={() => removeProduct(index)}
                                  className="text-red-600"
                                >
                                  <Trash2 size={16} />
                                </Button>
                              </div>
                            </div>
                          );
                        })}
                      </div>

                      <div className="bg-brand-blue-50 rounded-lg p-4 border border-brand-blue-200">
                        <p className="text-sm font-medium text-brand-blue-700 mb-3">Agregar Medio de Pago</p>
                        <div className="grid grid-cols-1 gap-3">
                          <div>
                            <Label className="text-sm text-slate-700">Seleccionar Medio de Pago</Label>
                            <Select
                              value={newProduct.service_id}
                              onValueChange={handleMedioPagoSelect}
                            >
                              <SelectTrigger data-testid="select-medio-pago-bank">
                                <SelectValue placeholder="Seleccione un medio de pago..." />
                              </SelectTrigger>
                              <SelectContent>
                                {mediosPago.map((medio) => (
                                  <SelectItem key={medio.service_id} value={medio.service_id}>
                                    {medio.name}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                          
                          {newProduct.service_id && newProduct.description && (
                            <div className="bg-white rounded-lg p-3 border border-slate-200">
                              <p className="text-xs font-medium text-slate-500 mb-1">Descripción</p>
                              <p className="text-sm text-slate-700">{newProduct.description}</p>
                            </div>
                          )}
                          
                          {newProduct.service_id && (
                            <div className="border-t pt-3 mt-2">
                              <p className="text-sm font-medium text-slate-700 mb-3">Compatibilidad del Medio de Pago (heredada)</p>
                              <div className="grid grid-cols-2 gap-3">
                                {COMPONENT_TYPES.map((comp) => {
                                  const Icon = comp.icon;
                                  const isEnabled = newProduct[comp.id];
                                  return (
                                    <div
                                      key={comp.id}
                                      className={`flex items-center gap-3 p-3 rounded-lg border ${
                                        isEnabled
                                          ? 'border-brand-green-600 bg-brand-green-50'
                                          : 'border-slate-200 bg-slate-50 opacity-50'
                                      }`}
                                    >
                                      <Icon size={18} className={isEnabled ? 'text-brand-green-600' : 'text-slate-400'} />
                                      <div>
                                        <p className="text-sm font-medium">{comp.name}</p>
                                        <p className="text-xs text-slate-500">{comp.description}</p>
                                      </div>
                                      {isEnabled && (
                                        <span className="ml-auto text-brand-green-600 text-xs font-medium">✓</span>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          )}
                          
                          <Button
                            type="button"
                            variant="outline"
                            onClick={addProduct}
                            disabled={!newProduct.service_id}
                            className="w-full mt-2 border-brand-green-600 text-brand-green-600 hover:bg-brand-green-50 disabled:opacity-50"
                          >
                            <Plus size={16} className="mr-1" />
                            Agregar Medio de Pago
                          </Button>
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
                        data-testid="save-bank-button"
                        className="bg-brand-green-600 hover:bg-brand-green-700 text-white"
                      >
                        {editingBank ? 'Actualizar' : 'Guardar'}
                      </Button>
                    </div>
                  </form>
                </DialogContent>
              </Dialog>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {banks.map((bank) => (
              <div
                key={bank.bank_id}
                className="bg-white rounded-lg border border-slate-200 p-6 card-hover"
              >
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="text-xl font-semibold text-slate-900 font-manrope">
                      {bank.name}
                    </h3>
                    <div className="flex gap-2 mt-2">
                      <span className="inline-block px-2 py-1 text-xs font-medium bg-slate-100 text-slate-700 rounded">
                        {bank.type}
                      </span>
                      <span className="inline-block px-2 py-1 text-xs font-medium bg-brand-blue-50 text-brand-blue-600 rounded">
                        {bank.country}
                      </span>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      data-testid={`edit-bank-${bank.bank_id}`}
                      onClick={() => openEditDialog(bank)}
                    >
                      <Pencil size={16} />
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      data-testid={`delete-bank-${bank.bank_id}`}
                      onClick={() => handleDelete(bank.bank_id)}
                      className="text-red-600 hover:text-red-700 hover:border-red-300"
                    >
                      <Trash2 size={16} />
                    </Button>
                  </div>
                </div>

                <div className="border-t pt-4">
                  <p className="text-sm font-medium text-slate-700 mb-2">
                    Medios de Pago: {bank.products?.length || 0}
                  </p>
                  {bank.products && bank.products.length > 0 && (
                    <ul className="space-y-2">
                      {bank.products.slice(0, 3).map((product, index) => {
                        const badges = getComponentBadges(product);
                        return (
                          <li key={index} className="text-sm">
                            <span className="text-slate-700 font-medium">• {product.product_name}</span>
                            {badges.length > 0 && (
                              <div className="flex gap-1 mt-1 ml-3 flex-wrap">
                                {badges.map((badge, i) => (
                                  <span key={i} className={`px-1.5 py-0.5 text-xs font-medium rounded ${badge.color}`}>
                                    {badge.name}
                                  </span>
                                ))}
                              </div>
                            )}
                          </li>
                        );
                      })}
                      {bank.products.length > 3 && (
                        <li className="text-sm text-slate-500 italic">
                          +{bank.products.length - 3} más...
                        </li>
                      )}
                    </ul>
                  )}
                </div>
              </div>
            ))}
          </div>

          {banks.length === 0 && (
            <div className="bg-white rounded-lg border border-slate-200 p-12 text-center text-slate-500">
              <p>No hay bancos registrados</p>
              <p className="text-sm mt-1">Cree su primer banco usando el botón superior</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default Banks;
