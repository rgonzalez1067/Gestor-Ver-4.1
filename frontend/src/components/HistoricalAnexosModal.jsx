import { useState, useEffect, useRef } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import {
  FileText, Upload, Trash2, Download, FolderOpen, File, Image,
  FileSpreadsheet, Loader2, DollarSign, Truck,
} from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

// Categorías que normalizan ("subsanan") las irregularidades de auditoría.
// Cada categoría está mapeada en el backend (SUBSANA_CATEGORY_MAP) hacia la
// fase del flujo cuya falta de timestamp queda compensada por el documento.
// Nota: "Orden de Compra" subsana la fase Aprobada (consistente con el modal
// de Cotizaciones activas).
const HIST_CATEGORIES = [
  { id: 'Cotización',           icon: FileText,        color: 'text-blue-600 bg-blue-50 border-blue-200',         desc: 'PDF de la cotización original (subsana Enviada al Cliente)' },
  { id: 'Orden de Compra',      icon: FileSpreadsheet, color: 'text-amber-600 bg-amber-50 border-amber-200',      desc: 'OC / Soporte de aprobación del cliente (subsana Aprobada)' },
  { id: 'Factura',              icon: File,            color: 'text-purple-600 bg-purple-50 border-purple-200',   desc: 'Documento fiscal (subsana Facturada)' },
  { id: 'Pagos',                icon: DollarSign,      color: 'text-emerald-700 bg-emerald-50 border-emerald-200',desc: 'Comprobantes (subsana Pagada)' },
  { id: 'Nota de Entrega',      icon: Truck,           color: 'text-teal-600 bg-teal-50 border-teal-200',         desc: 'Documento de entrega (subsana Entregada)' },
  { id: 'Otros',                icon: FolderOpen,      color: 'text-slate-600 bg-slate-50 border-slate-200',      desc: 'Documentación miscelánea — no normaliza fases' },
];

