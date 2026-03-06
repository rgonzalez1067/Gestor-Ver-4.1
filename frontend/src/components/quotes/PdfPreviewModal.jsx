import { Download, X } from 'lucide-react';
import { Button } from '../ui/button';
import { Dialog, DialogContent } from '../ui/dialog';

export const PdfPreviewModal = ({ open, onOpenChange, pdfUrl, loading }) => {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[90vw] max-h-[95vh] w-[900px] p-0" data-testid="pdf-preview-modal">
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="font-semibold text-lg">Vista Previa del PDF</h3>
          <div className="flex items-center gap-2">
            {pdfUrl && (
              <Button size="sm" onClick={() => window.open(pdfUrl, '_blank')}
                className="bg-brand-green-600 hover:bg-brand-green-700 text-white" data-testid="pdf-download-btn">
                <Download size={16} className="mr-2" /> Descargar PDF
              </Button>
            )}
            <Button size="sm" variant="outline" onClick={() => onOpenChange(false)}>
              <X size={16} className="mr-2" /> Cerrar
            </Button>
          </div>
        </div>
        <div className="flex-1 h-[80vh]">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-green-600 mx-auto"></div>
                <p className="mt-4 text-slate-500">Generando PDF...</p>
              </div>
            </div>
          ) : pdfUrl ? (
            <iframe src={pdfUrl} className="w-full h-full border-0" title="Vista previa PDF" />
          ) : (
            <div className="flex items-center justify-center h-full text-slate-400">
              No se pudo generar el PDF
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};
