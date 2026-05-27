import { useRef } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { ClipboardList, Building2, FileText, Server, CreditCard } from 'lucide-react';
import { toast } from 'sonner';
import { RichTextEditor } from '../RichTextEditor';

const VAR_GROUPS = [
  { cat: 'Cliente', icon: <Building2 size={14} className="text-blue-500" />, vars: [
    { token: 'Nombre_Cliente', desc: 'Razón social del cliente' },
    { token: 'Rif_Cliente', desc: 'RIF del cliente' },
    { token: 'Contacto_Principal', desc: 'Nombre del contacto' },
    { token: 'Datos_Contacto', desc: 'Contacto + Tel + Email' },
    { token: 'Telefono_Contacto', desc: 'Teléfono del contacto' },
    { token: 'Email_Contacto', desc: 'Correo del contacto' },
  ]},
  { cat: 'Proyecto', icon: <FileText size={14} className="text-violet-500" />, vars: [
    { token: 'Nro_Proyecto', desc: 'Número del proyecto' },
    { token: 'Ticket_Nro', desc: 'Número de ticket' },
    { token: 'Tipo_Proyecto', desc: 'Tipo de implementación' },
    { token: 'Fecha_Asignacion', desc: 'Fecha de asignación' },
    { token: 'Nombre_Sucursal', desc: 'Sucursal del cliente' },
    { token: 'Cantidad_Cajas', desc: 'Cantidad de cajas' },
  ]},
  { cat: 'Infraestructura', icon: <Server size={14} className="text-emerald-500" />, vars: [
    { token: 'Servidor_Instalacion', desc: 'Servidor asignado' },
    { token: 'Nombre_Implementador', desc: 'Implementador asignado' },
    { token: 'Correo_Implementador', desc: 'Correo del implementador' },
    { token: 'Integrador', desc: 'Nombre del integrador' },
    { token: 'Aplicativo_Integracion', desc: 'App de integración' },
  ]},
  { cat: 'Hardware', icon: <CreditCard size={14} className="text-amber-500" />, vars: [
    { token: 'Modelo_Seriales_POS', desc: 'Tabla de POS/Pinpad' },
    { token: 'Modelo_Seriales_Equipos', desc: 'Tabla de equipos' },
    { token: 'Lista_VTID', desc: 'Lista de VTIDs' },
    { token: 'Matriz_Bancos_Productos', desc: 'Matriz de bancos' },
  ]},
];

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
            <p className="text-[10px] text-slate-400 mb-3">Haz clic en una variable para copiarla al portapapeles e insertarla en el editor.</p>
            <div className="space-y-3 max-h-[430px] overflow-y-auto pr-1">
              {VAR_GROUPS.map(group => (
                <div key={group.cat}>
                  <div className="flex items-center gap-1.5 mb-1.5">
                    {group.icon}
                    <span className="text-xs font-bold text-slate-700">{group.cat}</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {group.vars.map(v => (
                      <button key={v.token} title={v.desc}
                        data-testid={`var-token-${v.token}`}
                        className="inline-flex items-center px-2 py-1 text-[11px] font-mono bg-slate-100 hover:bg-blue-100 hover:text-blue-700 border border-slate-200 hover:border-blue-300 rounded-md cursor-pointer transition-all group"
                        onClick={() => insertVar(v.token)}>
                        <span className="text-slate-500 group-hover:text-blue-500">{'{'}</span>
                        <span>{v.token}</span>
                        <span className="text-slate-500 group-hover:text-blue-500">{'}'}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default TemplatesAdminDialog;
