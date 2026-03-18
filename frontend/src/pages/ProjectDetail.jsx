import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import api from '../utils/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';
import {
  ArrowLeft, CreditCard, Building2, CheckCircle2, Circle, Clock,
  FileText, Send, Calendar, User, Store
} from 'lucide-react';

const PHASES = ['Notificado', 'Recibido', 'Configurado', 'Testeado', 'En Producción'];
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

  const fetchProject = useCallback(async () => {
    try {
      const res = await api.get(`/projects/${projectId}`);
      setProject(res.data);
    } catch (err) {
      toast.error('Error cargando proyecto');
      navigate('/projects');
    } finally { setLoading(false); }
  }, [projectId, navigate]);

  useEffect(() => { fetchProject(); }, [fetchProject]);

  const togglePhase = async (bankName, productName, phase, currentlyCompleted) => {
    try {
      await api.put(`/projects/${projectId}/matrix/phase`, {
        bank_name: bankName,
        product_name: productName,
        phase: phase,
        completed: !currentlyCompleted
      });
      fetchProject();
    } catch (err) { toast.error('Error actualizando fase'); }
  };

  const toggleStorePhase = async (storeId, bankName, productName, phase, currentlyCompleted) => {
    try {
      await api.put(`/projects/${projectId}/stores/${storeId}/matrix/phase`, {
        bank_name: bankName,
        product_name: productName,
        phase: phase,
        completed: !currentlyCompleted
      });
      fetchProject();
    } catch (err) { toast.error('Error actualizando fase de tienda'); }
  };

  const handleAddBitacora = async () => {
    if (!bitacoraText.trim() || !bitacoraDate) return;
    setBitacoraSubmitting(true);
    try {
      await api.post(`/projects/${projectId}/bitacora`, { text: bitacoraText, execution_date: bitacoraDate });
      toast.success('Entrada agregada a la bitácora');
      setBitacoraText('');
      setBitacoraDate(new Date().toISOString().split('T')[0]);
      fetchProject();
    } catch (err) { toast.error('Error al agregar entrada'); }
    finally { setBitacoraSubmitting(false); }
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

  // Build matrix data: { bankName: { productName: { phase: {completed, updated_at, updated_by} } } }
  const matrix = project.implementation_matrix || {};
  const bankNames = Object.keys(matrix);

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
                <p className="text-lg font-semibold text-slate-700">{project.project_number}</p>
                <p className="text-sm text-slate-500">{project.client_name} — {project.client_rif} — {project.client_sede}</p>
              </div>
              <div className="text-right">
                <span className={`inline-block px-3 py-1 rounded-full text-sm font-medium border ${
                  project.status === 'Pendiente por Asignar' ? 'bg-amber-100 text-amber-800 border-amber-200' :
                  project.status === 'Asignado / En Proceso' ? 'bg-blue-100 text-blue-800 border-blue-200' :
                  project.status === 'Detenido por Cliente/Banco' ? 'bg-red-100 text-red-800 border-red-200' :
                  'bg-emerald-100 text-emerald-800 border-emerald-200'
                }`}>{project.status}</span>
                {project.assigned_to_name && (
                  <p className="text-sm text-slate-500 mt-1">Implementador: <strong>{project.assigned_to_name}</strong></p>
                )}
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

          {/* Implementation Matrix */}
          <div className="mb-6">
            <h2 className="text-lg font-bold text-slate-900 mb-3">Matriz de Implementación</h2>
            {project.project_type === 'multistore' && (
              <div className="mb-3 bg-blue-50 border border-blue-200 rounded-lg p-3">
                <p className="text-sm text-blue-800 font-medium flex items-center gap-2">
                  <Store size={16} className="text-blue-600" />
                  Proyecto Multitienda — Las matrices por tienda se encuentran más abajo
                </p>
              </div>
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
                      <th className="bg-blue-600 text-white px-4 py-3 text-left text-sm font-semibold min-w-[200px]" colSpan={1}>
                        Bancos / Productos
                      </th>
                      {PHASES.map(phase => (
                        <th key={phase} className={`px-3 py-3 text-center text-xs font-semibold border-l border-slate-200 min-w-[110px] ${PHASE_COLORS[phase]}`}>
                          {phase}
                        </th>
                      ))}
                      <th className="bg-blue-600 text-white px-3 py-3 text-center text-xs font-semibold border-l border-slate-200 min-w-[150px]">
                        Notas
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {bankNames.map(bankName => {
                      const products = Object.keys(matrix[bankName]);
                      return (
                        <BankSection key={bankName} bankName={bankName} products={products}
                          matrixData={matrix[bankName]} onTogglePhase={togglePhase} />
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Sección Multitienda: Matrices por Tienda */}
          {project.project_type === 'multistore' && project.stores && project.stores.length > 0 && (
            <div className="mb-6" data-testid="multistore-section">
              <h2 className="text-lg font-bold text-slate-900 mb-3 flex items-center gap-2">
                <Store size={20} className="text-blue-600" />
                Seguimiento por Tienda ({project.stores.length})
              </h2>

              {/* Tabs para seleccionar tienda */}
              <div className="flex gap-2 mb-4 flex-wrap">
                {project.stores.map((store) => {
                  const storeMatrix = store.implementation_matrix || {};
                  const totalPhases = Object.values(storeMatrix).reduce((sum, products) => {
                    return sum + Object.values(products).reduce((pSum, phases) => {
                      return pSum + Object.values(phases).filter(p => p?.completed).length;
                    }, 0);
                  }, 0);
                  const maxPhases = Object.values(storeMatrix).reduce((sum, products) => {
                    return sum + Object.keys(products).length * PHASES.length;
                  }, 0);
                  const progress = maxPhases > 0 ? Math.round((totalPhases / maxPhases) * 100) : 0;
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
                        <p className="text-xs text-slate-500">{store.box_count} caja{store.box_count !== 1 ? 's' : ''} · Estado: {store.status || 'Pendiente'}</p>
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
                              {PHASES.map(phase => (
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
                                  matrixData={storeMatrix[bankName]} storeId={store.store_id} onTogglePhase={toggleStorePhase} />
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
      </main>
    </div>
  );
};


// Sub-component: Bank section with products
const BankSection = ({ bankName, products, matrixData, onTogglePhase }) => {
  return (
    <>
      {/* Bank header row */}
      <tr className="bg-blue-50 border-t-2 border-blue-200">
        <td className="px-4 py-2 text-sm font-bold text-blue-900" colSpan={PHASES.length + 2}>
          <Building2 size={14} className="inline mr-2 text-blue-600" />{bankName}
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

export default ProjectDetail;

// Sub-component: Store Bank section with products (for multistore)
const StoreBankSection = ({ bankName, products, matrixData, storeId, onTogglePhase }) => {
  return (
    <>
      <tr className="bg-blue-50 border-t-2 border-blue-200">
        <td className="px-4 py-2 text-sm font-bold text-blue-900" colSpan={PHASES.length + 2}>
          <Building2 size={14} className="inline mr-2 text-blue-600" />{bankName}
        </td>
      </tr>
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
                    onClick={() => onTogglePhase(storeId, bankName, productName, phase, completed)}
                    className={`inline-flex items-center justify-center w-7 h-7 rounded-md transition-all ${
                      completed
                        ? 'bg-emerald-500 text-white shadow-sm hover:bg-emerald-600'
                        : 'bg-slate-100 text-slate-400 hover:bg-slate-200'
                    }`}
                    title={completed ? `${phase}: Completado por ${phaseData?.updated_by || ''}` : `Marcar ${phase}`}
                    data-testid={`store-phase-${storeId}-${bankName}-${productName}-${phase}`}
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
