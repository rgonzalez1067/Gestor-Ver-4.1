/**
 * QuoteModals — Todos los modales secundarios de la vista de Cotizaciones.
 * Extraído de Quotes.jsx para reducir el tamaño del archivo principal.
 * Recibe un objeto `ctx` con todas las variables y funciones necesarias del padre.
 */
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../ui/alert-dialog';
import { Label } from '../ui/label';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';
import { Button } from '../ui/button';
import { Checkbox } from '../ui/checkbox';
import { AlertTriangle, CheckCircle, Mail, Paperclip, Plus, Send, Store, Trash2, X, Users, Landmark, Upload } from 'lucide-react';
import { useRef, useState, useEffect, useCallback, memo } from 'react';
import api from '../../utils/api';
import * as XLSX from 'xlsx';
import { toast } from 'sonner';
import { EquipmentQuoteWizard } from '../EquipmentQuoteWizard';
import { AnexosModal } from '../AnexosModal';
import { WorkflowUploadModal } from '../WorkflowUploadModal';
import { ApprovalBillingModal } from '../ApprovalBillingModal';
import { PdfPreviewModal } from './PdfPreviewModal';
import { DeliveryDialog } from './DeliveryDialog';
import { RepairDeliveryDialog } from './RepairDeliveryDialog';
import { PreassignSerialsModal } from './PreassignSerialsModal';
import { InternalEmailInput } from '../InternalEmailInput';
import { RichTextEditor } from '../RichTextEditor';
import { ACTION_LABELS } from './constants';

// ============================================================================
// Inputs aislados para Multitienda (rendimiento de escritura).
// El estado de las tiendas vive en el componente padre (Quotes.jsx, muy grande),
// por lo que escribir en un <input> controlado por el padre re-renderizaba TODO
// el modal en cada tecla, generando latencia. Estos componentes mantienen estado
// LOCAL y propagan al padre con debounce (nombre) o al confirmar (formulario),
// eliminando el re-render por tecla.
// ============================================================================
const MultistoreRow = memo(function MultistoreRow({ store, idx, onCommit, onRemove }) {
  const [name, setName] = useState(store.name || '');
  const [box, setBox] = useState(store.box_count ?? 1);
  const timer = useRef(null);
  const extName = useRef(store.name);
  const extBox = useRef(store.box_count);

  // Resincroniza si el valor cambia desde el padre (restaurar, reordenar, etc.)
  useEffect(() => {
    if (store.name !== extName.current) { extName.current = store.name; setName(store.name || ''); }
  }, [store.name]);
  useEffect(() => {
    if (store.box_count !== extBox.current) { extBox.current = store.box_count; setBox(store.box_count ?? 1); }
  }, [store.box_count]);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const onNameChange = (e) => {
    const v = e.target.value;
    setName(v);
    extName.current = v; // marca como propio para evitar reset por el efecto de sync
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => onCommit(idx, { name: v }), 200);
  };
  const onNameBlur = () => {
    if (timer.current) { clearTimeout(timer.current); timer.current = null; }
    extName.current = name;
    onCommit(idx, { name });
  };
  const onBoxBlur = () => {
    const v = Math.max(1, parseInt(box) || 1);
    setBox(v);
    extBox.current = v;
    onCommit(idx, { box_count: v });
  };

  return (
    <tr className="border-b last:border-0" data-testid={`inherited-row-${idx}`}>
      <td className="px-3 py-1.5 text-slate-400 font-mono">{idx + 1}</td>
      <td className="px-3 py-1.5">
        <input
          type="text"
          value={name}
          onChange={onNameChange}
          onBlur={onNameBlur}
          className="w-full h-8 px-2 text-sm border border-slate-200 rounded focus:border-blue-400 focus:outline-none"
          data-testid={`inherited-name-${idx}`}
        />
      </td>
      <td className="px-3 py-1.5">
        <input
          type="number"
          min="1"
          value={box}
          onChange={(e) => setBox(e.target.value)}
          onBlur={onBoxBlur}
          className="w-full h-8 px-2 text-sm text-center border border-slate-200 rounded focus:border-blue-400 focus:outline-none"
          data-testid={`inherited-qty-${idx}`}
        />
      </td>
      <td className="px-3 py-1.5 text-center">
        <button
          type="button"
          onClick={() => onRemove(idx)}
          className="text-red-500 hover:text-red-700 p-1"
          title="Eliminar sucursal"
          data-testid={`inherited-remove-${idx}`}
        >
          <Trash2 size={14} />
        </button>
      </td>
    </tr>
  );
});

const MultistoreAddForm = memo(function MultistoreAddForm({ remaining, onAppend }) {
  const [name, setName] = useState('');
  const [box, setBox] = useState('');
  const submit = () => {
    const nm = name.trim();
    const boxCount = parseInt(box) || 0;
    if (!nm) { toast.error('Ingrese el nombre de la tienda'); return; }
    if (boxCount <= 0) { toast.error('La cantidad de cajas debe ser mayor a 0'); return; }
    if (boxCount > remaining) { toast.error(`Solo quedan ${remaining} caja(s) por asignar`); return; }
    onAppend(nm, boxCount);
    setName(''); setBox('');
  };
  return (
    <div className="flex items-end gap-2">
      <div className="flex-1">
        <Label className="text-xs text-slate-500">Nombre de tienda</Label>
        <Input
          placeholder="Ej: Tienda Centro, Sucursal Norte..."
          value={name}
          onChange={(e) => setName(e.target.value)}
          data-testid="multistore-store-name"
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); submit(); } }}
        />
      </div>
      <div className="w-24">
        <Label className="text-xs text-slate-500">Cajas</Label>
        <Input
          type="number"
          min="1"
          max={remaining}
          placeholder="Cant."
          value={box}
          onChange={(e) => setBox(e.target.value)}
          data-testid="multistore-store-boxes"
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); submit(); } }}
        />
      </div>
      <Button variant="outline" size="sm" onClick={submit} data-testid="multistore-add-store-btn" className="shrink-0">
        <Plus size={14} className="mr-1" /> Agregar
      </Button>
    </div>
  );
});

// Barra de carga por Excel para la distribución Multitienda.
// Reutiliza el MISMO formato y lógica cliente que "Detalle de Sucursales" del
// cotizador (xlsx en el navegador, plantilla estándar 'plantilla_tiendas.xlsx',
// columnas Nombre Tienda | Cantidad de Cajas). Reemplaza la distribución actual.
const MultistoreExcelBar = memo(function MultistoreExcelBar({ onLoaded }) {
  const inputRef = useRef(null);

  const downloadTemplate = () => {
    const data = [
      ['Nombre Tienda', 'Cantidad de Cajas'],
      ['Sucursal Centro', 3],
      ['Sucursal Norte', 2],
      ['Sucursal Sur', 1],
    ];
    const ws = XLSX.utils.aoa_to_sheet(data);
    ws['!cols'] = [{ wch: 30 }, { wch: 18 }];
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Tiendas');
    XLSX.writeFile(wb, 'plantilla_tiendas.xlsx');
  };

  const onFile = (e) => {
    const file = e.target.files?.[0];
    if (e.target) e.target.value = '';
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      try {
        const wb = XLSX.read(evt.target.result, { type: 'binary' });
        const ws = wb.Sheets[wb.SheetNames[0]];
        const data = XLSX.utils.sheet_to_json(ws, { header: 1 });
        const isHeaderRow = (row) => {
          if (!row || row.length < 2) return true;
          const v = row[1];
          if (v === null || v === undefined || v === '') return true;
          const n = parseFloat(String(v).trim().replace(',', '.'));
          return !Number.isFinite(n) || n <= 0;
        };
        const startIdx = isHeaderRow(data[0]) ? 1 : 0;
        const imported = [];
        let invalid = 0;
        for (let i = startIdx; i < data.length; i++) {
          const row = data[i];
          if (!row || row.length < 2) continue;
          const name = String(row[0] ?? '').trim();
          const rawQty = row[1];
          if (!name && (rawQty === null || rawQty === undefined || rawQty === '')) continue;
          if (!name) continue;
          const qty = parseInt(String(rawQty).trim().replace(',', '.'));
          if (!Number.isFinite(qty) || qty <= 0) { invalid += 1; continue; }
          imported.push({ name, box_count: qty });
        }
        if (imported.length === 0) {
          toast.error('No se encontraron datos válidos. Use columnas: Nombre Tienda | Cantidad de Cajas (numérica)');
          return;
        }
        onLoaded(imported);
        const msg = `${imported.length} tienda(s) importada(s) (reemplazo total)`;
        if (invalid > 0) toast.warning(`${msg}. ${invalid} fila(s) ignoradas por cantidad inválida.`);
        else toast.success(msg);
      } catch {
        toast.error('Error al leer el archivo');
      }
    };
    reader.readAsBinaryString(file);
  };

  return (
    <div className="flex items-center gap-2 rounded-md bg-slate-50 border border-slate-200 px-2.5 py-2" data-testid="multistore-excel-bar">
      <span className="text-xs text-slate-500 mr-auto">Cargar por Excel (opcional)</span>
      <Button type="button" variant="outline" size="sm" className="text-xs h-7 border-blue-300 text-blue-600" onClick={downloadTemplate} data-testid="multistore-excel-template-btn">
        Plantilla
      </Button>
      <Button type="button" variant="outline" size="sm" className="text-xs h-7" onClick={() => inputRef.current?.click()} data-testid="multistore-excel-upload-btn">
        <Upload size={12} className="mr-1" />Excel
      </Button>
      <input ref={inputRef} type="file" accept=".xlsx,.xls,.csv" className="hidden" onChange={onFile} data-testid="multistore-excel-input" />
    </div>
  );
});


