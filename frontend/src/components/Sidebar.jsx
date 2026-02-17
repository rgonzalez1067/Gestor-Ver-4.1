import { Link, useLocation } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Users, 
  Building2, 
  Package, 
  CreditCard, 
  FileText,
  TrendingUp,
  Settings,
  LogOut
} from 'lucide-react';
import api from '../utils/api';

const menuItems = [
  { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/clients', icon: Users, label: 'Clientes' },
  { path: '/banks', icon: Building2, label: 'Bancos' },
  { path: '/hardware', icon: Package, label: 'Dispositivos y Accesorios' },
  { path: '/medios-pago', icon: CreditCard, label: 'Medios de Pago' },
  { path: '/quotes', icon: FileText, label: 'Cotizaciones' },
  { path: '/exchange-rate', icon: TrendingUp, label: 'Tasa de Cambio' },
  { path: '/settings', icon: Settings, label: 'Configuración' }
];

export const Sidebar = () => {
  const location = useLocation();

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

  return (
    <aside className="w-64 bg-white border-r border-slate-200 min-h-screen flex flex-col">
      <div className="p-6 border-b border-slate-200">
        <h1 className="text-xl font-bold text-slate-900 font-manrope">Cotizador</h1>
        <p className="text-sm text-slate-500 mt-1">Merchant Server</p>
      </div>

      <nav className="flex-1 p-4">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;
          
          return (
            <Link
              key={item.path}
              to={item.path}
              data-testid={`nav-${item.label.toLowerCase()}`}
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

      <div className="p-4 border-t border-slate-200">
        <button
          onClick={handleLogout}
          data-testid="logout-button"
          className="sidebar-nav-item flex items-center gap-3 px-4 py-3 rounded-lg w-full text-slate-600 hover:text-red-600"
        >
          <LogOut size={20} />
          <span className="font-medium">Cerrar Sesión</span>
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;