import React from 'react';

/**
 * Boundary local para el Sidebar.
 * Si cualquier item del menú lanza una excepción durante el render
 * (p. ej. permiso desconocido, groupId inexistente, etc.), evitamos
 * que la app entera quede en blanco. Mostramos un fallback mínimo
 * con accesos seguros a Dashboard y Cerrar Sesión.
 */
class SidebarErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error('[Sidebar] render crash:', error, info);
  }

  handleLogout = () => {
    try {
      localStorage.removeItem('session_token');
      localStorage.removeItem('user');
    } catch {}
    window.location.href = '/login';
  };

  render() {
    if (this.state.hasError) {
      return (
        <aside
          data-testid="sidebar-fallback"
          className="w-64 bg-white border-r border-slate-200 h-screen flex flex-col sticky top-0 flex-shrink-0"
        >
          <div className="px-4 py-4 border-b border-slate-200">
            <h1 className="text-lg font-bold text-slate-900 font-manrope">Gestor</h1>
            <p className="text-xs text-amber-600 mt-0.5">Modo seguro: revisa permisos del usuario</p>
          </div>
          <nav className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
            <a
              href="/dashboard"
              data-testid="sidebar-fallback-dashboard"
              className="block px-4 py-2.5 rounded-lg text-slate-700 hover:bg-slate-100 text-sm font-medium"
            >
              Dashboard
            </a>
            <a
              href="/settings"
              data-testid="sidebar-fallback-settings"
              className="block px-4 py-2.5 rounded-lg text-slate-700 hover:bg-slate-100 text-sm font-medium"
            >
              Configuración
            </a>
          </nav>
          <button
            onClick={this.handleLogout}
            data-testid="sidebar-fallback-logout"
            className="m-3 px-4 py-2.5 rounded-lg text-slate-600 hover:text-red-600 hover:bg-red-50 text-sm font-medium text-left"
          >
            Cerrar Sesión
          </button>
        </aside>
      );
    }
    return this.props.children;
  }
}

export default SidebarErrorBoundary;
