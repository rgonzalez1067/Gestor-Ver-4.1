// Filtrado dinámico de Integradores según Tipo de Proyecto.
// Regla de negocio basada en la "Modalidad de Integración" (campo
// `integration_modality`) del integrador. Centralizado para garantizar
// consistencia entre Cotizaciones y Proyectos Directos.
//
//  - Ecosistema Físico  (VPOS / MPOS / Fast Track / Multi-RIF):
//        REST, Stand Alone, Wrapper, MPOS
//  - Ecosistema Digital (Payment Gateway / Link de Pago):
//        Bridge PG, Web Link de Pago (No Universal / Universal),
//        TKN (No Universal / Universal), PG (No Universal / Universal)

const _norm = (s) => (s || '').toString().trim().toLowerCase().replace(/\s+/g, ' ');

export const PHYSICAL_MODALITIES = ['REST', 'Stand Alone', 'Wrapper', 'MPOS'];

export const DIGITAL_MODALITIES = [
  'Bridge PG',
  'Web Link de Pago Modalidad No Universal',
  'Web Link de Pago Modalidad Universal',
  'TKN No Universal',
  'TKN Universal',
  'PG Universal',
  'PG No universal',
];

const PHYSICAL_SET = new Set(PHYSICAL_MODALITIES.map(_norm));
const DIGITAL_SET = new Set(DIGITAL_MODALITIES.map(_norm));

// Tipos de Proyecto agrupados por ecosistema.
const PHYSICAL_TYPES = new Set(['VPOS', 'VPOS_MULTIRIF', 'MPOS', 'FAST_TRACK']);
const DIGITAL_TYPES = new Set(['GATEWAY', 'LINK_PAGO', 'LINK']);

// Devuelve un predicado (modalidad) => boolean según el Tipo de Proyecto.
// Si el tipo es desconocido / no seleccionado, no filtra (devuelve true).
export const integratorModalityMatch = (quoteType) => {
  const qt = (quoteType || '').toString().trim().toUpperCase();
  if (PHYSICAL_TYPES.has(qt)) return (m) => PHYSICAL_SET.has(_norm(m));
  if (DIGITAL_TYPES.has(qt)) return (m) => DIGITAL_SET.has(_norm(m));
  return () => true;
};
