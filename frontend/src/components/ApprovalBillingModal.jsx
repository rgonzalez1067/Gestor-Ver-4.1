import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Upload, FileText, X, Loader2, CheckCircle, AlertTriangle, Calculator, CalendarIcon, ShieldCheck } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

/**
 * ApprovalBillingModal — Modal de Aprobación con:
 *  1. Carga opcional de soporte de pago anticipado
 *  2. Carga opcional de comprobante de aprobación de cotización
 *  3. Fecha de facturación con auto-lookup de tasa histórica BCV
 *  4. Tabla de Instrucción de Facturación consolidada
 */
export function ApprovalBillingModal({ open, onClose, onSuccess, quoteId, quotes, config }) {
  const [paymentFiles, setPaymentFiles] = useState([]);
  const [approvalFiles, setApprovalFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [billingDate, setBillingDate] = useState('');
  const [exchangeRate, setExchangeRate] = useState('');
  const [rateSource, setRateSource] = useState('');
  const [rateLookupStatus, setRateLookupStatus] = useState('idle'); // idle | loading | found | not_found | manual
  const [manualRateMode, setManualRateMode] = useState(false);
  const [corpMatrix, setCorpMatrix] = useState(null); // {eligible, columns, setup_by_corp, recurring_by_corp}
  const [matrixRowMode, setMatrixRowMode] = useState('both'); // both | setup | recurring
  const [matrixCurrency, setMatrixCurrency] = useState('USD'); // USD | BS
  const [tokenizadorLine, setTokenizadorLine] = useState(null); // {applies, concepto, monto_usd}
  const paymentFileRef = useRef(null);
  const approvalFileRef = useRef(null);

  const quote = useMemo(() => quotes?.find(q => q.quote_id === quoteId), [quotes, quoteId]);
  const isEquipmentQuote = quote?.quote_category === 'equipment';
  const isRepairQuote = quote?.quote_category === 'repair';

  // Fetch matriz corporativa por tipo_corp (solo aplica a cotizaciones Corp elegibles)
  useEffect(() => {
    if (!open || !quoteId) { setCorpMatrix(null); return; }
    setMatrixRowMode('both');
    setMatrixCurrency('USD');
    api.get(`/quotes/${quoteId}/corp-billing-matrix`)
      .then(res => setCorpMatrix(res.data?.eligible ? res.data : null))
      .catch(() => setCorpMatrix(null));
    // Línea 'Configuración del Tokenizador' (Link de Pago variante tokenizador/ambos)
    api.get(`/quotes/${quoteId}/tokenizador-billing-line`)
      .then(res => setTokenizadorLine(res.data?.applies ? res.data : null))
      .catch(() => setTokenizadorLine(null));
  }, [open, quoteId]);

  // Set default billing date to today
  useEffect(() => {
    if (open) {
      const today = new Date().toISOString().split('T')[0];
      setBillingDate(today);
    }
  }, [open]);

  // Fetch rate when billing date changes
  useEffect(() => {
    if (!billingDate || !open) return;
    
    setRateLookupStatus('loading');
    setManualRateMode(false);
    
    api.get(`/exchange-rate/by-date/${billingDate}`).then(res => {
      if (res.data?.found) {
        setExchangeRate(String(res.data.valor_tasa));
        setRateSource(res.data.fuente || 'Histórico');
        setRateLookupStatus('found');
      } else {
        // Try fetching current rate as fallback
        api.get('/exchange-rate/current').then(curr => {
          const rate = curr.data?.rate || curr.data?.tasa;
          if (rate && rate > 0) {
            setExchangeRate(String(rate));
            setRateSource(curr.data?.source || 'Tasa vigente');
            setRateLookupStatus('not_found');
          } else {
            setExchangeRate('');
            setRateSource('');
            setRateLookupStatus('not_found');
          }
        }).catch(() => {
          setExchangeRate('');
          setRateSource('');
          setRateLookupStatus('not_found');
        });
      }
    }).catch(() => {
      setExchangeRate('');
      setRateSource('');
      setRateLookupStatus('not_found');
    });
  }, [billingDate, open]);

  // Consolidate items: para equipos usa equipment_items, para implementación usa services,
  // para Payment Gateway (quote_type=GATEWAY) usa pg_setup_items.
  // Para Fast Track (MPOS Imple+POS) la cotización es MIXTA: incluye dos secciones:
  //   1. Implementación (de `services`, excluyendo recurrentes)
  //   2. Pinpads (de `ft_equipment_items`)
  const consolidated = useMemo(() => {
    if (!quote) return [];

    const isFastTrack = quote.quote_category === 'fast_track';

    if (isFastTrack) {
      const out = [];
      // Sección 1: Implementación (services, excluyendo recurrentes)
      const services = quote.services || [];
      const implMap = {};
      for (const s of services) {
        if (s.item_type === 'recurring_basic' || s.item_type === 'recurring_other') continue;
        const name = s.item_name || s.name || 'Sin nombre';
        if (!implMap[name]) {
          implMap[name] = { name, quantity: 0, total_usd: 0, unit_price_usd: s.unit_price_usd || s.price || 0, section: 'Implementación' };
        }
        implMap[name].quantity += (s.quantity || 1);
        implMap[name].total_usd += (s.total_usd || s.subtotal_usd || 0);
      }
      out.push(...Object.values(implMap));
      // Sección 2: Pinpads (ft_equipment_items)
      const ftItems = quote.ft_equipment_items || [];
      const pinMap = {};
      for (const it of ftItems) {
        const name = it.modelo || it.model_name || it.name || 'Pinpad';
        const qty = Number(it.quantity || 1) || 1;
        const unit = Number(it.unit_price_usd || it.price || 0) || 0;
        if (!pinMap[name]) {
          pinMap[name] = { name, quantity: 0, total_usd: 0, unit_price_usd: unit, section: 'Pinpads' };
        }
        pinMap[name].quantity += qty;
        pinMap[name].total_usd += unit * qty;
      }
      out.push(...Object.values(pinMap));
      return out;
    }

    if (isEquipmentQuote) {
      // Cotización de Equipos y Accesorios: usar equipment_items
      const items = quote.equipment_items || [];
      return items.map(item => ({
        name: item.name || item.hardware_name || 'Equipo',
        quantity: item.quantity || 1,
        unit_price_usd: item.unit_price_usd || item.price || 0,
        total_usd: (item.unit_price_usd || item.price || 0) * (item.quantity || 1),
      }));
    }

    // Payment Gateway y Link de Pago/Tokenizador: los conceptos viven en
    // `pg_setup_items` (no en `services`). Link de Pago clona la estructura de PG.
    if (['GATEWAY', 'LINK_PAGO'].includes((quote.quote_type || '').toUpperCase())) {
      const pgItems = quote.pg_setup_items || [];
      const map = {};
      for (const it of pgItems) {
        const baseName = it.concepto || it.item_name || it.name || 'Concepto PG';
        const bank = it.banco && it.banco !== 'N/A' ? it.banco : '';
        const name = bank ? `${baseName} — ${bank}` : baseName;
        const cost = Number(it.costo ?? it.unit_price_usd ?? it.total_usd ?? 0) || 0;
        if (!map[name]) {
          map[name] = { name, quantity: 0, total_usd: 0, unit_price_usd: cost };
        }
        map[name].quantity += 1;
        map[name].total_usd += cost;
      }
      const out = Object.values(map);
      // Inyección obligatoria de 'Configuración del Tokenizador' (variante tokenizador/ambos)
      if (tokenizadorLine?.applies) {
        out.push({
          name: tokenizadorLine.concepto || 'Configuración del Tokenizador',
          quantity: 1,
          unit_price_usd: Number(tokenizadorLine.monto_usd || 0),
          total_usd: Number(tokenizadorLine.monto_usd || 0),
        });
      }
      return out;
    }

    // Cotización de Implementación: usar services (excluir recurrentes)
    const services = quote.services || [];
    const map = {};
    for (const s of services) {
      if (s.item_type === 'recurring_basic' || s.item_type === 'recurring_other') continue;
      const name = s.item_name || s.name || 'Sin nombre';
      if (!map[name]) {
        map[name] = { name, quantity: 0, total_usd: 0, unit_price_usd: s.unit_price_usd || s.price || 0 };
      }
      map[name].quantity += (s.quantity || 1);
      map[name].total_usd += (s.total_usd || s.subtotal_usd || 0);
    }
    return Object.values(map);
  }, [quote, isEquipmentQuote, tokenizadorLine]);

  const rateNum = parseFloat(exchangeRate) || 0;
  const grandTotalUsd = consolidated.reduce((sum, c) => sum + c.total_usd, 0);
  const grandTotalBs = grandTotalUsd * rateNum;
  const isIvaExempt = !!quote?.iva_exempt;
  const ivaRate = isIvaExempt ? 0 : 0.16;
  const ivaUsd = grandTotalUsd * ivaRate;
  const ivaBs = grandTotalBs * ivaRate;
  const grandTotalConIvaUsd = grandTotalUsd + ivaUsd;
  const grandTotalConIvaBs = grandTotalBs + ivaBs;

  // Matriz Financiera Consolidada por tipo_corp (aprobación Corporativa)
  const CORP_COLS = corpMatrix?.columns || ['Derecho de Uso', 'Infraestructura', 'Apoyo Técnico', 'Soporte y Monitoreo'];
  const fmtMatrix = useCallback((usd) => {
    if (matrixCurrency === 'BS') return `Bs. ${(usd * rateNum).toLocaleString('es-VE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    return `$${(usd || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }, [matrixCurrency, rateNum]);
  const matrixData = useMemo(() => {
    if (!corpMatrix?.eligible) return null;
    const setup = corpMatrix.setup_by_corp || {};
    const recurring = corpMatrix.recurring_by_corp || {};
    const showSetup = matrixRowMode === 'both' || matrixRowMode === 'setup';
    const showRec = matrixRowMode === 'both' || matrixRowMode === 'recurring';
    const rows = [];
    if (showSetup) rows.push({ label: 'Setup', byCol: setup, total: CORP_COLS.reduce((s, c) => s + (setup[c] || 0), 0) });
    if (showRec) rows.push({ label: 'Recurrentes', byCol: recurring, total: CORP_COLS.reduce((s, c) => s + (recurring[c] || 0), 0) });
    const totalByCol = {};
    CORP_COLS.forEach(c => { totalByCol[c] = (showSetup ? (setup[c] || 0) : 0) + (showRec ? (recurring[c] || 0) : 0); });
    const totalGeneral = Object.values(totalByCol).reduce((s, v) => s + v, 0);
    return { rows, totalByCol, totalGeneral, showSetup, showRec };
  }, [corpMatrix, matrixRowMode]);

  const resetState = useCallback(() => {
    setPaymentFiles([]);
    setApprovalFiles([]);
    setUploading(false);
    setBillingDate('');
    setExchangeRate('');
    setRateSource('');
    setRateLookupStatus('idle');
    setManualRateMode(false);
    if (paymentFileRef.current) paymentFileRef.current.value = '';
    if (approvalFileRef.current) approvalFileRef.current.value = '';
  }, []);

  const handleClose = () => { resetState(); onClose(); };

  const handleFileSelect = (e, setFn, inputRef) => {
    const selected = Array.from(e.target.files || []);
    if (!selected.length) return;
    const oversized = selected.filter(f => f.size > 10 * 1024 * 1024);
    if (oversized.length) { toast.error('Los archivos no deben superar los 10MB'); return; }
    setFn(prev => [...prev, ...selected]);
    if (inputRef.current) inputRef.current.value = '';
  };

  const removeFile = (index, setFn) => setFn(prev => prev.filter((_, i) => i !== index));

  const handleSaveManualRate = async () => {
    const val = parseFloat(exchangeRate);
    if (!val || val <= 0) { toast.error('Ingrese una tasa válida'); return; }
    try {
      await api.post('/exchange-rate/manual', { fecha: billingDate, valor_tasa: val });
      setRateSource('Manual');
      setRateLookupStatus('found');
      setManualRateMode(false);
      toast.success(`Tasa de ${val.toFixed(2)} registrada para ${billingDate}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al registrar tasa');
    }
  };

  const handleSubmit = async () => {
    if (!isRepairQuote && (!rateNum || rateNum <= 0)) { toast.error('La tasa de cambio es requerida'); return; }
    if (!isRepairQuote && !billingDate) { toast.error('La fecha de facturación es requerida'); return; }

    setUploading(true);
    try {
      // Step 1: Upload approval proof files (Orden de Compra) — SE PERSISTEN en quote.attachments
      for (const file of approvalFiles) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('category', 'Orden de Compra');
        await api.post(`/quotes/${quoteId}/attachments`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
      }

      // Step 2: Build approve payload + multipart con archivos de Pago Anticipado EFÍMEROS
      // (NO se almacenan; solo se adjuntan al correo de Administración).
      const exHeaders = {};
      if (config?.exceptionHeaders) {
        exHeaders['x-exception-reason'] = config.exceptionHeaders.reason;
        exHeaders['x-regularization-date'] = config.exceptionHeaders.regularization_date || '';
      }
      if (config?.emailHeaders) Object.assign(exHeaders, config.emailHeaders);

      const billingData = isRepairQuote ? {
        has_approval_proof: approvalFiles.length > 0,
      } : {
        consolidated_items: consolidated.map((c) => ({
          name: c.name,
          quantity: c.quantity,
          total_usd: c.total_usd,
          exchange_rate: rateNum,
          total_bs: c.total_usd * rateNum,
          section: c.section || null,
        })),
        exchange_rate: rateNum,
        rate_source: rateSource,
        billing_date: billingDate,
        grand_total_usd: grandTotalUsd,
        grand_total_bs: grandTotalBs,
        iva_usd: ivaUsd,
        iva_bs: ivaBs,
        grand_total_con_iva_usd: grandTotalConIvaUsd,
        grand_total_con_iva_bs: grandTotalConIvaBs,
        has_payment_proof: paymentFiles.length > 0,
        has_approval_proof: approvalFiles.length > 0,
      };

      // Matriz Financiera Consolidada (solo Corp elegible): moneda + filas + montos por tipo_corp
      if (corpMatrix?.eligible) {
        billingData.billing_matrix = {
          row_mode: matrixRowMode,
          currency: matrixCurrency,
          exchange_rate: rateNum,
          columns: CORP_COLS,
          setup_by_corp: corpMatrix.setup_by_corp || {},
          recurring_by_corp: corpMatrix.recurring_by_corp || {},
        };
      }

      const approveFormData = new FormData();
      approveFormData.append('payload', JSON.stringify(billingData));
      // Solo adjuntar archivos de pago anticipado si NO es reparación (no aplica)
      if (!isRepairQuote) {
        for (const file of paymentFiles) {
          approveFormData.append('payment_files', file);
        }
      }

      await api.post(`/quotes/${quoteId}/approve`, approveFormData, {
        headers: { ...exHeaders, 'Content-Type': 'multipart/form-data' },
      });

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

  const FileUploadZone = ({ label, description, files, setFiles, inputRef, icon: Icon, color, testIdPrefix, optional = true }) => (
    <div className="border border-slate-200 rounded-lg p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={16} className={color} />
        <Label className="text-sm font-semibold text-slate-800">{label}</Label>
        {optional && <span className="text-[10px] px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded font-medium">Opcional</span>}
      </div>
      <p className="text-xs text-slate-500 mb-3">{description}</p>
      <label className={`flex items-center justify-center gap-2 p-3 border-2 border-dashed rounded-lg cursor-pointer transition-colors
        ${files.length > 0 ? 'border-green-400 bg-green-50/50' : 'border-slate-300 hover:border-blue-400'}`}
        data-testid={`${testIdPrefix}-dropzone`}>
        <Upload size={16} className={files.length > 0 ? 'text-green-600' : 'text-slate-400'} />
        <span className={`text-sm ${files.length > 0 ? 'text-green-700' : 'text-slate-500'}`}>
          {files.length > 0 ? `${files.length} archivo(s)` : 'Seleccionar archivo(s)'}
        </span>
        <input ref={inputRef} type="file" className="hidden" accept=".pdf,.png,.jpg,.jpeg,.doc,.docx"
          multiple onChange={(e) => handleFileSelect(e, setFiles, inputRef)} data-testid={`${testIdPrefix}-input`} />
      </label>
      {files.length > 0 && (
        <div className="space-y-1 mt-2">
          {files.map((file, idx) => (
            <div key={idx} className="flex items-center gap-2 bg-white rounded-md px-3 py-1.5 border border-slate-200">
              <FileText size={13} className="text-red-500 shrink-0" />
              <span className="text-xs truncate flex-1">{file.name}</span>
              <span className="text-[10px] text-slate-400">{(file.size / 1024).toFixed(0)} KB</span>
              <button onClick={() => removeFile(idx, setFiles)} className="text-slate-400 hover:text-red-500">
                <X size={13} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) handleClose(); }}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto" data-testid="approval-billing-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            <CheckCircle size={22} className="text-green-600" />
            {isEquipmentQuote
              ? `Aprobación de Cotización de Equipos y Accesorios — ${quote.quote_number}`
              : `Aprobación de Cotización — ${quote.quote_number}`}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">

          {/* === VISTA SIMPLIFICADA PARA REPARACIONES === */}
          {isRepairQuote ? (
            <>
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-sm text-blue-800">
                  Cargue el documento que respalda la <strong>aprobación de la reparación</strong> por parte del cliente.
                  Este comprobante se adjuntará al registro de la cotización.
                </p>
              </div>
              <FileUploadZone
                label="Comprobante de Aprobación de Reparación"
                description="Orden de servicio firmada, correo de aprobación o captura del cliente autorizando la reparación."
                files={approvalFiles}
                setFiles={setApprovalFiles}
                inputRef={approvalFileRef}
                icon={ShieldCheck}
                color="text-indigo-600"
                testIdPrefix="approval-proof"
              />
            </>
          ) : (
            <>
          {/* 1. Upload: Comprobante de Pago Anticipado */}
          <FileUploadZone
            label="Comprobante de Pago Anticipado"
            description="Si el cliente canceló por adelantado, anexe el comprobante. Se adjuntará al correo de Administración."
            files={paymentFiles}
            setFiles={setPaymentFiles}
            inputRef={paymentFileRef}
            icon={Upload}
            color="text-blue-600"
            testIdPrefix="payment-proof"
          />

          {/* 2. Upload: Comprobante de Aprobación de Cotización */}
          <FileUploadZone
            label={isEquipmentQuote ? "Orden de Compra / Autorización" : "Comprobante de Aprobación de Cotización"}
            description={isEquipmentQuote
              ? "Respaldo de la compra de equipos: orden de compra, autorización de compra o correo de aprobación del cliente."
              : "Respaldo legal de aprobación del cliente: orden de compra, correo firmado o captura de aprobación."}
            files={approvalFiles}
            setFiles={setApprovalFiles}
            inputRef={approvalFileRef}
            icon={ShieldCheck}
            color="text-indigo-600"
            testIdPrefix="approval-proof"
          />

          {/* 3. Instrucción de Facturación */}
          <div className="border border-slate-200 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Calculator size={16} className="text-purple-600" />
                <Label className="text-sm font-semibold text-slate-800">Instrucción de Facturación</Label>
              </div>
            </div>

            {/* Fecha de Facturación + Tasa automática */}
            <div className="flex flex-wrap items-end gap-4 mb-4 p-3 bg-slate-50 rounded-lg border border-slate-200">
              <div className="flex-1 min-w-[180px]">
                <Label className="text-xs text-slate-600 mb-1 flex items-center gap-1">
                  <CalendarIcon size={12} /> Fecha de Facturación
                </Label>
                <Input
                  type="date"
                  value={billingDate}
                  onChange={(e) => setBillingDate(e.target.value)}
                  className="h-9 text-sm"
                  data-testid="billing-date-input"
                />
              </div>
              <div className="flex-1 min-w-[160px]">
                <Label className="text-xs text-slate-600 mb-1">Tasa Bs./$ (BCV)</Label>
                <div className="flex items-center gap-2">
                  <Input
                    type="number" step="0.01" min="0"
                    value={exchangeRate}
                    onChange={(e) => { setExchangeRate(e.target.value); setManualRateMode(true); }}
                    disabled={rateLookupStatus === 'loading' || (rateLookupStatus === 'found' && !manualRateMode)}
                    className={`h-9 text-sm text-right font-mono flex-1 ${rateLookupStatus === 'found' && !manualRateMode ? 'bg-green-50 border-green-300' : ''}`}
                    placeholder="0.00"
                    data-testid="exchange-rate-input"
                  />
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

            {/* Alerta si no hay tasa para la fecha */}
            {rateLookupStatus === 'not_found' && (
              <div className="flex items-start gap-2 p-3 mb-3 bg-amber-50 border border-amber-200 rounded-lg">
                <AlertTriangle size={16} className="text-amber-600 mt-0.5 shrink-0" />
                <div className="flex-1">
                  <p className="text-xs text-amber-800 font-semibold">No hay tasa registrada para {billingDate}</p>
                  <p className="text-xs text-amber-700 mt-1">
                    Se muestra la tasa vigente como referencia. Puede editarla manualmente y registrarla para esta fecha.
                  </p>
                  {manualRateMode && parseFloat(exchangeRate) > 0 && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="mt-2 h-7 text-xs border-amber-300 text-amber-700 hover:bg-amber-100"
                      onClick={handleSaveManualRate}
                      data-testid="save-manual-rate-btn"
                    >
                      Registrar tasa {parseFloat(exchangeRate).toFixed(2)} para {billingDate}
                    </Button>
                  )}
                </div>
              </div>
            )}

            <p className="text-xs text-slate-500 mb-3">
              {isIvaExempt
                ? 'Cliente EXENTO de IVA — el impuesto se forzó a $0.00 conforme al régimen fiscal del cliente.'
                : (isEquipmentQuote
                  ? 'Equipos y accesorios cotizados. IVA 16% calculado automáticamente.'
                  : 'Conceptos de Setup y Productos (excluye mantenimiento mensual/recurrentes). Consolidados por similitud. IVA 16% calculado automáticamente.')}
            </p>

            {/* ===== Matriz Financiera Consolidada (Corporativo) ===== */}
            {corpMatrix?.eligible && matrixData && (
              <div className="mb-4" data-testid="corp-billing-matrix">
                {/* Toggles */}
                <div className="flex flex-wrap items-center gap-4 mb-3">
                  <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1">
                    {[['both', 'Ambas'], ['setup', 'Solo Setup'], ['recurring', 'Solo Recurrente']].map(([val, lbl]) => (
                      <button
                        key={val}
                        onClick={() => setMatrixRowMode(val)}
                        className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${matrixRowMode === val ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                        data-testid={`matrix-rowmode-${val}`}
                      >{lbl}</button>
                    ))}
                  </div>
                  <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1">
                    {[['USD', '$ Dólares'], ['BS', 'Bs. Bolívares']].map(([val, lbl]) => (
                      <button
                        key={val}
                        onClick={() => setMatrixCurrency(val)}
                        disabled={val === 'BS' && rateNum <= 0}
                        className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors disabled:opacity-40 ${matrixCurrency === val ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                        data-testid={`matrix-currency-${val.toLowerCase()}`}
                      >{lbl}</button>
                    ))}
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-sm border-collapse" data-testid="corp-matrix-table">
                    <thead>
                      <tr>
                        <th rowSpan={2} className="px-3 py-2 text-left text-xs font-semibold text-white bg-[#00447C] border border-slate-300">Concepto</th>
                        <th colSpan={2} className="px-3 py-2 text-center text-xs font-semibold text-white bg-[#00447C] border border-slate-300">Hardware y Software</th>
                        <th colSpan={2} className="px-3 py-2 text-center text-xs font-semibold text-white bg-[#00447C] border border-slate-300">Consultoría</th>
                        <th rowSpan={2} className="px-3 py-2 text-right text-xs font-semibold text-white bg-[#00447C] border border-slate-300">Total ({matrixCurrency === 'BS' ? 'Bs.' : 'USD'})</th>
                      </tr>
                      <tr>
                        {CORP_COLS.map(c => (
                          <th key={c} className="px-3 py-1.5 text-center text-[11px] font-semibold text-white bg-[#336699] border border-slate-300">{c}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {matrixData.rows.map((r) => (
                        <tr key={r.label} data-testid={`matrix-row-${r.label.toLowerCase()}`}>
                          <td className="px-3 py-2 text-xs font-semibold text-[#00447C] border border-slate-200">{r.label}</td>
                          {CORP_COLS.map(c => (
                            <td key={c} className="px-3 py-2 text-right font-mono text-xs text-slate-800 border border-slate-200">{fmtMatrix(r.byCol[c] || 0)}</td>
                          ))}
                          <td className="px-3 py-2 text-right font-mono text-xs font-bold text-slate-900 border border-slate-200">{fmtMatrix(r.total)}</td>
                        </tr>
                      ))}
                      <tr className="font-bold" data-testid="matrix-row-total">
                        <td className="px-3 py-2 text-xs text-white bg-[#1E293B] border border-slate-300">TOTAL GENERAL</td>
                        {CORP_COLS.map(c => (
                          <td key={c} className="px-3 py-2 text-right font-mono text-xs text-white bg-[#1E293B] border border-slate-300">{fmtMatrix(matrixData.totalByCol[c] || 0)}</td>
                        ))}
                        <td className="px-3 py-2 text-right font-mono text-xs text-slate-900 bg-amber-400 border border-slate-300" data-testid="matrix-total-general">{fmtMatrix(matrixData.totalGeneral)}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <p className="text-[11px] text-slate-500 mt-1.5">
                  Montos no incluyen IVA{matrixCurrency === 'BS' && rateNum > 0 ? ` · Tasa: Bs. ${rateNum.toFixed(2)}/$` : ''}.
                </p>
              </div>
            )}

            <div className="overflow-x-auto" style={{ display: corpMatrix?.eligible ? 'none' : 'block' }}>
              <table className="w-full text-sm" data-testid="billing-consolidation-table">
                <thead>
                  <tr className="bg-slate-700 text-white">
                    <th className="px-3 py-2 text-left text-xs font-medium">
                      {isEquipmentQuote ? 'Equipo / Accesorio' : 'Concepto Consolidado'}
                    </th>
                    <th className="px-3 py-2 text-center text-xs font-medium">Cant.</th>
                    <th className="px-3 py-2 text-right text-xs font-medium">Monto ($)</th>
                    <th className="px-3 py-2 text-center text-xs font-medium w-20">Tasa Bs./$</th>
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
                        <td className="px-3 py-2 text-right font-mono text-xs text-slate-800">${item.total_usd.toFixed(2)}</td>
                        <td className="px-3 py-2 text-center text-xs text-slate-400 font-mono">{rateNum > 0 ? rateNum.toFixed(2) : '—'}</td>
                        <td className="px-3 py-2 text-right font-mono text-xs text-slate-800 whitespace-nowrap">
                          {costoUnitBs > 0 ? `Bs. ${costoUnitBs.toFixed(2)}` : '—'}
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-xs text-slate-800 whitespace-nowrap">
                          {rateNum > 0 ? `Bs. ${bsCalc.toFixed(2)}` : '—'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot>
                  <tr className="bg-slate-50 border-t border-slate-200">
                    <td className="px-3 py-2 text-xs text-slate-700 font-semibold" colSpan={2}>
                      {isEquipmentQuote ? 'Subtotal (Equipos y Accesorios)' : ((quote?.quote_type || '').toUpperCase() === 'GATEWAY' ? 'Subtotal (Conceptos PG)' : 'Subtotal (Setup + Productos)')}
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-xs text-slate-800 font-semibold">${grandTotalUsd.toFixed(2)}</td>
                    <td className="px-3 py-2"></td>
                    <td className="px-3 py-2"></td>
                    <td className="px-3 py-2 text-right font-mono text-xs text-slate-800 font-semibold whitespace-nowrap">Bs. {grandTotalBs.toFixed(2)}</td>
                  </tr>
                  <tr className="bg-slate-50" data-testid="billing-iva-row">
                    <td className="px-3 py-1.5 text-xs text-slate-600" colSpan={2}>{isIvaExempt ? 'IVA (Exento)' : 'IVA (16%)'}</td>
                    <td className="px-3 py-1.5 text-right font-mono text-xs text-slate-600">${ivaUsd.toFixed(2)}</td>
                    <td className="px-3 py-1.5"></td>
                    <td className="px-3 py-1.5"></td>
                    <td className="px-3 py-1.5 text-right font-mono text-xs text-slate-600 whitespace-nowrap">Bs. {ivaBs.toFixed(2)}</td>
                  </tr>
                  <tr className="bg-slate-100 font-bold border-t-2 border-slate-300">
                    <td className="px-3 py-2.5 text-xs text-slate-900" colSpan={2}>TOTAL GENERAL</td>
                    <td className="px-3 py-2.5 text-right font-mono text-xs text-slate-900">${grandTotalConIvaUsd.toFixed(2)}</td>
                    <td className="px-3 py-2.5"></td>
                    <td className="px-3 py-2.5"></td>
                    <td className="px-3 py-2.5 text-right font-mono text-xs text-slate-900 whitespace-nowrap">Bs. {grandTotalConIvaBs.toFixed(2)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
            </>
          )}
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-2 border-t border-slate-200">
          <Button variant="outline" onClick={handleClose} disabled={uploading}>Cancelar</Button>
          <Button
            onClick={handleSubmit}
            disabled={uploading || (!isRepairQuote && (rateNum <= 0 || !billingDate))}
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
