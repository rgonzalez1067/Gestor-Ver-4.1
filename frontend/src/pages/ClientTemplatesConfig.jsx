import { useState, useEffect, useRef } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { ArrowLeft, FileText, Upload, Trash2, Plus, Save, Pencil, FileUp } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import { usePermission } from '../hooks/usePermission';

const VARIABLES_HINT = '{{nombre}}, {{rif}}, {{email}}, {{contacto}}, {{direccion}}, {{telefono}}, {{nombre_comercial}}';

export const ClientTemplatesConfig = () => {
  const navigate = useNavigate();
  const { user: currentUser } = usePermission('clientes');
  const isAdmin = currentUser?.role === 'admin';

  const [activeTab, setActiveTab] = useState('plantillas');
  // Templates
  const [templates, setTemplates] = useState([]);
  const [tplDialogOpen, setTplDialogOpen] = useState(false);
  const [editingTpl, setEditingTpl] = useState(null);
  const [tplForm, setTplForm] = useState({ name: '', subject: '', body_html: '' });
  // Documents
  const [documents, setDocuments] = useState([]);
  const [docDialogOpen, setDocDialogOpen] = useState(false);
  const [docForm, setDocForm] = useState({ name: '', description: '', category: 'General' });
  const [docFile, setDocFile] = useState(null);
  const fileRef = useRef(null);

  const fetchTemplates = () => api.get('/email-templates?context=CLIENTES').then(r => setTemplates(r.data || [])).catch(() => {});
  const fetchDocuments = () => api.get('/client-documents').then(r => setDocuments(r.data || [])).catch(() => {});

  useEffect(() => { fetchTemplates(); fetchDocuments(); }, []);

  // ===== TEMPLATES =====
  const openNewTemplate = () => {
    setEditingTpl(null);
    setTplForm({ name: '', subject: '', body_html: '' });
    setTplDialogOpen(true);
  };
  const openEditTemplate = (tpl) => {
    setEditingTpl(tpl);
    setTplForm({ name: tpl.name, subject: tpl.subject || '', body_html: tpl.body_html || tpl.body || '' });
    setTplDialogOpen(true);
  };
  const saveTemplate = async () => {
    if (!tplForm.name.trim()) { toast.error('El nombre es obligatorio'); return; }
    try {
      if (editingTpl) {
        await api.put(`/email-templates/${editingTpl.template_id}`, {
          template_id: editingTpl.template_id,
          ...tplForm,
          context: 'CLIENTES',
          is_active: true,
        });
        toast.success('Plantilla actualizada');
      } else {
        const newId = `cli_tpl_${Date.now().toString(36)}`;
        await api.post('/email-templates', {
          template_id: newId,
          ...tplForm,
          context: 'CLIENTES',
          is_active: true,
        });
        toast.success('Plantilla creada');
      }
      setTplDialogOpen(false);
      fetchTemplates();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al guardar'); }
  };
  const deleteTemplate = async (tpl) => {
    if (!confirm(`¿Eliminar plantilla "${tpl.name}"?`)) return;
    try {
      await api.delete(`/email-templates/${tpl.template_id}`);
      toast.success('Plantilla eliminada');
      fetchTemplates();
    } catch { toast.error('Error al eliminar'); }
  };

  // ===== DOCUMENTS =====
  const uploadDocument = async () => {
    if (!docForm.name.trim()) { toast.error('El nombre es obligatorio'); return; }
    if (!docFile) { toast.error('Seleccione un archivo'); return; }
    try {
      const formData = new FormData();
      formData.append('name', docForm.name);
      formData.append('description', docForm.description);
      formData.append('category', docForm.category);
      formData.append('file', docFile);
      await api.post('/client-documents/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      toast.success('Documento subido');
      setDocDialogOpen(false);
      setDocFile(null);
      setDocForm({ name: '', description: '', category: 'General' });
      fetchDocuments();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al subir'); }
  };
  const deleteDocument = async (doc) => {
    if (!confirm(`¿Eliminar "${doc.name}"?`)) return;
    try {
      await api.delete(`/client-documents/${doc.document_id}`);
      toast.success('Documento eliminado');
      fetchDocuments();
    } catch { toast.error('Error al eliminar'); }
  };

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 p-6 overflow-auto">
        <div className="flex items-center gap-3 mb-6">
          <Button variant="ghost" size="sm" onClick={() => navigate('/clients')}>
            <ArrowLeft className="w-4 h-4 mr-1" /> Clientes
          </Button>
          <div>
            <h1 className="text-xl font-bold text-slate-800">Comunicaciones a Clientes</h1>
            <p className="text-sm text-slate-500">Gestión de plantillas y documentos para comunicaciones comerciales</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6">
          <Button variant={activeTab === 'plantillas' ? 'default' : 'outline'} size="sm"
            onClick={() => setActiveTab('plantillas')} data-testid="tab-plantillas">
            <FileText className="w-4 h-4 mr-1" /> Plantillas de Correo
          </Button>
          <Button variant={activeTab === 'documentos' ? 'default' : 'outline'} size="sm"
            onClick={() => setActiveTab('documentos')} data-testid="tab-documentos">
            <FileUp className="w-4 h-4 mr-1" /> Documentos de Comunicación
          </Button>
        </div>

        {/* PLANTILLAS */}
        {activeTab === 'plantillas' && (
          <div>
            <div className="flex justify-between items-center mb-4">
              <p className="text-xs text-slate-500">Variables disponibles: <code className="text-blue-600">{VARIABLES_HINT}</code></p>
              <Button size="sm" onClick={openNewTemplate} data-testid="new-template-btn">
                <Plus className="w-4 h-4 mr-1" /> Nueva Plantilla
              </Button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {templates.map(tpl => (
                <div key={tpl.template_id} className="bg-white rounded-lg border border-slate-200 p-4 hover:border-blue-300 transition" data-testid={`tpl-${tpl.template_id}`}>
                  <div className="flex justify-between items-start mb-2">
                    <h4 className="font-semibold text-sm text-slate-800">{tpl.name}</h4>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="sm" onClick={() => openEditTemplate(tpl)} className="h-7 w-7 p-0">
                        <Pencil className="w-3.5 h-3.5 text-slate-400" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => deleteTemplate(tpl)} className="h-7 w-7 p-0">
                        <Trash2 className="w-3.5 h-3.5 text-slate-400 hover:text-rose-500" />
                      </Button>
                    </div>
                  </div>
                  <p className="text-xs text-blue-600 font-medium mb-1">Asunto: {tpl.subject || '—'}</p>
                  <p className="text-xs text-slate-500 line-clamp-3">{tpl.body_html || tpl.body || '—'}</p>
                </div>
              ))}
              {templates.length === 0 && (
                <div className="col-span-full text-center py-12 text-slate-400">
                  <FileText className="w-10 h-10 mx-auto mb-2 opacity-40" />
                  <p>No hay plantillas de clientes. Cree la primera.</p>
                </div>
              )}
            </div>

            {/* Template Dialog */}
            <Dialog open={tplDialogOpen} onOpenChange={setTplDialogOpen}>
              <DialogContent className="max-w-lg" data-testid="template-dialog">
                <DialogHeader>
                  <DialogTitle>{editingTpl ? 'Editar' : 'Nueva'} Plantilla</DialogTitle>
                  <DialogDescription>Las plantillas de Clientes son independientes de las de Proyectos.</DialogDescription>
                </DialogHeader>
                <div className="space-y-3">
                  <div><Label className="text-xs">Nombre</Label><Input value={tplForm.name} onChange={e => setTplForm({...tplForm, name: e.target.value})} placeholder="Ej: Bienvenida Nuevo Cliente" /></div>
                  <div><Label className="text-xs">Asunto</Label><Input value={tplForm.subject} onChange={e => setTplForm({...tplForm, subject: e.target.value})} placeholder="Ej: Bienvenido {{nombre}}" /></div>
                  <div>
                    <Label className="text-xs">Cuerpo del Mensaje</Label>
                    <Textarea value={tplForm.body_html} onChange={e => setTplForm({...tplForm, body_html: e.target.value})} rows={8} placeholder="Estimado {{contacto}},&#10;&#10;Es un placer..." />
                    <p className="text-[10px] text-slate-400 mt-1">Variables: {VARIABLES_HINT}</p>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setTplDialogOpen(false)}>Cancelar</Button>
                  <Button onClick={saveTemplate}><Save className="w-4 h-4 mr-1" /> Guardar</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        )}

        {/* DOCUMENTOS */}
        {activeTab === 'documentos' && (
          <div>
            <div className="flex justify-end mb-4">
              <Button size="sm" onClick={() => { setDocForm({ name: '', description: '', category: 'General' }); setDocFile(null); setDocDialogOpen(true); }} data-testid="upload-doc-btn">
                <Upload className="w-4 h-4 mr-1" /> Subir Documento
              </Button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {documents.map(doc => (
                <div key={doc.document_id} className="bg-white rounded-lg border border-slate-200 p-4 flex items-center gap-3" data-testid={`doc-${doc.document_id}`}>
                  <div className="p-2.5 bg-slate-100 rounded-lg"><FileText className="w-5 h-5 text-blue-600" /></div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-slate-800 truncate">{doc.name}</p>
                    <p className="text-[10px] text-slate-400">{doc.filename} | {doc.category}</p>
                  </div>
                  {isAdmin && (
                    <Button variant="ghost" size="sm" onClick={() => deleteDocument(doc)} className="text-slate-300 hover:text-rose-500">
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  )}
                </div>
              ))}
              {documents.length === 0 && (
                <div className="col-span-full text-center py-12 text-slate-400">
                  <FileUp className="w-10 h-10 mx-auto mb-2 opacity-40" />
                  <p>No hay documentos cargados. Suba flyers, presentaciones o PDFs.</p>
                </div>
              )}
            </div>

            {/* Upload Dialog */}
            <Dialog open={docDialogOpen} onOpenChange={setDocDialogOpen}>
              <DialogContent className="max-w-md" data-testid="upload-doc-dialog">
                <DialogHeader>
                  <DialogTitle>Subir Documento de Comunicación</DialogTitle>
                  <DialogDescription>Este documento estará disponible como adjunto al enviar comunicaciones a clientes.</DialogDescription>
                </DialogHeader>
                <div className="space-y-3">
                  <div><Label className="text-xs">Nombre</Label><Input value={docForm.name} onChange={e => setDocForm({...docForm, name: e.target.value})} placeholder="Ej: Flyer VPOS 2026" /></div>
                  <div><Label className="text-xs">Descripción (opcional)</Label><Input value={docForm.description} onChange={e => setDocForm({...docForm, description: e.target.value})} /></div>
                  <div>
                    <Label className="text-xs">Archivo</Label>
                    <div className="mt-1">
                      <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()}>
                        <Upload className="w-3.5 h-3.5 mr-1" /> {docFile ? docFile.name : 'Seleccionar archivo'}
                      </Button>
                      <input type="file" ref={fileRef} onChange={e => setDocFile(e.target.files?.[0] || null)} className="hidden" />
                    </div>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setDocDialogOpen(false)}>Cancelar</Button>
                  <Button onClick={uploadDocument}><Upload className="w-4 h-4 mr-1" /> Subir</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        )}
      </main>
    </div>
  );
};

export default ClientTemplatesConfig;
