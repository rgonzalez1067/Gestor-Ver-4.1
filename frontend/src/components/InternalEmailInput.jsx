import { useState, useEffect, useMemo, useRef } from 'react';
import { UserCheck, X } from 'lucide-react';
import { Input } from './ui/input';
import { Button } from './ui/button';
import api from '../utils/api';

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
    if (!q) return users.slice(0, 8);
    return users.filter(u =>
      u.email.toLowerCase().includes(q) || (u.full_name || '').toLowerCase().includes(q)
    ).slice(0, 8);
  }, [query, value, users]);

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
          <div className="px-3 py-1.5 text-[10px] uppercase text-slate-400 font-bold flex items-center gap-1 border-b border-slate-100">
            <UserCheck size={10} /> Usuarios internos MegaNexus
          </div>
          {filtered.map(u => (
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
      )}
    </div>
  );
};

export default InternalEmailInput;