function formatFileSize(bytes) {
  if (!bytes) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileIcon(filename) {
  const ext = (filename || '').split('.').pop().toLowerCase();
  if (['pdf'].includes(ext)) return <FileText size={16} className="text-red-500" />;
  if (['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(ext)) return <Image size={16} className="text-green-500" />;
  if (['xlsx', 'xls', 'csv'].includes(ext)) return <FileSpreadsheet size={16} className="text-emerald-600" />;
  return <File size={16} className="text-slate-500" />;
}

export function HistoricalAnexosModal({ open, onClose, historyId, quoteNumber, onChange }) {
  const [attachments, setAttachments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(null);
  const fileInputRefs = useRef({});

  useEffect(() => {
    if (open && historyId) fetchAttachments();
  }, [open, historyId]);

  const fetchAttachments = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/quote-history/${historyId}/attachments`);
      setAttachments(res.data.attachments || []);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al cargar los anexos');
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (category) => {
    const input = fileInputRefs.current[category];
    if (!input?.files?.[0]) return;
    const file = input.files[0];
    if (file.size > 10 * 1024 * 1024) {
      toast.error('El archivo no debe superar los 10MB');
      input.value = '';
      return;
    }
    setUploading(category);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('category', category);
    try {
      const res = await api.post(`/quote-history/${historyId}/attachments`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      toast.success(`Anexo "${file.name}" subido al histórico`);
      setAttachments(prev => [...prev, res.data.attachment]);
      onChange && onChange();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al subir el anexo');
    } finally {
      setUploading(null);
      input.value = '';
    }
  };

  const handleDelete = async (attachmentId, filename) => {
    if (!confirm(`¿Eliminar el anexo "${filename}" del histórico?`)) return;
    try {
      await api.delete(`/quote-history/${historyId}/attachments/${attachmentId}`);
      setAttachments(prev => prev.filter(a => a.attachment_id !== attachmentId));
      toast.success('Anexo eliminado');
      onChange && onChange();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al eliminar el anexo');
    }
  };

  const handleDownload = async (attachment) => {
    try {
      const url = `${BACKEND_URL}/api/quote-history/${historyId}/attachments/${attachment.attachment_id}/download`;
      const token = localStorage.getItem('session_token');
      const response = await fetch(url, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('Download failed');
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      if ((attachment.filename || '').toLowerCase().endsWith('.pdf')) {
        window.open(blobUrl, '_blank');
      } else {
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = attachment.filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
      }
      setTimeout(() => URL.revokeObjectURL(blobUrl), 30000);
    } catch {
      toast.error('Error al descargar el archivo');
    }
  };

  const grouped = HIST_CATEGORIES.map(cat => ({
    ...cat,
    files: attachments.filter(a => a.category === cat.id),
  }));

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="historical-anexos-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            <FolderOpen size={20} className="text-amber-500" />
            Anexos Histórico — {quoteNumber || historyId}
          </DialogTitle>
          <p className="text-xs text-slate-500 mt-1">
            Carga documentos subsanatorios. Las cotizaciones del histórico marcadas como
            irregulares se normalizarán automáticamente al subir el documento que falte.
          </p>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="animate-spin h-6 w-6 text-slate-400" />
          </div>
        ) : (
          <div className="space-y-3 mt-2">
            {grouped.map(({ id, icon: Icon, color, desc, files }) => (
              <div
                key={id}
                className={`rounded-lg border p-3 ${color.split(' ').slice(1).join(' ')}`}
                data-testid={`hist-anexo-category-${id.replace(/\s/g, '-').toLowerCase()}`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <Icon size={18} className={color.split(' ')[0]} />
                    <span className="font-semibold text-sm">{id}</span>
                    <span className="text-xs text-slate-500 bg-white/80 px-1.5 py-0.5 rounded-full">{files.length}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="file"
                      className="hidden"
                      ref={el => fileInputRefs.current[id] = el}
                      onChange={() => handleUpload(id)}
                      accept=".pdf,.doc,.docx,.xlsx,.xls,.csv,.png,.jpg,.jpeg,.webp"
                      data-testid={`hist-anexo-upload-input-${id.replace(/\s/g, '-').toLowerCase()}`}
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs gap-1"
                      disabled={uploading === id}
                      onClick={() => fileInputRefs.current[id]?.click()}
                      data-testid={`hist-anexo-upload-btn-${id.replace(/\s/g, '-').toLowerCase()}`}
                    >
                      {uploading === id ? <Loader2 size={12} className="animate-spin" /> : <Upload size={12} />}
                      Subir
                    </Button>
                  </div>
                </div>
                <p className="text-[11px] text-slate-500 mb-2 pl-6">{desc}</p>

                {files.length === 0 ? (
                  <p className="text-xs text-slate-400 italic pl-6">Sin documentos</p>
                ) : (
                  <div className="space-y-1.5">
                    {files.map((att) => (
                      <div
                        key={att.attachment_id}
                        className="flex items-center gap-2 bg-white rounded-md px-3 py-2 border border-slate-100"
                        data-testid={`hist-anexo-file-${att.attachment_id}`}
                      >
                        {getFileIcon(att.filename)}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{att.filename}</p>
                          <p className="text-xs text-slate-400">
                            {formatFileSize(att.file_size)} · {att.uploaded_by_name || att.uploaded_by} · {att.uploaded_at ? new Date(att.uploaded_at).toLocaleDateString('es-VE') : ''}
                          </p>
                        </div>
                        <div className="flex items-center gap-1 shrink-0">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 w-7 p-0 text-blue-500 hover:text-blue-700 hover:bg-blue-50"
                            onClick={() => handleDownload(att)}
                            data-testid={`hist-anexo-download-${att.attachment_id}`}
                          >
                            <Download size={14} />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 w-7 p-0 text-slate-400 hover:text-red-600 hover:bg-red-50"
                            onClick={() => handleDelete(att.attachment_id, att.filename)}
                            data-testid={`hist-anexo-delete-${att.attachment_id}`}
                          >
                            <Trash2 size={14} />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default HistoricalAnexosModal;
