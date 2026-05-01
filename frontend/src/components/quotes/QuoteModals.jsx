/**
 * QuoteModals — Todos los modales secundarios de la vista de Cotizaciones.
 * Extraído de Quotes.jsx para reducir el tamaño del archivo principal.
 * Recibe un objeto `ctx` con todas las variables y funciones necesarias del padre.
 */
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../ui/alert-dialog';
import { Label } from '../ui/label';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';
import { Button } from '../ui/button';
import { AlertTriangle, CheckCircle, Mail, Plus, Send, Store, Trash2, X } from 'lucide-react';
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

export const QuoteModals = ({ ctx }) => {
  const {
    // PDF Preview
    pdfPreviewOpen, setPdfPreviewOpen, pdfPreviewUrl, setPdfPreviewUrl, pdfPreviewLoading,
    // Equipment Wizard
    equipmentWizardOpen, setEquipmentWizardOpen, equipmentWizardMode, setEquipmentWizardMode,
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
    // Bitacora
    bitacoraFlujoOpen, setBitacoraFlujoOpen, bitacoraFlujoQuoteNumber,
    bitacoraFlujoEntries, bitacoraFlujoLoading,
    // Delivery
    deliveryDialogOpen, setDeliveryDialogOpen, deliveryQuoteId, deliveryExceptionInfo,
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
    // Equipment phase
    projectTypeImpl, equipmentList, equipmentAvailable, equipmentLoading,
    equipmentSelected, setEquipmentSelected,
  } = ctx;

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
            userSede={currentUser?.sede || 'PYME'}
          />

          {/* Modal de confirmación para Eliminar */}
          <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>¿Eliminar Cotización?</AlertDialogTitle>
                <AlertDialogDescription>
                  ¿Está seguro de que desea eliminar la Cotización <strong>"{deleteQuoteData.number}"</strong> de forma permanente?
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

          {/* Modal de Personalización de Envío */}
          <Dialog open={emailModalOpen} onOpenChange={(open) => { if (!open) { setEmailModalOpen(false); setPendingAction(null); } }}>
            <DialogContent className="max-w-md" data-testid="email-modal">
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
                  <Label className="text-sm font-medium">Mensaje personalizado <span className="text-xs text-slate-400">(opcional, máx 200 caracteres)</span></Label>
                  <Textarea
                    key={emailModalOpen ? 'modal-open' : 'modal-closed'}
                    defaultValue={emailCustomMessage}
                    onBlur={e => setEmailCustomMessage(e.target.value.slice(0, 200))}
                    placeholder="Ej: Estimado cliente, adjuntamos la documentación solicitada..."
                    className="mt-1 min-h-[70px] text-sm"
                    maxLength={200}
                    data-testid="email-custom-message" />
                </div>
                <div>
                  <Label className="text-sm font-medium">Destinatarios adicionales (CC)</Label>
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
                              El usuario <strong className="text-slate-900">{entry.user_name}</strong> ejecutó <strong>{ACTION_LABELS[entry.action]}</strong> sin haber completado el paso <strong>"{entry.expected_status}"</strong>.
                              <span className="text-slate-500"> Estado en el momento: "{entry.actual_status}".</span>
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
            <DialogContent className="max-w-lg" data-testid="multistore-dialog">
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
                    <div>
                      <Label className="text-sm font-medium">Instrucciones adicionales para el Implementador</Label>
                      <p className="text-[11px] text-slate-500 mt-0.5 mb-1.5">Máximo 500 caracteres de texto visible. Use negrita, cursiva, listas u otros formatos para destacar puntos clave.</p>
                      <RichTextEditor
                        value={implInstructions}
                        onChange={(html, len) => { setImplInstructions(html); setImplInstructionsLen(len); }}
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
                          La ficha del cliente no tiene un implementador fijo. El proyecto quedará en estado "Pendiente por Asignar" para que el Coordinador lo asigne manualmente.
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
                  <p className="text-xs text-slate-400">Si requiere dispositivos POS o Pinpad, seleccione "Sí" para vincular los seriales desde el inventario.</p>
                  <div className="grid grid-cols-2 gap-3">
                    <button onClick={() => handlePymePinpadAnswer(true)}
                      className="p-4 rounded-lg border-2 border-slate-200 hover:border-emerald-400 hover:bg-emerald-50 transition-all text-center"
                      data-testid="pinpad-yes-btn">
                      <p className="text-sm font-bold text-emerald-700">Sí</p>
                      <p className="text-[11px] text-slate-500 mt-0.5">Seleccionar modelo y seriales</p>
                    </button>
                    <button onClick={() => handlePymePinpadAnswer(false)}
                      className="p-4 rounded-lg border-2 border-slate-200 hover:border-slate-400 hover:bg-slate-50 transition-all text-center"
                      data-testid="pinpad-no-btn">
                      <p className="text-sm font-bold text-slate-700">No</p>
                      <p className="text-[11px] text-slate-500 mt-0.5">Continuar sin equipos</p>
                    </button>
                  </div>
                  <div className="pt-2 border-t flex items-center justify-between">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
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
                              <tr key={s.serial} className="border-b last:border-0 hover:bg-emerald-50/30">
                                <td className="px-2 py-1.5">
                                  <input type="checkbox" checked={!!pymePinpadSerialsSelected[s.serial]}
                                    onChange={e => setPymePinpadSerialsSelected(prev => ({...prev, [s.serial]: e.target.checked}))}
                                    data-testid={`pinpad-serial-${s.serial}`} />
                                </td>
                                <td className="px-2 py-1.5 font-mono text-slate-800">{s.serial}</td>
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

              {/* Fase Equipment: Selección de equipos */}
              {multistorePhase === 'equipment' && (
                <div className="space-y-3 py-2" data-testid="equipment-phase">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-slate-700">
                      {projectTypeImpl === 'pos_fast_track' ? 'Equipos de la Cotización' : 'Equipos Entregados al Cliente'}
                    </p>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-500">
                      {projectTypeImpl === 'pos_fast_track' ? 'MPOS (Imple + POS)' : 'VPOS / MPOS'}
                    </span>
                  </div>

                  {equipmentLoading ? (
                    <div className="text-center py-8 text-sm text-slate-400">Buscando equipos...</div>
                  ) : (
                    <>
                      {/* Equipos de la cotización */}
                      {equipmentAvailable.quote_equipment?.length > 0 && (
                        <div>
                          <p className="text-xs font-semibold text-blue-700 mb-1">Vinculados a esta cotización</p>
                          <div className="border rounded-lg overflow-hidden">
                            <table className="w-full text-xs">
                              <thead>
                                <tr className="bg-blue-50 border-b">
                                  <th className="w-8 px-2 py-1.5"><input type="checkbox" checked={equipmentAvailable.quote_equipment.every(eq => equipmentSelected[eq.equipo_id])} onChange={e => { const s = {...equipmentSelected}; equipmentAvailable.quote_equipment.forEach(eq => { s[eq.equipo_id] = e.target.checked; }); setEquipmentSelected(s); }} /></th>
                                  <th className="text-left px-2 py-1.5 text-slate-600">Modelo</th>
                                  <th className="text-left px-2 py-1.5 text-slate-600">Serial</th>
                                </tr>
                              </thead>
                              <tbody>
                                {equipmentAvailable.quote_equipment.map(eq => (
                                  <tr key={eq.equipo_id} className="border-b last:border-0 hover:bg-blue-50/30">
                                    <td className="px-2 py-1.5"><input type="checkbox" checked={!!equipmentSelected[eq.equipo_id]} onChange={e => setEquipmentSelected(s => ({...s, [eq.equipo_id]: e.target.checked}))} /></td>
                                    <td className="px-2 py-1.5 font-medium text-slate-800">{eq.modelo}</td>
                                    <td className="px-2 py-1.5 font-mono text-slate-600">{eq.serial}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}

                      {/* Equipos del cliente (por RIF) — solo para VPOS/MPOS */}
                      {projectTypeImpl === 'vpos_mpos' && equipmentAvailable.rif_equipment?.length > 0 && (
                        <div>
                          <p className="text-xs font-semibold text-violet-700 mb-1">Otros equipos del cliente (RIF: {equipmentAvailable.client_rif})</p>
                          <div className="border rounded-lg overflow-hidden">
                            <table className="w-full text-xs">
                              <thead>
                                <tr className="bg-violet-50 border-b">
                                  <th className="w-8 px-2 py-1.5"><input type="checkbox" checked={equipmentAvailable.rif_equipment.every(eq => equipmentSelected[eq.equipo_id])} onChange={e => { const s = {...equipmentSelected}; equipmentAvailable.rif_equipment.forEach(eq => { s[eq.equipo_id] = e.target.checked; }); setEquipmentSelected(s); }} /></th>
                                  <th className="text-left px-2 py-1.5 text-slate-600">Modelo</th>
                                  <th className="text-left px-2 py-1.5 text-slate-600">Serial</th>
                                  <th className="text-left px-2 py-1.5 text-slate-600">Cotización</th>
                                </tr>
                              </thead>
                              <tbody>
                                {equipmentAvailable.rif_equipment.map(eq => (
                                  <tr key={eq.equipo_id} className="border-b last:border-0 hover:bg-violet-50/30">
                                    <td className="px-2 py-1.5"><input type="checkbox" checked={!!equipmentSelected[eq.equipo_id]} onChange={e => setEquipmentSelected(s => ({...s, [eq.equipo_id]: e.target.checked}))} /></td>
                                    <td className="px-2 py-1.5 font-medium text-slate-800">{eq.modelo}</td>
                                    <td className="px-2 py-1.5 font-mono text-slate-600">{eq.serial}</td>
                                    <td className="px-2 py-1.5 text-slate-500">{eq.quote_number || '—'}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}

                      {/* Sin equipos encontrados */}
                      {(equipmentAvailable.quote_equipment?.length === 0 && equipmentAvailable.rif_equipment?.length === 0) && (
                        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-center">
                          <p className="text-sm text-amber-800 font-medium">No se encontraron equipos entregados</p>
                          <p className="text-xs text-amber-600 mt-1">Puede continuar sin vincular equipos o verificar las Notas de Entrega.</p>
                        </div>
                      )}

                      {/* Resumen de selección */}
                      {Object.values(equipmentSelected).filter(Boolean).length > 0 && (
                        <div className="bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
                          <p className="text-xs text-emerald-700 font-medium">{Object.values(equipmentSelected).filter(Boolean).length} equipo(s) seleccionado(s)</p>
                        </div>
                      )}

                      <div className="flex gap-3 justify-between pt-2 border-t">
                        <Button variant="outline" size="sm" onClick={() => setMultistoreDialogOpen(false)} data-testid="equipment-back-btn">
                          Cancelar
                        </Button>
                        <Button className="bg-blue-600 hover:bg-blue-700 text-white" size="sm" onClick={advanceToMultistorePhase} data-testid="equipment-continue-btn">
                          Continuar
                        </Button>
                      </div>
                    </>
                  )}
                </div>
              )}

              {/* Fase 1: Pregunta Multitienda (solo si NO hay distribución previa) */}
              {multistorePhase === 'ask' && (
                <div className="space-y-4 py-2" data-testid="multistore-ask-phase">
                  <p className="text-sm text-slate-600">¿Esta implementación es <strong>Multitienda</strong>?</p>
                  <p className="text-xs text-slate-400">Si el proyecto incluye múltiples sucursales o tiendas, seleccione "Sí" para registrar los datos de cada una.</p>
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

              {/* Fase Herencia: Distribución pre-definida detectada */}
              {multistorePhase === 'inherited' && (
                <div className="space-y-4 py-2" data-testid="multistore-inherited-phase">
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                    <div className="flex items-center gap-2 mb-2">
                      <CheckCircle size={16} className="text-blue-600" />
                      <span className="text-sm font-medium text-blue-800">Distribución de sucursales detectada</span>
                    </div>
                    <p className="text-xs text-blue-600">
                      Se encontró una distribución previa de sucursales en esta cotización. ¿Desea utilizar esta misma configuración para el proyecto?
                    </p>
                  </div>

                  {/* Tabla resumen de sucursales heredadas */}
                  <div className="border rounded-lg overflow-hidden">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-slate-50 border-b">
                          <th className="text-left px-3 py-2 text-xs font-semibold text-slate-600">#</th>
                          <th className="text-left px-3 py-2 text-xs font-semibold text-slate-600">Sucursal</th>
                          <th className="text-center px-3 py-2 text-xs font-semibold text-slate-600">Cajas</th>
                        </tr>
                      </thead>
                      <tbody>
                        {multistoreStores.map((store, idx) => (
                          <tr key={idx} className="border-b last:border-0" data-testid={`inherited-row-${idx}`}>
                            <td className="px-3 py-2 text-slate-500">{idx + 1}</td>
                            <td className="px-3 py-2 font-medium text-slate-800">{store.name}</td>
                            <td className="px-3 py-2 text-center text-slate-700">{store.box_count}</td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr className="bg-slate-50 border-t">
                          <td colSpan={2} className="px-3 py-2 text-right text-xs font-semibold text-slate-600">Total:</td>
                          <td className="px-3 py-2 text-center font-bold text-slate-900">
                            {multistoreStores.reduce((sum, s) => sum + (s.box_count || 0), 0)}
                          </td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>

                  <div className="flex gap-3 justify-end pt-2 border-t">
                    <Button variant="outline" onClick={modifyInheritedStores} data-testid="inherited-modify-btn">
                      No, Modificar
                    </Button>
                    <Button className="bg-emerald-600 hover:bg-emerald-700 text-white" onClick={confirmInheritedStores} data-testid="inherited-confirm-btn">
                      <CheckCircle size={14} className="mr-1.5" />
                      Sí, Confirmar y Enviar
                    </Button>
                  </div>
                </div>
              )}

              {/* Fase 2: Recolectar tiendas */}
              {multistorePhase === 'collect' && (
                <div className="space-y-4 py-2" data-testid="multistore-collect-phase">
                  {(() => {
                    const totalCajas = getMultistoreTotalCajas();
                    const remaining = totalCajas - multistoreAssignedBoxes;
                    return (
                      <>
                        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-medium text-blue-800">Total de cajas en cotización:</span>
                            <span className="text-lg font-bold text-blue-900">{totalCajas}</span>
                          </div>
                          <div className="flex items-center justify-between mt-1">
                            <span className="text-sm text-blue-700">Cajas asignadas:</span>
                            <span className={`text-sm font-semibold ${multistoreAssignedBoxes === totalCajas ? 'text-emerald-600' : 'text-blue-700'}`}>{multistoreAssignedBoxes} / {totalCajas}</span>
                          </div>
                          {remaining > 0 && (
                            <div className="mt-1 text-xs text-blue-600">Faltan {remaining} caja(s) por asignar</div>
                          )}
                          {remaining === 0 && (
                            <div className="mt-1 text-xs text-emerald-600 font-medium">Todas las cajas han sido asignadas</div>
                          )}
                        </div>

                        {/* Lista de tiendas registradas */}
                        {multistoreStores.length > 0 && (
                          <div className="border rounded-lg overflow-hidden">
                            <table className="w-full text-sm">
                              <thead>
                                <tr className="bg-slate-50 border-b">
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

                        {/* Formulario para agregar tienda */}
                        {remaining > 0 && (
                          <div className="flex items-end gap-2">
                            <div className="flex-1">
                              <Label className="text-xs text-slate-500">Nombre de tienda</Label>
                              <Input
                                placeholder="Ej: Tienda Centro, Sucursal Norte..."
                                value={multistoreNewStore.name}
                                onChange={(e) => setMultistoreNewStore({ ...multistoreNewStore, name: e.target.value })}
                                data-testid="multistore-store-name"
                                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addMultistoreStore(); } }}
                              />
                            </div>
                            <div className="w-24">
                              <Label className="text-xs text-slate-500">Cajas</Label>
                              <Input
                                type="number"
                                min="1"
                                max={remaining}
                                placeholder="Cant."
                                value={multistoreNewStore.box_count}
                                onChange={(e) => setMultistoreNewStore({ ...multistoreNewStore, box_count: e.target.value })}
                                data-testid="multistore-store-boxes"
                                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addMultistoreStore(); } }}
                              />
                            </div>
                            <Button variant="outline" size="sm" onClick={addMultistoreStore} data-testid="multistore-add-store-btn" className="shrink-0">
                              <Plus size={14} className="mr-1" /> Agregar
                            </Button>
                          </div>
                        )}

                        {/* Botones de acción */}
                        <div className="flex justify-between items-center pt-3 border-t">
                          <Button variant="ghost" size="sm" onClick={() => {
                            // Si venimos de herencia, volver a inherited; si no, volver a ask
                            const quote = getMultistoreQuote();
                            const hasPrior = (quote?.branch_details || []).filter(b => b.store_name && b.quantity > 0).length > 0;
                            if (hasPrior) {
                              // Restaurar datos heredados y volver a fase inherited
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
                            className="bg-blue-600 hover:bg-blue-700 text-white"
                            disabled={multistoreAssignedBoxes !== totalCajas || multistoreStores.length === 0}
                            onClick={confirmMultistore}
                            data-testid="multistore-confirm-btn"
                          >
                            <Send size={14} className="mr-1.5" />
                            Confirmar y Enviar ({multistoreStores.length} tienda{multistoreStores.length !== 1 ? 's' : ''})
                          </Button>
                        </div>
                      </>
                    );
                  })()}
                </div>
              )}
            </DialogContent>
          </Dialog>
    </>
  );
};
