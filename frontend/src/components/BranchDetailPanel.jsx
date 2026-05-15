import { useState, useRef } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Plus, Trash2, Upload, Store, AlertCircle, CheckCircle, Download } from 'lucide-react';
import { toast } from 'sonner';
import * as XLSX from 'xlsx';

/**
 * Panel de Detalle de Sucursales para cotizaciones VPOS/MPOS/Fast Track.
 * Props:
 * - branches: Array de {store_name, quantity}
 * - onChange: (branches) => void
 * - totalEquipment: número total de equipos cotizados (para validación)
 */
export const BranchDetailPanel = ({ branches = [], onChange, totalEquipment = 0 }) => {
  const [expanded, setExpanded] = useState(branches.length > 0);
  const fileRef = useRef(null);

  const totalBranches = branches.reduce((sum, b) => sum + (parseInt(b.quantity) || 0), 0);
  const isValid = totalBranches === totalEquipment;

  const addRow = () => {
    onChange([...branches, { store_name: '', quantity: 1 }]);
  };

  const removeRow = (index) => {
    onChange(branches.filter((_, i) => i !== index));
  };

  const updateRow = (index, field, value) => {
    const updated = branches.map((b, i) => i === index ? { ...b, [field]: value } : b);
    onChange(updated);
  };

  const handleExcelImport = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      try {
        const wb = XLSX.read(evt.target.result, { type: 'binary' });
        const ws = wb.Sheets[wb.SheetNames[0]];
        const data = XLSX.utils.sheet_to_json(ws, { header: 1 });

        const imported = [];
        let invalidQtyRows = 0;
        for (let i = 0; i < data.length; i++) {
          const row = data[i];
          if (!row || row.length < 2) continue;
          const name = String(row[0] || '').trim();
          const rawQty = row[1];
          if (!name || name.toLowerCase() === 'nombre' || name.toLowerCase().includes('tienda')) continue;
          // Validar numérico
          const qty = parseInt(rawQty);
          if (!Number.isFinite(qty) || qty <= 0) {
            invalidQtyRows += 1;
            continue;
          }
          imported.push({ store_name: name, quantity: qty });
        }

        if (imported.length === 0) {
          toast.error('No se encontraron datos válidos. Use columnas: Nombre Tienda | Cantidad (numérica)');
          return;
        }
        // REEMPLAZA las filas existentes con las del Excel.
        onChange(imported);
        const msg = `${imported.length} sucursales importadas (reemplazo total)`;
        if (invalidQtyRows > 0) {
          toast.warning(`${msg}. ${invalidQtyRows} fila(s) ignoradas por cantidad inválida.`);
        } else {
          toast.success(msg);
        }
      } catch {
        toast.error('Error al leer el archivo');
      }
    };
    reader.readAsBinaryString(file);
    e.target.value = '';
  };

  const downloadTemplate = () => {
    const data = [
      ['Nombre Tienda', 'Cantidad de Cajas'],
      ['Sucursal Centro', 3],
      ['Sucursal Norte', 2],
      ['Sucursal Sur', 1],
    ];
    const ws = XLSX.utils.aoa_to_sheet(data);
    ws['!cols'] = [{ wch: 30 }, { wch: 18 }];
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Tiendas');
    XLSX.writeFile(wb, 'plantilla_tiendas.xlsx');
  };

  if (!expanded) {
    return (
      <div className="mt-4">
        <Button
          type="button"
          variant="outline"
          onClick={() => { setExpanded(true); if (branches.length === 0) addRow(); }}
          className="border-dashed border-purple-300 text-purple-600 hover:bg-purple-50"
          data-testid="btn-expand-branches"
        >
          <Store size={16} className="mr-2" />
          + Detalle de Sucursales
        </Button>
        <p className="text-[10px] text-slate-400 mt-1 ml-1">Opcional: desglose de tiendas y cantidad de cajas por ubicación</p>
      </div>
    );
  }

  return (
    <div className="mt-4 border border-purple-200 rounded-lg bg-purple-50/30 p-4" data-testid="branch-detail-panel">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Store size={18} className="text-purple-600" />
          <h4 className="font-semibold text-sm text-purple-800">Detalle de Sucursales</h4>
          <Badge variant="outline" className={`text-xs ${isValid ? 'border-green-400 text-green-700' : totalBranches > 0 ? 'border-amber-400 text-amber-700' : 'border-slate-300 text-slate-500'}`}>
            {totalBranches} / {totalEquipment} cajas
            {isValid && totalBranches > 0 && <CheckCircle size={11} className="ml-1" />}
          </Badge>
        </div>
        <div className="flex gap-2">
          <input ref={fileRef} type="file" accept=".xlsx,.xls,.csv" onChange={handleExcelImport} className="hidden" />
          <Button type="button" size="sm" variant="outline" onClick={downloadTemplate}
            className="h-7 text-xs border-blue-300 text-blue-600" data-testid="btn-download-branches-template"
            title="Descargar plantilla Excel">
            <Download size={12} className="mr-1" />Plantilla
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={() => fileRef.current?.click()}
            className="h-7 text-xs border-purple-300 text-purple-600" data-testid="btn-import-branches"
            title="Importar desde Excel (reemplaza el listado actual)">
            <Upload size={12} className="mr-1" />Excel
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={addRow}
            className="h-7 text-xs border-purple-300 text-purple-600" data-testid="btn-add-branch">
            <Plus size={12} className="mr-1" />Fila
          </Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => { setExpanded(false); onChange([]); }}
            className="h-7 text-xs text-slate-400 hover:text-red-500">
            Quitar
          </Button>
        </div>
      </div>

      {!isValid && totalBranches > 0 && (
        <div className="flex items-center gap-1.5 text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-2 py-1.5 mb-2" data-testid="branch-validation-warning">
          <AlertCircle size={13} />
          La suma de cajas ({totalBranches}) no coincide con el total de equipos ({totalEquipment})
        </div>
      )}

      {/* Header */}
      <div className="grid grid-cols-[1fr_100px_32px] gap-2 mb-1">
        <Label className="text-[10px] text-slate-500 font-medium">Nombre de Tienda</Label>
        <Label className="text-[10px] text-slate-500 font-medium text-center">Cajas</Label>
        <div />
      </div>

      {/* Rows */}
      <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
        {branches.map((branch, idx) => (
          <div key={idx} className="grid grid-cols-[1fr_100px_32px] gap-2 items-center" data-testid={`branch-row-${idx}`}>
            <Input
              defaultValue={branch.store_name}
              onBlur={(e) => updateRow(idx, 'store_name', e.target.value)}
              placeholder={`Tienda ${idx + 1}`}
              className="h-8 text-xs"
              data-testid={`branch-name-${idx}`}
            />
            <Input
              type="number"
              min={1}
              defaultValue={branch.quantity}
              onBlur={(e) => updateRow(idx, 'quantity', parseInt(e.target.value) || 0)}
              className="h-8 text-xs text-center"
              data-testid={`branch-qty-${idx}`}
            />
            <Button type="button" size="sm" variant="ghost" onClick={() => removeRow(idx)}
              className="h-8 w-8 p-0 text-slate-300 hover:text-red-500">
              <Trash2 size={13} />
            </Button>
          </div>
        ))}
      </div>

      {branches.length === 0 && (
        <p className="text-xs text-slate-400 text-center py-3">Agregue filas manualmente o importe desde Excel</p>
      )}
    </div>
  );
};

export default BranchDetailPanel;
