import { useState, useEffect, useMemo } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Search, Pencil, Wrench, Building2, AlertTriangle, Loader2 } from 'lucide-react';
import api from '../utils/api';
import { formatRif } from '../utils/rifFormatter';
import { toast } from 'sonner';
import { usePermission } from '../hooks/usePermission';

// "Componentes" = tipo_servicio (misma lista que el módulo Clientes)
const TIPOS_SERVICIO = ['VPOS', 'MPOS', 'Payment Gateway', 'Link de Pago'];

const emptyForm = {
  tipo_servicio: [],
  integrador_id: '', integrador_name: '',
  aplicativo: '',
  implementer_user_id: '', implementer_name: '',
  coordinator_user_id: '', coordinator_name: '',
};

export default function DatosImple() {
  const { canEdit } = usePermission('datos_imple');
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [integrators, setIntegrators] = useState([]);
  const [coordinadores, setCoordinadores] = useState([]);
  const [implementadores, setImplementadores] = useState([]);
  const [defaultCoordinator, setDefaultCoordinator] = useState({ user_id: '', name: '' });

  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [cl, intg, coords, impls, def] = await Promise.all([
          api.get('/clients'),
          api.get('/integrators/dropdown'),
          api.get('/auth/coordinadores'),
          api.get('/auth/implementadores'),
          api.get('/implementation/default-coordinator'),
        ]);
        setClients(cl.data || []);
        setIntegrators(intg.data || []);
        setCoordinadores(coords.data || []);
        setImplementadores(impls.data || []);
        setDefaultCoordinator(def.data || { user_id: '', name: '' });
      } catch (e) {
        toast.error('Error al cargar datos');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const refreshClients = async () => {
    const cl = await api.get('/clients');
    setClients(cl.data || []);
  };

  // Cuenta de sucursales por RIF (para el aviso de cascada)
  const branchesByRif = useMemo(() => {
    const map = {};
    clients.forEach(c => { if (c.rif) map[c.rif] = (map[c.rif] || 0) + 1; });
    return map;
  }, [clients]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return clients;
    const qClean = q.replace(/[.\-\s]/g, '');
    return clients.filter(c => {
      const name = `${c.fantasy_name || ''} ${c.legal_name || ''}`.toLowerCase();
      const rif = (c.rif || '').toLowerCase().replace(/[.\-\s]/g, '');
      const impl = (c.implementer_name || '').toLowerCase();
      return name.includes(q) || rif.includes(qClean) || impl.includes(q);
    });
  }, [clients, query]);

  const openEdit = (client) => {
    setEditing(client);
    setForm({
      tipo_servicio: client.tipo_servicio || [],
      integrador_id: client.integrador_id || '',
      integrador_name: client.integrador_name || '',
      aplicativo: client.aplicativo || '',
      implementer_user_id: client.implementer_user_id || '',
      implementer_name: client.implementer_name || '',
      // Precarga dinámica: si no tiene coordinador, usar el del perfil "Coordinador de Administración"
      coordinator_user_id: client.coordinator_user_id || defaultCoordinator.user_id || '',
      coordinator_name: client.coordinator_name || defaultCoordinator.name || '',
    });
  };

  const toggleTipo = (tipo) => {
    setForm(prev => ({
      ...prev,
      tipo_servicio: (prev.tipo_servicio || []).includes(tipo)
        ? prev.tipo_servicio.filter(t => t !== tipo)
        : [...(prev.tipo_servicio || []), tipo],
    }));
  };

  const onIntegradorChange = (integradorId) => {
    const intg = integrators.find(i => i.integrator_id === integradorId);
    setForm(prev => ({
      ...prev,
      integrador_id: integradorId,
      integrador_name: intg?.name || '',
      aplicativo: '', // reset al cambiar integrador
    }));
  };

  const aplicativos = useMemo(() => {
    if (!form.integrador_id) return [];
    const intg = integrators.find(i => i.integrator_id === form.integrador_id);
    return intg?.app_name ? [intg.app_name] : [];
  }, [form.integrador_id, integrators]);

  const onCoordinadorChange = (userId) => {
    if (userId === '_none_') { setForm(p => ({ ...p, coordinator_user_id: '', coordinator_name: '' })); return; }
    const u = coordinadores.find(c => c.user_id === userId);
    setForm(p => ({ ...p, coordinator_user_id: userId, coordinator_name: u?.full_name || '' }));
  };

  const onImplementadorChange = (userId) => {
    if (userId === '_none_') { setForm(p => ({ ...p, implementer_user_id: '', implementer_name: '' })); return; }
    const u = implementadores.find(c => c.user_id === userId);
    setForm(p => ({ ...p, implementer_user_id: userId, implementer_name: u?.full_name || '' }));
  };

  const handleSave = async () => {
    if (!editing) return;
    setSaving(true);
    try {
      const res = await api.put(`/clients/${editing.client_id}/imple-data`, form);
      toast.success(res.data.message || 'Datos actualizados');
      setEditing(null);
      await refreshClients();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error al guardar');
    } finally {
      setSaving(false);
    }
  };

  const clientName = (c) => c.fantasy_name || c.legal_name || 'Sin nombre';
  const editBranches = editing ? (branchesByRif[editing.rif] || 1) : 1;

  if (loading) {
    return (
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center bg-white">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-green-600" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-white">
      <Sidebar />
      <main className="flex-1 p-8" data-testid="datos-imple-page">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="flex justify-between items-center mb-2">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-cyan-50 text-cyan-600 flex items-center justify-center">
                <Wrench size={20} />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-900">Datos de Imple</h1>
                <p className="text-sm text-slate-500">Corrección rápida de datos de implementación del cliente.</p>
              </div>
            </div>
          </div>

          <div className="flex items-start gap-2 text-[12px] text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-4">
            <AlertTriangle size={15} className="mt-0.5 shrink-0" />
            <span>Los cambios guardados se replican automáticamente a <strong>todas las sucursales del mismo RIF</strong>.</span>
          </div>

          {/* Search */}
          <div className="relative mb-4 max-w-md">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Buscar por nombre de cliente, RIF o implementador..."
              className="pl-9"
              data-testid="datos-imple-search"
            />
          </div>

          {/* Table */}
          <div className="border border-slate-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm" data-testid="datos-imple-table">
              <thead className="bg-slate-50 text-slate-500 text-xs uppercase">
                <tr>
                  <th className="text-left px-4 py-3 font-semibold">Cliente</th>
                  <th className="text-left px-4 py-3 font-semibold">RIF</th>
                  <th className="text-left px-4 py-3 font-semibold">Sucursal</th>
                  <th className="text-left px-4 py-3 font-semibold">Integrador</th>
                  <th className="text-left px-4 py-3 font-semibold">Aplicación</th>
                  <th className="text-left px-4 py-3 font-semibold">Implementador</th>
                  <th className="text-left px-4 py-3 font-semibold">Coordinador</th>
                  <th className="text-right px-4 py-3 font-semibold">Acción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.length === 0 ? (
                  <tr><td colSpan={8} className="text-center py-10 text-slate-400">No se encontraron clientes.</td></tr>
                ) : filtered.map(c => (
                  <tr key={c.client_id} className="hover:bg-slate-50" data-testid={`datos-imple-row-${c.client_id}`}>
                    <td className="px-4 py-3 font-medium text-slate-800">{clientName(c)}</td>
                    <td className="px-4 py-3 text-slate-500">{formatRif(c.rif) || c.rif}</td>
                    <td className="px-4 py-3 text-slate-500">
                      <span className="inline-flex items-center gap-1">
                        <Building2 size={13} className="text-slate-400" />{c.sucursal || 'Principal'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{c.integrador_name || '—'}</td>
                    <td className="px-4 py-3 text-slate-600">{c.aplicativo || '—'}</td>
                    <td className="px-4 py-3 text-slate-600">{c.implementer_name || '—'}</td>
                    <td className="px-4 py-3 text-slate-600">{c.coordinator_name || '—'}</td>
                    <td className="px-4 py-3 text-right">
                      <Button
                        size="sm" variant="outline"
                        onClick={() => openEdit(c)}
                        disabled={!canEdit}
                        className="gap-1.5 text-xs"
                        data-testid={`datos-imple-edit-${c.client_id}`}
                      >
                        <Pencil size={13} /> Editar
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-slate-400 mt-2">{filtered.length} cliente(s)</p>
        </div>
      </main>

      {/* Edit dialog (solo 5 campos) */}
      <Dialog open={!!editing} onOpenChange={(o) => { if (!o) setEditing(null); }}>
        <DialogContent className="max-w-lg" data-testid="datos-imple-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Wrench size={18} className="text-cyan-600" />
              Editar Datos de Imple
            </DialogTitle>
          </DialogHeader>

          {editing && (
            <div className="space-y-4">
              <div className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
                <p className="text-sm font-semibold text-slate-800">{clientName(editing)}</p>
                <p className="text-xs text-slate-500">{formatRif(editing.rif) || editing.rif} · Sucursal: {editing.sucursal || 'Principal'}</p>
                {editBranches > 1 && (
                  <p className="text-[11px] text-amber-700 mt-1 flex items-center gap-1">
                    <AlertTriangle size={12} /> Se actualizarán <strong>{editBranches} sucursales</strong> con este RIF.
                  </p>
                )}
              </div>

              {/* 1. Componentes (tipo_servicio) */}
              <div>
                <Label className="text-xs font-semibold text-slate-600">Componentes</Label>
                <div className="flex flex-wrap gap-1.5 mt-1.5" data-testid="datos-imple-componentes">
                  {TIPOS_SERVICIO.map(ts => {
                    const on = (form.tipo_servicio || []).includes(ts);
                    return (
                      <button
                        key={ts} type="button" onClick={() => toggleTipo(ts)}
                        className={`px-2.5 py-1 rounded-full text-xs border transition-colors ${on ? 'bg-cyan-600 text-white border-cyan-600' : 'bg-white text-slate-600 border-slate-300 hover:border-cyan-400'}`}
                        data-testid={`datos-imple-componente-${ts.replace(/\s+/g, '-')}`}
                      >
                        {ts}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* 2. Integrador */}
              <div>
                <Label className="text-xs font-semibold text-slate-600">Integrador</Label>
                <Select value={form.integrador_id || '_none_'} onValueChange={(v) => v === '_none_' ? onIntegradorChange('') : onIntegradorChange(v)}>
                  <SelectTrigger className="mt-1.5" data-testid="datos-imple-integrador"><SelectValue placeholder="Seleccione integrador" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="_none_">— Ninguno —</SelectItem>
                    {integrators.map(i => <SelectItem key={i.integrator_id} value={i.integrator_id}>{i.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>

              {/* 3. Aplicación (aplicativo) */}
              <div>
                <Label className="text-xs font-semibold text-slate-600">Aplicación</Label>
                {aplicativos.length > 0 ? (
                  <Select value={form.aplicativo || '_none_'} onValueChange={(v) => setForm(p => ({ ...p, aplicativo: v === '_none_' ? '' : v }))}>
                    <SelectTrigger className="mt-1.5" data-testid="datos-imple-aplicacion"><SelectValue placeholder="Seleccione aplicación" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="_none_">— Ninguna —</SelectItem>
                      {aplicativos.map(a => <SelectItem key={a} value={a}>{a}</SelectItem>)}
                    </SelectContent>
                  </Select>
                ) : (
                  <Input
                    value={form.aplicativo || ''}
                    onChange={(e) => setForm(p => ({ ...p, aplicativo: e.target.value }))}
                    placeholder={form.integrador_id ? 'Aplicación del integrador' : 'Seleccione un integrador primero'}
                    className="mt-1.5"
                    data-testid="datos-imple-aplicacion-input"
                  />
                )}
              </div>

              {/* 4. Implementador */}
              <div>
                <Label className="text-xs font-semibold text-slate-600">Implementador</Label>
                <Select value={form.implementer_user_id || '_none_'} onValueChange={onImplementadorChange}>
                  <SelectTrigger className="mt-1.5" data-testid="datos-imple-implementador"><SelectValue placeholder="Seleccione implementador" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="_none_">— Ninguno —</SelectItem>
                    {implementadores.map(u => <SelectItem key={u.user_id} value={u.user_id}>{u.full_name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>

              {/* 5. Coordinador (precargado dinámicamente) */}
              <div>
                <Label className="text-xs font-semibold text-slate-600">Coordinador</Label>
                <Select value={form.coordinator_user_id || '_none_'} onValueChange={onCoordinadorChange}>
                  <SelectTrigger className="mt-1.5" data-testid="datos-imple-coordinador"><SelectValue placeholder="Seleccione coordinador" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="_none_">— Ninguno —</SelectItem>
                    {coordinadores.map(u => <SelectItem key={u.user_id} value={u.user_id}>{u.full_name}</SelectItem>)}
                  </SelectContent>
                </Select>
                {defaultCoordinator.name && (
                  <p className="text-[11px] text-slate-400 mt-1">Predeterminado (Coordinación de Administración): {defaultCoordinator.name}</p>
                )}
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setEditing(null)} data-testid="datos-imple-cancel">Cancelar</Button>
            <Button onClick={handleSave} disabled={saving || !canEdit} className="bg-cyan-600 hover:bg-cyan-700 text-white gap-1.5" data-testid="datos-imple-save">
              {saving && <Loader2 size={14} className="animate-spin" />}
              Guardar y replicar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
