/**
 * Utility: Normalización fiscal de RIF (Venezuela).
 *
 * Espejo JavaScript del backend `services/rif_formatter.py`.
 * Regla: el RIF venezolano tiene 1 letra (J/V/E/G/P/C) + 9 dígitos.
 * Si el cuerpo numérico tiene menos de 9 dígitos, se rellena con ceros
 * a la izquierda. Preserva la letra inicial y el dígito verificador si
 * está separado por guión.
 *
 *   "V12345"      → "V-000012345"
 *   "V-12345"     → "V-000012345"
 *   "V123456789"  → "V-123456789"
 *   "V-1234567-8" → "V-001234567-8"
 *   "N/A"         → "N/A"
 *   "" / null     → ""
 *
 * Esta función debe usarse SOLO al renderizar el RIF al usuario final
 * (pantallas, tablas, PDFs). NO debe usarse al guardar o buscar en BD.
 */
const PLACEHOLDERS = new Set(['N/A', 'NA', '-', '—', 'SIN RIF', 'SIN_RIF', 'NO APLICA', 'NOAPLICA']);
const RIF_LETTERS = new Set(['J', 'V', 'E', 'G', 'P', 'C']);

export function formatRif(rif) {
  if (rif === null || rif === undefined) return '';
  const s = String(rif).trim();
  if (!s) return '';
  if (PLACEHOLDERS.has(s.toUpperCase())) return 'NO APLICA';

  let letter = '';
  let rest = s;
  const first = s[0].toUpperCase();
  if (RIF_LETTERS.has(first)) {
    letter = first;
    rest = s.slice(1).replace(/^-+/, '');
  }

  let verifier = '';
  if (rest.includes('-')) {
    const parts = rest.split('-');
    const last = parts[parts.length - 1];
    if (/^\d$/.test(last)) {
      verifier = last;
      rest = parts.slice(0, -1).join('-');
    }
  }

  const digits = rest.replace(/\D/g, '');
  if (!digits) return s; // no hay dígitos a formatear

  const padded = digits.length < 9 ? digits.padStart(9, '0') : digits;

  if (letter && verifier) return `${letter}-${padded}-${verifier}`;
  if (letter) return `${letter}-${padded}`;
  if (verifier) return `${padded}-${verifier}`;
  return padded;
}

export default formatRif;
