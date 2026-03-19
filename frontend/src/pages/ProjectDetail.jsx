import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import api from '../utils/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { toast } from 'sonner';
import {
  ArrowLeft, CreditCard, Building2, CheckCircle2, Circle, Clock,
  FileText, Send, Calendar, User, Store, Bell, BellRing, Lock, BarChart3, Mail,
  Plus, X, Paperclip, Image, Ticket
} from 'lucide-react';

const PHASES = ['Notificado', 'Recibido', 'Configurado', 'Testeado', 'En Producción'];
const STORE_PHASES = ['Recibido', 'Configurado', 'Testeado', 'En Producción'];
const PHASE_COLORS = {
  'Notificado': 'bg-lime-100 text-lime-800 border-lime-300',
  'Recibido': 'bg-sky-100 text-sky-800 border-sky-300',
  'Configurado': 'bg-violet-100 text-violet-800 border-violet-300',
  'Testeado': 'bg-cyan-100 text-cyan-800 border-cyan-300',
  'En Producción': 'bg-emerald-100 text-emerald-800 border-emerald-300',
};

const ProjectDetail = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [bitacoraText, setBitacoraText] = useState('');
  const [bitacoraDate, setBitacoraDate] = useState(new Date().toISOString().split('T')[0]);
  const [bitacoraSubmitting, setBitacoraSubmitting] = useState(false);
  const [selectedStoreId, setSelectedStoreId] = useState(null);
  const [notifyingClient, setNotifyingClient] = useState(false);
  const [notifyingBank, setNotifyingBank] = useState(null);

  // Email Ad-hoc
  const [emailDialogOpen, setEmailDialogOpen] = useState(false);
  const [emailForm, setEmailForm] = useState({ recipients: [''], subject: '', message: '' });
  const [emailFiles, setEmailFiles] = useState([]);
  const [emailSending, setEmailSending] = useState(false);
  const fileInputRef = useRef(null);

  const fetchProject = useCallback(async () => {
    try {
      const res = await api.get(`/projects/${projectId}`);
      setProject(res.data);
    } catch { toast.error('Error al cargar proyecto'); }
    finally { setLoading(false); }
  }, [projectId]);

  useEffect(() => { fetchProject(); }, [fetchProject]);

  const togglePhase = async (bankName, productName, phase, currentlyCompleted) => {
    try {
      await api.put(`/projects/${projectId}/matrix/phase`, {
        bank_name: bankName, product_name: productName, phase, completed: !currentlyCompleted
      });
      fetchProject();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error actualizando fase');
    }
  };

  const toggleStorePhase = async (storeId, bankName, productName, phase, currentlyCompleted) => {
    try {
      await api.put(`/projects/${projectId}/stores/${storeId}/matrix/phase`, {
        bank_name: bankName, product_name: productName, phase, completed: !currentlyCompleted
      });
      fetchProject();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error actualizando fase de tienda');
    }
  };

  const handleNotifyClient = async () => {
    setNotifyingClient(true);
    try {
      const res = await api.post(`/projects/${projectId}/notify-client`);
      toast.success(res.data.message);
      fetchProject();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al notificar cliente');
    } finally { setNotifyingClient(false); }
  };

  const handleNotifyBank = async (bankName) => {
    setNotifyingBank(bankName);
    try {
      const res = await api.post(`/projects/${projectId}/notify-bank`, { bank_name: bankName });
      toast.success(res.data.message);
      fetchProject();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al notificar banco');
    } finally { setNotifyingBank(null); }
  };

  const handleAddBitacora = async () => {
    setBitacoraSubmitting(true);
    try {
      await api.post(`/projects/${projectId}/bitacora`, { text: bitacoraText, execution_date: bitacoraDate });
      toast.success('Entrada registrada');
      setBitacoraText('');
      fetchProject();
    } catch { toast.error('Error al registrar entrada'); }
    finally { setBitacoraSubmitting(false); }
  };

  // ==================== EMAIL AD-HOC ====================
  const openEmailDialog = () => {
    setEmailForm({ recipients: [''], subject: '', message: '' });
    setEmailFiles([]);
    setEmailDialogOpen(true);
  };

  const addRecipient = () => setEmailForm(prev => ({ ...prev, recipients: [...prev.recipients, ''] }));
  const removeRecipient = (idx) => setEmailForm(prev => ({ ...prev, recipients: prev.recipients.filter((_, i) => i !== idx) }));
  const updateRecipient = (idx, val) => setEmailForm(prev => {
    const r = [...prev.recipients];
    r[idx] = val;
    return { ...prev, recipients: r };
  });

  const handleFileSelect = (e) => {
    const newFiles = Array.from(e.target.files || []);
    setEmailFiles(prev => [...prev, ...newFiles]);
  };
  const removeFile = (idx) => setEmailFiles(prev => prev.filter((_, i) => i !== idx));

  const handleSendAdhocEmail = async () => {
    const validRecipients = emailForm.recipients.filter(r => r.trim());
    if (validRecipients.length === 0) { toast.error('Agregue al menos un destinatario'); return; }
    if (!emailForm.subject.trim()) { toast.error('El asunto es obligatorio'); return; }
    if (!emailForm.message.trim()) { toast.error('El mensaje es obligatorio'); return; }
    if (emailForm.message.length > 500) { toast.error('El mensaje no puede exceder 500 caracteres'); return; }

    setEmailSending(true);
    try {
      const formData = new FormData();
      formData.append('recipients', JSON.stringify(validRecipients));
      formData.append('subject', emailForm.subject);
      formData.append('message', emailForm.message);
      emailFiles.forEach(f => formData.append('files', f));

      const res = await api.post(`/projects/${projectId}/send-adhoc-email`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      toast.success(res.data.message);
      setEmailDialogOpen(false);
      fetchProject();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al enviar correo');
    } finally { setEmailSending(false); }
  };

  if (loading || !project) {
    return (
      <div className="flex min-h-screen bg-white">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-green-600" />
        </div>
      </div>
    );
  }

  const isMultistore = project.project_type === 'multistore';
  const clientNotified = project.client_notified === true;
  const bankNotifications = project.bank_notifications || {};
  const matrix = project.implementation_matrix || {};
  const bankNames = Object.keys(matrix);
  const rollup = project.rollup_progress || {};

  // Fases según tipo de proyecto para tiendas
  const activePhasesForStores = STORE_PHASES;

  // Calcular progreso por tienda en frontend (para tabs)
  const calcStoreProgress = (store) => {
    const sm = store.implementation_matrix || {};
    let completed = 0, total = 0;
    Object.values(sm).forEach(products => {
      Object.values(products).forEach(phases => {
        activePhasesForStores.forEach(p => {
          total++;
          if (phases[p]?.completed) completed++;
        });
      });
    });
    return total > 0 ? Math.round((completed / total) * 100) : 0;
  };

  return (
    <div className="flex min-h-screen bg-white">
      <Sidebar />
      <main className="flex-1 p-8" data-testid="project-detail-page">
        <div className="max-w-7xl mx-auto">
          {/* Back + Header */}
          <Button variant="ghost" onClick={() => navigate('/projects')} className="mb-4 text-slate-600">
            <ArrowLeft size={16} className="mr-2" />Volver a Proyectos
          </Button>

          <div className="bg-slate-50 border border-slate-200 rounded-xl p-6 mb-6">
            <div className="flex items-start justify-between">
              <div>
                <h1 className="text-2xl font-bold text-slate-900 mb-1" data-testid="project-title">
                  Detalle para Implementación del Proyecto
                </h1>
                <div className="flex items-center gap-3">
                  {project.ticket_number ? (
                    <p className="text-lg font-semibold text-indigo-700 flex items-center gap-2" data-testid="project-ticket">
                      <Ticket size={18} className="text-indigo-500" />{project.ticket_number}
                      <span className="text-sm text-slate-400 font-normal">({project.project_number})</span>
                    </p>
                  ) : (
                    <p className="text-lg font-semibold text-slate-700">{project.project_number}</p>
                  )}
                </div>
                <p className="text-sm text-slate-500">{project.client_name} — {project.client_rif} — {project.client_sede}</p>
              </div>
              <div className="text-right space-y-1">
                <span className={`inline-block px-3 py-1 rounded-full text-sm font-medium border ${
                  project.status === 'Pendiente por Asignar' ? 'bg-amber-100 text-amber-800 border-amber-200' :
                  project.status === 'Asignado / En Proceso' ? 'bg-blue-100 text-blue-800 border-blue-200' :
                  project.status === 'Detenido por Cliente/Banco' ? 'bg-red-100 text-red-800 border-red-200' :
                  'bg-emerald-100 text-emerald-800 border-emerald-200'
                }`}>{project.status}</span>
                {project.assigned_to_name && (
                  <p className="text-sm text-slate-500">Implementador: <strong>{project.assigned_to_name}</strong></p>
                )}
                {isMultistore && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-semibold rounded bg-blue-100 text-blue-700 border border-blue-200">
                    <Store size={12} />Multitienda ({project.stores?.length || 0})
                  </span>
                )}
                {/* Progreso global */}
                {rollup.global_progress !== undefined && (
                  <div className="flex items-center gap-2 justify-end mt-1">
                    <div className="w-24 bg-slate-100 rounded-full h-2 overflow-hidden">
                      <div className={`h-full rounded-full ${rollup.global_progress >= 100 ? 'bg-emerald-500' : rollup.global_progress >= 50 ? 'bg-blue-500' : 'bg-amber-400'}`}
                        style={{ width: `${Math.min(rollup.global_progress, 100)}%` }} />
                    </div>
                    <span className="text-xs font-bold text-slate-600" data-testid="header-progress">{rollup.global_progress}%</span>
                  </div>
                )}
                {/* Botón Email Ad-hoc */}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={openEmailDialog}
                  className="mt-1 text-xs gap-1.5 border-indigo-200 text-indigo-600 hover:bg-indigo-50"
                  data-testid="adhoc-email-btn"
                >
                  <Mail size={14} />Enviar Correo
                </Button>
              </div>
            </div>

            {/* Technical Header */}
            <div className="grid grid-cols-2 gap-4 mt-4 pt-4 border-t border-slate-200">
              <div className="flex items-center gap-3 bg-white rounded-lg p-3 border border-slate-200">
                <CreditCard size={20} className="text-emerald-600" />
                <div>
                  <p className="text-xs text-slate-500 uppercase font-medium">Modelo de Pinpad</p>
                  <p className="text-sm font-semibold text-slate-800" data-testid="pinpad-model">{project.pinpad_model || '—'}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 bg-white rounded-lg p-3 border border-slate-200">
                <Building2 size={20} className="text-blue-600" />
                <div>
                  <p className="text-xs text-slate-500 uppercase font-medium">Banco Patrocinador</p>
                  <p className="text-sm font-semibold text-slate-800" data-testid="sponsor-bank">{project.sponsor_bank_name || '—'}</p>
                </div>
              </div>
            </div>
          </div>

          {/* ============ NOTIFICATION SECTION (HITO 1 + HITO 2) ============ */}
          <div className="mb-6">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-bold text-slate-900">Matriz de Implementación</h2>
              {/* Botón Notificar Cliente (Hito 1 - Fase Cero) */}
              {!clientNotified ? (
                <Button
                  onClick={handleNotifyClient}
                  disabled={notifyingClient}
                  className="bg-amber-500 hover:bg-amber-600 text-white gap-2"
                  data-testid="notify-client-btn"
                >
                  <Bell size={16} />
                  {notifyingClient ? 'Notificando...' : 'Notificar Cliente'}
                </Button>
              ) : (
                <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-50 border border-emerald-200 rounded-lg" data-testid="client-notified-badge">
                  <BellRing size={16} className="text-emerald-600" />
                  <span className="text-sm font-medium text-emerald-700">Cliente Notificado</span>
                  <span className="text-xs text-emerald-500">{project.client_notified_at ? new Date(project.client_notified_at).toLocaleDateString('es-VE') : ''}</span>
                </div>
              )}
            </div>

            {/* Hard Stop overlay if client not notified */}
            {!clientNotified && (
              <div className="bg-slate-50 border-2 border-dashed border-slate-300 rounded-xl p-10 text-center" data-testid="matrix-locked">
                <Lock size={40} className="mx-auto text-slate-300 mb-3" />
                <p className="text-sm font-semibold text-slate-500">Matriz Bloqueada</p>
                <p className="text-xs text-slate-400 mt-1">Debe notificar al cliente primero para desbloquear la matriz de seguimiento</p>
              </div>
            )}

            {/* ============ MAIN MATRIX (only when client notified) ============ */}
            {clientNotified && (
              <>
                {isMultistore ? (
                  <div className="mb-3 bg-blue-50 border border-blue-200 rounded-lg p-3">
                    <div className="flex items-center justify-between">
                      <p className="text-sm text-blue-800 font-medium flex items-center gap-2">
                        <Store size={16} className="text-blue-600" />
                        Proyecto Multitienda — Matriz principal de solo lectura (avance automático)
                      </p>
                      {rollup.global_progress !== undefined && (
                        <span className="text-sm font-bold text-blue-900" data-testid="rollup-global-progress">
                          <BarChart3 size={14} className="inline mr-1" />
                          Avance Global: {rollup.global_progress}%
                        </span>
                      )}
                    </div>
                  </div>
                ) : (
                  rollup.global_progress !== undefined && rollup.global_progress > 0 && (
                    <div className="mb-3 bg-emerald-50 border border-emerald-200 rounded-lg p-3">
                      <div className="flex items-center justify-between">
                        <p className="text-sm text-emerald-800 font-medium flex items-center gap-2">
                          <BarChart3 size={16} className="text-emerald-600" />
                          Avance de Implementación
                        </p>
                        <span className="text-sm font-bold text-emerald-900" data-testid="single-progress">
                          {rollup.global_progress}%
                        </span>
                      </div>
                    </div>
                  )
                )}

                {bankNames.length === 0 ? (
                  <div className="text-center py-10 bg-slate-50 rounded-lg border">
                    <p className="text-slate-400">No hay datos en la matriz de implementación</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto rounded-lg border border-slate-200">
                    <table className="w-full" data-testid="implementation-matrix">
                      <thead>
                        <tr>
                          <th className="bg-blue-600 text-white px-4 py-3 text-left text-sm font-semibold min-w-[200px]">
                            Bancos / Productos
                          </th>
                          {isMultistore ? (
                            <th className="bg-blue-600 text-white px-4 py-3 text-center text-sm font-semibold min-w-[300px]" colSpan={1}>
                              Avance (Roll-up)
                            </th>
                          ) : (
                            PHASES.map(phase => (
                              <th key={phase} className={`px-3 py-3 text-center text-xs font-semibold border-l border-slate-200 min-w-[110px] ${PHASE_COLORS[phase]}`}>
                                {phase}
                              </th>
                            ))
                          )}
                          <th className="bg-blue-600 text-white px-3 py-3 text-center text-xs font-semibold border-l border-slate-200 min-w-[140px]">
                            {isMultistore ? 'Notificar' : 'Notas'}
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {bankNames.map(bankName => {
                          const products = Object.keys(matrix[bankName]);
                          const isBankNotified = !!bankNotifications[bankName];
                          return isMultistore ? (
                            <MultistoreBankSection
                              key={bankName}
                              bankName={bankName}
                              products={products}
                              rollupBankData={rollup.bank_progress?.[bankName] || {}}
                              isBankNotified={isBankNotified}
                              bankNotification={bankNotifications[bankName]}
                              onNotifyBank={handleNotifyBank}
                              notifyingBank={notifyingBank}
                            />
                          ) : (
                            <SingleBankSection
                              key={bankName}
                              bankName={bankName}
                              products={products}
                              matrixData={matrix[bankName]}
                              onTogglePhase={togglePhase}
                              isBankNotified={isBankNotified}
                              bankNotification={bankNotifications[bankName]}
                              onNotifyBank={handleNotifyBank}
                              notifyingBank={notifyingBank}
                            />
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </div>

          {/* ============ MULTISTORE: MATRICES POR TIENDA ============ */}
          {isMultistore && clientNotified && project.stores && project.stores.length > 0 && (
            <div className="mb-6" data-testid="multistore-section">
              <h2 className="text-lg font-bold text-slate-900 mb-3 flex items-center gap-2">
                <Store size={20} className="text-blue-600" />
                Seguimiento por Tienda ({project.stores.length})
              </h2>

              {/* Tabs para seleccionar tienda */}
              <div className="flex gap-2 mb-4 flex-wrap">
                {project.stores.map((store) => {
                  const progress = calcStoreProgress(store);
                  const isActive = selectedStoreId === store.store_id;
                  return (
                    <button
                      key={store.store_id}
                      onClick={() => setSelectedStoreId(isActive ? null : store.store_id)}
                      className={`px-4 py-2.5 rounded-lg border text-sm font-medium transition-all ${
                        isActive
                          ? 'bg-blue-600 text-white border-blue-600 shadow-sm'
                          : 'bg-white text-slate-700 border-slate-200 hover:border-blue-300 hover:bg-blue-50'
                      }`}
                      data-testid={`store-tab-${store.store_id}`}
                    >
                      <span className="font-semibold">{store.name}</span>
                      <span className={`ml-2 text-xs ${isActive ? 'text-blue-200' : 'text-slate-400'}`}>
                        {store.box_count} caja{store.box_count !== 1 ? 's' : ''} · {progress}%
                      </span>
                    </button>
                  );
                })}
              </div>

              {/* Matriz de la tienda seleccionada */}
              {selectedStoreId && (() => {
                const store = project.stores.find(s => s.store_id === selectedStoreId);
                if (!store) return null;
                const storeMatrix = store.implementation_matrix || {};
                const storeBankNames = Object.keys(storeMatrix);
                return (
                  <div className="bg-white rounded-lg border border-blue-200 p-4" data-testid={`store-matrix-${store.store_id}`}>
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                          <Store size={16} className="text-blue-600" />
                          {store.name}
                        </h3>
                        <p className="text-xs text-slate-500">{store.box_count} caja{store.box_count !== 1 ? 's' : ''} · Avance: {calcStoreProgress(store)}%</p>
                      </div>
                    </div>
                    {storeBankNames.length === 0 ? (
                      <p className="text-sm text-slate-400 text-center py-6">Sin datos en la matriz de esta tienda</p>
                    ) : (
                      <div className="overflow-x-auto rounded-lg border border-slate-200">
                        <table className="w-full">
                          <thead>
                            <tr>
                              <th className="bg-blue-600 text-white px-4 py-2.5 text-left text-xs font-semibold min-w-[200px]">Bancos / Productos</th>
                              {activePhasesForStores.map(phase => (
                                <th key={phase} className={`px-3 py-2.5 text-center text-xs font-semibold border-l border-slate-200 min-w-[100px] ${PHASE_COLORS[phase]}`}>{phase}</th>
                              ))}
                              <th className="bg-blue-600 text-white px-3 py-2.5 text-center text-xs font-semibold border-l border-slate-200">Avance</th>
                            </tr>
                          </thead>
                          <tbody>
                            {storeBankNames.map(bankName => {
                              const products = Object.keys(storeMatrix[bankName]);
                              return (
                                <StoreBankSection key={bankName} bankName={bankName} products={products}
                                  matrixData={storeMatrix[bankName]} storeId={store.store_id} onTogglePhase={toggleStorePhase}
                                  phases={activePhasesForStores} />
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                );
              })()}
            </div>
          )}

          {/* Bitácora de Seguimiento */}
          <div className="mb-6">
            <h2 className="text-lg font-bold text-slate-900 mb-3">Bitácora de Seguimiento</h2>

            {/* Add entry form */}
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 mb-4">
              <div className="grid grid-cols-12 gap-3 items-end">
                <div className="col-span-2">
                  <label className="text-xs font-medium text-slate-600">Fecha de Ejecución</label>
                  <Input type="date" value={bitacoraDate} onChange={e => setBitacoraDate(e.target.value)}
                    data-testid="bitacora-date" className="h-9" />
                </div>
                <div className="col-span-8">
                  <label className="text-xs font-medium text-slate-600">Observación</label>
                  <Input value={bitacoraText} onChange={e => setBitacoraText(e.target.value)}
                    placeholder="Registrar observación o avance..."
                    data-testid="bitacora-text" className="h-9" />
                </div>
                <div className="col-span-2">
                  <Button onClick={handleAddBitacora} disabled={!bitacoraText.trim() || bitacoraSubmitting}
                    className="w-full h-9 bg-brand-green-600 hover:bg-brand-green-700 text-white text-sm"
                    data-testid="bitacora-submit">
                    <Send size={14} className="mr-1" />Registrar
                  </Button>
                </div>
              </div>
            </div>

            {/* Entries */}
            <div className="space-y-2" data-testid="bitacora-list">
              {(project.bitacora || []).length === 0 ? (
                <p className="text-sm text-slate-400 text-center py-6">Sin entradas en la bitácora</p>
              ) : (
                [...(project.bitacora || [])].reverse().map(entry => (
                  <div key={entry.entry_id} className="flex items-start gap-4 p-3 bg-white border border-slate-100 rounded-lg">
                    <div className="shrink-0 flex items-center gap-2 text-xs bg-slate-100 rounded px-2 py-1">
                      <Calendar size={12} className="text-slate-500" />
                      <span className="font-mono font-medium">{entry.execution_date}</span>
                    </div>
                    <div className="flex-1">
                      <p className="text-sm text-slate-800">{entry.text}</p>
                      <p className="text-xs text-slate-400 mt-1">
                        <User size={10} className="inline mr-1" />{entry.created_by_name} · {new Date(entry.created_at).toLocaleString('es-VE')}
                      </p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* ==================== EMAIL AD-HOC DIALOG ==================== */}
        <Dialog open={emailDialogOpen} onOpenChange={(open) => { if (!emailSending) setEmailDialogOpen(open); }}>
          <DialogContent className="max-w-lg" data-testid="adhoc-email-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Mail size={20} className="text-indigo-500" />
                Enviar Correo Ad-hoc
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 max-h-[70vh] overflow-y-auto">
              {/* Proyecto info */}
              <div className="bg-slate-50 border rounded-lg p-2.5">
                <p className="text-xs text-slate-500">
                  {project.ticket_number ? `Ticket: ${project.ticket_number} · ` : ''}{project.project_number} — {project.client_name}
                </p>
              </div>

              {/* Destinatarios */}
              <div>
                <Label className="text-sm font-medium">Destinatarios <span className="text-red-500">*</span></Label>
                <div className="space-y-2 mt-1.5">
                  {emailForm.recipients.map((r, idx) => (
                    <div key={idx} className="flex items-center gap-2">
                      <Input
                        type="email"
                        placeholder="correo@ejemplo.com"
                        value={r}
                        onChange={e => updateRecipient(idx, e.target.value)}
                        className="flex-1 h-9 text-sm"
                        data-testid={`email-recipient-${idx}`}
                      />
                      {emailForm.recipients.length > 1 && (
                        <button onClick={() => removeRecipient(idx)} className="text-red-400 hover:text-red-600">
                          <X size={16} />
                        </button>
                      )}
                    </div>
                  ))}
                  <Button variant="ghost" size="sm" onClick={addRecipient} className="text-xs text-indigo-600" data-testid="add-recipient-btn">
                    <Plus size={14} className="mr-1" />Agregar destinatario
                  </Button>
                </div>
              </div>

              {/* Asunto */}
              <div>
                <Label className="text-sm font-medium">Asunto <span className="text-red-500">*</span></Label>
                <Input
                  placeholder="Asunto del correo..."
                  value={emailForm.subject}
                  onChange={e => setEmailForm(prev => ({ ...prev, subject: e.target.value }))}
                  className="mt-1 h-9 text-sm"
                  data-testid="email-subject"
                />
              </div>

              {/* Mensaje */}
              <div>
                <div className="flex items-center justify-between">
                  <Label className="text-sm font-medium">Mensaje <span className="text-red-500">*</span></Label>
                  <span className={`text-[10px] ${emailForm.message.length > 500 ? 'text-red-500 font-semibold' : 'text-slate-400'}`}>
                    {emailForm.message.length}/500
                  </span>
                </div>
                <Textarea
                  placeholder="Escriba su mensaje aquí..."
                  value={emailForm.message}
                  onChange={e => setEmailForm(prev => ({ ...prev, message: e.target.value }))}
                  className="mt-1 text-sm min-h-[100px] resize-none"
                  maxLength={500}
                  data-testid="email-message"
                />
              </div>

              {/* Adjuntos */}
              <div>
                <Label className="text-sm font-medium">Adjuntos</Label>
                <div className="mt-1.5 flex items-center gap-2">
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept=".jpg,.jpeg,.png,.pdf,.doc,.docx,.xls,.xlsx,.txt"
                    className="hidden"
                    onChange={handleFileSelect}
                  />
                  <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()} className="text-xs gap-1.5" data-testid="attach-files-btn">
                    <Paperclip size={14} />Archivos
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => {
                    const input = document.createElement('input');
                    input.type = 'file';
                    input.accept = 'image/jpeg,image/png';
                    input.multiple = true;
                    input.onchange = (e) => {
                      const files = Array.from(e.target.files || []);
                      setEmailFiles(prev => [...prev, ...files]);
                    };
                    input.click();
                  }} className="text-xs gap-1.5" data-testid="attach-images-btn">
                    <Image size={14} />Imágenes
                  </Button>
                </div>
                {emailFiles.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {emailFiles.map((f, idx) => (
                      <div key={idx} className="flex items-center justify-between bg-slate-50 rounded px-2.5 py-1.5 text-xs">
                        <span className="truncate text-slate-700 flex-1">{f.name}</span>
                        <button onClick={() => removeFile(idx)} className="ml-2 text-red-400 hover:text-red-600 shrink-0">
                          <X size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Botones */}
              <div className="flex justify-end gap-3 pt-3 border-t">
                <Button variant="outline" onClick={() => setEmailDialogOpen(false)} disabled={emailSending}>Cancelar</Button>
                <Button
                  onClick={handleSendAdhocEmail}
                  disabled={emailSending || !emailForm.subject.trim() || !emailForm.message.trim() || !emailForm.recipients.some(r => r.trim())}
                  className="bg-indigo-600 hover:bg-indigo-700 text-white gap-1.5"
                  data-testid="send-adhoc-email-btn"
                >
                  <Send size={14} />{emailSending ? 'Enviando...' : 'Enviar Correo'}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
};


// ==================== SINGLE PROJECT: Bank Section ====================
const SingleBankSection = ({ bankName, products, matrixData, onTogglePhase, isBankNotified, bankNotification, onNotifyBank, notifyingBank }) => {
  return (
    <>
      {/* Bank header row with notify button */}
      <tr className="bg-blue-50 border-t-2 border-blue-200">
        <td className="px-4 py-2 text-sm font-bold text-blue-900" colSpan={PHASES.length + 1}>
          <Building2 size={14} className="inline mr-2 text-blue-600" />{bankName}
        </td>
        <td className="px-3 py-2 text-center">
          {isBankNotified ? (
            <span className="inline-flex items-center gap-1 px-2 py-1 text-[10px] font-semibold rounded bg-emerald-100 text-emerald-700" data-testid={`bank-notified-${bankName}`}>
              <BellRing size={10} />Notificado
            </span>
          ) : (
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs border-amber-300 text-amber-700 hover:bg-amber-50"
              onClick={() => onNotifyBank(bankName)}
              disabled={notifyingBank === bankName}
              data-testid={`notify-bank-btn-${bankName}`}
            >
              <Mail size={12} className="mr-1" />Notificar
            </Button>
          )}
        </td>
      </tr>
      {/* Product rows */}
      {products.map(productName => {
        const phases = matrixData[productName] || {};
        return (
          <tr key={productName} className="border-t border-slate-100 hover:bg-slate-50">
            <td className="px-6 py-2.5 text-sm text-slate-700">{productName}</td>
            {PHASES.map(phase => {
              const phaseData = phases[phase];
              const completed = phaseData?.completed || false;
              return (
                <td key={phase} className="px-3 py-2.5 text-center border-l border-slate-100">
                  <button
                    onClick={() => onTogglePhase(bankName, productName, phase, completed)}
                    className={`inline-flex items-center justify-center w-7 h-7 rounded-md transition-all ${
                      completed
                        ? 'bg-emerald-500 text-white shadow-sm hover:bg-emerald-600'
                        : 'bg-slate-100 text-slate-400 hover:bg-slate-200'
                    }`}
                    title={completed ? `${phase}: Completado por ${phaseData?.updated_by || ''}` : `Marcar ${phase}`}
                    data-testid={`phase-${bankName}-${productName}-${phase}`}
                  >
                    {completed ? <CheckCircle2 size={16} /> : <Circle size={16} />}
                  </button>
                </td>
              );
            })}
            <td className="px-3 py-2.5 text-center border-l border-slate-100 text-xs text-slate-400">
              {Object.values(phases).filter(p => p?.completed).length}/{PHASES.length}
            </td>
          </tr>
        );
      })}
    </>
  );
};


// ==================== MULTISTORE PROJECT: Bank Section (Read-Only with Roll-up) ====================
const MultistoreBankSection = ({ bankName, products, rollupBankData, isBankNotified, bankNotification, onNotifyBank, notifyingBank }) => {
  return (
    <>
      {/* Bank header row */}
      <tr className="bg-blue-50 border-t-2 border-blue-200">
        <td className="px-4 py-2 text-sm font-bold text-blue-900">
          <Building2 size={14} className="inline mr-2 text-blue-600" />{bankName}
        </td>
        <td className="px-4 py-2 text-center text-xs text-blue-600 font-medium">
          {(() => {
            const pcts = products.map(p => rollupBankData[p] || 0);
            const avg = pcts.length > 0 ? Math.round(pcts.reduce((a, b) => a + b, 0) / pcts.length) : 0;
            return `Promedio: ${avg}%`;
          })()}
        </td>
        <td className="px-3 py-2 text-center">
          {isBankNotified ? (
            <span className="inline-flex items-center gap-1 px-2 py-1 text-[10px] font-semibold rounded bg-emerald-100 text-emerald-700" data-testid={`bank-notified-${bankName}`}>
              <BellRing size={10} />Notificado
            </span>
          ) : (
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs border-amber-300 text-amber-700 hover:bg-amber-50"
              onClick={() => onNotifyBank(bankName)}
              disabled={notifyingBank === bankName}
              data-testid={`notify-bank-btn-${bankName}`}
            >
              <Mail size={12} className="mr-1" />Notificar
            </Button>
          )}
        </td>
      </tr>
      {/* Product rows with progress bars */}
      {products.map(productName => {
        const pct = rollupBankData[productName] || 0;
        return (
          <tr key={productName} className="border-t border-slate-100 hover:bg-slate-50">
            <td className="px-6 py-2.5 text-sm text-slate-700">{productName}</td>
            <td className="px-4 py-2.5 border-l border-slate-100">
              <div className="flex items-center gap-3">
                <div className="flex-1 bg-slate-100 rounded-full h-3 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      pct >= 100 ? 'bg-emerald-500' : pct >= 50 ? 'bg-blue-500' : pct > 0 ? 'bg-amber-400' : 'bg-slate-200'
                    }`}
                    style={{ width: `${Math.min(pct, 100)}%` }}
                    data-testid={`rollup-bar-${bankName}-${productName}`}
                  />
                </div>
                <span className={`text-sm font-bold min-w-[45px] text-right ${
                  pct >= 100 ? 'text-emerald-600' : 'text-slate-600'
                }`}>{pct}%</span>
              </div>
            </td>
            <td className="px-3 py-2.5 text-center border-l border-slate-100 text-xs text-slate-400">
              <Lock size={12} className="inline text-slate-300" />
            </td>
          </tr>
        );
      })}
    </>
  );
};


// ==================== STORE: Bank Section (editable, without Notificado) ====================
const StoreBankSection = ({ bankName, products, matrixData, storeId, onTogglePhase, phases }) => {
  return (
    <>
      <tr className="bg-blue-50 border-t-2 border-blue-200">
        <td className="px-4 py-2 text-sm font-bold text-blue-900" colSpan={phases.length + 2}>
          <Building2 size={14} className="inline mr-2 text-blue-600" />{bankName}
        </td>
      </tr>
      {products.map(productName => {
        const phaseData = matrixData[productName] || {};
        return (
          <tr key={productName} className="border-t border-slate-100 hover:bg-slate-50">
            <td className="px-6 py-2.5 text-sm text-slate-700">{productName}</td>
            {phases.map(phase => {
              const data = phaseData[phase];
              const completed = data?.completed || false;
              return (
                <td key={phase} className="px-3 py-2.5 text-center border-l border-slate-100">
                  <button
                    onClick={() => onTogglePhase(storeId, bankName, productName, phase, completed)}
                    className={`inline-flex items-center justify-center w-7 h-7 rounded-md transition-all ${
                      completed
                        ? 'bg-emerald-500 text-white shadow-sm hover:bg-emerald-600'
                        : 'bg-slate-100 text-slate-400 hover:bg-slate-200'
                    }`}
                    title={completed ? `${phase}: Completado por ${data?.updated_by || ''}` : `Marcar ${phase}`}
                    data-testid={`store-phase-${storeId}-${bankName}-${productName}-${phase}`}
                  >
                    {completed ? <CheckCircle2 size={16} /> : <Circle size={16} />}
                  </button>
                </td>
              );
            })}
            <td className="px-3 py-2.5 text-center border-l border-slate-100 text-xs text-slate-400">
              {Object.values(phaseData).filter(p => p?.completed).length}/{phases.length}
            </td>
          </tr>
        );
      })}
    </>
  );
};


export default ProjectDetail;
