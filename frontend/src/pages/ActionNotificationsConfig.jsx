import { useState, useEffect, useMemo, useRef } from 'react';
import { formatDateTime, formatDate, formatTime } from '../utils/dateFormat';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, ChevronRight, ChevronDown, Plus, Trash2, Save, ShieldCheck, Loader2, AlertCircle, Sparkles, Activity, RefreshCw, Edit2, Eye, EyeOff } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Checkbox } from '../components/ui/checkbox';
import { Badge } from '../components/ui/badge';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../components/ui/alert-dialog';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';
import api from '../utils/api';

/**
 * Configuración de Acciones de Cotizaciones — Fase 3.
 *
 * Página admin que permite definir, por cada (tipo_negocio, sub_categoria, accion),
 * qué destinatarios reciben qué plantilla y si llevan PDFs.
 *
 * - Tab "Matriz": acordeones colapsados con la configuración de cada combinación.
 * - Tab "Auditoría": historial de despachos del motor con filtros.
 * - Botón "Pre-cargar matriz legacy": llama al seeder admin-only que crea
 *   skeleton (con plantilla cliente cuando aplica) por cada combinación.
 */
const TEMPLATE_CATEGORIES = ['Pyme', 'Corp', 'Implementación', 'Equipos', 'Reparaciones', 'General'];

function configKey(business_type, sub_category, action_id) {
  return `${business_type}|${sub_category || '_'}|${action_id}`;
}

// Ordena los destinatarios en orden alfabético estricto (A-Z) por nombre.
// NOTA: NO se filtra por sede. Cualquier usuario (PYME o CORP) puede ser
// destinatario de notificaciones de cualquier unidad de negocio, incluyendo
// las Implementaciones Pyme (que pueden requerir avisar a personal Corporativo).
function usersForBiz(users, bizId) {
  const list = users || [];
  return [...list].sort((a, b) => (a.label || '').localeCompare(b.label || '', 'es', { sensitivity: 'base' }));
}

function MatrixRow({ row, users, templates, onChange, onRemove }) {
  // Plantillas filtradas por categoría coherente con el tipo de negocio
  // (la categoría se determina afuera; aquí solo se muestra el dropdown completo).
  const [, forceUpdate] = useState(0);

  const update = (patch) => {
    onChange({ ...row, ...patch });
    forceUpdate((x) => x + 1);
  };

  return (
    <tr className="border-b border-slate-100 hover:bg-slate-50">
      <td className="px-3 py-2 align-middle">
        <Select value={row.type} onValueChange={(v) => update({ type: v, user_id: v === 'user' ? row.user_id : null })}>
          <SelectTrigger className="h-9 w-52" data-testid={`row-type-${row.row_id}`}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="client_field">📧 Correo del Cliente</SelectItem>
            <SelectItem value="user">👤 Usuario interno</SelectItem>
            <SelectItem value="session_user">⚡ Usuario generador</SelectItem>
            <SelectItem value="session_executive">🧑‍💼 Ejecutivo generador</SelectItem>
          </SelectContent>
        </Select>
      </td>
      <td className="px-3 py-2 align-middle">
        {row.type === 'user' ? (
          <Select value={row.user_id || ''} onValueChange={(v) => update({ user_id: v })}>
            <SelectTrigger className="h-9 w-64" data-testid={`row-user-${row.row_id}`}>
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
        ) : (
          <span className="text-sm text-slate-500 italic">
            {row.type === 'session_user'
              ? '— usuario que ejecuta la acción —'
              : row.type === 'session_executive'
              ? '— ejecutivo creador de la cotización —'
              : '— se resuelve al ejecutar la acción —'}
          </span>
        )}
      </td>
      <td className="px-3 py-2 align-middle">
        <Select value={row.template_id || ''} onValueChange={(v) => update({ template_id: v })}>
          <SelectTrigger className="h-9 w-72" data-testid={`row-tpl-${row.row_id}`}>
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
      <td className="px-3 py-2 align-middle text-center">
        <Checkbox
          checked={row.send_pdf_attachments}
          onCheckedChange={(v) => update({ send_pdf_attachments: !!v })}
          data-testid={`row-pdf-${row.row_id}`}
        />
      </td>
      <td className="px-3 py-2 align-middle">
        {/* Canal de entrega — aplica a usuarios internos y a destinatarios
            dinámicos de sesión. Para "client_field" se fuerza Email (cliente externo). */}
        {row.type !== 'client_field' ? (
          <Select
            value={row.delivery_channel || 'email'}
            onValueChange={(v) => update({ delivery_channel: v })}
          >
            <SelectTrigger className="h-9 w-44" data-testid={`row-channel-${row.row_id}`}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="email">📧 Correo Electrónico</SelectItem>
              <SelectItem value="inbox">📨 Centro de Mensajes</SelectItem>
            </SelectContent>
          </Select>
        ) : (
          <span className="text-xs text-slate-400 italic">Email (cliente externo)</span>
        )}
      </td>
      <td className="px-3 py-2 align-middle text-right">
        <Button variant="ghost" size="sm" onClick={onRemove} className="text-red-600 hover:bg-red-50" data-testid={`row-remove-${row.row_id}`}>
          <Trash2 size={14} />
        </Button>
      </td>
    </tr>
  );
}

