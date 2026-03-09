import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog';
import { ArrowLeft, Building2, Monitor, Globe, Smartphone, Link, Plus, Trash2, ChevronRight, User, Phone, Mail, Hash, Rocket, Package, FileText, Pencil } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const INTEGRATION_STATUSES = [
  { id: 'Negoc.', label: 'Negoc.', full: 'En Negociación', color: 'bg-slate-100 text-slate-700 border-slate-300' },
  { id: 'DESA', label: 'DESA', full: 'Desarrollo', color: 'bg-amber-100 text-amber-700 border-amber-300' },
  { id: 'SQA', label: 'SQA', full: 'Control de Calidad', color: 'bg-blue-100 text-blue-700 border-blue-300' },
  { id: 'Imple.', label: 'Imple.', full: 'Implementación', color: 'bg-purple-100 text-purple-700 border-purple-300' },
  { id: 'PreProd', label: 'PreProd', full: 'Pre-Producción', color: 'bg-orange-100 text-orange-700 border-orange-300' },
  { id: 'Completado', label: 'Completado', full: 'Completado', color: 'bg-emerald-100 text-emerald-700 border-emerald-300' }
];

const PHASE_DOT_COLORS = {
  'Negoc.': 'bg-slate-400 border-slate-300',
  'DESA': 'bg-amber-500 border-amber-300',
  'SQA': 'bg-blue-500 border-blue-300',
  'Imple.': 'bg-purple-500 border-purple-300',
  'PreProd': 'bg-orange-500 border-orange-300',
  'Completado': 'bg-emerald-500 border-emerald-300'
};

const getStatusStyle = (status) => INTEGRATION_STATUSES.find(s => s.id === status) || INTEGRATION_STATUSES[0];

const StatusBadge = ({ status }) => {
  const s = getStatusStyle(status);
  return <span className={`px-2.5 py-1 text-xs font-semibold rounded-full border ${s.color}`}>{s.label}</span>;
};

const StatusPipeline = ({ currentStatus }) => {
  const idx = INTEGRATION_STATUSES.findIndex(s => s.id === currentStatus);
  return (
    <div className="flex items-center gap-0.5">
      {INTEGRATION_STATUSES.slice(0, -1).map((s, i) => (
        <div key={s.id} className="flex items-center gap-0.5">
          <div className={`w-2 h-2 rounded-full ${i <= idx ? 'bg-emerald-500' : 'bg-slate-300'}`} title={s.full} />
          {i < 4 && <div className={`w-3 h-0.5 ${i < idx ? 'bg-emerald-400' : 'bg-slate-200'}`} />}
        </div>
      ))}
    </div>
  );
};

