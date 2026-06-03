import { useState, useEffect, useCallback } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from '../components/ui/dialog';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '../components/ui/alert-dialog';
import { Plus, Pencil, Trash2, Save, Tag, CheckCircle2, XCircle, Search } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';
import { usePermission } from '../hooks/usePermission';

export const CommercialCategories = () => {
  const { user } = usePermission('configuracion');
  const isAdmin = user?.role === 'admin';

  const [cats, setCats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: '', description: '', is_active: true });
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [saving, setSaving] = useState(false);

  const fetchCats = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/commercial-categories');
      setCats(Array.isArray(data) ? data : []);
    } catch {
      toast.error('No se pudo cargar el catálogo');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchCats(); }, [fetchCats]);

  const openNew = () => {
    setEditing(null);
    setForm({ name: '', description: '', is_active: true });
    setDialogOpen(true);
  };

  const openEdit = (c) => {
    setEditing(c);
    setForm({ name: c.name || '', description: c.description || '', is_active: c.is_active !== false });
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!form.name.trim()) {
      toast.error('El nombre es obligatorio');
      return;
    }
    setSaving(true);
    try {
      if (editing) {
        await api.put(`/commercial-categories/${editing.category_id}`, form);
        toast.success('Categoría actualizada');
      } else {
        await api.post('/commercial-categories', form);
        toast.success('Categoría creada');
      }
      setDialogOpen(false);
      fetchCats();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error al guardar');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await api.delete(`/commercial-categories/${deleteTarget.category_id}`);
      toast.success('Categoría eliminada');
      setDeleteTarget(null);
      fetchCats();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error al eliminar');
    }
  };

  const toggleActive = async (c) => {
    try {
      await api.put(`/commercial-categories/${c.category_id}`, { is_active: !c.is_active });
      fetchCats();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error al actualizar estado');
    }
  };

  const q = search.trim().toLowerCase();
  const filtered = q
    ? cats.filter(c => (c.name || '').toLowerCase().includes(q) || (c.description || '').toLowerCase().includes(q))
    : cats;

  return (
    <div className="flex h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-6xl mx-auto p-6 lg:p-8">
          {/* Header */}
          <div className="flex items-start justify-between gap-4 mb-6">
            <div>
              <h1 className="text-3xl font-bold text-slate-900 font-manrope flex items-center gap-2" data-testid="cc-page-title">
                <Tag size={28} className="text-indigo-600" />
                Categoría Comercial
              </h1>
              <p className="text-sm text-slate-600 mt-1">
                Catálogo dinámico de categorías utilizadas en la ficha de Clientes. Solo las activas aparecen en el dropdown.
              </p>
            </div>
            {isAdmin && (
              <Button onClick={openNew} data-testid="cc-new-btn">
                <Plus size={16} className="mr-1.5" />
                Nueva Categoría
              </Button>
            )}
          </div>

          {/* Search */}
          <div className="flex justify-end mb-4">
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-4 mb-4">
            <div className="relative max-w-md">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <Input
                placeholder="Buscar por nombre o descripción..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
                data-testid="cc-search-input"
              />
            </div>
          </div>

          {/* Table */}
          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            {loading ? (
              <div className="py-16 text-center text-sm text-slate-400">Cargando catálogo...</div>
            ) : filtered.length === 0 ? (
              <div className="py-16 text-center text-sm text-slate-400">
                {q ? 'Sin resultados para la búsqueda.' : 'No hay categorías aún. Crea la primera con el botón arriba.'}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid="cc-table">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="px-4 py-3 text-left font-medium text-slate-600">Nombre</th>
                      <th className="px-4 py-3 text-left font-medium text-slate-600">Descripción</th>
                      <th className="px-4 py-3 text-center font-medium text-slate-600">Estado</th>
                      <th className="px-4 py-3 text-left font-medium text-slate-600">Última actualización</th>
                      {isAdmin && <th className="px-4 py-3 text-right font-medium text-slate-600">Acciones</th>}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filtered.map((c) => (
                      <tr key={c.category_id} className="hover:bg-slate-50" data-testid={`cc-row-${c.category_id}`}>
                        <td className="px-4 py-3 font-medium text-slate-800">{c.name}</td>
                        <td className="px-4 py-3 text-slate-600 max-w-md">
                          {c.description ? c.description : <span className="text-slate-400 italic">—</span>}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <button
                            onClick={() => isAdmin && toggleActive(c)}
                            disabled={!isAdmin}
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium transition-colors ${
                              c.is_active
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100'
                                : 'bg-slate-100 text-slate-500 border border-slate-200 hover:bg-slate-200'
                            } ${isAdmin ? 'cursor-pointer' : 'cursor-default'}`}
                            data-testid={`cc-toggle-${c.category_id}`}
                          >
                            {c.is_active
                              ? <><CheckCircle2 size={12} /> Activa</>
                              : <><XCircle size={12} /> Inactiva</>
                            }
                          </button>
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-500">
                          {c.updated_at
                            ? `${new Date(c.updated_at).toLocaleString('es-VE')} · ${c.updated_by || ''}`
                            : c.created_at
                              ? `Creada: ${new Date(c.created_at).toLocaleDateString('es-VE')}`
                              : '—'}
                        </td>
                        {isAdmin && (
                          <td className="px-4 py-3 text-right whitespace-nowrap">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openEdit(c)}
                              data-testid={`cc-edit-${c.category_id}`}
                            >
                              <Pencil size={14} />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setDeleteTarget(c)}
                              className="text-red-600 hover:text-red-700 hover:bg-red-50"
                              data-testid={`cc-delete-${c.category_id}`}
                            >
                              <Trash2 size={14} />
                            </Button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
          {!isAdmin && (
            <p className="text-xs text-amber-600 mt-3" data-testid="cc-admin-warning">
              Solo los administradores pueden modificar el catálogo.
            </p>
          )}
        </div>
      </main>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-md" data-testid="cc-dialog">
          <DialogHeader>
            <DialogTitle>{editing ? 'Editar categoría' : 'Nueva categoría comercial'}</DialogTitle>
            <DialogDescription>
              {editing
                ? 'Los cambios al nombre se propagarán a los clientes que la usen.'
                : 'Completa los datos de la nueva categoría. Solo las activas aparecen en clientes.'}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div>
              <Label>Nombre <span className="text-red-500">*</span></Label>
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Ej. Retail"
                data-testid="cc-input-name"
              />
            </div>
            <div>
              <Label>Descripción (opcional)</Label>
              <Textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Breve descripción de esta categoría comercial..."
                rows={3}
                data-testid="cc-input-description"
              />
            </div>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                className="h-4 w-4 accent-indigo-600"
                data-testid="cc-input-active"
              />
              <span className="text-sm text-slate-700">Activa (visible en el dropdown de Clientes)</span>
            </label>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={saving} data-testid="cc-cancel-btn">
              Cancelar
            </Button>
            <Button onClick={handleSave} disabled={saving} data-testid="cc-save-btn">
              <Save size={14} className="mr-1.5" />
              {saving ? 'Guardando...' : (editing ? 'Actualizar' : 'Crear')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirm */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <AlertDialogContent data-testid="cc-delete-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar categoría?</AlertDialogTitle>
            <AlertDialogDescription>
              Esta acción no se puede deshacer. Si hay clientes que la usan, el sistema lo impedirá
              y deberás reasignarlos o desactivarla.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="cc-delete-cancel">Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-red-600 hover:bg-red-700"
              data-testid="cc-delete-confirm"
            >
              Eliminar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default CommercialCategories;
