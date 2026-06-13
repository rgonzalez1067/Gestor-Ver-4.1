import { useState, useEffect, useMemo, useRef } from 'react';
import { UserCheck, X } from 'lucide-react';
import { Input } from './ui/input';
import { Button } from './ui/button';
import api from '../utils/api';

// Secciones del desplegable, agrupadas por equipo (orden y estilo del encabezado).
const TEAM_SECTIONS = [
  { key: 'direccion', label: 'Dirección', color: 'text-purple-600 bg-purple-50' },
  { key: 'ventas', label: 'Ventas', color: 'text-emerald-600 bg-emerald-50' },
  { key: 'implementacion', label: 'Implementación', color: 'text-blue-600 bg-blue-50' },
  { key: 'otros', label: 'Otros', color: 'text-slate-500 bg-slate-50' },
];

/**
 * Campo de email con autocomplete de usuarios internos MegaNexus.
 *
 * Props:
 *   value: string (email actual)
 *   onChange: (email) => void
 *   onRemove: () => void  (opcional — muestra botón X)
 *   placeholder: string
 *   testId: string (ej: 'notif-to-0')
 */
export const InternalEmailInput = ({ value, onChange, onRemove, onEnter, placeholder = 'correo@ejemplo.com — o escriba para buscar usuario', testId, profile }) => {
  const [users, setUsers] = useState([]);
  const [focused, setFocused] = useState(false);
  const [query, setQuery] = useState('');
  const blurTimeout = useRef(null);

  useEffect(() => {
    let cancelled = false;
    const url = profile ? `/users/internal-emails?profile=${encodeURIComponent(profile)}` : '/users/internal-emails';
    api.get(url)
      .then(r => { if (!cancelled) setUsers(r.data || []); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [profile]);

  const filtered = useMemo(() => {
    const q = (query || value || '').trim().toLowerCase();
    // Sin texto: mostrar TODA la lista (el contenedor tiene scroll). Antes se
    // limitaba a 8 y la lista se veía "corta" aunque hubiese más usuarios.
    if (!q) return users;
    return users.filter(u =>
      u.email.toLowerCase().includes(q) || (u.full_name || '').toLowerCase().includes(q)
    );
  }, [query, value, users]);

  // Agrupación por equipo para el desplegable (Dirección / Ventas / Implementación / Otros).
  const grouped = useMemo(() => {
    const teamOf = (u) => {
      const cargo = (u.cargo || '').trim().toLowerCase();
      const dept = (u.departamento || '').trim().toLowerCase();
      if (cargo === 'director' || dept === 'dirección' || dept === 'direccion') return 'direccion';
      if (dept.startsWith('ventas')) return 'ventas';
      if (dept === 'implementación' || dept === 'implementacion') return 'implementacion';
      return 'otros';
    };
    const g = { direccion: [], ventas: [], implementacion: [], otros: [] };
    filtered.forEach(u => { g[teamOf(u)].push(u); });
    return g;
  }, [filtered]);

  const handleChange = (e) => {
    onChange(e.target.value);
    setQuery(e.target.value);
  };
  const handlePick = (email) => {
    onChange(email);
    setFocused(false);
    setQuery('');
  };

  return (
    <div className="relative flex gap-2">
      <Input
        value={value}
        onChange={handleChange}
        onKeyDown={(e) => { if (e.key === 'Enter' && onEnter) { e.preventDefault(); onEnter(); } }}
        onFocus={() => { if (blurTimeout.current) clearTimeout(blurTimeout.current); setFocused(true); setQuery(value); }}
        onBlur={() => { blurTimeout.current = setTimeout(() => setFocused(false), 150); }}
        placeholder={placeholder}
        className="text-sm flex-1"
        data-testid={testId}
      />
      {onRemove && (
        <Button variant="ghost" size="sm" onClick={onRemove}>
          <X className="w-3.5 h-3.5 text-slate-400" />
        </Button>
      )}
      {focused && filtered.length > 0 && (
        <div className="absolute left-0 right-12 top-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg z-50 max-h-52 overflow-y-auto" data-testid={`${testId}-suggestions`}>
          {TEAM_SECTIONS.map(({ key, label, color }) => (
            grouped[key].length === 0 ? null : (
              <div key={key} data-testid={`${testId}-group-${key}`}>
                <div className={`sticky top-0 px-3 py-1.5 text-[10px] uppercase font-bold flex items-center gap-1 border-b border-slate-100 ${color}`}>
                  <UserCheck size={10} /> {label} ({grouped[key].length})
                </div>
                {grouped[key].map(u => (
                  <button
                    key={u.email}
                    type="button"
                    onMouseDown={(e) => { e.preventDefault(); handlePick(u.email); }}
                    className="w-full text-left px-3 py-2 hover:bg-blue-50 flex items-center gap-2 text-xs border-b border-slate-50"
                    data-testid={`${testId}-opt-${u.email}`}
                  >
                    <div className="flex-1">
                      <div className="font-medium text-slate-800">{u.full_name}</div>
                      <div className="text-[10px] text-slate-500 font-mono">{u.email}</div>
                    </div>
                    {u.cargo && <span className="text-[9px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">{u.cargo}</span>}
                  </button>
                ))}
              </div>
            )
          ))}
        </div>
      )}
    </div>
  );
};

export default InternalEmailInput;
