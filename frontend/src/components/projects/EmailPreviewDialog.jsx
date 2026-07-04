import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Edit3, Send, ImagePlus, ClipboardList, RotateCcw } from 'lucide-react';
import { memo } from 'react';
import { ALL_TOKENS } from './projectConstants';

// Variables de inserción rápida — HOMOLOGADO con el entorno de Cotizaciones.
const QUICK_VARS = ALL_TOKENS.map(t => `{${t}}`);

// Cuerpo editable aislado y MEMOIZADO: solo se re-renderiza cuando cambia el HTML
// base (`html`). Así, escribir en el Asunto (que re-renderiza el padre) NO vuelve a
// aplicar dangerouslySetInnerHTML → las ediciones manuales del usuario persisten.
// El re-montaje para cargar HTML nuevo / restaurar plantilla se controla vía `key`
// (previewVersion) desde el padre, que fuerza el remount ignorando el memo.
const EditableEmailBody = memo(function EditableEmailBody({ html, editorRef, onPaste, onDrop }) {
  return (
    <div
      ref={editorRef}
      contentEditable
      suppressContentEditableWarning
      onPaste={onPaste}
      onDrop={onDrop}
      onDragOver={e => e.preventDefault()}
      className="p-4 bg-white min-h-[300px] max-h-[50vh] overflow-y-auto email-render max-w-none focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:ring-inset"
      dangerouslySetInnerHTML={{ __html: html || '' }}
      data-testid="preview-editable-content"
    />
  );
}, (prev, next) => prev.html === next.html);

/**
 * Editor final del correo antes de enviar. Permite ajustar asunto y cuerpo HTML
 * (contentEditable), insertar variables manualmente, pegar/arrastrar imágenes.
 * Las variables se procesan en backend al enviar.
 */
