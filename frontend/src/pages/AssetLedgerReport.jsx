import { useState, useEffect, useRef } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Printer, ArrowLeft, Package } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';

const formatCurrency = (num) => {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(num || 0);
};

const formatDate = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('es-VE', { day: '2-digit', month: '2-digit', year: 'numeric' });
};

export const AssetLedgerReport = () => {
  const [reportData, setReportData] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const printRef = useRef();

  useEffect(() => {
    const fetchReport = async () => {
      try {
        const res = await api.get('/inventory/asset-ledger');
        setReportData(res.data);
      } catch { toast.error('Error al generar reporte Mayor de Activos'); }
      finally { setLoading(false); }
    };
    fetchReport();
  }, []);

  const handlePrint = () => window.print();

  if (loading) {
    return (
      <div className="flex min-h-screen bg-slate-50">
        <Sidebar />
        <main className="flex-1 p-8 flex items-center justify-center">
          <div className="text-slate-400 text-lg">Generando Mayor de Activos (PEPS)...</div>
        </main>
      </div>
    );
  }

  const items = reportData?.items || [];
  const grandTotal = reportData?.grand_total || 0;

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 p-6 overflow-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6 print:hidden">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate('/inventory')} data-testid="back-btn">
              <ArrowLeft className="w-4 h-4 mr-1" /> Volver
            </Button>
            <div>
              <h1 className="text-2xl font-bold text-slate-800">Mayor de Activos</h1>
              <p className="text-sm text-slate-500">Valoración PEPS (Primero en Entrar, Primero en Salir)</p>
            </div>
          </div>
          <Button onClick={handlePrint} variant="outline" size="sm" data-testid="print-btn">
            <Printer className="w-4 h-4 mr-1" /> Imprimir
          </Button>
        </div>

        {/* Report Content */}
        <div ref={printRef} className="bg-white rounded-lg border border-slate-200 p-6 print:border-0 print:shadow-none print:p-0">
          {/* Print Header */}
          <div className="hidden print:block mb-4 text-center border-b pb-3">
            <h2 className="text-xl font-bold">MAYOR DE ACTIVOS — VALORACIÓN PEPS</h2>
            <p className="text-sm text-slate-500">
              Fecha de emisión: {formatDate(reportData?.report_date)} | Método: {reportData?.method}
            </p>
          </div>

          {items.length === 0 ? (
            <div className="text-center py-16 text-slate-400" data-testid="empty-state">
              <Package className="w-12 h-12 mx-auto mb-3 opacity-40" />
              <p className="text-lg">No hay activos con saldo disponible</p>
              <p className="text-sm mt-1">Registre entradas en el Almacén Principal para generar el reporte</p>
            </div>
          ) : (
            <>
              {items.map((item) => (
                <div key={item.item_id} className="mb-6" data-testid={`item-${item.item_id}`}>
                  {/* Item Header */}
                  <div className="flex items-center justify-between bg-slate-700 text-white px-4 py-2 rounded-t-md">
                    <div>
                      <span className="font-semibold text-sm">{item.item_name}</span>
                      {item.item_type && (
                        <span className="ml-2 text-xs bg-slate-500 px-2 py-0.5 rounded">{item.item_type}</span>
                      )}
                    </div>
                    <div className="text-right text-xs">
                      <span className="opacity-70">Unidades: </span>
                      <span className="font-bold">{item.total_units}</span>
                      <span className="mx-2">|</span>
                      <span className="opacity-70">Total: </span>
                      <span className="font-bold text-emerald-300">{formatCurrency(item.item_total)}</span>
                    </div>
                  </div>

                  {/* Lots Table */}
                  <table className="w-full border-collapse text-xs" data-testid={`table-${item.item_id}`}>
                    <thead>
                      <tr className="bg-slate-100 text-slate-600">
                        <th className="px-3 py-2 text-left font-semibold border border-slate-200">Fecha Compra</th>
                        <th className="px-3 py-2 text-left font-semibold border border-slate-200">Proveedor</th>
                        <th className="px-3 py-2 text-left font-semibold border border-slate-200">Referencia</th>
                        <th className="px-3 py-2 text-right font-semibold border border-slate-200">Cant. Comprada</th>
                        <th className="px-3 py-2 text-right font-semibold border border-slate-200">Saldo Disponible</th>
                        <th className="px-3 py-2 text-right font-semibold border border-slate-200">Costo Unitario</th>
                        <th className="px-3 py-2 text-right font-semibold border border-slate-200">Valor del Lote</th>
                      </tr>
                    </thead>
                    <tbody>
                      {item.lots.map((lot, idx) => (
                        <tr key={idx} className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                          <td className="px-3 py-1.5 border border-slate-200">{formatDate(lot.purchase_date)}</td>
                          <td className="px-3 py-1.5 border border-slate-200">{lot.supplier || '—'}</td>
                          <td className="px-3 py-1.5 border border-slate-200">{lot.invoice_ref || '—'}</td>
                          <td className="px-3 py-1.5 text-right border border-slate-200 text-slate-500">{lot.quantity_purchased}</td>
                          <td className="px-3 py-1.5 text-right border border-slate-200 font-semibold">
                            <span className={lot.remaining < lot.quantity_purchased ? 'text-amber-600' : 'text-slate-700'}>
                              {lot.remaining}
                            </span>
                          </td>
                          <td className="px-3 py-1.5 text-right border border-slate-200 font-mono">{formatCurrency(lot.unit_cost)}</td>
                          <td className="px-3 py-1.5 text-right border border-slate-200 font-mono font-semibold text-emerald-700">{formatCurrency(lot.lot_value)}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr className="bg-slate-100 font-semibold">
                        <td colSpan={4} className="px-3 py-2 text-right border border-slate-200">Total {item.item_name}:</td>
                        <td className="px-3 py-2 text-right border border-slate-200">{item.total_units}</td>
                        <td className="px-3 py-2 border border-slate-200"></td>
                        <td className="px-3 py-2 text-right border border-slate-200 font-mono text-emerald-700">{formatCurrency(item.item_total)}</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              ))}

              {/* Grand Total */}
              <div className="mt-4 flex justify-end" data-testid="grand-total">
                <div className="bg-slate-800 text-white px-6 py-3 rounded-md">
                  <span className="text-sm opacity-80 mr-3">Gran Total Contable:</span>
                  <span className="text-xl font-bold text-emerald-300">{formatCurrency(grandTotal)}</span>
                </div>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
};

export default AssetLedgerReport;
