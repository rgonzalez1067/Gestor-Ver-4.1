import { useState, useEffect, useCallback } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '../components/ui/alert-dialog';
import { ArrowLeft, CalendarDays, Plus, Trash2, Info, Repeat } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import { usePermission } from '../hooks/usePermission';

const fmtDate = (iso, recurring) => {
  if (!iso) return '';
  const [y, m, d] = iso.slice(0, 10).split('-');
  if (recurring) return `${d}/${m} (cada año)`;
  return `${d}/${m}/${y}`;
};

export const WorkCalendarConfig = () => {
  const navigate = useNavigate();
  const { user: currentUser } = usePermission('configuracion');
  const isAdmin = currentUser?.role === 'admin';

  const [holidays, setHolidays] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [newDate, setNewDate] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newRecurring, setNewRecurring] = useState(false);
  const [toDelete, setToDelete] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/calendar/holidays');
      setHolidays(Array.isArray(data) ? data : []);
    } catch (e) {
      toast.error('No se pudo cargar el calendario de días festivos');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSave = async () => {
    if (!newDate) { toast.error('Selecciona una fecha'); return; }
    if (!newDesc.trim()) { toast.error('La descripción es obligatoria'); return; }
    setSaving(true);
    try {
      await api.post('/calendar/holidays', {
        holiday_date: newDate,
        description: newDesc.trim(),
        recurring: newRecurring,
      });
      toast.success('Día festivo guardado');
      setNewDate(''); setNewDesc(''); setNewRecurring(false);
      load();
    } catch (e) {
      const msg = e?.response?.data?.detail || 'No se pudo guardar el día festivo';
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!toDelete) return;
    try {
      await api.delete(`/calendar/holidays/${toDelete.holiday_id}`);
      toast.success('Día festivo eliminado');
      setToDelete(null);
      load();
    } catch (e) {
      toast.error('No se pudo eliminar el día festivo');
      setToDelete(null);
    }
  };

  // Orden cronológico ascendente por fecha.
  const sorted = [...holidays].sort((a, b) => (a.holiday_date || '').localeCompare(b.holiday_date || ''));

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <div className="flex-1 p-8 max-w-5xl">
        <button
          onClick={() => navigate('/settings')}
          className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-800 mb-4"
          data-testid="back-to-settings-btn"
        >
          <ArrowLeft size={16} /> Volver a Configuración
        </button>

        <div className="flex items-center gap-3 mb-2">
          <div className="w-11 h-11 bg-indigo-600 rounded-lg flex items-center justify-center">
            <CalendarDays size={22} className="text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 font-manrope">Calendario Laboral</h1>
            <p className="text-sm text-slate-600">
              Días festivos no laborables. El seguimiento de proyectos y los SLAs cuentan
              <strong> solo días hábiles</strong>, descontando fines de semana y estos feriados.
            </p>
          </div>
        </div>

        {!isAdmin && (
          <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800 my-4" data-testid="readonly-notice">
            <Info size={16} className="mt-0.5 shrink-0" />
            Solo el Administrador puede agregar o eliminar días festivos. Estás en modo de solo lectura.
          </div>
        )}

        {/* Formulario de alta (solo Admin) */}
        {isAdmin && (
          <div className="bg-white rounded-lg border border-slate-200 p-5 my-5" data-testid="holiday-form">
            <h2 className="text-lg font-semibold text-slate-900 mb-3">Agregar día festivo</h2>
            <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
              <div className="md:col-span-3">
                <Label htmlFor="holiday-date" className="text-xs text-slate-600">Fecha</Label>
                <Input
                  id="holiday-date" type="date" value={newDate}
                  onChange={(e) => setNewDate(e.target.value)}
                  data-testid="holiday-date-input"
                />
              </div>
              <div className="md:col-span-5">
                <Label htmlFor="holiday-desc" className="text-xs text-slate-600">Descripción / Motivo</Label>
                <Input
                  id="holiday-desc" placeholder="Ej: Año Nuevo" maxLength={150} value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  data-testid="holiday-desc-input"
                />
              </div>
              <div className="md:col-span-2 flex items-center gap-2 pb-2">
                <Switch checked={newRecurring} onCheckedChange={setNewRecurring} data-testid="holiday-recurring-switch" id="holiday-recurring" />
                <Label htmlFor="holiday-recurring" className="text-xs text-slate-600 cursor-pointer flex items-center gap-1">
                  <Repeat size={13} /> Cada año
                </Label>
              </div>
              <div className="md:col-span-2">
                <Button onClick={handleSave} disabled={saving} className="w-full gap-1" data-testid="save-holiday-btn">
                  <Plus size={16} /> Guardar
                </Button>
              </div>
            </div>
            {newRecurring && (
              <p className="text-xs text-slate-500 mt-2">
                Recurrente: se aplicará el <strong>{newDate ? fmtDate(newDate, true) : 'día/mes'}</strong> de todos los años, sin recargar.
              </p>
            )}
          </div>
        )}

        {/* Grilla de festivos */}
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden" data-testid="holidays-table">
          <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-900">
              Días festivos registrados ({sorted.length})
            </h2>
          </div>
          {loading ? (
            <div className="p-8 text-center text-slate-400 text-sm">Cargando...</div>
          ) : sorted.length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-sm" data-testid="holidays-empty">
              No hay días festivos registrados todavía.
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-slate-600 text-xs uppercase">
                  <th className="px-5 py-2.5 text-left font-medium">Fecha</th>
                  <th className="px-5 py-2.5 text-left font-medium">Descripción / Motivo</th>
                  <th className="px-5 py-2.5 text-left font-medium">Tipo</th>
                  {isAdmin && <th className="px-5 py-2.5 text-center font-medium">Acciones</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {sorted.map((h) => (
                  <tr key={h.holiday_id} className="hover:bg-slate-50" data-testid={`holiday-row-${h.holiday_id}`}>
                    <td className="px-5 py-3 font-mono text-slate-800">{fmtDate(h.holiday_date, h.recurring)}</td>
                    <td className="px-5 py-3 text-slate-700">{h.description}</td>
                    <td className="px-5 py-3">
                      {h.recurring ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-indigo-100 text-indigo-700">
                          <Repeat size={11} /> Recurrente
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs bg-slate-100 text-slate-600">Único</span>
                      )}
                    </td>
                    {isAdmin && (
                      <td className="px-5 py-3 text-center">
                        <Button
                          variant="ghost" size="sm"
                          className="text-red-500 hover:text-red-700 hover:bg-red-50"
                          onClick={() => setToDelete(h)}
                          data-testid={`delete-holiday-${h.holiday_id}`}
                        >
                          <Trash2 size={15} />
                        </Button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <AlertDialog open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)}>
        <AlertDialogContent data-testid="delete-holiday-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Eliminar día festivo</AlertDialogTitle>
            <AlertDialogDescription>
              ¿Eliminar <strong>{toDelete?.description}</strong> ({fmtDate(toDelete?.holiday_date, toDelete?.recurring)})?
              Los proyectos en curso recalcularán sus tiempos hábiles de inmediato, reincorporando ese día como hábil.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="delete-holiday-cancel">Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-red-600 hover:bg-red-700" data-testid="delete-holiday-confirm">
              Eliminar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default WorkCalendarConfig;