export const QuoteModals = ({ ctx }) => {
  const {
    // PDF Preview
    pdfPreviewOpen, setPdfPreviewOpen, pdfPreviewUrl, setPdfPreviewUrl, pdfPreviewLoading,
    // Equipment Wizard
    equipmentWizardOpen, setEquipmentWizardOpen, equipmentWizardMode, setEquipmentWizardMode, equipmentWizardSegment,
    clients, allHardware, currentUser, fetchData, quotes,
    // Delete confirm
    deleteConfirmOpen, setDeleteConfirmOpen, deleteQuoteData, executeDeleteQuote,
    // Workflow
    workflowModalOpen, setWorkflowModalOpen, workflowQuoteId, setWorkflowQuoteId,
    workflowConfig, setWorkflowConfig, handleWorkflowSuccess,
    // Approval
    approvalModalOpen, setApprovalModalOpen, approvalQuoteId, setApprovalQuoteId,
    approvalConfig, setApprovalConfig,
    // Anexos
    anexosOpen, setAnexosOpen, anexosQuoteId, setAnexosQuoteId, anexosQuoteNumber,
    // Exception (Irregular)
    exceptionModalOpen, setExceptionModalOpen, exceptionData, setExceptionData,
    exceptionReasonRef, exceptionDebounceRef, pendingAction, setPendingAction,
    confirmException,
    // Email modal
    emailModalOpen, setEmailModalOpen, emailModalConfig, emailCustomMessage, setEmailCustomMessage,
    emailNewRecipient, setEmailNewRecipient, emailRecipientsList, setEmailRecipientsList,
    addEmailRecipient, removeEmailRecipient, confirmEmailAndProceed,
    // Enviar al Cliente — Paso 1: selección de contactos
    contactSelectOpen, setContactSelectOpen, contactList, contactSelectLoading,
    contactSelectedEmails, toggleContactEmail, handleContactSelectContinue, contactSelectAction,
    // Bitacora
    bitacoraFlujoOpen, setBitacoraFlujoOpen, bitacoraFlujoQuoteNumber,
    bitacoraFlujoEntries, bitacoraFlujoLoading,
    // Delivery
    deliveryDialogOpen, setDeliveryDialogOpen, deliveryQuoteId, deliveryExceptionInfo, deliveryEmailHeaders,
    // Repair Delivery
    repairDeliveryDialogOpen, setRepairDeliveryDialogOpen,
    // Preassign
    preassignModal, setPreassignModal,
    // Multistore
    multistoreDialogOpen, setMultistoreDialogOpen, multistoreSending,
    multistorePhase, setMultistorePhase, multistoreStores, setMultistoreStores,
    multistoreNewStore, setMultistoreNewStore, isMultistore, setIsMultistore,
    multistoreAssignedBoxes, confirmMultistore, addMultistoreStore, removeMultistoreStore,
    getMultistoreTotalCajas, getMultistoreQuote, confirmInheritedStores,
    handleProjectTypeSelect, advanceToMultistorePhase, modifyInheritedStores, handleMultistoreAnswer,
    // PYME extended flow
    pymeServerName, setPymeServerName, pymeServerCustom, setPymeServerCustom,
    economicGroup, setEconomicGroup, fantasyName, setFantasyName, handleEconomicDataContinue,
    confirmImplementerInfo, handleConfirmImplementerAdvance,
    implInstructions, setImplInstructions, implInstructionsLen, setImplInstructionsLen, handleConsolidatedContinue,
    pymeNeedsPinpads, setPymeNeedsPinpads,
    pymePinpadModels, pymePinpadSelectedModel,
    pymePinpadSerials, pymePinpadSerialsSelected, setPymePinpadSerialsSelected,
    pymePinpadLoading, handlePymeServerContinue, handlePymePinpadAnswer,
    handlePymePinpadModelSelect, handlePymePinpadConfirm,
    // Sub-flujo: seriales suministrados por un tercero
    banks,
    serialsByOther, setSerialsByOther, serialsProviderNote,
    serialsBankModal, setSerialsBankModal,
    handleSerialsProvider, handleSerialsBankSelect, handleSerialsLinkedBankSelect,
    // Fiscal Printer phase
    fiscalPrinterFromClient, fiscalPrinterModel, setFiscalPrinterModel, handleFiscalPrinterContinue,
    // Equipment phase
    projectTypeImpl, equipmentList, equipmentAvailable, equipmentLoading,
    equipmentSelected, setEquipmentSelected,
  } = ctx;

  // Handlers estables para Multitienda (evitan romper el memo de las filas).
  const commitStore = useCallback((idx, patch) => {
    setMultistoreStores(prev => prev.map((s, i) => (i === idx ? { ...s, ...patch } : s)));
  }, [setMultistoreStores]);
  const removeStore = useCallback((idx) => {
    setMultistoreStores(prev => prev.filter((_, i) => i !== idx));
  }, [setMultistoreStores]);
  const appendStore = useCallback((name, box_count) => {
    setMultistoreStores(prev => [...prev, { name, box_count }]);
  }, [setMultistoreStores]);

  // Instrucciones adicionales: propagación con debounce al padre para que escribir
  // no re-renderice todo el modal en cada tecla. Se hace flush al perder el foco
  // (p. ej. al pulsar "Continuar") para no perder los últimos caracteres.
  const implTimerRef = useRef(null);
  const implLatestRef = useRef({ html: implInstructions, len: implInstructionsLen });
  const handleInstrChange = useCallback((html, len) => {
    implLatestRef.current = { html, len };
    if (implTimerRef.current) clearTimeout(implTimerRef.current);
    implTimerRef.current = setTimeout(() => {
      setImplInstructions(html);
      setImplInstructionsLen(len);
    }, 250);
  }, [setImplInstructions, setImplInstructionsLen]);
  const flushInstr = useCallback(() => {
    if (implTimerRef.current) { clearTimeout(implTimerRef.current); implTimerRef.current = null; }
    const { html, len } = implLatestRef.current;
    setImplInstructions(html);
    setImplInstructionsLen(len);
  }, [setImplInstructions, setImplInstructionsLen]);

  return (
    <>
          {/* Modal de Previsualización PDF */}
          <PdfPreviewModal
            open={pdfPreviewOpen}
            onOpenChange={(open) => {
              if (!open && pdfPreviewUrl) { window.URL.revokeObjectURL(pdfPreviewUrl); setPdfPreviewUrl(null); }
              setPdfPreviewOpen(open);
            }}
            pdfUrl={pdfPreviewUrl}
            loading={pdfPreviewLoading}
          />

          {/* Wizard de Equipos y Accesorios / Reparaciones */}
          <EquipmentQuoteWizard
            open={equipmentWizardOpen}
            onClose={() => { setEquipmentWizardOpen(false); setEquipmentWizardMode(''); }}
            onQuoteCreated={fetchData}
            clients={clients}
            hardware={allHardware}
            forcedMode={equipmentWizardMode}
            userSede={equipmentWizardSegment || currentUser?.sede || 'PYME'}
          />

          {/* Modal de confirmación para Eliminar */}
          <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>¿Eliminar Cotización?</AlertDialogTitle>
                <AlertDialogDescription>
                  ¿Está seguro de que desea eliminar la Cotización <strong>&quot;{deleteQuoteData.number}&quot;</strong> de forma permanente?
                  <br /><br />
                  <span className="text-red-600 font-medium">Esta acción no se puede deshacer.</span>
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancelar</AlertDialogCancel>
                <AlertDialogAction 
                  onClick={executeDeleteQuote}
                  className="bg-red-600 hover:bg-red-700 text-white"
                >
                  Eliminar
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>

          {/* Modal de Workflow (Aprobar/Facturar/Cobrar con carga de documentos) */}
          <WorkflowUploadModal
            open={workflowModalOpen}
            onClose={() => { setWorkflowModalOpen(false); setWorkflowQuoteId(null); setWorkflowConfig(null); }}
            onSuccess={handleWorkflowSuccess}
            quoteId={workflowQuoteId}
            config={workflowConfig}
          />

          {/* Modal de Aprobación con Instrucción de Facturación */}
          <ApprovalBillingModal
            open={approvalModalOpen}
            onClose={() => { setApprovalModalOpen(false); setApprovalQuoteId(null); setApprovalConfig(null); }}
            onSuccess={() => { setApprovalModalOpen(false); setApprovalQuoteId(null); setApprovalConfig(null); fetchData(); }}
            quoteId={approvalQuoteId}
            quotes={quotes}
            config={approvalConfig}
          />

          {/* Modal de Anexos */}
          <AnexosModal
            open={anexosOpen}
            onClose={() => { setAnexosOpen(false); setAnexosQuoteId(null); }}
            quoteId={anexosQuoteId}
            quoteNumber={anexosQuoteNumber}
          />

          {/* Modal de Protocolo de Excepción (Flujo Irregular) */}
          <Dialog open={exceptionModalOpen} onOpenChange={setExceptionModalOpen}>
            <DialogContent className="max-w-md" data-testid="exception-modal">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2 text-orange-700">
                  <AlertTriangle size={22} className="text-orange-500" />
                  Alerta de Flujo Irregular
                </DialogTitle>
              </DialogHeader>
              {pendingAction && (
                <div className="space-y-4">
                  <div className="bg-orange-50 border border-orange-200 rounded-lg p-3 text-sm">
                    <p className="text-orange-800">
                      Detectamos que está intentando <strong>{ACTION_LABELS[pendingAction.action]}</strong> sin haber completado el paso anterior.
                    </p>
                    <p className="text-orange-600 mt-1 text-xs">
                      Estado esperado: <strong>{pendingAction.expectedStatus}</strong> — Estado actual: <strong>{pendingAction.currentStatus}</strong>
                    </p>
                  </div>
                  <div>
                    <Label className="text-sm font-medium">Motivo de la Excepción <span className="text-red-500">*</span></Label>
                    <Textarea defaultValue={exceptionData.reason}
                      onChange={e => {
                        exceptionReasonRef.current = e.target.value;
                        if (exceptionDebounceRef.current) clearTimeout(exceptionDebounceRef.current);
                        exceptionDebounceRef.current = setTimeout(() => {
                          setExceptionData(p => ({ ...p, reason: exceptionReasonRef.current }));
                        }, 400);
                      }}
                      placeholder="Explique por qué se realiza esta acción fuera del flujo regular..."
                      className="mt-1 min-h-[70px] text-sm" data-testid="exception-reason" />
                  </div>
                  <div>
                    <Label className="text-sm font-medium">Compromiso de Regularización</Label>
                    <Input type="date" value={exceptionData.regularization_date}
                      onChange={e => setExceptionData(p => ({ ...p, regularization_date: e.target.value }))}
                      className="mt-1" data-testid="exception-regularization-date" />
                    <p className="text-[10px] text-slate-400 mt-1">Fecha máxima para completar el paso faltante</p>
                  </div>
                  <div className="flex justify-end gap-3 pt-2 border-t">
                    <Button variant="outline" onClick={() => { setExceptionModalOpen(false); setPendingAction(null); }}>Cancelar</Button>
                    <Button onClick={confirmException}
                      disabled={!exceptionData.reason.trim()}
                      className="bg-orange-600 hover:bg-orange-700 text-white"
                      data-testid="exception-confirm-btn">
                      Confirmar Acción
                    </Button>
                  </div>
                </div>
              )}
            </DialogContent>
          </Dialog>

          {/* Enviar al Cliente — Paso 1: Modal de Selección de Destinatarios.
              Lista los contactos de la ficha del cliente (Nombre, Email, Rol) con
              checkbox; al Continuar precarga los correos en el modal de comunicación. */}
          <Dialog open={contactSelectOpen} onOpenChange={(open) => { if (!open) setContactSelectOpen(false); }}>
            <DialogContent className="max-w-lg" data-testid="contact-select-modal">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2 text-blue-700">
                  <Users size={20} className="text-blue-500" />
                  Seleccionar Destinatarios
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-3">
                <p className="text-sm text-slate-500">
                  {contactSelectAction === 'invoice'
                    ? 'Elija los contactos de la ficha del cliente a quienes se enviará la factura / proforma.'
                    : 'Elija los contactos de la ficha del cliente a quienes se enviará la cotización.'}
                </p>
                {contactSelectLoading ? (
                  <div className="flex items-center justify-center py-10">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
                  </div>
                ) : contactList.length === 0 ? (
                  <div className="text-center py-8 bg-slate-50 rounded-lg" data-testid="contact-select-empty">
                    <Users size={32} className="mx-auto text-slate-300 mb-2" />
                    <p className="text-sm text-slate-400">La ficha del cliente no tiene contactos con correo.</p>
                    <p className="text-xs text-slate-400 mt-1">Puede continuar y agregar destinatarios manualmente.</p>
                  </div>
                ) : (
                  <div className="border border-slate-200 rounded-lg overflow-hidden max-h-[340px] overflow-y-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-slate-50 text-slate-500 sticky top-0">
                        <tr>
                          <th className="px-3 py-2 w-10"></th>
                          <th className="px-3 py-2 text-left text-xs uppercase font-medium">Nombre</th>
                          <th className="px-3 py-2 text-left text-xs uppercase font-medium">Email</th>
                          <th className="px-3 py-2 text-left text-xs uppercase font-medium">Rol / Cargo</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {contactList.map((c, idx) => {
                          const checked = contactSelectedEmails.includes(c.email);
                          return (
                            <tr
                              key={c.contact_id || c.email || idx}
                              className={`cursor-pointer hover:bg-blue-50/60 ${checked ? 'bg-blue-50' : ''}`}
                              onClick={() => toggleContactEmail(c.email)}
                              data-testid={`contact-row-${idx}`}
                            >
                              <td className="px-3 py-2 text-center">
                                <Checkbox
                                  checked={checked}
                                  onCheckedChange={() => toggleContactEmail(c.email)}
                                  onClick={(e) => e.stopPropagation()}
                                  data-testid={`contact-checkbox-${idx}`}
                                />
                              </td>
                              <td className="px-3 py-2 text-slate-700 font-medium">
                                {c.full_name || `${c.first_name || ''} ${c.last_name || ''}`.trim() || '—'}
                                {c.scope === 'local' && (
                                  <span className="ml-1.5 text-[10px] font-semibold text-amber-700 bg-amber-100 px-1.5 py-0.5 rounded-full" data-testid={`contact-scope-local-${idx}`}>Sucursal{c.sucursal ? `: ${c.sucursal}` : ''}</span>
                                )}
                                {c.scope === 'principal' && (
                                  <span className="ml-1.5 text-[10px] font-semibold text-indigo-700 bg-indigo-100 px-1.5 py-0.5 rounded-full" data-testid={`contact-scope-principal-${idx}`}>Principal</span>
                                )}
                              </td>
                              <td className="px-3 py-2 text-slate-600 truncate max-w-[180px]">{c.email}</td>
                              <td className="px-3 py-2 text-slate-500">{c.role || '—'}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
                <div className="flex items-center justify-between pt-3 border-t">
                  <span className="text-xs text-slate-400" data-testid="contact-select-count">
                    {contactSelectedEmails.length} seleccionado(s)
                  </span>
                  <div className="flex gap-3">
                    <Button variant="outline" onClick={() => setContactSelectOpen(false)} data-testid="contact-select-cancel">Cancelar</Button>
                    <Button
                      onClick={handleContactSelectContinue}
                      className="bg-blue-600 hover:bg-blue-700 text-white"
                      data-testid="contact-select-continue"
                    >
                      Continuar
                    </Button>
                  </div>
                </div>
              </div>
            </DialogContent>
          </Dialog>

          {/* Modal de Personalización de Envío */}
          <Dialog open={emailModalOpen} onOpenChange={(open) => { if (!open) { setEmailModalOpen(false); setPendingAction(null); } }}>
            <DialogContent className="w-[70vw] max-w-[70vw]" data-testid="email-modal">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2 text-blue-700">
                  <Mail size={20} className="text-blue-500" />
                  Personalizar Comunicación
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800">
                  <p>Acción: <strong>{ACTION_LABELS[emailModalConfig.action] || emailModalConfig.action}</strong></p>
                  {emailModalConfig.quoteName && <p className="text-xs text-blue-600 mt-0.5">Cotización: {emailModalConfig.quoteName}</p>}
                </div>
                <div>
                  <Label className="text-sm font-medium">Mensaje personalizado <span className="text-xs text-slate-400">(opcional, máx 1500 caracteres)</span></Label>
                  <Textarea
                    key={emailModalOpen ? 'modal-open' : 'modal-closed'}
                    defaultValue={emailCustomMessage}
                    onBlur={e => setEmailCustomMessage(e.target.value.slice(0, 1500))}
                    placeholder="Ej: Estimado cliente, adjuntamos la documentación solicitada..."
                    className="mt-1 min-h-[220px] text-sm"
                    maxLength={1500}
                    data-testid="email-custom-message" />
                </div>
                <div>
                  <Label className="text-sm font-medium">
                    {emailModalConfig.action === 'send-to-client' ? 'Para (Destinatarios)' : 'Destinatarios adicionales (CC)'}
                  </Label>
                  <div className="flex gap-2 mt-1 items-start">
                    <div className="flex-1">
                      <InternalEmailInput
                        value={emailNewRecipient}
                        onChange={(v) => setEmailNewRecipient(v)}
                        placeholder="correo@ejemplo.com — o escriba para buscar usuario interno"
                        testId="email-cc-input"
                      />
                    </div>
                    <Button type="button" variant="outline" size="sm" onClick={addEmailRecipient}
                      disabled={!emailNewRecipient.trim() || !emailNewRecipient.includes('@')}
                      data-testid="email-add-cc-btn" className="mt-0">
                      <Plus size={14} />
                    </Button>
                  </div>
                  {emailRecipientsList.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {emailRecipientsList.map((email, idx) => (
                        <span key={idx} className="inline-flex items-center gap-1 text-xs bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded-full">
                          {email}
                          <button onClick={() => removeEmailRecipient(email)} className="hover:text-red-500 ml-0.5">
                            <X size={12} />
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <EmailManualAttachments ctx={ctx} />
                <div className="flex justify-end gap-3 pt-3 border-t">
                  <Button variant="outline" onClick={() => { setEmailModalOpen(false); setPendingAction(null); }} data-testid="email-cancel-btn">Cancelar</Button>
                  <Button onClick={confirmEmailAndProceed}
                    className="bg-blue-600 hover:bg-blue-700 text-white"
                    data-testid="email-confirm-btn">
                    <Send size={14} className="mr-1.5" />
                    Continuar
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>

          {/* Modal de Bitácora de Flujo (Historial de Excepciones) */}
          <Dialog open={bitacoraFlujoOpen} onOpenChange={setBitacoraFlujoOpen}>
            <DialogContent className="max-w-2xl max-h-[85vh] overflow-hidden flex flex-col" data-testid="bitacora-flujo-modal">
              <DialogHeader className="shrink-0">
                <DialogTitle className="flex items-center gap-2">
                  <AlertTriangle size={20} className="text-orange-500" />
                  Bitácora de Flujo — {bitacoraFlujoQuoteNumber}
                </DialogTitle>
              </DialogHeader>
              <div className="flex-1 overflow-y-auto min-h-0 mt-2">
                {bitacoraFlujoLoading ? (
                  <p className="text-sm text-slate-400 text-center py-8">Cargando historial...</p>
                ) : bitacoraFlujoEntries.length === 0 ? (
                  <div className="text-center py-8">
                    <CheckCircle size={32} className="mx-auto text-emerald-300 mb-2" />
                    <p className="text-sm text-slate-400">No hay excepciones registradas para esta cotización</p>
                  </div>
                ) : (
                  <div className="relative pl-8 space-y-0">
                    <div className="absolute left-[12px] top-3 bottom-3 w-0.5 bg-orange-200" />
                    {bitacoraFlujoEntries.map((entry) => {
                      const isOverdue = entry.regularization_date && entry.regularization_date < new Date().toISOString().slice(0, 10);
                      return (
                        <div key={entry.audit_id} className="relative pb-5" data-testid={`flujo-entry-${entry.audit_id}`}>
                          <div className={`absolute left-[-22px] top-1.5 w-4 h-4 rounded-full border-2 ${isOverdue ? 'bg-red-500 border-red-300' : 'bg-orange-500 border-orange-300'}`} />
                          <div className={`bg-white border rounded-lg p-4 ml-1 ${isOverdue ? 'border-red-200' : 'border-slate-200'}`}>
                            <div className="flex items-center justify-between mb-2">
                              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-bold rounded-full bg-orange-100 text-orange-700 border border-orange-200">
                                {ACTION_LABELS[entry.action] || entry.action}
                              </span>
                              <span className="text-[10px] text-slate-400">{entry.created_at?.slice(0, 10)}</span>
                            </div>
                            <p className="text-sm text-slate-800 mb-2">
                              El usuario <strong className="text-slate-900">{entry.user_name}</strong> ejecutó <strong>{ACTION_LABELS[entry.action]}</strong> sin haber completado el paso <strong>&quot;{entry.expected_status}&quot;</strong>.
                              <span className="text-slate-500"> Estado en el momento: &quot;{entry.actual_status}&quot;.</span>
                            </p>
                            <div className="bg-slate-50 rounded p-2.5 space-y-1.5">
                              <p className="text-xs"><span className="font-semibold text-slate-700">Motivo:</span> <span className="text-slate-600">{entry.exception_reason}</span></p>
                              {entry.regularization_date && (
                                <p className="text-xs">
                                  <span className="font-semibold text-slate-700">Compromiso de regularización:</span>{' '}
                                  <span className={`font-medium ${isOverdue ? 'text-red-600' : 'text-slate-600'}`}>
                                    {entry.regularization_date}
                                    {isOverdue && <span className="ml-1.5 text-[9px] font-bold text-red-500 uppercase">Vencido</span>}
                                  </span>
                                </p>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
              <div className="shrink-0 flex items-center justify-between pt-2 border-t border-slate-200 mt-2">
                <span className="text-[10px] text-slate-400">{bitacoraFlujoEntries.length} excepciones registradas</span>
                <Button variant="outline" size="sm" onClick={() => setBitacoraFlujoOpen(false)}>Cerrar</Button>
              </div>
            </DialogContent>
          </Dialog>

          {/* Delivery Dialog (Hoja de Ruta) */}
          <DeliveryDialog
            open={deliveryDialogOpen}
            onOpenChange={setDeliveryDialogOpen}
            quoteId={deliveryQuoteId}
            exceptionInfo={deliveryExceptionInfo}
            emailHeaders={deliveryEmailHeaders}
            onDelivered={() => fetchData()}
          />

          {/* Repair Delivery Dialog (Entrega de Reparaciones) */}
          <RepairDeliveryDialog
            open={repairDeliveryDialogOpen}
            onOpenChange={setRepairDeliveryDialogOpen}
            quoteId={deliveryQuoteId}
            exceptionInfo={deliveryExceptionInfo}
            onDelivered={() => fetchData()}
          />

          {/* Prerregistro de Seriales (Fast Track) */}
          <PreassignSerialsModal
            open={preassignModal.open}
            onClose={() => setPreassignModal({ open: false, quote: null })}
            quote={preassignModal.quote}
            token={localStorage.getItem('session_token')}
            onSuccess={() => fetchData()}
          />

          {/* Diálogo Multitienda + Tipo de Proyecto + Equipos */}
          <Dialog open={multistoreDialogOpen} onOpenChange={(open) => { if (!open && !multistoreSending) { setMultistoreDialogOpen(false); } }}>
            <DialogContent className={`max-w-lg ${(multistorePhase === 'inherited' || multistorePhase === 'collect') ? 'max-h-[80vh] flex flex-col overflow-hidden' : ''}`} data-testid="multistore-dialog">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <Store size={20} className="text-blue-600" />
                  Enviar a Implementación
                </DialogTitle>
              </DialogHeader>

              {/* Fase 0: Tipo de Proyecto — ELIMINADA (heredado automáticamente desde quote.quote_type) */}

              {/* Fase: Modal Consolidado (Servidor + Grupo Económico + Nombre de Fantasía + Instrucciones) */}
              {multistorePhase === 'consolidated_data' && (
                <div className="space-y-4 py-2" data-testid="consolidated-data-phase">
                  <div className="border-b pb-2">
                    <p className="text-sm text-slate-600 font-medium">Datos Técnicos e Instrucciones</p>
                    <p className="text-xs text-slate-400 mt-0.5">Último paso de captura. Estos datos se archivan en la Ficha Técnica del proyecto.</p>
                  </div>
                  <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-1">
                    {/* Servidor */}
                    <div>
                      <Label className="text-sm font-medium">Nombre del Servidor <span className="text-red-500">*</span></Label>
                      <div className="grid gap-1.5 mt-1.5">
                        {['Multicomercio MSC', 'Multicomercio MSC2', 'Otro'].map(opt => (
                          <button
                            key={opt}
                            type="button"
                            onClick={() => { setPymeServerName(opt); if (opt !== 'Otro') setPymeServerCustom(''); }}
                            className={`w-full text-left px-3 py-2 rounded-md border-2 transition-all text-sm ${pymeServerName === opt ? 'border-blue-500 bg-blue-50 font-semibold text-blue-800' : 'border-slate-200 hover:border-blue-300 hover:bg-blue-50/50 text-slate-700'}`}
                            data-testid={`consolidated-server-${opt.replace(/\s/g, '-').toLowerCase()}`}
                          >
                            {opt}
                          </button>
                        ))}
                      </div>
                      {pymeServerName === 'Otro' && (
                        <Input
                          type="text"
                          value={pymeServerCustom}
                          onChange={e => setPymeServerCustom(e.target.value)}
                          placeholder="Nombre del servidor personalizado…"
                          className="mt-2"
                          data-testid="consolidated-server-custom-input"
                        />
                      )}
                    </div>

                    {/* Grupo Económico */}
                    <div>
                      <Label htmlFor="consolidated_economic_group" className="text-sm font-medium">Grupo Económico</Label>
                      <Input
                        id="consolidated_economic_group"
                        type="text"
                        placeholder="(opcional — vacío registra 'Sin Grupo Económico')"
                        value={economicGroup}
                        onChange={(e) => setEconomicGroup(e.target.value)}
                        className="mt-1.5"
                        data-testid="consolidated-economic-group-input"
                      />
                    </div>

                    {/* Nombre de Fantasía */}
                    <div>
                      <Label htmlFor="consolidated_fantasy_name" className="text-sm font-medium">Nombre de Fantasía</Label>
                      <Input
                        id="consolidated_fantasy_name"
                        type="text"
                        placeholder="(opcional — vacío hereda Nombre del Comercio)"
                        value={fantasyName}
                        onChange={(e) => setFantasyName(e.target.value)}
                        className="mt-1.5"
                        data-testid="consolidated-fantasy-name-input"
                      />
                    </div>

                    {/* Instrucciones adicionales (Rich Text, 500 chars) */}
                    <div onBlur={flushInstr}>
                      <Label className="text-sm font-medium">Instrucciones adicionales para el Implementador</Label>
                      <p className="text-[11px] text-slate-500 mt-0.5 mb-1.5">Máximo 500 caracteres de texto visible. Use negrita, cursiva, listas u otros formatos para destacar puntos clave.</p>
                      <RichTextEditor
                        value={implInstructions}
                        onChange={handleInstrChange}
                        maxChars={500}
                        placeholder="Escriba aquí las indicaciones técnicas o comerciales que el implementador debe conocer…"
                        testid="impl-instructions-editor"
                      />
                    </div>
                  </div>
                  <div className="flex gap-3 justify-between pt-2 border-t">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        // Producto digital (Payment Gateway / Link de Pago): este es el
                        // primer paso, no hubo Pinpad/Fiscal → "Atrás" cierra el wizard.
                        if (projectTypeImpl === 'payment_gateway') {
                          setMultistoreDialogOpen(false);
                          return;
                        }
                        // Volver al paso anterior: pinpad_selection si seleccionó Sí, pinpad_question si No
                        setMultistorePhase(pymeNeedsPinpads ? 'pinpad_selection' : 'pinpad_question');
                      }}
                      data-testid="consolidated-back-btn"
                    >
                      Atrás
                    </Button>
                    <Button
                      className="bg-blue-600 hover:bg-blue-700 text-white"
                      size="sm"
                      onClick={handleConsolidatedContinue}
                      disabled={!pymeServerName || (pymeServerName === 'Otro' && !pymeServerCustom.trim())}
                      data-testid="consolidated-continue-btn"
                    >
                      Continuar
                    </Button>
                  </div>
                </div>
              )}

              {/* Fase: Confirmación de Implementador (heredado desde ficha de cliente) */}
              {multistorePhase === 'confirm_implementer' && (
                <div className="space-y-4 py-2" data-testid="confirm-implementer-phase">
                  <div className="border-b pb-2">
                    <p className="text-sm text-slate-600 font-medium">Confirmación de Responsable</p>
                    <p className="text-xs text-slate-400 mt-0.5">Herencia automática desde la ficha del cliente.</p>
                  </div>
                  <div className="rounded-lg border p-4 bg-slate-50 border-slate-200" data-testid="confirm-implementer-info">
                    {confirmImplementerInfo?.loading ? (
                      <p className="text-sm text-slate-500 italic">Consultando ficha del cliente…</p>
                    ) : confirmImplementerInfo?.name ? (
                      <>
                        <p className="text-sm text-slate-700">El implementador asignado para este cliente es:</p>
                        <p className="text-lg font-bold text-emerald-700 mt-1.5" data-testid="confirm-implementer-name">{confirmImplementerInfo.name}</p>
                        <p className="text-[11px] text-slate-500 mt-1">
                          Al avanzar, la cotización se convertirá en proyecto y quedará asignada automáticamente a este implementador.
                        </p>
                      </>
                    ) : (
                      <>
                        <p className="text-base font-semibold text-amber-700" data-testid="confirm-implementer-unassigned">Por asignar Implementador</p>
                        <p className="text-[11px] text-slate-500 mt-1">
                          La ficha del cliente no tiene un implementador fijo. El proyecto quedará en estado &quot;Pendiente por Asignar&quot; para que el Coordinador lo asigne manualmente.
                        </p>
                      </>
                    )}
                  </div>
                  <div className="flex gap-3 justify-between pt-2 border-t">
                    <Button variant="outline" size="sm" onClick={() => setMultistorePhase('consolidated_data')} data-testid="confirm-implementer-back-btn">
                      Atrás
                    </Button>
                    <Button
                      className="bg-blue-600 hover:bg-blue-700 text-white"
                      size="sm"
                      onClick={handleConfirmImplementerAdvance}
                      disabled={confirmImplementerInfo?.loading}
                      data-testid="confirm-implementer-advance-btn"
                    >
                      Avanzar
                    </Button>
                  </div>
                </div>
              )}

              {/* Fase PYME: ¿Requiere Pinpads? */}
              {multistorePhase === 'pinpad_question' && (
                <div className="space-y-4 py-2" data-testid="pyme-pinpad-question-phase">
                  <p className="text-sm text-slate-600 font-medium">¿La implementación requiere Pinpads?</p>
                  <p className="text-xs text-slate-400">Seleccione cómo se proveerán los seriales de los equipos.</p>
                  <div className="space-y-2.5">
                    {/* Opción 1: Sí (carga inmediata desde inventario) */}
                    <button onClick={() => handlePymePinpadAnswer(true)}
                      className="w-full p-3.5 rounded-lg border-2 border-slate-200 hover:border-emerald-400 hover:bg-emerald-50 transition-all text-left"
                      data-testid="pinpad-yes-btn">
                      <p className="text-sm font-bold text-emerald-700">Sí</p>
                      <p className="text-[11px] text-slate-500 mt-0.5">Dispongo de los seriales: seleccionar modelo y vincular desde inventario.</p>
                    </button>

                    {/* Opción 2: Sí, pero los suministra un tercero */}
                    <button onClick={() => setSerialsByOther(v => !v)}
                      className={`w-full p-3.5 rounded-lg border-2 transition-all text-left ${serialsByOther ? 'border-blue-400 bg-blue-50' : 'border-slate-200 hover:border-blue-400 hover:bg-blue-50'}`}
                      data-testid="pinpad-yes-other-btn">
                      <p className="text-sm font-bold text-blue-700">Sí, pero no dispongo de la información de los seriales</p>
                      <p className="text-[11px] text-slate-500 mt-0.5">Serán suministrados por otro (Infraestructura, cliente o un banco).</p>
                    </button>

                    {/* Sub-opciones del tercero proveedor */}
                    {serialsByOther && (
                      <div className="ml-3 pl-3 border-l-2 border-blue-200 space-y-2 py-1" data-testid="serials-provider-suboptions">
                        <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">¿Quién suministrará los seriales?</p>
                        <button onClick={() => handleSerialsProvider('infra')}
                          className="w-full p-2.5 rounded-lg border-2 border-slate-200 hover:border-indigo-400 hover:bg-indigo-50 transition-all text-left text-sm font-medium text-slate-700"
                          data-testid="serials-provider-infra-btn">
                          Infraestructura Mega Soft
                        </button>
                        <button onClick={() => handleSerialsProvider('client')}
                          className="w-full p-2.5 rounded-lg border-2 border-slate-200 hover:border-indigo-400 hover:bg-indigo-50 transition-all text-left text-sm font-medium text-slate-700"
                          data-testid="serials-provider-client-btn">
                          El cliente
                        </button>
                        <button onClick={() => handleSerialsProvider('bank')}
                          className="w-full p-2.5 rounded-lg border-2 border-slate-200 hover:border-indigo-400 hover:bg-indigo-50 transition-all text-left text-sm font-medium text-slate-700"
                          data-testid="serials-provider-bank-btn">
                          Un Banco
                        </button>
                      </div>
                    )}

                    {/* Opción 3: No */}
                    <button onClick={() => handlePymePinpadAnswer(false)}
                      className="w-full p-3.5 rounded-lg border-2 border-slate-200 hover:border-slate-400 hover:bg-slate-50 transition-all text-left"
                      data-testid="pinpad-no-btn">
                      <p className="text-sm font-bold text-slate-700">No</p>
                      <p className="text-[11px] text-slate-500 mt-0.5">Continuar sin equipos.</p>
                    </button>
                  </div>
                  <div className="pt-2 border-t flex items-center justify-between">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        // VPOS Multi-RIF: pinpad_question es el PRIMER paso (se omitió el
                        // modal de Multitienda), por lo que "Atrás" cierra el wizard.
                        const _q = getMultistoreQuote && getMultistoreQuote();
                        if ((_q?.quote_type || '').toUpperCase() === 'VPOS_MULTIRIF') {
                          setMultistoreDialogOpen(false);
                          return;
                        }
                        // Si venimos desde multistore: volver a inherited/collect/ask; si no, cancelar
                        if (isMultistore) setMultistorePhase('collect');
                        else setMultistorePhase('ask');
                      }}
                      data-testid="pinpad-question-back-btn"
                    >
                      Atrás
                    </Button>
                    <span className="text-[11px] text-slate-400">Paso 1 de 3</span>
                  </div>
                </div>
              )}

              {/* Fase PYME: Selección de Modelo y Seriales de Pinpad */}
              {multistorePhase === 'pinpad_selection' && (
                <div className="space-y-3 py-2" data-testid="pyme-pinpad-selection-phase">
                  <p className="text-sm font-medium text-slate-700">Selección de Modelo y Seriales</p>

                  {/* Dropdown de modelo */}
                  <div>
                    <label className="text-xs font-semibold text-slate-600 mb-1 block">Modelo de POS / Pinpad</label>
                    <select value={pymePinpadSelectedModel} onChange={e => handlePymePinpadModelSelect(e.target.value)}
                      className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-300 focus:border-blue-400 outline-none bg-white"
                      data-testid="pinpad-model-select">
                      <option value="">Seleccionar modelo...</option>
                      {pymePinpadModels.map(m => (
                        <option key={m.hardware_id} value={m.hardware_id}>{m.name} ({m.type})</option>
                      ))}
                    </select>
                  </div>

                  {/* Loading */}
                  {pymePinpadLoading && (
                    <div className="text-center py-4 text-sm text-slate-400">Buscando seriales en inventario (últimos 15 días)...</div>
                  )}

                  {/* Lista de seriales */}
                  {!pymePinpadLoading && pymePinpadSelectedModel && pymePinpadSerials.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-emerald-700 mb-1">Seriales encontrados ({pymePinpadSerials.length})</p>
                      <div className="border rounded-lg overflow-hidden max-h-48 overflow-y-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="bg-emerald-50 border-b sticky top-0">
                              <th className="w-8 px-2 py-1.5">
                                <input type="checkbox" checked={pymePinpadSerials.every(s => pymePinpadSerialsSelected[s.serial])}
                                  onChange={e => { const sel = {}; pymePinpadSerials.forEach(s => { sel[s.serial] = e.target.checked; }); setPymePinpadSerialsSelected(sel); }}
                                  data-testid="pinpad-serial-select-all" />
                              </th>
                              <th className="text-left px-2 py-1.5 text-slate-600">Serial</th>
                              <th className="text-left px-2 py-1.5 text-slate-600">Modelo</th>
                              <th className="text-left px-2 py-1.5 text-slate-600">Fecha</th>
                            </tr>
                          </thead>
                          <tbody>
                            {pymePinpadSerials.map(s => (
                              <tr key={s.serial} className={`border-b last:border-0 ${s.from_preassign ? 'bg-indigo-50/40 hover:bg-indigo-50' : 'hover:bg-emerald-50/30'}`} data-testid={`pinpad-serial-row-${s.serial}`}>
                                <td className="px-2 py-1.5">
                                  <input type="checkbox" checked={!!pymePinpadSerialsSelected[s.serial]}
                                    onChange={e => setPymePinpadSerialsSelected(prev => ({...prev, [s.serial]: e.target.checked}))}
                                    data-testid={`pinpad-serial-${s.serial}`} />
                                </td>
                                <td className="px-2 py-1.5 font-mono text-slate-800">
                                  {s.serial}
                                  {s.from_preassign && (
                                    <span className="ml-2 text-[9px] font-semibold bg-indigo-600 text-white px-1.5 py-0.5 rounded uppercase tracking-wide" data-testid={`preassign-badge-${s.serial}`}>Preasignado</span>
                                  )}
                                </td>
                                <td className="px-2 py-1.5 text-slate-600">{s.modelo}</td>
                                <td className="px-2 py-1.5 text-slate-500">{s.date ? new Date(s.date).toLocaleDateString('es-VE') : '—'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Sin seriales */}
                  {!pymePinpadLoading && pymePinpadSelectedModel && pymePinpadSerials.length === 0 && (
                    <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-center">
                      <p className="text-sm text-amber-800 font-medium">No se encontraron seriales</p>
                      <p className="text-xs text-amber-600 mt-1">No hay salidas de inventario para este modelo al RIF del cliente en los últimos 15 días.</p>
                    </div>
                  )}

                  {/* Resumen de selección */}
                  {Object.values(pymePinpadSerialsSelected).filter(Boolean).length > 0 && (
                    <div className="bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
                      <p className="text-xs text-emerald-700 font-medium">{Object.values(pymePinpadSerialsSelected).filter(Boolean).length} serial(es) seleccionado(s)</p>
                    </div>
                  )}

                  <div className="flex gap-3 justify-between pt-2 border-t">
                    <Button variant="outline" size="sm" onClick={() => setMultistorePhase('pinpad_question')} data-testid="pinpad-selection-back-btn">
                      Atrás
                    </Button>
                    <Button className="bg-blue-600 hover:bg-blue-700 text-white" size="sm" onClick={handlePymePinpadConfirm} data-testid="pinpad-confirm-btn">
                      Continuar
                    </Button>
                  </div>
                </div>
              )}

              {/* Fase Equipment ELIMINADA (Feb 2026):
                  El modal "Equipos Entregados al Cliente" fue removido para
                  agilizar el flujo. La selección automática de equipos
                  vinculados a la cotización se hace en backend al recibir
                  send-to-implementation. */}

              {/* Fase Impresora Fiscal: solicita o muestra el modelo registrado.
                  Posicionado después del paso de Pinpads y antes del modal
                  consolidado, para que el dato esté disponible en la Ficha
                  Técnica de la Implementación. */}
              {multistorePhase === 'fiscal_printer' && (
                <div className="space-y-4 py-2" data-testid="fiscal-printer-phase">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-slate-700">Impresora Fiscal del Cliente</p>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-50 text-amber-700">
                      Ficha Técnica
                    </span>
                  </div>
                  <div className="bg-white border border-slate-200 rounded-lg p-3">
                    {fiscalPrinterFromClient ? (
                      <p className="text-[11px] text-emerald-700 mb-2" data-testid="fiscal-printer-prefilled-hint">
                        ✓ Precargado desde la ficha del cliente. Puedes editarlo si requiere corrección.
                      </p>
                    ) : (
                      <p className="text-xs text-amber-800 mb-2">
                        La ficha del cliente no tiene registrado el modelo de impresora fiscal.
                        <b> Indique el modelo</b> para imprimirlo en la Ficha Técnica.
                      </p>
                    )}
                    <Input
                      value={fiscalPrinterModel}
                      onChange={(e) => setFiscalPrinterModel(e.target.value)}
                      placeholder="Ej: BIXOLON SRP-330, EPSON TM-T20III"
                      className="bg-white"
                      data-testid="fiscal-printer-input" />
                  </div>
                  <div className="flex gap-3 justify-between pt-2 border-t">
                    <Button variant="outline" size="sm" onClick={() => setMultistoreDialogOpen(false)} data-testid="fiscal-printer-cancel-btn">
                      Cancelar
                    </Button>
                    <Button
                      className="bg-blue-600 hover:bg-blue-700 text-white"
                      size="sm"
                      onClick={handleFiscalPrinterContinue}
                      disabled={!fiscalPrinterModel.trim()}
                      data-testid="fiscal-printer-continue-btn">
                      Continuar
                    </Button>
                  </div>
                </div>
              )}
                {/* Bloque de selección de equipos removido (Feb 2026) */}

              {/* Fase 1: Pregunta Multitienda (solo si NO hay distribución previa) */}
              {multistorePhase === 'ask' && (
                <div className="space-y-4 py-2" data-testid="multistore-ask-phase">
                  <p className="text-sm text-slate-600">¿Esta implementación es <strong>Multitienda</strong>?</p>
                  <p className="text-xs text-slate-400">Si el proyecto incluye múltiples sucursales o tiendas, seleccione &quot;Sí&quot; para registrar los datos de cada una.</p>
                  <div className="flex gap-3 justify-end pt-2">
                    <Button variant="outline" onClick={() => handleMultistoreAnswer(false)} data-testid="multistore-no-btn">
                      No, tienda única
                    </Button>
                    <Button className="bg-blue-600 hover:bg-blue-700 text-white" onClick={() => handleMultistoreAnswer(true)} data-testid="multistore-yes-btn">
                      <Store size={14} className="mr-1.5" />
                      Sí, Multitienda
                    </Button>
                  </div>
                </div>
              )}

              {/* Fase Herencia: Distribución pre-definida detectada — VISTA DE VALIDACIÓN EDITABLE.
                  FIX Iter37 (feb 2026): la grilla ahora permite editar/agregar/eliminar tiendas
                  directamente; el botón único "Conformar Distribución" cierra la fase. */}
              {multistorePhase === 'inherited' && (
                <div className="flex flex-col min-h-0 flex-1 py-2 gap-3" data-testid="multistore-inherited-phase">
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 shrink-0">
                    <div className="flex items-center gap-2 mb-1">
                      <CheckCircle size={16} className="text-blue-600" />
                      <span className="text-sm font-medium text-blue-800">Distribución de sucursales detectada</span>
                    </div>
                    <p className="text-xs text-blue-600">
                      Se encontró una distribución previa. Revisa los datos y modifícalos si lo necesitas antes de conformar.
                    </p>
                  </div>

                  <MultistoreExcelBar
                    onLoaded={(stores) => setMultistoreStores(stores)}
                  />

                  {/* Grilla EDITABLE de sucursales heredadas — con scroll interno */}
                  <div className="border rounded-lg overflow-y-auto flex-1 min-h-0" data-testid="inherited-stores-scroll">
                    <table className="w-full text-sm">
                      <thead className="sticky top-0 z-10">
                        <tr className="bg-slate-100 border-b">
                          <th className="text-left px-3 py-2 text-xs font-semibold text-slate-600 w-10">#</th>
                          <th className="text-left px-3 py-2 text-xs font-semibold text-slate-600">Sucursal</th>
                          <th className="text-center px-3 py-2 text-xs font-semibold text-slate-600 w-28">Cajas</th>
                          <th className="text-center px-3 py-2 text-xs font-semibold text-slate-600 w-10"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {multistoreStores.map((store, idx) => (
                          <MultistoreRow
                            key={idx}
                            store={store}
                            idx={idx}
                            onCommit={commitStore}
                            onRemove={removeStore}
                          />
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Footer fijo: agregar sucursal + contador reactivo + acción */}
                  <div className="shrink-0 space-y-2 pt-2 border-t">
                    <div className="flex items-center justify-between">
                      <Button
                        type="button" variant="outline" size="sm"
                        onClick={() => setMultistoreStores([...multistoreStores, { name: '', box_count: 1 }])}
                        className="text-xs"
                        data-testid="inherited-add-row-btn"
                      >
                        + Agregar Sucursal
                      </Button>
                      <p className="text-xs text-slate-500">
                        {multistoreStores.length} sucursal(es)
                      </p>
                    </div>

                    {(() => {
                      const sum = multistoreStores.reduce((s, st) => s + (parseInt(st.box_count) || 0), 0);
                      const initial = getMultistoreTotalCajas();
                      const balanced = sum === initial;
                      const structInvalid = multistoreStores.length === 0 || multistoreStores.some(s => !s.name?.trim() || !s.box_count);
                      return (
                        <>
                          <div
                            className={`flex items-center justify-between rounded-md px-3 py-2 text-sm font-bold border ${balanced ? 'bg-emerald-50 text-emerald-700 border-emerald-300' : 'bg-red-50 text-red-700 border-red-300'}`}
                            data-testid="inherited-balance-counter"
                            data-balanced={balanced ? 'true' : 'false'}
                          >
                            <span>Cajas Distribuidas: {sum} / Cantidad Inicial Obligatoria: {initial}</span>
                            {balanced ? <CheckCircle size={16} className="shrink-0" /> : <AlertTriangle size={16} className="shrink-0" />}
                          </div>
                          <div className="flex gap-3 justify-end">
                            <Button
                              className="bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-50"
                              onClick={confirmInheritedStores}
                              disabled={structInvalid}
                              data-testid="inherited-confirm-btn"
                            >
                              <CheckCircle size={14} className="mr-1.5" />
                              Conformar Distribución
                            </Button>
                          </div>
                        </>
                      );
                    })()}
                  </div>
                </div>
              )}

              {/* Fase 2: Recolectar tiendas */}
              {multistorePhase === 'collect' && (
                <div className="flex flex-col min-h-0 flex-1 py-2 gap-3" data-testid="multistore-collect-phase">
                  {(() => {
                    const totalCajas = getMultistoreTotalCajas();
                    const remaining = totalCajas - multistoreAssignedBoxes;
                    const balanced = multistoreAssignedBoxes === totalCajas;
                    return (
                      <>
                        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 shrink-0">
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-medium text-blue-800">Total de cajas en cotización:</span>
                            <span className="text-lg font-bold text-blue-900">{totalCajas}</span>
                          </div>
                          {remaining > 0 && (
                            <div className="mt-1 text-xs text-blue-600">Faltan {remaining} caja(s) por asignar</div>
                          )}
                        </div>

                          <MultistoreExcelBar
                            onLoaded={(stores) => setMultistoreStores(stores)}
                          />

                        {/* Lista de tiendas registradas — con scroll interno */}
                        <div className="flex-1 min-h-0 overflow-y-auto" data-testid="collect-stores-scroll">
                          {multistoreStores.length > 0 && (
                            <div className="border rounded-lg overflow-hidden">
                              <table className="w-full text-sm">
                                <thead className="sticky top-0 z-10">
                                  <tr className="bg-slate-100 border-b">
                                    <th className="text-left px-3 py-2 text-xs font-semibold text-slate-600">#</th>
                                    <th className="text-left px-3 py-2 text-xs font-semibold text-slate-600">Tienda</th>
                                    <th className="text-center px-3 py-2 text-xs font-semibold text-slate-600">Cajas</th>
                                    <th className="text-center px-3 py-2 text-xs font-semibold text-slate-600 w-10"></th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {multistoreStores.map((store, idx) => (
                                    <tr key={idx} className="border-b last:border-0 hover:bg-slate-50" data-testid={`multistore-row-${idx}`}>
                                      <td className="px-3 py-2 text-slate-500">{idx + 1}</td>
                                      <td className="px-3 py-2 font-medium text-slate-800">{store.name}</td>
                                      <td className="px-3 py-2 text-center text-slate-700">{store.box_count}</td>
                                      <td className="px-3 py-2 text-center">
                                        <button onClick={() => removeMultistoreStore(idx)} className="text-red-400 hover:text-red-600 transition-colors" data-testid={`multistore-remove-${idx}`}>
                                          <Trash2 size={14} />
                                        </button>
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}
                        </div>

                        {/* Footer fijo: agregar tienda + contador reactivo + acciones */}
                        <div className="shrink-0 space-y-2 pt-2 border-t">
                          {remaining > 0 && (
                            <MultistoreAddForm remaining={remaining} onAppend={appendStore} />
                          )}

                          <div
                            className={`flex items-center justify-between rounded-md px-3 py-2 text-sm font-bold border ${balanced ? 'bg-emerald-50 text-emerald-700 border-emerald-300' : 'bg-red-50 text-red-700 border-red-300'}`}
                            data-testid="collect-balance-counter"
                            data-balanced={balanced ? 'true' : 'false'}
                          >
                            <span>Cajas Distribuidas: {multistoreAssignedBoxes} / Cantidad Inicial Obligatoria: {totalCajas}</span>
                            {balanced ? <CheckCircle size={16} className="shrink-0" /> : <AlertTriangle size={16} className="shrink-0" />}
                          </div>

                          <div className="flex justify-between items-center">
                            <Button variant="ghost" size="sm" onClick={() => {
                              const quote = getMultistoreQuote();
                              const hasPrior = (quote?.branch_details || []).filter(b => b.store_name && b.quantity > 0).length > 0;
                              if (hasPrior) {
                                setMultistoreStores(quote.branch_details.filter(b => b.store_name && b.quantity > 0).map(b => ({ name: b.store_name, box_count: parseInt(b.quantity) || 0 })));
                                setMultistorePhase('inherited');
                              } else {
                                setMultistorePhase('ask');
                                setMultistoreStores([]);
                              }
                            }} data-testid="multistore-back-btn">
                              Volver
                            </Button>
                            <Button
                              className="bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50"
                              disabled={multistoreStores.length === 0}
                              onClick={confirmMultistore}
                              data-testid="multistore-confirm-btn"
                            >
                              <Send size={14} className="mr-1.5" />
                              Confirmar y Enviar ({multistoreStores.length} tienda{multistoreStores.length !== 1 ? 's' : ''})
                            </Button>
                          </div>
                        </div>
                      </>
                    );
                  })()}
                </div>
              )}
            </DialogContent>
          </Dialog>

          {/* Sub-modal jerárquico: Banco proveedor de seriales (Procesador → Banco) */}
          <Dialog open={serialsBankModal.open} onOpenChange={(o) => !o && setSerialsBankModal({ open: false, processor: null })}>
            <DialogContent className="max-w-md" data-testid="serials-bank-modal">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <Landmark size={18} className="text-indigo-600" />
                  {serialsBankModal.processor ? 'Banco vinculado al Procesador' : 'Banco proveedor de seriales'}
                </DialogTitle>
                <DialogDescription>
                  {serialsBankModal.processor
                    ? 'Seleccione el banco final vinculado al procesador para registrar quién suministrará los seriales.'
                    : 'Seleccione el banco o procesador que suministrará los seriales de los equipos.'}
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-3">
                {!serialsBankModal.processor ? (
                  <>
                    <p className="text-sm text-slate-600">
                      Seleccione el banco o procesador que suministrará los seriales de los equipos.
                    </p>
                    <div className="space-y-1.5 max-h-[340px] overflow-y-auto" data-testid="serials-bank-list">
                      {(banks || []).map((b) => (
                        <button
                          key={b.bank_id}
                          type="button"
                          onClick={() => handleSerialsBankSelect(b)}
                          className="w-full text-left px-3 py-2.5 rounded-lg border-2 border-slate-200 hover:border-indigo-400 hover:bg-indigo-50/60 transition-all text-sm font-medium text-slate-700 flex items-center justify-between"
                          data-testid={`serials-bank-${b.bank_id}`}
                        >
                          <span>{b.name}</span>
                          <span className="text-[10px] text-slate-400">{b.type}</span>
                        </button>
                      ))}
                    </div>
                  </>
                ) : (
                  <>
                    <p className="text-sm text-slate-600">
                      <strong>{serialsBankModal.processor.name}</strong> es un <strong>Procesador</strong>.
                      Seleccione el banco final que operará la transacción.
                    </p>
                    {(() => {
                      const linked = (banks || []).filter((b) => b.type !== 'Procesador' && b.procesador === serialsBankModal.processor.name);
                      if (linked.length === 0) {
                        return (
                          <div className="text-center py-6 text-sm text-amber-700 bg-amber-50 rounded-lg" data-testid="serials-bank-linked-empty">
                            No hay bancos asociados a este procesador. Vincúlelos desde la ficha del banco
                            (campo &quot;Procesador&quot;) en el maestro de Bancos.
                          </div>
                        );
                      }
                      return (
                        <div className="space-y-1.5 max-h-[320px] overflow-y-auto" data-testid="serials-bank-linked-list">
                          {linked.map((b) => (
                            <button
                              key={b.bank_id}
                              type="button"
                              onClick={() => handleSerialsLinkedBankSelect(serialsBankModal.processor, b)}
                              className="w-full text-left px-3 py-2.5 rounded-lg border-2 border-slate-200 hover:border-indigo-400 hover:bg-indigo-50/60 transition-all text-sm font-medium text-slate-700 flex items-center justify-between"
                              data-testid={`serials-bank-linked-${b.bank_id}`}
                            >
                              <span>{b.name}</span>
                              <span className="text-[10px] text-slate-400">{b.type}</span>
                            </button>
                          ))}
                        </div>
                      );
                    })()}
                  </>
                )}
                <div className="flex justify-between pt-1">
                  {serialsBankModal.processor ? (
                    <Button variant="outline" size="sm" onClick={() => setSerialsBankModal({ open: true, processor: null })} data-testid="serials-bank-back-btn">
                      Atrás
                    </Button>
                  ) : <span />}
                  <Button variant="outline" size="sm" onClick={() => setSerialsBankModal({ open: false, processor: null })} data-testid="serials-bank-cancel-btn">
                    Cancelar
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
    </>
  );
};

// ========================================================================
// EmailManualAttachments — Adjuntos manuales para el modal de Personalizar
// Comunicación. Sube cada archivo al endpoint `/quotes/manual-attachments/
// upload`, almacena los IDs en `ctx.emailManualAttachmentIds` y muestra una
// lista con tamaño total + botón de quitar. Límite total: 10 MB.
// ========================================================================
const MAX_TOTAL_BYTES = 10 * 1024 * 1024;
const fmtBytes = (b) => {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(2)} MB`;
};

function EmailManualAttachments({ ctx }) {
  const { emailManualAttachments = [], setEmailManualAttachments } = ctx;
  const fileRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const totalBytes = emailManualAttachments.reduce((s, a) => s + (a.size || 0), 0);

  const handleSelectFiles = async (e) => {
    const files = Array.from(e.target.files || []);
    e.target.value = '';
    if (!files.length) return;
    // Validar peso total ANTES de subir
    const newTotal = totalBytes + files.reduce((s, f) => s + f.size, 0);
    if (newTotal > MAX_TOTAL_BYTES) {
      toast.error(`El peso total excede 10 MB. Total previsto: ${fmtBytes(newTotal)}`);
      return;
    }
    setUploading(true);
    try {
      const uploaded = [];
      for (const f of files) {
        const fd = new FormData();
        fd.append('file', f);
        try {
          const { data } = await api.post('/quotes/manual-attachments/upload', fd, {
            headers: { 'Content-Type': 'multipart/form-data' },
          });
          uploaded.push(data);
        } catch (err) {
          toast.error(`Error subiendo ${f.name}: ${err?.response?.data?.detail || err.message}`);
        }
      }
      if (uploaded.length) {
        setEmailManualAttachments([...(emailManualAttachments || []), ...uploaded]);
        toast.success(`${uploaded.length} archivo(s) cargado(s)`);
      }
    } finally {
      setUploading(false);
    }
  };

  const removeAttachment = (id) => {
    setEmailManualAttachments(emailManualAttachments.filter((a) => a.attachment_id !== id));
  };

  return (
    <div data-testid="email-manual-attachments">
      <Label className="text-sm font-medium">
        Adjuntos manuales{' '}
        <span className="text-xs text-slate-400">(PDF, imágenes, Excel — máx 10 MB total)</span>
      </Label>
      <div className="flex items-center gap-2 mt-1">
        <input
          ref={fileRef}
          type="file"
          multiple
          accept=".pdf,.png,.jpg,.jpeg,.gif,.webp,.txt,.csv,.xlsx,.xls,.docx,.doc"
          className="hidden"
          onChange={handleSelectFiles}
          data-testid="email-attachment-input"
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => fileRef.current?.click()}
          disabled={uploading || totalBytes >= MAX_TOTAL_BYTES}
          className="h-8 text-xs border-blue-300 text-blue-600"
          data-testid="email-attachment-add-btn"
        >
          <Paperclip size={13} className="mr-1.5" />
          {uploading ? 'Subiendo...' : 'Añadir archivo'}
        </Button>
        <span className="text-[11px] text-slate-500" data-testid="email-attachment-total">
          {emailManualAttachments.length} archivo(s) · {fmtBytes(totalBytes)} / 10 MB
        </span>
      </div>
      {emailManualAttachments.length > 0 && (
        <div className="mt-2 space-y-1.5">
          {emailManualAttachments.map((a) => (
            <div
              key={a.attachment_id}
              className="flex items-center justify-between text-xs bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5"
              data-testid={`email-attachment-item-${a.attachment_id}`}
            >
              <div className="flex items-center gap-2 min-w-0">
                <Paperclip size={12} className="text-slate-400 shrink-0" />
                <span className="truncate text-slate-700">{a.filename}</span>
                <span className="text-slate-400 shrink-0">({fmtBytes(a.size || 0)})</span>
              </div>
              <button
                type="button"
                onClick={() => removeAttachment(a.attachment_id)}
                className="text-slate-400 hover:text-red-500 shrink-0 ml-2"
                title="Quitar"
              >
                <X size={13} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
