import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from './ui/dialog';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { MessageSquare, AlertCircle } from 'lucide-react';

export const JustificationModal = ({ open, onClose, onConfirm, quoteNumber, version }) => {
  const [justification, setJustification] = useState('');
  const [saving, setSaving] = useState(false);

  const handleConfirm = async () => {
    if (justification.length < 20) return;
    setSaving(true);
    try {
      await onConfirm(justification);
    } finally {
      setSaving(false);
      setJustification('');
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) { setJustification(''); onClose(); } }}>
      <DialogContent className="max-w-md" data-testid="impl-justify-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-blue-500" /> Justificación de Cambio
          </DialogTitle>
          <DialogDescription>
            Se generará la versión <span className="font-bold text-blue-600">v{(version || 1) + 1}</span> de {quoteNumber}. Indique el motivo del cambio.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <Textarea
            value={justification}
            onChange={(e) => setJustification(e.target.value)}
            maxLength={300}
            rows={4}
            placeholder="Ej: Ajuste de tarifas por negociación comercial..."
            data-testid="impl-justification-input"
          />
          <div className="flex justify-between items-center">
            <span className={`text-xs font-semibold ${justification.length < 20 ? 'text-rose-500' : 'text-emerald-500'}`}>
              {justification.length}/300 (mín. 20)
            </span>
            {justification.length < 20 && (
              <span className="text-xs text-rose-400 flex items-center gap-1">
                <AlertCircle className="w-3 h-3" /> Mínimo 20 caracteres
              </span>
            )}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => { setJustification(''); onClose(); }}>Cancelar</Button>
          <Button
            disabled={justification.length < 20 || saving}
            onClick={handleConfirm}
            className="bg-slate-900 hover:bg-slate-800"
            data-testid="impl-confirm-save-btn"
          >
            {saving ? 'Guardando...' : 'Confirmar y Guardar'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default JustificationModal;
