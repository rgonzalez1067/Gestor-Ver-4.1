import { useEffect, useState } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../components/ui/select';
import { Server, Plus, Trash2, RefreshCw } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const TIPOS = ['Monocomercio', 'Multicomercio'];

export default function ServersCatalog() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ tipo: 'Monocomercio', descripcion: '' });
  const isAdmin = (() => { try { const u = JSON.parse(localStorage.getItem('user') || '{}'); return u?.role === 'admin'; } catch { return false; } })();

  const load = async () => {
    try { const { data } = await api.get('/servers'); setItems(data || []); }
    catch { toast.error('Error al cargar servidores'); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!form.descripcion.trim()) { toast.error('La descripción es obligatoria'); return; }
    setSaving(true);
    try {
      await api.post('/servers', { tipo: form.tipo, descripcion: form.descripcion.trim() });
      toast.success('Servidor registrado');
      setForm({ tipo: 'Monocomercio', descripcion: '' });
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Error al registrar'); }
    finally { setSaving(false); }
  };

  const remove = async (s) => {
    if (!window.confirm(`¿Eliminar el servidor "${s.descripcion}" del catálogo?`)) return;
    try { await api.delete(`/servers/${s.server_id}`); toast.success('Eliminado'); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || 'Error al eliminar'); }
  };

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 p-8" data-testid="servers-catalog-page">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-12 h-12 rounded-xl bg-indigo-100 text-indigo-600 flex items-center justify-center"><Server size={26} /></div>
            <div>
              <h1 className="text-3xl font-bold text-slate-900 font-manrope">Servidores</h1>
              <p className="text-slate-600 text-sm mt-1">Catálogo maestro de servidores clasificados por tipo (Monocomercio / Multicomercio).</p>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6" data-testid="server-form">
            <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2"><Plus size={18} /> Registrar servidor</h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <Label className="text-sm">Tipo <span className="text-red-500">*</span></Label>
                <Select value={form.tipo} onValueChange={(v) => setForm({ ...form, tipo: v })}>
                  <SelectTrigger className="mt-1" data-testid="server-tipo-select"><SelectValue /></SelectTrigger>
                  <SelectContent>{TIPOS.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="sm:col-span-2">
                <Label className="text-sm">Descripción <span className="text-red-500">*</span> <span className="text-xs text-slate-400">(máx. 50)</span></Label>
                <Input value={form.descripcion} maxLength={50} onChange={(e) => setForm({ ...form, descripcion: e.target.value })} placeholder="Ej: MSC principal caja 1" className="mt-1" data-testid="server-descripcion-input" />
                <p className="text-[11px] text-slate-400 mt-1">{form.descripcion.length}/50</p>
              </div>
            </div>
            <div className="flex justify-end mt-2">
              <Button onClick={save} disabled={saving} className="bg-indigo-600 hover:bg-indigo-700 text-white" data-testid="server-save-btn">
                {saving ? 'Guardando...' : 'Agregar al catálogo'}
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
              <div className="py-10 text-center text-slate-400">Sin servidores registrados</div>
            ) : (
              <table className="w-full text-sm" data-testid="servers-table">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="px-4 py-2.5 text-left font-medium text-slate-600">Tipo</th>
                    <th className="px-4 py-2.5 text-left font-medium text-slate-600">Descripción</th>
                    {isAdmin && <th className="px-4 py-2.5 text-right"></th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {items.map((s) => (
                    <tr key={s.server_id} className="hover:bg-slate-50" data-testid={`server-row-${s.server_id}`}>
                      <td className="px-4 py-2.5">
                        <Badge className={s.tipo === 'Multicomercio' ? 'bg-blue-100 text-blue-700 border-blue-200' : 'bg-teal-100 text-teal-700 border-teal-200'}>{s.tipo}</Badge>
                      </td>
                      <td className="px-4 py-2.5 text-slate-700">{s.descripcion}</td>
                      {isAdmin && (
                        <td className="px-4 py-2.5 text-right">
                          <Button size="sm" variant="ghost" onClick={() => remove(s)} data-testid={`server-delete-${s.server_id}`} className="text-rose-500 hover:text-rose-700">
                            <Trash2 size={14} />
                          </Button>
                        </td>
                      )}
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
