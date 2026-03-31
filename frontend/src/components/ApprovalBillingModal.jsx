import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Upload, FileText, X, Loader2, CheckCircle, AlertTriangle, Calculator, DollarSign } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

/**
 * ApprovalBillingModal — Modal de Aprobación con:
 *  1. Carga opcional de soporte (comprobante de pago anticipado)
 *  2. Tabla de Instrucción de Facturación (consolidación de conceptos)
 *  3. Calculadora de conversión Bs./$ con tasa de cambio
 */
export function ApprovalBillingModal({ open, onClose, onSuccess, quoteId, quotes, config }) {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [exchangeRate, setExchangeRate] = useState('');
  const [overrides, setOverrides] = useState({});
  const fileInputRef = useRef(null);

  const quote = useMemo(() => quotes?.find(q => q.quote_id === quoteId), [quotes, quoteId]);

  // Fetch current exchange rate on open
  useEffect(() => {
    if (open) {
      api.get('/exchange-rate/current').then(res => {
        const rate = res.data?.rate || res.data?.tasa;
        if (rate) setExchangeRate(String(rate));
      }).catch(() => {});
    }
  }, [open]);

  // Consolidate services: group by item_name, sum quantities and totals
  const consolidated = useMemo(() => {
    if (!quote) return [];
    const services = quote.services || [];
    const map = {};
    for (const s of services) {
      const name = s.item_name || s.name || 'Sin nombre';
      if (!map[name]) {
        map[name] = { name, quantity: 0, total_usd: 0, unit_price_usd: s.unit_price_usd || s.price || 0 };
      }
      map[name].quantity += (s.quantity || 1);
      map[name].total_usd += (s.total_usd || s.subtotal_usd || 0);
    }
    // Also include additional items if present
    for (const s of (quote.additional_items || [])) {
      const name = s.item_name || s.name || 'Adicional';
      if (!map[name]) {
        map[name] = { name, quantity: 0, total_usd: 0, unit_price_usd: s.unit_price_usd || 0 };
      }
      map[name].quantity += (s.quantity || 1);
      map[name].total_usd += (s.total_usd || 0);
    }
    return Object.values(map);
  }, [quote]);

  const rateNum = parseFloat(exchangeRate) || 0;
  const grandTotalUsd = consolidated.reduce((sum, c) => sum + c.total_usd, 0);
  const grandTotalBs = consolidated.reduce((sum, c, idx) => {
    const bsVal = overrides[idx] !== undefined ? parseFloat(overrides[idx]) || 0 : c.total_usd * rateNum;
    return sum + bsVal;
  }, 0);

  const resetState = useCallback(() => {
    setFiles([]);
    setUploading(false);
    setOverrides({});
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, []);

  const handleClose = () => { resetState(); onClose(); };

  const handleFileSelect = (e) => {
    const selected = Array.from(e.target.files || []);
    if (!selected.length) return;
    const oversized = selected.filter(f => f.size > 10 * 1024 * 1024);
    if (oversized.length) { toast.error('Los archivos no deben superar los 10MB'); return; }
    setFiles(prev => [...prev, ...selected]);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const removeFile = (index) => setFiles(prev => prev.filter((_, i) => i !== index));

  const handleSubmit = async () => {
    setUploading(true);
    try {
      // Step 1: Upload files if any (optional - comprobante de pago)
      for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('category', 'Soporte de Aprobación');
        await api.post(`/quotes/${quoteId}/attachments`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
      }

      // Step 2: Call approve endpoint
      const exHeaders = {};
      if (config?.exceptionHeaders) {
        exHeaders['x-exception-reason'] = config.exceptionHeaders.reason;
        exHeaders['x-regularization-date'] = config.exceptionHeaders.regularization_date || '';
      }
      if (config?.emailHeaders) Object.assign(exHeaders, config.emailHeaders);

      // Send consolidation data as body for the billing instruction
      const billingData = {
        consolidated_items: consolidated.map((c, idx) => ({
          name: c.name,
          quantity: c.quantity,
          total_usd: c.total_usd,
          exchange_rate: rateNum,
          total_bs: overrides[idx] !== undefined ? parseFloat(overrides[idx]) || 0 : c.total_usd * rateNum,
          is_override: overrides[idx] !== undefined
        })),
        exchange_rate: rateNum,
        grand_total_usd: grandTotalUsd,
        grand_total_bs: grandTotalBs,
        has_payment_proof: files.length > 0,
      };

      await api.post(`/quotes/${quoteId}/approve`, billingData, { headers: exHeaders });

      toast.success('Aprobación registrada exitosamente');
      resetState();
      onSuccess?.();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al aprobar');
    } finally {
      setUploading(false);
    }
  };

  if (!config || !quote) return null;

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) handleClose(); }}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="approval-billing-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            <CheckCircle size={22} className="text-green-600" />
            Aprobación de Cotización — {quote.quote_number}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-5 py-2">

          {/* 1. Soporte de Pago Anticipado (Opcional) */}
          <div className="border border-slate-200 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <Upload size={16} className="text-blue-600" />
              <Label className="text-sm font-semibold text-slate-800">Comprobante de Pago Anticipado</Label>
              <span className="text-[10px] px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded font-medium">Opcional</span>
            </div>
            <p className="text-xs text-slate-500 mb-3">
              Si el cliente canceló por adelantado, anexe el comprobante. Se adjuntará al correo de Administración.
            </p>
            <label className={`flex items-center justify-center gap-2 p-4 border-2 border-dashed rounded-lg cursor-pointer transition-colors
              ${files.length > 0 ? 'border-green-400 bg-green-50/50' : 'border-slate-300 hover:border-blue-400'}`}
              data-testid="approval-upload-dropzone">
              <Upload size={18} className={files.length > 0 ? 'text-green-600' : 'text-slate-400'} />
              <span className={`text-sm ${files.length > 0 ? 'text-green-700' : 'text-slate-500'}`}>
                {files.length > 0 ? `${files.length} archivo(s)` : 'Seleccionar archivo(s)'}
              </span>
              <input ref={fileInputRef} type="file" className="hidden" accept=".pdf,.png,.jpg,.jpeg,.doc,.docx"
                multiple onChange={handleFileSelect} data-testid="approval-file-input" />
            </label>
            {files.length > 0 && (
              <div className="space-y-1 mt-2">
                {files.map((file, idx) => (
                  <div key={idx} className="flex items-center gap-2 bg-white rounded-md px-3 py-1.5 border border-slate-200">
                    <FileText size={13} className="text-red-500 shrink-0" />
                    <span className="text-xs truncate flex-1">{file.name}</span>
                    <span className="text-[10px] text-slate-400">{(file.size / 1024).toFixed(0)} KB</span>
                    <button onClick={() => removeFile(idx)} className="text-slate-400 hover:text-red-500">
                      <X size={13} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 2. Instrucción de Facturación (Consolidación) */}
          <div className="border border-slate-200 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Calculator size={16} className="text-purple-600" />
                <Label className="text-sm font-semibold text-slate-800">Instrucción de Facturación</Label>
              </div>
              {/* 3. Tasa de Cambio */}
              <div className="flex items-center gap-2">
                <DollarSign size={14} className="text-emerald-600" />
                <Label className="text-xs text-slate-600 whitespace-nowrap">Tasa Bs./$:</Label>
                <Input
                  type="number" step="0.01" min="0"
                  value={exchangeRate}
                  onChange={(e) => { setExchangeRate(e.target.value); setOverrides({}); }}
                  className="w-24 h-8 text-sm text-right font-mono"
                  placeholder="36.50"
                  data-testid="exchange-rate-input"
                />
              </div>
            </div>
            <p className="text-xs text-slate-500 mb-3">
              Conceptos consolidados por similitud. Los montos en Bs. se calculan en tiempo real. Puede sobreescribir valores individuales.
            </p>

            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="billing-consolidation-table">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200">
                    <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Concepto Consolidado</th>
                    <th className="px-3 py-2 text-center text-xs font-medium text-slate-600">Cant.</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-slate-600">Monto ($)</th>
                    <th className="px-3 py-2 text-center text-xs font-medium text-slate-600 w-24">Tasa</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-slate-600">Total (Bs.)</th>
                  </tr>
                </thead>
                <tbody>
                  {consolidated.map((item, idx) => {
                    const bsCalc = item.total_usd * rateNum;
                    const bsValue = overrides[idx] !== undefined ? overrides[idx] : bsCalc.toFixed(2);
                    const isOverridden = overrides[idx] !== undefined;
                    return (
                      <tr key={idx} className="border-b border-slate-100 hover:bg-slate-50">
                        <td className="px-3 py-2 text-slate-800 text-xs">{item.name}</td>
                        <td className="px-3 py-2 text-center text-slate-600 text-xs">{item.quantity}</td>
                        <td className="px-3 py-2 text-right font-mono text-xs text-slate-800">${item.total_usd.toFixed(2)}</td>
                        <td className="px-3 py-2 text-center text-xs text-slate-400 font-mono">{rateNum > 0 ? rateNum.toFixed(2) : '—'}</td>
                        <td className="px-3 py-2 text-right">
                          <Input
                            type="number" step="0.01" min="0"
                            value={bsValue}
                            onChange={(e) => setOverrides(prev => ({ ...prev, [idx]: e.target.value }))}
                            className={`w-28 h-7 text-xs text-right font-mono ml-auto ${isOverridden ? 'border-amber-400 bg-amber-50' : ''}`}
                            data-testid={`bs-amount-${idx}`}
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot>
                  <tr className="bg-slate-100 font-semibold">
                    <td className="px-3 py-2 text-xs text-slate-700" colSpan={2}>TOTAL</td>
                    <td className="px-3 py-2 text-right font-mono text-xs text-slate-900">${grandTotalUsd.toFixed(2)}</td>
                    <td className="px-3 py-2"></td>
                    <td className="px-3 py-2 text-right font-mono text-xs text-slate-900">Bs. {grandTotalBs.toFixed(2)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>

            {Object.keys(overrides).length > 0 && (
              <p className="text-[10px] text-amber-600 mt-1 flex items-center gap-1">
                <AlertTriangle size={10} /> Valores en amarillo han sido ajustados manualmente.
              </p>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-2 border-t border-slate-200">
          <Button variant="outline" onClick={handleClose} disabled={uploading}>Cancelar</Button>
          <Button
            onClick={handleSubmit}
            disabled={uploading}
            className="bg-green-600 hover:bg-green-700"
            data-testid="approval-submit-btn"
          >
            {uploading ? <Loader2 size={16} className="mr-2 animate-spin" /> : <CheckCircle size={16} className="mr-2" />}
            {uploading ? 'Procesando...' : 'Confirmar Aprobación'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
