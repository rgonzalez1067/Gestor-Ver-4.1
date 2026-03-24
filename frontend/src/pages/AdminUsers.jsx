import { useState, useEffect } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Switch } from '../components/ui/switch';
import { Badge } from '../components/ui/badge';
import { Users, Shield, ShieldCheck, ShieldX, Search, RefreshCw, Crown, User as UserIcon } from 'lucide-react';
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

export const AdminUsers = () => {
  const [users, setUsers] = useState([]);
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
      const response = await api.get('/admin/users');
      setUsers(response.data);
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
          
          {/* Users Table */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="text-left py-4 px-6 text-sm font-semibold text-slate-700">Usuario</th>
                    <th className="text-left py-4 px-4 text-sm font-semibold text-slate-700">Rol</th>
                    <th className="text-center py-4 px-4 text-sm font-semibold text-slate-700">Estado</th>
                    {MODULES.map(module => (
                      <th key={module.id} className="text-center py-4 px-2 text-xs font-semibold text-slate-700">
                        {module.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {loading ? (
                    <tr>
                      <td colSpan={3 + MODULES.length} className="py-12 text-center text-slate-500">
                        <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2" />
                        Cargando usuarios...
                      </td>
                    </tr>
                  ) : filteredUsers.length === 0 ? (
                    <tr>
                      <td colSpan={3 + MODULES.length} className="py-12 text-center text-slate-500">
                        No se encontraron usuarios
                      </td>
                    </tr>
                  ) : (
                    filteredUsers.map(user => {
                      const isCurrentUser = currentUser?.user_id === user.user_id;
                      const displayName = user.first_name 
                        ? `${user.first_name} ${user.last_name || ''}`
                        : user.name || user.email;
                      
                      return (
                        <tr 
                          key={user.user_id} 
                          className={`hover:bg-slate-50 ${!user.is_active ? 'opacity-60' : ''}`}
                          data-testid={`user-row-${user.user_id}`}
                        >
                          {/* Usuario */}
                          <td className="py-4 px-6">
                            <div className="flex items-center gap-3">
                              <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                                user.role === 'admin' ? 'bg-amber-100' : 'bg-slate-100'
                              }`}>
                                {user.role === 'admin' ? (
                                  <Crown className="h-5 w-5 text-amber-600" />
                                ) : (
                                  <UserIcon className="h-5 w-5 text-slate-600" />
                                )}
                              </div>
                              <div>
                                <p className="font-medium text-slate-900 flex items-center gap-2">
                                  {displayName}
                                  {isCurrentUser && (
                                    <Badge variant="secondary" className="text-xs">Tú</Badge>
                                  )}
                                </p>
                                <p className="text-sm text-slate-500">{user.email}</p>
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
