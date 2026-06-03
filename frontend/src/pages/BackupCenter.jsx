import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { ArrowLeft, Download, Upload, DatabaseBackup, Package, ShieldAlert, Loader2 } from 'lucide-react';
import api from '../utils/api';
import { Button } from '../components/ui/button';
import { Checkbox } from '../components/ui/checkbox';
import { Badge } from '../components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../components/ui/dialog';

const downloadBlob = (data, filename, type) => {
  const blob = new Blob([data], { type });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
};

const tsNow = () => new Date().toISOString().slice(0, 19).replace(/[:T]/g, '').slice(0, 15);

export default function BackupCenter() {
  const navigate = useNavigate();
  const [entities, setEntities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(new Set());
  const [busyZip, setBusyZip] = useState(false);
  const [importTarget, setImportTarget] = useState(null); // entity row
  const fileRef = useRef(null);

  const loadEntities = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/admin/backup-center/entities');
      setEntities(data.entities || []);
    } catch (err) {
      toast.error(`No se pudieron cargar las entidades: ${err.response?.data?.detail || err.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadEntities(); }, [loadEntities]);

  const allSelected = entities.length > 0 && selected.size === entities.length;
  const someSelected = selected.size > 0 && !allSelected;

  const toggleAll = () => {
    setSelected(allSelected ? new Set() : new Set(entities.map((e) => e.module)));
  };
  const toggleOne = (module) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(module)) next.delete(module); else next.add(module);
      return next;
    });
  };

  const handleExportOne = async (entity) => {
    try {
      const res = await api.get(`/admin/migration/${entity.module}/export`, { responseType: 'blob' });
      downloadBlob(res.data, `${entity.module}_export_${tsNow()}.json`, 'application/json');
      toast.success(`${entity.label} exportado correctamente`);
    } catch (err) {
      toast.error(`Error al exportar ${entity.label}: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleExportSelected = async () => {
    if (selected.size === 0) {
      toast.error('Seleccione al menos una entidad para exportar');
      return;
    }
    setBusyZip(true);
    try {
      const res = await api.post(
        '/admin/backup-center/export-zip',
        { modules: Array.from(selected) },
        { responseType: 'blob' },
      );
      downloadBlob(res.data, `backup_center_${tsNow()}.zip`, 'application/zip');
      toast.success(`Respaldo de ${selected.size} entidad(es) generado en ZIP`);
    } catch (err) {
      toast.error(`Error en la exportación masiva: ${err.response?.data?.detail || err.message}`);
    } finally {
      setBusyZip(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50" data-testid="backup-center-page">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
        {/* Header */}
        <button
          onClick={() => navigate('/settings')}
          className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 transition-colors mb-4"
          data-testid="backup-center-back"
        >
          <ArrowLeft size={16} /> Volver a Configuración
        </button>

        <div className="flex items-start gap-3 mb-2">
          <div className="rounded-xl bg-indigo-600 text-white p-2.5 shadow-sm">
            <DatabaseBackup size={22} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 font-manrope">Centro de Respaldos</h1>
            <p className="text-sm text-slate-600 max-w-2xl mt-0.5">
              Exporta (Backup) e importa (Restauración) los datos maestros del sistema. La importación
              actualiza registros existentes y crea los nuevos (upsert), sin borrar el resto.
            </p>
          </div>
        </div>

        <div className="flex items-start gap-2 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 px-3 py-2 text-xs my-4">
          <ShieldAlert size={15} className="shrink-0 mt-0.5" />
          <span>
            Cotizaciones, Histórico y Proyectos se respaldan en sus propias vistas y no forman parte de
            este centro. Formato de respaldo: <strong>JSON</strong> (round-trip sin pérdida).
          </span>
        </div>

        {/* Acción masiva */}
        <div className="flex items-center justify-between gap-3 mb-3">
          <p className="text-sm text-slate-500" data-testid="backup-selected-count">
            {selected.size} de {entities.length} entidad(es) seleccionada(s)
          </p>
          <Button
            onClick={handleExportSelected}
            disabled={busyZip || selected.size === 0}
            className="bg-indigo-600 hover:bg-indigo-700"
            data-testid="export-selected-btn"
          >
            {busyZip ? <Loader2 size={16} className="mr-1.5 animate-spin" /> : <Package size={16} className="mr-1.5" />}
            Ejecutar Exportación Seleccionados
          </Button>
        </div>

        {/* Grilla */}
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 text-xs uppercase tracking-wide">
                <th className="w-12 px-4 py-3 text-left">
                  <Checkbox
                    checked={allSelected ? true : someSelected ? 'indeterminate' : false}
                    onCheckedChange={toggleAll}
                    data-testid="select-all-checkbox"
                    aria-label="Seleccionar todos"
                  />
                </th>
                <th className="px-2 py-3 text-left font-semibold">Entidad / Base de Datos</th>
                <th className="px-2 py-3 text-left font-semibold w-28">Registros</th>
                <th className="px-4 py-3 text-right font-semibold w-72">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={4} className="px-4 py-10 text-center text-slate-400">
                  <Loader2 size={20} className="animate-spin inline mr-2" /> Cargando entidades…
                </td></tr>
              ) : entities.map((e) => (
                <tr
                  key={e.module}
                  className="border-b border-slate-100 last:border-0 hover:bg-slate-50/60 transition-colors"
                  data-testid={`backup-row-${e.module}`}
                >
                  <td className="px-4 py-3">
                    <Checkbox
                      checked={selected.has(e.module)}
                      onCheckedChange={() => toggleOne(e.module)}
                      data-testid={`row-checkbox-${e.module}`}
                      aria-label={`Seleccionar ${e.label}`}
                    />
                  </td>
                  <td className="px-2 py-3 font-medium text-slate-800">{e.label}</td>
                  <td className="px-2 py-3">
                    <Badge variant="secondary" className="bg-slate-100 text-slate-600">{e.count}</Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        variant="outline" size="sm"
                        onClick={() => handleExportOne(e)}
                        data-testid={`export-row-${e.module}`}
                      >
                        <Download size={14} className="mr-1" /> Exportar
                      </Button>
                      <Button
                        variant="outline" size="sm"
                        className="border-indigo-300 text-indigo-700 hover:bg-indigo-50"
                        onClick={() => setImportTarget(e)}
                        data-testid={`import-row-${e.module}`}
                      >
                        <Upload size={14} className="mr-1" /> Importar / Restaurar
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <ImportDialog
        entity={importTarget}
        onClose={() => setImportTarget(null)}
        onDone={loadEntities}
        fileRef={fileRef}
      />
    </div>
  );
}

function ImportDialog({ entity, onClose, onDone, fileRef }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { setFile(null); setPreview(null); setBusy(false); }, [entity]);

  if (!entity) return null;

  const handleFile = async (e) => {
    const f = e.target.files?.[0];
    if (e.target) e.target.value = '';
    if (!f) return;
    if (!f.name.endsWith('.json')) { toast.error('Solo se permiten archivos .json'); return; }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append('file', f);
      const { data } = await api.post(`/admin/migration/${entity.module}/import-preview`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setPreview(data);
      setFile(f);
    } catch (err) {
      toast.error(`Archivo inválido: ${err.response?.data?.detail || err.message}`);
      setPreview(null); setFile(null);
    } finally {
      setBusy(false);
    }
  };

  const handleApply = async () => {
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const { data } = await api.post(`/admin/migration/${entity.module}/import-apply`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      toast.success(`${entity.label}: ${data.inserted} creado(s), ${data.updated} actualizado(s)${data.skipped ? `, ${data.skipped} omitido(s)` : ''}`);
      onDone?.();
      onClose();
    } catch (err) {
      toast.error(`Error al importar: ${err.response?.data?.detail || err.message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={!!entity} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md" data-testid="import-restore-dialog">
        <DialogHeader>
          <DialogTitle>Importar / Restaurar: {entity.label}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 min-w-0">
          <p className="text-sm text-slate-600">
            Suba el archivo de respaldo <strong>.json</strong> de <strong>{entity.label}</strong>.
            Los registros existentes se actualizarán y los nuevos se crearán (upsert).
          </p>
          <input ref={fileRef} type="file" accept=".json" onChange={handleFile} className="hidden" />
          <Button
            variant="outline"
            onClick={() => fileRef.current?.click()}
            disabled={busy}
            className="w-full justify-start max-w-full"
            title={file ? file.name : undefined}
            data-testid="import-pick-file-btn"
          >
            <Upload size={15} className="mr-1.5 shrink-0" />
            <span className="truncate min-w-0">{file ? file.name : 'Seleccionar archivo .json'}</span>
          </Button>

          {preview && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm" data-testid="import-preview-summary">
              <p className="font-semibold text-slate-700 mb-1">Resumen de la importación</p>
              <ul className="text-slate-600 space-y-0.5">
                <li>A crear: <strong className="text-emerald-600">{preview.to_create_count}</strong></li>
                <li>A actualizar: <strong className="text-blue-600">{preview.to_update_count}</strong></li>
                {preview.exported_at && (
                  <li className="text-xs text-slate-400 mt-1">Respaldo del: {new Date(preview.exported_at).toLocaleString()}</li>
                )}
              </ul>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={busy} data-testid="import-cancel-btn">Cancelar</Button>
          <Button
            onClick={handleApply}
            disabled={busy || !preview}
            className="bg-indigo-600 hover:bg-indigo-700"
            data-testid="import-apply-btn"
          >
            {busy ? <Loader2 size={16} className="mr-1.5 animate-spin" /> : null}
            Aplicar Restauración
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
