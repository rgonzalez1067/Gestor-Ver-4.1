import { useState } from 'react';
import { Button } from './ui/button';
import { Download, ShieldAlert, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import api from '../utils/api';

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
  const [downloadingPaged, setDownloadingPaged] = useState(false);
  const [pagedProgress, setPagedProgress] = useState('');

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
    // Usar axios (api) en lugar de fetch nativo: en producción algunos
    // service workers / interceptores del ingress consumen el body de Response
    // antes de que podamos leerlo, generando "body stream already read".
    // axios usa XHR y devuelve un Blob completo sin re-streamings problemáticos.
    const res = await api.get(path, { responseType: 'blob' });
    const blob = res.data;
    const cd = res.headers?.['content-disposition'] || '';
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
    if (onSuccessHeaders) onSuccessHeaders(res.headers || {});
  };

  const handleDownloadAttachments = async () => {
    setDownloading(true);
    try {
      await _streamedDownload(
        '/admin/quotes-bundle-migration/export-attachments-streamed',
        'quotes_bundle_attachments_streamed.zip',
        (h) => {
          const inc = h['x-files-included'] || h['X-Files-Included'] || '?';
          const miss = h['x-files-missing'] || h['X-Files-Missing'] || '0';
          toast.success(`ZIP descargado (${inc} archivos, ${miss} no encontrados)`);
        },
      );
    } catch (e) {
      const msg = e.response?.data?.detail || e.message || 'Error desconocido';
      toast.error(`Error al exportar (contingencia anexos): ${msg}`);
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
          const q = h['x-counts-quotes'] || h['X-Counts-Quotes'] || '?';
          const hi = h['x-counts-history'] || h['X-Counts-History'] || '?';
          const p = h['x-counts-projects'] || h['X-Counts-Projects'] || '?';
          toast.success(`JSON descargado · ${q} cotizaciones, ${hi} históricos, ${p} proyectos`);
        },
      );
    } catch (e) {
      const msg = e.response?.data?.detail || e.message || 'Error desconocido';
      toast.error(`Error al exportar (contingencia datos): ${msg}`);
    } finally {
      setDownloadingData(false);
    }
  };

  // Descarga PAGINADA: itera por (colección, página) y arma el JSON localmente.
  // Inmune al 504 Gateway Timeout en producción porque cada request es pequeña (<2s).
  const handleDownloadPaged = async () => {
    setDownloadingPaged(true);
    setPagedProgress('Consultando totales...');
    try {
      const PAGE_SIZE = 100;
      const countsRes = await api.get('/admin/quotes-bundle-migration/counts');
      const counts = countsRes.data?.counts || {};
      const collections = countsRes.data?.collections || [];
      const result = {
        schema_version: 1,
        module: 'quotes-bundle',
        mode: 'paginated',
        exported_at: new Date().toISOString(),
        collections: {},
        counts,
      };
      for (const col of collections) {
        const total = counts[col] || 0;
        result.collections[col] = [];
        let skip = 0;
        let pageNo = 1;
        while (skip < total) {
          setPagedProgress(`${col} · página ${pageNo} (${skip}/${total})`);
          const r = await api.get('/admin/quotes-bundle-migration/page', {
            params: { collection: col, skip, limit: PAGE_SIZE },
          });
          const docs = r.data?.docs || [];
          result.collections[col].push(...docs);
          skip += docs.length;
          pageNo += 1;
          if (docs.length === 0) break;
        }
      }
      const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      a.href = url;
      a.download = `quotes_bundle_data_paged_${ts}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
      const summary = Object.entries(counts).map(([k, v]) => `${v} ${k}`).join(', ');
      toast.success(`JSON paginado descargado · ${summary}`);
    } catch (e) {
      const msg = e.response?.data?.detail || e.message || 'Error desconocido';
      toast.error(`Error al exportar (paginado): ${msg}`);
    } finally {
      setDownloadingPaged(false);
      setPagedProgress('');
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
        Modo alternativo de exportación del bundle de cotizaciones diseñado para
        cuando el dataset es grande y el endpoint estándar falla por timeouts (504).
        <br />
        <strong className="text-emerald-800">JSON Paginado (Recomendado):</strong> descarga en
        chunks pequeños (100 docs/pág) y arma el archivo final localmente. Inmune a
        timeouts del ingress. Compatible con la importación estándar.
        <br />
        <span className="font-medium">JSON Streaming / ZIP Streaming:</span> construyen el
        archivo en disco del backend en una sola request. Útiles si la paginación no aplica.
        <br />
        <span className="font-medium">Las opciones estándar de Cotizaciones permanecen sin cambios.</span>
      </p>
      <div className="flex flex-wrap gap-3">
        <Button
          onClick={handleDownloadPaged}
          disabled={downloadingPaged}
          className="bg-emerald-600 hover:bg-emerald-700 text-white"
          data-testid="contingency-export-paged-btn"
        >
          {downloadingPaged ? (
            <>
              <Loader2 size={16} className="mr-2 animate-spin" />
              {pagedProgress || 'Descargando paginado...'}
            </>
          ) : (
            <>
              <Download size={16} className="mr-2" />
              Descargar JSON Paginado (Recomendado)
            </>
          )}
        </Button>
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
              JSON Streaming (1 request)
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
              ZIP de Anexos (Streaming)
            </>
          )}
        </Button>
      </div>
    </div>
  );
};

export default ContingencyAttachmentsExport;
