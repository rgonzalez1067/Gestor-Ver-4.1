import { useEffect, useRef } from 'react';

/**
 * TwinScrollTable — Iter52.
 *
 * Wrapper que renderiza dos barras de desplazamiento horizontal (una arriba
 * y otra abajo de la grilla) sincronizadas en ratio 1:1. Útil cuando la
 * tabla tiene muchas columnas y el usuario quiere desplazarse sin tener
 * que llegar al final del listado.
 *
 * Implementación:
 *   - Barra superior: un `<div>` con altura 1px que contiene un spacer cuyo
 *     width equivale al `scrollWidth` real de la tabla. Como su contenedor
 *     tiene `overflow-x: auto`, el navegador renderiza la barra nativa.
 *   - Barra inferior: el contenedor scrollable que envuelve la tabla.
 *   - Sync bidireccional: cuando el usuario arrastra una, replicamos el
 *     `scrollLeft` en la otra. Un flag `syncingRef` evita bucles infinitos.
 *   - Reaccionamos a cambios de tamaño con `ResizeObserver` para que el
 *     spacer superior siempre refleje el ancho real del contenido (necesario
 *     cuando filas se agregan/quitan dinámicamente).
 */
export function TwinScrollTable({ children }) {
  const topRef = useRef(null);
  const bottomRef = useRef(null);
  const spacerRef = useRef(null);
  const syncingRef = useRef(false);

  useEffect(() => {
    const top = topRef.current;
    const bot = bottomRef.current;
    if (!top || !bot) return;

    const handle = (source, target) => () => {
      if (syncingRef.current) return;
      syncingRef.current = true;
      target.scrollLeft = source.scrollLeft;
      // Liberar en el siguiente tick para permitir que el otro scroll repinte.
      requestAnimationFrame(() => { syncingRef.current = false; });
    };
    const onTop = handle(top, bot);
    const onBot = handle(bot, top);
    top.addEventListener('scroll', onTop, { passive: true });
    bot.addEventListener('scroll', onBot, { passive: true });

    const updateSpacer = () => {
      if (spacerRef.current && bot) {
        spacerRef.current.style.width = `${bot.scrollWidth}px`;
      }
    };
    updateSpacer();
    // Diferir el callback con requestAnimationFrame para evitar el clásico
    // "ResizeObserver loop completed with undelivered notifications" cuando
    // el cambio de width del spacer dispara otro resize en cascada.
    const ro = new ResizeObserver(() => {
      requestAnimationFrame(updateSpacer);
    });
    ro.observe(bot);
    // Solo observar el contenedor; observar el child generaba loops cuando
    // el alto/ancho del contenido se recalcula con cada render.

    return () => {
      top.removeEventListener('scroll', onTop);
      bot.removeEventListener('scroll', onBot);
      ro.disconnect();
    };
  }, []);

  return (
    <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
      {/* Barra superior: solo es un sleeve de scroll, sin contenido visible. */}
      <div
        ref={topRef}
        className="overflow-x-auto overflow-y-hidden border-b border-slate-100 bg-slate-50"
        style={{ height: '14px' }}
        data-testid="twin-scroll-top"
      >
        <div ref={spacerRef} style={{ height: '1px' }} />
      </div>
      {/* Contenedor real que envuelve la tabla — barra inferior nativa. */}
      <div ref={bottomRef} className="overflow-x-auto" data-testid="twin-scroll-bottom">
        {children}
      </div>
    </div>
  );
}
