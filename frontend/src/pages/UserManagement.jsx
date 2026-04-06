import { useState, useEffect } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { 
  Users, Search, Plus, Edit, Key, UserCheck, UserX, 
  Building2, Phone, Mail, CreditCard, Briefcase, MapPin,
  Shield, ShieldCheck, Filter, RefreshCw
} from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

// Configuración de sedes
const SEDES = [
  { id: 'PYME', name: 'PYME', color: 'bg-blue-100 text-blue-800 border-blue-300' },
  { id: 'CORP', name: 'CORP', color: 'bg-purple-100 text-purple-800 border-purple-300' }
];

// Configuración de perfiles
const ROLES = [
  { id: 'admin', name: 'Administrador', description: 'Nivel Total', icon: ShieldCheck, color: 'text-amber-600' },
  { id: 'user', name: 'Usuario', description: 'Nivel Operativo', icon: Shield, color: 'text-slate-600' }
];

// Departamentos
const DEPARTAMENTOS = [
  'Desarrollo',
  'Aseguramiento de Calidad',
  'Implementación',
  'Infraestructura',
  'Operaciones',
  'Dirección',
  'Ventas Pyme',
  'Ventas Corporativas',
  'Administración',
];

// Cargos
const CARGOS = [
  'Director',
  'Gerente',
  'Coordinador',
  'Analista',
  'Asistente',
  'Tecnico',
  'Desarrollador',
  'Implementador',
  'Ejecutivo',
];

