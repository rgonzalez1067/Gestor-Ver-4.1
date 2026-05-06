import { useState } from 'react';
import { Button } from './ui/button';
import { Download, ShieldAlert, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

/**
 * Sección de Configuración (Admin) — Exportación de Contingencia para Anexos.
 *
 * Usa el endpoint streaming-a-disco `/admin/quotes-bundle-migration/export-attachments-streamed`
 * que escribe el ZIP en un archivo temporal en disco y lo sirve con FileResponse.
 * Diseñado para datasets grandes que saturan el endpoint estándar (en memoria) por:
 *   - Timeouts del proxy/ingress en producción.
 *   - "body stream already read" tras transferencia parcial.
 *   - Memoria del backend agotada por ZIPs muy grandes.
 *
 * La opción estándar (en memoria) sigue disponible desde la pantalla de Cotizaciones
 * (botón "Migración (Admin) ZIP de Anexos") y permanece sin cambios.
 */
export const ContingencyAttachmentsExport = () => {
  const [downloading, setDownloading] = useState(false);

  // Solo admin
  const userStr = localStorage.getItem('user');
  let isAdmin = false;
  try {
    isAdmin = userStr && JSON.parse(userStr)?.role === 'admin';
  } catch {
    isAdmin = false;
  }
  if (!isAdmin) return null;

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const token = localStorage.getItem('session_token');
      const res = await fetch(
        `${BACKEND_URL}/api/admin/quotes-bundle-migration/export-attachments-streamed`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      // Leer el body UNA sola vez como Blob para evitar "body stream already read"
      // si el ingress/proxy interrumpe la transferencia.
      const blob = await res.blob();
      if (!res.ok) {
        let txt = '';
        try { txt = await blob.text(); } catch { /* ignore */ }
        throw new Error(txt || `HTTP ${res.status} ${res.statusText || ''}`.trim());
      }
      const cd = res.headers.get('Content-Disposition') || '';
      const m = cd.match(/filename="?([^"]+)"?/);
      const filename = (m && m[1]) || 'quotes_bundle_attachments_streamed.zip';
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
      const included = res.headers.get('X-Files-Included') || '?';
      const missing = res.headers.get('X-Files-Missing') || '0';
      toast.success(`ZIP descargado (${included} archivos, ${missing} no encontrados)`);
    } catch (e) {
      toast.error(`Error al exportar (contingencia): ${e.message}`);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div
      className="bg-amber-50 rounded-lg border border-amber-200 p-6 mb-6"
      data-testid="contingency-attachments-section"
    >
      <h2 className="text-xl font-semibold text-amber-900 font-manrope mb-2 flex items-center gap-2">
        <ShieldAlert size={24} />
        Contingencia · Export Streaming de Anexos
      </h2>
      <p className="text-amber-800 text-sm mb-4 leading-relaxed">
        Modo alternativo de exportación de anexos del bundle de cotizaciones.
        El ZIP se construye en disco (no en memoria), lo cual evita timeouts y
        errores de transferencia parcial cuando el dataset es grande.
        <br />
        <span className="font-medium">Uso recomendado:</span> únicamente cuando el
        botón estándar de "Migración (Admin) — ZIP de Anexos" en la pantalla de
        Cotizaciones falle por <code className="bg-amber-100 px-1 rounded">body stream already read</code>{' '}
        o timeouts del ingress. La opción estándar permanece disponible y sin cambios.
      </p>
      <Button
        onClick={handleDownload}
        disabled={downloading}
        className="bg-amber-600 hover:bg-amber-700 text-white"
        data-testid="contingency-export-attachments-btn"
      >
        {downloading ? (
          <>
            <Loader2 size={16} className="mr-2 animate-spin" />
            Generando ZIP en disco...
          </>
        ) : (
          <>
            <Download size={16} className="mr-2" />
            Descargar ZIP de Anexos (Streaming)
          </>
        )}
      </Button>
    </div>
  );
};

export default ContingencyAttachmentsExport;
