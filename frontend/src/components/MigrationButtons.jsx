import { useRef, useState } from 'react';
import { Button } from './ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from './ui/alert-dialog';
import { Download, Upload, Database } from 'lucide-react';
import { toast } from 'sonner';
import api from '../utils/api';

/**
 * Botones admin para Exportar/Importar datos del módulo entre ambientes.
 * Usa endpoints /api/admin/migration/{module}/{export|import-preview|import-apply}
 *
 * Props:
 *   - module: 'banks' | 'payment-methods' | 'hardware' | 'commercial-categories'
 *   - label:  Nombre legible del módulo (ej. "Bancos")
 *   - onImported?: callback tras import exitoso (refresca lista)
 */
export const MigrationButtons = ({ module, label, onImported }) => {
  const fileInputRef = useRef(null);
  const [preview, setPreview] = useState(null); // { to_create_count, to_update_count, ... }
  const [pendingFile, setPendingFile] = useState(null);
  const [busy, setBusy] = useState(false);

  // Solo admin
  const userStr = localStorage.getItem('user');
  let isAdmin = false;
  try {
    isAdmin = userStr && JSON.parse(userStr)?.role === 'admin';
  } catch {
    isAdmin = false;
  }
  if (!isAdmin) return null;

  const handleExport = async () => {
    setBusy(true);
    try {
      const res = await api.get(`/admin/migration/${module}/export`, { responseType: 'blob' });
      const blob = new Blob([res.data], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '').slice(0, 15);
      a.download = `${module}_export_${ts}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success(`${label} exportados correctamente`);
    } catch (err) {
      toast.error(`Error al exportar: ${err.response?.data?.detail || err.message}`);
    } finally {
      setBusy(false);
    }
  };

  const handleFilePicked = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = ''; // permitir re-seleccionar el mismo archivo
    if (!file) return;
    if (!file.name.endsWith('.json')) {
      toast.error('Solo se permiten archivos .json');
      return;
    }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await api.post(`/admin/migration/${module}/import-preview`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setPreview(res.data);
      setPendingFile(file);
    } catch (err) {
      toast.error(`Archivo inválido: ${err.response?.data?.detail || err.message}`);
      setPreview(null);
      setPendingFile(null);
    } finally {
      setBusy(false);
    }
  };

  const handleConfirmImport = async () => {
    if (!pendingFile) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append('file', pendingFile);
      const res = await api.post(`/admin/migration/${module}/import-apply`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const { inserted, updated, skipped } = res.data;
      toast.success(`Migración OK: ${inserted} creado(s), ${updated} actualizado(s)${skipped ? `, ${skipped} omitido(s)` : ''}`);
      setPreview(null);
      setPendingFile(null);
      if (onImported) onImported();
    } catch (err) {
      toast.error(`Error al importar: ${err.response?.data?.detail || err.message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        accept="application/json,.json"
        className="hidden"
        onChange={handleFilePicked}
        data-testid={`migration-import-input-${module}`}
      />
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-amber-200 bg-amber-50">
        <Database className="w-4 h-4 text-amber-700" />
        <span className="text-xs font-semibold text-amber-800 mr-1">Migración (Admin):</span>
        <Button
          variant="outline"
          size="sm"
          onClick={handleExport}
          disabled={busy}
          className="border-amber-300 text-amber-800 hover:bg-amber-100"
          data-testid={`migration-export-btn-${module}`}
        >
          <Download className="w-4 h-4 mr-1" /> Exportar
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => fileInputRef.current?.click()}
          disabled={busy}
          className="border-amber-300 text-amber-800 hover:bg-amber-100"
          data-testid={`migration-import-btn-${module}`}
        >
          <Upload className="w-4 h-4 mr-1" /> Importar
        </Button>
      </div>

      <AlertDialog open={!!preview} onOpenChange={(o) => { if (!o) { setPreview(null); setPendingFile(null); } }}>
        <AlertDialogContent data-testid={`migration-preview-dialog-${module}`}>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirmar importación de {label}</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3 text-sm">
                {preview && (
                  <>
                    <div className="bg-slate-50 rounded-lg p-3 border border-slate-200 space-y-1">
                      <div className="break-words"><strong>Archivo:</strong> {pendingFile?.name}</div>
                      {preview.exported_at && (
                        <div className="text-xs text-slate-600">
                          Exportado: {new Date(preview.exported_at).toLocaleString()} por {preview.exported_by || 'desconocido'}
                        </div>
                      )}
                      <div><strong>Total en archivo:</strong> {preview.total_in_file}</div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="bg-emerald-50 rounded-lg p-3 border border-emerald-200">
                        <div className="text-2xl font-bold text-emerald-700" data-testid={`migration-preview-create-count-${module}`}>
                          {preview.to_create_count}
                        </div>
                        <div className="text-xs text-emerald-800">Se CREARÁN (nuevos)</div>
                      </div>
                      <div className="bg-sky-50 rounded-lg p-3 border border-sky-200">
                        <div className="text-2xl font-bold text-sky-700" data-testid={`migration-preview-update-count-${module}`}>
                          {preview.to_update_count}
                        </div>
                        <div className="text-xs text-sky-800">Se ACTUALIZARÁN (existentes)</div>
                      </div>
                    </div>
                    {preview.invalid_count > 0 && (
                      <div className="bg-rose-50 border border-rose-200 rounded-lg p-2 text-xs text-rose-800">
                        ⚠️ {preview.invalid_count} registro(s) sin id válido serán omitidos.
                      </div>
                    )}
                    {preview.duplicates_in_file?.length > 0 && (
                      <div className="bg-amber-50 border border-amber-200 rounded-lg p-2 text-xs text-amber-800">
                        ⚠️ {preview.duplicates_in_file.length} id(s) duplicados dentro del archivo (solo el primero contará).
                      </div>
                    )}
                    <div className="text-xs text-slate-500">
                      Esta acción es <strong>idempotente</strong>: existentes se actualizan por su id natural, nuevos se crean. ¿Aplicar?
                    </div>
                  </>
                )}
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid={`migration-preview-cancel-${module}`}>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmImport}
              disabled={busy}
              className="bg-amber-600 hover:bg-amber-700"
              data-testid={`migration-preview-confirm-${module}`}
            >
              Aplicar importación
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};

export default MigrationButtons;
