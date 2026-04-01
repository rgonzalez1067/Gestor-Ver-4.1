import { useState, useEffect, useRef } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Switch } from '../components/ui/switch';
import { Badge } from '../components/ui/badge';
import { Checkbox } from '../components/ui/checkbox';
import { Users, Shield, ShieldCheck, ShieldX, Search, RefreshCw, Crown, User as UserIcon, Warehouse, Zap, Link2 } from 'lucide-react';
import { Input } from '../components/ui/input';
import api from '../utils/api';
import { toast } from 'sonner';

const MODULES = [
  { id: 'cotizaciones', name: 'Cotizaciones' },
  { id: 'clientes', name: 'Clientes' },
  { id: 'bancos', name: 'Bancos' },
  { id: 'medios_pago', name: 'Medios de Pago' },
  { id: 'dispositivos', name: 'Bienes y Servicios' },
  { id: 'integradores', name: 'Integradores' },
  { id: 'configuracion', name: 'Configuración' },
  { id: 'proyectos', name: 'Proyectos' },
  { id: 'inventarios', name: 'Inventarios' },
  { id: 'taller_equipos', name: 'Equipos en Reparación' },
  { id: 'nuevos_productos', name: 'Nuevos Productos' }
];

const PERMISSION_OPTIONS = [
  { value: 'none', label: 'Ninguno', icon: ShieldX, color: 'text-red-500' },
  { value: 'read', label: 'Leer', icon: Shield, color: 'text-yellow-500' },
  { value: 'edit', label: 'Editar', icon: ShieldCheck, color: 'text-green-500' }
];

// Permisos especiales disponibles (overrides)
const SPECIAL_PERMISSIONS = [
  { id: 'integradores:create', module: 'integradores', label: 'Crear Proyecto Integración', description: 'Permite crear nuevos proyectos aunque tenga permiso Leer' },
  { id: 'cotizaciones:impl_pyme', module: 'cotizaciones', label: 'Implementaciones PYME', description: 'Acceso a cotizaciones de implementación PYME (VPOS, MPOS, Gateway, Link)' },
  { id: 'cotizaciones:impl_corp', module: 'cotizaciones', label: 'Implementaciones Corporativas', description: 'Acceso a cotizaciones de implementación Corporativa' },
  { id: 'cotizaciones:equipos', module: 'cotizaciones', label: 'Equipos y Accesorios', description: 'Acceso a cotizaciones de venta de equipos, dispositivos y accesorios' },
  { id: 'cotizaciones:reparaciones', module: 'cotizaciones', label: 'Reparaciones', description: 'Acceso a cotizaciones de reparación de equipos (POS, Pinpad)' },
];

