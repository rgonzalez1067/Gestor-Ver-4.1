import { useState, useEffect, useRef, useMemo } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Switch } from '../components/ui/switch';
import { Badge } from '../components/ui/badge';
import { Checkbox } from '../components/ui/checkbox';
import { Input } from '../components/ui/input';
import { RadioGroup, RadioGroupItem } from '../components/ui/radio-group';
import { Label } from '../components/ui/label';
import { Users, Shield, ShieldAlert, Search, RefreshCw, Crown, User as UserIcon, Warehouse, Link2, ChevronDown, Power } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

// =============================
// Helpers UI (sticky constants)
// =============================
const LEVEL_COLORS = {
  none: { bg: 'bg-slate-100', text: 'text-slate-500', ring: 'ring-slate-300', dot: 'bg-slate-400' },
  read: { bg: 'bg-amber-50', text: 'text-amber-700', ring: 'ring-amber-300', dot: 'bg-amber-500' },
  edit: { bg: 'bg-emerald-50', text: 'text-emerald-700', ring: 'ring-emerald-400', dot: 'bg-emerald-500' },
};

// =============================
// SupervisorSelect (typeahead)
// =============================
const SupervisorSelect = ({ userId, currentSupervisorName, allUsers, onChange }) => {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const candidates = allUsers.filter(u => {
    if (u.user_id === userId) return false;
    if (u.is_active === false) return false;
    if (!search) return true;
    const name = `${u.first_name || ''} ${u.last_name || ''} ${u.email || ''}`.toLowerCase();
    return name.includes(search.toLowerCase());
  });

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full h-9 text-xs border rounded-md px-3 text-left truncate bg-white hover:bg-slate-50 transition"
        data-testid={`supervisor-btn-${userId}`}
      >
        {currentSupervisorName || <span className="text-slate-400">Sin supervisor</span>}
      </button>
      {open && (
        <div className="absolute z-50 mt-1 w-64 bg-white border rounded-lg shadow-lg" data-testid={`supervisor-dropdown-${userId}`}>
          <div className="p-1.5">
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Buscar usuario..."
              className="w-full px-2 py-1.5 text-xs border rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
              autoFocus
              data-testid={`supervisor-search-${userId}`}
            />
          </div>
          <div className="max-h-48 overflow-y-auto">
            <button type="button" onClick={() => { onChange(userId, null); setOpen(false); setSearch(''); }}
              className="w-full text-left px-3 py-1.5 text-xs text-slate-400 hover:bg-slate-50">
              Sin supervisor
            </button>
            {candidates.slice(0, 20).map(u => {
              const name = `${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email;
              return (
                <button key={u.user_id} type="button"
                  onClick={() => { onChange(userId, u.user_id); setOpen(false); setSearch(''); }}
                  className="w-full text-left px-3 py-1.5 text-xs hover:bg-slate-50 border-t border-slate-100">
                  <div className="font-medium text-slate-800">{name}</div>
                  <div className="text-[10px] text-slate-400">{u.cargo || ''} · {u.email}</div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

// =============================
// Main Component
// =============================
const AdminUsers = () => {
  const [users, setUsers] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [catalog, setCatalog] = useState(null);
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedUserId, setSelectedUserId] = useState(null);
  const [savingKey, setSavingKey] = useState(null);
  const [currentUser, setCurrentUser] = useState(null);

  useEffect(() => {
    const userStr = localStorage.getItem('user');
    if (userStr) setCurrentUser(JSON.parse(userStr));
    fetchAll();
  }, []);

  const fetchAll = async () => {
    try {
      setLoading(true);
      const [usersRes, whRes, catRes, profRes] = await Promise.all([
        api.get('/admin/users'),
        api.get('/inventory/warehouses').catch(() => ({ data: [] })),
        api.get('/admin/permission-catalog'),
        api.get('/admin/profiles').catch(() => ({ data: [] })),
      ]);
      setUsers(usersRes.data);
      setWarehouses(whRes.data || []);
      setCatalog(catRes.data);
      setProfiles(profRes.data || []);
      if (!selectedUserId && usersRes.data.length > 0) {
        setSelectedUserId(usersRes.data[0].user_id);
      }
    } catch (err) {
      if (err.response?.status === 403) toast.error('No tiene permisos para ver esta página');
      else toast.error('Error al cargar datos');
    } finally {
      setLoading(false);
    }
  };

  const selectedUser = useMemo(
    () => users.find(u => u.user_id === selectedUserId) || null,
    [users, selectedUserId]
  );

  const filteredUsers = useMemo(() => {
    const q = searchTerm.toLowerCase();
    if (!q) return users;
    return users.filter(u =>
      u.email?.toLowerCase().includes(q) ||
      u.first_name?.toLowerCase().includes(q) ||
      u.last_name?.toLowerCase().includes(q) ||
      u.name?.toLowerCase().includes(q) ||
      u.cedula?.includes(searchTerm)
    );
  }, [users, searchTerm]);

  // ========= Mutations =========
  const patchUser = (userId, patch) => {
    setUsers(prev => prev.map(u => u.user_id === userId ? { ...u, ...patch } : u));
  };

  const handleRoleChange = async (userId, newRole) => {
    try {
      await api.put(`/admin/users/${userId}/role?role=${newRole}`);
      patchUser(userId, { role: newRole });
      toast.success(`Rol actualizado a "${newRole}"`);
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  const handleStatusChange = async (userId, isActive) => {
    try {
      await api.put(`/admin/users/${userId}/status?is_active=${isActive}`);
      patchUser(userId, { is_active: isActive });
      toast.success(isActive ? 'Usuario activado' : 'Usuario desactivado');
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  const handleAlmacenChange = async (userId, almacenId) => {
    try {
      const value = almacenId === '__none__' ? null : almacenId;
      await api.put(`/admin/users/${userId}/almacen`, { almacen_asignado: value });
      patchUser(userId, { almacen_asignado: value });
      toast.success(value ? 'Almacén asignado' : 'Almacén desasignado');
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  const handleSupervisorChange = async (userId, supervisorId) => {
    try {
      const value = supervisorId || null;
      await api.put(`/admin/users/${userId}/supervisor`, { supervisor_id: value });
      const supervisor = value ? users.find(u => u.user_id === value) : null;
      const supervisorName = supervisor
        ? `${supervisor.first_name || ''} ${supervisor.last_name || ''}`.trim() || supervisor.email
        : null;
      patchUser(userId, { supervisor_id: value, supervisor_name: supervisorName });
      toast.success(value ? 'Supervisor asignado' : 'Supervisor removido');
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  const handleProfileChange = async (userId, profileId) => {
    try {
      const value = profileId === '__none__' ? null : profileId;
      const res = await api.put(`/admin/users/${userId}/profile`, { profile_id: value });
      // El backend devuelve el user actualizado con permisos/grupos/flags reinicializados
      const updated = res.data?.user || {};
      patchUser(userId, {
        profile_id: updated.profile_id ?? null,
        permissions: updated.permissions || {},
        menu_groups: updated.menu_groups || {},
        special_permissions: updated.special_permissions || [],
      });
      toast.success(value ? 'Perfil asignado (permisos heredados)' : 'Perfil removido');
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  const handleGroupToggle = async (userId, groupId, active) => {
    const k = `group-${userId}-${groupId}`;
    setSavingKey(k);
    try {
      const user = users.find(u => u.user_id === userId);
      const newGroups = { ...(user?.menu_groups || {}), [groupId]: !!active };
      await api.put(`/admin/users/${userId}/menu-groups`, { menu_groups: newGroups });
      patchUser(userId, { menu_groups: newGroups });
      toast.success(active ? 'Grupo activado' : 'Grupo desactivado');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error');
    } finally { setSavingKey(null); }
  };

  const handleLevelChange = async (userId, moduleId, level) => {
    const k = `level-${userId}-${moduleId}`;
    setSavingKey(k);
    try {
      const user = users.find(u => u.user_id === userId);
      const newPerms = { ...(user?.permissions || {}), [moduleId]: level };
      await api.put(`/admin/users/${userId}/permissions`, newPerms);
      patchUser(userId, { permissions: newPerms });
      toast.success('Nivel actualizado');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error');
    } finally { setSavingKey(null); }
  };

  const handleSpecialToggle = async (userId, flag, checked) => {
    const k = `sp-${userId}-${flag}`;
    setSavingKey(k);
    try {
      const user = users.find(u => u.user_id === userId);
      const current = user?.special_permissions || [];
      const updated = checked ? [...new Set([...current, flag])] : current.filter(f => f !== flag);
      await api.put(`/admin/users/${userId}/special-permissions`, { special_permissions: updated });
      patchUser(userId, { special_permissions: updated });
      toast.success('Función especial actualizada');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error');
    } finally { setSavingKey(null); }
  };

  // ========= Render helpers =========
  const getUserDisplay = (u) => {
    if (!u) return '';
    return u.first_name ? `${u.first_name} ${u.last_name || ''}`.trim() : (u.name || u.email);
  };

  return (
    <div className="flex h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-8 pt-8 pb-4 border-b border-slate-200 bg-white">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-3">
                <Shield className="h-7 w-7 text-blue-600" />
                Permisos de Usuarios
              </h1>
              <p className="text-sm text-slate-500 mt-1">Configure grupos de menú, niveles de acceso y funciones especiales por usuario.</p>
            </div>
            <Button variant="outline" onClick={fetchAll} disabled={loading} data-testid="refresh-users">
              <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Actualizar
            </Button>
          </div>
        </div>

        {/* Body: 2 column layout */}
        <div className="flex-1 grid grid-cols-12 overflow-hidden">
          {/* LEFT: user list */}
          <aside className="col-span-4 xl:col-span-3 border-r border-slate-200 bg-white flex flex-col overflow-hidden">
            <div className="p-3 border-b border-slate-100">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input
                  placeholder="Buscar usuario..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-9 h-9 text-sm"
                  data-testid="search-users"
                />
              </div>
              <p className="text-[11px] text-slate-400 mt-1">{filteredUsers.length} usuario(s)</p>
            </div>
            <div className="flex-1 overflow-y-auto" data-testid="user-list">
              {loading ? (
                <div className="p-8 text-center text-slate-400 text-sm">
                  <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2" />
                  Cargando...
                </div>
              ) : filteredUsers.length === 0 ? (
                <div className="p-8 text-center text-slate-400 text-sm">No hay usuarios</div>
              ) : filteredUsers.map(u => {
                const active = u.is_active !== false;
                const isSel = u.user_id === selectedUserId;
                const isMe = currentUser?.user_id === u.user_id;
                return (
                  <button
                    key={u.user_id}
                    onClick={() => setSelectedUserId(u.user_id)}
                    data-testid={`user-card-${u.user_id}`}
                    className={`w-full text-left px-4 py-3 border-b border-slate-100 hover:bg-slate-50 transition flex items-start gap-3 ${
                      isSel ? 'bg-blue-50 border-l-4 border-l-blue-500' : 'border-l-4 border-l-transparent'
                    } ${!active ? 'opacity-60' : ''}`}
                  >
                    <div className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 ${
                      u.role === 'admin' ? 'bg-amber-100' : 'bg-slate-100'
                    }`}>
                      {u.role === 'admin'
                        ? <Crown className="h-4 w-4 text-amber-600" />
                        : <UserIcon className="h-4 w-4 text-slate-600" />}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <p className="font-medium text-sm text-slate-900 truncate">{getUserDisplay(u)}</p>
                        {isMe && <Badge variant="secondary" className="text-[9px] px-1 py-0">Tú</Badge>}
                      </div>
                      <p className="text-[11px] text-slate-500 truncate">{u.email}</p>
                      <div className="flex items-center gap-1 mt-1">
                        <span className={`text-[9px] px-1.5 py-0.5 rounded ${u.role === 'admin' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-600'}`}>
                          {u.role === 'admin' ? 'Admin' : 'Usuario'}
                        </span>
                        <span className={`text-[9px] px-1.5 py-0.5 rounded ${active ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>
                          {active ? 'Activo' : 'Inactivo'}
                        </span>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </aside>

          {/* RIGHT: permissions panel */}
          <section className="col-span-8 xl:col-span-9 overflow-y-auto" data-testid="permissions-panel">
            {!selectedUser ? (
              <div className="h-full flex items-center justify-center text-slate-400">
                <div className="text-center">
                  <Users className="h-12 w-12 mx-auto mb-3 opacity-40" />
                  <p className="text-sm">Seleccione un usuario para configurar sus permisos</p>
                </div>
              </div>
            ) : (
              <UserPermissionsPanel
                user={selectedUser}
                currentUser={currentUser}
                catalog={catalog}
                warehouses={warehouses}
                allUsers={users}
                profiles={profiles}
                savingKey={savingKey}
                onRoleChange={handleRoleChange}
                onStatusChange={handleStatusChange}
                onAlmacenChange={handleAlmacenChange}
                onSupervisorChange={handleSupervisorChange}
                onProfileChange={handleProfileChange}
                onGroupToggle={handleGroupToggle}
                onLevelChange={handleLevelChange}
                onSpecialToggle={handleSpecialToggle}
              />
            )}
          </section>
        </div>
      </main>
    </div>
  );
};

// =============================
// Sub-component: UserPermissionsPanel
// =============================
const UserPermissionsPanel = ({
  user, currentUser, catalog, warehouses, allUsers, profiles, savingKey,
  onRoleChange, onStatusChange, onAlmacenChange, onSupervisorChange, onProfileChange,
  onGroupToggle, onLevelChange, onSpecialToggle,
}) => {
  const isMe = currentUser?.user_id === user.user_id;
  const isAdminUser = user.role === 'admin';
  const menuGroups = user.menu_groups || {};
  const permissions = user.permissions || {};
  const specials = user.special_permissions || [];
  const activeProfile = (profiles || []).find(p => p.profile_id === user.profile_id) || null;
  const profilePerms = activeProfile?.permissions || null;
  const profileGroups = activeProfile?.menu_groups || null;
  const profileSpecials = activeProfile?.special_permissions || null;

  if (!catalog) return <div className="p-8 text-slate-400">Cargando catálogo...</div>;

  const levels = catalog.levels || [];
  const modulesByGroup = (groupId) => (catalog.modules || []).filter(m => m.group === groupId);
  const specialsByModule = (moduleId) => (catalog.special_permissions || []).filter(s => s.module === moduleId);
  const displayName = user.first_name ? `${user.first_name} ${user.last_name || ''}`.trim() : (user.name || user.email);

  return (
    <div className="p-6 max-w-4xl">
      {/* Header card */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 mb-5 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className={`w-14 h-14 rounded-xl flex items-center justify-center ${isAdminUser ? 'bg-amber-100' : 'bg-slate-100'}`}>
              {isAdminUser ? <Crown className="h-7 w-7 text-amber-600" /> : <UserIcon className="h-7 w-7 text-slate-600" />}
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-900">{displayName}</h2>
              <p className="text-sm text-slate-500">{user.email}</p>
              <div className="flex items-center gap-2 mt-1">
                {user.cargo && <span className="text-[10px] px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded">{user.cargo}</span>}
                {user.sede && <span className="text-[10px] px-1.5 py-0.5 bg-indigo-100 text-indigo-700 rounded">{user.sede}</span>}
                {user.cedula && <span className="text-[10px] px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded">CI: {user.cedula}</span>}
              </div>
            </div>
          </div>
        </div>

        {/* Attributes grid: Rol, Estado, Almacén, Supervisor */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-5 pt-5 border-t border-slate-100">
          <div>
            <Label className="text-xs text-slate-500 uppercase tracking-wide">Rol</Label>
            <Select value={user.role || 'user'} onValueChange={(v) => onRoleChange(user.user_id, v)} disabled={isMe}>
              <SelectTrigger className="mt-1.5 h-9" data-testid={`role-select-${user.user_id}`}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="admin"><span className="flex items-center gap-2"><Crown className="h-4 w-4 text-amber-500" />Admin</span></SelectItem>
                <SelectItem value="user"><span className="flex items-center gap-2"><UserIcon className="h-4 w-4 text-slate-500" />Usuario</span></SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs text-slate-500 uppercase tracking-wide flex items-center gap-1"><Power size={10} /> Estado</Label>
            <div className="mt-3 flex items-center gap-2">
              <Switch
                checked={user.is_active !== false}
                onCheckedChange={(checked) => onStatusChange(user.user_id, checked)}
                disabled={isMe}
                data-testid={`user-status-${user.user_id}`}
              />
              <span className={`text-xs font-medium ${user.is_active !== false ? 'text-emerald-700' : 'text-red-700'}`}>
                {user.is_active !== false ? 'Activo' : 'Inactivo'}
              </span>
            </div>
          </div>
          <div>
            <Label className="text-xs text-slate-500 uppercase tracking-wide flex items-center gap-1"><Warehouse size={10} /> Almacén</Label>
            <Select value={user.almacen_asignado || '__none__'} onValueChange={(v) => onAlmacenChange(user.user_id, v)}>
              <SelectTrigger className="mt-1.5 h-9 text-xs" data-testid={`almacen-select-${user.user_id}`}>
                <SelectValue placeholder="Sin asignar" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__"><span className="text-slate-400">Sin asignar</span></SelectItem>
                {warehouses.map(wh => (
                  <SelectItem key={wh.warehouse_id} value={wh.warehouse_id}>
                    <span className="flex items-center gap-1.5"><Warehouse size={12} className="text-teal-600" />{wh.name}</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs text-slate-500 uppercase tracking-wide flex items-center gap-1"><Link2 size={10} /> Supervisor</Label>
            <div className="mt-1.5">
              <SupervisorSelect
                userId={user.user_id}
                currentSupervisorName={user.supervisor_name}
                allUsers={allUsers}
                onChange={onSupervisorChange}
              />
            </div>
          </div>
        </div>

        {/* Profile picker — fila separada */}
        {!isAdminUser && (
          <div className="mt-5 pt-5 border-t border-slate-100">
            <Label className="text-xs text-slate-500 uppercase tracking-wide flex items-center gap-1"><Shield size={10} /> Perfil asignado (techo de permisos)</Label>
            <div className="flex items-center gap-2 mt-1.5">
              <Select value={user.profile_id || '__none__'} onValueChange={(v) => onProfileChange(user.user_id, v)} disabled={isMe}>
                <SelectTrigger className="h-9 text-sm flex-1" data-testid={`profile-select-${user.user_id}`}>
                  <SelectValue placeholder="Sin perfil (acceso libre)" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__"><span className="text-slate-400">Sin perfil (acceso libre)</span></SelectItem>
                  {(profiles || []).map(p => (
                    <SelectItem key={p.profile_id} value={p.profile_id}>
                      <span className="flex items-center gap-1.5"><Shield size={12} className="text-purple-600" />{p.name}</span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {activeProfile && (
                <Badge variant="secondary" className="text-[10px] bg-purple-100 text-purple-700">
                  {(activeProfile.description || '').slice(0, 50) || 'Perfil activo'}
                </Badge>
              )}
            </div>
            {activeProfile && (
              <p className="text-[11px] text-slate-500 mt-1.5">
                El usuario hereda los permisos del perfil como <strong>techo</strong>. Solo puede ajustarse hacia abajo.
              </p>
            )}
          </div>
        )}
      </div>

      {/* Admin banner */}
      {isAdminUser && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4 flex items-start gap-2" data-testid="admin-banner">
          <ShieldAlert className="h-4 w-4 text-amber-600 mt-0.5 flex-shrink-0" />
          <p className="text-xs text-amber-800">
            Este usuario tiene rol <strong>Administrador</strong>: acceso total al sistema. Los toggles de grupos y niveles son sólo informativos.
            Funciones admin-only: {(catalog.admin_only_actions || []).map(a => a.label).join(' · ')}.
          </p>
        </div>
      )}

      {/* Groups + modules */}
      <h3 className="text-sm font-semibold text-slate-800 mb-3 uppercase tracking-wide">Menú y Funciones</h3>
      <div className="space-y-3" data-testid="groups-list">
        {(catalog.menu_groups || []).map(g => (
          <GroupCard
            key={g.id}
            group={g}
            active={isAdminUser ? true : (menuGroups[g.id] !== false)}
            disabled={isAdminUser || isMe}
            isAdminUser={isAdminUser}
            modules={modulesByGroup(g.id)}
            levels={levels}
            permissions={permissions}
            specials={specials}
            specialsByModule={specialsByModule}
            savingKey={savingKey}
            profileName={activeProfile?.name}
            profilePerms={profilePerms}
            profileGroups={profileGroups}
            profileSpecials={profileSpecials}
            onGroupToggle={(active) => onGroupToggle(user.user_id, g.id, active)}
            onLevelChange={(mid, lv) => onLevelChange(user.user_id, mid, lv)}
            onSpecialToggle={(flag, checked) => onSpecialToggle(user.user_id, flag, checked)}
            userId={user.user_id}
          />
        ))}
      </div>
    </div>
  );
};

// =============================
// Sub-component: GroupCard
// =============================
const LEVEL_RANK = { none: 0, read: 1, edit: 2 };

const GroupCard = ({
  group, active, disabled, isAdminUser, modules, levels, permissions, specials,
  specialsByModule, savingKey, profileName, profilePerms, profileGroups, profileSpecials,
  onGroupToggle, onLevelChange, onSpecialToggle, userId,
}) => {
  const [expanded, setExpanded] = useState(true);
  const inactiveCascade = !active;
  // Ceiling del grupo: si profileGroups tiene este grupo en false, el toggle no puede activarse.
  const groupProfileAllowed = profileGroups ? (profileGroups[group.id] !== false) : true;
  const groupSwitchDisabled = disabled || savingKey === `group-${userId}-${group.id}` || !groupProfileAllowed;
  const groupTip = !groupProfileAllowed && profileName
    ? `Acceso restringido: el perfil "${profileName}" tiene este grupo Inactivo.`
    : '';

  return (
    <div className={`bg-white rounded-lg border transition-all ${inactiveCascade ? 'border-slate-200 opacity-70' : 'border-slate-200'} shadow-sm`} data-testid={`group-card-${group.id}`}>
      {/* Group header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
        <button onClick={() => setExpanded(!expanded)} className="flex items-center gap-2 flex-1 text-left">
          <ChevronDown className={`h-4 w-4 text-slate-400 transition-transform ${expanded ? '' : '-rotate-90'}`} />
          <span className="font-semibold text-sm text-slate-800">{group.name}</span>
          {inactiveCascade && <span className="text-[10px] px-1.5 py-0.5 bg-red-100 text-red-700 rounded-full font-medium">Inactivo</span>}
          {isAdminUser && <span className="text-[10px] px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded-full font-medium">Admin — acceso total</span>}
          {!groupProfileAllowed && !isAdminUser && (
            <span className="text-[10px] px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded-full font-medium" title={groupTip}>
              Techo del perfil
            </span>
          )}
        </button>
        <div className="flex items-center gap-2" title={groupTip}>
          <span className="text-[11px] text-slate-500">{active ? 'Activo' : 'Inactivo'}</span>
          <Switch
            checked={active}
            disabled={groupSwitchDisabled}
            onCheckedChange={(checked) => onGroupToggle(checked)}
            data-testid={`group-toggle-${group.id}-${userId}`}
          />
        </div>
      </div>

      {/* Modules */}
      {expanded && (
        <div className="p-4 space-y-3">
          {modules.length === 0 ? (
            <p className="text-xs text-slate-400 italic">Sin submódulos configurados</p>
          ) : modules.map(m => {
            const level = permissions[m.id] || 'read';
            const specialFns = specialsByModule(m.id);
            const moduleDisabled = inactiveCascade || disabled;
            // Ceiling por módulo: profilePerms define el nivel máximo para este módulo.
            const profileLv = profilePerms ? (profilePerms[m.id] || 'edit') : null;
            const profileCap = profileLv ? LEVEL_RANK[profileLv] : 2;
            return (
              <div key={m.id} className={`border border-slate-200 rounded-md p-3 transition ${moduleDisabled ? 'bg-slate-50 opacity-60 pointer-events-none' : 'bg-white'}`} data-testid={`module-row-${m.id}-${userId}`}>
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${LEVEL_COLORS[level]?.dot || 'bg-slate-300'}`} />
                    <span className="font-medium text-sm text-slate-700">{m.name}</span>
                    {moduleDisabled && !isAdminUser && (
                      <span className="text-[9px] px-1.5 py-0.5 bg-slate-200 text-slate-500 rounded uppercase tracking-wide" data-testid={`module-disabled-badge-${m.id}-${userId}`}>
                        Grupo inactivo
                      </span>
                    )}
                    {profileLv && !isAdminUser && (
                      <span className="text-[9px] px-1.5 py-0.5 bg-purple-50 text-purple-600 rounded uppercase tracking-wide" title={`Nivel máximo permitido por el perfil: ${profileLv}`}>
                        Max: {profileLv === 'edit' ? 'Edición' : profileLv === 'read' ? 'Consulta' : 'Inactivo'}
                      </span>
                    )}
                  </div>
                  <RadioGroup
                    value={level}
                    onValueChange={(v) => onLevelChange(m.id, v)}
                    className="flex items-center gap-4"
                    disabled={moduleDisabled || savingKey === `level-${userId}-${m.id}`}
                  >
                    {levels.map(lv => {
                      const color = LEVEL_COLORS[lv.value] || LEVEL_COLORS.none;
                      const optionBlocked = profileLv && !isAdminUser && LEVEL_RANK[lv.value] > profileCap;
                      const optionTip = optionBlocked
                        ? `Acceso restringido: el nivel máximo para el perfil "${profileName}" es "${profileLv === 'edit' ? 'Edición Total' : profileLv === 'read' ? 'Consulta' : 'Inactivo'}".`
                        : '';
                      return (
                        <label key={lv.value}
                          title={optionTip}
                          className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded transition ${
                            level === lv.value ? `${color.bg} ${color.text} ring-1 ${color.ring}` : 'text-slate-500 hover:bg-slate-100'
                          } ${moduleDisabled || optionBlocked ? 'cursor-not-allowed opacity-40' : 'cursor-pointer'}`}>
                          <RadioGroupItem
                            value={lv.value}
                            disabled={optionBlocked}
                            data-testid={`level-${lv.value}-${m.id}-${userId}`}
                            className="h-3 w-3"
                          />
                          {lv.label}
                        </label>
                      );
                    })}
                  </RadioGroup>
                </div>
                {/* Special functions */}
                {specialFns.length > 0 && (
                  <div className={`mt-3 pt-3 border-t border-slate-100 ${moduleDisabled ? 'pointer-events-none opacity-60' : ''}`}>
                    <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-2">Funciones Especiales</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                      {specialFns.map(sp => {
                        const checked = specials.includes(sp.id);
                        const flagBlocked = profileSpecials && !isAdminUser && !profileSpecials.includes(sp.id);
                        const flagTip = flagBlocked
                          ? `Acceso restringido: el perfil "${profileName}" no incluye esta función.`
                          : (sp.description || '');
                        return (
                          <label key={sp.id} className={`flex items-start gap-2 text-xs ${flagBlocked ? 'cursor-not-allowed opacity-40' : 'cursor-pointer'}`} title={flagTip}>
                            <Checkbox
                              checked={checked}
                              disabled={moduleDisabled || flagBlocked || savingKey === `sp-${userId}-${sp.id}`}
                              onCheckedChange={(c) => onSpecialToggle(sp.id, c)}
                              className="h-3.5 w-3.5 mt-0.5"
                              data-testid={`sp-${sp.id}-${userId}`}
                            />
                            <span className={`${checked ? 'text-purple-700 font-medium' : 'text-slate-600'}`}>
                              {sp.label}
                              {flagBlocked && <span className="ml-1 text-[9px] text-purple-500 uppercase">no en perfil</span>}
                            </span>
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

export default AdminUsers;
