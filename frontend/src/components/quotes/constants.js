import { Monitor, Smartphone, Globe, Link, Building2 } from 'lucide-react';

export const QUOTE_TYPES = [
  { id: 'VPOS', name: 'VPOS (Cajas)', icon: Monitor, description: 'Puntos de venta físicos' },
  { id: 'VPOS_MULTIRIF', name: 'VPOS Multi-RIF', icon: Building2, description: 'Lote bancario para múltiples RIFs' },
  { id: 'MPOS', name: 'MPOS (Tablet/Móvil)', icon: Smartphone, description: 'Terminales móviles POS' },
  { id: 'FAST_TRACK', name: 'MPOS (Imple + POS)', icon: Smartphone, description: 'Equipos autogestionados Pyme' },
  { id: 'GATEWAY', name: 'Payment Gateway', icon: Globe, description: 'Pasarela de pagos' },
  { id: 'LINK_PAGO', name: 'Link de Pago', icon: Link, description: 'Pasarela + Link de Pago (anexo en PDF)' }
];

export const PRICING_MODELS = [
  { id: 'conventional', name: 'Modelo Convencional', description: 'Precios estándar' },
  { id: 'outsourcing', name: 'Modelo Outsourcing', description: 'Precios para tercerización' }
];

// Conceptos EXCLUSIVOS de Setup (Inversión Inicial)
// lockBancos: true = campo Bancos bloqueado para edición
// autoBancos: true = auto-calcular basado en medios de pago agregados
export const SETUP_CONCEPTS = [
  { name: 'Suscripción PDV/Banco', isDefault: true, type: 'setup', lockBancos: false, autoBancos: false, inheritBancos: true },
  { name: 'Configuración dispositivo (Pinpad o POS)', isDefault: true, type: 'setup', lockBancos: true, autoBancos: false },
  { name: 'Configuración PDV en MServer', isDefault: true, type: 'setup', lockBancos: true, autoBancos: false },
  { name: 'Configuración Medio de Pago / Banco en MServer, por PDV', isDefault: true, type: 'setup', lockBancos: false, autoBancos: true }
];

// Recurrentes Básicos (obligatorios) - incluye conceptos pre-relacionados con Setup
// lockBancos: true = campo Bancos bloqueado en 1 (cobro unitario por PDV)
export const RECURRING_BASIC_CONCEPTS = [
  { name: 'Derecho de uso de plataforma MServer por PDV', isDefault: true, type: 'recurring_basic', lockBancos: true, autoTariff: { ceiling: 8, perUnit: 2 } },
  { name: 'Derecho de uso de plataforma MServer por PDV / Banco', isDefault: true, type: 'recurring_basic', inheritBancos: true }
];

// Otros Recurrentes - lockBancos: true para mostrar N/A
export const RECURRING_OTHER_CONCEPTS = [
  { name: 'Comunicación Backend (SSL Público o VPN, APN, etc.)', isDefault: true, type: 'recurring_other', lockBancos: true },
  { name: 'Procesamiento (HSM, Server, DC, etc.)', isDefault: true, type: 'recurring_other', lockBancos: true, autoTariff: { ceiling: 6, perUnit: 2 } }
];

// Colores de estado
export const STATUS_COLORS = {
  'Borrador': 'bg-slate-100 text-slate-700',
  'draft': 'bg-slate-100 text-slate-700',
  'Enviada': 'bg-blue-100 text-blue-700',
  'Emitida': 'bg-blue-100 text-blue-700',
  'Aprobada': 'bg-green-100 text-green-700',
  'Reparada': 'bg-cyan-100 text-cyan-700',
  'Configurada': 'bg-indigo-100 text-indigo-700',
  'Facturada': 'bg-purple-100 text-purple-700',
  'Pagada': 'bg-emerald-100 text-emerald-700',
  'Entregada': 'bg-teal-100 text-teal-700',
  'Enviada a Imple': 'bg-amber-100 text-amber-700',
  'En Implementación': 'bg-amber-100 text-amber-700',
  'Completada': 'bg-emerald-100 text-emerald-700'
};

// Mapeo de nombres de estado
export const STATUS_DISPLAY_NAMES = {
  'draft': 'Borrador',
  'Borrador': 'Borrador',
  'Enviada': 'Enviada',
  'Emitida': 'Emitida',
  'Aprobada': 'Aprobada',
  'Reparada': 'Reparada',
  'Configurada': 'Configurada',
  'Facturada': 'Facturada',
  'Pagada': 'Pagada',
  'Entregada': 'Entregada',
  'Enviada a Imple': 'Enviada a Imple',
  'En Implementación': 'En Implementación',
  'Completada': 'Completada'
};

// Categorías de cotización
export const QUOTE_CATEGORY_LABELS = {
  'implementation': 'Implementación',
  'equipment': 'Equipos',
  'repair': 'Reparaciones',
  'fast_track': 'MPOS (Imple + POS)'
};

// Etiquetas de acciones
export const ACTION_LABELS = {
  'approve': 'Aprobación',
  'repair-complete': 'Marcar como Reparada',
  'configure': 'Marcar como Configurada',
  'invoice': 'Factura / Proforma',
  'collect': 'Cobranza',
  'deliver': 'Entregar',
  'send-to-client': 'Enviar al Cliente',
  'send-to-implementation': 'Enviar a Implementación',
};
