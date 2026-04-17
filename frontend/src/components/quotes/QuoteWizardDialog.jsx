/**
 * QuoteWizardDialog — Wizard completo de creación/edición de cotizaciones.
 * Extraído de Quotes.jsx para reducir el tamaño del archivo principal.
 * Recibe un objeto `ctx` con todas las variables y funciones necesarias del padre.
 */
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Label } from '../ui/label';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';
import { Button } from '../ui/button';
import { Plus, Download, CreditCard, CheckCircle2, Copy, Cpu, Users, Landmark, Trash2, Building2, RefreshCw, Unlock, Eye } from 'lucide-react';
import { BranchDetailPanel } from '../BranchDetailPanel';
import { MultiProductSelector } from '../MultiProductSelector';
import { QUOTE_TYPES, PRICING_MODELS } from './constants';
import { toast } from 'sonner';

export const QuoteWizardDialog = ({ ctx }) => {
  const {
    // State
    wizardOpen, setWizardOpen, isEditing, setIsEditing, setEditingQuoteId,
    quoteData, setQuoteData, banks, integrators, pinpads, posDevices, allHardware,
    serviceCatalog, clients, clientSearchQuery, setClientSearchQuery, clientSearchResults,
    selectedBankId, setSelectedBankId, selectedMedioPagoId, setSelectedMedioPagoId,
    availableMediosPago, setAvailableMediosPago,
    pgSetupItems, setPgSetupItems, pgTransactionRange, setPgTransactionRange,
    pgRecurringCostsTable, setPgRecurringCostsTable, pgSelectedMedioPago, setPgSelectedMedioPago,
    pgSelectedBankId, setPgSelectedBankId, pgDefaults,
    pgShowRecurringTable, setPgShowRecurringTable, pgFilteredProducts, setPgFilteredProducts,
    ftEquipmentItems, setFtEquipmentItems,
    branchDetails, setBranchDetails,
    isProductionClient, setIsProductionClient,
    productionItems, setProductionItems,
    productionSelectedServiceId, setProductionSelectedServiceId,
    pdfPreviewLoading,
    // Derived
    selectedClient, selectedIntegrator, selectedPinpad, selectedSponsorBank,
    isPaymentGateway, isVPOS, isMPOS, isFastTrackType, isMegaSoftSponsor,
    isHeaderComplete, canShowItems,
    // Calculated totals
    calcularTotal, calcularTotalEstandar, calcularTotalRecurrente,
    subtotalSetup, subtotalRecurringBasic, subtotalRecurringOther, subtotalRecurringAdditional,
    subtotalRecurrente, subtotalProduction, montoDescuentoSetup, montoDescuentoRecurrente,
    totalNetoSetup, totalNetoRecurrente, ftHardwareSubtotal, grandTotal,
    pgSetupTotal,
    pgMediosPagoCount,
    // Functions
    initializeSetupConcepts, initializeRecurringBasicConcepts, initializeRecurringOtherConcepts,
    findServicePrice, findServicePriceWithModel, handleBankSelect,
    addMedioPagoItem, addMultipleMediosPago, duplicateSetupItem, handleSubmitQuote,
    handleSubmitPGQuote, exportCurrentQuoteToPDF, previewCurrentQuotePDF,
    handlePgBankChange, addPgSetupItem, addMultiplePgSetupItems,
    generatePgRecurringTable, getPgFullRecurringTable,
    getPricingModelName,
    handleIntegratorChange, removeAdditionalItem, removeSetupItem,
    removeRecurringBasicItem, removeRecurringOtherItem, removePgSetupItem,
    getQuoteTypeName, initPgSetup,
    pgFullRecurringTable, updateSetupItem, updateRecurringBasicItem,
    updateRecurringOtherItem, updateAdditionalItem, updatePgSetupItem,
    // Misc
    isLoadingEdit, editingQuoteId, currentUser,
  } = ctx;

  return (
          <Dialog open={wizardOpen} onOpenChange={(open) => {
            if (!open) {
              // Al cerrar el dialog, resetear el modo edición
              setIsEditing(false);
              setEditingQuoteId(null);
            }
            setWizardOpen(open);
          }}>
            <DialogContent className="max-w-6xl max-h-[95vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle className="font-manrope text-2xl flex items-center gap-3">
                  {isEditing ? 'Modificar Cotización (Nueva Versión)' : 'Nueva Implementación'}
                  {!isEditing && quoteData.client_segment && (
                    <span className={`px-3 py-1 text-xs font-semibold rounded-full ${
                      quoteData.client_segment === 'CORP'
                        ? 'bg-blue-100 text-blue-700 border border-blue-300'
                        : 'bg-emerald-100 text-emerald-700 border border-emerald-300'
                    }`} data-testid="segment-badge">
                      {quoteData.client_segment === 'CORP' ? 'Corporativo' : 'Pyme'}
                    </span>
                  )}
                </DialogTitle>
                {isEditing && (
                  <p className="text-sm text-amber-600 bg-amber-50 px-3 py-2 rounded-lg mt-2">
                    Está editando una cotización existente. Al guardar se creará una nueva versión con número correlativo diferente.
                  </p>
                )}
              </DialogHeader>

              {/* SECCIÓN 1: Parámetros Iniciales */}
              <div className="bg-slate-50 rounded-lg p-5 border">
                <h3 className="font-semibold text-lg text-slate-800 mb-4 flex items-center gap-2">
                  <span className="w-7 h-7 rounded-full bg-brand-blue-600 text-white flex items-center justify-center text-sm">1</span>
                  Parámetros de la Cotización
                </h3>
                
                <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 block">
                      Tipo de Cotización <span className="text-red-500">*</span>
                    </Label>
                    <Select
                      value={quoteData.quote_type}
                      onValueChange={(value) => {
                        const isMposSelected = value === 'MPOS';
                        const isFastTrack = value === 'FAST_TRACK';
                        const isMposLike = isMposSelected || isFastTrack;
                        
                        // Buscar banco "Mega Soft" para default de Fast Track
                        const megaSoftBank = isFastTrack ? banks.find(b => b.name?.toLowerCase().includes('mega soft') || b.name?.toLowerCase().includes('megasoft')) : null;
                        
                        // Limpiar integrador si no es compatible con la nueva modalidad
                        const currentIntegrator = integrators.find(i => i.integrator_id === quoteData.integrator_id);
                        let newIntegratorId = '';
                        if (isFastTrack) {
                          newIntegratorId = (currentIntegrator?.integration_modality === 'MPOS') ? quoteData.integrator_id : 'sin_integrador';
                        } else if (value === 'GATEWAY') {
                          newIntegratorId = (currentIntegrator?.integration_modality === 'PG Universal' || currentIntegrator?.integration_modality === 'PG No universal') ? quoteData.integrator_id : '';
                        } else if (value === 'VPOS') {
                          newIntegratorId = (currentIntegrator?.integration_modality === 'REST') ? quoteData.integrator_id : '';
                        } else if (isMposSelected) {
                          newIntegratorId = quoteData.integrator_id || '';
                        }
                        if (quoteData.integrator_id && quoteData.integrator_id !== 'sin_integrador' && newIntegratorId !== quoteData.integrator_id) {
                          toast.info('Integrador anterior no compatible con esta modalidad. Seleccione uno nuevo.');
                        }
                        
                        setQuoteData({ 
                          ...quoteData, 
                          quote_type: value, 
                          medios_pago_items: [], 
                          pricing_model: value === 'GATEWAY' ? 'conventional' : (isMposLike ? 'outsourcing' : ''),
                          requires_vpn: isFastTrack ? false : true,
                          requires_pinpad_config: true,
                          integrator_id: newIntegratorId,
                          sponsor_bank_id: isFastTrack ? (megaSoftBank?.bank_id || quoteData.sponsor_bank_id || '') : quoteData.sponsor_bank_id,
                        });
                        setSelectedBankId('');
                        setSelectedMedioPagoId('');
                        setAvailableMediosPago([]);
                        setPgSetupItems([]);
                        setPgTransactionRange(null);
                        setPgShowRecurringTable(false);
                        setPgFilteredProducts([]);
                        if (value === 'GATEWAY') {
                          const pjService = serviceCatalog.find(s => s.gateway_enabled && s.name?.toLowerCase().includes('persona jur'));
                          const pjCost = pjService?.setup_cost_outsourcing || pgDefaults?.costo || 240;
                          setPgSetupItems([{
                            concepto: 'Persona Jurídica',
                            costo: pjCost,
                            banco: 'N/A',
                            observacion: 'Costo Base',
                            fixed: true
                          }]);
                        }
                        // MPOS/Fast Track: auto-inicializar items con outsourcing
                        if (isMposLike) {
                          const cajas = quoteData.cantidad_cajas || 1;
                          const bancos = quoteData.cantidad_bancos || 1;
                          const setupItems = initializeSetupConcepts('outsourcing', cajas, bancos, quoteData.requires_pinpad_config);
                          const recurringBasicItems = initializeRecurringBasicConcepts('outsourcing', cajas, bancos);
                          const recurringOtherItems = initializeRecurringOtherConcepts('outsourcing', cajas, bancos, true);
                          setQuoteData(prev => ({
                            ...prev,
                            quote_type: value,
                            pricing_model: 'outsourcing',
                            setup_items: setupItems,
                            recurring_basic_items: recurringBasicItems,
                            recurring_other_items: recurringOtherItems,
                            additional_items: [],
                          }));
                        }
                      }}
                    >
                      <SelectTrigger data-testid="select-quote-type">
                        <SelectValue placeholder="Seleccione tipo..." />
                      </SelectTrigger>
                      <SelectContent>
                        {QUOTE_TYPES.filter(t => !t.disabled).map((type) => (
                          <SelectItem key={type.id} value={type.id}>{type.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 block">
                      Cliente <span className="text-red-500">*</span>
                    </Label>
                    <Select
                      value={quoteData.client_id || ''}
                      onValueChange={(val) => setQuoteData(prev => ({ ...prev, client_id: val }))}
                    >
                      <SelectTrigger className="w-full h-10" data-testid="select-client">
                        <SelectValue placeholder="Seleccione un cliente..." />
                      </SelectTrigger>
                      <SelectContent className="max-h-[280px]">
                        <div className="px-2 pb-2 sticky top-0 bg-white z-10">
                          <input
                            type="text"
                            placeholder="Buscar por nombre o RIF..."
                            className="w-full h-8 px-2 text-sm border rounded-md outline-none focus:ring-1 focus:ring-blue-400"
                            value={clientSearchQuery}
                            onChange={(e) => setClientSearchQuery(e.target.value)}
                            onKeyDown={(e) => e.stopPropagation()}
                            data-testid="client-search-input"
                          />
                        </div>
                        {(clientSearchQuery.length >= 2 ? clientSearchResults : clients.slice(0, 50)).map((client) => (
                          <SelectItem key={client.client_id} value={client.client_id} data-testid={`client-option-${client.client_id}`}>
                            {client.fantasy_name || client.legal_name} — {client.rif}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Hide Modelo/Cajas/Bancos for Payment Gateway */}
                  {!isPaymentGateway && (<>
                  {/* Modelo de Precios: oculto para MPOS (forzado a Outsourcing) */}
                  {!isMPOS ? (
                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 block">
                      Modelo de Precios <span className="text-red-500">*</span>
                    </Label>
                    <Select 
                      value={quoteData.pricing_model} 
                      onValueChange={(value) => {
                        // Al seleccionar modelo, inicializar conceptos SOLO si no estamos en modo edición
                        // o si no hay items ya cargados
                        const cajas = quoteData.cantidad_cajas || 1;
                        const bancos = quoteData.cantidad_bancos || 1;
                        
                        // Si estamos editando y ya hay items, mantenerlos
                        if (isEditing && (quoteData.setup_items.length > 0 || quoteData.recurring_basic_items.length > 0)) {
                          setQuoteData({ 
                            ...quoteData, 
                            pricing_model: value
                          });
                        } else {
                          // Nueva cotización: inicializar conceptos desde el catálogo
                          const setupItems = initializeSetupConcepts(value, cajas, bancos, quoteData.requires_pinpad_config);
                          const recurringBasicItems = initializeRecurringBasicConcepts(value, cajas, bancos);
                          const recurringOtherItems = initializeRecurringOtherConcepts(value, cajas, bancos, quoteData.requires_vpn);
                          setQuoteData({ 
                            ...quoteData, 
                            pricing_model: value, 
                            cantidad_cajas: cajas,
                            cantidad_bancos: bancos,
                            setup_items: setupItems,
                            recurring_basic_items: recurringBasicItems,
                            recurring_other_items: recurringOtherItems,
                            additional_items: []
                          });
                        }
                      }}
                    >
                      <SelectTrigger data-testid="select-pricing-model">
                        <SelectValue placeholder="Seleccione modelo..." />
                      </SelectTrigger>
                      <SelectContent>
                        {PRICING_MODELS.map((model) => (
                          <SelectItem key={model.id} value={model.id}>{model.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  ) : (
                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 block">
                      Modelo de Precios
                    </Label>
                    <div className="h-10 px-3 py-2 bg-slate-100 border border-slate-200 rounded-md flex items-center">
                      <span className="text-sm text-slate-700 font-medium">Outsourcing (fijo MPOS)</span>
                    </div>
                  </div>
                  )}

                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 block">
                      Cajas (VTID) <span className="text-red-500">*</span>
                    </Label>
                    <Input
                      type="number"
                      min="1"
                      value={quoteData.cantidad_cajas}
                      onChange={(e) => setQuoteData({ ...quoteData, cantidad_cajas: e.target.value === '' ? '' : parseInt(e.target.value) })}
                      onBlur={(e) => {
                        if (e.target.value === '' || parseInt(e.target.value) < 1) {
                          setQuoteData({ ...quoteData, cantidad_cajas: 1 });
                        }
                      }}
                      data-testid="cantidad-cajas-input"
                      className="h-10"
                    />
                  </div>

                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 block">
                      Bancos/Entes
                    </Label>
                    <Input
                      type="number"
                      min="1"
                      value={quoteData.cantidad_bancos}
                      onChange={(e) => setQuoteData({ ...quoteData, cantidad_bancos: e.target.value === '' ? '' : parseInt(e.target.value) })}
                      onBlur={(e) => {
                        if (e.target.value === '' || parseInt(e.target.value) < 1) {
                          setQuoteData({ ...quoteData, cantidad_bancos: 1 });
                        }
                      }}
                      data-testid="cantidad-bancos-input"
                      className="h-10"
                    />
                  </div>
                  {/* End conditional for non-PG fields */}
                  </>)}
                </div>

                {/* Parámetros dinámicos VPOS: PinPads y VPN */}
                {!isPaymentGateway && quoteData.pricing_model && (
                  <div className={`grid grid-cols-1 ${isMPOS ? 'md:grid-cols-1' : 'md:grid-cols-2'} gap-4 mt-4 pt-4 border-t border-slate-200`}>
                    <div>
                      <Label className="text-sm font-medium text-slate-700 mb-2 block">
                        ¿Requiere Configuración de {isMPOS ? 'POS' : 'PinPads'}?
                      </Label>
                      <Select
                        value={quoteData.requires_pinpad_config ? 'si' : 'no'}
                        onValueChange={(v) => {
                          const newVal = v === 'si';
                          const cajas = quoteData.cantidad_cajas || 1;
                          const bancos = quoteData.cantidad_bancos || 1;
                          if (newVal && !quoteData.requires_pinpad_config) {
                            // Agregar ítem de vuelta
                            const pinpadConcept = SETUP_CONCEPTS.find(c => c.name === 'Configuración dispositivo (Pinpad o POS)');
                            if (pinpadConcept) {
                              const prices = findServicePriceWithModel(pinpadConcept.name, quoteData.pricing_model);
                              const pinpadItem = {
                                id: `setup_${pinpadConcept.name}`,
                                medio_pago_name: pinpadConcept.name,
                                cantidad_cajas: cajas,
                                cantidad_bancos: 1,
                                tarifa: prices.setup_cost,
                                isDefault: true,
                                type: 'setup',
                                lockBancos: true,
                                autoBancos: false
                              };
                              // Insertar en posición 1 (después del primer concepto)
                              const newSetup = [...quoteData.setup_items];
                              newSetup.splice(1, 0, pinpadItem);
                              setQuoteData({ ...quoteData, requires_pinpad_config: true, setup_items: newSetup });
                            }
                          } else if (!newVal && quoteData.requires_pinpad_config) {
                            // Eliminar ítem de Configuración dispositivo
                            const newSetup = quoteData.setup_items.filter(
                              i => i.medio_pago_name !== 'Configuración dispositivo (Pinpad o POS)'
                            );
                            setQuoteData({ ...quoteData, requires_pinpad_config: false, setup_items: newSetup });
                          }
                        }}
                      >
                        <SelectTrigger data-testid="select-requires-pinpad">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="si">Sí</SelectItem>
                          <SelectItem value="no">No</SelectItem>
                        </SelectContent>
                      </Select>
                      <p className="text-[10px] text-slate-400 mt-1">
                        {quoteData.requires_pinpad_config
                          ? `Incluye "Configuración dispositivo (${isMPOS ? 'POS' : 'Pinpad o POS'})" en Setup`
                          : 'Excluido del Setup — total recalculado'}
                      </p>
                    </div>

                    {/* VPN toggle: solo VPOS, MPOS asume conectividad estándar */}
                    {!isMPOS && (
                      <div>
                        <Label className="text-sm font-medium text-slate-700 mb-2 block">
                          ¿Requiere VPN?
                        </Label>
                        <Select
                          value={quoteData.requires_vpn ? 'si' : 'no'}
                          onValueChange={(v) => {
                            const newVal = v === 'si';
                            // Actualizar tarifa de "Comunicación Backend" en recurring_other_items
                            const updatedOther = quoteData.recurring_other_items.map(item => {
                              if (item.medio_pago_name.includes('Comunicación Backend')) {
                                const service = serviceCatalog.find(s =>
                                  s.name.toLowerCase().includes('comunicación backend') ||
                                  s.name.toLowerCase().includes('comunicacion backend') ||
                                  item.medio_pago_name.toLowerCase().includes(s.name.toLowerCase())
                                );
                                if (service) {
                                  return {
                                    ...item,
                                    tarifa: newVal
                                      ? (service.monthly_cost_conventional || 0)
                                      : (service.monthly_cost_outsourcing || 0)
                                  };
                                }
                              }
                              return item;
                            });
                            setQuoteData({ ...quoteData, requires_vpn: newVal, recurring_other_items: updatedOther });
                          }}
                        >
                          <SelectTrigger data-testid="select-requires-vpn">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="si">Sí — Costo Conv.</SelectItem>
                            <SelectItem value="no">No — Costo Outs.</SelectItem>
                          </SelectContent>
                        </Select>
                        <p className="text-[10px] text-slate-400 mt-1">
                          {quoteData.requires_vpn
                            ? 'Comunicación Backend usa tarifa Convencional'
                            : 'Comunicación Backend usa tarifa Outsourcing'}
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {isHeaderComplete && (
                  <div className="mt-4 p-3 bg-brand-green-50 border border-brand-green-200 rounded-lg flex items-center gap-2">
                    <CheckCircle2 size={18} className="text-brand-green-600" />
                    <span className="text-sm text-brand-green-700 font-medium">
                      {getQuoteTypeName(quoteData.quote_type)} • {selectedClient?.fantasy_name || selectedClient?.legal_name} - {selectedClient?.rif}
                      {!isPaymentGateway && <> • {getPricingModelName(quoteData.pricing_model)} • {quoteData.cantidad_cajas} cajas • {quoteData.cantidad_bancos} bancos</>}
                    </span>
                  </div>
                )}
              </div>

              {/* SECCIÓN 1.5: Detalles de Integración y Hardware */}
              <div className="bg-gradient-to-r from-slate-50 to-blue-50 rounded-lg p-5 border border-blue-100 mt-4">
                <h3 className="font-semibold text-lg text-slate-800 mb-4 flex items-center gap-2">
                  <Cpu size={20} className="text-brand-blue-600" />
                  {isPaymentGateway ? 'Integrador' : 'Detalles de Integración y Hardware'}
                </h3>
                
                <div className={`grid grid-cols-1 ${isPaymentGateway ? 'md:grid-cols-2' : 'md:grid-cols-4'} gap-4`}>
                  {/* Campo 1: Integrador */}
                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 flex items-center gap-2">
                      <Users size={14} className="text-brand-blue-600" />
                      Integrador {!isMPOS && <span className="text-red-500">*</span>}
                      {isMPOS && <span className="text-slate-400 text-xs font-normal">(Opcional)</span>}
                    </Label>
                    <Select 
                      value={quoteData.integrator_id} 
                      onValueChange={handleIntegratorChange}
                    >
                      <SelectTrigger data-testid="select-integrator">
                        <SelectValue placeholder="Seleccione integrador..." />
                      </SelectTrigger>
                      <SelectContent>
                        {(isMPOS || isPaymentGateway) && (
                          <SelectItem value="sin_integrador">Sin integrador</SelectItem>
                        )}
                        {(() => {
                          const filtered = integrators.filter(i => {
                            if (i.integrator_status !== 'Certificado') return false;
                            if (isPaymentGateway) {
                              return i.integration_modality === 'PG Universal' || i.integration_modality === 'PG No universal';
                            }
                            if (isFastTrackType) {
                              return i.integration_modality === 'MPOS';
                            }
                            if (isVPOS) {
                              return i.integration_modality === 'REST';
                            }
                            return true;
                          });
                          return filtered.length > 0 ? filtered.map((integrator) => (
                            <SelectItem key={integrator.integrator_id} value={integrator.integrator_id}>
                              {integrator.name}
                            </SelectItem>
                          )) : (
                            <SelectItem value="_no_integrators_" disabled>
                              No hay integradores para esta modalidad
                            </SelectItem>
                          );
                        })()}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Campo Informativo: Aplicativo */}
                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 block">
                      Aplicativo Certificado
                    </Label>
                    <div className="h-10 px-3 py-2 bg-slate-100 border border-slate-200 rounded-md flex items-center">
                      <span className={`text-sm ${quoteData.integrator_app_name ? 'text-slate-900 font-medium' : 'text-slate-400'}`}>
                        {quoteData.integrator_app_name || 'Se completa al seleccionar integrador'}
                      </span>
                    </div>
                  </div>

                  {/* Campo 2: Modelo de POS/Pinpad — Visible para VPOS/MPOS y Fast Track */}
                  {!isPaymentGateway && (
                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 flex items-center gap-2">
                      <Cpu size={14} className="text-brand-green-600" />
                      {isFastTrackType ? 'Modelo de POS / PINPAD' : isMPOS ? 'Modelo de POS' : 'Modelo de Pinpad'}
                      {isFastTrackType
                        ? <span className="text-red-500">*</span>
                        : <span className="text-slate-400 text-xs font-normal">(Opcional)</span>}
                    </Label>
                    <Select 
                      value={quoteData.pinpad_id} 
                      onValueChange={(value) => setQuoteData({ ...quoteData, pinpad_id: value })}
                    >
                      <SelectTrigger data-testid="select-pinpad">
                        <SelectValue placeholder={isFastTrackType ? 'Seleccione modelo (obligatorio)...' : `Seleccione ${isMPOS ? 'POS' : 'modelo'}...`} />
                      </SelectTrigger>
                      <SelectContent>
                        {!isFastTrackType && (
                          <SelectItem value="none">Sin {isMPOS ? 'POS' : 'Pinpad'}</SelectItem>
                        )}
                        {isFastTrackType ? (
                          // Fast Track: mostrar POS + Pinpads combinados (solo tipo Bien)
                          [...posDevices, ...pinpads].length === 0 ? (
                            <SelectItem value="no-devices" disabled>No hay dispositivos disponibles</SelectItem>
                          ) : (
                            [...posDevices, ...pinpads].map((device) => (
                              <SelectItem key={device.hardware_id} value={device.hardware_id}>
                                {device.name} — {device.type} {(device.price_bs_usd || device.price_usd) > 0 && `($${device.price_bs_usd || device.price_usd})`}
                              </SelectItem>
                            ))
                          )
                        ) : (
                          // VPOS/MPOS: lógica original
                          (isMPOS ? posDevices : pinpads).length === 0 ? (
                            <SelectItem value="no-devices" disabled>No hay {isMPOS ? 'POS' : 'Pinpads'} disponibles</SelectItem>
                          ) : (
                            (isMPOS ? posDevices : pinpads).map((device) => (
                              <SelectItem key={device.hardware_id} value={device.hardware_id}>
                                {device.name} {(device.price_bs_usd || device.price_usd) > 0 && `($${device.price_bs_usd || device.price_usd})`}
                              </SelectItem>
                            ))
                          )
                        )}
                      </SelectContent>
                    </Select>
                    {isFastTrackType && (
                      <p className="text-[10px] text-slate-400 mt-1">
                        Este modelo se hereda a la Ficha Técnica y al proyecto. No requiere carga en "Equipos a Despachar".
                      </p>
                    )}
                  </div>
                  )}

                  {/* Campo 3: Entidad Patrocinadora (Opcional) - Solo para VPOS/MPOS */}
                  {!isPaymentGateway && (
                  <div>
                    <Label className="text-sm font-medium text-slate-700 mb-2 flex items-center gap-2">
                      <Landmark size={14} className="text-amber-600" />
                      Entidad Patrocinadora <span className="text-slate-400 text-xs font-normal">(Opcional)</span>
                    </Label>
                    <Select 
                      value={quoteData.sponsor_bank_id} 
                      onValueChange={(value) => {
                        setQuoteData({ ...quoteData, sponsor_bank_id: value });
                        // Si es Fast Track y cambia de patrocinador, limpiar equipos si no es Mega Soft
                        if (isFastTrackType) {
                          const bank = banks.find(b => b.bank_id === value);
                          const isMega = bank?.name?.toLowerCase().includes('mega soft') || bank?.name?.toLowerCase().includes('megasoft');
                          if (!isMega) setFtEquipmentItems([]);
                        }
                      }}
                    >
                      <SelectTrigger data-testid="select-sponsor-bank">
                        <SelectValue placeholder="Seleccione entidad..." />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">Sin Entidad Patrocinadora</SelectItem>
                        {banks.map((bank) => (
                          <SelectItem key={bank.bank_id} value={bank.bank_id}>
                            {bank.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  )}
                </div>

                {/* Indicador de campos completos - Solo requiere Integrador */}
                {quoteData.integrator_id && (
                  <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg flex items-center gap-2">
                    <CheckCircle2 size={18} className="text-brand-blue-600" />
                    <span className="text-sm text-brand-blue-700 font-medium">
                      Integrador: {selectedIntegrator?.name} ({quoteData.integrator_app_name})
                      {selectedPinpad && ` • ${isFastTrackType ? 'Modelo' : 'Pinpad'}: ${selectedPinpad.name}`}
                      {selectedSponsorBank && ` • Patrocinador: ${selectedSponsorBank.name}`}
                    </span>
                  </div>
                )}
              </div>

              {/* ====== SECCIÓN FAST TRACK: Equipos a Despachar (solo si Patrocinador = Mega Soft) ====== */}
              {isFastTrackType && isMegaSoftSponsor && isHeaderComplete && (
                <div className="bg-white rounded-lg p-5 border mt-4">
                  <h3 className="font-semibold text-lg text-slate-800 mb-4 flex items-center gap-2">
                    <span className="w-7 h-7 rounded-full bg-violet-600 text-white flex items-center justify-center text-sm">2</span>
                    Equipos a Despachar (Cotizacion de Equipos)
                  </h3>

                  {/* Espejo de datos: modelo sincronizado desde Detalles de Integración */}
                  {quoteData.pinpad_id && quoteData.pinpad_id !== 'none' ? (
                    <div data-testid="ft-hardware-mirror">
                      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4 flex items-center gap-2">
                        <CheckCircle2 size={14} className="text-blue-600" />
                        <span className="text-xs text-blue-700">
                          Modelo sincronizado desde <strong>Detalles de Integración</strong> — Solo lectura.
                        </span>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full border-collapse" data-testid="ft-hardware-readonly-table">
                          <thead>
                            <tr className="bg-slate-100">
                              <th className="border p-2 text-left text-sm font-medium text-slate-700">Equipo</th>
                              <th className="border p-2 text-left text-sm font-medium text-slate-700 w-24">Tipo</th>
                              <th className="border p-2 text-center text-sm font-medium text-slate-700 w-20">Cant.</th>
                              <th className="border p-2 text-right text-sm font-medium text-slate-700 w-32">P. Unit. (USD)</th>
                              <th className="border p-2 text-right text-sm font-medium text-slate-700 w-32">Subtotal (USD)</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr className="bg-white">
                              <td className="border p-2 text-sm font-semibold text-slate-800">{selectedPinpad?.name || '—'}</td>
                              <td className="border p-2 text-sm text-slate-600">{selectedPinpad?.type || 'POS'}</td>
                              <td className="border p-2 text-center text-sm font-medium">{parseInt(quoteData.cantidad_cajas) || 1}</td>
                              <td className="border p-2 text-right text-sm font-medium">${(selectedPinpad?.price_bs_usd || selectedPinpad?.price_usd || 0).toFixed(2)}</td>
                              <td className="border p-2 text-right text-sm font-bold text-slate-900">
                                ${((parseInt(quoteData.cantidad_cajas) || 1) * (selectedPinpad?.price_bs_usd || selectedPinpad?.price_usd || 0)).toFixed(2)}
                              </td>
                            </tr>
                          </tbody>
                          <tfoot>
                            <tr className="bg-slate-800 text-white">
                              <td colSpan={3} className="border p-2 text-right text-sm font-bold">Total Equipos (USD):</td>
                              <td className="border p-2"></td>
                              <td className="border p-2 text-right text-sm font-bold">
                                ${((parseInt(quoteData.cantidad_cajas) || 1) * (selectedPinpad?.price_bs_usd || selectedPinpad?.price_usd || 0)).toFixed(2)}
                              </td>
                            </tr>
                          </tfoot>
                        </table>
                      </div>
                      <p className="text-[10px] text-slate-400 mt-2">
                        Este monto se incluye en el Total General de la cotización. Para cambiar el modelo, modifique el campo arriba en Detalles de Integración.
                      </p>
                    </div>
                  ) : (
                    <>
                  <p className="text-xs text-slate-500 mb-3">
                    Estos equipos se incluiran como pagina adicional en el PDF hibrido.
                  </p>

                  {/* Selector de hardware - Filtro estricto: solo POS tipo Bien */}
                  <div className="bg-slate-50 rounded-lg p-4 border mb-4">
                    <p className="text-xs text-slate-500 mb-2 font-medium uppercase tracking-wide">Agregar Equipo</p>
                    <div className="grid grid-cols-4 gap-3 items-end">
                      <div className="col-span-4">
                        <Label className="text-xs text-slate-600">Equipo</Label>
                        <Select onValueChange={(value) => {
                          const hw = allHardware.find(h => h.hardware_id === value);
                          if (hw) {
                            const exists = ftEquipmentItems.find(i => i.hardware_id === value);
                            if (exists) {
                              toast.error('Este equipo ya fue agregado');
                              return;
                            }
                            setFtEquipmentItems(prev => [...prev, {
                              hardware_id: hw.hardware_id,
                              name: hw.name,
                              hardware_type: hw.type || hw.hardware_type || 'POS',
                              quantity: parseInt(quoteData.cantidad_cajas) || 1,
                              unit_price_usd: hw.price_bs_usd || hw.price_usd || 0
                            }]);
                          }
                        }}>
                          <SelectTrigger data-testid="ft-select-equipment" className="h-9 text-sm">
                            <SelectValue placeholder="Seleccione equipo del catalogo..." />
                          </SelectTrigger>
                          <SelectContent>
                            {allHardware.filter(hw => hw.type === 'POS' && hw.asset_type !== 'Servicio').map(hw => (
                              <SelectItem key={hw.hardware_id} value={hw.hardware_id}>
                                {hw.name} — {hw.type || 'Equipo'} {(hw.price_bs_usd || hw.price_usd) > 0 && `($${hw.price_bs_usd || hw.price_usd})`}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  </div>

                  {/* Tabla de equipos */}
                  {ftEquipmentItems.length > 0 && (
                    <div className="overflow-x-auto">
                      <table className="w-full border-collapse" data-testid="ft-equipment-table">
                        <thead>
                          <tr className="bg-slate-100">
                            <th className="border p-2 text-left text-sm font-medium text-slate-700">Equipo</th>
                            <th className="border p-2 text-left text-sm font-medium text-slate-700 w-24">Tipo</th>
                            <th className="border p-2 text-center text-sm font-medium text-slate-700 w-20">Cant.</th>
                            <th className="border p-2 text-right text-sm font-medium text-slate-700 w-32">P. Unit. (USD)</th>
                            <th className="border p-2 text-right text-sm font-medium text-slate-700 w-32">Total (USD)</th>
                            <th className="border p-2 text-center text-sm font-medium text-slate-700 w-12"></th>
                          </tr>
                        </thead>
                        <tbody>
                          {ftEquipmentItems.map((item, idx) => (
                            <tr key={idx} className="hover:bg-slate-50">
                              <td className="border p-2 text-sm font-medium">{item.name}</td>
                              <td className="border p-2 text-sm text-slate-600">{item.hardware_type}</td>
                              <td className="border p-2">
                                <Input type="number" min="1" value={item.quantity} className="h-7 text-center text-sm"
                                  onChange={e => {
                                    const qty = Math.max(1, parseInt(e.target.value) || 1);
                                    setFtEquipmentItems(prev => prev.map((it, i) => i === idx ? {...it, quantity: qty} : it));
                                  }}
                                  data-testid={`ft-eq-qty-${idx}`}
                                />
                              </td>
                              <td className="border p-2">
                                <Input type="number" step="0.01" min="0" value={item.unit_price_usd} className="h-7 text-right text-sm"
                                  onChange={e => {
                                    const price = parseFloat(e.target.value) || 0;
                                    setFtEquipmentItems(prev => prev.map((it, i) => i === idx ? {...it, unit_price_usd: price} : it));
                                  }}
                                  data-testid={`ft-eq-price-${idx}`}
                                />
                              </td>
                              <td className="border p-2 text-right text-sm font-semibold">${(item.quantity * item.unit_price_usd).toFixed(2)}</td>
                              <td className="border p-2 text-center">
                                <button onClick={() => setFtEquipmentItems(prev => prev.filter((_, i) => i !== idx))}
                                  className="text-red-500 hover:text-red-700" data-testid={`ft-eq-remove-${idx}`}>
                                  <X size={14} />
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                        <tfoot>
                          <tr className="bg-slate-800 text-white">
                            <td colSpan={4} className="border p-2 text-right text-sm font-bold">Total Equipos (USD):</td>
                            <td className="border p-2 text-right text-sm font-bold">
                              ${ftEquipmentItems.reduce((acc, it) => acc + (it.quantity * it.unit_price_usd), 0).toFixed(2)}
                            </td>
                            <td className="border p-2"></td>
                          </tr>
                        </tfoot>
                      </table>
                    </div>
                  )}

                  {ftEquipmentItems.length === 0 && (
                    <div className="text-center py-6 text-slate-400 text-sm border-2 border-dashed rounded-lg">
                      Seleccione equipos del catalogo para incluir en la cotizacion hibrida
                    </div>
                  )}
                    </>
                  )}
                </div>
              )}

              {/* ====== SECCIÓN PG: Setup de Payment Gateway ====== */}
              {isPaymentGateway && isHeaderComplete && (
                <div className="bg-white rounded-lg p-5 border mt-4">
                  <h3 className="font-semibold text-lg text-slate-800 mb-4 flex items-center gap-2">
                    <span className="w-7 h-7 rounded-full bg-emerald-600 text-white flex items-center justify-center text-sm">2</span>
                    Payment Gateway - Inversión en Setup / Arranque
                  </h3>
                  
                  {/* Auto-load Persona Jurídica */}
                  {pgSetupItems.length === 0 && pgDefaults && (
                    <div className="mb-4">
                      <Button onClick={initPgSetup} className="bg-amber-600 hover:bg-amber-700 text-white" data-testid="pg-init-setup-btn">
                        Cargar concepto base (Persona Jurídica)
                      </Button>
                    </div>
                  )}

                  {/* Agregar medio de pago: BANCO primero, luego selector múltiple */}
                  <div className="bg-slate-50 rounded-lg p-4 border mb-4">
                    <p className="text-xs text-slate-500 mb-3 font-medium uppercase tracking-wide">Agregar Medio de Pago</p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-end">
                      <div>
                        <Label className="text-sm font-medium text-slate-700 mb-2 block">1. Banco</Label>
                        <Select value={pgSelectedBankId} onValueChange={handlePgBankChange}>
                          <SelectTrigger data-testid="pg-select-bank">
                            <SelectValue placeholder="Seleccione banco..." />
                          </SelectTrigger>
                          <SelectContent>
                            {banks.map((bank) => (
                              <SelectItem key={bank.bank_id} value={bank.bank_id}>{bank.name}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <Label className="text-sm font-medium text-slate-700 mb-2 block">2. Concepto(s) (Medio de Pago)</Label>
                        <MultiProductSelector
                          products={pgFilteredProducts}
                          existingItems={pgSetupItems}
                          bankName={banks.find(b => b.bank_id === pgSelectedBankId)?.name || ''}
                          onAdd={addMultiplePgSetupItems}
                          disabled={!pgSelectedBankId}
                          duplicateKey="product_name"
                          existingKey="concepto"
                          existingBankKey="banco"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Tabla de setup items */}
                  {pgSetupItems.length > 0 && (
                    <div className="overflow-x-auto">
                      <table className="w-full border-collapse">
                        <thead>
                          <tr className="bg-slate-100">
                            <th className="border p-2 text-left text-sm font-medium text-slate-700">Concepto</th>
                            <th className="border p-2 text-left text-sm font-medium text-slate-700 w-36">Costo ($)</th>
                            <th className="border p-2 text-left text-sm font-medium text-slate-700">Banco</th>
                            <th className="border p-2 text-left text-sm font-medium text-slate-700">Observación</th>
                            <th className="border p-2 text-center text-sm font-medium text-slate-700 w-16"></th>
                          </tr>
                        </thead>
                        <tbody>
                          {pgSetupItems.map((item, index) => (
                            <tr key={index} className={`hover:bg-slate-50 ${item.fixed ? 'bg-amber-50' : ''}`}>
                              <td className="border p-2 text-sm font-medium">
                                {item.concepto}
                                {item.fixed && <span className="ml-2 text-xs bg-amber-200 text-amber-800 px-1.5 py-0.5 rounded">Fijo</span>}
                              </td>
                              <td className="border p-2">
                                <Input
                                  type="number"
                                  step="0.01"
                                  value={item.costo}
                                  onChange={(e) => updatePgSetupItem(index, 'costo', e.target.value)}
                                  data-testid={`pg-setup-cost-${index}`}
                                  className="h-8 text-sm"
                                />
                              </td>
                              <td className="border p-2 text-sm">{item.banco}</td>
                              <td className="border p-2">
                                <Input
                                  value={item.observacion}
                                  onChange={(e) => updatePgSetupItem(index, 'observacion', e.target.value)}
                                  data-testid={`pg-setup-obs-${index}`}
                                  className="h-8 text-sm"
                                  placeholder="Observación..."
                                />
                              </td>
                              <td className="border p-2 text-center">
                                {!item.fixed && (
                                  <Button variant="ghost" size="sm" onClick={() => removePgSetupItem(index)} data-testid={`pg-remove-item-${index}`} className="text-red-500 hover:text-red-700 h-7 w-7 p-0">
                                    <Trash2 size={14} />
                                  </Button>
                                )}
                              </td>
                            </tr>
                          ))}
                          <tr className="bg-emerald-50 font-semibold">
                            <td className="border p-2 text-sm text-right" colSpan={1}>Total Setup:</td>
                            <td className="border p-2 text-sm text-emerald-700">${pgSetupTotal.toFixed(2)}</td>
                            <td className="border p-2" colSpan={3}></td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  )}

                  {pgSetupItems.length === 0 && !pgDefaults && (
                    <div className="text-center py-8 text-slate-400">
                      Cargando configuración...
                    </div>
                  )}
                </div>
              )}

              {/* ====== SECCIÓN PG: Costos Recurrentes ====== */}
              {isPaymentGateway && isHeaderComplete && pgSetupItems.length > 0 && pgRecurringCostsTable && (
                <div className="bg-white rounded-lg p-5 border mt-4">
                  <h3 className="font-semibold text-lg text-slate-800 mb-4 flex items-center gap-2">
                    <span className="w-7 h-7 rounded-full bg-blue-600 text-white flex items-center justify-center text-sm">3</span>
                    Costos Recurrentes Mensuales
                  </h3>
                  
                  <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                    <p className="text-sm text-blue-700">
                      Medios de Pago seleccionados: <strong>{pgMediosPagoCount}</strong>
                      {pgMediosPagoCount === 0 && <span className="text-amber-600 ml-2">(Agregue al menos un medio de pago para calcular recurrentes)</span>}
                    </p>
                  </div>

                  {!pgShowRecurringTable ? (
                    <div className="text-center py-4">
                      <Button 
                        onClick={generatePgRecurringTable} 
                        className="bg-blue-600 hover:bg-blue-700 text-white px-6"
                        disabled={pgMediosPagoCount === 0}
                        data-testid="pg-generate-recurring-btn"
                      >
                        <RefreshCw size={16} className="mr-2" />
                        Generar Tabla de Recurrentes
                      </Button>
                    </div>
                  ) : (
                    <>
                      <div className="mb-3 flex items-center justify-between">
                        <p className="text-sm text-slate-600">
                          Tabla calculada para <strong>{Math.min(pgMediosPagoCount, 11)}</strong> medio(s) de pago
                        </p>
                        <Button 
                          variant="outline" size="sm"
                          onClick={generatePgRecurringTable}
                          data-testid="pg-refresh-recurring-btn"
                        >
                          <RefreshCw size={14} className="mr-1" /> Recalcular
                        </Button>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full border-collapse text-sm">
                          <thead>
                            <tr className="bg-blue-100">
                              <th className="border p-2 text-left font-medium text-blue-800">Rango</th>
                              <th className="border p-2 text-left font-medium text-blue-800">Transacciones</th>
                              <th className="border p-2 text-right font-medium text-blue-800">Total $ Base</th>
                              <th className="border p-2 text-right font-medium text-blue-800">Precio Tope por Rango</th>
                            </tr>
                          </thead>
                          <tbody>
                            {pgFullRecurringTable.map((row, idx) => (
                              <tr key={row.rango} className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                                <td className="border p-2 font-medium">{row.rango}</td>
                                <td className="border p-2">{row.label}</td>
                                <td className="border p-2 text-right font-semibold text-emerald-700">
                                  {row.base !== null && row.base !== undefined ? `$${row.base.toFixed(2)}` : 'Negociable'}
                                </td>
                                <td className="border p-2 text-right">
                                  {row.tope !== null && row.tope !== undefined ? `$${row.tope.toFixed(6)}` : 'N/A'}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </div>
              )}

              {/* SECCIÓN 2: Selección de Medios de Pago - Solo para VPOS/MPOS */}
              {!isPaymentGateway && isHeaderComplete && (
                <div className="bg-white rounded-lg p-5 border mt-4">
                  <h3 className="font-semibold text-lg text-slate-800 mb-4 flex items-center gap-2">
                    <span className="w-7 h-7 rounded-full bg-brand-blue-600 text-white flex items-center justify-center text-sm">2</span>
                    Selección de Medios de Pago
                  </h3>
                  
                  <div className="bg-slate-50 rounded-lg p-4 border mb-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-end">
                      <div>
                        <Label className="text-sm font-medium text-slate-700 mb-2 flex items-center gap-2">
                          <Building2 size={16} className="text-brand-blue-600" />
                          Banco
                        </Label>
                        <Select value={selectedBankId} onValueChange={handleBankSelect}>
                          <SelectTrigger data-testid="select-bank">
                            <SelectValue placeholder="Seleccione banco..." />
                          </SelectTrigger>
                          <SelectContent>
                            {banks.map((bank) => (
                              <SelectItem key={bank.bank_id} value={bank.bank_id}>
                                {bank.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      <div>
                        <Label className="text-sm font-medium text-slate-700 mb-2 flex items-center gap-2">
                          <CreditCard size={16} className="text-brand-green-600" />
                          Medios de Pago
                        </Label>
                        <MultiProductSelector
                          products={availableMediosPago}
                          existingItems={quoteData.additional_items}
                          bankName={banks.find(b => b.bank_id === selectedBankId)?.name || ''}
                          onAdd={addMultipleMediosPago}
                          disabled={!selectedBankId}
                          duplicateKey="product_name"
                          existingKey="medio_pago_name"
                          existingBankKey="bank_name"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* SECCIÓN 3: Matriz de Resumen - Set Up (EXCLUSIVO) - Solo para VPOS/MPOS */}
              {!isPaymentGateway && canShowItems && quoteData.setup_items.length > 0 && (
                <div className="bg-white rounded-lg border mt-4 overflow-hidden">
                  {/* Encabezado Set Up */}
                  <div className="bg-gradient-to-r from-cyan-500 to-cyan-600 text-white text-center py-2 font-semibold">
                    Set Up - Puesta en Marcha (Inversión Inicial)
                  </div>
                  
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse text-sm">
                      <thead>
                        <tr className="bg-slate-100">
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-16">N°</th>
                          <th className="px-3 py-2 text-left font-semibold text-slate-700 border border-slate-300">Concepto</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-24">(VTID)<br/>Cajas</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-24">Bancos o<br/>Entes</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-28">Tarifa Set-up<br/>(USD)</th>
                          <th className="px-3 py-2 text-center font-semibold text-brand-blue-600 border border-slate-300 w-32 bg-blue-50">Total USD</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-16"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {/* Conceptos base de Setup */}
                        {quoteData.setup_items.map((item, index) => (
                          <tr key={`setup-${index}`} className={`${index % 2 === 0 ? 'bg-white' : 'bg-slate-50'} border-l-4 ${item.isCopy ? 'border-l-amber-500' : 'border-l-cyan-500'}`}>
                            <td className="px-3 py-2 text-center font-medium border border-slate-300">{index + 1}</td>
                            <td className="px-3 py-2 border border-slate-300">
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-slate-900">{item.medio_pago_name}</span>
                                {item.isCopy ? (
                                  <span className="px-1.5 py-0.5 text-xs font-medium bg-amber-100 text-amber-700 rounded">Copia</span>
                                ) : (
                                  <span className="px-1.5 py-0.5 text-xs font-medium bg-cyan-100 text-cyan-700 rounded">Base</span>
                                )}
                                {item.lockBancos && <span className="px-1.5 py-0.5 text-xs font-medium bg-slate-200 text-slate-600 rounded">N/A</span>}
                                {item.autoBancos && !item.bancosOverride && <span className="px-1.5 py-0.5 text-xs font-medium bg-purple-100 text-purple-700 rounded">Auto</span>}
                                {item.autoBancos && item.bancosOverride && <span className="px-1.5 py-0.5 text-xs font-medium bg-amber-100 text-amber-700 rounded">Manual</span>}
                              </div>
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Input
                                type="number"
                                min="1"
                                value={item.cantidad_cajas}
                                onChange={(e) => updateSetupItem(index, 'cantidad_cajas', e.target.value)}
                                className="w-16 h-7 text-center text-sm mx-auto"
                              />
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              {item.lockBancos ? (
                                <div className="w-16 h-7 flex items-center justify-center text-sm mx-auto font-medium text-slate-400 bg-slate-100 rounded">
                                  N/A
                                </div>
                              ) : item.autoBancos ? (
                                <div className="flex items-center justify-center gap-1">
                                  {(item.bancosOverride !== undefined && item.bancosOverride !== null) && (
                                    <Unlock size={12} className="text-amber-500" title="Valor editado manualmente (auto-cálculo desactivado)" />
                                  )}
                                  <Input
                                    type="number"
                                    min="1"
                                    value={item.cantidad_bancos}
                                    onChange={(e) => {
                                      const val = parseInt(e.target.value) || 1;
                                      const autoVal = Math.max(1, quoteData.additional_items.length);
                                      if (val === autoVal || e.target.value === '') {
                                        // Si el valor coincide con el auto-cálculo, quitar override
                                        const updatedItems = [...quoteData.setup_items];
                                        updatedItems[index] = { ...updatedItems[index], cantidad_bancos: autoVal, bancosOverride: undefined, totalOverride: undefined };
                                        setQuoteData({ ...quoteData, setup_items: updatedItems });
                                      } else {
                                        const updatedItems = [...quoteData.setup_items];
                                        updatedItems[index] = { ...updatedItems[index], cantidad_bancos: val, bancosOverride: val, totalOverride: undefined };
                                        setQuoteData({ ...quoteData, setup_items: updatedItems });
                                      }
                                    }}
                                    className={`w-16 h-7 text-center text-sm mx-auto ${(item.bancosOverride !== undefined && item.bancosOverride !== null) ? 'border-amber-400 bg-amber-50' : 'border-purple-300 bg-purple-50'}`}
                                    data-testid={`setup-bancos-${index}`}
                                  />
                                </div>
                              ) : (
                                <Input
                                  type="number"
                                  min="1"
                                  value={item.cantidad_bancos}
                                  onChange={(e) => updateSetupItem(index, 'cantidad_bancos', e.target.value)}
                                  className="w-16 h-7 text-center text-sm mx-auto"
                                />
                              )}
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Input
                                type="number"
                                min="0"
                                step="0.01"
                                value={item.tarifa}
                                onChange={(e) => updateSetupItem(index, 'tarifa', e.target.value)}
                                className="w-20 h-7 text-right text-sm mx-auto font-mono"
                              />
                            </td>
                            <td className="px-3 py-2 text-right border border-slate-300 bg-blue-50 font-mono font-semibold text-brand-blue-600">
                              {item.autoBancos ? (
                                <div className="flex items-center justify-end gap-1">
                                  {item.totalOverride !== undefined && item.totalOverride !== null && (
                                    <Unlock size={12} className="text-amber-500" title="Monto editado manualmente" />
                                  )}
                                  <span className="text-sm">$</span>
                                  <Input
                                    type="number"
                                    min="0"
                                    step="0.01"
                                    value={item.totalOverride !== undefined && item.totalOverride !== null ? item.totalOverride : calcularTotalEstandar(item)}
                                    onChange={(e) => {
                                      const val = parseFloat(e.target.value);
                                      const stdTotal = calcularTotalEstandar(item);
                                      if (val === stdTotal || e.target.value === '') {
                                        updateSetupItem(index, 'totalOverride', undefined);
                                      } else {
                                        updateSetupItem(index, 'totalOverride', val || 0);
                                      }
                                    }}
                                    className={`w-24 h-7 text-right text-sm font-mono ${item.totalOverride !== undefined && item.totalOverride !== null ? 'border-amber-400 bg-amber-50' : ''}`}
                                    data-testid={`setup-total-${index}`}
                                  />
                                </div>
                              ) : (
                                <span>${calcularTotal(item).toFixed(2)}</span>
                              )}
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <div className="flex items-center justify-center gap-1">
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => duplicateSetupItem(index)}
                                  className="h-7 w-7 p-0 text-brand-blue-500 hover:text-brand-blue-700 hover:bg-blue-50"
                                  title="Duplicar"
                                >
                                  <Copy size={14} />
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => removeSetupItem(index)}
                                  className="h-7 w-7 p-0 text-red-500 hover:text-red-700 hover:bg-red-50"
                                  title="Eliminar"
                                >
                                  <Trash2 size={14} />
                                </Button>
                              </div>
                            </td>
                          </tr>
                        ))}
                        {/* Items adicionales (medios de pago por banco) */}
                        {quoteData.additional_items.map((item, index) => {
                          const realIndex = index;
                          return (
                          <tr key={`add-setup-${index}`} className="bg-white border-l-4 border-l-amber-500">
                            <td className="px-3 py-2 text-center font-medium border border-slate-300">{quoteData.setup_items.length + index + 1}</td>
                            <td className="px-3 py-2 border border-slate-300">
                              <div className="font-medium text-slate-900">{item.medio_pago_name}</div>
                              <div className="text-xs text-slate-500">{item.bank_name}</div>
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Input
                                type="number"
                                min="1"
                                value={item.cantidad_cajas}
                                onChange={(e) => updateAdditionalItem(realIndex, 'cantidad_cajas', e.target.value)}
                                className="w-16 h-7 text-center text-sm mx-auto"
                              />
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Input
                                type="number"
                                min="1"
                                value={item.cantidad_bancos}
                                onChange={(e) => updateAdditionalItem(realIndex, 'cantidad_bancos', e.target.value)}
                                className="w-16 h-7 text-center text-sm mx-auto"
                              />
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Input
                                type="number"
                                min="0"
                                step="0.01"
                                value={item.tarifa_setup}
                                onChange={(e) => updateAdditionalItem(realIndex, 'tarifa_setup', e.target.value)}
                                className="w-20 h-7 text-right text-sm mx-auto font-mono"
                              />
                            </td>
                            <td className="px-3 py-2 text-right border border-slate-300 bg-blue-50 font-mono font-semibold text-brand-blue-600">
                              {(item.tarifa_setup || 0) > 0
                                ? `$${((item.tarifa_setup || 0) * (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1)).toFixed(2)}`
                                : <span className="text-slate-500 italic text-xs">Incluido</span>}
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => removeAdditionalItem(realIndex)}
                                className="h-7 w-7 p-0 text-red-500 hover:text-red-700 hover:bg-red-50"
                                title="Eliminar"
                              >
                                <Trash2 size={14} />
                              </Button>
                            </td>
                          </tr>
                        )})}
                      </tbody>
                      <tfoot>
                        <tr className="bg-slate-100">
                          <td colSpan={6} className="px-3 py-2 text-right font-semibold border border-slate-300">Subtotal Setup:</td>
                          <td className="px-3 py-2 text-right font-mono font-bold text-brand-blue-600 border border-slate-300 bg-blue-50">${subtotalSetup.toFixed(2)}</td>
                        </tr>
                        <tr className="bg-amber-50">
                          <td colSpan={5} className="px-3 py-2 text-right font-semibold border border-slate-300">Descuento Setup:</td>
                          <td className="px-3 py-2 text-center border border-slate-300">
                            <div className="flex items-center justify-center gap-1">
                              <Input
                                type="number"
                                min="0"
                                max="100"
                                step="0.01"
                                value={quoteData.descuento_setup}
                                onChange={(e) => setQuoteData({ ...quoteData, descuento_setup: parseFloat(e.target.value) || 0 })}
                                className="w-16 h-7 text-right text-sm font-mono"
                                data-testid="descuento-setup-input"
                              />
                              <span className="text-sm">%</span>
                            </div>
                          </td>
                          <td className="px-3 py-2 text-right font-mono font-bold text-amber-600 border border-slate-300">-${montoDescuentoSetup.toFixed(2)}</td>
                          <td></td>
                        </tr>
                        <tr className="bg-cyan-100">
                          <td colSpan={6} className="px-3 py-2 text-right font-bold border border-slate-300">Total Setup Neto:</td>
                          <td className="px-3 py-2 text-right font-mono font-bold text-cyan-700 border border-slate-300 text-lg">${totalNetoSetup.toFixed(2)}</td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>

                  {/* BLOQUE 1: Recurrentes Básicos */}
                  <div className="bg-gradient-to-r from-green-500 to-green-600 text-white text-center py-2 font-semibold mt-4">
                    Costos Recurrentes - Básicos
                  </div>
                  
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse text-sm">
                      <thead>
                        <tr className="bg-slate-100">
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-16">N°</th>
                          <th className="px-3 py-2 text-left font-semibold text-slate-700 border border-slate-300">Concepto</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-24">(VTID)<br/>Cajas</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-24">Bancos o<br/>Entes</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-28">Tarifa Mensual<br/>(USD)</th>
                          <th className="px-3 py-2 text-center font-semibold text-brand-green-600 border border-slate-300 w-32 bg-green-50">Total USD</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-16"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {(quoteData.recurring_basic_items || []).map((item, index) => (
                          <tr key={`rec-basic-${index}`} className={`${index % 2 === 0 ? 'bg-white' : 'bg-slate-50'} border-l-4 ${item.isAutoLinked ? 'border-l-purple-500' : 'border-l-green-500'}`}>
                            <td className="px-3 py-2 text-center font-medium border border-slate-300">{index + 1}</td>
                            <td className="px-3 py-2 border border-slate-300">
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-slate-900">{item.medio_pago_name}</span>
                                {item.isAutoLinked ? (
                                  <span className="px-1.5 py-0.5 text-xs font-medium bg-purple-100 text-purple-700 rounded">Auto</span>
                                ) : (
                                  <span className="px-1.5 py-0.5 text-xs font-medium bg-green-100 text-green-700 rounded">Básico</span>
                                )}
                                {item.lockBancos && <span className="px-1.5 py-0.5 text-xs font-medium bg-slate-200 text-slate-600 rounded">N/A</span>}
                              </div>
                              {item.linkedTo && (
                                <div className="text-xs text-slate-500 mt-1">Vinculado a: {item.linkedTo}</div>
                              )}
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Input
                                type="number"
                                min="1"
                                value={item.cantidad_cajas}
                                onChange={(e) => updateRecurringBasicItem(index, 'cantidad_cajas', e.target.value)}
                                className="w-16 h-7 text-center text-sm mx-auto"
                              />
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              {item.lockBancos ? (
                                <div className="w-16 h-7 flex items-center justify-center text-sm mx-auto font-medium text-slate-400 bg-slate-100 rounded">
                                  N/A
                                </div>
                              ) : (
                                <Input
                                  type="number"
                                  min="1"
                                  value={item.cantidad_bancos}
                                  onChange={(e) => updateRecurringBasicItem(index, 'cantidad_bancos', e.target.value)}
                                  className="w-16 h-7 text-center text-sm mx-auto"
                                />
                              )}
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Input
                                type="number"
                                min="0"
                                step="0.01"
                                value={item.tarifa}
                                onChange={(e) => updateRecurringBasicItem(index, 'tarifa', e.target.value)}
                                className="w-20 h-7 text-right text-sm mx-auto font-mono"
                              />
                            </td>
                            <td className="px-3 py-2 text-right border border-slate-300 bg-green-50 font-mono font-semibold text-brand-green-600">
                              ${calcularTotal(item).toFixed(2)}
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => removeRecurringBasicItem(index)}
                                className="h-7 w-7 p-0 text-red-500 hover:text-red-700 hover:bg-red-50"
                                title="Eliminar"
                              >
                                <Trash2 size={14} />
                              </Button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr className="bg-green-50">
                          <td colSpan={6} className="px-3 py-2 text-right font-semibold border border-slate-300">Subtotal Básicos:</td>
                          <td className="px-3 py-2 text-right font-mono font-bold text-brand-green-600 border border-slate-300">${subtotalRecurringBasic.toFixed(2)}</td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>

                  {/* BLOQUE 2: Otros Recurrentes */}
                  <div className="bg-gradient-to-r from-teal-500 to-teal-600 text-white text-center py-2 font-semibold mt-4">
                    Otros Recurrentes
                  </div>
                  
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse text-sm">
                      <thead>
                        <tr className="bg-slate-100">
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-16">N°</th>
                          <th className="px-3 py-2 text-left font-semibold text-slate-700 border border-slate-300">Concepto</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-24">(VTID)<br/>Cajas</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-24">Bancos o<br/>Entes</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-28">Tarifa Mensual<br/>(USD)</th>
                          <th className="px-3 py-2 text-center font-semibold text-teal-600 border border-slate-300 w-32 bg-teal-50">Total USD</th>
                          <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-16"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {(quoteData.recurring_other_items || []).map((item, index) => (
                          <tr key={`rec-other-${index}`} className={`${index % 2 === 0 ? 'bg-white' : 'bg-slate-50'} border-l-4 border-l-teal-500`}>
                            <td className="px-3 py-2 text-center font-medium border border-slate-300">{index + 1}</td>
                            <td className="px-3 py-2 border border-slate-300">
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-slate-900">{item.medio_pago_name}</span>
                                <span className="px-1.5 py-0.5 text-xs font-medium bg-teal-100 text-teal-700 rounded">Otro</span>
                                {item.lockBancos && <span className="px-1.5 py-0.5 text-xs font-medium bg-slate-200 text-slate-600 rounded">N/A</span>}
                              </div>
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Input
                                type="number"
                                min="1"
                                value={item.cantidad_cajas}
                                onChange={(e) => updateRecurringOtherItem(index, 'cantidad_cajas', e.target.value)}
                                className="w-16 h-7 text-center text-sm mx-auto"
                              />
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              {item.lockBancos ? (
                                <div className="w-16 h-7 flex items-center justify-center text-sm mx-auto font-medium text-slate-400 bg-slate-100 rounded">
                                  N/A
                                </div>
                              ) : (
                                <Input
                                  type="number"
                                  min="1"
                                  value={item.cantidad_bancos}
                                  onChange={(e) => updateRecurringOtherItem(index, 'cantidad_bancos', e.target.value)}
                                  className="w-16 h-7 text-center text-sm mx-auto"
                                />
                              )}
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Input
                                type="number"
                                min="0"
                                step="0.01"
                                value={item.tarifa}
                                onChange={(e) => updateRecurringOtherItem(index, 'tarifa', e.target.value)}
                                className={`w-20 h-7 text-right text-sm mx-auto font-mono ${(!item.tarifa || item.tarifa === 0) ? 'border-amber-400 bg-amber-50' : ''}`}
                                placeholder="0.00"
                              />
                              {(!item.tarifa || item.tarifa === 0) && (
                                <p className="text-xs text-amber-600 mt-1">Configurar</p>
                              )}
                            </td>
                            <td className="px-3 py-2 text-right border border-slate-300 bg-teal-50 font-mono font-semibold text-teal-600">
                              ${calcularTotal(item).toFixed(2)}
                            </td>
                            <td className="px-3 py-2 text-center border border-slate-300">
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => removeRecurringOtherItem(index)}
                                className="h-7 w-7 p-0 text-red-500 hover:text-red-700 hover:bg-red-50"
                                title="Eliminar"
                              >
                                <Trash2 size={14} />
                              </Button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr className="bg-teal-50">
                          <td colSpan={6} className="px-3 py-2 text-right font-semibold border border-slate-300">Subtotal Otros:</td>
                          <td className="px-3 py-2 text-right font-mono font-bold text-teal-600 border border-slate-300">${subtotalRecurringOther.toFixed(2)}</td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>

                  {/* Resumen Total Recurrentes */}
                  <div className="overflow-x-auto mt-4">
                    <table className="w-full border-collapse text-sm">
                      <tfoot>
                        <tr className="bg-slate-100">
                          <td colSpan={6} className="px-3 py-2 text-right font-semibold border border-slate-300">SUBTOTAL RECURRENTES:</td>
                          <td className="px-3 py-2 text-right font-mono font-bold text-brand-green-600 border border-slate-300 bg-green-50 w-32">${subtotalRecurrente.toFixed(2)}</td>
                        </tr>
                        <tr className="bg-amber-50">
                          <td colSpan={5} className="px-3 py-2 text-right font-semibold border border-slate-300">Descuento Recurrente:</td>
                          <td className="px-3 py-2 text-center border border-slate-300">
                            <div className="flex items-center justify-center gap-1">
                              <Input
                                type="number"
                                min="0"
                                max="100"
                                step="0.01"
                                value={quoteData.descuento_recurrente}
                                onChange={(e) => setQuoteData({ ...quoteData, descuento_recurrente: parseFloat(e.target.value) || 0 })}
                                className="w-16 h-7 text-right text-sm font-mono"
                                data-testid="descuento-recurrente-input"
                              />
                              <span className="text-sm">%</span>
                            </div>
                          </td>
                          <td className="px-3 py-2 text-right font-mono font-bold text-amber-600 border border-slate-300 w-32">-${montoDescuentoRecurrente.toFixed(2)}</td>
                        </tr>
                        <tr className="bg-green-100">
                          <td colSpan={6} className="px-3 py-2 text-right font-bold border border-slate-300">TOTAL RECURRENTE NETO:</td>
                          <td className="px-3 py-2 text-right font-mono font-bold text-brand-green-700 border border-slate-300 text-lg w-32">${totalNetoRecurrente.toFixed(2)}</td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>

                  {/* SECCIÓN: Cliente en Producción */}
                  <div className="mt-4 bg-white rounded-lg border border-orange-200 overflow-hidden" data-testid="production-client-section">
                    <div className="bg-gradient-to-r from-orange-500 to-orange-600 text-white px-4 py-2.5 flex items-center justify-between">
                      <span className="font-semibold">Cliente en Producción</span>
                    </div>
                    <div className="p-4">
                      <div className="flex items-center gap-4 mb-3">
                        <span className="text-sm font-medium text-slate-700">¿Este cliente ya se encuentra en producción?</span>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant={isProductionClient ? 'default' : 'outline'}
                            onClick={() => setIsProductionClient(true)}
                            className={`h-8 px-4 ${isProductionClient ? 'bg-orange-600 hover:bg-orange-700' : ''}`}
                            data-testid="production-client-yes"
                          >
                            Sí
                          </Button>
                          <Button
                            size="sm"
                            variant={!isProductionClient ? 'default' : 'outline'}
                            onClick={() => { setIsProductionClient(false); setProductionItems([]); }}
                            className={`h-8 px-4 ${!isProductionClient ? 'bg-slate-600 hover:bg-slate-700' : ''}`}
                            data-testid="production-client-no"
                          >
                            No
                          </Button>
                        </div>
                      </div>

                      {isProductionClient && (
                        <div className="space-y-3 mt-3 pt-3 border-t border-orange-100">
                          <p className="text-xs text-slate-500">Seleccione conceptos recurrentes adicionales que apliquen para este cliente en producción.</p>
                          
                          {/* Selector de servicio recurrente */}
                          <div className="flex items-end gap-2">
                            <div className="flex-1">
                              <Label className="text-xs font-medium text-slate-600 mb-1 block">Concepto Recurrente</Label>
                              <Select value={productionSelectedServiceId} onValueChange={setProductionSelectedServiceId}>
                                <SelectTrigger className="h-9" data-testid="production-service-select">
                                  <SelectValue placeholder="Seleccionar concepto..." />
                                </SelectTrigger>
                                <SelectContent>
                                  {serviceCatalog
                                    .filter(s => s.application_type === 'recurring' || s.application_type === 'both')
                                    .filter(s => !productionItems.find(pi => pi.service_id === s.service_id))
                                    .map(s => (
                                      <SelectItem key={s.service_id} value={s.service_id}>
                                        {s.name}
                                      </SelectItem>
                                    ))
                                  }
                                </SelectContent>
                              </Select>
                            </div>
                            <Button
                              size="sm"
                              className="h-9 bg-orange-600 hover:bg-orange-700"
                              disabled={!productionSelectedServiceId}
                              data-testid="production-add-btn"
                              onClick={() => {
                                const service = serviceCatalog.find(s => s.service_id === productionSelectedServiceId);
                                if (!service) return;
                                const isOutsourcing = quoteData.pricing_model === 'outsourcing';
                                const tarifa = isOutsourcing ? (service.monthly_cost_outsourcing || 0) : (service.monthly_cost_conventional || 0);
                                setProductionItems([...productionItems, {
                                  id: `prod_${Date.now()}`,
                                  service_id: service.service_id,
                                  medio_pago_name: service.name,
                                  cantidad_cajas: quoteData.cantidad_cajas || 1,
                                  cantidad_bancos: quoteData.cantidad_bancos || 1,
                                  tarifa: tarifa,
                                  type: 'production_recurring'
                                }]);
                                setProductionSelectedServiceId('');
                              }}
                            >
                              <Plus size={14} className="mr-1" /> Agregar
                            </Button>
                          </div>

                          {/* Tabla de items de producción */}
                          {productionItems.length > 0 && (
                            <div className="overflow-x-auto">
                              <table className="w-full border-collapse text-sm">
                                <thead>
                                  <tr className="bg-orange-50">
                                    <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-16">N°</th>
                                    <th className="px-3 py-2 text-left font-semibold text-slate-700 border border-slate-300">Concepto</th>
                                    <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-24">Cajas</th>
                                    <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-24">Bancos</th>
                                    <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-28">Tarifa (USD)</th>
                                    <th className="px-3 py-2 text-center font-semibold text-orange-600 border border-slate-300 w-32 bg-orange-50">Total USD</th>
                                    <th className="px-3 py-2 text-center font-semibold text-slate-700 border border-slate-300 w-12"></th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {productionItems.map((item, idx) => (
                                    <tr key={item.id} className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                                      <td className="px-3 py-2 text-center font-medium border border-slate-300">{idx + 1}</td>
                                      <td className="px-3 py-2 border border-slate-300 font-medium text-slate-900">{item.medio_pago_name}</td>
                                      <td className="px-3 py-2 text-center border border-slate-300">
                                        <Input
                                          type="number" min="1" value={item.cantidad_cajas}
                                          onChange={(e) => {
                                            const updated = [...productionItems];
                                            updated[idx] = { ...updated[idx], cantidad_cajas: parseInt(e.target.value) || 1 };
                                            setProductionItems(updated);
                                          }}
                                          className="w-16 h-7 text-center text-sm mx-auto"
                                          data-testid={`production-cajas-${idx}`}
                                        />
                                      </td>
                                      <td className="px-3 py-2 text-center border border-slate-300">
                                        <Input
                                          type="number" min="1" value={item.cantidad_bancos}
                                          onChange={(e) => {
                                            const updated = [...productionItems];
                                            updated[idx] = { ...updated[idx], cantidad_bancos: parseInt(e.target.value) || 1 };
                                            setProductionItems(updated);
                                          }}
                                          className="w-16 h-7 text-center text-sm mx-auto"
                                          data-testid={`production-bancos-${idx}`}
                                        />
                                      </td>
                                      <td className="px-3 py-2 text-center border border-slate-300">
                                        <Input
                                          type="number" min="0" step="0.01" value={item.tarifa}
                                          onChange={(e) => {
                                            const updated = [...productionItems];
                                            updated[idx] = { ...updated[idx], tarifa: parseFloat(e.target.value) || 0 };
                                            setProductionItems(updated);
                                          }}
                                          className="w-20 h-7 text-right text-sm mx-auto font-mono"
                                          data-testid={`production-tarifa-${idx}`}
                                        />
                                      </td>
                                      <td className="px-3 py-2 text-right border border-slate-300 bg-orange-50 font-mono font-semibold text-orange-600">
                                        ${((item.tarifa || 0) * (item.cantidad_cajas || 1) * (item.cantidad_bancos || 1)).toFixed(2)}
                                      </td>
                                      <td className="px-3 py-2 text-center border border-slate-300">
                                        <Button
                                          size="sm" variant="ghost"
                                          onClick={() => setProductionItems(productionItems.filter((_, i) => i !== idx))}
                                          className="h-7 w-7 p-0 text-red-500 hover:text-red-700 hover:bg-red-50"
                                          data-testid={`production-remove-${idx}`}
                                        >
                                          <Trash2 size={14} />
                                        </Button>
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                                <tfoot>
                                  <tr className="bg-orange-50">
                                    <td colSpan={5} className="px-3 py-2 text-right font-semibold border border-slate-300">Subtotal Producción:</td>
                                    <td className="px-3 py-2 text-right font-mono font-bold text-orange-600 border border-slate-300">${subtotalProduction.toFixed(2)}</td>
                                    <td className="border border-slate-300"></td>
                                  </tr>
                                </tfoot>
                              </table>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Resumen General */}
                  <div className="bg-slate-900 text-white p-4 mt-4 rounded-b-lg" data-testid="grand-total-section">
                    <div className="space-y-1.5">
                      <div className="flex justify-between items-center text-slate-300 text-sm">
                        <span>Implementación (Servicios)</span>
                        <span className="font-mono">${(totalNetoSetup + totalNetoRecurrente).toFixed(2)}</span>
                      </div>
                      {ftHardwareSubtotal > 0 && (
                        <div className="flex justify-between items-center text-slate-300 text-sm">
                          <span>Equipos (Hardware)</span>
                          <span className="font-mono">${ftHardwareSubtotal.toFixed(2)}</span>
                        </div>
                      )}
                      <div className="border-t border-slate-700 pt-2 flex justify-between items-center">
                        <span className="text-lg font-semibold">TOTAL GENERAL{ftHardwareSubtotal > 0 ? ' (Servicios + Hardware)' : ' (Setup + Recurrente)'}</span>
                        <span className="text-2xl font-bold font-mono">${grandTotal.toFixed(2)} USD</span>
                      </div>
                    </div>
                  </div>

                  {/* SECCIÓN: Resumen Ejecutivo - Matriz de Distribución */}
                  <div className="mt-6 bg-white rounded-lg border border-slate-200 overflow-hidden" data-testid="executive-summary">
                    <div className="bg-slate-100 px-4 py-3 border-b border-slate-200">
                      <h3 className="font-semibold text-lg text-slate-800">Resumen Ejecutivo</h3>
                    </div>
                    
                    {/* Cabecera del Resumen */}
                    <div className="p-4 space-y-3">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="flex">
                          <span className="bg-amber-400 text-slate-900 px-3 py-2 font-semibold text-sm min-w-[140px]">Cliente</span>
                          <span className="bg-white border border-slate-200 px-3 py-2 flex-1 text-slate-900 font-medium">
                            {selectedClient?.legal_name || selectedClient?.fantasy_name || 'N/A'}
                          </span>
                        </div>
                        <div className="flex">
                          <span className="bg-blue-200 text-slate-900 px-3 py-2 font-semibold text-sm min-w-[140px]">Cantidad de Cajas</span>
                          <span className="bg-white border border-slate-200 px-3 py-2 flex-1 text-slate-900 font-medium">
                            {quoteData.cantidad_cajas}
                          </span>
                        </div>
                      </div>
                      
                      <div className="flex">
                        <span className="bg-green-200 text-slate-900 px-3 py-2 font-semibold text-sm min-w-[140px]">Dirección Fiscal</span>
                        <span className="bg-white border border-slate-200 px-3 py-2 flex-1 text-slate-700">
                          {selectedClient?.address || 'No especificada'}
                        </span>
                      </div>
                    </div>

                    {/* Matriz de Distribución - Bancos/Productos/Cajas */}
                    <div className="px-4 pb-4">
                      <table className="w-full border-collapse">
                        <thead>
                          <tr>
                            <th className="bg-green-200 text-slate-900 px-4 py-2 text-left font-semibold border border-slate-200">Bancos</th>
                            <th className="bg-blue-200 text-slate-900 px-4 py-2 text-left font-semibold border border-slate-200">Productos</th>
                            <th className="bg-amber-400 text-slate-900 px-4 py-2 text-center font-semibold border border-slate-200 w-32">Cantidad de Cajas</th>
                          </tr>
                        </thead>
                        <tbody>
                          {/* Agrupar items por banco - SOLO medios de pago con banco (excluir conceptos base) */}
                          {(() => {
                            // Consolidar solo additional_items que tienen bank_name (medios de pago por banco)
                            const bankProductMap = {};
                            quoteData.additional_items
                              .filter(item => item.bank_name) // Solo items con banco asociado
                              .forEach(item => {
                                const bankName = item.bank_name;
                                const productName = item.medio_pago_name || 'Producto';
                                const key = `${bankName}-${productName}`;
                                
                                if (!bankProductMap[key]) {
                                  bankProductMap[key] = {
                                    bank: bankName,
                                    product: productName,
                                    cajas: 0
                                  };
                                }
                                bankProductMap[key].cajas += item.cantidad_cajas || 1;
                              });
                            
                            const rows = Object.values(bankProductMap);
                            
                            if (rows.length === 0) {
                              return (
                                <tr>
                                  <td colSpan={3} className="px-4 py-3 text-center text-slate-500 italic border border-slate-200">
                                    No hay medios de pago seleccionados
                                  </td>
                                </tr>
                              );
                            }
                            
                            return rows.map((row, idx) => (
                              <tr key={idx} className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                                <td className="px-4 py-2 border border-slate-200 text-slate-900">{row.bank}</td>
                                <td className="px-4 py-2 border border-slate-200 text-slate-700">{row.product}</td>
                                <td className="px-4 py-2 border border-slate-200 text-center font-medium text-slate-900">{row.cajas}</td>
                              </tr>
                            ));
                          })()}
                        </tbody>
                      </table>
                    </div>

                    {/* Total de Terminales Virtuales */}
                    <div className="border-t-2 border-slate-400 px-4 py-3 flex justify-between items-center bg-slate-50">
                      <span className="font-semibold text-slate-800">Total de Terminales Virtuales</span>
                      <span className="font-bold text-xl text-slate-900">
                        {(() => {
                          // Sumar cajas solo de medios de pago con banco (excluir conceptos base)
                          const total = quoteData.additional_items
                            .filter(item => item.bank_name)
                            .reduce((sum, item) => sum + (item.cantidad_cajas || 1), 0);
                          return total || quoteData.cantidad_cajas;
                        })()}
                      </span>
                    </div>
                  </div>

                  {/* Notas y Botón Finalizar */}
                  <div className="p-4">
                    <Label htmlFor="notes" className="text-sm font-medium text-slate-700">Notas adicionales</Label>
                    <Textarea
                      id="notes"
                      value={quoteData.notes}
                      onChange={(e) => setQuoteData({ ...quoteData, notes: e.target.value })}
                      placeholder="Observaciones o condiciones especiales..."
                      rows={2}
                      className="mt-2"
                    />

                    {/* Detalle de Sucursales (opcional para VPOS/MPOS/Fast Track) */}
                    {(quoteData.quote_type === 'VPOS' || isMPOS || isFastTrackType) && (
                      <BranchDetailPanel
                        branches={branchDetails}
                        onChange={setBranchDetails}
                        totalEquipment={parseInt(quoteData.cantidad_cajas) || 1}
                      />
                    )}

                    {/* Toggle: Incluir Costos Recurrentes en PDF (no aplica para PG) */}
                    {!isPaymentGateway && (
                      <div className="mt-4 p-3 bg-slate-50 rounded-lg border border-slate-200">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm font-medium text-slate-700">Incluir Costos Recurrentes en el PDF</p>
                            <p className="text-xs text-slate-500">Si selecciona "No", se omitira la seccion de costos recurrentes del documento</p>
                          </div>
                          <div className="flex items-center gap-3">
                            <button
                              type="button"
                              onClick={() => setQuoteData({ ...quoteData, include_recurring: true })}
                              className={`px-3 py-1 rounded text-xs font-semibold transition ${quoteData.include_recurring !== false ? 'bg-green-600 text-white' : 'bg-slate-200 text-slate-500'}`}
                              data-testid="include-recurring-yes"
                            >Si</button>
                            <button
                              type="button"
                              onClick={() => setQuoteData({ ...quoteData, include_recurring: false })}
                              className={`px-3 py-1 rounded text-xs font-semibold transition ${quoteData.include_recurring === false ? 'bg-red-600 text-white' : 'bg-slate-200 text-slate-500'}`}
                              data-testid="include-recurring-no"
                            >No</button>
                          </div>
                        </div>
                        {quoteData.include_recurring === false && (
                          <p className="mt-2 text-xs text-blue-600 italic">El PDF no incluira la seccion de Costos Recurrentes Mensuales ni su total en el Resumen de Inversion.</p>
                        )}
                      </div>
                    )}

                    <div className="mt-4 flex justify-end gap-3">
                      <Button
                        onClick={previewCurrentQuotePDF}
                        variant="outline"
                        disabled={pdfPreviewLoading}
                        className="border-slate-400 text-slate-600 hover:bg-slate-50 px-5 py-3 text-base"
                        data-testid="preview-pdf-button"
                      >
                        <Eye size={18} className="mr-2" />
                        {pdfPreviewLoading ? 'Generando...' : 'Previsualizar PDF'}
                      </Button>
                      <Button
                        onClick={exportCurrentQuoteToPDF}
                        variant="outline"
                        className="border-brand-blue-600 text-brand-blue-600 hover:bg-brand-blue-50 px-5 py-3 text-base"
                        data-testid="export-pdf-button"
                      >
                        <Download size={18} className="mr-2" />
                        Exportar PDF
                      </Button>
                      <Button
                        onClick={handleSubmitQuote}
                        className="bg-brand-green-600 hover:bg-brand-green-700 text-white px-6 py-3 text-base"
                        data-testid="submit-quote-button"
                      >
                        <CheckCircle2 size={18} className="mr-2" />
                        Guardar Cotización
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {/* Botones de acción para Payment Gateway */}
              {isPaymentGateway && isHeaderComplete && pgSetupItems.length > 0 && (
                <div className="bg-white rounded-lg p-5 border mt-4">
                  <Label htmlFor="pg-notes" className="text-sm font-medium text-slate-700">Notas adicionales</Label>
                  <Textarea
                    id="pg-notes"
                    value={quoteData.notes}
                    onChange={(e) => setQuoteData({ ...quoteData, notes: e.target.value })}
                    placeholder="Observaciones o condiciones especiales..."
                    rows={2}
                    className="mt-2"
                    data-testid="pg-notes-input"
                  />
                  <div className="mt-4 flex justify-end gap-3">
                    <Button
                      onClick={previewCurrentQuotePDF}
                      variant="outline"
                      disabled={pdfPreviewLoading}
                      className="border-slate-400 text-slate-600 hover:bg-slate-50 px-5 py-3 text-base"
                      data-testid="pg-preview-pdf-button"
                    >
                      <Eye size={18} className="mr-2" />
                      {pdfPreviewLoading ? 'Generando...' : 'Previsualizar PDF'}
                    </Button>
                    <Button
                      onClick={exportCurrentQuoteToPDF}
                      variant="outline"
                      className="border-brand-blue-600 text-brand-blue-600 hover:bg-brand-blue-50 px-5 py-3 text-base"
                      data-testid="pg-export-pdf-button"
                    >
                      <Download size={18} className="mr-2" />
                      Exportar PDF
                    </Button>
                    <Button
                      onClick={handleSubmitPGQuote}
                      className="bg-emerald-600 hover:bg-emerald-700 text-white px-6 py-3 text-base"
                      data-testid="pg-submit-quote-button"
                    >
                      <CheckCircle2 size={18} className="mr-2" />
                      Guardar Cotización PG
                    </Button>
                  </div>
                </div>
              )}

              {/* Mensaje cuando no hay items - Solo para VPOS/MPOS */}
              {!isPaymentGateway && canShowItems && quoteData.setup_items.length === 0 && (
                <div className="text-center py-8 text-slate-500 bg-slate-50 rounded-lg mt-4 border-2 border-dashed">
                  <CreditCard size={40} className="mx-auto mb-3 text-slate-300" />
                  <p className="font-medium">No hay medios de pago agregados</p>
                  <p className="text-sm mt-1">Seleccione un banco y medio de pago para comenzar</p>
                </div>
              )}
            </DialogContent>
          </Dialog>
  );
};
