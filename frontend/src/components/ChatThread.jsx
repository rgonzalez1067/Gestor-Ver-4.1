import { useEffect, useRef, useState, useCallback } from 'react';
import { Send, X, UserCircle2, Loader2, Trash2 } from 'lucide-react';
import { Dialog, DialogContent, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from './ui/alert-dialog';
import { toast } from 'sonner';
import api from '../utils/api';

/**
 * ChatThread — Vista de Conversación tipo WhatsApp (Iter48).
 *
 * Muestra el histórico completo de un hilo entre dos usuarios:
 *   - Burbujas alineadas a la derecha (mensajes propios, violeta) y
 *     a la izquierda (mensajes del otro, blancas con borde).
 *   - Orden cronológico ascendente, con autoscroll al final.
 *   - Caja de texto fija en la parte inferior; Enter para enviar
 *     (Shift+Enter agrega salto de línea).
 *   - Botón "Eliminar hilo" archiva la conversación SOLO para el usuario
 *     actual (el otro participante la sigue viendo).
 *
 * NOTA: No usa websockets — el envío re-fetcha el hilo al instante;
 * suficiente para una v1. Polling/SSE pueden agregarse después.
 */
function formatTime(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    const today = new Date();
    const sameDay = d.toDateString() === today.toDateString();
    if (sameDay) {
      return d.toLocaleTimeString('es-VE', { hour: '2-digit', minute: '2-digit' });
    }
    return d.toLocaleString('es-VE', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '';
  }
}

export function ChatThread({ conversationId, open, onOpenChange, onChanged }) {
  const [header, setHeader] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const scrollRef = useRef(null);
  const textareaRef = useRef(null);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      const el = scrollRef.current;
      if (el) el.scrollTop = el.scrollHeight;
    }, 30);
  }, []);

  const load = useCallback(async () => {
    if (!conversationId) return;
    try {
      const { data } = await api.get(`/inbox/conversations/${conversationId}/messages`);
      setHeader(data.conversation || null);
      setMessages(data.messages || []);
      scrollToBottom();
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || 'Error';
      toast.error(`No se pudo cargar el hilo: ${detail}`);
    } finally {
      setLoading(false);
    }
  }, [conversationId, scrollToBottom]);

  useEffect(() => {
    if (open && conversationId) {
      setLoading(true);
      setBody('');
      load();
      // foco en el input al abrir
      setTimeout(() => textareaRef.current?.focus(), 250);
    }
  }, [open, conversationId, load]);

  const handleSend = async () => {
    const text = body.trim();
    if (!text || sending) return;
    setSending(true);
    // Optimistic UI: agregar la burbuja inmediatamente
    const optimistic = {
      message_id: `tmp_${Date.now()}`,
      from_user_id: '__me__',
      from_user_name: 'Yo',
      body_plain: text,
      created_at: new Date().toISOString(),
      is_mine: true,
      _pending: true,
    };
    setMessages((prev) => [...prev, optimistic]);
    setBody('');
    scrollToBottom();
    try {
      const { data } = await api.post(
        `/inbox/conversations/${conversationId}/messages`,
        { body: text },
      );
      // Reemplazar el optimista por el real
      setMessages((prev) =>
        prev.map((m) => (m.message_id === optimistic.message_id ? data.message : m)),
      );
      scrollToBottom();
      onChanged?.();
    } catch (err) {
      // revertir
      setMessages((prev) => prev.filter((m) => m.message_id !== optimistic.message_id));
      const detail = err?.response?.data?.detail || err?.message || 'Error';
      toast.error(`No se pudo enviar: ${detail}`);
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleDelete = async () => {
    try {
      await api.delete(`/inbox/conversations/${conversationId}`);
      toast.success('Conversación archivada');
      setConfirmDelete(false);
      onOpenChange(false);
      onChanged?.();
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || 'Error';
      toast.error(`No se pudo archivar: ${detail}`);
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent
          className="max-w-2xl p-0 gap-0 overflow-hidden h-[85vh] flex flex-col"
          data-testid="chat-thread-dialog"
        >
          {/* DialogTitle accesible (oculto visualmente, leído por screen readers) */}
          <DialogTitle className="sr-only">
            {header?.subject ? `Conversación con ${header.other_user_name} · ${header.subject}` : 'Conversación'}
          </DialogTitle>
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-3 bg-gradient-to-r from-indigo-600 via-violet-600 to-fuchsia-600 text-white shrink-0">
            <div className="flex items-center gap-3 min-w-0">
              <div className="p-2 rounded-full bg-white/20">
                <UserCircle2 size={20} />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-bold truncate" data-testid="chat-other-name">
                  {header?.other_user_name || 'Conversación'}
                </p>
                <p className="text-[11px] text-indigo-100 truncate">
                  {header?.subject || ''}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setConfirmDelete(true)}
                className="text-white hover:bg-white/15 hover:text-white"
                data-testid="chat-delete-btn"
                title="Archivar conversación"
              >
                <Trash2 size={14} />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onOpenChange(false)}
                className="text-white hover:bg-white/15 hover:text-white"
                data-testid="chat-close-btn"
              >
                <X size={16} />
              </Button>
            </div>
          </div>

          {/* Mensajes */}
          <div
            ref={scrollRef}
            className="flex-1 overflow-y-auto px-5 py-4 bg-slate-50/60"
            style={{
              backgroundImage:
                'radial-gradient(circle at 20% 0%, rgba(139,92,246,0.06) 0px, transparent 220px), radial-gradient(circle at 80% 100%, rgba(219,39,119,0.05) 0px, transparent 260px)',
            }}
            data-testid="chat-messages-scroll"
          >
            {loading ? (
              <div className="flex items-center justify-center h-full text-slate-500 text-sm gap-2">
                <Loader2 size={14} className="animate-spin" />
                Cargando conversación…
              </div>
            ) : messages.length === 0 ? (
              <div className="text-center text-sm text-slate-400 italic py-12">
                Aún no hay mensajes. Envía el primero abajo.
              </div>
            ) : (
              <ul className="space-y-2" data-testid="chat-messages-list">
                {messages.map((m) => {
                  const mine = m.is_mine;
                  return (
                    <li
                      key={m.message_id}
                      className={`flex ${mine ? 'justify-end' : 'justify-start'}`}
                      data-testid={`chat-msg-${m.message_id}`}
                      data-mine={mine ? 'true' : 'false'}
                    >
                      <div
                        className={`max-w-[78%] rounded-2xl px-4 py-2 shadow-sm ${
                          mine
                            ? 'bg-violet-600 text-white rounded-br-sm'
                            : 'bg-white border border-slate-200 text-slate-800 rounded-bl-sm'
                        } ${m._pending ? 'opacity-70' : ''}`}
                      >
                        {!mine && (
                          <p className="text-[10px] font-bold text-violet-600 mb-0.5">
                            {m.from_user_name}
                          </p>
                        )}
                        <p
                          className="text-sm whitespace-pre-wrap break-words leading-snug"
                          data-testid={`chat-msg-body-${m.message_id}`}
                        >
                          {m.body_plain}
                        </p>
                        <p
                          className={`text-[10px] mt-1 ${
                            mine ? 'text-violet-100' : 'text-slate-400'
                          } text-right`}
                        >
                          {formatTime(m.created_at)}
                        </p>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {/* Caja de texto fija */}
          <div className="border-t border-slate-200 bg-white p-3 flex items-end gap-2 shrink-0">
            <Textarea
              ref={textareaRef}
              value={body}
              onChange={(e) => setBody(e.target.value.slice(0, 4000))}
              onKeyDown={handleKeyDown}
              placeholder="Escribe un mensaje… (Enter para enviar, Shift+Enter para nueva línea)"
              rows={2}
              maxLength={4000}
              className="resize-none text-sm flex-1"
              data-testid="chat-input-textarea"
            />
            <Button
              onClick={handleSend}
              disabled={!body.trim() || sending}
              className="bg-violet-600 hover:bg-violet-700 text-white shrink-0 self-stretch"
              data-testid="chat-send-btn"
            >
              {sending ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Send size={16} />
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Archivar conversación</AlertDialogTitle>
            <AlertDialogDescription>
              La conversación con <strong>{header?.other_user_name}</strong> desaparecerá de tu
              bandeja. El otro participante seguirá viéndola; si te responde, la conversación
              reaparecerá automáticamente.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="chat-delete-cancel">Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-rose-600 hover:bg-rose-700"
              data-testid="chat-delete-confirm"
            >
              Archivar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
