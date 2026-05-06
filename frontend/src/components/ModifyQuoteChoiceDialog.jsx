import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { Button } from './ui/button';
import { Copy, RotateCcw, AlertTriangle } from 'lucide-react';

/**
 * Modal de elección al ejecutar "Modificar Cotización".
 *
 * El usuario decide entre:
 *  - new_version: crea nueva cotización con número siguiente (no rompe la original).
 *  - in_place: reinicia la MISMA cotización a Borrador, mantiene número original.
 *    Útil para preservar la secuencia y regenerar anexos perdidos.
 */
export function ModifyQuoteChoiceDialog({ open, onClose, quote, onChoose }) {
  if (!quote) return null;
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg" data-testid="modify-quote-choice-dialog">
        <DialogHeader>
          <DialogTitle>Modificar Cotización · {quote.quote_number}</DialogTitle>
          <DialogDescription>
            Elige cómo deseas modificar esta cotización. Esta decisión afecta la secuencia
            de números y los anexos asociados.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 mt-2">
          <button
            type="button"
            onClick={() => onChoose('new_version')}
            className="w-full text-left p-4 border-2 border-blue-200 hover:border-blue-500 hover:bg-blue-50 rounded-lg transition-colors group"
            data-testid="modify-choice-new-version"
          >
            <div className="flex items-start gap-3">
              <Copy size={20} className="text-blue-600 mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <div className="font-semibold text-slate-900 group-hover:text-blue-700">
                  Generar nueva cotización
                </div>
                <p className="text-sm text-slate-600 mt-1">
                  Crea una nueva cotización con el siguiente número de la secuencia. La
                  cotización original queda intacta como histórico. <strong>Comportamiento
                  por defecto.</strong>
                </p>
              </div>
            </div>
          </button>

          <button
            type="button"
            onClick={() => onChoose('in_place')}
            className="w-full text-left p-4 border-2 border-amber-200 hover:border-amber-500 hover:bg-amber-50 rounded-lg transition-colors group"
            data-testid="modify-choice-in-place"
          >
            <div className="flex items-start gap-3">
              <RotateCcw size={20} className="text-amber-600 mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <div className="font-semibold text-slate-900 group-hover:text-amber-700">
                  Mantener cotización original
                </div>
                <p className="text-sm text-slate-600 mt-1">
                  Conserva el número {quote.quote_number} y reinicia la cotización al
                  estado Borrador. Útil para regenerar el PDF/anexos sin romper la
                  secuencia.
                </p>
                <div className="mt-2 flex items-start gap-1.5 text-xs text-amber-700 bg-amber-100/60 rounded px-2 py-1">
                  <AlertTriangle size={12} className="mt-0.5 flex-shrink-0" />
                  <span>
                    Se borrarán los anexos actuales y los timestamps de fases (envío,
                    aprobación, factura, etc.). Quedará registrado en bitácora quién y
                    cuándo lo hizo.
                  </span>
                </div>
              </div>
            </div>
          </button>
        </div>

        <div className="flex justify-end mt-4">
          <Button variant="outline" onClick={onClose} data-testid="modify-choice-cancel">
            Cancelar
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
