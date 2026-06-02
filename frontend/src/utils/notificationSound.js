// Sonido de notificación (beep corto) usando Web Audio API + estado de silencio persistido.
const MUTE_KEY = 'notif_sound_muted';

export const isNotifMuted = () => {
  try { return localStorage.getItem(MUTE_KEY) === '1'; } catch { return false; }
};

export const setNotifMuted = (val) => {
  try { localStorage.setItem(MUTE_KEY, val ? '1' : '0'); } catch { /* noop */ }
};

let audioCtx = null;

export function playNotifBeep() {
  if (isNotifMuted()) return;
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    audioCtx = audioCtx || new Ctx();
    if (audioCtx.state === 'suspended') audioCtx.resume();
    const now = audioCtx.currentTime;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = 'sine';
    // Dos tonos cortos ascendentes (estilo "ding-dong" sutil)
    osc.frequency.setValueAtTime(880, now);
    osc.frequency.setValueAtTime(1175, now + 0.12);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.28, now + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.33);
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start(now);
    osc.stop(now + 0.35);
  } catch {
    /* noop */
  }
}
