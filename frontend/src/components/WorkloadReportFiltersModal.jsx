import { useState, useEffect, useMemo } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Checkbox } from './ui/checkbox';
import { FileText, Filter, Loader2, X } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const QUOTE_TYPES = ['VPOS', 'VPOS_MULTIRIF', 'MPOS', 'GATEWAY', 'LINK'];
const TYPE_LABELS = { VPOS_MULTIRIF: 'VPOS Multi-RIF', GATEWAY: 'Payment Gateway', LINK: 'Link de Pago' };
const STATUS_OPTIONS = [
  'Pendiente por Asignar',
  'Asignado / En Proceso',
  'En proceso/reasignado',
  'Suspendido por Cliente',
  'Suspendido por Banco',
  'Finalizado / Producción',
];

// Botón-chip de selección múltiple (módulo-level para no recrearlo en cada render).
const Chip = ({ active, onClick, children, testid }) => (
  <button
    type="button" onClick={onClick}
    data-testid={testid}
    className={`px-2.5 py-1 rounded-full text-[11px] font-medium border transition ${
      active
        ? 'bg-indigo-600 text-white border-indigo-700 shadow-sm'
        : 'bg-white text-slate-700 border-slate-300 hover:border-indigo-400 hover:text-indigo-700'
    }`}
  >
    {children}
  </button>
);

/**
 * Modal de filtros para el Reporte de Carga PDF.
 * Soporta multi-selección en Implementador Actual, Implementador Original,
 * Estatus y Tipo de Proyecto. Búsqueda libre por Cliente.
 */
