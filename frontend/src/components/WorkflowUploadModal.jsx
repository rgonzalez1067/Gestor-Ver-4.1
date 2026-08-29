import { useState, useRef } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Upload, FileText, X, Loader2, CheckCircle, AlertTriangle } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

/**
 * WorkflowUploadModal - Modal genérico para carga obligatoria de documentos
 * durante transiciones de estado.
 * 
 * Props:
 *  - open: boolean
 *  - onClose: () => void
 *  - onSuccess: () => void  (called after successful state transition)
 *  - quoteId: string
 *  - config: {
 *      title: string,
 *      description: string,
 *      category: string (attachment category),
 *      acceptMultiple: boolean,
 *      acceptTypes: string (file input accept),
 *      actionLabel: string (button text),
 *      actionColor: string (button CSS class),
 *      actionIcon: ReactNode,
 *      stateEndpoint: string (API endpoint to call after upload),
 *      extraFields: [{ name, label, placeholder, required }],  // optional extra form fields
 *    }
 */
export function WorkflowUploadModal({ open, onClose, onSuccess, quoteId, config }) {
  const [files, setFiles] = useState([]);
  const [perFileValues, setPerFileValues] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [extraData, setExtraData] = useState({});
  const fileInputRef = useRef(null);

  const resetState = () => {
    setFiles([]);
    setPerFileValues([]);
    setUploading(false);
    setExtraData({});
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleClose = () => {
    resetState();
    onClose();
  };

  const handleFileSelect = (e) => {
    const selected = Array.from(e.target.files || []);
    if (!selected.length) return;

    // Validate file size (10MB max each)
    const oversized = selected.filter(f => f.size > 10 * 1024 * 1024);
    if (oversized.length) {
      toast.error('Los archivos no deben superar los 10MB cada uno');
      return;
    }

    if (config.acceptMultiple) {
      setFiles(prev => [...prev, ...selected]);
      setPerFileValues(prev => [...prev, ...selected.map(() => '')]);
    } else {
      setFiles([selected[0]]);
      setPerFileValues(['']);
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
    setPerFileValues(prev => prev.filter((_, i) => i !== index));
  };

  const setPerFileValue = (index, value) => {
    setPerFileValues(prev => prev.map((v, i) => (i === index ? value : v)));
  };

  const handleSubmit = async () => {
    if (files.length === 0) {
      toast.error(`Debe cargar al menos un archivo de ${config.category}`);
      return;
    }

    // Check required extra fields
    if (config.extraFields) {
      for (const field of config.extraFields) {
        if (field.required && !extraData[field.name]?.trim()) {
          toast.error(`El campo "${field.label}" es obligatorio`);
          return;
        }
      }
    }

    // Check required per-file field (e.g., Nº de Factura por archivo)
    if (config.perFileField?.required) {
      const missing = files.some((_, i) => !(perFileValues[i] || '').trim());
      if (missing) {
        toast.error(`Debe indicar "${config.perFileField.label}" para cada archivo`);
        return;
      }
    }

    setUploading(true);
    try {
      // Step 1: Upload all files as attachments
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const formData = new FormData();
        formData.append('file', file);
        formData.append('category', config.category);
        if (config.perFileField && (perFileValues[i] || '').trim()) {
          formData.append(config.perFileField.name, perFileValues[i].trim());
        }
        await api.post(`/quotes/${quoteId}/attachments`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
      }

      // Step 2: Call the state transition endpoint
      if (config.stateEndpoint) {
        const exHeaders = {};
        if (config.exceptionHeaders) {
          exHeaders['x-exception-reason'] = config.exceptionHeaders.reason;
          exHeaders['x-regularization-date'] = config.exceptionHeaders.regularization_date || '';
        }
        // Email personalization headers
        if (config.emailHeaders) {
          Object.assign(exHeaders, config.emailHeaders);
        }
        // Consolidar los Nº de factura por archivo hacia el campo del endpoint de estado.
        const joinedPerFile = config.perFileField?.stateField
          ? perFileValues.map(v => (v || '').trim()).filter(Boolean).join(', ')
          : '';
        const hasStateForm = (config.extraFields?.length > 0) || (config.perFileField?.stateField && joinedPerFile);
        if (hasStateForm) {
          const formData = new FormData();
          for (const field of (config.extraFields || [])) {
            if (extraData[field.name]) {
              formData.append(field.name, extraData[field.name]);
            }
          }
          if (config.perFileField?.stateField && joinedPerFile) {
            formData.append(config.perFileField.stateField, joinedPerFile);
          }
          await api.post(`/quotes/${quoteId}/${config.stateEndpoint}`, formData, {
            headers: { 'Content-Type': 'multipart/form-data', ...exHeaders }
          });
        } else {
          await api.post(`/quotes/${quoteId}/${config.stateEndpoint}`, {}, { headers: exHeaders });
        }
      }

      toast.success(config.successMessage || 'Estado actualizado exitosamente');
      resetState();
      onSuccess?.();
    } catch (error) {
      const detail = error.response?.data?.detail;
      toast.error(detail || 'Error al procesar la solicitud');
    } finally {
      setUploading(false);
    }
  };

  if (!config) return null;

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) handleClose(); }}>
      <DialogContent className="max-w-md" data-testid="workflow-upload-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            {config.actionIcon}
            {config.title}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Description */}
          <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg">
            <AlertTriangle size={16} className="text-amber-600 mt-0.5 shrink-0" />
            <p className="text-sm text-amber-800">{config.description}</p>
          </div>

          {/* Extra fields (e.g., invoice number) */}
          {config.extraFields?.map(field => (
            <div key={field.name}>
              <Label htmlFor={`wf-${field.name}`}>
                {field.label} {field.required && <span className="text-red-500">*</span>}
              </Label>
              <Input
                id={`wf-${field.name}`}
                value={extraData[field.name] || ''}
                onChange={(e) => setExtraData(prev => ({ ...prev, [field.name]: e.target.value }))}
                placeholder={field.placeholder}
                data-testid={`workflow-field-${field.name}`}
              />
            </div>
          ))}

          {/* File upload area */}
          <div>
            <Label>
              {config.category} {config.acceptMultiple ? '(múltiples archivos)' : ''} <span className="text-red-500">*</span>
            </Label>
            <div className="mt-2">
              <label
                className={`flex items-center justify-center gap-2 p-5 border-2 border-dashed rounded-lg cursor-pointer transition-colors
                  ${files.length > 0 ? 'border-green-400 bg-green-50/50' : 'border-slate-300 hover:border-blue-400 hover:bg-blue-50/30'}`}
                data-testid="workflow-upload-dropzone"
              >
                <Upload size={20} className={files.length > 0 ? 'text-green-600' : 'text-slate-400'} />
                <span className={`text-sm ${files.length > 0 ? 'text-green-700' : 'text-slate-500'}`}>
                  {files.length > 0
                    ? `${files.length} archivo(s) seleccionado(s)`
                    : config.acceptMultiple
                      ? 'Seleccionar archivo(s)'
                      : 'Seleccionar archivo'
                  }
                </span>
                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  accept={config.acceptTypes || '.pdf,.doc,.docx,.xlsx,.xls,.png,.jpg,.jpeg'}
                  multiple={config.acceptMultiple}
                  onChange={handleFileSelect}
                  data-testid="workflow-file-input"
                />
              </label>
            </div>
          </div>

          {/* File list */}
          {files.length > 0 && (
            <div className="space-y-2">
              {files.map((file, idx) => (
                <div key={idx} className="rounded-md border border-slate-200 bg-white px-3 py-2" data-testid={`workflow-file-row-${idx}`}>
                  <div className="flex items-center gap-2">
                    <FileText size={14} className="text-red-500 shrink-0" />
                    <span className="text-sm truncate flex-1">{file.name}</span>
                    <span className="text-xs text-slate-400 shrink-0">
                      {(file.size / 1024).toFixed(0)} KB
                    </span>
                    <button
                      onClick={() => removeFile(idx)}
                      className="text-slate-400 hover:text-red-500 transition-colors"
                      data-testid={`workflow-remove-file-${idx}`}
                    >
                      <X size={14} />
                    </button>
                  </div>
                  {config.perFileField && (
                    <div className="mt-2 pl-6">
                      <Label htmlFor={`wf-perfile-${idx}`} className="text-xs text-slate-600">
                        {config.perFileField.label} {config.perFileField.required && <span className="text-red-500">*</span>}
                      </Label>
                      <Input
                        id={`wf-perfile-${idx}`}
                        value={perFileValues[idx] || ''}
                        onChange={(e) => setPerFileValue(idx, e.target.value)}
                        placeholder={config.perFileField.placeholder}
                        className="h-8 text-sm mt-1"
                        data-testid={`workflow-perfile-input-${idx}`}
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="outline" onClick={handleClose} disabled={uploading}>
            Cancelar
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={files.length === 0 || uploading}
            className={config.actionColor || 'bg-blue-600 hover:bg-blue-700'}
            data-testid="workflow-submit-btn"
          >
            {uploading ? (
              <Loader2 size={16} className="mr-2 animate-spin" />
            ) : (
              <CheckCircle size={16} className="mr-2" />
            )}
            {uploading ? 'Procesando...' : config.actionLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
