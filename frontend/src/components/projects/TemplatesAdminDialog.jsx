import { useRef, useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip';
import { ClipboardList, FileText, Sparkles, Search, Plus, Pencil, Trash2 } from 'lucide-react';
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
  // Campo activo (donde se insertará la variable): 'subject' o 'body'.
  const [activeField, setActiveField] = useState('body');
  // Búsqueda dentro del panel de variables.
  const [varSearch, setVarSearch] = useState('');

  const insertVar = (token) => {
    const tag = `{${token}}`;
    // Inserta en el ASUNTO si el cursor está allí.
    if (activeField === 'subject') {
      const el = document.getElementById('project-tpl-subject');
      if (el) {
        const start = el.selectionStart ?? (el.value?.length || 0);
        const end = el.selectionEnd ?? (el.value?.length || 0);
        const text = templateForm.subject || '';
        const newText = text.substring(0, start) + tag + text.substring(end);
        setTemplateForm(p => ({ ...p, subject: newText }));
        setTimeout(() => {
          el.focus();
          const pos = start + tag.length;
          el.setSelectionRange(pos, pos);
        }, 50);
        toast.success(`Insertado: ${tag}`);
        return;
      }
    }
    // Por defecto: inserta EN LA POSICIÓN DEL CURSOR del editor TipTap (cuerpo).
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
      <DialogContent className="max-w-6xl" data-testid="templates-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><ClipboardList size={20} className="text-slate-600" />Gestionar Plantillas de Correo</DialogTitle>
        </DialogHeader>
        <div className="grid grid-cols-12 gap-4 min-h-[480px]">
          {/* Lista de plantillas */}
          <div className="col-span-3 border-r border-slate-200 pr-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs font-semibold text-slate-500 uppercase">
                Plantillas <span className="text-slate-300 mx-0.5">·</span> <span className="text-slate-400">{emailTemplates.length}</span>
              </p>
              <button
                type="button"
                onClick={() => { setEditingTemplateId(null); setTemplateForm({ name: '', subject: '', body: '' }); }}
                className="inline-flex items-center gap-1 text-[11px] font-semibold text-blue-600 hover:text-blue-700 hover:bg-blue-50 px-2 py-1 rounded-md transition-colors"
                data-testid="new-template-btn"
              >
                <Plus size={13} /> Nueva
              </button>
            </div>
            <TooltipProvider delayDuration={150}>
              <div className="space-y-1.5 max-h-[500px] overflow-y-auto pr-1 -mr-1">
                {emailTemplates.length === 0 ? (
                  <div className="text-center py-12 px-3">
                    <div className="w-11 h-11 mx-auto rounded-full bg-slate-100 flex items-center justify-center mb-2.5">
                      <FileText size={18} className="text-slate-400" />
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">Aún no hay plantillas.<br />Crea la primera con “Nueva”.</p>
                  </div>
                ) : emailTemplates.map(t => {
                  const active = editingTemplateId === t.template_id;
                  const loadTpl = () => { setEditingTemplateId(t.template_id); setTemplateForm({ name: t.name, subject: t.subject, body: t.body_html || t.body || '' }); };
                  return (
                    <div key={t.template_id}
                      role="button"
                      tabIndex={0}
                      onClick={loadTpl}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); loadTpl(); } }}
                      className={`group relative flex items-start gap-2.5 p-2.5 pr-2 rounded-xl border cursor-pointer transition-all duration-150 ${active ? 'bg-blue-50/70 border-blue-300 ring-1 ring-blue-200 shadow-sm' : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50'}`}
                      data-testid={`template-item-${t.template_id}`}>
                      {active && <span className="absolute left-0 top-2.5 bottom-2.5 w-1 rounded-full bg-blue-500" />}
                      <div className={`shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${active ? 'bg-blue-500 text-white' : 'bg-slate-100 text-slate-500 group-hover:bg-blue-100 group-hover:text-blue-600'}`}>
                        <FileText size={15} />
                      </div>
                      <div className="min-w-0 flex-1 py-0.5">
                        <p className={`text-sm font-semibold truncate ${active ? 'text-blue-900' : 'text-slate-800'}`}>{t.name}</p>
                        <p className="text-[11px] text-slate-500 truncate mt-0.5">{t.subject || 'Sin asunto'}</p>
                      </div>
                      {/* Acciones (aparecen al hover/focus) */}
                      <div className="absolute right-1.5 top-1.5 flex items-center gap-0.5 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity duration-150">
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button type="button"
                              onClick={(e) => { e.stopPropagation(); loadTpl(); }}
                              className="w-7 h-7 inline-flex items-center justify-center rounded-lg bg-white/80 backdrop-blur text-slate-400 hover:text-blue-600 hover:bg-blue-50 border border-transparent hover:border-blue-200 transition-colors"
                              data-testid={`edit-template-${t.template_id}`} aria-label="Editar plantilla">
                              <Pencil size={13} />
                            </button>
                          </TooltipTrigger>
                          <TooltipContent side="top" className="text-[11px]">Editar</TooltipContent>
                        </Tooltip>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button type="button"
                              onClick={(e) => { e.stopPropagation(); handleDeleteTemplate(t.template_id); }}
                              className="w-7 h-7 inline-flex items-center justify-center rounded-lg bg-white/80 backdrop-blur text-slate-400 hover:text-red-600 hover:bg-red-50 border border-transparent hover:border-red-200 transition-colors"
                              data-testid={`delete-template-${t.template_id}`} aria-label="Eliminar plantilla">
                              <Trash2 size={13} />
                            </button>
                          </TooltipTrigger>
                          <TooltipContent side="top" className="text-[11px]">Eliminar</TooltipContent>
                        </Tooltip>
                      </div>
                    </div>
                  );
                })}
              </div>
            </TooltipProvider>
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
                <Input id="project-tpl-subject" placeholder="Asunto predeterminado del correo" value={templateForm.subject}
                  onChange={e => setTemplateForm(p => ({ ...p, subject: e.target.value }))}
                  onFocus={() => setActiveField('subject')}
                  className="h-9 text-sm mt-1" data-testid="template-subject" />
              </div>
              <div onFocusCapture={() => setActiveField('body')}>
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
            <p className="text-xs font-semibold text-slate-500 uppercase mb-2">Variables Disponibles</p>
            <p className="text-[10px] text-slate-400 mb-2">
              Clic en una variable para insertarla donde tengas el cursor (Asunto o Cuerpo). Pasa el cursor sobre ella para ver una vista previa.
              <span className="block mt-0.5 font-semibold text-slate-500">
                Insertando en: {activeField === 'subject' ? 'Asunto' : 'Cuerpo'}
              </span>
            </p>
            <div className="relative mb-3">
              <Search size={13} className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-400" />
              <Input
                value={varSearch}
                onChange={(e) => setVarSearch(e.target.value)}
                placeholder="Buscar variable..."
                className="h-8 pl-7 text-xs"
                data-testid="var-search"
              />
            </div>
            <TooltipProvider delayDuration={150}>
              <div className="space-y-3 max-h-[400px] overflow-y-auto pr-1">
                {(() => {
                  const q = varSearch.trim().toLowerCase();
                  const filtered = VARIABLE_CATEGORIES
                    .map(group => ({
                      ...group,
                      vars: q
                        ? group.vars.filter(v =>
                            v.key.toLowerCase().includes(q) ||
                            (v.label || '').toLowerCase().includes(q) ||
                            group.cat.toLowerCase().includes(q))
                        : group.vars,
                    }))
                    .filter(group => group.vars.length > 0);
                  if (filtered.length === 0) {
                    return (
                      <p className="text-xs text-slate-400 text-center py-4" data-testid="var-no-results">
                        No se encontraron variables para "{varSearch}".
                      </p>
                    );
                  }
                  return filtered.map(group => {
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
                  });
                })()}
              </div>
            </TooltipProvider>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default TemplatesAdminDialog;
