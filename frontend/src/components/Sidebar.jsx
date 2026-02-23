import { Link, useLocation } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { 
  LayoutDashboard, 
  Users, 
  Building2, 
  Package, 
  CreditCard, 
  FileText,
  TrendingUp,
  Settings,
  LogOut,
  UserCheck,
  Shield,
  Boxes
} from 'lucide-react';
import api from '../utils/api';

const menuItems = [
  { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/clients', icon: Users, label: 'Clientes' },
  { path: '/banks', icon: Building2, label: 'Bancos' },
  { path: '/hardware', icon: Boxes, label: 'Bienes y Servicios' },
  { path: '/medios-pago', icon: CreditCard, label: 'Medios de Pago' },
  { path: '/integrators', icon: UserCheck, label: 'Integradores' },
  { path: '/quotes', icon: FileText, label: 'Cotizaciones' },
  { path: '/exchange-rate', icon: TrendingUp, label: 'Tasa de Cambio' }
];

// Items solo para admin
const adminItems = [
  { path: '/admin/users', icon: Shield, label: 'Gestión de Usuarios' }
];

export const Sidebar = () => {
  const location = useLocation();
  const [isAdmin, setIsAdmin] = useState(false);
  const [userName, setUserName] = useState('');
  
  useEffect(() => {
    // Verificar si el usuario es admin
    const userStr = localStorage.getItem('user');
    if (userStr) {
      try {
        const user = JSON.parse(userStr);
        setIsAdmin(user.role === 'admin');
        setUserName(user.first_name || user.name?.split(' ')[0] || user.email?.split('@')[0] || '');
      } catch (e) {
        console.error('Error parsing user data:', e);
      }
    }
  }, []);

  const handleLogout = async () => {
    try {
      await api.post('/auth/logout');
      localStorage.removeItem('session_token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    } catch (error) {
      console.error('Logout failed:', error);
      localStorage.clear();
      window.location.href = '/login';
    }
  };
  
  const allMenuItems = isAdmin ? [...menuItems, ...adminItems] : menuItems;

  return (
    <aside className="w-64 bg-white border-r border-slate-200 h-screen flex flex-col sticky top-0">
      {/* Header - Fixed */}
      <div className="p-6 border-b border-slate-200 flex-shrink-0">
        <h1 className="text-xl font-bold text-slate-900 font-manrope">Cotizador</h1>
        <p className="text-sm text-slate-500 mt-1">Merchant Server</p>
      </div>

      {/* Navigation - Scrollable */}
      <nav className="flex-1 p-4 overflow-y-auto">
        {allMenuItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;
          
          return (
            <Link
              key={item.path}
              to={item.path}
              data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
              className={`sidebar-nav-item flex items-center gap-3 px-4 py-3 rounded-lg mb-1 ${
                isActive ? 'active' : 'text-slate-600'
              }`}
            >
              <Icon size={20} />
              <span className="font-medium">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Footer - Fixed at bottom */}
      <div className="flex-shrink-0 border-t border-slate-200">
        {/* Settings Link */}
        <Link
          to="/settings"
          data-testid="nav-configuración"
          className={`sidebar-nav-item flex items-center gap-3 px-4 py-3 mx-4 mt-2 rounded-lg ${
            location.pathname === '/settings' ? 'active' : 'text-slate-600'
          }`}
        >
          <Settings size={20} />
          <span className="font-medium">Configuración</span>
        </Link>
        
        {/* User Info */}
        {userName && (
          <div className="mx-4 my-2 px-4 py-2 bg-slate-50 rounded-lg">
            <p className="text-xs text-slate-500">Sesión activa:</p>
            <p className="text-sm font-medium text-slate-700 flex items-center gap-2">
              {userName}
              {isAdmin && (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-700">
                  Admin
                </span>
              )}
            </p>
          </div>
        )}
        
        {/* Logout Button */}
        <button
          onClick={handleLogout}
          data-testid="logout-button"
          className="sidebar-nav-item flex items-center gap-3 px-4 py-3 mx-4 mb-4 rounded-lg w-[calc(100%-2rem)] text-slate-600 hover:text-red-600 hover:bg-red-50"
        >
          <LogOut size={20} />
          <span className="font-medium">Cerrar Sesión</span>
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;