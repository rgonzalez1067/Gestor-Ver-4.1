// Constantes compartidas para el detalle de proyectos.
export const PHASES = ['Recibido', 'Configurado', 'Testeado', 'En Producción'];
export const STORE_PHASES = ['Recibido', 'Configurado', 'Testeado', 'En Producción'];

export const PHASE_COLORS = {
  'Notificado': 'bg-lime-100 text-lime-800',
  'Recibido': 'bg-sky-100 text-sky-800',
  'Configurado': 'bg-violet-100 text-violet-800',
  'Testeado': 'bg-cyan-100 text-cyan-800',
  'En Producción': 'bg-emerald-100 text-emerald-800',
};

// Variables que pueden insertarse en plantillas de notificación de proyectos.
// HOMOLOGADO con el entorno de Cotizaciones: incluye todas las variables de
// cotización (ventas, ejecutivo, despacho/equipos) además de las de proyecto.
export const ALL_TOKENS = [
  // Cliente
  'Nombre_Cliente', 'Nombre_Fantasia', 'Rif_Cliente', 'Contacto_Principal', 'Datos_Contacto', 'Telefono_Contacto', 'Email_Contacto', 'client_address',
  // Cotización / Ventas
  'Cotizacion_Nro', 'quote_number', 'quote_type', 'total_usd', 'Monto_Total', 'invoice_number', 'approved_date', 'abreviaturas_medios_pago', 'Banco_Patrocinador', 'company_name', 'sede_name', 'Nombre_Ejecutivo', 'Email_Ejecutivo',
  // Proyecto
  'Nro_Proyecto', 'project_number', 'Ticket_Nro', 'ticket_number', 'Tipo_Proyecto', 'Patrocinador', 'Fecha_Asignacion', 'Nombre_Sucursal', 'Cantidad_Cajas', 'Matriz_Sucursales', 'Matriz_MultiRif_Distribucion', 'Matriz_MultiRif_Avance', 'Matriz_Avance_Proyecto', 'Matriz_Avance_Proyecto_Con_Fecha',
  // Infraestructura
  'Servidor_Instalacion', 'Nombre_Implementador', 'Correo_Implementador', 'Telefono_Implementador', 'Integrador', 'Aplicativo_Integracion',
  // Hardware
  'Modelo_Seriales_POS', 'Modelo_Seriales_Equipos', 'Lista_VTID', 'Matriz_Bancos_Productos',
  // Despacho / Equipos / Reparación
  'Modelo_Equipo', 'Cantidad', 'Modelo_Pinpad', 'items_table', 'services_table', 'Direccion_Entrega', 'Lista_Seriales', 'lista_modelos_seriales', 'lista_equipos_seriales', 'modelos_resumen', 'almacen_custodia',
];
