import { HoverCard, HoverCardContent, HoverCardTrigger } from '../ui/hover-card';
import { User, Phone, Mail, Handshake } from 'lucide-react';

// Tooltip de Contacto Principal del integrador. Datos locales (vienen en la grilla),
// se renderiza al instante al pasar el cursor sobre el nombre.
export const IntegratorContactHover = ({ integrator, children }) => {
  const name = integrator?.principal_contact_name;
  const phone = integrator?.principal_contact_phone;
  const email = integrator?.principal_contact_email;
  const neg = integrator?.interface_negotiation;
  const hasData = name || phone || email || neg;

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
    <HoverCard openDelay={250} closeDelay={80}>
      <HoverCardTrigger asChild>{children}</HoverCardTrigger>
      <HoverCardContent align="start" className="w-64 p-0 overflow-hidden" data-testid={`integrator-contact-popover-${integrator?.integrator_id}`}>
        <div className="bg-gradient-to-r from-fuchsia-600 to-purple-600 px-3 py-2">
          <p className="text-[10px] font-medium text-fuchsia-100 uppercase tracking-wide">Contacto Principal</p>
          <p className="text-sm font-semibold text-white truncate">{integrator?.name}</p>
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
                  data-testid={`integrator-contact-negotiation-${integrator?.integrator_id}`}
                >
                  {neg || '—'}
                </span>
              </div>
            </div>
          )}
        </div>
      </HoverCardContent>
    </HoverCard>
  );
};

export default IntegratorContactHover;
