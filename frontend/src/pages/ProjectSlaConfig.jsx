import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, ChevronRight, ChevronDown, Plus, Trash2, Save, Timer, Loader2, AlertCircle, AlertTriangle, ShieldAlert, Snowflake } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Switch } from '../components/ui/switch';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import api from '../utils/api';

const TEMPLATE_CATEGORIES = ['Implementación', 'Pyme', 'Corp', 'General'];

function RecipientRow({ row, users, templates, onChange, onRemove }) {
  const update = (patch) => onChange({ ...row, ...patch });
  const isExternal = row.type === 'external_client';
  return (
    <tr className="border-b border-slate-100 hover:bg-slate-50">
      <td className="px-3 py-2 align-middle">
        <Select value={row.type || 'owner'} onValueChange={(v) => update({ type: v, user_id: v === 'user' ? row.user_id : null, delivery_channel: v === 'external_client' ? 'email' : row.delivery_channel })}>
          <SelectTrigger className="h-9 w-56" data-testid={`sla-row-type-${row.row_id}`}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="owner">⚡ Generador del Proyecto</SelectItem>
            <SelectItem value="project_implementer">🛠️ Usuario Implementador</SelectItem>
            <SelectItem value="external_client">🌐 Cliente Externo (correo)</SelectItem>
            <SelectItem value="user">👤 Usuario interno</SelectItem>
          </SelectContent>
        </Select>
      </td>
      <td className="px-3 py-2 align-middle">
        {row.type === 'user' ? (
          <Select value={row.user_id || ''} onValueChange={(v) => update({ user_id: v })}>
            <SelectTrigger className="h-9 w-60" data-testid={`sla-row-user-${row.row_id}`}>
              <SelectValue placeholder="Seleccionar usuario..." />
            </SelectTrigger>
            <SelectContent>
              {users.map((u) => (
                <SelectItem key={u.user_id} value={u.user_id}>
                  {u.label}<span className="text-xs text-slate-400 ml-2">{u.departamento || u.cargo || u.email}</span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <span className="text-sm text-slate-500 italic">
            {isExternal
              ? '— contacto del cliente (variables del proyecto) —'
              : row.type === 'project_implementer'
              ? '— implementador asignado al proyecto —'
              : '— usuario que dio de alta el proyecto —'}
          </span>
        )}
      </td>
      <td className="px-3 py-2 align-middle">
        <Select value={row.template_id || ''} onValueChange={(v) => update({ template_id: v })}>
          <SelectTrigger className="h-9 w-72" data-testid={`sla-row-tpl-${row.row_id}`}>
            <SelectValue placeholder="Seleccionar plantilla..." />
          </SelectTrigger>
          <SelectContent className="max-h-80">
            {TEMPLATE_CATEGORIES.map((cat) => {
              const subset = templates.filter((t) => (t.category || 'General') === cat);
              if (subset.length === 0) return null;
              return (
                <div key={cat}>
                  <div className="px-2 py-1 text-xs font-bold text-slate-500 bg-slate-50">{cat}</div>
                  {subset.map((t) => (
                    <SelectItem key={t.template_id} value={t.template_id}>
                      <span className="truncate max-w-[260px] inline-block">{t.name}</span>
                    </SelectItem>
                  ))}
                </div>
              );
            })}
          </SelectContent>
        </Select>
      </td>
      <td className="px-3 py-2 align-middle">
        <Select value={row.delivery_channel || 'email'} onValueChange={(v) => update({ delivery_channel: v })} disabled={isExternal}>
          <SelectTrigger className="h-9 w-48" data-testid={`sla-row-channel-${row.row_id}`}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="email">📧 Correo Electrónico</SelectItem>
            <SelectItem value="inbox">📨 Centro de Mensajes</SelectItem>
          </SelectContent>
        </Select>
      </td>
      <td className="px-3 py-2 align-middle text-right">
        <Button variant="ghost" size="sm" onClick={onRemove} className="text-red-600 hover:bg-red-50" data-testid={`sla-row-remove-${row.row_id}`}>
          <Trash2 size={14} />
        </Button>
      </td>
    </tr>
  );
}

function ActionCard({ action, users, templates, existingCfg, onSaved }) {
  const [expanded, setExpanded] = useState(false);
  const [rows, setRows] = useState([]);
  const [enabled, setEnabled] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (expanded && !dirty) {
      setRows(existingCfg?.recipients ? existingCfg.recipients.map((r) => ({ ...r })) : []);
      setEnabled(existingCfg ? existingCfg.enabled !== false : true);
    }
  }, [expanded, existingCfg, dirty]);

  const hasConfig = !!(existingCfg && existingCfg.recipients?.length);
  const isWarning = action.transition === 'warning';

  const handleAddRow = () => {
    setRows((prev) => [...prev, { row_id: `row_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`, type: 'owner', user_id: null, template_id: null, delivery_channel: 'email' }]);
    setDirty(true);
  };
  const handleChangeRow = (idx, nr) => { setRows((prev) => prev.map((r, i) => (i === idx ? nr : r))); setDirty(true); };
  const handleRemoveRow = (idx) => { setRows((prev) => prev.filter((_, i) => i !== idx)); setDirty(true); };

  const handleSave = async () => {
    for (const r of rows) {
      if (r.type === 'user' && !r.user_id) { toast.error('Cada fila de tipo "Usuario interno" debe tener un usuario seleccionado'); return; }
      if (!r.template_id) { toast.error('Cada fila debe tener una plantilla seleccionada'); return; }
    }
    setSaving(true);
    try {
      await api.put('/project-sla/actions', { action_id: action.id, enabled, recipients: rows });
      toast.success(`Acción guardada: ${action.label}`);
      setDirty(false);
      onSaved?.();
    } catch (e) {
      toast.error(`Error al guardar: ${e.response?.data?.detail || e.message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={`border rounded-md mb-3 bg-white ${isWarning ? 'border-yellow-200' : 'border-red-200'}`}>
      <button type="button" onClick={() => setExpanded((v) => !v)} className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors" data-testid={`sla-action-toggle-${action.id}`}>
        <div className="flex items-center gap-2 text-left">
          {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          <span className={`w-2.5 h-2.5 rounded-full ${isWarning ? 'bg-yellow-500' : 'bg-red-500'}`} />
          <div>
            <span className="font-medium text-slate-800 text-sm">{action.label}</span>
            {action.description && <p className="text-xs text-slate-500 mt-0.5 max-w-2xl">{action.description}</p>}
          </div>
          {hasConfig && <Badge variant="secondary" className="bg-emerald-100 text-emerald-700 text-xs">{existingCfg.recipients.length} dest.</Badge>}
          {existingCfg && existingCfg.enabled === false && <Badge variant="secondary" className="bg-red-100 text-red-700 text-xs">Desactivada</Badge>}
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-slate-100">
          <div className="flex items-center justify-between mt-3 mb-1 bg-slate-50 rounded px-3 py-2">
            <span className="text-sm font-medium text-slate-700">Acción activa (al desactivar no se envía ninguna notificación)</span>
            <Switch checked={enabled} onCheckedChange={(v) => { setEnabled(!!v); setDirty(true); }} data-testid={`sla-action-enabled-${action.id}`} />
          </div>
          {action.variables?.length > 0 && (
            <p className="text-xs text-slate-500 mb-2 mt-2">Variables disponibles: {action.variables.map((v) => `{${v}}`).join(', ')}</p>
          )}
          <table className="w-full mt-1 text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-3 py-2 text-left text-xs font-medium text-slate-600 uppercase">Tipo (Receptor)</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-slate-600 uppercase">Destinatario</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-slate-600 uppercase">Plantilla</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-slate-600 uppercase">Canal</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr><td colSpan="5" className="px-3 py-6 text-center text-slate-400 text-sm italic">Sin destinatarios. Al cumplirse la condición de tiempo no se enviará nada.</td></tr>
              ) : (
                rows.map((r, idx) => (
                  <RecipientRow key={r.row_id} row={r} users={users} templates={templates} onChange={(nr) => handleChangeRow(idx, nr)} onRemove={() => handleRemoveRow(idx)} />
                ))
              )}
            </tbody>
          </table>
          <div className="flex justify-between items-center mt-3 gap-2">
            <Button variant="outline" size="sm" onClick={handleAddRow} data-testid={`sla-action-add-row-${action.id}`}>
              <Plus size={14} className="mr-1" />Agregar Fila
            </Button>
            <Button onClick={handleSave} disabled={!dirty || saving} size="sm" className="bg-blue-600 hover:bg-blue-700" data-testid={`sla-action-save-${action.id}`}>
              {saving ? <Loader2 size={14} className="animate-spin mr-1" /> : <Save size={14} className="mr-1" />}Guardar
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ProjectSlaConfig() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [catalog, setCatalog] = useState(null);
  const [stages, setStages] = useState([]);
  const [matrix, setMatrix] = useState({});
  const [configs, setConfigs] = useState({});
  const [savingMatrix, setSavingMatrix] = useState(false);
  const [frozenFreq, setFrozenFreq] = useState(7);
  const [evaluating, setEvaluating] = useState(false);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [cfgRes, catRes, actRes] = await Promise.all([
        api.get('/project-sla/config'),
        api.get('/project-sla/catalog'),
        api.get('/project-sla/actions'),
      ]);
      setStages(cfgRes.data.stages || []);
      setMatrix(cfgRes.data.config?.stages || {});
      setFrozenFreq(cfgRes.data.config?.frozen_notify_frequency_days ?? 7);
      setCatalog(catRes.data);
      const map = {};
      (actRes.data.items || []).forEach((c) => { map[c.action_id] = c; });
      setConfigs(map);
      setError(null);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAll(); }, []);

  const updateCell = (stageKey, field, value) => {
    setMatrix((prev) => ({ ...prev, [stageKey]: { ...prev[stageKey], [field]: value === '' ? '' : Math.max(0, parseInt(value, 10) || 0) } }));
  };

  const handleSaveMatrix = async () => {
    for (const s of stages) {
      const cell = matrix[s.key] || {};
      if (cell.warning_days === '' || cell.delay_days === '') { toast.error(`Completa los días de la etapa "${s.label}"`); return; }
      if (Number(cell.delay_days) < Number(cell.warning_days)) { toast.error(`En "${s.label}", los días de retraso deben ser ≥ a los de advertencia`); return; }
    }
    setSavingMatrix(true);
    try {
      await api.put('/project-sla/config', { stages: matrix, frozen_notify_frequency_days: Number(frozenFreq) || 7 });
      toast.success('Matriz de tiempos (SLA) guardada');
      loadAll();
    } catch (e) {
      toast.error(`Error al guardar: ${e.response?.data?.detail || e.message}`);
    } finally {
      setSavingMatrix(false);
    }
  };

  const handleEvaluateNow = async () => {
    setEvaluating(true);
    try {
      const res = await api.post('/project-sla/evaluate');
      toast.success(`Evaluación ejecutada: ${res.data.evaluated} proyectos, ${res.data.transitions} cambios de color, ${res.data.dispatched} envíos`);
    } catch (e) {
      toast.error(`Error: ${e.response?.data?.detail || e.message}`);
    } finally {
      setEvaluating(false);
    }
  };

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center bg-slate-50"><Loader2 size={28} className="animate-spin text-blue-600" /></div>;
  }

  const warningActions = (catalog?.actions || []).filter((a) => a.transition === 'warning');
  const delayActions = (catalog?.actions || []).filter((a) => a.transition === 'delay');

  return (
    <div className="min-h-screen bg-slate-50" data-testid="project-sla-config-page">
      <div className="max-w-5xl mx-auto px-6 py-8">
        <Button variant="ghost" size="sm" onClick={() => navigate('/settings')} className="mb-4" data-testid="sla-back-btn">
          <ArrowLeft size={16} className="mr-1" />Volver a Configuración
        </Button>

        <div className="flex items-start gap-3 mb-6">
          <Timer size={28} className="text-blue-600 flex-shrink-0 mt-1" />
          <div>
            <h1 className="text-2xl font-bold text-slate-900 font-manrope">Configuración de Tiempos y SLA de Proyectos</h1>
            <p className="text-sm text-slate-600 max-w-3xl mt-1">
              Define a cuántos días el semáforo de cada etapa pasa de <span className="font-semibold text-green-600">Verde</span> a
              <span className="font-semibold text-yellow-600"> Amarillo</span> (advertencia) y de Amarillo a
              <span className="font-semibold text-red-600"> Rojo</span> (retraso). Luego configura las acciones automáticas
              (correo o Centro de Mensajes) que se disparan en cada transición de color.
            </p>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-md p-4 flex items-center gap-2 text-red-700 text-sm mb-4" data-testid="sla-error">
            <AlertCircle size={18} /> {error}
          </div>
        )}

        {/* ===== MATRIZ DE DÍAS (SLA) ===== */}
        <div className="bg-white border border-slate-200 rounded-lg p-5 mb-8" data-testid="sla-matrix-card">
          <h2 className="text-base font-bold text-slate-800 mb-1">Matriz de Días (Semáforo de Tiempos)</h2>
          <p className="text-xs text-slate-500 mb-4">El conteo de días inicia desde que el proyecto entra al estado actual.</p>
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50">
                <th className="px-3 py-2 text-left text-xs font-semibold text-slate-600 uppercase">Etapa del Proyecto</th>
                <th className="px-3 py-2 text-left text-xs font-semibold text-yellow-700 uppercase">Días para notificar advertencia (Verde → Amarillo)</th>
                <th className="px-3 py-2 text-left text-xs font-semibold text-red-700 uppercase">Días para notificar retraso (Amarillo → Rojo)</th>
              </tr>
            </thead>
            <tbody>
              {stages.map((s) => (
                <tr key={s.key} className="border-b border-slate-100">
                  <td className="px-3 py-3 font-medium text-slate-700">{s.label}<div className="text-xs text-slate-400">Estado: {s.status}</div></td>
                  <td className="px-3 py-3">
                    <div className="flex items-center gap-2">
                      <AlertTriangle size={15} className="text-yellow-500" />
                      <Input type="number" min="0" value={matrix[s.key]?.warning_days ?? ''} onChange={(e) => updateCell(s.key, 'warning_days', e.target.value)} className="h-9 w-24" data-testid={`sla-matrix-warning-${s.key}`} />
                      <span className="text-xs text-slate-400">días</span>
                    </div>
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex items-center gap-2">
                      <ShieldAlert size={15} className="text-red-500" />
                      <Input type="number" min="0" value={matrix[s.key]?.delay_days ?? ''} onChange={(e) => updateCell(s.key, 'delay_days', e.target.value)} className="h-9 w-24" data-testid={`sla-matrix-delay-${s.key}`} />
                      <span className="text-xs text-slate-400">días</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-4 flex flex-wrap items-center gap-3 rounded-lg border border-blue-200 bg-blue-50/60 p-3" data-testid="frozen-freq-config">
            <span className="flex items-center gap-1.5 text-sm font-semibold text-blue-800">
              <Snowflake size={15} className="text-blue-600" />
              Frecuencia de Notificación de Congelados (Días)
            </span>
            <Input
              type="number" min="1"
              value={frozenFreq}
              onChange={(e) => setFrozenFreq(e.target.value === '' ? '' : Math.max(1, parseInt(e.target.value, 10) || 1))}
              className="h-9 w-24"
              data-testid="frozen-freq-input"
            />
            <span className="text-xs text-slate-500">Cada cuántos días se avisa de los proyectos que siguen Congelados (se guarda con "Guardar Matriz").</span>
          </div>
          <div className="flex justify-between items-center mt-4 gap-2">
            <Button variant="outline" size="sm" onClick={handleEvaluateNow} disabled={evaluating} data-testid="sla-evaluate-btn">
              {evaluating ? <Loader2 size={14} className="animate-spin mr-1" /> : <Timer size={14} className="mr-1" />}Evaluar Ahora
            </Button>
            <Button onClick={handleSaveMatrix} disabled={savingMatrix} className="bg-blue-600 hover:bg-blue-700" data-testid="sla-matrix-save-btn">
              {savingMatrix ? <Loader2 size={14} className="animate-spin mr-1" /> : <Save size={14} className="mr-1" />}Guardar Matriz
            </Button>
          </div>
        </div>

        {/* ===== ACCIONES (TRIGGERS) ===== */}
        <div className="mb-2">
          <h2 className="text-base font-bold text-slate-800 flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-yellow-500" />Bloque 1 — Transición Verde → Amarillo (Advertencia)</h2>
          <p className="text-xs text-slate-500 mb-3">Se dispara al alcanzar los días de advertencia en cada etapa.</p>
        </div>
        {warningActions.map((action) => (
          <ActionCard key={action.id} action={action} users={catalog.users} templates={catalog.templates} existingCfg={configs[action.id]} onSaved={loadAll} />
        ))}

        <div className="mt-6 mb-2">
          <h2 className="text-base font-bold text-slate-800 flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-red-500" />Bloque 2 — Transición Amarillo → Rojo (Retraso / Vencimiento)</h2>
          <p className="text-xs text-slate-500 mb-3">Se dispara al alcanzar los días de retraso en cada etapa.</p>
        </div>
        {delayActions.map((action) => (
          <ActionCard key={action.id} action={action} users={catalog.users} templates={catalog.templates} existingCfg={configs[action.id]} onSaved={loadAll} />
        ))}
      </div>
    </div>
  );
}
