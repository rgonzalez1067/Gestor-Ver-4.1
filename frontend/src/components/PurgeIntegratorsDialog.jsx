import { useState, memo } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { AlertCircle, Trash2, ShieldAlert } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

/**
 * Diálogo aislado para purga de integradores.
 * - Paso 1: confirmar con "BORRAR TODO" → borra los sin cotizaciones/proyectos.
 * - Paso 2: si quedaron protegidos, pregunta si desea forzar cascada (borra integradores + cotizaciones + proyectos).
 *
 * Aislado en componente propio para evitar re-renders del monolito Integrators.jsx mientras se escribe.
 */
const PurgeIntegratorsDialog = memo(function PurgeIntegratorsDialog({ open, onOpenChange, onSuccess }) {
  const [step, setStep] = useState('confirm'); // 'confirm' | 'cascade'
  const [confirmText, setConfirmText] = useState('');
  const [cascadeConfirmText, setCascadeConfirmText] = useState('');
  const [loading, setLoading] = useState(false);
  const [protectedItems, setProtectedItems] = useState([]);
  const [firstPhaseDeleted, setFirstPhaseDeleted] = useState(0);

  const reset = () => {
    setStep('confirm');
    setConfirmText('');
    setCascadeConfirmText('');
    setLoading(false);
    setProtectedItems([]);
    setFirstPhaseDeleted(0);
  };

  const handleClose = (o) => {
    if (!o) reset();
    onOpenChange(o);
  };

  const handleSafePurge = async () => {
    if (confirmText !== 'BORRAR TODO') {
      toast.error('Debe escribir exactamente: BORRAR TODO');
      return;
    }
    setLoading(true);
    try {
      const res = await api.delete('/integrators/bulk/all');
      const { deleted_count = 0, protected: prot = [] } = res.data || {};
      setFirstPhaseDeleted(deleted_count);
      if (prot.length > 0) {
        // Queda segundo paso: preguntar cascada
        setProtectedItems(prot);
        setStep('cascade');
        setLoading(false);
        if (deleted_count > 0) {
          toast.success(`Se eliminaron ${deleted_count} integrador(es).`);
        }
        return;
      }
      // Todo borrado sin bloqueos
      toast.success(res.data.message || 'Integradores eliminados');
      onSuccess?.();
      handleClose(false);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al vaciar la BD');
      setLoading(false);
    }
  };

  const handleCascadePurge = async () => {
    if (cascadeConfirmText !== 'FORZAR CASCADA') {
      toast.error('Debe escribir exactamente: FORZAR CASCADA');
      return;
    }
    setLoading(true);
    try {
      const res = await api.delete('/integrators/bulk/all?force_cascade=true');
      toast.success(res.data.message || 'Eliminación en cascada completada');
      onSuccess?.();
      handleClose(false);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al forzar cascada');
      setLoading(false);
    }
  };

  const handleKeepProtected = () => {
    if (firstPhaseDeleted > 0) {
      toast.success(`Se conservaron ${protectedItems.length} integrador(es) con asociaciones.`);
    } else {
      toast.info(`Ningún integrador fue eliminado. ${protectedItems.length} tienen cotizaciones/proyectos.`);
    }
    onSuccess?.();
    handleClose(false);
  };

  const totalQuotes = protectedItems.reduce((s, p) => s + (p.quotes_count || 0), 0);
  const totalProjects = protectedItems.reduce((s, p) => s + (p.projects_count || 0), 0);

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-md" data-testid="purge-integrators-dialog">
        {step === 'confirm' && (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-rose-600">
                <AlertCircle size={22} /> Vaciar Base de Datos
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <div className="bg-rose-50 border border-rose-200 rounded-lg p-3 text-sm text-rose-800">
                <p className="font-semibold mb-1">Acción irreversible</p>
                <p className="text-xs">Esto eliminará todos los integradores <b>sin cotizaciones ni proyectos asociados</b>. Los que tengan asociaciones se conservarán y te preguntaremos a continuación si deseas forzar su eliminación en cascada.</p>
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-700">
                  Para confirmar, escriba exactamente: <span className="text-rose-600 font-mono">BORRAR TODO</span>
                </label>
                <Input
                  value={confirmText}
                  onChange={(e) => setConfirmText(e.target.value)}
                  placeholder="BORRAR TODO"
                  className="mt-1 font-mono"
                  data-testid="purge-confirm-input"
                  autoFocus
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-3 border-t">
              <Button variant="outline" onClick={() => handleClose(false)} data-testid="purge-cancel-btn">Cancelar</Button>
              <Button
                onClick={handleSafePurge}
                disabled={loading || confirmText !== 'BORRAR TODO'}
                className="bg-rose-600 hover:bg-rose-700 text-white"
                data-testid="purge-confirm-btn"
              >
                {loading ? 'Eliminando...' : <><Trash2 size={14} className="mr-1" />Eliminar</>}
              </Button>
            </div>
          </>
        )}

        {step === 'cascade' && (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-amber-600">
                <ShieldAlert size={22} /> Integradores con asociaciones
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-900">
                {firstPhaseDeleted > 0 && (
                  <p className="text-xs mb-2">Se eliminaron <b>{firstPhaseDeleted}</b> integrador(es) sin asociaciones.</p>
                )}
                <p className="font-semibold mb-1">Quedan {protectedItems.length} integrador(es) protegido(s)</p>
                <p className="text-xs">Tienen <b>{totalQuotes}</b> cotización(es){totalProjects > 0 ? <> y <b>{totalProjects}</b> proyecto(s)</> : null} asociadas. ¿Deseas forzar el borrado en cascada (integradores + todas sus cotizaciones y proyectos)?</p>
              </div>
              <div className="max-h-40 overflow-y-auto border rounded-lg p-2 bg-slate-50 text-xs">
                {protectedItems.map((p) => (
                  <div key={p.integrator_id} className="flex items-center justify-between py-1 border-b last:border-b-0">
                    <span className="font-medium text-slate-700">{p.name}</span>
                    <span className="text-slate-500">
                      {p.quotes_count > 0 && <span className="mr-2">{p.quotes_count} cot.</span>}
                      {p.projects_count > 0 && <span>{p.projects_count} proy.</span>}
                    </span>
                  </div>
                ))}
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-700">
                  Para forzar cascada, escriba exactamente: <span className="text-rose-600 font-mono">FORZAR CASCADA</span>
                </label>
                <Input
                  value={cascadeConfirmText}
                  onChange={(e) => setCascadeConfirmText(e.target.value)}
                  placeholder="FORZAR CASCADA"
                  className="mt-1 font-mono"
                  data-testid="cascade-confirm-input"
                  autoFocus
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-3 border-t">
              <Button variant="outline" onClick={handleKeepProtected} data-testid="cascade-keep-btn">
                Conservar y cerrar
              </Button>
              <Button
                onClick={handleCascadePurge}
                disabled={loading || cascadeConfirmText !== 'FORZAR CASCADA'}
                className="bg-rose-700 hover:bg-rose-800 text-white"
                data-testid="cascade-confirm-btn"
              >
                {loading ? 'Eliminando...' : <><Trash2 size={14} className="mr-1" />Forzar cascada</>}
              </Button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
});

export default PurgeIntegratorsDialog;
