import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { ArrowLeft, Building2, Rocket, Filter, Layers } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const STATUS_CONFIG = {
  'PreProd':       { label: 'PreProd',      full: 'Pre-Producción',       color: 'bg-orange-100 text-orange-700 border-orange-300',    dot: 'bg-orange-500' },
  'Primer Prod':   { label: 'Primer Prod',  full: 'Primera Producción',   color: 'bg-blue-100 text-blue-700 border-blue-300',          dot: 'bg-blue-500' },
  'Masificación':  { label: 'Masificación', full: 'Masificación',         color: 'bg-emerald-100 text-emerald-700 border-emerald-300', dot: 'bg-emerald-500' }
};

const getStatus = (s) => STATUS_CONFIG[s] || STATUS_CONFIG['PreProd'];

const FILTER_OPTIONS = [
  { value: 'all', label: 'Todas las Fases' },
  { value: 'PreProd', label: 'Pre-Producción' },
  { value: 'Primer Prod', label: 'Primera Producción' },
  { value: 'Masificación', label: 'Masificación' }
];

const GROUP_OPTIONS = [
  { key: 'none', label: 'Sin Agrupar' },
  { key: 'bank', label: 'Por Banco' },
  { key: 'product', label: 'Por Producto' },
  { key: 'phase', label: 'Por Fase' },
];

