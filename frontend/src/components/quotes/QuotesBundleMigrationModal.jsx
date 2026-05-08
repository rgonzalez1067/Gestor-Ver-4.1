import { useState, useRef } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../ui/tabs';
import {
  Database, Download, Upload, FileJson, FileArchive, Loader2,
  AlertTriangle, CheckCircle2, FolderOpen,
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
  const [importingZip, setImportingZip] = useState(false);
  const [zipProgress, setZipProgress] = useState('');
  const [previewSummary, setPreviewSummary] = useState(null);
  const [dataResult, setDataResult] = useState(null);
  const [zipResult, setZipResult] = useState(null);
  const dataFileRef = useRef(null);
  const zipFileRef = useRef(null);
  const previewFileRef = useRef(null);

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
    const f = dataFileRef.current?.files?.[0];
    if (!f) {
      toast.error('Seleccione el archivo JSON de datos');
      return;
    }
    if (!confirm(
      'Esto aplicará un UPSERT sobre las cotizaciones, históricos y proyectos:\n\n' +
      '• Los registros existentes se actualizarán con los datos del archivo.\n' +
      '• Los registros nuevos se crearán.\n\n' +
      '¿Confirma proceder?'
    )) return;
    setImportingData(true);
    try {
      const fd = new FormData();
      fd.append('file', f);
      const res = await api.post('/admin/quotes-bundle-migration/import-data', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setDataResult(res.data);
      toast.success(res.data.message || 'Importación completada');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error al importar datos');
    } finally {
      setImportingData(false);
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
        if (relPath.split('/').includes('..')) return;
        entries.push({ relPath, entry });
      });
      const total = entries.length;
      if (total === 0) {
        toast.error('El ZIP no contiene archivos restaurables');
        return;
      }
      let restored = 0;
      let skipped = 0;
      const errors = [];
      for (let i = 0; i < total; i++) {
        const { relPath, entry } = entries[i];
        setZipProgress(`Subiendo ${i + 1}/${total} · ${relPath.slice(-40)}`);
        try {
          const blob = await entry.async('blob');
          const fd = new FormData();
          fd.append('path', relPath);
          fd.append('file', blob, relPath.split('/').pop() || 'file.bin');
          await api.post('/admin/quotes-bundle-migration/import-attachment', fd, {
            headers: { 'Content-Type': 'multipart/form-data' },
          });
          restored += 1;
        } catch (err) {
          skipped += 1;
          errors.push({ path: relPath, error: err.response?.data?.detail || err.message });
        }
      }
      const result = {
        module: 'quotes-bundle-attachments',
        restored,
        skipped,
        errors: errors.slice(0, 20),
        message: `Restauración completada: ${restored} archivo(s) restaurado(s), ${skipped} omitido(s).`,
      };
      setZipResult(result);
      if (restored > 0) toast.success(result.message);
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
                  <p className="text-xs text-slate-500 mt-0.5">UPSERT por id natural en las 3 colecciones.</p>
                </div>
              </div>
              <div className="flex gap-2 mt-2">
                <input
                  ref={dataFileRef}
                  type="file"
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
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}

export default QuotesBundleMigrationModal;
