import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, ChevronRight, ChevronDown, Plus, Trash2, Save, Settings2, Loader2, AlertCircle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Checkbox } from '../components/ui/checkbox';
import { Switch } from '../components/ui/switch';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import api from '../utils/api';

const TEMPLATE_CATEGORIES = ['Implementación', 'Pyme', 'Corp', 'General'];

function RecipientRow({ row, users, templates, onChange, onRemove }) {
  const update = (patch) => onChange({ ...row, ...patch });
  return (
    <tr className="border-b border-slate-100 hover:bg-slate-50">
      <td className="px-3 py-2 align-middle">
        <div className="flex items-center gap-2 text-sm text-slate-700 font-medium">
          <span role="img" aria-label="user">👤</span> Usuario interno
        </div>
      </td>
      <td className="px-3 py-2 align-middle">
        <Select value={row.user_id || ''} onValueChange={(v) => update({ user_id: v })}>
          <SelectTrigger className="h-9 w-64" data-testid={`oa-row-user-${row.row_id}`}>
            <SelectValue placeholder="Seleccionar usuario..." />
          </SelectTrigger>
          <SelectContent>
            {users.map((u) => (
              <SelectItem key={u.user_id} value={u.user_id}>
                {u.label}
                <span className="text-xs text-slate-400 ml-2">{u.departamento || u.cargo || u.email}</span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </td>
      <td className="px-3 py-2 align-middle">
        <Select value={row.template_id || ''} onValueChange={(v) => update({ template_id: v })}>
          <SelectTrigger className="h-9 w-72" data-testid={`oa-row-tpl-${row.row_id}`}>
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
        <Select value={row.delivery_channel || 'email'} onValueChange={(v) => update({ delivery_channel: v })}>
          <SelectTrigger className="h-9 w-48" data-testid={`oa-row-channel-${row.row_id}`}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="email">📧 Correo Electrónico</SelectItem>
            <SelectItem value="inbox">📨 Centro de Mensajes</SelectItem>
          </SelectContent>
        </Select>
      </td>
      <td className="px-3 py-2 align-middle text-right">
        <Button variant="ghost" size="sm" onClick={onRemove} className="text-red-600 hover:bg-red-50" data-testid={`oa-row-remove-${row.row_id}`}>
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

  const handleAddRow = () => {
    setRows((prev) => [
      ...prev,
      { row_id: `row_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`, type: 'user', user_id: null, template_id: null, send_pdf_attachments: false, delivery_channel: 'email' },
    ]);
    setDirty(true);
  };
  const handleChangeRow = (idx, nr) => { setRows((prev) => prev.map((r, i) => (i === idx ? nr : r))); setDirty(true); };
  const handleRemoveRow = (idx) => { setRows((prev) => prev.filter((_, i) => i !== idx)); setDirty(true); };

  const handleSave = async () => {
    for (const r of rows) {
      if (!r.user_id) { toast.error('Cada fila debe tener un usuario seleccionado'); return; }
    }
    setSaving(true);
    try {
      await api.put('/other-actions/configs', { action_id: action.id, enabled, recipients: rows });
      toast.success(`Configuración guardada: ${action.label}`);
      setDirty(false);
      onSaved?.();
    } catch (e) {
      toast.error(`Error al guardar: ${e.response?.data?.detail || e.message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="border border-slate-200 rounded-md mb-3 bg-white">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors"
        data-testid={`oa-action-toggle-${action.id}`}
      >
        <div className="flex items-center gap-2 text-left">
          {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          <div>
            <span className="font-medium text-slate-800 text-sm">{action.label}</span>
            {action.description && <p className="text-xs text-slate-500 mt-0.5">{action.description}</p>}
          </div>
          {hasConfig && <Badge variant="secondary" className="bg-emerald-100 text-emerald-700 text-xs">{existingCfg.recipients.length} dest.</Badge>}
          {existingCfg && existingCfg.enabled === false && <Badge variant="secondary" className="bg-red-100 text-red-700 text-xs">Desactivada</Badge>}
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-slate-100">
          <div className="flex items-center justify-between mt-3 mb-1 bg-slate-50 rounded px-3 py-2">
            <span className="text-sm font-medium text-slate-700">Acción activa (al desactivar no se envía ninguna notificación)</span>
            <Switch
              checked={enabled}
              onCheckedChange={(v) => { setEnabled(!!v); setDirty(true); }}
              data-testid={`oa-action-enabled-${action.id}`}
            />
          </div>

          {action.variables?.length > 0 && (
            <p className="text-xs text-slate-500 mb-2 mt-2">
              Variables disponibles para la plantilla: {action.variables.map((v) => `{${v}}`).join(', ')}
            </p>
          )}

          <table className="w-full mt-1 text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-3 py-2 text-left text-xs font-medium text-slate-600 uppercase">Tipo</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-slate-600 uppercase">Destinatario</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-slate-600 uppercase">Plantilla</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-slate-600 uppercase">Canal</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr><td colSpan="5" className="px-3 py-6 text-center text-slate-400 text-sm italic">Sin destinatarios configurados. La acción usará el comportamiento por defecto.</td></tr>
              ) : (
                rows.map((r, idx) => (
                  <RecipientRow
                    key={r.row_id}
                    row={r}
                    users={users}
                    templates={templates}
                    onChange={(nr) => handleChangeRow(idx, nr)}
                    onRemove={() => handleRemoveRow(idx)}
                  />
                ))
              )}
            </tbody>
          </table>
          <div className="flex justify-between items-center mt-3 gap-2">
            <Button variant="outline" size="sm" onClick={handleAddRow} data-testid={`oa-action-add-row-${action.id}`}>
              <Plus size={14} className="mr-1" />Agregar Fila
            </Button>
            <Button onClick={handleSave} disabled={!dirty || saving} size="sm" className="bg-blue-600 hover:bg-blue-700" data-testid={`oa-action-save-${action.id}`}>
              {saving ? <Loader2 size={14} className="animate-spin mr-1" /> : <Save size={14} className="mr-1" />}
              Guardar
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function OtherActionsConfig() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [catalog, setCatalog] = useState(null);
  const [configs, setConfigs] = useState({});

  const loadAll = async () => {
    setLoading(true);
    try {
      const [cat, cfg] = await Promise.all([
        api.get('/other-actions/catalog'),
        api.get('/other-actions/configs'),
      ]);
      setCatalog(cat.data);
      const map = {};
      (cfg.data.items || []).forEach((c) => { map[c.action_id] = c; });
      setConfigs(map);
      setError(null);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAll(); }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <Loader2 size={28} className="animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50" data-testid="other-actions-config-page">
      <div className="max-w-5xl mx-auto px-6 py-8">
        <Button variant="ghost" size="sm" onClick={() => navigate('/settings')} className="mb-4" data-testid="oa-back-btn">
          <ArrowLeft size={16} className="mr-1" />Volver a Configuración
        </Button>

        <div className="flex items-start gap-3 mb-6">
          <Settings2 size={28} className="text-blue-600 flex-shrink-0 mt-1" />
          <div>
            <h1 className="text-2xl font-bold text-slate-900 font-manrope">Configuración de otras Acciones</h1>
            <p className="text-sm text-slate-600 max-w-3xl mt-1">
              Define los destinatarios internos, la plantilla y el canal (Correo / Centro de Mensajes)
              de las notificaciones automáticas que antes estaban fijas en el código. Mientras una acción
              no se configure, mantiene su comportamiento por defecto; al desactivarla, no se envía nada.
            </p>
          </div>
        </div>

        {error ? (
          <div className="bg-red-50 border border-red-200 rounded-md p-4 flex items-center gap-2 text-red-700 text-sm" data-testid="oa-error">
            <AlertCircle size={18} /> {error}
          </div>
        ) : (
          (catalog?.actions || []).map((action) => (
            <ActionCard
              key={action.id}
              action={action}
              users={catalog.users}
              templates={catalog.templates}
              existingCfg={configs[action.id]}
              onSaved={loadAll}
            />
          ))
        )}
      </div>
    </div>
  );
}
