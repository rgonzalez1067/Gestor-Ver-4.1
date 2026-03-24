import { useState, useEffect, useCallback } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog';
import { FlaskConical, Plus, Trash2, FileText, Pencil, Building2, ChevronRight, ArrowRight, CheckCircle2, Clock, ArrowRightLeft } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';
import { usePermission } from '../hooks/usePermission';

const PIPELINE_STATUSES = [
  { id: 'Negociación', label: 'Negociación', color: 'bg-slate-100 text-slate-700 border-slate-300', dot: 'bg-slate-400' },
  { id: 'DESA', label: 'DESA', color: 'bg-amber-100 text-amber-700 border-amber-300', dot: 'bg-amber-500' },
  { id: 'SQA', label: 'SQA', color: 'bg-blue-100 text-blue-700 border-blue-300', dot: 'bg-blue-500' },
  { id: 'IMPLE', label: 'IMPLE', color: 'bg-purple-100 text-purple-700 border-purple-300', dot: 'bg-purple-500' },
];

const PROMOTED_STYLE = { id: 'Promovido', label: 'Promovido', color: 'bg-emerald-100 text-emerald-700 border-emerald-300', dot: 'bg-emerald-500' };

const getStatusStyle = (status) => {
  if (status === 'Promovido') return PROMOTED_STYLE;
  return PIPELINE_STATUSES.find(s => s.id === status) || PIPELINE_STATUSES[0];
};

const StatusBadge = ({ status }) => {
  const s = getStatusStyle(status);
  return <span className={`px-2.5 py-1 text-xs font-semibold rounded-full border ${s.color}`}>{s.label}</span>;
};

const PipelineDots = ({ currentStatus }) => {
  const idx = PIPELINE_STATUSES.findIndex(s => s.id === currentStatus);
  const isPromoted = currentStatus === 'Promovido';
  return (
    <div className="flex items-center gap-0.5">
      {PIPELINE_STATUSES.map((s, i) => (
        <div key={s.id} className="flex items-center gap-0.5">
          <div className={`w-2.5 h-2.5 rounded-full ${isPromoted || i <= idx ? 'bg-emerald-500' : 'bg-slate-300'}`} title={s.label} />
          {i < PIPELINE_STATUSES.length - 1 && (
            <div className={`w-4 h-0.5 ${isPromoted || i < idx ? 'bg-emerald-400' : 'bg-slate-200'}`} />
          )}
        </div>
      ))}
      {isPromoted && (
        <>
          <div className="w-4 h-0.5 bg-emerald-400" />
          <CheckCircle2 size={14} className="text-emerald-600" />
        </>
      )}
    </div>
  );
};

