import { useEffect, useState } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import { Badge } from '../components/ui/badge';
import { Printer, Plus, Trash2, RefreshCw, Check, X, Pencil } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

export default function FiscalPrintersCatalog() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ marca: '', modelo: '', valida_voucher_vpos: false });
  const isAdmin = (() => { try { const u = JSON.parse(localStorage.getItem('user') || '{}'); return u?.role === 'admin'; } catch { return false; } })();

  const load = async () => {
    try {
      const { data } = await api.get('/fiscal-printers');
      setItems(data || []);
    } catch { toast.error('Error al cargar impresoras fiscales'); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const resetForm = () => { setForm({ marca: '', modelo: '', valida_voucher_vpos: false }); setEditingId(null); };

  const startEdit = (m) => {
    setEditingId(m.model_id);
    setForm({ marca: m.marca || '', modelo: m.modelo || '', valida_voucher_vpos: !!m.valida_voucher_vpos });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const save = async () => {
    if (!form.marca.trim() || !form.modelo.trim()) { toast.error('Marca y Modelo son obligatorios'); return; }
    setSaving(true);
    try {
      const payload = { marca: form.marca.trim(), modelo: form.modelo.trim(), valida_voucher_vpos: form.valida_voucher_vpos };
      if (editingId) {
        await api.put(`/fiscal-printers/${editingId}`, payload);
        toast.success('Impresora fiscal actualizada');
      } else {
        await api.post('/fiscal-printers', payload);
        toast.success('Impresora fiscal registrada');
      }
      resetForm();
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Error al guardar'); }
    finally { setSaving(false); }
  };

  const remove = async (m) => {
    if (!window.confirm(`¿Eliminar "${m.name}" del catálogo?`)) return;
    try { await api.delete(`/fiscal-printers/${m.model_id}`); toast.success('Eliminado'); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || 'Error al eliminar'); }
  };

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 p-8" data-testid="fiscal-printers-catalog-page">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-12 h-12 rounded-xl bg-purple-100 text-purple-600 flex items-center justify-center"><Printer size={26} /></div>
            <div>
              <h1 className="text-3xl font-bold text-slate-900 font-manrope">Impresoras Fiscales</h1>
              <p className="text-slate-600 text-sm mt-1">Catálogo maestro de impresoras fiscales (Marca, Modelo y validez para vouchers VPOS).</p>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6" data-testid="fiscal-printer-form">
            <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
              {editingId ? <><Pencil size={18} /> Editar impresora fiscal</> : <><Plus size={18} /> Registrar impresora fiscal</>}
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <Label className="text-sm">Marca <span className="text-red-500">*</span></Label>
                <Input value={form.marca} onChange={(e) => setForm({ ...form, marca: e.target.value })} placeholder="Ej: Bixolon, HKA, PNP" className="mt-1" data-testid="fp-marca-input" />
              </div>
              <div>
                <Label className="text-sm">Modelo <span className="text-red-500">*</span></Label>
                <Input value={form.modelo} onChange={(e) => setForm({ ...form, modelo: e.target.value })} placeholder="Ej: SRP-812, PP-9" className="mt-1" data-testid="fp-modelo-input" />
              </div>
            </div>
            <label className="flex items-center gap-2 mt-4 cursor-pointer text-sm text-slate-700">
              <Checkbox checked={form.valida_voucher_vpos} onCheckedChange={(v) => setForm({ ...form, valida_voucher_vpos: !!v })} data-testid="fp-valida-vpos" />
              Válida para impresión de vouchers VPOS
            </label>
            <div className="flex justify-end gap-2 mt-4">
              {editingId && (
                <Button variant="outline" onClick={resetForm} data-testid="fp-cancel-btn">Cancelar</Button>
              )}
              <Button onClick={save} disabled={saving} className="bg-purple-600 hover:bg-purple-700 text-white" data-testid="fp-save-btn">
                {saving ? 'Guardando...' : editingId ? 'Guardar cambios' : 'Agregar al catálogo'}
              </Button>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100">
              <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">Registrados ({items.length})</h2>
              <Button variant="outline" size="sm" onClick={load}><RefreshCw size={14} className={loading ? 'animate-spin' : ''} /></Button>
            </div>
            {loading ? (
              <div className="py-10 text-center text-slate-400">Cargando...</div>
            ) : items.length === 0 ? (
              <div className="py-10 text-center text-slate-400">Sin impresoras registradas</div>
            ) : (
              <table className="w-full text-sm" data-testid="fiscal-printers-table">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="px-4 py-2.5 text-left font-medium text-slate-600">Marca</th>
                    <th className="px-4 py-2.5 text-left font-medium text-slate-600">Modelo</th>
                    <th className="px-4 py-2.5 text-center font-medium text-slate-600">Voucher VPOS</th>
                    <th className="px-4 py-2.5 text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {items.map((m) => (
                    <tr key={m.model_id} className="hover:bg-slate-50" data-testid={`fp-row-${m.model_id}`}>
                      <td className="px-4 py-2.5 text-slate-800">{m.marca || m.name}</td>
                      <td className="px-4 py-2.5 text-slate-600">{m.modelo || '—'}</td>
                      <td className="px-4 py-2.5 text-center">
                        {m.valida_voucher_vpos
                          ? <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200"><Check size={12} className="mr-1" />Sí</Badge>
                          : <Badge className="bg-slate-100 text-slate-500 border-slate-200"><X size={12} className="mr-1" />No</Badge>}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <div className="flex justify-end gap-1">
                          <Button size="sm" variant="ghost" onClick={() => startEdit(m)} data-testid={`fp-edit-${m.model_id}`} className="text-slate-500 hover:text-purple-700">
                            <Pencil size={14} />
                          </Button>
                          {isAdmin && (
                            <Button size="sm" variant="ghost" onClick={() => remove(m)} data-testid={`fp-delete-${m.model_id}`} className="text-rose-500 hover:text-rose-700">
                              <Trash2 size={14} />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
