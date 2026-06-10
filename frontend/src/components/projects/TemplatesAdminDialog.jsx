import { useRef } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip';
import { ClipboardList, FileText, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { RichTextEditor, getExampleValue } from '../RichTextEditor';
import { VARIABLE_CATEGORIES, VARIABLE_ICON_MAP } from '../email/templateVariables';

/**
 * Diálogo de administración (CRUD) de plantillas de correo del proyecto.
 * Layout 3 columnas: lista de plantillas (3) | formulario (6) | diccionario de variables (3).
 */
export const TemplatesAdminDialog = ({
  open, onOpenChange,
  emailTemplates,
  editingTemplateId, setEditingTemplateId,
  templateForm, setTemplateForm,
  templateSaving,
  handleSaveTemplate, handleDeleteTemplate,
}) => {
  const editorRef = useRef(null);

  const insertVar = (token) => {
    const tag = `{${token}}`;
    // Inserta el token EN LA POSICIÓN DEL CURSOR del editor TipTap.
    if (editorRef.current?.insertText) {
      editorRef.current.insertText(tag);
      toast.success(`Insertado: ${tag}`);
      return;
    }
    // Fallback: append al final (en caso de que el editor aún no esté listo)
    setTemplateForm(p => ({ ...p, body: (p.body || '') + tag }));
    toast.success(`Insertado: ${tag}`);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl" data-testid="templates-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><ClipboardList size={20} className="text-slate-600" />Gestionar Plantillas de Correo</DialogTitle>
        </DialogHeader>
        <div className="grid grid-cols-12 gap-4 min-h-[400px]">
          {/* Lista de plantillas */}
          <div className="col-span-3 border-r border-slate-200 pr-4">
            <p className="text-xs font-semibold text-slate-500 uppercase mb-3">Plantillas Registradas</p>
            <div className="space-y-2 max-h-[450px] overflow-y-auto">
              {emailTemplates.length === 0 ? (
                <p className="text-sm text-slate-400 text-center py-8">No hay plantillas registradas</p>
              ) : emailTemplates.map(t => (
                <div key={t.template_id}
                  className={`p-3 rounded-lg border cursor-pointer transition-all ${editingTemplateId === t.template_id ? 'bg-blue-50 border-blue-300' : 'bg-white border-slate-200 hover:border-slate-300'}`}
                  data-testid={`template-item-${t.template_id}`}>
                  <p className="text-sm font-semibold text-slate-800">{t.name}</p>
                  <p className="text-xs text-slate-500 mt-0.5 truncate">Asunto: {t.subject}</p>
                  {t.body && <p className="text-xs text-slate-400 mt-1 line-clamp-2">{t.body.slice(0, 100)}{t.body.length > 100 ? '...' : ''}</p>}
                  <div className="flex gap-2 mt-2">
                    <Button variant="outline" size="sm" className="h-7 text-xs gap-1" data-testid={`edit-template-${t.template_id}`}
                      onClick={() => { setEditingTemplateId(t.template_id); setTemplateForm({ name: t.name, subject: t.subject, body: t.body_html || t.body || '' }); }}>
                      Editar
                    </Button>
                    <Button variant="outline" size="sm" className="h-7 text-xs gap-1 text-red-500 hover:text-red-700 border-red-200 hover:border-red-300"
                      data-testid={`delete-template-${t.template_id}`}
                      onClick={() => handleDeleteTemplate(t.template_id)}>
                      Eliminar
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Formulario */}
          <div className="col-span-6">
            <p className="text-xs font-semibold text-slate-500 uppercase mb-3">{editingTemplateId ? 'Editar Plantilla' : 'Nueva Plantilla'}</p>
            <div className="space-y-3">
              <div>
                <Label className="text-sm">Nombre <span className="text-red-500">*</span></Label>
                <Input placeholder="Ej: Solicitud de acceso, Confirmación de pruebas..." value={templateForm.name}
                  onChange={e => setTemplateForm(p => ({ ...p, name: e.target.value }))}
                  className="h-9 text-sm mt-1" data-testid="template-name" />
              </div>
              <div>
                <Label className="text-sm">Asunto <span className="text-red-500">*</span></Label>
                <Input placeholder="Asunto predeterminado del correo" value={templateForm.subject}
                  onChange={e => setTemplateForm(p => ({ ...p, subject: e.target.value }))}
                  className="h-9 text-sm mt-1" data-testid="template-subject" />
              </div>
              <div>
                <Label className="text-sm">Cuerpo del mensaje</Label>
                <RichTextEditor
                  ref={editorRef}
                  value={templateForm.body}
                  onChange={(html) => setTemplateForm(p => ({ ...p, body: html }))}
                  maxChars={20000}
                  hardLimit={false}
                  placeholder="Redacte aquí el contenido del correo. Use el panel lateral para insertar variables."
                  testid="project-tpl-editor"
                  showPreview
                  minHeight={240}
                  maxHeight={420}
                />
              </div>
              <div className="flex gap-2 pt-2">
                <Button onClick={handleSaveTemplate} disabled={templateSaving || !templateForm.name.trim() || !templateForm.subject.trim()}
                  className="bg-blue-600 hover:bg-blue-700 text-white text-sm" data-testid="save-template-btn">
                  {templateSaving ? 'Guardando...' : editingTemplateId ? 'Actualizar Plantilla' : 'Crear Plantilla'}
                </Button>
                {editingTemplateId && (
                  <Button variant="outline" onClick={() => { setEditingTemplateId(null); setTemplateForm({ name: '', subject: '', body: '' }); }}
                    className="text-sm">Nueva Plantilla</Button>
                )}
              </div>
            </div>
          </div>

          {/* Diccionario de variables */}
          <div className="col-span-3 border-l border-slate-200 pl-4">
            <p className="text-xs font-semibold text-slate-500 uppercase mb-3">Variables Disponibles</p>
            <p className="text-[10px] text-slate-400 mb-3">Haz clic en una variable para insertarla en el editor. Pasa el cursor sobre ella para ver una vista previa del dato.</p>
            <TooltipProvider delayDuration={150}>
              <div className="space-y-3 max-h-[430px] overflow-y-auto pr-1">
                {VARIABLE_CATEGORIES.map(group => {
                  const IconComp = VARIABLE_ICON_MAP[group.icon] || FileText;
                  return (
                  <div key={group.cat}>
                    <div className="flex items-center gap-1.5 mb-1.5">
                      <IconComp size={14} className={group.iconColor} />
                      <span className="text-xs font-bold text-slate-700">{group.cat}</span>
                    </div>
                    <div className="flex flex-wrap gap-1.5 mb-2">
                      {group.vars.map(v => {
                        const demo = getExampleValue(v.key);
                        return (
                          <Tooltip key={v.key}>
                            <TooltipTrigger asChild>
                              <button
                                type="button"
                                data-testid={`var-token-${v.key}`}
                                className="inline-flex items-center px-2 py-1 text-[11px] font-mono bg-slate-100 hover:bg-blue-100 hover:text-blue-700 border border-slate-200 hover:border-blue-300 rounded-md cursor-pointer transition-all group"
                                onClick={() => insertVar(v.key)}
                              >
                                <span className="text-slate-500 group-hover:text-blue-500">{'{'}</span>
                                <span>{v.key}</span>
                                <span className="text-slate-500 group-hover:text-blue-500">{'}'}</span>
                              </button>
                            </TooltipTrigger>
                            <TooltipContent
                              side="left"
                              align="start"
                              className="max-w-[260px] p-0 overflow-hidden bg-slate-900 text-white border-slate-800 shadow-xl"
                              data-testid={`var-tooltip-${v.key}`}
                            >
                              <div className="px-3 pt-2 pb-1.5 border-b border-slate-700">
                                <p className="text-[10px] uppercase tracking-wide text-slate-400 font-semibold">{v.label}</p>
                                <p className="text-[11px] font-mono text-blue-300 mt-0.5">{'{'}{v.key}{'}'}</p>
                              </div>
                              <div className="px-3 py-2 bg-slate-950">
                                <div className="flex items-center gap-1.5 mb-1">
                                  <Sparkles size={10} className="text-amber-300" />
                                  <span className="text-[9px] uppercase tracking-wider text-amber-300 font-bold">Vista previa</span>
                                </div>
                                {demo ? (
                                  <p className="text-[12px] text-white leading-snug break-words" data-testid={`var-demo-${v.key}`}>
                                    {demo}
                                  </p>
                                ) : (
                                  <p className="text-[11px] text-slate-400 italic">Se mostrará el valor real al enviar el correo.</p>
                                )}
                              </div>
                            </TooltipContent>
                          </Tooltip>
                        );
                      })}
                    </div>
                  </div>
                  );
                })}
              </div>
            </TooltipProvider>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default TemplatesAdminDialog;
