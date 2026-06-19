import { useState, useRef } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { Button } from './ui/button';
import { Loader2, Upload, Download, FileUp, CheckCircle2, AlertTriangle, XCircle, Eye } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const HEADERS = ['RIF', 'Cantidad de Tiendas', 'Nro de Cajas', 'Tipo de Servicio', 'Integrador', 'Coordinador', 'Implementador', 'Ejecutivo Propietario'];

const STATUS_META = {
  ok: { label: 'Actualizado', cls: 'bg-emerald-100 text-emerald-700', Icon: CheckCircle2 },
  sin_cambios: { label: 'Sin cambios', cls: 'bg-slate-100 text-slate-600', Icon: Eye },
  not_found: { label: 'RIF no encontrado', cls: 'bg-amber-100 text-amber-700', Icon: AlertTriangle },
  error: { label: 'Error', cls: 'bg-rose-100 text-rose-700', Icon: XCircle },
};

export const ClientsBulkUpdateModal = ({ open, onClose, onApplied }) => {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [isDryRun, setIsDryRun] = useState(true);
  const fileRef = useRef(null);

  const reset = () => { setFile(null); setResult(null); setLoading(false); if (fileRef.current) fileRef.current.value = ''; };

  const downloadTemplate = () => {
    const example = ['J-12345678-9', '5', '15', 'POS;Pinpad', 'Nombre del Integrador', 'correo.coordinador@empresa.com', 'correo.implementador@empresa.com', 'correo.ejecutivo@empresa.com'];
    const csv = [HEADERS.join(','), example.map(c => /[",\n]/.test(c) ? `"${c}"` : c).join(',')].join('\n');
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'plantilla_actualizacion_clientes.csv';
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  };

  const exportReportCsv = () => {
    if (!result?.report?.length) return;
    const cell = (v) => {
      const s = String(v ?? '');
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const meta = { ok: 'Actualizado', sin_cambios: 'Sin cambios', not_found: 'RIF no encontrado', error: 'Error' };
    const lines = [];
    lines.push(`Reporte de Actualización Masiva de Clientes - ${result.dry_run ? 'PREVISUALIZACIÓN' : 'APLICADO'}`);
    lines.push(`Generado: ${new Date().toLocaleString('es-VE')}`);
    lines.push(`Filas: ${result.rows_processed} | OK: ${result.rows_ok} | No encontrados: ${result.rows_not_found} | Errores: ${result.rows_error} | Clientes afectados: ${result.clients_updated}`);
    lines.push('');
    lines.push(['Fila', 'RIF', 'Sucursales', 'Estado', 'Campos aplicados', 'Avisos'].map(cell).join(','));
    result.report.forEach((r) => lines.push([
      r.row, r.rif || '', r.matched_clients, meta[r.status] || r.status,
      (r.applied || []).join(' | '), (r.warnings || []).join(' | '),
    ].map(cell).join(',')));
    const blob = new Blob(['\ufeff' + lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `reporte_actualizacion_clientes_${result.dry_run ? 'preview' : 'aplicado'}_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  };

  const send = async (dryRun) => {
    if (!file) { toast.error('Selecciona un archivo CSV o Excel'); return; }
    setLoading(true); setIsDryRun(dryRun);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('dry_run', dryRun ? 'true' : 'false');
      const res = await api.post('/clients/bulk-update-by-rif', fd);
      setResult(res.data);
      if (dryRun) {
        toast.success(`Previsualización: ${res.data.rows_ok} fila(s) lista(s), ${res.data.clients_updated} cliente(s) a actualizar`);
      } else {
        toast.success(`Aplicado: ${res.data.clients_updated} cliente(s) actualizado(s)`);
        onApplied?.();
      }
    } catch (e) {
      toast.error(`Error: ${e.response?.data?.detail || e.message}`);
    } finally { setLoading(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) { onClose(); reset(); } }}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="clients-bulk-update-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Upload size={18} /> Actualización masiva de clientes (por RIF)</DialogTitle>
          <DialogDescription>Sube un CSV/Excel para actualizar en bloque los datos de imple de los clientes coincidiendo por RIF.</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="bg-blue-50 border border-blue-200 rounded p-3 text-xs text-slate-700 space-y-1">
            <p>Sube un CSV/Excel con la columna <b>RIF</b> (obligatoria) y las columnas a actualizar. Coincidencia por RIF <b>en cascada a todas las sucursales</b>. Las celdas <b>vacías se ignoran</b> (actualización parcial).</p>
            <p><b>Tipo de Servicio</b>: separa varios con <code>;</code> (ej. <code>POS;Pinpad</code>) — se <b>agrega</b> a la lista existente.</p>
            <p><b>Integrador</b> debe existir en el catálogo. <b>Coordinador/Implementador/Ejecutivo</b> por correo o nombre exacto del usuario.</p>
          </div>

          <div className="flex flex-wrap gap-2 items-center">
            <Button variant="outline" size="sm" onClick={downloadTemplate} data-testid="bulk-update-template-btn">
              <Download size={14} className="mr-1" /> Descargar plantilla CSV
            </Button>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,.xlsx,.xlsm"
              onChange={(e) => { setFile(e.target.files?.[0] || null); setResult(null); }}
              className="hidden"
              data-testid="bulk-update-file-input"
            />
            <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} data-testid="bulk-update-pick-btn">
              <FileUp size={14} className="mr-1" /> {file ? file.name : 'Seleccionar archivo'}
            </Button>
          </div>

          <div className="flex gap-2">
            <Button onClick={() => send(true)} disabled={loading || !file} variant="outline" className="border-slate-400" data-testid="bulk-update-preview-btn">
              {loading && isDryRun ? <Loader2 size={14} className="animate-spin mr-1" /> : <Eye size={14} className="mr-1" />} Previsualizar
            </Button>
            <Button onClick={() => send(false)} disabled={loading || !file} className="bg-brand-green-600 hover:bg-brand-green-700" data-testid="bulk-update-apply-btn">
              {loading && !isDryRun ? <Loader2 size={14} className="animate-spin mr-1" /> : <CheckCircle2 size={14} className="mr-1" />} Aplicar cambios
            </Button>
          </div>

          {result && (
            <div className="space-y-2" data-testid="bulk-update-result">
              <div className="flex items-center justify-between gap-2">
                <div className="flex flex-wrap gap-2 text-xs">
                  <span className={`px-2 py-1 rounded ${result.dry_run ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'} font-semibold`}>
                    {result.dry_run ? 'PREVISUALIZACIÓN (no se guardó nada)' : 'CAMBIOS APLICADOS'}
                  </span>
                  <span className="px-2 py-1 rounded bg-slate-100">Filas: {result.rows_processed}</span>
                  <span className="px-2 py-1 rounded bg-emerald-50 text-emerald-700">OK: {result.rows_ok}</span>
                  <span className="px-2 py-1 rounded bg-amber-50 text-amber-700">No encontrados: {result.rows_not_found}</span>
                  <span className="px-2 py-1 rounded bg-rose-50 text-rose-700">Errores: {result.rows_error}</span>
                  <span className="px-2 py-1 rounded bg-blue-50 text-blue-700">Clientes afectados: {result.clients_updated}</span>
                </div>
                <Button variant="outline" size="sm" onClick={exportReportCsv} className="shrink-0 text-emerald-700 border-emerald-300" data-testid="bulk-update-export-report-btn">
                  <Download size={14} className="mr-1" /> Exportar reporte CSV
                </Button>
              </div>
              <div className="max-h-[40vh] overflow-y-auto border rounded">
                <table className="w-full text-xs">
                  <thead className="bg-slate-100 text-slate-600 sticky top-0">
                    <tr>
                      <th className="px-2 py-1.5 text-left">Fila</th>
                      <th className="px-2 py-1.5 text-left">RIF</th>
                      <th className="px-2 py-1.5 text-center">Sucursales</th>
                      <th className="px-2 py-1.5 text-left">Estado</th>
                      <th className="px-2 py-1.5 text-left">Campos / Avisos</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.report.map((r) => {
                      const meta = STATUS_META[r.status] || STATUS_META.error;
                      return (
                        <tr key={r.row} className="border-t align-top" data-testid={`bulk-update-row-${r.row}`}>
                          <td className="px-2 py-1.5">{r.row}</td>
                          <td className="px-2 py-1.5 font-mono">{r.rif || '—'}</td>
                          <td className="px-2 py-1.5 text-center">{r.matched_clients}</td>
                          <td className="px-2 py-1.5"><span className={`px-1.5 py-0.5 rounded text-[10px] ${meta.cls}`}>{meta.label}</span></td>
                          <td className="px-2 py-1.5">
                            {r.applied?.length > 0 && <div className="text-emerald-700">{r.applied.join(' · ')}</div>}
                            {r.warnings?.map((w, i) => <div key={i} className="text-rose-600">⚠ {w}</div>)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ClientsBulkUpdateModal;
