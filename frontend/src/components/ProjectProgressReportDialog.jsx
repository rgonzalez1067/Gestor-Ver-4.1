import { useState, useEffect, useMemo } from 'react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from './ui/dialog';
import { Button } from './ui/button';
import { Label } from './ui/label';
import { Checkbox } from './ui/checkbox';
import { FileBarChart, Eye, FileText, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import api from '../utils/api';

const PHASES = ['Recibido', 'Configurado', 'Testeado', 'En Producción'];

const fmtDate = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString('es-VE'); } catch { return String(iso).slice(0, 10); }
};

/**
 * Modal: Reporte de Estatus / Avance de Proyecto
 * Props:
 *  - open, onOpenChange
 *  - projectId
 */
export const ProjectProgressReportDialog = ({ open, onOpenChange, projectId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);

  // Filtros
  const [selBanks, setSelBanks] = useState([]);
  const [selProducts, setSelProducts] = useState([]);
  const [selStores, setSelStores] = useState([]);
  const [selRifs, setSelRifs] = useState([]);

  // Carga inicial: catálogos (sin filtros) → mostrar Todo el Proyecto
  const fetchReport = async (params) => {
    if (!projectId) return;
    setLoading(true);
    try {
      const res = await api.get(`/projects/${projectId}/report/avance`, { params });
      setData(res.data);
    } catch (err) {
      toast.error(`Error al cargar reporte: ${err.response?.data?.detail || err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open && projectId) {
      setSelBanks([]); setSelProducts([]); setSelStores([]); setSelRifs([]);
      fetchReport({});
    }
    // eslint-disable-next-line
  }, [open, projectId]);

  const applyFilters = () => {
    const params = {};
    if (selBanks.length) params.banks = selBanks.join(',');
    if (selProducts.length) params.products = selProducts.join(',');
    if (selStores.length) params.stores = selStores.join(',');
    if (selRifs.length) params.rifs = selRifs.join(',');
    fetchReport(params);
  };

  const downloadPdf = async () => {
    if (!projectId) return;
    setPdfLoading(true);
    try {
      const params = {};
      if (selBanks.length) params.banks = selBanks.join(',');
      if (selProducts.length) params.products = selProducts.join(',');
      if (selStores.length) params.stores = selStores.join(',');
      if (selRifs.length) params.rifs = selRifs.join(',');
      const res = await api.get(`/projects/${projectId}/report/avance/pdf`, { params, responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url;
      const ts = new Date().toISOString().slice(0, 16).replace(/[-:T]/g, '');
      const num = data?.header?.project_number || 'proyecto';
      a.download = `avance_${num}_${ts}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success('PDF descargado');
    } catch (err) {
      toast.error(`Error: ${err.response?.data?.detail || err.message}`);
    } finally {
      setPdfLoading(false);
    }
  };

  const isMultistore = ['multistore', 'multirif'].includes(data?.header?.project_type);
  const isMultirif = data?.header?.project_type === 'multirif';
  const banksAvail = data?.available?.banks || [];
  const productsAvail = data?.available?.products || [];
  const rifsAvail = data?.available?.rifs || [];
  const allStoresAvail = data?.available?.stores || [];
  // Cascada: si hay RIF seleccionados, solo mostrar las tiendas de esos RIF
  const storesAvail = selRifs.length
    ? allStoresAvail.filter((s) => selRifs.includes(s.rif_id))
    : allStoresAvail;

  const groupedRows = useMemo(() => {
    if (!data?.rows) return [];
    const g = [];
    let lastStore = null;
    let lastRif = null;
    for (const r of data.rows) {
      // Encabezado de RIF (solo Multi-RIF): número de RIF + nombre del comercio
      if (isMultirif) {
        const rifKey = r.rif_id || r.rif;
        if (rifKey !== lastRif) {
          g.push({ type: 'rif', rif: r.rif, rifName: r.rif_name });
          lastRif = rifKey;
          lastStore = null;
        }
      }
      const storeKey = r.store_id || r.store_label;
      if (isMultistore && storeKey !== lastStore) {
        g.push({ type: 'store', label: r.store_label });
        lastStore = storeKey;
      }
      g.push({ type: 'data', row: r });
    }
    return g;
  }, [data, isMultistore, isMultirif]);

  const phaseCellClass = (info) => {
    if (info.expected === 0) return 'bg-slate-50 text-slate-300';
    if (info.completed || info.percent >= 100) return 'bg-emerald-100 text-emerald-800 font-bold';
    if (info.percent >= 50) return 'bg-amber-100 text-amber-800';
    if (info.percent > 0) return 'bg-rose-100 text-rose-800';
    return 'bg-slate-100 text-slate-500';
  };

  const toggleArrayItem = (arr, item) =>
    arr.includes(item) ? arr.filter(x => x !== item) : [...arr, item];

  // Cascada RIF → Tiendas: al deseleccionar un RIF, se podan sus tiendas seleccionadas.
  const toggleRif = (rifId) => {
    setSelRifs((cur) => {
      const next = toggleArrayItem(cur, rifId);
      if (!next.includes(rifId)) {
        const prunedStoreIds = allStoresAvail.filter((s) => s.rif_id === rifId).map((s) => s.store_id);
        setSelStores((curS) => curS.filter((sid) => !prunedStoreIds.includes(sid)));
      }
      return next;
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-6xl max-h-[90vh] overflow-y-auto" data-testid="project-progress-report-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 font-manrope">
            <FileBarChart className="text-sky-600" size={22} />
            Reporte de Estatus / Avance del Proyecto
          </DialogTitle>
        </DialogHeader>

        {loading && !data ? (
          <div className="text-center py-10 text-slate-500"><Loader2 className="inline mr-2 animate-spin" />Cargando...</div>
        ) : !data ? (
          <div className="text-center py-10 text-slate-500">Sin datos</div>
        ) : (
          <div className="space-y-4">
            {/* HEADER del proyecto */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 p-4 bg-slate-50 rounded-lg border border-slate-200">
              {[
                ['Cliente', data.header.client_name],
                ['Nro. Ticket', data.header.ticket_number],
                ['Nro. Proyecto', data.header.project_number],
                ['Cotización', data.header.quote_number],
                ['Integrador', data.header.integrator_name],
                ['Aplicativo', data.header.integrator_app_name],
                ['Implementador', data.header.assigned_to_name],
                ['Fecha Asignación', fmtDate(data.header.assigned_at)],
              ].map(([lbl, val]) => (
                <div key={lbl}>
                  <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide">{lbl}</p>
                  <p className="text-sm font-bold text-slate-800 break-words">{val || '—'}</p>
                </div>
              ))}
            </div>

            {/* FILTROS */}
            <div className="border border-slate-200 rounded-lg p-4 bg-white">
              <p className="text-xs font-bold text-slate-700 uppercase tracking-wide mb-3">Filtros</p>
              {/* RIF (solo Multi-RIF) — cascada hacia Tiendas */}
              {isMultirif && (
                <div className="mb-4">
                  <Label className="text-xs font-semibold text-slate-600">RIF / Razón Social</Label>
                  <div className="mt-1 max-h-32 overflow-y-auto border border-slate-200 rounded p-2 grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-1 bg-slate-50">
                    {rifsAvail.length === 0 ? (
                      <p className="text-xs text-slate-400 italic">Sin RIF</p>
                    ) : (
                      rifsAvail.map((rf) => (
                        <label key={rf.rif_id} className="flex items-center gap-2 text-xs cursor-pointer hover:bg-white rounded px-1 py-0.5">
                          <Checkbox
                            checked={selRifs.includes(rf.rif_id)}
                            onCheckedChange={() => toggleRif(rf.rif_id)}
                            data-testid={`filter-rif-${rf.rif_id}`}
                          />
                          <span className="truncate"><span className="font-semibold">{rf.rif}</span> · {rf.client_name}</span>
                        </label>
                      ))
                    )}
                  </div>
                  <p className="text-[10px] text-slate-400 mt-1">{selRifs.length === 0 ? 'Todos los RIF' : `${selRifs.length} RIF seleccionado(s) — las tiendas se filtran por estos RIF`}</p>
                </div>
              )}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Bancos */}
                <div>
                  <Label className="text-xs font-semibold text-slate-600">Banco / Ente</Label>
                  <div className="mt-1 max-h-32 overflow-y-auto border border-slate-200 rounded p-2 space-y-1 bg-slate-50">
                    {banksAvail.length === 0 ? (
                      <p className="text-xs text-slate-400 italic">Sin bancos</p>
                    ) : (
                      banksAvail.map((b) => (
                        <label key={b} className="flex items-center gap-2 text-xs cursor-pointer hover:bg-white rounded px-1 py-0.5">
                          <Checkbox
                            checked={selBanks.includes(b)}
                            onCheckedChange={() => setSelBanks((cur) => toggleArrayItem(cur, b))}
                            data-testid={`filter-bank-${b}`}
                          />
                          <span>{b}</span>
                        </label>
                      ))
                    )}
                  </div>
                  <p className="text-[10px] text-slate-400 mt-1">{selBanks.length === 0 ? 'Todos' : `${selBanks.length} seleccionado(s)`}</p>
                </div>

                {/* Productos */}
                <div>
                  <Label className="text-xs font-semibold text-slate-600">Producto</Label>
                  <div className="mt-1 max-h-32 overflow-y-auto border border-slate-200 rounded p-2 space-y-1 bg-slate-50">
                    {productsAvail.length === 0 ? (
                      <p className="text-xs text-slate-400 italic">Sin productos</p>
                    ) : (
                      productsAvail.map((p) => (
                        <label key={p} className="flex items-center gap-2 text-xs cursor-pointer hover:bg-white rounded px-1 py-0.5">
                          <Checkbox
                            checked={selProducts.includes(p)}
                            onCheckedChange={() => setSelProducts((cur) => toggleArrayItem(cur, p))}
                            data-testid={`filter-product-${p}`}
                          />
                          <span>{p}</span>
                        </label>
                      ))
                    )}
                  </div>
                  <p className="text-[10px] text-slate-400 mt-1">{selProducts.length === 0 ? 'Todos' : `${selProducts.length} seleccionado(s)`}</p>
                </div>

                {/* Tienda (solo multistore) */}
                <div>
                  <Label className="text-xs font-semibold text-slate-600">
                    Tienda {!isMultistore && <span className="text-slate-400">(N/A — proyecto single)</span>}
                  </Label>
                  <div className="mt-1 max-h-32 overflow-y-auto border border-slate-200 rounded p-2 space-y-1 bg-slate-50">
                    {!isMultistore ? (
                      <p className="text-xs text-slate-400 italic">Sin tiendas (proyecto single)</p>
                    ) : storesAvail.length === 0 ? (
                      <p className="text-xs text-slate-400 italic">Sin tiendas</p>
                    ) : (
                      storesAvail.map((s) => (
                        <label key={s.store_id} className="flex items-center gap-2 text-xs cursor-pointer hover:bg-white rounded px-1 py-0.5">
                          <Checkbox
                            checked={selStores.includes(s.store_id)}
                            onCheckedChange={() => setSelStores((cur) => toggleArrayItem(cur, s.store_id))}
                            data-testid={`filter-store-${s.store_id}`}
                          />
                          <span>{s.name}</span>
                        </label>
                      ))
                    )}
                  </div>
                  <p className="text-[10px] text-slate-400 mt-1">{selStores.length === 0 ? 'Todas' : `${selStores.length} seleccionada(s)`}</p>
                </div>
              </div>

              <div className="flex justify-end gap-2 mt-3">
                <Button variant="outline" size="sm" onClick={() => { setSelBanks([]); setSelProducts([]); setSelStores([]); setSelRifs([]); fetchReport({}); }}>
                  Limpiar
                </Button>
                <Button onClick={applyFilters} disabled={loading} size="sm" className="bg-sky-600 hover:bg-sky-700 text-white" data-testid="apply-filters-btn">
                  <Eye size={14} className="mr-1" /> Vista previa
                </Button>
              </div>
            </div>

            {/* RESUMEN POR FASE */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {PHASES.map((ph) => {
                const t = data.totals[ph];
                const cls = t.percent >= 100 ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                  : t.percent >= 50 ? 'bg-amber-50 border-amber-200 text-amber-800'
                  : t.expected > 0 ? 'bg-rose-50 border-rose-200 text-rose-800'
                  : 'bg-slate-50 border-slate-200 text-slate-500';
                return (
                  <div key={ph} className={`border rounded-lg p-3 text-center ${cls}`} data-testid={`phase-summary-${ph}`}>
                    <p className="text-xs font-semibold uppercase tracking-wide">{ph}</p>
                    <p className="text-2xl font-bold mt-1">{t.processed}/{t.expected}</p>
                    <p className="text-sm font-semibold">{t.percent}%</p>
                  </div>
                );
              })}
            </div>

            {/* MATRIZ */}
            <div className="border border-slate-200 rounded-lg overflow-hidden">
              <table className="w-full text-sm" data-testid="progress-matrix-table">
                <thead className="bg-sky-900 text-white">
                  <tr>
                    <th className="px-3 py-2 text-left font-semibold">Banco / Ente</th>
                    <th className="px-3 py-2 text-left font-semibold">Producto</th>
                    {PHASES.map((ph) => <th key={ph} className="px-3 py-2 text-center font-semibold">{ph}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {groupedRows.length === 0 ? (
                    <tr><td colSpan={6} className="text-center py-6 text-slate-400 italic">No hay datos para los filtros aplicados.</td></tr>
                  ) : groupedRows.map((g, i) => g.type === 'rif' ? (
                    <tr key={`rif-${i}`} className="bg-sky-900" data-testid="report-rif-header">
                      <td colSpan={6} className="px-3 py-2 font-extrabold text-white text-sm tracking-wide">
                        🆔 RIF {g.rif || '—'} · {g.rifName || '—'}
                      </td>
                    </tr>
                  ) : g.type === 'store' ? (
                    <tr key={`s-${i}`} className="bg-sky-50">
                      <td colSpan={6} className="px-3 py-1.5 pl-8 font-bold text-sky-900 text-sm">🏬 {g.label}</td>
                    </tr>
                  ) : (
                    <tr key={`r-${i}`} className="border-t border-slate-100">
                      <td className="px-3 py-2 font-semibold text-slate-800">{g.row.bank}</td>
                      <td className="px-3 py-2 text-slate-700">{g.row.product}</td>
                      {PHASES.map((ph) => {
                        const info = g.row.phases[ph];
                        return (
                          <td key={ph} className={`px-2 py-2 text-center text-xs ${phaseCellClass(info)}`}>
                            {info.expected === 0 ? (
                              <span>—</span>
                            ) : (
                              <>
                                <div className="font-bold">{info.processed}/{info.expected}</div>
                                <div className="text-[10px] opacity-80">{info.percent}%</div>
                              </>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cerrar</Button>
          <Button onClick={downloadPdf} disabled={pdfLoading || !data} className="bg-rose-600 hover:bg-rose-700 text-white" data-testid="download-progress-pdf">
            <FileText size={16} className="mr-1" />
            {pdfLoading ? 'Generando...' : 'Descargar PDF'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ProjectProgressReportDialog;
