import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Eye } from 'lucide-react';

/**
 * Visualizador del detalle de un correo enviado (asunto, destinatarios, fecha,
 * adjuntos y contenido). Read-only.
 */
export const EmailDetailViewer = ({ open, onOpenChange, data }) => {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto" data-testid="email-detail-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Eye size={20} className="text-indigo-500" />Detalle del Correo</DialogTitle>
        </DialogHeader>
        {data && (
          <div className="space-y-3">
            <div className="bg-slate-50 rounded-lg p-3 space-y-2 text-sm">
              <div><span className="font-medium text-slate-600">Asunto:</span> <span className="text-slate-800">{data.subject}</span></div>
              <div><span className="font-medium text-slate-600">Destinatarios:</span> <span className="text-slate-800">{data.recipients?.join(', ')}</span></div>
              {data.level && <div><span className="font-medium text-slate-600">Nivel:</span> <span className="text-slate-800">{data.level}</span></div>}
              <div><span className="font-medium text-slate-600">Fecha:</span> <span className="text-slate-800">{data.sent_at ? new Date(data.sent_at).toLocaleString('es-VE') : '—'}</span></div>
              {data.attachments?.length > 0 && (
                <div><span className="font-medium text-slate-600">Adjuntos:</span> <span className="text-slate-800">{data.attachments.map(a => a.filename).join(', ')}</span></div>
              )}
            </div>
            <div className="border rounded-lg p-4">
              <p className="text-xs font-medium text-slate-500 uppercase mb-2">Contenido</p>
              {data.message ? (
                <div className="text-sm text-slate-800 whitespace-pre-wrap">{data.message}</div>
              ) : data.html_content ? (
                <div className="text-sm text-slate-800 prose prose-sm max-w-none" dangerouslySetInnerHTML={{ __html: data.html_content }} />
              ) : (
                <p className="text-sm text-slate-400">Sin contenido disponible</p>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default EmailDetailViewer;
