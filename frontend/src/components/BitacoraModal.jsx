// ============================================================================
// BitacoraModal — Modal unificado de bitácora
// ============================================================================
// Componente reutilizable usado por Clientes Y Contacto Inicial. La idea es
// tener UNA SOLA UX para registrar gestiones, fechas de seguimiento (que se
// reflejan en el Dashboard como alertas), persona contactada, y check de
// completado.
//
// Props:
//   open: boolean
//   onOpenChange: (v: boolean) => void
//   entityId: string — id del Cliente o Contacto Inicial
//   entityName: string — nombre a mostrar en el header
//   contacts: [{id, name, role}] — opciones del select "Persona contactada"
//   apiPrefix: string — "clients" para clientes, "initial-contacts" para C.I.
//                       (lee/escribe en /api/{prefix}/{id}/logs y
//                        /api/{prefix}/logs/{logId}/complete)
//   originBadge: string|null — si se setea, cada log con origin === este valor
//                              recibe un badge de origen (audit trail).
// ============================================================================
import { useState, useEffect, useCallback } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Badge } from './ui/badge';
import { BookOpen, Plus, CheckCircle, Circle } from 'lucide-react';
import { toast } from 'sonner';
import api from '../utils/api';

const EMPTY_LOG = { detail: '', action: '', follow_up_date: '', contacted_person: '' };

