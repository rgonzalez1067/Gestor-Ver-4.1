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
export const ALL_TOKENS = [
  'Nombre_Cliente', 'Rif_Cliente', 'Contacto_Principal', 'Datos_Contacto', 'Telefono_Contacto', 'Email_Contacto',
  'Nro_Proyecto', 'Ticket_Nro', 'Tipo_Proyecto', 'Fecha_Asignacion', 'Nombre_Sucursal', 'Cantidad_Cajas',
  'Servidor_Instalacion', 'Nombre_Implementador', 'Correo_Implementador', 'Integrador', 'Aplicativo_Integracion',
  'Modelo_Seriales_POS', 'Modelo_Seriales_Equipos', 'Lista_VTID', 'Matriz_Bancos_Productos',
];
