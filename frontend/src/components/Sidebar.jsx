import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useState, useEffect, useMemo } from 'react';
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
  Boxes,
  UsersRound,
  FlaskConical,
  Warehouse,
  Wrench,
  FolderKanban,
  PanelLeftClose,
  PanelLeftOpen,
  Pin,
  PinOff
} from 'lucide-react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';
import api from '../utils/api';
import { ROUTE_MODULE_MAP } from '../hooks/usePermission';

const menuItems = [
  { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/clients', icon: Users, label: 'Clientes' },
  { path: '/banks', icon: Building2, label: 'Bancos' },
  { path: '/hardware', icon: Boxes, label: 'Bienes y Servicios' },
  { path: '/medios-pago', icon: CreditCard, label: 'Medios de Pago' },
  { path: '/integrators', icon: UserCheck, label: 'Integradores' },
  { path: '/quotes', icon: FileText, label: 'Cotizaciones' },
  { path: '/projects', icon: FolderKanban, label: 'Proyectos' },
  { path: '/new-products', icon: FlaskConical, label: 'Nuevos Productos' },
  { path: '/inventory', icon: Warehouse, label: 'Inventarios' },
  { path: '/taller-equipos', icon: Wrench, label: 'Equipos en Reparacion' },
  { path: '/exchange-rate', icon: TrendingUp, label: 'Tasa de Cambio' }
];

const adminItems = [
  { path: '/users', icon: UsersRound, label: 'Gestión de Usuarios Pro' },
  { path: '/admin/users', icon: Shield, label: 'Permisos de Usuarios' }
];

export const Sidebar = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [isAdmin, setIsAdmin] = useState(false);
  const [userName, setUserName] = useState('');
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('sidebar_collapsed') === 'true');
  const [pinned, setPinned] = useState(() => localStorage.getItem('sidebar_pinned') === 'true');

  useEffect(() => {
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

  const persist = (key, val) => localStorage.setItem(key, String(val));

  const handleNavClick = (e, path) => {
    e.preventDefault();
    navigate(path);
    if (!pinned) {
      setCollapsed(true);
      persist('sidebar_collapsed', true);
    }
  };

  const togglePin = () => {
    const next = !pinned;
    setPinned(next);
    persist('sidebar_pinned', next);
    if (next) {
      setCollapsed(false);
      persist('sidebar_collapsed', false);
    }
  };

  const toggleCollapse = () => {
    const next = !collapsed;
    setCollapsed(next);
    persist('sidebar_collapsed', next);
  };

  const handleLogout = async () => {
    try {
      await api.post('/auth/logout');
      localStorage.removeItem('session_token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    } catch (error) {
      localStorage.clear();
      window.location.href = '/login';
    }
  };

  // Filtrar menú por permisos RBAC: "Ninguno" → remover del DOM
  const allMenuItems = useMemo(() => {
    const userStr = localStorage.getItem('user');
    let user = null;
    try { user = userStr ? JSON.parse(userStr) : null; } catch { user = null; }
    const permissions = user?.permissions || {};
    const role = user?.role;

    let items = menuItems.filter(item => {
      const module = ROUTE_MODULE_MAP[item.path];
      if (!module) return true; // Dashboard, exchange-rate sin módulo → siempre visible
      if (role === 'admin') return true;
      const level = permissions[module] || 'none';
      return level !== 'none'; // Solo mostrar si tiene "read" o "edit"
    });

    if (isAdmin) items = [...items, ...adminItems];
    return items;
  }, [isAdmin]);

  const w = collapsed ? 'w-[60px]' : 'w-64';

  const NavItem = ({ item, isActive, isFooter }) => {
    const Icon = item.icon;
    const inner = (
      <Link
        to={item.path}
        onClick={(e) => handleNavClick(e, item.path)}
        data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
        className={`sidebar-nav-item flex items-center gap-3 rounded-lg mb-0.5 transition-all duration-200 ${
          collapsed ? 'px-0 py-2.5 justify-center' : 'px-4 py-2.5'
        } ${isActive
          ? 'active'
          : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
        }`}
      >
        <Icon size={20} className="flex-shrink-0" />
        {!collapsed && <span className="font-medium text-sm whitespace-nowrap overflow-hidden">{item.label}</span>}
      </Link>
    );

    if (collapsed) {
      return (
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>{inner}</TooltipTrigger>
          <TooltipContent side="right" sideOffset={8}>
            <p className="text-sm font-medium">{item.label}</p>
          </TooltipContent>
        </Tooltip>
      );
    }
    return inner;
  };

  return (
    <TooltipProvider>
      <aside
        className={`${w} bg-white border-r border-slate-200 h-screen flex flex-col sticky top-0 transition-all duration-300 ease-in-out overflow-hidden flex-shrink-0`}
        data-testid="sidebar"
      >
        {/* Header */}
        <div className={`border-b border-slate-200 flex-shrink-0 flex items-center ${collapsed ? 'px-2 py-4 justify-center' : 'px-4 py-4 justify-between'}`}>
          {!collapsed && (
            <div className="min-w-0">
              <h1 className="text-lg font-bold text-slate-900 font-manrope leading-tight">Gestor</h1>
              <p className="text-xs text-slate-400 mt-0.5">Work Flow de Procesos Integrales</p>
            </div>
          )}
          <div className={`flex items-center ${collapsed ? 'gap-0' : 'gap-1'}`}>
            {!collapsed && (
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <button
                    onClick={togglePin}
                    data-testid="sidebar-pin-btn"
                    className={`p-1.5 rounded-md transition-colors ${
                      pinned ? 'text-sky-600 bg-sky-50 hover:bg-sky-100' : 'text-slate-400 hover:text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    {pinned ? <Pin size={15} /> : <PinOff size={15} />}
                  </button>
                </TooltipTrigger>
                <TooltipContent side="right" sideOffset={4}>
                  <p className="text-xs">{pinned ? 'Desfijar menú' : 'Fijar menú abierto'}</p>
                </TooltipContent>
              </Tooltip>
            )}
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <button
                  onClick={toggleCollapse}
                  data-testid="sidebar-toggle-btn"
                  className="p-1.5 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
                >
                  {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
                </button>
              </TooltipTrigger>
              <TooltipContent side="right" sideOffset={4}>
                <p className="text-xs">{collapsed ? 'Expandir menú' : 'Contraer menú'}</p>
              </TooltipContent>
            </Tooltip>
          </div>
        </div>

        {/* Navigation */}
        <nav className={`flex-1 overflow-y-auto ${collapsed ? 'px-1.5 py-2' : 'px-3 py-2'}`}>
          {allMenuItems.map((item) => (
            <NavItem key={item.path} item={item} isActive={location.pathname === item.path} />
          ))}
        </nav>

        {/* Footer */}
        <div className="flex-shrink-0 border-t border-slate-200">
          <div className={collapsed ? 'px-1.5 pt-2' : 'px-3 pt-2'}>
            <NavItem
              item={{ path: '/settings', icon: Settings, label: 'Configuración' }}
              isActive={location.pathname === '/settings'}
              isFooter
            />
          </div>

          {/* User info - only when expanded */}
          {!collapsed && userName && (
            <div className="mx-3 my-1.5 px-3 py-1.5 bg-slate-50 rounded-lg">
              <p className="text-[10px] text-slate-400">Sesión activa:</p>
              <p className="text-xs font-medium text-slate-700 flex items-center gap-1.5">
                {userName}
                {isAdmin && (
                  <span className="inline-flex items-center px-1 py-0 rounded text-[10px] font-medium bg-amber-100 text-amber-700">
                    Admin
                  </span>
                )}
              </p>
            </div>
          )}

          {/* Logout */}
          {collapsed ? (
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <button
                  onClick={handleLogout}
                  data-testid="logout-button"
                  className="flex items-center justify-center w-full py-2.5 mb-2 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                >
                  <LogOut size={20} />
                </button>
              </TooltipTrigger>
              <TooltipContent side="right" sideOffset={8}>
                <p className="text-sm font-medium">Cerrar Sesión</p>
              </TooltipContent>
            </Tooltip>
          ) : (
            <button
              onClick={handleLogout}
              data-testid="logout-button"
              className="sidebar-nav-item flex items-center gap-3 px-4 py-2.5 mx-3 mb-3 rounded-lg w-[calc(100%-1.5rem)] text-slate-600 hover:text-red-600 hover:bg-red-50 transition-colors"
            >
              <LogOut size={20} className="flex-shrink-0" />
              <span className="font-medium text-sm">Cerrar Sesión</span>
            </button>
          )}
        </div>
      </aside>
    </TooltipProvider>
  );
};

export default Sidebar;
