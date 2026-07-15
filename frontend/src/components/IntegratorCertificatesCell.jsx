import { useState } from 'react';
import { Popover, PopoverTrigger, PopoverContent } from './ui/popover';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { Button } from './ui/button';
import { FileText, Plus, Download, UploadCloud } from 'lucide-react';
import { toast } from 'sonner';
import api from '../utils/api';

export const IntegratorCertificatesCell = ({ integratorId, count = 0, onChange }) => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);

  const loadList = async () => {
    setLoading(true);
    try {
      const r = await api.get(`/integrators/${integratorId}/certificates`);
      setItems(r.data?.certificates || []);
    } catch { setItems([]); } finally { setLoading(false); }
  };

  const handleDownload = async (cert) => {
    try {
      const r = await api.get(`/integrators/certificates/${cert.certificate_id}/download`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url; a.download = cert.original_name || 'certificado.pdf';
      document.body.appendChild(a); a.click(); a.remove();
      window.URL.revokeObjectURL(url);
    } catch { toast.error('No se pudo descargar el certificado'); }
  };

  const pickFile = (e) => {
    const f = e.target.files?.[0];
    if (f && !f.name.toLowerCase().endsWith('.pdf')) {
      toast.error('Solo se permiten archivos en formato PDF'); e.target.value = ''; return;
    }
    setFile(f || null);
  };

  const handleUpload = async () => {
    if (!file) { toast.error('Seleccione un archivo PDF'); return; }
    setUploading(true);
    try {
      const fd = new FormData(); fd.append('file', file);
      await api.post(`/integrators/${integratorId}/certificates`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      toast.success('Certificado agregado al historial');
      setUploadOpen(false); setFile(null);
      await loadList();
      onChange && onChange();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al cargar el certificado');
    } finally { setUploading(false); }
  };

  return (
    <>
      <Popover onOpenChange={(o) => { if (o) loadList(); }}>
        <PopoverTrigger asChild>
          <button className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded transition-colors hover:bg-slate-100"
            data-testid={`certs-trigger-${integratorId}`} title="Certificados Digitales">
            <FileText size={12} className={count > 0 ? 'text-emerald-600' : 'text-slate-400'} />
            <span className={count > 0 ? 'font-semibold text-emerald-700' : 'text-slate-400'}>{count}</span>
          </button>
        </PopoverTrigger>
        <PopoverContent className="w-80 p-0" align="center" data-testid={`certs-popover-${integratorId}`}>
          <div className="flex items-center justify-between px-3 py-2 border-b bg-slate-50">
            <span className="text-xs font-semibold text-slate-700">Certificados Digitales</span>
            <Button size="sm" variant="outline" className="h-6 px-2 text-[11px]" onClick={() => setUploadOpen(true)} data-testid={`certs-add-${integratorId}`}>
              <Plus size={12} className="mr-0.5" />Agregar
            </Button>
          </div>
          <div className="max-h-60 overflow-auto">
            {loading ? (
              <p className="text-xs text-slate-400 p-3 text-center">Cargando…</p>
            ) : items.length === 0 ? (
              <p className="text-xs text-slate-400 p-3 text-center">Sin certificados. Use "Agregar".</p>
            ) : items.map((c) => (
              <div key={c.certificate_id} className="flex items-center gap-2 px-3 py-2 border-b border-slate-100 hover:bg-slate-50" data-testid={`cert-item-${c.certificate_id}`}>
                <button onClick={() => handleDownload(c)} className="text-brand-blue-600 hover:text-brand-blue-800 shrink-0" title="Descargar PDF" data-testid={`cert-dl-${c.certificate_id}`}>
                  <Download size={15} />
                </button>
                <div className="min-w-0 flex-1">
                  <p className="text-[11px] font-medium text-slate-700 truncate">{c.original_name}</p>
                  <p className="text-[10px] text-slate-400">
                    {c.created_at ? new Date(c.created_at).toLocaleString('es-VE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''}
                    {' · '}{c.origin_label}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </PopoverContent>
      </Popover>

      <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
        <DialogContent className="max-w-sm" data-testid="cert-upload-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-emerald-700"><UploadCloud size={18} />Agregar Certificado</DialogTitle>
            <DialogDescription className="text-xs text-slate-500">
              Se agrega como una nueva versión sin reemplazar los certificados existentes. Solo PDF.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <input type="file" accept="application/pdf,.pdf" onChange={pickFile}
              className="block w-full text-sm text-slate-600 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-emerald-600 file:text-white file:cursor-pointer hover:file:bg-emerald-700"
              data-testid="cert-upload-input" />
            {file && <p className="text-xs text-slate-600">{file.name}</p>}
            <div className="flex justify-end gap-2 pt-2 border-t">
              <Button variant="outline" onClick={() => { setUploadOpen(false); setFile(null); }} data-testid="cert-upload-cancel">Cancelar</Button>
              <Button onClick={handleUpload} disabled={uploading || !file} className="bg-emerald-600 hover:bg-emerald-700 text-white" data-testid="cert-upload-confirm">
                {uploading ? 'Cargando…' : 'Cargar PDF'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default IntegratorCertificatesCell;
