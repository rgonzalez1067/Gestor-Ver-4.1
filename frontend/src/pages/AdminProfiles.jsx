import { useState, useEffect, useMemo } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { Checkbox } from '../components/ui/checkbox';
import { RadioGroup, RadioGroupItem } from '../components/ui/radio-group';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog';
import { Badge } from '../components/ui/badge';
import { Shield, Plus, Trash2, Copy, Search, RefreshCw, ChevronDown, Users } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const LEVEL_COLORS = {
  none: { dot: 'bg-slate-400' },
  read: { dot: 'bg-amber-500' },
  edit: { dot: 'bg-emerald-500' },
};

const AdminProfiles = () => {
  const [profiles, setProfiles] = useState([]);
  const [catalog, setCatalog] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(null);
  const [savingKey, setSavingKey] = useState(null);
  const [search, setSearch] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [deleteOpen, setDeleteOpen] = useState(false);

  useEffect(() => { fetchAll(); }, []);

  const fetchAll = async () => {
    try {
      setLoading(true);
      const [p, c] = await Promise.all([
        api.get('/admin/profiles'),
        api.get('/admin/permission-catalog'),
      ]);
      setProfiles(p.data);
      setCatalog(c.data);
      if (!selectedId && p.data.length > 0) setSelectedId(p.data[0].profile_id);
    } catch (err) {
      if (err.response?.status === 403) toast.error('Solo administradores');
      else toast.error('Error al cargar perfiles');
    } finally { setLoading(false); }
  };

  const selected = useMemo(() => profiles.find(p => p.profile_id === selectedId) || null, [profiles, selectedId]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    if (!q) return profiles;
    return profiles.filter(p => p.name?.toLowerCase().includes(q) || p.description?.toLowerCase().includes(q));
  }, [profiles, search]);

  const patchProfile = (pid, patch) => {
    setProfiles(prev => prev.map(p => p.profile_id === pid ? { ...p, ...patch } : p));
  };

  // ========= Mutations =========
  const handleCreate = async () => {
    if (!newName.trim()) { toast.error('Nombre requerido'); return; }
    try {
      const res = await api.post('/admin/profiles', {
        name: newName.trim(),
        description: newDesc.trim(),
      });
      setProfiles(prev => [...prev, res.data].sort((a, b) => a.name.localeCompare(b.name)));
      setSelectedId(res.data.profile_id);
      setCreateOpen(false); setNewName(''); setNewDesc('');
      toast.success('Perfil creado');
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  const handleDuplicate = async (pid) => {
    try {
      const res = await api.post(`/admin/profiles/${pid}/duplicate`);
      setProfiles(prev => [...prev, res.data].sort((a, b) => a.name.localeCompare(b.name)));
      setSelectedId(res.data.profile_id);
      toast.success('Perfil duplicado');
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  const handleDelete = async () => {
    if (!selected) return;
    try {
      await api.delete(`/admin/profiles/${selected.profile_id}`);
      const remaining = profiles.filter(p => p.profile_id !== selected.profile_id);
      setProfiles(remaining);
      setSelectedId(remaining[0]?.profile_id || null);
      setDeleteOpen(false);
      toast.success('Perfil eliminado');
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  const patchUpdate = async (patch) => {
    if (!selected) return;
    try {
      const res = await api.put(`/admin/profiles/${selected.profile_id}`, patch);
      patchProfile(selected.profile_id, res.data);
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  const handleGroupToggle = async (groupId, active) => {
    const k = `g-${groupId}`; setSavingKey(k);
    const newGroups = { ...(selected.menu_groups || {}), [groupId]: !!active };
    await patchUpdate({ menu_groups: newGroups });
    setSavingKey(null);
    toast.success(active ? 'Grupo activado' : 'Grupo desactivado');
  };

  const handleLevelChange = async (moduleId, level) => {
    const k = `lv-${moduleId}`; setSavingKey(k);
    const newPerms = { ...(selected.permissions || {}), [moduleId]: level };
    await patchUpdate({ permissions: newPerms });
    setSavingKey(null);
    toast.success('Nivel actualizado');
  };

  const handleSpecialToggle = async (flag, checked) => {
    const k = `sp-${flag}`; setSavingKey(k);
    const current = selected.special_permissions || [];
    const updated = checked ? [...new Set([...current, flag])] : current.filter(f => f !== flag);
    await patchUpdate({ special_permissions: updated });
    setSavingKey(null);
  };

  const handleNameBlur = async (e) => {
    const v = e.target.value.trim();
    if (v && v !== selected.name) await patchUpdate({ name: v });
  };
  const handleDescBlur = async (e) => {
    const v = e.target.value.trim();
    if (v !== (selected.description || '')) await patchUpdate({ description: v });
  };

  // ============================================================
  return (
    <div className="flex h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 overflow-hidden flex flex-col">
        <div className="px-8 pt-8 pb-4 border-b border-slate-200 bg-white">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-3">
                <Shield className="h-7 w-7 text-purple-600" />
                Perfiles de Usuario
              </h1>
              <p className="text-sm text-slate-500 mt-1">Plantillas de permisos que actúan como techo para los usuarios asignados.</p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={fetchAll} disabled={loading} data-testid="profiles-refresh">
                <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                Actualizar
              </Button>
              <Button onClick={() => setCreateOpen(true)} className="bg-purple-600 hover:bg-purple-700" data-testid="profile-new-btn">
                <Plus className="h-4 w-4 mr-1.5" />
                Nuevo Perfil
              </Button>
            </div>
          </div>
        </div>

        <div className="flex-1 grid grid-cols-12 overflow-hidden">
          {/* LEFT: profiles list */}
          <aside className="col-span-4 xl:col-span-3 border-r border-slate-200 bg-white flex flex-col overflow-hidden">
            <div className="p-3 border-b border-slate-100">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input placeholder="Buscar perfil..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9 h-9 text-sm" data-testid="profiles-search" />
              </div>
              <p className="text-[11px] text-slate-400 mt-1">{filtered.length} perfil(es)</p>
            </div>
            <div className="flex-1 overflow-y-auto" data-testid="profiles-list">
              {loading ? (
                <div className="p-8 text-center text-slate-400 text-sm"><RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2" />Cargando...</div>
              ) : filtered.length === 0 ? (
                <div className="p-8 text-center text-slate-400 text-sm">No hay perfiles</div>
              ) : filtered.map(p => {
                const isSel = p.profile_id === selectedId;
                return (
                  <button key={p.profile_id}
                    onClick={() => setSelectedId(p.profile_id)}
                    data-testid={`profile-card-${p.profile_id}`}
                    className={`w-full text-left px-4 py-3 border-b border-slate-100 hover:bg-slate-50 transition ${
                      isSel ? 'bg-purple-50 border-l-4 border-l-purple-500' : 'border-l-4 border-l-transparent'
                    }`}>
                    <div className="flex items-center justify-between">
                      <p className="font-medium text-sm text-slate-900 truncate">{p.name}</p>
                      <Badge variant="secondary" className="text-[9px] px-1.5 py-0"><Users size={9} className="mr-1" />{p.user_count || 0}</Badge>
                    </div>
                    {p.description && <p className="text-[11px] text-slate-500 line-clamp-2 mt-0.5">{p.description}</p>}
                  </button>
                );
              })}
            </div>
          </aside>

          {/* RIGHT: profile permissions panel */}
          <section className="col-span-8 xl:col-span-9 overflow-y-auto" data-testid="profile-panel">
            {!selected ? (
              <div className="h-full flex items-center justify-center text-slate-400">
                <div className="text-center">
                  <Shield className="h-12 w-12 mx-auto mb-3 opacity-40" />
                  <p className="text-sm">Seleccione un perfil o cree uno nuevo</p>
                </div>
              </div>
            ) : catalog ? (
              <div className="p-6 max-w-4xl">
                {/* Header card */}
                <div className="bg-white rounded-xl border border-slate-200 p-5 mb-5 shadow-sm">
                  <div className="flex items-start justify-between gap-4 mb-4">
                    <div className="flex items-center gap-3 flex-1">
                      <div className="w-12 h-12 rounded-xl bg-purple-100 flex items-center justify-center">
                        <Shield className="h-6 w-6 text-purple-600" />
                      </div>
                      <div className="flex-1">
                        <Input
                          defaultValue={selected.name}
                          onBlur={handleNameBlur}
                          className="text-lg font-semibold border-0 border-b border-transparent hover:border-slate-200 focus:border-purple-500 rounded-none px-0 h-auto py-0.5"
                          data-testid="profile-name-input"
                        />
                        <p className="text-[11px] text-slate-400 mt-1">ID: {selected.profile_id} · {selected.user_count || 0} usuario(s) vinculado(s)</p>
                      </div>
                    </div>
                    <div className="flex gap-1">
                      <Button variant="outline" size="sm" onClick={() => handleDuplicate(selected.profile_id)} data-testid="profile-duplicate-btn">
                        <Copy size={14} className="mr-1" />Duplicar
                      </Button>
                      <Button
                        variant="outline" size="sm"
                        onClick={() => setDeleteOpen(true)}
                        disabled={(selected.user_count || 0) > 0}
                        className="text-red-600 hover:text-red-700 disabled:opacity-40"
                        title={(selected.user_count || 0) > 0 ? `No se puede eliminar: ${selected.user_count} usuario(s) vinculado(s)` : ''}
                        data-testid="profile-delete-btn"
                      >
                        <Trash2 size={14} />
                      </Button>
                    </div>
                  </div>
                  <div>
                    <Label className="text-xs text-slate-500 uppercase tracking-wide">Descripción</Label>
                    <Textarea
                      defaultValue={selected.description || ''}
                      onBlur={handleDescBlur}
                      rows={2}
                      placeholder="Descripción funcional del perfil..."
                      className="mt-1 text-sm"
                      data-testid="profile-desc-input"
                    />
                  </div>
                </div>

                {/* Groups + modules */}
                <h3 className="text-sm font-semibold text-slate-800 mb-3 uppercase tracking-wide">Techo de permisos (menús y funciones)</h3>
                <div className="space-y-3" data-testid="profile-groups-list">
                  {(catalog.menu_groups || []).map(g => {
                    const active = selected.menu_groups?.[g.id] !== false;
                    const modules = (catalog.modules || []).filter(m => m.group === g.id);
                    return (
                      <GroupCard
                        key={g.id}
                        group={g}
                        active={active}
                        modules={modules}
                        levels={catalog.levels}
                        permissions={selected.permissions || {}}
                        specials={selected.special_permissions || []}
                        specialsByModule={(mid) => (catalog.special_permissions || []).filter(s => s.module === mid)}
                        savingKey={savingKey}
                        onGroupToggle={(v) => handleGroupToggle(g.id, v)}
                        onLevelChange={handleLevelChange}
                        onSpecialToggle={handleSpecialToggle}
                      />
                    );
                  })}
                </div>
              </div>
            ) : null}
          </section>
        </div>
      </main>

      {/* Create dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Nuevo Perfil</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Nombre *</Label>
              <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Ej: Vendedor Pyme" data-testid="new-profile-name" />
            </div>
            <div>
              <Label>Descripción</Label>
              <Textarea value={newDesc} onChange={(e) => setNewDesc(e.target.value)} rows={3} placeholder="Función del perfil..." data-testid="new-profile-desc" />
            </div>
            <p className="text-xs text-slate-500">El perfil se creará con acceso de Edición Total a todos los módulos. Ajuste los niveles luego.</p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>Cancelar</Button>
            <Button onClick={handleCreate} className="bg-purple-600 hover:bg-purple-700" data-testid="new-profile-submit">Crear</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete dialog */}
      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Eliminar perfil</AlertDialogTitle>
            <AlertDialogDescription>
              ¿Confirma eliminar el perfil <strong>{selected?.name}</strong>? Esta acción no se puede deshacer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-red-600 hover:bg-red-700" data-testid="profile-delete-confirm">Eliminar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

// =============================
// GroupCard (for profile editor — simpler than user variant, no ceiling since this IS the ceiling)
// =============================
const GroupCard = ({ group, active, modules, levels, permissions, specials, specialsByModule, savingKey, onGroupToggle, onLevelChange, onSpecialToggle }) => {
  const [expanded, setExpanded] = useState(true);
  return (
    <div className={`bg-white rounded-lg border border-slate-200 shadow-sm ${!active ? 'opacity-70' : ''}`} data-testid={`profile-group-${group.id}`}>
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
        <button onClick={() => setExpanded(!expanded)} className="flex items-center gap-2 flex-1 text-left">
          <ChevronDown className={`h-4 w-4 text-slate-400 transition-transform ${expanded ? '' : '-rotate-90'}`} />
          <span className="font-semibold text-sm text-slate-800">{group.name}</span>
          {!active && <span className="text-[10px] px-1.5 py-0.5 bg-red-100 text-red-700 rounded-full font-medium">Inactivo</span>}
        </button>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-500">{active ? 'Activo' : 'Inactivo'}</span>
          <Switch
            checked={active}
            disabled={savingKey === `g-${group.id}`}
            onCheckedChange={onGroupToggle}
            data-testid={`profile-group-toggle-${group.id}`}
          />
        </div>
      </div>
      {expanded && (
        <div className="p-4 space-y-3">
          {modules.length === 0 ? <p className="text-xs text-slate-400 italic">Sin submódulos</p> : modules.map(m => {
            const level = permissions[m.id] || 'read';
            const specialFns = specialsByModule(m.id);
            const disabled = !active;
            return (
              <div key={m.id} className={`border border-slate-200 rounded-md p-3 ${disabled ? 'bg-slate-50 opacity-60 pointer-events-none' : 'bg-white'}`}>
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${LEVEL_COLORS[level]?.dot}`} />
                    <span className="font-medium text-sm text-slate-700">{m.name}</span>
                  </div>
                  <RadioGroup
                    value={level}
                    onValueChange={(v) => onLevelChange(m.id, v)}
                    className="flex items-center gap-4"
                    disabled={disabled || savingKey === `lv-${m.id}`}
                  >
                    {levels.map(lv => (
                      <label key={lv.value} className={`flex items-center gap-1.5 cursor-pointer text-xs px-2 py-1 rounded ${
                        level === lv.value ? 'bg-slate-100 text-slate-800 font-medium' : 'text-slate-500 hover:bg-slate-100'
                      }`}>
                        <RadioGroupItem value={lv.value} data-testid={`profile-lv-${lv.value}-${m.id}`} className="h-3 w-3" />
                        {lv.label}
                      </label>
                    ))}
                  </RadioGroup>
                </div>
                {specialFns.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-slate-100">
                    <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-2">Funciones Especiales</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                      {specialFns.map(sp => {
                        const checked = specials.includes(sp.id);
                        return (
                          <label key={sp.id} className="flex items-start gap-2 cursor-pointer text-xs" title={sp.description}>
                            <Checkbox
                              checked={checked}
                              disabled={savingKey === `sp-${sp.id}`}
                              onCheckedChange={(c) => onSpecialToggle(sp.id, c)}
                              className="h-3.5 w-3.5 mt-0.5"
                              data-testid={`profile-sp-${sp.id}`}
                            />
                            <span className={checked ? 'text-purple-700 font-medium' : 'text-slate-600'}>{sp.label}</span>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default AdminProfiles;
