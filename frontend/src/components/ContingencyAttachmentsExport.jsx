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
  // Construye el JSON como múltiples Blob parts para evitar el límite de string V8
  // (~512MB) cuando hay muchos documentos con history embebido.
  const handleDownloadPaged = async () => {
    setDownloadingPaged(true);
    setPagedProgress('Consultando totales...');
    try {
      const PAGE_SIZE = 100;
      const countsRes = await api.get('/admin/quotes-bundle-migration/counts');
      const counts = countsRes.data?.counts || {};
      const collections = countsRes.data?.collections || [];

      // Cabecera y metadata del JSON
      const meta = {
        schema_version: 1,
        module: 'quotes-bundle',
        mode: 'paginated',
        exported_at: new Date().toISOString(),
        counts,
      };
      // Construimos el JSON como array de Blob parts. Cada documento se serializa
      // individualmente — evita explotar el heap con un solo JSON.stringify masivo.
      const parts = [];
      parts.push('{');
      parts.push(`"schema_version":${meta.schema_version},`);
      parts.push(`"module":"quotes-bundle",`);
      parts.push(`"mode":"paginated",`);
      parts.push(`"exported_at":${JSON.stringify(meta.exported_at)},`);
      parts.push(`"counts":${JSON.stringify(counts)},`);
      parts.push('"collections":{');

      for (let ci = 0; ci < collections.length; ci++) {
        const col = collections[ci];
        const total = counts[col] || 0;
        if (ci > 0) parts.push(',');
        parts.push(`${JSON.stringify(col)}:[`);
        let skip = 0;
        let pageNo = 1;
        let docsInCol = 0;
        while (skip < total) {
          setPagedProgress(`${col} · página ${pageNo} (${skip}/${total})`);
          const r = await api.get('/admin/quotes-bundle-migration/page', {
            params: { collection: col, skip, limit: PAGE_SIZE },
          });
          const docs = r.data?.docs || [];
          if (docs.length === 0) break;
          for (const d of docs) {
            if (docsInCol > 0) parts.push(',');
            try {
              parts.push(JSON.stringify(d));
            } catch (serErr) {
              console.warn('No se pudo serializar documento', d?._id || d?.quote_id, serErr);
              parts.push('null');
            }
            docsInCol += 1;
          }
          skip += docs.length;
          pageNo += 1;
        }
        parts.push(']');
      }
      parts.push('}}');

      setPagedProgress('Generando archivo...');
      // Pasar las parts directamente al Blob — no construye un string intermedio masivo.
      const blob = new Blob(parts, { type: 'application/json' });
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
      const msg = e?.response?.data?.detail || e?.message || 'Error desconocido';
      toast.error(`Error al exportar (paginado): ${msg}`);
      console.error('[JSON Paginado] error:', e);
    } finally {
      setDownloadingPaged(false);
      setPagedProgress('');
    }
  };

  // Descarga PAGINADA de ZIP DE ANEXOS: lista todos los archivos, los descarga uno
  // a uno con requests pequeñas y empaqueta el ZIP final en el browser con JSZip.
  // Inmune al 504: cada archivo viaja en su propia request <2s.
  //
  // Implementación resistente a OOM para datasets grandes (>200MB):
  //  1. compression: 'STORE' (no DEFLATE) — los PDFs ya están comprimidos internamente,
  //     deflate solo consume CPU y ~30% más memoria sin ganancia real.
  //  2. generateInternalStream + Streams API → escribe chunks al disco a medida que
  //     se generan, sin armar el ZIP completo en memoria.
  //  3. Fallback a generateAsync(blob) solo para browsers viejos.
  //  4. buf = null tras cada zip.file(...) para que el GC pueda liberar.
  //  5. Guards defensivos sobre item.path / r.data.
  const handleDownloadPagedZip = async () => {
    setDownloadingPagedZip(true);
    setPagedZipProgress('Listando anexos...');
    try {
      const listRes = await api.get('/admin/quotes-bundle-migration/attachments-list');
      const items = (listRes.data?.items || []).filter(
        (it) => it && typeof it.path === 'string' && it.path.length > 0,
      );
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
        const shortPath = String(item.path).slice(-40);
        setPagedZipProgress(`Descargando ${i + 1}/${total} · ${shortPath}`);
        try {
          const r = await api.get('/admin/quotes-bundle-migration/attachment', {
            params: { path: item.path },
            responseType: 'blob',
          });
          if (!r?.data || typeof r.data.arrayBuffer !== 'function') {
            missing.push({ path: item.path, error: 'respuesta sin blob' });
            continue;
          }
          let buf = await r.data.arrayBuffer();
          zip.file(item.path, buf, { binary: true });
          included.push({ path: item.path, size: buf.byteLength });
          buf = null; // ayudar al GC a liberar memoria
          // Pequeño yield al event loop cada 25 archivos para que el GC corra y
          // el navegador no marque el tab como "sin responder".
          if (i % 25 === 24) await new Promise((res) => setTimeout(res, 0));
        } catch (err) {
          missing.push({ path: item.path, error: err?.message || 'error' });
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
        }),
      );

      const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      const filename = `quotes_bundle_attachments_paged_${ts}.zip`;

      setPagedZipProgress(`Comprimiendo ${included.length} archivos...`);

      // PATH PREFERIDO: File System Access API → escritura streaming directo a disco.
      // Soportado en Chrome/Edge 86+. Evita armar el blob completo en RAM.
      if (typeof window.showSaveFilePicker === 'function') {
        try {
          const handle = await window.showSaveFilePicker({
            suggestedName: filename,
            types: [{ description: 'ZIP', accept: { 'application/zip': ['.zip'] } }],
          });
          const writable = await handle.createWritable();
          await new Promise((resolve, reject) => {
            const stream = zip.generateInternalStream({
              type: 'uint8array',
              compression: 'STORE',
              streamFiles: true,
            });
            stream.on('data', (chunk, meta) => {
              writable.write(chunk).catch(reject);
              if (meta && meta.percent != null) {
                setPagedZipProgress(`Escribiendo ZIP · ${meta.percent.toFixed(0)}%`);
              }
            });
            stream.on('error', (e) => reject(e));
            stream.on('end', async () => {
              try { await writable.close(); resolve(); } catch (e) { reject(e); }
            });
            stream.resume();
          });
          toast.success(`ZIP paginado descargado · ${included.length} archivos${missing.length ? `, ${missing.length} no encontrados` : ''}`);
          return;
        } catch (pickErr) {
          // El usuario canceló el picker o el browser falló → caer al fallback Blob.
          if (pickErr?.name === 'AbortError') {
            toast.info('Descarga cancelada.');
            return;
          }
          console.warn('[ZIP Paginado] showSaveFilePicker falló, usando Blob fallback:', pickErr);
        }
      }

      // FALLBACK: Blob acumulado (browsers sin File System Access API)
      // Sin compresión (STORE) para minimizar consumo de memoria.
      const blob = await zip.generateAsync({ type: 'blob', compression: 'STORE' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
      toast.success(`ZIP paginado descargado · ${included.length} archivos${missing.length ? `, ${missing.length} no encontrados` : ''}`);
    } catch (e) {
      const msg = e?.response?.data?.detail || e?.message || 'Error desconocido';
      toast.error(`Error al exportar (ZIP paginado): ${msg}`);
      console.error('[ZIP Paginado] error:', e);
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
