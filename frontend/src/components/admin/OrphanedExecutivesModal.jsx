import { useState, useEffect, useCallback } from 'react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../ui/select';
import { RefreshCw, UserX, ArrowRight, CheckCircle2, ShieldAlert } from 'lucide-react';
import api from '../../utils/api';
import { toast } from 'sonner';

/**
 * Herramienta de Administrador para SANAR registros huérfanos creados al borrar
 * un usuario que tenía cotizaciones/proyectos (su `user_id` quedó referenciado
 * pero el usuario ya no existe).
 *
 * - Diagnóstico: GET /admin/executives/orphaned
 * - Reasignación: POST /admin/executives/reassign?from_user_id=&to_user_id=
 *   (reasigna cotizaciones, históricas, proyectos y remapea los overrides de acciones).
 */
export const OrphanedExecutivesModal = ({ open, onOpenChange, activeUsers = [], onResolved }) => {
  const [loading, setLoading] = useState(false);
  const [orphans, setOrphans] = useState([]);
  const [targets, setTargets] = useState({}); // { from_user_id: to_user_id }
  const [working, setWorking] = useState(null);

  const userLabel = (u) =>
    `${u.first_name || ''} ${u.last_name || ''}`.trim() || u.name || u.email || u.user_id;

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.get('/admin/executives/orphaned');
      setOrphans(res.data?.orphaned || []);
    } catch (e) {
      toast.error('No se pudo cargar el diagnóstico de huérfanos');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      setTargets({});
      load();
    }
  }, [open, load]);

  const reassign = async (fromId) => {
    const toId = targets[fromId];
    if (!toId) {
      toast.error('Seleccione el usuario destino');
      return;
    }
    try {
      setWorking(fromId);
      const res = await api.post(
        `/admin/executives/reassign?from_user_id=${encodeURIComponent(fromId)}&to_user_id=${encodeURIComponent(toId)}`
      );
      const r = res.data?.reassigned || {};
      const total = (r.quotes || 0) + (r.quote_history || 0) + (r.projects_created || 0) +
        (r.projects_assigned || 0) + (r.overrides || 0) + (r.custom_actions || 0);
      toast.success(
        `Reasignados ${total} registro(s) → ${res.data?.to_user_email || toId} ` +
        `(${r.quotes || 0} cotiz., ${r.projects_created + r.projects_assigned || 0} proy., ${(r.overrides || 0) + (r.custom_actions || 0)} acción/es)`
      );
      await load();
      onResolved?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error al reasignar');
    } finally {
      setWorking(null);
    }
  };

  const sortedActive = [...activeUsers]
    .filter((u) => u.is_active !== false)
    .sort((a, b) => userLabel(a).localeCompare(userLabel(b)));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl" data-testid="orphaned-executives-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <UserX className="h-5 w-5 text-amber-600" />
            Reasignar Ejecutivos Huérfanos
          </DialogTitle>
          <DialogDescription>
            Cotizaciones/proyectos cuyo ejecutivo fue eliminado quedan "huérfanos" (solo
            visibles para el Admin). Asígnelos a un usuario activo para restaurar la
            visibilidad y arreglar los overrides de acciones.
          </DialogDescription>
        </DialogHeader>

        <div className="flex items-center justify-between">
          <span className="text-xs text-slate-500">
            {loading ? 'Cargando…' : `${orphans.length} ejecutivo(s) huérfano(s)`}
          </span>
          <Button variant="outline" size="sm" onClick={load} disabled={loading} data-testid="orphan-refresh">
            <RefreshCw className={`h-4 w-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
            Actualizar
          </Button>
        </div>

        <div className="max-h-[55vh] overflow-y-auto space-y-2 mt-1">
          {!loading && orphans.length === 0 && (
            <div className="flex flex-col items-center justify-center py-10 text-center" data-testid="orphan-empty">
              <CheckCircle2 className="h-10 w-10 text-emerald-500 mb-2" />
              <p className="text-sm font-medium text-slate-700">No hay registros huérfanos</p>
              <p className="text-xs text-slate-400">Todas las cotizaciones y proyectos tienen un ejecutivo válido.</p>
            </div>
          )}

          {orphans.map((o) => (
            <div
              key={o.user_id}
              className="border border-amber-200 bg-amber-50/40 rounded-lg p-3"
              data-testid={`orphan-row-${o.user_id}`}
            >
              <div className="flex items-center gap-2 flex-wrap">
                <ShieldAlert className="h-4 w-4 text-amber-600 shrink-0" />
                <span className="text-xs font-mono text-slate-600">{o.user_id}</span>
                {o.sample_name && (
                  <span className="text-xs font-semibold text-slate-800">· {o.sample_name}</span>
                )}
                <div className="flex items-center gap-1.5 ml-auto">
                  {o.quotes > 0 && <Badge variant="secondary" className="text-[10px]">{o.quotes} cotiz.</Badge>}
                  {o.quote_history > 0 && <Badge variant="secondary" className="text-[10px]">{o.quote_history} hist.</Badge>}
                  {o.projects > 0 && <Badge variant="secondary" className="text-[10px]">{o.projects} proy.</Badge>}
                  {o.overrides > 0 && <Badge variant="secondary" className="text-[10px]">{o.overrides} acción/es</Badge>}
                </div>
              </div>

              <div className="flex items-center gap-2 mt-3">
                <span className="text-xs text-slate-500 shrink-0">Reasignar a:</span>
                <Select
                  value={targets[o.user_id] || ''}
                  onValueChange={(v) => setTargets((p) => ({ ...p, [o.user_id]: v }))}
                >
                  <SelectTrigger className="h-9 text-xs flex-1" data-testid={`orphan-target-select-${o.user_id}`}>
                    <SelectValue placeholder="Seleccione usuario activo…" />
                  </SelectTrigger>
                  <SelectContent className="max-h-64">
                    {sortedActive.map((u) => (
                      <SelectItem key={u.user_id} value={u.user_id} className="text-xs">
                        {userLabel(u)} <span className="text-slate-400">· {u.email}</span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  size="sm"
                  onClick={() => reassign(o.user_id)}
                  disabled={working === o.user_id || !targets[o.user_id]}
                  data-testid={`orphan-reassign-btn-${o.user_id}`}
                >
                  {working === o.user_id ? (
                    <RefreshCw className="h-4 w-4 animate-spin" />
                  ) : (
                    <>Reasignar <ArrowRight className="h-4 w-4 ml-1" /></>
                  )}
                </Button>
              </div>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default OrphanedExecutivesModal;