export const EmailPreviewDialog = ({
  open, onOpenChange,
  previewData, previewSubject, setPreviewSubject,
  previewSending, sendFromPreview,
  editorRef, handleEditorPaste, handleEditorDrop,
  handleInsertImage, insertVariableInEditor,
  previewVersion, onRestoreTemplate,
}) => {
  // PERSISTENCIA + RENDER CONFIABLE:
  // `key={previewVersion}` hace que el editor se MONTE de nuevo (aplicando el HTML
  // base vía dangerouslySetInnerHTML) SOLO cuando cambia la versión: al generar una
  // nueva vista previa o al pulsar "Restaurar Plantilla Base". En cualquier otro
  // re-render (editar Asunto, abrir detalles) la versión no cambia → el nodo NO se
  // re-monta y React no re-aplica el innerHTML → las ediciones manuales persisten.

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[78vw] max-w-[78vw] max-h-[90vh] overflow-y-auto" data-testid="email-preview-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Edit3 size={20} className="text-blue-500" />Editor de Envío Final</DialogTitle>
        </DialogHeader>
        {previewData && (
          <div className="space-y-3">
            {/* Editable subject + meta */}
            <div className="bg-slate-50 rounded-lg p-3 space-y-2 text-sm border border-slate-200">
              <div className="flex items-center gap-2">
                <span className="font-medium text-slate-500 min-w-[70px] shrink-0">Asunto:</span>
                <Input
                  value={previewSubject}
                  onChange={e => setPreviewSubject(e.target.value)}
                  className="h-8 text-sm font-medium"
                  data-testid="preview-subject-input"
                />
              </div>
              {previewData.recipients && (
                <div className="flex items-start gap-2">
                  <span className="font-medium text-slate-500 min-w-[70px]">Para:</span>
                  <span className="text-slate-700 text-xs">{previewData.recipients.join(', ')}</span>
                </div>
              )}
              {previewData.entity_label && (
                <div className="flex items-start gap-2">
                  <span className="font-medium text-slate-500 min-w-[70px]">Destino:</span>
                  <span className="text-slate-700 text-xs">{previewData.entity_label}</span>
                </div>
              )}
            </div>

            {/* Variables resueltas (collapsible) */}
            {previewData.variables && Object.keys(previewData.variables).length > 0 && (
              <details className="bg-blue-50 rounded-lg border border-blue-200">
                <summary className="px-3 py-2 text-xs font-semibold text-blue-700 cursor-pointer select-none">Variables Resueltas ({Object.keys(previewData.variables).length})</summary>
                <div className="px-3 pb-3 grid grid-cols-2 gap-x-4 gap-y-1">
                  {Object.entries(previewData.variables).map(([k, v]) => (
                    <div key={k} className="flex items-start gap-1.5 text-[11px]">
                      <code className="text-blue-600 font-mono shrink-0">{`{${k}}`}</code>
                      <span className="text-slate-600 truncate" title={String(v)}>{String(v || '—').slice(0, 60)}</span>
                    </div>
                  ))}
                </div>
              </details>
            )}

            {/* Editable HTML content */}
            <div className="border rounded-lg overflow-hidden">
              <div className="bg-slate-100 px-3 py-2 border-b flex items-center justify-between">
                <p className="text-xs font-semibold text-slate-500 uppercase">Contenido Editable — Modifique antes de enviar</p>
                <div className="flex items-center gap-1">
                  <Button variant="ghost" size="sm" onClick={onRestoreTemplate} className="h-7 px-2 text-xs gap-1 text-slate-500 hover:text-amber-700" data-testid="preview-restore-template-btn">
                    <RotateCcw size={14} />Restaurar Plantilla Base
                  </Button>
                  <Button variant="ghost" size="sm" onClick={handleInsertImage} className="h-7 px-2 text-xs gap-1 text-slate-600 hover:text-indigo-700" data-testid="preview-insert-image-btn">
                    <ImagePlus size={14} />Imagen
                  </Button>
                </div>
              </div>

              {/* Variables insert panel */}
              <details className="bg-indigo-50 border-b border-indigo-200">
                <summary className="px-3 py-1.5 text-[10px] font-semibold text-indigo-700 cursor-pointer select-none flex items-center gap-1">
                  <ClipboardList size={11} />Insertar Variable en el editor
                </summary>
                <div className="px-3 pb-2 flex flex-wrap gap-1">
                  {QUICK_VARS.map(v => (
                    <button key={v} type="button" onClick={() => insertVariableInEditor(v)}
                      className="text-[10px] px-1.5 py-0.5 rounded bg-white border border-indigo-200 text-indigo-600 hover:bg-indigo-100 cursor-pointer transition-all"
                      title={`Insertar ${v} en la posición del cursor`}>{v}</button>
                  ))}
                </div>
                <p className="px-3 pb-1.5 text-[9px] text-indigo-400">Las variables insertadas aquí se procesan automáticamente antes del envío.</p>
              </details>

              <EditableEmailBody
                key={previewVersion}
                html={previewData?.html}
                editorRef={editorRef}
                onPaste={handleEditorPaste}
                onDrop={handleEditorDrop}
              />
              <div className="bg-amber-50 px-3 py-1.5 border-t border-amber-200">
                <p className="text-[10px] text-amber-700">Los cambios realizados aquí solo afectan este envío. La plantilla base NO se modifica. Puede pegar imágenes directamente (Ctrl+V) o arrastrar archivos JPG/PNG.</p>
              </div>
            </div>

            <div className="flex justify-between items-center pt-2">
              <Button variant="outline" onClick={() => onOpenChange(false)} data-testid="close-preview-btn">Cancelar</Button>
              <Button
                onClick={sendFromPreview}
                disabled={previewSending}
                className="bg-emerald-600 hover:bg-emerald-700 text-white gap-2"
                data-testid="preview-send-btn"
              >
                <Send size={16} />{previewSending ? 'Enviando...' : 'Enviar Correo'}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default EmailPreviewDialog;
