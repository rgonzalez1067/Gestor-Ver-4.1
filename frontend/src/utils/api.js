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

// ---------------------------------------------------------------------------
// Contador de peticiones CRÍTICAS en vuelo (generación de cotizaciones/PDFs).
// Si una petición concurrente recibe un 401 mientras una de estas está en
// curso, NO debemos redirigir (window.location.href) de inmediato porque eso
// aborta el XHR en vuelo (el navegador lo marca como "(failed)") aunque el
// backend SÍ complete la operación. Diferimos el redirect hasta que terminen.
// ---------------------------------------------------------------------------
let inFlightCritical = 0;
const CRITICAL_URL_RE = /(create-with-pdf|generate-equipment-pdf|generate-pdf|create-with-equipment-pdf)/i;
export const markCriticalStart = () => { inFlightCritical += 1; };
export const markCriticalEnd = () => { inFlightCritical = Math.max(0, inFlightCritical - 1); };

// Marca/Desmarca automáticamente peticiones axios críticas.
api.interceptors.request.use((config) => {
  if (CRITICAL_URL_RE.test(config.url || '')) {
    config.__critical = true;
    markCriticalStart();
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
  } catch { /* localStorage no disponible */ }

  if (!silent) {
    try {
      toast.error('Su sesión ha expirado. Por favor inicie sesión nuevamente.');
    } catch { /* toast no disponible */ }
  }

  // Pequeño delay para que el toast sea visible antes del redirect.
  // Si hay peticiones CRÍTICAS en vuelo (generación de cotización/PDF, ~2s),
  // esperamos a que terminen para NO abortarlas con la navegación.
  const maxWaitMs = 15000;
  const startedAt = Date.now();
  const redirectWhenIdle = () => {
    const elapsed = Date.now() - startedAt;
    if (inFlightCritical > 0 && elapsed < maxWaitMs) {
      setTimeout(redirectWhenIdle, 300);
      return;
    }
    window.location.href = '/login';
  };
  setTimeout(redirectWhenIdle, 600);
};

api.interceptors.response.use(
  (response) => {
    if (response.config && response.config.__critical) markCriticalEnd();
    return response;
  },
  (error) => {
    if (error.config && error.config.__critical) markCriticalEnd();
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