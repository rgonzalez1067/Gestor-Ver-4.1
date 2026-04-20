import { useState, useEffect, useRef, useMemo } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Label } from './ui/label';
import { Send, Eye, Edit3, Plus, Paperclip, FileText, X, Upload, UserCheck } from 'lucide-react';
import { toast } from 'sonner';
import api from '../utils/api';

/**
 * Componente genérico de envío de comunicaciones.
 * Props:
 *   open, onClose, onSent
 *   context: 'CLIENTES' | 'INTEGRADORES' | 'NUEVOS_PRODUCTOS'
 *   title: título visible del modal
 *   subtitle: subtítulo (ej: nombre del integrador)
 *   sendEndpoint: `/integrators/{id}/send-email` etc.
 *   previewEndpoint: `/integrators/{id}/preview-email` etc.
 *   variables: [{ key: '{{xxx}}', desc: '...' }]
 *   initialRecipients: string[]
 */
export const EntityEmailDialog = ({
  open, onClose, onSent,
  context, title, subtitle,
  sendEndpoint, previewEndpoint,
  variables = [],
  initialRecipients = [],
}) => {
  const [templates, setTemplates] = useState([]);
  const [internalDocs, setInternalDocs] = useState([]);
  const [selectedInternalDocs, setSelectedInternalDocs] = useState([]);
  const [recipients, setRecipients] = useState(['']);
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [previewMode, setPreviewMode] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  const [externalFiles, setExternalFiles] = useState([]);
  const fileInputRef = useRef(null);

  // Autocomplete
  const [internalUsers, setInternalUsers] = useState([]);
  const [activeRecipientIdx, setActiveRecipientIdx] = useState(-1);
  const [autocompleteQuery, setAutocompleteQuery] = useState('');

  useEffect(() => {
    if (!open) return;
    setRecipients(initialRecipients.length ? initialRecipients : ['']);
    setSubject('');
    setMessage('');
    setExternalFiles([]);
    setSelectedInternalDocs([]);
    setPreviewMode(false);
    setPreviewData(null);
    setActiveRecipientIdx(-1);
    setAutocompleteQuery('');

    api.get(`/email-templates?context=${context}`).then(r => setTemplates(r.data || [])).catch(() => setTemplates([]));
    api.get(`/entity-documents?context=${context}`).then(r => setInternalDocs(r.data || [])).catch(() => setInternalDocs([]));
    api.get('/users/internal-emails').then(r => setInternalUsers(r.data || [])).catch(() => setInternalUsers([]));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, context]);

  const filteredInternalUsers = useMemo(() => {
    const q = (autocompleteQuery || '').trim().toLowerCase();
    if (!q) return internalUsers.slice(0, 8);
    return internalUsers.filter(u =>
      u.email.toLowerCase().includes(q) || (u.full_name || '').toLowerCase().includes(q)
    ).slice(0, 8);
  }, [autocompleteQuery, internalUsers]);

  const addRecipient = () => setRecipients(prev => [...prev, '']);
  const removeRecipient = (idx) => setRecipients(prev => prev.filter((_, i) => i !== idx));
  const updateRecipient = (idx, val) => {
    setRecipients(prev => { const r = [...prev]; r[idx] = val; return r; });
    setActiveRecipientIdx(idx);
    setAutocompleteQuery(val);
  };
  const pickAutocomplete = (idx, email) => {
    setRecipients(prev => { const r = [...prev]; r[idx] = email; return r; });
    setActiveRecipientIdx(-1);
    setAutocompleteQuery('');
  };

  const handleTemplateSelect = (tpl) => {
    setSubject(tpl.subject || '');
    setMessage(tpl.body_html || tpl.body || '');
    setPreviewMode(false);
  };

  const insertVariable = (varKey) => setMessage(prev => prev + varKey);

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
    try {
      const res = await api.post(previewEndpoint, { subject, message });
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
      const res = await api.post(sendEndpoint, formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      toast.success(res.data.message || 'Comunicación enviada');
      onSent && onSent(res.data);
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al enviar');
    } finally { setSending(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-hidden p-0" data-testid="entity-email-dialog">
        <div className="flex h-[80vh]">
          {/* Sidebar */}
          <div className="w-72 bg-slate-50 border-r border-slate-200 p-4 overflow-y-auto flex-shrink-0">
            <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-3">Plantillas</h4>
            <div className="space-y-1.5 mb-6">
              {templates.length === 0 ? (
                <p className="text-xs text-slate-400">Sin plantillas registradas</p>
              ) : templates.map(tpl => (
                <button
                  key={tpl.template_id}
                  onClick={() => handleTemplateSelect(tpl)}
                  className="w-full text-left p-2.5 bg-white border border-slate-200 rounded-lg text-xs font-medium hover:border-blue-400 hover:text-blue-600 transition"
                  data-testid={`entity-tpl-${tpl.template_id}`}
                >
                  {tpl.name}
                </button>
              ))}
            </div>

            <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Variables</h4>
            <div className="flex flex-wrap gap-1 mb-6">
              {variables.map(v => (
                <button key={v.key} onClick={() => insertVariable(v.key)}
                  className="text-[10px] bg-white border border-blue-200 text-blue-600 px-2 py-1 rounded font-mono hover:bg-blue-50 transition"
                  title={v.desc}>
                  {v.key}
                </button>
              ))}
            </div>

            <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Documentos de Comunicación</h4>
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

          {/* Main — composer */}
          <div className="flex-1 flex flex-col p-5 overflow-y-auto">
            <DialogHeader className="mb-4">
              <DialogTitle className="flex items-center gap-2 text-base">
                <Send className="w-4 h-4 text-blue-500" />{title || 'Enviar Comunicación'}
              </DialogTitle>
              {subtitle && <DialogDescription className="text-xs">{subtitle}</DialogDescription>}
            </DialogHeader>

            <div className="space-y-3 flex-1">
              {/* Recipients con autocomplete */}
              <div>
                <Label className="text-xs">Destinatarios</Label>
                {recipients.map((r, idx) => (
                  <div key={idx} className="relative">
                    <div className="flex gap-2 mt-1">
                      <Input
                        value={r}
                        onChange={(e) => updateRecipient(idx, e.target.value)}
                        onFocus={() => { setActiveRecipientIdx(idx); setAutocompleteQuery(r); }}
                        onBlur={() => setTimeout(() => setActiveRecipientIdx(-1), 150)}
                        placeholder="correo@ejemplo.com  —  o escriba para buscar usuario interno"
                        className="text-sm"
                        data-testid={`entity-recipient-${idx}`}
                      />
                      {idx > 0 && (
                        <Button variant="ghost" size="sm" onClick={() => removeRecipient(idx)}>
                          <X className="w-3.5 h-3.5 text-slate-400" />
                        </Button>
                      )}
                    </div>
                    {activeRecipientIdx === idx && filteredInternalUsers.length > 0 && (
                      <div className="absolute left-0 right-0 top-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg z-30 max-h-52 overflow-y-auto" data-testid={`entity-autocomplete-${idx}`}>
                        <div className="px-3 py-1.5 text-[10px] uppercase text-slate-400 font-bold flex items-center gap-1 border-b border-slate-100">
                          <UserCheck size={10} /> Usuarios internos MegaNexus
                        </div>
                        {filteredInternalUsers.map(u => (
                          <button
                            key={u.email}
                            type="button"
                            onMouseDown={(e) => { e.preventDefault(); pickAutocomplete(idx, u.email); }}
                            className="w-full text-left px-3 py-2 hover:bg-blue-50 flex items-center gap-2 text-xs border-b border-slate-50"
                            data-testid={`entity-autocomplete-option-${u.email}`}
                          >
                            <div className="flex-1">
                              <div className="font-medium text-slate-800">{u.full_name}</div>
                              <div className="text-[10px] text-slate-500 font-mono">{u.email}</div>
                            </div>
                            {u.cargo && <span className="text-[9px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">{u.cargo}</span>}
                          </button>
                        ))}
                      </div>
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
                <Input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Asunto del correo..." className="text-sm font-semibold" data-testid="entity-email-subject" />
              </div>

              {/* Message */}
              <div className="flex-1">
                <div className="flex justify-between items-center mb-1">
                  <Label className="text-xs">Cuerpo del Mensaje</Label>
                  <Button variant="ghost" size="sm" onClick={previewMode ? () => setPreviewMode(false) : handlePreview} className="text-xs text-blue-600">
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
                    data-testid="entity-email-message"
                  />
                )}
              </div>

              {/* Attachments */}
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
              <Button onClick={handleSend} disabled={sending} className="bg-slate-900 hover:bg-slate-800" data-testid="entity-send-email-btn">
                {sending ? 'Enviando...' : <><Send className="w-4 h-4 mr-1" /> Enviar</>}
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default EntityEmailDialog;
