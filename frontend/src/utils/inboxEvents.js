// Eventos globales para sincronizar el estado de la bandeja (Centro de Mensajes)
// entre componentes desacoplados (WS, ChatThread, InboxCenter) y el banner global.
export const INBOX_CHANGED = 'inbox:changed';
export const INBOX_RELOAD_LIST = 'inbox:reload-list';

export const emitInboxChanged = () => {
  try {
    window.dispatchEvent(new CustomEvent(INBOX_CHANGED));
  } catch {
    /* noop */
  }
};

export const emitInboxReloadList = () => {
  try {
    window.dispatchEvent(new CustomEvent(INBOX_RELOAD_LIST));
  } catch {
    /* noop */
  }
};
