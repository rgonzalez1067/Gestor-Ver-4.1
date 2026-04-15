import { useState, useEffect, useRef } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Printer, ArrowLeft, Package } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';

const formatBs = (num) => 'Bs ' + new Intl.NumberFormat('es-VE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(num || 0);

const formatDate = (iso) => {
  if (!iso) return '';
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
              <p className="text-sm text-slate-500">Valoración PEPS (Primero en Entrar, Primero en Salir) — Moneda: Bs</p>
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
              Fecha de emisión: {formatDate(reportData?.report_date)} | Moneda: Bolívares (Bs)
            </p>
          </div>

          {items.length === 0 ? (
            <div className="text-center py-16 text-slate-400" data-testid="empty-state">
              <Package className="w-12 h-12 mx-auto mb-3 opacity-40" />
              <p className="text-lg">No hay activos con saldo disponible</p>
              <p className="text-sm mt-1">Registre entradas en el Almacén Principal para generar el reporte</p>
            </div>
          ) : (
            <div className="space-y-5">
              {/* Tabla única con todas las secciones */}
              <table className="w-full border-collapse text-xs" data-testid="asset-ledger-table">
                <colgroup>
                  <col style={{width: '12%'}} />
                  <col style={{width: '18%'}} />
                  <col style={{width: '12%'}} />
                  <col style={{width: '12%'}} />
                  <col style={{width: '12%'}} />
                  <col style={{width: '15%'}} />
                  <col style={{width: '19%'}} />
                </colgroup>
                <thead>
                  <tr className="bg-slate-700 text-white">
                    <th className="px-3 py-2.5 text-left font-semibold border border-slate-600">Fecha Compra</th>
                    <th className="px-3 py-2.5 text-left font-semibold border border-slate-600">Proveedor</th>
                    <th className="px-3 py-2.5 text-left font-semibold border border-slate-600">Referencia</th>
                    <th className="px-3 py-2.5 text-right font-semibold border border-slate-600">Cant. Comprada</th>
                    <th className="px-3 py-2.5 text-right font-semibold border border-slate-600">Saldo Disponible</th>
                    <th className="px-3 py-2.5 text-right font-semibold border border-slate-600">Costo Unit. (Bs)</th>
                    <th className="px-3 py-2.5 text-right font-semibold border border-slate-600">Valor del Lote (Bs)</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item, itemIdx) => (
                    <>
                      {/* Item Header Row */}
                      <tr key={`header-${item.item_id}`} className="bg-slate-100">
                        <td colSpan={5} className="px-3 py-2 border border-slate-200">
                          <span className="font-bold text-slate-800 text-sm">{item.item_name}</span>
                          {item.item_type && (
                            <span className="ml-2 text-[10px] bg-slate-300 text-slate-700 px-1.5 py-0.5 rounded font-medium">{item.item_type}</span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-right border border-slate-200 text-xs text-slate-500">
                          Uds: <span className="font-bold text-slate-700">{item.total_units}</span>
                        </td>
                        <td className="px-3 py-2 text-right border border-slate-200 font-bold text-emerald-700">
                          {formatBs(item.item_total)}
                        </td>
                      </tr>
                      {/* Lot Rows */}
                      {item.lots.map((lot, lotIdx) => (
                        <tr key={`lot-${item.item_id}-${lotIdx}`} className={lotIdx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                          <td className="px-3 py-1.5 border border-slate-200">{formatDate(lot.purchase_date)}</td>
                          <td className="px-3 py-1.5 border border-slate-200">{lot.supplier || '—'}</td>
                          <td className="px-3 py-1.5 border border-slate-200">{lot.invoice_ref || '—'}</td>
                          <td className="px-3 py-1.5 text-right border border-slate-200 text-slate-500">{lot.quantity_purchased}</td>
                          <td className="px-3 py-1.5 text-right border border-slate-200 font-semibold">
                            <span className={lot.remaining < lot.quantity_purchased ? 'text-amber-600' : 'text-slate-700'}>
                              {lot.remaining}
                            </span>
                          </td>
                          <td className="px-3 py-1.5 text-right border border-slate-200 font-mono">{formatBs(lot.unit_cost)}</td>
                          <td className="px-3 py-1.5 text-right border border-slate-200 font-mono font-semibold text-emerald-700">{formatBs(lot.lot_value)}</td>
                        </tr>
                      ))}
                      {/* Item Subtotal Row */}
                      <tr key={`subtotal-${item.item_id}`} className="bg-slate-100">
                        <td colSpan={4} className="px-3 py-2 text-right border border-slate-200 font-semibold text-slate-600 text-xs">
                          Total {item.item_name}:
                        </td>
                        <td className="px-3 py-2 text-right border border-slate-200 font-bold text-slate-700">{item.total_units}</td>
                        <td className="px-3 py-2 border border-slate-200"></td>
                        <td className="px-3 py-2 text-right border border-slate-200 font-mono font-bold text-emerald-700">{formatBs(item.item_total)}</td>
                      </tr>
                      {/* Separator */}
                      {itemIdx < items.length - 1 && (
                        <tr key={`sep-${item.item_id}`}>
                          <td colSpan={7} className="h-2 border-0 bg-slate-50"></td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
                {/* Grand Total Footer */}
                <tfoot>
                  <tr className="bg-slate-800 text-white">
                    <td colSpan={4} className="px-3 py-3 text-right font-bold border border-slate-700">
                      GRAN TOTAL CONTABLE:
                    </td>
                    <td className="px-3 py-3 text-right font-bold border border-slate-700">
                      {items.reduce((s, i) => s + i.total_units, 0)}
                    </td>
                    <td className="px-3 py-3 border border-slate-700"></td>
                    <td className="px-3 py-3 text-right font-bold text-emerald-300 text-sm border border-slate-700">
                      {formatBs(grandTotal)}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default AssetLedgerReport;
