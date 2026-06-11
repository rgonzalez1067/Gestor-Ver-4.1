// =============================================================================
// FUENTE ÚNICA DE VERDAD del catálogo de variables de plantillas de correo.
//
// Este archivo se consume EXCLUSIVAMENTE en AMBOS editores de plantillas:
//   - /app/frontend/src/components/EmailTemplatesEditor.jsx  (Configuración / Cotizaciones)
//   - /app/frontend/src/components/projects/TemplatesAdminDialog.jsx  (Proyectos)
//
// Cualquier variable nueva debe agregarse SOLO aquí para garantizar paridad
// absoluta entre ambos paneles (homologación solicitada por el usuario).
// =============================================================================
import { Building2, CreditCard, Users, Server, Package, Box } from 'lucide-react';

// Mapa de iconos (renderizado por nombre para soportar ambos componentes).
export const VARIABLE_ICON_MAP = { Building2, CreditCard, Users, Server, Package, Box };

// Catálogo unificado de categorías y variables. `key` = token, `label` = descripción.
export const VARIABLE_CATEGORIES = [
  {
    cat: 'Cliente',
    icon: 'Building2',
    iconColor: 'text-blue-500',
    vars: [
      { key: 'Nombre_Cliente', label: 'Razón social del cliente' },
      { key: 'Nombre_Fantasia', label: 'Nombre de fantasía del cliente' },
      { key: 'Rif_Cliente', label: 'RIF del cliente' },
      { key: 'Contacto_Principal', label: 'Nombre del contacto' },
      { key: 'Datos_Contacto', label: 'Contacto + Tel + Email' },
      { key: 'Telefono_Contacto', label: 'Teléfono del contacto' },
      { key: 'Email_Contacto', label: 'Correo del contacto' },
      { key: 'client_name', label: 'Nombre del cliente (alias)' },
      { key: 'client_rif', label: 'RIF del cliente (alias)' },
      { key: 'client_address', label: 'Dirección del cliente' },
    ],
  },
  {
    cat: 'Financiero (Ventas)',
    icon: 'CreditCard',
    iconColor: 'text-violet-500',
    vars: [
      { key: 'Cotizacion_Nro', label: 'Número de cotización' },
      { key: 'quote_number', label: 'Número de cotización (alias)' },
      { key: 'nro_cotizacion', label: 'Nro. cotización (reparación)' },
      { key: 'quote_type', label: 'Tipo de cotización' },
      { key: 'total_usd', label: 'Total en USD' },
      { key: 'Monto_Total', label: 'Monto total USD (equipos)' },
      { key: 'invoice_number', label: 'Número de factura' },
      { key: 'Referencia_Factura', label: 'Referencia de factura (equipos)' },
      { key: 'approved_date', label: 'Fecha de aprobación' },
      { key: 'abreviaturas_medios_pago', label: 'Medios de pago (abreviaturas /)' },
      { key: 'Banco_Patrocinador', label: 'Banco patrocinador' },
      { key: 'sede_name', label: 'Sede (PYME / CORP)' },
      { key: 'company_name', label: 'Nombre de la empresa' },
      { key: 'items_table', label: 'Tabla HTML de productos' },
      { key: 'services_table', label: 'Tabla de servicios' },
      { key: 'Direccion_Entrega', label: 'Dirección de entrega' },
    ],
  },
  {
    cat: 'Ejecutivo',
    icon: 'Users',
    iconColor: 'text-emerald-500',
    vars: [
      { key: 'Nombre_Ejecutivo', label: 'Nombre del ejecutivo' },
      { key: 'Email_Ejecutivo', label: 'Correo del ejecutivo' },
      { key: 'contacto_cliente', label: 'Contacto del cliente' },
    ],
  },
  {
    cat: 'Implementación (Técnico)',
    icon: 'Server',
    iconColor: 'text-amber-500',
    vars: [
      { key: 'Servidor_Instalacion', label: 'Servidor asignado' },
      { key: 'Lista_VTID', label: 'Lista de VTIDs' },
      { key: 'Modelo_Seriales_POS', label: 'Tabla de POS/Pinpad' },
      { key: 'Modelo_Seriales_Equipos', label: 'Tabla de equipos' },
      { key: 'Nombre_Implementador', label: 'Implementador asignado' },
      { key: 'Correo_Implementador', label: 'Correo del implementador' },
      { key: 'Telefono_Implementador', label: 'Teléfono del implementador' },
      { key: 'Integrador', label: 'Nombre del integrador' },
      { key: 'Aplicativo_Integracion', label: 'App de integración' },
      { key: 'Nombre_Sucursal', label: 'Sucursal(es)' },
      { key: 'Cantidad_Cajas', label: 'Cantidad de cajas' },
      { key: 'Matriz_Bancos_Productos', label: 'Tabla de bancos y productos' },
      { key: 'Matriz_Sucursales', label: 'Tabla de sucursales / cajas' },
      { key: 'Patrocinador', label: 'Patrocinador (banco/procesador o cliente)' },
      { key: 'project_number', label: 'Nro. de proyecto' },
      { key: 'Nro_Proyecto', label: 'Nro. de proyecto (alias)' },
      { key: 'Estado_Proyecto', label: 'Estado actual del proyecto' },
      { key: 'Tipo_Proyecto', label: 'Tipo de implementación' },
      { key: 'Fecha_Asignacion', label: 'Fecha de asignación' },
      { key: 'Ticket_Nro', label: 'Nro. de ticket (se carga al desbloquear)' },
      { key: 'ticket_number', label: 'Nro. de ticket (alias)' },
      { key: 'integrator_name', label: 'Integrador (alias)' },
      { key: 'pinpad_model', label: 'Modelo de pinpad' },
      { key: 'Modelo_Pinpad', label: 'Modelo de pinpad (alias)' },
    ],
  },
  {
    cat: 'Despacho / Reparación / Equipos',
    icon: 'Box',
    iconColor: 'text-rose-500',
    vars: [
      { key: 'Modelo_Equipo', label: 'Modelo de POS / PINPAD' },
      { key: 'Cantidad', label: 'Cantidad de equipos' },
      { key: 'Lista_Seriales', label: 'Lista de seriales preasignados' },
      { key: 'lista_modelos_seriales', label: 'Lista de modelos y seriales (HTML)' },
      { key: 'lista_equipos_seriales', label: 'Lista de equipos y seriales (HTML)' },
      { key: 'modelos_resumen', label: 'Resumen de modelos' },
      { key: 'almacen_custodia', label: 'Almacén de custodia' },
    ],
  },
  {
    cat: 'Nuevos Productos',
    icon: 'Package',
    iconColor: 'text-cyan-500',
    vars: [
      { key: 'nombre_producto', label: 'Nombre del Producto' },
      { key: 'nombre_banco', label: 'Banco' },
      { key: 'fase_actual', label: 'Fase actual (anterior)' },
      { key: 'nueva_fase', label: 'Nueva fase' },
      { key: 'dias_fase_saliente', label: 'Días en la fase saliente' },
      { key: 'dias_totales_proyecto', label: 'Días totales del proyecto' },
      { key: 'responsable_fase_entrante', label: 'Responsable de la fase entrante' },
      { key: 'tipo_evento', label: 'Tipo de evento (Creación / Cambio de fase)' },
    ],
  },
];

