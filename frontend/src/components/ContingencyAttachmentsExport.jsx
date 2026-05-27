import { useState } from 'react';
import { Button } from './ui/button';
import { Download, ShieldAlert, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import api from '../utils/api';
import JSZip from 'jszip';

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
  const [downloadingPaged, setDownloadingPaged] = useState(false);
  const [pagedProgress, setPagedProgress] = useState('');
  const [downloadingPagedZip, setDownloadingPagedZip] = useState(false);
  const [pagedZipProgress, setPagedZipProgress] = useState('');

  // Solo admin
  const userStr = localStorage.getItem('user');
  let isAdmin = false;
  try {
    isAdmin = userStr && JSON.parse(userStr)?.role === 'admin';
  } catch {
    isAdmin = false;
  }
  if (!isAdmin) return null;

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

  // Descarga PAGINADA de ZIP DE ANEXOS: lista todos los archivos, los descarga uno
  // a uno con requests pequeñas y empaqueta el ZIP final en el browser con JSZip.
  // Inmune al 504: cada archivo viaja en su propia request <2s.
  const handleDownloadPagedZip = async () => {
    setDownloadingPagedZip(true);
    setPagedZipProgress('Listando anexos...');
    try {
      const listRes = await api.get('/admin/quotes-bundle-migration/attachments-list');
      const items = listRes.data?.items || [];
      const total = items.length;
      if (total === 0) {
        toast.info('No hay anexos para descargar.');
        return;
      }
      const zip = new JSZip();
      const included = [];
      const missing = [];
      for (let i = 0; i < total; i++) {
        const item = items[i];
        setPagedZipProgress(`Descargando ${i + 1}/${total} · ${item.path.slice(-40)}`);
        try {
          const r = await api.get('/admin/quotes-bundle-migration/attachment', {
            params: { path: item.path },
            responseType: 'blob',
          });
          const buf = await r.data.arrayBuffer();
          zip.file(item.path, buf);
          included.push({ path: item.path, size: buf.byteLength });
        } catch (err) {
          missing.push({ path: item.path, error: err.message });
        }
      }
      // Manifest
      zip.file(
        'manifest.json',
        JSON.stringify({
          schema_version: 1,
          module: 'quotes-bundle-attachments',
          mode: 'paginated-browser',
          exported_at: new Date().toISOString(),
          files_included: included,
          files_missing: missing,
          total_included: included.length,
          total_missing: missing.length,
        }, null, 2),
      );
      setPagedZipProgress('Comprimiendo ZIP local...');
      const blob = await zip.generateAsync({ type: 'blob', compression: 'DEFLATE' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      a.href = url;
      a.download = `quotes_bundle_attachments_paged_${ts}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
      toast.success(`ZIP paginado descargado · ${included.length} archivos${missing.length ? `, ${missing.length} no encontrados` : ''}`);
    } catch (e) {
      const msg = e.response?.data?.detail || e.message || 'Error desconocido';
      toast.error(`Error al exportar (ZIP paginado): ${msg}`);
    } finally {
      setDownloadingPagedZip(false);
      setPagedZipProgress('');
    }
  };

  return (
    <div
      className="bg-amber-50 rounded-lg border border-amber-200 p-6 mb-6"
      data-testid="contingency-attachments-section"
    >
      <h2 className="text-xl font-semibold text-amber-900 font-manrope mb-2 flex items-center gap-2">
        <ShieldAlert size={24} />
        Contingencia · Migración Cotizaciones
      </h2>
      <p className="text-amber-800 text-sm mb-4 leading-relaxed">
        Modo alternativo de exportación del bundle de cotizaciones diseñado para
        cuando el dataset es grande y el endpoint estándar falla por timeouts (504).
        <br />
        <strong className="text-emerald-800">JSON Paginado (Recomendado):</strong> descarga en
        chunks pequeños (100 docs/pág) y arma el archivo final localmente. Inmune a
        timeouts del ingress. Compatible con la importación estándar.
        <br />
        <strong className="text-cyan-800">ZIP paginado de Anexos:</strong> lista todos los
        archivos, los descarga uno a uno y empaqueta el ZIP final en el navegador.
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
          onClick={handleDownloadPagedZip}
          disabled={downloadingPagedZip}
          className="bg-cyan-600 hover:bg-cyan-700 text-white"
          data-testid="contingency-export-paged-zip-btn"
        >
          {downloadingPagedZip ? (
            <>
              <Loader2 size={16} className="mr-2 animate-spin" />
              {pagedZipProgress || 'Descargando ZIP paginado...'}
            </>
          ) : (
            <>
              <Download size={16} className="mr-2" />
              Descargar ZIP Paginado de Anexos (Recomendado)
            </>
          )}
        </Button>
      </div>
    </div>
  );
};

export default ContingencyAttachmentsExport;
