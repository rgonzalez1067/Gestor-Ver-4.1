import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { Button } from '../ui/button';
import { Landmark } from 'lucide-react';

/**
 * Sub-modal relacional reutilizable: dado un Procesador, lista sus bancos
 * vinculados (Procesador → Banco final) para consolidar una adquirencia.
 * Homologa el comportamiento del patrocinio de implementación, patrocinio de
 * Pinpads y provisión de seriales, evitando duplicar la misma UI en cada flujo.
 *
 * Props:
 *  - open: bool
 *  - processor: objeto banco con type === 'Procesador'
 *  - linkedBanks: array de bancos vinculados (precomputado por el caller)
 *  - onSelect(bank): callback al elegir el banco final
 *  - onClose(): cierra el modal
 *  - description: nodo/texto contextual (opcional)
 *  - testid: base para data-testid del modal/empty/cancel (ej. 'processor-link')
 *  - linkedTestid: prefijo para los botones de banco (ej. 'processor-linked-bank')
 */
export const ProcessorLinkBankModal = ({
  open,
  processor,
  linkedBanks = [],
  onSelect,
  onClose,
  description,
  testid = 'processor-link',
  linkedTestid = 'processor-linked-bank',
}) => (
  <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
    <DialogContent className="max-w-md" data-testid={`${testid}-modal`}>
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2">
          <Landmark size={18} className="text-indigo-600" />
          Banco vinculado al Procesador
        </DialogTitle>
        <DialogDescription>
          {description || (
            <>
              <strong>{processor?.name}</strong> es un <strong>Procesador</strong>.
              Seleccione el banco que operará la transacción.
            </>
          )}
        </DialogDescription>
      </DialogHeader>
      <div className="space-y-3">
        {linkedBanks.length === 0 ? (
          <div className="text-center py-6 text-sm text-amber-700 bg-amber-50 rounded-lg" data-testid={`${testid}-empty`}>
            No hay bancos asociados a este procesador. Vincúlelos desde la ficha del banco
            (campo &quot;Procesador&quot;) en el maestro de Bancos.
          </div>
        ) : (
          <div className="space-y-1.5 max-h-[320px] overflow-y-auto">
            {linkedBanks.map((b) => (
              <button
                key={b.bank_id}
                type="button"
                onClick={() => onSelect(b)}
                className="w-full text-left px-3 py-2.5 rounded-lg border-2 border-slate-200 hover:border-indigo-400 hover:bg-indigo-50/60 transition-all text-sm font-medium text-slate-700 flex items-center justify-between"
                data-testid={`${linkedTestid}-${b.bank_id}`}
              >
                <span>{b.name}</span>
                <span className="text-[10px] text-slate-400">{b.type}</span>
              </button>
            ))}
          </div>
        )}
        <div className="flex justify-end pt-1">
          <Button variant="outline" size="sm" onClick={onClose} data-testid={`${testid}-cancel`}>
            Cancelar
          </Button>
        </div>
      </div>
    </DialogContent>
  </Dialog>
);

export default ProcessorLinkBankModal;