// HTML de ejemplo para variables de tipo TABLA/HTML (mini-preview por hover).
export const VARIABLE_PREVIEW_HTML = {
  Matriz_Bancos_Productos: '<table style="border-collapse:collapse;width:100%;font-size:12px;"><thead><tr style="background:#2c3e50;color:white;"><th style="padding:6px;border:1px solid #ddd;">Banco</th><th style="padding:6px;border:1px solid #ddd;">Producto / Servicio</th><th style="padding:6px;border:1px solid #ddd;text-align:center;">Cantidad</th></tr></thead><tbody><tr><td style="padding:6px;border:1px solid #ddd;">Banco Mercantil</td><td style="padding:6px;border:1px solid #ddd;">Tarjeta de Crédito/Débito</td><td style="padding:6px;border:1px solid #ddd;text-align:center;">2</td></tr><tr style="background:#f8f9fa;"><td style="padding:6px;border:1px solid #ddd;">Banesco</td><td style="padding:6px;border:1px solid #ddd;">C2P o Débito Inmediato</td><td style="padding:6px;border:1px solid #ddd;text-align:center;">1</td></tr></tbody></table>',
  Matriz_Sucursales: '<table style="border-collapse:collapse;width:100%;font-size:12px;"><thead><tr style="background:#2c3e50;color:white;"><th style="padding:6px;border:1px solid #ddd;">Sucursal</th><th style="padding:6px;border:1px solid #ddd;text-align:center;">Cantidad de Cajas</th></tr></thead><tbody><tr><td style="padding:6px;border:1px solid #ddd;">Sucursal Norte</td><td style="padding:6px;border:1px solid #ddd;text-align:center;">5</td></tr><tr style="background:#f8f9fa;"><td style="padding:6px;border:1px solid #ddd;">Sucursal Sur</td><td style="padding:6px;border:1px solid #ddd;text-align:center;">3</td></tr><tr style="background:#eef2f7;font-weight:bold;"><td style="padding:6px;border:1px solid #ddd;">Total</td><td style="padding:6px;border:1px solid #ddd;text-align:center;">8</td></tr></tbody></table>',
  items_table: '<table style="border-collapse:collapse;width:100%;font-size:12px;"><tr style="background:#f3f4f6"><th style="padding:6px;border:1px solid #ddd">Producto</th><th style="padding:6px;border:1px solid #ddd">Cantidad</th></tr><tr><td style="padding:6px;border:1px solid #ddd">Terminal POS</td><td style="padding:6px;border:1px solid #ddd;text-align:center">2</td></tr></table>',
  services_table: '<table style="border-collapse:collapse;width:100%;font-size:12px;"><tr style="background:#f3f4f6"><th style="padding:6px;border:1px solid #ddd">Servicio</th><th style="padding:6px;border:1px solid #ddd">Categoría</th></tr><tr><td style="padding:6px;border:1px solid #ddd">Setup Inicial</td><td style="padding:6px;border:1px solid #ddd;text-align:center">setup</td></tr></table>',
};
