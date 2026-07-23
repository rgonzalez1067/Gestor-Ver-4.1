// Perfilamiento multi-propósito de contactos de la ficha de clientes.
// Cada contacto puede tener 0..N propósitos activos. Los desplegables de cada
// módulo se filtran por el propósito correspondiente.

export const CONTACT_PURPOSES = [
  { key: 'taller', label: 'Cotizaciones de Taller' },
  { key: 'imple_equipos', label: 'Cotizaciones de Imple y Equipos' },
  { key: 'facturacion', label: 'Facturación' },
  { key: 'implementacion', label: 'Implementación' },
];

export const PURPOSE_LABELS = CONTACT_PURPOSES.reduce((acc, p) => {
  acc[p.key] = p.label;
  return acc;
}, {});

// Un contacto SIN perfilamiento (array vacío o ausente) se muestra en TODOS los
// módulos (compatibilidad con datos existentes; el perfilado es progresivo).
export function contactMatchesPurpose(contact, purposeKey) {
  const p = contact?.purposes;
  if (!Array.isArray(p) || p.length === 0) return true;
  return p.includes(purposeKey);
}

// Mapea la categoría de cotización al propósito requerido del contacto.
// repair -> Cotizaciones de Taller; implementation/equipment/fast_track -> Imple y Equipos.
export function purposeForQuoteCategory(quoteCategory) {
  return quoteCategory === 'repair' ? 'taller' : 'imple_equipos';
}
