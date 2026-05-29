import { toast } from 'sonner';
import api from './api';

/**
 * Saludo post-login: consulta el resumen de la bandeja interna y emite
 * un toast destacando los mensajes sin leer.
 *
 * Se ejecuta best-effort: si el endpoint falla, no interrumpe el flujo de
 * autenticación. Llamado por:
 *   - `Auth.jsx` (login email/password)
 *   - `AuthCallback.jsx` (Google OAuth callback)
 */
export async function showInboxWelcomeToast({ firstName } = {}) {
  try {
    const { data } = await api.get('/inbox/me/summary');
    const unread = data?.unread || 0;
    if (unread <= 0) return;
    const noun = unread === 1 ? 'mensaje nuevo' : 'mensajes nuevos';
    const greeting = firstName ? `Hola ${firstName}` : 'Bienvenido';
    toast.message(`${greeting} · Revisa tu Centro de Mensajes`, {
      description: `Tienes ${unread} ${noun} esperándote en el Dashboard.`,
      duration: 8000,
    });
  } catch {
    // Silencioso: el saludo es complementario, nunca debe romper el login.
  }
}
