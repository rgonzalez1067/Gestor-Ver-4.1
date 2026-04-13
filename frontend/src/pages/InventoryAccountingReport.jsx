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

export const InventoryAccountingReport = () => {
  const [reportData, setReportData] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const printRef = useRef();

  useEffect(() => {
    const fetchReport = async () => {
      try {
        const res = await api.get('/inventory/accounting-report');
        setReportData(res.data);
      } catch { toast.error('Error al generar reporte contable'); }
      finally { setLoading(false); }
    };
    fetchReport();
  }, []);

  const handlePrint = () => {
    window.print();
  };

  const formatDate = (iso) => {
    if (!iso) return '';
    return new Date(iso).toLocaleDateString('es-VE', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  if (loading) {
    return (
      <div className="flex min-h-screen bg-slate-50">
        <Sidebar />
        <main className="flex-1 p-8 flex items-center justify-center">
          <div className="text-slate-400 text-lg">Generando reporte contable...</div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-slate-100">
      <div className="print:hidden"><Sidebar /></div>
      <main className="flex-1 p-4 md:p-10 print:p-0" data-testid="accounting-report-page">

        <div className="max-w-6xl mx-auto" ref={printRef}>

          {/* Header */}
          <div className="flex justify-between items-start mb-10 border-b-2 border-slate-200 pb-6 print:mb-6">
            <div>
              <h1 className="text-3xl font-bold text-slate-800 uppercase tracking-tight print:text-2xl">Valor Contable del Inventario</h1>
              <p className="text-slate-500 mt-1 text-sm">Metodo de Valoracion: Costo Promedio Ponderado (CPP)</p>
            </div>
            <div className="text-right">
              <p className="font-bold text-slate-700">Mega Soft Computacion C.A.</p>
              <p className="text-sm text-slate-500">Fecha de Reporte: {formatDate(reportData?.report_date)}</p>
              <div className="flex gap-2 mt-4 print:hidden">
                <Button variant="outline" size="sm" onClick={() => navigate('/inventory')} data-testid="back-to-inventory">
                  <ArrowLeft size={14} className="mr-1" /> Volver
                </Button>
                <Button onClick={handlePrint} className="bg-slate-800 hover:bg-slate-700 text-white" size="sm" data-testid="print-report-btn">
                  <Printer size={14} className="mr-1" /> Generar PDF Contable
                </Button>
              </div>
            </div>
          </div>

          {/* Kardex por Item */}
          {(!reportData?.items || reportData.items.length === 0) ? (
            <div className="bg-white rounded-xl p-12 text-center text-slate-400 border">
              <Package size={48} className="mx-auto mb-4 text-slate-300" />
              <p className="text-lg">No hay movimientos de inventario registrados</p>
              <p className="text-sm mt-1">Registre entradas y salidas en Inventarios para generar este reporte</p>
            </div>
          ) : (
            <>
              {reportData.items.map((item) => (
                <div key={item.item_id} className="mb-12 bg-white p-6 rounded-xl shadow-sm border border-slate-200 print:shadow-none print:rounded-none print:mb-6 print:break-inside-avoid-page" data-testid={`kardex-item-${item.item_id}`}>
                  <h3 className="text-xl font-bold text-blue-900 mb-4 flex items-center gap-2 print:text-lg">
                    <Package size={20} className="text-blue-600" />
                    {item.item_name}
                    <span className="text-xs font-normal text-slate-400 ml-2">({item.item_type})</span>
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs mb-4">
                      <thead className="bg-slate-50 text-slate-400">
                        <tr>
                          <th className="px-4 py-2 text-left text-[10px] uppercase tracking-wider">Fecha</th>
                          <th className="px-4 py-2 text-left text-[10px] uppercase tracking-wider">Movimiento</th>
                          <th className="px-4 py-2 text-right text-[10px] uppercase tracking-wider">Cantidad</th>
                          <th className="px-4 py-2 text-right text-[10px] uppercase tracking-wider">Costo Unit.</th>
                          <th className="px-4 py-2 text-right text-[10px] uppercase tracking-wider">Subtotal Mov.</th>
                          <th className="px-4 py-2 text-left text-[10px] uppercase tracking-wider">Proveedor</th>
                          <th className="px-4 py-2 text-left text-[10px] uppercase tracking-wider">Referencia</th>
                          <th className="px-4 py-2 text-right text-[10px] uppercase tracking-wider">Saldo Qty</th>
                          <th className="px-4 py-2 text-right text-[10px] uppercase tracking-wider">CPP</th>
                        </tr>
                      </thead>
                      <tbody>
                        {item.kardex.map((row, idx) => (
                          <tr key={idx} className="border-b border-slate-50">
                            <td className="px-4 py-2.5 text-slate-600">{row.date}</td>
                            <td className="px-4 py-2.5">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${row.type_label === 'ENTRADA' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                                {row.type_label}
                              </span>
                            </td>
                            <td className="px-4 py-2.5 text-right font-medium">{row.quantity}</td>
                            <td className="px-4 py-2.5 text-right">{formatCurrency(row.cost_used)}</td>
                            <td className="px-4 py-2.5 text-right font-medium">{formatCurrency(row.subtotal)}</td>
                            <td className="px-4 py-2.5 text-xs text-slate-600">{row.supplier || '—'}</td>
                            <td className="px-4 py-2.5 text-xs text-slate-500">{row.invoice_ref || row.reference || '—'}</td>
                            <td className="px-4 py-2.5 text-right text-slate-500">{row.balance_qty}</td>
                            <td className="px-4 py-2.5 text-right font-bold text-blue-700">{formatCurrency(row.cpp)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {/* Resumen del Item */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 bg-blue-50 p-4 rounded-lg border-l-4 border-blue-500">
                    <div>
                      <p className="text-[10px] text-blue-600 font-bold uppercase">Unidades Disponibles</p>
                      <p className="text-xl font-bold text-blue-900">{item.current_qty}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-blue-600 font-bold uppercase">Costo Promedio Ponderado (CPP)</p>
                      <p className="text-xl font-bold text-blue-900">{formatCurrency(item.current_cpp)}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-[10px] text-blue-600 font-bold uppercase">Valor Total Calculado</p>
                      <p className="text-xl font-bold text-blue-900">{formatCurrency(item.total_value)}</p>
                    </div>
                  </div>
                </div>
              ))}

              {/* Resumen Consolidado */}
              <div className="mt-12 print:break-before-page">
                <h2 className="text-2xl font-bold text-slate-800 mb-6 border-b pb-2">Resumen de Valoracion de Inventario</h2>
                <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden print:shadow-none">
                  <table className="w-full text-sm text-left">
                    <thead className="bg-slate-800 text-white">
                      <tr>
                        <th className="px-6 py-4">Descripcion del Item</th>
                        <th className="px-6 py-4 text-center">Tipo</th>
                        <th className="px-6 py-4 text-center">Unidades Disp.</th>
                        <th className="px-6 py-4 text-right">CPP (Promedio)</th>
                        <th className="px-6 py-4 text-right">Valor Contable Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {reportData.items.map((item) => (
                        <tr key={item.item_id} className="border-b hover:bg-slate-50 transition">
                          <td className="px-6 py-4 font-medium text-slate-900">{item.item_name}</td>
                          <td className="px-6 py-4 text-center text-xs text-slate-500">{item.item_type}</td>
                          <td className="px-6 py-4 text-center font-semibold">{item.current_qty}</td>
                          <td className="px-6 py-4 text-right">{formatCurrency(item.current_cpp)}</td>
                          <td className="px-6 py-4 text-right font-bold text-slate-800">{formatCurrency(item.total_value)}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="bg-slate-100 font-bold text-slate-900 border-t-2 border-slate-300">
                      <tr>
                        <td className="px-6 py-5 text-right uppercase" colSpan={4}>Total Contable de Inventario</td>
                        <td className="px-6 py-5 text-right text-lg" data-testid="grand-total">{formatCurrency(reportData.grand_total)}</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>

              {/* Pie legal */}
              <div className="mt-12 text-center text-slate-400 text-xs italic pb-8">
                <p>Documento para fines contables y de auditoria interna. Prohibida su reproduccion total o parcial sin autorizacion.</p>
                <p>Mega Soft Computacion C.A.</p>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
};

export default InventoryAccountingReport;
