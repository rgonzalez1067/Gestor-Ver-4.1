import { useState, useEffect, useMemo } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { UserCog, ArrowRight, Loader2, AlertTriangle } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

/**
 * Modal de Reasignación Masiva de Proyectos.
 * Sólo Coordinadores / Gerentes / Admin pueden ejecutarlo (backend valida).
 * Flujo:
 *   1. Elige Implementador Origen → muestra sus proyectos activos
 *   2. Selecciona proyectos (checkboxes, seleccionar todos)
 *   3. Elige Implementador Destino
 *   4. Aplica → registra reassignment_history y cambia status a 'En proceso/reasignado'
 */
export function BulkReassignModal({ open, onClose, onSuccess, implementadores = [], projects = [] }) {
  const [fromUserId, setFromUserId] = useState('');
  const [toUserId, setToUserId] = useState('');
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [submitting, setSubmitting] = useState(false);

  // Al abrir / cerrar, resetear
  useEffect(() => {
    if (!open) {
      setFromUserId(''); setToUserId(''); setSelectedIds(new Set()); setSubmitting(false);
    }
  }, [open]);

  // Proyectos activos del implementador origen (excluye Finalizados)
  const eligibleProjects = useMemo(() => {
    if (!fromUserId) return [];
    return projects.filter(p =>
      p.assigned_to_user_id === fromUserId &&
      p.status !== 'Finalizado / Producción',
    );
  }, [fromUserId, projects]);

  // Reset selección cuando cambia el origen
  useEffect(() => { setSelectedIds(new Set()); }, [fromUserId]);

  const toggleAll = () => {
    if (selectedIds.size === eligibleProjects.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(eligibleProjects.map(p => p.project_id)));
    }
  };

  const toggleOne = (pid) => {
    const next = new Set(selectedIds);
    if (next.has(pid)) next.delete(pid); else next.add(pid);
    setSelectedIds(next);
  };

  const handleApply = async () => {
    if (!toUserId) { toast.error('Seleccione el implementador destino'); return; }
    if (selectedIds.size === 0) { toast.error('Seleccione al menos un proyecto'); return; }
    if (fromUserId === toUserId) { toast.error('Origen y destino no pueden ser iguales'); return; }
    const toName = implementadores.find(u => u.user_id === toUserId)?.full_name || '';
    if (!confirm(
      `¿Confirmar reasignación de ${selectedIds.size} proyecto(s) a ${toName}?\n\n` +
      `Los proyectos cambiarán a estatus "En proceso/reasignado" y se registrará el implementador anterior en el historial.`
    )) return;
    setSubmitting(true);
    try {
      const res = await api.post('/projects/bulk-reassign', {
        from_user_id: fromUserId,
        to_user_id: toUserId,
        project_ids: [...selectedIds],
      });
      toast.success(res.data.message || 'Reasignación completada');
      onSuccess && onSuccess();
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al reasignar');
    } finally { setSubmitting(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="bulk-reassign-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            <UserCog size={20} className="text-purple-600" />
            Reasignación Masiva de Proyectos
          </DialogTitle>
          <p className="text-xs text-slate-500 mt-1">
            Transfiere proyectos activos entre implementadores. Deja rastro en el historial y cambia el estatus a "En proceso/reasignado".
          </p>
        </DialogHeader>

        <div className="bg-purple-50 border border-purple-200 rounded p-3 text-xs text-purple-900 flex items-start gap-2 mt-2">
          <AlertTriangle size={14} className="text-purple-600 mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold">Acción gerencial restringida.</p>
            <p>Solo Coordinador, Gerente o Admin. El implementador original queda registrado en `reassignment_history`.</p>
          </div>
        </div>

        {/* Paso 1: Origen */}
        <div className="mt-3">
          <label className="block text-sm font-semibold text-slate-700 mb-1">1. Implementador Origen</label>
          <Select value={fromUserId || '_none_'} onValueChange={(v) => setFromUserId(v === '_none_' ? '' : v)}>
            <SelectTrigger data-testid="bulk-reassign-from-select" className="h-9">
              <SelectValue placeholder="Seleccionar implementador origen..." />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="_none_">Seleccionar...</SelectItem>
              {implementadores.map(u => (
                <SelectItem key={u.user_id} value={u.user_id}>{u.full_name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Paso 2: Lista */}
        {fromUserId && (
          <div className="mt-3">
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-sm font-semibold text-slate-700">
                2. Proyectos activos ({eligibleProjects.length})
              </label>
              {eligibleProjects.length > 0 && (
                <Button
                  size="sm" variant="ghost" className="h-7 text-xs"
                  onClick={toggleAll}
                  data-testid="bulk-reassign-select-all-btn"
                >
                  {selectedIds.size === eligibleProjects.length ? 'Deseleccionar todos' : 'Seleccionar todos'}
                </Button>
              )}
            </div>
            <div className="border rounded max-h-64 overflow-y-auto bg-white">
              {eligibleProjects.length === 0 ? (
                <p className="text-xs text-slate-400 italic p-4 text-center">Este implementador no tiene proyectos activos.</p>
              ) : eligibleProjects.map(p => (
                <label
                  key={p.project_id}
                  className="flex items-center gap-2 px-3 py-2 border-b border-slate-50 hover:bg-slate-50 cursor-pointer"
                  data-testid={`bulk-reassign-project-row-${p.project_id}`}
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.has(p.project_id)}
                    onChange={() => toggleOne(p.project_id)}
                    className="h-4 w-4"
                    data-testid={`bulk-reassign-checkbox-${p.project_id}`}
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-slate-800 truncate">{p.client_name}</p>
                    <p className="text-[11px] text-slate-500 flex items-center gap-2">
                      <span>{p.quote_type || '—'}</span>
                      <span>·</span>
                      <span>{p.status}</span>
                    </p>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Paso 3: Destino + Aplicar */}
        {fromUserId && selectedIds.size > 0 && (
          <div className="mt-3">
            <label className="block text-sm font-semibold text-slate-700 mb-1">3. Implementador Destino</label>
            <div className="flex gap-2">
              <Select value={toUserId || '_none_'} onValueChange={(v) => setToUserId(v === '_none_' ? '' : v)}>
                <SelectTrigger data-testid="bulk-reassign-to-select" className="h-9 flex-1">
                  <SelectValue placeholder="Seleccionar destino..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="_none_">Seleccionar...</SelectItem>
                  {implementadores.filter(u => u.user_id !== fromUserId).map(u => (
                    <SelectItem key={u.user_id} value={u.user_id}>{u.full_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                onClick={handleApply}
                disabled={submitting || !toUserId || selectedIds.size === 0}
                className="bg-purple-600 hover:bg-purple-700"
                data-testid="bulk-reassign-apply-btn"
              >
                {submitting ? <Loader2 size={14} className="animate-spin mr-1" /> : <ArrowRight size={14} className="mr-1" />}
                Reasignar {selectedIds.size}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default BulkReassignModal;
