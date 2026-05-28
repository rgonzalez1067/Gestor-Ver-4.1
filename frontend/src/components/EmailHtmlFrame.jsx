import { useEffect, useRef, useState } from 'react';

/**
 * Render seguro de cuerpos HTML de correos electrónicos en un iframe sandbox.
 *
 * ¿Por qué iframe y no `dangerouslySetInnerHTML`?
 *   Los cuerpos HTML de los correos son **documentos completos**
 *   (`<!DOCTYPE><html><head><body>...`). Inyectarlos dentro de un `<div>`
 *   provoca:
 *     1. HTML inválido — `<html>` y `<body>` anidados dentro de un `<div>`.
 *     2. Errores de hidratación de React.
 *     3. Cualquier estilo o `<style>` del email contamina la app.
 *     4. Errores que rebotan a `window.onerror` y aparecen como
 *        "Script error." en el overlay de desarrollo.
 *
 *   El iframe sandbox aísla el render, mantiene los estilos originales del
 *   correo y elimina cualquier posibilidad de contaminación o XSS
 *   (el sandbox bloquea scripts, navegación, formularios, etc.).
 *
 * Altura dinámica: tras `load`, medimos `scrollHeight` del documento del
 * iframe para que la altura se ajuste al contenido (sin scroll interno).
 */
export function EmailHtmlFrame({ html, title = 'Mensaje', testId }) {
  const iframeRef = useRef(null);
  const [height, setHeight] = useState(120);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;
    const onLoad = () => {
      try {
        const doc = iframe.contentDocument;
        if (!doc) return;
        // Ajustar altura al contenido real (mínimo 120px, máximo 1600px para
        // evitar consumir toda la pantalla en correos muy largos).
        const measured = Math.max(
          doc.documentElement.scrollHeight,
          doc.body?.scrollHeight || 0,
        );
        setHeight(Math.min(Math.max(measured + 24, 120), 1600));
      } catch {
        // Cross-origin no aplica (srcdoc es same-origin) pero protegemos por si acaso.
      }
    };
    iframe.addEventListener('load', onLoad);
    return () => iframe.removeEventListener('load', onLoad);
  }, [html]);

  return (
    <iframe
      ref={iframeRef}
      title={title}
      srcDoc={html || ''}
      // sandbox sin allow-scripts: bloquea cualquier JS embebido en el correo.
      // allow-same-origin permite medir scrollHeight del documento.
      sandbox="allow-same-origin"
      className="w-full bg-white rounded-lg border border-slate-200"
      style={{ height: `${height}px`, display: 'block' }}
      data-testid={testId}
    />
  );
}
