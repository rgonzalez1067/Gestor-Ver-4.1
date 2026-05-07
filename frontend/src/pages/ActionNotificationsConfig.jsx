import { useState, useEffect, useMemo } from 'react';
import { ChevronRight, ChevronDown, Plus, Trash2, Save, ShieldCheck, Loader2, AlertCircle, Sparkles, Activity, RefreshCw } from 'lucide-react';
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
        <Select value={row.type} onValueChange={(v) => update({ type: v, user_id: v === 'client_field' ? null : row.user_id })}>
          <SelectTrigger className="h-9 w-44" data-testid={`row-type-${row.row_id}`}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="client_field">📧 Correo del Cliente</SelectItem>
            <SelectItem value="user">👤 Usuario interno</SelectItem>
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
          <span className="text-sm text-slate-500 italic">— se resuelve al ejecutar la acción —</span>
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
      { row_id: `row_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`, type: 'client_field', user_id: null, template_id: null, send_pdf_attachments: true },
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
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr><td colSpan="5" className="px-3 py-6 text-center text-slate-400 text-sm italic">Sin destinatarios configurados. La acción usará el comportamiento por defecto.</td></tr>
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
  const subs = business.has_sub ? subCategories : [null];

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

export default function ActionNotificationsConfig() {
  const [loading, setLoading] = useState(true);
  const [catalog, setCatalog] = useState(null);
  const [configs, setConfigs] = useState({});
  const [tab, setTab] = useState('matrix'); // matrix | audit
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
      return new Date(iso).toLocaleString('es-VE', { dateStyle: 'short', timeStyle: 'short' });
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