export const NewProducts = () => {
  const { canEdit } = usePermission('nuevos_productos');
  const [products, setProducts] = useState([]);
  const [banks, setBanks] = useState([]);
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState({ open: false, id: null, name: '' });
  const [form, setForm] = useState({ service_id: '', component_type: '', bank_id: '', notes: '' });

  // Evolution log state
  const [evoOpen, setEvoOpen] = useState(false);
  const [evoProduct, setEvoProduct] = useState(null);
  const [evoEntries, setEvoEntries] = useState([]);
  const [transitions, setTransitions] = useState([]);
  const [evoLoading, setEvoLoading] = useState(false);
  const [evoForm, setEvoForm] = useState({ comment: '', phase: 'Negociación', date: new Date().toISOString().slice(0, 10) });
  const [evoEditing, setEvoEditing] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const [prodRes, bankRes, svcRes] = await Promise.all([
        api.get('/new-products'),
        api.get('/banks'),
        api.get('/services')
      ]);
      setProducts(prodRes.data);
      setBanks(bankRes.data);
      setServices(svcRes.data.filter(s => s.service_type === 'Producto' || !s.service_type));
    } catch {
      toast.error('Error al cargar datos');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleServiceSelect = (serviceId) => {
    const svc = services.find(s => s.service_id === serviceId);
    if (svc) {
      const comp = (svc.vpos_enabled || svc.mpos_enabled) ? 'VPOS/MPOS' : 'PG/Link';
      setForm({ ...form, service_id: serviceId, component_type: comp });
    }
  };

  const handleCreate = async () => {
    if (!form.service_id || !form.component_type || !form.bank_id) {
      toast.error('Complete los campos obligatorios');
      return;
    }
    try {
      await api.post('/new-products', form);
      toast.success('Producto creado en Negociación');
      setAddOpen(false);
      setForm({ service_id: '', component_type: '', bank_id: '', notes: '' });
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al crear producto');
    }
  };

  const handleStatusChange = async (productId, newStatus) => {
    try {
      const res = await api.put(`/new-products/${productId}/status`, { status: newStatus });
      if (res.data._handoff) {
        toast.success('Producto promovido. Insertado automáticamente en integraciones del banco.', { duration: 5000 });
      } else {
        toast.success(`Estado actualizado a ${newStatus}`);
      }
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al actualizar estado');
    }
  };

  const handleDelete = async () => {
    try {
      await api.delete(`/new-products/${deleteConfirm.id}`);
      toast.success('Producto eliminado');
      setDeleteConfirm({ open: false, id: null, name: '' });
      fetchData();
    } catch {
      toast.error('Error al eliminar');
    }
  };

  // ==================== EVOLUTION LOG ====================
  const openEvolution = async (product) => {
    setEvoProduct(product);
    setEvoOpen(true);
    setEvoLoading(true);
    setEvoEditing(null);
    setEvoForm({ comment: '', phase: product.status === 'Promovido' ? 'IMPLE' : product.status, date: new Date().toISOString().slice(0, 10) });
    try {
      const [evoRes, transRes] = await Promise.all([
        api.get(`/new-products/${product.product_id}/evolution`),
        api.get(`/new-products/${product.product_id}/transitions`)
      ]);
      setEvoEntries(evoRes.data);
      setTransitions(transRes.data);
    } catch { toast.error('Error al cargar historial'); }
    finally { setEvoLoading(false); }
  };

  const saveEvoEntry = async () => {
    if (!evoForm.comment.trim()) { toast.error('Escriba un comentario'); return; }
    try {
      if (evoEditing) {
        await api.patch(`/new-products/${evoProduct.product_id}/evolution/${evoEditing}`, evoForm);
        toast.success('Entrada actualizada');
      } else {
        await api.post(`/new-products/${evoProduct.product_id}/evolution`, evoForm);
        toast.success('Hito registrado');
      }
      setEvoEditing(null);
      setEvoForm({ comment: '', phase: evoProduct?.status === 'Promovido' ? 'IMPLE' : (evoProduct?.status || 'Negociación'), date: new Date().toISOString().slice(0, 10) });
      const res = await api.get(`/new-products/${evoProduct.product_id}/evolution`);
      setEvoEntries(res.data);
    } catch { toast.error('Error al guardar'); }
  };

  const startEditEvo = (entry) => {
    setEvoEditing(entry.entry_id);
    setEvoForm({ comment: entry.comment, phase: entry.phase, date: entry.date });
  };

  const deleteEvoEntry = async (entryId) => {
    try {
      await api.delete(`/new-products/${evoProduct.product_id}/evolution/${entryId}`);
      setEvoEntries(prev => prev.filter(e => e.entry_id !== entryId));
      toast.success('Entrada eliminada');
    } catch { toast.error('Error al eliminar'); }
  };

  // Merge evolution entries + transitions into unified timeline
  const buildTimeline = () => {
    const items = [];
    evoEntries.forEach(e => items.push({ ...e, _type: 'evolution', _sort: e.date || e.created_at }));
    transitions.forEach(t => {
      const ts = t.timestamp || t.created_at;
      const dateStr = typeof ts === 'string' ? ts.slice(0, 10) : ts;
      items.push({ ...t, _type: 'transition', _sort: dateStr });
    });
    items.sort((a, b) => (b._sort || '').localeCompare(a._sort || ''));
    return items;
  };

  const activeProducts = products.filter(p => p.status !== 'Promovido');
  const promotedProducts = products.filter(p => p.status === 'Promovido');
  const timeline = evoOpen ? buildTimeline() : [];

  if (loading) {
    return (
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center bg-white">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 p-8" data-testid="new-products-page">
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="text-3xl font-bold text-slate-900 font-manrope flex items-center gap-3">
                <FlaskConical size={28} className="text-purple-600" />
                Nuevos Productos
              </h1>
              <p className="text-sm text-slate-500 mt-1">Pipeline de I+D — Medios de pago en desarrollo antes de despliegue oficial</p>
            </div>
            {canEdit && <Button onClick={() => setAddOpen(true)} data-testid="add-new-product-btn"
              className="bg-purple-600 hover:bg-purple-700 text-white">
              <Plus size={16} className="mr-1.5" />Nuevo Producto
            </Button>}
          </div>

          {/* Stats */}
          <div className="grid grid-cols-5 gap-3 mb-6">
            {PIPELINE_STATUSES.map(s => {
              const count = products.filter(p => p.status === s.id).length;
              return (
                <div key={s.id} className="bg-white rounded-lg border border-slate-200 p-3 text-center" data-testid={`stat-${s.id}`}>
                  <div className={`w-3 h-3 rounded-full ${s.dot} mx-auto mb-1.5`} />
                  <p className="text-xs font-medium text-slate-500 uppercase">{s.label}</p>
                  <p className="text-2xl font-bold text-slate-900">{count}</p>
                </div>
              );
            })}
            <div className="bg-white rounded-lg border border-slate-200 p-3 text-center" data-testid="stat-Promovido">
              <div className="w-3 h-3 rounded-full bg-emerald-500 mx-auto mb-1.5" />
              <p className="text-xs font-medium text-slate-500 uppercase">Promovido</p>
              <p className="text-2xl font-bold text-slate-900">{promotedProducts.length}</p>
            </div>
          </div>

          {/* Active Pipeline */}
          <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6" data-testid="active-pipeline">
            <h2 className="font-semibold text-slate-900 flex items-center gap-2 mb-4">
              <FlaskConical size={18} className="text-purple-600" />
              En Pipeline ({activeProducts.length})
            </h2>
            {activeProducts.length > 0 ? (
              <div className="space-y-2">
                {activeProducts.map((p) => (
                  <div key={p.product_id} data-testid={`np-row-${p.product_id}`}
                    className="flex items-center gap-4 p-3 rounded-lg border border-slate-200 hover:border-slate-300 transition-colors">
                    <div className="min-w-[180px]">
                      <p className="font-medium text-slate-900 text-sm">{p.service_name}</p>
                      <p className="text-xs text-slate-500">{p.component_type}</p>
                      {p.tipo_corp && <span className="px-1.5 py-0.5 text-[10px] font-medium bg-indigo-100 text-indigo-700 rounded">{p.tipo_corp}</span>}
                    </div>
                    <div className="min-w-[120px]">
                      <p className="text-xs text-slate-400 flex items-center gap-1">
                        <Building2 size={11} />{p.bank_name}
                      </p>
                    </div>
                    <PipelineDots currentStatus={p.status} />
                    <div className="min-w-[140px]">
                      <Select value={p.status} onValueChange={(v) => handleStatusChange(p.product_id, v)}>
                        <SelectTrigger className="h-8 text-xs" data-testid={`np-status-${p.product_id}`}>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {PIPELINE_STATUSES.map(s => (
                            <SelectItem key={s.id} value={s.id}>
                              <StatusBadge status={s.id} />
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    {p.notes && <p className="text-xs text-slate-500 flex-1 truncate">{p.notes}</p>}
                    <Button size="sm" variant="ghost" title="Bitácora de Evolución"
                      onClick={() => openEvolution(p)}
                      className="h-7 w-7 p-0 text-purple-500 hover:text-purple-700 shrink-0"
                      data-testid={`np-evo-btn-${p.product_id}`}>
                      <FileText size={14} />
                    </Button>
                    {canEdit && <Button size="sm" variant="ghost"
                      onClick={() => setDeleteConfirm({ open: true, id: p.product_id, name: p.service_name })}
                      className="h-7 w-7 p-0 text-red-500 hover:text-red-700 shrink-0"
                      data-testid={`np-delete-${p.product_id}`}>
                      <Trash2 size={14} />
                    </Button>}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <FlaskConical size={32} className="mx-auto text-slate-300 mb-2" />
                <p className="text-sm text-slate-400">No hay productos en el pipeline</p>
              </div>
            )}
          </div>

          {/* Promoted Products */}
          {promotedProducts.length > 0 && (
            <div className="bg-white rounded-lg border border-emerald-200 p-6" data-testid="promoted-section">
              <h2 className="font-semibold text-slate-900 flex items-center gap-2 mb-4">
                <CheckCircle2 size={18} className="text-emerald-600" />
                Promovidos a Banco ({promotedProducts.length})
              </h2>
              <div className="space-y-2">
                {promotedProducts.map((p) => (
                  <div key={p.product_id} data-testid={`np-promoted-${p.product_id}`}
                    className="flex items-center gap-4 p-3 rounded-lg border border-emerald-100 bg-emerald-50/50">
                    <div className="min-w-[180px]">
                      <p className="font-medium text-slate-900 text-sm">{p.service_name}</p>
                      <p className="text-xs text-slate-500">{p.component_type}</p>
                      {p.tipo_corp && <span className="px-1.5 py-0.5 text-[10px] font-medium bg-indigo-100 text-indigo-700 rounded">{p.tipo_corp}</span>}
                    </div>
                    <div className="min-w-[120px]">
                      <p className="text-xs text-slate-400 flex items-center gap-1">
                        <Building2 size={11} />{p.bank_name}
                      </p>
                    </div>
                    <PipelineDots currentStatus="Promovido" />
                    <StatusBadge status="Promovido" />
                    <div className="flex items-center gap-1 text-xs text-emerald-600 flex-1">
                      <ArrowRight size={12} />
                      Continúa en integraciones del banco
                    </div>
                    <Button size="sm" variant="ghost" title="Bitácora de Evolución"
                      onClick={() => openEvolution(p)}
                      className="h-7 w-7 p-0 text-purple-500 hover:text-purple-700 shrink-0"
                      data-testid={`np-evo-btn-${p.product_id}`}>
                      <FileText size={14} />
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ==================== CREATE DIALOG ==================== */}
        <Dialog open={addOpen} onOpenChange={setAddOpen}>
          <DialogContent className="max-w-md" data-testid="new-product-dialog">
            <DialogHeader>
              <DialogTitle className="font-manrope">Nuevo Producto — Pipeline I+D</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <Label>Medio de Pago (Catálogo)</Label>
                <Select value={form.service_id} onValueChange={handleServiceSelect}>
                  <SelectTrigger data-testid="np-select-service">
                    <SelectValue placeholder="Seleccione un medio de pago..." />
                  </SelectTrigger>
                  <SelectContent>
                    {services.map(s => (
                      <SelectItem key={s.service_id} value={s.service_id}>{s.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-[10px] text-slate-400 mt-1">Si no aparece, créelo primero en Medios de Pago</p>
              </div>
              <div>
                <Label>Componente</Label>
                <Select value={form.component_type} onValueChange={(v) => setForm({ ...form, component_type: v })}>
                  <SelectTrigger data-testid="np-select-component"><SelectValue placeholder="Seleccione..." /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="VPOS/MPOS">VPOS / MPOS</SelectItem>
                    <SelectItem value="PG/Link">Payment Gateway / Link de Pago</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Banco Patrocinador / Socio</Label>
                <Select value={form.bank_id} onValueChange={(v) => setForm({ ...form, bank_id: v })}>
                  <SelectTrigger data-testid="np-select-bank"><SelectValue placeholder="Seleccione un banco..." /></SelectTrigger>
                  <SelectContent>
                    {banks.map(b => (
                      <SelectItem key={b.bank_id} value={b.bank_id}>{b.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Notas (opcional)</Label>
                <Input placeholder="Notas adicionales..." value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  data-testid="np-input-notes" />
              </div>
              <p className="text-xs text-slate-400 flex items-center gap-1">
                <ChevronRight size={12} />Estado inicial: <StatusBadge status="Negociación" />
              </p>
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={() => setAddOpen(false)}>Cancelar</Button>
                <Button onClick={handleCreate} data-testid="np-save-btn"
                  className="bg-purple-600 hover:bg-purple-700 text-white"
                  disabled={!form.service_id || !form.component_type || !form.bank_id}>
                  Crear Producto
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation */}
        <AlertDialog open={deleteConfirm.open} onOpenChange={(o) => setDeleteConfirm({ ...deleteConfirm, open: o })}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Eliminar Producto</AlertDialogTitle>
              <AlertDialogDescription>
                Eliminar <strong>"{deleteConfirm.name}"</strong> del pipeline? Esta acción no se puede deshacer.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancelar</AlertDialogCancel>
              <AlertDialogAction onClick={handleDelete} className="bg-red-600 hover:bg-red-700 text-white"
                data-testid="np-confirm-delete">
                Eliminar
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* ==================== EVOLUTION + TRANSITIONS MODAL ==================== */}
        <Dialog open={evoOpen} onOpenChange={(o) => { if (!o) { setEvoOpen(false); setEvoEditing(null); } }}>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="np-evolution-modal">
            <DialogHeader>
              <DialogTitle className="font-manrope text-xl flex items-center gap-2">
                <FileText size={20} className="text-purple-600" />
                Bitácora — {evoProduct?.service_name}
                {evoProduct?.status && <StatusBadge status={evoProduct.status} />}
              </DialogTitle>
            </DialogHeader>

            {/* Form to add evolution entry */}
            <div className="bg-slate-50 rounded-lg border border-slate-200 p-3 space-y-2">
              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">{evoEditing ? 'Editar Entrada' : 'Nuevo Hito'}</p>
              <Textarea value={evoForm.comment} onChange={(e) => setEvoForm(p => ({ ...p, comment: e.target.value }))}
                placeholder="Describa el avance técnico, observación o hito alcanzado..." className="text-sm min-h-[70px]" data-testid="np-evo-comment" />
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <Label className="text-[10px] text-slate-500">Fase</Label>
                  <Select value={evoForm.phase} onValueChange={(v) => setEvoForm(p => ({ ...p, phase: v }))}>
                    <SelectTrigger className="h-8 text-xs" data-testid="np-evo-phase-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {PIPELINE_STATUSES.map(s => <SelectItem key={s.id} value={s.id}>{s.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-[10px] text-slate-500">Fecha</Label>
                  <Input type="date" value={evoForm.date} onChange={(e) => setEvoForm(p => ({ ...p, date: e.target.value }))} className="h-8 text-xs" data-testid="np-evo-date" />
                </div>
              </div>
              <div className="flex justify-end gap-2">
                {evoEditing && (
                  <Button size="sm" variant="outline" className="h-8 text-xs" onClick={() => {
                    setEvoEditing(null);
                    setEvoForm({ comment: '', phase: evoProduct?.status === 'Promovido' ? 'IMPLE' : (evoProduct?.status || 'Negociación'), date: new Date().toISOString().slice(0, 10) });
                  }}>Cancelar Edición</Button>
                )}
                <Button size="sm" className="h-8 text-xs bg-purple-600 hover:bg-purple-700 text-white" onClick={saveEvoEntry} data-testid="np-evo-save-btn">
                  {evoEditing ? 'Actualizar' : '+ Registrar Hito'}
                </Button>
              </div>
            </div>

            {/* Unified Timeline */}
            <div className="mt-2">
              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-3">
                Línea de Tiempo ({timeline.length})
              </p>
              {evoLoading ? (
                <p className="text-sm text-slate-400 text-center py-4">Cargando...</p>
              ) : timeline.length === 0 ? (
                <p className="text-sm text-slate-400 text-center py-4 italic">Sin registros</p>
              ) : (
                <div className="relative pl-6 space-y-0">
                  <div className="absolute left-[10px] top-2 bottom-2 w-0.5 bg-slate-200" />
                  {timeline.map((item) => {
                    if (item._type === 'transition') {
                      const tsDate = (item.timestamp || '').slice(0, 10);
                      const tsTime = (item.timestamp || '').slice(11, 16);
                      return (
                        <div key={item.transition_id} className="relative pb-4" data-testid={`np-transition-${item.transition_id}`}>
                          <div className="absolute left-[-18px] top-1 w-3.5 h-3.5 rounded-full border-2 border-white bg-indigo-500" />
                          <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-3 ml-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <ArrowRightLeft size={12} className="text-indigo-500" />
                              <span className="text-[10px] font-semibold text-indigo-600 uppercase">Cambio de Estado</span>
                              <span className="text-[10px] text-slate-400">{tsDate} {tsTime}</span>
                            </div>
                            <div className="flex items-center gap-1.5 mt-1.5 text-sm text-slate-700">
                              {item.old_status ? <StatusBadge status={item.old_status} /> : <span className="text-xs text-slate-400 italic">Inicio</span>}
                              <ArrowRight size={14} className="text-slate-400 shrink-0" />
                              <StatusBadge status={item.new_status} />
                            </div>
                            <div className="flex items-center gap-3 mt-1.5 text-[10px] text-slate-500">
                              <span>Por: {item.user_name}</span>
                              {item.days_in_previous_phase != null && (
                                <span className="flex items-center gap-0.5 text-indigo-600 font-medium">
                                  <Clock size={10} />
                                  {item.days_in_previous_phase} día{item.days_in_previous_phase !== 1 ? 's' : ''} en {item.old_status}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    }

                    // Evolution entry
                    const dotColor = getStatusStyle(item.phase).dot || 'bg-slate-400';
                    return (
                      <div key={item.entry_id} className="relative pb-4" data-testid={`np-evo-entry-${item.entry_id}`}>
                        <div className={`absolute left-[-18px] top-1 w-3.5 h-3.5 rounded-full border-2 border-white ${dotColor}`} />
                        <div className="bg-white border border-slate-200 rounded-lg p-3 ml-1">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1.5">
                                <StatusBadge status={item.phase} />
                                <span className="text-[10px] text-slate-400">{item.date}</span>
                                {item.updated_at && <span className="text-[9px] text-slate-300 italic">editado</span>}
                              </div>
                              <p className="text-sm text-slate-800 whitespace-pre-wrap break-words">{item.comment}</p>
                            </div>
                            <div className="flex items-center gap-0.5 flex-shrink-0">
                              <Button size="sm" variant="ghost" className="h-6 w-6 p-0 text-slate-400 hover:text-purple-600" onClick={() => startEditEvo(item)} data-testid={`np-evo-edit-${item.entry_id}`}>
                                <Pencil size={11} />
                              </Button>
                              <Button size="sm" variant="ghost" className="h-6 w-6 p-0 text-slate-300 hover:text-red-500" onClick={() => deleteEvoEntry(item.entry_id)} data-testid={`np-evo-delete-${item.entry_id}`}>
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

export default NewProducts;
