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

  // Descarga PAGINADA de ZIP DE ANEXOS por LOTES — Estrategia "Batching" para garantizar
  // que no falle independientemente del tamaño del dataset:
  //
  //   - Divide los anexos en lotes de BATCH_SIZE (75 archivos ≈ 40-60 MB c/u)
  //   - Cada lote es su propio ZIP autocontenido (`part_NN_of_MM.zip`)
  //   - Memoria pico predecible (~60MB constante) sin importar si hay 100, 1000 o 5000 anexos
  //   - Funciona en TODOS los browsers (no requiere File System Access API)
  //   - Tolerante a fallos parciales: si un archivo individual falla, queda registrado
  //     en el manifest del lote y la descarga continúa
  //   - Genera al final un `quotes_attachments_manifest_global.json` con índice consolidado
  const handleDownloadPagedZip = async () => {
    const BATCH_SIZE = 75; // archivos por ZIP — calibrado para ~40-60MB por batch
    setDownloadingPagedZip(true);
    setPagedZipProgress('Listando anexos...');
    try {
      const listRes = await api.get('/admin/quotes-bundle-migration/attachments-list');
      const allItems = (listRes.data?.items || []).filter(
        (it) => it && typeof it.path === 'string' && it.path.length > 0,
      );
      const totalGlobal = allItems.length;
      if (totalGlobal === 0) {
        toast.info('No hay anexos para descargar.');
        return;
      }

      const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      const totalBatches = Math.ceil(totalGlobal / BATCH_SIZE);
      const globalIncluded = [];
      const globalMissing = [];

      // Helper para descargar un blob individual
      const triggerDownload = (blob, filename) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 30000);
      };

      const pad2 = (n) => String(n).padStart(2, '0');

      // Procesar cada lote secuencialmente
      for (let b = 0; b < totalBatches; b++) {
        const batchItems = allItems.slice(b * BATCH_SIZE, (b + 1) * BATCH_SIZE);
        const batchLabel = `Lote ${b + 1}/${totalBatches}`;
        const zip = new JSZip();
        const batchIncluded = [];
        const batchMissing = [];

        for (let i = 0; i < batchItems.length; i++) {
          const item = batchItems[i];
          const globalIdx = b * BATCH_SIZE + i + 1;
          const shortPath = String(item.path).slice(-40);
          setPagedZipProgress(`${batchLabel} · Archivo ${i + 1}/${batchItems.length} (global ${globalIdx}/${totalGlobal}) · ${shortPath}`);
          try {
            const r = await api.get('/admin/quotes-bundle-migration/attachment', {
              params: { path: item.path },
              responseType: 'blob',
            });
            if (!r?.data || typeof r.data.arrayBuffer !== 'function') {
              batchMissing.push({ path: item.path, error: 'respuesta sin blob' });
              globalMissing.push({ path: item.path, error: 'respuesta sin blob', batch: b + 1 });
              continue;
            }
            let buf = await r.data.arrayBuffer();
            zip.file(item.path, buf, { binary: true });
            batchIncluded.push({ path: item.path, size: buf.byteLength });
            globalIncluded.push({ path: item.path, size: buf.byteLength, batch: b + 1 });
            buf = null;
            // Yield al event loop cada 10 archivos
            if (i % 10 === 9) await new Promise((res) => setTimeout(res, 0));
          } catch (err) {
            batchMissing.push({ path: item.path, error: err?.message || 'error' });
            globalMissing.push({ path: item.path, error: err?.message || 'error', batch: b + 1 });
          }
        }

        // Manifest del lote (autocontenido)
        zip.file(
          'manifest.json',
          JSON.stringify({
            schema_version: 1,
            module: 'quotes-bundle-attachments',
            mode: 'paginated-batch',
            batch_number: b + 1,
            total_batches: totalBatches,
            exported_at: new Date().toISOString(),
            files_included: batchIncluded,
            files_missing: batchMissing,
            total_included: batchIncluded.length,
            total_missing: batchMissing.length,
          }),
        );

        setPagedZipProgress(`${batchLabel} · Comprimiendo (${batchIncluded.length} archivos)...`);
        // STORE: PDFs ya están comprimidos, deflate solo consume RAM/CPU sin ganancia
        const batchBlob = await zip.generateAsync({ type: 'blob', compression: 'STORE' });
        const batchFilename = `quotes_attachments_${ts}_part_${pad2(b + 1)}_of_${pad2(totalBatches)}.zip`;
        triggerDownload(batchBlob, batchFilename);

        // Pausa entre lotes para que el navegador libere memoria completamente
        // antes de empezar el siguiente. Suficiente tiempo para GC.
        if (b < totalBatches - 1) {
          setPagedZipProgress(`Pausando 500ms antes del siguiente lote...`);
          await new Promise((res) => setTimeout(res, 500));
        }
      }

      // Manifest global consolidado (índice + diagnóstico cruzado de los N batches)
      const globalManifest = {
        schema_version: 1,
        module: 'quotes-bundle-attachments',
        mode: 'paginated-batch-global',
        exported_at: new Date().toISOString(),
        total_batches: totalBatches,
        batch_size: BATCH_SIZE,
        total_files_global: totalGlobal,
        total_included_global: globalIncluded.length,
        total_missing_global: globalMissing.length,
        files_included: globalIncluded,
        files_missing: globalMissing,
      };
      const manifestBlob = new Blob([JSON.stringify(globalManifest, null, 2)], { type: 'application/json' });
      triggerDownload(manifestBlob, `quotes_attachments_${ts}_manifest_global.json`);

      const missSuffix = globalMissing.length ? `, ${globalMissing.length} no encontrados` : '';
      toast.success(`ZIP descargado en ${totalBatches} lotes · ${globalIncluded.length} archivos${missSuffix} · revisar manifest_global.json`);
    } catch (e) {
      const msg = e?.response?.data?.detail || e?.message || 'Error desconocido';
      toast.error(`Error al exportar (ZIP por lotes): ${msg}`);
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
        archivos, los descarga uno a uno y los empaqueta en lotes de ~75 archivos por ZIP
        (memoria pico acotada, ~60MB por lote) + un <code>manifest_global.json</code> consolidado.
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
