import { useState, useEffect, useCallback } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import { ArrowLeft, Save, Plus, Trash2, Mail, AtSign, Info } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import { usePermission } from '../hooks/usePermission';

const DEFAULT_VALUE = '__default__';

export const EmailSendersConfig = () => {
  const navigate = useNavigate();
  const { user: currentUser } = usePermission('configuracion');
  const isAdmin = currentUser?.role === 'admin';

  const [senders, setSenders] = useState([]);
  const [assignments, setAssignments] = useState({});
  const [areas, setAreas] = useState([]);
  const [defaultSender, setDefaultSender] = useState('');
  const [allowedDomain, setAllowedDomain] = useState('');
  const [updatedAt, setUpdatedAt] = useState(null);
  const [updatedBy, setUpdatedBy] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/config/email-senders');
      setSenders((data.senders || []).map(s => ({ ...s })));
      setAssignments(data.assignments || {});
      setAreas(data.areas || []);
      setDefaultSender(data.default_sender || '');
      setAllowedDomain(data.allowed_domain || '');
      setUpdatedAt(data.updated_at || null);
      setUpdatedBy(data.updated_by || null);
    } catch (e) {
      toast.error('No se pudo cargar la configuración de remitentes');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const addSender = () => setSenders(prev => [...prev, { id: `tmp_${Date.now()}`, label: '', email: '', active: true }]);
  const updateSender = (idx, field, value) => setSenders(prev => prev.map((s, i) => i === idx ? { ...s, [field]: value } : s));
  const removeSender = (idx) => {
    const removed = senders[idx];
    setSenders(prev => prev.filter((_, i) => i !== idx));
    // Limpiar asignaciones que apuntaban a este correo
    if (removed?.email) {
      setAssignments(prev => {
        const next = { ...prev };
        Object.keys(next).forEach(k => { if ((next[k] || '').toLowerCase() === removed.email.toLowerCase()) delete next[k]; });
        return next;
      });
    }
  };

  const setAssignment = (areaKey, value) => {
    setAssignments(prev => {
      const next = { ...prev };
      if (value === DEFAULT_VALUE) delete next[areaKey];
      else next[areaKey] = value;
      return next;
    });
  };

  const activeSenders = senders.filter(s => s.active && s.email && s.email.includes('@'));

  const handleSave = async () => {
    if (!isAdmin) { toast.error('Solo administradores pueden configurar los remitentes'); return; }
    // Validación de dominio en cliente
    for (const s of senders) {
      const email = (s.email || '').trim().toLowerCase();
      if (!email || !email.includes('@')) { toast.error(`Correo inválido: "${s.email || '(vacío)'}"`); return; }
      if (allowedDomain && !email.endsWith('@' + allowedDomain)) {
        toast.error(`Solo se permiten correos del dominio @${allowedDomain}`); return;
      }
    }
    setSaving(true);
    try {
      const payload = {
        senders: senders.map(s => ({ id: s.id?.startsWith('tmp_') ? null : s.id, label: s.label, email: s.email, active: !!s.active })),
        assignments,
      };
      const { data } = await api.put('/config/email-senders', payload);
      setSenders((data.senders || []).map(s => ({ ...s })));
      setAssignments(data.assignments || {});
      setUpdatedAt(data.updated_at);
      setUpdatedBy(data.updated_by);
      toast.success('Remitentes actualizados correctamente');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error al guardar los remitentes');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto p-6 lg:p-8">
          <div className="flex items-center gap-3 mb-6">
            <Button variant="ghost" size="sm" onClick={() => navigate('/settings')} data-testid="senders-back-btn">
              <ArrowLeft size={18} className="mr-1" />Configuración
            </Button>
          </div>

          <div className="mb-6">
            <h1 className="text-3xl font-bold text-slate-900 font-manrope" data-testid="senders-page-title">
              Remitentes de Correo
            </h1>
            <p className="text-slate-600 mt-1 text-sm">
              Define varias direcciones remitentes y asígnalas automáticamente por área.
              Cada área (Proyectos, Integradores, Cotizaciones, Comunicaciones a Clientes, Contactos Iniciales,
              Nuevos Productos e Inventarios) puede salir desde la dirección que indiques aquí;
              si no asignas ninguna, usa el remitente institucional por defecto.
            </p>
            {updatedAt && (
              <p className="text-xs text-slate-500 mt-2" data-testid="senders-last-updated">
                Última actualización: <span className="font-medium text-slate-700">{new Date(updatedAt).toLocaleString('es-VE')}</span>
                {updatedBy ? <> · por <span className="font-medium text-slate-700">{updatedBy}</span></> : null}
              </p>
            )}
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-6 flex items-start gap-2 text-xs text-blue-800">
            <Info size={16} className="shrink-0 mt-0.5" />
            <span>
              Por seguridad (SPF / anti-spoofing), todas las direcciones deben pertenecer al dominio institucional
              <strong> @{allowedDomain || 'megasoft.com.ve'}</strong>. Remitente por defecto del sistema: <strong>{defaultSender}</strong>.
            </span>
          </div>

          {loading ? (
            <p className="text-slate-500 text-sm">Cargando…</p>
          ) : (
            <div className="space-y-6">
              {/* Lista de remitentes */}
              <div className="bg-white rounded-lg border border-slate-200 overflow-hidden" data-testid="senders-list-panel">
                <div className="px-5 py-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Mail size={16} className="text-slate-500" />
                    <h2 className="text-sm font-semibold text-slate-800 uppercase tracking-wide">Direcciones Remitentes</h2>
                  </div>
                  {isAdmin && (
                    <Button size="sm" variant="outline" onClick={addSender} data-testid="add-sender-btn">
                      <Plus size={14} className="mr-1" />Agregar
                    </Button>
                  )}
                </div>
                <div className="p-4 space-y-3">
                  {senders.length === 0 && (
                    <p className="text-sm text-slate-400 text-center py-4">
                      No hay remitentes configurados. Se usa el institucional por defecto ({defaultSender}).
                    </p>
                  )}
                  {senders.map((s, idx) => (
                    <div key={s.id || idx} className="flex items-center gap-3 bg-slate-50 rounded-lg p-3 border border-slate-200" data-testid={`sender-row-${idx}`}>
                      <div className="flex-1 grid grid-cols-1 sm:grid-cols-2 gap-2">
                        <div>
                          <Label className="text-[10px] text-slate-400 uppercase">Nombre / Etiqueta</Label>
                          <Input value={s.label || ''} disabled={!isAdmin} placeholder="Ej. Implementación"
                            onChange={(e) => updateSender(idx, 'label', e.target.value)}
                            className="h-9 text-sm" data-testid={`sender-label-${idx}`} />
                        </div>
                        <div>
                          <Label className="text-[10px] text-slate-400 uppercase">Correo</Label>
                          <div className="relative">
                            <AtSign size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                            <Input value={s.email || ''} disabled={!isAdmin} placeholder={`cuenta@${allowedDomain || 'megasoft.com.ve'}`}
                              onChange={(e) => updateSender(idx, 'email', e.target.value)}
                              className="h-9 text-sm pl-8" data-testid={`sender-email-${idx}`} />
                          </div>
                        </div>
                      </div>
                      <div className="flex flex-col items-center gap-1">
                        <Label className="text-[10px] text-slate-400 uppercase">Activo</Label>
                        <Switch checked={!!s.active} disabled={!isAdmin}
                          onCheckedChange={(v) => updateSender(idx, 'active', v)}
                          data-testid={`sender-active-${idx}`} />
                      </div>
                      {isAdmin && (
                        <Button variant="ghost" size="sm" className="h-9 w-9 p-0 text-slate-400 hover:text-red-600"
                          onClick={() => removeSender(idx)} data-testid={`sender-remove-${idx}`}>
                          <Trash2 size={16} />
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Asignación por área */}
              <div className="bg-white rounded-lg border border-slate-200 overflow-hidden" data-testid="senders-assignments-panel">
                <div className="px-5 py-4 border-b border-slate-200 bg-slate-50">
                  <h2 className="text-sm font-semibold text-slate-800 uppercase tracking-wide">Asignación Automática por Área</h2>
                  <p className="text-xs text-slate-500 mt-0.5">Selecciona desde qué dirección saldrán los correos de cada área.</p>
                </div>
                <div className="p-4 space-y-3">
                  {areas.map((area) => (
                    <div key={area.key} className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4" data-testid={`area-row-${area.key}`}>
                      <div className="sm:w-1/2">
                        <p className="text-sm font-medium text-slate-700">{area.label}</p>
                      </div>
                      <div className="sm:w-1/2">
                        <Select value={assignments[area.key] || DEFAULT_VALUE} disabled={!isAdmin}
                          onValueChange={(v) => setAssignment(area.key, v)}>
                          <SelectTrigger className="h-9 text-sm" data-testid={`area-select-${area.key}`}>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value={DEFAULT_VALUE}>Institucional por defecto ({defaultSender})</SelectItem>
                            {activeSenders.map((s) => (
                              <SelectItem key={s.email} value={s.email}>{s.label || s.email} — {s.email}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {isAdmin && (
                <div className="flex justify-end">
                  <Button onClick={handleSave} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="save-senders-btn">
                    <Save size={16} className="mr-1.5" />{saving ? 'Guardando…' : 'Guardar Cambios'}
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default EmailSendersConfig;
