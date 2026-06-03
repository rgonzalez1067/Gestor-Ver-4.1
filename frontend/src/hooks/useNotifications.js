import { useEffect, useRef, useState, useCallback } from 'react';
import api from '../utils/api';
import { emitInboxChanged, emitInboxReloadList } from '../utils/inboxEvents';

/**
 * useNotifications — hook global para el sistema de Push Notifications (P1).
 * - Abre WebSocket al /api/ws/notifications/{user_id}?token=... con session_token.
 * - Carga historial inicial por REST (GET /api/notifications).
 * - Escucha eventos WS "notification" y los prepende al estado local.
 * - Reconexión exponencial (max 30s) si cae.
 * - Permite `markRead(id)` y `markAllRead()`.
 */
export default function useNotifications() {
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const pollingRef = useRef(null);
  const unmountedRef = useRef(false);

  // onIncoming es memo-ed para que los listeners que dependan de él lo usen sin crear closures viejos
  const onIncomingRef = useRef(null);

  const fetchInitial = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/notifications?limit=50');
      setItems(Array.isArray(data.items) ? data.items : []);
      setUnread(data.unread_count ?? 0);
    } catch {
      // silencioso
    } finally {
      setLoading(false);
    }
  }, []);

  const connectWebSocket = useCallback(() => {
    const token = localStorage.getItem('session_token');
    const userStr = localStorage.getItem('user');
    if (!token || !userStr) return;
    let user;
    try { user = JSON.parse(userStr); } catch { return; }
    const userId = user?.user_id;
    if (!userId) return;

    const baseUrl = process.env.REACT_APP_BACKEND_URL || '';
    const wsProto = baseUrl.startsWith('https') ? 'wss' : 'ws';
    const host = baseUrl.replace(/^https?:\/\//, '');
    const url = `${wsProto}://${host}/api/ws/notifications/${userId}?token=${encodeURIComponent(token)}`;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        reconnectAttemptsRef.current = 0;
      };

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === 'notification' && msg.payload) {
            setItems((prev) => [msg.payload, ...prev].slice(0, 100));
            setUnread((u) => u + 1);
            if (onIncomingRef.current) onIncomingRef.current(msg.payload);
          } else if (msg.type === 'internal_message' && msg.payload) {
            // Mensaje interno (Centro de Mensajes): no entra a la lista de notificaciones
            // del sistema, solo dispara la alerta intensa.
            if (onIncomingRef.current) onIncomingRef.current({ ...msg.payload, kind: 'internal' });
            // Notifica al banner global y solicita recargar la bandeja.
            emitInboxChanged();
            emitInboxReloadList();
          }
        } catch {
          // ping/pong u otro msg no-JSON — ignorar
        }
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        if (unmountedRef.current) return;
        // Backoff exponencial, máximo 3 intentos antes de hacer fallback a polling
        const attempts = reconnectAttemptsRef.current + 1;
        reconnectAttemptsRef.current = attempts;
        if (attempts >= 3 && !pollingRef.current) {
          // Fallback automático: polling cada 30s cuando el WS no puede conectar
          pollingRef.current = setInterval(fetchInitial, 30000);
        }
        if (attempts < 3) {
          const delay = Math.min(30000, 1000 * Math.pow(2, attempts - 1));
          reconnectTimerRef.current = setTimeout(connectWebSocket, delay);
        }
      };

      ws.onerror = () => {
        try { ws.close(); } catch (e) { /* noop */ }
      };
    } catch {
      // Red caída: re-intentar en 5s
      reconnectTimerRef.current = setTimeout(connectWebSocket, 5000);
    }
  }, []);

  useEffect(() => {
    unmountedRef.current = false;
    fetchInitial();
    connectWebSocket();
    return () => {
      unmountedRef.current = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (pollingRef.current) clearInterval(pollingRef.current);
      if (wsRef.current) {
        try { wsRef.current.close(); } catch (e) { /* noop */ }
      }
    };
  }, [fetchInitial, connectWebSocket]);

  const markRead = useCallback(async (notificationId) => {
    try {
      await api.post(`/notifications/${notificationId}/read`);
      setItems((prev) => prev.map((n) => n.notification_id === notificationId ? { ...n, is_read: true } : n));
      setUnread((u) => Math.max(0, u - 1));
    } catch {
      // noop
    }
  }, []);

  const markAllRead = useCallback(async () => {
    try {
      await api.post('/notifications/mark-all-read');
      setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnread(0);
    } catch {
      // noop
    }
  }, []);

  const setOnIncoming = useCallback((cb) => {
    onIncomingRef.current = cb;
  }, []);

  return {
    items,
    unread,
    connected,
    loading,
    markRead,
    markAllRead,
    refresh: fetchInitial,
    setOnIncoming,
  };
}
