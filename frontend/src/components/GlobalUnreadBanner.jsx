import { useEffect, useState, useRef, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { Mail, AlertTriangle, Lock } from 'lucide-react';
import { useUnreadMessages } from '../context/UnreadMessagesContext';

/**
 * Banner global persistente (fixed, esquina superior derecha) que avisa de forma
 * obligatoria que hay mensajes sin leer en el Centro de Mensajes.
 *
 * Posposición limitada (Snooze) — máximo 3 veces:
 *  - Mientras el banner es visible y NO está bloqueado, al pulsar ENTER el aviso
 *    se oculta en la vista actual y el contador aumenta +1. Reaparece en la
 *    siguiente navegación de módulo o recarga, mostrando el intento actualizado.
 *  - El contador vive en sessionStorage (sobrevive a la navegación, se reinicia
 *    al cerrar el navegador o cerrar sesión).
 *  - Tras 3 posposiciones, en la 4ª aparición el banner queda FIJO: desaparece la
 *    leyenda "Pulse ENTER...", se ignora la tecla Enter y no puede ocultarse.
 *  - Resolución definitiva: solo cuando el backend reporta `unread === 0` (el
 *    usuario leyó sus mensajes) el banner se destruye y el contador se reinicia.
 */
const SNOOZE_KEY = 'unread_banner_snooze_count';
const MAX_SNOOZE = 3;

const readSnoozeCount = () => {
  try {
    const n = parseInt(sessionStorage.getItem(SNOOZE_KEY), 10);
    return Number.isFinite(n) && n > 0 ? Math.min(n, MAX_SNOOZE) : 0;
  } catch {
    return 0;
  }
};

export const GlobalUnreadBanner = () => {
  const { unread, loaded } = useUnreadMessages();
  const location = useLocation();
  const [snoozeCount, setSnoozeCount] = useState(readSnoozeCount);
  const [snoozedHere, setSnoozedHere] = useState(false);
  // `lockedSticky` se engancha (latch) al alcanzar el máximo, pero SOLO en la
  // siguiente aparición (cambio de ruta/recarga), no en el mismo render del 3er
  // ENTER. Así el usuario obtiene las 3 posposiciones completas y el anclaje
  // ocurre en la 4ª aparición. Si la recarga preserva un conteo ya en el tope,
  // arranca bloqueado de inmediato (esa recarga ES la 4ª aparición).
  const [lockedSticky, setLockedSticky] = useState(() => readSnoozeCount() >= MAX_SNOOZE);
  const lockRef = useRef(false); // evita doble incremento por Enter repetido
  const snoozeCountRef = useRef(snoozeCount);
  useEffect(() => { snoozeCountRef.current = snoozeCount; }, [snoozeCount]);

  const hasUnread = unread > 0;
  const locked = lockedSticky;
  const visible = hasUnread && (locked || !snoozedHere);

  // Reset total: sin mensajes sin leer (lectura validada por backend) o al
  // cerrar sesión (token fuera → unread 0). Reinicia el ciclo de posposición.
  // Se gatea con `loaded` para NO confundir el valor por defecto 0 (cargando)
  // con un 0 confirmado por el backend, lo que borraría el contador en cada
  // recarga completa del navegador.
  useEffect(() => {
    if (loaded && !hasUnread) {
      try { sessionStorage.removeItem(SNOOZE_KEY); } catch { /* noop */ }
      setSnoozeCount(0);
      setSnoozedHere(false);
      setLockedSticky(false);
      lockRef.current = false;
    }
  }, [loaded, hasUnread]);

  // Reaparece en cada cambio de módulo/navegación. Si ya se agotaron las
  // posposiciones, esta nueva aparición queda anclada (4ª aparición). Se lee el
  // conteo por ref para disparar SOLO ante cambios de ruta (no al posponer).
  useEffect(() => {
    setSnoozedHere(false);
    lockRef.current = false;
    if (snoozeCountRef.current >= MAX_SNOOZE) setLockedSticky(true);
  }, [location.pathname]);

  const snooze = useCallback(() => {
    setSnoozeCount((c) => {
      const next = Math.min(c + 1, MAX_SNOOZE);
      try { sessionStorage.setItem(SNOOZE_KEY, String(next)); } catch { /* noop */ }
      return next;
    });
    setSnoozedHere(true);
  }, []);

  // Gatillo de teclado: ENTER pospone (solo si visible y NO bloqueado).
  useEffect(() => {
    if (!visible || locked) return;
    const onKey = (e) => {
      if (e.key !== 'Enter') return;
      // No interferir con la escritura/envío en campos editables.
      const el = document.activeElement;
      const tag = (el?.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select' || el?.isContentEditable) return;
      if (lockRef.current) return;
      lockRef.current = true;
      snooze();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [visible, locked, snooze]);

  if (!visible) return null;

  const remaining = MAX_SNOOZE - snoozeCount;
  const attempt = snoozeCount + 1; // intento que se ofrece ahora (1..3)

  return (
    <div
      className="fixed top-5 right-5 z-[2147483646] max-w-[380px]"
      data-testid="global-unread-banner"
      role="alert"
      aria-live="assertive"
    >
      <div className={`flex items-start gap-3 rounded-xl bg-red-600 text-white px-4 py-3 shadow-2xl ring-2 ${locked ? 'ring-amber-300' : 'ring-red-300/70'}`}>
        <span className="relative shrink-0 flex items-center justify-center mt-0.5">
          <span className="absolute inline-flex h-9 w-9 rounded-full bg-white/20 animate-ping" />
          <span className="relative inline-flex items-center justify-center h-9 w-9 rounded-lg bg-white/20">
            {locked ? <Lock size={18} /> : <Mail size={18} className="animate-pulse" />}
          </span>
        </span>
        <div className="min-w-0">
          <p className="flex items-center gap-1 text-sm font-bold leading-snug">
            <AlertTriangle size={14} className="shrink-0" />
            ¡Atención!
          </p>
          <p className="text-xs text-white/95 leading-snug" data-testid="global-unread-banner-text">
            Tiene {unread === 1 ? 'un mensaje pendiente' : `${unread} mensajes pendientes`} por leer en su bandeja.
          </p>
          {!locked ? (
            <p
              className="mt-1.5 text-[11px] text-white/85 leading-snug italic"
              data-testid="global-unread-banner-snooze-hint"
            >
              Pulse <kbd className="px-1 rounded bg-white/25 not-italic font-semibold tracking-wide">ENTER</kbd> para ocultar temporalmente — Quedan {remaining} de {MAX_SNOOZE} intentos ({attempt}/{MAX_SNOOZE}).
            </p>
          ) : (
            <p
              className="mt-1.5 text-[11px] text-amber-200 leading-snug font-semibold"
              data-testid="global-unread-banner-locked-hint"
            >
              Aviso fijo: lea sus mensajes en el Centro de Mensajes para retirarlo.
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default GlobalUnreadBanner;
