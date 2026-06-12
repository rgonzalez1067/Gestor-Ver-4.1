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
  Archive,
  BarChart3,
  Landmark,
  PanelLeftClose,
  PanelLeftOpen,
  Pin,
  PinOff,
  Briefcase,
  Phone,
  Tag,
  Plus,
  ChevronDown,
  ChevronRight
} from 'lucide-react';
import { NotificationBell } from './NotificationBell';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';
import api from '../utils/api';
import { ROUTE_MODULE_MAP, isGroupActive } from '../hooks/usePermission';
import SidebarErrorBoundary from './SidebarErrorBoundary';

const menuItems = [
  { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard', groupId: 'dashboard' },
  {
    icon: Briefcase, label: 'Gestion Comercial', isGroup: true, groupId: 'gestion_comercial',
    children: [
      { path: '/initial-contacts', icon: Phone, label: 'Contacto Inicial' },
      { path: '/clients', icon: Users, label: 'Clientes' },
      { path: '/quotes', icon: FileText, label: 'Cotizaciones' },
      { path: '/reports/sales', icon: BarChart3, label: 'Reportes de Ventas' },
      { path: '/reports/sponsors', icon: Landmark, label: 'Reportes por Patrocinador' },
      { path: '/historical-quotes', icon: Archive, label: 'Histórico de Cotizaciones', requiresHistoryAccess: true },
    ]
  },
  {
    icon: Package, label: 'Catálogos', isGroup: true, groupId: 'catalogos',
    children: [
      { path: '/banks', icon: Building2, label: 'Bancos' },
      { path: '/medios-pago', icon: CreditCard, label: 'Medios de Pago' },
      { path: '/hardware', icon: Boxes, label: 'Bienes y Servicios' },
      { path: '/commercial-categories', icon: Tag, label: 'Categoría Comercial' },
      { path: '/exchange-rate', icon: TrendingUp, label: 'Tasa de Cambio' },
    ]
  },
  {
    icon: FolderKanban, label: 'Gestión de Implementación', isGroup: true, groupId: 'gestion_implementacion',
    children: [
      { path: '/projects', icon: FolderKanban, label: 'Proyectos' },
      { path: '/direct-projects', icon: Plus, label: 'Proyectos Directos' },
      { path: '/integrators', icon: UserCheck, label: 'Integradores' },
      { path: '/datos-imple', icon: Wrench, label: 'Datos de Imple' },
    ]
  },
  { path: '/new-products', icon: FlaskConical, label: 'Nuevos Productos', groupId: 'nuevos_productos' },
  {
    icon: Warehouse, label: 'Gestión Administrativa', isGroup: true, groupId: 'gestion_administrativa',
    children: [
      { path: '/inventory', icon: Warehouse, label: 'Inventarios' },
      {
        icon: FileText, label: 'Reportes Contables', isSubGroup: true,
        children: [
          { path: '/inventory/accounting-report', icon: FileText, label: 'Kardex de Activos' },
          { path: '/inventory/asset-ledger', icon: Package, label: 'Mayor de Activos' },
          { path: '/inventory/invoiced-exits', icon: FileText, label: 'Salidas Facturadas' },
        ]
      },
    ]
  },
  { path: '/taller-equipos', icon: Wrench, label: 'Gestión de Taller', groupId: 'gestion_taller' },
];

const securityItems = [
  {
    icon: Shield, label: 'Gestión de Seguridad', isGroup: true, adminOnly: true,
    children: [
      { path: '/users', icon: UsersRound, label: 'Creación de Usuarios' },
      { path: '/admin/users', icon: Shield, label: 'Permisos de Usuarios' },
      { path: '/admin/profiles', icon: Shield, label: 'Perfiles de Usuario' },
    ]
  },
];

const SidebarInner = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [isAdmin, setIsAdmin] = useState(false);
  const [canSeeHistory, setCanSeeHistory] = useState(false);
  const [userName, setUserName] = useState('');
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('sidebar_collapsed') === 'true');
  const [pinned, setPinned] = useState(() => localStorage.getItem('sidebar_pinned') === 'true');
  const [expandedGroups, setExpandedGroups] = useState(() => {
    // Auto-expand if current path is inside a group or nested sub-group
    const groups = {};
    const scan = (arr) => {
      arr.forEach(item => {
        if (item.isGroup || item.isSubGroup) {
          if (item.children?.some(c => location.pathname === c.path)) {
            groups[item.label] = true;
          }
          if (item.children) scan(item.children);
        }
      });
    };
    scan(menuItems);
    return groups;
  });

  useEffect(() => {
    const userStr = localStorage.getItem('user');
    if (userStr) {
      try {
        const user = JSON.parse(userStr);
        setIsAdmin(user.role === 'admin');
        setCanSeeHistory(user.role === 'admin' || (user.cargo || '').trim() === 'Director');
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

    const filterChild = (child) => {
      try {
        // Visibilidad de Histórico de Cotizaciones: debe basarse en el PERMISO de
        // la matriz de seguridad (módulo `quote_history`), no solo en el cargo.
        // Se mantiene el acceso legacy para admin/Director como respaldo aditivo.
        if (child.requiresHistoryAccess) {
          const histModule = ROUTE_MODULE_MAP[child.path]; // 'quote_history'
          const hasMatrixAccess = role === 'admin' || (permissions[histModule] || 'none') !== 'none';
          if (!(hasMatrixAccess || canSeeHistory)) return null;
          return child;
        }
        // Sub-grupo anidado (Reportes Contables)
        if (child.isSubGroup) {
          const kept = (child.children || []).map(filterChild).filter(Boolean);
          if (kept.length === 0) return null;
          return { ...child, children: kept };
        }
        const module = ROUTE_MODULE_MAP[child.path];
        if (!module) return child;
        if (role === 'admin') return child;
        return (permissions[module] || 'none') !== 'none' ? child : null;
      } catch (err) {
        console.error('[Sidebar] filterChild error:', err, child);
        return null; // Excluir el item defectuoso, no romper el menú
      }
    };

    let items = menuItems.map(item => {
      try {
        if (item.isGroup) {
          // Nivel 1: si el grupo está inactivo para el usuario, se elimina completo del menú.
          if (item.groupId && !isGroupActive(item.groupId)) return null;
          const filteredChildren = (item.children || []).map(filterChild).filter(Boolean);
          if (filteredChildren.length === 0) return null;
          return { ...item, children: filteredChildren };
        }
        // Standalone items (Dashboard, Nuevos Productos, Taller) — validar también groupId.
        if (item.groupId && !isGroupActive(item.groupId)) return null;
        const module = ROUTE_MODULE_MAP[item.path];
        if (!module) return item;
        if (role === 'admin') return item;
        const level = permissions[module] || 'none';
        return level !== 'none' ? item : null;
      } catch (err) {
        console.error('[Sidebar] menu item error:', err, item);
        return null;
      }
    }).filter(Boolean);

    // Añadir Gestión de Seguridad solo para admins
    if (isAdmin) {
      items = [...items, ...securityItems];
    }
    return items;
  }, [isAdmin, canSeeHistory]);

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

  // Recursive renderer for groups (level 0) and sub-groups (level 1+)
  const renderMenuItem = (item, depth) => {
    if (item.isGroup || item.isSubGroup) {
      const isGroupActive = item.children?.some(c => location.pathname === c.path);
      // Si el usuario tocó el grupo (true/false explícito), respeta su elección.
      // Si nunca lo tocó (undefined), usa la ruta activa como default.
      const explicit = expandedGroups[item.label];
      const isExpanded = explicit !== undefined ? explicit : isGroupActive;
      const GroupIcon = item.icon;
      return (
        <div key={item.label}>
          <button
            onClick={() => setExpandedGroups(prev => ({ ...prev, [item.label]: !isExpanded }))}
            data-testid={`nav-group-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
            className={`w-full sidebar-nav-item flex items-center gap-3 rounded-lg mb-0.5 transition-all duration-200 ${
              collapsed ? 'px-0 py-2.5 justify-center' : depth > 0 ? 'px-3 py-2' : 'px-4 py-2.5'
            } ${isGroupActive ? 'text-brand-blue-700 bg-brand-blue-50' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'}`}
          >
            <GroupIcon size={depth > 0 ? 16 : 20} className="flex-shrink-0" />
            {!collapsed && (
              <>
                <span className={`font-medium whitespace-nowrap overflow-hidden flex-1 text-left ${depth > 0 ? 'text-xs' : 'text-sm'}`}>{item.label}</span>
                {isExpanded ? <ChevronDown size={14} className="text-slate-400" /> : <ChevronRight size={14} className="text-slate-400" />}
              </>
            )}
          </button>
          {isExpanded && !collapsed && (
            <div className={`ml-${depth > 0 ? '3' : '4'} border-l-2 border-slate-200 pl-2 mb-1`}>
              {item.children.map(child => renderMenuItem(child, depth + 1))}
            </div>
          )}
          {collapsed && isExpanded && item.children.map(child => renderMenuItem(child, depth + 1))}
        </div>
      );
    }
    return <NavItem key={item.path} item={item} isActive={location.pathname === item.path} />;
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
          {allMenuItems.map((item) => renderMenuItem(item, 0))}
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

          {/* User info + Notification bell - only when expanded */}
          {!collapsed && userName && (
            <div className="mx-3 my-1.5 px-3 py-1.5 bg-slate-50 rounded-lg flex items-center justify-between gap-2">
              <div className="min-w-0 flex-1">
                <p className="text-[10px] text-slate-400">Sesión activa:</p>
                <p className="text-xs font-medium text-slate-700 flex items-center gap-1.5 truncate">
                  {userName}
                  {isAdmin && (
                    <span className="inline-flex items-center px-1 py-0 rounded text-[10px] font-medium bg-amber-100 text-amber-700">
                      Admin
                    </span>
                  )}
                </p>
              </div>
              <NotificationBell />
            </div>
          )}

          {/* Collapsed: only bell icon */}
          {collapsed && (
            <div className="flex justify-center my-1.5">
              <NotificationBell />
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

export const Sidebar = (props) => (
  <SidebarErrorBoundary>
    <SidebarInner {...props} />
  </SidebarErrorBoundary>
);

export default Sidebar;
