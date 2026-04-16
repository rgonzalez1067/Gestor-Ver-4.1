import { useState, useEffect } from 'react';
import { Building2, Calendar, Download, Printer, ArrowRight, Package, FileText, Loader2 } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import api from '../utils/api';
import { toast } from 'sonner';

const InvoicedExitsReport = () => {
  const today = new Date();
  const firstDay = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0];
  const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().split('T')[0];

  const [desde, setDesde] = useState(firstDay);
  const [hasta, setHasta] = useState(lastDay);
  const [loading, setLoading] = useState(false);
  const [reportData, setReportData] = useState(null);

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

  return (
    <div className="space-y-6" data-testid="invoiced-exits-report">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Relacion de Salidas Facturadas</h1>
          <p className="text-sm text-slate-500">Auditoria contable de inventario despachado por almacen</p>
        </div>
        <div className="flex items-end gap-3 bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
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
          <Button size="sm" onClick={fetchReport} disabled={loading} className="h-8" data-testid="report-search">
            {loading ? <Loader2 size={14} className="animate-spin" /> : 'Buscar'}
          </Button>
          <Button size="sm" variant="outline" onClick={exportToExcel} className="h-8" data-testid="report-export-excel">
            <Download size={14} className="mr-1" /> Excel
          </Button>
          <Button size="sm" variant="outline" onClick={handlePrint} className="h-8 print:hidden">
            <Printer size={14} className="mr-1" /> Imprimir
          </Button>
        </div>
      </div>

      {loading && (
        <div className="flex justify-center py-20">
          <Loader2 size={32} className="animate-spin text-slate-400" />
        </div>
      )}

      {!loading && reportData && (
        <div className="space-y-8">
          {reportData.warehouses?.length === 0 && (
            <div className="text-center py-20 bg-white rounded-xl border border-dashed border-slate-300">
              <Package className="mx-auto text-slate-200 mb-4" size={48} />
              <p className="text-slate-400 font-medium">No se registran salidas en este periodo.</p>
            </div>
          )}

          {reportData.warehouses?.map((wh, idx) => (
            <div key={idx} className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden"
              data-testid={`warehouse-section-${idx}`}>
              <div className="flex items-center gap-3 px-6 py-4 bg-slate-800 text-white">
                <Building2 size={20} className="text-blue-400" />
                <h3 className="text-sm font-bold uppercase tracking-wide">{wh.warehouse_name}</h3>
                <span className="ml-auto text-xs bg-blue-600 px-2 py-0.5 rounded-full font-bold">
                  {wh.total_units} uds.
                </span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid={`exits-table-${idx}`}>
                  <thead>
                    <tr className="bg-slate-50 text-[10px] uppercase font-bold text-slate-500 border-b border-slate-200">
                      <th className="px-4 py-3 text-left">Fecha</th>
                      <th className="px-4 py-3 text-left">Nombre del Item</th>
                      <th className="px-4 py-3 text-left">Tipo</th>
                      <th className="px-4 py-3 text-center">Uds.</th>
                      <th className="px-4 py-3 text-left">Nro. Factura</th>
                      <th className="px-4 py-3 text-left">Cliente</th>
                      <th className="px-4 py-3 text-left">Cotizacion</th>
                      <th className="px-4 py-3 text-left">Operador</th>
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
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="bg-slate-50 border-t border-slate-200">
                      <td colSpan={3} className="px-4 py-2.5 text-xs font-bold text-slate-700">Total {wh.warehouse_name}</td>
                      <td className="px-4 py-2.5 text-center">
                        <span className="bg-slate-800 text-white px-2 py-0.5 rounded font-bold text-xs">{wh.total_units}</span>
                      </td>
                      <td colSpan={4}></td>
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
