import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Flag, Loader2, Trash2, CheckCircle2, Calendar, User } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

/**
 * CommitmentModal — gestión de Compromisos Gerenciales sobre un proyecto.
 *
 * Visibilidad: Cualquier usuario con acceso al proyecto puede ver la lista
 * (incluso sin permisos de gestión) para que el Implementador esté al tanto.
 * Mutación: SÓLO Coordinador / Gerente / Admin pueden crear, marcar
 * cumplido o eliminar.
 */
export function CommitmentModal({ open, onClose, projectId, projectNumber, clientName, canManage = false, onChange }) {
  const [commitments, setCommitments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [deadline, setDeadline] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open && projectId) fetchCommitments();
  }, [open, projectId]);

  const fetchCommitments = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/projects/${projectId}/commitments`);
      setCommitments(res.data || []);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al cargar compromisos');
    } finally { setLoading(false); }
  };

  const handleCreate = async () => {
    if (!message.trim()) { toast.error('Escriba el compromiso'); return; }
    setSubmitting(true);
    try {
      const res = await api.post(`/projects/${projectId}/commitments`, {
        message: message.trim(), deadline: deadline || null,
      });
      toast.success('Compromiso registrado');
      setCommitments(prev => [...prev, res.data.commitment]);
      setMessage(''); setDeadline('');
      onChange && onChange();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al crear compromiso');
    } finally { setSubmitting(false); }
  };

  const handleComplete = async (cid) => {
    if (!confirm('¿Marcar este compromiso como cumplido?')) return;
    try {
      await api.put(`/projects/${projectId}/commitments/${cid}/complete`);
      toast.success('Compromiso cumplido');
      fetchCommitments();
      onChange && onChange();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  const handleDelete = async (cid) => {
    if (!confirm('¿Eliminar este compromiso? Esta acción es irreversible.')) return;
    try {
      await api.delete(`/projects/${projectId}/commitments/${cid}`);
      toast.success('Compromiso eliminado');
      setCommitments(prev => prev.filter(c => c.commitment_id !== cid));
      onChange && onChange();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  const active = commitments.filter(c => !c.completed);
  const completed = commitments.filter(c => c.completed);

  const renderItem = (c) => {
    const overdue = c.deadline && !c.completed && new Date(c.deadline) < new Date();
    return (
      <div
        key={c.commitment_id}
        className={`rounded-lg border p-3 ${
          c.completed
            ? 'bg-emerald-50 border-emerald-200'
            : overdue
              ? 'bg-red-50 border-red-300'
              : 'bg-amber-50 border-amber-200'
        }`}
        data-testid={`commitment-item-${c.commitment_id}`}
      >
        <p className={`text-sm ${c.completed ? 'line-through text-slate-500' : 'text-slate-800'}`}>
          {c.message}
        </p>
        <div className="flex flex-wrap items-center gap-3 mt-1.5 text-[11px] text-slate-500">
          <span className="flex items-center gap-1"><User size={10} />{c.created_by_name} ({c.created_by_role})</span>
          <span className="flex items-center gap-1"><Calendar size={10} />Creado: {new Date(c.created_at).toLocaleDateString('es-VE')}</span>
          {c.deadline && (
            <span className={`flex items-center gap-1 font-semibold ${overdue ? 'text-red-700' : 'text-amber-700'}`}>
              <Flag size={10} />Fecha límite: {new Date(c.deadline).toLocaleDateString('es-VE')}
              {overdue && <span className="ml-1 bg-red-200 text-red-800 px-1 rounded">VENCIDO</span>}
            </span>
          )}
          {c.completed && c.completed_at && (
            <span className="flex items-center gap-1 text-emerald-700">
              <CheckCircle2 size={10} />Cumplido por {c.completed_by_name} · {new Date(c.completed_at).toLocaleDateString('es-VE')}
            </span>
          )}
        </div>
        {canManage && !c.completed && (
          <div className="flex gap-2 mt-2">
            <Button
              size="sm" variant="outline" className="h-7 text-xs border-emerald-300 text-emerald-700 hover:bg-emerald-50"
              onClick={() => handleComplete(c.commitment_id)}
              data-testid={`commitment-complete-${c.commitment_id}`}
            >
              <CheckCircle2 size={12} className="mr-1" />Marcar cumplido
            </Button>
            <Button
              size="sm" variant="ghost" className="h-7 text-xs text-red-600 hover:text-red-800 hover:bg-red-50"
              onClick={() => handleDelete(c.commitment_id)}
              data-testid={`commitment-delete-${c.commitment_id}`}
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
      <DialogContent className="max-w-xl max-h-[85vh] overflow-y-auto" data-testid="commitments-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            <Flag size={20} className="text-red-600" />
            Compromisos · {projectNumber || ''}
          </DialogTitle>
          <p className="text-xs text-slate-500 mt-1">
            {clientName ? `Cliente: ${clientName} · ` : ''}
            Alerta gerencial visible para el implementador asignado.
          </p>
        </DialogHeader>

        {canManage && (
          <div className="bg-slate-50 border border-slate-200 rounded p-3 mt-2">
            <p className="text-xs font-semibold text-slate-700 mb-1.5">Nuevo compromiso</p>
            <Textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Ej: Gestionar recepción de equipos VPOS con banco antes del viernes"
              rows={2}
              className="text-sm"
              data-testid="commitment-message-input"
            />
            <div className="flex items-end gap-2 mt-2">
              <div className="flex-1">
                <Label className="text-xs">Fecha límite (opcional)</Label>
                <Input
                  type="date"
                  value={deadline}
                  onChange={(e) => setDeadline(e.target.value)}
                  className="h-9"
                  data-testid="commitment-deadline-input"
                />
              </div>
              <Button
                onClick={handleCreate}
                disabled={submitting || !message.trim()}
                className="bg-red-600 hover:bg-red-700"
                data-testid="commitment-create-btn"
              >
                {submitting ? <Loader2 size={14} className="animate-spin mr-1" /> : <Flag size={14} className="mr-1" />}
                Crear
              </Button>
            </div>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-8"><Loader2 size={20} className="animate-spin text-slate-400" /></div>
        ) : (
          <div className="space-y-2 mt-2">
            {active.length > 0 && (
              <>
                <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide mt-2">Activos ({active.length})</p>
                {active.map(renderItem)}
              </>
            )}
            {completed.length > 0 && (
              <>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mt-3">Cumplidos ({completed.length})</p>
                {completed.map(renderItem)}
              </>
            )}
            {commitments.length === 0 && (
              <p className="text-xs text-slate-400 italic p-4 text-center">Sin compromisos registrados.</p>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default CommitmentModal;
