import { useState, useEffect } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Plus, Pencil, Trash2, Package } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

export const Banks = () => {
  const [banks, setBanks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingBank, setEditingBank] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    type: 'Banco',
    country: 'Venezuela',
    products: []
  });
  const [newProduct, setNewProduct] = useState({ product_name: '', description: '' });

  useEffect(() => {
    fetchBanks();
  }, []);

  const fetchBanks = async () => {
    try {
      const response = await api.get('/banks');
      setBanks(response.data);
    } catch (error) {
      console.error('Error fetching banks:', error);
      toast.error('Error al cargar bancos');
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
      fetchBanks();
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
      fetchBanks();
    } catch (error) {
      console.error('Error deleting bank:', error);
      toast.error('Error al eliminar banco');
    }
  };

  const addProduct = () => {
    if (!newProduct.product_name) {
      toast.error('El nombre del producto es requerido');
      return;
    }
    setFormData({
      ...formData,
      products: [...formData.products, { ...newProduct }]
    });
    setNewProduct({ product_name: '', description: '' });
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
    setNewProduct({ product_name: '', description: '' });
    setEditingBank(null);
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
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-slate-900 mx-auto"></div>
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
            
            <Dialog open={dialogOpen} onOpenChange={handleDialogClose}>
              <DialogTrigger asChild>
                <Button
                  data-testid="add-bank-button"
                  className="bg-sky-600 hover:bg-sky-700 text-white"
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
                      Productos Asociados
                    </h3>
                    
                    <div className="space-y-2 mb-4">
                      {formData.products.map((product, index) => (
                        <div
                          key={index}
                          className="flex items-center justify-between p-3 bg-slate-50 rounded-lg border"
                        >
                          <div>
                            <p className="font-medium">{product.product_name}</p>
                            {product.description && (
                              <p className="text-sm text-slate-500">{product.description}</p>
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
                      ))}
                    </div>

                    <div className="grid grid-cols-3 gap-3">
                      <div className="col-span-2">
                        <Input
                          placeholder="Nombre del producto"
                          value={newProduct.product_name}
                          onChange={(e) => setNewProduct({ ...newProduct, product_name: e.target.value })}
                        />
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={addProduct}
                        className="w-full"
                      >
                        <Plus size={16} className="mr-1" />
                        Agregar
                      </Button>
                      <div className="col-span-3">
                        <Input
                          placeholder="Descripción (opcional)"
                          value={newProduct.description}
                          onChange={(e) => setNewProduct({ ...newProduct, description: e.target.value })}
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
                      data-testid="save-bank-button"
                      className="bg-sky-600 hover:bg-sky-700 text-white"
                    >
                      {editingBank ? 'Actualizar' : 'Guardar'}
                    </Button>
                  </div>
                </form>
              </DialogContent>
            </Dialog>
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
                      <span className="inline-block px-2 py-1 text-xs font-medium bg-sky-100 text-sky-700 rounded">
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
                    Productos: {bank.products?.length || 0}
                  </p>
                  {bank.products && bank.products.length > 0 && (
                    <ul className="space-y-1">
                      {bank.products.slice(0, 3).map((product, index) => (
                        <li key={index} className="text-sm text-slate-600">
                          • {product.product_name}
                        </li>
                      ))}
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
