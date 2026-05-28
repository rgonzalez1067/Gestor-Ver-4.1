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
    const name = firstName ? `${firstName}, ` : '';
    const noun = unread === 1 ? 'mensaje sin leer' : 'mensajes sin leer';
    toast.message(`${name}tienes ${unread} ${noun}`, {
      description: 'Revisa tu Centro de Mensajes en el Dashboard.',
      duration: 7000,
    });
  } catch {
    // Silencioso: el saludo es complementario, nunca debe romper el login.
  }
}
