# PRD — Gestor: Work Flow de Procesos Integrales

## Descripcion
Plataforma full-stack para gestion de cotizaciones, clientes, bancos, medios de pago, dispositivos, integradores y proyectos de implementacion.

## Stack Tecnologico
- **Backend**: FastAPI + MongoDB (motor_asyncio)
- **Frontend**: React + Shadcn/UI + Tailwind CSS
- **Auth**: JWT con bcrypt

## Funcionalidades Implementadas

### Modulo de Clientes
- CRUD completo con contactos CRM
- **Ficha Maestra Rediseñada** (2026-03-11): Layout 3 columnas
  - Bloque A (Identidad Legal): RIF, Nombre Juridico, Fantasia, Grupo Economico, Segmento (Pymes/Corporativo/Emprendedor/Mixto)
  - Bloque B (Ubicacion): Direccion Fiscal, Nombre Sucursal, Direccion Sucursal
  - Bloque C (Relacion Comercial): Ejecutivo Propietario, Fecha 1er Contacto, Tipo Contacto (radio: Fisico/Telefonico/Email), Categoria Comercial, Tipo Servicio (multi-select: VPOS/MPOS/Payment Gateway/Link de Pago)
  - Integrador (dropdown dinamico desde BD) + Aplicativo (condicionado al integrador)
  - Bitacora de Inicio (boton en modo edicion para registrar primer contacto)
- Sanitizacion automatica de RIF (sin guiones)
- Tabla responsiva con DropdownMenu de acciones
- OCR de RIF Digital
- Bitacora de seguimiento
- Importacion/Exportacion

### Modulo de Bancos y Entidades
- CRUD completo con logo upload
- Productos bancarios, Roadmap, Bitacora de Evolucion
- Consulta Global con Agrupamiento Dinamico
- Importacion masiva, Exportacion PDF, Matriz de certificacion

### Modulo de Integradores
- CRUD con importacion masiva (upsert)
- CRM tecnico con contactos, Bitacora de gestiones
- Historial de evolucion, Reporte agrupado
- **Endpoint dropdown** (2026-03-11): GET /api/integrators/dropdown para selectores ligeros

### Modulo de Cotizaciones
- Wizard multi-tipo (VPOS/PG, Equipos, Reparaciones)
- Flujo Administrativo Flexible con Protocolo de Excepcion
- Generacion de PDF con WeasyPrint + logo empresa
- PDF de equipos vinculado como anexo automatico
- Flujo de regularizacion (facturar/cobrar post-entrega)

### Modulo de Proyectos
- Generacion automatica desde cotizaciones
- Persistencia de Proceso Irregular
- Asignacion dinamica, Cambiar Estado rapido

### Otros
- Dashboard con KPIs
- **Tasa de Cambio BCV operativa** (2026-03-10): API exchangedyn.com + fallback dolarapi.com
- Gestion de usuarios con roles y permisos
- Menu lateral abatible

## Integraciones de Terceros
- **Resend**: Email (SIMULADO)
- **WeasyPrint**: PDF desde HTML
- **exchangedyn.com / dolarapi.com**: Tasa BCV
- **openpyxl/pandas**: Excel

## Backlog Priorizado

### P1 (Proximas)
- Verificacion de Email y Recuperacion de Contrasena
- Refactorizacion de Quotes.jsx (4200+ lineas)

### P2 (Futuras)
- Modulo de Reportes de ventas
- Logica de "Completado" en Roadmap de Bancos
- Refactorizacion de Integrators.jsx (1500+ lineas)
