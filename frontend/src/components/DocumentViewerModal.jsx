import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { Button } from './ui/button';
import { Download, FileText } from 'lucide-react';
import { toast } from 'sonner';
import api from '../utils/api';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const isPdf = (doc) => /pdf/i.test(doc?.content_type || '') || /\.pdf$/i.test(doc?.filename || '');
const isImage = (doc) => /image\//i.test(doc?.content_type || '') || /\.(png|jpe?g|gif|webp|bmp)$/i.test(doc?.filename || '');

// Descarga nativa respetando el nombre/extensión original (vía blob autenticado).
export const downloadEntityDocument = async (doc) => {
  if (!doc?.document_id) return;
  try {
    const res = await api.get(`/entity-documents/${doc.document_id}/download`, { responseType: 'blob' });
    const url = window.URL.createObjectURL(res.data);
    const a = document.createElement('a');
    a.href = url;
    a.download = doc.filename || doc.name || 'documento';
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch {
    toast.error('No se pudo descargar el documento');
  }
};

// Visor embebido (lightbox) para PDF e imágenes; sin abandonar la plataforma.
export const DocumentViewerModal = ({ open, onOpenChange, doc }) => {
  if (!doc) return null;
  const token = localStorage.getItem('session_token');
  const previewUrl = `${BACKEND_URL}/api/entity-documents/${doc.document_id}/download?inline=true&token=${encodeURIComponent(token || '')}`;
  const pdf = isPdf(doc);
  const img = isImage(doc);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl h-[88vh] flex flex-col p-0 overflow-hidden" data-testid="doc-viewer-modal">
        <DialogHeader className="px-4 py-3 border-b">
          <DialogTitle className="flex items-center gap-2 text-sm text-slate-800 pr-8">
            <FileText size={16} className="text-blue-600 shrink-0" />
            <span className="truncate">{doc.name || doc.filename}</span>
          </DialogTitle>
          <DialogDescription className="sr-only">Vista previa embebida del documento {doc.filename}</DialogDescription>
        </DialogHeader>
        <div className="flex-1 min-h-0 bg-slate-100">
          {pdf ? (
            <iframe key={doc.document_id} src={previewUrl} title="Vista previa del documento" className="w-full h-full border-0" data-testid="doc-viewer-iframe" />
          ) : img ? (
            <div className="w-full h-full overflow-auto flex items-center justify-center p-4">
              <img src={previewUrl} alt={doc.filename} className="max-w-full max-h-full object-contain" data-testid="doc-viewer-img" />
            </div>
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center text-slate-500 gap-3 p-6 text-center" data-testid="doc-viewer-unsupported">
              <FileText size={40} className="opacity-40" />
              <p className="text-sm">Este formato ({doc.filename}) no admite vista previa embebida.<br />Descárguelo para revisarlo.</p>
            </div>
          )}
        </div>
        <div className="flex items-center justify-between gap-2 px-4 py-3 border-t bg-white">
          <span className="text-xs text-slate-400 truncate">{doc.filename}</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => onOpenChange(false)} data-testid="doc-viewer-close">Cerrar</Button>
            <Button size="sm" onClick={() => downloadEntityDocument(doc)} className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="doc-viewer-download">
              <Download size={14} className="mr-1.5" /> Descargar
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default DocumentViewerModal;
