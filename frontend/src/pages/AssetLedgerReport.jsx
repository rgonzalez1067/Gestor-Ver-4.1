import { useState, useEffect, useRef, Fragment } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Printer, ArrowLeft, Package, Download } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';

const printStyles = `
@media print {
  body { margin: 0; padding: 0; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; color-adjust: exact !important; }
  nav, aside, [data-sidebar], .print\\:hidden { display: none !important; }
  main { padding: 0 !important; margin: 0 !important; width: 100% !important; max-width: 100% !important; }
  .flex.min-h-screen { display: block !important; }
  table { font-size: 9.5px !important; page-break-inside: auto; }
  tr { page-break-inside: avoid; }
  thead { display: table-header-group; }
  @page { size: letter landscape; margin: 10mm 8mm; }
}
`;

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

  const exportToExcel = () => {
    if (!data?.items?.length) return;
    let csv = '\uFEFF';
    csv += 'MAYOR DE ACTIVOS - METODO PEPS (FIFO)\n\n';
    csv += 'Item,Tipo,Fecha Adquisicion,Lote,Costo Unit.(Bs),Cantidad,LCH,TBP,Total Bs.\n';
    for (const item of data.items) {
      for (const lot of (item.lots || [])) {
        csv += `"${item.item_name}",${item.item_type},${lot.acquisition_date},${lot.lot_index},${lot.unit_cost_bs},${lot.remaining_qty},${lot.qty_lch},${lot.qty_tbp},${lot.total_cost_bs}\n`;
      }
    }
    csv += `\nTOTAL GENERAL:,,,,,,,,${data.grand_total}\n`;
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'Mayor_de_Activos_PEPS.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  useEffect(() => {
    const style = document.createElement('style');
    style.id = 'asset-ledger-print-styles';
    style.textContent = printStyles;
    document.head.appendChild(style);
    return () => { const el = document.getElementById('asset-ledger-print-styles'); if (el) el.remove(); };
  }, []);

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
        {/* Screen Header */}
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
          <Button onClick={exportToExcel} variant="outline" size="sm" data-testid="export-excel-btn">
            <Download className="w-4 h-4 mr-1" /> Excel
          </Button>
        </div>

        {/* Report Body */}
        <div ref={printRef} className="bg-white rounded-lg border border-slate-200 p-6 print:border-0 print:shadow-none print:p-0 print:rounded-none">
          {/* Print-only Header */}
          <div className="hidden print:block mb-5 text-center">
            <h2 className="text-base font-bold tracking-wide" style={{color: '#1e293b'}}>MAYOR DE ACTIVOS — VALORACIÓN PEPS</h2>
            <p className="text-[10px] mt-1" style={{color: '#64748b'}}>
              Fecha de emisión: {formatDate(reportData?.report_date)} | Moneda: Bolívares (Bs) | Mega Soft Computación, C.A.
            </p>
            <div style={{borderBottom: '2px solid #334155', marginTop: '8px'}}></div>
          </div>

          {items.length === 0 ? (
            <div className="text-center py-16 text-slate-400" data-testid="empty-state">
              <Package className="w-12 h-12 mx-auto mb-3 opacity-40" />
              <p className="text-lg">No hay activos con saldo disponible</p>
              <p className="text-sm mt-1">Registre entradas en el Almacén Principal para generar el reporte</p>
            </div>
          ) : (
            <div>
              <table className="w-full border-collapse text-xs" data-testid="asset-ledger-table" style={{borderSpacing: 0}}>
                <colgroup>
                  <col style={{width: '10%'}} />
                  <col style={{width: '17%'}} />
                  <col style={{width: '10%'}} />
                  <col style={{width: '9%'}} />
                  <col style={{width: '9%'}} />
                  <col style={{width: '12%'}} />
                  <col style={{width: '15%'}} />
                </colgroup>
                <thead>
                  <tr style={{backgroundColor: '#1e293b', color: '#fff'}}>
                    <th className="px-3 py-2 text-left font-semibold" style={{border: '1px solid #334155'}}>Fecha Compra</th>
                    <th className="px-3 py-2 text-left font-semibold" style={{border: '1px solid #334155'}}>Proveedor</th>
                    <th className="px-3 py-2 text-left font-semibold" style={{border: '1px solid #334155'}}>Referencia</th>
                    <th className="px-3 py-2 text-right font-semibold" style={{border: '1px solid #334155'}}>Cant. Comprada</th>
                    <th className="px-3 py-2 text-right font-semibold" style={{border: '1px solid #334155'}}>Saldo Disponible</th>
                    <th className="px-3 py-2 text-right font-semibold" style={{border: '1px solid #334155'}}>Costo Unit. (Bs)</th>
                    <th className="px-3 py-2 text-right font-semibold" style={{border: '1px solid #334155'}}>Valor del Lote (Bs)</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item, itemIdx) => (
                    <Fragment key={item.item_id || `item-${itemIdx}`}>
                      {/* Item Header */}
                      <tr style={{backgroundColor: '#334155', color: '#fff'}}>
                        <td colSpan={3} className="px-3 py-1.5" style={{border: '1px solid #475569'}}>
                          <span className="font-bold text-sm">{item.item_name}</span>
                          {item.item_type && (
                            <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded font-medium" style={{backgroundColor: '#64748b', color: '#e2e8f0'}}>{item.item_type}</span>
                          )}
                        </td>
                        <td colSpan={2} className="px-3 py-1.5 text-right" style={{border: '1px solid #475569', whiteSpace: 'nowrap'}}>
                          <span className="text-xs" style={{color: '#94a3b8'}}>Uds: </span><span className="font-bold text-sm">{item.total_units}</span>
                          <span style={{color: '#94a3b8', marginLeft: '12px'}} className="text-xs">LCH: </span><span className="font-bold" style={{color: '#93c5fd'}}>{item.units_lch || 0}</span>
                          <span style={{color: '#94a3b8', marginLeft: '12px'}} className="text-xs">TBP: </span><span className="font-bold" style={{color: '#93c5fd'}}>{item.units_tbp || 0}</span>
                        </td>
                        <td className="px-3 py-1.5" style={{border: '1px solid #475569'}}></td>
                        <td className="px-3 py-1.5 text-right font-bold" style={{border: '1px solid #475569', color: '#86efac'}}>
                          {formatBs(item.item_total)}
                        </td>
                      </tr>
                      {/* Lot Rows */}
                      {item.lots.map((lot, lotIdx) => (
                        <tr key={`l-${item.item_id}-${lotIdx}`} style={{backgroundColor: lotIdx % 2 === 0 ? '#ffffff' : '#f8fafc'}}>
                          <td className="px-3 py-1.5" style={{border: '1px solid #e2e8f0'}}>
                            {formatDate(lot.purchase_date)}
                            {lot.warehouse_name && (
                              <span className="ml-1.5 text-[9px] px-1 py-0.5 rounded font-medium" style={{backgroundColor: '#dbeafe', color: '#1d4ed8'}} title={lot.warehouse_name}>
                                {lot.warehouse_name.toLowerCase().includes('chaguaramos') ? 'LCH' : (lot.warehouse_name.toLowerCase().includes('banco plaza') || lot.warehouse_name.toLowerCase().includes('pyme')) ? 'TBP' : lot.warehouse_name.slice(0,4)}
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-1.5" style={{border: '1px solid #e2e8f0'}}>{lot.supplier || '—'}</td>
                          <td className="px-3 py-1.5" style={{border: '1px solid #e2e8f0'}}>{lot.invoice_ref || '—'}</td>
                          <td className="px-3 py-1.5 text-right" style={{border: '1px solid #e2e8f0', color: '#64748b'}}>{lot.quantity_purchased}</td>
                          <td className="px-3 py-1.5 text-right font-semibold" style={{border: '1px solid #e2e8f0', color: lot.remaining < lot.quantity_purchased ? '#d97706' : '#1e293b'}}>
                            {lot.remaining}
                          </td>
                          <td className="px-3 py-1.5 text-right font-mono" style={{border: '1px solid #e2e8f0'}}>{formatBs(lot.unit_cost)}</td>
                          <td className="px-3 py-1.5 text-right font-mono font-semibold" style={{border: '1px solid #e2e8f0', color: '#047857'}}>{formatBs(lot.lot_value)}</td>
                        </tr>
                      ))}
                      {/* Item Subtotal */}
                      <tr key={`s-${item.item_id}`} style={{backgroundColor: '#e2e8f0'}}>
                        <td colSpan={4} className="px-3 py-1.5 text-right font-semibold" style={{border: '1px solid #cbd5e1', color: '#475569', fontSize: '11px'}}>
                          Total {item.item_name}:
                        </td>
                        <td className="px-3 py-1.5 text-right font-bold" style={{border: '1px solid #cbd5e1', color: '#1e293b'}}>{item.total_units}</td>
                        <td className="px-3 py-1.5" style={{border: '1px solid #cbd5e1'}}></td>
                        <td className="px-3 py-1.5 text-right font-mono font-bold" style={{border: '1px solid #cbd5e1', color: '#047857'}}>{formatBs(item.item_total)}</td>
                      </tr>
                      {/* Spacer */}
                      {itemIdx < items.length - 1 && (
                        <tr><td colSpan={7} style={{height: '6px', border: 'none', backgroundColor: '#fff'}}></td></tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>

              {/* Grand Total — only at the end, not in tfoot (avoids repeating on every page) */}
              <div className="mt-4 flex justify-end" data-testid="grand-total">
                <table className="border-collapse" style={{minWidth: '450px'}}>
                  <tbody>
                    <tr style={{backgroundColor: '#1e293b', color: '#fff'}}>
                      <td className="px-4 py-3 text-right font-bold" style={{border: '1px solid #334155', fontSize: '12px'}}>
                        GRAN TOTAL CONTABLE:
                      </td>
                      <td className="px-4 py-3 text-right font-bold" style={{border: '1px solid #334155', width: '100px'}}>
                        {items.reduce((s, i) => s + i.total_units, 0)}
                      </td>
                      <td className="px-4 py-3 text-right font-bold" style={{border: '1px solid #334155', color: '#86efac', fontSize: '14px', width: '180px'}}>
                        {formatBs(grandTotal)}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default AssetLedgerReport;
