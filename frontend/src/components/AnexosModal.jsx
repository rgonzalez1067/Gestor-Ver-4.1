import { useState, useEffect, useRef } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { FileText, Upload, Trash2, Download, FolderOpen, File, Image, FileSpreadsheet, Loader2 } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const CATEGORIES = [
  { id: 'Cotización Original', icon: FileText, color: 'text-blue-600 bg-blue-50 border-blue-200' },
  { id: 'Orden de Compra', icon: FileSpreadsheet, color: 'text-amber-600 bg-amber-50 border-amber-200' },
  { id: 'Factura', icon: File, color: 'text-purple-600 bg-purple-50 border-purple-200' },
  { id: 'Otros', icon: FolderOpen, color: 'text-slate-600 bg-slate-50 border-slate-200' },
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

export function AnexosModal({ open, onClose, quoteId, quoteNumber }) {
  const [attachments, setAttachments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(null);
  const fileInputRefs = useRef({});

  useEffect(() => {
    if (open && quoteId) fetchAttachments();
  }, [open, quoteId]);

  const fetchAttachments = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/quotes/${quoteId}/attachments`);
      setAttachments(res.data.attachments || []);
    } catch (err) {
      toast.error('Error al cargar los anexos');
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
      const res = await api.post(`/quotes/${quoteId}/attachments`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      toast.success(`Anexo "${file.name}" subido exitosamente`);
      setAttachments(prev => [...prev, res.data.attachment]);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al subir el anexo');
    } finally {
      setUploading(null);
      input.value = '';
    }
  };

  const handleDelete = async (attachmentId, filename) => {
    if (!confirm(`¿Eliminar el anexo "${filename}"?`)) return;
    try {
      await api.delete(`/quotes/${quoteId}/attachments/${attachmentId}`);
      setAttachments(prev => prev.filter(a => a.attachment_id !== attachmentId));
      toast.success('Anexo eliminado');
    } catch (err) {
      toast.error('Error al eliminar el anexo');
    }
  };

  const handleDownload = async (attachment) => {
    try {
      const url = `${BACKEND_URL}/api/quotes/${quoteId}/attachments/${attachment.attachment_id}/download`;
      const token = localStorage.getItem('session_token');
      const response = await fetch(url, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!response.ok) throw new Error('Download failed');
      const blob = await response.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = attachment.filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(a.href);
    } catch (err) {
      toast.error('Error al descargar el archivo');
    }
  };

  const grouped = CATEGORIES.map(cat => ({
    ...cat,
    files: attachments.filter(a => a.category === cat.id)
  }));

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="anexos-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            <FolderOpen size={20} className="text-brand-blue-600" />
            Anexos — {quoteNumber || quoteId}
          </DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="animate-spin h-6 w-6 text-slate-400" />
          </div>
        ) : (
          <div className="space-y-4 mt-2">
            {grouped.map(({ id, icon: Icon, color, files }) => (
              <div key={id} className={`rounded-lg border p-4 ${color.split(' ').slice(1).join(' ')}`} data-testid={`anexo-category-${id.replace(/\s/g, '-').toLowerCase()}`}>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Icon size={18} className={color.split(' ')[0]} />
                    <span className="font-semibold text-sm">{id}</span>
                    <span className="text-xs text-slate-500 bg-white/80 px-1.5 py-0.5 rounded-full">{files.length}</span>
                  </div>
                  <div>
                    <input
                      type="file"
                      className="hidden"
                      ref={el => fileInputRefs.current[id] = el}
                      onChange={() => handleUpload(id)}
                      accept=".pdf,.doc,.docx,.xlsx,.xls,.csv,.png,.jpg,.jpeg,.webp"
                      data-testid={`anexo-upload-input-${id.replace(/\s/g, '-').toLowerCase()}`}
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs gap-1"
                      disabled={uploading === id}
                      onClick={() => fileInputRefs.current[id]?.click()}
                      data-testid={`anexo-upload-btn-${id.replace(/\s/g, '-').toLowerCase()}`}
                    >
                      {uploading === id ? (
                        <Loader2 size={12} className="animate-spin" />
                      ) : (
                        <Upload size={12} />
                      )}
                      Subir
                    </Button>
                  </div>
                </div>

                {files.length === 0 ? (
                  <p className="text-xs text-slate-400 italic pl-6">Sin documentos en esta categoría</p>
                ) : (
                  <div className="space-y-1.5">
                    {files.map((att) => (
                      <div
                        key={att.attachment_id}
                        className="flex items-center gap-2 bg-white rounded-md px-3 py-2 border border-slate-100 group"
                        data-testid={`anexo-file-${att.attachment_id}`}
                      >
                        {getFileIcon(att.filename)}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{att.filename}</p>
                          <p className="text-xs text-slate-400">
                            {formatFileSize(att.file_size)} · {att.uploaded_by_name || att.uploaded_by} · {new Date(att.uploaded_at).toLocaleDateString('es-VE')}
                          </p>
                        </div>
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 w-7 p-0 text-slate-500 hover:text-blue-600"
                            onClick={() => handleDownload(att)}
                            data-testid={`anexo-download-${att.attachment_id}`}
                          >
                            <Download size={14} />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 w-7 p-0 text-slate-500 hover:text-red-600"
                            onClick={() => handleDelete(att.attachment_id, att.filename)}
                            data-testid={`anexo-delete-${att.attachment_id}`}
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
