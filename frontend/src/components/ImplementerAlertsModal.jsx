import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { BellRing, Loader2, Trash2, CheckCircle2, Calendar, User, Eye } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

/**
 * ImplementerAlertsModal — "Mis Alertas" (autogestión del Implementador).
 *
 * A diferencia de los Compromisos (rojos, gerenciales) estas alertas son
 * PERSONALES del implementador asignado. Sólo él puede crear/completar/eliminar.
 * Admin/Coord/Gerente pueden verlas como supervisión (lectura).
 *
 * Paleta: amber/orange para diferenciar visualmente de los Compromisos rojos.
 */
export function ImplementerAlertsModal({ open, onClose, projectId, projectNumber, clientName, canManage = false, readOnly = false, onChange }) {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [deadline, setDeadline] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open && projectId) fetchAlerts();
  }, [open, projectId]);

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/projects/${projectId}/implementer-alerts`);
      setAlerts(res.data || []);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al cargar alertas');
    } finally { setLoading(false); }
  };

  const handleCreate = async () => {
    if (!message.trim()) { toast.error('Escriba su alerta'); return; }
    setSubmitting(true);
    try {
      const res = await api.post(`/projects/${projectId}/implementer-alerts`, {
        message: message.trim(), deadline: deadline || null,
      });
      toast.success('Alerta registrada');
      setAlerts(prev => [...prev, res.data.alert]);
      setMessage(''); setDeadline('');
      onChange && onChange();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al crear alerta');
    } finally { setSubmitting(false); }
  };

  const handleComplete = async (aid) => {
    if (!window.confirm('¿Marcar esta alerta como cumplida?')) return;
    try {
      await api.put(`/projects/${projectId}/implementer-alerts/${aid}/complete`);
      toast.success('Alerta cumplida');
      fetchAlerts();
      onChange && onChange();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  const handleDelete = async (aid) => {
    if (!window.confirm('¿Eliminar esta alerta? Esta acción es irreversible.')) return;
    try {
      await api.delete(`/projects/${projectId}/implementer-alerts/${aid}`);
      toast.success('Alerta eliminada');
      setAlerts(prev => prev.filter(a => a.alert_id !== aid));
      onChange && onChange();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  const active = alerts.filter(a => !a.completed);
  const completed = alerts.filter(a => a.completed);

  const renderItem = (a) => {
    const overdue = a.deadline && !a.completed && new Date(a.deadline) < new Date();
    return (
      <div
        key={a.alert_id}
        className={`rounded-lg border-l-4 border-y border-r p-3 ${
          a.completed
            ? 'bg-emerald-50 border-emerald-400 border-y-emerald-200 border-r-emerald-200'
            : overdue
              ? 'bg-orange-50 border-orange-500 border-y-orange-200 border-r-orange-200'
              : 'bg-amber-50 border-amber-500 border-y-amber-200 border-r-amber-200'
        }`}
        data-testid={`alert-item-${a.alert_id}`}
      >
        <p className={`text-sm ${a.completed ? 'line-through text-slate-500' : 'text-slate-800'}`}>
          {a.message}
        </p>
        <div className="flex flex-wrap items-center gap-3 mt-1.5 text-[11px] text-slate-500">
          <span className="flex items-center gap-1"><User size={10} />{a.created_by_name}</span>
          <span className="flex items-center gap-1"><Calendar size={10} />Creada: {new Date(a.created_at).toLocaleDateString('es-VE')}</span>
          {a.deadline && (
            <span className={`flex items-center gap-1 font-semibold ${overdue ? 'text-orange-700' : 'text-amber-700'}`}>
              <BellRing size={10} />Fecha objetivo: {new Date(a.deadline).toLocaleDateString('es-VE')}
              {overdue && <span className="ml-1 bg-orange-200 text-orange-800 px-1 rounded">VENCIDA</span>}
            </span>
          )}
          {a.completed && a.completed_at && (
            <span className="flex items-center gap-1 text-emerald-700">
              <CheckCircle2 size={10} />Cumplida · {new Date(a.completed_at).toLocaleDateString('es-VE')}
            </span>
          )}
        </div>
        {canManage && !readOnly && !a.completed && (
          <div className="flex gap-2 mt-2">
            <Button
              size="sm" variant="outline" className="h-7 text-xs border-emerald-300 text-emerald-700 hover:bg-emerald-50"
              onClick={() => handleComplete(a.alert_id)}
              data-testid={`alert-complete-${a.alert_id}`}
            >
              <CheckCircle2 size={12} className="mr-1" />Marcar cumplida
            </Button>
            <Button
              size="sm" variant="ghost" className="h-7 text-xs text-red-600 hover:text-red-800 hover:bg-red-50"
              onClick={() => handleDelete(a.alert_id)}
              data-testid={`alert-delete-${a.alert_id}`}
            >
              <Trash2 size={12} className="mr-1" />Eliminar
            </Button>
          </div>
        )}
      </div>
    );
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-xl max-h-[85vh] overflow-y-auto" data-testid="implementer-alerts-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            <BellRing size={20} className="text-amber-600" />
            Mis Alertas · {projectNumber || ''}
          </DialogTitle>
          <p className="text-xs text-slate-500 mt-1">
            {clientName ? `Cliente: ${clientName} · ` : ''}
            {readOnly
              ? 'Vista de supervisión (solo lectura). Estas alertas son personales del implementador.'
              : 'Recordatorios personales para tu gestión. No reemplazan los compromisos del coordinador.'}
          </p>
        </DialogHeader>

        {canManage && !readOnly && (
          <div className="bg-amber-50 border border-amber-200 rounded p-3 mt-2">
            <p className="text-xs font-semibold text-amber-800 mb-1.5 flex items-center gap-1">
              <BellRing size={12} />Nueva alerta personal
            </p>
            <Textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Ej: Revisar configuración Testeado del banco BNC mañana 3pm"
              rows={2}
              className="text-sm bg-white"
              data-testid="alert-message-input"
            />
            <div className="flex items-end gap-2 mt-2">
              <div className="flex-1">
                <Label className="text-xs">Fecha objetivo (opcional)</Label>
                <Input
                  type="date"
                  value={deadline}
                  onChange={(e) => setDeadline(e.target.value)}
                  className="h-9 bg-white"
                  data-testid="alert-deadline-input"
                />
              </div>
              <Button
                onClick={handleCreate}
                disabled={submitting || !message.trim()}
                className="bg-amber-600 hover:bg-amber-700 text-white"
                data-testid="alert-create-btn"
              >
                {submitting ? <Loader2 size={14} className="animate-spin mr-1" /> : <BellRing size={14} className="mr-1" />}
                Crear
              </Button>
            </div>
          </div>
        )}

        {readOnly && (
          <div className="bg-slate-50 border border-slate-200 rounded p-2 mt-2 flex items-center gap-2">
            <Eye size={14} className="text-slate-500" />
            <p className="text-[11px] text-slate-600">Supervisión: solo lectura. El implementador gestiona estas alertas.</p>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-8"><Loader2 size={20} className="animate-spin text-slate-400" /></div>
        ) : (
          <div className="space-y-2 mt-2">
            {active.length > 0 && (
              <>
                <p className="text-xs font-semibold text-amber-700 uppercase tracking-wide mt-2">Pendientes ({active.length})</p>
                {active.map(renderItem)}
              </>
            )}
            {completed.length > 0 && (
              <>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mt-3">Cumplidas ({completed.length})</p>
                {completed.map(renderItem)}
              </>
            )}
            {alerts.length === 0 && (
              <p className="text-xs text-slate-400 italic p-4 text-center">Sin alertas personales registradas.</p>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default ImplementerAlertsModal;
