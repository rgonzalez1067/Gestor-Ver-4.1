import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Building2, Calendar, Download, Printer, ArrowRight, ArrowLeft, Package, FileText, Loader2, Pencil, Trash2, ShieldAlert } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import api from '../utils/api';
import { toast } from 'sonner';
import { usePermission } from '../hooks/usePermission';

const InvoicedExitsReport = () => {
  const navigate = useNavigate();
  const today = new Date();
  const firstDay = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0];
  const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().split('T')[0];

  const { user: currentUser } = usePermission('inventarios');
  const isAdmin = currentUser?.role === 'admin';

  const [desde, setDesde] = useState(firstDay);
  const [hasta, setHasta] = useState(lastDay);
  const [loading, setLoading] = useState(false);
  const [reportData, setReportData] = useState(null);

  // ── Estados del Modal Admin de Edición/Eliminación ──
  const [editOpen, setEditOpen] = useState(false);
  const [editExit, setEditExit] = useState(null); // registro original
  const [editForm, setEditForm] = useState(null);
  const [editSaving, setEditSaving] = useState(false);
  const [editDeleting, setEditDeleting] = useState(false);

  const fetchReport = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/inventory/invoiced-exits-report?desde=${desde}&hasta=${hasta}`);
      setReportData(res.data);
    } catch (err) {
      toast.error('Error al cargar reporte');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchReport(); }, []);

  const exportToExcel = () => {
    if (!reportData?.warehouses?.length) { toast.error('No hay datos para exportar'); return; }
    let csv = '\uFEFF';
    csv += 'RELACION DE SALIDAS FACTURADAS\n';
    csv += `Periodo: ${desde} al ${hasta}\n\n`;

    for (const wh of reportData.warehouses) {
      csv += `Almacen: ${wh.warehouse_name}\n`;
      csv += 'Fecha,Nombre del Item,Tipo,Cantidad,Nro. Factura,Cliente,Cotizacion,Referencia,Operador\n';
      for (const exit of wh.exits) {
        csv += `${exit.fecha},"${exit.item_name}",${exit.item_type},${exit.quantity},"${exit.invoice_number}","${exit.client_name}","${exit.quote_number}","${exit.reference}","${exit.created_by}"\n`;
      }
      csv += `,,Total Unidades:,${wh.total_units},,,,\n\n`;
    }
    csv += `TOTAL GENERAL SALIDAS:,,,${reportData.total_exits},,,,\n`;

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Salidas_Facturadas_${desde}_${hasta}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success('Reporte exportado a Excel/CSV');
  };

  const handlePrint = () => window.print();

  // ── Apertura modal admin: el reporte trae cada salida; usamos movement_id ──
  const openEditExit = (exit) => {
    setEditExit(exit);
    setEditForm({
      fecha: exit.fecha || '',
      item_name: exit.item_name || '',
      item_type: exit.item_type || '',
      quantity: exit.quantity ?? 0,
      unit_cost: exit.unit_cost ?? 0,
      invoice_number: exit.invoice_number || '',
      client_name: exit.client_name || '',
      quote_number: exit.quote_number || '',
      reference: exit.reference || '',
      serials: Array.isArray(exit.serials) ? exit.serials.join(', ') : (exit.serials || ''),
      notes: exit.notes || '',
    });
    setEditOpen(true);
  };

  const saveEditExit = async () => {
    if (!editExit?.movement_id) { toast.error('Registro sin ID'); return; }
    setEditSaving(true);
    try {
      const payload = { ...editForm };
      if (payload.quantity !== '' && payload.quantity !== null) payload.quantity = Number(payload.quantity);
      if (payload.unit_cost !== '' && payload.unit_cost !== null) payload.unit_cost = Number(payload.unit_cost);
      const res = await api.put(`/inventory/movements/${editExit.movement_id}`, payload);
      if (res.data?.changes_count === 0) toast.info('No se detectaron cambios');
      else toast.success(`Registro actualizado · ${res.data.changes_count} campo(s)`);
      setEditOpen(false);
      fetchReport();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al guardar');
    } finally {
      setEditSaving(false);
    }
  };

  const deleteEditExit = async () => {
    if (!editExit?.movement_id) return;
    if (!window.confirm(`¿Eliminar definitivamente el registro de salida de "${editExit.item_name}" (Factura ${editExit.invoice_number || 'S/N'})?\n\nEsta acción es irreversible y reescribe el inventario.`)) return;
    setEditDeleting(true);
    try {
      await api.delete(`/inventory/movements/${editExit.movement_id}`);
      toast.success('Registro eliminado');
      setEditOpen(false);
      fetchReport();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al eliminar');
    } finally {
      setEditDeleting(false);
    }
  };

  return (
    <div className="space-y-6" data-testid="invoiced-exits-report">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div className="flex items-center gap-3">
          {/* Botón "Volver" embebido en la app (no depende del navegador) */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate(-1)}
            className="border-slate-300 hover:bg-slate-100 print:hidden"
            data-testid="report-back-btn"
            title="Volver al módulo anterior">
            <ArrowLeft size={14} className="mr-1.5" />
            <span className="text-xs">Volver</span>
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Relacion de Salidas Facturadas</h1>
            <p className="text-sm text-slate-500">Auditoria contable de inventario despachado por almacen</p>
          </div>
        </div>
        <div className="flex items-end gap-3 bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex-wrap">
          <div>
            <Label className="text-[10px] text-slate-500 uppercase font-semibold">Desde</Label>
            <Input type="date" value={desde} onChange={e => setDesde(e.target.value)}
              className="h-8 text-sm w-36" data-testid="report-desde" />
          </div>
          <ArrowRight size={14} className="text-slate-300 mb-2" />
          <div>
            <Label className="text-[10px] text-slate-500 uppercase font-semibold">Hasta</Label>
            <Input type="date" value={hasta} onChange={e => setHasta(e.target.value)}
              className="h-8 text-sm w-36" data-testid="report-hasta" />
          </div>
          <Button onClick={fetchReport} disabled={loading} size="sm" className="bg-blue-600 hover:bg-blue-700 mb-0.5" data-testid="report-search">
            {loading ? <Loader2 size={14} className="animate-spin" /> : <Calendar size={14} />}
            <span className="ml-1.5 text-xs">Consultar</span>
          </Button>
          {/* ── Botón Admin embebido: solo visible para rol 'admin' ── */}
          {isAdmin && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => toast.info('Use el botón "Editar" en la columna Acciones de cada fila para corregir un registro.')}
              className="border-amber-300 text-amber-700 hover:bg-amber-50 mb-0.5"
              data-testid="report-admin-tools-btn">
              <ShieldAlert size={14} className="mr-1.5" />
              <span className="text-xs">Admin: Gestión de Salidas</span>
            </Button>
          )}
          <Button onClick={exportToExcel} variant="outline" size="sm" className="mb-0.5" data-testid="report-export-csv">
            <Download size={14} className="mr-1.5" /> <span className="text-xs">CSV</span>
          </Button>
          <Button onClick={handlePrint} variant="outline" size="sm" className="mb-0.5" data-testid="report-print">
            <Printer size={14} className="mr-1.5" /> <span className="text-xs">Imprimir</span>
          </Button>
        </div>
      </div>

      {/* Cuerpo del reporte */}
      {loading && (
        <div className="flex justify-center items-center py-12">
          <Loader2 size={32} className="animate-spin text-blue-500" />
        </div>
      )}

      {reportData && !loading && (
        <div className="space-y-6">
          {reportData.warehouses?.length === 0 && (
            <div className="text-center py-12 bg-white rounded-xl border border-slate-200">
              <FileText className="mx-auto text-slate-300 mb-2" size={48} />
              <p className="text-slate-500 text-sm">No hay salidas facturadas en este periodo</p>
            </div>
          )}

          {reportData.warehouses?.map((wh, widx) => (
            <div key={widx} className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
              <div className="bg-gradient-to-r from-slate-800 to-slate-700 px-5 py-3 flex items-center gap-2">
                <Building2 size={16} className="text-slate-300" />
                <h2 className="font-bold text-white text-sm">{wh.warehouse_name}</h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 border-b border-slate-200 uppercase tracking-wider text-[10px] text-slate-500 font-semibold">
                    <tr>
                      <th className="px-4 py-3 text-left">Fecha</th>
                      <th className="px-4 py-3 text-left">Item</th>
                      <th className="px-4 py-3 text-left">Tipo</th>
                      <th className="px-4 py-3 text-center">Cant.</th>
                      <th className="px-4 py-3 text-left">Nro. Factura</th>
                      <th className="px-4 py-3 text-left">Cliente</th>
                      <th className="px-4 py-3 text-left">Cotización</th>
                      <th className="px-4 py-3 text-left">Operador</th>
                      {isAdmin && <th className="px-3 py-3 text-center print:hidden">Acciones</th>}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {wh.exits.map((exit, eidx) => (
                      <tr key={eidx} className="hover:bg-slate-50/50">
                        <td className="px-4 py-2.5 text-slate-500 text-xs">{exit.fecha}</td>
                        <td className="px-4 py-2.5 font-semibold text-slate-800 uppercase text-xs">{exit.item_name}</td>
                        <td className="px-4 py-2.5 text-slate-500 text-xs">{exit.item_type}</td>
                        <td className="px-4 py-2.5 text-center">
                          <span className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded font-bold text-xs">{exit.quantity}</span>
                        </td>
                        <td className="px-4 py-2.5">
                          {exit.invoice_number ? (
                            <span className="bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-lg font-bold text-xs border border-emerald-100">
                              {exit.invoice_number}
                            </span>
                          ) : (
                            <span className="text-slate-300 text-xs">S/N</span>
                          )}
                        </td>
                        <td className="px-4 py-2.5 text-slate-600 text-xs truncate max-w-[150px]">{exit.client_name || '—'}</td>
                        <td className="px-4 py-2.5 text-blue-600 text-xs font-medium">{exit.quote_number || '—'}</td>
                        <td className="px-4 py-2.5 text-slate-400 text-xs">{exit.created_by || '—'}</td>
                        {isAdmin && (
                          <td className="px-3 py-2.5 text-center print:hidden">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 px-2 text-amber-600 hover:bg-amber-50"
                              onClick={() => openEditExit(exit)}
                              title="Editar o eliminar este registro (Admin)"
                              data-testid={`edit-exit-${exit.movement_id || eidx}`}>
                              <Pencil size={12} className="mr-1" />
                              <span className="text-[10px]">Gestionar</span>
                            </Button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="bg-slate-50 border-t border-slate-200">
                      <td colSpan={3} className="px-4 py-2.5 text-xs font-bold text-slate-700">Total {wh.warehouse_name}</td>
                      <td className="px-4 py-2.5 text-center">
                        <span className="bg-slate-800 text-white px-2 py-0.5 rounded font-bold text-xs">{wh.total_units}</span>
                      </td>
                      <td colSpan={isAdmin ? 5 : 4}></td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          ))}

          {reportData.total_exits > 0 && (
            <div className="flex justify-end">
              <div className="bg-slate-900 text-white px-6 py-3 rounded-xl font-bold text-sm flex items-center gap-3">
                <Package size={18} />
                Total General Salidas: {reportData.total_exits} unidades
              </div>
            </div>
          )}
        </div>
      )}

      {/* Modal Admin de edición/eliminación de salida facturada */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="max-w-2xl" data-testid="admin-edit-exit-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-amber-700">
              <ShieldAlert size={18} /> Gestión administrativa de salida facturada
            </DialogTitle>
          </DialogHeader>
          {editForm && (
            <div className="space-y-3 text-sm">
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-2 text-xs text-amber-800">
                <b>Atención:</b> los cambios aquí reescriben el histórico de inventario y quedan registrados en bitácora.
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs">Item</Label>
                  <Input value={editForm.item_name} onChange={e => setEditForm({...editForm, item_name: e.target.value})} data-testid="edit-exit-name" />
                </div>
                <div>
                  <Label className="text-xs">Tipo</Label>
                  <Input value={editForm.item_type} onChange={e => setEditForm({...editForm, item_type: e.target.value})} data-testid="edit-exit-type" />
                </div>
                <div>
                  <Label className="text-xs">Cantidad</Label>
                  <Input type="number" value={editForm.quantity} onChange={e => setEditForm({...editForm, quantity: e.target.value})} data-testid="edit-exit-qty" />
                </div>
                <div>
                  <Label className="text-xs">Costo unitario</Label>
                  <Input type="number" step="0.01" value={editForm.unit_cost} onChange={e => setEditForm({...editForm, unit_cost: e.target.value})} data-testid="edit-exit-cost" />
                </div>
                <div>
                  <Label className="text-xs">Nro. Factura</Label>
                  <Input value={editForm.invoice_number} onChange={e => setEditForm({...editForm, invoice_number: e.target.value})} data-testid="edit-exit-invoice" />
                </div>
                <div>
                  <Label className="text-xs">Nro. Cotización</Label>
                  <Input value={editForm.quote_number} onChange={e => setEditForm({...editForm, quote_number: e.target.value})} data-testid="edit-exit-quote" />
                </div>
                <div className="col-span-2">
                  <Label className="text-xs">Cliente</Label>
                  <Input value={editForm.client_name} onChange={e => setEditForm({...editForm, client_name: e.target.value})} data-testid="edit-exit-client" />
                </div>
                <div className="col-span-2">
                  <Label className="text-xs">Seriales (separados por coma)</Label>
                  <Input value={editForm.serials} onChange={e => setEditForm({...editForm, serials: e.target.value})} data-testid="edit-exit-serials" />
                </div>
                <div className="col-span-2">
                  <Label className="text-xs">Referencia</Label>
                  <Input value={editForm.reference} onChange={e => setEditForm({...editForm, reference: e.target.value})} data-testid="edit-exit-reference" />
                </div>
                <div className="col-span-2">
                  <Label className="text-xs">Notas</Label>
                  <Input value={editForm.notes} onChange={e => setEditForm({...editForm, notes: e.target.value})} data-testid="edit-exit-notes" />
                </div>
              </div>
            </div>
          )}
          <DialogFooter className="gap-2 flex-row justify-between">
            <Button
              variant="destructive"
              size="sm"
              onClick={deleteEditExit}
              disabled={editDeleting || editSaving}
              data-testid="edit-exit-delete-btn">
              {editDeleting ? <Loader2 size={14} className="animate-spin mr-1" /> : <Trash2 size={14} className="mr-1" />}
              Eliminar registro
            </Button>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setEditOpen(false)} disabled={editSaving || editDeleting}>
                Cancelar
              </Button>
              <Button
                size="sm"
                onClick={saveEditExit}
                disabled={editSaving || editDeleting}
                className="bg-amber-600 hover:bg-amber-700"
                data-testid="edit-exit-save-btn">
                {editSaving && <Loader2 size={14} className="animate-spin mr-1" />}
                Guardar cambios
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Print styles */}
      <style>{`
        @media print {
          .print\\:hidden { display: none !important; }
          body { font-size: 11px; }
        }
      `}</style>
    </div>
  );
};

export default InvoicedExitsReport;
