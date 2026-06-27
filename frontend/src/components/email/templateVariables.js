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
    cat: 'Firma Institucional',
    icon: 'Building2',
    iconColor: 'text-emerald-600',
    vars: [
      { key: 'Firma_Notificacion_Global', label: 'Bloque de firma institucional (logo + datos del usuario en sesión)' },
    ],
  },
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
      { key: 'Matriz_MultiRif_Distribucion', label: 'Multi-RIF: distribución (RIF → sucursales → cajas)' },
      { key: 'Matriz_MultiRif_Avance', label: 'Multi-RIF: distribución + avance % (3 niveles)' },
      { key: 'Matriz_Avance_Proyecto', label: 'Matriz de Avance (Banco→Producto→Fases · % por fase · KPI Global)' },
      { key: 'Matriz_Avance_Proyecto_Con_Fecha', label: 'Matriz de Avance CON FECHA (% por fase + fecha en que se alcanzó)' },
      { key: 'Matriz_Seguimiento_Evolutiva', label: 'Matriz de Seguimiento Evolutiva (RIF/Tienda/Cajas × Banco→Producto→Fases · modular por banco)' },
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
  Matriz_Bancos_Productos: '<div style="font-family:Arial,sans-serif;font-size:12px;font-weight:600;color:#475569;margin:6px 0 8px;">Matriz de Bancos y Productos</div><div style="margin:0 0 18px;"><div style="font-family:Arial,sans-serif;font-size:13px;font-weight:700;color:#16324f;background:#dbeafe;padding:7px 12px;border-left:4px solid #1f3a5f;border-radius:4px;margin-bottom:6px;">Banco: Banco Mercantil</div><table style="border-collapse:collapse;width:auto;max-width:100%;font-family:Arial,sans-serif;"><thead><tr style="background:#1f3a5f;color:#fff;"><th style="padding:7px 10px;border:1px solid #d8dee9;text-align:left;font-size:12px;font-weight:700;">Producto / Servicio</th><th style="padding:7px 10px;border:1px solid #d8dee9;text-align:center;font-size:12px;font-weight:700;width:120px;">Cantidad</th></tr></thead><tbody><tr style="background:#f8fafc;"><td style="padding:6px 10px;border:1px solid #d8dee9;font-size:11px;color:#334155;">Tarjeta de Crédito/Débito</td><td style="padding:6px 10px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#334155;font-weight:700;">2</td></tr></tbody></table></div><div style="margin:0 0 18px;"><div style="font-family:Arial,sans-serif;font-size:13px;font-weight:700;color:#16324f;background:#dbeafe;padding:7px 12px;border-left:4px solid #1f3a5f;border-radius:4px;margin-bottom:6px;">Banco: Banesco</div><table style="border-collapse:collapse;width:auto;max-width:100%;font-family:Arial,sans-serif;"><thead><tr style="background:#1f3a5f;color:#fff;"><th style="padding:7px 10px;border:1px solid #d8dee9;text-align:left;font-size:12px;font-weight:700;">Producto / Servicio</th><th style="padding:7px 10px;border:1px solid #d8dee9;text-align:center;font-size:12px;font-weight:700;width:120px;">Cantidad</th></tr></thead><tbody><tr style="background:#f8fafc;"><td style="padding:6px 10px;border:1px solid #d8dee9;font-size:11px;color:#334155;">C2P o Débito Inmediato</td><td style="padding:6px 10px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#334155;font-weight:700;">1</td></tr></tbody></table></div>',
  Matriz_Sucursales: '<div style="font-family:Arial,sans-serif;font-size:12px;font-weight:600;color:#475569;margin:6px 0 8px;">Sucursales y Cajas</div><table style="border-collapse:collapse;width:auto;max-width:100%;font-family:Arial,sans-serif;"><thead><tr style="background:#1f3a5f;color:#fff;"><th style="padding:7px 10px;border:1px solid #d8dee9;text-align:left;font-size:12px;font-weight:700;">Sucursal</th><th style="padding:7px 10px;border:1px solid #d8dee9;text-align:center;font-size:12px;font-weight:700;width:130px;">Cantidad de Cajas</th></tr></thead><tbody><tr style="background:#f8fafc;"><td style="padding:6px 10px;border:1px solid #d8dee9;font-size:11px;color:#334155;">Sucursal Norte</td><td style="padding:6px 10px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#334155;font-weight:700;">5</td></tr><tr><td style="padding:6px 10px;border:1px solid #d8dee9;font-size:11px;color:#334155;">Sucursal Sur</td><td style="padding:6px 10px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#334155;font-weight:700;">3</td></tr><tr style="background:#e8eef5;font-weight:700;color:#1f3a5f;"><td style="padding:6px 10px;border:1px solid #d8dee9;font-size:11px;">Total</td><td style="padding:6px 10px;border:1px solid #d8dee9;text-align:center;font-size:11px;">8</td></tr></tbody></table>',
  Matriz_Avance_Proyecto: '<div style="margin:6px 0 10px;padding:8px 12px;border-radius:8px;background:#f0f6ff;border:1px solid #cfe0f5;font-family:Arial,sans-serif;font-size:13px;"><b>Avance Global del Proyecto:</b> <span style="color:#2563eb;font-weight:800;">62%</span></div><table style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif;"><thead><tr style="background:#1f3a5f;color:#fff;"><th style="padding:7px 10px;border:1px solid #d8dee9;text-align:left;font-size:12px;font-weight:700;">Banco / Producto</th><th style="padding:7px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:700;">Recibido</th><th style="padding:7px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:700;">Configurado</th><th style="padding:7px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:700;">Testeado</th><th style="padding:7px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:700;">En Producción</th></tr></thead><tbody><tr style="background:#e8eef5;font-weight:700;color:#1f3a5f;"><td colspan="5" style="padding:6px 10px;border:1px solid #d8dee9;font-size:12px;">Banco: Bancamiga</td></tr><tr><td style="padding:6px 10px 6px 22px;border:1px solid #d8dee9;font-size:11px;color:#334155;">Tarjeta de Crédito/Débito</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#16a34a;font-weight:700;">100%</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#d97706;font-weight:700;">50%</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#9ca3af;font-weight:400;">—</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#9ca3af;font-weight:400;">—</td></tr></tbody></table>',
  Matriz_Avance_Proyecto_Con_Fecha: '<div style="margin:6px 0 10px;padding:8px 12px;border-radius:8px;background:#f0f6ff;border:1px solid #cfe0f5;font-family:Arial,sans-serif;font-size:13px;"><b>Avance Global del Proyecto:</b> <span style="color:#2563eb;font-weight:800;">62%</span></div><table style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif;"><thead><tr style="background:#1f3a5f;color:#fff;"><th style="padding:7px 10px;border:1px solid #d8dee9;text-align:left;font-size:12px;font-weight:700;">Banco / Producto</th><th style="padding:7px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:700;">Recibido</th><th style="padding:7px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:700;">Configurado</th><th style="padding:7px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:700;">Testeado</th><th style="padding:7px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:700;">En Producción</th></tr></thead><tbody><tr style="background:#e8eef5;font-weight:700;color:#1f3a5f;"><td colspan="5" style="padding:6px 10px;border:1px solid #d8dee9;font-size:12px;">Banco: Bancamiga</td></tr><tr><td style="padding:6px 10px 6px 22px;border:1px solid #d8dee9;font-size:11px;color:#334155;">Tarjeta de Crédito/Débito</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#16a34a;font-weight:700;">100%<div style="font-size:10px;color:#64748b;font-weight:400;margin-top:2px;">10/06/2026</div></td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#d97706;font-weight:700;">50%<div style="font-size:10px;color:#64748b;font-weight:400;margin-top:2px;">11/06/2026</div></td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#9ca3af;font-weight:400;">—</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#9ca3af;font-weight:400;">—</td></tr></tbody></table>',
  items_table: '<table style="border-collapse:collapse;width:100%;font-size:12px;"><tr style="background:#f3f4f6"><th style="padding:6px;border:1px solid #ddd">Producto</th><th style="padding:6px;border:1px solid #ddd">Cantidad</th></tr><tr><td style="padding:6px;border:1px solid #ddd">Terminal POS</td><td style="padding:6px;border:1px solid #ddd;text-align:center">2</td></tr></table>',
  services_table: '<table style="border-collapse:collapse;width:100%;font-size:12px;"><tr style="background:#f3f4f6"><th style="padding:6px;border:1px solid #ddd">Servicio</th><th style="padding:6px;border:1px solid #ddd">Categoría</th></tr><tr><td style="padding:6px;border:1px solid #ddd">Setup Inicial</td><td style="padding:6px;border:1px solid #ddd;text-align:center">setup</td></tr></table>',
  Matriz_Seguimiento_Evolutiva: '<div style="font-family:Arial,sans-serif;font-size:12px;font-weight:600;color:#475569;margin:6px 0 8px;">Matriz de Seguimiento Evolutiva &middot; Todos los bancos <span style="font-weight:400;color:#94a3b8;">&mdash; formato celda: % avance / cajas estimadas / cajas recibidas</span></div><div style="margin:0 0 16px;"><div style="font-family:Arial,sans-serif;font-size:13px;font-weight:700;color:#16324f;background:#dbeafe;padding:7px 12px;border-left:4px solid #1f3a5f;border-radius:4px;margin-bottom:6px;">Banco A</div><table style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif;"><thead><tr style="background:#1f3a5f;color:#fff;"><th rowspan="2" style="padding:7px 10px;border:1px solid #d8dee9;text-align:left;font-size:11px;min-width:170px;vertical-align:middle;">Estructura del Cliente</th><th colspan="4" style="padding:7px 9px;border:1px solid #d8dee9;text-align:center;font-size:12px;font-weight:700;">Cr&eacute;dito</th><th colspan="4" style="padding:7px 9px;border:1px solid #d8dee9;text-align:center;font-size:12px;font-weight:700;">D&eacute;bito</th></tr><tr style="background:#2c5378;color:#fff;"><th style="padding:6px 8px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:600;">Fase I</th><th style="padding:6px 8px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:600;">Fase II</th><th style="padding:6px 8px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:600;">Fase III</th><th style="padding:6px 8px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:600;">Fase IV</th><th style="padding:6px 8px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:600;">Fase I</th><th style="padding:6px 8px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:600;">Fase II</th><th style="padding:6px 8px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:600;">Fase III</th><th style="padding:6px 8px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:600;">Fase IV</th></tr></thead><tbody><tr><td colspan="9" style="padding:6px 10px;border:1px solid #d8dee9;background:#e8eef5;color:#1f3a5f;font-weight:700;font-size:12px;">RIF: Comercio XYZ &mdash; RIF: J-00343075-7</td></tr><tr><td style="padding:6px 10px;border:1px solid #d8dee9;font-size:11px;color:#334155;"><span style="color:#94a3b8;">&#9492;&#9472;</span> Sucursal Caracas Centro</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#16a34a;font-weight:700;white-space:nowrap;">100% / 5 / 5</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#d97706;font-weight:700;white-space:nowrap;">40% / 5 / 2</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#64748b;font-weight:700;white-space:nowrap;">0% / 5 / 0</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#64748b;font-weight:700;white-space:nowrap;">0% / 5 / 0</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#16a34a;font-weight:700;white-space:nowrap;">100% / 5 / 5</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#64748b;font-weight:700;white-space:nowrap;">0% / 5 / 0</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#64748b;font-weight:700;white-space:nowrap;">0% / 5 / 0</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#64748b;font-weight:700;white-space:nowrap;">0% / 5 / 0</td></tr><tr><td style="padding:6px 10px;border:1px solid #d8dee9;font-size:11px;color:#334155;"><span style="color:#94a3b8;">&#9492;&#9472;</span> Sucursal El Hatillo</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#16a34a;font-weight:700;white-space:nowrap;">100% / 2 / 2</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#64748b;font-weight:700;white-space:nowrap;">0% / 2 / 0</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#64748b;font-weight:700;white-space:nowrap;">0% / 2 / 0</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#64748b;font-weight:700;white-space:nowrap;">0% / 2 / 0</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#16a34a;font-weight:700;white-space:nowrap;">100% / 2 / 2</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#16a34a;font-weight:700;white-space:nowrap;">100% / 2 / 2</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#d97706;font-weight:700;white-space:nowrap;">50% / 2 / 1</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#64748b;font-weight:700;white-space:nowrap;">0% / 2 / 0</td></tr></tbody></table><div style="font-family:Arial,sans-serif;font-size:10.5px;color:#64748b;margin:4px 0 0;text-align:left;"><strong>Estatus de las Fases:</strong> Fase I = Recibido &nbsp;|&nbsp; Fase II = Configurado &nbsp;|&nbsp; Fase III = Testeado &nbsp;|&nbsp; Fase IV = En Producci&oacute;n</div></div>',
};
