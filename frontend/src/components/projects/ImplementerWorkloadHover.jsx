import { useState, useCallback } from 'react';
import { HoverCard, HoverCardContent, HoverCardTrigger } from '../ui/hover-card';
import { Loader2, FolderKanban, Package, Activity, Gauge } from 'lucide-react';
import api from '../../utils/api';

// Tooltip enriquecido (HoverCard) con el resumen de carga de un implementador.
// Estrategia A: carga bajo demanda al abrir (con micro-retraso de 300ms de Radix),
// cacheada por user_id para no re-consultar en cada hover.
export const ImplementerWorkloadHover = ({ userId, name, assignedAt, lastFollowupAt, projectId }) => {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  const fetchSummary = useCallback(async (open) => {
    if (!open || summary || loading) return;
    setLoading(true);
    setError(false);
    try {
      const id = userId && String(userId).trim() ? userId : '_';
      const { data } = await api.get(`/projects/implementers/${encodeURIComponent(id)}/workload-summary`, {
        params: name ? { name } : undefined,
      });
      setSummary(data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [userId, name, summary, loading]);

  const Metric = ({ icon: Icon, label, value, accent }) => (
    <div className="flex items-center justify-between gap-3 py-1.5">
      <span className="flex items-center gap-1.5 text-xs text-slate-600">
        <Icon size={13} className={accent} />
        {label}
      </span>
      <span className="text-sm font-semibold text-slate-900 tabular-nums" data-testid={`workload-${label.toLowerCase().replace(/[^a-z]+/g, '-')}`}>
        {value}
      </span>
    </div>
  );

  const DualMetric = ({ icon: Icon, label, accent, asignadas, pendientes, keyName, asignTestid }) => (
    <div className="py-1.5">
      <div className="flex items-center justify-between gap-3">
        <span className="flex items-center gap-1.5 text-xs text-slate-600">
          <Icon size={13} className={accent} />
          {label}
        </span>
        <span className="flex items-center gap-2 tabular-nums">
          <span className="text-xs text-slate-500" data-testid={asignTestid || `workload-${keyName}-asignadas`}>
            <span className="text-[10px] uppercase tracking-wide text-slate-400">Asig.</span> <b className="text-slate-700">{asignadas}</b>
          </span>
          <span className="text-slate-300">·</span>
          <span className="text-xs text-amber-700" data-testid={`workload-${keyName}-pendientes`}>
            <span className="text-[10px] uppercase tracking-wide text-amber-500">Pend.</span> <b>{pendientes}</b>
          </span>
        </span>
      </div>
    </div>
  );

  return (
    <HoverCard openDelay={300} closeDelay={80} onOpenChange={fetchSummary}>
      <HoverCardTrigger asChild>
        <div>
          <span
            className="cursor-default border-b border-dotted border-slate-300 hover:text-indigo-700 hover:border-indigo-400 transition-colors"
            data-testid={`implementer-name-${projectId}`}
          >
            {name}
          </span>
          {assignedAt && (
            <p className="text-[10px] text-slate-400 mt-0.5">Asignado: {new Date(assignedAt).toLocaleDateString('es-VE')}</p>
          )}
          <p className="text-[10px] text-emerald-600 mt-0.5" data-testid={`last-followup-${projectId}`}>
            Último Seguimiento: {lastFollowupAt ? new Date(lastFollowupAt).toLocaleDateString('es-VE') : '--/--/----'}
          </p>
        </div>
      </HoverCardTrigger>
      <HoverCardContent align="start" className="w-72 p-0 overflow-hidden" data-testid={`workload-popover-${projectId}`}>
        <div className="bg-gradient-to-r from-indigo-600 to-violet-600 px-4 py-2.5">
          <p className="text-[10px] font-medium text-indigo-100 uppercase tracking-wide">Resumen de Carga</p>
          <p className="text-sm font-semibold text-white truncate">{summary?.implementer_name || name}</p>
        </div>
        <div className="p-4">
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-4 text-sm text-slate-500" data-testid="workload-loading">
              <Loader2 size={16} className="animate-spin" /> Cargando…
            </div>
          ) : error ? (
            <p className="py-3 text-center text-sm text-rose-600" data-testid="workload-error">No se pudo cargar el resumen.</p>
          ) : (
            <div className="divide-y divide-slate-100">
              <Metric icon={FolderKanban} label="Proyectos" value={summary?.projects_count ?? 0} accent="text-indigo-500" />
              <DualMetric
                icon={Package} label="Cajas" accent="text-amber-500" keyName="cajas"
                asignadas={summary?.cajas_asignadas ?? 0} pendientes={summary?.cajas_pendientes ?? 0}
              />
              <DualMetric
                icon={Activity} label="PVV" accent="text-cyan-500" keyName="pvv"
                asignTestid="workload-pvv-asignados"
                asignadas={summary?.pvv_asignados ?? 0} pendientes={summary?.pvv_pendientes ?? 0}
              />
              <div className="pt-2">
                <div className="flex items-center justify-between gap-3">
                  <span className="flex items-center gap-1.5 text-xs text-slate-600">
                    <Gauge size={13} className="text-violet-500" />
                    % Global de Avance
                  </span>
                  <span className="text-sm font-bold text-violet-700 tabular-nums" data-testid="workload-avance">{summary?.avance_global ?? 0}%</span>
                </div>
                <div className="mt-1.5 h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-violet-500 to-indigo-500 transition-all"
                    style={{ width: `${summary?.avance_global ?? 0}%` }}
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      </HoverCardContent>
    </HoverCard>
  );
};

export default ImplementerWorkloadHover;
