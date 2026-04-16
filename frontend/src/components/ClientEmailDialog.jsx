import { useState, useEffect, useRef } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Label } from './ui/label';
import { Send, Eye, Edit3, Plus, Trash2, Paperclip, FileText, X, Search, Upload } from 'lucide-react';
import { toast } from 'sonner';
import api from '../utils/api';

const VARIABLES = [
  { key: '{{nombre}}', desc: 'Razón Social' },
  { key: '{{rif}}', desc: 'RIF' },
  { key: '{{email}}', desc: 'Email contacto' },
  { key: '{{contacto}}', desc: 'Nombre contacto' },
  { key: '{{direccion}}', desc: 'Dirección' },
  { key: '{{telefono}}', desc: 'Teléfono' },
  { key: '{{nombre_comercial}}', desc: 'Nombre comercial' },
];

export const ClientEmailDialog = ({ open, onClose, client, onSent }) => {
  const [templates, setTemplates] = useState([]);
  const [recipients, setRecipients] = useState(['']);
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [previewMode, setPreviewMode] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  // Attachments
  const [externalFiles, setExternalFiles] = useState([]);
  const [internalDocs, setInternalDocs] = useState([]);
  const [selectedInternalDocs, setSelectedInternalDocs] = useState([]);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (open && client) {
      // Pre-fill first recipient from client contact
      const contacts = client.contacts || [];
      const primaryEmail = contacts[0]?.email || client.email || '';
      setRecipients([primaryEmail]);
      setSubject('');
      setMessage('');
      setExternalFiles([]);
      setSelectedInternalDocs([]);
      setPreviewMode(false);
      setPreviewData(null);
      // Load templates for CLIENTES context
      api.get('/email-templates?context=CLIENTES').then(r => setTemplates(r.data || [])).catch(() => setTemplates([]));
      // Load internal documents
      api.get('/client-documents').then(r => setInternalDocs(r.data || [])).catch(() => setInternalDocs([]));
    }
  }, [open, client]);

  const addRecipient = () => setRecipients(prev => [...prev, '']);
  const removeRecipient = (idx) => setRecipients(prev => prev.filter((_, i) => i !== idx));
  const updateRecipient = (idx, val) => setRecipients(prev => { const r = [...prev]; r[idx] = val; return r; });

  // Resolución inmediata de variables del cliente al seleccionar plantilla
  const resolveClientVars = (text) => {
    if (!text || !client) return text;
    const contacts = client.contacts || [];
    const contactName = contacts[0]?.full_name || contacts[0]?.name || contacts[0]?.first_name || '';
    const contactEmail = contacts[0]?.email || client.email || '';
    const contactPhone = contacts[0]?.phone || '';
    const vars = {
      nombre: client.legal_name || client.fantasy_name || '',
      razon_social: client.legal_name || '',
      rif: client.rif || '',
      email: contactEmail,
      contacto: contactName,
      direccion: client.address || '',
      telefono: contactPhone,
      nombre_comercial: client.fantasy_name || '',
    };
    let result = text;
    Object.entries(vars).forEach(([key, val]) => {
      result = result.replace(new RegExp(`\\{\\{${key}\\}\\}`, 'g'), val);
      result = result.replace(new RegExp(`\\{${key}\\}`, 'g'), val);
    });
    return result;
  };

  const handleTemplateSelect = (tpl) => {
    const rawSubject = tpl.subject || '';
    const rawBody = tpl.body_html || tpl.body || '';
    setSubject(resolveClientVars(rawSubject));
    setMessage(resolveClientVars(rawBody));
    setPreviewMode(false);
  };

  const insertVariable = (varKey) => {
    setMessage(prev => prev + varKey);
  };

  const handleFileSelect = (e) => {
    setExternalFiles(prev => [...prev, ...Array.from(e.target.files || [])]);
    e.target.value = '';
  };

  const toggleInternalDoc = (docId) => {
    setSelectedInternalDocs(prev =>
      prev.includes(docId) ? prev.filter(id => id !== docId) : [...prev, docId]
    );
  };

  const handlePreview = async () => {
    if (!client) return;
    try {
      const res = await api.post(`/clients/${client.client_id}/preview-email`, { subject, message });
      setPreviewData(res.data);
      setPreviewMode(true);
    } catch { toast.error('Error al generar vista previa'); }
  };

  const handleSend = async () => {
    const validRecipients = recipients.filter(r => r.trim() && r.includes('@'));
    if (!validRecipients.length) { toast.error('Agregue al menos un destinatario válido'); return; }
    if (!subject.trim()) { toast.error('El asunto es obligatorio'); return; }
    if (!message.trim()) { toast.error('El mensaje es obligatorio'); return; }

    setSending(true);
    try {
      const formData = new FormData();
      formData.append('recipients', JSON.stringify(validRecipients));
      formData.append('subject', subject);
      formData.append('message', message);
      formData.append('internal_doc_ids', JSON.stringify(selectedInternalDocs));
      externalFiles.forEach(f => formData.append('files', f));

      const res = await api.post(`/clients/${client.client_id}/send-email`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      toast.success(res.data.message);
      onSent && onSent();
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al enviar');
    } finally { setSending(false); }
  };

  if (!client) return null;

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-hidden p-0" data-testid="client-email-dialog">
        <div className="flex h-[80vh]">
          {/* Sidebar — Templates + Variables + Internal Docs */}
          <div className="w-72 bg-slate-50 border-r border-slate-200 p-4 overflow-y-auto flex-shrink-0">
            <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-3">Plantillas</h4>
            <div className="space-y-1.5 mb-6">
              {templates.length === 0 ? (
                <p className="text-xs text-slate-400">No hay plantillas para Clientes</p>
              ) : templates.map(tpl => (
                <button
                  key={tpl.template_id}
                  onClick={() => handleTemplateSelect(tpl)}
                  className="w-full text-left p-2.5 bg-white border border-slate-200 rounded-lg text-xs font-medium hover:border-blue-400 hover:text-blue-600 transition"
                >
                  {tpl.name}
                </button>
              ))}
            </div>

            <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Variables</h4>
            <div className="flex flex-wrap gap-1 mb-6">
              {VARIABLES.map(v => (
                <button key={v.key} onClick={() => insertVariable(v.key)}
                  className="text-[10px] bg-white border border-blue-200 text-blue-600 px-2 py-1 rounded font-mono hover:bg-blue-50 transition"
                  title={v.desc}>
                  {v.key}
                </button>
              ))}
            </div>

            <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Docs. de Comunicación</h4>
            <div className="space-y-1.5">
              {internalDocs.length === 0 ? (
                <p className="text-xs text-slate-400">No hay documentos cargados</p>
              ) : internalDocs.map(doc => (
                <button
                  key={doc.document_id}
                  onClick={() => toggleInternalDoc(doc.document_id)}
                  className={`w-full text-left p-2 rounded-lg text-xs flex items-center gap-2 border transition ${
                    selectedInternalDocs.includes(doc.document_id)
                      ? 'bg-blue-50 border-blue-400 text-blue-700'
                      : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}>
                  <Paperclip size={12} />
                  <span className="truncate">{doc.name}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Main — Email Composer */}
          <div className="flex-1 flex flex-col p-5 overflow-y-auto">
            <DialogHeader className="mb-4">
              <DialogTitle className="flex items-center gap-2 text-base">
                <Send className="w-4 h-4 text-blue-500" />
                Comunicación a Cliente
              </DialogTitle>
              <DialogDescription className="text-xs">
                {client.legal_name || client.fantasy_name} — {client.rif}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3 flex-1">
              {/* Recipients */}
              <div>
                <Label className="text-xs">Destinatarios</Label>
                {recipients.map((r, idx) => (
                  <div key={idx} className="flex gap-2 mt-1">
                    <Input
                      value={r}
                      onChange={(e) => updateRecipient(idx, e.target.value)}
                      placeholder="correo@ejemplo.com"
                      className="text-sm"
                      data-testid={`recipient-${idx}`}
                    />
                    {idx > 0 && (
                      <Button variant="ghost" size="sm" onClick={() => removeRecipient(idx)}>
                        <X className="w-3.5 h-3.5 text-slate-400" />
                      </Button>
                    )}
                  </div>
                ))}
                <Button variant="ghost" size="sm" onClick={addRecipient} className="mt-1 text-xs text-blue-600">
                  <Plus className="w-3 h-3 mr-1" /> Agregar destinatario
                </Button>
              </div>

              {/* Subject */}
              <div>
                <Label className="text-xs">Asunto</Label>
                <Input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Asunto del correo..." className="text-sm font-semibold" data-testid="email-subject" />
              </div>

              {/* Message Body */}
              <div className="flex-1">
                <div className="flex justify-between items-center mb-1">
                  <Label className="text-xs">Cuerpo del Mensaje</Label>
                  <Button variant="ghost" size="sm" onClick={previewMode ? () => setPreviewMode(false) : handlePreview}
                    className="text-xs text-blue-600">
                    {previewMode ? <><Edit3 className="w-3 h-3 mr-1" /> Editar</> : <><Eye className="w-3 h-3 mr-1" /> Vista Previa</>}
                  </Button>
                </div>
                {previewMode ? (
                  <div className="w-full p-4 bg-slate-50 border rounded-lg text-sm min-h-[180px] whitespace-pre-wrap leading-relaxed">
                    <p className="text-xs text-slate-400 mb-2 font-semibold">Asunto: {previewData?.subject || subject}</p>
                    <div dangerouslySetInnerHTML={{ __html: (previewData?.message || message).replace(/\n/g, '<br>') }} />
                  </div>
                ) : (
                  <Textarea
                    value={message} onChange={(e) => setMessage(e.target.value)}
                    placeholder="Escriba su mensaje. Use variables como {{nombre}} para personalizar..."
                    rows={8} className="text-sm resize-none"
                    data-testid="email-message"
                  />
                )}
              </div>

              {/* External Attachments */}
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <Label className="text-xs">Adjuntos externos</Label>
                  <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()} className="text-xs h-7">
                    <Upload className="w-3 h-3 mr-1" /> Subir archivo
                  </Button>
                  <input type="file" ref={fileInputRef} onChange={handleFileSelect} multiple className="hidden" />
                </div>
                {externalFiles.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {externalFiles.map((f, idx) => (
                      <span key={idx} className="flex items-center gap-1 bg-slate-100 text-xs px-2 py-1 rounded">
                        <FileText className="w-3 h-3" />{f.name}
                        <button onClick={() => setExternalFiles(prev => prev.filter((_, i) => i !== idx))}><X className="w-3 h-3 text-slate-400 hover:text-rose-500" /></button>
                      </span>
                    ))}
                  </div>
                )}
                {selectedInternalDocs.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-1">
                    {selectedInternalDocs.map(id => {
                      const doc = internalDocs.find(d => d.document_id === id);
                      return doc ? (
                        <span key={id} className="flex items-center gap-1 bg-blue-50 text-blue-700 text-xs px-2 py-1 rounded">
                          <Paperclip className="w-3 h-3" />{doc.name}
                        </span>
                      ) : null;
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* Footer */}
            <div className="pt-4 border-t flex justify-end gap-2">
              <Button variant="outline" onClick={onClose}>Cancelar</Button>
              <Button onClick={handleSend} disabled={sending} className="bg-slate-900 hover:bg-slate-800" data-testid="send-email-btn">
                {sending ? 'Enviando...' : <><Send className="w-4 h-4 mr-1" /> Enviar</>}
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ClientEmailDialog;
