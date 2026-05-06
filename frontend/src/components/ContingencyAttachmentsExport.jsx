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
  const [downloadingData, setDownloadingData] = useState(false);

  // Solo admin
  const userStr = localStorage.getItem('user');
  let isAdmin = false;
  try {
    isAdmin = userStr && JSON.parse(userStr)?.role === 'admin';
  } catch {
    isAdmin = false;
  }
  if (!isAdmin) return null;

  const _streamedDownload = async (path, fallbackName, onSuccessHeaders) => {
    const token = localStorage.getItem('session_token');
    const res = await fetch(`${BACKEND_URL}/api${path}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const blob = await res.blob();
    if (!res.ok) {
      let txt = '';
      try { txt = await blob.text(); } catch { /* ignore */ }
      throw new Error(txt || `HTTP ${res.status} ${res.statusText || ''}`.trim());
    }
    const cd = res.headers.get('Content-Disposition') || '';
    const m = cd.match(/filename="?([^"]+)"?/);
    const filename = (m && m[1]) || fallbackName;
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
    if (onSuccessHeaders) onSuccessHeaders(res.headers);
  };

  const handleDownloadAttachments = async () => {
    setDownloading(true);
    try {
      await _streamedDownload(
        '/admin/quotes-bundle-migration/export-attachments-streamed',
        'quotes_bundle_attachments_streamed.zip',
        (h) => {
          const inc = h.get('X-Files-Included') || '?';
          const miss = h.get('X-Files-Missing') || '0';
          toast.success(`ZIP descargado (${inc} archivos, ${miss} no encontrados)`);
        },
      );
    } catch (e) {
      toast.error(`Error al exportar (contingencia anexos): ${e.message}`);
    } finally {
      setDownloading(false);
    }
  };

  const handleDownloadData = async () => {
    setDownloadingData(true);
    try {
      await _streamedDownload(
        '/admin/quotes-bundle-migration/export-data-streamed',
        'quotes_bundle_data_streamed.json',
        (h) => {
          const q = h.get('X-Counts-Quotes') || '?';
          const hi = h.get('X-Counts-History') || '?';
          const p = h.get('X-Counts-Projects') || '?';
          toast.success(`JSON descargado · ${q} cotizaciones, ${hi} históricos, ${p} proyectos`);
        },
      );
    } catch (e) {
      toast.error(`Error al exportar (contingencia datos): ${e.message}`);
    } finally {
      setDownloadingData(false);
    }
  };

  return (
    <div
      className="bg-amber-50 rounded-lg border border-amber-200 p-6 mb-6"
      data-testid="contingency-attachments-section"
    >
      <h2 className="text-xl font-semibold text-amber-900 font-manrope mb-2 flex items-center gap-2">
        <ShieldAlert size={24} />
        Contingencia · Migración Cotizaciones (Streaming)
      </h2>
      <p className="text-amber-800 text-sm mb-4 leading-relaxed">
        Modo alternativo de exportación del bundle de cotizaciones. El JSON y el ZIP se
        construyen en disco (no en memoria), evitando timeouts y errores de transferencia
        parcial cuando el dataset es grande.
        <br />
        <span className="font-medium">Uso recomendado:</span> únicamente cuando los botones
        estándar de "Migración (Admin)" en la pantalla de Cotizaciones fallen por{' '}
        <code className="bg-amber-100 px-1 rounded">body stream already read</code> o
        timeouts del ingress. Las opciones estándar permanecen disponibles y sin cambios.
      </p>
      <div className="flex flex-wrap gap-3">
        <Button
          onClick={handleDownloadData}
          disabled={downloadingData}
          variant="outline"
          className="border-amber-600 text-amber-800 hover:bg-amber-100"
          data-testid="contingency-export-data-btn"
        >
          {downloadingData ? (
            <>
              <Loader2 size={16} className="mr-2 animate-spin" />
              Generando JSON en disco...
            </>
          ) : (
            <>
              <Download size={16} className="mr-2" />
              Descargar JSON de Datos (Streaming)
            </>
          )}
        </Button>
        <Button
          onClick={handleDownloadAttachments}
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
    </div>
  );
};

export default ContingencyAttachmentsExport;