export const BankDetail = () => {
  const { bankId } = useParams();
  const navigate = useNavigate();
  const [bank, setBank] = useState(null);
  const [mediosPago, setMediosPago] = useState([]);
  const [loading, setLoading] = useState(true);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState({ open: false, id: null, name: '' });
  const [newIntegration, setNewIntegration] = useState({ service_name: '', component_type: '', status: 'Negoc.', notes: '' });

  // Evolution log state
  const [evoOpen, setEvoOpen] = useState(false);
  const [evoIntegration, setEvoIntegration] = useState(null);
  const [evoEntries, setEvoEntries] = useState([]);
  const [evoLoading, setEvoLoading] = useState(false);
  const [evoForm, setEvoForm] = useState({ comment: '', phase: '', date: new Date().toISOString().slice(0, 10) });
  const [evoEditing, setEvoEditing] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const [bankRes, servicesRes] = await Promise.all([
        api.get(`/banks/${bankId}/detail`),
        api.get('/services')
      ]);
      setBank(bankRes.data);
      setMediosPago(servicesRes.data);
    } catch {
      toast.error('Error al cargar datos del banco');
      navigate('/banks');
    } finally { setLoading(false); }
  }, [bankId, navigate]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const activeProducts = (bank?.products || []);
  const vposMpos = activeProducts.filter(p => p.vpos_available || p.mpos_available);
  const pgLink = activeProducts.filter(p => p.gateway_available || p.link_available);
  const integrations = bank?.integrations || [];

  const productoServices = mediosPago.filter(s => s.service_type === 'Producto' || !s.service_type);

  const handleAddIntegration = async () => {
    if (!newIntegration.service_name || !newIntegration.component_type) {
      toast.error('Complete los campos obligatorios');
      return;
    }
    try {
      await api.post(`/banks/${bankId}/integrations`, newIntegration);
      toast.success('Integración agregada');
      setAddDialogOpen(false);
      setNewIntegration({ service_name: '', component_type: '', status: 'Negoc.', notes: '' });
      fetchData();
    } catch { toast.error('Error al agregar integración'); }
  };

  const handleStatusChange = async (integrationId, newStatus) => {
    try {
      await api.put(`/banks/${bankId}/integrations/${integrationId}`, { status: newStatus });
      toast.success('Estatus actualizado');
      fetchData();
    } catch { toast.error('Error al actualizar estatus'); }
  };

  const handleDeleteIntegration = async () => {
    try {
      await api.delete(`/banks/${bankId}/integrations/${deleteConfirm.id}`);
      toast.success('Integración eliminada');
      setDeleteConfirm({ open: false, id: null, name: '' });
      fetchData();
    } catch { toast.error('Error al eliminar'); }
  };

  const handleServiceSelect = (serviceId) => {
    const svc = mediosPago.find(s => s.service_id === serviceId);
    if (svc) {
      const comp = (svc.vpos_enabled || svc.mpos_enabled) ? 'VPOS/MPOS' : 'PG/Link';
      setNewIntegration({ ...newIntegration, service_name: svc.name, component_type: comp });
    }
  };

  // ==================== EVOLUTION LOG FUNCTIONS ====================
  const openEvolution = async (intg) => {
    setEvoIntegration(intg);
    setEvoOpen(true);
    setEvoLoading(true);
    setEvoEditing(null);
    setEvoForm({ comment: '', phase: intg.status || 'Negoc.', date: new Date().toISOString().slice(0, 10) });
    try {
      const res = await api.get(`/banks/${bankId}/integrations/${intg.integration_id}/evolution`);
      setEvoEntries(res.data);
    } catch { toast.error('Error al cargar historial'); }
    finally { setEvoLoading(false); }
  };

  const saveEvoEntry = async () => {
    if (!evoForm.comment.trim()) { toast.error('Escriba un comentario'); return; }
    try {
      if (evoEditing) {
        await api.patch(`/banks/${bankId}/integrations/${evoIntegration.integration_id}/evolution/${evoEditing}`, evoForm);
        toast.success('Entrada actualizada');
      } else {
        await api.post(`/banks/${bankId}/integrations/${evoIntegration.integration_id}/evolution`, evoForm);
        toast.success('Hito registrado');
      }
      setEvoEditing(null);
      setEvoForm({ comment: '', phase: evoIntegration.status || 'Negoc.', date: new Date().toISOString().slice(0, 10) });
      const res = await api.get(`/banks/${bankId}/integrations/${evoIntegration.integration_id}/evolution`);
      setEvoEntries(res.data);
    } catch { toast.error('Error al guardar'); }
  };

  const startEditEvo = (entry) => {
    setEvoEditing(entry.entry_id);
    setEvoForm({ comment: entry.comment, phase: entry.phase, date: entry.date });
  };

  const deleteEvoEntry = async (entryId) => {
    try {
      await api.delete(`/banks/${bankId}/integrations/${evoIntegration.integration_id}/evolution/${entryId}`);
      setEvoEntries(prev => prev.filter(e => e.entry_id !== entryId));
      toast.success('Entrada eliminada');
    } catch { toast.error('Error al eliminar'); }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center bg-white">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-green-600" />
        </div>
      </div>
    );
  }

  if (!bank) return null;

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 p-8" data-testid="bank-detail-page">
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <div className="flex items-center gap-4 mb-8">
            <Button variant="outline" size="sm" onClick={() => navigate('/banks')} data-testid="back-to-banks">
              <ArrowLeft size={16} className="mr-1" />Volver
            </Button>
            <div className="flex items-center gap-4 flex-1">
              <div className="w-14 h-14 rounded-lg bg-white border border-slate-200 flex items-center justify-center overflow-hidden shrink-0">
                {bank.bank_logo_url ? (
                  <img src={`${API_URL}${bank.bank_logo_url}`} alt={bank.name} className="w-12 h-12 object-contain" onError={(e) => { e.target.onerror = null; e.target.src = ''; e.target.style.display = 'none'; }} />
                ) : null}
                {!bank.bank_logo_url && <Building2 size={24} className="text-slate-400" />}
              </div>
              <div>
                <h1 className="text-3xl font-bold text-slate-900 font-manrope">{bank.name}</h1>
                <div className="flex items-center gap-3 mt-1 text-sm text-slate-500">
                  <span className="px-2 py-0.5 text-xs font-semibold rounded bg-slate-100 text-slate-600">{bank.type}</span>
                  {bank.rif && <span className="flex items-center gap-1"><Hash size={12} />{bank.rif}</span>}
                  {bank.bank_code && <span>Código: {bank.bank_code}</span>}
                </div>
              </div>
            </div>
            {bank.contact_name && (
              <div className="text-right text-sm">
                <p className="font-medium text-slate-700 flex items-center justify-end gap-1"><User size={13} />{bank.contact_name}</p>
                {bank.contact_phone && <p className="text-slate-500 flex items-center justify-end gap-1"><Phone size={11} />{bank.contact_phone}</p>}
                {bank.contact_email && <p className="text-slate-500 flex items-center justify-end gap-1"><Mail size={11} />{bank.contact_email}</p>}
              </div>
            )}
          </div>

          {/* Stats summary */}
          <div className="grid grid-cols-3 gap-4 mb-8">
            <div className="bg-white rounded-lg border border-slate-200 p-4">
              <div className="flex items-center gap-2 mb-1">
                <Monitor size={16} className="text-blue-600" />
                <span className="text-sm font-medium text-slate-500">VPOS / MPOS</span>
              </div>
              <p className="text-2xl font-bold text-slate-900">{vposMpos.length}</p>
              <p className="text-xs text-slate-400">medios activos</p>
            </div>
            <div className="bg-white rounded-lg border border-slate-200 p-4">
              <div className="flex items-center gap-2 mb-1">
                <Globe size={16} className="text-green-600" />
                <span className="text-sm font-medium text-slate-500">PG / Link de Pago</span>
              </div>
              <p className="text-2xl font-bold text-slate-900">{pgLink.length}</p>
              <p className="text-xs text-slate-400">medios activos</p>
            </div>
            <div className="bg-white rounded-lg border border-slate-200 p-4">
              <div className="flex items-center gap-2 mb-1">
                <Rocket size={16} className="text-purple-600" />
                <span className="text-sm font-medium text-slate-500">En Integración</span>
              </div>
              <p className="text-2xl font-bold text-slate-900">{integrations.filter(i => i.status !== 'Completado').length}</p>
              <p className="text-xs text-slate-400">proyectos en curso</p>
            </div>
          </div>

          {/* Section A: VPOS / MPOS */}
          <div className="bg-white rounded-lg border border-slate-200 p-6 mb-4" data-testid="section-vpos-mpos">
            <h2 className="font-semibold text-slate-900 flex items-center gap-2 mb-4">
              <Monitor size={18} className="text-blue-600" />
              Medios de Pago Activos — VPOS / MPOS
            </h2>
            {vposMpos.length > 0 ? (
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                {vposMpos.map((p, i) => (
                  <div key={i} className="flex items-center gap-2 p-2.5 rounded-lg bg-blue-50 border border-blue-100">
                    <Package size={14} className="text-blue-600 shrink-0" />
                    <span className="text-sm font-medium text-blue-800 truncate">{p.product_name}</span>
                    <div className="flex gap-1 ml-auto shrink-0">
                      {p.vpos_available && <span className="px-1 py-0.5 text-[9px] font-bold rounded bg-blue-200 text-blue-700">VPOS</span>}
                      {p.mpos_available && <span className="px-1 py-0.5 text-[9px] font-bold rounded bg-indigo-200 text-indigo-700">MPOS</span>}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-400 italic">Sin medios de pago VPOS/MPOS activos</p>
            )}
          </div>

          {/* Section B: Payment Gateway / Link */}
          <div className="bg-white rounded-lg border border-slate-200 p-6 mb-4" data-testid="section-pg-link">
            <h2 className="font-semibold text-slate-900 flex items-center gap-2 mb-4">
              <Globe size={18} className="text-green-600" />
              Medios de Pago Activos — Payment Gateway / Link de Pago
            </h2>
            {pgLink.length > 0 ? (
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                {pgLink.map((p, i) => (
                  <div key={i} className="flex items-center gap-2 p-2.5 rounded-lg bg-green-50 border border-green-100">
                    <Package size={14} className="text-green-600 shrink-0" />
                    <span className="text-sm font-medium text-green-800 truncate">{p.product_name}</span>
                    <div className="flex gap-1 ml-auto shrink-0">
                      {p.gateway_available && <span className="px-1 py-0.5 text-[9px] font-bold rounded bg-green-200 text-green-700">PG</span>}
                      {p.link_available && <span className="px-1 py-0.5 text-[9px] font-bold rounded bg-teal-200 text-teal-700">Link</span>}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-400 italic">Sin medios de pago PG/Link activos</p>
            )}
          </div>

          {/* Section C: Integration Roadmap */}
          <div className="bg-white rounded-lg border border-slate-200 p-6" data-testid="section-integrations">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-slate-900 flex items-center gap-2">
                <Rocket size={18} className="text-purple-600" />
                Medios de Pago en Proceso de Integración (Roadmap)
              </h2>
              <Button size="sm" onClick={() => setAddDialogOpen(true)} data-testid="add-integration-btn"
                className="bg-purple-600 hover:bg-purple-700 text-white">
                <Plus size={16} className="mr-1" />Nueva Integración
              </Button>
            </div>

            {integrations.length > 0 ? (
              <div className="space-y-2">
                {integrations.map((intg) => (
                  <div key={intg.integration_id} data-testid={`integration-${intg.integration_id}`}
                    className="flex items-center gap-4 p-3 rounded-lg border border-slate-200 hover:border-slate-300 transition-colors">
                    <div className="min-w-[180px]">
                      <p className="font-medium text-slate-900 text-sm">{intg.service_name}</p>
                      <p className="text-xs text-slate-500">{intg.component_type}</p>
                    </div>
                    <StatusPipeline currentStatus={intg.status} />
                    <div className="min-w-[120px]">
                      <Select value={intg.status} onValueChange={(v) => handleStatusChange(intg.integration_id, v)}>
                        <SelectTrigger className="h-8 text-xs" data-testid={`status-select-${intg.integration_id}`}>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {INTEGRATION_STATUSES.map(s => (
                            <SelectItem key={s.id} value={s.id}>
                              <span className="flex items-center gap-1.5">
                                <StatusBadge status={s.id} />
                              </span>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    {intg.notes && <p className="text-xs text-slate-500 flex-1 truncate">{intg.notes}</p>}
                    <Button size="sm" variant="ghost" title="Historial de Evolución"
                      onClick={() => openEvolution(intg)}
                      className="h-7 w-7 p-0 text-purple-500 hover:text-purple-700 shrink-0"
                      data-testid={`evo-btn-${intg.integration_id}`}>
                      <FileText size={14} />
                    </Button>
                    <Button size="sm" variant="ghost"
                      onClick={() => setDeleteConfirm({ open: true, id: intg.integration_id, name: intg.service_name })}
                      className="h-7 w-7 p-0 text-red-500 hover:text-red-700 shrink-0"
                      data-testid={`delete-integration-${intg.integration_id}`}>
                      <Trash2 size={14} />
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <Rocket size={32} className="mx-auto text-slate-300 mb-2" />
                <p className="text-sm text-slate-400">No hay integraciones en curso</p>
                <p className="text-xs text-slate-400 mt-1">Agregue una nueva integración usando el botón superior</p>
              </div>
            )}
          </div>
        </div>

        {/* Add Integration Dialog */}
        <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="font-manrope">Nueva Integración</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <Label>Medio de Pago</Label>
                <Select onValueChange={handleServiceSelect}>
                  <SelectTrigger data-testid="select-integration-service">
                    <SelectValue placeholder="Seleccione un producto..." />
                  </SelectTrigger>
                  <SelectContent>
                    {productoServices.map(s => (
                      <SelectItem key={s.service_id} value={s.service_id}>{s.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Componente</Label>
                <Select value={newIntegration.component_type} onValueChange={(v) => setNewIntegration({ ...newIntegration, component_type: v })}>
                  <SelectTrigger data-testid="select-integration-component">
                    <SelectValue placeholder="Seleccione..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="VPOS/MPOS">VPOS / MPOS</SelectItem>
                    <SelectItem value="PG/Link">Payment Gateway / Link de Pago</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Estatus Inicial</Label>
                <Select value={newIntegration.status} onValueChange={(v) => setNewIntegration({ ...newIntegration, status: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {INTEGRATION_STATUSES.map(s => (
                      <SelectItem key={s.id} value={s.id}>{s.label} — {s.full}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Notas (opcional)</Label>
                <Input placeholder="Notas adicionales..." value={newIntegration.notes}
                  onChange={(e) => setNewIntegration({ ...newIntegration, notes: e.target.value })}
                  data-testid="integration-notes-input" />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={() => setAddDialogOpen(false)}>Cancelar</Button>
                <Button onClick={handleAddIntegration} data-testid="save-integration-btn"
                  className="bg-purple-600 hover:bg-purple-700 text-white"
                  disabled={!newIntegration.service_name || !newIntegration.component_type}>
                  Guardar
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation */}
        <AlertDialog open={deleteConfirm.open} onOpenChange={(o) => setDeleteConfirm({ ...deleteConfirm, open: o })}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Eliminar Integración</AlertDialogTitle>
              <AlertDialogDescription>
                Eliminar la integración <strong>"{deleteConfirm.name}"</strong>?
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancelar</AlertDialogCancel>
              <AlertDialogAction onClick={handleDeleteIntegration} className="bg-red-600 hover:bg-red-700 text-white">
                Eliminar
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Evolution Timeline Modal */}
        <Dialog open={evoOpen} onOpenChange={(o) => { if (!o) { setEvoOpen(false); setEvoEditing(null); } }}>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="product-evolution-modal">
            <DialogHeader>
              <DialogTitle className="font-manrope text-xl flex items-center gap-2">
                <FileText size={20} className="text-purple-600" />
                Bitácora de Evolución — {evoIntegration?.service_name}
                {evoIntegration?.status && (
                  <span className={`ml-2 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getStatusStyle(evoIntegration.status).color}`}>
                    {evoIntegration.status}
                  </span>
                )}
              </DialogTitle>
            </DialogHeader>

            {/* Form */}
            <div className="bg-slate-50 rounded-lg border border-slate-200 p-3 space-y-2">
              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">{evoEditing ? 'Editar Entrada' : 'Nuevo Hito'}</p>
              <Textarea value={evoForm.comment} onChange={(e) => setEvoForm(p => ({ ...p, comment: e.target.value }))}
                placeholder="Describa el avance técnico, observación o hito alcanzado..." className="text-sm min-h-[70px]" data-testid="product-evo-comment" />
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <Label className="text-[10px] text-slate-500">Fase</Label>
                  <Select value={evoForm.phase} onValueChange={(v) => setEvoForm(p => ({ ...p, phase: v }))}>
                    <SelectTrigger className="h-8 text-xs" data-testid="product-evo-phase-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {INTEGRATION_STATUSES.map(s => <SelectItem key={s.id} value={s.id}>{s.label} — {s.full}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-[10px] text-slate-500">Fecha</Label>
                  <Input type="date" value={evoForm.date} onChange={(e) => setEvoForm(p => ({ ...p, date: e.target.value }))} className="h-8 text-xs" data-testid="product-evo-date" />
                </div>
              </div>
              <div className="flex justify-end gap-2">
                {evoEditing && (
                  <Button size="sm" variant="outline" className="h-8 text-xs" onClick={() => {
                    setEvoEditing(null);
                    setEvoForm({ comment: '', phase: evoIntegration?.status || 'Negoc.', date: new Date().toISOString().slice(0, 10) });
                  }}>Cancelar Edición</Button>
                )}
                <Button size="sm" className="h-8 text-xs bg-purple-600 hover:bg-purple-700 text-white" onClick={saveEvoEntry} data-testid="product-evo-save-btn">
                  {evoEditing ? 'Actualizar' : '+ Registrar Hito'}
                </Button>
              </div>
            </div>

            {/* Timeline */}
            <div className="mt-2">
              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-3">Línea de Tiempo ({evoEntries.length})</p>
              {evoLoading ? (
                <p className="text-sm text-slate-400 text-center py-4">Cargando...</p>
              ) : evoEntries.length === 0 ? (
                <p className="text-sm text-slate-400 text-center py-4 italic">Sin hitos registrados para esta integración</p>
              ) : (
                <div className="relative pl-6 space-y-0">
                  <div className="absolute left-[10px] top-2 bottom-2 w-0.5 bg-slate-200" />
                  {evoEntries.map((entry) => {
                    const dotColor = PHASE_DOT_COLORS[entry.phase] || 'bg-slate-400 border-slate-300';
                    return (
                      <div key={entry.entry_id} className="relative pb-4" data-testid={`product-evo-entry-${entry.entry_id}`}>
                        <div className={`absolute left-[-18px] top-1 w-3.5 h-3.5 rounded-full border-2 ${dotColor}`} />
                        <div className="bg-white border border-slate-200 rounded-lg p-3 ml-1">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1.5">
                                <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold border ${getStatusStyle(entry.phase).color}`}>{entry.phase}</span>
                                <span className="text-[10px] text-slate-400">{entry.date}</span>
                                {entry.updated_at && <span className="text-[9px] text-slate-300 italic">editado</span>}
                              </div>
                              <p className="text-sm text-slate-800 whitespace-pre-wrap break-words">{entry.comment}</p>
                            </div>
                            <div className="flex items-center gap-0.5 flex-shrink-0">
                              <Button size="sm" variant="ghost" className="h-6 w-6 p-0 text-slate-400 hover:text-purple-600" onClick={() => startEditEvo(entry)} title="Editar" data-testid={`product-evo-edit-${entry.entry_id}`}>
                                <Pencil size={11} />
                              </Button>
                              <Button size="sm" variant="ghost" className="h-6 w-6 p-0 text-slate-300 hover:text-red-500" onClick={() => deleteEvoEntry(entry.entry_id)} data-testid={`product-evo-delete-${entry.entry_id}`}>
                                <Trash2 size={11} />
                              </Button>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
};

export default BankDetail;