function ActionAccordion({ action, businessType, subCategory, configs, users, templates, onSaved }) {
  const [expanded, setExpanded] = useState(false);
  const [rows, setRows] = useState([]);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  const cfgKey = configKey(businessType, subCategory, action.id);
  const existingCfg = configs[cfgKey];
  const hasConfig = !!(existingCfg && existingCfg.recipients?.length);

  useEffect(() => {
    if (expanded && !dirty) {
      setRows(existingCfg?.recipients ? existingCfg.recipients.map((r) => ({ ...r })) : []);
    }
  }, [expanded, existingCfg, dirty]);

  const handleAddRow = () => {
    setRows((prev) => [
      ...prev,
      { row_id: `row_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`, type: 'client_field', user_id: null, template_id: null, send_pdf_attachments: true, delivery_channel: 'email' },
    ]);
    setDirty(true);
  };
  const handleChangeRow = (idx, newRow) => {
    setRows((prev) => prev.map((r, i) => (i === idx ? newRow : r)));
    setDirty(true);
  };
  const handleRemoveRow = (idx) => {
    setRows((prev) => prev.filter((_, i) => i !== idx));
    setDirty(true);
  };
  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put('/action-notifications/configs', {
        business_type: businessType,
        product_subcategory: subCategory,
        action_id: action.id,
        recipients: rows,
      });
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
    <div className="border border-slate-200 rounded-md mb-2 bg-white">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-slate-50 transition-colors"
        data-testid={`action-toggle-${action.id}`}
      >
        <div className="flex items-center gap-2">
          {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          <span className="font-medium text-slate-800 text-sm">{action.label}</span>
          {hasConfig && <Badge variant="secondary" className="bg-emerald-100 text-emerald-700 text-xs">{existingCfg.recipients.length} dest.</Badge>}
        </div>
        {action.pdfs_default?.length > 0 && (
          <span className="text-xs text-slate-500">PDFs: {action.pdfs_default.join(', ')}</span>
        )}
      </button>

      {expanded && (
        <div className="px-3 pb-3 border-t border-slate-100">
          <table className="w-full mt-3 text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-3 py-2 text-left text-xs font-medium text-slate-600 uppercase">Tipo</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-slate-600 uppercase">Destinatario</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-slate-600 uppercase">Plantilla</th>
                <th className="px-3 py-2 text-center text-xs font-medium text-slate-600 uppercase">PDFs</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-slate-600 uppercase">Canal</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr><td colSpan="6" className="px-3 py-6 text-center text-slate-400 text-sm italic">Sin destinatarios configurados. La acción usará el comportamiento por defecto.</td></tr>
              ) : (
                rows.map((r, idx) => (
                  <MatrixRow
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
            <Button variant="outline" size="sm" onClick={handleAddRow} data-testid={`action-add-row-${action.id}`}>
              <Plus size={14} className="mr-1" />Agregar Fila
            </Button>
            <Button onClick={handleSave} disabled={!dirty || saving} size="sm" className="bg-blue-600 hover:bg-blue-700" data-testid={`action-save-${action.id}`}>
              {saving ? <Loader2 size={14} className="animate-spin mr-1" /> : <Save size={14} className="mr-1" />}
              Guardar
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function SubCategoryAccordion({ subCategory, businessType, actions, allowedMap, configs, users, templates, onSaved }) {
  const [expanded, setExpanded] = useState(false);
  const subId = subCategory?.id || null;
  // Filtrar acciones permitidas para esta combinación (biz, sub)
  const allowedKey = `${businessType}|${subId || '_'}`;
  const allowedIds = allowedMap?.[allowedKey] || [];
  const filteredActions = allowedIds.length > 0
    ? allowedIds.map((id) => actions.find((a) => a.id === id)).filter(Boolean)
    : actions;
  const actionsConfigured = filteredActions.filter((a) => configs[configKey(businessType, subId, a.id)]?.recipients?.length).length;

  return (
    <div className="border border-slate-200 rounded-md mb-2 bg-slate-50/50">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-100 transition-colors"
        data-testid={`subcat-toggle-${businessType}-${subId || 'none'}`}
      >
        <div className="flex items-center gap-2">
          {expanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
          <span className="font-semibold text-slate-700">{subCategory?.label || 'Sin sub-categoría'}</span>
          <Badge variant="outline" className="text-xs">{filteredActions.length} acción(es)</Badge>
          {actionsConfigured > 0 && (
            <Badge className="bg-blue-100 text-blue-700">{actionsConfigured}/{filteredActions.length} configuradas</Badge>
          )}
        </div>
      </button>
      {expanded && (
        <div className="px-3 pb-3">
          {filteredActions.map((act) => (
            <ActionAccordion
              key={act.id}
              action={act}
              businessType={businessType}
              subCategory={subId}
              configs={configs}
              users={users}
              templates={templates}
              onSaved={onSaved}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function BusinessTypeAccordion({ business, subCategories, actions, allowedMap, configs, users, templates, onSaved }) {
  const [expanded, setExpanded] = useState(false);
  // Filtro PyME/Corp + orden alfabético de destinatarios según la unidad de negocio.
  const bizUsers = useMemo(() => usersForBiz(users, business.id), [users, business.id]);
  // Iter50: filtrar subcategorías por las que tengan acciones permitidas para
  // ESTE negocio. Antes se renderizaban todas, mostrando subcategorías
  // ajenas (ej. VPOS bajo "Equipos y Accesorios"). Igual lógica que el bloque
  // de Override de Acciones.
  const subs = business.has_sub
    ? subCategories.filter((s) => (allowedMap[`${business.id}|${s.id}`] || []).length)
    : [null];

  return (
    <div className="border-2 border-slate-300 rounded-lg mb-3 bg-white shadow-sm">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-4 hover:bg-slate-50 transition-colors rounded-t-lg"
        data-testid={`biz-toggle-${business.id}`}
      >
        <div className="flex items-center gap-3">
          {expanded ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
          <span className="font-bold text-slate-900 text-base">{business.label}</span>
          {!business.has_sub && (
            <Badge variant="outline" className="text-xs">Sin sub-categorías</Badge>
          )}
        </div>
      </button>
      {expanded && (
        <div className="p-3 border-t border-slate-200">
          {subs.map((sub) => (
            <SubCategoryAccordion
              key={sub?.id || 'none'}
              subCategory={sub}
              businessType={business.id}
              actions={actions}
              allowedMap={allowedMap}
              configs={configs}
              users={bizUsers}
              templates={templates}
              onSaved={onSaved}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function ActionNotificationsConfig() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [catalog, setCatalog] = useState(null);
  const [configs, setConfigs] = useState({});
  const [tab, setTab] = useState('matrix'); // matrix | audit | overrides | custom
  const [seedDialogOpen, setSeedDialogOpen] = useState(false);
  const [seeding, setSeeding] = useState(false);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [catRes, cfgRes] = await Promise.all([
        api.get('/action-notifications/catalog'),
        api.get('/action-notifications/configs'),
      ]);
      setCatalog(catRes.data);
      const map = {};
      for (const c of cfgRes.data?.items || []) {
        map[c.config_key] = c;
      }
      setConfigs(map);
    } catch (e) {
      toast.error(`Error cargando configuración: ${e.response?.data?.detail || e.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAll(); }, []);

  const handleSeed = async (overwrite) => {
    setSeeding(true);
    try {
      const res = await api.post(`/action-notifications/seed-legacy?overwrite=${overwrite}`);
      const d = res.data;
      toast.success(`Matriz legacy: ${d.created} creada(s), ${d.updated} actualizada(s), ${d.skipped_existing} omitida(s)`);
      setSeedDialogOpen(false);
      await loadAll();
    } catch (e) {
      toast.error(`Error precargando matriz: ${e.response?.data?.detail || e.message}`);
    } finally {
      setSeeding(false);
    }
  };

  const totalConfigs = useMemo(() => Object.keys(configs).filter((k) => configs[k]?.recipients?.length).length, [configs]);

  if (loading || !catalog) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={32} className="animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto p-6" data-testid="action-notifications-page">
      <div className="flex items-center gap-3 mb-4">
        <Button variant="ghost" size="sm" onClick={() => navigate('/settings')} data-testid="anc-back-btn">
          <ArrowLeft size={18} className="mr-1" />
          Configuración
        </Button>
      </div>

      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <ShieldCheck size={26} className="text-blue-600" />
            Configuración de Acciones de Cotizaciones
          </h1>
          <p className="text-slate-600 mt-1 text-sm">
            Define, por cada acción del flujo, quiénes reciben correos y con qué plantilla.
            Las acciones sin configurar conservan el comportamiento por defecto del sistema.
          </p>
        </div>
        <Button
          onClick={() => setSeedDialogOpen(true)}
          variant="outline"
          className="border-violet-300 text-violet-700 hover:bg-violet-50 flex-shrink-0"
          data-testid="seed-legacy-btn"
        >
          <Sparkles size={16} className="mr-2" />
          Pre-cargar matriz legacy
        </Button>
      </div>

      <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 mb-5 flex items-start gap-2">
        <AlertCircle size={18} className="text-emerald-600 mt-0.5 flex-shrink-0" />
        <div className="text-sm text-emerald-900">
          <strong>Motor activo.</strong> Las configuraciones guardadas aquí <strong>se ejecutan en
          tiempo real</strong>: cuando el flujo dispare una acción para una combinación con regla
          definida, el correo se envía según los destinatarios y plantillas configuradas. Si la
          combinación no tiene regla, el sistema cae al envío legacy automáticamente (cero
          regresión).
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-slate-200">
        <button
          type="button"
          onClick={() => setTab('matrix')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            tab === 'matrix' ? 'border-blue-600 text-blue-700' : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
          data-testid="tab-matrix"
        >
          Matriz de configuración
        </button>
        <button
          type="button"
          onClick={() => setTab('audit')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
            tab === 'audit' ? 'border-blue-600 text-blue-700' : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
          data-testid="tab-audit"
        >
          <Activity size={14} />
          Auditoría de envíos
        </button>
        <button
          type="button"
          onClick={() => setTab('overrides')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
            tab === 'overrides' ? 'border-blue-600 text-blue-700' : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
          data-testid="tab-overrides"
        >
          <Sparkles size={14} />
          Override de Acciones
        </button>
        <button
          type="button"
          onClick={() => setTab('custom')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
            tab === 'custom' ? 'border-blue-600 text-blue-700' : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
          data-testid="tab-custom"
        >
          <Plus size={14} />
          Acciones Personalizadas
        </button>
      </div>

      {tab === 'matrix' && (
        <>
          <div className="flex items-center justify-between mb-4">
            <div className="text-sm text-slate-600">
              <strong className="text-slate-900">{totalConfigs}</strong> configuración(es) guardada(s) ·{' '}
              <strong className="text-slate-900">{catalog.users.length}</strong> usuarios disponibles ·{' '}
              <strong className="text-slate-900">{catalog.templates.length}</strong> plantillas disponibles
            </div>
          </div>

          {catalog.business_types.map((biz) => (
            <BusinessTypeAccordion
              key={biz.id}
              business={biz}
              subCategories={catalog.product_subcategories}
              actions={catalog.actions}
              allowedMap={catalog.allowed_actions_by_biz_sub || {}}
              configs={configs}
              users={catalog.users}
              templates={catalog.templates}
              onSaved={loadAll}
            />
          ))}
        </>
      )}

      {tab === 'audit' && <AuditLogTab actions={catalog.actions} businessTypes={catalog.business_types} />}

      {tab === 'overrides' && <OverridesTab actions={catalog.actions} businessTypes={catalog.business_types} subCategories={catalog.product_subcategories} allowedMap={catalog.allowed_actions_by_biz_sub || {}} users={catalog.users} />}

      {tab === 'custom' && <CustomActionsTab actions={catalog.actions} businessTypes={catalog.business_types} subCategories={catalog.product_subcategories} users={catalog.users} />}

      <AlertDialog open={seedDialogOpen} onOpenChange={setSeedDialogOpen}>
        <AlertDialogContent data-testid="seed-legacy-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Pre-cargar matriz legacy</AlertDialogTitle>
            <AlertDialogDescription>
              Esta acción crea una configuración base para <strong>cada combinación</strong> (tipo
              de negocio + sub-categoría + acción). Las combinaciones con notificación al cliente
              (envío al cliente, aprobación de reparación, reparación finalizada) se precargan con
              la fila <em>Correo del Cliente</em> y la plantilla equivalente. Las demás se crean
              vacías para que las completes manualmente.
              <br /><br />
              <strong>Las configuraciones que ya tienen destinatarios definidos NO se sobrescriben.</strong>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={seeding}>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => handleSeed(false)}
              disabled={seeding}
              className="bg-violet-600 hover:bg-violet-700"
              data-testid="seed-legacy-confirm"
            >
              {seeding ? <Loader2 size={16} className="mr-2 animate-spin" /> : <Sparkles size={16} className="mr-2" />}
              Pre-cargar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function AuditLogTab({ actions, businessTypes }) {
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState({ action_id: '', business_type: '', quote_number: '', date_from: '', date_to: '' });
  const [offset, setOffset] = useState(0);
  const limit = 25;

  const load = async (newOffset = 0) => {
    setLoading(true);
    try {
      const params = { limit, offset: newOffset };
      Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v; });
      const res = await api.get('/action-notifications/audit-log', { params });
      setItems(res.data.items || []);
      setTotal(res.data.total || 0);
      setOffset(newOffset);
    } catch (e) {
      toast.error(`Error cargando auditoría: ${e.response?.data?.detail || e.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(0); }, []); // eslint-disable-line

  const fmtDate = (iso) => {
    if (!iso) return '—';
    try {
      return formatDateTime(iso);
    } catch {
      return iso;
    }
  };

  return (
    <div data-testid="audit-log-tab">
      <div className="bg-white border border-slate-200 rounded-lg p-4 mb-4">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <div>
            <label className="text-xs text-slate-600 mb-1 block">Acción</label>
            <Select value={filters.action_id || 'all'} onValueChange={(v) => setFilters((f) => ({ ...f, action_id: v === 'all' ? '' : v }))}>
              <SelectTrigger className="h-9" data-testid="audit-filter-action">
                <SelectValue placeholder="Todas" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas</SelectItem>
                {actions.map((a) => <SelectItem key={a.id} value={a.id}>{a.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-xs text-slate-600 mb-1 block">Tipo de negocio</label>
            <Select value={filters.business_type || 'all'} onValueChange={(v) => setFilters((f) => ({ ...f, business_type: v === 'all' ? '' : v }))}>
              <SelectTrigger className="h-9" data-testid="audit-filter-biz">
                <SelectValue placeholder="Todos" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                {businessTypes.map((b) => <SelectItem key={b.id} value={b.id}>{b.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-xs text-slate-600 mb-1 block">Nº cotización</label>
            <Input
              value={filters.quote_number}
              onChange={(e) => setFilters((f) => ({ ...f, quote_number: e.target.value }))}
              placeholder="COT-2026-..."
              className="h-9"
              data-testid="audit-filter-quote"
            />
          </div>
          <div>
            <label className="text-xs text-slate-600 mb-1 block">Desde</label>
            <Input
              type="date"
              value={filters.date_from}
              onChange={(e) => setFilters((f) => ({ ...f, date_from: e.target.value }))}
              className="h-9"
              data-testid="audit-filter-from"
            />
          </div>
          <div>
            <label className="text-xs text-slate-600 mb-1 block">Hasta</label>
            <Input
              type="date"
              value={filters.date_to}
              onChange={(e) => setFilters((f) => ({ ...f, date_to: e.target.value }))}
              className="h-9"
              data-testid="audit-filter-to"
            />
          </div>
        </div>
        <div className="mt-3 flex gap-2">
          <Button onClick={() => load(0)} disabled={loading} size="sm" data-testid="audit-apply-btn">
            {loading ? <Loader2 size={14} className="mr-1 animate-spin" /> : <RefreshCw size={14} className="mr-1" />}
            Aplicar filtros
          </Button>
          <Button
            onClick={() => { setFilters({ action_id: '', business_type: '', quote_number: '', date_from: '', date_to: '' }); setTimeout(() => load(0), 0); }}
            disabled={loading}
            variant="outline"
            size="sm"
            data-testid="audit-clear-btn"
          >
            Limpiar
          </Button>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Fecha</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Acción</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Combinación</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Cotización</th>
              <th className="px-3 py-2 text-center font-medium text-slate-600">Enviados</th>
              <th className="px-3 py-2 text-center font-medium text-slate-600">Saltados</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Ejecutado por</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && !loading && (
              <tr><td colSpan={7} className="px-3 py-8 text-center text-slate-400">Sin despachos registrados con estos filtros</td></tr>
            )}
            {items.map((it, idx) => (
              <tr key={idx} className="border-b border-slate-100 hover:bg-slate-50" data-testid={`audit-row-${idx}`}>
                <td className="px-3 py-2 font-mono text-xs">{fmtDate(it.executed_at)}</td>
                <td className="px-3 py-2"><Badge variant="outline" className="text-xs">{it.action_id}</Badge></td>
                <td className="px-3 py-2 font-mono text-xs text-slate-600">{it.config_key}</td>
                <td className="px-3 py-2 font-mono text-xs">{it.quote_number || '—'}</td>
                <td className="px-3 py-2 text-center">
                  <Badge className={it.sent_count > 0 ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'}>
                    {it.sent_count || 0}
                  </Badge>
                </td>
                <td className="px-3 py-2 text-center">
                  {(it.skipped?.length || 0) > 0 ? (
                    <Badge className="bg-amber-100 text-amber-800" title={(it.skipped || []).map((s) => s.reason).join('\n')}>
                      {it.skipped.length}
                    </Badge>
                  ) : (
                    <span className="text-slate-400 text-xs">0</span>
                  )}
                </td>
                <td className="px-3 py-2 text-xs text-slate-600">{it.executed_by || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="px-3 py-2 border-t border-slate-200 bg-slate-50 flex items-center justify-between text-xs text-slate-600">
          <span>Total: <strong>{total}</strong> · Mostrando {items.length === 0 ? 0 : offset + 1}–{offset + items.length}</span>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" disabled={offset === 0 || loading} onClick={() => load(Math.max(0, offset - limit))} data-testid="audit-prev-btn">‹ Anterior</Button>
            <Button size="sm" variant="outline" disabled={offset + items.length >= total || loading} onClick={() => load(offset + limit)} data-testid="audit-next-btn">Siguiente ›</Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// FASE B — Override de Acciones Legacy (renombrar / desactivar / restringir)
// ============================================================================
// ============================================================================
// UserMultiSelect — Selector múltiple de usuarios con búsqueda
// ============================================================================
function UserMultiSelect({ users = [], selected = [], onChange, testid = 'user-multi-select' }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const containerRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const q = query.trim().toLowerCase();
  const filtered = q
    ? users.filter((u) =>
        (u.label || '').toLowerCase().includes(q) ||
        (u.email || '').toLowerCase().includes(q) ||
        (u.cargo || '').toLowerCase().includes(q) ||
        (u.departamento || '').toLowerCase().includes(q)
      )
    : users;

  const toggle = (uid) => {
    if (selected.includes(uid)) onChange(selected.filter((x) => x !== uid));
    else onChange([...selected, uid]);
  };

  const selectedLabels = selected
    .map((uid) => users.find((u) => u.user_id === uid)?.label)
    .filter(Boolean);

  return (
    <div className="relative" ref={containerRef} data-testid={testid}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full min-h-9 px-2 py-1.5 border border-slate-200 rounded bg-white text-left text-sm hover:border-slate-300 focus:outline-none focus:border-blue-500 flex flex-wrap items-center gap-1"
        data-testid={`${testid}-trigger`}
      >
        {selected.length === 0 ? (
          <span className="text-slate-400">Todos los usuarios</span>
        ) : (
          selectedLabels.slice(0, 3).map((lab, i) => (
            <Badge key={i} variant="secondary" className="text-[10px] bg-blue-100 text-blue-800">{lab}</Badge>
          ))
        )}
        {selected.length > 3 && <Badge variant="secondary" className="text-[10px]">+{selected.length - 3}</Badge>}
      </button>
      {open && (
        <div className="absolute z-50 mt-1 w-full max-h-72 bg-white border border-slate-200 rounded shadow-lg flex flex-col">
          <div className="p-2 border-b border-slate-100">
            <Input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Buscar usuario..."
              className="h-8 text-sm"
              data-testid={`${testid}-search`}
            />
          </div>
          <div className="overflow-y-auto flex-1 py-1">
            {filtered.length === 0 ? (
              <div className="px-3 py-4 text-xs text-slate-400 text-center">Sin resultados</div>
            ) : (
              filtered.map((u) => {
                const checked = selected.includes(u.user_id);
                return (
                  <label
                    key={u.user_id}
                    className="flex items-center gap-2 px-3 py-1.5 hover:bg-slate-50 cursor-pointer text-sm"
                    data-testid={`${testid}-option-${u.user_id}`}
                  >
                    <Checkbox checked={checked} onCheckedChange={() => toggle(u.user_id)} />
                    <div className="flex-1 min-w-0">
                      <div className="truncate">{u.label}</div>
                      <div className="text-[10px] text-slate-400 truncate">{u.cargo || u.departamento || u.email}</div>
                    </div>
                  </label>
                );
              })
            )}
          </div>
          {selected.length > 0 && (
            <div className="p-1.5 border-t border-slate-100 flex justify-between items-center">
              <span className="text-[10px] text-slate-500 px-2">{selected.length} seleccionado{selected.length !== 1 ? 's' : ''}</span>
              <Button size="sm" variant="ghost" className="h-6 text-xs" onClick={() => onChange([])}>Limpiar</Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}


function OverridesTab({ actions, businessTypes, subCategories, allowedMap, users = [] }) {
  const [overrides, setOverrides] = useState({});
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get('/quote-action-overrides');
      const map = {};
      for (const o of res.data?.items || []) map[o.config_key] = o;
      setOverrides(map);
    } catch (e) {
      toast.error(`Error cargando overrides: ${e.response?.data?.detail || e.message}`);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  if (loading) return <div className="flex items-center justify-center h-32"><Loader2 size={24} className="animate-spin text-blue-600" /></div>;

  return (
    <div data-testid="overrides-tab" className="space-y-4">
      <div className="bg-blue-50 border border-blue-200 rounded p-3 text-sm text-blue-900">
        <strong>Override de acciones existentes.</strong> Renombra el botón, desactívalo o restringe qué usuarios pueden ejecutarlo. La lógica de la acción (cambio de estado, generación de PDFs, archivos) NO se altera.
      </div>
      {businessTypes.map((biz) => (
        <BusinessOverridesBlock
          key={biz.id}
          biz={biz}
          subCategories={subCategories}
          actions={actions}
          allowedMap={allowedMap}
          overrides={overrides}
          users={users}
          onChanged={load}
        />
      ))}
    </div>
  );
}

function BusinessOverridesBlock({ biz, subCategories, actions, allowedMap, overrides, users = [], onChanged }) {
  const [expanded, setExpanded] = useState(false);
  // Filtro PyME/Corp + orden alfabético de Usuarios Autorizados según la unidad
  // de negocio (impide asignación cruzada: PyME→PYME, Corp→CORP).
  const bizUsers = useMemo(() => usersForBiz(users, biz.id), [users, biz.id]);
  // Iter50: drill-down. Cuando el negocio se expande sólo se ven los nombres
  // de subcategorías; al hacer click sobre una subcategoría se cargan sus
  // acciones para edición. Evita renderizar masivamente toda la matriz.
  const [activeSubId, setActiveSubId] = useState(null);
  const subs = biz.has_sub ? subCategories.filter((s) => (allowedMap[`${biz.id}|${s.id}`] || []).length) : [{ id: null, label: '' }];

  return (
    <div className="border border-slate-200 rounded bg-white">
      <button
        onClick={() => { setExpanded((v) => !v); setActiveSubId(null); }}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-slate-50"
        data-testid={`ov-biz-toggle-${biz.id}`}
      >
        <span className="font-medium text-slate-800">{biz.label}</span>
        {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
      </button>
      {expanded && (
        <div className="p-3 border-t border-slate-100 space-y-2">
          {/* Caso sin subcategorías: mostrar acciones directamente */}
          {!biz.has_sub ? (
            <div className="space-y-1.5">
              {(allowedMap[`${biz.id}|_`] || []).map((aid) => {
                const action = actions.find((a) => a.id === aid);
                if (!action) return null;
                const key = `${biz.id}|_|${aid}`;
                return (
                  <OverrideRow
                    key={key}
                    action={action}
                    configKey={key}
                    bizId={biz.id}
                    subId={null}
                    override={overrides[key]}
                    users={bizUsers}
                    onChanged={onChanged}
                  />
                );
              })}
            </div>
          ) : (
            <>
              {/* Lista de subcategorías como tabs/pills */}
              <div className="flex flex-wrap gap-2 pb-2 border-b border-slate-100" data-testid={`ov-sub-list-${biz.id}`}>
                {subs.map((sub) => {
                  const isActive = activeSubId === sub.id;
                  return (
                    <button
                      key={sub.id || 'none'}
                      type="button"
                      onClick={() => setActiveSubId(isActive ? null : sub.id)}
                      className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                        isActive
                          ? 'bg-blue-600 text-white shadow-sm'
                          : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                      }`}
                      data-testid={`ov-sub-toggle-${biz.id}-${sub.id || 'none'}`}
                    >
                      {sub.label || '(sin subcategoría)'}
                    </button>
                  );
                })}
              </div>
              {/* Acciones — sólo de la subcategoría seleccionada */}
              {activeSubId === null ? (
                <p className="text-xs text-slate-400 italic py-3">
                  Selecciona una subcategoría arriba para ver sus acciones.
                </p>
              ) : (
                <div className="space-y-1.5 pt-2">
                  {(allowedMap[`${biz.id}|${activeSubId}`] || []).map((aid) => {
                    const action = actions.find((a) => a.id === aid);
                    if (!action) return null;
                    const key = `${biz.id}|${activeSubId}|${aid}`;
                    return (
                      <OverrideRow
                        key={key}
                        action={action}
                        configKey={key}
                        bizId={biz.id}
                        subId={activeSubId}
                        override={overrides[key]}
                        users={bizUsers}
                        onChanged={onChanged}
                      />
                    );
                  })}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function OverrideRow({ action, configKey, bizId, subId, override, users = [], onChanged }) {
  const [editing, setEditing] = useState(false);
  const [label, setLabel] = useState(override?.custom_label || '');
  const [enabled, setEnabled] = useState(override?.enabled !== false);
  const [allowedUserIds, setAllowedUserIds] = useState(override?.allowed_user_ids || []);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setLabel(override?.custom_label || '');
    setEnabled(override?.enabled !== false);
    setAllowedUserIds(override?.allowed_user_ids || []);
  }, [override]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put('/quote-action-overrides', {
        business_type: bizId,
        product_subcategory: subId || null,
        action_id: action.id,
        custom_label: label.trim() || null,
        enabled,
        required_roles: [],
        required_cargos: [],
        allowed_user_ids: allowedUserIds,
      });
      toast.success('Override guardado');
      setEditing(false);
      onChanged?.();
    } catch (e) {
      toast.error(`Error: ${e.response?.data?.detail || e.message}`);
    } finally { setSaving(false); }
  };
  const handleReset = async () => {
    if (!override) return;
    setSaving(true);
    try {
      await api.delete(`/quote-action-overrides/${encodeURIComponent(configKey)}`);
      toast.success('Override eliminado');
      onChanged?.();
    } catch (e) {
      toast.error(`Error: ${e.response?.data?.detail || e.message}`);
    } finally { setSaving(false); }
  };

  const allowedUsersLabel = (override?.allowed_user_ids || [])
    .map((uid) => users.find((u) => u.user_id === uid)?.label)
    .filter(Boolean);

  if (!editing) {
    return (
      <div className="flex items-center justify-between gap-2 p-2 bg-slate-50 rounded border border-slate-200">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <span className={`text-sm ${enabled ? '' : 'line-through text-slate-400'}`}>{label || action.label}</span>
          {label && <Badge variant="secondary" className="text-[10px]">renombrado</Badge>}
          {!enabled && <Badge variant="secondary" className="bg-red-100 text-red-700 text-[10px]">desactivado</Badge>}
          {allowedUsersLabel.length > 0 && (
            <Badge variant="secondary" className="bg-amber-100 text-amber-800 text-[10px]" title={allowedUsersLabel.join(', ')}>
              {allowedUsersLabel.length} usuario{allowedUsersLabel.length !== 1 ? 's' : ''}
            </Badge>
          )}
        </div>
        <Button variant="ghost" size="sm" onClick={() => setEditing(true)} data-testid={`override-edit-${action.id}`}>
          <Edit2 size={14} />
        </Button>
        {override && <Button variant="ghost" size="sm" onClick={handleReset} className="text-red-500" title="Eliminar override"><Trash2 size={14} /></Button>}
      </div>
    );
  }

  return (
    <div className="p-2 bg-blue-50 rounded border border-blue-300 space-y-2">
      <div className="text-xs text-slate-600">Acción original: <strong>{action.label}</strong> ({action.id})</div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        <div>
          <label className="text-[11px] text-slate-600">Nuevo label (vacío = original)</label>
          <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder={action.label} className="h-8" />
        </div>
        <div>
          <label className="text-[11px] text-slate-600">Usuarios autorizados (vacío = todos)</label>
          <UserMultiSelect users={users} selected={allowedUserIds} onChange={setAllowedUserIds} testid={`override-users-${action.id}`} />
        </div>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <Checkbox checked={enabled} onCheckedChange={(v) => setEnabled(!!v)} />
        Acción activa (visible en el menú)
      </label>
      <div className="flex gap-2">
        <Button size="sm" onClick={handleSave} disabled={saving} data-testid={`override-save-${action.id}`}>
          {saving ? <Loader2 size={14} className="animate-spin mr-1" /> : <Save size={14} className="mr-1" />}
          Guardar
        </Button>
        <Button size="sm" variant="outline" onClick={() => setEditing(false)}>Cancelar</Button>
      </div>
    </div>
  );
}

// ============================================================================
// FASE A — Acciones Personalizadas (nuevas, sin cambio de estado)
// ============================================================================
function CustomActionsTab({ actions, businessTypes, subCategories, users = [] }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get('/quote-custom-actions');
      setItems(res.data?.items || []);
    } catch (e) {
      toast.error(`Error: ${e.response?.data?.detail || e.message}`);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const openNew = () => { setEditing(null); setDialogOpen(true); };
  const openEdit = (item) => { setEditing(item); setDialogOpen(true); };
  const handleDelete = async (item) => {
    if (!window.confirm(`¿Eliminar acción "${item.label}"?`)) return;
    try {
      await api.delete(`/quote-custom-actions/${encodeURIComponent(item.config_key)}`);
      toast.success('Acción eliminada');
      load();
    } catch (e) { toast.error(`Error: ${e.response?.data?.detail || e.message}`); }
  };

  if (loading) return <div className="flex items-center justify-center h-32"><Loader2 size={24} className="animate-spin text-blue-600" /></div>;

  return (
    <div data-testid="custom-actions-tab" className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div className="bg-violet-50 border border-violet-200 rounded p-3 text-sm text-violet-900 flex-1">
          <strong>Acciones personalizadas.</strong> Crea botones nuevos en el menú de cotizaciones. NO cambian el estado de la cotización; solo envían correos según la configuración del Motor de Notificaciones.
        </div>
        <Button onClick={openNew} className="bg-violet-600 hover:bg-violet-700 text-white flex-shrink-0" data-testid="new-custom-action-btn">
          <Plus size={14} className="mr-1" /> Nueva Acción
        </Button>
      </div>

      {items.length === 0 ? (
        <div className="text-center py-12 text-slate-400 text-sm">Sin acciones personalizadas. Crea la primera con el botón superior.</div>
      ) : (
        <div className="border border-slate-200 rounded overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-slate-600">Label</th>
                <th className="px-3 py-2 text-left font-medium text-slate-600">Tipo · Sub</th>
                <th className="px-3 py-2 text-left font-medium text-slate-600">Posición</th>
                <th className="px-3 py-2 text-left font-medium text-slate-600">Usuarios</th>
                <th className="px-3 py-2 text-center font-medium text-slate-600">Activa</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr key={it.config_key} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-3 py-2"><strong>{it.label}</strong> <code className="text-[10px] bg-slate-100 px-1 rounded ml-1">{it.action_id}</code></td>
                  <td className="px-3 py-2 text-xs text-slate-600">{(businessTypes.find((b) => b.id === it.business_type) || {}).label || it.business_type}{it.product_subcategory ? ` · ${it.product_subcategory}` : ''}</td>
                  <td className="px-3 py-2 text-xs">{it.position_after ? `después de ${actions.find((a) => a.id === it.position_after)?.label || it.position_after}` : 'al final'}</td>
                  <td className="px-3 py-2 text-xs text-slate-600">
                    {(() => {
                      const ids = it.allowed_user_ids || [];
                      if (!ids.length) return 'Todos';
                      const names = ids.map((uid) => users.find((u) => u.user_id === uid)?.label).filter(Boolean);
                      return names.length <= 2 ? names.join(', ') : `${names.slice(0, 2).join(', ')} +${names.length - 2}`;
                    })()}
                  </td>
                  <td className="px-3 py-2 text-center">{it.enabled ? <Eye size={14} className="inline text-emerald-500" /> : <EyeOff size={14} className="inline text-slate-400" />}</td>
                  <td className="px-3 py-2 text-right">
                    <Button variant="ghost" size="sm" onClick={() => openEdit(it)}><Edit2 size={14} /></Button>
                    <Button variant="ghost" size="sm" onClick={() => handleDelete(it)} className="text-red-500"><Trash2 size={14} /></Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <CustomActionDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        editing={editing}
        actions={actions}
        businessTypes={businessTypes}
        subCategories={subCategories}
        users={users}
        onSaved={() => { setDialogOpen(false); load(); }}
      />
    </div>
  );
}

function CustomActionDialog({ open, onOpenChange, editing, actions, businessTypes, subCategories, users = [], onSaved }) {
  const [form, setForm] = useState({
    action_id: '', business_type: 'implementacion_pyme', product_subcategory: null,
    label: '', position_after: '', enabled: true,
    allowed_user_ids: [], icon: 'Mail', color: 'blue', description: '',
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (editing) {
      setForm({
        action_id: editing.action_id, business_type: editing.business_type,
        product_subcategory: editing.product_subcategory || null,
        label: editing.label, position_after: editing.position_after || '',
        enabled: editing.enabled !== false,
        allowed_user_ids: editing.allowed_user_ids || [],
        icon: editing.icon || 'Mail', color: editing.color || 'blue',
        description: editing.description || '',
      });
    } else if (open) {
      setForm({
        action_id: '', business_type: 'implementacion_pyme', product_subcategory: null,
        label: '', position_after: '', enabled: true,
        allowed_user_ids: [], icon: 'Mail', color: 'blue', description: '',
      });
    }
  }, [editing, open]);

  const handleSave = async () => {
    if (!form.action_id || !form.label) { toast.error('action_id y label son obligatorios'); return; }
    setSaving(true);
    try {
      await api.put('/quote-custom-actions', {
        action_id: form.action_id.trim().toLowerCase(),
        business_type: form.business_type,
        product_subcategory: form.product_subcategory || null,
        label: form.label.trim(),
        position_after: form.position_after || null,
        enabled: form.enabled,
        required_roles: [],
        required_cargos: [],
        allowed_user_ids: form.allowed_user_ids || [],
        icon: form.icon || null, color: form.color || null,
        description: form.description || null,
      });
      toast.success('Acción guardada');
      onSaved?.();
    } catch (e) {
      toast.error(`Error: ${e.response?.data?.detail || e.message}`);
    } finally { setSaving(false); }
  };

  if (!open) return null;
  const biz = businessTypes.find((b) => b.id === form.business_type);
  const subs = biz?.has_sub ? subCategories : [];

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-2xl">
        <AlertDialogHeader>
          <AlertDialogTitle>{editing ? 'Editar' : 'Nueva'} Acción Personalizada</AlertDialogTitle>
          <AlertDialogDescription>
            Esta acción aparecerá en el menú de cotizaciones del tipo seleccionado. Solo envía correos; no cambia el estado de la cotización.
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div className="space-y-3 py-2">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-600">ID técnico * (a-z, 0-9, _)</label>
              <Input value={form.action_id} onChange={(e) => setForm((f) => ({ ...f, action_id: e.target.value }))} disabled={!!editing} placeholder="pago_recibido" className="font-mono text-sm" />
            </div>
            <div>
              <label className="text-xs text-slate-600">Texto del botón *</label>
              <Input value={form.label} onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))} placeholder="Pago Recibido" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-600">Tipo de negocio *</label>
              <Select value={form.business_type} onValueChange={(v) => setForm((f) => ({ ...f, business_type: v, product_subcategory: null }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {businessTypes.map((b) => <SelectItem key={b.id} value={b.id}>{b.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs text-slate-600">Subcategoría {biz?.has_sub ? '*' : '(no aplica)'}</label>
              <Select disabled={!biz?.has_sub} value={form.product_subcategory || 'none'} onValueChange={(v) => setForm((f) => ({ ...f, product_subcategory: v === 'none' ? null : v }))}>
                <SelectTrigger><SelectValue placeholder="Todas" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Todas las subcategorías</SelectItem>
                  {subs.map((s) => <SelectItem key={s.id} value={s.id}>{s.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-600">Posición en menú</label>
              <Select value={form.position_after || 'end'} onValueChange={(v) => setForm((f) => ({ ...f, position_after: v === 'end' ? '' : v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="end">Al final</SelectItem>
                  {actions.map((a) => <SelectItem key={a.id} value={a.id}>Después de "{a.label}"</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs text-slate-600">Usuarios autorizados (vacío = todos)</label>
              <UserMultiSelect users={users} selected={form.allowed_user_ids} onChange={(ids) => setForm((f) => ({ ...f, allowed_user_ids: ids }))} testid="custom-action-users" />
            </div>
          </div>

          <div>
            <label className="text-xs text-slate-600">Descripción (opcional)</label>
            <Input value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} placeholder="Cuándo usar esta acción" />
          </div>

          <label className="flex items-center gap-2 text-sm">
            <Checkbox checked={form.enabled} onCheckedChange={(v) => setForm((f) => ({ ...f, enabled: !!v }))} />
            Acción activa
          </label>

          <div className="bg-amber-50 border border-amber-200 rounded p-2 text-xs text-amber-900">
            Recuerda configurar los <strong>destinatarios y plantillas</strong> de esta acción en la pestaña <strong>Matriz</strong> luego de crearla. Sin destinatarios, el botón aparecerá pero no enviará correos.
          </div>
        </div>

        <AlertDialogFooter>
          <AlertDialogCancel disabled={saving}>Cancelar</AlertDialogCancel>
          <AlertDialogAction onClick={handleSave} disabled={saving} className="bg-violet-600 hover:bg-violet-700">
            {saving ? <Loader2 size={14} className="animate-spin mr-1" /> : <Save size={14} className="mr-1" />}
            {editing ? 'Guardar' : 'Crear'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}