import { useState, useEffect, useMemo } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { Button } from './ui/button';
import { Label } from './ui/label';
import { Checkbox } from './ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Send, Mail, Search, Paperclip, Users, FileText, Eye, Download } from 'lucide-react';
import { toast } from 'sonner';
import api from '../utils/api';
import { DocumentViewerModal, downloadEntityDocument } from './DocumentViewerModal';

const TYPE_OPTIONS = [
  { code: 'ALL', label: 'Todos los tipos' },
  { code: 'CR', label: 'CR — Caja Registradora' },
  { code: 'LP', label: 'LP — Link de Pago' },
  { code: 'PG', label: 'PG — Payment Gateway' },
  { code: 'MP', label: 'MP — Android (Mobile POS)' },
  { code: 'TK', label: 'TK — Tokenizador' },
];

export const MassCommunicationDialog = ({ open, onOpenChange }) => {
  const [filterType, setFilterType] = useState('ALL');
  const [search, setSearch] = useState('');
  const [recipients, setRecipients] = useState([]);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [templates, setTemplates] = useState([]);
  const [templateId, setTemplateId] = useState('');
  const [docs, setDocs] = useState([]);
  const [selectedDocs, setSelectedDocs] = useState(new Set());
  const [localFiles, setLocalFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [viewerDoc, setViewerDoc] = useState(null);
  const [viewerOpen, setViewerOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    setSelectedIds(new Set()); setTemplateId(''); setSelectedDocs(new Set()); setLocalFiles([]); setSearch(''); setFilterType('ALL');
    api.get('/email-templates?context=INTEGRADORES').then(r => setTemplates(r.data || [])).catch(() => setTemplates([]));
    api.get('/entity-documents?context=INTEGRADORES').then(r => setDocs(r.data || [])).catch(() => setDocs([]));
  }, [open]);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    const q = filterType && filterType !== 'ALL' ? `?integration_type=${filterType}` : '';
    api.get(`/integrators/mass/recipients${q}`)
      .then(r => { setRecipients(r.data?.recipients || []); setSelectedIds(new Set()); })
      .catch(() => setRecipients([]))
      .finally(() => setLoading(false));
  }, [open, filterType]);

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return recipients;
    return recipients.filter(r =>
      r.name.toLowerCase().includes(q) || (r.contact || '').toLowerCase().includes(q) || (r.email || '').toLowerCase().includes(q));
  }, [recipients, search]);

  const selectableVisible = visible.filter(r => r.has_email);
  const allSelected = selectableVisible.length > 0 && selectableVisible.every(r => selectedIds.has(r.integrator_id));
  const withEmailCount = recipients.filter(r => r.has_email).length;

  const toggleAll = () => {
    const next = new Set(selectedIds);
    if (allSelected) selectableVisible.forEach(r => next.delete(r.integrator_id));
    else selectableVisible.forEach(r => next.add(r.integrator_id));
    setSelectedIds(next);
  };
  const toggleOne = (id) => {
    const next = new Set(selectedIds);
    next.has(id) ? next.delete(id) : next.add(id);
    setSelectedIds(next);
  };
  const toggleDoc = (id) => {
    const next = new Set(selectedDocs);
    next.has(id) ? next.delete(id) : next.add(id);
    setSelectedDocs(next);
  };

  const handleSend = async () => {
    if (!templateId) { toast.error('Seleccione una plantilla institucional'); return; }
    if (selectedIds.size === 0) { toast.error('Seleccione al menos un integrador con correo'); return; }
    setSending(true);
    try {
      const fd = new FormData();
      fd.append('template_id', templateId);
      fd.append('integrator_ids', JSON.stringify(Array.from(selectedIds)));
      fd.append('internal_doc_ids', JSON.stringify(Array.from(selectedDocs)));
      localFiles.forEach(f => fd.append('files', f));
      const res = await api.post('/integrators/mass/communication', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      toast.success(res.data?.message || 'Comunicación masiva enviada');
      onOpenChange(false);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al enviar la comunicación masiva');
    } finally { setSending(false); }
  };

  return (
    <>
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl max-h-[92vh] overflow-hidden flex flex-col" data-testid="mass-comm-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-blue-700">
            <Mail size={20} className="text-blue-500" />Comunicación Masiva a Integradores
          </DialogTitle>
          <DialogDescription className="text-xs text-slate-500">
            Seleccione destinatarios, plantilla y adjuntos. El envío se realiza en copia oculta (BCC).
          </DialogDescription>
        </DialogHeader>
        <div className="flex-1 overflow-y-auto grid grid-cols-1 lg:grid-cols-5 gap-5 pr-1">
          <div className="lg:col-span-3 flex flex-col min-h-0">
            <div className="flex items-center gap-2 mb-2">
              <Select value={filterType} onValueChange={setFilterType}>
                <SelectTrigger className="w-56" data-testid="mass-filter-type"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {TYPE_OPTIONS.map(o => <SelectItem key={o.code} value={o.code} data-testid={`mass-type-${o.code}`}>{o.label}</SelectItem>)}
                </SelectContent>
              </Select>
              <div className="relative flex-1">
                <Search size={14} className="absolute left-2.5 top-2.5 text-slate-400" />
                <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Buscar nombre, contacto o correo…"
                  className="w-full pl-8 pr-3 py-2 text-sm border border-slate-200 rounded-lg" data-testid="mass-search" />
              </div>
            </div>
            <div className="text-xs text-slate-500 mb-1 flex items-center gap-1.5">
              <Users size={12} /> {selectedIds.size} seleccionado(s) · {withEmailCount} con correo de {recipients.length}
            </div>
            <div className="border border-slate-200 rounded-lg overflow-auto" style={{ maxHeight: '46vh' }}>
              <table className="w-full text-sm">
                <thead className="bg-slate-50 sticky top-0 z-10">
                  <tr className="text-left text-xs text-slate-500">
                    <th className="p-2 w-10"><Checkbox checked={allSelected} onCheckedChange={toggleAll} data-testid="mass-select-all" /></th>
                    <th className="p-2">Integrador</th><th className="p-2">Contacto</th><th className="p-2">Correo</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr><td colSpan={4} className="p-6 text-center text-slate-400">Cargando…</td></tr>
                  ) : visible.length === 0 ? (
                    <tr><td colSpan={4} className="p-6 text-center text-slate-400">Sin integradores para el filtro</td></tr>
                  ) : visible.map(r => (
                    <tr key={r.integrator_id} className={`border-t border-slate-100 ${!r.has_email ? 'opacity-50' : 'hover:bg-blue-50/40'}`} data-testid={`mass-row-${r.integrator_id}`}>
                      <td className="p-2"><Checkbox disabled={!r.has_email} checked={selectedIds.has(r.integrator_id)} onCheckedChange={() => toggleOne(r.integrator_id)} data-testid={`mass-check-${r.integrator_id}`} /></td>
                      <td className="p-2 font-medium text-slate-800">{r.name}</td>
                      <td className="p-2 text-slate-600">{r.contact || '—'}</td>
                      <td className="p-2 text-slate-500 font-mono text-xs">{r.email || <span className="italic text-rose-400">sin correo</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="lg:col-span-2 space-y-4">
            <div>
              <Label className="text-sm font-medium">Plantilla institucional</Label>
              <Select value={templateId} onValueChange={setTemplateId}>
                <SelectTrigger className="mt-1" data-testid="mass-template-select"><SelectValue placeholder="Seleccione una plantilla…" /></SelectTrigger>
                <SelectContent>
                  {templates.map(t => <SelectItem key={t.template_id} value={t.template_id} data-testid={`mass-tpl-${t.template_id}`}>{t.name}</SelectItem>)}
                </SelectContent>
              </Select>
              {templates.length === 0 && <p className="text-xs text-slate-400 mt-1">No hay plantillas de Integradores en la biblioteca.</p>}
            </div>
            <div>
              <Label className="text-sm font-medium flex items-center gap-1"><FileText size={14} />Documentos del repositorio</Label>
              <div className="mt-1 border border-slate-200 rounded-lg p-2 space-y-1 max-h-32 overflow-auto">
                {docs.length === 0 ? <p className="text-xs text-slate-400">Repositorio vacío</p>
                  : docs.map(d => (
                    <div key={d.document_id} className="flex items-center gap-1 text-xs hover:bg-slate-50 p-1 rounded" data-testid={`mass-doc-${d.document_id}`}>
                      <label className="flex items-center gap-2 flex-1 min-w-0 cursor-pointer">
                        <Checkbox checked={selectedDocs.has(d.document_id)} onCheckedChange={() => toggleDoc(d.document_id)} />
                        <span className="truncate">{d.filename}</span>
                      </label>
                      <button type="button" onClick={(e) => { e.stopPropagation(); setViewerDoc(d); setViewerOpen(true); }} className="p-1 text-slate-400 hover:text-blue-600 shrink-0" title="Visualizar" data-testid={`mass-doc-view-${d.document_id}`}><Eye size={14} /></button>
                      <button type="button" onClick={(e) => { e.stopPropagation(); downloadEntityDocument(d); }} className="p-1 text-slate-400 hover:text-emerald-600 shrink-0" title="Descargar" data-testid={`mass-doc-download-${d.document_id}`}><Download size={14} /></button>
                    </div>
                  ))}
              </div>
            </div>
            <div>
              <Label className="text-sm font-medium flex items-center gap-1"><Paperclip size={14} />Anexo local adicional</Label>
              <input type="file" multiple onChange={e => setLocalFiles(Array.from(e.target.files || []))}
                className="mt-1 block w-full text-xs text-slate-600 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-blue-600 file:text-white file:cursor-pointer hover:file:bg-blue-700" data-testid="mass-local-files" />
              {localFiles.length > 0 && <p className="text-xs text-slate-500 mt-1">{localFiles.length} archivo(s) local(es)</p>}
            </div>
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-2.5 text-xs text-amber-800">
              🔒 Privacidad: todos los correos se envían en <strong>copia oculta (BCC)</strong>. Ningún destinatario verá a los demás.
            </div>
          </div>
        </div>
        <div className="flex items-center justify-between gap-3 pt-3 border-t mt-1">
          <span className="text-xs text-slate-500">{selectedIds.size} destinatario(s) · {selectedDocs.size + localFiles.length} adjunto(s)</span>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)} data-testid="mass-cancel">Cancelar</Button>
            <Button onClick={handleSend} disabled={sending || selectedIds.size === 0 || !templateId}
              className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="mass-send-btn">
              <Send size={14} className="mr-1.5" />{sending ? 'Enviando…' : `Enviar a ${selectedIds.size}`}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
    <DocumentViewerModal open={viewerOpen} onOpenChange={setViewerOpen} doc={viewerDoc} />
    </>
  );
};

export default MassCommunicationDialog;
