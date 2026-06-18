import { useState, useRef } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../ui/tabs';
import {
  Database, Download, Upload, FileJson, FileArchive, Loader2,
  AlertTriangle, CheckCircle2, FolderOpen, ShieldCheck,
} from 'lucide-react';
import api from '../../utils/api';
import { toast } from 'sonner';
import JSZip from 'jszip';

// Helper: descarga binaria autenticada usando el cliente axios (api).
// Antes usaba fetch nativo, pero en producción algunos service workers /
// interceptores del ingress consumen el body de Response antes de que podamos
// leerlo, generando "body stream already read". axios usa XHR y devuelve un
// Blob completo sin re-streaming problemático.
async function authedDownload(path, suggestedName) {
  const res = await api.get(path, { responseType: 'blob' });
  const blob = res.data;
  const cd = res.headers?.['content-disposition'] || '';
  const m = cd.match(/filename="?([^"]+)"?/);
  const filename = (m && m[1]) || suggestedName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}

export function QuotesBundleMigrationModal({ open, onClose }) {
  const [downloadingData, setDownloadingData] = useState(false);
  const [downloadingZip, setDownloadingZip] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [importingData, setImportingData] = useState(false);
  const [importProgress, setImportProgress] = useState(null); // { current, total, fileName }
  const [importingZip, setImportingZip] = useState(false);
  const [zipProgress, setZipProgress] = useState('');
  const [previewSummary, setPreviewSummary] = useState(null);
  const [dataResult, setDataResult] = useState(null);
  const [zipResult, setZipResult] = useState(null);
  const dataFileRef = useRef(null);
  const zipFileRef = useRef(null);
  const previewFileRef = useRef(null);

  // Auto-recovery: replica anexos del FS local al Object Storage
  const [recovering, setRecovering] = useState(false);
  const [recoveryResult, setRecoveryResult] = useState(null);
  const [recoveryProgress, setRecoveryProgress] = useState(null); // { processed, total }

  const handleRecoverToStorage = async (dryRun = false) => {
    setRecovering(true);
    setRecoveryResult(null);
    setRecoveryProgress(null);

    // Acumuladores globales sobre todos los lotes
    const totals = {
      scanned: 0, already_in_storage: 0, uploaded: 0,
      missing_everywhere: 0, errors: 0,
      by_collection: {
        quotes: { scanned: 0, ok: 0, uploaded: 0, missing: 0 },
        quote_history: { scanned: 0, ok: 0, uploaded: 0, missing: 0 },
      },
      missing_details: [],
      error_details: [],
    };
    const BATCH = 50;
    let skip = 0;
    let total = null;

    try {
      // Loop hasta done=true (paginado para evitar timeout proxy K8s 60s)
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const res = await api.post(
          `/admin/attachments/recover-to-storage?dry_run=${dryRun}&skip=${skip}&limit=${BATCH}`,
          {},
          { timeout: 90000 },
        );
        const d = res.data;
        if (total === null) total = d.total;

        totals.scanned += d.scanned;
        totals.already_in_storage += d.already_in_storage;
        totals.uploaded += d.uploaded;
        totals.missing_everywhere += d.missing_everywhere;
        totals.errors += d.errors;
        ['quotes', 'quote_history'].forEach(c => {
          totals.by_collection[c].scanned += d.by_collection[c].scanned;
          totals.by_collection[c].ok += d.by_collection[c].ok;
          totals.by_collection[c].uploaded += d.by_collection[c].uploaded;
          totals.by_collection[c].missing += d.by_collection[c].missing;
        });
        totals.missing_details = [...totals.missing_details, ...(d.missing_details || [])];
        totals.error_details = [...totals.error_details, ...(d.error_details || [])];

        setRecoveryProgress({ processed: d.processed_so_far, total: d.total });

        if (d.done) break;
        skip = d.next_skip;
        if (skip == null) break;
      }

      const finalMsg = `${dryRun ? '[DRY-RUN] ' : ''}` +
        `Escaneados: ${totals.scanned} | Ya en storage: ${totals.already_in_storage} | ` +
        `${dryRun ? 'A subir' : 'Subidos'}: ${totals.uploaded} | ` +
        `Sin archivo: ${totals.missing_everywhere} | Errores: ${totals.errors}`;

      setRecoveryResult({
        dry_run: dryRun,
        ...totals,
        missing_details_total: totals.missing_details.length,
        missing_details: totals.missing_details.slice(0, 50),
        message: finalMsg,
      });
      toast.success(finalMsg);
    } catch (e) {
      toast.error(`Error en auto-recuperación: ${e.response?.data?.detail || e.message}`);
    } finally {
      setRecovering(false);
      setRecoveryProgress(null);
    }
  };

  const handleExportData = async () => {
    setDownloadingData(true);
    try {
      await authedDownload(
        '/admin/quotes-bundle-migration/export-data',
        'quotes_bundle_data.json',
      );
      toast.success('Archivo de datos descargado');
    } catch (e) {
      toast.error(`Error al exportar datos: ${e.message}`);
    } finally {
      setDownloadingData(false);
    }
  };

  const handleExportAttachments = async () => {
    setDownloadingZip(true);
    try {
      await authedDownload(
        '/admin/quotes-bundle-migration/export-attachments',
        'quotes_bundle_attachments.zip',
      );
      toast.success('ZIP de anexos descargado');
    } catch (e) {
      toast.error(`Error al exportar anexos: ${e.message}`);
    } finally {
      setDownloadingZip(false);
    }
  };

  const handlePreview = async () => {
    const f = previewFileRef.current?.files?.[0];
    if (!f) {
      toast.error('Seleccione el archivo JSON de datos');
      return;
    }
    setPreviewing(true);
    try {
      const fd = new FormData();
      fd.append('file', f);
      const res = await api.post('/admin/quotes-bundle-migration/import-preview', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setPreviewSummary(res.data);
      toast.success('Vista previa generada');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error en vista previa');
      setPreviewSummary(null);
    } finally {
      setPreviewing(false);
    }
  };

  const handleImportData = async () => {
    const files = Array.from(dataFileRef.current?.files || []);
    if (files.length === 0) {
      toast.error('Seleccione uno o más archivos JSON de datos');
      return;
    }
    if (!confirm(
      `Esto aplicará un UPSERT sobre cotizaciones, históricos y proyectos usando ` +
      `${files.length} archivo(s):\n\n` +
      '• Los registros existentes se actualizarán con los datos del archivo.\n' +
      '• Los registros nuevos se crearán.\n' +
      '• Los archivos se importan en orden, de forma automática (idempotente).\n\n' +
      '¿Confirma proceder?'
    )) return;

    setImportingData(true);
    setDataResult(null);
    // Acumulador por colección para mostrar el total combinado de todos los archivos.
    const aggMap = {}; // collection -> { label, inserted, updated, skipped }
    let okFiles = 0;
    const fileErrors = [];

    try {
      // Orden estable por nombre (page_1, page_2, ...) para reproducibilidad.
      const ordered = [...files].sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
      for (let i = 0; i < ordered.length; i++) {
        const f = ordered[i];
        setImportProgress({ current: i + 1, total: ordered.length, fileName: f.name });
        try {
          const fd = new FormData();
          fd.append('file', f);
          const res = await api.post('/admin/quotes-bundle-migration/import-data', fd, {
            headers: { 'Content-Type': 'multipart/form-data' },
          });
          okFiles += 1;
          for (const r of (res.data?.results || [])) {
            const cur = aggMap[r.collection] || { label: r.label, collection: r.collection, inserted: 0, updated: 0, skipped: 0 };
            cur.inserted += r.inserted || 0;
            cur.updated += r.updated || 0;
            cur.skipped += r.skipped || 0;
            aggMap[r.collection] = cur;
          }
        } catch (e) {
          fileErrors.push(`${f.name}: ${e.response?.data?.detail || e.message}`);
        }
      }

      const results = Object.values(aggMap);
      const totals = {
        inserted: results.reduce((a, r) => a + r.inserted, 0),
        updated: results.reduce((a, r) => a + r.updated, 0),
        skipped: results.reduce((a, r) => a + r.skipped, 0),
      };
      setDataResult({
        results,
        totals,
        files_ok: okFiles,
        files_total: ordered.length,
        file_errors: fileErrors,
        message:
          `Importación de ${okFiles}/${ordered.length} archivo(s) completada: ` +
          `${totals.inserted} creado(s), ${totals.updated} actualizado(s), ${totals.skipped} omitido(s).`,
      });
      if (fileErrors.length) {
        toast.error(`${fileErrors.length} archivo(s) con error. Revise el detalle.`);
      } else {
        toast.success(`${okFiles} archivo(s) importado(s) correctamente`);
      }
    } finally {
      setImportingData(false);
      setImportProgress(null);
    }
  };

  const handleImportAttachments = async () => {
    const f = zipFileRef.current?.files?.[0];
    if (!f) {
      toast.error('Seleccione el archivo ZIP de anexos');
      return;
    }
    setImportingZip(true);
    setZipResult(null);
    setZipProgress('Leyendo ZIP local...');
    try {
      // Extraer el ZIP en el browser con JSZip y subir cada archivo
      // individualmente. Inmune al límite de tamaño del ingress (que rechaza
      // uploads grandes con 413) y al timeout del proxy.
      const zip = await JSZip.loadAsync(f);
      const entries = [];
      zip.forEach((relPath, entry) => {
        if (entry.dir) return;
        if (relPath === 'manifest.json') return;
        // Normalizar path para el backend (siempre forward-slash)
        const norm = relPath.replace(/\\/g, '/');
        if (norm.split('/').includes('..')) return;
        entries.push({ relPath: norm, entry });
      });
      const total = entries.length;
      if (total === 0) {
        toast.error('El ZIP no contiene archivos restaurables');
        return;
      }

      // Subida con reintentos automáticos para sobrevivir a 502/504 y errores
      // de red transitorios típicos del ingress en producción. Sin reintentos
      // muchos anexos fallaban silenciosamente con "skipped".
      const MAX_RETRIES = 3;
      const BACKOFF_MS = [500, 1500, 3500];
      const uploadOne = async ({ relPath, entry }) => {
        let lastErr = null;
        for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
          try {
            const blob = await entry.async('blob');
            const fd = new FormData();
            fd.append('path', relPath);
            fd.append('file', blob, relPath.split('/').pop() || 'file.bin');
            await api.post('/admin/quotes-bundle-migration/import-attachment', fd, {
              headers: { 'Content-Type': 'multipart/form-data' },
              timeout: 60000,
            });
            return { ok: true, path: relPath, retries: attempt };
          } catch (err) {
            lastErr = err;
            const status = err.response?.status;
            // 4xx (excepto 408/429) NO reintentamos — es error de cliente.
            if (status && status >= 400 && status < 500 && status !== 408 && status !== 429) {
              return { ok: false, path: relPath, error: err.response?.data?.detail || err.message, retries: attempt };
            }
            if (attempt < MAX_RETRIES) {
              await new Promise((r) => setTimeout(r, BACKOFF_MS[attempt] || 3500));
            }
          }
        }
        return { ok: false, path: relPath, error: lastErr?.response?.data?.detail || lastErr?.message || 'unknown', retries: MAX_RETRIES };
      };

      let restored = 0;
      let skipped = 0;
      let retriedCount = 0;
      const errors = [];
      // Concurrencia controlada: 4 uploads simultáneos es buen balance entre
      // velocidad e impacto en el ingress (evita gateway timeouts por overload).
      const CONCURRENCY = 4;
      let cursor = 0;
      let done = 0;

      const worker = async () => {
        while (true) {
          const i = cursor++;
          if (i >= total) return;
          const item = entries[i];
          setZipProgress(`Subiendo ${done + 1}/${total} · ${item.relPath.slice(-40)}`);
          const res = await uploadOne(item);
          done += 1;
          if (res.ok) {
            restored += 1;
            if (res.retries > 0) retriedCount += 1;
          } else {
            skipped += 1;
            errors.push({ path: res.path, error: res.error });
          }
          setZipProgress(`Subiendo ${done}/${total} (${restored} OK · ${skipped} fallidos)`);
        }
      };
      await Promise.all(Array.from({ length: Math.min(CONCURRENCY, total) }, worker));

      const result = {
        module: 'quotes-bundle-attachments',
        restored,
        skipped,
        retried: retriedCount,
        errors: errors.slice(0, 50),
        message: `Restauración completada: ${restored} restaurado(s), ${skipped} fallido(s)${retriedCount ? `, ${retriedCount} requirió reintento` : ''}.`,
      };
      setZipResult(result);
      if (restored > 0 && skipped === 0) toast.success(result.message);
      else if (skipped > 0 && restored > 0) toast.warning(result.message);
      else toast.error(result.message);
    } catch (e) {
      toast.error(e.response?.data?.detail || e.message || 'Error al restaurar anexos');
    } finally {
      setImportingZip(false);
      setZipProgress('');
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent
        className="max-w-3xl max-h-[88vh] overflow-y-auto"
        data-testid="quotes-bundle-migration-modal"
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            <Database size={20} className="text-indigo-600" />
            Migración de Cotizaciones (Exportar / Importar)
          </DialogTitle>
          <p className="text-xs text-slate-500 mt-1">
            Exporta o importa cotizaciones activas, histórico y proyectos derivados.
            Los anexos viajan en un ZIP separado para no inflar el JSON.
          </p>
        </DialogHeader>

        <div className="bg-amber-50 border border-amber-200 rounded p-3 text-xs text-amber-900 flex items-start gap-2 mt-2">
          <AlertTriangle size={14} className="text-amber-600 mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold">Acceso restringido a Administradores del Sistema.</p>
            <p>Al importar, los registros existentes se actualizarán (UPSERT por id). Los registros nuevos se crearán. No se elimina nada.</p>
          </div>
        </div>

        <Tabs defaultValue="export" className="mt-3">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="export" data-testid="bundle-tab-export">
              <Download size={14} className="mr-1.5" /> Exportar
            </TabsTrigger>
            <TabsTrigger value="import" data-testid="bundle-tab-import">
              <Upload size={14} className="mr-1.5" /> Importar
            </TabsTrigger>
          </TabsList>

          {/* ============== EXPORT ============== */}
          <TabsContent value="export" className="space-y-3 pt-3">
            <div className="rounded-lg border p-4 bg-slate-50">
              <div className="flex items-start gap-3">
                <FileJson size={20} className="text-blue-600 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-semibold text-slate-800">1. Datos (JSON)</p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Cotizaciones + Histórico + Proyectos. No incluye archivos
                    binarios — descárguelos en el paso 2.
                  </p>
                </div>
                <Button
                  size="sm"
                  onClick={handleExportData}
                  disabled={downloadingData}
                  data-testid="bundle-export-data-btn"
                  className="bg-blue-600 hover:bg-blue-700"
                >
                  {downloadingData ? <Loader2 size={14} className="animate-spin mr-1" /> : <Download size={14} className="mr-1" />}
                  Descargar JSON
                </Button>
              </div>
            </div>

            <div className="rounded-lg border p-4 bg-slate-50">
              <div className="flex items-start gap-3">
                <FileArchive size={20} className="text-emerald-600 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-semibold text-slate-800">2. Anexos (ZIP)</p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Bundle con todos los PDFs y archivos referenciados. Puede
                    tomar varios segundos según el volumen.
                  </p>
                </div>
                <Button
                  size="sm"
                  onClick={handleExportAttachments}
                  disabled={downloadingZip}
                  data-testid="bundle-export-attachments-btn"
                  className="bg-emerald-600 hover:bg-emerald-700"
                >
                  {downloadingZip ? <Loader2 size={14} className="animate-spin mr-1" /> : <FolderOpen size={14} className="mr-1" />}
                  Descargar ZIP
                </Button>
              </div>
            </div>
          </TabsContent>

          {/* ============== IMPORT ============== */}
          <TabsContent value="import" className="space-y-3 pt-3">
            {/* PREVIEW */}
            <div className="rounded-lg border p-4 bg-slate-50">
              <p className="text-sm font-semibold text-slate-800 mb-1.5">Vista previa (opcional)</p>
              <p className="text-xs text-slate-500 mb-2">
                Sube el JSON para ver cuántos registros se crearán o actualizarán antes de aplicar.
              </p>
              <div className="flex gap-2">
                <input
                  ref={previewFileRef}
                  type="file"
                  accept=".json,application/json"
                  className="flex-1 text-xs file:mr-2 file:py-1 file:px-2 file:border-0 file:bg-slate-200 file:text-slate-700"
                  data-testid="bundle-preview-file-input"
                />
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handlePreview}
                  disabled={previewing}
                  data-testid="bundle-preview-btn"
                >
                  {previewing ? <Loader2 size={14} className="animate-spin mr-1" /> : <Database size={14} className="mr-1" />}
                  Analizar
                </Button>
              </div>
              {previewSummary && (
                <div className="mt-3 bg-white border rounded p-3 text-xs">
                  <p className="text-slate-600 mb-1">
                    Exportado: <span className="font-mono">{previewSummary.exported_at?.substring(0, 19)}</span>
                    {previewSummary.exported_by && <> · por <b>{previewSummary.exported_by}</b></>}
                  </p>
                  <table className="w-full mt-1.5">
                    <thead>
                      <tr className="text-[10px] text-slate-500 uppercase">
                        <th className="text-left py-1">Colección</th>
                        <th className="text-right py-1">En archivo</th>
                        <th className="text-right py-1 text-emerald-700">Crear</th>
                        <th className="text-right py-1 text-blue-700">Actualizar</th>
                      </tr>
                    </thead>
                    <tbody>
                      {previewSummary.summary?.map((s) => (
                        <tr key={s.collection} className="border-t border-slate-100">
                          <td className="py-1">{s.label}</td>
                          <td className="py-1 text-right font-mono">{s.total_in_file}</td>
                          <td className="py-1 text-right font-mono text-emerald-700">{s.to_create}</td>
                          <td className="py-1 text-right font-mono text-blue-700">{s.to_update}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* IMPORT DATA */}
            <div className="rounded-lg border p-4 bg-slate-50">
              <div className="flex items-start gap-3">
                <FileJson size={20} className="text-blue-600 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-semibold text-slate-800">1. Importar datos (JSON)</p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    UPSERT por id natural en las 3 colecciones. Puede seleccionar <strong>varios archivos
                    paginados a la vez</strong> (page_1, page_2, …) y se importan automáticamente en orden.
                  </p>
                </div>
              </div>
              <div className="flex gap-2 mt-2">
                <input
                  ref={dataFileRef}
                  type="file"
                  multiple
                  accept=".json,application/json"
                  className="flex-1 text-xs file:mr-2 file:py-1 file:px-2 file:border-0 file:bg-slate-200 file:text-slate-700"
                  data-testid="bundle-import-data-file-input"
                />
                <Button
                  size="sm"
                  onClick={handleImportData}
                  disabled={importingData}
                  data-testid="bundle-import-data-btn"
                  className="bg-blue-600 hover:bg-blue-700"
                >
                  {importingData ? <Loader2 size={14} className="animate-spin mr-1" /> : <Upload size={14} className="mr-1" />}
                  Aplicar
                </Button>
              </div>
              {importProgress && (
                <div className="mt-2" data-testid="bundle-import-progress">
                  <div className="flex justify-between text-[11px] text-slate-500 mb-1">
                    <span>Importando {importProgress.fileName}</span>
                    <span>{importProgress.current} / {importProgress.total}</span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-600 transition-all duration-300"
                      style={{ width: `${Math.round((importProgress.current / importProgress.total) * 100)}%` }}
                    />
                  </div>
                </div>
              )}
              {dataResult && (
                <div className="mt-3 bg-white border rounded p-3 text-xs">
                  <p className="text-emerald-700 font-semibold flex items-center gap-1.5">
                    <CheckCircle2 size={14} /> {dataResult.message}
                  </p>
                  <table className="w-full mt-1.5">
                    <thead>
                      <tr className="text-[10px] text-slate-500 uppercase">
                        <th className="text-left py-1">Colección</th>
                        <th className="text-right py-1 text-emerald-700">Creados</th>
                        <th className="text-right py-1 text-blue-700">Actualizados</th>
                        <th className="text-right py-1 text-rose-700">Omitidos</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dataResult.results?.map((r) => (
                        <tr key={r.collection} className="border-t border-slate-100">
                          <td className="py-1">{r.label}</td>
                          <td className="py-1 text-right font-mono text-emerald-700">{r.inserted}</td>
                          <td className="py-1 text-right font-mono text-blue-700">{r.updated}</td>
                          <td className="py-1 text-right font-mono text-rose-700">{r.skipped}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {dataResult.file_errors?.length > 0 && (
                    <div className="mt-2 text-[11px] text-rose-700" data-testid="bundle-import-file-errors">
                      <p className="font-semibold">Archivos con error ({dataResult.file_errors.length}):</p>
                      <ul className="list-disc ml-4">
                        {dataResult.file_errors.map((er, idx) => <li key={idx}>{er}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* IMPORT ATTACHMENTS */}
            <div className="rounded-lg border p-4 bg-slate-50">
              <div className="flex items-start gap-3">
                <FileArchive size={20} className="text-emerald-600 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-semibold text-slate-800">2. Restaurar anexos (ZIP)</p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Descomprime el ZIP en tu navegador y sube cada archivo individualmente
                    al Object Storage. Inmune a límites de tamaño del proxy (ingress).
                  </p>
                </div>
              </div>
              <div className="flex gap-2 mt-2">
                <input
                  ref={zipFileRef}
                  type="file"
                  accept=".zip,application/zip"
                  className="flex-1 text-xs file:mr-2 file:py-1 file:px-2 file:border-0 file:bg-slate-200 file:text-slate-700"
                  data-testid="bundle-import-attachments-file-input"
                />
                <Button
                  size="sm"
                  onClick={handleImportAttachments}
                  disabled={importingZip}
                  data-testid="bundle-import-attachments-btn"
                  className="bg-emerald-600 hover:bg-emerald-700"
                >
                  {importingZip ? <Loader2 size={14} className="animate-spin mr-1" /> : <Upload size={14} className="mr-1" />}
                  {importingZip ? (zipProgress || 'Restaurando...') : 'Restaurar'}
                </Button>
              </div>
              {zipResult && (
                <div className="mt-3 bg-white border rounded p-3 text-xs">
                  <p className="text-emerald-700 font-semibold flex items-center gap-1.5">
                    <CheckCircle2 size={14} /> {zipResult.message}
                  </p>
                  <p className="text-slate-600 mt-1">
                    Restaurados: <b className="text-emerald-700">{zipResult.restored}</b> · Omitidos: <b className="text-rose-700">{zipResult.skipped}</b>
                  </p>
                </div>
              )}
            </div>

            {/* AUTO-RECOVERY: anexos en FS local → Object Storage */}
            <div className="rounded-lg border p-4 bg-indigo-50/40 border-indigo-200">
              <div className="flex items-start gap-3">
                <ShieldCheck size={20} className="text-indigo-600 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-semibold text-slate-800">3. Auto-recuperación de anexos al Object Storage</p>
                  <p className="text-xs text-slate-600 mt-0.5">
                    Audita todos los anexos referenciados en BD (<b>cotizaciones</b> + <b>histórico</b>) y sube al Object Storage
                    los que solo existen en disco local. Garantiza disponibilidad cross-deploy en Producción.
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2 mt-3">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleRecoverToStorage(true)}
                  disabled={recovering}
                  data-testid="attachment-recovery-dryrun-btn"
                  className="border-indigo-300 text-indigo-700 hover:bg-indigo-100"
                >
                  {recovering ? <Loader2 size={14} className="animate-spin mr-1" /> : null}
                  Auditar (Dry-Run)
                </Button>
                <Button
                  size="sm"
                  onClick={() => handleRecoverToStorage(false)}
                  disabled={recovering}
                  data-testid="attachment-recovery-execute-btn"
                  className="bg-indigo-600 hover:bg-indigo-700"
                >
                  {recovering ? <Loader2 size={14} className="animate-spin mr-1" /> : <Upload size={14} className="mr-1" />}
                  Ejecutar Recuperación
                </Button>
              </div>
              {recoveryProgress && (
                <div className="mt-3 bg-white border rounded p-3 text-xs">
                  <div className="flex justify-between mb-1">
                    <span className="text-slate-700">Procesando lote a lote…</span>
                    <span className="font-mono text-indigo-700">
                      {recoveryProgress.processed} / {recoveryProgress.total}
                    </span>
                  </div>
                  <div className="w-full bg-slate-200 rounded-full h-2">
                    <div
                      className="bg-indigo-600 h-2 rounded-full transition-all"
                      style={{ width: `${Math.min(100, (recoveryProgress.processed / Math.max(1, recoveryProgress.total)) * 100)}%` }}
                    />
                  </div>
                </div>
              )}
              {recoveryResult && (
                <div className="mt-3 bg-white border rounded p-3 text-xs space-y-2">
                  <p className={`font-semibold flex items-center gap-1.5 ${recoveryResult.missing_everywhere > 0 ? 'text-amber-700' : 'text-emerald-700'}`}>
                    <CheckCircle2 size={14} /> {recoveryResult.message}
                  </p>
                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs">
                    <div className="bg-slate-50 rounded p-2">
                      <div className="text-slate-500">Escaneados</div>
                      <div className="text-base font-bold text-slate-800">{recoveryResult.scanned}</div>
                    </div>
                    <div className="bg-emerald-50 rounded p-2">
                      <div className="text-emerald-700">Ya en storage</div>
                      <div className="text-base font-bold text-emerald-800">{recoveryResult.already_in_storage}</div>
                    </div>
                    <div className="bg-indigo-50 rounded p-2">
                      <div className="text-indigo-700">{recoveryResult.dry_run ? 'Por subir' : 'Subidos'}</div>
                      <div className="text-base font-bold text-indigo-800">{recoveryResult.uploaded}</div>
                    </div>
                    <div className="bg-amber-50 rounded p-2">
                      <div className="text-amber-700">Sin archivo</div>
                      <div className="text-base font-bold text-amber-800">{recoveryResult.missing_everywhere}</div>
                    </div>
                    <div className="bg-rose-50 rounded p-2">
                      <div className="text-rose-700">Errores</div>
                      <div className="text-base font-bold text-rose-800">{recoveryResult.errors}</div>
                    </div>
                  </div>
                  {recoveryResult.missing_details_total > 0 && (
                    <details className="mt-2">
                      <summary className="cursor-pointer text-amber-700 font-medium">
                        Ver primeros {Math.min(recoveryResult.missing_details_total, 50)} de {recoveryResult.missing_details_total} anexos sin archivo
                      </summary>
                      <div className="max-h-40 overflow-y-auto mt-2 border rounded">
                        <table className="w-full text-xs">
                          <thead className="bg-slate-100 sticky top-0">
                            <tr>
                              <th className="text-left px-2 py-1">Origen</th>
                              <th className="text-left px-2 py-1">N° Cot</th>
                              <th className="text-left px-2 py-1">Archivo</th>
                              <th className="text-left px-2 py-1">Path</th>
                            </tr>
                          </thead>
                          <tbody>
                            {recoveryResult.missing_details.map((m, i) => (
                              <tr key={i} className="border-t">
                                <td className="px-2 py-1 text-slate-700">{m.collection}</td>
                                <td className="px-2 py-1 font-mono text-slate-600">{m.parent_number || '—'}</td>
                                <td className="px-2 py-1 text-slate-700">{m.filename || '—'}</td>
                                <td className="px-2 py-1 font-mono text-slate-500 truncate max-w-[200px]" title={m.rel_path}>{m.rel_path}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </details>
                  )}
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}

export default QuotesBundleMigrationModal;
