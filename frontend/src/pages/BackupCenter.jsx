import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import JSZip from 'jszip';
import { ArrowLeft, Download, Upload, DatabaseBackup, Package, ShieldAlert, Loader2, CloudUpload, CheckCircle2, AlertTriangle, Search } from 'lucide-react';
import api from '../utils/api';
import { Button } from '../components/ui/button';
import { Checkbox } from '../components/ui/checkbox';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
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
  const [bulkImportOpen, setBulkImportOpen] = useState(false);
  const [history, setHistory] = useState([]);
  const fileRef = useRef(null);
  const zipRef = useRef(null);

  // --- Respaldo Total de Base de Datos (todas las colecciones) ---
  const [dbInfo, setDbInfo] = useState(null); // { db_name, total_collections, total_documents }
  const [dbBusy, setDbBusy] = useState(null); // null | 'export' | 'restore'
  const [dbProgress, setDbProgress] = useState(0);
  const [dbRestoreResult, setDbRestoreResult] = useState(null);
  const [dbConfirmOpen, setDbConfirmOpen] = useState(false);
  const [dbFile, setDbFile] = useState(null);
  const [dbExactReplica, setDbExactReplica] = useState(true);
  const [dbConfirmText, setDbConfirmText] = useState('');
  const [dbBackupCols, setDbBackupCols] = useState([]); // [{name, count}] leídas del manifiesto
  const [dbSelectedCols, setDbSelectedCols] = useState(new Set()); // nombres seleccionados
  const [dbParsing, setDbParsing] = useState(false);
  const dbFileRef = useRef(null);

  const dbAllSelected = dbBackupCols.length > 0 && dbSelectedCols.size === dbBackupCols.length;
  const dbIsSelective = dbBackupCols.length > 0 && !dbAllSelected;
  const dbCurrentCountMap = (dbInfo?.collections || []).reduce((acc, c) => { acc[c.name] = c.count; return acc; }, {});

  const openRestoreDialog = async (file) => {
    setDbParsing(true);
    setDbFile(file);
    setDbConfirmText('');
    setDbBackupCols([]);
    setDbSelectedCols(new Set());
    try {
      const zip = await JSZip.loadAsync(file);
      const manifestFile = zip.file('_manifest.json');
      if (!manifestFile) throw new Error('El archivo no es un Respaldo Total (falta _manifest.json)');
      const manifest = JSON.parse(await manifestFile.async('string'));
      if (manifest.type !== 'full-database-backup') throw new Error('El archivo no es un Respaldo Total de Base de Datos');
      const cols = (manifest.collections || []).slice().sort((a, b) => a.name.localeCompare(b.name));
      setDbBackupCols(cols);
      setDbSelectedCols(new Set(cols.map((c) => c.name))); // todo seleccionado por defecto
      setDbConfirmOpen(true);
    } catch (err) {
      toast.error(`No se pudo leer el respaldo: ${err.message}`);
      setDbFile(null);
      if (dbFileRef.current) dbFileRef.current.value = '';
    } finally {
      setDbParsing(false);
    }
  };

  const toggleCol = (name) => {
    setDbSelectedCols((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name); else next.add(name);
      return next;
    });
  };
  const toggleAllCols = () => {
    setDbSelectedCols(dbAllSelected ? new Set() : new Set(dbBackupCols.map((c) => c.name)));
  };

  const loadDbInfo = useCallback(async () => {
    try {
      const { data } = await api.get('/admin/full-backup/info');
      setDbInfo(data);
    } catch (err) {
      // silencioso: la tarjeta sigue usable aunque falle el conteo
    }
  }, []);

  const exportFullDb = async () => {
    setDbBusy('export');
    try {
      // Descarga NATIVA en streaming: el servidor arma el ZIP con memoria O(1)
      // y el navegador lo escribe directo a disco (no acumula en RAM).
      const { data } = await api.post('/admin/full-backup/export-ticket');
      const base = process.env.REACT_APP_BACKEND_URL;
      const url = `${base}/api/admin/full-backup/export?ticket=${encodeURIComponent(data.ticket)}`;
      // Disparar la descarga nativa del navegador
      const a = document.createElement('a');
      a.href = url;
      a.rel = 'noopener';
      document.body.appendChild(a);
      a.click();
      a.remove();
      toast.success('La descarga del respaldo total comenzó (revisa tu carpeta de descargas)');
    } catch (err) {
      toast.error(`Error al iniciar el export: ${err.response?.data?.detail || err.message}`);
    } finally {
      setDbBusy(null);
    }
  };

  const doRestoreFullDb = async () => {
    if (!dbFile || dbSelectedCols.size === 0) return;
    setDbConfirmOpen(false);
    setDbBusy('restore');
    setDbProgress(0);
    setDbRestoreResult(null);
    const CHUNK = 4 * 1024 * 1024; // 4MB por chunk (evita límites del proxy)
    try {
      const { data: initData } = await api.post('/admin/full-backup/upload-init');
      const uploadId = initData.upload_id;
      const totalChunks = Math.max(1, Math.ceil(dbFile.size / CHUNK));
      for (let i = 0; i < totalChunks; i++) {
        const blob = dbFile.slice(i * CHUNK, (i + 1) * CHUNK);
        const fd = new FormData();
        fd.append('upload_id', uploadId);
        fd.append('chunk_index', i);
        fd.append('file', blob, 'chunk.part');
        await api.post('/admin/full-backup/upload-chunk', fd);
        setDbProgress(Math.round(((i + 1) / totalChunks) * 90));
      }
      const fd = new FormData();
      fd.append('upload_id', uploadId);
      fd.append('mode', dbExactReplica ? 'replace' : 'merge');
      // Restauración selectiva: enviar la lista solo si NO están todas seleccionadas.
      if (dbIsSelective) fd.append('collections', JSON.stringify(Array.from(dbSelectedCols)));
      const { data } = await api.post('/admin/full-backup/restore', fd);
      setDbProgress(100);
      setDbRestoreResult(data);
      toast.success(`Restauración completada: ${data.restored_collections} colección(es), ${data.restored_documents} documento(s)`);
      loadDbInfo();
    } catch (err) {
      toast.error(`Error al restaurar: ${err.response?.data?.detail || err.message}`);
    } finally {
      setDbBusy(null);
      setDbFile(null);
      setDbConfirmText('');
      setDbBackupCols([]);
      setDbSelectedCols(new Set());
      if (dbFileRef.current) dbFileRef.current.value = '';
    }
  };

  // --- Backfill de Anexos hacia Object Storage (paginado) ---
  const [backfillBusy, setBackfillBusy] = useState(false);
  const [backfillMode, setBackfillMode] = useState(null); // 'audit' | 'upload'
  const [backfillProgress, setBackfillProgress] = useState(0); // 0..100
  const [backfillResult, setBackfillResult] = useState(null); // contadores acumulados
  const backfillCancelRef = useRef(false);

  const runBackfill = async (dryRun) => {
    setBackfillBusy(true);
    setBackfillMode(dryRun ? 'audit' : 'upload');
    setBackfillProgress(0);
    setBackfillResult(null);
    backfillCancelRef.current = false;

    const acc = {
      total: 0, scanned: 0, already_in_storage: 0, uploaded: 0,
      missing_everywhere: 0, errors: 0, missing_details: [],
    };
    const LIMIT = 100;
    let skip = 0;
    try {
      // eslint-disable-next-line no-constant-condition
      while (true) {
        if (backfillCancelRef.current) break;
        const { data } = await api.post(
          `/admin/attachments/recover-to-storage?dry_run=${dryRun}&skip=${skip}&limit=${LIMIT}`,
        );
        acc.total = data.total || 0;
        acc.scanned += data.scanned || 0;
        acc.already_in_storage += data.already_in_storage || 0;
        acc.uploaded += data.uploaded || 0;
        acc.missing_everywhere += data.missing_everywhere || 0;
        acc.errors += data.errors || 0;
        if (Array.isArray(data.missing_details)) {
          acc.missing_details.push(...data.missing_details);
        }
        const processed = data.processed_so_far || 0;
        setBackfillProgress(acc.total > 0 ? Math.round((processed / acc.total) * 100) : 100);
        setBackfillResult({ ...acc });

        if (data.done || data.next_skip == null) break;
        skip = data.next_skip;
      }
      setBackfillProgress(100);
      if (dryRun) {
        toast.success(`Auditoría completada: ${acc.uploaded} anexo(s) por subir, ${acc.already_in_storage} ya en la nube`);
      } else {
        toast.success(`Respaldo completado: ${acc.uploaded} anexo(s) subido(s) a la nube`);
        if (acc.errors > 0) toast.error(`${acc.errors} anexo(s) con error al subir`);
      }
    } catch (err) {
      toast.error(`Error en el respaldo de anexos: ${err.response?.data?.detail || err.message}`);
    } finally {
      setBackfillBusy(false);
      setBackfillMode(null);
    }
  };

  const downloadMissingCsv = () => {
    const rows = backfillResult?.missing_details || [];
    if (rows.length === 0) return;
    const headers = ['Colección', 'Cotización', 'Cliente', 'Archivo', 'Tipo', 'ID Anexo', 'Ruta', 'Fecha'];
    const esc = (v) => {
      const s = String(v ?? '');
      return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const lines = rows.map((m) => [
      m.collection === 'quote_history' ? 'Histórico' : 'Cotización',
      m.parent_number || m.parent_id || '',
      m.client_name || '',
      m.filename || '',
      m.content_type || '',
      m.attachment_id || '',
      m.rel_path || '',
      m.uploaded_at || '',
    ].map(esc).join(','));
    const csv = '\uFEFF' + [headers.join(','), ...lines].join('\n');
    downloadBlob(csv, `anexos_perdidos_${tsNow()}.csv`, 'text/csv;charset=utf-8;');
    toast.success(`Reporte de ${rows.length} anexo(s) perdido(s) descargado`);
  };

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

  const loadHistory = useCallback(async () => {
    try {
      const { data } = await api.get('/admin/backup-center/history');
      setHistory(data.history || []);
    } catch (err) { console.warn('No se pudo cargar el historial de respaldos:', err?.message); }
  }, []);

  useEffect(() => { loadEntities(); loadHistory(); loadDbInfo(); }, [loadEntities, loadHistory, loadDbInfo]);

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
      loadHistory();
    } catch (err) {
      toast.error(`Error al exportar ${entity.label}: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleExportAll = async () => {
    if (entities.length === 0) return;
    setBusyZip(true);
    try {
      const allMods = entities.map((e) => e.module);
      const res = await api.post(
        '/admin/backup-center/export-zip',
        { modules: allMods },
        { responseType: 'blob' },
      );
      downloadBlob(res.data, `respaldo_total_${tsNow()}.zip`, 'application/zip');
      toast.success(`Respaldo TOTAL generado: ${allMods.length} entidad(es) en un ZIP`);
      loadHistory();
    } catch (err) {
      toast.error(`Error en el respaldo total: ${err.response?.data?.detail || err.message}`);
    } finally {
      setBusyZip(false);
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
      loadHistory();
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

        {/* Respaldo Total de Base de Datos (todas las colecciones) */}
        <div className="bg-white rounded-xl border border-indigo-200 shadow-sm mb-6 overflow-hidden" data-testid="full-backup-card">
          <div className="bg-indigo-50/70 border-b border-indigo-100 px-4 py-3 flex items-start gap-3">
            <div className="rounded-lg bg-indigo-600 text-white p-2 shadow-sm shrink-0">
              <DatabaseBackup size={18} />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Respaldo Total de Base de Datos</h2>
              <p className="text-xs text-slate-600 mt-0.5 max-w-2xl">
                Respalda y restaura <strong>TODAS las colecciones</strong> (incluye bitácora, correos,
                notificaciones, plantillas, configuración, contadores, sesiones, mensajería, etc.) con
                <strong> fidelidad exacta</strong>. Úsalo para clonar un ambiente completo (ej. Producción → Preview).
              </p>
              {dbInfo && (
                <p className="text-[11px] text-indigo-700/80 mt-1" data-testid="full-backup-info">
                  Base actual: <strong>{dbInfo.db_name}</strong> · {dbInfo.total_collections} colecciones · {dbInfo.total_documents?.toLocaleString('es')} documentos
                </p>
              )}
            </div>
          </div>

          <div className="px-4 py-4">
            <div className="flex flex-wrap items-center gap-2">
              <Button
                onClick={exportFullDb}
                disabled={dbBusy !== null}
                className="bg-indigo-600 hover:bg-indigo-700"
                data-testid="full-backup-export-btn"
              >
                {dbBusy === 'export'
                  ? <Loader2 size={16} className="mr-1.5 animate-spin" />
                  : <Download size={16} className="mr-1.5" />}
                Exportar Base Completa (.zip)
              </Button>

              <input
                ref={dbFileRef}
                type="file"
                accept=".zip"
                className="hidden"
                data-testid="full-backup-file-input"
                onChange={(e) => {
                  const f = e.target.files?.[0] || null;
                  if (f) openRestoreDialog(f);
                }}
              />
              <Button
                variant="outline"
                onClick={() => dbFileRef.current?.click()}
                disabled={dbBusy !== null || dbParsing}
                className="border-red-300 text-red-700 hover:bg-red-50"
                data-testid="full-backup-restore-btn"
              >
                {dbParsing ? <Loader2 size={16} className="mr-1.5 animate-spin" /> : <Upload size={16} className="mr-1.5" />}
                Restaurar Base Completa…
              </Button>
            </div>

            <div className="flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 text-red-800 px-3 py-2 text-xs mt-3">
              <ShieldAlert size={15} className="shrink-0 mt-0.5" />
              <span>
                La restauración <strong>reemplaza por completo</strong> la base de datos de este ambiente
                (<strong>{dbInfo?.db_name || 'preview'}</strong>). Tu sesión de administrador se preserva
                automáticamente. Esta acción no se puede deshacer.
              </span>
            </div>

            {dbBusy === 'restore' && (
              <div className="mt-4" data-testid="full-backup-progress">
                <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
                  <span>{dbProgress < 90 ? 'Subiendo respaldo…' : 'Restaurando colecciones…'}</span>
                  <span>{dbProgress}%</span>
                </div>
                <Progress value={dbProgress} className="h-2" />
              </div>
            )}

            {dbRestoreResult && (
              <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50/60 p-3" data-testid="full-backup-result">
                <div className="flex items-center gap-1.5 text-sm font-semibold text-emerald-800 mb-2">
                  <CheckCircle2 size={15} className="text-emerald-600" />
                  Restauración completada
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-center mb-2">
                  <div className="rounded-lg bg-white border border-slate-200 py-2">
                    <p className="text-lg font-bold text-indigo-700">{dbRestoreResult.restored_collections}</p>
                    <p className="text-[11px] text-slate-500">Colecciones</p>
                  </div>
                  <div className="rounded-lg bg-white border border-slate-200 py-2">
                    <p className="text-lg font-bold text-indigo-700">{dbRestoreResult.restored_documents?.toLocaleString('es')}</p>
                    <p className="text-[11px] text-slate-500">Documentos</p>
                  </div>
                  <div className="rounded-lg bg-white border border-slate-200 py-2">
                    <p className="text-lg font-bold text-slate-600">{dbRestoreResult.dropped_extra_collections?.length || 0}</p>
                    <p className="text-[11px] text-slate-500">Colecciones eliminadas</p>
                  </div>
                </div>
                <p className="text-[11px] text-slate-500">
                  Origen: <strong>{dbRestoreResult.source_db}</strong>
                  {dbRestoreResult.source_exported_at ? ` · exportado ${new Date(dbRestoreResult.source_exported_at).toLocaleString('es')}` : ''}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Respaldo de Anexos hacia Object Storage (Backfill) */}
        <div className="bg-white rounded-xl border border-sky-200 shadow-sm mb-6 overflow-hidden" data-testid="attachments-backfill-card">
          <div className="bg-sky-50/70 border-b border-sky-100 px-4 py-3 flex items-start gap-3">
            <div className="rounded-lg bg-sky-600 text-white p-2 shadow-sm shrink-0">
              <CloudUpload size={18} />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Respaldar Anexos en la Nube (Object Storage)</h2>
              <p className="text-xs text-slate-600 mt-0.5 max-w-2xl">
                Sube a la nube los PDF de anexos que hoy solo existen en el disco local del servidor.
                La memoria local se borra en cada despliegue, así que ejecuta esto <strong>antes de
                apagar tus respaldos manuales</strong>. Primero puedes <strong>Auditar</strong> (simulación,
                no sube nada) para ver cuántos anexos faltan.
              </p>
            </div>
          </div>

          <div className="px-4 py-4">
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                onClick={() => runBackfill(true)}
                disabled={backfillBusy}
                className="border-sky-300 text-sky-700 hover:bg-sky-50"
                data-testid="backfill-audit-btn"
              >
                {backfillBusy && backfillMode === 'audit'
                  ? <Loader2 size={16} className="mr-1.5 animate-spin" />
                  : <Search size={16} className="mr-1.5" />}
                Auditar (simulación)
              </Button>
              <Button
                onClick={() => runBackfill(false)}
                disabled={backfillBusy}
                className="bg-sky-600 hover:bg-sky-700"
                data-testid="backfill-run-btn"
              >
                {backfillBusy && backfillMode === 'upload'
                  ? <Loader2 size={16} className="mr-1.5 animate-spin" />
                  : <CloudUpload size={16} className="mr-1.5" />}
                Ejecutar Respaldo a la Nube
              </Button>
            </div>

            {backfillBusy && (
              <div className="mt-4" data-testid="backfill-progress">
                <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
                  <span>{backfillMode === 'audit' ? 'Auditando anexos…' : 'Subiendo anexos a la nube…'}</span>
                  <span>{backfillProgress}%</span>
                </div>
                <Progress value={backfillProgress} className="h-2" />
              </div>
            )}

            {backfillResult && (
              <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3" data-testid="backfill-result">
                <div className="flex items-center gap-1.5 text-sm font-semibold text-slate-700 mb-2">
                  <CheckCircle2 size={15} className="text-emerald-600" />
                  {backfillMode === 'audit' || (backfillBusy && backfillMode === 'audit') ? 'Resultado de la auditoría' : 'Resultado del respaldo'}
                  <span className="text-xs font-normal text-slate-400">· {backfillResult.total} anexo(s) en total</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
                  <div className="rounded-lg bg-white border border-slate-200 py-2" data-testid="backfill-stat-uploaded">
                    <p className="text-lg font-bold text-sky-700">{backfillResult.uploaded}</p>
                    <p className="text-[11px] text-slate-500">Subidos / por subir</p>
                  </div>
                  <div className="rounded-lg bg-white border border-slate-200 py-2" data-testid="backfill-stat-already">
                    <p className="text-lg font-bold text-emerald-700">{backfillResult.already_in_storage}</p>
                    <p className="text-[11px] text-slate-500">Ya en la nube</p>
                  </div>
                  <div className="rounded-lg bg-white border border-slate-200 py-2" data-testid="backfill-stat-missing">
                    <p className="text-lg font-bold text-amber-600">{backfillResult.missing_everywhere}</p>
                    <p className="text-[11px] text-slate-500">Faltantes (perdidos)</p>
                  </div>
                  <div className="rounded-lg bg-white border border-slate-200 py-2" data-testid="backfill-stat-errors">
                    <p className="text-lg font-bold text-red-600">{backfillResult.errors}</p>
                    <p className="text-[11px] text-slate-500">Errores</p>
                  </div>
                </div>

                {backfillResult.missing_details?.length > 0 && (
                  <div className="mt-3" data-testid="backfill-missing-list">
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-700">
                        <AlertTriangle size={13} />
                        Anexos faltantes (no están ni en el disco local ni en la nube)
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={downloadMissingCsv}
                        disabled={!backfillResult.missing_details?.length}
                        className="h-7 border-amber-300 text-amber-700 hover:bg-amber-100"
                        data-testid="backfill-missing-csv-btn"
                      >
                        <Download size={13} className="mr-1" /> Descargar reporte CSV
                      </Button>
                    </div>
                    <div className="max-h-56 overflow-auto rounded-lg border border-amber-200 bg-amber-50/50">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="text-left text-amber-700/80 border-b border-amber-200">
                            <th className="px-2.5 py-1.5 font-semibold">Cotización</th>
                            <th className="px-2.5 py-1.5 font-semibold">Cliente</th>
                            <th className="px-2.5 py-1.5 font-semibold">Archivo</th>
                            <th className="px-2.5 py-1.5 font-semibold">Origen</th>
                          </tr>
                        </thead>
                        <tbody>
                          {backfillResult.missing_details.map((m, i) => (
                            <tr key={i} className="border-b border-amber-100 last:border-0" data-testid={`backfill-missing-row-${i}`}>
                              <td className="px-2.5 py-1.5 text-slate-700">{m.parent_number || m.parent_id || '—'}</td>
                              <td className="px-2.5 py-1.5 text-slate-600 truncate max-w-[160px]" title={m.client_name}>{m.client_name || '—'}</td>
                              <td className="px-2.5 py-1.5 text-slate-600 truncate max-w-[220px]" title={m.filename || m.rel_path}>{m.filename || m.rel_path || '—'}</td>
                              <td className="px-2.5 py-1.5 text-slate-500">{m.collection === 'quote_history' ? 'Histórico' : 'Cotización'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Acciones masivas */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <p className="text-sm text-slate-500" data-testid="backup-selected-count">
            {selected.size} de {entities.length} entidad(es) seleccionada(s)
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              onClick={handleExportAll}
              disabled={busyZip || entities.length === 0}
              className="border-emerald-300 text-emerald-700 hover:bg-emerald-50"
              data-testid="export-all-btn"
            >
              {busyZip ? <Loader2 size={16} className="mr-1.5 animate-spin" /> : <DatabaseBackup size={16} className="mr-1.5" />}
              Respaldo Total (1 clic)
            </Button>
            <Button
              variant="outline"
              onClick={() => setBulkImportOpen(true)}
              className="border-indigo-300 text-indigo-700 hover:bg-indigo-50"
              data-testid="import-zip-btn"
            >
              <Upload size={16} className="mr-1.5" />
              Importar Masivo (ZIP)
            </Button>
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

        {/* Historial de respaldos / restauraciones (auditoría) */}
        <div className="mt-8" data-testid="backup-history-section">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-semibold text-slate-800 uppercase tracking-wide">Historial de Respaldos y Restauraciones</h2>
            <button onClick={loadHistory} className="text-xs text-indigo-600 hover:text-indigo-800" data-testid="backup-history-refresh">Actualizar</button>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
            {history.length === 0 ? (
              <p className="text-sm text-slate-400 px-4 py-6 text-center" data-testid="backup-history-empty">
                Aún no hay actividad registrada. Las exportaciones e importaciones aparecerán aquí.
              </p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 text-xs uppercase tracking-wide">
                    <th className="px-4 py-2.5 text-left font-semibold">Acción</th>
                    <th className="px-2 py-2.5 text-left font-semibold">Entidad(es)</th>
                    <th className="px-2 py-2.5 text-left font-semibold w-44">Resultado</th>
                    <th className="px-2 py-2.5 text-left font-semibold w-48">Usuario</th>
                    <th className="px-4 py-2.5 text-left font-semibold w-40">Fecha</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((h, i) => (
                    <tr key={i} className="border-b border-slate-100 last:border-0" data-testid={`backup-history-row-${i}`}>
                      <td className="px-4 py-2.5">
                        <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full ${h.kind === 'export' ? 'bg-emerald-100 text-emerald-700' : (h.mode === 'replace' ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700')}`}>
                          {h.kind === 'export' ? 'Respaldo' : (h.mode === 'replace' ? 'Restaurar (réplica)' : 'Restaurar')}
                          {h.scope === 'masivo' ? ' · masivo' : ''}
                        </span>
                      </td>
                      <td className="px-2 py-2.5 text-slate-700 max-w-[260px] truncate" title={h.modules_label}>{h.modules_label}</td>
                      <td className="px-2 py-2.5 text-xs text-slate-500">
                        {h.kind === 'export'
                          ? (h.scope === 'masivo' ? `${h.modules_count} entidades` : `${h.count || 0} reg.`)
                          : `+${h.inserted} / ~${h.updated}${h.deleted ? ` / -${h.deleted}` : ''}${h.errors ? ` · ${h.errors} err` : ''}`}
                      </td>
                      <td className="px-2 py-2.5 text-slate-600 truncate max-w-[180px]" title={h.executed_by}>{h.executed_by}</td>
                      <td className="px-4 py-2.5 text-xs text-slate-500">{h.executed_at ? new Date(h.executed_at).toLocaleString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

      </div>

      <ImportDialog
        entity={importTarget}
        onClose={() => setImportTarget(null)}
        onDone={() => { loadEntities(); loadHistory(); }}
        fileRef={fileRef}
      />

      <BulkImportDialog
        open={bulkImportOpen}
        onClose={() => setBulkImportOpen(false)}
        onDone={() => { loadEntities(); loadHistory(); }}
        zipRef={zipRef}
      />

      {/* Confirmación de Restauración (Total o Selectiva) */}
      <Dialog open={dbConfirmOpen} onOpenChange={(o) => { if (!o) { setDbConfirmOpen(false); setDbFile(null); setDbBackupCols([]); setDbSelectedCols(new Set()); if (dbFileRef.current) dbFileRef.current.value = ''; } }}>
        <DialogContent className="max-w-lg" data-testid="full-backup-confirm-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-700">
              <ShieldAlert size={18} /> Restaurar Base de Datos
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 text-sm text-slate-700">
            <p>
              Restaurando desde <strong className="break-all">{dbFile?.name}</strong>
              {dbFile ? ` (${(dbFile.size / 1024 / 1024).toFixed(1)} MB)` : ''} sobre el ambiente
              <strong> {dbInfo?.db_name || 'actual'}</strong>.
            </p>

            {/* Selección de colecciones */}
            <div className="rounded-lg border border-slate-200">
              <div className="flex items-center justify-between px-3 py-2 border-b border-slate-100 bg-slate-50">
                <span className="text-xs font-semibold text-slate-600">
                  Colecciones a restaurar ({dbSelectedCols.size}/{dbBackupCols.length})
                </span>
                <button
                  type="button"
                  onClick={toggleAllCols}
                  className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
                  data-testid="full-backup-toggle-all"
                >
                  {dbAllSelected ? 'Deseleccionar todo' : 'Seleccionar todo'}
                </button>
              </div>
              <div className="flex items-center justify-end gap-1.5 px-3 py-1 text-[10px] text-slate-400 border-b border-slate-50">
                <span>actual</span><span className="text-slate-300">→</span><span>respaldo</span>
              </div>
              <div className="max-h-52 overflow-auto p-1" data-testid="full-backup-collections-list">
                {dbBackupCols.map((c) => {
                  const cur = dbCurrentCountMap[c.name];
                  const hasCur = cur !== undefined;
                  const isNew = !hasCur; // no existe en el ambiente actual
                  const changes = hasCur && cur !== c.count;
                  return (
                    <label
                      key={c.name}
                      className="flex items-center justify-between gap-2 px-2 py-1.5 rounded hover:bg-slate-50 cursor-pointer"
                      data-testid={`full-backup-col-${c.name}`}
                    >
                      <span className="flex items-center gap-2 min-w-0">
                        <Checkbox
                          checked={dbSelectedCols.has(c.name)}
                          onCheckedChange={() => toggleCol(c.name)}
                          data-testid={`full-backup-col-checkbox-${c.name}`}
                        />
                        <span className="text-xs text-slate-700 truncate font-mono">{c.name}</span>
                        {isNew && <span className="text-[9px] uppercase tracking-wide bg-emerald-100 text-emerald-700 px-1 py-0.5 rounded shrink-0">nueva</span>}
                      </span>
                      <span
                        className="text-[11px] shrink-0 tabular-nums flex items-center gap-1"
                        data-testid={`full-backup-col-counts-${c.name}`}
                        title={`Ambiente actual: ${hasCur ? cur : 0} · Respaldo: ${c.count}`}
                      >
                        <span className={changes ? 'text-slate-400 line-through' : 'text-slate-400'}>{hasCur ? cur?.toLocaleString('es') : 0}</span>
                        <span className="text-slate-300">→</span>
                        <span className={changes ? 'text-indigo-600 font-semibold' : 'text-slate-500'}>{c.count?.toLocaleString('es')}</span>
                      </span>
                    </label>
                  );
                })}
              </div>
            </div>

            <div className="rounded-lg bg-red-50 border border-red-200 text-red-800 px-3 py-2 text-xs">
              {dbIsSelective ? (
                <>Se <strong>eliminarán y reemplazarán</strong> únicamente las <strong>{dbSelectedCols.size}</strong> colección(es) seleccionada(s). El resto del ambiente <strong>no se toca</strong>. La acción no se puede deshacer.</>
              ) : (
                <>Restauración <strong>completa</strong>: se reemplazará <strong>toda</strong> la base de datos. La acción <strong>no se puede deshacer</strong>. Tu sesión de administrador se conservará.</>
              )}
            </div>

            {/* Réplica exacta solo aplica a restauración completa */}
            {!dbIsSelective && (
              <label className="flex items-start gap-2 cursor-pointer">
                <Checkbox checked={dbExactReplica} onCheckedChange={(v) => setDbExactReplica(!!v)} data-testid="full-backup-exact-checkbox" />
                <span className="text-xs text-slate-600">
                  <strong>Réplica exacta</strong>: eliminar también las colecciones de este ambiente que no
                  estén en el respaldo (recomendado para clonar 1:1).
                </span>
              </label>
            )}

            <div>
              <p className="text-xs text-slate-500 mb-1">Escribe <strong>RESTAURAR</strong> para confirmar:</p>
              <input
                type="text"
                value={dbConfirmText}
                onChange={(e) => setDbConfirmText(e.target.value)}
                className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-red-300"
                placeholder="RESTAURAR"
                data-testid="full-backup-confirm-input"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setDbConfirmOpen(false); setDbFile(null); setDbBackupCols([]); setDbSelectedCols(new Set()); if (dbFileRef.current) dbFileRef.current.value = ''; }} data-testid="full-backup-cancel-btn">
              Cancelar
            </Button>
            <Button
              className="bg-red-600 hover:bg-red-700"
              disabled={dbConfirmText.trim().toUpperCase() !== 'RESTAURAR' || dbSelectedCols.size === 0}
              onClick={doRestoreFullDb}
              data-testid="full-backup-confirm-btn"
            >
              <Upload size={15} className="mr-1.5" /> Restaurar {dbIsSelective ? `${dbSelectedCols.size} colección(es)` : 'Todo'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function ImportDialog({ entity, onClose, onDone, fileRef }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [replaceMode, setReplaceMode] = useState(false);

  useEffect(() => { setFile(null); setPreview(null); setBusy(false); setReplaceMode(false); }, [entity]);

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
      fd.append('mode', replaceMode ? 'replace' : 'upsert');
      const { data } = await api.post(`/admin/migration/${entity.module}/import-apply`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      toast.success(`${entity.label}: ${data.inserted} creado(s), ${data.updated} actualizado(s)${data.deleted ? `, ${data.deleted} eliminado(s)` : ''}${data.skipped ? `, ${data.skipped} omitido(s)` : ''}`);
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
            Por defecto se actualizan los existentes y se crean los nuevos (upsert). Para dejar este
            entorno <strong>idéntico al respaldo</strong>, active "Reemplazo total" abajo.
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
                {replaceMode && (
                  <li>A eliminar (no están en el respaldo): <strong className="text-red-600">{preview.to_delete_count ?? 0}</strong></li>
                )}
                {preview.exported_at && (
                  <li className="text-xs text-slate-400 mt-1">Respaldo del: {new Date(preview.exported_at).toLocaleString()}</li>
                )}
              </ul>
            </div>
          )}

          <label className="flex items-start gap-2 rounded-lg border border-slate-200 p-2.5 cursor-pointer hover:bg-slate-50" data-testid="import-replace-mode-label">
            <Checkbox checked={replaceMode} onCheckedChange={(v) => setReplaceMode(!!v)} data-testid="import-replace-mode-checkbox" className="mt-0.5" />
            <span className="text-xs text-slate-600">
              <strong className="text-slate-800">Reemplazo total (réplica exacta)</strong><br />
              Deja <strong>{entity.label}</strong> idéntico al respaldo: además de crear/actualizar, <strong className="text-red-600">elimina</strong> los registros que no estén en el archivo. Úsalo para que este entorno quede exactamente igual al de origen.
            </span>
          </label>
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

function BulkImportDialog({ open, onClose, onDone, zipRef }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [replaceMode, setReplaceMode] = useState(false);

  useEffect(() => { if (!open) { setFile(null); setPreview(null); setBusy(false); setReplaceMode(false); } }, [open]);

  const handleFile = async (e) => {
    const f = e.target.files?.[0];
    if (e.target) e.target.value = '';
    if (!f) return;
    if (!f.name.toLowerCase().endsWith('.zip')) { toast.error('Solo se permite un archivo .zip de respaldo'); return; }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append('file', f);
      const { data } = await api.post('/admin/backup-center/import-preview-zip', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setPreview(data);
      setFile(f);
    } catch (err) {
      toast.error(`ZIP inválido: ${err.response?.data?.detail || err.message}`);
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
      fd.append('mode', replaceMode ? 'replace' : 'upsert');
      const { data } = await api.post('/admin/backup-center/import-zip', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      toast.success(data.message || 'Importación masiva completada');
      if (data.errors?.length) {
        toast.error(`${data.errors.length} entidad(es) con error: ${data.errors.map((e) => e.module).join(', ')}`);
      }
      onDone?.();
      onClose();
    } catch (err) {
      toast.error(`Error en importación masiva: ${err.response?.data?.detail || err.message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md" data-testid="bulk-import-dialog">
        <DialogHeader>
          <DialogTitle>Importar Masivo desde ZIP</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 min-w-0">
          <p className="text-sm text-slate-600">
            Suba el archivo <strong>.zip</strong> de respaldo (generado por "Ejecutar Exportación
            Seleccionados"). Por defecto se restauran todas las entidades mediante upsert. Para clonar
            exactamente el entorno de origen, active "Reemplazo total" abajo.
          </p>
          <input ref={zipRef} type="file" accept=".zip" onChange={handleFile} className="hidden" />
          <Button
            variant="outline"
            onClick={() => zipRef.current?.click()}
            disabled={busy}
            className="w-full justify-start max-w-full"
            title={file ? file.name : undefined}
            data-testid="bulk-import-pick-file-btn"
          >
            <Package size={15} className="mr-1.5 shrink-0" />
            <span className="truncate min-w-0">{file ? file.name : 'Seleccionar archivo .zip'}</span>
          </Button>

          {preview && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm" data-testid="bulk-import-preview">
              <p className="font-semibold text-slate-700 mb-1.5">
                {preview.total_entities} entidad(es) en el respaldo
              </p>
              <ul className="text-slate-600 space-y-1 max-h-48 overflow-auto">
                {preview.entities.map((e) => (
                  <li key={e.module} className="flex items-center justify-between gap-2">
                    <span>{e.label}</span>
                    <Badge variant="secondary" className="bg-slate-100 text-slate-600">{e.records} reg.</Badge>
                  </li>
                ))}
              </ul>
              {preview.skipped_files?.length > 0 && (
                <p className="text-xs text-amber-600 mt-2">
                  Se ignorarán {preview.skipped_files.length} archivo(s) no reconocido(s).
                </p>
              )}
            </div>
          )}

          <label className="flex items-start gap-2 rounded-lg border border-slate-200 p-2.5 cursor-pointer hover:bg-slate-50" data-testid="bulk-replace-mode-label">
            <Checkbox checked={replaceMode} onCheckedChange={(v) => setReplaceMode(!!v)} data-testid="bulk-replace-mode-checkbox" className="mt-0.5" />
            <span className="text-xs text-slate-600">
              <strong className="text-slate-800">Reemplazo total (réplica exacta)</strong><br />
              Deja cada entidad idéntica al respaldo: además de crear/actualizar, <strong className="text-red-600">elimina</strong> los registros que no estén en el archivo. Úsalo para clonar exactamente el entorno de origen.
            </span>
          </label>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={busy} data-testid="bulk-import-cancel-btn">Cancelar</Button>
          <Button
            onClick={handleApply}
            disabled={busy || !preview}
            className="bg-indigo-600 hover:bg-indigo-700"
            data-testid="bulk-import-apply-btn"
          >
            {busy ? <Loader2 size={16} className="mr-1.5 animate-spin" /> : null}
            Restaurar Todo
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

