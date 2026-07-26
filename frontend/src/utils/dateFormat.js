// Formateo centralizado de fechas en zona horaria de Caracas (UTC-4).
// Los timestamps CON HORA se almacenan en UTC (con o sin offset) y SIEMPRE se
// muestran en hora de Caracas, sin importar la zona del navegador (auditoría).
// Las cadenas de SOLO FECHA (YYYY-MM-DD) se muestran tal cual, sin desplazar el
// día (no se les aplica conversión de zona horaria).

const TZ = 'America/Caracas';
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;
const HAS_TIME = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}/;

// Convierte a Date interpretando como UTC las cadenas con hora "naive"
// (sin offset ni Z). Devuelve null si es inválida.
export function parseUTC(input) {
  if (input === null || input === undefined || input === '') return null;
  if (input instanceof Date) return isNaN(input.getTime()) ? null : input;
  let s = String(input);
  if (HAS_TIME.test(s) && !/[zZ]$|[+-]\d{2}:?\d{2}$/.test(s)) {
    s = s.replace(' ', 'T') + 'Z';
  }
  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d;
}

// dd/mm/aaaa hh:mm a. m./p. m. (hora Caracas)
export function formatDateTime(input, fallback = '—') {
  const d = parseUTC(input);
  if (!d) return fallback;
  return d.toLocaleString('es-VE', {
    timeZone: TZ, day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: true,
  });
}

// dd/mm/aaaa — Para solo-fecha (YYYY-MM-DD) NO aplica conversión de zona
// horaria para evitar el corrimiento de día por medianoche UTC.
export function formatDate(input, fallback = '—') {
  if (typeof input === 'string' && DATE_ONLY.test(input.trim())) {
    const [y, m, day] = input.trim().split('-');
    return `${day}/${m}/${y}`;
  }
  const d = parseUTC(input);
  if (!d) return fallback;
  return d.toLocaleDateString('es-VE', {
    timeZone: TZ, day: '2-digit', month: '2-digit', year: 'numeric',
  });
}

// hh:mm a. m./p. m. (hora Caracas)
export function formatTime(input, fallback = '—') {
  const d = parseUTC(input);
  if (!d) return fallback;
  return d.toLocaleTimeString('es-VE', {
    timeZone: TZ, hour: '2-digit', minute: '2-digit', hour12: true,
  });
}
