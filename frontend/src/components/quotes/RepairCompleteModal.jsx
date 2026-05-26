import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Upload, FileText, X, Loader2, CheckCircle, AlertTriangle, Calculator, CalendarIcon, Wrench, CreditCard } from 'lucide-react';
import api from '../../utils/api';
import { toast } from 'sonner';

/**
 * RepairCompleteModal — Modal para acción "Reparada":
 *  1. Calculadora fiscal con conceptos de la cotización de reparación
 *  2. Carga opcional de comprobante de pago/anticipo
 *  3. Llama al endpoint repair-complete con datos de facturación
 */
export function RepairCompleteModal({ open, onClose, onSuccess, quoteId, quotes, config }) {
  const [paymentFiles, setPaymentFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [billingDate, setBillingDate] = useState('');
  const [exchangeRate, setExchangeRate] = useState('');
  const [rateSource, setRateSource] = useState('');
  const [rateLookupStatus, setRateLookupStatus] = useState('idle');
  const [manualRateMode, setManualRateMode] = useState(false);
  const paymentFileRef = useRef(null);

  const quote = useMemo(() => quotes?.find(q => q.quote_id === quoteId), [quotes, quoteId]);

  useEffect(() => {
    if (open) {
      const today = new Date().toISOString().split('T')[0];
      setBillingDate(today);
      setPaymentFiles([]);
      setManualRateMode(false);
    }
  }, [open]);

  useEffect(() => {
    if (!billingDate || !open) return;
    setRateLookupStatus('loading');
    setManualRateMode(false);
    api.get(`/exchange-rate/by-date/${billingDate}`).then(res => {
      if (res.data?.found) {
        setExchangeRate(String(res.data.valor_tasa));
        setRateSource(res.data.fuente || 'Historico');
        setRateLookupStatus('found');
      } else {
        api.get('/exchange-rate/current').then(curr => {
          const rate = curr.data?.rate || curr.data?.tasa;
          if (rate && rate > 0) {
            setExchangeRate(String(rate));
            setRateSource(curr.data?.source || 'Tasa vigente');
            setRateLookupStatus('not_found');
          } else {
            setExchangeRate(''); setRateSource(''); setRateLookupStatus('not_found');
          }
        }).catch(() => { setExchangeRate(''); setRateSource(''); setRateLookupStatus('not_found'); });
      }
    }).catch(() => { setExchangeRate(''); setRateSource(''); setRateLookupStatus('not_found'); });
  }, [billingDate, open]);

  // Consolidar items de reparación (equipment_items)
  const consolidated = useMemo(() => {
    if (!quote) return [];
    const items = quote.equipment_items || [];
    return items.map(item => ({
      name: item.name || item.hardware_name || 'Concepto',
      quantity: item.quantity || 1,
      unit_price_usd: item.unit_price_usd || item.price || 0,
      total_usd: (item.unit_price_usd || item.price || 0) * (item.quantity || 1),
    }));
  }, [quote]);

  const rateNum = parseFloat(exchangeRate) || 0;
  const grandTotalUsd = consolidated.reduce((sum, c) => sum + c.total_usd, 0);
  const grandTotalBs = grandTotalUsd * rateNum;
  const isIvaExempt = !!quote?.iva_exempt;
  const ivaRate = isIvaExempt ? 0 : 0.16;
  const ivaUsd = grandTotalUsd * ivaRate;
  const ivaBs = grandTotalBs * ivaRate;
  const grandTotalConIvaUsd = grandTotalUsd + ivaUsd;
  const grandTotalConIvaBs = grandTotalBs + ivaBs;

  const handleFileSelect = (e) => {
    const selected = Array.from(e.target.files || []);
    if (!selected.length) return;
    const oversized = selected.filter(f => f.size > 10 * 1024 * 1024);
    if (oversized.length) { toast.error('Los archivos no deben superar los 10MB'); return; }
    setPaymentFiles(prev => [...prev, ...selected]);
    if (paymentFileRef.current) paymentFileRef.current.value = '';
  };

  const removeFile = (index) => setPaymentFiles(prev => prev.filter((_, i) => i !== index));

  const handleSaveManualRate = async () => {
    const val = parseFloat(exchangeRate);
    if (!val || val <= 0) { toast.error('Ingrese una tasa valida'); return; }
    try {
      await api.post('/exchange-rate/manual', { fecha: billingDate, valor_tasa: val });
      setRateSource('Manual'); setRateLookupStatus('found'); setManualRateMode(false);
      toast.success(`Tasa de ${val.toFixed(2)} registrada para ${billingDate}`);
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al registrar tasa'); }
  };

  const handleSubmit = async () => {
    if (!rateNum || rateNum <= 0) { toast.error('La tasa de cambio es requerida'); return; }
    if (!billingDate) { toast.error('La fecha de facturacion es requerida'); return; }

    setUploading(true);
    try {
      // Upload payment proof files
      for (const file of paymentFiles) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('category', 'Soporte de Aprobación');
        await api.post(`/quotes/${quoteId}/attachments`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
      }

      // Call repair-complete with billing data
      const headers = {};
      if (config?.exceptionHeaders) {
        headers['x-exception-reason'] = config.exceptionHeaders.reason;
        headers['x-regularization-date'] = config.exceptionHeaders.regularization_date || '';
      }
      if (config?.emailHeaders) Object.assign(headers, config.emailHeaders);

      await api.post(`/quotes/${quoteId}/repair-complete`, {
        billing_data: {
          consolidated_items: consolidated.map(c => ({
            name: c.name, quantity: c.quantity, total_usd: c.total_usd,
            exchange_rate: rateNum, total_bs: c.total_usd * rateNum,
          })),
          exchange_rate: rateNum, rate_source: rateSource, billing_date: billingDate,
          grand_total_usd: grandTotalUsd, grand_total_bs: grandTotalBs,
          iva_usd: ivaUsd, iva_bs: ivaBs,
          grand_total_con_iva_usd: grandTotalConIvaUsd, grand_total_con_iva_bs: grandTotalConIvaBs,
          has_payment_proof: paymentFiles.length > 0,
        }
      }, { headers });

      toast.success('Reparacion finalizada — Administracion notificada');
      onSuccess?.();
      onClose();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al procesar');
    } finally { setUploading(false); }
  };

  if (!quote) return null;

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto" data-testid="repair-complete-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            <Wrench size={22} className="text-emerald-600" />
            Finalizar Reparacion — {quote.quote_number}
          </DialogTitle>
          <p className="text-sm text-slate-500">
            Esta accion informa a Administracion Sede PYME para la generacion de la factura.
          </p>
        </DialogHeader>

        <div className="space-y-4 py-2">

          {/* Calculadora fiscal */}
          <div className="border border-slate-200 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <Calculator size={16} className="text-purple-600" />
              <Label className="text-sm font-semibold text-slate-800">Preparacion de Factura (Conceptos de Reparacion)</Label>
            </div>

            {/* Fecha + Tasa */}
            <div className="flex flex-wrap items-end gap-4 mb-4 p-3 bg-slate-50 rounded-lg border border-slate-200">
              <div className="flex-1 min-w-[180px]">
                <Label className="text-xs text-slate-600 mb-1 flex items-center gap-1">
                  <CalendarIcon size={12} /> Fecha de Facturacion
                </Label>
                <Input type="date" value={billingDate} onChange={(e) => setBillingDate(e.target.value)}
                  className="h-9 text-sm" data-testid="repair-billing-date" />
              </div>
              <div className="flex-1 min-w-[160px]">
                <Label className="text-xs text-slate-600 mb-1">Tasa Bs./$ (BCV)</Label>
                <div className="flex items-center gap-2">
                  <Input type="number" step="0.01" min="0" value={exchangeRate}
                    onChange={(e) => { setExchangeRate(e.target.value); setManualRateMode(true); }}
                    disabled={rateLookupStatus === 'loading' || (rateLookupStatus === 'found' && !manualRateMode)}
                    className={`h-9 text-sm text-right font-mono flex-1 ${rateLookupStatus === 'found' && !manualRateMode ? 'bg-green-50 border-green-300' : ''}`}
                    placeholder="0.00" data-testid="repair-exchange-rate" />
                  {rateLookupStatus === 'loading' && <Loader2 size={16} className="animate-spin text-slate-400" />}
                  {rateLookupStatus === 'found' && !manualRateMode && <CheckCircle size={16} className="text-green-500 shrink-0" />}
                </div>
              </div>
              <div className="min-w-[100px]">
                <Label className="text-xs text-slate-600 mb-1">Fuente</Label>
                <div className="h-9 flex items-center px-2 bg-white border border-slate-200 rounded-md text-xs text-slate-600 font-medium truncate">
                  {rateSource || '—'}
                </div>
              </div>
            </div>

            {rateLookupStatus === 'not_found' && (
              <div className="flex items-start gap-2 p-3 mb-3 bg-amber-50 border border-amber-200 rounded-lg">
                <AlertTriangle size={16} className="text-amber-600 mt-0.5 shrink-0" />
                <div className="flex-1">
                  <p className="text-xs text-amber-800 font-semibold">No hay tasa registrada para {billingDate}</p>
                  <p className="text-xs text-amber-700 mt-1">Se muestra la tasa vigente como referencia.</p>
                  {manualRateMode && parseFloat(exchangeRate) > 0 && (
                    <Button size="sm" variant="outline" className="mt-2 h-7 text-xs border-amber-300 text-amber-700"
                      onClick={handleSaveManualRate}>
                      Registrar tasa {parseFloat(exchangeRate).toFixed(2)} para {billingDate}
                    </Button>
                  )}
                </div>
              </div>
            )}

            <p className="text-xs text-slate-500 mb-3">{isIvaExempt ? 'Cliente EXENTO de IVA — el impuesto se forzó a $0.00.' : 'Conceptos de la cotizacion de reparacion. IVA 16% calculado automaticamente.'}</p>

            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="repair-billing-table">
                <thead>
                  <tr className="bg-slate-700 text-white">
                    <th className="px-3 py-2 text-left text-xs font-medium">Concepto</th>
                    <th className="px-3 py-2 text-center text-xs font-medium">Cant.</th>
                    <th className="px-3 py-2 text-right text-xs font-medium">Monto ($)</th>
                    <th className="px-3 py-2 text-center text-xs font-medium w-20">Tasa</th>
                    <th className="px-3 py-2 text-right text-xs font-medium">C.U. Bs.</th>
                    <th className="px-3 py-2 text-right text-xs font-medium">Total (Bs.)</th>
                  </tr>
                </thead>
                <tbody>
                  {consolidated.map((item, idx) => {
                    const bsCalc = item.total_usd * rateNum;
                    const costoUnitBs = (item.quantity > 0 && rateNum > 0) ? (bsCalc / item.quantity) : 0;
                    return (
                      <tr key={idx} className="border-b border-slate-100 hover:bg-slate-50">
                        <td className="px-3 py-2 text-slate-800 text-xs">{item.name}</td>
                        <td className="px-3 py-2 text-center text-slate-600 text-xs">{item.quantity}</td>
                        <td className="px-3 py-2 text-right font-mono text-xs">${item.total_usd.toFixed(2)}</td>
                        <td className="px-3 py-2 text-center text-xs text-slate-400 font-mono">{rateNum > 0 ? rateNum.toFixed(2) : '—'}</td>
                        <td className="px-3 py-2 text-right font-mono text-xs whitespace-nowrap">{costoUnitBs > 0 ? `Bs. ${costoUnitBs.toFixed(2)}` : '—'}</td>
                        <td className="px-3 py-2 text-right font-mono text-xs whitespace-nowrap">{rateNum > 0 ? `Bs. ${bsCalc.toFixed(2)}` : '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot>
                  <tr className="bg-slate-50 border-t border-slate-200">
                    <td className="px-3 py-2 text-xs text-slate-700 font-semibold" colSpan={2}>Subtotal</td>
                    <td className="px-3 py-2 text-right font-mono text-xs font-semibold">${grandTotalUsd.toFixed(2)}</td>
                    <td colSpan={2}></td>
                    <td className="px-3 py-2 text-right font-mono text-xs font-semibold whitespace-nowrap">Bs. {grandTotalBs.toFixed(2)}</td>
                  </tr>
                  <tr className="bg-slate-50" data-testid="repair-iva-row">
                    <td className="px-3 py-1.5 text-xs text-slate-600" colSpan={2}>{isIvaExempt ? 'IVA (Exento)' : 'IVA (16%)'}</td>
                    <td className="px-3 py-1.5 text-right font-mono text-xs text-slate-600">${ivaUsd.toFixed(2)}</td>
                    <td colSpan={2}></td>
                    <td className="px-3 py-1.5 text-right font-mono text-xs text-slate-600 whitespace-nowrap">Bs. {ivaBs.toFixed(2)}</td>
                  </tr>
                  <tr className="bg-slate-100 font-bold border-t-2 border-slate-300">
                    <td className="px-3 py-2.5 text-xs text-slate-900" colSpan={2}>TOTAL GENERAL</td>
                    <td className="px-3 py-2.5 text-right font-mono text-xs text-slate-900">${grandTotalConIvaUsd.toFixed(2)}</td>
                    <td colSpan={2}></td>
                    <td className="px-3 py-2.5 text-right font-mono text-xs text-slate-900 whitespace-nowrap">Bs. {grandTotalConIvaBs.toFixed(2)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>

          {/* Comprobante de pago (opcional) */}
          <div className="border border-slate-200 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <CreditCard size={16} className="text-blue-600" />
              <Label className="text-sm font-semibold text-slate-800">Comprobante de Pago / Anticipo</Label>
              <span className="text-[10px] px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded font-medium">Opcional</span>
            </div>
            <p className="text-xs text-slate-500 mb-3">Si el cliente cancelo por adelantado, adjunte el comprobante para Administracion.</p>
            <label className={`flex items-center justify-center gap-2 p-3 border-2 border-dashed rounded-lg cursor-pointer transition-colors
              ${paymentFiles.length > 0 ? 'border-green-400 bg-green-50/50' : 'border-slate-300 hover:border-blue-400'}`}
              data-testid="repair-payment-dropzone">
              <Upload size={16} className={paymentFiles.length > 0 ? 'text-green-600' : 'text-slate-400'} />
              <span className={`text-sm ${paymentFiles.length > 0 ? 'text-green-700' : 'text-slate-500'}`}>
                {paymentFiles.length > 0 ? `${paymentFiles.length} archivo(s)` : 'Seleccionar archivo(s)'}
              </span>
              <input ref={paymentFileRef} type="file" className="hidden" accept=".pdf,.png,.jpg,.jpeg,.doc,.docx"
                multiple onChange={handleFileSelect} data-testid="repair-payment-input" />
            </label>
            {paymentFiles.length > 0 && (
              <div className="space-y-1 mt-2">
                {paymentFiles.map((file, idx) => (
                  <div key={idx} className="flex items-center gap-2 bg-white rounded-md px-3 py-1.5 border border-slate-200">
                    <FileText size={13} className="text-red-500 shrink-0" />
                    <span className="text-xs truncate flex-1">{file.name}</span>
                    <span className="text-[10px] text-slate-400">{(file.size / 1024).toFixed(0)} KB</span>
                    <button onClick={() => removeFile(idx)} className="text-slate-400 hover:text-red-500"><X size={13} /></button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-2 border-t border-slate-200">
          <Button variant="outline" onClick={onClose} disabled={uploading}>Cancelar</Button>
          <Button onClick={handleSubmit} disabled={uploading || rateNum <= 0 || !billingDate}
            className="bg-emerald-600 hover:bg-emerald-700" data-testid="repair-complete-submit">
            {uploading ? <Loader2 size={16} className="mr-2 animate-spin" /> : <Wrench size={16} className="mr-2" />}
            {uploading ? 'Procesando...' : 'Notificar a Administracion'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
