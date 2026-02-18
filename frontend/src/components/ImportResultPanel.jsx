import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react';
import { Button } from './ui/button';

export const ImportResultPanel = ({ result, onClose }) => {
  if (!result) return null;

  const getStatusColor = (status) => {
    switch (status) {
      case 'success': return 'bg-green-50 border-green-200';
      case 'partial': return 'bg-amber-50 border-amber-200';
      case 'error': return 'bg-red-50 border-red-200';
      default: return 'bg-slate-50 border-slate-200';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'success': return <CheckCircle className="text-green-600" size={24} />;
      case 'partial': return <AlertTriangle className="text-amber-600" size={24} />;
      case 'error': return <XCircle className="text-red-600" size={24} />;
      default: return <Info className="text-slate-600" size={24} />;
    }
  };

  const getStatusTitle = (status) => {
    switch (status) {
      case 'success': return 'Importación Exitosa';
      case 'partial': return 'Importación Parcial';
      case 'error': return 'Error en Importación';
      default: return 'Resultado de Importación';
    }
  };

  const getErrorTypeLabel = (errorType) => {
    switch (errorType) {
      case 'missing': return 'Campo requerido vacío';
      case 'invalid': return 'Valor no válido';
      case 'format': return 'Formato incorrecto';
      case 'duplicate': return 'Registro duplicado';
      default: return errorType;
    }
  };

  const getErrorTypeBadgeClass = (errorType) => {
    switch (errorType) {
      case 'missing': return 'bg-red-100 text-red-700';
      case 'invalid': return 'bg-amber-100 text-amber-700';
      case 'duplicate': return 'bg-blue-100 text-blue-700';
      default: return 'bg-slate-100 text-slate-700';
    }
  };

  return (
    <div className={`rounded-lg border-2 p-4 mb-6 ${getStatusColor(result.status)}`} data-testid="import-result-panel">
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          {getStatusIcon(result.status)}
          <div>
            <h3 className="font-semibold text-slate-900 text-lg">
              {getStatusTitle(result.status)}
            </h3>
            <p className="text-slate-600 mt-1">{result.message}</p>
          </div>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose} className="text-slate-500 hover:text-slate-700">
          <X size={18} />
        </Button>
      </div>
      
      {/* Contadores */}
      <div className="flex gap-6 mt-4 pt-4 border-t border-slate-200">
        <div className="text-center">
          <div className="text-2xl font-bold text-slate-900">{result.total_processed}</div>
          <div className="text-xs text-slate-500">Total procesados</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-green-600">{result.success_count}</div>
          <div className="text-xs text-green-600">Exitosos</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-red-600">{result.error_count}</div>
          <div className="text-xs text-red-600">Con errores</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-amber-600">{result.skipped_count}</div>
          <div className="text-xs text-amber-600">Omitidos</div>
        </div>
      </div>
      
      {/* Log de Errores */}
      {result.errors && result.errors.length > 0 && (
        <div className="mt-4 pt-4 border-t border-slate-200">
          <h4 className="font-medium text-slate-800 mb-2 flex items-center gap-2">
            <AlertTriangle size={16} className="text-amber-600" />
            Detalle de Errores ({result.errors.length})
          </h4>
          <div className="max-h-48 overflow-y-auto bg-white rounded border border-slate-200">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 sticky top-0">
                <tr>
                  <th className="px-3 py-2 text-left font-medium text-slate-600">Fila</th>
                  <th className="px-3 py-2 text-left font-medium text-slate-600">Columna</th>
                  <th className="px-3 py-2 text-left font-medium text-slate-600">Valor</th>
                  <th className="px-3 py-2 text-left font-medium text-slate-600">Error</th>
                  <th className="px-3 py-2 text-left font-medium text-slate-600">Acción sugerida</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {result.errors.map((err, idx) => (
                  <tr key={idx} className="hover:bg-slate-50">
                    <td className="px-3 py-2 text-slate-900 font-medium">{err.row}</td>
                    <td className="px-3 py-2 text-slate-700">{err.column}</td>
                    <td className="px-3 py-2 text-slate-500 font-mono text-xs">{err.value || '-'}</td>
                    <td className="px-3 py-2">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${getErrorTypeBadgeClass(err.error_type)}`}>
                        {getErrorTypeLabel(err.error_type)}
                      </span>
                      <p className="text-slate-600 text-xs mt-1">{err.message}</p>
                    </td>
                    <td className="px-3 py-2 text-slate-600 text-xs">{err.suggested_action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default ImportResultPanel;
