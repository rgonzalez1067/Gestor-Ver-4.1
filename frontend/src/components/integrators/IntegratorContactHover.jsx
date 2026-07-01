import { useState, useCallback } from 'react';
import { HoverCard, HoverCardContent, HoverCardTrigger } from '../ui/hover-card';
import { User, Phone, Mail, Handshake, Store, FileText, Loader2 } from 'lucide-react';
import api from '../../utils/api';
import { toast } from 'sonner';

// Tooltip de Contacto Principal del integrador + subventana "Clientes Instalados".
// Los datos de contacto son locales (Strategy B); los clientes instalados se
// consultan bajo demanda al abrir el popover (Strategy A) y se pueden exportar a PDF.
export const IntegratorContactHover = ({ integrator, children }) => {
  const name = integrator?.principal_contact_name;
  const phone = integrator?.principal_contact_phone;
  const email = integrator?.principal_contact_email;
  const neg = integrator?.interface_negotiation;
  const hasData = name || phone || email || neg;
  const intId = integrator?.integrator_id;

  const [clients, setClients] = useState(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);

  const fetchClients = useCallback(async (open) => {
    if (!open || !intId || clients || loading) return;
    setLoading(true);
    try {
      const { data } = await api.get(`/integrators/${intId}/installed-clients`);
      setClients(data.clients || []);
    } catch {
      setClients([]);
    } finally {
      setLoading(false);
    }
  }, [intId, clients, loading]);

  const exportPdf = async (e) => {
    e.stopPropagation();
    setExporting(true);
    try {
      const { data } = await api.get(`/integrators/${intId}/installed-clients/pdf`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `clientes_instalados_${(integrator?.name || 'integrador').replace(/[^a-z0-9]+/gi, '_')}.pdf`;
      document.body.appendChild(a); a.click(); a.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      toast.error('No se pudo exportar el PDF de clientes instalados');
    } finally {
      setExporting(false);
    }
  };

  const Row = ({ icon: Icon, label, value, accent }) => (
    <div className="flex items-start gap-2 py-0.5">
      <Icon size={13} className={`mt-0.5 shrink-0 ${accent}`} />
      <div className="min-w-0">
        <span className="text-[10px] uppercase tracking-wide text-slate-400">{label}</span>
        <p className="text-xs text-slate-800 break-words leading-tight">{value || '—'}</p>
      </div>
    </div>
  );

  return (
    <HoverCard openDelay={250} closeDelay={120} onOpenChange={fetchClients}>
      <HoverCardTrigger asChild>{children}</HoverCardTrigger>
      <HoverCardContent align="start" className="w-72 p-0 overflow-hidden" data-testid={`integrator-contact-popover-${intId}`}>
        <div className="bg-gradient-to-r from-fuchsia-600 to-purple-600 px-3 py-2">
          <p className="text-[10px] font-medium text-fuchsia-100 uppercase tracking-wide">Contacto Principal</p>
          <p className="text-sm font-semibold text-white truncate">{integrator?.name}</p>
          <p className="text-[10px] text-fuchsia-100 truncate">Aplicación: {integrator?.app_name || '—'}</p>
        </div>
        <div className="p-3">
          {!hasData ? (
            <p className="text-xs text-slate-400 italic py-1" data-testid="integrator-contact-empty">Sin datos de contacto registrados.</p>
          ) : (
            <div className="space-y-0.5">
              <Row icon={User} label="Contacto" value={name} accent="text-fuchsia-500" />
              <Row icon={Phone} label="Teléfono" value={phone} accent="text-cyan-500" />
              <Row icon={Mail} label="Email" value={email} accent="text-blue-500" />
              <div className="flex items-center gap-2 pt-1 mt-1 border-t border-slate-100">
                <Handshake size={13} className="text-emerald-500 shrink-0" />
                <span className="text-[10px] uppercase tracking-wide text-slate-400">Negocia interfaz:</span>
                <span
                  className={`text-xs font-semibold ${neg === 'Sí' ? 'text-emerald-600' : neg === 'No' ? 'text-rose-600' : 'text-slate-400'}`}
                  data-testid={`integrator-contact-negotiation-${intId}`}
                >
                  {neg || '—'}
                </span>
              </div>
            </div>
          )}

          {/* Subventana: Clientes Instalados */}
          <div className="mt-2 pt-2 border-t border-slate-200" data-testid={`installed-clients-section-${intId}`}>
            <div className="flex items-center justify-between mb-1">
              <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
                <Store size={13} className="text-indigo-500" />
                Clientes Instalados
                {clients && <span className="ml-1 text-[10px] font-bold text-indigo-600 bg-indigo-50 rounded-full px-1.5">{clients.length}</span>}
              </span>
              <button
                onClick={exportPdf}
                disabled={exporting || !(clients && clients.length)}
                className="flex items-center gap-1 text-[10px] font-medium text-slate-600 hover:text-rose-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                data-testid={`installed-clients-export-${intId}`}
                title="Exportar Lista a PDF"
              >
                {exporting ? <Loader2 size={12} className="animate-spin" /> : <FileText size={12} className="text-rose-600" />}
                Exportar a PDF
              </button>
            </div>
            {loading ? (
              <div className="flex items-center gap-2 py-1.5 text-xs text-slate-400" data-testid="installed-clients-loading">
                <Loader2 size={12} className="animate-spin" /> Cargando…
              </div>
            ) : !clients ? (
              <p className="text-[11px] text-slate-400 italic py-1">Pase el cursor para cargar…</p>
            ) : clients.length === 0 ? (
              <p className="text-[11px] text-slate-400 italic py-1" data-testid="installed-clients-empty">Sin clientes instalados para esta aplicación.</p>
            ) : (
              <div className="max-h-32 overflow-y-auto rounded border border-slate-100 divide-y divide-slate-50">
                {clients.map((c, i) => (
                  <div key={i} className="px-2 py-1" data-testid={`installed-client-row-${i}`}>
                    <p className="text-xs font-medium text-slate-800 truncate">{c.fantasy_name || c.legal_name}</p>
                    <p className="text-[10px] text-slate-400 truncate">{c.rif} · {c.condicion || '—'}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </HoverCardContent>
    </HoverCard>
  );
};

export default IntegratorContactHover;