export function WorkloadReportFiltersModal({ open, onClose }) {
  const [projects, setProjects] = useState([]);
  const [loadingMeta, setLoadingMeta] = useState(false);
  const [generating, setGenerating] = useState(false);

  const [assignedTo, setAssignedTo] = useState([]);      // current implementers
  const [originalImpl, setOriginalImpl] = useState([]);  // reassigned from
  const [statuses, setStatuses] = useState([]);
  const [types, setTypes] = useState([]);
  const [clientSearch, setClientSearch] = useState('');
  const [groupBy, setGroupBy] = useState('implementer'); // 'implementer' | 'type'

  useEffect(() => {
    if (!open) return undefined;
    let cancelled = false;
    const loadMeta = async () => {
      setLoadingMeta(true);
      try {
        const r = await api.get('/projects');
        if (!cancelled) setProjects(r.data || []);
      } catch {
        if (!cancelled) toast.error('Error cargando proyectos');
      } finally {
        if (!cancelled) setLoadingMeta(false);
      }
    };
    loadMeta();
    return () => { cancelled = true; };
  }, [open]);

  const assignedOptions = useMemo(() => {
    const s = new Set();
    projects.forEach(p => s.add(p.assigned_to_name || 'Sin asignar'));
    return [...s].sort();
  }, [projects]);

  const originalOptions = useMemo(() => {
    const s = new Set();
    projects.forEach(p => { if (p.reassigned_from_name) s.add(p.reassigned_from_name); });
    return [...s].sort();
  }, [projects]);

  const resetFilters = () => {
    setAssignedTo([]); setOriginalImpl([]); setStatuses([]); setTypes([]); setClientSearch(''); setGroupBy('implementer');
  };

  const toggle = (arr, setArr, value) => {
    setArr(arr.includes(value) ? arr.filter(v => v !== value) : [...arr, value]);
  };

  const generate = async () => {
    setGenerating(true);
    try {
      const params = new URLSearchParams();
      assignedTo.forEach(v => params.append('assigned_to', v));
      originalImpl.forEach(v => params.append('original_implementer', v));
      statuses.forEach(v => params.append('status', v));
      types.forEach(v => params.append('quote_type', v));
      if (clientSearch.trim()) params.append('client', clientSearch.trim());
      params.append('group_by', groupBy);

      const token = localStorage.getItem('session_token');
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
      const res = await fetch(`${BACKEND_URL}/api/projects/reports/workload-pdf?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('fail');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      onClose();
    } catch {
      toast.error('Error al generar el reporte');
    } finally { setGenerating(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="workload-filters-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            <Filter size={18} className="text-indigo-600" />
            Filtros — Reporte de Carga y Estatus
          </DialogTitle>
          <p className="text-xs text-slate-500 mt-1">
            Seleccione uno o varios criterios. Los filtros se aplican con &quot;Y&quot; (intersección) entre categorías y con &quot;O&quot; (unión) dentro de la misma categoría.
          </p>
        </DialogHeader>

        {loadingMeta ? (
          <div className="flex items-center justify-center py-10"><Loader2 size={22} className="animate-spin text-slate-400" /></div>
        ) : (
          <div className="space-y-4 mt-2">
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
              <Label className="text-xs font-semibold text-slate-700">Agrupar el reporte por</Label>
              <div className="flex gap-2 mt-1.5" data-testid="workload-groupby">
                <button
                  type="button"
                  onClick={() => setGroupBy('implementer')}
                  data-testid="groupby-implementer"
                  className={`flex-1 px-3 py-2 rounded-md text-xs font-semibold border transition ${groupBy === 'implementer' ? 'bg-indigo-600 text-white border-indigo-700 shadow-sm' : 'bg-white text-slate-700 border-slate-300 hover:border-indigo-400'}`}
                >
                  Implementador
                </button>
                <button
                  type="button"
                  onClick={() => setGroupBy('type')}
                  data-testid="groupby-type"
                  className={`flex-1 px-3 py-2 rounded-md text-xs font-semibold border transition ${groupBy === 'type' ? 'bg-indigo-600 text-white border-indigo-700 shadow-sm' : 'bg-white text-slate-700 border-slate-300 hover:border-indigo-400'}`}
                >
                  Tipo de Proyecto
                </button>
              </div>
              <p className="text-[10px] text-slate-400 mt-1.5">
                {groupBy === 'type'
                  ? 'El PDF se segmenta por Tipo de Proyecto (VPOS, MPOS, Payment Gateway, Link de Pago) con subtotales y un resumen del mix comercial.'
                  : 'El PDF se agrupa por implementador con ranking de carga por PVV.'}
              </p>
            </div>

            <div>
              <Label className="text-xs font-semibold text-slate-700">Implementador Actual</Label>
              <div className="flex flex-wrap gap-1.5 mt-1.5">
                {assignedOptions.length === 0 && <p className="text-[11px] text-slate-400 italic">Sin opciones</p>}
                {assignedOptions.map(name => (
                  <Chip key={name} active={assignedTo.includes(name)} onClick={() => toggle(assignedTo, setAssignedTo, name)}
                    testid={`filter-assigned-${name.replace(/\s+/g, '-')}`}>{name}</Chip>
                ))}
              </div>
            </div>

            <div>
              <Label className="text-xs font-semibold text-slate-700">Implementador Original <span className="text-slate-400 font-normal">(para proyectos reasignados)</span></Label>
              <div className="flex flex-wrap gap-1.5 mt-1.5">
                {originalOptions.length === 0 && <p className="text-[11px] text-slate-400 italic">No hay proyectos reasignados.</p>}
                {originalOptions.map(name => (
                  <Chip key={name} active={originalImpl.includes(name)} onClick={() => toggle(originalImpl, setOriginalImpl, name)}
                    testid={`filter-original-${name.replace(/\s+/g, '-')}`}>{name}</Chip>
                ))}
              </div>
            </div>

            <div>
              <Label className="text-xs font-semibold text-slate-700">Estatus</Label>
              <div className="flex flex-wrap gap-1.5 mt-1.5">
                {STATUS_OPTIONS.map(s => (
                  <Chip key={s} active={statuses.includes(s)} onClick={() => toggle(statuses, setStatuses, s)}
                    testid={`filter-status-${s.replace(/[\s/]+/g, '-')}`}>{s}</Chip>
                ))}
              </div>
            </div>

            <div>
              <Label className="text-xs font-semibold text-slate-700">Tipo de Proyecto</Label>
              <div className="flex flex-wrap gap-1.5 mt-1.5">
                {QUOTE_TYPES.map(t => (
                  <Chip key={t} active={types.includes(t)} onClick={() => toggle(types, setTypes, t)}
                    testid={`filter-type-${t}`}>{TYPE_LABELS[t] || t}</Chip>
                ))}
              </div>
            </div>

            <div>
              <Label className="text-xs font-semibold text-slate-700">Cliente <span className="text-slate-400 font-normal">(razón social, fantasía o RIF)</span></Label>
              <Input
                placeholder="Buscar por nombre o RIF…"
                value={clientSearch}
                onChange={(e) => setClientSearch(e.target.value)}
                className="mt-1.5"
                data-testid="filter-client-input"
              />
            </div>
          </div>
        )}

        <div className="flex items-center justify-between pt-4 border-t mt-4">
          <Button variant="ghost" size="sm" onClick={resetFilters} data-testid="filter-reset-btn">
            <X size={14} className="mr-1" />Limpiar filtros
          </Button>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={onClose} data-testid="filter-cancel-btn">Cancelar</Button>
            <Button
              onClick={generate}
              disabled={generating || loadingMeta}
              className="bg-indigo-600 hover:bg-indigo-700 text-white"
              data-testid="filter-generate-btn"
            >
              {generating ? <Loader2 size={14} className="animate-spin mr-1" /> : <FileText size={14} className="mr-1" />}
              Generar PDF
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default WorkloadReportFiltersModal;
