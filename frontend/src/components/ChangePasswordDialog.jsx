import { useState } from 'react';
import { toast } from 'sonner';
import { KeyRound, Eye, EyeOff, Check, X, Loader2 } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Button } from './ui/button';
import api from '../utils/api';

const RULES = [
  { key: 'len', label: 'Al menos 10 caracteres', test: (v) => v.length >= 10 },
  { key: 'upper', label: 'Una letra mayúscula', test: (v) => /[A-Z]/.test(v) },
  { key: 'lower', label: 'Una letra minúscula', test: (v) => /[a-z]/.test(v) },
  { key: 'num', label: 'Un número', test: (v) => /[0-9]/.test(v) },
  { key: 'special', label: 'Un carácter especial', test: (v) => /[^A-Za-z0-9]/.test(v) },
];

export const ChangePasswordDialog = ({ open, onOpenChange }) => {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNext, setShowNext] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const policyOk = RULES.every((r) => r.test(next));
  const matchOk = next.length > 0 && next === confirm;
  const differentOk = next.length === 0 || next !== current;
  const canSubmit = current.length > 0 && policyOk && matchOk && differentOk && !submitting;

  const reset = () => {
    setCurrent(''); setNext(''); setConfirm('');
    setShowCurrent(false); setShowNext(false); setSubmitting(false);
  };

  const handleClose = (o) => {
    if (!o) reset();
    onOpenChange(o);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      await api.post('/auth/change-password', {
        current_password: current,
        new_password: next,
      });
      toast.success('Contraseña actualizada correctamente.');
      reset();
      onOpenChange(false);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'No se pudo cambiar la contraseña.');
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-md" data-testid="change-password-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <KeyRound size={18} className="text-indigo-600" /> Cambiar contraseña
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="cp-current" className="text-xs">Contraseña actual</Label>
            <div className="relative">
              <Input
                id="cp-current"
                type={showCurrent ? 'text' : 'password'}
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
                autoComplete="current-password"
                data-testid="cp-current-input"
                className="pr-9"
              />
              <button
                type="button"
                onClick={() => setShowCurrent((s) => !s)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                data-testid="cp-toggle-current"
                tabIndex={-1}
              >
                {showCurrent ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="cp-new" className="text-xs">Nueva contraseña</Label>
            <div className="relative">
              <Input
                id="cp-new"
                type={showNext ? 'text' : 'password'}
                value={next}
                onChange={(e) => setNext(e.target.value)}
                autoComplete="new-password"
                data-testid="cp-new-input"
                className="pr-9"
              />
              <button
                type="button"
                onClick={() => setShowNext((s) => !s)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                data-testid="cp-toggle-new"
                tabIndex={-1}
              >
                {showNext ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="cp-confirm" className="text-xs">Confirmar nueva contraseña</Label>
            <Input
              id="cp-confirm"
              type={showNext ? 'text' : 'password'}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              autoComplete="new-password"
              data-testid="cp-confirm-input"
            />
          </div>

          {/* Checklist de política */}
          <div className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 space-y-1" data-testid="cp-policy-checklist">
            {RULES.map((r) => {
              const ok = r.test(next);
              return (
                <div key={r.key} className={`flex items-center gap-1.5 text-xs ${ok ? 'text-emerald-600' : 'text-slate-400'}`}>
                  {ok ? <Check size={13} /> : <X size={13} />} {r.label}
                </div>
              );
            })}
            <div className={`flex items-center gap-1.5 text-xs ${matchOk ? 'text-emerald-600' : 'text-slate-400'}`}>
              {matchOk ? <Check size={13} /> : <X size={13} />} Las contraseñas coinciden
            </div>
            {!differentOk && (
              <div className="flex items-center gap-1.5 text-xs text-red-500">
                <X size={13} /> Debe ser diferente a la actual
              </div>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => handleClose(false)} data-testid="cp-cancel-btn">
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={!canSubmit}
              className="bg-indigo-600 hover:bg-indigo-700"
              data-testid="cp-submit-btn"
            >
              {submitting ? <Loader2 size={16} className="mr-1.5 animate-spin" /> : <KeyRound size={16} className="mr-1.5" />}
              Actualizar contraseña
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
