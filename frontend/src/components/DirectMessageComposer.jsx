import { useEffect, useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { Button } from './ui/button';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Checkbox } from './ui/checkbox';
import { Badge } from './ui/badge';
import { Send, Save, Trash2, FileText, MessageSquare } from 'lucide-react';
import { toast } from 'sonner';
import api from '../utils/api';

const LEVELS = [
  { key: 'low', label: 'Baja', hint: 'Toast sutil', cls: 'border-slate-300', dot: 'bg-slate-400' },
  { key: 'medium', label: 'Media (Azul)', hint: 'Modal azul institucional', cls: 'border-blue-400', dot: 'bg-blue-600' },
  { key: 'high', label: 'Alta (Urgente)', hint: 'Modal rojo intrusivo', cls: 'border-red-400', dot: 'bg-red-600' },
];

export default function DirectMessageComposer({ open, onOpenChange, connectedUsers = [] }) {
  const [recipients, setRecipients] = useState([]);
  const [allOnline, setAllOnline] = useState(false);
  const [level, setLevel] = useState('medium');
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [showTemplates, setShowTemplates] = useState(false);

  const loadTemplates = async () => {
    try { const { data } = await api.get('/admin/message-templates'); setTemplates(data?.items || []); }
    catch { /* noop */ }
  };

  useEffect(() => {
    if (open) {
      setRecipients([]); setAllOnline(false); setLevel('medium'); setBody(''); setShowTemplates(false);
      loadTemplates();
    }
  }, [open]);

  const toggleRecipient = (uid) => {
    setRecipients((prev) => prev.includes(uid) ? prev.filter((x) => x !== uid) : [...prev, uid]);
  };

  const send = async () => {
    if (!body.trim()) { toast.error('Escriba el mensaje'); return; }
    if (!allOnline && recipients.length === 0) { toast.error('Seleccione destinatarios o marque "Todos"'); return; }
    setSending(true);
    try {
      const { data } = await api.post('/admin/direct-message', {
        body: body.trim(), level, all_online: allOnline,
        recipient_ids: allOnline ? [] : recipients,
      });
      toast.success(data?.message || 'Mensaje enviado');
      onOpenChange(false);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'No se pudo enviar');
    } finally { setSending(false); }
  };

  const saveTemplate = async () => {
    if (!body.trim()) { toast.error('Escriba un texto para guardar como plantilla'); return; }
    try {
      await api.post('/admin/message-templates', { text: body.trim() });
      toast.success('Plantilla guardada');
      loadTemplates();
    } catch (err) { toast.error(err?.response?.data?.detail || 'No se pudo guardar'); }
  };

  const deleteTemplate = async (id) => {
    try { await api.delete(`/admin/message-templates/${id}`); loadTemplates(); }
    catch { toast.error('No se pudo eliminar'); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto" data-testid="direct-message-composer">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-indigo-700"><MessageSquare size={20} /> Enviar Mensaje Directo</DialogTitle>
          <DialogDescription>Notificación instantánea a usuarios conectados.</DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-1">
          {/* Destinatarios */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <Label className="text-xs font-semibold">Destinatarios <span className="text-indigo-600">({allOnline ? connectedUsers.length : recipients.length})</span></Label>
              <label className="flex items-center gap-2 text-xs font-medium cursor-pointer" data-testid="dm-all-online">
                <Checkbox checked={allOnline} onCheckedChange={(v) => setAllOnline(!!v)} />
                Todos los conectados
              </label>
            </div>
            <div className={`border rounded-lg p-2 max-h-40 overflow-y-auto bg-slate-50 ${allOnline ? 'opacity-50 pointer-events-none' : ''}`} data-testid="dm-recipients-list">
              {connectedUsers.length === 0 ? (
                <p className="text-xs text-slate-400 text-center py-2">No hay usuarios conectados</p>
              ) : connectedUsers.map((u) => (
                <label key={u.user_id} className="flex items-center gap-2 text-sm p-1.5 rounded hover:bg-white cursor-pointer" data-testid={`dm-recipient-${u.user_id}`}>
                  <Checkbox checked={allOnline || recipients.includes(u.user_id)} onCheckedChange={() => toggleRecipient(u.user_id)} />
                  <span className="flex-1 min-w-0 truncate font-medium text-slate-700">{u.full_name}</span>
                  <span className="text-[10px] text-slate-400 truncate">{u.email}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Nivel de importancia */}
          <div>
            <Label className="text-xs font-semibold">Nivel de importancia</Label>
            <div className="grid grid-cols-3 gap-2 mt-1.5">
              {LEVELS.map((l) => (
                <button
                  key={l.key} type="button" onClick={() => setLevel(l.key)}
                  className={`border-2 rounded-lg p-2 text-left transition-all ${level === l.key ? `${l.cls} bg-white ring-2 ring-offset-1 ring-indigo-200` : 'border-slate-200 bg-slate-50 hover:bg-white'}`}
                  data-testid={`dm-level-${l.key}`}
                >
                  <span className="flex items-center gap-1.5 text-xs font-bold text-slate-700"><span className={`w-2.5 h-2.5 rounded-full ${l.dot}`} />{l.label}</span>
                  <span className="block text-[10px] text-slate-400 mt-0.5">{l.hint}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Plantillas */}
          <div>
            <button type="button" onClick={() => setShowTemplates((s) => !s)} className="text-xs font-semibold text-indigo-600 flex items-center gap-1" data-testid="dm-templates-toggle">
              <FileText size={13} /> Mensajes Preelaborados ({templates.length}) {showTemplates ? '▲' : '▼'}
            </button>
            {showTemplates && (
              <div className="mt-1.5 border rounded-lg p-2 max-h-32 overflow-y-auto bg-slate-50 space-y-1" data-testid="dm-templates-list">
                {templates.length === 0 ? (
                  <p className="text-xs text-slate-400 text-center py-1">Sin plantillas guardadas</p>
                ) : templates.map((t) => (
                  <div key={t.template_id} className="flex items-center gap-2 bg-white rounded px-2 py-1.5 text-xs" data-testid={`dm-template-${t.template_id}`}>
                    <button type="button" onClick={() => setBody(t.text)} className="flex-1 min-w-0 truncate text-left text-slate-700 hover:text-indigo-600" title={t.text}>
                      {t.title || t.text}
                    </button>
                    <button type="button" onClick={() => deleteTemplate(t.template_id)} className="text-slate-300 hover:text-red-500 shrink-0" data-testid={`dm-template-del-${t.template_id}`}>
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Cuerpo */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <Label className="text-xs font-semibold">Mensaje</Label>
              <Button type="button" variant="ghost" size="sm" onClick={saveTemplate} className="text-xs text-indigo-600 h-7" data-testid="dm-save-template">
                <Save size={13} className="mr-1" /> Guardar como Plantilla
              </Button>
            </div>
            <Textarea value={body} onChange={(e) => setBody(e.target.value)} rows={4} placeholder="Escriba el mensaje..." className="text-sm" data-testid="dm-body" />
          </div>

          {level !== 'low' && (
            <div className={`rounded-lg p-2.5 text-xs text-white ${level === 'high' ? 'bg-red-600' : 'bg-blue-700'}`}>
              <Badge className="bg-white/20 text-white mb-1">Vista previa</Badge>
              <p className="whitespace-pre-wrap">{body || 'El receptor verá este mensaje en una ventana grande bloqueante.'}</p>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 pt-2 border-t">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button onClick={send} disabled={sending} className="bg-indigo-600 hover:bg-indigo-700 text-white" data-testid="dm-send-btn">
            {sending ? 'Enviando...' : <><Send size={14} className="mr-1" /> Enviar</>}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