export const IntegrationReport = () => {
  const navigate = useNavigate();
  const [flatData, setFlatData] = useState([]);
  const [groupedData, setGroupedData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [groupBy, setGroupBy] = useState('none');

  useEffect(() => {
    const fetchReport = async () => {
      setLoading(true);
      try {
        if (groupBy === 'none') {
          const res = await api.get('/banks/integrations/report');
          setFlatData(res.data);
          setGroupedData(null);
        } else {
          const res = await api.get(`/banks/integrations/report?group_by=${groupBy}`);
          setGroupedData(res.data);
          setFlatData([]);
        }
      } catch { toast.error('Error al cargar reporte'); }
      finally { setLoading(false); }
    };
    fetchReport();
  }, [groupBy]);

  // Flat mode: apply status filter
  const filtered = statusFilter === 'all' ? flatData : flatData.filter(r => r.status === statusFilter);

  // Count statuses from flat data or grouped data
  const statusCounts = {};
  if (groupBy === 'none') {
    flatData.forEach(r => { statusCounts[r.status] = (statusCounts[r.status] || 0) + 1; });
  } else if (groupedData) {
    Object.values(groupedData.groups || {}).forEach(g => {
      g.items.forEach(r => { statusCounts[r.status] = (statusCounts[r.status] || 0) + 1; });
    });
  }

  const totalCount = groupBy === 'none' ? flatData.length : (groupedData?.total || 0);

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

  return (
    <div className="flex min-h-screen bg-white">
      <Sidebar />
      <main className="flex-1 p-8" data-testid="integration-report-page">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="flex items-center gap-4 mb-6">
            <Button variant="outline" size="sm" onClick={() => navigate('/banks')} data-testid="back-to-banks-btn">
              <ArrowLeft size={16} className="mr-1" />Bancos
            </Button>
            <div className="flex-1">
              <h1 className="text-3xl font-bold text-slate-900 font-manrope">Proyectos en Proceso de Integración</h1>
              <p className="text-slate-500 text-sm mt-1">Radar consolidado de todas las integraciones bancarias en desarrollo</p>
            </div>
          </div>

          {/* Summary Cards */}
          <div className="grid grid-cols-6 gap-3 mb-6">
            {FILTER_OPTIONS.slice(1).map(opt => {
              const count = statusCounts[opt.value] || 0;
              const cfg = getStatus(opt.value);
              const isActive = statusFilter === opt.value;
              return (
                <button key={opt.value} onClick={() => setStatusFilter(isActive ? 'all' : opt.value)}
                  data-testid={`filter-${opt.value.toLowerCase().replace('.','')}`}
                  className={`p-3 rounded-lg border-2 text-center transition-all ${isActive ? 'border-slate-800 shadow-sm' : 'border-slate-200 hover:border-slate-300'}`}>
                  <div className={`w-3 h-3 rounded-full mx-auto mb-1.5 ${cfg.dot}`} />
                  <p className="text-2xl font-bold text-slate-900">{count}</p>
                  <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wide">{opt.label}</p>
                </button>
              );
            })}
          </div>

          {/* Toolbar: Group By + Filter */}
          <div className="flex items-center gap-4 mb-4 p-3 bg-slate-50 rounded-lg border border-slate-200">
            {/* Group by selector */}
            <div className="flex items-center gap-2">
              <Layers size={16} className="text-slate-500" />
              <span className="text-sm text-slate-600 font-medium">Agrupar por:</span>
              <div className="flex items-center gap-1 bg-white rounded-lg p-0.5 border border-slate-200">
                {GROUP_OPTIONS.map(g => (
                  <button key={g.key} onClick={() => setGroupBy(g.key)}
                    className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${groupBy === g.key ? 'bg-slate-900 text-white shadow-sm' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'}`}
                    data-testid={`group-by-${g.key}`}>{g.label}</button>
                ))}
              </div>
            </div>

            {/* Filter (only for flat mode) */}
            {groupBy === 'none' && (
              <div className="flex items-center gap-2 ml-auto">
                <Filter size={16} className="text-slate-500" />
                <span className="text-sm text-slate-600 font-medium">Filtrar:</span>
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger className="w-[200px] h-8 text-sm bg-white" data-testid="status-filter-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {FILTER_OPTIONS.map(o => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            )}
            <span className="text-sm text-slate-400 ml-auto">{groupBy === 'none' ? `${filtered.length} de ${flatData.length}` : `${totalCount} total`} integraciones</span>
          </div>

          {/* FLAT VIEW (no grouping) */}
          {groupBy === 'none' && (
            <div className="bg-white rounded-lg border border-slate-200 overflow-hidden" data-testid="integrations-table">
              <table className="w-full table-fixed">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200">
                    <th className="w-[22%] px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Banco</th>
                    <th className="w-[25%] px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Producto</th>
                    <th className="w-[13%] px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Componente</th>
                    <th className="w-[15%] px-4 py-3 text-center text-xs font-semibold text-slate-600 uppercase tracking-wider">Fase (Estatus)</th>
                    <th className="w-[25%] px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Notas</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.length > 0 ? filtered.map((row) => {
                    const cfg = getStatus(row.status);
                    return (
                      <tr key={`${row.bank_id}-${row.integration_id}`}
                        onClick={() => navigate(`/banks/${row.bank_id}`)}
                        className="border-b border-slate-100 hover:bg-slate-50 cursor-pointer transition-colors"
                        data-testid={`report-row-${row.integration_id}`}>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2.5">
                            <div className="w-8 h-8 rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center overflow-hidden shrink-0">
                              {row.bank_logo_url ? (
                                <img src={`${API_URL}${row.bank_logo_url}`} alt="" className="w-7 h-7 object-contain" />
                              ) : (
                                <Building2 size={14} className="text-slate-400" />
                              )}
                            </div>
                            <span className="text-sm font-medium text-slate-900">{row.bank_name}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-sm text-slate-800">{row.service_name}</span>
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-xs font-medium text-slate-600 bg-slate-100 px-2 py-1 rounded">{row.component_type}</span>
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span className={`inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-full border ${cfg.color}`}>
                            <span className={`w-2 h-2 rounded-full ${cfg.dot}`} />
                            {cfg.label}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-xs text-slate-500 truncate max-w-[200px] block">{row.notes || '—'}</span>
                        </td>
                      </tr>
                    );
                  }) : (
                    <tr>
                      <td colSpan={5} className="py-12 text-center">
                        <Rocket size={32} className="mx-auto text-slate-300 mb-2" />
                        <p className="text-sm text-slate-400">
                          {statusFilter === 'all' ? 'No hay integraciones registradas' : `No hay integraciones en fase "${statusFilter}"`}
                        </p>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* GROUPED VIEW */}
          {groupBy !== 'none' && groupedData && (
            <div className="space-y-4" data-testid="grouped-view">
              {Object.values(groupedData.groups || {}).length === 0 ? (
                <div className="text-center py-12">
                  <Rocket size={32} className="mx-auto text-slate-300 mb-2" />
                  <p className="text-sm text-slate-400">No hay integraciones registradas</p>
                </div>
              ) : (
                Object.values(groupedData.groups)
                  .sort((a, b) => b.count - a.count)
                  .map(group => {
                    // Apply status filter inside groups
                    const groupItems = statusFilter === 'all'
                      ? group.items
                      : group.items.filter(i => i.status === statusFilter);
                    if (groupItems.length === 0) return null;

                    return (
                      <div key={group.label} className="border border-slate-200 rounded-lg overflow-hidden" data-testid={`group-${group.label}`}>
                        {/* Group Header */}
                        <div className="bg-slate-50 px-4 py-3 flex items-center justify-between border-b border-slate-200">
                          <div className="flex items-center gap-3">
                            {groupBy === 'bank' && <Building2 size={16} className="text-slate-500" />}
                            {groupBy === 'phase' && <div className={`w-3 h-3 rounded-full ${getStatus(group.items[0]?.status).dot}`} />}
                            <h3 className="font-semibold text-sm text-slate-800">{group.label}</h3>
                          </div>
                          <span className="text-xs font-bold text-slate-600 bg-slate-200 px-2.5 py-1 rounded-full">{groupItems.length}</span>
                        </div>

                        {/* Group Table */}
                        <table className="w-full table-fixed">
                          <colgroup>
                            {groupBy !== 'bank' && <col style={{ width: '28%' }} />}
                            {groupBy !== 'product' && <col style={{ width: '30%' }} />}
                            <col style={{ width: '15%' }} />
                            {groupBy !== 'phase' && <col style={{ width: '15%' }} />}
                            <col style={{ width: groupBy === 'phase' ? '55%' : '27%' }} />
                          </colgroup>
                          <thead>
                            <tr className="bg-white border-b border-slate-100">
                              {groupBy !== 'bank' && <th className="px-4 py-2 text-left text-[10px] font-semibold text-slate-500 uppercase">Banco</th>}
                              {groupBy !== 'product' && <th className="px-4 py-2 text-left text-[10px] font-semibold text-slate-500 uppercase">Producto</th>}
                              <th className="px-4 py-2 text-left text-[10px] font-semibold text-slate-500 uppercase">Componente</th>
                              {groupBy !== 'phase' && <th className="px-4 py-2 text-center text-[10px] font-semibold text-slate-500 uppercase">Fase</th>}
                              <th className="px-4 py-2 text-left text-[10px] font-semibold text-slate-500 uppercase">Notas</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {groupItems.map((row) => {
                              const cfg = getStatus(row.status);
                              return (
                                <tr key={`${row.bank_id}-${row.integration_id}`}
                                  onClick={() => navigate(`/banks/${row.bank_id}`)}
                                  className="hover:bg-slate-50 cursor-pointer transition-colors"
                                  data-testid={`grouped-row-${row.integration_id}`}>
                                  {groupBy !== 'bank' && (
                                    <td className="px-4 py-2.5 overflow-hidden">
                                      <div className="flex items-center gap-2">
                                        <div className="w-6 h-6 rounded bg-slate-100 border border-slate-200 flex items-center justify-center overflow-hidden shrink-0">
                                          {row.bank_logo_url ? (
                                            <img src={`${API_URL}${row.bank_logo_url}`} alt="" className="w-5 h-5 object-contain" />
                                          ) : (
                                            <Building2 size={10} className="text-slate-400" />
                                          )}
                                        </div>
                                        <span className="text-xs font-medium text-slate-800 truncate">{row.bank_name}</span>
                                      </div>
                                    </td>
                                  )}
                                  {groupBy !== 'product' && (
                                    <td className="px-4 py-2.5 overflow-hidden">
                                      <span className="text-xs text-slate-800 truncate block">{row.service_name}</span>
                                    </td>
                                  )}
                                  <td className="px-4 py-2.5 overflow-hidden">
                                    <span className="text-[10px] font-medium text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded">{row.component_type}</span>
                                  </td>
                                  {groupBy !== 'phase' && (
                                    <td className="px-4 py-2.5 text-center overflow-hidden">
                                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-semibold rounded-full border ${cfg.color}`}>
                                        <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
                                        {cfg.label}
                                      </span>
                                    </td>
                                  )}
                                  <td className="px-4 py-2.5 overflow-hidden">
                                    <span className="text-[10px] text-slate-500 truncate block">{row.notes || '—'}</span>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    );
                  })
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default IntegrationReport;