export default function BitacoraModal({
  open,
  onOpenChange,
  entityId,
  entityName,
  contacts = [],
  apiPrefix = 'clients',
  originBadge = null,
  // Iter56: callback que se dispara cada vez que se crea o completa una
  // entrada de bitácora. Permite al padre (ej. listado de Contactos Iniciales)
  // refrescar columnas dependientes (last_contact_date / next_contact_date)
  // de forma inmediata sin necesidad de cerrar el modal ni recargar.
  onLogCreated = null,
}) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [newLog, setNewLog] = useState(EMPTY_LOG);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    if (!entityId) return;
    setLoading(true);
    try {
      const res = await api.get(`/${apiPrefix}/${entityId}/logs`);
      setLogs(res.data || []);
    } catch {
      setLogs([]);
    } finally {
      setLoading(false);
    }
  }, [entityId, apiPrefix]);

  useEffect(() => {
    if (open) {
      load();
      setNewLog(EMPTY_LOG);
    }
  }, [open, load]);

  const handleAdd = async () => {
    if (!newLog.detail.trim()) {
      toast.error('El detalle es obligatorio');
      return;
    }
    setSubmitting(true);
    try {
      const res = await api.post(`/${apiPrefix}/${entityId}/logs`, {
        detail: newLog.detail.trim(),
        action: newLog.action.trim() || null,
        follow_up_date: newLog.follow_up_date || null,
        contacted_person: newLog.contacted_person || null,
      });
      setLogs((prev) => [res.data, ...prev]);
      setNewLog(EMPTY_LOG);
      toast.success('Entrada de bitácora registrada');
      // Iter56: avisar al padre para refrescar la grilla en línea.
      onLogCreated?.(res.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error al registrar la entrada');
    } finally {
      setSubmitting(false);
    }
  };

  const toggleComplete = async (logId) => {
    try {
      const res = await api.patch(`/${apiPrefix}/logs/${logId}/complete`);
      setLogs((prev) =>
        prev.map((l) => (l.log_id === logId ? { ...l, is_completed: res.data.is_completed } : l))
      );
    } catch {
      toast.error('Error al actualizar');
    }
  };

  const todayIso = new Date().toISOString().split('T')[0];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-2xl max-h-[85vh] overflow-y-auto"
        data-testid="bitacora-modal"
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            <BookOpen size={20} className="text-blue-600" />
            Bitácora — {entityName}
          </DialogTitle>
        </DialogHeader>

        {/* Form: nueva entrada */}
        <div className="bg-slate-50 rounded-lg border p-4 space-y-3">
          <h4 className="text-sm font-semibold text-slate-700">Nueva entrada</h4>
          <div>
            <Label className="text-xs">Detalle del contacto *</Label>
            <Textarea
              value={newLog.detail}
              onChange={(e) => setNewLog((p) => ({ ...p, detail: e.target.value }))}
              placeholder="Resumen de la interacción..."
              rows={2}
              data-testid="log-detail-input"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs">Acción / Compromiso adquirido</Label>
              <Input
                value={newLog.action}
                onChange={(e) => setNewLog((p) => ({ ...p, action: e.target.value }))}
                placeholder="Ej: Llamar para confirmar recepción"
                data-testid="log-action-input"
              />
            </div>
            <div>
              <Label className="text-xs">Persona contactada</Label>
              <Select
                value={newLog.contacted_person}
                onValueChange={(v) => setNewLog((p) => ({ ...p, contacted_person: v }))}
              >
                <SelectTrigger data-testid="log-contact-select" className="h-9">
                  <SelectValue placeholder="Seleccione contacto..." />
                </SelectTrigger>
                <SelectContent>
                  {contacts.length === 0 && (
                    <div className="px-2 py-1.5 text-xs text-slate-400">Sin contactos</div>
                  )}
                  {contacts.map((c) => (
                    <SelectItem key={c.id || c.name} value={c.name}>
                      {c.name}
                      {c.role ? ` (${c.role})` : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs">Fecha de seguimiento (alerta en Dashboard)</Label>
              <Input
                type="date"
                value={newLog.follow_up_date}
                onChange={(e) => setNewLog((p) => ({ ...p, follow_up_date: e.target.value }))}
                data-testid="log-followup-input"
              />
            </div>
          </div>
          <Button
            size="sm"
            onClick={handleAdd}
            disabled={submitting}
            className="bg-blue-600 hover:bg-blue-700"
            data-testid="log-submit-btn"
          >
            <Plus size={14} className="mr-1" />
            Registrar
          </Button>
        </div>

        {/* Histórico de entradas */}
        <div className="mt-4 space-y-2">
          {loading ? (
            <div className="text-center py-8 text-slate-400">Cargando bitácora...</div>
          ) : logs.length === 0 ? (
            <div className="text-center py-8 text-slate-400">No hay entradas en la bitácora</div>
          ) : (
            logs.map((log) => {
              const isOverdue =
                log.follow_up_date && !log.is_completed && log.follow_up_date < todayIso;
              const showOriginBadge = originBadge && log.origin === originBadge;
              return (
                <div
                  key={log.log_id}
                  className={`p-3 rounded-lg border ${
                    log.is_completed
                      ? 'bg-green-50/50 border-green-200'
                      : isOverdue
                      ? 'bg-red-50/50 border-red-200'
                      : 'bg-white border-slate-200'
                  }`}
                  data-testid={`log-entry-${log.log_id}`}
                >
                  <div className="flex items-start gap-2">
                    <button
                      onClick={() => toggleComplete(log.log_id)}
                      className="mt-0.5 shrink-0"
                      data-testid={`log-toggle-${log.log_id}`}
                    >
                      {log.is_completed ? (
                        <CheckCircle size={16} className="text-green-600" />
                      ) : (
                        <Circle size={16} className={isOverdue ? 'text-red-400' : 'text-slate-300'} />
                      )}
                    </button>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <p
                          className={`text-sm flex-1 ${
                            log.is_completed ? 'line-through text-slate-400' : 'text-slate-800'
                          }`}
                        >
                          {log.detail}
                        </p>
                        {showOriginBadge && (
                          <Badge
                            variant="secondary"
                            className="text-[10px] bg-amber-100 text-amber-800 shrink-0"
                            title="Esta entrada proviene del módulo Contacto Inicial"
                          >
                            Origen: Contacto Inicial
                          </Badge>
                        )}
                      </div>
                      {log.action && (
                        <p className="text-xs text-blue-600 mt-1 font-medium">
                          Acción/Compromiso: {log.action}
                        </p>
                      )}
                      {log.contacted_person && (
                        <p className="text-xs text-purple-600 mt-0.5 font-medium">
                          Contacto: {log.contacted_person}
                        </p>
                      )}
                      <div className="flex items-center gap-3 mt-1.5 text-xs text-slate-400 flex-wrap">
                        <span>Fecha: {log.contact_date}</span>
                        {log.created_at && (
                          <span className="text-blue-500 font-medium">
                            {new Date(log.created_at).toLocaleTimeString('es-VE', {
                              hour: '2-digit',
                              minute: '2-digit',
                              hour12: true,
                            })}
                          </span>
                        )}
                        {log.follow_up_date && (
                          <span
                            className={`px-1.5 py-0.5 rounded ${
                              isOverdue && !log.is_completed
                                ? 'bg-red-100 text-red-600 font-medium'
                                : 'bg-slate-100'
                            }`}
                          >
                            Seguimiento: {log.follow_up_date}
                          </span>
                        )}
                        <span>Por: {log.created_by_name || log.created_by}</span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