export const UserManagement = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterSede, setFilterSede] = useState('all');
  const [filterRole, setFilterRole] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  
  // Modal de usuario
  const [userModalOpen, setUserModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    cedula: '',
    email: '',
    phone: '',
    cargo: '',
    departamento: '',
    sede: 'PYME',
    role: 'user',
    password: ''
  });
  const [saving, setSaving] = useState(false);

  // Modal de reset password
  const [resetModalOpen, setResetModalOpen] = useState(false);
  const [resetUser, setResetUser] = useState(null);
  const [resetResult, setResetResult] = useState(null);

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const response = await api.get('/admin/users');
      setUsers(response.data);
    } catch (error) {
      console.error('Error fetching users:', error);
      if (error.response?.status === 403) {
        toast.error('No tiene permisos para ver usuarios');
      } else {
        toast.error('Error al cargar usuarios');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleOpenCreateModal = () => {
    setEditingUser(null);
    setFormData({
      first_name: '',
      last_name: '',
      cedula: '',
      email: '',
      phone: '',
      cargo: '',
      departamento: '',
      sede: 'PYME',
      role: 'user',
      password: ''
    });
    setUserModalOpen(true);
  };

  const handleOpenEditModal = (user) => {
    setEditingUser(user);
    setFormData({
      first_name: user.first_name || '',
      last_name: user.last_name || '',
      cedula: user.cedula || '',
      email: user.email || '',
      phone: user.phone || '',
      cargo: user.cargo || '',
      departamento: user.departamento || '',
      sede: user.sede || 'PYME',
      role: user.role || 'user',
      password: ''
    });
    setUserModalOpen(true);
  };

  const handleSaveUser = async () => {
    // Validaciones
    if (!formData.first_name || !formData.last_name) {
      toast.error('Nombre y apellido son requeridos');
      return;
    }
    if (!formData.cedula) {
      toast.error('Cédula es requerida');
      return;
    }
    if (!formData.email) {
      toast.error('Correo electrónico es requerido');
      return;
    }
    if (!editingUser && !formData.password) {
      toast.error('Contraseña es requerida para nuevos usuarios');
      return;
    }
    if (!editingUser && formData.password.length < 8) {
      toast.error('La contraseña debe tener al menos 8 caracteres');
      return;
    }

    setSaving(true);
    try {
      if (editingUser) {
        // Actualizar usuario existente
        const updateData = {
          first_name: formData.first_name,
          last_name: formData.last_name,
          cedula: formData.cedula,
          phone: formData.phone,
          cargo: formData.cargo,
          departamento: formData.departamento,
          sede: formData.sede,
          role: formData.role
        };
        await api.put(`/admin/users/${editingUser.user_id}`, updateData);
        toast.success('Usuario actualizado exitosamente');
      } else {
        // Crear nuevo usuario
        await api.post('/admin/users/create', formData);
        toast.success('Usuario creado exitosamente');
      }
      setUserModalOpen(false);
      fetchUsers();
    } catch (error) {
      console.error('Error saving user:', error);
      toast.error(error.response?.data?.detail || 'Error al guardar usuario');
    } finally {
      setSaving(false);
    }
  };

  const handleToggleStatus = async (user) => {
    const newStatus = !user.is_active;
    const action = newStatus ? 'activar' : 'inactivar';
    
    if (!confirm(`¿Está seguro de ${action} al usuario ${user.first_name} ${user.last_name}?`)) {
      return;
    }

    try {
      await api.put(`/admin/users/${user.user_id}/status?is_active=${newStatus}`);
      toast.success(`Usuario ${newStatus ? 'activado' : 'inactivado'} exitosamente`);
      fetchUsers();
    } catch (error) {
      console.error('Error toggling status:', error);
      toast.error(error.response?.data?.detail || 'Error al cambiar estado');
    }
  };

  const handleResetPassword = async (user) => {
    setResetUser(user);
    setResetResult(null);
    setResetModalOpen(true);
  };

  const confirmResetPassword = async () => {
    try {
      const response = await api.post(`/admin/users/${resetUser.user_id}/reset-password`);
      setResetResult(response.data);
      toast.success('Token de restablecimiento generado');
    } catch (error) {
      console.error('Error resetting password:', error);
      toast.error(error.response?.data?.detail || 'Error al restablecer contraseña');
    }
  };

  // Filtrar usuarios
  const filteredUsers = users.filter(user => {
    const matchSearch = 
      (user.first_name?.toLowerCase() || '').includes(searchTerm.toLowerCase()) ||
      (user.last_name?.toLowerCase() || '').includes(searchTerm.toLowerCase()) ||
      (user.email?.toLowerCase() || '').includes(searchTerm.toLowerCase()) ||
      (user.cedula || '').includes(searchTerm) ||
      (user.cargo?.toLowerCase() || '').includes(searchTerm.toLowerCase());
    
    const matchSede = filterSede === 'all' || user.sede === filterSede;
    const matchRole = filterRole === 'all' || user.role === filterRole;
    const matchStatus = filterStatus === 'all' || 
      (filterStatus === 'active' && user.is_active) ||
      (filterStatus === 'inactive' && !user.is_active);
    
    return matchSearch && matchSede && matchRole && matchStatus;
  });

  const getSedeConfig = (sedeId) => SEDES.find(s => s.id === sedeId) || SEDES[0];
  const getRoleConfig = (roleId) => ROLES.find(r => r.id === roleId) || ROLES[1];

  if (loading) {
    return (
      <div className="flex h-screen">
        <Sidebar />
        <main className="flex-1 p-8 bg-slate-50 overflow-auto">
          <div className="flex items-center justify-center h-full">
            <div className="animate-spin h-8 w-8 border-4 border-brand-blue-600 border-t-transparent rounded-full"></div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 p-8 bg-slate-50 overflow-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
              <Users size={28} />
              Gestión de Usuarios
            </h1>
            <p className="text-slate-600 mt-1">Administración de cuentas y perfiles de colaboradores</p>
          </div>
          <Button 
            onClick={handleOpenCreateModal}
            className="bg-brand-green-600 hover:bg-brand-green-700"
            data-testid="create-user-btn"
          >
            <Plus size={18} className="mr-2" />
            Nuevo Usuario
          </Button>
        </div>

        {/* Filtros y Búsqueda */}
        <div className="bg-white rounded-lg border border-slate-200 p-4 mb-6">
          <div className="flex flex-wrap gap-4 items-center">
            {/* Búsqueda */}
            <div className="flex-1 min-w-[250px]">
              <div className="relative">
                <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  placeholder="Buscar por nombre, email, cédula o cargo..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                  data-testid="search-users"
                />
              </div>
            </div>

            {/* Filtro Sede */}
            <div className="flex items-center gap-2">
              <MapPin size={16} className="text-slate-500" />
              <select
                value={filterSede}
                onChange={(e) => setFilterSede(e.target.value)}
                className="border border-slate-200 rounded-md px-3 py-2 text-sm"
                data-testid="filter-sede"
              >
                <option value="all">Todas las Sedes</option>
                {SEDES.map(sede => (
                  <option key={sede.id} value={sede.id}>{sede.name}</option>
                ))}
              </select>
            </div>

            {/* Filtro Perfil */}
            <div className="flex items-center gap-2">
              <Shield size={16} className="text-slate-500" />
              <select
                value={filterRole}
                onChange={(e) => setFilterRole(e.target.value)}
                className="border border-slate-200 rounded-md px-3 py-2 text-sm"
                data-testid="filter-role"
              >
                <option value="all">Todos los Perfiles</option>
                {ROLES.map(role => (
                  <option key={role.id} value={role.id}>{role.name}</option>
                ))}
              </select>
            </div>

            {/* Filtro Estado */}
            <div className="flex items-center gap-2">
              <Filter size={16} className="text-slate-500" />
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="border border-slate-200 rounded-md px-3 py-2 text-sm"
                data-testid="filter-status"
              >
                <option value="all">Todos los Estados</option>
                <option value="active">Activos</option>
                <option value="inactive">Inactivos</option>
              </select>
            </div>

            {/* Refresh */}
            <Button variant="outline" size="sm" onClick={fetchUsers}>
              <RefreshCw size={16} />
            </Button>
          </div>
        </div>

        {/* Tabla de Usuarios */}
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full" data-testid="users-table">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="text-left px-4 py-3 text-sm font-semibold text-slate-700">Nombre y Cargo</th>
                  <th className="text-left px-4 py-3 text-sm font-semibold text-slate-700">Contacto</th>
                  <th className="text-center px-4 py-3 text-sm font-semibold text-slate-700">Sede</th>
                  <th className="text-center px-4 py-3 text-sm font-semibold text-slate-700">Perfil</th>
                  <th className="text-center px-4 py-3 text-sm font-semibold text-slate-700">Estatus</th>
                  <th className="text-center px-4 py-3 text-sm font-semibold text-slate-700">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.length === 0 ? (
                  <tr>
                    <td colSpan="6" className="text-center py-8 text-slate-500">
                      No se encontraron usuarios
                    </td>
                  </tr>
                ) : (
                  filteredUsers.map((user) => {
                    const sedeConfig = getSedeConfig(user.sede);
                    const roleConfig = getRoleConfig(user.role);
                    const RoleIcon = roleConfig.icon;

                    return (
                      <tr 
                        key={user.user_id} 
                        className="border-b border-slate-100 hover:bg-slate-50"
                        data-testid={`user-row-${user.user_id}`}
                      >
                        {/* Nombre y Cargo */}
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 font-semibold">
                              {user.first_name?.[0]}{user.last_name?.[0]}
                            </div>
                            <div>
                              <p className="font-medium text-slate-900">
                                {user.first_name} {user.last_name}
                              </p>
                              <p className="text-sm text-slate-500">
                                {user.cargo || 'Sin cargo'} 
                                {user.departamento && ` • ${user.departamento}`}
                              </p>
                            </div>
                          </div>
                        </td>

                        {/* Contacto */}
                        <td className="px-4 py-3">
                          <div className="text-sm">
                            <p className="flex items-center gap-1 text-slate-700">
                              <Mail size={14} className="text-slate-400" />
                              {user.email}
                            </p>
                            {user.phone && (
                              <p className="flex items-center gap-1 text-slate-500 mt-1">
                                <Phone size={14} className="text-slate-400" />
                                {user.phone}
                              </p>
                            )}
                            <p className="flex items-center gap-1 text-slate-500 mt-1">
                              <CreditCard size={14} className="text-slate-400" />
                              {user.cedula}
                            </p>
                          </div>
                        </td>

                        {/* Sede */}
                        <td className="px-4 py-3 text-center">
                          <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border ${sedeConfig.color}`}>
                            <MapPin size={12} />
                            {sedeConfig.id}
                          </span>
                        </td>

                        {/* Perfil */}
                        <td className="px-4 py-3 text-center">
                          <div className="flex flex-col items-center">
                            <RoleIcon size={18} className={roleConfig.color} />
                            <span className="text-xs text-slate-600 mt-1">{roleConfig.name}</span>
                          </div>
                        </td>

                        {/* Estatus */}
                        <td className="px-4 py-3 text-center">
                          <button
                            onClick={() => handleToggleStatus(user)}
                            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                              user.is_active
                                ? 'bg-green-100 text-green-700 hover:bg-green-200'
                                : 'bg-red-100 text-red-700 hover:bg-red-200'
                            }`}
                            data-testid={`toggle-status-${user.user_id}`}
                          >
                            {user.is_active ? (
                              <>
                                <UserCheck size={14} />
                                Activo
                              </>
                            ) : (
                              <>
                                <UserX size={14} />
                                Inactivo
                              </>
                            )}
                          </button>
                        </td>

                        {/* Acciones */}
                        <td className="px-4 py-3 text-center">
                          <div className="flex items-center justify-center gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleOpenEditModal(user)}
                              data-testid={`edit-user-${user.user_id}`}
                            >
                              <Edit size={14} />
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleResetPassword(user)}
                              className="text-amber-600 border-amber-300 hover:bg-amber-50"
                              data-testid={`reset-password-${user.user_id}`}
                            >
                              <Key size={14} />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Footer con conteo */}
          <div className="px-4 py-3 bg-slate-50 border-t border-slate-200 text-sm text-slate-600">
            Mostrando {filteredUsers.length} de {users.length} usuarios
          </div>
        </div>

        {/* Modal de Usuario */}
        <Dialog open={userModalOpen} onOpenChange={setUserModalOpen}>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                {editingUser ? <Edit size={20} /> : <Plus size={20} />}
                {editingUser ? 'Editar Usuario' : 'Nuevo Usuario'}
              </DialogTitle>
            </DialogHeader>

            <div className="grid grid-cols-2 gap-4 py-4">
              {/* Nombre */}
              <div className="space-y-2">
                <Label htmlFor="first_name" className="flex items-center gap-1">
                  Nombre <span className="text-red-500">*</span>
                </Label>
                <Input
                  id="first_name"
                  value={formData.first_name}
                  onChange={(e) => setFormData({...formData, first_name: e.target.value})}
                  placeholder="Nombre"
                  data-testid="input-first-name"
                />
              </div>

              {/* Apellido */}
              <div className="space-y-2">
                <Label htmlFor="last_name" className="flex items-center gap-1">
                  Apellido <span className="text-red-500">*</span>
                </Label>
                <Input
                  id="last_name"
                  value={formData.last_name}
                  onChange={(e) => setFormData({...formData, last_name: e.target.value})}
                  placeholder="Apellido"
                  data-testid="input-last-name"
                />
              </div>

              {/* Cédula */}
              <div className="space-y-2">
                <Label htmlFor="cedula" className="flex items-center gap-1">
                  <CreditCard size={14} />
                  Cédula <span className="text-red-500">*</span>
                </Label>
                <Input
                  id="cedula"
                  value={formData.cedula}
                  onChange={(e) => setFormData({...formData, cedula: e.target.value})}
                  placeholder="V-12345678"
                  data-testid="input-cedula"
                />
              </div>

              {/* Teléfono */}
              <div className="space-y-2">
                <Label htmlFor="phone" className="flex items-center gap-1">
                  <Phone size={14} />
                  Teléfono
                </Label>
                <Input
                  id="phone"
                  value={formData.phone}
                  onChange={(e) => setFormData({...formData, phone: e.target.value})}
                  placeholder="+58 412 1234567"
                  data-testid="input-phone"
                />
              </div>

              {/* Email */}
              <div className="space-y-2 col-span-2">
                <Label htmlFor="email" className="flex items-center gap-1">
                  <Mail size={14} />
                  Correo Electrónico <span className="text-red-500">*</span>
                </Label>
                <Input
                  id="email"
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({...formData, email: e.target.value})}
                  placeholder="usuario@empresa.com"
                  disabled={!!editingUser}
                  data-testid="input-email"
                />
                {editingUser && (
                  <p className="text-xs text-slate-500">El correo no se puede modificar</p>
                )}
              </div>

              {/* Cargo */}
              <div className="space-y-2">
                <Label htmlFor="cargo" className="flex items-center gap-1">
                  <Briefcase size={14} />
                  Cargo
                </Label>
                <select
                  id="cargo"
                  value={formData.cargo}
                  onChange={(e) => setFormData({...formData, cargo: e.target.value})}
                  className="w-full border border-slate-200 rounded-md px-3 py-2"
                  data-testid="input-cargo"
                >
                  <option value="">Seleccionar...</option>
                  {CARGOS.map(cargo => (
                    <option key={cargo} value={cargo}>{cargo}</option>
                  ))}
                </select>
              </div>

              {/* Departamento */}
              <div className="space-y-2">
                <Label htmlFor="departamento" className="flex items-center gap-1">
                  <Building2 size={14} />
                  Departamento
                </Label>
                <select
                  id="departamento"
                  value={formData.departamento}
                  onChange={(e) => setFormData({...formData, departamento: e.target.value})}
                  className="w-full border border-slate-200 rounded-md px-3 py-2"
                  data-testid="select-departamento"
                >
                  <option value="">Seleccionar...</option>
                  {DEPARTAMENTOS.map(dep => (
                    <option key={dep} value={dep}>{dep}</option>
                  ))}
                </select>
              </div>

              {/* Sede */}
              <div className="space-y-2">
                <Label htmlFor="sede" className="flex items-center gap-1">
                  <MapPin size={14} />
                  Sede <span className="text-red-500">*</span>
                </Label>
                <select
                  id="sede"
                  value={formData.sede}
                  onChange={(e) => setFormData({...formData, sede: e.target.value})}
                  className="w-full border border-slate-200 rounded-md px-3 py-2"
                  data-testid="select-sede"
                >
                  {SEDES.map(sede => (
                    <option key={sede.id} value={sede.id}>{sede.name} ({sede.id})</option>
                  ))}
                </select>
              </div>

              {/* Perfil */}
              <div className="space-y-2">
                <Label htmlFor="role" className="flex items-center gap-1">
                  <Shield size={14} />
                  Perfil <span className="text-red-500">*</span>
                </Label>
                <select
                  id="role"
                  value={formData.role}
                  onChange={(e) => setFormData({...formData, role: e.target.value})}
                  className="w-full border border-slate-200 rounded-md px-3 py-2"
                  data-testid="select-role"
                >
                  {ROLES.map(role => (
                    <option key={role.id} value={role.id}>{role.name} - {role.description}</option>
                  ))}
                </select>
              </div>

              {/* Contraseña (solo para nuevos) */}
              {!editingUser && (
                <div className="space-y-2 col-span-2">
                  <Label htmlFor="password" className="flex items-center gap-1">
                    <Key size={14} />
                    Contraseña <span className="text-red-500">*</span>
                  </Label>
                  <Input
                    id="password"
                    type="password"
                    value={formData.password}
                    onChange={(e) => setFormData({...formData, password: e.target.value})}
                    placeholder="Mínimo 8 caracteres"
                    data-testid="input-password"
                  />
                </div>
              )}
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setUserModalOpen(false)}>
                Cancelar
              </Button>
              <Button 
                onClick={handleSaveUser} 
                disabled={saving}
                className="bg-brand-green-600 hover:bg-brand-green-700"
                data-testid="save-user-btn"
              >
                {saving ? 'Guardando...' : (editingUser ? 'Actualizar' : 'Crear Usuario')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Modal de Reset Password */}
        <Dialog open={resetModalOpen} onOpenChange={setResetModalOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Key size={20} className="text-amber-600" />
                Restablecer Contraseña
              </DialogTitle>
            </DialogHeader>

            {resetUser && !resetResult && (
              <div className="py-4">
                <p className="text-slate-600 mb-4">
                  Se generará un token de seguridad de un solo uso para el usuario:
                </p>
                <div className="bg-slate-50 p-4 rounded-lg">
                  <p className="font-medium">{resetUser.first_name} {resetUser.last_name}</p>
                  <p className="text-sm text-slate-500">{resetUser.email}</p>
                </div>
                <p className="text-sm text-amber-600 mt-4">
                  El token será enviado al correo electrónico del usuario.
                </p>
              </div>
            )}

            {resetResult && (
              <div className="py-4">
                <div className="bg-green-50 border border-green-200 p-4 rounded-lg">
                  <p className="text-green-700 font-medium mb-2">Token generado exitosamente</p>
                  <p className="text-sm text-slate-600">Email: {resetResult.email}</p>
                  <p className="text-sm text-slate-600">Expira: {new Date(resetResult.expires_at).toLocaleString()}</p>
                  <div className="mt-3 p-2 bg-white rounded border">
                    <p className="text-xs text-slate-500">Token (solo para pruebas):</p>
                    <code className="text-xs break-all">{resetResult.reset_token}</code>
                  </div>
                </div>
              </div>
            )}

            <DialogFooter>
              <Button variant="outline" onClick={() => setResetModalOpen(false)}>
                {resetResult ? 'Cerrar' : 'Cancelar'}
              </Button>
              {!resetResult && (
                <Button 
                  onClick={confirmResetPassword}
                  className="bg-amber-500 hover:bg-amber-600"
                >
                  Generar Token
                </Button>
              )}
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
};

export default UserManagement;
