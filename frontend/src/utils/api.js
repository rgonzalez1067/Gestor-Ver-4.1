import axios from 'axios';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export const api = axios.create({
  baseURL: `${BACKEND_URL}/api`,
  withCredentials: true
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('session_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Flag global para evitar mostrar el toast multiple veces cuando varias requests
// fallan simultáneamente con 401.
let sessionExpiredHandled = false;

/**
 * Maneja un error 401 limpiando el localStorage y redirigiendo a /login.
 * Es exportado para que también pueda invocarse desde llamadas `fetch` directas
 * (no axios) en componentes que descargan archivos / usan streams.
 */
export const handleSessionExpired = ({ silent = false } = {}) => {
  // Si ya estamos en login no hace falta nada
  const path = window.location.pathname || '';
  if (path.startsWith('/login') || path.startsWith('/reset-password') || path.startsWith('/verify-email')) {
    return;
  }
  if (sessionExpiredHandled) return;
  sessionExpiredHandled = true;

  try {
    localStorage.removeItem('session_token');
    localStorage.removeItem('user');
    // Limpieza defensiva de cualquier otra clave residual relacionada con la sesión
    Object.keys(localStorage).forEach((k) => {
      if (/token|session|auth|user/i.test(k)) {
        localStorage.removeItem(k);
      }
    });
  } catch {}

  if (!silent) {
    try {
      toast.error('Su sesión ha expirado. Por favor inicie sesión nuevamente.');
    } catch {}
  }

  // Pequeño delay para que el toast sea visible antes del redirect
  setTimeout(() => {
    window.location.href = '/login';
  }, 600);
};

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const url = error.config?.url || '';
    // No interferir con el flujo de login: errores 401 al intentar autenticar
    // deben mostrar mensaje normal en el formulario, no limpiar localStorage.
    const isAuthEndpoint = /\/auth\/(login|register|forgot|reset|verify)/i.test(url);
    if (status === 401 && !isAuthEndpoint) {
      handleSessionExpired();
    }
    return Promise.reject(error);
  }
);

export default api;