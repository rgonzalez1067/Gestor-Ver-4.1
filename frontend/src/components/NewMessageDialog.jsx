import { useState, useEffect, useMemo } from 'react';
import { Send, X, Search, User as UserIcon, Loader2, Check } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import { toast } from 'sonner';
import api from '../utils/api';

/**
 * Modal de composición de mensajes user-to-user del Centro de Mensajes (Iter46).
 *
 * - Multi-destinatario (chips removibles + buscador de usuarios activos).
 * - Asunto (≤200 caracteres).
 * - Cuerpo texto plano estilo WhatsApp (≤4000 caracteres), saltos de línea
 *   se preservan en el receptor vía `<pre style="white-space:pre-wrap">`.
 * - Sin adjuntos en esta versión (se podría agregar luego).
 */
export function NewMessageDialog({ open, onOpenChange, onSent, initialData }) {
  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(true);
  const [selected, setSelected] = useState([]); // [{user_id, full_name, email}]
  const [search, setSearch] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);
  const [currentUserId, setCurrentUserId] = useState('');

  useEffect(() => {
    if (!open) return;
    setSubject(initialData?.subject || '');
    setBody(initialData?.body || '');
    setSelected(initialData?.recipients || []);
    setSearch('');
    try {
      const u = JSON.parse(localStorage.getItem('user') || '{}');
      setCurrentUserId(u.user_id || '');
    } catch { /* noop */ }
    (async () => {
      setUsersLoading(true);
      try {
        const { data } = await api.get('/auth/users');
        setUsers(Array.isArray(data) ? data : []);
      } catch {
        toast.error('No se pudo cargar la lista de usuarios');
      } finally {
        setUsersLoading(false);
      }
    })();
  }, [open, initialData]);

  const availableUsers = useMemo(() => {
    const selectedIds = new Set(selected.map((s) => s.user_id));
    const q = search.trim().toLowerCase();
    return users
      .filter((u) => u.user_id !== currentUserId) // no enviarse a sí mismo
      .filter((u) => !selectedIds.has(u.user_id))
      .filter((u) => {
        if (!q) return true;
        const hay = [u.full_name, u.email, u.cargo, u.departamento]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();
        return hay.includes(q);
      })
      .slice(0, 30);
  }, [users, selected, search, currentUserId]);

  const addRecipient = (u) => {
    setSelected((prev) => [...prev, u]);
    setSearch('');
  };
  const removeRecipient = (uid) => {
    setSelected((prev) => prev.filter((u) => u.user_id !== uid));
  };

  const canSend = selected.length > 0 && subject.trim().length > 0 && body.trim().length > 0;

  const handleSend = async () => {
    if (!canSend || sending) return;
    setSending(true);
    try {
      const { data } = await api.post('/inbox/send', {
        recipient_user_ids: selected.map((s) => s.user_id),
        subject: subject.trim(),
        body: body.trim(),
      });
      toast.success(
        `Mensaje enviado a ${data.delivered_count} destinatario${data.delivered_count === 1 ? '' : 's'}`,
      );
      onOpenChange(false);
      onSent?.();
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || 'Error';
      toast.error(`No se pudo enviar: ${detail}`);
    } finally {
      setSending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl" data-testid="new-message-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Send size={18} className="text-violet-600" />
            Nuevo mensaje
          </DialogTitle>
          <DialogDescription>
            El mensaje aparecerá en el Centro de Mensajes de cada destinatario.
            No se envía por correo electrónico.
          </DialogDescription>
        </DialogHeader>

        {/* Destinatarios */}
        <div className="space-y-2">
          <label className="text-xs font-bold uppercase text-slate-500 tracking-wider">
            Para ({selected.length})
          </label>
          <div className="flex flex-wrap gap-1.5 min-h-[36px] p-2 rounded-md border border-slate-200 bg-slate-50/40">
            {selected.length === 0 && (
              <span className="text-xs text-slate-400 italic px-1 py-1">Sin destinatarios seleccionados</span>
            )}
            {selected.map((u) => (
              <Badge
                key={u.user_id}
                variant="secondary"
                className="bg-violet-100 text-violet-800 hover:bg-violet-200 pl-2.5 pr-1 py-1 gap-1"
                data-testid={`recipient-chip-${u.user_id}`}
              >
                <UserIcon size={12} />
                <span className="text-xs">{u.full_name || u.email}</span>
                <button
                  type="button"
                  onClick={() => removeRecipient(u.user_id)}
                  className="ml-0.5 rounded-full hover:bg-violet-300/60 p-0.5"
                  aria-label={`Quitar ${u.full_name}`}
                >
                  <X size={12} />
                </button>
              </Badge>
            ))}
          </div>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar por nombre, cargo o departamento…"
              className="pl-9 h-9 text-sm"
              data-testid="recipient-search-input"
            />
          </div>
          {search.trim() && (
            <div className="max-h-44 overflow-y-auto rounded-md border border-slate-200 bg-white shadow-sm">
              {usersLoading ? (
                <div className="px-3 py-3 text-xs text-slate-500 flex items-center gap-2">
                  <Loader2 size={12} className="animate-spin" /> Cargando usuarios…
                </div>
              ) : availableUsers.length === 0 ? (
                <div className="px-3 py-3 text-xs text-slate-400 italic">Sin coincidencias</div>
              ) : (
                <ul className="divide-y divide-slate-100" data-testid="recipient-suggestions">
                  {availableUsers.map((u) => (
                    <li key={u.user_id}>
                      <button
                        type="button"
                        onClick={() => addRecipient(u)}
                        className="w-full text-left px-3 py-2 hover:bg-violet-50 flex items-center gap-2"
                        data-testid={`recipient-option-${u.user_id}`}
                      >
                        <UserIcon size={14} className="text-slate-400" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-slate-800 truncate">{u.full_name || u.email}</p>
                          <p className="text-[10px] text-slate-400 truncate">
                            {[u.cargo, u.departamento].filter(Boolean).join(' · ') || u.email}
                          </p>
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        {/* Asunto */}
        <div className="space-y-1.5">
          <label className="text-xs font-bold uppercase text-slate-500 tracking-wider">Asunto</label>
          <Input
            value={subject}
            onChange={(e) => setSubject(e.target.value.slice(0, 200))}
            placeholder="Asunto del mensaje"
            maxLength={200}
            className="h-9 text-sm"
            data-testid="new-message-subject"
          />
          <div className="text-[10px] text-slate-400 text-right">{subject.length}/200</div>
        </div>

        {/* Cuerpo */}
        <div className="space-y-1.5">
          <label className="text-xs font-bold uppercase text-slate-500 tracking-wider">Mensaje</label>
          <Textarea
            value={body}
            onChange={(e) => setBody(e.target.value.slice(0, 4000))}
            placeholder="Escribe tu mensaje…"
            maxLength={4000}
            rows={6}
            className="text-sm font-normal resize-y"
            data-testid="new-message-body"
          />
          <div className="text-[10px] text-slate-400 text-right">{body.length}/4000</div>
        </div>

        {/* Acciones */}
        <div className="flex justify-end gap-2 pt-2">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={sending}
            data-testid="new-message-cancel"
          >
            Cancelar
          </Button>
          <Button
            onClick={handleSend}
            disabled={!canSend || sending}
            className="bg-violet-600 hover:bg-violet-700 text-white"
            data-testid="new-message-send"
          >
            {sending ? (
              <Loader2 size={14} className="mr-2 animate-spin" />
            ) : (
              <Check size={14} className="mr-2" />
            )}
            Enviar
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