// Componente Supervisor con búsqueda tipo Typeahead
const SupervisorSelect = ({ userId, currentSupervisorId, currentSupervisorName, allUsers, onChange }) => {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const ref = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
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
        className="w-40 h-8 text-xs border rounded-md px-2 text-left truncate bg-white hover:bg-slate-50 transition-colors"
        data-testid={`supervisor-btn-${userId}`}
      >
        {currentSupervisorName || <span className="text-slate-400">Sin supervisor</span>}
      </button>
      {open && (
        <div className="absolute z-50 mt-1 w-56 bg-white border rounded-lg shadow-lg" data-testid={`supervisor-dropdown-${userId}`}>
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
          <div className="max-h-40 overflow-y-auto">
            <button
              type="button"
              onClick={() => { onChange(userId, null); setOpen(false); setSearch(''); }}
              className="w-full text-left px-3 py-1.5 text-xs text-slate-400 hover:bg-slate-50"
            >
              Sin supervisor
            </button>
            {candidates.slice(0, 10).map(u => {
              const name = `${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email;
              return (
                <button
                  key={u.user_id}
                  type="button"
                  onClick={() => { onChange(userId, u.user_id); setOpen(false); setSearch(''); }}
                  className={`w-full text-left px-3 py-1.5 text-xs hover:bg-blue-50 ${u.user_id === currentSupervisorId ? 'bg-blue-50 text-blue-700 font-medium' : 'text-slate-700'}`}
                  data-testid={`supervisor-option-${u.user_id}`}
                >
                  {name}
                  {u.cargo && <span className="text-slate-400 ml-1">({u.cargo})</span>}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export const AdminUsers = () => {
  const [users, setUsers] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [currentUser, setCurrentUser] = useState(null);
  const [savingUserId, setSavingUserId] = useState(null);
  
  useEffect(() => {
    // Obtener usuario actual
    const userStr = localStorage.getItem('user');
    if (userStr) {
      setCurrentUser(JSON.parse(userStr));
    }
    fetchUsers();
  }, []);
  
  const fetchUsers = async () => {
    try {
      setLoading(true);
      const [usersRes, whRes] = await Promise.all([
        api.get('/admin/users'),
        api.get('/inventory/warehouses').catch(() => ({ data: [] }))
      ]);
      setUsers(usersRes.data);
      setWarehouses(whRes.data || []);
    } catch (error) {
      console.error('Error fetching users:', error);
      if (error.response?.status === 403) {
        toast.error('No tiene permisos para ver esta página');
      } else {
        toast.error('Error al cargar usuarios');
      }
    } finally {
      setLoading(false);
    }
  };
  
  const handlePermissionChange = async (userId, module, newPermission) => {
    setSavingUserId(userId);
    
    try {
      // Obtener permisos actuales del usuario
      const user = users.find(u => u.user_id === userId);
      const currentPermissions = user?.permissions || {};
      
      // Actualizar permiso específico
      const newPermissions = {
        ...currentPermissions,
        [module]: newPermission
      };
      
      await api.put(`/admin/users/${userId}/permissions`, newPermissions);
      
      // Actualizar estado local
      setUsers(prev => prev.map(u => 
        u.user_id === userId 
          ? { ...u, permissions: newPermissions }
          : u
      ));
      
      toast.success('Permiso actualizado');
    } catch (error) {
      console.error('Error updating permission:', error);
      toast.error(error.response?.data?.detail || 'Error al actualizar permiso');
    } finally {
      setSavingUserId(null);
    }
  };
  
  const handleRoleChange = async (userId, newRole) => {
    try {
      await api.put(`/admin/users/${userId}/role?role=${newRole}`);
      
      setUsers(prev => prev.map(u => 
        u.user_id === userId 
          ? { ...u, role: newRole }
          : u
      ));
      
      toast.success(`Rol actualizado a "${newRole}"`);
    } catch (error) {
      console.error('Error updating role:', error);
      toast.error(error.response?.data?.detail || 'Error al actualizar rol');
    }
  };
  
  const handleStatusChange = async (userId, isActive) => {
    try {
      await api.put(`/admin/users/${userId}/status?is_active=${isActive}`);
      
      setUsers(prev => prev.map(u => 
        u.user_id === userId 
          ? { ...u, is_active: isActive }
          : u
      ));
      
      toast.success(isActive ? 'Usuario activado' : 'Usuario desactivado');
    } catch (error) {
      console.error('Error updating status:', error);
      toast.error(error.response?.data?.detail || 'Error al actualizar estado');
    }
  };

  const handleSpecialPermissionToggle = async (userId, permId, checked) => {
    try {
      const user = users.find(u => u.user_id === userId);
      const current = user?.special_permissions || [];
      const updated = checked
        ? [...new Set([...current, permId])]
        : current.filter(p => p !== permId);
      
      await api.put(`/admin/users/${userId}/special-permissions`, { special_permissions: updated });
      
      setUsers(prev => prev.map(u =>
        u.user_id === userId ? { ...u, special_permissions: updated } : u
      ));
      toast.success('Permiso especial actualizado');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al actualizar permiso especial');
    }
  };

  const handleAlmacenChange = async (userId, almacenId) => {
    try {
      const value = almacenId === '__none__' ? null : almacenId;
      await api.put(`/admin/users/${userId}/almacen`, { almacen_asignado: value });
      
      setUsers(prev => prev.map(u =>
        u.user_id === userId ? { ...u, almacen_asignado: value } : u
      ));
      toast.success(value ? 'Almacén asignado' : 'Almacén desasignado');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al asignar almacén');
    }
  };

  const handleSupervisorChange = async (userId, supervisorId) => {
    try {
      const value = supervisorId || null;
      await api.put(`/admin/users/${userId}/supervisor`, { supervisor_id: value });
      
      const supervisor = value ? users.find(u => u.user_id === value) : null;
      const supervisorName = supervisor 
        ? `${supervisor.first_name || ''} ${supervisor.last_name || ''}`.trim() || supervisor.email
        : null;
      
      setUsers(prev => prev.map(u =>
        u.user_id === userId ? { ...u, supervisor_id: value, supervisor_name: supervisorName } : u
      ));
      toast.success(value ? 'Supervisor asignado' : 'Supervisor removido');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al asignar supervisor');
    }
  };

  
  const filteredUsers = users.filter(user => {
    const searchLower = searchTerm.toLowerCase();
    return (
      user.email?.toLowerCase().includes(searchLower) ||
      user.first_name?.toLowerCase().includes(searchLower) ||
      user.last_name?.toLowerCase().includes(searchLower) ||
      user.name?.toLowerCase().includes(searchLower) ||
      user.cedula?.includes(searchTerm)
    );
  });
  
  const getPermissionIcon = (permission) => {
    const opt = PERMISSION_OPTIONS.find(p => p.value === permission);
    if (!opt) return null;
    const Icon = opt.icon;
    return <Icon className={`h-4 w-4 ${opt.color}`} />;
  };
  
  return (
    <div className="flex h-screen bg-slate-50">
      <Sidebar />
      
      <main className="flex-1 overflow-y-auto">
        <div className="p-8">
          {/* Header */}
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-3">
                <Users className="h-7 w-7 text-blue-600" />
                Gestión de Usuarios
              </h1>
              <p className="text-slate-600 mt-1">
                Administre roles y permisos de los usuarios del sistema
              </p>
            </div>
            
            <Button
              variant="outline"
              onClick={fetchUsers}
              disabled={loading}
              data-testid="refresh-users"
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Actualizar
            </Button>
          </div>
          
          {/* Search */}
          <div className="mb-6">
            <div className="relative max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder="Buscar por nombre, email o cédula..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                data-testid="search-users"
              />
            </div>
          </div>
          
          {/* Users Table — Sticky Headers & Columns */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-auto max-h-[calc(100vh-260px)]" data-testid="permissions-matrix">
              <table className="w-full border-collapse">
                <thead>
                  <tr>
                    {/* Intersección Maestra: sticky top + left, z-index máximo */}
                    <th className="sticky top-0 left-0 z-30 bg-slate-100 text-left py-4 px-6 text-sm font-semibold text-slate-700 border-b border-r border-slate-200 min-w-[280px]">
                      Usuario
                    </th>
                    <th className="sticky top-0 z-10 bg-slate-100 text-left py-4 px-4 text-sm font-semibold text-slate-700 border-b border-slate-200 min-w-[120px]">Rol</th>
                    <th className="sticky top-0 z-10 bg-slate-100 text-center py-4 px-4 text-sm font-semibold text-slate-700 border-b border-slate-200 min-w-[80px]">Estado</th>
                    <th className="sticky top-0 z-10 bg-slate-100 text-center py-4 px-3 text-xs font-semibold text-slate-700 border-b border-slate-200 min-w-[150px] whitespace-nowrap">
                      <span className="flex items-center justify-center gap-1"><Warehouse size={13} />Almacén</span>
                    </th>
                    <th className="sticky top-0 z-10 bg-slate-100 text-center py-4 px-3 text-xs font-semibold text-slate-700 border-b border-slate-200 min-w-[160px] whitespace-nowrap">
                      <span className="flex items-center justify-center gap-1"><Zap size={13} />Permisos Especiales</span>
                    </th>
                    <th className="sticky top-0 z-10 bg-slate-100 text-center py-4 px-3 text-xs font-semibold text-slate-700 border-b border-slate-200 min-w-[180px] whitespace-nowrap">
                      <span className="flex items-center justify-center gap-1"><Link2 size={13} />Supervisor</span>
                    </th>
                    {MODULES.map(module => (
                      <th key={module.id} className="sticky top-0 z-10 bg-slate-100 text-center py-4 px-2 text-xs font-semibold text-slate-700 border-b border-slate-200 min-w-[110px] whitespace-nowrap">
                        {module.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td colSpan={6 + MODULES.length} className="py-12 text-center text-slate-500">
                        <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2" />
                        Cargando usuarios...
                      </td>
                    </tr>
                  ) : filteredUsers.length === 0 ? (
                    <tr>
                      <td colSpan={6 + MODULES.length} className="py-12 text-center text-slate-500">
                        No se encontraron usuarios
                      </td>
                    </tr>
                  ) : (
                    filteredUsers.map((user, idx) => {
                      const isCurrentUser = currentUser?.user_id === user.user_id;
                      const displayName = user.first_name 
                        ? `${user.first_name} ${user.last_name || ''}`
                        : user.name || user.email;
                      const zebraClass = idx % 2 === 0 ? 'bg-white' : 'bg-slate-50/60';
                      const zebraStickyBg = idx % 2 === 0 ? 'bg-white' : 'bg-slate-50';
                      
                      return (
                        <tr 
                          key={user.user_id} 
                          className={`${zebraClass} hover:bg-blue-50/50 transition-colors ${!user.is_active ? 'opacity-60' : ''}`}
                          data-testid={`user-row-${user.user_id}`}
                        >
                          {/* Usuario — Columna sticky izquierda */}
                          <td className={`sticky left-0 z-20 ${zebraStickyBg} py-4 px-6 border-r border-slate-200`}
                              style={{ boxShadow: '2px 0 4px -2px rgba(0,0,0,0.06)' }}>
                            <div className="flex items-center gap-3">
                              <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
                                user.role === 'admin' ? 'bg-amber-100' : 'bg-slate-100'
                              }`}>
                                {user.role === 'admin' ? (
                                  <Crown className="h-5 w-5 text-amber-600" />
                                ) : (
                                  <UserIcon className="h-5 w-5 text-slate-600" />
                                )}
                              </div>
                              <div className="min-w-0">
                                <p className="font-medium text-slate-900 flex items-center gap-2 truncate">
                                  {displayName}
                                  {isCurrentUser && (
                                    <Badge variant="secondary" className="text-xs flex-shrink-0">Tú</Badge>
                                  )}
                                </p>
                                <p className="text-sm text-slate-500 truncate">{user.email}</p>
                                {user.cedula && (
                                  <p className="text-xs text-slate-400">CI: {user.cedula}</p>
                                )}
                              </div>
                            </div>
                          </td>
                          
                          {/* Rol */}
                          <td className="py-4 px-4">
                            <Select
                              value={user.role || 'user'}
                              onValueChange={(value) => handleRoleChange(user.user_id, value)}
                              disabled={isCurrentUser}
                            >
                              <SelectTrigger className="w-28">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="admin">
                                  <span className="flex items-center gap-2">
                                    <Crown className="h-4 w-4 text-amber-500" />
                                    Admin
                                  </span>
                                </SelectItem>
                                <SelectItem value="user">
                                  <span className="flex items-center gap-2">
                                    <UserIcon className="h-4 w-4 text-slate-500" />
                                    Usuario
                                  </span>
                                </SelectItem>
                              </SelectContent>
                            </Select>
                          </td>
                          
                          {/* Estado */}
                          <td className="py-4 px-4 text-center">
                            <Switch
                              checked={user.is_active !== false}
                              onCheckedChange={(checked) => handleStatusChange(user.user_id, checked)}
                              disabled={isCurrentUser}
                              data-testid={`user-status-${user.user_id}`}
                            />
                          </td>
                          
                          {/* Almacén Asignado */}
                          <td className="py-4 px-3 text-center">
                            <Select
                              value={user.almacen_asignado || '__none__'}
                              onValueChange={(value) => handleAlmacenChange(user.user_id, value)}
                            >
                              <SelectTrigger className="w-36 h-8 text-xs">
                                <SelectValue placeholder="Sin asignar" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="__none__">
                                  <span className="text-slate-400">Sin asignar</span>
                                </SelectItem>
                                {warehouses.map(wh => (
                                  <SelectItem key={wh.warehouse_id} value={wh.warehouse_id}>
                                    <span className="flex items-center gap-1.5">
                                      <Warehouse size={12} className="text-teal-600" />
                                      {wh.name}
                                    </span>
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </td>
                          
                          {/* Permisos Especiales */}
                          <td className="py-4 px-3">
                            <div className="flex flex-col gap-1.5">
                              {SPECIAL_PERMISSIONS.map(sp => {
                                const isChecked = (user.special_permissions || []).includes(sp.id);
                                return (
                                  <label key={sp.id} className="flex items-center gap-1.5 cursor-pointer text-xs" title={sp.description}>
                                    <Checkbox
                                      checked={isChecked}
                                      onCheckedChange={(checked) => handleSpecialPermissionToggle(user.user_id, sp.id, checked)}
                                      className="h-3.5 w-3.5"
                                      data-testid={`sp-${sp.id}-${user.user_id}`}
                                    />
                                    <span className={`${isChecked ? 'text-purple-700 font-medium' : 'text-slate-500'}`}>
                                      {sp.label}
                                    </span>
                                  </label>
                                );
                              })}
                            </div>
                          </td>
                          
                          {/* Supervisor */}
                          <td className="py-4 px-3 text-center">
                            <SupervisorSelect
                              userId={user.user_id}
                              currentSupervisorId={user.supervisor_id}
                              currentSupervisorName={user.supervisor_name}
                              allUsers={users}
                              onChange={handleSupervisorChange}
                            />
                          </td>
                          
                          {/* Permisos por módulo */}
                          {MODULES.map(module => {
                            const permission = user.permissions?.[module.id] || 'read';
                            
                            return (
                              <td key={module.id} className="py-4 px-2 text-center">
                                <Select
                                  value={permission}
                                  onValueChange={(value) => handlePermissionChange(user.user_id, module.id, value)}
                                  disabled={savingUserId === user.user_id}
                                >
                                  <SelectTrigger className="w-24 h-8 text-xs">
                                    <SelectValue>
                                      <span className="flex items-center gap-1">
                                        {getPermissionIcon(permission)}
                                        <span className="hidden sm:inline">
                                          {PERMISSION_OPTIONS.find(p => p.value === permission)?.label}
                                        </span>
                                      </span>
                                    </SelectValue>
                                  </SelectTrigger>
                                  <SelectContent>
                                    {PERMISSION_OPTIONS.map(opt => {
                                      const Icon = opt.icon;
                                      return (
                                        <SelectItem key={opt.value} value={opt.value}>
                                          <span className={`flex items-center gap-2 ${opt.color}`}>
                                            <Icon className="h-4 w-4" />
                                            {opt.label}
                                          </span>
                                        </SelectItem>
                                      );
                                    })}
                                  </SelectContent>
                                </Select>
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
          </div>
          
          {/* Legend */}
          <div className="mt-6 flex items-center gap-6 text-sm text-slate-600">
            <span className="font-medium">Leyenda de Permisos:</span>
            {PERMISSION_OPTIONS.map(opt => {
              const Icon = opt.icon;
              return (
                <span key={opt.value} className="flex items-center gap-1.5">
                  <Icon className={`h-4 w-4 ${opt.color}`} />
                  {opt.label}
                </span>
              );
            })}
          </div>
        </div>
      </main>
    </div>
  );
};

export default AdminUsers;
