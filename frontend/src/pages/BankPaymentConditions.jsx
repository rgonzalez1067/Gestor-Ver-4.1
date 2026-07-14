import { useState, useEffect, useCallback } from 'react';
import { Sidebar } from '../components/Sidebar';
import { Button } from '../components/ui/button';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { BookOpen, Save, Lock, Building2, CreditCard } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';
import { usePermission } from '../hooks/usePermission';

const MAX_LEN = 2000;

export default function BankPaymentConditions() {
  const { canEdit } = usePermission('condiciones_banco_mediopago');
  const [banks, setBanks] = useState([]);
  const [medios, setMedios] = useState([]);
  const [bankId, setBankId] = useState('');
  const [serviceId, setServiceId] = useState('');
  const [conditions, setConditions] = useState('');
  const [loadingText, setLoadingText] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [b, m] = await Promise.all([
          api.get('/banco-mediopago-condiciones/banks'),
          api.get('/banco-mediopago-condiciones/medios-pago'),
        ]);
        setBanks(b.data || []);
        setMedios(m.data || []);
      } catch (e) {
        toast.error('No se pudieron cargar los catálogos');
      }
    })();
  }, []);

  const loadCondition = useCallback(async (bk, sv) => {
    if (!bk || !sv) { setConditions(''); return; }
    setLoadingText(true);
    try {
      const res = await api.get('/banco-mediopago-condiciones/condicion', { params: { bank_id: bk, service_id: sv } });
      setConditions(res.data?.conditions || '');
    } catch (e) {
      setConditions('');
    } finally {
      setLoadingText(false);
    }
  }, []);

  useEffect(() => { loadCondition(bankId, serviceId); }, [bankId, serviceId, loadCondition]);

  const handleSave = async () => {
    if (!bankId || !serviceId) { toast.error('Seleccione Banco y Medio de Pago'); return; }
    setSaving(true);
    try {
      await api.post('/banco-mediopago-condiciones/condicion', {
        bank_id: bankId, service_id: serviceId, conditions,
      });
      toast.success('Condiciones guardadas');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error al guardar');
    } finally {
      setSaving(false);
    }
  };

  const binomioReady = bankId && serviceId;
  const remaining = MAX_LEN - conditions.length;

  return (
    <div className="flex min-h-screen bg-white">
      <Sidebar />
      <main className="flex-1 p-8" data-testid="bank-payment-conditions-page">
        <div className="max-w-3xl">
          <div className="flex items-center gap-3 mb-1">
            <div className="w-10 h-10 rounded-lg bg-indigo-600 text-white flex items-center justify-center">
              <BookOpen size={20} />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-800">Condiciones Banco/Medio de Pago</h1>
              <p className="text-sm text-slate-500">Biblioteca de tips, restricciones y especificaciones para implementadores.</p>
            </div>
          </div>

          {!canEdit && (
            <div className="mt-4 flex items-center gap-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2" data-testid="bpc-readonly-banner">
              <Lock size={15} /> Modo solo consulta: no tienes permisos de edición.
            </div>
          )}

          <div className="mt-6 bg-slate-50 border border-slate-200 rounded-xl p-6 space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label className="text-sm font-medium text-slate-700 mb-1 flex items-center gap-1.5">
                  <Building2 size={15} className="text-indigo-600" /> Banco (Entidad Adquirente)
                </Label>
                <Select value={bankId} onValueChange={setBankId}>
                  <SelectTrigger className="bg-white" data-testid="bpc-bank-select">
                    <SelectValue placeholder="Seleccione un banco" />
                  </SelectTrigger>
                  <SelectContent>
                    {banks.map((b) => (
                      <SelectItem key={b.bank_id} value={b.bank_id} data-testid={`bpc-bank-option-${b.bank_id}`}>{b.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-sm font-medium text-slate-700 mb-1 flex items-center gap-1.5">
                  <CreditCard size={15} className="text-indigo-600" /> Medio de Pago (Setup)
                </Label>
                <Select value={serviceId} onValueChange={setServiceId}>
                  <SelectTrigger className="bg-white" data-testid="bpc-medio-select">
                    <SelectValue placeholder="Seleccione un medio de pago" />
                  </SelectTrigger>
                  <SelectContent>
                    {medios.map((s) => (
                      <SelectItem key={s.service_id} value={s.service_id} data-testid={`bpc-medio-option-${s.service_id}`}>{s.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <Label className="text-sm font-medium text-slate-700">Condiciones / Tips técnicos</Label>
                <span className={`text-xs ${remaining <= 0 ? 'text-red-500 font-semibold' : 'text-slate-400'}`} data-testid="bpc-char-counter">
                  {conditions.length} / {MAX_LEN}
                </span>
              </div>
              <Textarea
                value={conditions}
                onChange={(e) => setConditions(e.target.value.slice(0, MAX_LEN))}
                maxLength={MAX_LEN}
                disabled={!canEdit || !binomioReady || loadingText}
                rows={10}
                placeholder={binomioReady ? 'Escriba las condiciones técnicas, parámetros particulares o tips de compatibilidad de este binomio Banco + Medio de Pago…' : 'Seleccione Banco y Medio de Pago para ver/editar sus condiciones'}
                className="bg-white resize-y"
                data-testid="bpc-conditions-textarea"
              />
            </div>

            {canEdit && (
              <div className="flex justify-end">
                <Button
                  onClick={handleSave}
                  disabled={!binomioReady || saving}
                  className="bg-indigo-600 hover:bg-indigo-700 text-white"
                  data-testid="bpc-save-btn"
                >
                  <Save size={16} className="mr-2" /> {saving ? 'Guardando…' : 'Guardar condiciones'}
                </Button>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
