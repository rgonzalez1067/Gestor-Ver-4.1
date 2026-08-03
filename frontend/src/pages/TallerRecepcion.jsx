import { useState, useEffect, useCallback, useRef } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import {
  PackageCheck, Search, Plus, X, Trash2, ClipboardCheck, Loader2, Building2, Barcode, FileSpreadsheet, MessageSquareText
} from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';
import { usePermission } from '../hooks/usePermission';

const REPAIR_MODEL_TYPES = ['POS', 'Pinpad'];

let ROW_SEQ = 1;
const newRow = () => ({ id: ROW_SEQ++, model_id: '', model_name: '', serialInput: '', serials: [] });

export default function TallerRecepcion() {
  const { canEdit } = usePermission('taller_recepcion');

  // Cliente
  const [clientQuery, setClientQuery] = useState('');
  const [clientResults, setClientResults] = useState([]);
  const [showResults, setShowResults] = useState(false);
  const [selectedClient, setSelectedClient] = useState(null);
  const searchTimer = useRef(null);

  // Modelos disponibles (catálogo hardware POS/Pinpad)
  const [models, setModels] = useState([]);
  // Filas de equipos a recibir
  const [rows, setRows] = useState([newRow()]);
  // Instrucciones especiales al Equipo de Operaciones (máx 500)
  const [detalles, setDetalles] = useState('');
  const DETALLES_MAX = 500;

  // Resumen / guardado
  const [summaryOpen, setSummaryOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const r = await api.get('/hardware');
        const list = (r.data || []).filter((h) => REPAIR_MODEL_TYPES.includes(h.type));
        setModels(list);
      } catch (e) {
        // silencioso: la lista de modelos es de apoyo
      }
    })();
  }, []);

  const searchClients = useCallback((q) => {
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(async () => {
      try {
        const r = await api.get(`/clients/search?q=${encodeURIComponent(q)}`);
        setClientResults(r.data || []);
        setShowResults(true);
      } catch (e) {
        setClientResults([]);
      }
    }, 300);
  }, []);

  const onClientInput = (v) => {
    setClientQuery(v);
    setSelectedClient(null);
    if (v.trim().length >= 2) searchClients(v.trim());
    else setShowResults(false);
  };

  const pickClient = (c) => {
    setSelectedClient(c);
    setClientQuery(c.fantasy_name || c.legal_name || c.rif || '');
    setShowResults(false);
  };

  const updateRowModel = (id, model_id) => {
    const m = models.find((x) => x.hardware_id === model_id);
    setRows((rs) => rs.map((r) => r.id === id ? { ...r, model_id, model_name: m?.name || '' } : r));
  };

  const addSerials = (id) => {
    setRows((rs) => rs.map((r) => {
      if (r.id !== id) return r;
      const tokens = (r.serialInput || '').split(/[\n,;\s]+/).map((s) => s.trim()).filter(Boolean);
      const merged = Array.from(new Set([...r.serials, ...tokens]));
      return { ...r, serials: merged, serialInput: '' };
    }));
  };

  const removeSerial = (id, serial) => {
    setRows((rs) => rs.map((r) => r.id === id ? { ...r, serials: r.serials.filter((s) => s !== serial) } : r));
  };

  const addRow = () => setRows((rs) => [...rs, newRow()]);

  const removeRow = (id) => setRows((rs) => rs.length > 1 ? rs.filter((r) => r.id !== id) : rs);

  const importSerialsExcel = async (id, e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = '';
    try {
      const fd = new FormData();
      fd.append('file', file);
      const r = await api.post('/taller/parse-serials', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      const imported = r.data?.serials || [];
      setRows((rs) => rs.map((row) => {
        if (row.id !== id) return row;
        const merged = Array.from(new Set([...row.serials, ...imported]));
        return { ...row, serials: merged };
      }));
      toast.success(`${imported.length} serial(es) importado(s) desde Excel.`);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'No se pudo leer el Excel');
    }
  };

  const validRows = rows.filter((r) => r.model_name && r.serials.length > 0);
  const totalEquipos = validRows.reduce((acc, r) => acc + r.serials.length, 0);
  const canSubmit = !!selectedClient && validRows.length > 0 && canEdit;

  const openSummary = () => {
    if (!selectedClient) { toast.error('Selecciona un cliente'); return; }
    if (validRows.length === 0) { toast.error('Agrega al menos un modelo con seriales'); return; }
    setSummaryOpen(true);
  };

  const confirmRecepcion = async () => {
    setSaving(true);
    try {
      const payload = {
        client_id: selectedClient.client_id,
        client_name: selectedClient.fantasy_name || selectedClient.legal_name || '',
        client_rif: selectedClient.rif || '',
        detalles_recepcion: detalles.trim(),
        models: validRows.map((r) => ({ model_id: r.model_id, model_name: r.model_name, serials: r.serials })),
      };
      const r = await api.post('/taller/recepcion', payload);
      toast.success(`Recepción confirmada: ${r.data?.created || totalEquipos} equipo(s) ingresado(s) al taller como "Recibido".`);
      // reset
      setSelectedClient(null); setClientQuery(''); setRows([newRow()]); setDetalles(''); setSummaryOpen(false);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error al confirmar la recepción');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 overflow-auto" data-testid="taller-recepcion-page">
        <div className="max-w-4xl mx-auto p-6 lg:p-8">
          {/* Header */}
          <div className="flex items-start gap-3 mb-6">
            <div className="w-11 h-11 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center flex-shrink-0">
              <PackageCheck size={22} />
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-slate-900 font-manrope">Recepción de Equipos</h1>
              <p className="text-sm text-slate-500 mt-0.5">
                Registra la llegada física de equipos al taller. Al confirmar, ingresan con estatus
                <span className="font-semibold text-emerald-700"> "Recibido"</span> y se notifica al cliente y al taller.
              </p>
            </div>
          </div>

          {/* Cliente */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 mb-4">
            <label className="text-sm font-semibold text-slate-800 flex items-center gap-2 mb-2">
              <Building2 size={16} className="text-slate-400" /> Cliente
            </label>
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <Input
                data-testid="recepcion-client-search"
                placeholder="Buscar por nombre o RIF (mín. 2 caracteres)..."
                value={clientQuery}
                onChange={(e) => onClientInput(e.target.value)}
                onFocus={() => clientResults.length && setShowResults(true)}
                className="pl-9"
              />
              {showResults && clientResults.length > 0 && (
                <div className="absolute z-20 mt-1 w-full bg-white border border-slate-200 rounded-lg shadow-lg max-h-64 overflow-auto" data-testid="recepcion-client-results">
                  {clientResults.map((c) => (
                    <button
                      key={c.client_id}
                      type="button"
                      onClick={() => pickClient(c)}
                      className="w-full text-left px-3 py-2 hover:bg-emerald-50 border-b border-slate-100 last:border-0"
                      data-testid={`recepcion-client-option-${c.client_id}`}
                    >
                      <div className="text-sm font-medium text-slate-800">{c.fantasy_name || c.legal_name}</div>
                      <div className="text-xs text-slate-500">{c.legal_name} · {c.rif}</div>
                    </button>
                  ))}
                </div>
              )}
            </div>
            {selectedClient && (
              <div className="mt-3 flex items-center gap-2 text-sm bg-emerald-50 text-emerald-800 rounded-lg px-3 py-2" data-testid="recepcion-client-selected">
                <ClipboardCheck size={16} />
                <span className="font-medium">{selectedClient.fantasy_name || selectedClient.legal_name}</span>
                <span className="text-emerald-600">· {selectedClient.rif}</span>
              </div>
            )}
          </div>

          {/* Equipos */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 mb-4">
            <div className="flex items-center justify-between mb-3">
              <label className="text-sm font-semibold text-slate-800 flex items-center gap-2">
                <Barcode size={16} className="text-slate-400" /> Equipos a recibir
              </label>
              <Button type="button" variant="outline" size="sm" onClick={addRow} data-testid="recepcion-add-model-btn">
                <Plus size={15} className="mr-1" /> Agregar modelo
              </Button>
            </div>

            <div className="space-y-3">
              {rows.map((r, idx) => (
                <div key={r.id} className="border border-slate-200 rounded-lg p-3" data-testid={`recepcion-row-${idx}`}>
                  <div className="flex items-center gap-2">
                    <div className="flex-1">
                      <Select value={r.model_id} onValueChange={(v) => updateRowModel(r.id, v)}>
                        <SelectTrigger data-testid={`recepcion-model-select-${idx}`}>
                          <SelectValue placeholder="Selecciona el modelo (POS / Pinpad)" />
                        </SelectTrigger>
                        <SelectContent>
                          {models.map((m) => (
                            <SelectItem key={m.hardware_id} value={m.hardware_id}>{m.name} ({m.type})</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    {rows.length > 1 && (
                      <Button type="button" variant="ghost" size="icon" onClick={() => removeRow(r.id)} data-testid={`recepcion-remove-row-${idx}`}>
                        <Trash2 size={16} className="text-rose-500" />
                      </Button>
                    )}
                  </div>

                  <div className="flex items-center gap-2 mt-2">
                    <Input
                      data-testid={`recepcion-serial-input-${idx}`}
                      placeholder="Escribe seriales (Enter para agregar; separa varios por coma)"
                      value={r.serialInput}
                      onChange={(e) => setRows((rs) => rs.map((x) => x.id === r.id ? { ...x, serialInput: e.target.value } : x))}
                      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addSerials(r.id); } }}
                    />
                    <Button type="button" variant="outline" size="sm" onClick={() => addSerials(r.id)} data-testid={`recepcion-add-serial-${idx}`}>
                      Agregar
                    </Button>
                    <label className="inline-flex items-center gap-1 text-sm cursor-pointer border border-slate-200 rounded-md px-2.5 py-1.5 hover:bg-slate-50 whitespace-nowrap" data-testid={`recepcion-excel-label-${idx}`}>
                      <FileSpreadsheet size={15} className="text-emerald-600" /> Excel
                      <input
                        type="file"
                        accept=".xlsx,.xls"
                        className="hidden"
                        data-testid={`recepcion-excel-input-${idx}`}
                        onChange={(e) => importSerialsExcel(r.id, e)}
                      />
                    </label>
                  </div>

                  {r.serials.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2" data-testid={`recepcion-serials-${idx}`}>
                      {r.serials.map((s) => (
                        <span key={s} className="inline-flex items-center gap-1 bg-slate-100 text-slate-700 text-xs rounded-full px-2 py-0.5">
                          {s}
                          <button type="button" onClick={() => removeSerial(r.id, s)} className="text-slate-400 hover:text-rose-500">
                            <X size={12} />
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Instrucciones especiales al Equipo de Operaciones */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-4" data-testid="recepcion-detalles-card">
          <label htmlFor="recepcion-detalles" className="text-sm font-semibold text-slate-800 flex items-center gap-2 mb-1">
            <MessageSquareText size={16} className="text-slate-400" /> Detalles de la recepción para Operaciones
            <span className="text-xs font-normal text-slate-400">(opcional)</span>
          </label>
          <p className="text-xs text-slate-500 mb-2">
            Instrucciones especiales para el Equipo de Operaciones. Se incluirán en la notificación de recepción.
          </p>
          <textarea
            id="recepcion-detalles"
            data-testid="recepcion-detalles-input"
            value={detalles}
            maxLength={DETALLES_MAX}
            onChange={(e) => setDetalles(e.target.value.slice(0, DETALLES_MAX))}
            rows={4}
            placeholder="Ej.: Los equipos llegaron con caja dañada; revisar prioridad de este cliente…"
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 resize-y"
          />
          <div className="flex justify-end mt-1">
            <span className={`text-xs ${detalles.length >= DETALLES_MAX ? 'text-rose-500' : 'text-slate-400'}`} data-testid="recepcion-detalles-counter">
              {detalles.length}/{DETALLES_MAX}
            </span>
          </div>
        </div>

        {/* Acción */}
          <div className="flex items-center justify-between">
            <div className="text-sm text-slate-500" data-testid="recepcion-total">
              Total a recibir: <span className="font-semibold text-slate-800">{totalEquipos}</span> equipo(s)
            </div>
            <Button onClick={openSummary} disabled={!canSubmit} data-testid="recepcion-review-btn" className="bg-emerald-600 hover:bg-emerald-700">
              <ClipboardCheck size={16} className="mr-1" /> Revisar y confirmar
            </Button>
          </div>
          {!canEdit && (
            <p className="text-xs text-amber-600 mt-2">No tienes permiso de Edición Total para confirmar recepciones.</p>
          )}
        </div>

        {/* Resumen de validación */}
        <Dialog open={summaryOpen} onOpenChange={setSummaryOpen}>
          <DialogContent className="max-w-lg" data-testid="recepcion-summary-dialog">
            <DialogHeader>
              <DialogTitle>Confirmar recepción de equipos</DialogTitle>
            </DialogHeader>
            <div className="text-sm">
              <div className="bg-emerald-50 text-emerald-800 rounded-lg px-3 py-2 mb-3">
                <span className="font-semibold">{selectedClient?.fantasy_name || selectedClient?.legal_name}</span>
                <span className="text-emerald-600"> · {selectedClient?.rif}</span>
              </div>
              <div className="space-y-2 max-h-64 overflow-auto">
                {validRows.map((r) => (
                  <div key={r.id} className="border border-slate-200 rounded-lg p-2.5">
                    <div className="font-medium text-slate-800">{r.model_name} <span className="text-slate-400 font-normal">({r.serials.length})</span></div>
                    <div className="text-xs text-slate-500 mt-1">{r.serials.join(' · ')}</div>
                  </div>
                ))}
              </div>
              <div className="mt-3 text-slate-600">Total: <span className="font-semibold">{totalEquipos}</span> equipo(s) ingresarán como <span className="font-semibold text-emerald-700">"Recibido"</span>.</div>
              {detalles.trim() && (
                <div className="mt-3 border border-slate-200 rounded-lg p-2.5 bg-slate-50" data-testid="recepcion-summary-detalles">
                  <div className="text-xs font-semibold text-slate-600 mb-0.5">Detalles para Operaciones:</div>
                  <div className="text-xs text-slate-600 whitespace-pre-wrap">{detalles.trim()}</div>
                </div>
              )}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setSummaryOpen(false)} disabled={saving} data-testid="recepcion-cancel-btn">Cancelar</Button>
              <Button onClick={confirmRecepcion} disabled={saving} className="bg-emerald-600 hover:bg-emerald-700" data-testid="recepcion-confirm-btn">
                {saving ? <><Loader2 size={16} className="mr-1 animate-spin" /> Guardando...</> : 'Confirmar recepción'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
}
